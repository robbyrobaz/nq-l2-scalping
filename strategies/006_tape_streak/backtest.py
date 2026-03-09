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
    load_trades, build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, compute_session_breakdown
)

# Default parameters
PARAMS = {
    "min_consecutive_trades": 5,
    "allowed_opposite_ticks": 3,
    "min_total_volume": 0,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _resolve_streak_params(params):
    return {
        'min_consecutive_trades': int(params.get('min_consecutive_trades', 5)),
        'allowed_opposite_ticks': int(params.get('allowed_opposite_ticks', min(3, int(params.get('lookback_bars', 3))))),
        'min_total_volume': float(params.get('min_total_volume', 0)),
    }


def find_tape_streaks(df_trades, params):
    """Walk the full tick stream and confirm continuation after a short pause."""
    cfg = _resolve_streak_params(params)
    trades = df_trades[df_trades['side'].isin(['B', 'S'])].sort_values('ts_utc').reset_index(drop=True)
    signals = []
    if trades.empty:
        return signals

    streak = None
    pending = None

    for row in trades.itertuples(index=False):
        if streak is None:
            streak = {
                'direction': row.side,
                'count': 1,
                'start_price': float(row.price),
                'total_volume': float(row.size),
                'end_ts': row.ts_utc,
            }
            continue

        if row.side == streak['direction']:
            streak['count'] += 1
            streak['total_volume'] += float(row.size)
            streak['end_ts'] = row.ts_utc
            if pending and pending['direction'] != row.side:
                pending['opposite_ticks'] += 1
                if pending['opposite_ticks'] > cfg['allowed_opposite_ticks']:
                    pending = None
            if pending and pending['direction'] == row.side:
                if pending['opposite_ticks'] <= cfg['allowed_opposite_ticks']:
                    signals.append({
                        'ts': row.ts_utc,
                        'direction': 'long' if row.side == 'B' else 'short',
                        'entry_price': float(row.price),
                        'streak_count': int(pending['count']),
                        'streak_volume': float(pending['total_volume']),
                    })
                pending = None
            continue

        qualifies = (
            streak['count'] >= cfg['min_consecutive_trades'] and
            streak['total_volume'] >= cfg['min_total_volume']
        )
        if qualifies:
            if pending is None or pending['direction'] != streak['direction']:
                pending = {
                    'direction': streak['direction'],
                    'count': streak['count'],
                    'total_volume': streak['total_volume'],
                    'opposite_ticks': 1,
                }
        elif pending and row.side != pending['direction']:
            pending['opposite_ticks'] += 1

        if pending and pending['opposite_ticks'] > cfg['allowed_opposite_ticks']:
            pending = None

        streak = {
            'direction': row.side,
            'count': 1,
            'start_price': float(row.price),
            'total_volume': float(row.size),
            'end_ts': row.ts_utc,
        }

    return signals


def find_signals(trades_df, price_bars, params=PARAMS):
    """Map confirmed tape streak continuations to bar indexes for simulation."""
    if trades_df.empty or price_bars.empty:
        return []

    raw_signals = find_tape_streaks(trades_df, params)
    if not raw_signals:
        return []

    bar_ts = price_bars['ts_utc'].to_numpy()
    signals = []
    last_bar_idx = -1
    for sig in raw_signals:
        bar_idx = np.searchsorted(bar_ts, sig['ts'].to_datetime64(), side='right') - 1
        if bar_idx < 0 or bar_idx >= len(price_bars) or bar_idx == last_bar_idx:
            continue
        signals.append({
            'bar_idx': int(bar_idx),
            'ts': sig['ts'],
            'direction': sig['direction'],
            'entry_price': sig['entry_price'],
            'streak_count': sig['streak_count'],
            'streak_volume': sig['streak_volume'],
        })
        last_bar_idx = int(bar_idx)
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
        params = PARAMS.copy()
    else:
        params = params.copy()

    print("Loading trades...")
    trades_df = load_trades()
    trades_df = filter_sessions(trades_df, sessions=params.get('session_filter'))
    print(f"Building price bars from {len(trades_df)} ticks...")
    price_bars = build_1min_bars_with_delta(trades_df)
    print(f"Filtered bars: {len(price_bars)}")

    print("Scanning for tape streak signals...")
    signals = find_signals(trades_df, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['min_consecutive_trades'] = 3
        relaxed['allowed_opposite_ticks'] = 3
        signals = find_signals(trades_df, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '006',
        'strategy_name': 'Aggressive Tape Streak',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} filtered ticks. Tape streaks run across the full stream and confirm continuation after a brief counterflow pause.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '006_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
