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
    "lookback_bars": 50,
    "std_dev_threshold": 2.0,
    "min_trade_size": 1000,
    "signal_cooldown_bars": 5,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def build_1min_volume_stats(trades_df):
    """Build 1-min bars with trade size stats."""
    if trades_df.empty:
        return pd.DataFrame()

    trades_df['bar'] = trades_df['ts_utc'].dt.floor('1min')

    bars = trades_df.groupby('bar').agg(
        volume=('size', 'sum'),
        max_size=('size', 'max'),
        mean_size=('size', 'mean'),
    ).reset_index().rename(columns={'bar': 'ts_utc'})

    # Rolling stats
    bars['rolling_mean'] = bars['mean_size'].rolling(window=PARAMS['lookback_bars'], min_periods=1).mean()
    bars['rolling_std'] = bars['mean_size'].rolling(window=PARAMS['lookback_bars'], min_periods=1).std()

    return bars


def find_signals(trades_df, price_bars, params=PARAMS):
    """Scan for large print momentum signals."""
    signals = []
    if trades_df.empty or price_bars.empty:
        return signals

    trades_df = trades_df.sort_values('ts_utc').reset_index(drop=True)
    trades_df['bar'] = trades_df['ts_utc'].dt.floor('1min')

    # Minute-level cumulative stats based on prior trades only.
    minute_stats = trades_df.groupby('bar').agg(
        trade_count=('size', 'count'),
        size_sum=('size', 'sum'),
        size_sq_sum=('size', lambda s: float((s.astype(float) ** 2).sum())),
    ).reset_index().sort_values('bar')

    minute_stats['cum_count_prev'] = minute_stats['trade_count'].cumsum().shift(1).fillna(0)
    minute_stats['cum_sum_prev'] = minute_stats['size_sum'].cumsum().shift(1).fillna(0.0)
    minute_stats['cum_sq_sum_prev'] = minute_stats['size_sq_sum'].cumsum().shift(1).fillna(0.0)

    valid = minute_stats['cum_count_prev'] > 1
    minute_stats['lookback_mean'] = 0.0
    minute_stats['lookback_std'] = 0.0
    minute_stats.loc[valid, 'lookback_mean'] = (
        minute_stats.loc[valid, 'cum_sum_prev'] / minute_stats.loc[valid, 'cum_count_prev']
    )
    variance = 0.0
    minute_stats.loc[valid, 'lookback_std'] = np.sqrt(
        np.maximum(
            (minute_stats.loc[valid, 'cum_sq_sum_prev'] / minute_stats.loc[valid, 'cum_count_prev']) -
            (minute_stats.loc[valid, 'lookback_mean'] ** 2),
            variance
        )
    )
    minute_stats['threshold'] = (
        minute_stats['lookback_mean'] + params['std_dev_threshold'] * minute_stats['lookback_std']
    )
    threshold_map = minute_stats.set_index('bar')['threshold']

    trades_with_thr = trades_df.merge(
        threshold_map.rename('threshold'),
        left_on='bar',
        right_index=True,
        how='left',
    )
    trades_with_thr = trades_with_thr[
        (trades_with_thr['size'] >= params['min_trade_size']) &
        (trades_with_thr['size'] > trades_with_thr['threshold'].fillna(np.inf))
    ]

    if trades_with_thr.empty:
        return signals

    # One candidate signal per bar: first qualifying print.
    candidates = (
        trades_with_thr
        .sort_values('ts_utc')
        .drop_duplicates(subset='bar', keep='first')
    )
    bar_lookup = price_bars.reset_index(drop=True).reset_index().rename(columns={'index': 'bar_idx'})
    bar_lookup = bar_lookup.set_index('ts_utc')

    last_signal_idx = -params['signal_cooldown_bars']
    allowed_bars = set(price_bars['ts_utc'])
    for _, trade in candidates.iterrows():
        bar_ts = trade['bar']
        if bar_ts not in allowed_bars or bar_ts not in bar_lookup.index:
            continue

        price_bar = bar_lookup.loc[bar_ts]
        idx = int(price_bar['bar_idx'])
        if idx - last_signal_idx < params['signal_cooldown_bars']:
            continue

        direction = 'long' if trade['side'] == 'B' else 'short'
        signals.append({
            'bar_idx': idx,
            'ts': bar_ts,
            'direction': direction,
            'entry_price': float(price_bar['close']),
            'trade_size': float(trade['size']),
            'threshold': float(trade['threshold']),
        })
        last_signal_idx = idx

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
    print(f"Building price bars from {len(trades_df)} ticks...")
    price_bars = build_1min_bars_with_delta(trades_df)
    price_bars = filter_sessions(price_bars, sessions=params.get('session_filter'))
    print(f"Filtered bars: {len(price_bars)}")

    print("Scanning for large print signals...")
    signals = find_signals(trades_df, price_bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['std_dev_threshold'] = 1.5
        relaxed['min_trade_size'] = 500
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
        'notes': f'Data: {len(trades_df)} ticks. Session filter driven. Block trades > 2 std devs.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '005_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
