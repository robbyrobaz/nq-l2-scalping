"""Strategy 007: Sweep & Fade

Identifies rapid same-side trade sweeps on the raw tick stream and fades them.
Tick-level sweep detection: N consecutive same-side aggressor ticks within T seconds.
Optional LightGBM ML filter for high-quality entries only.
"""

import sys
import json
import importlib.util
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, compute_session_breakdown
)

# Default parameters — tight L2 sweep definition
PARAMS = {
    "min_consecutive": 10,      # 10+ consecutive same-side aggressor ticks
    "min_sweep_volume": 30,     # 30+ contracts total in sweep
    "max_sweep_seconds": 5,     # all within 5 seconds
    "min_sweep_pts": 1.0,       # sweep must cover >= 1 pt (4 ticks)
    "take_profit_ticks": 6,
    "stop_loss_ticks": 10,
    "session_filter": None,
}


def _resolve_sweep_params(params):
    min_consecutive = int(params.get('min_consecutive', params.get('sweep_tick_threshold', 8)))
    min_volume = float(params.get('min_sweep_volume', 20))
    max_seconds = float(params.get('max_sweep_seconds', params.get('sweep_time_seconds', 10)))
    min_sweep_pts = float(
        params.get(
            'min_sweep_pts',
            params.get('sweep_tick_threshold', 8) * NQ_TICK_SIZE,
        )
    )
    return min_consecutive, min_volume, max_seconds, min_sweep_pts


def find_tick_sweeps(df_trades, min_consecutive=8, min_volume=20, max_seconds=10, min_sweep_pts=1.0):
    """Walk the tick stream and emit qualifying same-side sweeps."""
    sweeps = []
    if df_trades.empty:
        return sweeps

    trades = df_trades.sort_values('ts_utc').reset_index(drop=True)
    current = None

    for row in trades.itertuples(index=False):
        side = row.side
        if side not in {'B', 'S'}:
            current = None
            continue

        if current is None:
            current = {
                'direction': side,
                'start_ts': row.ts_utc,
                'end_ts': row.ts_utc,
                'first_price': float(row.price),
                'last_price': float(row.price),
                'sweep_ticks': 1,
                'sweep_volume': float(row.size),
            }
            continue

        elapsed = (row.ts_utc - current['start_ts']).total_seconds()
        if side == current['direction'] and elapsed <= max_seconds:
            current['end_ts'] = row.ts_utc
            current['last_price'] = float(row.price)
            current['sweep_ticks'] += 1
            current['sweep_volume'] += float(row.size)
            continue

        sweep_pts = abs(current['last_price'] - current['first_price'])
        if (
            current['sweep_ticks'] >= min_consecutive and
            current['sweep_volume'] >= min_volume and
            sweep_pts >= min_sweep_pts
        ):
            sweeps.append({
                'direction': current['direction'],
                'start_ts': current['start_ts'],
                'end_ts': current['end_ts'],
                'sweep_ticks': current['sweep_ticks'],
                'sweep_volume': current['sweep_volume'],
                'sweep_pts': sweep_pts,
            })

        current = {
            'direction': side,
            'start_ts': row.ts_utc,
            'end_ts': row.ts_utc,
            'first_price': float(row.price),
            'last_price': float(row.price),
            'sweep_ticks': 1,
            'sweep_volume': float(row.size),
        }

    if current is not None:
        sweep_pts = abs(current['last_price'] - current['first_price'])
        if (
            current['sweep_ticks'] >= min_consecutive and
            current['sweep_volume'] >= min_volume and
            sweep_pts >= min_sweep_pts
        ):
            sweeps.append({
                'direction': current['direction'],
                'start_ts': current['start_ts'],
                'end_ts': current['end_ts'],
                'sweep_ticks': current['sweep_ticks'],
                'sweep_volume': current['sweep_volume'],
                'sweep_pts': sweep_pts,
            })

    return sweeps


