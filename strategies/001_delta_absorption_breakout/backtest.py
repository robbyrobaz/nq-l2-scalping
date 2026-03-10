"""Strategy 001: Delta Absorption Breakout."""

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
    "range_window": 10,
    "max_range_pts": 25.0,
    "delta_threshold": 50,
    "absorption_bars": 1,
    "price_move_max_ticks": 2,
    "take_profit_ticks": 8,
    "stop_loss_ticks": 6,
    "session_filter": None,
}


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    specs: list[TradeSpec] = []
    rw = int(params["range_window"])
    ab = int(params["absorption_bars"])
    max_absorb_move = NQ_TICK_SIZE * float(params.get("price_move_max_ticks", 2))

    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    for i in range(rw + ab, len(bars) - 1):
        range_window = bars.iloc[i - rw - ab:i - ab]
        absorb_window = bars.iloc[i - ab:i]
        breakout = bars.iloc[i]
        if range_window.empty or absorb_window.empty:
            continue

        range_hi = float(range_window["high"].max())
        range_lo = float(range_window["low"].min())
        if range_hi - range_lo > float(params["max_range_pts"]):
            continue

        long_absorption = True
        short_absorption = True
        for bar in absorb_window.itertuples(index=False):
            close_move = float(bar.close - bar.open)
            long_absorption &= (
                float(bar.bar_delta) <= -float(params["delta_threshold"])
                and close_move >= -max_absorb_move
            )
            short_absorption &= (
                float(bar.bar_delta) >= float(params["delta_threshold"])
                and close_move <= max_absorb_move
            )

        # Absorption reversal: absorbed sellers at range_lo → long, absorbed buyers at range_hi → short
        # No breakout confirmation required; enter at market on the next bar
        direction = None
        if long_absorption:
            direction = "long"
        elif short_absorption:
            direction = "short"
        if direction is None:
            continue

        start_ts = pd.to_datetime(breakout.ts_utc, utc=True)
        start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
        future = ticks.iloc[start_idx:start_idx + 2000]
        if future.empty:
            continue

        row = future.iloc[0]
        entry_price = float(row.get("ask", np.nan)) if direction == "long" else float(row.get("bid", np.nan))
        if not np.isfinite(entry_price):
            continue
        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                signal_ts=start_ts,
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={
                    "breakout_bar_ts": str(breakout.ts_utc),
                    "defended_range_high": range_hi,
                    "defended_range_low": range_lo,
                    "breakout_close": float(breakout.close),
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
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    result = run_backtest()
    print(json.dumps(result["metrics"], indent=2))
