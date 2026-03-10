"""Strategy 005: Large Print Momentum."""

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
    "lookback_ticks": 200,
    "std_dev_threshold": 2.0,
    "min_trade_size": 50,
    "signal_cooldown_ticks": 50,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _build_specs(ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    lookback = int(params.get("lookback_ticks", params.get("lookback_bars", 200)))
    cooldown = int(params.get("signal_cooldown_ticks", params.get("signal_cooldown_bars", 50)))
    sizes = ticks["size"].astype(float)
    mean = sizes.rolling(lookback, min_periods=lookback).mean()
    std = sizes.rolling(lookback, min_periods=lookback).std(ddof=0).fillna(0.0)

    specs: list[TradeSpec] = []
    last_signal_idx = -cooldown
    # Vectorized — avoid Python loop over millions of ticks
    threshold_arr = mean.to_numpy() + float(params["std_dev_threshold"]) * std.to_numpy()
    threshold_arr = np.maximum(threshold_arr, float(params["min_trade_size"]))
    valid = (sizes.to_numpy() >= threshold_arr) & np.isin(ticks["side"].to_numpy(), ["B", "S"])
    candidate_idxs = np.where(valid)[0]
    candidate_idxs = candidate_idxs[(candidate_idxs >= lookback) & (candidate_idxs < len(ticks) - 1)]

    specs: list[TradeSpec] = []
    last_signal_idx = -cooldown
    for i in candidate_idxs:
        if i - last_signal_idx < cooldown:
            continue
        row = ticks.iloc[i]; entry_row = ticks.iloc[i + 1]
        direction = "long" if row["side"] == "B" else "short"
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(TradeSpec(
            entry_ts=pd.to_datetime(entry_row["ts_utc"], utc=True),
            signal_ts=pd.to_datetime(row["ts_utc"], utc=True),
            direction=direction, entry_price=entry_price,
            stop_loss_ticks=float(params["stop_loss_ticks"]),
            take_profit_ticks=float(params["take_profit_ticks"]),
            meta={"large_print_size": float(row["size"])},
        ))
        last_signal_idx = i
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
