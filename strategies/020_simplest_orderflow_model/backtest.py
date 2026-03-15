"""Strategy 020: Simplest Orderflow Model (IVB - Invalid/Initial Balance Breakout).

Source: Fabervaale - Opening Range + IVB
Video: https://www.youtube.com/watch?v=cUTsoU-15Tc

Core Logic:
1. Define opening range (IVB) in first N minutes of RTH session
2. Enter long on breakout above IVB high, short on breakout below IVB low
3. Optional: wait for retest/pullback to improve risk/reward
4. Exit at fixed TP/SL

Key Concept: "Who won the battle of the most important time of the day" (first 15-30 min)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import NQ_TICK_SIZE, filter_sessions
from pipeline.strategy_cache import bars_with_delta, trades_with_nbbo


PARAMS = {
    "opening_range_bars": 30,  # Number of bars to define IVB (15-60 min)
    "wait_for_retest": False,  # Wait for pullback after breakout
    "retest_lookback": 10,  # Bars to wait for retest
    "retest_proximity_ticks": 4,  # How close to IVB level for valid retest
    "take_profit_ticks": 16,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",  # Only trade RTH for opening range logic
}


def _find_session_start_indices(bars: pd.DataFrame) -> list[int]:
    """Find indices where new RTH sessions start (9:30 ET)."""
    bars = bars.reset_index(drop=True)

    # Convert to ET timezone and extract date + hour/minute
    ts_et = pd.to_datetime(bars["ts_utc"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    hour = ts_et.dt.hour
    minute = ts_et.dt.minute
    date = ts_et.dt.date

    # Find 9:30 ET bars
    is_930 = (hour == 9) & (minute == 30)

    # Find first 9:30 bar of each day
    date_changed = date != date.shift(1)
    session_starts = bars.index[is_930 & date_changed].tolist()

    return session_starts


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    """Build trade specs from IVB opening range breakout logic."""
    specs: list[TradeSpec] = []
    or_bars = int(params["opening_range_bars"])
    wait_retest = bool(params["wait_for_retest"])
    retest_lookback = int(params["retest_lookback"])
    retest_prox = NQ_TICK_SIZE * float(params["retest_proximity_ticks"])

    session_starts = _find_session_start_indices(bars)
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()

    for session_idx in session_starts:
        # Define opening range (IVB)
        or_end_idx = session_idx + or_bars
        if or_end_idx >= len(bars):
            continue

        or_window = bars.iloc[session_idx:or_end_idx]
        if len(or_window) < or_bars:
            continue

        ivb_high = float(or_window["high"].max())
        ivb_low = float(or_window["low"].min())

        # Track if we've entered a trade for this session
        entered_long = False
        entered_short = False

        # Scan bars after opening range for breakout
        for i in range(or_end_idx, min(or_end_idx + 360, len(bars) - 1)):  # Max 6 hours after OR
            bar = bars.iloc[i]

            # Check for IVB high breakout (long)
            if not entered_long and float(bar.close) > ivb_high:
                direction = "long"
                breakout_bar_idx = i

                # Wait for retest if configured
                entry_bar_idx = None
                if wait_retest:
                    # Look for pullback within next N bars
                    for j in range(i + 1, min(i + retest_lookback + 1, len(bars))):
                        test_bar = bars.iloc[j]
                        # Retest = low comes within X ticks of IVB high
                        if abs(float(test_bar.low) - ivb_high) <= retest_prox:
                            entry_bar_idx = j
                            break
                    if entry_bar_idx is None:
                        continue  # No retest found
                else:
                    entry_bar_idx = i

                # Create trade spec
                entry_bar = bars.iloc[entry_bar_idx]
                start_ts = pd.to_datetime(entry_bar.ts_utc, utc=True)
                start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
                future = ticks.iloc[start_idx:start_idx + 2000]
                if future.empty:
                    continue

                row = future.iloc[0]
                entry_price = float(row.get("ask", np.nan))
                if not np.isfinite(entry_price):
                    continue

                specs.append(
                    TradeSpec(
                        entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                        signal_ts=pd.to_datetime(bars.iloc[breakout_bar_idx].ts_utc, utc=True),
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_ticks=float(params["stop_loss_ticks"]),
                        take_profit_ticks=float(params["take_profit_ticks"]),
                        meta={
                            "ivb_high": ivb_high,
                            "ivb_low": ivb_low,
                            "breakout_bar_idx": breakout_bar_idx,
                            "entry_bar_idx": entry_bar_idx,
                            "waited_for_retest": wait_retest,
                        },
                    )
                )
                entered_long = True

            # Check for IVB low breakout (short)
            elif not entered_short and float(bar.close) < ivb_low:
                direction = "short"
                breakout_bar_idx = i

                # Wait for retest if configured
                entry_bar_idx = None
                if wait_retest:
                    # Look for pullback within next N bars
                    for j in range(i + 1, min(i + retest_lookback + 1, len(bars))):
                        test_bar = bars.iloc[j]
                        # Retest = high comes within X ticks of IVB low
                        if abs(float(test_bar.high) - ivb_low) <= retest_prox:
                            entry_bar_idx = j
                            break
                    if entry_bar_idx is None:
                        continue  # No retest found
                else:
                    entry_bar_idx = i

                # Create trade spec
                entry_bar = bars.iloc[entry_bar_idx]
                start_ts = pd.to_datetime(entry_bar.ts_utc, utc=True)
                start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
                future = ticks.iloc[start_idx:start_idx + 2000]
                if future.empty:
                    continue

                row = future.iloc[0]
                entry_price = float(row.get("bid", np.nan))
                if not np.isfinite(entry_price):
                    continue

                specs.append(
                    TradeSpec(
                        entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                        signal_ts=pd.to_datetime(bars.iloc[breakout_bar_idx].ts_utc, utc=True),
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_ticks=float(params["stop_loss_ticks"]),
                        take_profit_ticks=float(params["take_profit_ticks"]),
                        meta={
                            "ivb_high": ivb_high,
                            "ivb_low": ivb_low,
                            "breakout_bar_idx": breakout_bar_idx,
                            "entry_bar_idx": entry_bar_idx,
                            "waited_for_retest": wait_retest,
                        },
                    )
                )
                entered_short = True

            # Only one trade per session per direction
            if entered_long and entered_short:
                break

    return specs


def run_backtest(params=PARAMS) -> dict:
    """Run IVB opening range breakout backtest."""
    params = {**PARAMS, **(params or {})}
    bars = filter_sessions(bars_with_delta(), sessions=params.get("session_filter"))
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter"))

    specs = _build_specs(bars.reset_index(drop=True), ticks.reset_index(drop=True), params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, bars)
    return {
        "trades": trades,
        "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"},
        "session_breakdown": metrics.get("session_breakdown", {}),
    }


def run(params=None):
    """Entry point for optimizer."""
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    result = run_backtest()
    print(json.dumps(result["metrics"], indent=2))
