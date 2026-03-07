"""Load historical NQ tick data and run strategies 001, 002, 003."""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import importlib.util
import glob

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.data_loader import (
    build_1min_bars_with_delta, compute_cvd, filter_rth,
    NQ_TICK_SIZE, MNQ_TICK_VALUE, pnl_mnq
)
from pipeline.optimize import STRATEGIES

TICK_DATA_PATH = "/home/rob/.openclaw/workspace/NQ-Trading-PIPELINE/processed_data/tick"


def load_historical_ticks():
    """Load all parquet files from tick folder and combine.

    Returns:
        DataFrame: ts_utc, price, size, side, delta
    """
    print("Loading historical tick data...")
    parquet_files = sorted(glob.glob(f"{TICK_DATA_PATH}/*.parquet"))
    print(f"  Found {len(parquet_files)} files")

    all_trades = []
    for pf in parquet_files:
        print(f"  Loading {Path(pf).name}...", end=" ", flush=True)
        df = pd.read_parquet(pf)
        print(f"({len(df)} ticks)", flush=True)

        # Rename columns to match expected format
        df = df.rename(columns={
            'datetime': 'ts_utc',
            'last': 'price',
            'volume': 'size',
        })

        # Convert to UTC datetime
        df['ts_utc'] = pd.to_datetime(df['ts_utc'], utc=True)

        # Infer side from bid/ask
        # If trade price >= ask: side = 'B' (aggressive buyer lifted the ask)
        # If trade price <= bid: side = 'S' (aggressive seller hit the bid)
        # Otherwise: side = '' (mid-market)
        df['side'] = np.where(
            df['price'] >= df['ask'], 'B',
            np.where(df['price'] <= df['bid'], 'S', '')
        )

        # Compute delta
        df['delta'] = np.where(
            df['side'] == 'B', df['size'],
            np.where(df['side'] == 'S', -df['size'], 0)
        )

        all_trades.append(df[['ts_utc', 'price', 'size', 'side', 'delta']])

    trades = pd.concat(all_trades, ignore_index=True)
    trades = trades.sort_values('ts_utc').reset_index(drop=True)

    print(f"\nTotal ticks loaded: {len(trades):,}")
    print(f"Date range: {trades['ts_utc'].min()} to {trades['ts_utc'].max()}")

    return trades


def run_strategy(strategy_id, trades, trades_fast=None, data_dir="data/results/historical"):
    """Run a strategy on the historical data."""

    print(f"\n{'='*60}")
    print(f"Strategy {strategy_id}: Running...")
    print(f"{'='*60}")

    if strategy_id not in STRATEGIES:
        print(f"Strategy {strategy_id} not found")
        return None

    # Get backtest module from STRATEGIES
    backtest_mod = STRATEGIES[strategy_id]['backtest']
    strategy_name = STRATEGIES[strategy_id]['name']

    # Filter to RTH
    trades_rth = filter_rth(trades, ts_col='ts_utc')
    print(f"RTH trades: {len(trades_rth):,}")

    # Build 1-min bars
    bars = build_1min_bars_with_delta(trades_rth)
    print(f"1-min bars: {len(bars)}")

    # Add CVD if needed (for 003)
    if strategy_id == '003':
        bars = compute_cvd(bars)

    # Run all variations
    variations = STRATEGIES[strategy_id].get('variations', {})

    results = []
    for var_id in sorted(variations.keys()):
        var = variations[var_id]
        params = var['params']

        print(f"\n  Variation {var_id}: {var['name']}")

        try:
            # Strategy-specific signal finding
            if strategy_id == '001':
                signals = backtest_mod.find_signals(bars, params)
            elif strategy_id == '002':
                # Strategy 002: find swings → fvg_levels → signals
                if trades_fast is None:
                    trades_fast = trades_rth[['ts_utc', 'price', 'size']].copy()
                swings = backtest_mod.find_swings(bars, lookback=params['swing_lookback'])
                fvg_levels = backtest_mod.find_fvg_levels(swings, trades_fast, bars, params)
                signals = backtest_mod.find_signals(fvg_levels, bars, params)
            elif strategy_id == '003':
                signals = backtest_mod.find_divergences(bars, params)
            else:
                print(f"    ERROR: Unknown strategy {strategy_id}")
                continue

            print(f"    Signals: {len(signals)}")

            # Simulate trades
            trades_result = backtest_mod.simulate_trades(signals, bars, params)
            print(f"    Trades: {len(trades_result)}")

            # Compute metrics
            metrics = backtest_mod.compute_metrics(trades_result)
            print(f"    PF: {metrics['profit_factor']:.2f}, Sharpe: {metrics['sharpe']:.2f}, "
                  f"WR: {metrics['win_rate']*100:.1f}%, Net: ${metrics['net_pnl_usd']:.0f}")

            results.append({
                'variation_id': var_id,
                'variation_name': var['name'],
                'params': params,
                'signals': len(signals),
                'trades': len(trades_result),
                'trades_detail': trades_result,
                **metrics
            })
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Save results
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    result_file = Path(data_dir) / f"{strategy_id}_historical.json"

    # Convert trades_detail to serializable format
    for r in results:
        trades_list = r.pop('trades_detail', [])
        r['trades_detail'] = [
            {
                'entry_ts': str(t['entry_ts']),
                'exit_ts': str(t['exit_ts']),
                'direction': t['direction'],
                'entry_price': float(t['entry_price']),
                'exit_price': float(t['exit_price']),
                'pnl_ticks': float(t['pnl_ticks']),
                'pnl_usd': pnl_mnq(t['pnl_ticks']),
            }
            for t in trades_list
        ]

    with open(result_file, 'w') as f:
        json.dump({
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'date_generated': datetime.now().isoformat(),
            'data_range': {
                'start': str(trades['ts_utc'].min()),
                'end': str(trades['ts_utc'].max()),
                'total_ticks': len(trades),
                'rth_ticks': len(trades_rth),
                'bars': len(bars),
            },
            'variations': results,
        }, f, indent=2)

    print(f"\n  Saved: {result_file}")
    return results


if __name__ == '__main__':
    # Load historical data once
    trades = load_historical_ticks()

    # Create trades_fast variant (without side/delta info) for strategy 002
    trades_fast = trades[['ts_utc', 'price', 'size']].copy()

    # Run strategies
    for strategy_id in ['001', '002', '003']:
        try:
            run_strategy(strategy_id, trades, trades_fast)
        except Exception as e:
            print(f"\nERROR in strategy {strategy_id}: {e}")
            import traceback
            traceback.print_exc()
