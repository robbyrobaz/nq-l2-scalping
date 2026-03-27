"""Fast backtest runner for Strategy 020 (IVB/Opening Range).

Optimized for 14.8M tick dataset by:
1. Using DuckDB SQL aggregation instead of pandas merge_asof
2. Loading only last 7 days of data
3. Building 1-min bars directly in SQL
"""

import sys
import json
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import NQ_TICK_SIZE

# Strategy params
PARAMS = {
    "opening_range_bars": 30,
    "wait_for_retest": False,
    "retest_lookback": 10,
    "retest_proximity_ticks": 4,
    "take_profit_ticks": 16,
    "stop_loss_ticks": 8,
    "session_filter": "RTH",
    "lookback_days": 7,
}


def _build_bars_from_db(conn, lookback_days=7):
    """Build 1-min OHLCV bars with delta directly from DuckDB."""
    query = f"""
    WITH trades_with_side AS (
        SELECT 
            t.ts_utc,
            t.price,
            t.size,
            CASE 
                WHEN t.price >= q.ask THEN 'B'
                WHEN t.price <= q.bid THEN 'S'
                ELSE ''
            END as side
        FROM nq_ticks t
        ASOF LEFT JOIN nq_quotes q 
            ON t.ts_utc >= q.ts_utc
        WHERE t.ts_utc >= CURRENT_TIMESTAMP - INTERVAL {lookback_days} DAY
    )
    SELECT 
        time_bucket(INTERVAL '1 minute', ts_utc) as ts_utc,
        FIRST(price) as open,
        MAX(price) as high,
        MIN(price) as low,
        LAST(price) as close,
        SUM(size) as volume,
        SUM(CASE WHEN side = 'B' THEN size WHEN side = 'S' THEN -size ELSE 0 END) as delta
    FROM trades_with_side
    GROUP BY time_bucket(INTERVAL '1 minute', ts_utc)
    ORDER BY ts_utc
    """
    
    df = conn.execute(query).fetchdf()
    df['ts_utc'] = pd.to_datetime(df['ts_utc'], utc=True)
    return df


def _load_ticks_for_fills(conn, lookback_days=7):
    """Load tick data with NBBO for fill simulation."""
    query = f"""
    SELECT 
        t.ts_utc,
        t.price,
        t.size,
        q.bid,
        q.ask
    FROM nq_ticks t
    ASOF LEFT JOIN nq_quotes q 
        ON t.ts_utc >= q.ts_utc
    WHERE t.ts_utc >= CURRENT_TIMESTAMP - INTERVAL {lookback_days} DAY
    ORDER BY t.ts_utc
    """
    
    df = conn.execute(query).fetchdf()
    df['ts_utc'] = pd.to_datetime(df['ts_utc'], utc=True)
    return df


def _find_session_start_indices(bars: pd.DataFrame) -> list[int]:
    """Find indices where new RTH sessions start (9:30 ET)."""
    bars = bars.reset_index(drop=True)
    
    ts = pd.to_datetime(bars["ts_utc"], utc=True)
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    ts_et = ts.dt.tz_convert("America/New_York")
    hour = ts_et.dt.hour
    minute = ts_et.dt.minute
    date = ts_et.dt.date
    
    is_930 = (hour == 9) & (minute == 30)
    date_changed = date != date.shift(1)
    session_starts = bars.index[is_930 & date_changed].tolist()
    
    return session_starts


