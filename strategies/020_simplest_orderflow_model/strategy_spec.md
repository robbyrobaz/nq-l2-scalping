# Strategy 020: Simplest Orderflow Model

**Source:** https://www.youtube.com/watch?v=cUTsoU-15Tc (Fabervaale)
**Concept:** IVB (Invalid/Initial Balance Breakout) - Opening range breakout with orderflow confirmation

## Core Philosophy

"Who won the battle of the most important time of the day" — Fabervaale

The first 15-30 minutes of the RTH session (9:30-10:00 ET) establishes the battlefield. The first side to break out defines the direction for the session. This is a statistical edge published by Toby Crabel in the 1990s with proven consistency.

## Logic

1. **Define IVB (Opening Range)**: Track high/low of first 15-30 minutes of RTH session
2. **Wait for Breakout**: Price closes above IVB high (long signal) or below IVB low (short signal)
3. **Entry Options**:
   - **Model 1 (Immediate)**: Enter market order on next bar after breakout
   - **Model 2 (Retest)**: Wait for pullback to IVB level within 5-10 bars for better R:R
4. **Exit**: Fixed TP/SL (Fabervaale suggests 1:2 to 1:2.5 R:R ratio)

## Signal Rules

**Long Entry:**
- Wait for first 15-30 min of RTH to complete (IVB formation)
- Bar closes above IVB high
- Optional: Wait for retest (low comes within 4 ticks of IVB high)
- Enter at ask on next bar

**Short Entry:**
- Wait for first 15-30 min of RTH to complete (IVB formation)
- Bar closes below IVB low
- Optional: Wait for retest (high comes within 4 ticks of IVB low)
- Enter at bid on next bar

**Exit:**
- Take profit: 12-24 ticks (1.5x to 3x SL for 1:2-1:3 R:R)
- Stop loss: 8-12 ticks

## Parameters to Optimize
- `opening_range_bars`: 15, 30, 45 minutes
- `wait_for_retest`: False (immediate) or True (wait for pullback)
- `retest_lookback`: 5-10 bars to wait for retest
- `retest_proximity_ticks`: 4 ticks (how close counts as retest)
- `take_profit_ticks`: 12-24 ticks
- `stop_loss_ticks`: 8-12 ticks
- `session_filter`: RTH only (required for opening range logic)

## Implementation Details (2026-03-15)

### Backtest Structure
- **File**: `backtest.py`
- **Core Logic**:
  1. `_identify_ivb_ranges()`: Identifies opening range high/low for each RTH day
  2. `_build_specs()`: Detects breakouts and generates TradeSpec entries
  3. Entry modes:
     - **Immediate**: Enter next bar after breakout above/below IVB
     - **Retest**: Wait for pullback within N bars, enter when price retests IVB level

### 5 Parameter Variations

| # | Name | OR Bars | Entry Mode | TP/SL Ticks | R:R Ratio |
|---|------|---------|------------|-------------|-----------|
| 1 | Baseline 30min | 30 | Immediate | 16 / 8 | 1:2 |
| 2 | Default | 15 | Immediate | 12 / 8 | 1:1.5 |
| 3 | Wide Targets | 30 | Immediate | 24 / 12 | 1:2 |
| 4 | Retest Entry | 30 | Retest | 16 / 8 | 1:2 |
| 5 | Conservative | 45 | Retest | 20 / 10 | 1:2 |

**Design Rationale**:
- Variations 1-3 test opening range duration (15 vs 30 vs 45 min) and TP/SL sizing
- Variation 4 tests retest entry (better R:R but fewer setups)
- Variation 5 tests conservative approach (longer OR + retest + wider targets)

## Key Implementation Notes

### Session Detection (Performance Critical)
- **Challenge**: Identifying RTH session starts at 9:30 ET across multiple days
- **Solution**: Vectorized pandas operations instead of `iterrows()` loop
- **Impact**: Reduces session detection from O(N) row-by-row to O(N) vectorized

```python
# SLOW (original): iterrows() over 3K+ bars
for i, row in bars_et.iterrows():
    if row["hour"] == 9 and row["minute"] == 30 and row["date"] != prev_date:
        session_starts.append(i)

# FAST (optimized): vectorized boolean indexing
is_930 = (hour == 9) & (minute == 30)
date_changed = date != date.shift(1)
session_starts = bars.index[is_930 & date_changed].tolist()
```

### Entry Logic
**Immediate Mode** (Variations 1-3):
- Breakout detection: Bar closes above IVB high (long) or below IVB low (short)
- Entry: Next bar, at ask (long) or bid (short)
- Advantage: More setups, faster signals
- Risk: No confirmation, higher false breakouts

