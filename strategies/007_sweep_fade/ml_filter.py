"""ML filter for Strategy 007: Sweep & Fade.

Builds a LightGBM classifier on 20+ L2 features computed at each sweep signal.
Uses walk-forward (day-by-day) validation.
Saves trained model + calibrated threshold to lgbm_filter.pkl.
Saves walk-forward results to ml_results.json.

Usage:
    python3 strategies/007_sweep_fade/ml_filter.py
"""

import sys
import json
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, load_depth_raw, precompute_dom_series,
    build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, SESSION_DEFS, _get_conn,
)

STRATEGY_DIR = Path(__file__).resolve().parent
MODEL_PATH = STRATEGY_DIR / "lgbm_filter.pkl"
RESULTS_PATH = STRATEGY_DIR / "ml_results.json"

LGBM_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "num_leaves": 15,
    "min_data_in_leaf": 10,
    "learning_rate": 0.05,
    "n_estimators": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
}

TARGET_DAILY_TRADES = 7   # midpoint of 5-10
RTH_SESSION_NAMES = {"NYOpen", "MidDay", "PowerHour", "Close"}

FEATURE_COLS = [
    # Core sweep
    "sweep_tick_count", "sweep_volume_total", "sweep_pts",
    "sweep_duration_ms", "absorption_ratio", "tick_velocity",
    # Delta context
    "delta_pre_sweep_20t", "delta_post_sweep_5t", "delta_exhaustion",
    # Quote
    "bid_ask_imbalance", "bid_ask_imbalance_pre", "bid_ask_imbalance_delta",
    "spread_pts", "bid_size_at_signal", "ask_size_at_signal",
    # DOM
    "dom_available", "dom_bid_total", "dom_ask_total",
    "dom_imbalance", "dom_top_bid_size", "dom_top_ask_size",
    # Bar context
    "prior_bar_delta", "prior_cvd_slope", "bar_volume_vs_20bar_avg",
    "is_rth", "direction_long", "minutes_into_session",
]


# ---------------------------------------------------------------------------
# Quote features via DuckDB ASOF JOIN (bulk, efficient)
# ---------------------------------------------------------------------------

def _compute_quote_features_bulk(signal_tss):
    """Return per-signal quote features using DuckDB ASOF JOIN.

    Avoids loading 68M rows into pandas — queries point-in-time.
    """
    conn = _get_conn()
    sigs = pd.DataFrame({
        "signal_ts": pd.to_datetime(signal_tss),
        "signal_ts_10s": [pd.Timestamp(ts) - pd.Timedelta(seconds=10) for ts in signal_tss],
    })
    conn.register("_sig_times", sigs)

    # Quote at signal moment
    q_at = conn.execute("""
        SELECT
            s.signal_ts                                              AS ts,
            COALESCE(q.bid_size, 0)                                  AS bid_size,
            COALESCE(q.ask_size, 0)                                  AS ask_size,
            COALESCE(q.ask - q.bid, 0)                               AS spread_pts
        FROM _sig_times s
        ASOF JOIN nq_quotes q ON s.signal_ts >= q.ts_utc
        ORDER BY s.signal_ts
    """).fetchdf()

    # Quote 10 s before signal
    q_pre = conn.execute("""
        SELECT
            s.signal_ts                                              AS ts,
            COALESCE(q.bid_size, 0)                                  AS bid_size_pre,
            COALESCE(q.ask_size, 0)                                  AS ask_size_pre
        FROM _sig_times s
        ASOF JOIN nq_quotes q ON s.signal_ts_10s >= q.ts_utc
        ORDER BY s.signal_ts
    """).fetchdf()

    conn.close()

    result = q_at.merge(q_pre, on="ts", how="left").fillna(0)

    def _imb(bs, as_):
        total = bs + as_
        return np.where(total > 0, (bs - as_) / total, 0.0)

    result["bid_ask_imbalance"] = _imb(result["bid_size"], result["ask_size"])
    result["bid_ask_imbalance_pre"] = _imb(result["bid_size_pre"], result["ask_size_pre"])
    result["bid_ask_imbalance_delta"] = (
        result["bid_ask_imbalance"] - result["bid_ask_imbalance_pre"]
    )
    result.rename(
        columns={"bid_size": "bid_size_at_signal", "ask_size": "ask_size_at_signal"},
        inplace=True,
    )
    return result  # indexed 0..N-1, aligned with signals


