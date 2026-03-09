"""Shared utilities for strategy backtests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from pipeline.data_loader import (
    NQ_TICK_SIZE,
    NQ_TICK_VALUE,
    compute_session_breakdown,
    load_quotes_full,
    pnl_mnq,
)


@dataclass
class TradeSpec:
    entry_ts: pd.Timestamp
    direction: str
    entry_price: float
    stop_loss_ticks: float
    take_profit_ticks: float
    signal_ts: pd.Timestamp | None = None
    meta: dict | None = None


def prepare_quotes(start_ts=None, end_ts=None) -> pd.DataFrame:
    quotes = load_quotes_full(start_ts=start_ts, end_ts=end_ts).sort_values("ts_utc").reset_index(drop=True)
    quotes["ts_utc"] = pd.to_datetime(quotes["ts_utc"], utc=True)
    return quotes


def attach_nbbo(df: pd.DataFrame, quotes: pd.DataFrame, ts_col: str = "ts_utc") -> pd.DataFrame:
    left = df.copy()
    left[ts_col] = pd.to_datetime(left[ts_col], utc=True)
    merged = pd.merge_asof(
        left.sort_values(ts_col),
        quotes[["ts_utc", "bid", "ask", "bid_size", "ask_size"]].sort_values("ts_utc"),
        left_on=ts_col,
        right_on="ts_utc",
        direction="backward",
    )
    merged.drop(columns=["ts_utc_y"], errors="ignore", inplace=True)
    if "ts_utc_x" in merged.columns:
        merged.rename(columns={"ts_utc_x": ts_col}, inplace=True)
    return merged


def profile_to_levels(profile: dict[float, float], value_area_pct: float) -> dict[str, object] | None:
    if not profile:
        return None

    levels = pd.Series(profile, dtype=float).sort_index()
    if levels.empty or float(levels.sum()) <= 0:
        return None

    prices = levels.index.to_numpy(dtype=float)
    volumes = levels.to_numpy(dtype=float)
    poc_idx = int(np.argmax(volumes))
    included = {poc_idx}
    total = float(volumes.sum())
    captured = float(volumes[poc_idx])
    left = poc_idx - 1
    right = poc_idx + 1

    while captured < total * value_area_pct and (left >= 0 or right < len(prices)):
        left_vol = volumes[left] if left >= 0 else -1
        right_vol = volumes[right] if right < len(prices) else -1
        if right_vol > left_vol:
            included.add(right)
            captured += float(right_vol)
            right += 1
        else:
            included.add(left)
            captured += float(left_vol)
            left -= 1

    included_prices = prices[sorted(included)]
    return {
        "levels": levels,
        "poc": float(prices[poc_idx]),
        "poc_volume": float(volumes[poc_idx]),
        "vah": float(included_prices.max()),
        "val": float(included_prices.min()),
        "value_area_levels": {float(prices[i]): float(volumes[i]) for i in sorted(included)},
        "total_volume": total,
    }


def compute_trade_metrics(trades: list[dict], bars: pd.DataFrame | None = None) -> dict:
    if not trades:
        metrics = {
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "net_pnl_usd": 0.0,
            "sharpe": 0.0,
            "max_drawdown_pct": 0.0,
        }
        if bars is not None:
            metrics["session_breakdown"] = compute_session_breakdown([], bars)
        return metrics

    pnls = np.asarray([float(t["pnl_ticks"]) for t in trades], dtype=float)
    winners = pnls[pnls > 0]
    losers = pnls[pnls < 0]
    gross_profit = float(winners.sum()) if winners.size else 0.0
    gross_loss = float(np.abs(losers.sum())) if losers.size else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    sharpe = float(pnls.mean() / pnls.std() * np.sqrt(len(pnls))) if pnls.size > 1 and pnls.std() > 0 else 0.0

    cum = np.cumsum(pnls * NQ_TICK_VALUE)
    peak = np.maximum.accumulate(np.maximum(cum, 0.0))
    drawdown = peak - cum
    max_drawdown_pct = float(drawdown.max() / peak.max() * 100.0) if peak.max() > 0 else 0.0

    metrics = {
        "profit_factor": round(float(profit_factor), 2) if np.isfinite(profit_factor) else float("inf"),
        "win_rate": round(float((pnls > 0).mean() * 100.0), 1),
        "total_trades": int(len(trades)),
        "net_pnl_usd": round(float(pnl_mnq(float(pnls.sum()))), 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 1),
    }
    if bars is not None:
        metrics["session_breakdown"] = compute_session_breakdown(trades, bars)
    return metrics


def simulate_tick_trade(spec: TradeSpec, ticks: pd.DataFrame, force_exit_price: float | None = None) -> dict | None:
    entry_ts = pd.to_datetime(spec.entry_ts, utc=True)
    future = ticks[ticks["ts_utc"] > entry_ts]
    tp_delta = spec.take_profit_ticks * NQ_TICK_SIZE
    sl_delta = spec.stop_loss_ticks * NQ_TICK_SIZE

    if spec.direction == "long":
        target = spec.entry_price + tp_delta
        stop = spec.entry_price - sl_delta
    else:
        target = spec.entry_price - tp_delta
        stop = spec.entry_price + sl_delta

    exit_row = None
    exit_reason = "force_exit"
    exit_price = force_exit_price
    pnl_ticks = 0.0

    for row in future.itertuples(index=False):
        price = float(row.price)
        if spec.direction == "long":
            if price >= target:
                exit_row = row
                exit_price = target
                exit_reason = "tp"
                pnl_ticks = float(spec.take_profit_ticks)
                break
            if price <= stop:
                exit_row = row
                exit_price = stop
                exit_reason = "sl"
                pnl_ticks = -float(spec.stop_loss_ticks)
                break
        else:
            if price <= target:
                exit_row = row
                exit_price = target
                exit_reason = "tp"
                pnl_ticks = float(spec.take_profit_ticks)
                break
            if price >= stop:
                exit_row = row
                exit_price = stop
                exit_reason = "sl"
                pnl_ticks = -float(spec.stop_loss_ticks)
                break

    if exit_row is None:
        if ticks.empty:
            return None
        last = ticks.iloc[-1]
        exit_ts = pd.to_datetime(last["ts_utc"], utc=True)
        if exit_price is None:
            exit_price = float(last["price"])
        if spec.direction == "long":
            pnl_ticks = (float(exit_price) - spec.entry_price) / NQ_TICK_SIZE
        else:
            pnl_ticks = (spec.entry_price - float(exit_price)) / NQ_TICK_SIZE
    else:
        exit_ts = pd.to_datetime(exit_row.ts_utc, utc=True)

    trade = {
        "signal_ts": str(pd.to_datetime(spec.signal_ts or spec.entry_ts, utc=True)),
        "entry_ts": str(entry_ts),
        "exit_ts": str(exit_ts),
        "direction": spec.direction,
        "entry_price": round(float(spec.entry_price), 4),
        "exit_price": round(float(exit_price), 4),
        "pnl_ticks": round(float(pnl_ticks), 2),
        "pnl_usd": round(float(pnl_ticks * NQ_TICK_VALUE), 2),
        "exit_reason": exit_reason,
    }
    if spec.meta:
        trade.update(spec.meta)
    return trade


def iter_trade_specs(specs: Iterable[TradeSpec], ticks: pd.DataFrame) -> list[dict]:
    trades = []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    for spec in sorted(specs, key=lambda item: item.entry_ts):
        entry_ts = pd.to_datetime(spec.entry_ts, utc=True)
        if entry_ts <= last_exit:
            continue
        trade = simulate_tick_trade(spec, ticks)
        if trade is None:
            continue
        trades.append(trade)
        last_exit = pd.to_datetime(trade["exit_ts"], utc=True)
    return trades
