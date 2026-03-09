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
    load_trades, build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, _get_conn, compute_session_breakdown
)

# Default parameters
PARAMS = {
    "imbalance_threshold": 0.4,
    "sustained_quotes": 20,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def load_quote_imbalance_events(threshold, sustained_quotes):
    """Compute sustained bid/ask imbalance events directly from the raw quote stream.

    Scans ALL nq_quotes (no bar-derived active_minutes filter).
    Uses DuckDB window function for efficiency over 68M rows.
    """
    conn = _get_conn()
    q = """
        WITH scored AS (
            SELECT
                ts_utc,
                CASE
                    WHEN bid_size + ask_size > 0
                    THEN CAST(bid_size - ask_size AS DOUBLE) / CAST(bid_size + ask_size AS DOUBLE)
                    ELSE 0.0
                END AS imbalance
            FROM nq_quotes
        ),
        rolled AS (
            SELECT
                ts_utc,
                AVG(imbalance) OVER (
                    ORDER BY ts_utc
                    ROWS BETWEEN ? PRECEDING AND CURRENT ROW
                ) AS rolling_imbalance
            FROM scored
        ),
        edged AS (
            SELECT
                ts_utc,
                rolling_imbalance,
                LAG(rolling_imbalance) OVER (ORDER BY ts_utc) AS prev_rolling_imbalance
            FROM rolled
        )
        SELECT
            ts_utc,
            CASE
                WHEN rolling_imbalance > ? THEN 'long'
                ELSE 'short'
            END AS direction,
            rolling_imbalance AS quote_imbalance
        FROM edged
        WHERE
            (rolling_imbalance > ? AND COALESCE(prev_rolling_imbalance, 0.0) <= ?)
            OR
            (rolling_imbalance < -? AND COALESCE(prev_rolling_imbalance, 0.0) >= -?)
        ORDER BY ts_utc
    """
    quotes = conn.execute(
        q,
        [
            sustained_quotes - 1,
            threshold,
            threshold, threshold,
            threshold, threshold,
        ],
    ).fetchdf()
    conn.close()
    return quotes


def find_quote_imbalance_signals(df_quotes, df_trades, df_bars, params=PARAMS):
    """Detect sustained quote imbalance on the raw quote stream."""
    signals = []
    if df_quotes.empty or df_trades.empty or df_bars.empty:
        return signals

    quotes = df_quotes.sort_values('ts_utc').reset_index(drop=True)
    trades = df_trades[df_trades['side'].isin(['B', 'S'])].sort_values('ts_utc').reset_index(drop=True)
    trade_ts = trades['ts_utc'].to_numpy()
    bar_ts = df_bars['ts_utc'].to_numpy()
    last_bar_idx = -1

    for _, quote in quotes.iterrows():
        direction = quote['direction']
        side = 'B' if direction == 'long' else 'S'
        signal_ts = quote['ts_utc']
        trade_idx = np.searchsorted(trade_ts, signal_ts.to_datetime64(), side='right')
        while trade_idx < len(trades) and trades.iloc[trade_idx]['side'] != side:
            trade_idx += 1
        if trade_idx >= len(trades):
            continue

        entry_trade = trades.iloc[trade_idx]
        bar_idx = np.searchsorted(bar_ts, entry_trade['ts_utc'].to_datetime64(), side='right') - 1
        if bar_idx < 0 or bar_idx >= len(df_bars) or bar_idx == last_bar_idx:
            continue

        signals.append({
            'bar_idx': int(bar_idx),
            'ts': entry_trade['ts_utc'],
            'direction': direction,
            'entry_price': float(entry_trade['price']),
            'quote_imbalance': float(quote['quote_imbalance']),
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
        params = PARAMS.copy()
    else:
        params = params.copy()

    print("Loading trades and building price bars...")
    trades_df = load_trades()
    price_bars = build_1min_bars_with_delta(trades_df)
    price_bars = filter_sessions(price_bars, sessions=params.get('session_filter'))
    trades_df = filter_sessions(trades_df, sessions=params.get('session_filter'))

    print("Computing sustained quote imbalance events (raw quote stream, no bar filter)...")
    quotes_df = load_quote_imbalance_events(
        threshold=float(params.get('imbalance_threshold', 0.4)),
        sustained_quotes=int(params.get('sustained_quotes', 20)),
    )

    if quotes_df.empty or price_bars.empty or trades_df.empty:
        print("No data available")
        return None

    print(f"Price bars: {len(price_bars)}, quote events: {len(quotes_df)}")

    print("Scanning for signals...")
    signals = find_quote_imbalance_signals(quotes_df, trades_df, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals found. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['imbalance_threshold'] = 0.25
        relaxed['sustained_quotes'] = 10
        quotes_df = load_quote_imbalance_events(
            threshold=float(relaxed['imbalance_threshold']),
            sustained_quotes=int(relaxed['sustained_quotes']),
        )
        signals = find_quote_imbalance_signals(quotes_df, trades_df, price_bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, price_bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '004',
        'strategy_name': 'Bid/Ask Imbalance',
        'backtest_period': {
            'start': str(price_bars['ts_utc'].min()),
            'end': str(price_bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. Session filter driven. Quotes-based imbalance ratio.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '004_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