# ---------------------------------------------------------------------------
# Per-signal feature extraction (tick + DOM + bar)
# ---------------------------------------------------------------------------

def _ts_ns(ts):
    """Convert pandas Timestamp / numpy datetime64 to int64 nanoseconds."""
    if isinstance(ts, (int, np.integer)):
        return int(ts)
    return pd.Timestamp(ts).value


def _extract_tick_features(sig, df_ticks, tick_ts_ns):
    """Delta-based features from raw tick stream."""
    sweep_start_ns = _ts_ns(sig["sweep_start_ts"])
    sweep_end_ns = _ts_ns(sig["sweep_end_ts"])

    sw_i = int(np.searchsorted(tick_ts_ns, sweep_start_ns, side="left"))
    sw_j = int(np.searchsorted(tick_ts_ns, sweep_end_ns, side="right"))

    sweep_ticks = int(sig.get("sweep_ticks", max(sw_j - sw_i, 1)))
    sweep_volume = float(sig.get("sweep_volume_total", sig.get("sweep_volume", 1)))
    sweep_pts = float(sig.get("sweep_pts", 0))
    sweep_dur_ms = float(sig.get("sweep_duration_ms", 1))

    absorption_ratio = sweep_pts / max(sweep_volume, 1)
    tick_velocity = sweep_ticks / max(sweep_dur_ms / 1000, 0.001)

    # Pre-sweep delta (20 ticks before sweep)
    pre_i = max(0, sw_i - 20)
    delta_pre = float(df_ticks.iloc[pre_i:sw_i]["delta"].sum()) if sw_i > 0 else 0.0

    # Post-sweep delta (first 5 ticks after sweep)
    post_j = min(len(df_ticks), sw_j + 5)
    delta_post = float(df_ticks.iloc[sw_j:post_j]["delta"].sum()) if sw_j < len(df_ticks) else 0.0

    # Delta exhaustion: abs(last-5 sweep ticks delta) / abs(first-5 sweep ticks delta)
    n_sw = sw_j - sw_i
    if n_sw >= 10:
        first5 = abs(float(df_ticks.iloc[sw_i:sw_i + 5]["delta"].sum()))
        last5 = abs(float(df_ticks.iloc[sw_j - 5:sw_j]["delta"].sum()))
        delta_exhaustion = last5 / max(first5, 0.001)
    else:
        delta_exhaustion = 1.0

    return {
        "sweep_tick_count": sweep_ticks,
        "sweep_volume_total": sweep_volume,
        "sweep_pts": sweep_pts,
        "sweep_duration_ms": sweep_dur_ms,
        "absorption_ratio": absorption_ratio,
        "tick_velocity": tick_velocity,
        "delta_pre_sweep_20t": delta_pre,
        "delta_post_sweep_5t": delta_post,
        "delta_exhaustion": delta_exhaustion,
    }


def _extract_dom_features(sig, df_dom, dom_ts_ns):
    """DOM features from pre-aggregated per-snapshot series."""
    base = {
        "dom_available": 0,
        "dom_bid_total": 0.0, "dom_ask_total": 0.0,
        "dom_imbalance": 0.0,
        "dom_top_bid_size": 0.0, "dom_top_ask_size": 0.0,
    }
    if df_dom.empty or len(dom_ts_ns) == 0:
        return base

    signal_ns = _ts_ns(sig["ts"])
    idx = int(np.searchsorted(dom_ts_ns, signal_ns, side="right")) - 1
    if idx < 0:
        return base

    dom_ts = dom_ts_ns[idx]
    if abs(int(dom_ts) - signal_ns) > 5 * 10**9:   # more than 5 s away
        return base

    row = df_dom.iloc[idx]
    bid_t = float(row.get("dom_bid_total", 0))
    ask_t = float(row.get("dom_ask_total", 0))
    total = bid_t + ask_t
    imb = (bid_t - ask_t) / total if total > 0 else 0.0

    return {
        "dom_available": 1,
        "dom_bid_total": bid_t,
        "dom_ask_total": ask_t,
        "dom_imbalance": imb,
        "dom_top_bid_size": float(row.get("dom_top_bid_size", 0)),
        "dom_top_ask_size": float(row.get("dom_top_ask_size", 0)),
    }


