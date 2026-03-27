# L2 Research Status

## Last Update
2026-03-27 01:06 MST (autonomous research loop — FIXED)

## Status
**✅ FIXED: Previous runs were hanging on DuckDB tick processing**

### Root Cause
- Previous backtest code used `bars_with_delta()` + `trades_with_nbbo()` which:
  1. Loaded ALL 14.8M ticks into memory
  2. Did expensive `merge_asof` between trades and quotes
  3. Hung indefinitely (took >5 minutes, never completed)

### Solution Implemented
Created `run_020_ultra_fast.py` + `research_runner.py`:
- Uses pre-aggregated 1-min CSV bars (12K bars vs 14.8M ticks)
- Skips expensive tick-level delta calculation (not needed for opening range)
- Simplified fill simulation using bar OHLC
- **Result: 0.4s per backtest (was timing out before)**

## Current Results (Mar 27, 2026)

### Strategy 020: Simplest Orderflow Model (IVB Opening Range)
**Best config:** Baseline 30min OR, TP=16, SL=8
- **PF: 1.33** (needs 1.5 for winner)
- Trades: 25 (needs 50)
- WR: 40%
- Net PnL: $800 (14 days)

**Status:** ⚠️ Close, but not a winner yet

**Variations tested:**
1. Baseline 30min: PF 1.33, 25 trades
2. Wide targets (TP=20, SL=10): PF 1.33, 25 trades, $1000 PnL
3. Conservative 45min: PF 1.20, 24 trades
4. Aggressive 15min: PF 1.10, 31 trades
5. Tight targets: PF 1.12, 25 trades

## Data Quality
- **14,880,303 ticks** (Mar 5-27, 2026)
- **12,490 1-min bars** (last 14 days)
- **19 RTH sessions** (full market days)
- Full NBBO quotes + 5-level DOM depth
- 10x more data than last optimization (Mar 18: only 1.3M ticks)

## Next Actions
1. ✅ Test Strategy 014 Failed Auction Hook (was PF 2.50 on old data)
2. ✅ Test Strategy 007 Sweep Fade with London-only filter
3. ✅ Test Strategy 018 Delta Absorption Live Trade
4. ✅ Test Strategy 001 Delta Absorption Breakout
5. Create hybrid strategies if patterns emerge
6. Increase lookback to 21 days (more trades for statistical significance)

## Winner Criteria
- **PF ≥ 1.5** (profitability)
- **Trades ≥ 50** (statistical significance)
- **Drawdown < $3K @ 2 NQ** (Lucid 50K constraint)
- If found: notify NQ agent immediately

## Technical Improvements Made
1. Created `run_020_ultra_fast.py` — CSV-based backtest engine
2. Created `research_runner.py` — multi-strategy param sweep
3. Fixed timezone handling (13:30/14:30 UTC = 9:30 ET)
4. Fixed session start detection logic
5. Simplified fill simulation (bar-based vs tick-based)

**Next run:** Test remaining 4 priority strategies, then expand param grid if no winners
