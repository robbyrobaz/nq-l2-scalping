# NQ L2 Scalping — Order Flow Strategy Library

📊 **[Latest Report (2026-03-09)](data/results/comparison_report_2026-03-09.md)** | **[Baseline (2026-03-06)](data/results/comparison_report.md)**

A video-driven research pipeline that:
1. Ingests trading education videos → extracts strategies
2. Implements each strategy against IBKR tick-level + L2 data
3. Backtests and stores results in a unified comparison schema
4. Ranks strategies by live-tradeable edge

## Data Source
- **Feed**: IBKR live tick stream via `ibkr-nq-feed.service`
- **Trades**: `nq_feed.duckdb` — 3.7M+ trade ticks, 67.9M+ quote ticks
- **1-min bars**: `NQ_ibkr_1min.csv` — 2,531+ bars (growing daily)
- **Session tagger**: NQ v3 `ZoneInfo("America/New_York")` approach — DST-aware, all 9 sessions

## ⚠️ Important Context: Sample Size

All results below are from **RTH-only backtests on limited IBKR history** (feed live since Mar 6).
Low trade counts are expected — one RTH session = ~6.5 hours of data.
A **session-aware backtest across all 9 sessions** (Asia, London, LondonNY, etc.) is running now
to get statistically meaningful sample sizes. Results will supersede these.

---

## Strategy Rankings — 2026-03-09 (RTH backtest, post-DST fix)

> RTH filter corrected for DST: was 14:30–21:15 UTC (EST), now 13:30–20:15 UTC (EDT)

### ✅ Tier 1: Real Edge (PF > 1.5, Trades ≥ 10)
| ID | Strategy | Variation | PF | WR | Trades | PnL | Sharpe |
|----|----------|-----------|----|----|--------|-----|--------|
| 014 | **Failed Auction Hook** | **Aggressive** | **2.50** | **58.8%** | **17** | **+$42** | **7.24** |
| 014 | Failed Auction Hook | Tight | 1.79 | 58.8% | 17 | +$22 | 4.64 |

**014 is the only strategy with both meaningful trade count AND positive edge in today's RTH session.**
The Aggressive variant is the lead candidate for forward testing.

### ⚠️ Tier 2: Insufficient Sample (PF looks good but trades < 10)
| ID | Strategy | Variation | PF | Trades | Note |
|----|----------|-----------|-----|--------|------|
| 003 | CVD Divergence | Momentum | ∞ | 3 | 3 trades — not meaningful |
| 001 | Delta Absorption | Aggressive TP | 2.00 | 4 | Degraded from PF 4.00 (Mar 6) |
| 014 | Failed Auction Hook | Default | 1.40 | 13 | Borderline — below 1.5 threshold |

### ❌ Tier 3: Not Working (RTH)
| ID | Strategy | Best PF | Trades | Note |
|----|----------|---------|--------|------|
| 013 | Value Area Rejection | 0.29 | 71 | Was #1 on Mar 6 (PF 3.60) — completely collapsed |
| 007 | Sweep Fade | 0.48 | 867 | Highest signal count, consistent loser |
| 012 | LVN Rebalance | 0.52 | 47 | Below breakeven across all variants |
| 010 | Initiative Auction | 0.32 | 17 | No edge RTH |
| 006 | Tape Streak | 0.89 | 466 | High frequency, marginal loser |
| 002 | Volume Profile FVG | 0.95 | 82 | Near breakeven, not there yet |

---

## Key Findings — 2026-03-09

### What Changed vs 2026-03-06
| Strategy | Mar 6 PF | Mar 9 PF | Verdict |
|----------|----------|----------|---------|
| 013 Value Area Rejection | 3.60 | 0.29 | ❌ Regime-dependent — was edge, now isn't |
| 001 Delta Absorption | 4.00 | 2.00 | ⚠️ Degraded, still positive but low samples |
| 014 Failed Auction Hook | ∞ (1 trade) | 2.50 (17 trades) | ✅ Scaled up, held edge |

