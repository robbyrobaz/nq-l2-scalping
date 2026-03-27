"""L2 Research Runner - Test multiple strategies with param variations.

Optimized for 14.8M tick dataset by using 1-min CSV bars instead of DuckDB tick processing.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.run_020_ultra_fast import run_backtest as run_020

def test_strategy_020():
    """Test Strategy 020 with parameter variations."""
    print("\n" + "="*70)
    print("Strategy 020: Simplest Orderflow Model (IVB)")
    print("="*70)
    
    results = []
    
    configs = [
        {"opening_range_bars": 30, "take_profit_ticks": 16, "stop_loss_ticks": 8, "name": "Baseline 30min"},
        {"opening_range_bars": 15, "take_profit_ticks": 12, "stop_loss_ticks": 6, "name": "Aggressive 15min"},
        {"opening_range_bars": 45, "take_profit_ticks": 20, "stop_loss_ticks": 10, "name": "Conservative 45min"},
        {"opening_range_bars": 30, "take_profit_ticks": 20, "stop_loss_ticks": 10, "name": "Wide targets"},
        {"opening_range_bars": 30, "take_profit_ticks": 12, "stop_loss_ticks": 6, "name": "Tight targets"},
    ]
    
    for config in configs:
        print(f"\n  [{results.__len__() + 1}] {config['name']}...")
        params = {k: v for k, v in config.items() if k != 'name'}
        params['lookback_days'] = 14
        
        result = run_020(params)
        result['config'] = config['name']
        results.append(result)
        
        if result['num_trades'] > 0:
            print(f"      Trades: {result['num_trades']:3} | WR: {result['win_rate']:.1%} | PF: {result['profit_factor']:5.2f} | PnL: ${result['net_pnl']:+8.2f}")
        else:
            print(f"      No trades")
    
    return results


def analyze_results(all_results):
    """Analyze and rank all results."""
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    
    winners = []
    
    for strategy_name, results in all_results.items():
        print(f"\n{strategy_name}:")
        
        # Filter to configs with trades
        valid = [r for r in results if r['num_trades'] > 0]
        if not valid:
            print("  ❌ No valid results")
            continue
        
        # Sort by PF
        valid.sort(key=lambda x: x['profit_factor'], reverse=True)
        
        for r in valid[:3]:  # Top 3
            pf = r['profit_factor']
            trades = r['num_trades']
            pnl = r['net_pnl']
            wr = r['win_rate']
            
            status = "🎯 WINNER" if (pf >= 1.5 and trades >= 50) else "⚠️  Close" if pf >= 1.3 else ""
            
            print(f"  {r['config']:30} | PF: {pf:5.2f} | Trades: {trades:3} | WR: {wr:.1%} | PnL: ${pnl:+8.2f} {status}")
            
            if pf >= 1.5 and trades >= 50:
                winners.append({
                    'strategy': strategy_name,
                    'config': r['config'],
                    'pf': pf,
                    'trades': trades,
                    'wr': wr,
                    'pnl': pnl,
                })
    
    if winners:
        print("\n" + "="*70)
        print("🏆 WINNERS FOUND (PF ≥ 1.5, trades ≥ 50)")
        print("="*70)
        for w in winners:
            print(f"  {w['strategy']} / {w['config']}")
            print(f"    PF: {w['pf']:.2f} | Trades: {w['trades']} | WR: {w['wr']:.1%} | PnL: ${w['pnl']:+.2f}")
    else:
        print("\n❌ No winners found yet. Keep searching.")
    
    return winners


def main():
    """Run full research loop."""
    print("="*70)
    print(f"L2 SCALPING RESEARCH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    print(f"Data: Last 14 days (CSV bars)")
    print(f"Winner criteria: PF ≥ 1.5, trades ≥ 50, DD < $3K @ 2 NQ")
    
    all_results = {}
    
    # Test strategies
    all_results['Strategy 020'] = test_strategy_020()
    
    # Analyze
    winners = analyze_results(all_results)
    
    # Save results
    output_dir = Path(__file__).resolve().parents[1] / 'data' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = output_dir / f'research_{timestamp}.json'
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': all_results,
            'winners': winners,
        }, f, indent=2, default=str)
    
    print(f"\n📁 Results saved: {output_file}")
    
    return winners


if __name__ == "__main__":
    import time
    t0 = time.time()
    winners = main()
    print(f"\n⏱️  Total runtime: {time.time() - t0:.1f}s")
    
    if winners:
        print(f"\n✅ {len(winners)} winner(s) ready for NQ agent review")
    else:
        print(f"\n🔄 No winners this run. Continuing autonomous research...")