def _build_specs(bars: pd.DataFrame, ticks: pd.DataFrame, params: dict) -> list[TradeSpec]:
    """Build trade specs from IVB opening range breakout logic."""
    specs: list[TradeSpec] = []
    or_bars = int(params["opening_range_bars"])
    wait_retest = bool(params["wait_for_retest"])
    retest_lookback = int(params["retest_lookback"])
    retest_prox = NQ_TICK_SIZE * float(params["retest_proximity_ticks"])
    
    session_starts = _find_session_start_indices(bars)
    tick_ts = ticks["ts_utc"].astype("int64").to_numpy()
    
    for session_idx in session_starts:
        or_end_idx = session_idx + or_bars
        if or_end_idx >= len(bars):
            continue
        
        or_window = bars.iloc[session_idx:or_end_idx]
        if len(or_window) < or_bars:
            continue
        
        ivb_high = float(or_window["high"].max())
        ivb_low = float(or_window["low"].min())
        
        entered_long = False
        entered_short = False
        
        for i in range(or_end_idx, min(or_end_idx + 360, len(bars) - 1)):
            bar = bars.iloc[i]
            
            # Long breakout
            if not entered_long and float(bar.close) > ivb_high:
                direction = "long"
                breakout_bar_idx = i
                
                entry_bar_idx = None
                if wait_retest:
                    for j in range(i + 1, min(i + retest_lookback + 1, len(bars))):
                        test_bar = bars.iloc[j]
                        if abs(float(test_bar.low) - ivb_high) <= retest_prox:
                            entry_bar_idx = j
                            break
                    if entry_bar_idx is None:
                        continue
                else:
                    entry_bar_idx = i
                
                entry_bar = bars.iloc[entry_bar_idx]
                start_ts = pd.to_datetime(entry_bar.ts_utc, utc=True)
                start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
                future = ticks.iloc[start_idx:start_idx + 2000]
                if future.empty:
                    continue
                
                row = future.iloc[0]
                entry_price = float(row.get("ask", np.nan))
                if not np.isfinite(entry_price):
                    continue
                
                specs.append(
                    TradeSpec(
                        entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                        signal_ts=pd.to_datetime(bars.iloc[breakout_bar_idx].ts_utc, utc=True),
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_ticks=float(params["stop_loss_ticks"]),
                        take_profit_ticks=float(params["take_profit_ticks"]),
                        meta={
                            "ivb_high": ivb_high,
                            "ivb_low": ivb_low,
                            "breakout_bar_idx": breakout_bar_idx,
                            "entry_bar_idx": entry_bar_idx,
                            "waited_for_retest": wait_retest,
                        },
                    )
                )
                entered_long = True
            
            # Short breakout
            elif not entered_short and float(bar.close) < ivb_low:
                direction = "short"
                breakout_bar_idx = i
                
                entry_bar_idx = None
                if wait_retest:
                    for j in range(i + 1, min(i + retest_lookback + 1, len(bars))):
                        test_bar = bars.iloc[j]
                        if abs(float(test_bar.high) - ivb_low) <= retest_prox:
                            entry_bar_idx = j
                            break
                    if entry_bar_idx is None:
                        continue
                else:
                    entry_bar_idx = i
                
                entry_bar = bars.iloc[entry_bar_idx]
                start_ts = pd.to_datetime(entry_bar.ts_utc, utc=True)
                start_idx = int(np.searchsorted(tick_ts, start_ts.value // 1000, side="left"))
                future = ticks.iloc[start_idx:start_idx + 2000]
                if future.empty:
                    continue
                
                row = future.iloc[0]
                entry_price = float(row.get("bid", np.nan))
                if not np.isfinite(entry_price):
                    continue
                
                specs.append(
                    TradeSpec(
                        entry_ts=pd.to_datetime(row["ts_utc"], utc=True),
                        signal_ts=pd.to_datetime(bars.iloc[breakout_bar_idx].ts_utc, utc=True),
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_ticks=float(params["stop_loss_ticks"]),
                        take_profit_ticks=float(params["take_profit_ticks"]),
                        meta={
                            "ivb_high": ivb_high,
                            "ivb_low": ivb_low,
                            "breakout_bar_idx": breakout_bar_idx,
                            "entry_bar_idx": entry_bar_idx,
                            "waited_for_retest": wait_retest,
                        },
                    )
                )
                entered_short = True
            
            if entered_long and entered_short:
                break
    
    return specs


def run_backtest(params=PARAMS):
    """Run IVB backtest using optimized DuckDB queries."""
    params = {**PARAMS, **(params or {})}
    
    print(f"Loading data (last {params['lookback_days']} days)...")
    conn = duckdb.connect('/tmp/nq_feed_readonly.duckdb', read_only=True)
    
    bars = _build_bars_from_db(conn, params['lookback_days'])
    print(f"  Loaded {len(bars)} bars")
    
    ticks = _load_ticks_for_fills(conn, params['lookback_days'])
    print(f"  Loaded {len(ticks)} ticks")
    
    conn.close()
    
    print("Building trade specs...")
    specs = _build_specs(bars.reset_index(drop=True), ticks.reset_index(drop=True), params)
    print(f"  Found {len(specs)} signals")
    
    print("Simulating fills...")
    trades = iter_trade_specs(specs, ticks)
    
    print("Computing metrics...")
    metrics = compute_trade_metrics(trades, bars)
    
    return {
        "trades": trades,
        "metrics": {k: v for k, v in metrics.items() if k != "session_breakdown"},
        "session_breakdown": metrics.get("session_breakdown", {}),
    }


if __name__ == "__main__":
    import time
    t0 = time.time()
    result = run_backtest()
    print(f"\n{'='*70}")
    print(f"Strategy 020: Simplest Orderflow Model (IVB)")
    print(f"{'='*70}")
    print(json.dumps(result["metrics"], indent=2))
    print(f"\nRuntime: {time.time() - t0:.1f}s")
