# Strategy 001: Delta Absorption Breakout

**Source:** https://www.youtube.com/watch?v=o-w5Gxss6T0  
**Concept:** Absorption (large delta but price doesn't move) precedes breakout in the opposite direction of the absorbed side

## Logic

1. Identify a price level being "protected" (price bouncing between two levels)
2. Monitor cumulative delta per bar at the level — when delta is high but price doesn't break, that's absorption
3. When absorbed side gives up (price breaks through), take a trade in the breakout direction
4. Absorbers (passive) win; aggressors (active, absorbed) lose

## Signal Rules

**Long Entry:**
- Price in a range (ATR-normalized, say 10-bar range < 1.5x ATR)
- Sellers try to push down: delta < -threshold (e.g., -300 contracts)
- BUT price stays flat or rises — absorption of sellers
- Next bar closes above the defended level → LONG

**Short Entry:**
- Buyers push up: delta > +threshold
- Price stays flat or drops — absorption of buyers
- Next bar closes below defended level → SHORT

## Parameters to Optimize
- `range_window`: bars to define the compressed range (default: 10)
- `delta_threshold`: minimum delta to qualify as "aggression" (default: 300 contracts)
- `absorption_bars`: how many bars must show absorption before signal (default: 2)
- `entry_offset_ticks`: ticks above/below breakout level to enter (default: 1)
- `take_profit_ticks`: (default: 8 = 2pt)
- `stop_loss_ticks`: (default: 12 = 3pt)
- `session_filter`: RTH only (08:30-15:15 CT)

## Implementation Notes
- Delta = sum of (buy volume - sell volume) per bar from IBKR trade ticks
- Buy volume = trades where price >= ask (aggressor buys)
- Sell volume = trades where price <= bid (aggressor sells)
- Use DuckDB: `nq_feed.duckdb` table `trades` (ts_ns, price, size, side)