**Retest Mode** (Variations 4-5):
- Breakout detection: Same as immediate
- Wait: Up to N bars for pullback to IVB level (within X ticks)
- Entry: When retest confirmed
- Advantage: Better R:R, confirmation of level
- Risk: Fewer setups, may miss strong directional moves

### Data Requirements
- **Session filter**: RTH only (NYOpen, MidDay, PowerHour, Close)
- **Bar data**: 1-min OHLC with delta
- **Tick data**: Trades with NBBO for precise entry fills
- **Timezone**: All bars converted to ET for 9:30 detection

## Transcript

A lot of traders are familiar with the opening range breakout. You buy or sell the breakout of the first 15 minutes of the cash session. This strategy published in the 1990 by Toby Crabel proven to be one of the most consistent edge over the last decade with a positive profit factor and an amazing sharp ratio. It's one of my favorite because it's really easy to trade and you can pair it with orderflow confirmation to boost its edge. In this video, I will show you how to put this edge on steroids by using two main things. The first one it's an orderflow trigger and the second one it's deep statistical analysis. and how I work with the deep charts team to build a model that shows you one the highest probable excursion to give you a level where you put your first take profit and second one the best imbalance or aggression to put your entry. If you like this video subscribe to the channel and put a like and if you want to access the IVB model go on deeparts.com. So in this video we are going to understand how the opening range breakout or initial balance breakout works and how we can improve it. Now the logic behind the opening range breakout or initial balance is the following. The New York session is the session that hold the maximum amount of volume for the day. So you have the strongest battle between buyers and sellers. You have the peak of interest and input of volume during the day and usually you see this as soon as the London session open with big swings and a big battle between aggressive buyers and aggressive sellers. This situation here define a clear range and from this range you can see rejection you can see absorption of the buyers of the sellers exhaustion. So you can do a lot of analysis with volume. But the orb method works this way. You have two defined levels that are the top and the bottom of the range of the first 15, 30 or 60 minutes. It depends how you want to use it. If you want to use it more scalp or more intraday bias and what the model says is that the first one that break is telling you what is telling you who won the battle of the most important time of the day. So the first 15 minutes of New York opening or 30. Okay. And from a statistical point of view, this one have a strong value in predicting the direction for the day at least till certain level that you can use as high probability profit target. Now when we understand this, we understand that what we are doing is aligning with the biggest market participants that won the battle. So we are protected by a wall of balance. We are going in a condition of imbalance and we are in the direction of the volume. Okay. Now this one used the loan without any other confirmation have value. Okay. Have value. This one is using the first 15 minutes of the session without implementing volume. So you can already see that compared with the S&amp;P 500 buy and provide a smoother equity line with less draw down and gives you a expectancy or profit factor that is positive. Okay. Now why this gets interesting because during the years I was trying to understand how to take a model that it's already profitable and putting it on steroids and my kind of steroids it's orderflow. So what I'm doing now is using the statistical reliability of a profitable model paired with the steroids of orderflow analysis to get better entry point and better riskto-reward. Okay, how can we do this? We can do this in multiple way. The first way is by implementing in the model the volume profile. Okay, let's see the model one of IVB. So the model one of IVB is using the following. We have point A and we have point B. How can we define this point A and point B? This is the opening of the New York. We have a top. We have a bottom on the first 15 to 30 minutes. Okay. This is our point A and this is our point B and the price is inside this value for 15 30 depends on what you prefer to use. Okay. Now we take this top, we drag down with the fixed profile to this level. Why this gets interesting? Because now we not only have price but we have the volume distribution of the most important interaction of the day. And we can notice that the major point of control so the PC so the level where the majority of volume of the market participant it's here. Okay, this takes the name of PC. Now this is really powerful because when we go from a balance situation inside to an out of balance. So the price accept this value. Now the most sensitive level after you have this is the level contained between the value area and the PC. This is our real block of orders. This is where when you retrace you can expect buyers to reload. Okay. So this is a really sensitive confirmation from the volume profile. So we have a profitable model plus the volume profile framing. Okay. And this is for location. This is letting you understand the direction and letting you understand also the potential location of the area, the sensitive area. Why this is interesting? Because first of all, you have a more precise entry point so you can boost your risk to reward. And second of all, you also have a level of invalidation if broken. So you have a value area low that if it gets broken, so the market accept it, it's an invalidation point. Okay, you don't need to wait till here. You don't need to wait till here. You don't need to wait till here. If we close a candle here, okay, the setup is invalidated. So our real risk-to-reward is this from here to the first protection point. And the first protection point can be for example here. Okay. So now our risk-to-reward is not one to one like the test that we did but maybe it's 1 to2 one to 2.5. So we are using the same model with the same directional frame and probability but paired with order flow to improve his matrix. This is the model one. Okay. And this one don't use anything complicated. Then the model two of IVB is using orderflow. Okay. This is a little bit more advanced. Okay. because it's using the confirmation after the breakout. Okay, so we have a range, we have a point A, we have a point B, we have our profile. Okay, we have the value area low, we have the PC, sorry, the value area high, the P, and we have the value area low. And we have our framing area to seek buy. Okay, we have a breakout, we have the market retracing, and now we can start using the confirmation of order flow. Okay, what do I mean that we can start to see how orders interact this level? Maybe we have a lot of aggressive sellers here with zero result. This means that there is a big absorption on this level on the PC. Okay, so we can use this as a confirmation trigger to go long or maybe you can see an exhaustion. So you can see that the sellers don't interact. We have aggressive buyers with momentum at the top and you can take a momentum trade with a really tight stop-loss to go to the protection level. You can use all the confirmation of order flow not only to have direction.1 location 2 and confirmation of order flow.3. This is how I built during the years the basis and the foundation of the IVB model. Then the team of deep charts step in and says okay let's do deep statistical analysis. Okay let's go through years and years of data and use an algorithm using neural network machine learning or digging into the data to see what's the highest probability point that the market reach when you have a breakout of the initial balance or orb. Okay. And what the IVB does is that when you have a breakout, okay, it plot for you the high probability profit target, okay, and the potential TP2. So you know that with 65 to 70% probability, you go here and you know that with another lower probability, of course, you go to the TP2. Okay? So now you have this logic done for you by an algo. You have this logic done for you by an algo. Okay. And you can concentrate all your skills on the location and on the order flow confirmation. Okay. So the statistical analysis is doing 50% of your work by removing all the analysis of where you should go the direction the analysis and stuff is giving you an edge in direction and in location. and point 2 and three can add more value because you are more precise and you have a better entry area and confirmation than the simple orb model. Okay. And this one it's paired with a data analysis on the deep charts platform that is giving you the summary of the distribution between consolidation session and directional. Okay. So when you have this you can also understand that the opposite is true. So if you are inside this level okay you have the opportunity to fade the top and the bottom using a mean reverting okay because you know that till the market don't break completely this level the direction is not clear so you can also use a mean reverting model that is spotting the absorption of the sellers of the buyers the exhaustion on sensitive areas that are the top and the bottom of the range to take some mean reverting trades okay with high probability ility and then maybe use this profit to get trend following when you have enough confirmation that the market decided where to go. And this is what we built with the deep charts team. Now let's go to the platform and I show you how this works in action. Okay, now we are in the back testing mode of deep charts. We have a clean defined IVB top and bottom and we are waiting for the first 30 minutes of the session to be completed to define clearly the areas where we see breakout. We have a statistical edge that the price will continue in that direction. I will speed up for you a little bit. Let's see how it goes. You can see the aggression of the sellers. On the same template I have also the big orders. So as you can see till the 30 minutes is completed they continue to upload the IVB range. So we have clear defined area. Okay we are in the deep charts back testing system. We have a clear defined IVB top and IVB bottom. We have the balance area and we have the deep trade model to see the absorption and the aggression and the imbalance. Okay. And we can see that the pressure is building on the upside. So if we have a breakout now, this is the first 30 minutes of the session, we will have a protection level that is the highest probability target for the day. Let's see how it goes. As you can see, the sellers are getting absorbed here. Can go up a little bit. See the buyers continuing to step in without the support of the aggressive orders. Can zoom out for you a little bit inside. We have the aggression of the buyers with the big trades on top and we have the imbalance. But as you can see the result is not following up the aggression. So probably we go a little bit in a retracement. I go faster in the back testing model. As you can see now it's getting something interesting. They rejected perfectly from the top of the IVB. This is letting you understand how much is sensitive this area and why if we don't break out usually the price stays in a range. Okay. Now what you can see here a lot of absorption aggression and you can see that they are trying to break it again. Let's see how it goes. Okay, we have a first candle breakout and now the algorithm understand the protection level. This is the highest probability target for the single session. Let's go on this one. You can see that from this level you have an absorption of the sellers. Really clear. You have a lock in and confirmation from the buyers from here. this aggression and they come inside to reload in the same area. Now look here what you can see. You can see that on the testing level they insisted again and they got absorbed more and more. Okay? And they are building pressure. So you have a huge absorption on this horizontal level. We have a clean direction. We have a clean breakout and we are heading to the protection level that is the most sensitive level from a statistical point of view. I can go faster for you to see this in a speed up mode. See how they are building the auction on the upside. They are building the momentum for the session. A little bit of retracement. You can see that every time, see how much is sensitive the initial balance breakout area. Okay. Every time they come to test this area back, they have interaction of the aggressive market participants. Okay. They are trying to go up to the protection level. aggression from the buyers. Again, consider this guys. It's a really big really big risk-to-reward. If you know how to use orderflow and you try to manage to take this entry or the test entry, you are already 1 2 3 1 to four. But you know that if you wants to keep a runner when taking it out, the most sensitive area for the day is the protection level. Okay, this is the I took a choppy session. As you can see now they are facing the previous imbalance cluster of the buyers and they are pushing into it. So they are trying to break and you can see that every time they manage to go close to the initial balance area that got broken. You can see this catalyst on the upside momentum of the aggressive buyers that is pushing really strong on the upside. Again you see they reached again this absorption area and this one is really convenient because you have the power of order flow paired with the directional predictability of the system that is based on statistics. So you are not using discretionality to frame your bias for the day. See how much this one I took the choppy session to make you understand that even in days where you don't have a directional day still giving you an amazing edge when you break out. Imagine how many trades you would have been able to take in this area again to the same absorption area for the fourth time. Gone a little bit. Now we are going late in the session. I'm showing you all of this because I want to show you how the market feel the area of the IVB also on the long term. Okay. So look at this. This is the breakout level. Okay. And we had a choppy day. So I took one of the worst session to do this. But look how the market reacted to this level. Okay. So we frame this area in the beginning. We have an amazing absorption here. They came back the day after. Okay. And they had this kind of reaction. Why? Because this is the accumulation area of the cash session and the model is spotting this with the most sensitive level. And you can scalp in the middle all this execution. Let's go to another day. Let's go to the next one. The 27. Let's reset. I show also how the model is built before the session. So we have here the first 30 minutes that are starting. So I show you how this is created. Now we are not interested in order flow because the pressure it's unfolding and you will start to see that they start to create the area after the opening of New York. So let me go a little bit further and this area last for the first 30 minutes. Here they start with the IVB. Okay, they start to plot the level. Now wait for the first 30 minutes of the session. So we have a clean defined range. The range is expanding till you don't have the closure of the first 30 minutes. It's a really big range. This session still not closed. We are 15 minutes into the session. You see they still expand the IVB because the session is still unfolding. 3 minutes and it's closed. Okay. Now if they break this level because the range is defined. Okay. Look how much aggression then the protection level will appear somewhere here. the algo will plot it for us. Okay, you see it's plotted the protection level and it's plotted also the maximum extreme average. So when you have a really directional session this is a huge risk-to-reward but the probability of course is lower. Let me show you how this work in real time. As you can see the sellers are trying to push it down but the buyers have a clear direction and you start to plot all kind of imbalance in the middle. Okay. So as you can see on the level you see that the sellers are trying their best to push and you have a lot of absorption on this horizontal level but when they break this one they have a drift. Okay they have a drift on the upside direction. So what this means is that usually you see a breakout, you see a retracement and then you see the real battle beginning between buyers and sellers and from this interaction you can see that the sellers got absorbed on multiple cluster but the buyers are still managing to push above the IVB and when they push above the IVB they have a drift okay because you have to consider that they won the first battle of the day that is the most important one because it's the cash session battle and they defined in the direction for the day. So everything you take either you prefer to take absorption on the test of an imbalance or you prefer to take a potential reload on the level if they manage to reach it again. You have multiple trades that you can execute with the confirmation of where the price will most likely extend with the biggest probability. So you can say okay I'm done for the day and then consider that in some directional session that the first two ones that we saw so the one of Monday and this one that we are seeing it's not the best directional session okay because you have a really compressed price after the breakout but it's letting you understand that it's really powerful at defining the direction and I'm keeping on the chart also all this executed order because it's giving you a proxy for who is winning the battle. For example, in this interaction, you can see a lot of rewarded buyers and a lot of absorbed sellers. What does it mean? The buyers want this interaction here. Here, what you can see that the sellers are actually managing to have more results. Why? Because the buyers are absorbed and the sellers are having results. In this case, what we see the buyers are actually trying to push the auction up and they are winning this battle. Okay. So, what we can expect? We can expect from the orderflow perspective that this can be an interesting reload level of the buyers. And how can we have a confirmation when you have a breakout of this horizontal level? Okay, because this is the level where the real fight between buyers and seller is happening. They reach the discount one that is all this area and they are loading again. Okay, this is the high risk-to-reward trade if you want to take it. Okay. So when you have aggression of the buyers for example here okay they are protecting the area you can consider a buy with a stop loss below that goes to the protection level. Now not all the session will give you this amazing setups but when you know what you are watching in terms of order flow. So you have a allocation and you have a confirmation you can frame this opportunity by using the win of the battle of the buyers. Okay. and the momentum that it's directly derived from this interaction. Let's go a little bit faster. Can see the sellers are still super aggressive on this one. They tested again the entry level and they are playing around. Okay, now let's go to the replay of another session. You can see that the IV bits unfolding. Now we need to wait for 30 minutes for it to be defined. You can see all these absorption of the sellers. Okay, on this level then you can see a huge aggression of the sellers. So if they will break on the downside, we will consider short. If they break on the upside, we will consider long. As of now, the buyers are really aggressive on the upside. But still, we are only 15 minutes into the session. So let's see who is managing to break out either the high or the low. And from this moment, you will see either the protection level appear on the top or on the bottom side. They are managing to do still 5 minutes to finish the first 30 minutes of interaction. So the IVB is updating to the actual volume and price interaction. Little bit of absorption at the top. Okay, they managed to break. What is this? This is the protection level. Okay, the protection level is the most sensitive areas to reach if we go buy and then we have the extended average. And you know what I will do? I will just remove the order flow from this one because I want to show you also the power of the profile. Okay, remove everything. Just keep the imbalance to show you who is dominating this situation. I will mark the top of the IVB and I will give a projection of the profile on this one. So you can see what you can see that on this interaction we have the major volume concentration here. Okay. So what can we expect? We can expect that the price will break and reload. Break and reload. Break and reload. Okay. All this accumulation area it's also sustained by this amazing imbalance. Okay, they already show you an absorption of the sellers. So we have all the confirmation that this session we can play the bounce to go up maybe 1 2 3 1 2 3 1 2 3 and then if the market gives you and it's a direction all day you have the run that goes to the protection level. Now we will go a little bit fast and let's see how it unfolds. Okay, they managed to reload on the level and you can see that the price is really aggressive on the upside and it bricks the price back to the IVB high. Okay, and all these this can seems to you like small entry but all these setups have a really high risk-to-reward when you know how to frame the area. Okay, you have a really high now if you manage to reach the maximum. It's amazing but the win rate goes low. So it's better to take 1 2 3 1 to 2.5 with a really consistent way of executing it. Let's see how this area react also for the long term. Let's put a protection level cell. This one is calculated by an algo. It's doing a lot of analysis behind. Let me go faster so you can enjoy. I took another session that is choppy to make you understand that even when the market is not moving and is giving you a consolidation range, you are only engaging from the most interesting area. Okay. So if you also have problems of overtrading or if you don't know how to stay out of the market when the conditions are not good. See for example he already gave you an amazing long here another long here and you could have made one to two one two one two three and then another one two three. Okay now we are going late in the session but I will keep the level marked because I want to show you this was a super consolidation session. Okay. I want to show you how the price react from the level that we marked. How much they are powerful. Let's mark it on. As you can see, it's a super compression. Okay. They It's really compressed. They are dancing in the area of the IVB low. Okay. And the area of the protection level that it's on the top. They are in this area. They are late in the session. The session is almost closing. Look how they manage to react to the protection level. Okay. Now, it's possible that you close before that you will not hold this position. But what I want to show you is the power in helping you to understand first of all the pressure, second the location and the orderflow confirmation.

## Backtest Results

### Status (2026-03-15)
✅ Implementation complete
⏳ Optimization running (5 variations in progress)

Results will be saved to: `data/results/020_optimization_2026-03-15.json`

**Run command:**
```bash
python3 pipeline/optimize.py --strategy-id 020
```

**Expected output:**
- Top 3 variations ranked by Profit Factor
- Metrics: PF, Win Rate, Total Trades, Net PnL, Sharpe, Max DD
- Full results JSON with all 5 variations

### Next Steps
1. Wait for optimization to complete (~10-15 min for L2 tick data)
2. Analyze results: Compare immediate vs retest entry modes
3. Identify best variation for forward testing
4. Document findings in comparison with strategies 018-019

## Implementation Notes
- Use DuckDB: `nq_feed.duckdb` tables `nq_ticks`, `nq_quotes`
- Delta = inferred from trade price vs bid/ask
- Session filtering: RTH only (required for 9:30 ET opening range)
