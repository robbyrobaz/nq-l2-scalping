"""Strategy 003: CVD Divergence (Absorption via Volume Spread Analysis)

When CVD makes a lower low but price doesn't (or vice versa), passive players
are absorbing aggressors. Trade the direction of the passive players.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import argrelextrema

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.data_loader import (
    load_trades, build_1min_bars_with_delta, compute_cvd, filter_rth,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq
)

PARAMS = {
    "divergence_window": 3,
    "min_cvd_move": 200,
    "confirmation_bars": 1,
    "price_tolerance_ticks": 10,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",
}


def find_local_extrema(series, order=5):
    """Find local minima and maxima indices."""
    maxima = argrelextrema(series.values, np.greater_equal, order=order)[0]
    minima = argrelextrema(series.values, np.less_equal, order=order)[0]
    return minima, maxima


def find_divergences(bars, params):
    """Find CVD vs price divergences.

    Bullish: CVD lower low + price equal/higher low → long
    Bearish: CVD higher high + price equal/lower high → short
    """
    signals = []
    dw = params['divergence_window']
    min_cvd = params['min_cvd_move']
    conf = params['confirmation_bars']

    prices = bars['close'].values
    cvd = bars['cvd'].values
    n = len(bars)

    price_lows_idx, price_highs_idx = find_local_extrema(pd.Series(prices), order=dw)
    cvd_lows_idx, cvd_highs_idx = find_local_extrema(pd.Series(cvd), order=dw)

    # Bullish divergence: CVD lower low, price higher/equal low
    for i in range(1, len(cvd_lows_idx)):
        ci = cvd_lows_idx[i]
        ci_prev = cvd_lows_idx[i - 1]

        if ci >= n - conf - 1:
            continue

        # CVD lower low
        if cvd[ci] >= cvd[ci_prev]:
            continue
        if abs(cvd[ci] - cvd[ci_prev]) < min_cvd:
            continue

        # Find nearest price low near ci
        nearby_price_lows = price_lows_idx[
            (price_lows_idx >= ci - dw) & (price_lows_idx <= ci + dw)
        ]
        if len(nearby_price_lows) == 0:
            continue

        # Find previous price low near ci_prev
        nearby_price_lows_prev = price_lows_idx[
            (price_lows_idx >= ci_prev - dw) & (price_lows_idx <= ci_prev + dw)
        ]
        if len(nearby_price_lows_prev) == 0:
            continue

        price_at_ci = prices[nearby_price_lows[-1]]
        price_at_prev = prices[nearby_price_lows_prev[-1]]

        # Price equal or higher low (divergence)
        price_tol = params.get('price_tolerance_ticks', 10) * NQ_TICK_SIZE
        if price_at_ci < price_at_prev - price_tol:
            continue

        # Confirmation: check next conf bars have rising price
        confirmed = True
        entry_idx = ci + conf
        if entry_idx >= n:
            continue

        for c in range(1, conf + 1):
            if ci + c >= n:
                confirmed = False
                break
            if prices[ci + c] < prices[ci]:
                confirmed = False
                break

        if confirmed:
            signals.append({
                'bar_idx': entry_idx,
                'ts': bars.iloc[entry_idx]['ts_utc'],
                'direction': 'long',
                'entry_price': float(bars.iloc[entry_idx]['open']),
                'cvd_low': float(cvd[ci]),
                'cvd_low_prev': float(cvd[ci_prev]),
                'price_low': float(price_at_ci),
                'price_low_prev': float(price_at_prev),
            })

    # Bearish divergence: CVD higher high, price lower/equal high
    for i in range(1, len(cvd_highs_idx)):
        ci = cvd_highs_idx[i]
        ci_prev = cvd_highs_idx[i - 1]

        if ci >= n - conf - 1:
            continue

        # CVD higher high
        if cvd[ci] <= cvd[ci_prev]:
            continue
        if abs(cvd[ci] - cvd[ci_prev]) < min_cvd:
            continue

        nearby_price_highs = price_highs_idx[
            (price_highs_idx >= ci - dw) & (price_highs_idx <= ci + dw)
        ]
        if len(nearby_price_highs) == 0:
            continue

        nearby_price_highs_prev = price_highs_idx[
            (price_highs_idx >= ci_prev - dw) & (price_highs_idx <= ci_prev + dw)
        ]
        if len(nearby_price_highs_prev) == 0:
            continue

        price_at_ci = prices[nearby_price_highs[-1]]
        price_at_prev = prices[nearby_price_highs_prev[-1]]

        # Price equal or lower high
        price_tol = params.get('price_tolerance_ticks', 10) * NQ_TICK_SIZE
        if price_at_ci > price_at_prev + price_tol:
            continue

        confirmed = True
        entry_idx = ci + conf
        if entry_idx >= n:
            continue

        for c in range(1, conf + 1):
            if ci + c >= n:
                confirmed = False
                break
            if prices[ci + c] > prices[ci]:
                confirmed = False
                break

        if confirmed:
            signals.append({
                'bar_idx': entry_idx,
                'ts': bars.iloc[entry_idx]['ts_utc'],
                'direction': 'short',
                'entry_price': float(bars.iloc[entry_idx]['open']),
                'cvd_high': float(cvd[ci]),
                'cvd_high_prev': float(cvd[ci_prev]),
                'price_high': float(price_at_ci),
                'price_high_prev': float(price_at_prev),
            })

    return signals


def simulate_trades(signals, bars, params):
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

    print("Loading trades...")
    trades_df = load_trades()
    print(f"Building 1-min bars from {len(trades_df)} ticks...")
    bars = build_1min_bars_with_delta(trades_df)
    bars = compute_cvd(bars)
    bars = filter_rth(bars)
    print(f"RTH bars: {len(bars)}")
    bars = bars.reset_index(drop=True)

    print("Scanning for CVD divergences...")
    signals = find_divergences(bars, params)
    print(f"Signals found: {len(signals)}")

    if not signals:
        print("No signals with default params. Trying relaxed parameters...")
        relaxed = params.copy()
        relaxed['min_cvd_move'] = 100
        relaxed['divergence_window'] = 3
        relaxed['confirmation_bars'] = 1
        relaxed['price_tolerance_ticks'] = 20
        signals = find_divergences(bars, relaxed)
        print(f"Signals with relaxed params: {len(signals)}")
        params = relaxed

    trade_list = simulate_trades(signals, bars, params)
    print(f"Trades: {len(trade_list)}")

    metrics = compute_metrics(trade_list)
    print(f"Metrics: {metrics}")

    result = {
        'strategy_id': '003',
        'strategy_name': 'CVD Divergence Absorption',
        'backtest_period': {
            'start': str(bars['ts_utc'].min()),
            'end': str(bars['ts_utc'].max()),
        },
        'metrics': metrics,
        'params': params,
        'trades': trade_list,
        'notes': f'Data: {len(trades_df)} ticks. RTH only. CVD reset at session open. Mar 5-6 2026.',
    }

    out = Path(__file__).resolve().parents[2] / 'data' / 'results' / '003_2026-03-06.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Results saved to {out}")

    return result


if __name__ == '__main__':
    run()
