# Telegram Bot Notifications Specification

## Overview

This document describes all notification types that your trading system will send to your Telegram bots. You have two separate bots for different trading activities.

---

## 🤖 Bot Configuration

### Bot 1: Grid Bot & Guardian Bot (Futures Trading)
**Purpose:** Notifications for BTC/ETH futures grid trading and risk management  
**Bot Token:** `8577856008:AAH4C52AeHRvcWjrRt3ztWt6RZS5MAkinxU`  
**Bot Username:** `@BTCSSR_bot`

### Bot 2: Options Trading Bot
**Purpose:** Notifications for BTC/ETH options trades  
**Bot Token:** `8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0`

---

## 📱 Bot 1: Grid Bot & Guardian Bot Notifications

### 1. Bot Lifecycle Notifications

#### 1.1 Grid Bot Startup
**When:** Grid bot starts trading
**Frequency:** Once per bot start
**Example Message:**
```
[LIVE] 🚀 ASYNCGRIDBOT STARTED

Mode: LIVE
Symbol: BTCUSD
Grid: $90,000 - $95,000
Step: $500
TP Offset: $500
Max Positions: 5

Architecture: Actor + Saga
Time: 2026-01-19 15:30:45
```

#### 1.2 Grid Bot Shutdown
**When:** Grid bot stops (manual or scheduled)
**Frequency:** Once per bot stop
**Example Message:**
```
[LIVE] 🛑 ASYNCGRIDBOT STOPPED

Symbol: BTCUSD
Runtime: 24.5h
Final Positions: 3/5
Fills Processed: 47
Sagas: 94 completed, 0 failed

Time: 2026-01-20 16:00:15
```

---

### 2. Trade Execution Alerts

#### 2.1 BUY Order Filled (Entry)
**When:** A grid BUY order is filled
**Frequency:** Multiple times per day (depends on market volatility)
**Example Message:**
```
[LIVE] 📥 BUY FILLED @ $92,500

Size: 1 contract
Entry Price: $92,500
TP Target: $93,000
Order ID: 1041347522
Grid Level: 5/10

Next: Place TP order
```

#### 2.2 SELL Order Filled (Take Profit)
**When:** A TP SELL order is filled (position closed with profit)
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 💰 TAKE PROFIT HIT @ $93,000

Entry: $92,500
Exit: $93,000
Profit: $500 ($500/contract)
Size: 1 contract
Position Runtime: 2.3h

Grid Level: 5/10
Next: Place BUY order @ $92,500
```

#### 2.3 SHORT Entry Filled
**When:** A grid SELL order is filled (short entry)
**Frequency:** Multiple times per day (SHORT mode only)
**Example Message:**
```
[LIVE] 📤 SELL FILLED @ $93,500

Size: 1 contract
Entry Price: $93,500
TP Target: $93,000
Order ID: 1041447890
Grid Level: 7/10

Next: Place TP BUY order
```

#### 2.4 SHORT Take Profit Filled
**When:** A TP BUY order is filled (short closed with profit)
**Frequency:** Multiple times per day (SHORT mode only)
**Example Message:**
```
[LIVE] 💰 SHORT PROFIT @ $93,000

Entry: $93,500
Exit: $93,000
Profit: $500 ($500/contract)
Size: 1 contract
Position Runtime: 1.8h

Grid Level: 7/10
Next: Place SELL order @ $93,500
```

---

### 3. Order Status Alerts

#### 3.1 Partial Fill Detection
**When:** Order is partially filled
**Frequency:** Rare (only when market liquidity is low)
**Example Message:**
```
[LIVE] ⚠️ PARTIAL FILL DETECTED

Order: 1041347522
Expected: 5 contracts
Filled: 2 contracts (40%)
Remaining: 3 contracts

Status: Waiting for full fill
```

#### 3.2 Order Cancellation
**When:** Bot cancels pending order (Guardian STOP or strategy change)
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] ❌ ORDER CANCELLED

Order ID: 1041347522
Price: $92,500
Side: BUY
Reason: Guardian signal STOP
Status: Cancelled successfully
```

---

### 4. Guardian Risk Management Alerts

#### 4.1 Guardian Signal: STOP
**When:** Risk conditions trigger trading halt
**Frequency:** 1-5 times per day (depends on market conditions)
**Example Message:**
```
[LIVE] 🔴 GUARDIAN SIGNAL: STOP

Reason: Daily loss limit approaching
Loss: -$850 / -$1000 limit (85%)

Action: All pending orders cancelled
Status: Trading paused
Positions: 3 open positions maintained
```