def find_signals(df_trades, bars, params=PARAMS):
    """Fade a sweep on the first opposite-side aggressor after it ends."""
    signals = []
    if df_trades.empty or bars.empty:
        return signals

    min_consecutive, min_volume, max_seconds, min_sweep_pts = _resolve_sweep_params(params)
    sweeps = find_tick_sweeps(
        df_trades,
        min_consecutive=min_consecutive,
        min_volume=min_volume,
        max_seconds=max_seconds,
        min_sweep_pts=min_sweep_pts,
    )
    if not sweeps:
        return signals

    trades = df_trades.sort_values('ts_utc').reset_index(drop=True)
    bar_ts = bars['ts_utc'].to_numpy()
    trade_ts = trades['ts_utc'].to_numpy()

    search_idx = 0
    for sweep in sweeps:
        start_idx = np.searchsorted(trade_ts, sweep['end_ts'].to_datetime64(), side='right')
        search_idx = max(search_idx, int(start_idx))
        reversal = None
        while search_idx < len(trades):
            row = trades.iloc[search_idx]
            search_idx += 1
            if row['side'] not in {'B', 'S'}:
                continue
            if row['side'] != sweep['direction']:
                reversal = row
                break
        if reversal is None:
            continue

        bar_idx = np.searchsorted(bar_ts, reversal['ts_utc'].to_datetime64(), side='right') - 1
        if bar_idx < 0 or bar_idx >= len(bars):
            continue

        signals.append({
            'bar_idx': int(bar_idx),
            'ts': reversal['ts_utc'],
            'direction': 'short' if sweep['direction'] == 'B' else 'long',
            'entry_price': float(reversal['price']),
            'sweep_start_ts': sweep['start_ts'],
            'sweep_end_ts': sweep['end_ts'],
            'sweep_ticks': int(sweep['sweep_ticks']),
            'sweep_volume': float(sweep['sweep_volume']),
            'sweep_pts': float(sweep['sweep_pts']),
            'sweep_duration_ms': (sweep['end_ts'] - sweep['start_ts']).total_seconds() * 1000,
        })

    deduped = []
    last_bar_idx = -1
    for sig in signals:
        if sig['bar_idx'] == last_bar_idx:
            continue
        deduped.append(sig)
        last_bar_idx = sig['bar_idx']
    return deduped


def simulate_trades(signals, bars, params=PARAMS):
    """Simulate entries and exits using TP/SL in ticks."""
    tp = params['take_profit_ticks'] * NQ_TICK_SIZE
    sl = params['stop_loss_ticks'] * NQ_TICK_SIZE
    trades = []

    for sig in signals:
        idx = sig['bar_idx'] + 1  # Entry on next bar
        if idx >= len(bars):
            continue

        entry = sig['entry_price']
        direction = sig['direction']

        exited = False
        for j in range(idx + 1, len(bars)):
            bar = bars.iloc[j]
            if direction == 'long':
                if bar['low'] <= entry - sl:
                    exit_price = entry - sl
                    pnl_ticks = -params['stop_loss_ticks']
                    trades.append(_make_trade(sig, bar, exit_price, pnl_ticks))
                    exited = True
                    break
                if bar['high'] >= entry + tp:
                    exit_price = entry + tp
                    pnl_ticks = params['take_profit_ticks']
                    trades.append(_make_trade(sig, bar, exit_price, pnl_ticks))
                    exited = True
                    break
            else:
                if bar['high'] >= entry + sl:
                    exit_price = entry + sl
                    pnl_ticks = -params['stop_loss_ticks']
                    trades.append(_make_trade(sig, bar, exit_price, pnl_ticks))
                    exited = True
                    break
                if bar['low'] <= entry - tp:
                    exit_price = entry - tp
                    pnl_ticks = params['take_profit_ticks']
                    trades.append(_make_trade(sig, bar, exit_price, pnl_ticks))
                    exited = True
                    break

        if not exited:
            last = bars.iloc[-1]
            if direction == 'long':
                pnl_ticks = (last['close'] - entry) / NQ_TICK_SIZE
            else:
                pnl_ticks = (entry - last['close']) / NQ_TICK_SIZE
            trades.append(_make_trade(sig, last, last['close'], pnl_ticks))

    return trades


def _make_trade(sig, exit_bar, exit_price, pnl_ticks):
    return {
        'entry_ts': str(sig['ts']),
        'exit_ts': str(exit_bar['ts_utc']),
        'direction': sig['direction'],
        'entry_price': float(sig['entry_price']),
        'exit_price': float(exit_price),
        'pnl_ticks': float(pnl_ticks),
    }


