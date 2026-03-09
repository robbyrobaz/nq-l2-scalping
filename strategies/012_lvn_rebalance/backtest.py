"""Strategy 012: LVN Rebalance."""

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
    "lvn_threshold_ratio": 0.30,
    "value_area_pct": 0.70,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 12,
    "session_filter": None,
}


def _session_profiles(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> dict:
    profiles = {}
    for (date_key, session), group in bars.groupby([bars["ts_utc"].dt.date, "session"]):
        start_ts = pd.to_datetime(group["ts_utc"].min(), utc=True)
        end_ts = pd.to_datetime(group["ts_utc"].max(), utc=True) + pd.Timedelta(minutes=1)
        profile = compute_volume_profile(
            ticks[["ts_utc", "price", "size"]],
            float(group["low"].min()) - 5.0,
            float(group["high"].max()) + 5.0,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        levels = profile_to_levels(profile, float(params["value_area_pct"]))
        if levels:
            profiles[(date_key, session)] = levels
    return profiles


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    profiles = _session_profiles(bars, ticks, params)
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []

    for i, row in enumerate(bars.itertuples(index=False)):
        key = (pd.to_datetime(row.ts_utc, utc=True).date(), row.session)
        levels = profiles.get(key)
        if not levels:
            continue
        poc_vol = float(levels["poc_volume"])
        lvns = [price for price, vol in levels["levels"].items() if vol < poc_vol * float(params["lvn_threshold_ratio"])]
        if not lvns:
            continue
        direction = None
        target_lvn = None
        if float(row.close) > float(levels["vah"]):
            below = [price for price in lvns if price <= float(row.close)]
            if below:
                direction = "long"
                target_lvn = max(below)
        elif float(row.close) < float(levels["val"]):
            above = [price for price in lvns if price >= float(row.close)]
            if above:
                direction = "short"
                target_lvn = min(above)
        if direction is None:
            continue
        start_ts = pd.to_datetime(row.ts_utc, utc=True)
        idx = int(np.searchsorted(tick_ts, start_ts.value, side="left"))
        future = ticks.iloc[idx:]
        touch = future[(future["price"] - target_lvn).abs() <= NQ_TICK_SIZE].head(1)
        if touch.empty:
            continue
        entry_row = touch.iloc[0]
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(
            TradeSpec(
                pd.to_datetime(entry_row["ts_utc"], utc=True),
                direction,
                entry_price,
                float(params["stop_loss_ticks"]),
                float(params["take_profit_ticks"]),
                signal_ts=start_ts,
                meta={"lvn_level": float(target_lvn), "vah": float(levels["vah"]), "val": float(levels["val"])},
            )
        )
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
