# Strategy 012: LVN Rebalance

## Overview

Identifies low-volume nodes (LVN) in a session's value area and trades price returns to these nodes from trend positions. Low-volume regions attract price because they represent gaps in the auction process where buyers and sellers need to agree.

## Signal Logic

1. **Build Volume Profile**: Last 50 bars worth of volume data
2. **Find Low-Volume Nodes**: Identify price levels where volume < 30% of POC (point of control) volume
3. **Trend Detection**: Price breaks above/below the value area (VAH/VAL)
4. **Signal**: When price is trending away from value area (above VAH or below VAL) and an LVN exists nearby, enter in trend direction expecting mean reversion to LVN

Entry prices are at current bar close when conditions align.

## Rationale

Low-volume areas are "unfilled" gaps in the market structure. When price moves away from these areas, it tends to return to fill them (rebalance). This is especially true for short-term intraday moves.

## Example Trades

- **LONG**: Price rallies above VAH. An LVN at -8 ticks from VAH identified. Buy on pullback touching that LVN level.
- **SHORT**: Price falls below VAL. An LVN at +10 ticks from VAL identified. Sell on bounce toward that level.

## Parameters

| Parameter              | Default | Description                        |
|------------------------|---------|-----------------------------------|
| volume_profile_bars    | 50      | Bars for profile calculation       |
| lvn_threshold_ratio    | 0.30    | Volume threshold for LVN (<30% POC)|
| value_area_pct         | 0.70    | % of volume in value area (70%)    |
| take_profit_ticks      | 10      | TP distance in ticks               |
| stop_loss_ticks        | 12      | SL distance in ticks               |

### 5 Variations

| Variation   | bars | lvn_ratio | TP  | SL  |
|-------------|------|-----------|-----|-----|
| Tight       | 40   | 0.35      | 8   | 8   |
| Default     | 50   | 0.30      | 10  | 12  |
| Wide        | 60   | 0.25      | 14  | 14  |
| Aggressive  | 40   | 0.25      | 12  | 10  |
| Scalp       | 50   | 0.35      | 6   | 6   |

## Risk Management

- RTH session only
- One position at a time
- Force close at session end
- Monitor LVN proximity to entry (avoid trades far from LVN target)
