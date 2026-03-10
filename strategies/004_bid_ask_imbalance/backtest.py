"""Strategy 004: Bid/Ask Imbalance."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import filter_sessions
from pipeline.strategy_cache import quotes, trades_with_nbbo


PARAMS = {
    "imbalance_ratio_threshold": 3.0,
    "sustained_quotes": 20,
    "min_size_contracts": 50,
    "take_profit_ticks": 10,
    "stop_loss_ticks": 8,
    "session_filter": None,
}


def _build_specs(df_quotes: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    sustained_quotes = int(params.get("sustained_quotes", params.get("consecutive_bars", 20)))
    ratio = float(params["imbalance_ratio_threshold"])
    min_size = float(params["min_size_contracts"])
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    specs: list[TradeSpec] = []

    long_count = 0
    short_count = 0
    for row in df_quotes.itertuples(index=False):
        bid_ratio = float(row.bid_size) / (float(row.ask_size) + 1.0)
        ask_ratio = float(row.ask_size) / (float(row.bid_size) + 1.0)
        long_count = long_count + 1 if bid_ratio >= ratio and float(row.bid_size) >= min_size else 0
        short_count = short_count + 1 if ask_ratio >= ratio and float(row.ask_size) >= min_size else 0

        direction = None
        if long_count >= sustained_quotes:
            direction = "long"
        elif short_count >= sustained_quotes:
            direction = "short"
        if direction is None:
            continue

        next_idx = int(np.searchsorted(tick_ts, pd.to_datetime(row.ts_utc, utc=True).value // 1000, side="right"))
        if next_idx >= len(ticks):
            continue
        future = ticks.iloc[next_idx:next_idx + 2001]
        if direction == "long":
            fill = future[future["side"] == "B"].head(1)
        else:
            fill = future[future["side"] == "S"].head(1)
        if fill.empty:
            continue

        trade_row = fill.iloc[0]
        entry_price = float(trade_row["ask"]) if direction == "long" else float(trade_row["bid"])
        if not np.isfinite(entry_price):
            continue
        specs.append(
            TradeSpec(
                entry_ts=pd.to_datetime(trade_row["ts_utc"], utc=True),
                signal_ts=pd.to_datetime(row.ts_utc, utc=True),
                direction=direction,
                entry_price=entry_price,
                stop_loss_ticks=float(params["stop_loss_ticks"]),
                take_profit_ticks=float(params["take_profit_ticks"]),
                meta={"imbalance_quote_ts": str(row.ts_utc)},
            )
        )
        long_count = 0
        short_count = 0
    return specs


def run_backtest(params=PARAMS) -> dict:
    params = {**PARAMS, **(params or {})}
    df_quotes = filter_sessions(quotes(), sessions=params.get("session_filter")).reset_index(drop=True)
    ticks = filter_sessions(trades_with_nbbo(), sessions=params.get("session_filter")).reset_index(drop=True)
    specs = _build_specs(df_quotes, ticks, params)
    trades = iter_trade_specs(specs, ticks)
    metrics = compute_trade_metrics(trades, df_quotes)
    return {"trades": trades, "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"}, "session_breakdown": metrics.get("session_breakdown", {})}


def run(params=None):
    return run_backtest(params=params or PARAMS)


if __name__ == "__main__":
    print(json.dumps(run_backtest()["metrics"], indent=2))
