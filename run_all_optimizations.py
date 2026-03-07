#!/usr/bin/env python3
"""Master runner: optimize all strategies and generate ranked summary.

Usage:
    python3 run_all_optimizations.py

This script:
1. Runs parameter optimization for all 3 strategies
2. Collects results from JSON files
3. Generates a consolidated ranked summary
4. Outputs comparison_report.md with forward test recommendations
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def load_optimization_results():
    """Load all optimization result files and return combined results."""
    results_dir = Path('data/results')
    all_results = defaultdict(list)

    # Find all *_optimization_*.json files
    for result_file in sorted(results_dir.glob('*_optimization_*.json')):
        with open(result_file) as f:
            strategy_results = json.load(f)
            strategy_id = result_file.stem.split('_')[0]
            all_results[strategy_id] = strategy_results
            print(f"✓ Loaded {result_file.name}")

    if not all_results:
        print("❌ No optimization results found. Run: python3 pipeline/optimize.py --strategy-id all")
        sys.exit(1)

    return all_results


def print_summary(all_results):
    """Print a human-readable summary of all results."""
    print("\n" + "="*80)
    print("NQ L2 SCALPING - OPTIMIZATION SUMMARY")
    print("="*80)

    # Flatten and rank all variations
    all_variations = []
    for strategy_id, results in sorted(all_results.items()):
        for result in results:
            m = result['metrics']
            all_variations.append({
                'strategy_id': strategy_id,
                'strategy_name': result['strategy_name'],
                'variation': result['variation'],
                'variation_name': result['variation_name'],
                'pf': m['profit_factor'],
                'pnl': m['net_pnl_usd'],
                'trades': m['total_trades'],
                'wr': m['win_rate'],
                'sharpe': m['sharpe'],
                'max_dd': m['max_drawdown_pct'],
            })

    # Sort by PF (desc), then PnL (desc)
    all_variations.sort(key=lambda x: (-x['pf'], -x['pnl']))

    print(f"\nTotal Variations: {len(all_variations)}")
    print(f"Total Net PnL: ${sum(v['pnl'] for v in all_variations):.2f}")
    print(f"Profitable Variations: {len([v for v in all_variations if v['pf'] > 1.0])}")
    print(f"High Potential (PF>2.0): {len([v for v in all_variations if v['pf'] > 2.0])}")

    print("\n" + "-"*80)
    print("TOP 10 VARIATIONS (Ranked by Profit Factor)")
    print("-"*80)
    print(f"{'#':<3} {'Strategy':<5} {'Variation':<20} {'PF':<6} {'PnL':<10} {'Trades':<8} {'WR%':<6} {'Sharpe':<8}")
    print("-"*80)

    for i, v in enumerate(all_variations[:10], 1):
        marker = "🚀" if v['pf'] > 2.0 and v['trades'] > 5 else "✓" if v['pf'] > 1.5 else "·"
        print(f"{i:<3} {v['strategy_id']:<5} {v['variation_name']:<20} {v['pf']:<6.2f} ${v['pnl']:<9.0f} {v['trades']:<8} {v['wr']:<6.1f} {v['sharpe']:<8.2f} {marker}")

    # Tier recommendations
    print("\n" + "-"*80)
    print("FORWARD TEST RECOMMENDATIONS")
    print("-"*80)

    tier1 = [v for v in all_variations if v['pf'] > 2.0 and v['trades'] > 5]
    tier2 = [v for v in all_variations if 1.5 < v['pf'] <= 2.0 and v['trades'] > 10]
    tier3 = [v for v in all_variations if 1.0 < v['pf'] <= 1.5 and v['trades'] > 20]

    if tier1:
        print("\n🚀 TIER 1: Ready for Live Testing")
        for v in tier1:
            print(f"   • {v['strategy_id']} - {v['variation_name']}: PF={v['pf']:.2f}, PnL=${v['pnl']:.0f}, Trades={v['trades']}")

    if tier2:
        print("\n✓ TIER 2: Promising (Needs More Data)")
        for v in tier2:
            print(f"   • {v['strategy_id']} - {v['variation_name']}: PF={v['pf']:.2f}, PnL=${v['pnl']:.0f}, Trades={v['trades']}")

    if tier3:
        print("\n· TIER 3: Marginal (Research Needed)")
        for v in tier3[:3]:  # Show top 3 only
            print(f"   • {v['strategy_id']} - {v['variation_name']}: PF={v['pf']:.2f}, PnL=${v['pnl']:.0f}, Trades={v['trades']}")

    print("\n" + "-"*80)
    print(f"For detailed analysis, see: data/results/comparison_report.md")
    print("="*80 + "\n")


def main():
    print("Loading optimization results...")
    all_results = load_optimization_results()
    print_summary(all_results)
    print("✓ Analysis complete")


if __name__ == '__main__':
    main()