def _extract_bar_features(sig, bars, bar_ts_ns):
    """Bar-context features: prior delta, CVD slope, relative volume, session."""
    sweep_start_ns = _ts_ns(sig["sweep_start_ts"])
    bar_idx = int(np.searchsorted(bar_ts_ns, sweep_start_ns, side="right")) - 1
    bar_idx = max(0, min(bar_idx, len(bars) - 1))

    row = bars.iloc[bar_idx]
    prior_bar_delta = float(row.get("bar_delta", 0))

    # CVD slope over last 5 bars
    if bar_idx >= 4:
        cvd_slice = bars.iloc[bar_idx - 4: bar_idx + 1]["cumulative_delta"].values
        prior_cvd_slope = float(cvd_slice[-1] - cvd_slice[0])
    else:
        prior_cvd_slope = 0.0

    # Relative volume vs 20-bar average
    if bar_idx >= 19:
        avg_vol = bars.iloc[bar_idx - 19: bar_idx + 1]["volume"].mean()
        bar_vol_vs_avg = float(row["volume"]) / max(float(avg_vol), 1.0)
    else:
        bar_vol_vs_avg = 1.0

    session = str(row.get("session", "Unknown"))
    is_rth = 1 if session in RTH_SESSION_NAMES else 0
    direction_long = 1 if sig["direction"] == "long" else 0

    minutes_into_session = 0
    if "minute_of_day" in bars.columns:
        mod = int(row.get("minute_of_day", 0))
        for sname, sstart, send, _ in SESSION_DEFS:
            if sname == session:
                minutes_into_session = max(0, mod - sstart)
                break

    return {
        "prior_bar_delta": prior_bar_delta,
        "prior_cvd_slope": prior_cvd_slope,
        "bar_volume_vs_20bar_avg": bar_vol_vs_avg,
        "is_rth": is_rth,
        "direction_long": direction_long,
        "minutes_into_session": minutes_into_session,
    }


# ---------------------------------------------------------------------------
# Feature matrix builder
# ---------------------------------------------------------------------------

def build_feature_matrix(signals, trades_list, df_ticks, df_dom, bars):
    """Build feature matrix aligned to trades (1 row per traded signal).

    Returns DataFrame with FEATURE_COLS + ['signal_ts', 'trade_won', 'pnl_ticks'].
    """
    if not signals or not trades_list:
        return pd.DataFrame()

    # Align signals → trades by entry_ts (str representation of signal ts)
    trade_by_entry = {}
    for t in trades_list:
        trade_by_entry[t["entry_ts"]] = t

    # Pre-index tick timestamps as int64 for fast searchsorted
    tick_ts_ns = df_ticks["ts_utc"].values.astype("int64")
    dom_ts_ns = df_dom["ts_utc"].values.astype("int64") if not df_dom.empty else np.array([], dtype="int64")
    bar_ts_ns = bars["ts_utc"].values.astype("int64")

    # Bulk quote features (single DuckDB pass for all signals)
    signal_tss = [sig["ts"] for sig in signals]
    print(f"Computing quote features for {len(signals)} signals via ASOF JOIN...")
    quote_feats = _compute_quote_features_bulk(signal_tss)

    rows = []
    missing_trades = 0
    for i, sig in enumerate(signals):
        trade_key = str(sig["ts"])
        trade = trade_by_entry.get(trade_key)
        if trade is None:
            missing_trades += 1
            continue

        feats = {}
        feats.update(_extract_tick_features(sig, df_ticks, tick_ts_ns))
        feats.update(_extract_dom_features(sig, df_dom, dom_ts_ns))
        feats.update(_extract_bar_features(sig, bars, bar_ts_ns))

        # Quote features from bulk result (aligned by index)
        if i < len(quote_feats):
            qrow = quote_feats.iloc[i]
            feats["bid_ask_imbalance"] = float(qrow.get("bid_ask_imbalance", 0))
            feats["bid_ask_imbalance_pre"] = float(qrow.get("bid_ask_imbalance_pre", 0))
            feats["bid_ask_imbalance_delta"] = float(qrow.get("bid_ask_imbalance_delta", 0))
            feats["spread_pts"] = float(qrow.get("spread_pts", 0))
            feats["bid_size_at_signal"] = float(qrow.get("bid_size_at_signal", 0))
            feats["ask_size_at_signal"] = float(qrow.get("ask_size_at_signal", 0))
        else:
            for col in ["bid_ask_imbalance", "bid_ask_imbalance_pre",
                        "bid_ask_imbalance_delta", "spread_pts",
                        "bid_size_at_signal", "ask_size_at_signal"]:
                feats[col] = 0.0

        feats["signal_ts"] = sig["ts"]
        feats["trade_won"] = 1 if trade["pnl_ticks"] > 0 else 0
        feats["pnl_ticks"] = float(trade["pnl_ticks"])

        rows.append(feats)

    if missing_trades > 0:
        print(f"  {missing_trades} signals had no matching trade (end-of-data); skipped")

    df = pd.DataFrame(rows)
    # Ensure all feature columns exist
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    return df


