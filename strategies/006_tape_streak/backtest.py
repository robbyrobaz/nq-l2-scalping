"""Strategy 006: Aggressive Tape Streak

Identifies N consecutive same-side trades and trades the momentum continuation.
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
    "min_consecutive_trades": 5,
    "lookback_bars": 3,
    "min_total_volume": 0,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",
}


def find_signals(trades_df, price_bars, params=PARAMS):
    """Scan for tape streak signals."""
    signals = []

    if trades_df.empty:
        return signals

    trades_df = trades_df.sort_values('ts_utc').reset_index(drop=True)
    min_consec = params['min_consecutive_trades']
    lookback = params['lookback_bars']

    for bar_idx, price_bar in price_bars.iterrows():
        bar_start = price_bar['ts_utc']
        bar_end = bar_start + pd.Timedelta(minutes=1)

        # Get trades in current bar and lookback bars
        lookback_end = bar_start
        lookback_start = bar_start - pd.Timedelta(minutes=lookback)
        lookback_trades = trades_df[
            (trades_df['ts_utc'] >= lookback_start) & (trades_df['ts_utc'] <= lookback_end)
        ].sort_values('ts_utc')

        if lookback_trades.empty:
            continue

        # Count consecutive same-side trades
        sides = lookback_trades['side'].values
        current_side = None
        current_count = 0
        max_buy_count = 0
        max_sell_count = 0

        for side in sides:
            if side == 'B':
                if current_side == 'B':
                    current_count += 1
                else:
                    current_count = 1
                    current_side = 'B'
                max_buy_count = max(max_buy_count, current_count)
            elif side == 'S':
                if current_side == 'S':
                    current_count += 1
                else:
                    current_count = 1
                    current_side = 'S'
                max_sell_count = max(max_sell_count, current_count)

        # Check for long signal
        if max_buy_count >= min_consec:
            signals.append({
                'bar_idx': bar_idx,
                'ts': price_bar['ts_utc'],
                'direction': 'long',
                'entry_price': price_bar['close'],
                'streak_count': max_buy_count,
            })

        # Check for short signal
        elif max_sell_count >= min_consec:
            signals.append({
                'bar_idx': bar_idx,
                'ts': price_bar['ts_utc'],
                'direction': 'short',
                'entry_price': price_bar['close'],
                'streak_count': max_sell_count,
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
    price_bars = build_1min_bars_with_delta(trades_df)
    price_bars = filter_rth(price_bars)
    print(f"RTH bars: {len(price_bars)}")

    print("Scanning for tape streak signals...")
    signals = find_signals(trades_df, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['min_consecutive_trades'] = 3
        relaxed['lookback_bars'] = 5
        signals = find_signals(trades_df, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '006',
        'strategy_name': 'Aggressive Tape Streak',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. RTH only. Consecutive same-side trades.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '006_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
