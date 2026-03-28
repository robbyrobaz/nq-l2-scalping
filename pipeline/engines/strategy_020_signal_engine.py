#!/usr/bin/env python3
"""
Strategy 020 Signal Engine - L2 Opening Range Breakout

Reads IBKR tick data, generates signals, outputs to REBEL-ALLIANCE for NT execution.

Config: OR=50 bars, TP=32 ticks, SL=4 ticks
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import duckdb

# Paths
TICK_DB = "/home/rob/infrastructure/ibkr/data/nq_feed.duckdb"
SIGNAL_OUTPUT = Path(__file__).parent.parent.parent / "nt_bridge" / "signal_output.json"
L2_DB = Path(__file__).parent.parent.parent / "data" / "l2_signals.db"

# Strategy params
OR_BARS = 50  # First 50 1-min bars = 9:30-10:20 ET
TP_TICKS = 32  # $640 profit target
SL_TICKS = 4   # $80 stop loss
NQ_TICK_SIZE = 0.25
NQ_TICK_VALUE = 5.0  # $5 per 0.25 tick

# Session windows (UTC)
RTH_START_HOUR_EDT = 13  # 9:30 AM EDT = 1:30 PM UTC
RTH_START_HOUR_EST = 14  # 9:30 AM EST = 2:30 PM UTC
RTH_START_MIN = 30

DRY_RUN = True  # Set False to send real signals to NT


def log(msg):
    """Timestamped log."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def init_db():
    """Create L2 signals database."""
    con = duckdb.connect(str(L2_DB))
    con.execute("""
        CREATE TABLE IF NOT EXISTS l2_signals (
            id INTEGER PRIMARY KEY,
            strategy TEXT,
            timestamp TEXT,
            direction TEXT,
            or_high REAL,
            or_low REAL,
            entry_price REAL,
            tp_price REAL,
            sl_price REAL,
            executed BOOLEAN DEFAULT 0,
            created_at TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS l2_fills (
            id INTEGER PRIMARY KEY,
            signal_id INTEGER,
            entry_time TEXT,
            exit_time TEXT,
            entry_price REAL,
            exit_price REAL,
            contracts INTEGER,
            pnl_usd REAL,
            exit_reason TEXT,
            slippage_ticks REAL,
            fill_latency_ms INTEGER,
            created_at TEXT
        )
    """)
    con.close()


def load_todays_bars():
    """Load today's 1-min bars from IBKR tick DB."""
    con = duckdb.connect(TICK_DB, read_only=True)
    
    # Get today's date
    today = datetime.now(timezone.utc).date()
    start_ts = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    
    # Query 1-min bars
    query = f"""
        SELECT * FROM nq_bars_1min
        WHERE ts_utc >= '{start_ts.isoformat()}'
        ORDER BY ts_utc
    """
    
    try:
        df = con.execute(query).df()
        con.close()
        return df
    except Exception as e:
        log(f"Error loading bars: {e}")
        con.close()
        return pd.DataFrame()


def find_session_start(bars):
    """Find today's RTH session start (9:30 ET)."""
    # Check both EDT (13:30) and EST (14:30) UTC
    for idx, row in bars.iterrows():
        hour = row['ts_utc'].hour
        minute = row['ts_utc'].minute
        if minute == RTH_START_MIN and (hour == RTH_START_HOUR_EDT or hour == RTH_START_HOUR_EST):
            return idx
    return None


def calculate_or(bars, start_idx):
    """Calculate opening range (first 50 bars)."""
    end_idx = start_idx + OR_BARS
    if end_idx >= len(bars):
        return None, None
    
    or_window = bars.iloc[start_idx:end_idx]
    or_high = or_window['high'].max()
    or_low = or_window['low'].min()
    
    return or_high, or_low


def check_breakout(bars, or_idx, or_high, or_low):
    """Check if current bar breaks OR high/low."""
    current_idx = len(bars) - 1
    
    # Only check after OR period completes
    if current_idx < or_idx + OR_BARS:
        return None, None
    
    current_bar = bars.iloc[current_idx]
    
    # Long breakout
    if current_bar['close'] > or_high:
        entry_price = or_high + NQ_TICK_SIZE  # Fill at breakout + 1 tick
        tp_price = entry_price + (TP_TICKS * NQ_TICK_SIZE)
        sl_price = entry_price - (SL_TICKS * NQ_TICK_SIZE)
        return 'long', {
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'or_high': or_high,
            'or_low': or_low,
        }
    
    # Short breakout
    if current_bar['close'] < or_low:
        entry_price = or_low - NQ_TICK_SIZE
        tp_price = entry_price - (TP_TICKS * NQ_TICK_SIZE)
        sl_price = entry_price + (SL_TICKS * NQ_TICK_SIZE)
        return 'short', {
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'or_high': or_high,
            'or_low': or_low,
        }
    
    return None, None


