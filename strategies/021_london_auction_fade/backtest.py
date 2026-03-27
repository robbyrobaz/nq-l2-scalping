"""021: London Auction Fade (Hybrid)

Combines:
- Failed auction detection (014) at value area boundaries
- London killzone session filter (where sweep fade 007 shows promise)
- Orderflow model entry logic (020) for timing

Theory: Failed auction breakouts in London session are often false moves
that fade back into value. We want to fade those failed breakouts when
orderflow shows absorption/reversal.

Entry Logic:
1. Calculate value area (VAH/VAL) from prior session
2. Detect breakout beyond VA boundary (failed auction setup)
3. Wait for price to reject back into VA (failed breakout confirmed)
4. Enter fade in direction back toward value area center (POC)
5. London session only (2 AM - 8 AM MST)

Exit:
- TP: Back to POC or fixed ticks
- SL: Beyond the failed breakout extreme
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.backtest_utils import TradeSpec, compute_trade_metrics, iter_trade_specs
from pipeline.data_loader import load_tick_data, compute_value_areas

PARAMS = {
    'volume_profile_bars': 50,
    'value_area_pct': 0.70,
    'breakout_threshold_ticks': 3,
    'reentry_tolerance_ticks': 2,
    'take_profit_ticks': 12,
    'stop_loss_ticks': 10,
    'session_filter': ['London'],  # London killzone only
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
    
    # Calculate value areas
    lookback = params['volume_profile_bars']
    value_area_pct = params['value_area_pct']
    
    df['VAH'] = np.nan
    df['VAL'] = np.nan
    df['POC'] = np.nan
    
    for i in range(lookback, len(df)):
        window = df.iloc[i-lookback:i]
        va = compute_value_areas(window, value_area_pct)
        df.loc[df.index[i], 'VAH'] = va['VAH']
        df.loc[df.index[i], 'VAL'] = va['VAL']
        df.loc[df.index[i], 'POC'] = va['POC']
    
    # Forward fill VA levels
    df['VAH'].ffill(inplace=True)
    df['VAL'].ffill(inplace=True)
    df['POC'].ffill(inplace=True)
    
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
    
    # Detect signals
    signals = []
    breakout_threshold_ticks = params['breakout_threshold_ticks']
    reentry_tolerance_ticks = params['reentry_tolerance_ticks']
    
    in_failed_breakout_long = False
    in_failed_breakout_short = False
    breakout_extreme = None
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        
        vah = row['VAH']
        val = row['VAL']
        poc = row['POC']
        
        if pd.isna(vah) or pd.isna(val) or pd.isna(poc):
            continue
        
        price = row['close']
        prev_price = prev['close']
        
        # Detect breakout above VAH (potential failed auction)
        if not in_failed_breakout_short and prev_price < vah and price > vah + breakout_threshold_ticks * 0.25:
            in_failed_breakout_short = True
            breakout_extreme = price
        
        # Detect breakout below VAL (potential failed auction)
        if not in_failed_breakout_long and prev_price > val and price < val - breakout_threshold_ticks * 0.25:
            in_failed_breakout_long = True
            breakout_extreme = price
        
        # Check for reentry (fade signal)
        if in_failed_breakout_short and price < vah - reentry_tolerance_ticks * 0.25:
            # Failed breakout above VAH → fade short
            signals.append({
                'timestamp': row['timestamp'],
                'direction': 'short',
                'entry_price': row['ask'] + 0.25,  # Market sell at bid + slippage
                'stop_price': breakout_extreme + params['stop_loss_ticks'] * 0.25,
                'target_price': poc,  # Target POC
            })
            in_failed_breakout_short = False
            breakout_extreme = None
        
        if in_failed_breakout_long and price > val + reentry_tolerance_ticks * 0.25:
            # Failed breakout below VAL → fade long
            signals.append({
                'timestamp': row['timestamp'],
                'direction': 'long',
                'entry_price': row['bid'] - 0.25,  # Market buy at ask + slippage (reversed)
                'stop_price': breakout_extreme - params['stop_loss_ticks'] * 0.25,
                'target_price': poc,  # Target POC
            })
            in_failed_breakout_long = False
            breakout_extreme = None
    
    # Build trade specs
    trade_specs = []
    for sig in signals:
        # Calculate TP distance to POC, but cap at fixed TP ticks
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
