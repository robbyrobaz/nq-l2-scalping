# Strategy 008: Stacked Book Breakout

**Concept:** When bid (or ask) liquidity at a price level is > 3x the average, and price breaks through that level, it's a real breakout. Buyers (or sellers) were willing to absorb all that depth to push through.

## Logic

1. Monitor bid/ask depth at each price level (from level 2 data)
2. Identify "stacked" levels: bid_size at level > 3x average OR ask_size > 3x average
3. When price breaks above a heavily stacked ask level → LONG (seller got overwhelmed)
4. When price breaks below a heavily stacked bid level → SHORT (buyer got overwhelmed)
5. Exit on TP/SL in ticks

## Signal Rules

**Long Entry:**
- Price has been resting near a stacked ask level (ask_size > 3x avg)
- Price breaks above that level on strong volume
- Enter at breakout level + entry_offset

**Short Entry:**
- Price has been resting near a stacked bid level (bid_size > 3x avg)
- Price breaks below that level on strong volume
- Enter at breakout level - entry_offset

## Parameters to Optimize

- `stack_threshold`: multiplier for what counts as "stacked" (default: 3.0)
- `stack_lookback_bars`: bars to compute average bid/ask size (default: 10)
- `breakout_min_ticks`: minimum distance from stacked level to signal (default: 1)
- `entry_offset_ticks`: entry relative to breakout level (default: 1)
- `take_profit_ticks`: (default: 12)
- `stop_loss_ticks`: (default: 8)
- `session_filter`: RTH only

## Implementation Notes

- Use `quotes` table: ts_utc, bid_size, ask_size
- Resample to 1-min bars
- For each bar, check if bid/ask size is "stacked" relative to rolling average
- Track which level is stacked and wait for breakout
