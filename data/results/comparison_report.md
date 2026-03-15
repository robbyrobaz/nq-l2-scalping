# NQ L2 Scalping - Strategy Performance Comparison
**Date:** 2026-03-14 02:00 AM | **Data:** 961,058 total L2 ticks (Mar 5 - Mar 14)

---

## Executive Summary

⚠️ **CRITICAL: MAJOR PERFORMANCE DEGRADATION DETECTED**

New data accumulated since last run (2026-03-12 02:31): **249,508 ticks** (~26% increase)

**Optimization Status:** Partial completion (3/14 strategies completed before timeout)

| Metric | 2026-03-12 | 2026-03-14 | Change |
|--------|------------|------------|--------|
| **Profitable Configs** | 4/56 (7%) | 0/12 (0%) | -4 |
| **High Potential (PF>2.0)** | 1 | 0 | -1 |
| **Total Net PnL** | -$7,742 | -$3,670 | Worse |
| **Best Config PF** | 6.00 | 0.75 | **-87.5%** |

---

## Top 5 Configurations - Current Run (2026-03-14)

| Rank | Strategy | Variation | PF | PnL | Trades | WR% | Status |
|------|----------|-----------|-----|-----|--------|-----|--------|
| 1 | 003 | All sessions | 0.75 | -$304 | 481 | 37.4% | ❌ UNPROFITABLE |
| 2 | 003 | RTH only | 0.73 | -$57 | 84 | 36.9% | ❌ UNPROFITABLE |
| 3 | 003 | Overnight | 0.70 | -$283 | 370 | 35.9% | ❌ UNPROFITABLE |
| 4 | 003 | London + LondonNY | 0.59 | -$202 | 181 | 32.0% | ❌ UNPROFITABLE |
| 5 | 002 | London + LondonNY | 0.49 | -$400 | 260 | 24.6% | ❌ UNPROFITABLE |

---

## Top 5 Configurations - Previous Run (2026-03-12)

| Rank | Strategy | Variation | PF | PnL | Trades | WR% | Status |
|------|----------|-----------|-----|-----|--------|-----|--------|
| 1 | 008 | Overnight | 6.00 | $20 | 5 | 80.0% | ✓ (Low sample) |
| 2 | 008 | All sessions | 1.88 | $14 | 9 | 55.6% | ✓ |
| 3 | 011 | RTH only | 1.60 | $3 | 3 | 66.7% | ✓ (Low sample) |
| 4 | 008 | RTH only | 1.50 | $4 | 4 | 50.0% | ✓ (Low sample) |
| 5 | 014 | London + LondonNY | 0.98 | -$5 | 111 | 45.0% | · |

---

## Strategy-by-Strategy Analysis

### Strategy 001: Delta Absorption Reversal
**Status:** ❌ NO VIABLE CONFIGS
- All variations: PF ≤ 0.00
- Best: var_C (London + LondonNY): 0 trades, $0 PnL
- **Verdict:** Strategy no longer triggering signals

### Strategy 002: Volume Profile FVG Rejection
**Status:** ❌ UNPROFITABLE
- All variations: PF 0.43-0.49 (losing)
- Best: var_C: PF=0.49, -$400 over 260 trades
- **Verdict:** Massive sample size but consistent losses

### Strategy 003: CVD Divergence
**Status:** ❌ UNPROFITABLE
- All variations: PF 0.59-0.75 (losing)
- Best: var_A: PF=0.75, -$304 over 481 trades
- Win rate collapsed: 32-37% (vs ~50% previously)
- **Verdict:** Edge completely disappeared

---

## Forward Test Candidates

### Configs Meeting Criteria (PF > 2.5, Trades ≥ 20):
**❌ NONE**

No configurations meet the forward test criteria. The highest PF achieved is 0.75 (Strategy 003), which represents a 25% loss rate.

---

## Key Findings

### 🚨 Critical Issues

1. **Complete Strategy Failure:** All tested strategies (001-003) are now unprofitable across all variations
2. **Win Rate Collapse:** CVD Divergence (003) win rates dropped from ~50% to 32-37%
3. **Signal Degradation:** Strategy 001 stopped generating meaningful signals (0-1 trades)
4. **Market Regime Change:** The new data (Mar 12-14) shows fundamentally different characteristics

### 📊 Data Characteristics

- **Total ticks:** 961,058 L2 depth updates
- **New data:** 249,508 ticks (25.9% of total)
- **Date range:** Mar 5 - Mar 14, 2026
- **Completed optimizations:** 3/14 strategies (timeout at ~8 minutes)

### ⚠️ Optimization Incomplete

The optimization process timed out after completing only strategies 001-003. The following strategies were not re-tested on the new data:
- 004: Bid/Ask Imbalance
- 005: Large Print Momentum
- 006: Tape Streak
- 007: Sweep & Fade
- 008: Stacked Book Breakout (was #1 on 2026-03-12 with PF=6.0)
- 009: Absorption
- 010: Initiative Auction
- 011: Exhaustion Reversal
- 012: LVN Rebalance
- 013: Value Area Rejection
- 014: Failed Auction Hook

**Note:** Strategy 008 (Stacked Book) was the top performer on the last run but was not re-tested due to timeout.

---

## Recommendations

### Immediate Actions

1. **HALT LIVE TRADING:** No strategies are currently viable
2. **Re-run Full Optimization:** Complete strategies 004-014 with longer timeout
3. **Data Quality Check:** Verify the new L2 data (Mar 12-14) for anomalies or feed issues
4. **Market Analysis:** Investigate what changed in market microstructure during Mar 12-14

### Research Priorities

1. **Regime Detection:** Build filters to detect when market conditions match historical edge periods
2. **Robustness Testing:** Test strategies across multiple market regimes
3. **Signal Quality:** Review why Strategy 001 stopped generating signals
4. **Win Rate Analysis:** Understand why CVD divergence win rate collapsed

### Next Steps

1. Complete optimization for strategies 004-014 (increase timeout to 30+ minutes)
2. Analyze correlation between L2 data characteristics and strategy performance
3. Consider adding market regime filters before signals
4. Review data feed health for the Mar 12-14 period

---

## Historical Context

| Date | Top PF | Top Config | Profitable Configs | Status |
|------|--------|------------|-------------------|--------|
| 2026-03-06 | 4.00 | 013_Aggressive | 20/65 (30.8%) | ✅ Multiple viable |
| 2026-03-09 | - | - | - | (Partial data) |
| 2026-03-11 | - | - | - | (Partial data) |
| 2026-03-12 | 6.00 | 008_Overnight | 4/56 (7.1%) | ⚠️ Declining |
| 2026-03-14 | 0.75 | 003_All sessions | 0/12 (0%) | ❌ **FAILED** |

**Trend:** Sharp degradation from Mar 6 (30.8% profitable) → Mar 14 (0% profitable)

---

## Conclusion

The NQ L2 scalping strategies have experienced a **complete breakdown** on recent data (Mar 12-14). This represents either:

1. A fundamental market regime change that invalidates these approaches
2. Data quality issues with the L2 feed during this period
3. Overfitting to earlier market conditions (Mar 5-6)

**No strategies are recommended for live trading at this time.**

The next optimization run should complete all 14 strategies with sufficient timeout, and include data quality validation before drawing conclusions.

---

**Last Updated:** 2026-03-14 02:00 AM MST | **Optimizer:** Jarvis (cron job)
**Data Source:** /home/rob/infrastructure/ibkr/data/nq_feed.duckdb
**Optimization Status:** INCOMPLETE (3/14 strategies, timeout)
