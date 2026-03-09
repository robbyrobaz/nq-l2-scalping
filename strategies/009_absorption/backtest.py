"""Strategy 009: Absorption."""

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
    "delta_threshold": 250,
    "close_move_ticks": 1,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    close_move = float(params.get("close_move_ticks", params.get("close_move_required_ticks", 1))) * NQ_TICK_SIZE
    specs: list[TradeSpec] = []
    for row in bars.itertuples(index=False):
        direction = None
        if float(row.bar_delta) >= float(params["delta_threshold"]) and float(row.close) <= float(row.open) - close_move:
            direction = "short"
        elif float(row.bar_delta) <= -float(params["delta_threshold"]) and float(row.close) >= float(row.open) + close_move:
            direction = "long"
        if direction is None:
            continue
        entry_ts = pd.to_datetime(row.ts_utc, utc=True) + pd.Timedelta(minutes=1)
        idx = int(np.searchsorted(tick_ts, entry_ts.value, side="left"))
        if idx >= len(ticks):
            continue
        entry_row = ticks.iloc[idx]
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(TradeSpec(pd.to_datetime(entry_row["ts_utc"], utc=True), direction, entry_price, float(params["stop_loss_ticks"]), float(params["take_profit_ticks"]), signal_ts=entry_ts))
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    bars = filter_sessions(bars_with_delta(), sessions=params.get("session_filter")).reset_index(drop=True)
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    trades = iter_trade_specs(_build_specs(bars, ticks, params), ticks)
    metrics = compute_trade_metrics(trades, bars)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest()["metrics"], indent=2))
