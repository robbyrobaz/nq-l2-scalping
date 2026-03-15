"""Strategy 018: Delta Absorption Live Trade.

Concept: Large limit orders in the book act as price magnets. When significant
bid/ask walls appear, price tends to move toward these levels. Entry on momentum
toward the big order, target at the order level.

Based on Andrew Aziz's live trade using Market Atlas order flow.
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
    "volume_spike_multiplier": 3.0,  # Volume spike = 3x rolling average volume
    "lookback_bars": 20,  # Bars to compute rolling average volume
    "min_delta_momentum": 200,  # Minimum bar delta for momentum confirmation
    "min_price_move_ticks": 2,  # Min price move in direction of delta
    "take_profit_ticks": 12,  # Target profit
    "stop_loss_ticks": 8,  # Stop loss
    "session_filter": ["NYOpen", "MidDay", "PowerHour"],
}


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    """Build trade specs by detecting volume spikes (proxy for big orders) + delta momentum.

    Logic: When volume spikes significantly above average, it suggests large orders hitting
    the tape. Combined with strong delta, this indicates directional conviction.
    """
    specs: list[TradeSpec] = []

    if bars.empty:
        return specs

    lookback = int(params["lookback_bars"])
    volume_mult = float(params["volume_spike_multiplier"])
    min_delta = float(params["min_delta_momentum"])
    min_move = NQ_TICK_SIZE * float(params["min_price_move_ticks"])

    # Compute rolling average volume
    bars = bars.copy()
    bars["volume_ma"] = bars["volume"].rolling(window=lookback, min_periods=1).mean()

    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()

    for i in range(lookback, len(bars) - 1):
        bar = bars.iloc[i]

        volume = float(bar["volume"])
        volume_ma = float(bar["volume_ma"])
        bar_delta = float(bar["bar_delta"])
        bar_range = float(bar["high"]) - float(bar["low"])
        bar_close = float(bar["close"])
        bar_open = float(bar["open"])
        price_move = bar_close - bar_open

        # Skip if no volume spike
        if volume_ma == 0 or volume < volume_mult * volume_ma:
            continue

        # Skip if no meaningful price move
        if abs(price_move) < min_move:
            continue

        direction = None

        # Long: volume spike + strong positive delta + bullish price action
        if bar_delta >= min_delta and price_move > 0:
            direction = "long"

        # Short: volume spike + strong negative delta + bearish price action
        elif bar_delta <= -min_delta and price_move < 0:
            direction = "short"

        if direction is None:
            continue

        # Entry at next bar
        bar_ts = pd.to_datetime(bar.ts_utc, utc=True)
        start_idx = int(np.searchsorted(tick_ts, bar_ts.value // 1000, side="left"))
        future = ticks.iloc[start_idx:start_idx + 2000]
        if future.empty:
            continue

        entry_tick = future.iloc[0]
        entry_price = float(entry_tick.get("ask", np.nan)) if direction == "long" else float(entry_tick.get("bid", np.nan))

        if not np.isfinite(entry_price):
            continue

        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(entry_tick["ts_utc"], utc=True),
                signal_ts=bar_ts,
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={
                    "signal_bar_ts": str(bar.ts_utc),
                    "bar_delta": bar_delta,
                    "volume": volume,
                    "volume_ma": volume_ma,
                    "volume_ratio": volume / volume_ma if volume_ma > 0 else 0,
                    "price_move": price_move,
                },
            )
        )

    return specs


def run_backtest(params=PARAMS) -> dict:
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
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    result = run_backtest()
    print(json.dumps(result["metrics"], indent=2))
