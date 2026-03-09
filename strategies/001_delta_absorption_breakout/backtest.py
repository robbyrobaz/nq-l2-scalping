"""Strategy 001: Delta Absorption Breakout

Identifies compression zones where aggressive orders are absorbed (high delta
but no price movement), then trades the breakout when price escapes the range.
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
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, compute_session_breakdown
)

# Default parameters
PARAMS = {
    "range_window": 5,
    "range_atr_mult": 3.0,
    "delta_threshold": 40,
    "absorption_bars": 1,
    "price_move_max_ticks": 4,
    "take_profit_ticks": 8,
    "stop_loss_ticks": 12,
    "session_filter": None,
}


def compute_atr(bars, period=14):
    """Simple ATR on 1-min bars."""
    highs = bars['high'].values
    lows = bars['low'].values
    closes = bars['close'].values
    tr = np.maximum(highs - lows,
                    np.maximum(np.abs(highs - np.roll(closes, 1)),
                               np.abs(lows - np.roll(closes, 1))))
    tr[0] = highs[0] - lows[0]
    atr = pd.Series(tr).rolling(period).mean().values
    return atr


def find_signals(bars, params=PARAMS):
    """Scan bars for delta absorption breakout signals."""
    signals = []
    n = len(bars)
    atr = compute_atr(bars, period=params['range_window'])
    rw = params['range_window']
    dt = params['delta_threshold']
    ab = params['absorption_bars']
    pm = params['price_move_max_ticks'] * NQ_TICK_SIZE

    for i in range(rw + ab, n - 1):
        # Check compression: last rw bars range < atr_mult * ATR
        window = bars.iloc[i - rw:i]
        range_hi = window['high'].max()
        range_lo = window['low'].min()
        bar_range = range_hi - range_lo

        if np.isnan(atr[i]) or atr[i] == 0:
            continue
        if bar_range > params['range_atr_mult'] * atr[i]:
            continue

        # Check absorption in recent bars
        recent = bars.iloc[i - ab:i]
        sell_absorption = 0
        buy_absorption = 0

        for _, bar in recent.iterrows():
            price_move = abs(bar['close'] - bar['open'])
            if bar['bar_delta'] < -dt and price_move <= pm:
                sell_absorption += 1  # sellers absorbed → expect long
            if bar['bar_delta'] > dt and price_move <= pm:
                buy_absorption += 1   # buyers absorbed → expect short

        # Breakout bar
        breakout = bars.iloc[i]

        if sell_absorption >= ab and breakout['close'] > range_hi:
            signals.append({
                'bar_idx': i,
                'ts': breakout['ts_utc'],
                'direction': 'long',
                'entry_price': breakout['close'],
                'range_hi': range_hi,
                'range_lo': range_lo,
            })
        elif buy_absorption >= ab and breakout['close'] < range_lo:
            signals.append({
                'bar_idx': i,
                'ts': breakout['ts_utc'],
                'direction': 'short',
                'entry_price': breakout['close'],
                'range_hi': range_hi,
                'range_lo': range_lo,
            })

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

        # Walk forward from next bar to find exit
        exited = False
        for j in range(idx + 1, len(bars)):
            bar = bars.iloc[j]
            if direction == 'long':
                # Check SL first (worse case)
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
            # Force exit at last bar
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

    # Sharpe (annualized from per-trade)
    arr = np.array(pnls)
    sharpe = (arr.mean() / arr.std() * np.sqrt(252)) if arr.std() > 0 else 0.0

    # Max drawdown
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
    print(f"Building 1-min bars from {len(trades_df)} ticks...")
    bars = build_1min_bars_with_delta(trades_df)
    bars = filter_sessions(bars, sessions=params.get('session_filter'))
    print(f"Filtered bars: {len(bars)}")

    print("Scanning for signals...")
    signals = find_signals(bars, params)
    print(f"Signals found: {len(signals)}")

    # If no signals with default params, try relaxed params
    if not signals:
        print("No signals with default params. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['delta_threshold'] = 30
        relaxed['range_atr_mult'] = 4.0
        relaxed['range_window'] = 3
        relaxed['absorption_bars'] = 1
        relaxed['price_move_max_ticks'] = 6
        signals = find_signals(bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '001',
        'strategy_name': 'Delta Absorption Breakout',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks over Mar 5-6 2026. Session filter driven. Side inferred from bid/ask.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '001_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
