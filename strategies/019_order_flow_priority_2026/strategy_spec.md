# Strategy 019: Order Flow Priority 2026

**Source:** https://www.youtube.com/watch?v=hq5FKQAnvpY (Bear Bull Traders - Market Atlas)
**Concept:** Opening range breakout confirmation with DOM liquidity pool targeting

**Core Insight:**
- "Price goes toward liquidity pools" - large DOM orders act as price magnets
- Combine chart patterns (ORB, ABC, bull flag) with depth-of-market confirmation
- Target the liquidity level itself as take-profit

## Logic

1. **Define Opening Range**: First N bars of each RTH session (default 5 bars = 5 min)
2. **Detect Breakout**:
   - Long: close > OR high
   - Short: close < OR low
3. **Check DOM for Liquidity Pool**:
   - Query L2 order book at breakout bar timestamp
   - Find large orders (≥ 3x average book size) in breakout direction
   - Verify pool is within max distance (default 40 ticks = 10 pts)
4. **Entry**: Market order on next bar if liquidity pool confirmed
5. **Exit**: TP/SL (targeting liquidity pool level)

## Signal Rules

**Long Entry:**
- Close breaks above opening range high
- Large ask liquidity detected above current price (3x+ avg book size)
- Liquidity pool within 40 ticks (adjustable)
- Enter at ask on next bar

**Short Entry:**
- Close breaks below opening range low
- Large bid liquidity detected below current price (3x+ avg book size)
- Liquidity pool within 40 ticks (adjustable)
- Enter at bid on next bar

**Exit:**
- Take profit: 16 ticks (default)
- Stop loss: 8 ticks (default)

## Parameters to Optimize
- `or_bars`: Opening range bars (3, 5, 10)
- `liquidity_threshold_mult`: Threshold for "large" pool (2.0-4.0x avg book size)
- `max_pool_distance_ticks`: Max distance to liquidity pool (25-60 ticks)
- `min_breakout_ticks`: Min breakout size to consider (2-6 ticks)
- `take_profit_ticks`: (8, 12, 16, 20)
- `stop_loss_ticks`: (4, 6, 8, 10)
- `session_filter`: RTH only

## 5 Parameter Variations

1. **Tight Range**: 3-bar OR, 2.5x pool, 30 tick max, 12/6 TP/SL
2. **Default**: 5-bar OR, 3.0x pool, 40 tick max, 16/8 TP/SL
3. **Wide Range**: 10-bar OR, 3.5x pool, 60 tick max, 20/10 TP/SL
4. **Aggressive Pool**: 5-bar OR, 2.0x pool (easier to trigger), 50 tick max, 20/8 TP/SL
5. **Scalp**: 3-bar OR, 4.0x pool (very large only), 25 tick max, 8/4 TP/SL

## Results

**STATUS: NOT RUN - Database I/O Blocker**

Backtest implementation is complete and ready to run, but cannot execute due to active data collection process locking the database. See implementation status below for details.

---

## Implementation Status (2026-03-15)

### ✅ Code Complete - Awaiting Database Optimization

**Implementation:**
- ✅ `backtest.py`: Fully implemented (234 lines)
- ✅ DOM liquidity pool detection (3x+ average book size threshold)
- ✅ Opening range breakout confirmation
- ✅ 5 parameter variations in `pipeline/optimize.py` (lines 1045-1110)
- ✅ Integrated with optimization framework

**Data Available:**
- DOM depth: **972,707** snapshots (5-level book, Mar 5-15 2026)
- Database: `/home/rob/infrastructure/ibkr/data/nq_feed.duckdb` (737MB)

**Backtest Blocked:**
- ❌ Database I/O extremely slow (concurrent data collection process)
- ❌ `bars_with_delta()` hangs on initial load (5+ minutes, no output)
- ❌ Each variation requires full data reload

**Next Steps to Run:**
1. **Option A:** Stop data collector (`kill <PID>`), run backtest, restart collector
2. **Option B:** Wait for data collection cycle to complete (check process status)
3. **Option C:** Export data to read-only snapshot:
   ```bash
   cp /home/rob/infrastructure/ibkr/data/nq_feed.duckdb /tmp/nq_readonly.duckdb
   # Modify DB_SOURCE in pipeline/data_loader.py temporarily
   python3 pipeline/optimize.py --strategy-id 019
   ```
4. **Option D:** Optimize database with indexes on `ts_utc` columns

**Technical Notes:**
- First strategy to require `nq_depth` table (DOM snapshots)
- Tests Market Atlas "liquidity magnet" hypothesis
- Fallback mode: can run as pure ORB without DOM (degraded performance expected)

---

## Transcript