# ---------------------------------------------------------------------------
# Walk-forward training
# ---------------------------------------------------------------------------

def _find_threshold(test_probs_by_day, target=TARGET_DAILY_TRADES):
    """Find ML score threshold that gives ~target signals/RTH day."""
    all_probs = np.concatenate([np.array(p) for p in test_probs_by_day.values() if p])
    if len(all_probs) == 0:
        return 0.5

    n_days = len(test_probs_by_day)
    best_thresh = 0.5
    best_diff = float("inf")

    for thresh in np.arange(0.05, 0.98, 0.01):
        counts = [sum(1 for p in probs if p >= thresh) for probs in test_probs_by_day.values()]
        avg = np.mean(counts) if counts else 0
        diff = abs(avg - target)
        if diff < best_diff:
            best_diff = diff
            best_thresh = thresh

    return float(best_thresh)


def train_walk_forward(feature_df):
    """Walk-forward LightGBM training: train on prior days, test on each next day.

    Returns: (final_model, threshold, results_dict)
    """
    if feature_df.empty or "trade_won" not in feature_df.columns:
        return None, 0.5, {"error": "empty feature matrix"}

    feature_df = feature_df.copy()
    feature_df["date"] = pd.to_datetime(feature_df["signal_ts"]).dt.date
    dates = sorted(feature_df["date"].unique())
    print(f"Training data: {len(feature_df)} samples across {len(dates)} days: {dates}")
    print(f"Base win rate: {feature_df['trade_won'].mean():.1%}")

    if len(dates) < 2:
        print("Need ≥2 days for walk-forward. Training final model on all data.")
        X = feature_df[FEATURE_COLS].fillna(0)
        y = feature_df["trade_won"]
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(X, y)
        return model, 0.5, {"error": "only 1 day of data", "total_samples": len(feature_df)}

    fold_results = []
    all_test_probs_by_day = {}
    all_test_probs = []
    all_test_labels = []

    for test_date in dates[1:]:
        train_df = feature_df[feature_df["date"] < test_date]
        test_df = feature_df[feature_df["date"] == test_date]

        if len(train_df) < 10 or len(test_df) < 3:
            print(f"  Fold {test_date}: skipped (train={len(train_df)}, test={len(test_df)})")
            continue

        X_train = train_df[FEATURE_COLS].fillna(0)
        y_train = train_df["trade_won"]
        X_test = test_df[FEATURE_COLS].fillna(0)
        y_test = test_df["trade_won"]

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(X_train, y_train)

        probs = model.predict_proba(X_test)[:, 1]
        try:
            auc = float(roc_auc_score(y_test, probs)) if len(set(y_test)) > 1 else 0.5
        except Exception:
            auc = 0.5

        all_test_probs_by_day[test_date] = probs.tolist()
        all_test_probs.extend(probs.tolist())
        all_test_labels.extend(y_test.tolist())

        fold_results.append({
            "test_date": str(test_date),
            "train_days": len(dates[:dates.index(test_date)]),
            "train_samples": int(len(train_df)),
            "test_samples": int(len(test_df)),
            "auc": round(auc, 3),
            "base_wr": round(float(y_test.mean()), 3),
        })
        print(
            f"  Fold {test_date}: AUC={auc:.3f}, "
            f"WR={y_test.mean():.1%}, "
            f"n_train={len(train_df)}, n_test={len(test_df)}"
        )

    # Overall AUC on all test predictions
    overall_auc = 0.5
    if len(set(all_test_labels)) > 1:
        try:
            overall_auc = float(roc_auc_score(all_test_labels, all_test_probs))
        except Exception:
            pass

    # Calibrated threshold
    threshold = _find_threshold(all_test_probs_by_day)
    print(f"Calibrated threshold={threshold:.3f} for ~{TARGET_DAILY_TRADES} signals/RTH day")

    # Train final model on ALL data
    X_all = feature_df[FEATURE_COLS].fillna(0)
    y_all = feature_df["trade_won"]
    final_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    final_model.fit(X_all, y_all)

    # Feature importance
    fi = dict(zip(FEATURE_COLS, final_model.feature_importances_.tolist()))
    top_features = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:10]

    results = {
        "folds": fold_results,
        "overall_auc": round(overall_auc, 3),
        "threshold": round(threshold, 3),
        "target_daily_trades": TARGET_DAILY_TRADES,
        "total_samples": int(len(feature_df)),
        "base_win_rate": round(float(feature_df["trade_won"].mean()), 3),
        "top_features": [{"feature": f, "importance": round(imp, 1)} for f, imp in top_features],
    }

    return final_model, threshold, results


