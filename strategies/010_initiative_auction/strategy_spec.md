# Strategy 010: Initiative Auction

## Overview

Identifies bars where initiative traders are in control -- delta aligns with price
direction on above-average volume. This is a trend continuation signal: when buyers
(or sellers) are initiating aggressively and volume confirms, price is likely to
continue in that direction.

## Signal Logic

A signal fires when ALL three conditions are met on a single 1-min bar:

1. **High Volume**: Bar volume exceeds `volume_multiplier` x rolling average volume
   (default: 1.5x over 20 bars).
2. **Delta Threshold**: Absolute bar delta exceeds `delta_threshold` (default: 300).
3. **Delta-Price Alignment**:
   - LONG: Delta > +threshold AND close > open (green bar)
   - SHORT: Delta < -threshold AND close < open (red bar)

Entry is at the bar's close price. The trade follows the initiative direction
(continuation, not reversal).

## Rationale

When aggressive volume and delta agree with price direction, it signals initiative
activity rather than responsive (mean-reversion) activity. Initiative auctions tend
to continue because the aggressive side is not yet exhausted.

## Example Trades

- **LONG**: Bar delta = +450, close > open, volume = 180% of 20-bar avg.
  Buyers are initiating. Enter long at close, TP 12 ticks, SL 8 ticks.
- **SHORT**: Bar delta = -380, close < open, volume = 160% of 20-bar avg.
  Sellers are initiating. Enter short at close, TP 12 ticks, SL 8 ticks.

## Parameters

| Parameter          | Default | Description                              |
|--------------------|---------|------------------------------------------|
| delta_threshold    | 300     | Min absolute delta to qualify            |
| volume_avg_period  | 20      | Lookback for rolling volume average      |
| volume_multiplier  | 1.5     | Volume must exceed avg * this multiplier |
| take_profit_ticks  | 12      | TP distance in ticks                     |
| stop_loss_ticks    | 8       | SL distance in ticks                     |

### 5 Variations

| Variation   | delta_thresh | vol_mult | TP  | SL  |
|-------------|-------------|----------|-----|-----|
| Tight       | 250         | 1.8      | 8   | 6   |
| Default     | 300         | 1.5      | 12  | 8   |
| Wide        | 350         | 1.2      | 16  | 10  |
| Aggressive  | 250         | 1.3      | 16  | 6   |
| Scalp       | 200         | 1.8      | 6   | 4   |

## Risk Management

- Maximum 1 position at a time
- RTH session only (9:30-16:00 ET)
- All exits via fixed TP/SL or forced close at session end
- Watch for over-trading in high-volume regimes (Scalp variation)
