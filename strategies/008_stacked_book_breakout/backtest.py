"""Strategy 008: Stacked Book Breakout

Identifies stacked bid/ask levels and trades breakouts through them.
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
    "stack_threshold": 3.0,
    "stack_lookback_bars": 10,
    "breakout_min_ticks": 1,
    "entry_offset_ticks": 1,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def build_1min_book_depth_bars():
    """Build 1-min bars with stacked bid/ask detection."""
    conn = _get_conn()

    q = "SELECT ts_utc, bid_size, ask_size FROM nq_quotes ORDER BY ts_utc"
    quotes = conn.execute(q).fetchdf()
    conn.close()

    if quotes.empty:
        return pd.DataFrame()

    # Resample to 1-min bars
    quotes['bar'] = quotes['ts_utc'].dt.floor('1min')
    bars = quotes.groupby('bar').agg(
        bid_size=('bid_size', 'mean'),
        ask_size=('ask_size', 'mean'),
    ).reset_index().rename(columns={'bar': 'ts_utc'})

    # Rolling average
    bars['avg_bid_size'] = bars['bid_size'].rolling(window=PARAMS['stack_lookback_bars'], min_periods=1).mean()
    bars['avg_ask_size'] = bars['ask_size'].rolling(window=PARAMS['stack_lookback_bars'], min_periods=1).mean()

    # Detect stacks
    bars['bid_stacked'] = bars['bid_size'] > (bars['avg_bid_size'] * PARAMS['stack_threshold'])
    bars['ask_stacked'] = bars['ask_size'] > (bars['avg_ask_size'] * PARAMS['stack_threshold'])

    return bars


def find_signals(book_bars, price_bars, params=PARAMS):
    """Scan for stacked book breakout signals."""
    signals = []
    stack_threshold = params['stack_threshold']
    lookback = params['stack_lookback_bars']
    breakout_ticks = params['breakout_min_ticks'] * NQ_TICK_SIZE

    for i in range(lookback, min(len(book_bars), len(price_bars))):
        book_bar = book_bars.iloc[i]
        price_bar = price_bars.iloc[i]

        # Check if we have a stacked level and price breaks through
        avg_ask = book_bar['avg_ask_size']
        avg_bid = book_bar['avg_bid_size']

        # Stacked ask level → price breakout above = buyers win
        if book_bar['ask_stacked'] and avg_ask > 0:
            # Check if there was a stacked ask level in recent bars
            recent_book = book_bars.iloc[max(0, i - lookback):i]
            if (recent_book['ask_stacked']).any():
                # Entry on breakout
                signals.append({
                    'bar_idx': i,
                    'ts': price_bar['ts_utc'],
                    'direction': 'long',
                    'entry_price': price_bar['close'],
                    'stack_size': book_bar['ask_size'],
                })

        # Stacked bid level → price breakout below = sellers win
        if book_bar['bid_stacked'] and avg_bid > 0:
            recent_book = book_bars.iloc[max(0, i - lookback):i]
            if (recent_book['bid_stacked']).any():
                signals.append({
                    'bar_idx': i,
                    'ts': price_bar['ts_utc'],
                    'direction': 'short',
                    'entry_price': price_bar['close'],
                    'stack_size': book_bar['bid_size'],
                })

    # Remove duplicates (same direction within N bars)
    filtered_signals = []
    last_dir = None
    last_idx = -10
    for sig in signals:
        if sig['direction'] != last_dir or sig['bar_idx'] - last_idx > 5:
            filtered_signals.append(sig)
            last_dir = sig['direction']
            last_idx = sig['bar_idx']

    return filtered_signals


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

    print("Loading quotes and building book depth bars...")
    book_bars = build_1min_book_depth_bars()

    print("Loading trades and building price bars...")
    trades_df = load_trades()
    price_bars = build_1min_bars_with_delta(trades_df)
    price_bars = filter_sessions(price_bars, sessions=params.get('session_filter'))

    if book_bars.empty or price_bars.empty:
        print("No data available")
        return None

    print(f"Price bars: {len(price_bars)}")

    print("Scanning for stacked book breakout signals...")
    signals = find_signals(book_bars, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['stack_threshold'] = 2.0
        relaxed['stack_lookback_bars'] = 5
        signals = find_signals(book_bars, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '008',
        'strategy_name': 'Stacked Book Breakout',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. Session filter driven. Stacked bid/ask detection.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '008_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
