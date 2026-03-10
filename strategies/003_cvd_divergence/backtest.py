"""Strategy 003: CVD Divergence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import NQ_TICK_SIZE, filter_sessions
from pipeline.strategy_cache import bars_with_cvd, trades_with_nbbo


PARAMS = {
    "divergence_window": 5,
    "min_cvd_move": 50,
    "confirmation_bars": 1,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "debug": False,
    "session_filter": None,
}


def _latest_pair(indices: np.ndarray, current_idx: int) -> tuple[int, int] | None:
    valid = indices[indices < current_idx]
    if len(valid) < 2:
        return None
    return int(valid[-2]), int(valid[-1])


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    closes = bars["close"].to_numpy()
    cvd = bars["cvd"].to_numpy()
    distance = int(params["divergence_window"])
    price_highs, _ = find_peaks(closes, distance=distance, prominence=NQ_TICK_SIZE)
    price_lows, _ = find_peaks(-closes, distance=distance, prominence=NQ_TICK_SIZE)
    cvd_highs, _ = find_peaks(cvd, distance=distance, prominence=float(params["min_cvd_move"]) / 2.0)
    cvd_lows, _ = find_peaks(-cvd, distance=distance, prominence=float(params["min_cvd_move"]) / 2.0)

    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []
    confirmation = int(params["confirmation_bars"])
    long_count = 0
    short_count = 0
    # Dedup: track last pair indices used per direction to avoid re-firing same divergence
    last_long_price_pair: tuple[int, int] = (-1, -1)
    last_long_cvd_pair: tuple[int, int] = (-1, -1)
    last_short_price_pair: tuple[int, int] = (-1, -1)
    last_short_cvd_pair: tuple[int, int] = (-1, -1)

    for i in range(distance + confirmation + 1, len(bars) - 1):
        long_signal = False
        short_signal = False

        price_pair = _latest_pair(price_lows, i - confirmation)
        cvd_pair = _latest_pair(cvd_lows, i - confirmation)
        if price_pair and cvd_pair:
            p0, p1 = price_pair
            c0, c1 = cvd_pair
            if (
                closes[p1] >= closes[p0]
                and cvd[c1] < cvd[c0]
                and abs(cvd[c1] - cvd[c0]) >= float(params["min_cvd_move"])
                and ((p0, p1) != last_long_price_pair or (c0, c1) != last_long_cvd_pair)
            ):
                long_signal = True
                long_count += 1
                last_long_price_pair = (p0, p1)
                last_long_cvd_pair = (c0, c1)

        price_pair = _latest_pair(price_highs, i - confirmation)
        cvd_pair = _latest_pair(cvd_highs, i - confirmation)
        if price_pair and cvd_pair:
            p0, p1 = price_pair
            c0, c1 = cvd_pair
            if (
                closes[p1] <= closes[p0]
                and cvd[c1] > cvd[c0]
                and abs(cvd[c1] - cvd[c0]) >= float(params["min_cvd_move"])
                and ((p0, p1) != last_short_price_pair or (c0, c1) != last_short_cvd_pair)
            ):
                short_signal = True
                short_count += 1
                last_short_price_pair = (p0, p1)
                last_short_cvd_pair = (c0, c1)

        if not long_signal and not short_signal:
            continue

        entry_bar_ts = pd.to_datetime(bars.iloc[i + 1].ts_utc, utc=True)
        tick_idx = int(np.searchsorted(tick_ts, entry_bar_ts.value // 1000, side="left"))
        if tick_idx >= len(ticks):
            continue
        row = ticks.iloc[tick_idx]
        direction = "long" if long_signal else "short"
        entry_price = float(row["ask"]) if direction == "long" else float(row["bid"])
        if not np.isfinite(entry_price):
            continue

        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                signal_ts=pd.to_datetime(bars.iloc[i].ts_utc, utc=True),
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={"divergence_bar_ts": str(bars.iloc[i].ts_utc)},
            )
        )
    if params.get("debug"):
        print(
            f"[003] price_highs={len(price_highs)} price_lows={len(price_lows)} "
            f"cvd_highs={len(cvd_highs)} cvd_lows={len(cvd_lows)} "
            f"long_divergences={long_count} short_divergences={short_count}"
        )
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    bars = filter_sessions(bars_with_cvd(), sessions=params.get("session_filter")).reset_index(drop=True)
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    specs = _build_specs(bars, ticks, params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, bars)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest(params={**PARAMS, "debug": True})["metrics"], indent=2))
