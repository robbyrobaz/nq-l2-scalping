"""Strategy 008: Stacked Book Breakout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import NQ_TICK_SIZE, filter_sessions
from pipeline.strategy_cache import bars_with_delta, depth, quotes, trades_with_nbbo


PARAMS = {
    "stack_threshold": 3.0,
    "stack_lookback_bars": 10,
    "breakout_min_ticks": 1,
    "take_profit_ticks": 12,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _depth_snapshots(df_depth: pd.DataFrame) -> pd.DataFrame:
    if df_depth.empty:
        return pd.DataFrame()
    df = df_depth[df_depth["position"].between(0, 4)].copy()
    totals = df.groupby(["ts_utc", "side"])["size"].sum().unstack(fill_value=0)
    top = df[df["position"] == 0].pivot_table(index="ts_utc", columns="side", values="price", aggfunc="first")
    out = totals.join(top, rsuffix="_price").reset_index()
    cols = {c: str(c).lower() for c in out.columns}
    out.rename(columns=cols, inplace=True)
    out["bid_total"] = out.get("bid", 0.0)
    out["ask_total"] = out.get("ask", 0.0)
    out["bid_price"] = out.get("bid_price", out.get("bid_0", np.nan))
    out["ask_price"] = out.get("ask_price", out.get("ask_0", np.nan))
    return out[["ts_utc", "bid_total", "ask_total", "bid_price", "ask_price"]].sort_values("ts_utc").reset_index(drop=True)


def _quote_snapshots(df_quotes: pd.DataFrame) -> pd.DataFrame:
    return df_quotes.rename(columns={"bid_size": "bid_total", "ask_size": "ask_total", "bid": "bid_price", "ask": "ask_price"})[
        ["ts_utc", "bid_total", "ask_total", "bid_price", "ask_price"]
    ].copy()


def _build_specs(book: pd.DataFrame, bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    merged = pd.merge_asof(
        bars.sort_values("ts_utc"),
        book.sort_values("ts_utc"),
        on="ts_utc",
        direction="backward",
    )
    merged["avg_bid"] = merged["bid_total"].rolling(int(params["stack_lookback_bars"]), min_periods=int(params["stack_lookback_bars"])).mean()
    merged["avg_ask"] = merged["ask_total"].rolling(int(params["stack_lookback_bars"]), min_periods=int(params["stack_lookback_bars"])).mean()
    breakout = float(params["breakout_min_ticks"]) * NQ_TICK_SIZE
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []

    for i, row in enumerate(merged.itertuples(index=False)):
        if not np.isfinite(row.avg_bid) or not np.isfinite(row.avg_ask):
            continue
        direction = None
        if float(row.ask_total) >= float(params["stack_threshold"]) * float(row.avg_ask) and float(row.close) > float(row.ask_price) + breakout:
            direction = "long"
        elif float(row.bid_total) >= float(params["stack_threshold"]) * float(row.avg_bid) and float(row.close) < float(row.bid_price) - breakout:
            direction = "short"
        if direction is None or i + 1 >= len(merged):
            continue

        start_ts = pd.to_datetime(row.ts_utc, utc=True) + pd.Timedelta(minutes=1)
        tick_idx = int(np.searchsorted(tick_ts, start_ts.value, side="left"))
        if tick_idx >= len(ticks):
            continue
        entry_row = ticks.iloc[tick_idx]
        entry_price = float(entry_row["ask"]) if direction == "long" else float(entry_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(entry_row["ts_utc"], utc=True),
                signal_ts=pd.to_datetime(row.ts_utc, utc=True),
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={"stack_level": float(row.ask_price if direction == "long" else row.bid_price)},
            )
        )
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    bars = filter_sessions(bars_with_delta(), sessions=params.get("session_filter")).reset_index(drop=True)
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    df_depth = filter_sessions(depth(), sessions=params.get("session_filter")).reset_index(drop=True)
    if df_depth["ts_utc"].nunique() < 50:
        book = _quote_snapshots(filter_sessions(quotes(), sessions=params.get("session_filter")).reset_index(drop=True))
    else:
        book = _depth_snapshots(df_depth)
    specs = _build_specs(book, bars, ticks, params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, bars)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest()["metrics"], indent=2))
