"""Shared data loading and processing for NQ L2 scalping strategies."""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = "/tmp/nq_feed_readonly.duckdb"
DB_SOURCE = "/home/rob/infrastructure/ibkr/data/nq_feed.duckdb"
CSV_PATH = "/home/rob/infrastructure/ibkr/data/NQ_ibkr_1min.csv"

NQ_TICK_SIZE = 0.25  # NQ tick = 0.25 points
MNQ_TICK_VALUE = 0.50  # MNQ $0.50 per tick
NQ_TICK_VALUE = 5.00

# RTH session: 08:30-15:15 CT = 14:30-21:15 UTC (CT = UTC-6 in March CST)
RTH_START_UTC_HOUR = 14
RTH_START_UTC_MIN = 30
RTH_END_UTC_HOUR = 21
RTH_END_UTC_MIN = 15


def _get_conn():
    """Get a read-only DuckDB connection (uses temp copy to avoid lock)."""
    import shutil
    tmp = Path(DB_PATH)
    if not tmp.exists():
        shutil.copy2(DB_SOURCE, DB_PATH)
    return duckdb.connect(DB_PATH, read_only=True)


def load_trades(start_ts=None, end_ts=None):
    """Load trade ticks with inferred aggressor side from quotes.

    Returns DataFrame: ts_utc, price, size, side ('B','S',''), delta
    """
    conn = _get_conn()

    # Load trades
    q = "SELECT ts_utc, price, size FROM nq_ticks ORDER BY ts_utc"
    if start_ts and end_ts:
        q = f"SELECT ts_utc, price, size FROM nq_ticks WHERE ts_utc BETWEEN '{start_ts}' AND '{end_ts}' ORDER BY ts_utc"
    trades = conn.execute(q).fetchdf()

    # Load quotes for side inference
    q_quotes = "SELECT ts_utc, bid, ask FROM nq_quotes ORDER BY ts_utc"
    if start_ts and end_ts:
        q_quotes = f"SELECT ts_utc, bid, ask FROM nq_quotes WHERE ts_utc BETWEEN '{start_ts}' AND '{end_ts}' ORDER BY ts_utc"
    quotes = conn.execute(q_quotes).fetchdf()
    conn.close()

    if trades.empty:
        trades['side'] = []
        trades['delta'] = []
        return trades

    # merge_asof: for each trade, find the most recent quote
    trades = trades.sort_values('ts_utc').reset_index(drop=True)
    quotes = quotes.sort_values('ts_utc').reset_index(drop=True)

    merged = pd.merge_asof(trades, quotes, on='ts_utc', direction='backward')

    # Infer side
    merged['side'] = np.where(
        merged['price'] >= merged['ask'], 'B',
        np.where(merged['price'] <= merged['bid'], 'S', '')
    )
    merged['delta'] = np.where(
        merged['side'] == 'B', merged['size'],
        np.where(merged['side'] == 'S', -merged['size'], 0)
    )

    return merged[['ts_utc', 'price', 'size', 'side', 'delta']].copy()


def load_trades_fast(start_ts=None, end_ts=None):
    """Load trades without side inference (faster, for volume profile etc)."""
    conn = _get_conn()
    q = "SELECT ts_utc, price, size FROM nq_ticks ORDER BY ts_utc"
    if start_ts and end_ts:
        q = f"SELECT ts_utc, price, size FROM nq_ticks WHERE ts_utc BETWEEN '{start_ts}' AND '{end_ts}' ORDER BY ts_utc"
    df = conn.execute(q).fetchdf()
    conn.close()
    return df


def load_bars_1min():
    """Load 1-min OHLCV bars from DuckDB."""
    conn = _get_conn()
    df = conn.execute("SELECT * FROM nq_bars_1min ORDER BY ts_utc").fetchdf()
    conn.close()
    return df


def build_1min_bars_with_delta(df_trades):
    """Build 1-min OHLCV + cumulative_delta from trade ticks.

    Args:
        df_trades: DataFrame with ts_utc, price, size, delta columns
    Returns:
        DataFrame: ts_utc (bar start), open, high, low, close, volume, bar_delta, cumulative_delta
    """
    df = df_trades.copy()
    df['bar'] = df['ts_utc'].dt.floor('1min')

    bars = df.groupby('bar').agg(
        open=('price', 'first'),
        high=('price', 'max'),
        low=('price', 'min'),
        close=('price', 'last'),
        volume=('size', 'sum'),
        bar_delta=('delta', 'sum'),
    ).reset_index().rename(columns={'bar': 'ts_utc'})

    bars['cumulative_delta'] = bars['bar_delta'].cumsum()
    return bars


def compute_cvd(df_bars):
    """Add CVD column to bars, reset at each RTH session open (14:30 UTC = 08:30 CT).

    Args:
        df_bars: DataFrame with ts_utc and bar_delta columns
    Returns:
        DataFrame with added 'cvd' column
    """
    df = df_bars.copy()
    df['date'] = df['ts_utc'].dt.date
    df['time'] = df['ts_utc'].dt.time

    from datetime import time as dtime
    rth_start = dtime(RTH_START_UTC_HOUR, RTH_START_UTC_MIN)

    # Create session IDs: increment when we hit RTH start
    df['is_session_start'] = (df['time'] >= rth_start) & (df['time'] < dtime(RTH_START_UTC_HOUR, RTH_START_UTC_MIN + 1))
    # Group by date for session reset
    df['session'] = df['date'].astype(str)

    cvd = []
    running = 0.0
    prev_date = None
    for _, row in df.iterrows():
        if row['date'] != prev_date:
            running = 0.0
            prev_date = row['date']
        running += row['bar_delta']
        cvd.append(running)
    df['cvd'] = cvd

    df.drop(columns=['date', 'time', 'is_session_start', 'session'], inplace=True)
    return df


def compute_volume_profile(df_trades, price_lo, price_hi, start_ts=None, end_ts=None):
    """Compute tick-level volume profile for a price range.

    Args:
        df_trades: DataFrame with price, size columns
        price_lo, price_hi: price bounds
        start_ts, end_ts: optional time filter (column ts_utc)
    Returns:
        dict {price_level: total_volume}
    """
    df = df_trades.copy()
    if start_ts is not None:
        df = df[df['ts_utc'] >= start_ts]
    if end_ts is not None:
        df = df[df['ts_utc'] <= end_ts]

    df = df[(df['price'] >= price_lo) & (df['price'] <= price_hi)]

    # Round to tick
    df['price_level'] = (df['price'] / NQ_TICK_SIZE).round() * NQ_TICK_SIZE
    profile = df.groupby('price_level')['size'].sum().to_dict()
    return profile


def filter_rth(df, ts_col='ts_utc'):
    """Filter to RTH hours only (14:30-21:15 UTC)."""
    from datetime import time as dtime
    t = df[ts_col].dt.time
    start = dtime(RTH_START_UTC_HOUR, RTH_START_UTC_MIN)
    end = dtime(RTH_END_UTC_HOUR, RTH_END_UTC_MIN)
    return df[(t >= start) & (t <= end)].copy()


def ticks_to_points(ticks):
    return ticks * NQ_TICK_SIZE


def pnl_mnq(ticks):
    return ticks * MNQ_TICK_VALUE