Hey guys, in this video I want to talk about order flow and understanding the depth of market by using market atlas. If you understand the depth of market and the order flow, you have an edge. Over 99% of the traders that they try to benefit from the volatility of the market in the first two hours. Let's watch this recap and see how we're using market atlabs at trading terminal to find the direction of the stocks especially at the open of US stock market open. Today was a really great trading day just based on the market atlas. We did a media and Tesla TSL and uh that turned out to be a very profitable day for me. I covered the shorts that I had on Microsoft at the break even though those shorts were actually have given me a significant amount of profit if I were holding on that. All right guys, crazy day for the market but we did have really good uh uh trading right now. What I'm seeing right now is Nvidia earning is coming up and the best way of doing Nvidia earning is actually by using uh trading terminal uh breaking news. So as you're saying here the order book on Nvidia even though the market is closed the half an hour has been closed. It's bullish. So you have this 202 203 orders. There you go. So went through 202 went through 203 and uh yeah it looks like uh very strong in earning. Again, I didn't really watch to that what's happening, but uh it's very nice to see the price action. This is a really crazy volume and impacts the whole market. Like SPY is going up, Q's obviously is going up. These are all the same uh um so the same and uh you know AMD did get impacted, but uh it's really nice that how Nvidia is uh moving up and again the Atlas is really bullish uh the way that it's going up. So what we're going to do here is we're going to review the trades that we did today. Today was a really uh great day for me. It was one of the biggest day that I had and uh you know look at this big ask at you know two or three look at the or you know order. It's actually really nice to record this uh post market as well. So the market is the depth of market is the liquidity of the market but with a time stamp and you see the big levels forming and the way that we trade this one is usually we you know find the bullish patterns and then like ABC pattern or bull flag or opening range breakout and then we trade it toward the liquidity pools. So we want to uh go toward right now 204 on NVDA. So as you see here when you're actually zooming out now 205 is a huge order sitting up there. So if this continues go if this was at the open if this market was open I would have definitely taken this trade um you know toward the 205 but right now in the post market premarket so you can't really make market orders that easily. So you know I stay away from it but you know Nvidia and Nvidia is really great. So live uh earning action of uh NVDAS right now is happening. So let's go through uh the trades that we did today. So Tesla at the open again what I'm looking at is really simple is the most important indicator that you must have in your chart is uh the market atlas which shows you the depth of market. So as you see here Tesla at the open so really didn't do anything and suddenly a massive move a massive move from $412 to above 420 which is Elon Musk's favorite number. Uh so what happened here? How do we how do we catch to capitalize from this $412 all the way up to 415 420. So one thing that you're using is the chart pattern. So one thing that you want to use is look at the you know candlestick. So obviously this is a very strong one minute. This becomes one minute opening range breakout if you want to take it to the upside. But what would be the confirmation that you can use? The confirmation that you can use is actually uh the market atlas. So if you are having a market atlas, so what you can do is you can look at the level two and if there are big orders at around 420 like in this case again the market is closed but if the orders are sitting up they're very similar to that you can actually take the trade to the upside. So the higher the liquidity up toward the levels very significantly which in this case they are you know it means that the price is going to go toward that and that's exactly what we did it through TSLL. So Tesla you know get popped up really strong open we looked like the market assass and we saw that there's very strong liquidity still up here at 420. So I took this one minute open range break up I added on the way up through TSL 1570 all the way up we sold it above $16. We did add one more time here because we had this really amazing uh orders sitting up there and uh you know the last time I added here I got to stop it then came back. What happened later after that was uh let me see if you go to the to five minute. Yeah I did it never really came back to the high today but I still that was an amazing scalp that uh uh we could. So again two more important things that we had chart pattern you know like ABCD pattern opening range breakout ABCD pattern and very compared to the volume weighted average price and another thing that we looked at is the market atlas with the depth of market or liquidity same trade on Nvidia so Nvidia again we knew it was going to be earning tonight it's going to be some volatility um it tried to came up above the we app came back up again and we had really clear levels up toward 196 six then I went long and as you see there's a huge profit that we took on that and I actually have some recording and some screenshots of that as well. So if I go to the five minute so what right now what happens? So on the five minute closed red came back up I try to you know take open five minute range breakout or bullish engulfing this is strategy that we teach I got stopped out came back up again and then I decided to go back long again and then we get this massive move and I did add one time in there and I got stopped out. So [snorts] uh but you know on a 5 minute is a really massive move. But how did we do that is uh with the help of market aslas and market atlas is really showing as I showed you in the post market right now when you have this clear orders like if this was the open and I have this you know opening range strength strong opening range if I have this one and I have the 205 I would have definitely taken the trade with the hope to get to 205. So you know the price action which is a candlestick and VWAP and moving averages and market access this confirmation of these two together can be a very strong powerful. So this is the time that I took that trade again. Look at the time stamp 9511. So we went long here because we thought that it's going to squeeze up and we had this big order at 195 and uh it did drop. I got a stopped out. Okay, that's one risk. And as soon as it came back up I went long. I added more. The high of the day was 195 and obviously the market assessment was uh ready for us and uh um you know look at the time stamp that I'm going to the next um slide. This is the 47. I'm going to go to slide number 48. See boom, we took the 195 and this one continued going up. Uh again another thing that I wanted to show you here is that the at 951 here is that you see all of these orders here. This is all the same orders that are stacking here on NASDAQ. So the NASDAQ total view is the same. So all these orders are there and they're getting filled. So again 9511 and you just looked at uh just look at this you know 951 in 40 seconds later 50 seconds later boom not only just went through and also I started partially right for the fills and now they're taking the orders up toward 19550. This is the most important indicator that you should have for scalping and day trading. And what we did is uh uh partnership with NASDAQ. We built this one. And you know, let's take another screenshot here. And then yeah, I see as the order is going to go to 196. Look at the time frame. 95355. So as you see here is uh uh really uh continued orders continue going higher and uh you know you can continue partially or you can add in there. You know I potentially should have added in there but you know again you know on the pullback I could add it and then the order 96 here. You can zoom out and then boom, it goes up. And then the last piece that here, yeah, got filled at 196. So the most important indicator and most important tool that you guys should have for day trading is market atlas. Um, and market atlas by itself doesn't tell you what to do and how to trade. Uh, you need to put uh in the perspective of the price action and candlesticks and based on that you make a decision. I hope this been uh useful. you guys uh have a really good uh trading day and if you have any question just ask in the comments and I'm answering

## Implementation Notes
- Use DuckDB: `nq_feed.duckdb` tables `nq_ticks`, `nq_quotes`
- Delta = inferred from trade price vs bid/ask
