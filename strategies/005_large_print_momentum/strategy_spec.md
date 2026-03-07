# Strategy 005: Large Print Momentum

**Concept:** Unusually large trades (block prints > 2 std devs above average size) represent informed flow. Follow large buy prints with longs; follow large sell prints with shorts.

## Logic

1. Calculate mean and std dev of trade sizes over a lookback window (e.g., 50 bars)
2. Identify "large prints": trades where `size > mean + 2*std_dev`
3. When a large buy occurs, trend momentum is upward; when large sell occurs, trend is downward
4. Enter in the direction of the large print and exit on TP/SL

## Signal Rules

**Long Entry:**
- Trade size > (avg_size + 2 * std_dev) AND price >= ask (aggressor buy)
- Enter at market at next bar close
- Max 1 signal per lookback window (avoid clustering)

**Short Entry:**
- Trade size > (avg_size + 2 * std_dev) AND price <= bid (aggressor sell)
- Enter at market at next bar close
- Max 1 signal per lookback window

## Parameters to Optimize

- `lookback_bars`: window to compute size stats (default: 50)
- `std_dev_threshold`: multiplier (default: 2.0, meaning mean + 2*stddev)
- `min_trade_size`: absolute size floor (default: 1000 contracts)
- `signal_cooldown_bars`: bars to wait before next signal (default: 5)
- `take_profit_ticks`: (default: 12)
- `stop_loss_ticks`: (default: 8)
- `session_filter`: RTH only

## Implementation Notes

- Use `trades` table: ts_utc, price, size, side
- Resample to 1-min bars and compute rolling stats
- For each bar, check if any trade was a "large print"
- Track when last signal occurred to avoid clustering
