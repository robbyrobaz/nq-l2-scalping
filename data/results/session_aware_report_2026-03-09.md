# NQ L2 Session-Aware Backtest Report - 2026-03-09

## Coverage
- Session tagging: ZoneInfo("America/New_York") across 9 sessions
- Session variations run: var_A (All), var_B (RTH), var_C (London+LondonNY), var_D (Overnight)
- Strategies with optimization results: 14/14

## Best Session Variation By Strategy

| Strategy | Name | Best Variation | PF | PnL | Trades |
|---|---|---|---:|---:|---:|
| 001 | Delta Absorption Breakout | var_C: London + LondonNY | 0.33 | -32.0 | 12 |
| 002 | Volume Profile FVG Rejection | var_C: London + LondonNY | 0.54 | -170.0 | 125 |
| 003 | CVD Divergence Absorption | var_A: All sessions | inf | 25.0 | 5 |
| 004 | Bid/Ask Imbalance | var_A: All sessions | 0.0 | 0.0 | 0 |
| 005 | Large Print Momentum | var_B: RTH only | 0.0 | 0.0 | 0 |
| 006 | Aggressive Tape Streak | var_C: London + LondonNY | 260.35 | 345460.5 | 1166 |
| 007 | Sweep & Fade | var_B: RTH only | 0.42 | -1135.0 | 661 |
| 008 | Stacked Book Breakout | var_A: All sessions | 0.0 | 0.0 | 0 |
| 009 | Absorption | var_D: Overnight | 0.18 | -212.0 | 73 |
| 010 | Initiative Auction | var_B: RTH only | 1.5 | 2.0 | 2 |
| 011 | Exhaustion Reversal | var_B: RTH only | inf | 4.0 | 1 |
| 012 | LVN Rebalance | var_A: All sessions | 0.38 | -575.0 | 226 |
| 013 | Value Area Rejection | var_B: RTH only | 2.5 | 12.0 | 6 |
| 014 | Failed Auction Hook | var_B: RTH only | inf | 6.0 | 1 |

## Winners (PF > 2.0)

| Strategy | Variation | PF | PnL | Trades |
|---|---|---:|---:|---:|
| 003 | var_A: All sessions | inf | 25.0 | 5 |
| 003 | var_D: Overnight | inf | 25.0 | 5 |
| 003 | var_C: London + LondonNY | inf | 10.0 | 2 |
| 014 | var_B: RTH only | inf | 6.0 | 1 |
| 011 | var_B: RTH only | inf | 4.0 | 1 |
| 011 | var_D: Overnight | inf | 4.0 | 1 |
| 006 | var_C: London + LondonNY | 260.35 | 345460.5 | 1166 |
| 006 | var_D: Overnight | 81.81 | 401811.5 | 1934 |
| 013 | var_B: RTH only | 2.5 | 12.0 | 6 |

## London/Overnight Beats RTH

| Strategy | RTH PF | Best London/Overnight Variation | Best London/Overnight PF | Delta PF |
|---|---:|---|---:|---:|
| 001 | 0.22 | var_C: London + LondonNY | 0.33 | 0.11 |
| 002 | 0.44 | var_C: London + LondonNY | 0.54 | 0.1 |
| 003 | 0.0 | var_D: Overnight | inf | inf |
| 006 | 0.11 | var_C: London + LondonNY | 260.35 | 260.24 |
| 009 | 0.0 | var_D: Overnight | 0.18 | 0.18 |
| 012 | 0.0 | var_D: Overnight | 0.33 | 0.33 |

## Notes
- Result JSON files now include `session_breakdown` per variation for executed trades.
- Strategy 009 was added to optimizer coverage for this run.
