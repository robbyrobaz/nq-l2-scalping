# Strategy 011: Exhaustion Reversal

## Overview

Identifies reversal setups where volume decreases across successive bars moving in the same direction. When volume dries up on continuation bars, it signals the move is losing momentum and likely to reverse.

## Signal Logic

A reversal signal fires when:

1. **Trend Established**: Last 3-5 bars (lookback window) move in the same direction
   - All closes > opens (uptrend) OR all closes < opens (downtrend)
2. **Volume Declining**: Each successive bar's volume decreases
   - bar[i-1].volume > bar[i-2].volume > bar[i-3].volume, etc.
3. **Exhaustion Confirmation**: Volume of latest bar < 60% of 20-bar average volume

Entry fades the move in opposite direction (goes short on exhausted uptrend, long on exhausted downtrend).

## Rationale

Institutional flows drive volume. When volume dries up on continuation, it indicates weak hands or pause in buying/selling pressure. The reversal tends to snap back quickly as limit orders get taken out.

## Example Trades

- **Exhausted uptrend**: 5 consecutive green bars with declining volume. Last bar volume = 40% of average. Enter SHORT at its close.
- **Exhausted downtrend**: 4 consecutive red bars with volume drying up. Enter LONG at last bar close.

## Parameters

| Parameter          | Default | Description                        |
|--------------------|---------|------------------------------------|
| lookback_bars      | 4       | Window to check for trend          |
| volume_avg_period  | 20      | Rolling volume average period      |
| min_volume_ratio   | 0.6     | Min volume as ratio of average     |
| take_profit_ticks  | 8       | TP distance in ticks               |
| stop_loss_ticks    | 10      | SL distance in ticks               |

### 5 Variations

| Variation   | lookback | vol_ratio | TP  | SL  |
|-------------|----------|-----------|-----|-----|
| Tight       | 3        | 0.7       | 6   | 6   |
| Default     | 4        | 0.6       | 8   | 10  |
| Wide        | 5        | 0.5       | 12  | 12  |
| Aggressive  | 3        | 0.5       | 12  | 8   |
| Scalp       | 4        | 0.7       | 5   | 5   |

## Risk Management

- RTH session only
- One position at a time
- Force close at session end
- Monitor consecutive signals (may indicate chop)
