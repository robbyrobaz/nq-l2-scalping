"""Strategy 014: Failed Auction Hook

Identifies failed breakouts of value area boundaries and trades the reversal.
Simplified: Uses session-level volume profile computed once.
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
    "value_area_pct": 0.70,
    "breakout_threshold_ticks": 3,
    "reentry_tolerance_ticks": 2,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 10,
    "session_filter": "RTH",
}


def build_volume_profile_fast(bars, price_bucket=0.25):
    """Build volume profile from bars (bucketed by price) - very fast."""
    profile = defaultdict(int)
    for _, bar in bars.iterrows():
        for price_level in [bar['high'], bar['open'], bar['close'], bar['low']]:
            bucket = round(price_level / price_bucket) * price_bucket
            profile[bucket] += int(bar['volume'] / 4)
    return profile


def find_signals(bars, params=PARAMS):
    """Scan bars for failed auction hook signals."""
    signals = []
    n = len(bars)
    va_pct = params['value_area_pct']
    breakout_ticks = params['breakout_threshold_ticks'] * NQ_TICK_SIZE
    reentry_ticks = params['reentry_tolerance_ticks'] * NQ_TICK_SIZE

    # Pre-compute session profile
    session_profile = build_volume_profile_fast(bars)
    if not session_profile:
        return signals

    # Find VA
    sorted_prices = sorted(session_profile.keys(), key=lambda p: session_profile[p], reverse=True)
    total_vol = sum(session_profile.values())
    cumul_vol = 0
    va_prices = []
    for p in sorted_prices:
        cumul_vol += session_profile[p]
        va_prices.append(p)
        if cumul_vol >= va_pct * total_vol:
            break

    if len(va_prices) < 2:
        return signals

    vah = max(va_prices)
    val = min(va_prices)

    # Scan bars for failed breaks
    for i in range(1, n - 1):
        current_bar = bars.iloc[i]
        prev_bar = bars.iloc[i - 1]

        # Failed upside breakout
        if (prev_bar['high'] > vah + breakout_ticks and
            current_bar['close'] < vah - reentry_ticks):
            signals.append({
                'bar_idx': i,
                'ts': current_bar['ts_utc'],
                'direction': 'short',
                'entry_price': current_bar['close'],
                'vah': vah,
                'failed_type': 'upside',
                'prev_high': prev_bar['high'],
            })

        # Failed downside breakout
        if (prev_bar['low'] < val - breakout_ticks and
            current_bar['close'] > val + reentry_ticks):
            signals.append({
                'bar_idx': i,
                'ts': current_bar['ts_utc'],
                'direction': 'long',
                'entry_price': current_bar['close'],
                'val': val,
                'failed_type': 'downside',
                'prev_low': prev_bar['low'],
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
        'strategy_id': '014',
        'strategy_name': 'Failed Auction Hook',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks over Mar 5-6 2026. RTH only.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '014_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
