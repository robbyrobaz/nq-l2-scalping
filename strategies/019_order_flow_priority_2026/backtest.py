"""Strategy 019: Order Flow Priority 2026.

Source: Bear Bull Traders - Market Atlas orderflow tactics
Core concept: Opening range breakout + DOM liquidity pool targeting

Logic:
1. Detect opening range (first N bars of session)
2. Wait for breakout (close > OR high for long, close < OR low for short)
3. Check DOM for large liquidity pools in breakout direction
4. Enter towards the liquidity pool
5. Exit at pool level or TP/SL

Key insight from video:
- "Price goes towards liquidity pools" - large DOM orders act as magnets
- Combine chart patterns (ORB, ABC, bull flag) with DOM confirmation
- Target the liquidity level itself
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import (
    NQ_TICK_SIZE,
    filter_sessions,
    load_depth_raw,
    precompute_dom_series,
)
from pipeline.strategy_cache import bars_with_delta, trades_with_nbbo


PARAMS = {
    "or_bars": 5,  # Opening range bars (5 = first 5 min)
    "liquidity_threshold_mult": 3.0,  # 3x average book size = "large" pool
    "max_pool_distance_ticks": 40,  # Max distance to liquidity pool (10 pts)
    "min_breakout_ticks": 4,  # Min breakout size (1 pt)
    "take_profit_ticks": 16,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",
}


def _find_liquidity_pools(dom_df: pd.DataFrame, current_ts, direction: str, params: dict):
    """Find large liquidity pools in the DOM near current timestamp.

    Returns: (pool_price, pool_size) or (None, None) if no pool found
    """
    # Get DOM snapshot near current_ts (within 1 second)
    window_start = current_ts - pd.Timedelta(seconds=1)
    window_end = current_ts + pd.Timedelta(seconds=1)
    snapshot = dom_df[
        (dom_df['ts_utc'] >= window_start) & (dom_df['ts_utc'] <= window_end)
    ].copy()

    if snapshot.empty:
        return None, None

    # Get most recent snapshot
    latest_ts = snapshot['ts_utc'].max()
    snapshot = snapshot[snapshot['ts_utc'] == latest_ts]

    # Filter to relevant side: ask for longs, bid for shorts
    side_filter = 'ask' if direction == 'long' else 'bid'
    levels = snapshot[snapshot['side'].str.lower().str.startswith(side_filter[0])].copy()

    if levels.empty:
        return None, None

    # Calculate average size across all levels
    avg_size = levels['size'].mean()
    threshold = avg_size * float(params['liquidity_threshold_mult'])

    # Find pools above threshold
    large_pools = levels[levels['size'] >= threshold].copy()

    if large_pools.empty:
        return None, None

    # Return closest pool (by position - position 0 is closest)
    large_pools = large_pools.sort_values('position')
    pool = large_pools.iloc[0]

    return float(pool['price']), float(pool['size'])


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, dom_df: pd.DataFrame, params: dict) -> list[TradeSpec]:
    """Generate trade specs based on opening range breakout + DOM liquidity pools."""
    specs: list[TradeSpec] = []
    or_bars = int(params['or_bars'])
    min_breakout_ticks = float(params['min_breakout_ticks'])
    max_pool_distance_ticks = float(params['max_pool_distance_ticks'])

    if bars.empty or dom_df.empty:
        return specs

    # Group bars by session
    bars = bars.reset_index(drop=True)
    bars['date'] = bars['ts_utc'].dt.date

    tick_ts = ticks['ts_utc'].astype('int64').to_numpy()

    for date, session_bars in bars.groupby('date'):
        session_bars = session_bars.reset_index(drop=True)

        if len(session_bars) < or_bars + 2:
            continue

        # Define opening range
        or_window = session_bars.iloc[:or_bars]
        or_high = float(or_window['high'].max())
        or_low = float(or_window['low'].min())
        or_range = or_high - or_low

        # Skip if opening range too tight (no volatility)
        if or_range < NQ_TICK_SIZE * min_breakout_ticks:
            continue

        # Check for breakouts after opening range
        for i in range(or_bars, len(session_bars) - 1):
            bar = session_bars.iloc[i]
            prev_bar = session_bars.iloc[i - 1]

            # Long breakout: close > OR high
            if float(bar['close']) > or_high and float(prev_bar['close']) <= or_high:
                direction = 'long'
                breakout_price = or_high
            # Short breakout: close < OR low
            elif float(bar['close']) < or_low and float(prev_bar['close']) >= or_low:
                direction = 'short'
                breakout_price = or_low
            else:
                continue

            # Check for liquidity pool in DOM (if available)
            pool_price = None
            pool_size = None
            pool_distance = None

            if not dom_df.empty:
                bar_ts = pd.to_datetime(bar['ts_utc'], utc=True)
                pool_price, pool_size = _find_liquidity_pools(dom_df, bar_ts, direction, params)

                if pool_price is None:
                    continue

                # Verify pool is in breakout direction and within max distance
                if direction == 'long':
                    pool_distance = pool_price - float(bar['close'])
                    if pool_distance <= 0 or pool_distance > NQ_TICK_SIZE * max_pool_distance_ticks:
                        continue
                else:  # short
                    pool_distance = float(bar['close']) - pool_price
                    if pool_distance <= 0 or pool_distance > NQ_TICK_SIZE * max_pool_distance_ticks:
                        continue
            # If no DOM data, trade pure opening range breakout

            # Enter on next bar
            start_ts = pd.to_datetime(bar['ts_utc'], utc=True)
            start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side='left'))
            future = ticks.iloc[start_idx:start_idx + 2000]

            if future.empty:
                continue

            row = future.iloc[0]
            entry_price = float(row.get('ask', np.nan)) if direction == 'long' else float(row.get('bid', np.nan))

            if not np.isfinite(entry_price):
                continue

            specs.append(
                TradeSpec(
                    entry_ts=pd.to_datetime(row['ts_utc'], utc=True),
                    signal_ts=start_ts,
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss_ticks=float(params['stop_loss_ticks']),
                    take_profit_ticks=float(params['take_profit_ticks']),
                    meta={
                        'or_high': or_high,
                        'or_low': or_low,
                        'breakout_price': breakout_price,
                        'liquidity_pool_price': pool_price if pool_price else None,
                        'liquidity_pool_size': pool_size if pool_size else None,
                        'pool_distance_ticks': pool_distance / NQ_TICK_SIZE if pool_distance else None,
                        'dom_available': not dom_df.empty,
                    },
                )
            )

            # Only take first breakout per session per direction to avoid overtrading
            break

    return specs


def run_backtest(params=PARAMS) -> dict:
    """Run backtest with opening range + DOM liquidity pool logic."""
    params = {**PARAMS, **(params or {})}

    # Load data
    print("Loading bars...")
    bars = filter_sessions(bars_with_delta(), sessions=params.get('session_filter'))
    print(f"Loaded {len(bars)} bars")

    print("Loading ticks...")
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get('session_filter'))
    print(f"Loaded {len(ticks)} ticks")

    # Load DOM depth data
    # Note: This may take 2-5 minutes due to concurrent data collection
    if bars.empty:
        dom_df = pd.DataFrame()
    else:
        start_ts = bars['ts_utc'].min()
        end_ts = bars['ts_utc'].max()
        print(f"Loading DOM data from {start_ts} to {end_ts} (may take a few minutes)...")
        dom_df = load_depth_raw(start_ts=start_ts, end_ts=end_ts)
        dom_df['ts_utc'] = pd.to_datetime(dom_df['ts_utc'], utc=True, errors='coerce')
        print(f"Loaded {len(dom_df):,} DOM snapshots")

    print("Generating trade signals...")
    specs = _build_specs(bars.reset_index(drop=True), ticks.reset_index(drop=True), dom_df, params)
    print(f"Generated {len(specs)} trade specs")

    print("Simulating trades...")
    trades = iter_trade_specs(specs, ticks)
    print(f"Executed {len(trades)} trades")

    print("Computing metrics...")
    metrics = compute_trade_metrics(trades, bars)
    print("Done!")

    return {
        'trades': trades,
        'metrics': {k: v for k, v in metrics.items() if k != 'session_breakdown'},
        'session_breakdown': metrics.get('session_breakdown', {})
    }


def run(params=None):
    """Entry point for optimizer."""
    return run_backtest(params=params or PARAMS)


if __name__ == '__main__':
    result = run_backtest()
    print(json.dumps(result['metrics'], indent=2))