### Critical Insight: RTH-Only Is Not Enough
With only one day of IBKR data, RTH = ~400 bars. Most strategies fire 1–17 times.
**You cannot make deployment decisions on this sample size.**

Strategy 013 (Value Area Rejection) went from #1 on Mar 6 to near-zero on Mar 9. 
That's not the strategy changing — that's two different market days producing different regimes.
Without 100+ trades per variant, every ranking is provisional.

**Session-aware backtest (all 9 sessions)** is running now — will give 3–5x more data
and per-session PF breakdown (London killzone, Asia, overnight, etc.).

### Where to Look Next
- **014 Aggressive** → candidate for forward test (paper trade with 1 MNQ)
- **London Killzone (02:00–05:00 ET)** → sweep fade and bid-ask imbalance strategies are
  built for exactly this session — institutional flow, cleaner sweeps. Session-aware results
  expected to change the picture significantly.
- **007 Sweep Fade** → fires 867 times in one RTH session (overfit to noise?). Parameter
  tightening or London-only filter may fix it.

---

## Strategy Library

**Total Strategies:** 17 | **Active Backtests:** 014 (Aggressive), session-aware run pending

| ID | Strategy | Description | Source | Status |
|----|----------|-------------|--------|--------|
| 001 | Delta Absorption Breakout | Large absorbed volume → direction signal | Video | ⚠️ Degrading |
| 002 | Volume Profile FVG | FVG fill + volume confirmation | Video | ❌ Below edge |
| 003 | CVD Divergence | CVD vs price divergence | Video | ⚠️ Low samples |
| 004 | Bid-Ask Imbalance | Order book skew entry | Video | 🔬 Research |
| 005 | Large Print Momentum | Aggressive large-lot entry | Video | 🔬 Research |
| 006 | Tape Streak | Consecutive same-side prints | Video | ❌ Consistent loser |
| 007 | Sweep Fade | Sweep → reversal | Video | ❌ RTH loser (London?) |
| 008 | Stacked Book Breakout | Layered book breaks | Video | 🔬 Research |
| 009 | (reserved) | — | — | — |
| 010 | Initiative Auction | Auction theory breakout | Video | ❌ No edge |
| 011 | Exhaustion Reversal | Momentum exhaustion | Video | ⚠️ Low samples |
| 012 | LVN Rebalance | Low volume node fill | Video | ❌ Below edge |
| 013 | Value Area Rejection | VAH/VAL fade | Video | ❌ Regime-dependent |
| 014 | **Failed Auction Hook** | Failed breakout reversal | Video | ✅ **LEAD CANDIDATE** |
| 015 | Order Flow Market Structure | Multi-timeframe orderflow | Video | 🔬 Partial build |
| 016 | Orderflow Auction Theory Framework | Full auction cycle | Video | 🔬 Partial build |
| 017 | Simple Order Flow Delta Setups | Basic delta patterns | Video | 🔬 Partial build |

---

## Backtests Log
| Date | Data | Strategies | Winner | Notes |
|------|------|------------|--------|-------|
| 2026-03-06 | IBKR RTH (EST, day 1) | 001–014 | 013 Aggressive (PF 3.60) | EST hours, limited history |
| 2026-03-09 | IBKR RTH (EDT, day 3) | 001–014 | **014 Aggressive (PF 2.50)** | DST fix applied, 1.28M ticks |
| 2026-03-09 | All 9 sessions (pending) | 001–014 | TBD | Session-aware run in progress |

---

## Running a Backtest

```bash
cd nq-l2-scalping

# Refresh DuckDB copy (gets latest IBKR data)
rm -f /tmp/nq_feed_readonly.duckdb

# Full optimization sweep (all strategies, all variants)
# Long-running — use background
nohup python3 pipeline/optimize.py --strategy-id all > /tmp/nq_l2_backtest.log 2>&1 &

# Single strategy
python3 pipeline/optimize.py --strategy-id 014

# Generate summary from existing results
python3 run_all_optimizations.py
```
