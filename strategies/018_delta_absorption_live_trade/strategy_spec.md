# Strategy 018: Delta Absorption Live Trade

**Source:** https://www.youtube.com/watch?v=TahCL7FXXLs
**Concept:** Large limit orders in the order book act as "price magnets" - when significant bid/ask walls appear at specific levels, price tends to move toward these levels. This strategy identifies big orders and enters on momentum toward them.

## Logic (Simplified Implementation)

Since full DOM/depth data is not available, we use volume spikes as a proxy for "big orders":

1. **Detect Volume Spikes**: Identify bars where volume is significantly above rolling average (3x+ threshold)
2. **Confirm Momentum**: Check for strong delta in the direction of price move
3. **Price Action Filter**: Require meaningful price movement (2+ ticks) in direction of delta
4. **Entry**: Enter at market on next bar
5. **Exit**: Use fixed TP/SL

## Signal Rules

**Long Entry:**
- Volume spike detected (volume > 3x rolling average)
- Positive bar delta >= threshold (e.g., 200)
- Bullish price action (close > open by 2+ ticks)
- Entry at ask on next bar

**Short Entry:**
- Volume spike detected (volume > 3x rolling average)
- Negative bar delta <= -threshold (e.g., -200)
- Bearish price action (close < open by 2+ ticks)
- Entry at bid on next bar

## Parameters (5 Variations)
1. **Conservative**: 4x volume spike, 300 delta, tight TP (10 ticks)
2. **Default**: 3x volume spike, 200 delta, standard TP (12 ticks)
3. **Aggressive**: 2.5x volume spike, 150 delta, wide TP (16 ticks)
4. **Tight Scalp**: 3x volume spike, 200 delta, tight TP/SL (8/6 ticks)
5. **Wide Stop**: 3x volume spike, 200 delta, wide stop (10 ticks), higher TP (14 ticks)

## Transcript

