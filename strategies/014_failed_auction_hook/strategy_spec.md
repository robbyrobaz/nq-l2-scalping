# Strategy 014: Failed Auction Hook

## Overview

Identifies failed breakouts of value area boundaries. When price breaks above VAH or below VAL but fails to hold, it signals a trap reversal where aggressive traders are caught on the wrong side.

## Signal Logic

1. **Build Volume Profile**: Last 50 bars
2. **Calculate VAH/VAL**: Top and bottom 35% of volume distribution
3. **Detect Failed Break**:
   - Price breaks above VAH by N ticks, then closes back inside VA
   - Price breaks below VAL by N ticks, then closes back inside VA
4. **Signal**: Trade opposite the failed break direction

Entry on the bar where price re-enters the value area after a failed break.

## Rationale

When price breaks a significant level (VAH/VAL) but fails to hold, it creates a trap:
- Long breakouts that fail = shorts get caught
- Short breakouts that fail = longs get caught

The reversal is often sharp because trapped traders exit and realize losses. This creates a "hook" reversal pattern.

## Example Trades

- **Failed Long Break**: Price breaks VAH+5 ticks, fails to hold, closes below VAH. SHORT entry at re-entry.
- **Failed Short Break**: Price breaks VAL-5 ticks, fails to hold, closes above VAL. LONG entry at re-entry.

## Parameters

| Parameter              | Default | Description                        |
|------------------------|---------|----------------------------------|
| volume_profile_bars    | 50      | Bars for profile calculation       |
| value_area_pct         | 0.70    | % of volume in value area          |
| breakout_threshold_ticks | 3     | Ticks beyond boundary = breakout   |
| reentry_tolerance_ticks | 2      | Ticks inside VA = reentry signal   |
| take_profit_ticks      | 12      | TP distance in ticks               |
| stop_loss_ticks        | 10      | SL distance in ticks               |

### 5 Variations

| Variation   | bars | va_pct | break_ticks | reentry | TP  | SL  |
|-------------|------|--------|-------------|---------|-----|-----|
| Tight       | 40   | 0.65   | 2           | 1       | 10  | 8   |
| Default     | 50   | 0.70   | 3           | 2       | 12  | 10  |
| Wide        | 60   | 0.75   | 4           | 3       | 14  | 12  |
| Aggressive  | 40   | 0.70   | 2           | 1       | 14  | 8   |
| Scalp       | 50   | 0.65   | 3           | 2       | 8   | 6   |

## Risk Management

- RTH session only
- One position at a time
- Force close at session end
- Watch for double-fakes (hook then another hook)
