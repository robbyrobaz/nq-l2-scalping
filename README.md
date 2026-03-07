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

| ID | Strategy | Source | Status | Trades | WR | PF | Sharpe | Net PnL |
|----|----------|--------|--------|--------|-----|-----|--------|---------|
| 001 | Delta Absorption Breakout | YT: o-w5Gxss6T0 | backtested | 2 | 50.0% | 0.67 | -3.17 | -$2.00 |
| 002 | Volume Profile FVG Rejection | YT: o-w5Gxss6T0 | backtested | 30 | 43.3% | 1.15 | 1.07 | +$10.00 |
| 003 | CVD Divergence Absorption | YT: o-w5Gxss6T0 | backtested | 1 | 100% | inf | 0.00 | +$5.00 |

*Backtest period: Mar 5-6 2026 (2 RTH sessions). MNQ pricing ($0.50/tick). See `data/results/comparison_report.md` for detailed analysis.*

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
