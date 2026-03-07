# Strategy 003: CVD Divergence (Absorption via Volume Spread Analysis)

**Source:** https://www.youtube.com/watch?v=o-w5Gxss6T0  
**Concept:** When Cumulative Volume Delta makes a lower low but price doesn't (or vice versa), passive players are absorbing aggressors. Trade the direction of the passive players.

## Logic

Cumulative Volume Delta (CVD) = running sum of (buy_vol - sell_vol) over a session

**Bearish CVD Divergence → Bullish signal:**
- CVD makes a lower low (sellers dumping more volume than ever)
- BUT price makes equal low or higher low
- Interpretation: passive buyers absorbing all that sell aggression
- Signal: LONG (buyers win, sellers exhausted)

**Bullish CVD Divergence → Bearish signal:**
- CVD makes a higher high (buyers buying aggressively)
- BUT price stays flat or makes lower high
- Interpretation: passive sellers absorbing all buy aggression
- Signal: SHORT

## Signal Rules
1. Compute per-bar CVD (reset at session open each day)
2. Detect divergence: price_swing_direction != cvd_swing_direction over N bars
3. Confirm: divergence persists for `confirmation_bars` consecutive bars
4. Enter on next bar open after confirmation

## Parameters to Optimize
- `divergence_window`: bars to look for swing mismatch (default: 5)
- `min_cvd_move`: minimum CVD swing to qualify (default: 500 contracts)
- `confirmation_bars`: bars divergence must persist (default: 2)
- `take_profit_ticks`: (default: 10 = 2.5pt)
- `stop_loss_ticks`: (default: 8 = 2pt)
- `momentum_filter`: only trade when ADX > 20 (avoid choppy sessions)
- `session_filter`: RTH only

## Implementation Notes
- CVD reset at 08:30 CT each trading day
- Per-bar delta computed from IBKR trade ticks (side=B: buy aggressor, side=S: sell aggressor)
- Divergence detection: compare rolling highs/lows of price vs CVD using scipy.signal.find_peaks
- Complement: when in momentum phase (CVD and price aligned), use divergence within that trend for pullback entries
