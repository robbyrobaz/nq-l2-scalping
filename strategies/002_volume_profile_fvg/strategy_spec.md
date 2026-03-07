# Strategy 002: Volume Profile Fair Value Gap Rejection

**Source:** https://www.youtube.com/watch?v=o-w5Gxss6T0  
**Concept:** True FVG is the lowest-volume node in a price range (not just a 3-candle gap). Price returns to this node and rejects.

## Logic

1. After a significant move (A→B), compute the fixed volume profile of that range
2. Find the Point of Control (POC) and Value Area (70% of volume)
3. The true FVG = lowest volume node within the value area — often a single tick range
4. When price returns to that node, enter in the direction of the original move (fade the return)

## Signal Rules

**After a bullish leg (A→B):**
- Define the range: A = swing low, B = swing high
- Build volume profile at 1-tick resolution from IBKR trade ticks
- Find lowest-volume price level within Value Area Low to POC
- When price retraces back to that level → LONG (expecting rejection up)

**After a bearish leg (A→B):**
- Same logic — lowest volume node within POC to Value Area High
- When price returns → SHORT (rejection down)

## Parameters to Optimize
- `swing_lookback`: bars to define swing points (default: 20)
- `min_leg_size_ticks`: minimum move to qualify as a leg (default: 20 ticks = 5pt)
- `value_area_pct`: volume threshold for value area (default: 0.70)
- `entry_zone_ticks`: tolerance around FVG node (default: 2 ticks)
- `take_profit_ticks`: (default: 12 = 3pt)
- `stop_loss_ticks`: (default: 8 = 2pt)
- `max_retrace_time_bars`: if price hasn't returned in N bars, cancel (default: 30)

## Implementation Notes
- Fixed volume profile: bin all trades within A→B by price level (1-tick bins)
- Value Area: iterate outward from POC until 70% of volume captured
- FVG level = argmin(volume) within value area
- Needs tick-level IBKR data from DuckDB: `SELECT price, SUM(size) FROM trades WHERE ts_ns BETWEEN a_ts AND b_ts GROUP BY price ORDER BY price`
