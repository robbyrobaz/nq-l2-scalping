"""Strategy 005: Large Print Momentum

Identifies large block trades (outliers > 2 std devs above mean) and trades
in their direction, following informed flow.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, _get_conn, compute_session_breakdown
)

# Default parameters
PARAMS = {
    "lookback_ticks": 200,
    "size_multiplier": 5.0,
    "cluster_window_seconds": 30,
    "min_cluster_prints": 1,
    "min_trade_size": 0,
    "signal_cooldown_bars": 5,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _resolve_large_print_params(params):
    legacy_lookback = int(params.get('lookback_bars', 50))
    legacy_threshold = float(params.get('std_dev_threshold', 2.0))
    return {
        'lookback_ticks': int(params.get('lookback_ticks', max(200, legacy_lookback * 4))),
        'size_multiplier': float(params.get('size_multiplier', max(3.0, legacy_threshold * 2.0))),
        'cluster_window_seconds': float(params.get('cluster_window_seconds', 30)),
        'min_cluster_prints': int(params.get('min_cluster_prints', 1)),
        'min_trade_size': float(params.get('min_trade_size', 0)),
        'signal_cooldown_bars': int(params.get('signal_cooldown_bars', 5)),
    }


def find_large_prints(df_trades, params):
    """Find large individual prints and same-direction clusters."""
    if df_trades.empty:
        return pd.DataFrame()

    cfg = _resolve_large_print_params(params)
    trades = df_trades[df_trades['side'].isin(['B', 'S'])].sort_values('ts_utc').reset_index(drop=True).copy()
    if trades.empty:
        return trades

    trades['rolling_mean_size'] = trades['size'].rolling(
        window=cfg['lookback_ticks'],
        min_periods=max(20, min(cfg['lookback_ticks'], 50)),
    ).mean().shift(1)
    trades['large_print'] = (
        trades['rolling_mean_size'].notna() &
        (trades['size'] >= trades['rolling_mean_size'] * cfg['size_multiplier']) &
        (trades['size'] >= cfg['min_trade_size'])
    )

    candidates = trades[trades['large_print']].copy()
    if candidates.empty:
        return candidates

    cluster_counts = []
    for _, row in candidates.iterrows():
        window_start = row['ts_utc'] - pd.Timedelta(seconds=cfg['cluster_window_seconds'])
        count = candidates[
            (candidates['side'] == row['side']) &
            (candidates['ts_utc'] >= window_start) &
            (candidates['ts_utc'] <= row['ts_utc'])
        ].shape[0]
        cluster_counts.append(count)
    candidates['cluster_count'] = cluster_counts
    return candidates[candidates['cluster_count'] >= cfg['min_cluster_prints']].copy()


def find_signals(trades_df, price_bars, params=PARAMS):
    """Scan for large print momentum signals."""
    signals = []
    if trades_df.empty or price_bars.empty:
        return signals

    cfg = _resolve_large_print_params(params)
    trades_df = trades_df.sort_values('ts_utc').reset_index(drop=True)
    large_prints = find_large_prints(trades_df, params)
    if large_prints.empty:
        return signals

    bar_ts = price_bars['ts_utc'].to_numpy()
    trade_ts = trades_df['ts_utc'].to_numpy()
    last_signal_idx = -cfg['signal_cooldown_bars']

    for _, print_tick in large_prints.iterrows():
        next_trade_idx = np.searchsorted(trade_ts, print_tick['ts_utc'].to_datetime64(), side='right')
        if next_trade_idx >= len(trades_df):
            continue

        entry_trade = trades_df.iloc[next_trade_idx]
        idx = np.searchsorted(bar_ts, entry_trade['ts_utc'].to_datetime64(), side='right') - 1
        if idx < 0 or idx >= len(price_bars) or idx - last_signal_idx < cfg['signal_cooldown_bars']:
            continue

        direction = 'long' if print_tick['side'] == 'B' else 'short'
        signals.append({
            'bar_idx': int(idx),
            'ts': entry_trade['ts_utc'],
            'direction': direction,
            'entry_price': float(entry_trade['price']),
            'trade_size': float(print_tick['size']),
            'threshold': float(print_tick['rolling_mean_size'] * cfg['size_multiplier']),
            'cluster_count': int(print_tick['cluster_count']),
        })
        last_signal_idx = int(idx)

    return signals


def simulate_trades(signals, bars, params=PARAMS):
    """Simulate entries and exits using TP/SL in ticks."""
    tp = params['take_profit_ticks'] * NQ_TICK_SIZE
    sl = params['stop_loss_ticks'] * NQ_TICK_SIZE
    trades = []

    for sig in signals:
        idx = sig['bar_idx']
        entry = sig['entry_price']
        direction = sig['direction']

        # Walk forward
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


def run(params=None):
    if params is None:
        params = PARAMS.copy()
    else:
        params = params.copy()

    print("Loading trades...")
    trades_df = load_trades()
    trades_df = filter_sessions(trades_df, sessions=params.get('session_filter'))
    print(f"Building price bars from {len(trades_df)} ticks...")
    price_bars = build_1min_bars_with_delta(trades_df)
    print(f"Filtered bars: {len(price_bars)}")

    print("Scanning for large print signals...")
    signals = find_signals(trades_df, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['size_multiplier'] = 4.0
        relaxed['min_trade_size'] = 1
        relaxed['signal_cooldown_bars'] = 1
        signals = find_signals(trades_df, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '005',
        'strategy_name': 'Large Print Momentum',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} filtered ticks. Large-print detection uses raw tick outliers and same-direction clustering.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '005_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