# ---------------------------------------------------------------------------
# Scoring function (called from backtest.py at inference time)
# ---------------------------------------------------------------------------

def score_signals(signals, model, threshold, feature_cols, df_ticks, df_dom, bars):
    """Score signals with trained model; return those above threshold.

    This function is imported lazily by backtest.py when use_ml_filter=True.
    """
    if not signals:
        return []

    tick_ts_ns = df_ticks["ts_utc"].values.astype("int64")
    dom_ts_ns = df_dom["ts_utc"].values.astype("int64") if not df_dom.empty else np.array([], dtype="int64")
    bar_ts_ns = bars["ts_utc"].values.astype("int64")

    signal_tss = [sig["ts"] for sig in signals]
    quote_feats = _compute_quote_features_bulk(signal_tss)

    rows = []
    for i, sig in enumerate(signals):
        feats = {}
        feats.update(_extract_tick_features(sig, df_ticks, tick_ts_ns))
        feats.update(_extract_dom_features(sig, df_dom, dom_ts_ns))
        feats.update(_extract_bar_features(sig, bars, bar_ts_ns))

        if i < len(quote_feats):
            qrow = quote_feats.iloc[i]
            feats["bid_ask_imbalance"] = float(qrow.get("bid_ask_imbalance", 0))
            feats["bid_ask_imbalance_pre"] = float(qrow.get("bid_ask_imbalance_pre", 0))
            feats["bid_ask_imbalance_delta"] = float(qrow.get("bid_ask_imbalance_delta", 0))
            feats["spread_pts"] = float(qrow.get("spread_pts", 0))
            feats["bid_size_at_signal"] = float(qrow.get("bid_size_at_signal", 0))
            feats["ask_size_at_signal"] = float(qrow.get("ask_size_at_signal", 0))
        else:
            for col in ["bid_ask_imbalance", "bid_ask_imbalance_pre",
                        "bid_ask_imbalance_delta", "spread_pts",
                        "bid_size_at_signal", "ask_size_at_signal"]:
                feats[col] = 0.0

        rows.append(feats)

    X = pd.DataFrame(rows)[feature_cols].fillna(0)
    scores = model.predict_proba(X)[:, 1]

    filtered = [sig for sig, score in zip(signals, scores) if score >= threshold]
    return filtered


