"""Strategy 002: Volume Profile Fair Value Gap Rejection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs, profile_to_levels
from pipeline.data_loader import NQ_TICK_SIZE, compute_volume_profile, filter_sessions
from pipeline.strategy_cache import bars_with_delta, trades_with_nbbo


PARAMS = {
    "swing_lookback": 20,
    "min_leg_size_ticks": 20,
    "value_area_pct": 0.70,
    "entry_zone_ticks": 2,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "max_retrace_bars": 30,
    "session_filter": None,
}


def _find_swings(bars: pd.DataFrame, lookback: int) -> list[tuple[int, str]]:
    highs, _ = find_peaks(bars["high"].to_numpy(), distance=lookback)
    lows, _ = find_peaks(-bars["low"].to_numpy(), distance=lookback)
    swings = [(int(i), "high") for i in highs] + [(int(i), "low") for i in lows]
    return sorted(swings, key=lambda item: item[0])


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    swings = _find_swings(bars, int(params["swing_lookback"]))
    specs: list[TradeSpec] = []
    zone = float(params["entry_zone_ticks"]) * NQ_TICK_SIZE
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()

    for (idx_a, kind_a), (idx_b, kind_b) in zip(swings, swings[1:]):
        if kind_a == kind_b or idx_b <= idx_a:
            continue
        a = bars.iloc[idx_a]
        b = bars.iloc[idx_b]
        bullish = kind_a == "low" and kind_b == "high"
        bearish = kind_a == "high" and kind_b == "low"
        if not bullish and not bearish:
            continue

        leg_ticks = abs(float(b.close) - float(a.close)) / NQ_TICK_SIZE
        if leg_ticks < float(params["min_leg_size_ticks"]):
            continue

        profile = compute_volume_profile(
            ticks[["ts_utc", "price", "size"]],
            price_lo=min(float(a.low), float(b.low)),
            price_hi=max(float(a.high), float(b.high)),
            start_ts=pd.to_datetime(a.ts_utc, utc=True),
            end_ts=pd.to_datetime(b.ts_utc, utc=True) + pd.Timedelta(minutes=1),
        )
        levels = profile_to_levels(profile, float(params["value_area_pct"]))
        if not levels:
            continue

        va = levels["value_area_levels"]
        if bullish:
            candidates = {p: v for p, v in va.items() if p <= levels["poc"]}
            direction = "long"
        else:
            candidates = {p: v for p, v in va.items() if p >= levels["poc"]}
            direction = "short"
        if not candidates:
            continue

        fvg_level = min(candidates, key=candidates.get)
        end_bar = min(idx_b + int(params["max_retrace_bars"]), len(bars) - 1)
        start_ts = pd.to_datetime(b.ts_utc, utc=True) + pd.Timedelta(minutes=1)
        start_idx = int(np.searchsorted(tick_ts, start_ts.value, side="left"))
        end_ts = pd.to_datetime(bars.iloc[end_bar].ts_utc, utc=True) + pd.Timedelta(minutes=1)
        end_idx = int(np.searchsorted(tick_ts, end_ts.value, side="right"))
        retrace_ticks = ticks.iloc[start_idx:end_idx]
        if retrace_ticks.empty:
            continue

        touch = retrace_ticks[(retrace_ticks["price"] - fvg_level).abs() <= zone].head(1)
        if touch.empty:
            continue
        row = touch.iloc[0]
        entry_price = float(row["ask"]) if direction == "long" else float(row["bid"])
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
                    "leg_start_ts": str(a.ts_utc),
                    "leg_end_ts": str(b.ts_utc),
                    "fvg_level": float(fvg_level),
                    "poc": float(levels["poc"]),
                    "vah": float(levels["vah"]),
                    "val": float(levels["val"]),
                },
            )
        )
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    bars = filter_sessions(bars_with_delta(), sessions=params.get("session_filter")).reset_index(drop=True)
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    specs = _build_specs(bars, ticks, params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, bars)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest()["metrics"], indent=2))
