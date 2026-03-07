# Strategy 004: Bid/Ask Imbalance

**Concept:** Extreme bid/ask size imbalances signal directional pressure. When buyers outnumber sellers 3:1 at the top of book, price should move toward buyers (long). Conversely, when sellers dominate, price trends toward sellers (short).

## Logic

1. Monitor live bid_size and ask_size on every quote
2. Calculate imbalance ratio: `bid_size / ask_size` (or vice versa)
3. When ratio exceeds threshold for N consecutive bars, initiate trade in direction of imbalance
4. Exit on TP/SL in ticks

## Signal Rules

**Long Entry:**
- Bid size > 3x ask size for N bars (e.g., 2 consecutive bars)
- Current bar bid_size >= imbalance_threshold (e.g., 100+ contracts)
- Enter at ask price + entry_offset

**Short Entry:**
- Ask size > 3x bid size for N bars
- Current bar ask_size >= imbalance_threshold
- Enter at bid price - entry_offset

## Parameters to Optimize

- `imbalance_ratio_threshold`: bid/ask or ask/bid ratio to trigger (default: 3.0)
- `consecutive_bars`: how many bars must show imbalance (default: 2)
- `min_size_contracts`: minimum absolute bid/ask size to consider (default: 100)
- `entry_offset_ticks`: ticks away from market to enter (default: 1)
- `take_profit_ticks`: (default: 10)
- `stop_loss_ticks`: (default: 8)
- `session_filter`: RTH only

## Implementation Notes

- Use `quotes` table from DuckDB: ts_utc, bid_size, ask_size
- Resample to 1-min bars and check imbalance per bar
- Entry is market order at next bar open
- Exit on price levels or max hold time (30 bars)
