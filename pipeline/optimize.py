"""Parameter optimization framework for scalping strategies.

Runs all parameter combinations for a given strategy and returns results
ranked by profit factor, then net PnL.
"""

import sys
import json
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime
from itertools import product

import pandas as pd

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import backtest modules dynamically

import importlib.util
spec_001 = importlib.util.spec_from_file_location("backtest_001",
    Path(__file__).resolve().parents[1] / 'strategies' / '001_delta_absorption_breakout' / 'backtest.py')
s001_backtest = importlib.util.module_from_spec(spec_001)
spec_001.loader.exec_module(s001_backtest)

spec_002 = importlib.util.spec_from_file_location("backtest_002",
    Path(__file__).resolve().parents[1] / 'strategies' / '002_volume_profile_fvg' / 'backtest.py')
s002_backtest = importlib.util.module_from_spec(spec_002)
spec_002.loader.exec_module(s002_backtest)

spec_003 = importlib.util.spec_from_file_location("backtest_003",
    Path(__file__).resolve().parents[1] / 'strategies' / '003_cvd_divergence' / 'backtest.py')
s003_backtest = importlib.util.module_from_spec(spec_003)
spec_003.loader.exec_module(s003_backtest)


STRATEGIES = {
    '001': {
        'name': 'Delta Absorption Breakout',
        'backtest': s001_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'delta_threshold': 200,
                    'range_window': 5,
                    'range_atr_mult': 3.0,
                    'absorption_bars': 1,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'delta_threshold': 300,
                    'range_window': 10,
                    'range_atr_mult': 3.0,
                    'absorption_bars': 1,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 12,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide Range',
                'params': {
                    'delta_threshold': 400,
                    'range_window': 15,
                    'range_atr_mult': 3.0,
                    'absorption_bars': 1,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive TP',
                'params': {
                    'delta_threshold': 300,
                    'range_window': 8,
                    'range_atr_mult': 3.0,
                    'absorption_bars': 1,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'delta_threshold': 150,
                    'range_window': 5,
                    'range_atr_mult': 3.0,
                    'absorption_bars': 1,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 4,
                    'stop_loss_ticks': 3,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '002': {
        'name': 'Volume Profile FVG',
        'backtest': s002_backtest,
        'variations': {
            1: {
                'name': 'Tight Swings',
                'params': {
                    'swing_lookback': 10,
                    'min_leg_size_ticks': 15,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'max_retrace_time_bars': 30,
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'swing_lookback': 20,
                    'min_leg_size_ticks': 20,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'max_retrace_time_bars': 30,
                }
            },
            3: {
                'name': 'Wide Swings',
                'params': {
                    'swing_lookback': 30,
                    'min_leg_size_ticks': 30,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 10,
                    'max_retrace_time_bars': 30,
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'swing_lookback': 15,
                    'min_leg_size_ticks': 15,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 20,
                    'stop_loss_ticks': 8,
                    'max_retrace_time_bars': 30,
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'swing_lookback': 10,
                    'min_leg_size_ticks': 10,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'max_retrace_time_bars': 30,
                }
            },
        }
    },
    '003': {
        'name': 'CVD Divergence',
        'backtest': s003_backtest,
        'variations': {
            1: {
                'name': 'Sensitive',
                'params': {
                    'divergence_window': 3,
                    'min_cvd_move': 300,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'divergence_window': 5,
                    'min_cvd_move': 500,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'divergence_window': 7,
                    'min_cvd_move': 700,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Momentum',
                'params': {
                    'divergence_window': 4,
                    'min_cvd_move': 400,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'divergence_window': 3,
                    'min_cvd_move': 200,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 5,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
        }
    }
}


def run_variation(strategy_id, variation_num, variation_spec):
    """Run a single parameter variation and return results."""
    try:
        print(f"  [{variation_num}] {variation_spec['name']}...", end=" ", flush=True)

        result = STRATEGIES[strategy_id]['backtest'].run(variation_spec['params'])

        metrics = result['metrics']
        result['variation'] = variation_num
        result['variation_name'] = variation_spec['name']

        # Flag high potential configs
        potential = "🚀 HIGH POTENTIAL" if (
            metrics['profit_factor'] > 2.0 and metrics['total_trades'] > 5
        ) else ""

        status = "✓" if metrics['profit_factor'] > 1.5 else "·"
        print(f"{status} PF={metrics['profit_factor']:.2f} PnL=${metrics['net_pnl_usd']:.0f} {potential}")

        return result
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return None


def run_optimization(strategy_id):
    """Run all variations for a strategy and return ranked results."""
    if strategy_id not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}")

    strat = STRATEGIES[strategy_id]
    print(f"\n{'='*70}")
    print(f"Strategy {strategy_id}: {strat['name']}")
    print(f"{'='*70}")

    results = []
    for var_num, var_spec in sorted(strat['variations'].items()):
        result = run_variation(strategy_id, var_num, var_spec)
        if result:
            results.append(result)

    # Sort by profit factor (desc), then net_pnl (desc)
    results.sort(
        key=lambda r: (
            -r['metrics']['profit_factor'],
            -r['metrics']['net_pnl_usd'],
        )
    )

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d')
    out_dir = Path(__file__).resolve().parents[1] / 'data' / 'results'
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{strategy_id}_optimization_{timestamp}.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✓ Results saved to {out_file}")
    print(f"\nTop 3 Variations (by Profit Factor):")
    for i, r in enumerate(results[:3], 1):
        m = r['metrics']
        print(f"  {i}. {r['variation_name']}: PF={m['profit_factor']:.2f}, "
              f"PnL=${m['net_pnl_usd']:.0f}, Trades={m['total_trades']}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Optimize strategy parameters')
    parser.add_argument('--strategy-id', type=str, choices=['001', '002', '003', 'all'],
                        default='all', help='Strategy ID to optimize')
    args = parser.parse_args()

    if args.strategy_id == 'all':
        all_results = {}
        for sid in ['001', '002', '003']:
            all_results[sid] = run_optimization(sid)
        return all_results
    else:
        return run_optimization(args.strategy_id)


if __name__ == '__main__':
    main()
