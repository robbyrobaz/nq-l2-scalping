# Strategy 006: Aggressive Tape Streak

**Concept:** When N consecutive trades are all same side (all aggressive buys or all aggressive sells), momentum has established. Continue the trend.

## Logic

1. For each bar, count consecutive same-side trades within that bar (or lookback)
2. When count reaches threshold (e.g., 5+ consecutive buys), enter long
3. When count reaches threshold for sells, enter short
4. Exit on TP/SL in ticks

## Signal Rules

**Long Entry:**
- At least 5 consecutive aggressive buy trades (trades >= ask)
- Current bar shows buying pressure
- Enter at market at next bar

**Short Entry:**
- At least 5 consecutive aggressive sell trades (trades <= bid)
- Current bar shows selling pressure
- Enter at market at next bar

## Parameters to Optimize

- `min_consecutive_trades`: minimum streak length (default: 5)
- `lookback_bars`: how far back to check for streaks (default: 3 bars)
- `min_total_volume`: minimum volume in streak (default: 0, no filter)
- `take_profit_ticks`: (default: 10)
- `stop_loss_ticks`: (default: 8)
- `session_filter`: RTH only

## Implementation Notes

- Use `trades` table: ts_utc, price, size, side (inferred from bid/ask)
- Resample to 1-min bars and check consecutive trade sides
- Reset streak counter on opposite-side trade
- Track the streak bar index when signal forms