#### 4.2 Guardian Signal: GO (Resume)
**When:** Risk conditions clear, trading resumes
**Frequency:** 1-5 times per day
**Example Message:**
```
[LIVE] 🟢 GUARDIAN SIGNAL: GO

Previous Stop Duration: 45 minutes
Reason: Loss limit recovered
Current Loss: -$450 / -$1000 limit (45%)

Action: Trading resumed
Status: Placing missed grid orders
```

#### 4.3 Loss Limit Warning (80%)
**When:** Daily loss reaches 80% of limit
**Frequency:** 0-2 times per day
**Example Message:**
```
[LIVE] 📊 Guardian Alert: LOSS LIMIT WARNING

Current Loss: -$800
Daily Limit: -$1000
Percentage: 80%

Status: MONITORING
Action: Tightening risk controls
Positions: 3 open, 2 pending
```

#### 4.4 Critical Loss Limit (90%)
**When:** Daily loss reaches 90% of limit
**Frequency:** 0-1 times per day
**Example Message:**
```
[LIVE] 🚨 URGENT: CRITICAL LOSS LIMIT

Current Loss: -$900
Daily Limit: -$1000
Percentage: 90%

Status: CRITICAL
Action: Emergency risk mode activated
New Orders: BLOCKED
Positions: Protection mode enabled
```

#### 4.5 Emergency Stop (100%)
**When:** Daily loss limit reached
**Frequency:** Rare (0-1 times per week)
**Example Message:**
```
[LIVE] 🚨 URGENT: EMERGENCY STOP

Daily Loss Limit Reached: -$1000
All Trading: HALTED
All Pending Orders: CANCELLED

Action Required: Manual intervention
Status: System locked until reset
Contact: Review risk parameters
```

---

### 5. System Health Alerts

#### 5.1 WebSocket Disconnect
**When:** Connection to exchange is lost
**Frequency:** Rare (few times per week)
**Example Message:**
```
[LIVE] ⚠️ WEBSOCKET DISCONNECTED

Exchange: Delta Exchange
Last Connection: 2m 15s ago
Status: Attempting reconnection (3/5)

Impact: Order updates delayed
Action: Auto-reconnecting...
```

#### 5.2 WebSocket Reconnected
**When:** Connection restored
**Frequency:** Rare (few times per week)
**Example Message:**
```
[LIVE] ✅ WEBSOCKET RECONNECTED

Downtime: 2m 47s
Status: Connection restored
Orders Synced: 3 pending orders
Positions Synced: 2 open positions

System: Operating normally
```

#### 5.3 API Rate Limit Warning
**When:** Approaching exchange API rate limits
**Frequency:** Rare (few times per month)
**Example Message:**
```
[LIVE] ⚠️ API RATE LIMIT WARNING

Current Rate: 85/100 requests per minute
Status: Throttling enabled
Impact: Slight delay in order placement

Action: Auto-adjusting request rate
Expected: Normal operation in 60s
```

---

### 6. Reconciliation Alerts

#### 6.1 Order Mismatch Detected
**When:** Bot state doesn't match exchange state
**Frequency:** Rare (few times per week)
**Example Message:**
```
[LIVE] 🔴 Reconciliation Alert

Severity: CRITICAL
Reason: Order status mismatch

Order Details:
• Source: Bot placed
• Order ID: 1041347522
• Symbol: BTCUSD
• Side: BUY
• Qty: 1 @ $92,500

Status:
• Exchange: FILLED
• Bot: PENDING

🔗 Check WebUI for details
Action: Auto-sync initiated
```

#### 6.2 Position Sync Alert
**When:** Position count mismatch detected and fixed
**Frequency:** Rare (few times per week)
**Example Message:**
```
[LIVE] ⚠️ POSITION SYNC COMPLETED

Detected: Bot state mismatch
Exchange Positions: 3
Bot Memory: 2

Action: State synchronized
Missing Position: 1 position @ $92,500
Status: Tracking restored
```

---

### 7. Heartbeat & Monitoring

#### 7.1 Daily Status Report
**When:** Every 24 hours of operation
**Frequency:** Once per day
**Example Message:**
```
[LIVE] 📊 DAILY TRADING REPORT

Runtime: 24.0 hours
Uptime: 100%

Performance:
• Total Fills: 48
• Completed Cycles: 24
• Total Profit: $12,450
• Win Rate: 95.8%

System Health:
• WebSocket: Stable
• API Latency: 145ms avg
• Guardian Status: GO
• Open Positions: 2/5

Next Report: 2026-01-20 15:30
```

