"""Strategy 006: Tape Streak."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import filter_sessions
from pipeline.strategy_cache import trades_with_nbbo


PARAMS = {
    "min_consecutive_trades": 5,
    "min_total_volume": 0,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _build_specs(ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    specs: list[TradeSpec] = []
    streak_side = None
    streak_count = 0
    streak_volume = 0.0
    streak_start_idx = 0
    signaled = False

    for i, row in enumerate(ticks.itertuples(index=False)):
        side = row.side
        if side in {"B", "S"}:
            if side == streak_side:
                streak_count += 1
                streak_volume += float(row.size)
            else:
                streak_side = side
                streak_count = 1
                streak_volume = float(row.size)
                streak_start_idx = i
                signaled = False
        elif streak_side is None:
            continue

        if signaled or streak_side is None:
            continue
        if streak_count < int(params["min_consecutive_trades"]) or streak_volume < float(params["min_total_volume"]):
            continue

        signal_ts = pd.to_datetime(row.ts_utc, utc=True)
        future = ticks.iloc[i + 1:i + 2001]
        fill = future[(future["side"] != streak_side) | (future["side"] == "")].head(1)
        if fill.empty:
            fill = future[future["ts_utc"] >= signal_ts + pd.Timedelta(seconds=1)].head(1)
        if fill.empty:
            continue
        entry_row = fill.iloc[0]
        direction = "long" if streak_side == "B" else "short"
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(entry_row["ts_utc"], utc=True),
                signal_ts=signal_ts,
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={
                    "streak_start_ts": str(ticks.iloc[streak_start_idx]["ts_utc"]),
                    "streak_count": int(streak_count),
                    "streak_volume": float(streak_volume),
                },
            )
        )
        signaled = True
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    specs = _build_specs(ticks, params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, ticks)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest()["metrics"], indent=2))
