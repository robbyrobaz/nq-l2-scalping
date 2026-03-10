"""Strategy 013: Value Area Rejection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs, profile_to_levels
from pipeline.data_loader import NQ_TICK_SIZE, compute_volume_profile, filter_sessions
from pipeline.strategy_cache import bars_with_delta, trades_with_nbbo


PARAMS = {
    "volume_profile_bars": 50,
    "value_area_pct": 0.70,
    "boundary_touch_ticks": 2,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _session_profiles(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> dict:
    profiles = {}
    for (date_key, session), group in bars.groupby([bars["ts_utc"].dt.date, "session"]):
        profile = compute_volume_profile(
            ticks[["ts_utc", "price", "size"]],
            float(group["low"].min()) - 5.0,
            float(group["high"].max()) + 5.0,
            start_ts=pd.to_datetime(group["ts_utc"].min(), utc=True),
            end_ts=pd.to_datetime(group["ts_utc"].max(), utc=True) + pd.Timedelta(minutes=1),
        )
        levels = profile_to_levels(profile, float(params["value_area_pct"]))
        if levels:
            profiles[(date_key, session)] = levels
    return profiles


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    profiles = _session_profiles(bars, ticks, params)
    threshold = float(params["boundary_touch_ticks"]) * NQ_TICK_SIZE
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []
    for row in bars.itertuples(index=False):
        key = (pd.to_datetime(row.ts_utc, utc=True).date(), row.session)
        levels = profiles.get(key)
        if not levels:
            continue
        direction = None
        level = None
        if float(row.high) >= float(levels["vah"]) + threshold:
            direction = "short"
            level = float(levels["vah"])
        elif float(row.low) <= float(levels["val"]) - threshold:
            direction = "long"
            level = float(levels["val"])
        if direction is None:
            continue
        start_ts = pd.to_datetime(row.ts_utc, utc=True)
        idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
        future = ticks.iloc[idx:idx + 2001]
        if direction == "short":
            touch = future[future["price"] >= level + threshold].head(1)
        else:
            touch = future[future["price"] <= level - threshold].head(1)
        if touch.empty:
            continue
        entry_row = touch.iloc[0]
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(TradeSpec(pd.to_datetime(entry_row["ts_utc"], utc=True), direction, entry_price, float(params["stop_loss_ticks"]), float(params["take_profit_ticks"]), signal_ts=start_ts, meta={"vah": float(levels["vah"]), "val": float(levels["val"])}))
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
