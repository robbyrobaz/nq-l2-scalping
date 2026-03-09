"""Shared data loading and processing for NQ L2 scalping strategies."""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from zoneinfo import ZoneInfo

DB_PATH = "/tmp/nq_feed_readonly.duckdb"
DB_SOURCE = "/home/rob/infrastructure/ibkr/data/nq_feed.duckdb"
CSV_PATH = "/home/rob/infrastructure/ibkr/data/NQ_ibkr_1min.csv"

NQ_TICK_SIZE = 0.25  # NQ tick = 0.25 points
MNQ_TICK_VALUE = 0.50  # MNQ $0.50 per tick
NQ_TICK_VALUE = 5.00

# Session definitions in ET minute_of_day. Asia wraps midnight.
SESSION_DEFS = [
    ("Asia", 18 * 60, 2 * 60, 8 * 60),
    ("London", 2 * 60, 5 * 60, 3 * 60),
    ("LondonNY", 5 * 60, 8 * 60 + 30, 3 * 60 + 30),
    ("PreNY", 8 * 60 + 30, 9 * 60 + 30, 60),
    ("NYOpen", 9 * 60 + 30, 10 * 60 + 30, 60),
    ("MidDay", 10 * 60 + 30, 14 * 60, 3 * 60 + 30),
    ("PowerHour", 14 * 60, 15 * 60, 60),
    ("Close", 15 * 60, 16 * 60, 60),
    ("PostMarket", 16 * 60, 18 * 60, 2 * 60),
]

SESSION_NAMES = [s[0] for s in SESSION_DEFS]
RTH_SESSIONS = ["NYOpen", "MidDay", "PowerHour", "Close"]


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
    bars = tag_sessions(bars, ts_col='ts_utc')
    return bars


def compute_cvd(df_bars):
    """Add CVD column to bars, reset at each RTH session open (13:30 UTC = 08:30 CT).

    Args:
        df_bars: DataFrame with ts_utc and bar_delta columns
    Returns:
        DataFrame with added 'cvd' column
    """
    df = df_bars.copy()
    df['date'] = df['ts_utc'].dt.date
    df['time'] = df['ts_utc'].dt.time

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

    df.drop(columns=['date', 'time'], inplace=True)
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


def _get_session(minute_of_day):
    """Return session name for ET minute_of_day."""
    if minute_of_day >= 18 * 60 or minute_of_day < 2 * 60:
        return "Asia"
    if 2 * 60 <= minute_of_day < 5 * 60:
        return "London"
    if 5 * 60 <= minute_of_day < 8 * 60 + 30:
        return "LondonNY"
    if 8 * 60 + 30 <= minute_of_day < 9 * 60 + 30:
        return "PreNY"
    if 9 * 60 + 30 <= minute_of_day < 10 * 60 + 30:
        return "NYOpen"
    if 10 * 60 + 30 <= minute_of_day < 14 * 60:
        return "MidDay"
    if 14 * 60 <= minute_of_day < 15 * 60:
        return "PowerHour"
    if 15 * 60 <= minute_of_day < 16 * 60:
        return "Close"
    return "PostMarket"


def tag_sessions(df, ts_col='ts_utc'):
    """Tag rows with ET session metadata based on UTC timestamps."""
    out = df.copy()
    ts_utc = pd.to_datetime(out[ts_col], utc=True, errors='coerce')
    dt_et = ts_utc.dt.tz_convert(ZoneInfo("America/New_York")).dt.tz_localize(None)

    out['datetime_et'] = dt_et
    out['minute_of_day'] = dt_et.dt.hour * 60 + dt_et.dt.minute
    out['session'] = out['minute_of_day'].map(_get_session)
    return out


def filter_sessions(df, sessions=None, ts_col='ts_utc'):
    """Filter to requested sessions. None means no filter (all sessions)."""
    out = df if 'session' in df.columns else tag_sessions(df, ts_col=ts_col)
    if sessions is None:
        return out.copy()
    if isinstance(sessions, str):
        sessions = [sessions]
    sessions = set(sessions)
    return out[out['session'].isin(sessions)].copy()


def filter_rth(df, ts_col='ts_utc'):
    """Backward-compatible RTH filter (opt-in)."""
    return filter_sessions(df, sessions=RTH_SESSIONS, ts_col=ts_col)


def compute_session_breakdown(trades, bars, entry_ts_col='entry_ts'):
    """Compute per-session trade count, PF, and PnL (USD)."""
    if not trades:
        return {}

    trades_df = pd.DataFrame(trades)
    if trades_df.empty or entry_ts_col not in trades_df.columns:
        return {}

    bars_with_session = bars if 'session' in bars.columns else tag_sessions(bars, ts_col='ts_utc')
    session_map = bars_with_session[['ts_utc', 'session']].copy()
    session_map['_entry_ts'] = pd.to_datetime(session_map['ts_utc'], utc=True, errors='coerce')

    trades_df['_entry_ts'] = pd.to_datetime(trades_df[entry_ts_col], utc=True, errors='coerce')
    merged = trades_df.merge(
        session_map[['_entry_ts', 'session']],
        on='_entry_ts',
        how='left',
    )
    merged['session'] = merged['session'].fillna('Unknown')

    breakdown = {}
    for session_name, grp in merged.groupby('session'):
        pnls = grp['pnl_ticks'].astype(float).tolist()
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        gross_profit = sum(winners) if winners else 0.0
        gross_loss = abs(sum(losers)) if losers else 0.0
        pf = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
        pnl_usd = pnl_mnq(sum(pnls))
        breakdown[session_name] = {
            'trades': int(len(pnls)),
            'pf': round(float(pf), 2) if np.isfinite(pf) else float('inf'),
            'pnl': round(float(pnl_usd), 2),
        }

    ordered = {}
    for s in SESSION_NAMES + ['Unknown']:
        if s in breakdown:
            ordered[s] = breakdown[s]
    return ordered


def ticks_to_points(ticks):
    return ticks * NQ_TICK_SIZE


def pnl_mnq(ticks):
    return ticks * MNQ_TICK_VALUE
