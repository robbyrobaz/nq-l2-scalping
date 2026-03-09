"""LightGBM filter for Strategy 007."""

from __future__ import annotations

import json
import pickle
import sys
import importlib.util
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import RTH_SESSIONS, filter_sessions, tag_sessions
from pipeline.strategy_cache import bars_with_cvd, dom_series, quotes, trades_with_nbbo

BACKTEST_PATH = Path(__file__).resolve().with_name("backtest.py")
_spec = importlib.util.spec_from_file_location("s007_backtest", BACKTEST_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
PARAMS = _mod.PARAMS
_build_specs = _mod._build_specs
build_signal_frame = _mod.build_signal_frame


MODEL_PATH = Path(__file__).resolve().with_name("lgbm_filter.pkl")
RESULTS_PATH = Path(__file__).resolve().with_name("ml_results.json")


def build_dataset(params=None) -> pd.DataFrame:
    params = {**PARAMS, **(params or {})}
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter", RTH_SESSIONS)).reset_index(drop=True)
    bars = filter_sessions(bars_with_cvd(), sessions=params.get("session_filter", RTH_SESSIONS)).reset_index(drop=True)
    q = filter_sessions(quotes(), sessions=params.get("session_filter", RTH_SESSIONS)).reset_index(drop=True)
    dom = filter_sessions(dom_series(), sessions=params.get("session_filter", RTH_SESSIONS)).reset_index(drop=True)

    signals = build_signal_frame(ticks, params)
    specs = _build_specs(ticks, params)
    trades = pd.DataFrame(iter_trade_specs(specs, ticks))
    if signals.empty or trades.empty:
        return pd.DataFrame()

    signals["signal_ts"] = pd.to_datetime(signals["signal_ts"], utc=True)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    bars["ts_utc"] = pd.to_datetime(bars["ts_utc"], utc=True)
    q["ts_utc"] = pd.to_datetime(q["ts_utc"], utc=True)
    if not dom.empty:
        dom["ts_utc"] = pd.to_datetime(dom["ts_utc"], utc=True)

    features = signals.copy()
    features = pd.merge_asof(features.sort_values("signal_ts"), q[["ts_utc", "bid_size", "ask_size"]].sort_values("ts_utc"), left_on="signal_ts", right_on="ts_utc", direction="backward")
    features["bid_ask_imbalance"] = (features["bid_size"] - features["ask_size"]) / (features["bid_size"] + features["ask_size"] + 1.0)

    if dom.empty:
        features["dom_imbalance"] = 0.0
    else:
        features = pd.merge_asof(features.sort_values("signal_ts"), dom[["ts_utc", "dom_imbalance"]].sort_values("ts_utc"), left_on="signal_ts", right_on="ts_utc", direction="backward")
        features["dom_imbalance"] = features["dom_imbalance"].fillna(0.0)

    bars["cvd_slope"] = bars["cvd"].diff(3).fillna(0.0)
    features = pd.merge_asof(features.sort_values("signal_ts"), bars[["ts_utc", "bar_delta", "cvd_slope"]].sort_values("ts_utc"), left_on="signal_ts", right_on="ts_utc", direction="backward")
    features.rename(columns={"bar_delta": "delta_pre_sweep"}, inplace=True)
    features = tag_sessions(features, ts_col="signal_ts")

    labeled = features.merge(trades[["entry_ts", "direction", "pnl_ticks"]], left_on=["entry_ts", "direction"], right_on=["entry_ts", "direction"], how="inner")
    if labeled.empty:
        return pd.DataFrame()
    labeled["trade_won"] = (labeled["pnl_ticks"] > 0).astype(int)
    labeled["session"] = labeled["session"].astype("category")
    return labeled.sort_values("signal_ts").reset_index(drop=True)


def _pick_threshold(probabilities: np.ndarray, frame: pd.DataFrame) -> float:
    sessions = max(frame["signal_ts"].dt.date.nunique(), 1)
    best = 0.99
    best_score = float("inf")
    for threshold in np.arange(0.30, 0.996, 0.001):
        kept = int((probabilities >= threshold).sum())
        per_session = kept / sessions
        score = 0.0 if 5 <= per_session <= 10 else min(abs(per_session - 5), abs(per_session - 10)) + abs(per_session - 7.5)
        if score < best_score:
            best_score = score
            best = float(round(threshold, 2))
    return best


def train_ml_filter(params=None) -> dict:
    data = build_dataset(params=params)
    if data.empty or len(data) < 10:
        result = {"error": "Not enough labeled sweep signals to train filter."}
        RESULTS_PATH.write_text(json.dumps(result, indent=2))
        return result

    feature_cols = [
        "sweep_ticks",
        "sweep_volume",
        "sweep_pts",
        "sweep_duration_ms",
        "delta_pre_sweep",
        "bid_ask_imbalance",
        "dom_imbalance",
        "cvd_slope",
        "session",
    ]
    split_idx = max(int(len(data) * 0.6), 1)
    train_df = data.iloc[:split_idx].copy()
    test_df = data.iloc[split_idx:].copy()
    for frame in (train_df, test_df):
        frame["session"] = frame["session"].cat.codes

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=10,
        random_state=42,
    )
    model.fit(train_df[feature_cols], train_df["trade_won"])
    train_probs = model.predict_proba(train_df[feature_cols])[:, 1]
    threshold = _pick_threshold(train_probs, train_df)

    test_probs = model.predict_proba(test_df[feature_cols])[:, 1]
    test_df["prob"] = test_probs
    filtered = test_df[test_df["prob"] >= threshold].copy()

    baseline_trades = test_df[["entry_ts", "direction", "pnl_ticks"]].copy()
    filtered_trades = filtered[["entry_ts", "direction", "pnl_ticks"]].copy()
    baseline_metrics = compute_trade_metrics(baseline_trades.to_dict("records"))
    filtered_metrics = compute_trade_metrics(filtered_trades.to_dict("records"))

    sessions = max(test_df["signal_ts"].dt.date.nunique(), 1)
    report = {
        "threshold": threshold,
        "train_signals": int(len(train_df)),
        "test_signals": int(len(test_df)),
        "baseline": {
            "metrics": baseline_metrics,
            "trades_per_day": round(len(baseline_trades) / sessions, 2),
        },
        "filtered": {
            "metrics": filtered_metrics,
            "trades_per_day": round(len(filtered_trades) / sessions, 2),
        },
    }

    with MODEL_PATH.open("wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols, "threshold": threshold}, f)
    RESULTS_PATH.write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    print(json.dumps(train_ml_filter({"session_filter": RTH_SESSIONS}), indent=2))
