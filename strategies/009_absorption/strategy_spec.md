# Strategy 009: Absorption

**Concept:** High delta in one direction but price closes opposite = passive absorption. Trade contra-trend.

## Logic

1. On each bar, measure bar_delta (buy volume - sell volume)
2. If delta is strongly positive (buyers aggressive) but bar closes RED (close < open), passive sellers absorbed the buying pressure
3. If delta is strongly negative (sellers aggressive) but bar closes GREEN (close > open), passive buyers absorbed the selling pressure
4. Enter opposite to the delta direction at bar close

## Signal Rules

**Short Entry:**
- bar_delta > +delta_threshold (e.g., +200 contracts)
- close < open by at least close_move_required_ticks (bar is red)
- Interpretation: Buyers were absorbed by passive sellers; price should fall
- Entry: bar close, direction SHORT

**Long Entry:**
- bar_delta < -delta_threshold (e.g., -200 contracts)
- close > open by at least close_move_required_ticks (bar is green)
- Interpretation: Sellers were absorbed by passive buyers; price should rise
- Entry: bar close, direction LONG

## Example Trades

1. Bar has delta +350 (heavy buying), but closes 1pt below open. Passive sellers absorbed all buying. Enter SHORT at bar close. TP 12 ticks, SL 8 ticks.
2. Bar has delta -280 (heavy selling), but closes 0.5pt above open. Passive buyers absorbed selling. Enter LONG at bar close. TP 12 ticks, SL 8 ticks.

## Parameters to Optimize

| Parameter | Description | Range |
|-----------|-------------|-------|
| `delta_threshold` | Min absolute delta to qualify as absorption | 150-400 |
| `close_move_required_ticks` | Min ticks close must move opposite to delta | 0-4 |
| `take_profit_ticks` | Take profit in ticks | 4-24 |
| `stop_loss_ticks` | Stop loss in ticks | 3-12 |

## 5 Variations

1. **Tight:** delta 200, close 2 ticks, TP 8, SL 4
2. **Default:** delta 250, close 1 tick, TP 12, SL 8
3. **Wide:** delta 150, close 0, TP 20, SL 12
4. **Aggressive:** delta 200, close 1, TP 16, SL 6
5. **Scalp:** delta 300, close 2, TP 6, SL 3

## Edge Cases

- Very low volume bars may have low delta regardless; threshold filters these out
- Doji bars (open == close) are excluded unless close_move_required_ticks = 0
- Multiple signals in consecutive bars: each generates its own trade (no cooldown)
- Session filter: RTH only to avoid thin overnight markets
