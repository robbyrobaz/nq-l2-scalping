"""022: Delta Absorption at ORB Levels

Combines:
- Opening Range (OR) high/low levels (first 15-30min of RTH)
- Delta absorption detection (heavy delta against price movement)
- Thin orderbook signal (low liquidity at key levels = easier to reverse)

Theory: When price hits OR high/low and shows delta absorption
(heavy selling into highs / heavy buying into lows), it's a high-probability
reversal setup. Add thin book confirmation for increased edge.

Entry Logic:
1. Calculate OR high/low from first N bars of each session
2. Wait for price to touch OR high/low
3. Detect delta absorption (delta opposite to price direction)
4. Confirm thin orderbook (bid or ask depth < threshold)
5. Enter fade

Sessions: RTH (NY Open, MidDay, PowerHour)

Exit:
- TP: Back across OR to opposite boundary or fixed ticks
- SL: Beyond the touched OR level
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import load_tick_data

PARAMS = {
    'or_bars': 15,  # Opening range window (15 min = 15 bars if 1min)
    'delta_threshold': 200,  # Minimum cumulative delta against move
    'thin_book_threshold': 300,  # Max depth at touched level (thin = < 300 contracts)
    'take_profit_ticks': 12,
    'stop_loss_ticks': 8,
    'session_filter': ['NYOpen', 'MidDay', 'PowerHour'],
}


def detect_rth_sessions(df):
    """Mark RTH sessions (9:30 AM - 4 PM ET = 7:30 AM - 2 PM MST)."""
    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df['minute'] = pd.to_datetime(df['timestamp']).dt.minute
    df['is_rth'] = (
        ((df['hour'] == 7) & (df['minute'] >= 30)) |
        ((df['hour'] >= 8) & (df['hour'] < 14))
    )
    return df


def calculate_or_levels(df, or_bars):
    """Calculate OR high/low for each session."""
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    df['OR_high'] = np.nan
    df['OR_low'] = np.nan
    
    for date in df['date'].unique():
        day_data = df[df['date'] == date]
        if len(day_data) < or_bars:
            continue
        
        or_window = day_data.iloc[:or_bars]
        or_high = or_window['high'].max()
        or_low = or_window['low'].min()
        
        # Apply to rest of day
        df.loc[df['date'] == date, 'OR_high'] = or_high
        df.loc[df['date'] == date, 'OR_low'] = or_low
    
    return df


def run_backtest(params):
    """Run backtest with given parameters."""
    # Load data
    df = load_tick_data(start_date='2026-03-05', end_date='2026-03-26')
    df = detect_rth_sessions(df)
    
    # Filter to RTH
    session_filter = params.get('session_filter', ['NYOpen', 'MidDay', 'PowerHour'])
    if session_filter:
        df = df[df['is_rth']].copy()
    
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
    
    # Calculate OR levels
    df = calculate_or_levels(df, params['or_bars'])
    
    # Calculate cumulative delta
    df['delta'] = df['volume'] * np.where(df['close'] > df['open'], 1, -1)
    df['cumulative_delta'] = df['delta'].rolling(window=5).sum()
    
    # Detect signals
    signals = []
    delta_threshold = params['delta_threshold']
    thin_book_threshold = params['thin_book_threshold']
    
    for i in range(params['or_bars'] + 10, len(df)):
        row = df.iloc[i]
        
        or_high = row['OR_high']
        or_low = row['OR_low']
        
        if pd.isna(or_high) or pd.isna(or_low):
            continue
        
        price = row['close']
        cum_delta = row['cumulative_delta']
        
        # Check bid/ask depth (use volume as proxy if depth not available)
        bid_depth = row.get('bid_size', row['volume'])
        ask_depth = row.get('ask_size', row['volume'])
        
        # Signal 1: Price at OR high + negative delta (absorption) + thin ask
        if abs(price - or_high) < 1.0 and cum_delta < -delta_threshold and ask_depth < thin_book_threshold:
            signals.append({
                'timestamp': row['timestamp'],
                'direction': 'short',
                'entry_price': row['ask'] + 0.25,
                'stop_price': or_high + params['stop_loss_ticks'] * 0.25,
                'target_price': or_low,
            })
        
        # Signal 2: Price at OR low + positive delta (absorption) + thin bid
        if abs(price - or_low) < 1.0 and cum_delta > delta_threshold and bid_depth < thin_book_threshold:
            signals.append({
                'timestamp': row['timestamp'],
                'direction': 'long',
                'entry_price': row['bid'] - 0.25,
                'stop_price': or_low - params['stop_loss_ticks'] * 0.25,
                'target_price': or_high,
            })
    
    # Build trade specs
    trade_specs = []
    for sig in signals:
        # TP: back to opposite OR level or fixed ticks (whichever is closer)
        if sig['direction'] == 'long':
            tp_distance = min(
                sig['target_price'] - sig['entry_price'],
                params['take_profit_ticks'] * 0.25
            )
            tp_price = sig['entry_price'] + tp_distance
        else:
            tp_distance = min(
                sig['entry_price'] - sig['target_price'],
                params['take_profit_ticks'] * 0.25
            )
            tp_price = sig['entry_price'] - tp_distance
        
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
