"""Strategy 007: Sweep & Fade

Identifies rapid price sweeps (exhaustion moves) and fades them with opposite trades.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, build_1min_bars_with_delta, filter_rth,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq
)

# Default parameters
PARAMS = {
    "sweep_tick_threshold": 8,
    "sweep_time_seconds": 30,
    "take_profit_ticks": 6,
    "stop_loss_ticks": 10,
    "retracement_min_ticks": 1,
    "session_filter": "RTH",
}


def find_signals(bars, params=PARAMS):
    """Scan for sweep/fade signals."""
    signals = []
    sweep_threshold = params['sweep_tick_threshold'] * NQ_TICK_SIZE

    for i in range(1, len(bars) - 1):
        prev_bar = bars.iloc[i - 1]
        curr_bar = bars.iloc[i]
        next_bar = bars.iloc[i + 1]

        # Measure intra-bar range
        inbar_range = curr_bar['high'] - curr_bar['low']

        # Check for upswing (upswing = high - low of bar, or close relative to open)
        # A sweep up would be price moving up significantly
        upswing_magnitude = max(
            curr_bar['high'] - curr_bar['open'],
            curr_bar['high'] - curr_bar['close']
        )

        downswing_magnitude = max(
            curr_bar['open'] - curr_bar['low'],
            curr_bar['close'] - curr_bar['low']
        )

        # Fade short signal: after upswing, enter short if next bar retraces
        if upswing_magnitude >= sweep_threshold:
            # Check if next bar shows retracement (opens lower, closes lower)
            if next_bar['open'] < curr_bar['high'] - params['retracement_min_ticks'] * NQ_TICK_SIZE:
                signals.append({
                    'bar_idx': i,
                    'ts': curr_bar['ts_utc'],
                    'direction': 'short',
                    'entry_price': next_bar['open'],
                    'sweep_high': curr_bar['high'],
                    'sweep_magnitude': upswing_magnitude,
                })

        # Fade long signal: after downswing, enter long if next bar retraces
        if downswing_magnitude >= sweep_threshold:
            # Check if next bar shows retracement (opens higher, closes higher)
            if next_bar['open'] > curr_bar['low'] + params['retracement_min_ticks'] * NQ_TICK_SIZE:
                signals.append({
                    'bar_idx': i,
                    'ts': curr_bar['ts_utc'],
                    'direction': 'long',
                    'entry_price': next_bar['open'],
                    'sweep_low': curr_bar['low'],
                    'sweep_magnitude': downswing_magnitude,
                })

    return signals


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


def run(params=None):
    if params is None:
        params = PARAMS

    print("Loading trades...")
    trades_df = load_trades()
    print(f"Building price bars from {len(trades_df)} ticks...")
    bars = build_1min_bars_with_delta(trades_df)
    bars = filter_rth(bars)
    print(f"RTH bars: {len(bars)}")

    print("Scanning for sweep/fade signals...")
    signals = find_signals(bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['sweep_tick_threshold'] = 5
        relaxed['retracement_min_ticks'] = 0.5
        signals = find_signals(bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '007',
        'strategy_name': 'Sweep & Fade',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. RTH only. Fading exhaustion sweeps.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '007_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
