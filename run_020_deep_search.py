#!/usr/bin/env python3
"""Deep parameter search for Strategy 020 (IVB).

Goal: Find PF ≥ 1.5 with 50+ trades configuration.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import itertools
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.run_020_ultra_fast import run_backtest

def deep_search():
    """Test many parameter combinations."""
    print("="*70)
    print("STRATEGY 020: IVB OPENING RANGE — DEEP PARAMETER SEARCH")
    print("="*70)
    print(f"Goal: PF ≥ 1.5, trades ≥ 50")
    print(f"Data: Last 14 days (19 RTH sessions)")
    print()
    
    # Expanded param grid
    or_bars_range = [10, 15, 20, 25, 30, 35, 40, 45, 50, 60]
    tp_ticks_range = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32]
    sl_ticks_range = [4, 5, 6, 7, 8, 9, 10, 12, 14, 16]
    lookback_days = [14, 21]  # Test 14 and 21 days
    
    total_combos = len(or_bars_range) * len(tp_ticks_range) * len(sl_ticks_range) * len(lookback_days)
    print(f"Testing {total_combos} combinations...")
    print()
    
    results = []
    count = 0
    t0 = time.time()
    
    for lookback in lookback_days:
        for or_bars in or_bars_range:
            for tp_ticks in tp_ticks_range:
                for sl_ticks in sl_ticks_range:
                    count += 1
                    
                    # Skip if TP < SL (doesn't make sense for trending breakout)
                    if tp_ticks < sl_ticks:
                        continue
                    
                    params = {
                        "opening_range_bars": or_bars,
                        "take_profit_ticks": tp_ticks,
                        "stop_loss_ticks": sl_ticks,
                        "lookback_days": lookback,
                    }
                    
                    result = run_backtest(params)
                    
                    if result['num_trades'] > 0:
                        results.append({
                            'or_bars': or_bars,
                            'tp_ticks': tp_ticks,
                            'sl_ticks': sl_ticks,
                            'lookback_days': lookback,
                            'pf': result['profit_factor'],
                            'trades': result['num_trades'],
                            'wr': result['win_rate'],
                            'net_pnl': result['net_pnl'],
                            'avg_win': result['avg_win'],
                            'avg_loss': result['avg_loss'],
                        })
                    
                    if count % 100 == 0:
                        elapsed = time.time() - t0
                        rate = count / elapsed if elapsed > 0 else 0
                        eta = (total_combos - count) / rate if rate > 0 else 0
                        print(f"  [{count:4}/{total_combos}] {rate:.1f} tests/s | ETA: {eta:.0f}s | Valid: {len(results)}")
    
    runtime = time.time() - t0
    print(f"\n⏱️  Total runtime: {runtime:.1f}s ({len(results)} valid configs)")
    
    if not results:
        print("\n❌ No valid results")
        return []
    
    # Sort by PF
    results.sort(key=lambda x: x['pf'], reverse=True)
    
    print("\n" + "="*70)
    print("TOP 20 RESULTS (sorted by PF)")
    print("="*70)
    print(f"{'Rank':<5} {'OR':>3} {'TP':>3} {'SL':>3} {'Days':>4} {'PF':>6} {'Trades':>7} {'WR':>6} {'PnL':>10}")
    print("-"*70)
    
    for i, r in enumerate(results[:20], 1):
        status = "🎯" if (r['pf'] >= 1.5 and r['trades'] >= 50) else "⚠️ " if r['pf'] >= 1.5 else ""
        print(f"{i:<5} {r['or_bars']:3} {r['tp_ticks']:3} {r['sl_ticks']:3} {r['lookback_days']:4} "
              f"{r['pf']:6.2f} {r['trades']:7} {r['wr']:6.1%} ${r['net_pnl']:9.2f}  {status}")
    
    # Find winners
    winners = [r for r in results if r['pf'] >= 1.5 and r['trades'] >= 50]
    
    if winners:
        print("\n" + "="*70)
        print(f"🏆 WINNERS FOUND: {len(winners)} configurations")
        print("="*70)
        for w in winners:
            print(f"  OR={w['or_bars']:2} | TP={w['tp_ticks']:2} | SL={w['sl_ticks']:2} | Days={w['lookback_days']:2} | "
                  f"PF={w['pf']:.2f} | Trades={w['trades']} | PnL=${w['net_pnl']:+.2f}")
    else:
        print("\n❌ No winners (PF ≥ 1.5 AND trades ≥ 50)")
        
        # Show "close" candidates
        close = [r for r in results if r['pf'] >= 1.3 and r['trades'] >= 20]
        if close:
            print(f"\n⚠️  CLOSE CANDIDATES ({len(close)} configs with PF ≥ 1.3, trades ≥ 20):")
            for c in close[:10]:
                print(f"  OR={c['or_bars']:2} | TP={c['tp_ticks']:2} | SL={c['sl_ticks']:2} | Days={c['lookback_days']:2} | "
                      f"PF={c['pf']:.2f} | Trades={c['trades']} | PnL=${c['net_pnl']:+.2f}")
    
    # Save results
    output_dir = Path(__file__).resolve().parent / 'data' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M')
    output_file = output_dir / f'020_deep_search_{timestamp}.json'
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': pd.Timestamp.now().isoformat(),
            'total_combos_tested': count,
            'valid_configs': len(results),
            'winners': winners,
            'all_results': results,
        }, f, indent=2)
    
    print(f"\n📁 Results saved: {output_file}")
    
    return winners

if __name__ == "__main__":
    winners = deep_search()
    
    if winners:
        print(f"\n✅ {len(winners)} winner(s) ready for NQ agent review")
    else:
        print(f"\n🔄 No winners this run. May need to expand lookback or adjust criteria.")
