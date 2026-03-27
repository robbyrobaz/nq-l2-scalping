"""Ultra-fast backtest for Strategy 020 (IVB/Opening Range).

Simplified version that:
1. Uses pre-aggregated 1-min bars from CSV (faster than DuckDB tick processing)
2. Skips delta calculation (not needed for opening range breakout)
3. Uses simplified fill simulation
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.data_loader import NQ_TICK_SIZE

CSV_PATH = "/home/rob/infrastructure/ibkr/data/NQ_ibkr_1min.csv"

PARAMS = {
    "opening_range_bars": 30,
    "take_profit_ticks": 16,
    "stop_loss_ticks": 8,
    "lookback_days": 14,
}


def load_bars(lookback_days=14):
    """Load 1-min bars from CSV."""
    df = pd.read_csv(CSV_PATH, parse_dates=['timestamp'])
    df = df.rename(columns={'timestamp': 'ts_utc'})
    df['ts_utc'] = pd.to_datetime(df['ts_utc'], utc=True)
    
    # Filter to recent data
    cutoff = df['ts_utc'].max() - pd.Timedelta(days=lookback_days)
    df = df[df['ts_utc'] >= cutoff].copy()
    
    return df.sort_values('ts_utc').reset_index(drop=True)


def find_session_starts(bars):
    """Find 9:30 ET RTH session starts."""
    # Data is in UTC. 9:30 ET = 13:30 UTC (EDT) or 14:30 UTC (EST)
    # March 2026: DST starts Mar 8
    hour = bars['ts_utc'].dt.hour
    minute = bars['ts_utc'].dt.minute
    
    # Find 13:30 or 14:30 UTC (both are 9:30 ET depending on DST)
    is_930 = (minute == 30) & ((hour == 13) | (hour == 14))
    return bars.index[is_930].tolist()


def simulate_trade(entry_idx, direction, entry_price, bars, tp_ticks, sl_ticks):
    """Simulate trade outcome using bar data."""
    tp_price = entry_price + (tp_ticks * NQ_TICK_SIZE if direction == 'long' else -tp_ticks * NQ_TICK_SIZE)
    sl_price = entry_price - (sl_ticks * NQ_TICK_SIZE if direction == 'long' else -sl_ticks * NQ_TICK_SIZE)
    
    # Scan next 100 bars (up to ~2 hours)
    for i in range(entry_idx + 1, min(entry_idx + 100, len(bars))):
        bar = bars.iloc[i]
        
        if direction == 'long':
            if bar['low'] <= sl_price:
                return 'loss', sl_price, bar['ts_utc']
            if bar['high'] >= tp_price:
                return 'win', tp_price, bar['ts_utc']
        else:  # short
            if bar['high'] >= sl_price:
                return 'loss', sl_price, bar['ts_utc']
            if bar['low'] <= tp_price:
                return 'win', tp_price, bar['ts_utc']
    
    # Timed out - close at last bar
    last_bar = bars.iloc[min(entry_idx + 99, len(bars) - 1)]
    exit_price = last_bar['close']
    outcome = 'timeout'
    return outcome, exit_price, last_bar['ts_utc']


def run_backtest(params=PARAMS):
    """Run IVB backtest."""
    print(f"Loading bars (last {params['lookback_days']} days)...")
    bars = load_bars(params['lookback_days'])
    print(f"  {len(bars)} bars loaded")
    
    or_bars = params['opening_range_bars']
    tp_ticks = params['take_profit_ticks']
    sl_ticks = params['stop_loss_ticks']
    
    session_starts = find_session_starts(bars)
    print(f"  {len(session_starts)} RTH sessions found")
    
    trades = []
    
    for session_idx in session_starts:
        or_end_idx = session_idx + or_bars
        if or_end_idx >= len(bars):
            continue
        
        or_window = bars.iloc[session_idx:or_end_idx]
        ivb_high = or_window['high'].max()
        ivb_low = or_window['low'].min()
        
        entered_long = False
        entered_short = False
        
        # Scan for breakouts
        for i in range(or_end_idx, min(or_end_idx + 360, len(bars) - 1)):
            bar = bars.iloc[i]
            
            # Long breakout
            if not entered_long and bar['close'] > ivb_high:
                entry_price = ivb_high + NQ_TICK_SIZE  # Assume filled at breakout + 1 tick
                outcome, exit_price, exit_ts = simulate_trade(
                    i, 'long', entry_price, bars, tp_ticks, sl_ticks
                )
                
                pnl = (exit_price - entry_price) * (20 / NQ_TICK_SIZE)  # $20 per tick for NQ
                
                trades.append({
                    'entry_ts': bar['ts_utc'],
                    'exit_ts': exit_ts,
                    'direction': 'long',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'outcome': outcome,
                    'ivb_high': ivb_high,
                    'ivb_low': ivb_low,
                })
                entered_long = True
            
            # Short breakout
            elif not entered_short and bar['close'] < ivb_low:
                entry_price = ivb_low - NQ_TICK_SIZE
                outcome, exit_price, exit_ts = simulate_trade(
                    i, 'short', entry_price, bars, tp_ticks, sl_ticks
                )
                
                pnl = (entry_price - exit_price) * (20 / NQ_TICK_SIZE)
                
                trades.append({
                    'entry_ts': bar['ts_utc'],
                    'exit_ts': exit_ts,
                    'direction': 'short',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'outcome': outcome,
                    'ivb_high': ivb_high,
                    'ivb_low': ivb_low,
                })
                entered_short = True
            
            if entered_long and entered_short:
                break
    
    if not trades:
        return {
            'num_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'net_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
        }
    
    df_trades = pd.DataFrame(trades)
    
    wins = df_trades[df_trades['outcome'] == 'win']
    losses = df_trades[df_trades['outcome'] == 'loss']
    
    num_trades = len(df_trades)
    num_wins = len(wins)
    num_losses = len(losses)
    win_rate = num_wins / num_trades if num_trades > 0 else 0
    
    total_wins = wins['pnl'].sum() if len(wins) > 0 else 0
    total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
    
    profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
    net_pnl = df_trades['pnl'].sum()
    
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    
    return {
        'num_trades': num_trades,
        'num_wins': num_wins,
        'num_losses': num_losses,
        'win_rate': round(win_rate, 3),
        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.0,
        'net_pnl': round(net_pnl, 2),
        'total_wins': round(total_wins, 2),
        'total_losses': round(total_losses, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'trades': df_trades.to_dict('records')[:10],  # First 10 trades for review
    }


if __name__ == "__main__":
    import time
    t0 = time.time()
    result = run_backtest()
    runtime = time.time() - t0
    
    print(f"\n{'='*70}")
    print(f"Strategy 020: Simplest Orderflow Model (IVB)")
    print(f"Opening Range: {PARAMS['opening_range_bars']} bars | TP: {PARAMS['take_profit_ticks']} | SL: {PARAMS['stop_loss_ticks']}")
    print(f"{'='*70}")
    
    metrics = {k: v for k, v in result.items() if k != 'trades'}
    print(json.dumps(metrics, indent=2))
    
    print(f"\nRuntime: {runtime:.1f}s")
    
    if result['num_trades'] > 0:
        print(f"\n📊 Sample trades:")
        for i, t in enumerate(result['trades'][:5], 1):
            print(f"  {i}. {t['direction'].upper():5} | Entry: {t['entry_price']:.2f} → Exit: {t['exit_price']:.2f} | PnL: ${t['pnl']:+.2f} | {t['outcome']}")
