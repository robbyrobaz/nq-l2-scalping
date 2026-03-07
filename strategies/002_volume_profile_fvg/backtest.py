"""Strategy 002: Volume Profile Fair Value Gap Rejection

After a significant price leg, builds a tick-level volume profile and finds
the lowest-volume node within the value area. When price retraces to that
node, enters a fade trade.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades_fast, load_bars_1min, filter_rth,
    compute_volume_profile, NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq
)

PARAMS = {
    "swing_lookback": 20,
    "min_leg_size_ticks": 20,
    "value_area_pct": 0.70,
    "entry_zone_ticks": 2,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "max_retrace_time_bars": 30,
}


def find_swings(bars, lookback=20):
    """Find swing highs and lows using scipy find_peaks."""
    closes = bars['close'].values
    highs = bars['high'].values
    lows = bars['low'].values

    # Swing highs: peaks in highs
    hi_idx, _ = find_peaks(highs, distance=lookback // 2, prominence=NQ_TICK_SIZE * 5)
    # Swing lows: peaks in inverted lows
    lo_idx, _ = find_peaks(-lows, distance=lookback // 2, prominence=NQ_TICK_SIZE * 5)

    swings = []
    for i in hi_idx:
        swings.append({'idx': int(i), 'type': 'high', 'price': float(highs[i]), 'ts': bars.iloc[i]['ts_utc']})
    for i in lo_idx:
        swings.append({'idx': int(i), 'type': 'low', 'price': float(lows[i]), 'ts': bars.iloc[i]['ts_utc']})

    swings.sort(key=lambda s: s['idx'])
    return swings


def find_fvg_levels(swings, trades_df, bars, params):
    """For each leg (swing pair), find the lowest-volume node in the value area."""
    fvg_levels = []
    min_leg = params['min_leg_size_ticks'] * NQ_TICK_SIZE
    va_pct = params['value_area_pct']

    for i in range(len(swings) - 1):
        a, b = swings[i], swings[i + 1]
        if a['type'] == b['type']:
            continue

        leg_size = abs(b['price'] - a['price'])
        if leg_size < min_leg:
            continue

        price_lo = min(a['price'], b['price'])
        price_hi = max(a['price'], b['price'])

        profile = compute_volume_profile(
            trades_df, price_lo, price_hi,
            start_ts=a['ts'], end_ts=b['ts']
        )

        if not profile:
            continue

        # Find POC and Value Area
        total_vol = sum(profile.values())
        if total_vol == 0:
            continue

        poc_price = max(profile, key=profile.get)

        # Build value area by expanding outward from POC
        sorted_prices = sorted(profile.keys())
        poc_idx = sorted_prices.index(poc_price) if poc_price in sorted_prices else 0
        va_vol = profile[poc_price]
        lo_ptr = poc_idx - 1
        hi_ptr = poc_idx + 1
        va_prices = {poc_price}

        while va_vol / total_vol < va_pct and (lo_ptr >= 0 or hi_ptr < len(sorted_prices)):
            lo_vol = profile.get(sorted_prices[lo_ptr], 0) if lo_ptr >= 0 else 0
            hi_vol = profile.get(sorted_prices[hi_ptr], 0) if hi_ptr < len(sorted_prices) else 0

            if lo_vol >= hi_vol and lo_ptr >= 0:
                va_vol += lo_vol
                va_prices.add(sorted_prices[lo_ptr])
                lo_ptr -= 1
            elif hi_ptr < len(sorted_prices):
                va_vol += hi_vol
                va_prices.add(sorted_prices[hi_ptr])
                hi_ptr += 1
            else:
                break

        # Find lowest volume node within value area
        va_profile = {p: v for p, v in profile.items() if p in va_prices}
        if not va_profile:
            continue

        fvg_price = min(va_profile, key=va_profile.get)

        direction = 'long' if b['price'] > a['price'] else 'short'

        fvg_levels.append({
            'leg_start_idx': a['idx'],
            'leg_end_idx': b['idx'],
            'leg_start_ts': a['ts'],
            'leg_end_ts': b['ts'],
            'fvg_price': fvg_price,
            'direction': direction,
            'poc': poc_price,
            'leg_size': leg_size,
        })

    return fvg_levels


def find_signals(fvg_levels, bars, params):
    """Find retracement entries when price touches FVG level."""
    signals = []
    zone = params['entry_zone_ticks'] * NQ_TICK_SIZE
    max_bars = params['max_retrace_time_bars']

    for fvg in fvg_levels:
        start_idx = fvg['leg_end_idx'] + 1
        end_idx = min(start_idx + max_bars, len(bars))

        for i in range(start_idx, end_idx):
            bar = bars.iloc[i]
            # Price touches FVG level
            if bar['low'] <= fvg['fvg_price'] + zone and bar['high'] >= fvg['fvg_price'] - zone:
                signals.append({
                    'bar_idx': i,
                    'ts': bar['ts_utc'],
                    'direction': fvg['direction'],
                    'entry_price': fvg['fvg_price'],
                    'fvg_price': fvg['fvg_price'],
                    'poc': fvg['poc'],
                })
                break

    return signals


def simulate_trades(signals, bars, params):
    """Simulate TP/SL exits."""
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
                    trades.append(_trade(sig, bar, entry - sl, -params['stop_loss_ticks']))
                    exited = True
                    break
                if bar['high'] >= entry + tp:
                    trades.append(_trade(sig, bar, entry + tp, params['take_profit_ticks']))
                    exited = True
                    break
            else:
                if bar['high'] >= entry + sl:
                    trades.append(_trade(sig, bar, entry + sl, -params['stop_loss_ticks']))
                    exited = True
                    break
                if bar['low'] <= entry - tp:
                    trades.append(_trade(sig, bar, entry - tp, params['take_profit_ticks']))
                    exited = True
                    break

        if not exited:
            last = bars.iloc[-1]
            pnl = (last['close'] - entry) / NQ_TICK_SIZE if direction == 'long' else (entry - last['close']) / NQ_TICK_SIZE
            trades.append(_trade(sig, last, last['close'], pnl))

    return trades


def _trade(sig, exit_bar, exit_price, pnl_ticks):
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
        'net_pnl_usd': round(pnl_mnq(sum(pnls)), 2),
        'max_drawdown_pct': round(float(max_dd), 1),
    }


def run(params=None):
    if params is None:
        params = PARAMS

    print("Loading 1-min bars...")
    bars = load_bars_1min()
    bars = filter_rth(bars)
    print(f"RTH bars: {len(bars)}")

    print("Loading trade ticks for volume profiles...")
    trades_df = load_trades_fast()
    print(f"Trade ticks: {len(trades_df)}")

    print("Finding swings...")
    swings = find_swings(bars, params['swing_lookback'])
    print(f"Swings found: {len(swings)}")

    # Try with relaxed params if no swings
    if len(swings) < 2:
        print("Not enough swings. Trying shorter lookback...")
        swings = find_swings(bars, lookback=10)
        print(f"Swings with lookback=10: {len(swings)}")
        params = params.copy()
        params['swing_lookback'] = 10

    print("Finding FVG levels...")
    fvg_levels = find_fvg_levels(swings, trades_df, bars, params)
    print(f"FVG levels: {len(fvg_levels)}")

    if not fvg_levels:
        print("No FVG levels found. Trying relaxed min_leg_size...")
        params = params.copy()
        params['min_leg_size_ticks'] = 10
        fvg_levels = find_fvg_levels(swings, trades_df, bars, params)
        print(f"FVG levels with relaxed leg: {len(fvg_levels)}")

    print("Finding entry signals...")
    signals = find_signals(fvg_levels, bars, params)
    print(f"Entry signals: {len(signals)}")

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '002',
        'strategy_name': 'Volume Profile FVG Rejection',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks, {len(bars)} RTH bars. Mar 5-6 2026.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '002_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