---

## 📱 Bot 2: Options Trading Notifications

### 1. Position Management

#### 1.1 Options Position Opened
**When:** New options position is opened
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 📥 OPTIONS POSITION OPENED

Symbol: C-BTC-113000-300126
Type: BTC CALL
Strike: $113,000
Expiry: Jan 30, 2026

Trade Details:
• Side: BUY
• Size: 10 contracts
• Entry Price: $190.00
• Total Cost: $1,900
• Order Type: Market

Greeks:
• Delta: +0.65
• Gamma: 0.001
• Vega: 12.5
• Theta: -0.5

Days to Expiry: 11 days
```

#### 1.2 Added to Options Position
**When:** Position size is increased
**Frequency:** Several times per day
**Example Message:**
```
[LIVE] ➕ POSITION SIZE INCREASED

Symbol: C-BTC-113000-300126
Action: SELL additional contracts

Trade Details:
• Added Size: 5 contracts
• Fill Price: $206.00
• Total Cost: $1,030

Position Summary:
• Previous Size: -10
• New Size: -15
• Avg Entry: $195.33
• Current P&L: -$159.50 (-8.16%)

Order Type: Maker limit filled
```

#### 1.3 Options Position Closed
**When:** Position is fully closed
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 💰 OPTIONS POSITION CLOSED

Symbol: C-BTC-113000-300126
Type: BTC CALL $113,000

Trade Performance:
• Entry Price: $190.00
• Exit Price: $210.00
• Size: 10 contracts
• Profit: $200.00 (+10.53%)
• Hold Time: 6h 23m

Execution:
• Close Side: SELL
• Order Type: Market
• Fill Price: $210.00
• Slippage: 0.95%

Greeks at Close:
• Delta: 0.68
• Spot Price: $105,450
```

---

### 2. Profit & Loss Alerts

#### 2.1 Take Profit Hit
**When:** Position reaches profit target
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 🎯 TAKE PROFIT TARGET HIT

Symbol: C-BTC-113000-300126
Target: +15.00%
Actual: +15.24%

Position Details:
• Entry: $190.00
• Current: $219.00
• Profit: $290.00
• Size: 10 contracts

Action: Position auto-closed
Execution: Market order filled @ $219.50
Final Profit: $295.00 (+15.53%)
```

#### 2.2 Stop Loss Hit
**When:** Position reaches loss limit
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] 🛑 STOP LOSS TRIGGERED

Symbol: P-ETH-3500-300126
Limit: -10.00%
Actual: -10.12%

Position Details:
• Entry: $85.00
• Current: $76.40
• Loss: -$86.00
• Size: 10 contracts

Action: Position auto-closed
Execution: Market order filled @ $76.35
Final Loss: -$86.50 (-10.18%)

Risk Protection: Activated
```

#### 2.3 Max Loss Alert
**When:** Single position loss exceeds threshold
**Frequency:** Rare (few times per week)
**Example Message:**
```
[LIVE] 🚨 MAX LOSS BREACH

Symbol: C-BTC-115000-300126
Max Loss: $300 per position
Current Loss: -$315.40

Position:
• Entry: $175.00
• Current: $143.46
• Size: 10 contracts
• Loss %: -18.02%

Action: EMERGENCY CLOSE initiated
Execution: Market order placed
Status: Awaiting fill confirmation
```

---

### 3. Expiry Management

#### 3.1 Expiry Warning (24h)
**When:** Option expires in 24 hours
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] ⚠️ OPTIONS EXPIRY WARNING

Symbol: C-BTC-113000-300126
Time to Expiry: 23h 45m
Expiry: Jan 30, 2026 12:00 UTC

Position Status:
• Size: 10 contracts
• Current P&L: +$145.00 (+7.63%)
• In-the-Money: YES
• Intrinsic Value: $2,450

Recommendation:
Close before expiry if profit target met
Auto-close: 1 hour before expiry
```

#### 3.2 Critical Expiry (1h)
**When:** Option expires in 1 hour
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 🔴 CRITICAL EXPIRY ALERT

Symbol: C-BTC-113000-300126
Time to Expiry: 58 minutes
URGENT ACTION REQUIRED

Position:
• Size: 10 contracts
• Current P&L: +$175.00 (+9.21%)
• Spot Price: $105,890
• Strike: $113,000
• Status: Out-of-the-Money

WARNING: Position will expire worthless
Action: Auto-close in 10 minutes
Recommended: Close immediately
```