def compute_metrics(trades):
    if not trades:
        return {
            'profit_factor': 0.0, 'sharpe': 0.0, 'win_rate': 0.0,
            'avg_winner_ticks': 0, 'avg_loser_ticks': 0,
            'total_trades': 0, 'net_pnl_usd': 0.0, 'max_drawdown_pct': 0.0,
        }

    pnls = [t['pnl_ticks'] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    gross_profit = sum(winners) if winners else 0
    gross_loss = abs(sum(losers)) if losers else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0

    net_pnl = sum(pnls)
    net_pnl_usd = pnl_mnq(net_pnl)

    arr = np.array(pnls)
    sharpe = (arr.mean() / arr.std() * np.sqrt(252)) if arr.std() > 0 else 0.0

    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = dd.max() / peak.max() * 100 if peak.max() > 0 else 0.0

    return {
        'profit_factor': round(pf, 2),
        'sharpe': round(float(sharpe), 2),
        'win_rate': round(len(winners) / len(pnls) * 100, 1),
        'avg_winner_ticks': round(float(np.mean(winners)), 1) if winners else 0,
        'avg_loser_ticks': round(float(np.mean(np.abs(losers))), 1) if losers else 0,
        'total_trades': len(pnls),
        'net_pnl_usd': round(net_pnl_usd, 2),
        'max_drawdown_pct': round(float(max_dd), 1),
    }


def _load_ml_filter_module():
    """Lazy-load ml_filter.py to avoid import-time side effects."""
    spec = importlib.util.spec_from_file_location(
        "ml_filter_007", Path(__file__).parent / "ml_filter.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(params=None, use_ml_filter=False):
    if params is None:
        params = PARAMS.copy()
    else:
        params = params.copy()

    print("Loading trades...")
    trades_df = load_trades()
    print(f"Building price bars from {len(trades_df)} ticks...")
    trades_df = filter_sessions(trades_df, sessions=params.get('session_filter'))
    bars = build_1min_bars_with_delta(trades_df)
    print(f"Filtered bars: {len(bars)}")

    print("Scanning for sweep/fade signals...")
    signals = find_signals(trades_df, bars, params)
    print(f"Signals found (unfiltered): {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['min_consecutive'] = max(4, int(relaxed.get('min_consecutive', 10)) - 2)
        relaxed['min_sweep_volume'] = max(10, float(relaxed.get('min_sweep_volume', 30)) * 0.75)
        relaxed['min_sweep_pts'] = max(0.5, float(relaxed.get('min_sweep_pts', 1.0)) - 0.5)
        signals = find_signals(trades_df, bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    # Unfiltered backtest
    unfiltered_trades = simulate_trades(signals, bars, params)
    unfiltered_metrics = compute_metrics(unfiltered_trades)
    print(f"Unfiltered trades: {len(unfiltered_trades)}, metrics: {unfiltered_metrics}")

    # ML filter (optional)
    filtered_trades = unfiltered_trades
    filtered_metrics = unfiltered_metrics
    ml_threshold = None

    if use_ml_filter:
        model_path = Path(__file__).parent / 'lgbm_filter.pkl'
        if not model_path.exists():
            print("WARNING: lgbm_filter.pkl not found — run ml_filter.py first. Skipping ML filter.")
        else:
            import pickle
            from pipeline.data_loader import load_depth_raw, precompute_dom_series
            print("Loading ML model and auxiliary data for scoring...")
            with open(model_path, 'rb') as f:
                pkg = pickle.load(f)
            model = pkg['model']
            ml_threshold = pkg['threshold']
            feature_cols = pkg['feature_cols']

            df_depth = load_depth_raw()
            df_dom = precompute_dom_series(df_depth)

            ml_mod = _load_ml_filter_module()
            filtered_signals = ml_mod.score_signals(
                signals, model, ml_threshold, feature_cols,
                trades_df, df_dom, bars,
            )
            print(f"ML filter: {len(signals)} → {len(filtered_signals)} signals (threshold={ml_threshold:.3f})")

            filtered_trades = simulate_trades(filtered_signals, bars, params)
            filtered_metrics = compute_metrics(filtered_trades)
            print(f"Filtered trades: {len(filtered_trades)}, metrics: {filtered_metrics}")

    active_trades = filtered_trades
    active_metrics = filtered_metrics
    session_breakdown = compute_session_breakdown(active_trades, bars)

    result = {
        'strategy_id': '007',
        'strategy_name': 'Sweep & Fade',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': active_metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': active_trades,
        'notes': (
            f'Data: {len(trades_df)} filtered ticks. '
            f'Tick-level sweep detection (min_consec={params.get("min_consecutive")}, '
            f'min_vol={params.get("min_sweep_volume")}, max_s={params.get("max_sweep_seconds")}). '
            f'ML filter: {"ON threshold=" + str(round(ml_threshold, 3)) if use_ml_filter and ml_threshold else "OFF"}. '
            f'Unfiltered: {len(unfiltered_trades)} trades {unfiltered_metrics}.'
        ),
        'unfiltered_metrics': unfiltered_metrics,
        'ml_filter_active': use_ml_filter and ml_threshold is not None,
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '007_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--ml', action='store_true', help='Enable ML filter')
    args = ap.parse_args()
    run(use_ml_filter=args.ml)
