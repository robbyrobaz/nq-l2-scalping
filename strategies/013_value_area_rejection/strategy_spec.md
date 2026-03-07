# Strategy 013: Value Area Rejection

## Overview

Fades moves to value area boundaries (VAH/VAL). The value area represents where 70% of volume traded. Prices touching the top (VAH) or bottom (VAL) of the value area often reject because they reach where the institutional bids and offers are clustered.

## Signal Logic

1. **Build Volume Profile**: Last 50 bars
2. **Calculate VAH/VAL**: Top 35% (VAH) and bottom 35% (VAL) of volume distribution
3. **Signal at Boundary**:
   - SHORT: Price touches/exceeds VAH on up move
   - LONG: Price touches/falls below VAL on down move

Entry is at the bar where price reaches the boundary.

## Rationale

Market makers and institutional traders use value area boundaries as anchor points for orders. When aggressive retail traders push price to these boundaries, they often encounter passive liquidity that reverses the move. This is a fade setup with defined risk at the extreme.

## Example Trades

- **SHORT at VAH**: VAH = 5280.00. Price rallies to 5280.25 in bar. SHORT entry at 5280.25, SL at VAH+5 ticks.
- **LONG at VAL**: VAL = 5272.50. Price falls to 5272.25. LONG entry at 5272.25, SL at VAL-5 ticks.

## Parameters

| Parameter              | Default | Description                        |
|------------------------|---------|----------------------------------|
| volume_profile_bars    | 50      | Bars for profile calculation       |
| value_area_pct         | 0.70    | % of volume in value area          |
| boundary_touch_ticks   | 2       | Ticks beyond boundary = signal     |
| take_profit_ticks      | 10      | TP distance in ticks               |
| stop_loss_ticks        | 8       | SL distance in ticks               |

### 5 Variations

| Variation   | bars | va_pct | boundary | TP  | SL  |
|-------------|------|--------|----------|-----|-----|
| Tight       | 40   | 0.65   | 1        | 8   | 6   |
| Default     | 50   | 0.70   | 2        | 10  | 8   |
| Wide        | 60   | 0.75   | 3        | 12  | 10  |
| Aggressive  | 40   | 0.70   | 1        | 12  | 6   |
| Scalp       | 50   | 0.65   | 2        | 6   | 5   |

## Risk Management

- RTH session only
- One position at a time
- Force close at session end
- Monitor for range days (VAH=VAL means no setup)