def save_signal(direction, params):
    """Save signal to database."""
    con = duckdb.connect(str(L2_DB))
    
    con.execute("""
        INSERT INTO l2_signals (
            strategy, timestamp, direction, or_high, or_low,
            entry_price, tp_price, sl_price, executed, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'strategy_020',
        datetime.now(timezone.utc).isoformat(),
        direction,
        params['or_high'],
        params['or_low'],
        params['entry_price'],
        params['tp_price'],
        params['sl_price'],
        False,
        datetime.now(timezone.utc).isoformat()
    ))
    
    con.close()


def output_signal(direction, params):
    """Write signal to JSON for REBEL-ALLIANCE to read."""
    signal = {
        'strategy': 'strategy_020',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'direction': direction,
        'entry_price': params['entry_price'],
        'tp_price': params['tp_price'],
        'sl_price': params['sl_price'],
        'or_high': params['or_high'],
        'or_low': params['or_low'],
        'contracts': 1,  # Start with 1 for sim testing
        'account': 'SimL2020',
        'dry_run': DRY_RUN
    }
    
    SIGNAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNAL_OUTPUT, 'w') as f:
        json.dump(signal, f, indent=2)
    
    log(f"✅ Signal written: {direction.upper()} @ {params['entry_price']:.2f}")


def run():
    """Main engine loop."""
    log("="*70)
    log("STRATEGY 020 SIGNAL ENGINE — L2 Opening Range Breakout")
    log("="*70)
    log(f"Config: OR={OR_BARS} bars, TP={TP_TICKS} ticks, SL={SL_TICKS} ticks")
    log(f"Data source: IBKR tick DB (DuckDB)")
    log(f"Execution: NinjaTrader ATI via REBEL-ALLIANCE")
    log(f"Account: SimL2020 (paper)")
    log(f"Dry run: {DRY_RUN}")
    log("="*70)
    
    init_db()
    
    or_high = None
    or_low = None
    or_start_idx = None
    signal_fired = False
    
    while True:
        try:
            # Load today's bars
            bars = load_todays_bars()
            
            if bars.empty:
                log("No bars yet, waiting...")
                time.sleep(60)
                continue
            
            # Find session start (if not already found)
            if or_start_idx is None:
                or_start_idx = find_session_start(bars)
                if or_start_idx is not None:
                    log(f"✅ RTH session start found at index {or_start_idx}")
                    or_high, or_low = calculate_or(bars, or_start_idx)
                    if or_high and or_low:
                        log(f"✅ Opening range: HIGH={or_high:.2f}, LOW={or_low:.2f}")
                else:
                    log("Waiting for RTH session start (9:30 ET)...")
                    time.sleep(60)
                    continue
            
            # Check for breakout (only fire once per session)
            if not signal_fired and or_high and or_low:
                direction, params = check_breakout(bars, or_start_idx, or_high, or_low)
                
                if direction:
                    log(f"🎯 BREAKOUT DETECTED: {direction.upper()}")
                    log(f"   Entry: {params['entry_price']:.2f}")
                    log(f"   TP: {params['tp_price']:.2f} (+{TP_TICKS} ticks)")
                    log(f"   SL: {params['sl_price']:.2f} (-{SL_TICKS} ticks)")
                    
                    save_signal(direction, params)
                    output_signal(direction, params)
                    
                    signal_fired = True
                    log("✅ Signal sent to REBEL-ALLIANCE")
            
            # Check if session is over (reset for next day after 4 PM ET)
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            # 4 PM ET = 20:00 UTC (EDT) or 21:00 UTC (EST)
            if current_hour >= 20:
                if signal_fired or or_start_idx is not None:
                    log("📅 RTH session ended, resetting for next day")
                    or_start_idx = None
                    or_high = None
                    or_low = None
                    signal_fired = False
            
            # Sleep 60 seconds between checks
            time.sleep(60)
            
        except KeyboardInterrupt:
            log("⛔ Shutdown requested")
            break
        except Exception as e:
            log(f"❌ Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    run()