# ---------------------------------------------------------------------------
# Main: train and save
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("007 Sweep Fade — ML Filter Training")
    print("=" * 60)

    # --- Load data ---
    print("\n[1/5] Loading trades...")
    df_ticks = load_trades()
    print(f"  Loaded {len(df_ticks):,} ticks")

    print("[2/5] Building 1-min bars...")
    bars = build_1min_bars_with_delta(df_ticks)
    print(f"  {len(bars)} bars total")

    print("[3/5] Loading DOM depth and pre-computing aggregates...")
    df_depth = load_depth_raw()
    df_dom = precompute_dom_series(df_depth)
    print(f"  {len(df_depth):,} raw DOM rows → {len(df_dom):,} aggregated snapshots")

    # --- Run unfiltered backtest to get signals + labels ---
    print("[4/5] Running unfiltered sweep detection...")
    # Import at runtime to avoid circular dependency
    import importlib.util
    spec = importlib.util.spec_from_file_location("backtest_007", STRATEGY_DIR / "backtest.py")
    bt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt)

    from pipeline.data_loader import filter_sessions
    all_sessions_params = bt.PARAMS.copy()
    all_sessions_params["session_filter"] = None   # all sessions for more training data

    signals_all = bt.find_signals(df_ticks, bars, all_sessions_params)
    print(f"  Unfiltered signals: {len(signals_all)}")

    if len(signals_all) < 20:
        print("  Too few signals — trying relaxed params for feature matrix.")
        relaxed = all_sessions_params.copy()
        relaxed["min_consecutive"] = max(5, int(relaxed["min_consecutive"]) - 3)
        relaxed["min_sweep_volume"] = max(10, float(relaxed["min_sweep_volume"]) * 0.5)
        relaxed["max_sweep_seconds"] = 10
        signals_all = bt.find_signals(df_ticks, bars, relaxed)
        print(f"  Relaxed signals: {len(signals_all)}")

    trades_all = bt.simulate_trades(signals_all, bars, all_sessions_params)
    print(f"  Simulated trades: {len(trades_all)}")

    if not trades_all:
        print("ERROR: No trades to train on. Exiting.")
        return

    wins = sum(1 for t in trades_all if t["pnl_ticks"] > 0)
    print(f"  Win rate: {wins}/{len(trades_all)} = {wins/len(trades_all):.1%}")

    # --- Build feature matrix ---
    print("[5/5] Building feature matrix...")
    feature_df = build_feature_matrix(signals_all, trades_all, df_ticks, df_dom, bars)
    print(f"  Feature matrix: {feature_df.shape}")

    if feature_df.empty:
        print("ERROR: Empty feature matrix. Exiting.")
        return

    # --- Walk-forward training ---
    print("\nTraining walk-forward LightGBM...")
    model, threshold, results = train_walk_forward(feature_df)

    if model is None:
        print("Training failed.")
        return

    # --- Evaluate filtered vs unfiltered on full dataset ---
    print("\nEvaluating filtered backtest on full dataset...")
    filtered_sigs = score_signals(signals_all, model, threshold, FEATURE_COLS, df_ticks, df_dom, bars)
    filtered_trades = bt.simulate_trades(filtered_sigs, bars, all_sessions_params)

    unfiltered_m = bt.compute_metrics(trades_all)
    filtered_m = bt.compute_metrics(filtered_trades)

    results["backtest_comparison"] = {
        "unfiltered": {
            "total_signals": len(signals_all),
            "total_trades": len(trades_all),
            **unfiltered_m,
        },
        "filtered": {
            "total_signals": len(filtered_sigs),
            "total_trades": len(filtered_trades),
            **filtered_m,
        },
    }

    # Signals per day
    if filtered_sigs:
        sig_dates = [pd.Timestamp(s["ts"]).date() for s in filtered_sigs]
        from collections import Counter
        day_counts = Counter(sig_dates)
        results["filtered_signals_per_day"] = {str(k): v for k, v in sorted(day_counts.items())}

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Walk-forward AUC:   {results['overall_auc']:.3f}")
    print(f"ML threshold:        {threshold:.3f}")
    print(f"Unfiltered: {len(trades_all)} trades, PF={unfiltered_m['profit_factor']}, WR={unfiltered_m['win_rate']}%")
    print(f"Filtered:   {len(filtered_trades)} trades, PF={filtered_m['profit_factor']}, WR={filtered_m['win_rate']}%")
    print()
    if "top_features" in results:
        print("Top features:")
        for f in results["top_features"]:
            print(f"  {f['feature']:35s} importance={f['importance']:.0f}")
    if "filtered_signals_per_day" in results:
        print("\nFiltered signals/day:", results["filtered_signals_per_day"])

    # --- Save model ---
    pkg = {
        "model": model,
        "threshold": threshold,
        "feature_cols": FEATURE_COLS,
        "lgbm_params": LGBM_PARAMS,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pkg, f)
    print(f"\nModel saved to: {MODEL_PATH}")

    # --- Save results ---
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