#### 3.3 Auto-Close Before Expiry
**When:** System closes position 1h before expiry
**Frequency:** Multiple times per day
**Example Message:**
```
[LIVE] 🕐 AUTO-CLOSE: EXPIRY PROTECTION

Symbol: C-BTC-113000-300126
Reason: Approaching expiry (55m remaining)

Execution:
• Side: SELL to close
• Size: 10 contracts
• Fill Price: $182.50
• Order Type: Market

Result:
• Entry: $190.00
• Exit: $182.50
• Loss: -$75.00 (-3.95%)

Protection: Prevented total loss
```

---

### 4. Multi-Leg Strategy Notifications

#### 4.1 Strategy Executed
**When:** Multi-leg options strategy is opened
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] 🎯 STRATEGY EXECUTED

Strategy: Iron Condor
Underlying: BTC
Expiry: Jan 30, 2026

Legs Filled:
1. SELL Call $115,000 @ $85.00 (10 contracts)
2. BUY Call $117,000 @ $45.00 (10 contracts)
3. SELL Put $108,000 @ $90.00 (10 contracts)
4. BUY Put $106,000 @ $50.00 (10 contracts)

Total:
• Net Credit: $900.00
• Max Profit: $900.00
• Max Loss: $1,100.00
• Breakeven: $108,900 - $115,900

Status: All legs filled successfully
```

#### 4.2 Strategy Partial Fill
**When:** Some legs filled, others pending
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] ⏳ STRATEGY PARTIAL FILL

Strategy: Iron Condor
Progress: 2/4 legs filled

Filled Legs:
✅ SELL Call $115,000 @ $85.00
✅ BUY Call $117,000 @ $45.00

Pending Legs:
⏳ SELL Put $108,000 (maker order pending)
⏳ BUY Put $106,000 (waiting)

Status: Monitoring fills
Timeout: Auto-cancel in 5 minutes if incomplete
```

#### 4.3 Strategy Closed
**When:** All legs of strategy are closed
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] 💰 STRATEGY CLOSED

Strategy: Iron Condor
Underlying: BTC
Hold Time: 8h 15m

Performance:
• Entry Credit: $900.00
• Exit Cost: $450.00
• Profit: $450.00 (+50.00%)
• Max Profit: $900.00 (50% of max)

All Legs Closed:
1. BUY Call $115,000 @ $40.00
2. SELL Call $117,000 @ $25.00
3. BUY Put $108,000 @ $45.00
4. SELL Put $106,000 @ $30.00

Result: SUCCESS
ROI: 50% on max risk
```

---

### 5. Risk Alerts

#### 5.1 Liquidity Warning
**When:** Option has wide bid-ask spread
**Frequency:** Several times per day
**Example Message:**
```
[LIVE] ⚠️ LIQUIDITY WARNING

Symbol: C-BTC-118000-300126
Spread: 12.5% (wide)

Market Data:
• Best Bid: $70.00
• Best Ask: $80.00
• Mid Price: $75.00
• Volume: 5 contracts (low)

Warning:
• Difficult to exit
• Slippage risk high
• Consider closing with limit order

Position: -5 contracts @ $85.00
Current Loss: -$50.00 (-11.76%)
```

#### 5.2 Guardian Block (Options)
**When:** Guardian stops options trading
**Frequency:** Few times per day
**Example Message:**
```
[LIVE] 🔴 GUARDIAN: OPTIONS TRADING HALTED

Reason: Overall portfolio risk limit
Total Options Exposure: $5,450
Risk Limit: $5,000

Status: New orders blocked
Existing Positions: Maintained
Action: Close positions or wait for limit reset

Guardian Status: STOP
Resume: When exposure < $4,500
```

---

### 6. System Notifications

#### 6.1 Order Timeout
**When:** Order not filled within time limit
**Frequency:** Several times per day (maker orders)
**Example Message:**
```
[LIVE] ⏱️ ORDER TIMEOUT

Symbol: C-BTC-113000-300126
Order Type: Limit (maker)
Limit Price: $195.00

Status:
• Placed: 5 minutes ago
• Filled: 0 contracts
• Market Price: $197.50 (moved away)

Action: Order cancelled
Recommendation: Use market order or adjust price
```

#### 6.2 Options Module Status
**When:** Periodic status update
**Frequency:** Every 6 hours
**Example Message:**
```
[LIVE] 📊 OPTIONS TRADING STATUS

Active Positions: 7
Total Exposure: $3,250
Unrealized P&L: +$285.00 (+8.77%)

