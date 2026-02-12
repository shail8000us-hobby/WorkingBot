# Institutional Options Seller - Complete Guide

## For BankNifty & Nifty Scripts

> **Written for absolute beginners.** No prior knowledge of trading, options, or programming needed.

---

## Table of Contents

1. [What Are These Scripts?](#1-what-are-these-scripts)
2. [Before You Begin - Basic Concepts](#2-before-you-begin---basic-concepts)
3. [The Two Scripts - Quick Comparison](#3-the-two-scripts---quick-comparison)
4. [How to Install & Use](#4-how-to-install--use)
5. [The Split-Screen Layout Explained](#5-the-split-screen-layout-explained)
6. [All Settings (Inputs) Explained](#6-all-settings-inputs-explained)
7. [How the Script Decides to Trade (Confluence Scoring)](#7-how-the-script-decides-to-trade-confluence-scoring)
8. [Every Indicator Explained](#8-every-indicator-explained)
9. [The Dashboard - Reading Every Number](#9-the-dashboard---reading-every-number)
10. [Trade Simulation System](#10-trade-simulation-system)
11. [Signal Types - What Each Arrow/Shape Means](#11-signal-types---what-each-arrowshape-means)
12. [Alerts & Webhook Integration](#12-alerts--webhook-integration)
13. [Differences Between BankNifty & Nifty Scripts](#13-differences-between-banknifty--nifty-scripts)
14. [Tips & Best Practices](#14-tips--best-practices)
15. [Troubleshooting Common Issues](#15-troubleshooting-common-issues)

---

## 1. What Are These Scripts?

### In Plain English

Imagine you're watching a fruit market. You notice that sometimes mangoes get **overpriced** - people panic-buy them, and the price shoots up way beyond what they're worth. You, being smart, decide to **sell** at that high price because you know the price will come back down.

That's exactly what these scripts do, but with **stock market options** instead of mangoes.

### Specifically

These are **TradingView Pine Scripts** - small programs that run inside the TradingView charting platform. They:

1. **Watch** the BankNifty or Nifty index continuously
2. **Analyze** dozens of market conditions simultaneously
3. **Tell you** when it's a good time to SELL an option (because the premium is likely to decay/fall)
4. **Show you** when to exit your trade (take profit or cut loss)
5. **Track** how well the strategy is performing over time

### What is "Options Selling"?

In normal stock trading, you **buy** something hoping it goes **up**. 

In options selling, you **sell** an option contract and collect money (called "premium") upfront. If the market stays calm or moves in your favor, that option **loses value over time** (this is called "theta decay" - think of it like ice cream melting). You then buy it back cheaper, keeping the difference as profit.

**Key insight:** Options are like insurance policies. The seller (you) collects the insurance premium. Most of the time, the insurance doesn't get claimed, so the seller profits.

---

## 2. Before You Begin - Basic Concepts

### What is TradingView?

TradingView is a website (tradingview.com) where you can look at stock charts. Think of it like Google Maps, but instead of showing roads, it shows how stock prices move over time. You need a **Premium subscription** for these scripts to work (because they fetch data from multiple symbols simultaneously).

### What is Pine Script?

Pine Script is TradingView's own programming language. It lets you create custom tools that draw on charts and give you signals. You don't need to know how to code - you just copy-paste the script, and it works.

### What is BankNifty / Nifty?

- **Nifty** (also called Nifty 50) = An index that tracks the top 50 companies in India's stock market. Think of it as a scoreboard for the Indian economy.
- **BankNifty** = An index that tracks only the top banking companies in India. It moves faster and more dramatically than Nifty.

### What are Options (CE/PE)?

Options are financial contracts. There are two types:
- **CE (Call Option)** = You make money if the market goes **UP**
- **PE (Put Option)** = You make money if the market goes **DOWN**

When you **sell** a CE, you make money if the market does NOT go up.
When you **sell** a PE, you make money if the market does NOT go down.

### What is an "Index" vs an "Option Chart"?

- **Index chart** = Shows the actual BankNifty/Nifty price (e.g., 51,000)
- **Option chart** = Shows the price of one specific option contract (e.g., BankNifty 51000 CE expiring this week, currently trading at ₹250)

These scripts need you to open an **option chart** but they automatically fetch and display the **index chart** for you in a split screen.

### What is a "Timeframe"?

A timeframe is how much time each candle (bar) on the chart represents:
- **1 minute** = Each candle shows 1 minute of price movement
- **5 minutes** = Each candle shows 5 minutes
- **15 minutes** = Each candle shows 15 minutes
- **1 hour** = Each candle shows 1 hour

For options selling, 3-minute to 15-minute timeframes work best.

---

## 3. The Two Scripts - Quick Comparison

| Feature | BankNifty Script | Nifty Script |
|---------|-----------------|--------------|
| **File Name** | `BankNifty_Institutional_Seller.pine` | `Nifty_Institutional_Seller.pine` |
| **Short Name** | BN-IOS | NF-IOS |
| **Index Tracked** | NSE:BANKNIFTY | NSE:NIFTY |
| **Expiry Day** | Wednesday | Thursday |
| **Default Target** | 35% premium decay | 30% premium decay |
| **Default Stop Loss** | 25% premium rise | 20% premium rise |
| **Volatility** | Higher (moves fast) | Lower (moves slower) |
| **Use On** | BankNifty option charts (CE/PE) | Nifty option charts (CE/PE) |

Everything else - the logic, indicators, dashboard, scoring system - is **identical** between the two scripts. The only differences are the ones listed above.

---

## 4. How to Install & Use

### Step 1: Open TradingView

Go to [tradingview.com](https://tradingview.com) and log in to your Premium account.

### Step 2: Open an Option Chart

1. In the search bar at the top, type the option you want to trade. For example:
   - `BANKNIFTY 12FEB 51000CE` (for a BankNifty call option)
   - `NIFTY 13FEB 23500PE` (for a Nifty put option)
2. Select it from the dropdown
3. You should now see a candlestick chart of that option

### Step 3: Open Pine Script Editor

1. At the bottom of TradingView, click on **"Pine Editor"** tab
2. Delete any existing code in the editor
3. Copy the ENTIRE content of the `.pine` file and paste it into the editor

### Step 4: Add to Chart

1. Click the **"Add to chart"** button (or press Ctrl+Enter / Cmd+Enter)
2. You'll see a new pane appear below your option chart - this is the **index chart**
3. Drag the divider between the two panes to make each roughly 50% of the screen

### Step 5: Configure (Optional)

1. Click the ⚙️ gear icon on the indicator name
2. Adjust the settings as needed (all settings are explained in Section 6 below)

---

## 5. The Split-Screen Layout Explained

When you add this script, your TradingView screen will look like this:

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│           UPPER HALF: Your Options Chart             │
│                                                     │
│   Shows: Option candles + SELL/EXIT signals          │
│          + Bollinger Bands + VWAP                    │
│          + Support/Resistance zones                  │
│                                                     │
│   ▼ SELL (red triangle when script says to sell)     │
│   ● TP ✓ (green circle when target is hit)          │
│   ✗ SL (red X when stop loss is hit)               │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│           LOWER HALF: Index Chart                    │
│                                                     │
│   Shows: BankNifty/Nifty candles (auto-fetched)     │
│          + EMA lines (9, 21, 50, 200)               │
│          + VWAP line                                 │     ┌──────────────┐
│          + Previous Day High/Low                     │     │  DASHBOARD   │
│          + CPR (Pivot, TC, BC)                       │     │  (top-right) │
│          + Opening Range                             │     │  Shows all   │
│                                                     │     │  key numbers │
│                                                     │     └──────────────┘
└─────────────────────────────────────────────────────┘
```

### How Does This Work Technically?

The script uses `indicator(overlay=false)` which creates its own separate pane (the lower half). Then it uses `force_overlay=true` on certain plots to push them onto the main chart (upper half). This gives you two charts in one view:

- **Upper pane** = Your option's price chart with buy/sell signals overlaid
- **Lower pane** = The underlying index chart with institutional levels

### Why Is This Useful?

When you're trading options, you need to see BOTH:
1. The **option's own price** (to enter/exit trades)
2. The **index movement** (because the option's price depends on where the index goes)

Without this split-screen, you'd need two monitors or keep switching tabs.

---

## 6. All Settings (Inputs) Explained

When you click the ⚙️ gear icon, you'll see these settings organized in groups:

### 🏛️ Index Group

| Setting | Default | What It Does |
|---------|---------|-------------|
| **Index Symbol** | NSE:BANKNIFTY (or NSE:NIFTY) | Which index to track. Change this only if TradingView uses a different symbol for your broker. |

### 🎯 Strategy Group

| Setting | Default | What It Does |
|---------|---------|-------------|
| **Signal Quality** | High | Controls how picky the script is about trade signals. **Ultra** = Only takes the absolute best setups (2-4 trades per week, very safe). **High** = Good quality trades (5-10 per week, recommended). **Medium** = More trades (15+ per week, but lower quality each). |

**How it works:** Each potential trade gets a "score" (see Section 7). Ultra requires a score of 6+, High requires 4+, Medium requires 3+. Higher requirement = fewer but better trades.

### 🔄 Signals Group

| Setting | Default | What It Does |
|---------|---------|-------------|
| **RSI Length** | 14 | How many candles the RSI indicator looks back. Higher = slower, smoother. Lower = faster, more sensitive. 14 is the universal standard. |
| **RSI Extreme** | 78 | Above this RSI value, the option premium is considered "overpriced" (overbought). The script sees this as a sell opportunity. Range: 65-90. |
| **BB Period** | 20 | Bollinger Bands lookback period. 20 is the standard. Higher = wider bands, fewer breakout signals. |
| **BB Std Dev** | 2.5 | How wide the Bollinger Bands are. 2.0 = standard, 2.5 = wider (we use wider because options are volatile). Price going above the upper band is an "extreme" condition. |

### 📊 Structure Group

| Setting | Default | What It Does |
|---------|---------|-------------|
| **Swing Length** | 8 | How many candles the script looks at to find support/resistance levels. Higher = finds bigger, more important levels. Lower = finds more levels but less significant ones. |
| **ATR Length** | 14 | Period for Average True Range (measures how much price moves per candle). Used to judge if a candle is "big" or "small" relative to normal movement. |

### 💰 Risk Group

| Setting | BN Default | NF Default | What It Does |
|---------|-----------|-----------|-------------|
| **Target % (premium decay)** | 35% | 30% | How much the option premium must DROP for you to take profit. If you sold at ₹200, a 35% target means you exit when premium falls to ₹130 (you made ₹70). BankNifty has higher target because premiums move faster. |
| **Stop % (premium rise)** | 25% | 20% | How much the option premium can RISE before you cut your loss. If you sold at ₹200, a 25% stop means you exit if premium rises to ₹250 (you lost ₹50). |

**Understanding Risk-Reward:** With BankNifty defaults (35% target / 25% stop), your potential win is 35 units for every 25 units risked = R:R of 1.4. This means even if you only win 50% of trades, you'd still be profitable.

### 🕐 Session Group

| Setting | Default | What It Does |
|---------|---------|-------------|
| **NSE Hours Only** | On | Only generate signals during market hours (9:15 AM - 3:30 PM IST). Turn off if trading international markets. |
| **Skip First 15 Min** | On | Ignore the first 15 minutes after market opens (9:15-9:30). This period is chaotic and unpredictable. Professional traders avoid it. |
| **Skip 12:30-1:00** | On | Skip the lunch hour low-activity zone. Volume drops during lunch, signals are unreliable. |
| **Force Exit HHMM** | 1510 | Force-close any open trade at this time. 1510 = 3:10 PM. This gives 20 minutes buffer before market closes at 3:30 PM. **Never hold overnight** as an options seller. |

### 📈 Index Chart Group (Lower Pane)

| Setting | Default | What It Does |
|---------|---------|-------------|
| **Index EMAs** | On | Show moving average lines (EMA 9, 21, 50, 200) on the index chart. These show the index trend direction. |
| **Index VWAP** | On | Show VWAP (Volume Weighted Average Price) on index. This is the "fair price" for the day. |
| **Prev Day H/L** | On | Show yesterday's highest and lowest prices as horizontal lines. These are key levels where price often reacts. |
| **CPR Levels** | On | Show Central Pivot Range - three lines (Pivot, Top Central, Bottom Central) calculated from yesterday's data. Professional traders watch these closely. |
| **Opening Range** | On | Show the highest and lowest prices during the first 15 minutes (9:15-9:30). These act as support/resistance for the rest of the day. |

### 🎨 Options Chart Group (Upper Pane)

| Setting | Default | What It Does |
|---------|---------|-------------|
| **BB on Options** | On | Show Bollinger Bands on your option chart. Price touching the upper band = potentially overbought. |
| **VWAP on Options** | On | Show VWAP on your option chart. If option price is far above VWAP, premium is expensive (good to sell). |
| **S/R Zones on Options** | On | Show Support/Resistance levels on your option chart. These are price levels where option premium has repeatedly bounced. |

---

## 7. How the Script Decides to Trade (Confluence Scoring)

This is the **brain** of the script. Instead of relying on just one indicator (which would be unreliable), it checks **11 different conditions** and assigns points to each. Only when enough conditions align does it give a SELL signal.

### What is "Confluence"?

Confluence means "multiple things agreeing." If one person tells you it'll rain, you might not believe them. But if 5 people, the weather app, AND you see dark clouds - that's confluence. You'd bring an umbrella.

Same principle here. The script needs multiple indicators to agree before declaring a trade opportunity.

### The Scoring System (Sell Score)

Every candle, the script calculates a **Sell Score** by checking these conditions:

| # | Condition | Points | What It Means in Plain English |
|---|-----------|--------|-------------------------------|
| 1 | RSI extreme + above Bollinger Band | **+2** | The option price has gone WAY too high, WAY too fast. Like a rubber band stretched to its limit - it's about to snap back. This is the strongest signal because two independent measures (RSI and BB) both agree. |
| 2 | At resistance zone | **+2** | The option price has reached a level where it has previously stopped rising and turned back down. Think of it as a ceiling the price keeps hitting. |
| 3 | Bearish engulfing or top rejection candle | **+1** | The candlestick pattern shows sellers are pushing back hard. A bearish engulfing means a big red candle just swallowed the previous green candle. Top rejection means price shot up but got pushed back down (long upper wick). |
| 4 | Fair Value Gap (bearish) | **+1** | An institutional-level pattern where price drops so sharply that it leaves a "gap" in the chart. This means large institutions are aggressively selling. |
| 5 | High volatility regime | **+1** | Options are currently more volatile than usual. When volatility is high, premiums are inflated (expensive), making them great to sell. |
| 6 | Index is ranging (flat) | **+1** | The underlying index (BankNifty/Nifty) is moving sideways, not trending. This is PERFECT for options sellers because time decay works in your favor while the index isn't moving much. |
| 7 | Index is falling | **+1** | The index is trending down. If you're selling a Call option (CE), a falling index helps because call premiums drop when the index falls. |
| 8 | **Index is RISING** | **-2** | **PENALTY!** If the index is strongly trending up and you're selling calls, that's dangerous. The script deducts 2 points to discourage selling against a strong trend. |
| 9 | Volume spike with bearish close | **+1** | Heavy trading volume AND the candle closed lower than it opened. This means big players are actively selling - momentum is shifting in favor of premium sellers. |
| 10 | Theta acceleration zone (after 1:30 PM) | **+1** | After 1:30 PM, time decay accelerates dramatically. Options lose value faster in the afternoon. Great for sellers! |
| 11 | Expiry day | **+1** | On the day the option expires (Wednesday for BankNifty, Thursday for Nifty), time decay goes into overdrive. An option that's worth ₹200 at 10 AM might be worth ₹20 by 3 PM if the index hasn't moved much. |
| 12 | Price far above VWAP | **+1** | The option is trading significantly above its fair value (VWAP). It's overpriced. |

### Quality Levels

| Quality | Minimum Score Needed | How Many Trades? | Best For |
|---------|---------------------|-------------------|----------|
| **Ultra** | 6 points | 2-4 per week | Very conservative, high win rate |
| **High** | 4 points | 5-10 per week | Balanced (recommended for most) |
| **Medium** | 3 points | 15+ per week | Aggressive, more trades but lower quality |

### Example

Let's say it's 2:15 PM on Wednesday (BankNifty expiry day). The script checks:

- RSI is 82 and price is above BB upper band → +2 points
- Price is near a resistance level → +2 points  
- Index is moving sideways → +1 point
- It's after 1:30 PM (theta zone) → +1 point
- It's expiry day → +1 point

**Total: 7 points.** Even Ultra quality (needs 6) would trigger a SELL signal!

### The Exit Score System

Similarly, there's an **Exit Score** that tells you when to close the trade early (before target or stop is hit):

| Condition | Points | Meaning |
|-----------|--------|---------|
| RSI oversold + below lower BB | +2 | Premium has dropped extremely fast - take profit now |
| At support zone | +2 | Premium hit a floor where it historically bounces up |
| Bullish engulfing or bottom rejection | +2 | Candle pattern shows buyers are coming back aggressively |
| Bullish Fair Value Gap | +1 | Institutions are aggressively buying |
| Low volatility | +1 | Premium has flattened out - no more decay expected |
| Volume spike with bullish close | +2 | Big buyers stepping in |
| Index just turned bullish | +2 | Index trend just reversed upward - dangerous for call sellers |

If the Exit Score reaches **5 or more**, the script triggers an early exit even if the target hasn't been hit. This protects you from a reversal.

---

## 8. Every Indicator Explained

### Indicators on the Index Chart (Lower Pane)

#### EMA (Exponential Moving Average)

**What it is:** A smoothed line that follows the average price. "Exponential" means it gives more weight to recent prices.

**The 4 EMAs used:**
- **EMA 9** (Blue line) = Very fast, follows price closely. Shows immediate direction.
- **EMA 21** (Orange line) = Short-term trend. If price is above this, short-term trend is up.
- **EMA 50** (Purple line) = Medium-term trend. Takes about 2-3 weeks of data.
- **EMA 200** (White, thicker line) = The "big boss" of all EMAs. Represents the long-term trend. Professional traders worldwide watch this.

**How to read it:** When shorter EMAs are ABOVE longer EMAs (e.g., EMA 9 > EMA 21 > EMA 50), the trend is **bullish** (up). When they're below, it's **bearish** (down). When they're tangled up, the market is **ranging** (sideways).

**Trend Cloud:** The green/red shaded area between EMA 21 and EMA 50. Green = bullish trend, Red = bearish trend.

#### VWAP (Volume Weighted Average Price)

**What it is:** The average price of the day, weighted by how much was traded at each price. Displayed as yellow cross marks.

**Why it matters:** VWAP represents the "fair value" for the day. 
- If the index is ABOVE VWAP → buyers are stronger today
- If the index is BELOW VWAP → sellers are stronger today

Large institutions use VWAP as a benchmark. They try to buy below VWAP and sell above VWAP.

#### Previous Day High/Low (PDH/PDL)

**What it is:** Two horizontal lines showing yesterday's highest price (red line) and lowest price (green line).

**Why it matters:** These are psychological levels. If today's price approaches yesterday's high, traders who bought yesterday start thinking "should I sell?" This creates natural resistance. Similarly, yesterday's low creates natural support.

#### CPR (Central Pivot Range)

**What it is:** Three lines calculated from yesterday's data:
- **Pivot** = (Yesterday's High + Low + Close) ÷ 3 (orange circles)
- **TC (Top Central)** = Upper boundary of the pivot range (orange-red line)
- **BC (Bottom Central)** = Lower boundary of the pivot range (blue line)

**Why it matters:** The width of CPR tells you about today's expected range:
- **Narrow CPR** = Price is likely to make a big move today (trending day)
- **Wide CPR** = Price is likely to stay within a range (sideways day - great for options selling!)

If price is ABOVE the CPR zone → bullish bias. If BELOW → bearish bias.

#### Opening Range (OR)

**What it is:** The highest and lowest prices during the first 15 minutes of trading (9:15-9:30 AM IST). Shown as two orange horizontal lines.

**Why it matters:** The opening range sets the "battlefield" for the day. Many institutional strategies use OR breakouts:
- If price breaks ABOVE OR High → likely a bullish day
- If price breaks BELOW OR Low → likely a bearish day
- If price stays INSIDE OR → sideways/choppy day (excellent for options selling!)

### Indicators on the Options Chart (Upper Pane)

#### Bollinger Bands (BB)

**What it is:** Two lines (upper red, lower green) that create a channel around the price. The width of the channel changes based on volatility.

**How it works:** The bands are set at 2.5 standard deviations from the 20-period average. Statistically, price should stay within these bands about 98% of the time. So when price goes ABOVE the upper band, it's in extremely rare territory and will likely come back.

**For options selling:** When the option premium is ABOVE the upper BB AND RSI is extreme → the premium is overextended and ripe for selling.

#### VWAP (Options)

Same concept as the index VWAP, but calculated on the option's own price data. Shows the "fair price" of the option today.

#### Support/Resistance (S/R) Zones

**What it is:** Horizontal levels (red dots for resistance, green dots for support) where the option price has repeatedly stopped and reversed.

**Resistance** = A ceiling. The option premium keeps trying to go above this level but gets pushed back down. **Great place to SELL** because the premium is likely to fall from here.

**Support** = A floor. The option premium keeps trying to go below this level but bounces back up. **Good place to EXIT** because the premium might bounce back up.

---

## 9. The Dashboard - Reading Every Number

The dashboard appears in the **top-right corner** of the index pane (lower half). It's a table with 3 columns and 16 rows, divided into sections.

### Section 1: HEADER

```
┌─────────────────────────────────────┐
│ BN OPTIONS │ SELLER │ High          │
└─────────────────────────────────────┘
```

- Shows the script name and your selected Quality level

### Section 2: PERFORMANCE

| Label | What It Shows | Color Coding |
|-------|--------------|--------------|
| **Trades** | "5W 2L" = 5 Wins, 2 Losses. Total count on the right. | White |
| **Win Rate** | Percentage of trades that were winners. | 🟢 Green = 65%+ (great) / 🟡 Yellow = 55-65% (okay) / 🔴 Red = below 55% (needs improvement) |
| **Avg R:R** | Average Reward-to-Risk ratio. If you risk ₹100, how much do you make on average? R:R of 2.0 means you make ₹200 for every ₹100 risked. | 🟢 Green = 2.0+ / 🟡 Yellow = 1.3-2.0 / 🔴 Red = below 1.3 |
| **P.Factor** | Profit Factor = Total profits ÷ Total losses. Above 2.0 means you make ₹2 for every ₹1 lost. | 🟢 Green = 2.0+ / 🟡 Yellow = 1.5-2.0 / 🔴 Red = below 1.5 |
| **Net P&L** | Total profit/loss in ₹. Shows "+₹5.2K" or "-₹800". | 🟢 Green = positive / 🔴 Red = negative |
| **DD:₹X** (next to P&L) | Maximum Drawdown = The biggest drop from peak. If you were up ₹10K and dropped to ₹7K, DD = ₹3K. | 🟠 Orange always (it's a warning metric) |
| **Target/Stop** | Shows your target % and stop % settings. "35%↓ 25%↑" means target is 35% down, stop is 25% up. | 🟢 Green for target / 🔴 Red for stop |

**What do these mean in practice?**

- **Win Rate 65% + R:R 1.5** = Excellent strategy. You win often AND make more than you lose.
- **Win Rate 50% + R:R 2.0** = Still profitable. You only win half the time, but winners are twice as big as losers.
- **Win Rate 50% + R:R 0.8** = LOSING strategy. Even though you win half, your losses are bigger than wins.

### Section 3: INDEX (BankNifty/Nifty)

| Label | What It Shows | Color Coding |
|-------|--------------|--------------|
| **Index** | Current price of BankNifty/Nifty (e.g., "51234.5") with change from last candle. | 🟢 Green = rising / 🔴 Red = falling |
| **Trend** | Current trend assessment: "▲ BULL", "▼ BEAR", or "◼ RANGE". Also shows "SELL✓" (safe to sell options) or "CAUTION" (be careful). | 🟢 Green Bull / 🔴 Red Bear / 🟡 Yellow Range |
| **Idx RSI** | RSI of the index itself (not the option). Shows "OB" (overbought), "OS" (oversold), or "OK". | 🔴 Red if OB / 🟢 Green if OS / Grey if OK |

**Key insight:** For options selling, "◼ RANGE" with "SELL✓" is the IDEAL condition. It means the index is moving sideways, which is perfect for time decay to work in your favor.

### Section 4: LIVE

| Label | What It Shows | Color Coding |
|-------|--------------|--------------|
| **Sell Score** | Current confluence score (e.g., "5/4" = score is 5, need minimum 4). When ready, shows "🔴 READY". | 🔴 Red = signal ready / Gray = not enough confluence |
| **Opt RSI** | RSI of the option premium. Shows "EXTREME" (overbought - good to sell), "OVERSOLD" (take profit zone), or "NORMAL". | 🔴 Red if extreme / 🟢 Green if oversold / Grey if normal |
| **Session** | Current trading session status. | 🟢 "ACTIVE" = Market is open and trading allowed / 🔴 "PAUSED" = In skip zone (opening/lunch) / 🟠 "EOD EXIT" = End of day, close positions |
| **θ ACCEL / EXPIRY!** | Special conditions. "θ ACCEL" = After 1:30 PM, theta decay accelerating. "EXPIRY!" = It's the expiry day. | 🟠 Orange for expiry / 🟡 Gold for theta |

---

## 10. Trade Simulation System

### What is This?

Since the script is an "indicator" (not a "strategy" in TradingView terms), it can't use TradingView's built-in backtesting. Instead, it has its own **trade simulation engine** that manually tracks every trade entry and exit.

### How It Works

The script keeps track of these variables across ALL bars:

1. **inPos** = Am I currently in a trade? (true/false)
2. **entry** = At what price did I enter?
3. **tpLvl** = Target price (entry minus target%)
4. **slLvl** = Stop loss price (entry plus stop%)
5. **nTrades** = Total trades taken
6. **nWins / nLoss** = Wins and losses count
7. **sumWin / sumLoss** = Total ₹ won and lost
8. **runPnL** = Running total profit/loss
9. **peakPnL** = Highest profit ever reached
10. **maxDD** = Maximum drawdown (biggest fall from peak)

### Trade Flow

```
Is confluence score high enough?
        │
        ├── NO → Do nothing, keep watching
        │
        └── YES → Are we already in a trade?
                    │
                    ├── YES → Check exits:
                    │          │
                    │          ├── Premium fell to target? → EXIT (WIN) ✓
                    │          ├── Premium rose to stop? → EXIT (LOSS) ✗
                    │          ├── Exit score ≥ 5? → EXIT (REVERSAL)
                    │          └── After 3:10 PM? → EXIT (EOD)
                    │
                    └── NO → ENTER TRADE (SELL premium)
                              Set target at entry × (1 - target%)
                              Set stop at entry × (1 + stop%)
```

### Important: Simulation vs Real Trading

This simulation is **approximate**. In real trading:
- You'd face slippage (price moves between your decision and execution)
- Spreads (bid/ask gap)
- Brokerage charges
- Margin requirements

The simulation gives you a **rough idea** of how the strategy would perform. Always paper-trade (practice without real money) first!

---

## 11. Signal Types - What Each Arrow/Shape Means

When you see these on your **options chart** (upper pane):

### 🔻 Red Triangle Down (SELL)

**What it means:** "Sell this option premium NOW"

The confluence score just met the minimum requirement. Multiple conditions are aligned in favor of the premium dropping.

**What to do:** Enter a SHORT position (sell the option). If it's a CE option, sell it. If it's a PE option, sell it.

### 🟢 Green Circle (TP ✓)

**What it means:** "Target hit! You won this trade."

The premium has decayed (fallen) by the target percentage from your entry. For example, if target is 35% and you sold at ₹200, this appears when premium hits ₹130.

**What to do:** Close your position (buy back the option). Celebrate responsibly.

### ❌ Red X (SL ✗)

**What it means:** "Stop loss hit. You lost this trade."

The premium has risen against you. For example, if stop is 25% and you sold at ₹200, this appears when premium hits ₹250.

**What to do:** Close your position immediately. Accept the loss. Do NOT remove your stop loss - that leads to catastrophic losses.

### 🟠 Orange Triangle Up (EXIT)

**What it means:** "Exit for other reason" (either reversal exit or end-of-day exit).

This appears when:
1. The Exit Score reached 5+ (market conditions reversed - get out before it gets worse)
2. It's past 3:10 PM and any open trade must be closed before market close

### Background Colors

- **Faint Red Background** = A SELL signal just fired on this candle
- **Faint Orange Background** = End-of-day zone (after 3:10 PM) - no new trades, close existing ones

---

## 12. Alerts & Webhook Integration

### What Are Alerts?

TradingView alerts are notifications that fire when specific conditions are met. You can receive them as:
- Phone push notifications
- Email
- SMS
- **Webhook** (sends data to a URL - used for automated trading)

### Setting Up Alerts

1. Click "Alert" (🔔) button on TradingView
2. In "Condition", select "BN INSTITUTIONAL SELLER" (or NF)
3. Choose either:
   - "SELL Premium" = Fires when a sell signal appears
   - "EXIT Trade" = Fires when any exit signal appears
4. Set your notification method
5. Click "Create"

### Webhook Format

If you're using the WebUI webhook system, the script sends JSON data like this:

**Entry Alert:**
```json
{
  "symbol": "BANKNIFTY24126C51000",
  "action": "sell",
  "price": 245.50,
  "strategy": "BN_Institutional",
  "timeframe": "5",
  "confluence": 5,
  "index": 51234.5,
  "rsi": 82.3
}
```

**Exit Alert:**
```json
{
  "symbol": "BANKNIFTY24126C51000",
  "action": "buy",
  "price": 165.00,
  "strategy": "BN_Institutional_Exit",
  "timeframe": "5",
  "exit_type": "target"
}
```

The `exit_type` can be: `"target"`, `"stoploss"`, or `"reversal"`.

---

## 13. Differences Between BankNifty & Nifty Scripts

While 95% of the code is identical, these are the key differences and **why** they exist:

### 1. Index Symbol

- **BankNifty:** `NSE:BANKNIFTY`
- **Nifty:** `NSE:NIFTY`

Each script fetches data from its respective index to display in the lower pane and make decisions.

### 2. Expiry Day

- **BankNifty:** Wednesday (`dayofweek.wednesday`)
- **Nifty:** Thursday (`dayofweek.thursday`)

**Why?** NSE has different expiry days for different indices. On expiry day, time decay goes into hyperdrive - options lose value extremely fast. The script adds +1 confluence point on expiry day because it's the best day to be an options seller.

### 3. Target & Stop Percentages

| | BankNifty | Nifty | Why? |
|-|-----------|-------|------|
| Target | 35% | 30% | BankNifty options move faster, so premiums decay more quickly. You can target bigger moves. |
| Stop | 25% | 20% | BankNifty's higher volatility means tighter stops to avoid big losses. |
| R:R | 1.4 | 1.5 | Nifty actually has a slightly better risk-reward because it's less volatile. |

### 4. Dashboard Labels

- BankNifty shows "BN OPTIONS" and "BANKNIFTY"
- Nifty shows "NIFTY OPT" and "NIFTY50"

### 5. Alert Strategy Names

- BankNifty uses `"BN_Institutional"` and `"BN_Institutional_Exit"`
- Nifty uses `"NF_Institutional"` and `"NF_Institutional_Exit"`

This helps the webhook system distinguish which script sent which signal.

---

## 14. Tips & Best Practices

### For Beginners

1. **Start with "Ultra" quality** setting. It gives fewer trades but much higher win rate. As you gain confidence, move to "High".

2. **Use 5-minute timeframe** on TradingView. It's a good balance between speed and reliability.

3. **Paper trade first!** Use TradingView's "Paper Trading" feature to practice without real money for at least 2 weeks.

4. **Never trade the first 15 minutes.** The script already has this built in (`skipOpen = true`), but make sure you don't override it.

5. **Always exit by 3:10 PM.** The script forces this, but if you're manually trading, set a phone alarm.

### For Intermediate Traders

6. **Best days for options selling:**
   - Expiry day (Wednesday for BN, Thursday for NF)
   - Days when the index is in a tight range
   - Afternoons (after 1:30 PM) when theta decay accelerates

7. **Worst days to sell options:**
   - Big news days (RBI policy, US Fed meetings, earnings season)
   - When index is strongly trending (all EMAs aligned in one direction)
   - Mondays with gap openings

8. **Watch the Trend indicator** in the dashboard. When it says "◼ RANGE" with "SELL✓", that's the sweet spot. When it says "▲ BULL" or "▼ BEAR" with "CAUTION", be very selective.

9. **Don't override the script's stops.** If it says SL ✗, accept the loss. One unbounded loss can wipe out months of premium selling profits.

### For Advanced Traders

10. **Combine CE and PE selling.** If the index is ranging, you can sell both a CE and a PE (this is called a "short strangle"). The script gives signals for the option chart you're looking at, so apply it to both CE and PE charts.

11. **Adjust Quality based on market regime:**
    - In low-volatility markets → Use "Medium" (options are cheap, need more trades to make money)
    - In high-volatility markets → Use "Ultra" (options are expensive, fewer but bigger wins)

12. **Monitor the Profit Factor.** If PF drops below 1.5 consistently, the market regime might have changed. Consider pausing and re-evaluating.

---

## 15. Troubleshooting Common Issues

### "The script shows an error when I add it"

**Problem:** Pine Script compilation error.
**Solution:** Make sure you're using TradingView **Premium** (or higher). The `request.security()` function with multiple symbols requires a paid plan.

### "I don't see the split screen / lower pane"

**Problem:** The index pane might be too small.
**Solution:** Look for a thin line between the two chart panes. Click and drag it upward to give the lower pane more space. Aim for 50/50 split.

### "The index chart shows flat lines / no data"

**Problem:** The index symbol might be wrong for your broker's data feed.
**Solution:** Click ⚙️ → Index Symbol → Search for your broker's BankNifty/Nifty symbol. Common alternatives: `NSE:NIFTY50`, `NSE:BANKNIFTY1!`, `INDEX:BANKNIFTY`.

### "I see zero trades / the script never gives signals"

**Possible causes:**
1. **Quality set too high** → Try "Medium" first to see if signals appear
2. **Wrong timeframe** → Use 3m, 5m, or 15m (not 1D or 1W)
3. **Outside market hours** → The script only works 9:30 AM - 3:00 PM IST by default
4. **Very liquid/ATM option** → Deep OTM options may not have enough price action to trigger signals

### "Win rate looks bad in simulation"

**Possible causes:**
1. The simulation uses historical data which may not represent current market
2. Try different Target/Stop combinations
3. Illiquid option charts can produce misleading results
4. Use ATM (At The Money) or slightly OTM options for better results

### "Dashboard text is too small"

**Solution:** The dashboard uses `size.normal` which should be clearly readable. If it's still small:
1. Try zooming into TradingView (Ctrl/Cmd + '+')
2. Use a larger monitor/resolution
3. Expand the indicator pane by dragging the pane divider

### "I want signals for BUYING options, not selling"

These scripts are designed specifically for **options selling (short selling)**. They look for overextended premiums that are likely to decay. For options buying, you'd need a different strategy altogether - these scripts would give you the OPPOSITE of what you want.

---

## Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `BankNifty_Institutional_Seller.pine` | `pinescripts/` | Main BankNifty options seller script |
| `Nifty_Institutional_Seller.pine` | `pinescripts/` | Main Nifty options seller script |
| `INSTITUTIONAL_OPTIONS_SELLER_COMPLETE_GUIDE.md` | `pinescripts/` | This documentation file |
| `INSTITUTIONAL_SELLER_GUIDE.md` | `pinescripts/` | Older, shorter usage guide |
| `BankNifty_Options_Seller_Scalper.pine` | `pinescripts/archive/` | Old version (archived, replaced by new scripts) |

---

*Last updated: February 12, 2026*
*Scripts version: 1.0*
*Pine Script version: v5*
*Requires: TradingView Premium subscription*