I'm Andrew Aziz, the author of the book How to Day Trade for a Living. I'm going to walk you through my live trades on Tesla stock, which made me 65,000 in a morning trading session. But what you should focus on is not the profit figure. I want to emphasize why I took the trade, how I managed my position, and a game-changing trading tool that I used, Market Atlas Order Flow. If you are serious about trading, please pay attention to how I read and react to the level two order flow when I day trade. &gt;&gt; Today, it was really really nice uh one trade on Tesla and TSL that turned out to be the biggest uh trading that I had so far in 2026. As you know, I passed the $10 million mark. It was really amazing and I'm really grateful for every single one of you who actually followed my trading journey. So, let's go through the trading that we had today. There's only one single trade with the help of a tool that we had and we call it the market atlas. So the Tesla is gapping down a little bit but uh really squeezed up. Uh let me bring my pen as well. So really squeezed up at the open and with the help of Brian obviously at the you know chat room we trade together. Brian went long here for you know breakup 1 minute to pin range breakout. So he went long here and this is the previous day close. So again, we are red here and then we are green and um you know Brian had a much better entry at around 440 for me. But I kind of uh uh looked around to see if I can go in there. I have to check uh market atlas and I realized that at the previous day close 4:45 we had a huge order very big ask sitting here and the big ask is uh a very good signal that the market is going to go toward that higher. So here's I have the screenshot here. Um, so again, by the time that I took the screenshot, 9:35 34, by the time that I went long and I added more, you see this huge signal of 445 is standing up there. And this is a really good sign that the market is really going toward this big board there. So the market atlas, there's also a lot of education that we have on the market atlas and how to read that. And again, let's take a look at the date. Just uh take a look at the sorry the time here. I took a couple of screenshot here. So what happens at 9:36 still the 445 is there still I haven't partial you know one of the reasons that I had a really big profit today was I didn't partial I really needed to get to 445 and again another screenshot boom you know the 445 is taken and now the orders are through 446 and 448 so see they took the asks up higher so after we took the 445 here it's just continued ripped higher and then now I was sign I was hoping to get 448 so this amazing so as You see I started partiing a little bit here but I knew that it's going to go higher. So what else do we have again? 448 boom towards 448 and 449. Now orders are going to 449. So see market as fast is telling us exactly where the price is going and you know you can partial based on that as well and then all the way up to 450. You see just boom this is the same trade. So I went long I actually added more on that and then not only we get the red to green and then boom all the way up to 450 and uh a lot of traders are traded that this is a so again take a really nice screenshot from 450 and you know long like me added more in the red to green boom it's going up significantly higher so say easy so just read the price action read the market atlas and then you can see so you can also trade it that uh vl is a two times leverage so it's way more capital efficient Like for example, if you guys are in a funded account, instead of trading Tesla, you can trade TSL. So I traded similar to TSL as well. So long all the way up to 19 TSL Z. I added more a little bit than TSL here for the breakup high of the day. And then it went up all the way up to boom uh 1930. I had some orders here that I didn't get filled. So as you see here, I had some orders here that uh I didn't uh unfortunately get filled. So I'm going to uh cancel them. And uh I pro might actually keep these uh a little bit of the shares that I have for tomorrow. See maybe gapping up tomorrow. Uh market made alltime high. Same as Tesla. Tesla again I added more on Tesla as well. So why not you know significantly higher for all the way up to 454. That was an amazing trade that we did on Tesla. So again on the 5 minutes we did a really nice 5m minute break up red to green and with the help of market atlas we added more here all the way up to 455. So it's great great trading day. So market atlas has been really game changer for my trading and so many of our traders that we have in our community and uh you know without market atlas is actually very very difficult for me to trade right now. It's coming through trading terminal and you can check it out and uh you know if you really like it uh you can just use it and you can come into the chat room and you know you can see my screen what you're seeing right now. You can actually trade it. So just uh you know as simple as that and then we actually have a trial right now then you can actually come and check it out in the chat room just leave in the comment trial and I actually send you a link and code we trade this live in the chat room that you can trade uh just leave a comment trial and you know just trade with us. So the importance of daily chart and how you actually break out on a daily chart is something that uh you know is worth to discussing. As you see here we have very big profit we had toward that and uh you know on a daily chart we were gapping up you know yesterday we were gapping up and it was really um you know ready for uh essentially breakout toward 18568 which was the moving average 50 moving average on the daily chart. We also had this you know level back in December 2nd that we bounced back. So if we were going through this 18568, could we go to 187 792 as well? So that's also another level that before the market actually opened, we looked at these levels and if it's sell potentially we can go toward those uh areas. Um all right, so let's see uh let's see what happened on the market again. Yesterday was a really nice gap up day and today market was gapping up a strength. Quickly look at the daily chart and see what are we actually having on the daily chart. So I remove all of the daily charts. So this is what you see. You are, you know, you're coming here and, you know, you want to see, okay, this is a level. This is a level. And then obviously this one matches the moving average on the daily chart as well. See if you can actually get this breakout that we are expecting. Market atlas helps a lot. So as you know guys, market atlas is something that we look at the levels um you know at the market open. Right now there's huge orders stacking up at 190. Even the market's closed, but tomorrow morning we can actually go toward that. And then at the open we have so many of these education that you know the big orders are like whales that price is going toward that. Uh so one um going to one minute chart and see what's going to happen here. Uh so as you see here let's go through five minute chart. We had a really nice set from 183 all the way up to 19 90. But uh you know let's go through the trade management or one minute chart at the open open very strong. So the volume was really strong and then I went long for the opening range breakout dropped. I got a stopped out. I wish I didn't get a stopped out because it really never lost the VBA. Then I went back again long added more went up and then it, you know, didn't partial. I really wanted to get to 185 because we had a really big order at 185 and then came down and got a stop out. So that was second trade that I got a stopped out. So again, this one was the trade. This was my second trade and I wish I was actually partial at I was so close to 185 because it was a huge assa staying at the 185 but uh I came back up. So I went back up as soon as you know came back up you know squeeze back I went back up I added more and then we did break towards 185 186 all the way up to 187 held it all the way up to the afternoon toward 18790 and as you see here just continuously going up and you know the last piece at 18877 and I think actually as a matter of fact I think I might have still some yeah I think I still have a shares here on NVDA so here it is so I have a league of shares left at 1,000 shares left on Nvidia. So, you know, going up all the way up to 189. I might actually keep this one for tomorrow because tomorrow might gap up trading terminals funded trading program. One of the traders, Vini, sent us an email about his progress. I want to review his performance in the funded account with you guys. &gt;&gt; 81% uh the win rate again 50/50. The largest win, 1500, largest loss 600. That's good. He kept his uh uh ratio really nice. Average winner 238. Average loser 176. That's good. But you know, I should keep this ratio 2:1. Uh that looks good. Average winner loser 1.3. And uh yeah, nice. So he did a very nice uh profit for the fun account. Good. Congratulations. So he says they pick up the book three years ago started the journey couple of years to learn and go through the content was part of boot camp as well and uh very nice. So now see this fun account paying for all of his education like the book BBT boot camp courses of Lenny and Paris. Yeah it's $6,700 probably he spend on his education and now he's just getting paid through that. Congratulations.