By Type:
• Calls: 4 positions (+$180)
• Puts: 3 positions (+$105)

By Underlying:
• BTC: 5 positions (+$225)
• ETH: 2 positions (+$60)

Risk Status:
• Guardian: GO
• Max Loss Check: ACTIVE
• Expiry Monitor: RUNNING

System Health: All systems operational
```

---

## 📋 Message Format Standards

### Message Structure
All messages follow this format:
```
[MODE] EMOJI TITLE

Primary Info:
• Detail 1
• Detail 2
• Detail 3

Secondary Info (if needed):
• Additional context

Action/Status/Recommendation
```

### Mode Prefixes
- `[LIVE]` - Real money trading
- `[DEMO]` - Paper trading / testnet

### Emoji Legend
- 🚀 Bot startup
- 🛑 Bot shutdown
- 📥 BUY order filled
- 📤 SELL order filled
- 💰 Profit/Take profit hit
- ⚠️ Warning
- 🚨 Critical alert
- 🔴 Error/Stop
- 🟢 Resume/Success
- ✅ Confirmed/Completed
- ❌ Cancelled/Failed
- 📊 Status report
- 🎯 Target hit
- ➕ Addition
- 🕐 Time-based action
- 🔗 Link/Reference
- 📱 System notification

---

## 🔧 Configuration Notes

### Notification Frequency
- **Critical Alerts:** Immediate (no delay)
- **Trade Execution:** Immediate (no delay)
- **Status Updates:** Throttled (max 1 per 5 seconds per type)
- **Daily Reports:** Once per 24 hours

### Notification Cooldowns
- Guardian alerts: 5 minutes minimum between same type
- Reconciliation alerts: 1 hour minimum per order
- Liquidity warnings: 10 minutes minimum per symbol

### Message Deduplication
- Identical messages within 2 seconds are suppressed
- Prevents spam during reconnection events
- Hash-based deduplication with 50-message cache

---

## 🎯 Best Practices

### For Bot 1 (Grid/Guardian)
1. **Monitor Guardian signals** - Most important for risk management
2. **Track daily P&L** - Use daily reports to assess performance
3. **Watch WebSocket status** - Connection issues affect order updates
4. **Review reconciliation alerts** - Critical for state consistency

### For Bot 2 (Options)
1. **Expiry warnings are critical** - Act before 1-hour mark
2. **Max loss alerts require immediate action** - System auto-closes
3. **Liquidity warnings** - Be prepared for slippage
4. **Multi-leg strategies** - Ensure all legs fill within timeout

### General
1. All timestamps are in system local time (IST for your setup)
2. Loss values are always negative, profits positive
3. Prices are in USD for BTC/ETH
4. Sizes are in contracts (not USD value)
5. Percentages are rounded to 2 decimal places

---

## 📱 Testing Your Bots

### Test Message Examples

**For Grid Bot:**
```python
# Send test message to Bot 1
from bot.utils.notifier import TelegramNotifier
notifier = TelegramNotifier()
notifier.send("🧪 TEST: Grid Bot Telegram is working!")
```

**For Options Bot:**
```python
# Send test message to Bot 2
# Configure options bot token in config.yaml
from bot.utils.notifier import TelegramNotifier
notifier = TelegramNotifier(
    token="8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0",
    chat_id="YOUR_CHAT_ID"
)
notifier.send("🧪 TEST: Options Bot Telegram is working!")
```

---

## 🔐 Security Notes

1. **Never share bot tokens** - Anyone with token can control your bot
2. **Store tokens in environment variables** - Not in code
3. **Keep chat IDs private** - Prevents unauthorized message injection
4. **Regularly rotate tokens** - If compromised, create new bot
5. **Monitor unusual activity** - Check for unexpected messages

---

## 📞 Support & Troubleshooting

### If messages not arriving:
1. Check bot token is correct
2. Verify chat ID is correct
3. Ensure bot is started in Telegram (@BotFather)
4. Check config.yaml telegram.enabled = true
5. Verify no firewall blocking Telegram API

### If duplicate messages:
1. Check for multiple bot instances running
2. Verify deduplication is enabled (default)
3. Review cooldown settings

### If missing messages:
1. Check error logs for Telegram API errors
2. Verify rate limits not exceeded
3. Check notification cooldowns

---

**Document Version:** 1.0  
**Created:** January 19, 2026  
**Last Updated:** January 19, 2026  
**Author:** AI Assistant  
**Purpose:** Complete specification for Telegram bot notifications
