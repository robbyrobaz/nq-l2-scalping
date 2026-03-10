# NQ L2 Scalping — 14 Strategies (2026-03-09)

## Dataset
- **Data:** 3.8M IBKR ticks, 2906 1-min bars (5 days: Mar 5–9 2026)
- **DB:** `/home/rob/infrastructure/ibkr/data/nq_feed.duckdb`
- **ts_utc dtype:** `datetime64[us, UTC]` — astype("int64") gives **microseconds**
  - `.value` on pd.Timestamp gives nanoseconds → `// 1000` = microseconds (correct)

## Latest Resweep Results (2026-03-09, 5-day dataset)

### Best Performers
| Strategy | Session | PF | PnL | Trades | Status |
|---|---|---|---|---|---|
| **003 CVD Divergence** | London+LondonNY | **1.11** | +$16 | 68 | Marginal |
| **010 Initiative Auction** | RTH | 1.50 | +$4 | 4 | Too few |
| **013 Value Area Rejection** | London+LondonNY | 1.02 | +$16 | 365 | Marginal |
| **014 Failed Auction Hook** | London+LondonNY | **1.13** | +$21 | 64 | Marginal |

### Disabled / Not Viable
- **006 Tape Streak**: 100K+ trades → OOM in optimize sweep → SKIPPED
- **007 Sweep & Fade**: 100K+ trades → OOM in optimize sweep → SKIPPED
- **002 FVG**: PF 0.45–0.50, all sessions negative → Not viable
- **001 Absorption Reversal**: PF 0.44, 36 trades → Not viable as designed
- **005 Large Print**: 0 signals → Not viable

### Key Finding: London Session Edge
Most strategies with any positive PF show it ONLY in London+LondonNY (02:00–08:30 UTC).
RTH is consistently the worst session for most strategies.

## Strategy Status & Design Notes

### 001 Delta Absorption Reversal (REDESIGNED 2026-03-09)
- **Old design:** range compression + absorption bar + BREAKOUT required → 0 trades
- **New design:** range compression + absorbed delta → enter at market (no breakout check, no proximity check)
- **Why changed:** 1-min NQ never traverses full range in single bar → breakout check never fires
- **Current params:** max_range_pts=25, delta_threshold=50, ab=1, TP=8, SL=6
- **Result:** 36 trades but PF=0.44 → concept generates signals but no edge

### 003 CVD Divergence (FIXED 2026-03-09)
- **Bug fixed:** same divergence re-fired for hundreds of consecutive bars → 859 "signals" from ~100 actual divergences
- **Fix:** pair-based dedup (`last_long_price_pair`, `last_long_cvd_pair` etc.) — each unique price/CVD peak pair fires once
- **Result after fix:** 202 trades (default), 68 trades (London), PF=1.11 London session

### 008 Stacked Book (RELAXED 2026-03-09)
- **Change:** stack_threshold 3.0 → 2.0
- **Uses:** `quotes_1min()` cache (not raw 70M-row quotes) — see strategy_cache.py
- **Result:** 14 trades, PF=0.75

## Critical Bugs Fixed (History)

### 2026-03-09 commit 03e65f2: nanoseconds vs microseconds
- tick_ts built via `astype("int64")` → microseconds (DuckDB returns datetime64[us])
- pd.Timestamp.value → nanoseconds → must divide by 1000 for searchsorted
- ALL strategies: `np.searchsorted(tick_ts, ts.value // 1000, side="left")` is CORRECT

### 2026-03-09: 003 divergence dedup
- Before: 859 "divergences" (same pair re-detected each bar) → 814 trades, PF=0.74
- After: ~200 trades, PF closer to edge

### optimize.py "all" sweep: 006+007 skipped
- 006 (Tape Streak) and 007 (Sweep & Fade) excluded from all-sweep → OOM
- Can still run individually: `python3 pipeline/optimize.py --strategy-id 006`

## File Locations
- **Strategies:** `strategies/00{1..8}_*/backtest.py`
- **Optimizer:** `pipeline/optimize.py` (all 14 integrated, 006+007 excluded from all-sweep)
- **Results:** `data/results/{001..014}_optimization_2026-03-09.json`
- **Cache:** `pipeline/strategy_cache.py` (includes `quotes_1min()` for 008)

## Commands
```bash
# Run all viable strategies (skips 006, 007)
python3 pipeline/optimize.py --strategy-id all

# Run specific strategy
python3 pipeline/optimize.py --strategy-id 003

# Quick backtest with debug
python3 strategies/003_cvd_divergence/backtest.py
```

## Next Actions
1. Investigate 003 London session edge more deeply (68 trades, PF=1.11 — needs 200+ trades to confirm)
2. Try 014 Failed Auction Hook London deeper — 64 trades PF=1.13
3. Collect more data (current 5-day window is too small for statistical significance)
4. 001 concept needs fundamental rethink — delta absorption on 1-min NQ lacks edge

---
**Last updated:** 2026-03-09 (5-day resweep, all signals restored, 006/007 disabled)
