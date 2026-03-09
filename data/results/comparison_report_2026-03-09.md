# NQ L2 Backtest Comparison Report - 2026-03-09

## Run Context
- New optimization date: `2026-03-09`
- Baseline optimization date: `2026-03-06`
- Strategies covered: `001-014` (skipping `009`, no backtest)
- Ranking basis: Profit Factor (PF), then Net PnL

## Top 10 Variations (2026-03-09) vs 2026-03-06

| Rank | Strategy | Variation | PF (03-09) | PF (03-06) | ΔPF | PnL (03-09) | PnL (03-06) | ΔPnL | Trades (03-09) | Trades (03-06) | ΔTrades |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 003 | Momentum | inf | 2.00 | n/a | 24 | 8 | +16 | 3 | 4 | -1 |
| 2 | 003 | Strict | inf | 1.50 | n/a | 6 | 4 | +2 | 1 | 4 | -3 |
| 3 | 003 | Default | inf | 1.25 | n/a | 5 | 2 | +3 | 1 | 4 | -3 |
| 4 | 003 | Sensitive | inf | 1.33 | n/a | 4 | 2 | +2 | 1 | 4 | -3 |
| 5 | 014 | Aggressive | 2.50 | inf | n/a | 42 | 7 | +35 | 17 | 1 | +16 |
| 6 | 001 | Aggressive TP | 2.00 | 4.00 | -2.00 | 8 | 24 | -16 | 4 | 6 | -2 |
| 7 | 014 | Tight | 1.79 | inf | n/a | 22 | 5 | +17 | 17 | 1 | +16 |
| 8 | 011 | Default | 1.60 | inf | n/a | 3 | 4 | -1 | 3 | 1 | +2 |
| 9 | 014 | Default | 1.40 | inf | n/a | 12 | 6 | +6 | 13 | 1 | +12 |
| 10 | 001 | Wide Range | 1.25 | 2.50 | -1.25 | 2 | 12 | -10 | 4 | 6 | -2 |

## Significant Changes

### Improved
- `014 Aggressive`: PF inf -> 2.50 (n/a), PnL 7 -> 42 (+35), Trades 1 -> 17 (+16)
- `014 Tight`: PF inf -> 1.79 (n/a), PnL 5 -> 22 (+17), Trades 1 -> 17 (+16)
- `014 Default`: PF inf -> 1.40 (n/a), PnL 6 -> 12 (+6), Trades 1 -> 13 (+12)
### Degraded
- `001 Aggressive TP`: PF 4.00 -> 2.00 (-2.00), PnL 24 -> 8 (-16), Trades 6 -> 4 (-2)
- `001 Wide Range`: PF 2.50 -> 1.25 (-1.25), PnL 12 -> 2 (-10), Trades 6 -> 4 (-2)

## Winners (PF > 2.0 and Trades > 10)

- `014 Aggressive` (Failed Auction Hook): PF=2.50, Trades=17, PnL=42
