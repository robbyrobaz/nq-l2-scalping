"""023: London Sweep Fade (Filtered)

Based on 007 Sweep Fade but heavily filtered:
- London killzone ONLY (2 AM - 8 AM MST)
- Thin orderbook confirmation (low liquidity = easier fade)
- Stricter sweep threshold (reduce signal count from 867 → ~50-100)

Theory: London session sweeps are often false breakouts due to thin
liquidity. When price sweeps a level quickly in thin conditions,
it's a high-probability fade setup.

Entry Logic:
1. Detect rapid price sweep (X ticks in Y seconds)
2. Confirm thin orderbook at the sweep extreme
3. Wait for initial retracement (confirms rejection)
4. Enter fade

Session: London only (2 AM - 8 AM MST)

Exit:
- TP: Fixed ticks back toward pre-sweep level
- SL: Beyond sweep extreme
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import load_tick_data

PARAMS = {
    'sweep_tick_threshold': 10,  # Stricter: 10 ticks minimum (vs 5-8 in 007)
    'sweep_time_seconds': 30,
    'thin_book_threshold': 200,  # Max depth at sweep extreme
    'retracement_min_ticks': 2,  # Must see 2+ tick pullback
    'take_profit_ticks': 6,
    'stop_loss_ticks': 10,
    'session_filter': ['London'],
}


def detect_london_sessions(df):
    """Mark London killzone bars (2 AM - 8 AM MST)."""
    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df['is_london'] = (df['hour'] >= 2) & (df['hour'] < 8)
    return df


def run_backtest(params):
    """Run backtest with given parameters."""
    # Load data
    df = load_tick_data(start_date='2026-03-05', end_date='2026-03-26')
    df = detect_london_sessions(df)
    
    # Filter to London session
    session_filter = params.get('session_filter', ['London'])
    if session_filter:
        df = df[df['is_london']].copy()
    
    if len(df) < 100:
        return {
            'params': params,
            'metrics': {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'net_pnl_usd': 0.0,
                'gross_profit_usd': 0.0,
                'gross_loss_usd': 0.0,
                'avg_win_usd': 0.0,
                'avg_loss_usd': 0.0,
                'max_drawdown_usd': 0.0,
            },
            'trades': [],
        }
    
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
    
    # Detect sweeps
    signals = []
    sweep_threshold = params['sweep_tick_threshold']
    sweep_window = timedelta(seconds=params['sweep_time_seconds'])
    thin_book = params['thin_book_threshold']
    retracement_min = params['retracement_min_ticks']
    
    for i in range(10, len(df)):
        row = df.iloc[i]
        
        # Look back for rapid price movement
        window_start_time = row['timestamp_dt'] - sweep_window
        recent = df[(df['timestamp_dt'] >= window_start_time) & (df['timestamp_dt'] <= row['timestamp_dt'])]
        
        if len(recent) < 2:
            continue
        
        high_in_window = recent['high'].max()
        low_in_window = recent['low'].min()
        range_ticks = (high_in_window - low_in_window) / 0.25
        
        # Check if sweep occurred (rapid move up or down)
        if range_ticks < sweep_threshold:
            continue
        
        # Check thin book at extreme
        ask_depth = row.get('ask_size', row['volume'])
        bid_depth = row.get('bid_size', row['volume'])
        
        price = row['close']
        
        # Sweep up (potential fade short)
        if price >= high_in_window - 0.5:  # At or near high
            if ask_depth < thin_book:
                # Check for retracement in next few bars
                next_bars = df.iloc[i:i+5]
                if len(next_bars) > 1:
                    min_after = next_bars['low'].min()
                    retracement_ticks = (price - min_after) / 0.25
                    
                    if retracement_ticks >= retracement_min:
                        signals.append({
                            'timestamp': row['timestamp'],
                            'direction': 'short',
                            'entry_price': row['ask'] + 0.25,
                            'stop_price': high_in_window + params['stop_loss_ticks'] * 0.25,
                            'sweep_extreme': high_in_window,
                        })
        
        # Sweep down (potential fade long)
        if price <= low_in_window + 0.5:  # At or near low
            if bid_depth < thin_book:
                # Check for retracement in next few bars
                next_bars = df.iloc[i:i+5]
                if len(next_bars) > 1:
                    max_after = next_bars['high'].max()
                    retracement_ticks = (max_after - price) / 0.25
                    
                    if retracement_ticks >= retracement_min:
                        signals.append({
                            'timestamp': row['timestamp'],
                            'direction': 'long',
                            'entry_price': row['bid'] - 0.25,
                            'stop_price': low_in_window - params['stop_loss_ticks'] * 0.25,
                            'sweep_extreme': low_in_window,
                        })
    
    # Build trade specs
    trade_specs = []
    for sig in signals:
        if sig['direction'] == 'long':
            tp_price = sig['entry_price'] + params['take_profit_ticks'] * 0.25
        else:
            tp_price = sig['entry_price'] - params['take_profit_ticks'] * 0.25
        
        trade_specs.append(TradeSpec(
            entry_time=sig['timestamp'],
            direction=sig['direction'],
            entry_price=sig['entry_price'],
            stop_loss=sig['stop_price'],
            take_profit=tp_price,
        ))
    
    # Execute trades
    trades = list(iter_trade_specs(df, trade_specs, tick_level=True))
    
    # Compute metrics
    metrics = compute_trade_metrics(trades)
    
    return {
        'params': params,
        'metrics': metrics,
        'trades': trades,
    }