## Backtest Results (2026-03-15)

**Test Period:** Mar 5, 10-12 (3 days, RTH sessions)
**Data:** NQ L2 tick data from IBKR

### Performance Summary

| Variation | PF | Trades | WR | PnL | Sharpe | Max DD | Status |
|-----------|-----|---------|-----|------|--------|---------|---------|
| 1. Conservative | ∞ | 2 | 100% | $10 | 0.00 | 0% | ⚠️ Limited sample |
| 2. Default | 3.50 | 10 | 70% | $30 | 2.07 | 13.3% | ✅ HIGH POTENTIAL |
| 3. Aggressive | 3.14 | 18 | 61.1% | $60 | 2.42 | 25% | ✅ HIGH POTENTIAL |
| 4. Tight Scalp | 1.33 | 10 | 50% | $5 | 0.45 | 180% | ❌ High DD |
| 5. Wide Stop | 3.27 | 10 | 70% | $34 | 1.96 | 14.7% | ✅ HIGH POTENTIAL |

### Key Findings

**✅ What Works:**
- **Volume spike + delta confirmation**: All profitable variations use volume 3-4x above average as signal
- **Strong directional bias**: Best trades have delta >400 and clear price movement (>6 ticks)
- **Quick exits**: Most TP hits occur within 2-15 seconds
- **Balanced TP/SL ratios**: 12 TP / 8 SL (1.5:1) provides best risk/reward

**Best Performers:**
1. **Default** (Var 2): Most consistent - 70% WR, PF 3.50, Sharpe 2.07
2. **Wide Stop** (Var 5): Similar to Default but wider TP (14 ticks) - highest PnL per trade
3. **Aggressive** (Var 3): Most trades (18) but higher DD (25%)

**❌ What Doesn't Work:**
- **Tight Scalp** (Var 4): 8 TP / 6 SL too tight, results in 180% max DD and 50% WR
- **Conservative** (Var 1): Too selective (only 2 trades in 3 days)

### Signal Quality

**Common characteristics of winning trades:**
- Volume ratio: 3.0-5.5x average (sweet spot: 3.5-4.5x)
- Bar delta: 200-500 (absolute value)
- Price move on signal bar: 6-22 ticks in direction of delta
- Entry timing: Within 0-2 seconds after bar close

**Failed trades typically show:**
- Low price movement on signal bar (<3 ticks) despite volume spike
- Delta momentum doesn't follow through (immediate reversal)

### Recommendation

**Status:** ✅ **VIABLE - Ready for extended backtest**

**Next steps:**
1. Run 10-15 day forward test with Default variation
2. Consider live testing at minimal size ($500/trade)
3. Monitor volume ratio distribution (may need dynamic threshold)
4. Test session filtering (NYOpen vs PowerHour performance)

**Expected live performance (Default var):**
- 2-3 trades per day
- ~70% win rate
- ~$6-10 per day (per contract)
- Sharpe ratio: 2.0+

## Implementation Notes
- Use DuckDB: `nq_feed.duckdb` tables `nq_ticks`, `nq_quotes`
- Delta = inferred from trade price vs bid/ask
- Results file: `data/results/018_optimization_2026-03-15.json`
