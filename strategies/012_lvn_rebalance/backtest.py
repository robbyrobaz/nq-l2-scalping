"""Strategy 012: LVN Rebalance

Identifies low-volume nodes and trades returns to them when price trends away.
Simplified: Uses session-level volume profile instead of recalculating every bar.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades_fast, build_1min_bars_with_delta, filter_rth,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq
)

# Default parameters
PARAMS = {
    "volume_profile_bars": 50,
    "lvn_threshold_ratio": 0.30,
    "value_area_pct": 0.70,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 12,
    "session_filter": "RTH",
}


def build_volume_profile_fast(bars, price_bucket=0.25):
    """Build volume profile from bars (bucketed by price) - very fast."""
    profile = defaultdict(int)
    for _, bar in bars.iterrows():
        # Bucket by price
        for price_level in [bar['high'], bar['open'], bar['close'], bar['low']]:
            bucket = round(price_level / price_bucket) * price_bucket
            profile[bucket] += int(bar['volume'] / 4)  # Distribute volume across 4 levels
    return profile


def find_signals(bars, params=PARAMS):
    """Scan bars for LVN rebalance signals."""
    signals = []
    n = len(bars)
    vp_bars = params['volume_profile_bars']
    lvn_ratio = params['lvn_threshold_ratio']
    va_pct = params['value_area_pct']

    # Pre-compute session profile for efficiency
    session_profile = build_volume_profile_fast(bars)
    if not session_profile:
        return signals

    # Find POC and VA boundaries
    poc_price = max(session_profile, key=session_profile.get)
    poc_volume = session_profile[poc_price]
    lvn_threshold = poc_volume * lvn_ratio

    # Find LVN (low volume nodes)
    lvn_prices = [p for p, v in session_profile.items() if v < lvn_threshold]
    if not lvn_prices:
        return signals

    # Find VAH and VAL
    sorted_prices = sorted(session_profile.keys(), key=lambda p: session_profile[p], reverse=True)
    total_vol = sum(session_profile.values())
    cumul_vol = 0
    va_prices = []
    for p in sorted_prices:
        cumul_vol += session_profile[p]
        va_prices.append(p)
        if cumul_vol >= va_pct * total_vol:
            break

    if va_prices:
        vah = max(va_prices)
        val = min(va_prices)

        # Scan bars for trend + LVN alignment
        for i in range(vp_bars, n):
            current_bar = bars.iloc[i]

            # Trend: price above VAH (long) or below VAL (short)
            if current_bar['close'] > vah:
                lvn_below_vah = [p for p in lvn_prices if p < current_bar['close']]
                if lvn_below_vah:
                    signals.append({
                        'bar_idx': i,
                        'ts': current_bar['ts_utc'],
                        'direction': 'long',
                        'entry_price': current_bar['close'],
                        'vah': vah,
                        'lvn_target': max(lvn_below_vah),
                    })
            elif current_bar['close'] < val:
                lvn_above_val = [p for p in lvn_prices if p > current_bar['close']]
                if lvn_above_val:
                    signals.append({
                        'bar_idx': i,
                        'ts': current_bar['ts_utc'],
                        'direction': 'short',
                        'entry_price': current_bar['close'],
                        'val': val,
                        'lvn_target': min(lvn_above_val),
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
    trades_df = load_trades_fast()
    print(f"Building 1-min bars from {len(trades_df)} ticks...")

    from pipeline.data_loader import load_trades
    trades_df_delta = load_trades()
    bars = build_1min_bars_with_delta(trades_df_delta)
    bars = filter_rth(bars)
    print(f"RTH bars: {len(bars)}")

    print("Scanning for signals...")
    signals = find_signals(bars, params)
    print(f"Signals found: {len(signals)}")

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades executed: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '012',
        'strategy_name': 'LVN Rebalance',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks over Mar 5-6 2026. RTH only.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '012_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
