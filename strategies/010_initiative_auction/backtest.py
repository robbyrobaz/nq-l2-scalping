"""Strategy 010: Initiative Auction

Identifies bars where initiative traders are in control -- delta aligns with price
direction on above-average volume. This is a trend continuation signal.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, build_1min_bars_with_delta, filter_sessions,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq, compute_session_breakdown
)

# Default parameters
PARAMS = {
    "delta_threshold": 300,
    "volume_avg_period": 20,
    "volume_multiplier": 1.5,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def find_signals(bars, params=PARAMS):
    """Scan bars for initiative auction signals."""
    signals = []
    n = len(bars)
    vol_period = params['volume_avg_period']
    vol_mult = params['volume_multiplier']
    delta_thresh = params['delta_threshold']

    # Compute rolling avg volume
    rolling_vol = bars['volume'].rolling(vol_period).mean().values

    for i in range(vol_period, n):
        bar = bars.iloc[i]

        if np.isnan(rolling_vol[i]) or rolling_vol[i] == 0:
            continue

        # High volume condition
        if bar['volume'] < vol_mult * rolling_vol[i]:
            continue

        # Delta threshold
        bar_delta = bar['bar_delta']
        if abs(bar_delta) < delta_thresh:
            continue

        # Delta-Price Alignment
        if bar_delta > delta_thresh and bar['close'] > bar['open']:
            signals.append({
                'bar_idx': i,
                'ts': bar['ts_utc'],
                'direction': 'long',
                'entry_price': bar['close'],
                'bar_delta': bar_delta,
                'volume': bar['volume'],
                'avg_volume': rolling_vol[i],
            })
        elif bar_delta < -delta_thresh and bar['close'] < bar['open']:
            signals.append({
                'bar_idx': i,
                'ts': bar['ts_utc'],
                'direction': 'short',
                'entry_price': bar['close'],
                'bar_delta': bar_delta,
                'volume': bar['volume'],
                'avg_volume': rolling_vol[i],
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

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")
    session_breakdown = compute_session_breakdown(trade_list, bars if 'bars' in locals() else price_bars)

    result = {
        'strategy_id': '010',
        'strategy_name': 'Initiative Auction',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'session_breakdown': session_breakdown,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks over Mar 5-6 2026. Session filter driven.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '010_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
