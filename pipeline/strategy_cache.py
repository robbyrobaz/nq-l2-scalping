"""Cached dataset access for repeated optimization runs."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from pipeline.data_loader import (
    build_1min_bars_with_delta,
    compute_cvd,
    load_depth_raw,
    load_quotes_full,
    load_trades,
    load_trades_fast,
    precompute_dom_series,
)
from pipeline.backtest_utils import attach_nbbo


@lru_cache(maxsize=1)
def trades() -> pd.DataFrame:
    df = load_trades().sort_values("ts_utc").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def trades_fast() -> pd.DataFrame:
    df = load_trades_fast().sort_values("ts_utc").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def quotes() -> pd.DataFrame:
    df = load_quotes_full().sort_values("ts_utc").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def depth() -> pd.DataFrame:
    df = load_depth_raw().sort_values("ts_utc").reset_index(drop=True)
    if not df.empty:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def dom_series() -> pd.DataFrame:
    df = precompute_dom_series(depth())
    if not df.empty:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def bars_with_delta() -> pd.DataFrame:
    return build_1min_bars_with_delta(trades()).sort_values("ts_utc").reset_index(drop=True)


@lru_cache(maxsize=1)
def bars_with_cvd() -> pd.DataFrame:
    return compute_cvd(bars_with_delta()).sort_values("ts_utc").reset_index(drop=True)


@lru_cache(maxsize=1)
def trades_with_nbbo() -> pd.DataFrame:
    return attach_nbbo(trades(), quotes(), ts_col="ts_utc").sort_values("ts_utc").reset_index(drop=True)
