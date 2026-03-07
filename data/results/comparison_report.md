# NQ L2 Scalping - Strategy Comparison Report

**Backtest Period:** 2026-03-05 to 2026-03-06 (2 RTH sessions)
**Instrument:** MNQ (Micro NQ, $0.50/tick)
**Data:** 2.3M trade ticks + 43.6M quote ticks from IBKR DuckDB feed
**Side inference:** Trade price vs bid/ask at time of execution

## Results Summary

| Strategy | Trades | WR% | PF | Sharpe | Net PnL | Avg W/L (ticks) |
|----------|--------|-----|-----|--------|---------|-----------------|
| 001 Delta Absorption Breakout | 2 | 50.0% | 0.67 | -3.17 | -$2.00 | 8.0 / 12.0 |
| 002 Volume Profile FVG Rejection | 30 | 43.3% | 1.15 | 1.07 | +$10.00 | 12.0 / 8.0 |
| 003 CVD Divergence Absorption | 1 | 100.0% | inf | 0.00 | +$5.00 | 10.0 / 0 |

## Analysis

### 001 - Delta Absorption Breakout
- Only 2 signals in 2 days of RTH data
- Requires tight compression zones + high delta + non-moving price + breakout -- rare combination
- Negative expectancy on this tiny sample (1W, 1L with asymmetric SL > TP)
- **Verdict:** Insufficient data. Strategy is highly selective; needs weeks of data to evaluate.

### 002 - Volume Profile FVG Rejection
- Most active strategy: 30 trades across 2 sessions
- Positive PF (1.15) with favorable risk:reward (TP=12 ticks, SL=8 ticks)
- Win rate of 43.3% is adequate given the 1.5:1 R:R ratio (breakeven WR = 40%)
- Sharpe of 1.07 (annualized from per-trade) is reasonable
- **Verdict:** Most tradeable edge. Consistent signal generation with positive expectancy.

### 003 - CVD Divergence Absorption
- Only 1 signal (winner) -- statistically meaningless
- CVD divergences are rare in trending sessions; Mar 5-6 was a strong trend day
- Strategy will generate more signals during range-bound/rotational sessions
- **Verdict:** Needs more data, especially rotational/choppy sessions.

## Overall Verdict

**Strategy 002 (Volume Profile FVG Rejection)** shows the most tradeable edge:
- Highest signal frequency (15 trades/session avg)
- Positive profit factor despite moderate win rate
- Exploits a structural market feature (low-volume nodes attract reversion)
- The 1.5:1 R:R means it only needs ~40% WR to be profitable

**Caveats:**
- Only 2 days of data -- all results are preliminary
- No commission/slippage modeling
- Side inference from bid/ask has ~36% unknown trades
- Need 20+ sessions for statistical confidence
