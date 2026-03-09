"""Strategy 007: Sweep & Fade."""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import NQ_TICK_SIZE, filter_sessions
from pipeline.strategy_cache import trades_with_nbbo


PARAMS = {
    "sweep_tick_threshold": 8,
    "sweep_time_seconds": 30,
    "retracement_min_ticks": 1,
    "take_profit_ticks": 6,
    "stop_loss_ticks": 10,
    "session_filter": None,
}


def build_signal_frame(ticks: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = float(params["sweep_tick_threshold"]) * NQ_TICK_SIZE
    max_seconds = float(params["sweep_time_seconds"])
    retrace = float(params["retracement_min_ticks"]) * NQ_TICK_SIZE

    window = deque()
    signals = []
    active_sweep = None

    for i, row in enumerate(ticks.itertuples(index=False)):
        ts = pd.to_datetime(row.ts_utc, utc=True)
        price = float(row.price)
        window.append((i, ts, price))
        while window and (ts - window[0][1]).total_seconds() > max_seconds:
            window.popleft()
        prices = [p for _, _, p in window]
        low = min(prices)
        high = max(prices)
        first = window[0][2]

        if active_sweep is None:
            moved = high - low
            if moved >= threshold:
                if price > first and price >= high:
                    active_sweep = {"direction": "up", "start_idx": window[0][0], "end_idx": i, "low": low, "high": high}
                elif price < first and price <= low:
                    active_sweep = {"direction": "down", "start_idx": window[0][0], "end_idx": i, "low": low, "high": high}
            continue

        active_sweep["end_idx"] = i
        active_sweep["low"] = min(active_sweep["low"], price)
        active_sweep["high"] = max(active_sweep["high"], price)
        if active_sweep["direction"] == "up":
            if row.side == "S" and price <= active_sweep["high"] - retrace:
                start_row = ticks.iloc[active_sweep["start_idx"]]
                signals.append(
                    {
                        "signal_ts": ts,
                        "entry_ts": ts,
                        "direction": "short",
                        "entry_price": float(row.bid),
                        "sweep_ticks": round((active_sweep["high"] - active_sweep["low"]) / NQ_TICK_SIZE, 2),
                        "sweep_pts": round(active_sweep["high"] - active_sweep["low"], 4),
                        "sweep_volume": float(ticks.iloc[active_sweep["start_idx"] : i + 1]["size"].sum()),
                        "sweep_duration_ms": (ts - pd.to_datetime(start_row["ts_utc"], utc=True)).total_seconds() * 1000.0,
                        "sweep_start_ts": str(start_row["ts_utc"]),
                    }
                )
                active_sweep = None
        else:
            if row.side == "B" and price >= active_sweep["low"] + retrace:
                start_row = ticks.iloc[active_sweep["start_idx"]]
                signals.append(
                    {
                        "signal_ts": ts,
                        "entry_ts": ts,
                        "direction": "long",
                        "entry_price": float(row.ask),
                        "sweep_ticks": round((active_sweep["high"] - active_sweep["low"]) / NQ_TICK_SIZE, 2),
                        "sweep_pts": round(active_sweep["high"] - active_sweep["low"], 4),
                        "sweep_volume": float(ticks.iloc[active_sweep["start_idx"] : i + 1]["size"].sum()),
                        "sweep_duration_ms": (ts - pd.to_datetime(start_row["ts_utc"], utc=True)).total_seconds() * 1000.0,
                        "sweep_start_ts": str(start_row["ts_utc"]),
                    }
                )
                active_sweep = None

    return pd.DataFrame(signals)


def _build_specs(ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    signals = build_signal_frame(ticks, params)
    specs: list[TradeSpec] = []
    if signals.empty:
        return specs
    for row in signals.itertuples(index=False):
        if not np.isfinite(row.entry_price):
            continue
        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(row.entry_ts, utc=True),
                signal_ts=pd.to_datetime(row.signal_ts, utc=True),
                direction=row.direction,
                entry_price=float(row.entry_price),
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={
                    "sweep_ticks": float(row.sweep_ticks),
                    "sweep_pts": float(row.sweep_pts),
                    "sweep_volume": float(row.sweep_volume),
                    "sweep_duration_ms": float(row.sweep_duration_ms),
                    "sweep_start_ts": row.sweep_start_ts,
                },
            )
        )
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
