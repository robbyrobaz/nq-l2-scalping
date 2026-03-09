"""Strategy 010: Initiative Auction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import filter_sessions
from pipeline.strategy_cache import bars_with_delta, trades_with_nbbo


PARAMS = {
    "delta_threshold": 300,
    "volume_avg_period": 20,
    "volume_multiplier": 1.5,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    avg_vol = bars["volume"].rolling(int(params["volume_avg_period"]), min_periods=int(params["volume_avg_period"])).mean()
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []
    for i, row in enumerate(bars.itertuples(index=False)):
        if i < int(params["volume_avg_period"]) or not np.isfinite(avg_vol.iloc[i]):
            continue
        direction = None
        if float(row.volume) >= float(avg_vol.iloc[i]) * float(params["volume_multiplier"]) and float(row.bar_delta) >= float(params["delta_threshold"]) and float(row.close) > float(row.open):
            direction = "long"
        elif float(row.volume) >= float(avg_vol.iloc[i]) * float(params["volume_multiplier"]) and float(row.bar_delta) <= -float(params["delta_threshold"]) and float(row.close) < float(row.open):
            direction = "short"
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
