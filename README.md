# NQ L2 Scalping — Order Flow Strategy Library

A video-driven research pipeline that:
1. Ingests trading education videos → extracts strategies
2. Implements each strategy against IBKR tick-level + L2 data
3. Backtests and stores results in a unified comparison schema
4. Ranks strategies by live-tradeable edge

## Data Source
- **Trades**: IBKR tick data — `/home/rob/infrastructure/ibkr/data/nq_feed.duckdb` (1.18M+ trade ticks)
- **L2 Quotes**: IBKR quote ticks — bid/ask size up to 10 levels
- **1-min bars**: `/home/rob/infrastructure/ibkr/data/NQ_ibkr_1min.csv`

## Strategy Library

| ID | Strategy | Best Variation | Trades | WR | PF | Sharpe | PnL | Status |
|----|----------|-----------------|--------|-----|--------|---------|---------|---------|
| ✓ 001 | Delta Absorption Breakout | Aggressive TP | 6 | 66.7% | 4.00 | 11.22 | +$24 | 🚀 TRADEABLE |
| ✓ 002 | Volume Profile FVG Rejection | Aggressive | 42 | 38.1% | 1.54 | 3.06 | +$56 | ✓ VIABLE |
| ✓ 003 | CVD Divergence Absorption | Momentum | 4 | 50.0% | 2.00 | 5.29 | +$8 | ✓ VIABLE |
| ✗ 004 | Bid/Ask Imbalance | (all) | 0 | — | 0.00 | 0.00 | $0 | ❌ NO SIGNALS |
| ✗ 005 | Large Print Momentum | (all) | 0 | — | 0.00 | 0.00 | $0 | ❌ NO SIGNALS |
| ✗ 006 | Aggressive Tape Streak | (all) | 375 | 3.5% | 0.00 | -52.24 | -$282,856 | ❌ OVERFITTING |
| ✗ 007 | Sweep & Fade | Aggressive | 652 | 41.1% | 0.56 | -4.63 | -$847 | ❌ UNPROFITABLE |
| ✗ 008 | Stacked Book Breakout | (all) | 0 | — | 0.00 | 0.00 | $0 | ❌ NO SIGNALS |

**Backtest Period:** Mar 5-6 2026 (2 RTH sessions, 376 1-min bars)
**Data:** 2,347,158 IBKR ticks
**PnL Basis:** MNQ $0.50 per tick
**Report:** See `data/results/comparison_report.md` for full analysis

### Top 3 Performers (Live Testing Priority)
1. **001 - Aggressive TP**: PF=4.00, Sharpe=11.22 (6 trades, 66.7% WR)
2. **001 - Wide Range**: PF=2.50, Sharpe=7.48 (6 trades, 66.7% WR)
3. **002 - Aggressive**: PF=1.54, Sharpe=3.06 (42 trades, 38.1% WR)

## Pipeline

```
Video URL → transcript → strategy_spec.md → implementation → backtest → results/YYYY-MM-DD_<id>.json
```

Add a new video: `python3 pipeline/process_video.py --url <youtube_url>`

## Comparison Schema
Each strategy result stored in `data/results/<strategy_id>_<date>.json`:
```json
{
  "strategy_id": "001",
  "version": "1.0",
  "source_video": "https://youtube.com/watch?v=...",
  "backtest_period": {"start": "2026-03-01", "end": "2026-03-06"},
  "metrics": {
    "profit_factor": 0.0,
    "sharpe": 0.0,
    "win_rate": 0.0,
    "avg_winner_ticks": 0,
    "avg_loser_ticks": 0,
    "total_trades": 0,
    "net_pnl_usd": 0.0,
    "max_drawdown_pct": 0.0
  },
  "params": {}
}
```
