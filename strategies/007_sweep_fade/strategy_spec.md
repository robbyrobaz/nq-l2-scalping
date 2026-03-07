# Strategy 007: Sweep & Fade

**Concept:** Rapid price movements (> 8 ticks in < 30 seconds) are often exhaustion moves. Fade the sweep by trading the reversal.

## Logic

1. Monitor intra-bar price velocity: ticks moved per unit time
2. When price moves > 8 ticks in < 30 seconds, it's a "sweep" (likely exhaustion)
3. Enter opposite direction to fade the move
4. Target is tight (price often reverts 4-8 ticks after sweeps)
5. Exit on TP/SL or reversion signal

## Signal Rules

**Long Entry (fade a downswing):**
- Price drops > 8 ticks in < 30 seconds
- Enter long on the retracement signal (next bar opens above the sweep low)
- Expect revert to sweep midpoint or higher

**Short Entry (fade an upswing):**
- Price rises > 8 ticks in < 30 seconds
- Enter short on the retracement signal (next bar opens below the sweep high)
- Expect revert lower

## Parameters to Optimize

- `sweep_tick_threshold`: minimum ticks to qualify as sweep (default: 8)
- `sweep_time_seconds`: max time for sweep (default: 30)
- `take_profit_ticks`: tighter target (default: 6)
- `stop_loss_ticks`: (default: 10)
- `retracement_min_ticks`: minimum retracement to signal fade (default: 1)
- `session_filter`: RTH only

## Implementation Notes

- Use 1-min bars but track intra-bar price movement
- Calculate: max_inbar_move = bar_high - bar_low (or open-to-close)
- A "sweep" is when intra-bar range > threshold in time window
- Fade on next bar if retracement appears
