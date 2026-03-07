"""Strategy 004: Bid/Ask Imbalance

Trades extreme bid/ask size imbalances. When buyers outnumber sellers 3:1+,
expect price to move toward the heavier side.
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
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, _get_conn
)

# Default parameters
PARAMS = {
    "imbalance_ratio_threshold": 3.0,
    "consecutive_bars": 2,
    "min_size_contracts": 100,
    "entry_offset_ticks": 1,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",
}


def build_1min_imbalance_bars():
    """Build 1-min bars with bid/ask size imbalance data."""
    conn = _get_conn()

    # Load quotes
    q = "SELECT ts_utc, bid_size, ask_size FROM nq_quotes ORDER BY ts_utc"
    quotes = conn.execute(q).fetchdf()
    conn.close()

    if quotes.empty:
        return pd.DataFrame()

    # Resample to 1-min bars: for each minute, take last quote
    quotes['bar'] = quotes['ts_utc'].dt.floor('1min')
    bars = quotes.groupby('bar').agg(
        bid_size=('bid_size', 'last'),
        ask_size=('ask_size', 'last'),
    ).reset_index().rename(columns={'bar': 'ts_utc'})

    # Compute imbalance ratio
    bars['bid_ask_ratio'] = bars['bid_size'] / (bars['ask_size'] + 1)  # avoid div by 0
    bars['ask_bid_ratio'] = bars['ask_size'] / (bars['bid_size'] + 1)

    return bars


def find_signals(imbalance_bars, price_bars, params=PARAMS):
    """Scan bars for bid/ask imbalance signals."""
    signals = []
    n = len(imbalance_bars)
    threshold = params['imbalance_ratio_threshold']
    consec = params['consecutive_bars']
    min_size = params['min_size_contracts']

    for i in range(consec, n - 1):
        current = imbalance_bars.iloc[i]

        # Check for long signal (bid > ask)
        if current['bid_size'] >= min_size and current['bid_ask_ratio'] >= threshold:
            # Check consecutive bars
            recent = imbalance_bars.iloc[i - consec:i]
            if (recent['bid_ask_ratio'] >= threshold).sum() >= consec:
                # Get corresponding price bar for entry
                price_idx = min(i, len(price_bars) - 1)
                price_bar = price_bars.iloc[price_idx]

                signals.append({
                    'bar_idx': i,
                    'ts': current['ts_utc'],
                    'direction': 'long',
                    'entry_price': price_bar['close'],
                    'imbalance_ratio': current['bid_ask_ratio'],
                })

        # Check for short signal (ask > bid)
        elif current['ask_size'] >= min_size and current['ask_bid_ratio'] >= threshold:
            # Check consecutive bars
            recent = imbalance_bars.iloc[i - consec:i]
            if (recent['ask_bid_ratio'] >= threshold).sum() >= consec:
                price_idx = min(i, len(price_bars) - 1)
                price_bar = price_bars.iloc[price_idx]

                signals.append({
                    'bar_idx': i,
                    'ts': current['ts_utc'],
                    'direction': 'short',
                    'entry_price': price_bar['close'],
                    'imbalance_ratio': current['ask_bid_ratio'],
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
                # Check SL first
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

    # Sharpe
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
        params = PARAMS

    print("Loading quotes and building imbalance bars...")
    imbalance_bars = build_1min_imbalance_bars()

    print("Loading trades and building price bars...")
    trades_df = load_trades()
    price_bars = build_1min_bars_with_delta(trades_df)
    price_bars = filter_rth(price_bars)

    if imbalance_bars.empty or price_bars.empty:
        print("No data available")
        return None

    print(f"Price bars: {len(price_bars)}")

    print("Scanning for signals...")
    signals = find_signals(imbalance_bars, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals found. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['imbalance_ratio_threshold'] = 2.0
        relaxed['consecutive_bars'] = 1
        relaxed['min_size_contracts'] = 50
        signals = find_signals(imbalance_bars, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '004',
        'strategy_name': 'Bid/Ask Imbalance',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. RTH only. Quotes-based imbalance ratio.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '004_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
