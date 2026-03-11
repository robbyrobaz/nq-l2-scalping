# NQ L2 Scalping — Daily Optimization (2026-03-11)

## Current Dataset
- **Total ticks in DB:** 5,074,830 (Mar 5–11)
- **New data since Mar 9:** 1,241,178 ticks (Mar 10–11)
- **New data breakdown:**
  - Mar 10: 1,200,528 ticks
  - Mar 11 (00:00–02:00 UTC / 17:00–19:00 MST Mar 10): 40,650 ticks
- **Data window:** 7 trading days
- **Latest results:** 2026-03-11 02:25 UTC (12 strategies optimized)

## Mar 11 Optimization Results

### Top Performers
| Rank | Strategy | Variation | PF | PnL | Trades | Status |
|------|----------|-----------|-----|-----|--------|--------|
| 1 | **008 Stacked Book** | var_D | 4.50 | +$14 | 4 | Too few trades |
| 2 | **008 Stacked Book** | var_A | 3.00 | +$16 | 6 | Too few trades |
| 3 | **001 Delta Absorption** | var_A | 2.67 | +$2 | 3 | Too few trades |
| 4-10 | Various | - | 0.50–1.50 | -$300 to +$8 | 2–502 | Unprofitable or marginal |

### Key Findings
- **NO candidates for forward test** — no strategy meets PF > 2.5 with 20+ trades
- **Strategy 013 (Value Area Rejection) collapsed:** Was PF > 3.0 on Mar 5–6 data, now PF = 1.01 with 502 trades
  - Indicates strategy was curve-fitted to early data window
  - Adding 6 more days of data revealed the edge doesn't hold
- **New edge in Strategy 008:** Emerged with new data (PF=3.0 from PF=0.75)
  - But only 6 trades — insufficient sample for production deployment
- **Overall degradation:** Only 6 profitable variations (of 48), only 3 with PF > 2.0
  - Mar 9 had better results — data dependency is HIGH

### Disabled Strategies (per MEMORY)
- 006 (Tape Streak): OOM in backtest → excluded from sweeps
- 007 (Sweep & Fade): OOM in backtest → excluded from sweeps

## Strategy Status

### 001 - Delta Absorption Reversal
- **Latest:** var_A PF=2.67 (3 trades, all sessions)
- **Prior (Mar 9):** PF=1.33
- **Change:** +101% improvement (but still too few trades)
- **Notes:** Concept is generating signals but inconsistent profitability

### 008 - Stacked Book
- **Latest:** var_A PF=3.00, var_D PF=4.50 (6 and 4 trades respectively)
- **Prior (Mar 9):** PF=0.75 (14 trades)
- **Change:** +300% improvement but signal frequency dropped
- **Notes:** Appears to be catching rare high-conviction setups with new data

### 013 - Value Area Rejection ⚠️ **DEGRADED**
- **Latest:** var_C PF=1.01 (502 trades, London+LondonNY)
- **Prior (Mar 9):** PF=3.12 default, 3.60 wide
- **Change:** -68% degradation (went from gold standard to break-even)
- **Root cause:** 6-day dataset (Mar 5–6) was too short — overfitted to early session patterns
- **Implication:** Original results were NOT reproducible on expanded dataset

### 003, 009, 010, 012, 014
- All show negative or break-even PF in Mar 11 sweep
- None generate sufficient trades for statistical validity

## Key Learnings

1. **Overfitting Risk:** Original 2-day (Mar 5–6) optimization results were statistically unreliable
   - 013 showed 4.0 PF on 8 trades → expanded to 7 days → 1.01 PF on 502 trades
   - This is classic case of small-sample luck masquerading as edge

2. **Data Dependency:** NQ micro-structure signals are market-regime dependent
   - Some patterns only work in certain sessions or volatility regimes
   - Expanding dataset reveals which edges are real vs. lucky

3. **Strategy 008 Emerging Edge:** New data revealed Stacked Book can work (PF=3.0+)
   - But signal frequency is EXTREMELY low (6 signals in 7 days)
   - Need 50+ trades before considering live deployment

4. **Strategy 013 Still Worth Research:** Despite PF degradation, 502 trades at PF=1.01 on subset (London session) suggests pattern exists but needs tuning
   - Current VAH/VAL detection may be too loose
   - Consider tighter bounds or confirmation filters

## Next Actions

1. **Collect more data:** Current 7-day window still too small for statistical significance
   - Target: 4–8 weeks of data (1000+ trades per strategy)
   - Only then can we reliably identify real edges vs. noise

2. **Investigate 008 signal generation:** Why did Stacked Book trigger 14 times on Mar 9 but only 4–6 times on expanded dataset?
   - Check if stack detection params shifted
   - Verify quotes_1min() cache is working correctly

3. **Revisit 013 with tighter filters:** Don't abandon Value Area Rejection yet
   - Current results show 502 trades with break-even — might be salvageable with better entry/exit tuning

4. **Implement rolling validation:** Test each strategy on expanding windows (1w, 2w, 4w) to identify when edge starts/stops working
   - Will reveal which strategies are truly robust

## File Locations
- **Optimization results:** `data/results/*_2026-03-11.json`
- **Comparison report:** `data/results/comparison_report.md`
- **Strategies:** `strategies/00{1..14}_*/backtest.py`

---
**Last updated:** 2026-03-11 02:25 UTC (full 12-strategy sweep complete)
