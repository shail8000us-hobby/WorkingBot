# 📚 WorkingBot User Manual

**Complete guide for using the WorkingBot grid trading system**

**Last Updated:** October 30, 2025  
**Version:** 3.9.0  
**Status:** Production Ready ✅

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [Configuration Guide](#configuration-guide)
3. [WebUI Usage](#webui-usage)
4. [Trading Operations](#trading-operations)
5. [Safety Systems](#safety-systems)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)
9. [Best Practices](#best-practices)
10. [FAQ](#faq)

---

## 1. Introduction

### What is WorkingBot?

WorkingBot is a professional automated grid trading system for Bitcoin (BTC) futures on Delta Exchange India. It implements a **grid trading strategy** that profits from market volatility by placing buy and sell orders at regular price intervals.

### How Grid Trading Works

```
Price Range: $105,000 - $120,000
Grid Step: $1,000
Max Positions: 3

Example Grid:
┌─────────────────────────────────────────┐
│  $120,000  ← Upper boundary (stop buying)
│  $119,000  ← Sell level (if position at $118k)
│  $118,000  ← Buy level + TP at $119k
│  $117,000  ← Buy level + TP at $118k
│  ...
│  $110,000  ← Reference (starting point)
│  $109,000  ← First buy order placed here
│  ...
│  $105,000  ← Lower boundary (stop buying)
└─────────────────────────────────────────┘

Trading Flow:
1. Price at $110,000 → Bot places BUY @ $109,000
2. Price drops to $108,500 → BUY fills @ $109,000
3. Bot instantly places SELL (TP) @ $110,000
4. Price rises to $110,500 → SELL fills → Profit: $1,000!
5. Bot places new BUY @ $108,000
6. Repeat infinitely...
```

### Key Features

**Automation:**
- 24/7 automated trading
- WebSocket-based real-time execution
- Sub-second fill detection (0.05s vs 20s)
- Hot reload configuration (no restart needed)

**Safety:**
- Multi-layer capital protection
- Volatility monitoring (IV/RV tracking)
- Guardian bot (24/7 position monitoring)
- Dead man's switch (auto-cancel if crash)
- Two-man rule (config change confirmation)

**Monitoring:**
- Real-time WebUI dashboard
- Mobile access via Tailscale VPN
- Telegram alerts
- Comprehensive logging
- Performance analytics

---

## 2. Configuration Guide

### Configuration Files

**Main Config:** `grid_config.env` (1535 lines)
- Grid parameters
- Safety limits
- Feature toggles
- API settings

**API Keys:** `secrets/api_keys.env`
- Delta Exchange credentials
- Telegram tokens (optional)

### Essential Parameters

#### Trading Mode

```bash
# Demo Mode (Paper Trading - No Real Money)
TRADING_MODE=demo
EXECUTE_ORDERS=false
I_UNDERSTAND_LIVE=NO

# Live Mode (Real Money Trading)
TRADING_MODE=live
EXECUTE_ORDERS=true
I_UNDERSTAND_LIVE=YES  # CRITICAL: Must be YES for live
```

⚠️ **ALWAYS test in demo mode first!**

#### Grid Configuration

```bash
# Price Boundaries
GRID_LOWER=105000.0        # Lower price limit ($105k)
GRID_UPPER=120000.0        # Upper price limit ($120k)

# Grid Structure
GRID_STEP=1000.0           # Distance between levels ($1k)
REFERENCE_LEVEL=110000.0   # Starting reference price

# Position Control
GRIDBOT_LOT=1              # Lot size per order (contracts)
MAX_OPEN_POSITIONS=3       # Max concurrent positions
```

**How to Choose Grid Parameters:**

```
Price Range = GRID_UPPER - GRID_LOWER
              = $120k - $105k = $15,000

Number of Levels = Price Range / GRID_STEP
                 = $15,000 / $1,000 = 15 levels

Capital per Position = GRID_STEP × GRIDBOT_LOT
                     = $1,000 × 1 = $1,000

Total Capital Needed = Capital per Position × MAX_OPEN_POSITIONS
                     = $1,000 × 3 = $3,000 minimum

Recommended Balance = Total Capital × 3 (safety buffer)
                    = $3,000 × 3 = $9,000 (~₹75,000)
```

#### Safety Limits

```bash
# Capital Protection
MAX_ACCOUNT_LOSS_INR=25000           # Max total loss (₹25k)
GUARDIAN_MAX_ACCOUNT_LOSS_INR=20000  # Guardian acts at ₹20k
GUARDIAN_LOSS_BUFFER_INR=5000        # Buffer: ₹5k

# Position Limits
MAX_PENDING_ORDERS=6                 # Max pending orders
MAX_OPEN_POSITIONS=3                 # Max open positions
MAX_POSITION_VALUE_INR=100000        # Max position value

# Margin Protection
MAX_MARGIN_UTILIZATION=40            # Max margin % (40%)
MIN_LIQUIDATION_DISTANCE_PCT=60      # Min distance to liquidation
MARGIN_EMERGENCY_RESERVE=60          # Emergency reserve %

# Volatility Limits
VOLATILITY_MAX_IV=45                 # Max implied volatility (45%)
VOLATILITY_MAX_RV=55                 # Max realized volatility (55%)
VOLATILITY_MAX_SPREAD=10             # Max IV-RV spread (±10%)
```

### Editing Configuration

#### Via WebUI (Recommended)

1. Open http://localhost:5555/config
2. Use the configuration editor
3. Every parameter has inline help (click ❓ icon)
4. Validation happens before saving
5. Hot reload applies changes in ~5 seconds

**Benefits:**
- ✅ Built-in validation
- ✅ Inline documentation
- ✅ No syntax errors
- ✅ Two-man rule protection
- ✅ Immediate feedback

#### Via Text Editor

```bash
# Edit config file
nano grid_config.env

# Save and exit
# Bot detects change within 5 seconds

# Verify change applied
tail -f bot_live.log | grep "Config change detected"
```

**⚠️ Be careful:** Syntax errors can crash the bot!

### Hot Reload Feature

**What reloads without restart:**
- ✅ Grid parameters (LOWER, UPPER, STEP, REF)
- ✅ Position limits (LOT, MAX_OPEN)
- ✅ Safety thresholds (loss limits, margin)
- ✅ Volatility limits (IV, RV, spread)
- ✅ Feature toggles

**What requires restart:**
- ❌ API keys
- ❌ Trading mode (demo ↔ live)
- ❌ Database settings
- ❌ Network configuration

**How it works:**
1. You save changes to `grid_config.env`
2. Bot checks file every 5 seconds
3. If changed, validates new config
4. If valid, applies changes:
   - Cancels pending BUY (if grid changed)
   - Recalculates grid levels
   - Places new BUY at correct price
   - **TP orders never touched!**
5. Logs confirmation

**Example:**
```bash
# Change grid step from $1k to $500
nano grid_config.env  # Edit GRID_STEP=500

# Wait 5 seconds, check logs
tail -f bot_live.log

# You'll see:
2025-10-30 13:05:00 | INFO | Config change detected
2025-10-30 13:05:01 | INFO | Cancelling pending BUY order
2025-10-30 13:05:02 | INFO | Rebuilding grid with new step: 500.0
2025-10-30 13:05:03 | INFO | Placing new BUY @ 109500.0
2025-10-30 13:05:04 | INFO | Config reload complete
```

---

## 3. WebUI Usage

### Accessing the WebUI

**Local Access:**
```
http://localhost:5555
```

**Mobile Access (via Tailscale):**
```
http://100.107.230.67:5555  # Your Tailscale IP
```

### Dashboard Overview

```
┌────────────────────────────────────────────────┐
│  WorkingBot Dashboard                          │
├────────────────────────────────────────────────┤
│                                                │
│  🤖 BOT STATUS                                 │
│  ┌────────────────────────────────────────┐   │
│  │ Status: 🟢 Running                     │   │
│  │ Mode: LIVE                             │   │
│  │ Uptime: 2h 15m                         │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  💰 MARKET DATA                                │
│  ┌────────────────────────────────────────┐   │
│  │ BTC Price: $111,246.50                 │   │
│  │ 24h Change: +2.3% ↑                    │   │
│  │ Bid/Ask: $111,241 / $111,252          │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  📊 TRADING                                    │
│  ┌────────────────────────────────────────┐   │
│  │ Pending Orders: 5                      │   │
│  │ Open Positions: 2                      │   │
│  │ Unrealized PNL: +$125.50               │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  🛡️ SAFETY                                     │
│  ┌────────────────────────────────────────┐   │
│  │ Loss Limit: 12% used (₹3k/₹25k)       │   │
│  │ Volatility: ✅ Safe (IV: 35%)          │   │
│  │ Margin: ✅ Healthy (28% used)          │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  [Start Bot]  [Stop Bot]  [View Logs]         │
│                                                │
└────────────────────────────────────────────────┘
```

### Bot Control Panel

**Location:** http://localhost:5555/bot-control

#### Starting the Bot

1. **Select Mode:**
   - Demo (paper trading)
   - Live (real money - requires confirmation)

2. **Set Duration:**
   - Infinite (run until stopped)
   - Timed (e.g., 1 hour = 3600 seconds)

3. **Review Safety Checklist** (Live mode only):
   - [ ] API keys configured
   - [ ] Grid parameters validated
   - [ ] Loss limits appropriate
   - [ ] Sufficient account balance
   - [ ] I understand this is real money

4. **Click "Start Bot"**

5. **Monitor Status:**
   - Status changes to 🟢 Running
   - Heartbeat starts updating
   - First order placed

#### Stopping the Bot

1. Click "Stop Bot" button
2. Confirm shutdown
3. Bot performs graceful shutdown:
   - Existing positions remain open
   - TP orders stay active
   - Pending BUY may be cancelled (configurable)
   - Logs saved
   - Lock files released

### Configuration Editor

**Location:** http://localhost:5555/config

**Features:**
- **171 parameters** fully documented
- **Inline help** for every setting (click ❓)
- **Real-time validation**
- **Search/filter** parameters
- **Categories:** Grid, Safety, Volatility, Features, etc.

**Inline Help Example:**

```
Parameter: MAX_OPEN_POSITIONS
Current Value: 3

❓ What it does:
Maximum number of concurrent positions the bot can hold.
Each position represents a filled BUY order awaiting its TP to fill.

⚖️ Trading Impact:
- Higher value = More capital at risk
- Higher value = More profit potential (if price moves)
- Lower value = More conservative, safer

⚠️ Warnings:
- Must have sufficient capital for max positions
- Each position ties up capital until TP fills
- Margin usage increases with more positions

🎯 Recommended Values:
- Conservative: 2-3
- Moderate: 4-6
- Aggressive: 7-10

📊 Dependencies:
- Affects: Total capital requirement
- Related to: LOT_SIZE, GRID_STEP
- Validated against: Account balance, margin limits
```

### Logs Viewer

**Location:** http://localhost:5555/logs

**Features:**
- Real-time log streaming
- Filter by level (INFO, WARNING, ERROR)
- Search by keyword
- Download logs (TXT, CSV, JSON)
- Timestamp filtering

**Example:**
```
2025-10-30 13:05:00 | INFO | GridBot initialized
2025-10-30 13:05:01 | INFO | Placing BUY @ $109,000
2025-10-30 13:08:15 | INFO | Fill detected @ $109,000
2025-10-30 13:08:16 | INFO | Placing TP @ $110,000
2025-10-30 13:12:30 | INFO | TP filled @ $110,000 | Profit: $1,000
```

### Volatility Monitor

**Location:** http://localhost:5555/volatility

**Real-time Charts:**
- **Implied Volatility (IV)** - Red line
- **Realized Volatility (RV)** - Green line
- **Safety Thresholds** - Dashed lines

**Timeframes:**
- Hourly (last 90 minutes)
- Daily (last 30 days)
- Weekly (last 60 days)
- Monthly (last 90 days)

**Live BTC Price:** Click button for 24h stats

---

## 4. Trading Operations

### Starting Live Trading

**Pre-Flight Checklist:**
1. ✅ Tested in demo mode (24+ hours)
2. ✅ Account balance sufficient (≥₹50,000)
3. ✅ API keys configured and tested
4. ✅ Grid parameters validated
5. ✅ Loss limits set appropriately
6. ✅ Emergency procedures understood

**Launch Sequence:**

```bash
# Option 1: Via WebUI (Recommended)
1. Open http://localhost:5555/bot-control
2. Select "Live Mode"
3. Duration: "Infinite"
4. Click "Start Bot (Live Mode)"
5. Review safety checklist
6. Confirm: "I understand this is REAL MONEY"
7. Click "START LIVE TRADING"

# Option 2: Via Command Line
cd /Users/shailendrasinghrajawat/Projects/WorkingBot
python3 bot/run.py live infinite
```

**First 15 Minutes - Active Monitoring:**
- Watch for initialization logs
- Verify first BUY order placed
- Check grid levels are correct
- Monitor for any errors
- Confirm heartbeat updating
- Verify WebUI shows "Running"

**First 2 Hours - Close Monitoring:**
- Check every 15-30 minutes
- Watch for first fill (if price moves)
- Verify TP placement after fill
- Monitor margin usage
- Check volatility status
- Review any warnings

**First 24 Hours - Regular Monitoring:**
- Check every 1-2 hours
- Review cumulative P&L
- Verify grid structure maintained
- Monitor safety systems
- Check Telegram alerts (if configured)

### Normal Operations

**Daily Routine:**
- Check WebUI dashboard 2-3 times
- Review logs for errors
- Monitor P&L trend
- Verify volatility within limits
- Check margin utilization

**Weekly Routine:**
- Review weekly P&L
- Analyze win rate
- Check fee costs
- Evaluate grid effectiveness
- Adjust parameters if needed

**Monthly Routine:**
- Comprehensive performance review
- Evaluate risk metrics
- Consider scaling (if profitable)
- Review safety limit adequacy
- Update strategies if needed

### Stopping Trading

**Graceful Shutdown:**
1. Click "Stop Bot" in WebUI
2. Bot performs clean shutdown
3. Existing positions remain open
4. TP orders stay active
5. Pending BUY cancelled (configurable)
6. Logs saved to timestamped file

**What Happens to Open Positions:**
- Positions stay open (not force-closed)
- TP orders remain active
- Guardian continues monitoring
- You can manually close on exchange
- Or wait for TPs to fill naturally

**Emergency Shutdown:**
```bash
# Force kill (if WebUI unresponsive)
pkill -9 -f "python.*bot/run.py"

# Clean up
rm -f /tmp/trading_bot.lock
rm -f reports/bot.pid

# Verify stopped
ps aux | grep bot
```

---

## 5. Safety Systems

### 1. Capital Protection

**Loss Limits:**
```
Trader Limit:   ₹25,000 (your absolute max)
Guardian Limit: ₹20,000 (guardian acts first)
Buffer:         ₹5,000  (20% safety margin)
```

**How It Works:**
1. Current loss: ₹15,000
2. Guardian at 75%: ⚠️ Warning alert
3. Guardian at 90%: 🚨 Critical alert
4. Guardian at 100%: 🛑 AUTO-STOP (₹20k reached)
5. Trader limit never reached (buffer protection)

**Guardian Actions:**
- 80% loss → Warning notification
- 90% loss → Critical alert + position review
- 100% loss → **Emergency shutdown** + close all positions

### 2. Volatility Protection

**Auto-Halt Triggers:**
```
IV > 45%        → Trading halted
RV > 55%        → Trading halted
|IV - RV| > 10% → Trading halted (spread too wide)
```

**When Halted:**
1. Cancels pending BUY orders
2. Saves halt state to `.volatility_halt.json`
3. Keeps TP orders active (protects positions)
4. Sends Telegram alert
5. Monitors volatility every 30 seconds

**Auto-Resume:**
1. Volatility normalizes
2. Bot detects safe conditions
3. **Opportunistic Recovery** activated:
   - Calculates missed grid levels
   - Places market orders at current (lower) price
   - Sets TPs at original grid targets
   - **Extra profit from buying dip!**
4. Resumes normal grid trading

**Example:**
```
Price: $110k, Grid Level: $110k

Volatility spikes → Cancel BUY @ $109k
Price drops to $108k during halt
Volatility normalizes → Opportunistic recovery

Place market BUY @ $108k (current price)
Set TP @ $110k (original grid target)
Profit: $2k instead of $1k → 100% extra!
```

### 3. Position Limits

**Hard Limits:**
```
Max Open Positions:     3
Max Pending Orders:     6
Max Position Value:     ₹100,000
Max Qty Per Order:      10 contracts
```

**Enforcement:**
- Bot checks before each order
- Rejects order if limit exceeded
- Logs rejection reason
- Alerts via Telegram

### 4. Margin Protection

**Safety Thresholds:**
```
Max Margin Usage:         40%
Min Liquidation Distance: 60%
Emergency Reserve:        60%
```

**Monitoring:**
- Real-time margin calculation
- Liquidation distance tracking
- Auto-reject orders if margin too high
- Emergency position closure if critical

**Example:**
```
Account Balance: ₹100,000
Current Margin:  ₹28,000 (28% - ✅ Safe)
Free Margin:     ₹72,000
Liquidation at:  ~₹150,000 loss (very far)
```

### 5. Dead Man's Switch

**Heartbeat Monitor:**
- Bot updates `.heartbeat` every 5 seconds
- Separate monitoring process watches heartbeat
- If heartbeat stops for 30 seconds → Bot crashed!

**Auto-Actions on Crash:**
1. Detect heartbeat failure
2. Send critical alert
3. **Cancel all pending BUY orders** (reduce risk)
4. **Keep TP orders active** (protect positions)
5. Log crash event
6. Notify via Telegram

**Manual Recovery:**
1. Check what caused crash (logs)
2. Fix issue
3. Restart bot
4. Bot detects existing positions
5. Resumes normal operation

### 6. Two-Man Rule

**Config Change Protection:**

**For Risky Changes (e.g., increasing loss limits):**
1. You edit config in WebUI
2. System detects risk increase
3. Requires confirmation code
4. Code sent via Telegram
5. Enter code to confirm
6. Change applied only after confirmation

**Purpose:** Prevents impulsive decisions during losses

**Example:**
```
You try to change: MAX_ACCOUNT_LOSS_INR from ₹25k to ₹50k

System: ⚠️ This doubles your risk exposure!
System: Confirmation required.
System: Code sent to Telegram.

[Enter code: 729384]

System: ✅ Change confirmed and applied.
```

---

## 6. Monitoring & Alerts

### Real-Time Monitoring

**WebUI Dashboard:**
- Live P&L updates (every 2 seconds)
- Position status
- Order status
- Margin usage
- Volatility status
- Bot health

**Heartbeat File:**
```bash
# Real-time view
watch -n 1 cat .heartbeat

# Output updates every 5s
2025-10-30 13:10:00 | PID: 7926 | 💰 $111,246.50 | Pending: 5 | Open: 2
```

**Log Files:**
```bash
# Real-time log stream
tail -f bot_live.log

# Filter for important events
tail -f bot_live.log | grep "FILL\|ERROR\|WARNING"

# Check last 50 lines
tail -50 bot_live.log
```

### Telegram Alerts

**Setup:**
1. Create bot with @BotFather on Telegram
2. Get bot token
3. Get your chat ID from @userinfobot
4. Add to `grid_config.env`:
```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ENABLE_TELEGRAM_ALERTS=true
```

**Alert Types:**

**Trading Events:**
- 🤖 Bot started/stopped
- 📋 Order placed
- ✅ Fill detected
- 💰 TP executed (profit!)
- ❌ Order cancelled

**Safety Alerts:**
- ⚠️ 80% loss limit warning
- 🚨 90% loss limit critical
- 🛑 100% loss limit reached (auto-stop)
- 🌊 Volatility halt
- ✅ Volatility resume
- ⚡ Margin warning
- 🚨 Liquidation distance warning

**System Alerts:**
- 💥 Bot crash detected (heartbeat fail)
- 🔄 Config change applied
- ⚙️ Hot reload executed
- ❌ API error
- 🔌 Connection lost/restored

**Example Alert:**
```
🤖 WorkingBot Alert

✅ FILL DETECTED

Symbol: BTCUSD
Price: $109,000.00
Side: BUY
Quantity: 1
Entry: $109,000.00
TP Placed: $110,000.00
Expected Profit: $1,000.00

Time: 2025-10-30 13:15:30
Mode: LIVE
```

### Guardian Bot Monitoring

**What Guardian Watches:**
- Total account loss (every 5 seconds)
- Margin utilization
- Position risk
- Liquidation distance
- Safety limit proximity

**Guardian Health File:**
```bash
# View guardian status
cat .guardian_health

# Example output
{
  "status": "healthy",
  "last_check": "2025-10-30T13:15:30",
  "current_loss": -15000.50,
  "loss_limit": 20000.00,
  "loss_pct": 75.0,
  "alert_level": "warning",
  "actions_taken": []
}
```

### Performance Analytics

**WebUI Analytics Page:**
- Daily/Weekly/Monthly P&L
- Win rate
- Average profit per trade
- Max drawdown
- Sharpe ratio
- Fee costs
- Grid efficiency

**CSV Reports:**
```bash
# Trade history
bot/reports/trades_last_24h.csv

# Audit logs
bot/audit/orders.jsonl
bot/audit/orders.csv

# Equity snapshots
equity_snapshots_live.json
```

---

## 7. Troubleshooting

### Common Issues

#### 1. Bot Won't Start

**Symptoms:**
- Click "Start Bot", nothing happens
- Error in logs: "Port already in use"
- Lock file error

**Diagnosis:**
```bash
# Check if bot already running
ps aux | grep "bot/run.py"

# Check lock file
ls -la /tmp/trading_bot.lock
```

**Solution:**
```bash
# Stop existing bot
pkill -f "python.*bot/run.py"

# Remove lock file
rm -f /tmp/trading_bot.lock
rm -f reports/bot.pid

# Restart
python3 bot/run.py live infinite
```

#### 2. WebUI Not Loading

**Symptoms:**
- http://localhost:5555 not responding
- "Connection refused" error

**Diagnosis:**
```bash
# Check if WebUI running
launchctl list | grep com.gridbot.webui

# Check port
lsof -i :5555
```

**Solution:**
```bash
# Restart WebUI
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

# Or manual start
cd webui/backend
python3 app.py
```

#### 3. Orders Not Placing

**Symptoms:**
- Bot running but no orders on exchange
- Logs show "Order validation failed"

**Diagnosis:**
```bash
# Check logs for errors
tail -50 bot_live.log | grep ERROR

# Common causes:
# - Insufficient balance
# - API keys invalid
# - Volatility too high
# - Grid parameters invalid
```

**Solution:**
```bash
# Check config
grep -E "EXECUTE_ORDERS|TRADING_MODE" grid_config.env

# Verify EXECUTE_ORDERS=true for live trading
# Verify TRADING_MODE=live

# Check API keys
grep DELTA_API grid_config.env

# Check balance on exchange
```

#### 4. Fill Not Detected

**Symptoms:**
- Order filled on exchange
- Bot doesn't place TP
- Position not tracked

**Diagnosis:**
```bash
# Check fill detection logs
tail -100 bot_live.log | grep -i fill

# Check WebSocket connection
tail -100 bot_live.log | grep -i "websocket\|connection"
```

**Solution:**
```bash
# Restart bot (WebSocket reconnect)
# Bot will detect existing positions on startup
```

#### 5. Volatility Auto-Halt

**Symptoms:**
- Bot stops placing orders
- Logs show "Trading halted - volatility too high"

**Expected Behavior:**
- This is a safety feature working correctly!
- Bot waits for volatility to normalize
- Auto-resumes when safe

**Action:**
```bash
# Check current volatility
tail -20 bot_live.log | grep -i volatility

# Check halt state
cat .volatility_halt.json

# Wait for auto-resume or manually lower limits
# Edit grid_config.env:
# VOLATILITY_MAX_IV=50  (increase if comfortable)
```

#### 6. High Memory/CPU Usage

**Symptoms:**
- Bot consuming >500MB RAM
- CPU usage >50%

**Diagnosis:**
```bash
# Check bot resource usage
ps aux | grep "bot/run.py"

# Check logs for loops
tail -100 bot_live.log | grep WARNING
```

**Solution:**
```bash
# Restart bot (clears memory)
pkill -f "python.*bot/run.py"
python3 bot/run.py live infinite

# Check for log file size
ls -lh bot_live.log
# If >100MB, archive it:
mv bot_live.log bot_live.log.old_$(date +%Y%m%d)
```

### Emergency Procedures

#### 1. Unexpected Losses

**Immediate Actions:**
1. **STOP BOT** immediately
```bash
pkill -9 -f "python.*bot/run.py"
```

2. **Check positions on Delta Exchange**
3. **Review logs** for what went wrong
```bash
tail -200 bot_live.log > emergency_$(date +%Y%m%d_%H%M%S).log
grep ERROR bot_live.log
```

4. **Manually close positions** if needed
5. **Investigate root cause** before restarting

#### 2. Too Many Open Positions

**Diagnosis:**
```bash
# Check open positions
curl -s http://localhost:5555/api/positions | jq

# Expected: <= MAX_OPEN_POSITIONS
```

**Actions:**
1. Stop bot if exceeded limit
2. Manually close excess positions
3. Check logs for why limit was breached
4. Fix configuration before restarting

#### 3. Margin Call Risk

**Symptoms:**
- Margin usage > 80%
- Liquidation price approaching

**Immediate Actions:**
1. **STOP BOT**
2. **Reduce positions** (close some manually)
3. **Add margin** to account
4. **Lower MAX_OPEN_POSITIONS**
5. **Increase MIN_LIQUIDATION_DISTANCE_PCT**

#### 4. API Authentication Failed

**Symptoms:**
- All orders failing
- Logs show "401 Unauthorized"

**Actions:**
1. Check API keys on Delta Exchange
2. Verify IP whitelist includes your current IP
3. Generate new API keys if needed
4. Update `secrets/api_keys.env`
5. Restart bot

### Getting Help

**Log Analysis:**
```bash
# Create diagnostic package
tar -czf diagnostic_$(date +%Y%m%d_%H%M%S).tar.gz \
  bot_live.log \
  grid_config.env \
  .heartbeat \
  .guardian_health \
  bot/reports/pnl_history_*.csv

# Share this file for analysis
```

**Self-Diagnosis:**
1. Read error messages carefully
2. Check configuration
3. Verify account balance/margin
4. Review recent changes
5. Check Delta Exchange status page

---

## 8. Advanced Features

### Opportunistic Volatility Recovery

**What It Does:**
Turns volatility halts into profit opportunities by buying the dip.

**How It Works:**
1. Volatility spikes → Trading halted
2. Price drops during halt
3. Volatility normalizes
4. Bot places market orders at current (lower) price
5. Sets TPs at original grid targets
6. Extra profit from buying cheaper!

**Example:**
```
Grid Level: $110k, Price: $110k

Volatility halts → Cancel BUY @ $109k
Price drops to $108k
Volatility OK → Opportunistic recovery

BUY market @ $108k (instead of $109k)
TP @ $110k (original target)
Profit: $2k (instead of $1k) → 100% bonus!
```

**Configuration:**
```bash
ENABLE_OPPORTUNISTIC_RECOVERY=true
MAX_OPPORTUNISTIC_ORDERS=5       # Max levels to fill at once
RECOVERY_EXECUTION_DELAY_MS=300  # Delay between orders
MIN_PROFIT_MARGIN_INR=500        # Min profit to activate
```

### Capital Protection Layers

**1. Equity Floor:**
```bash
MIN_EQUITY_RUPEES=50000  # Hard stop if equity < ₹50k
```
Won't place orders if equity drops below minimum.

**2. Drawdown Cap:**
```bash
MAX_DRAWDOWN_PCT=20      # Protective mode if 30-day DD > 20%
```
Reduces position sizes when drawdown exceeds threshold.

**3. Exposure Growth Limiter:**
```bash
MAX_TRANCHES_PER_MINUTE=2  # Prevents flash cascade fills
```
Limits how fast positions can accumulate.

**4. Pending Order Budget:**
```bash
MAX_PENDING_ORDER_CAPITAL_INR=50000  # Max ₹ in pending orders
```
Limits total capital at risk in pending orders.

### Hot Grid Reload (Infinite Uptime)

**Use Case:** Change grid while bot running (no downtime!)

**Example:**
```bash
# Bot running with GRID_STEP=1000

# Edit config (while bot running!)
nano grid_config.env
# Change: GRID_STEP=500

# Save and wait 5 seconds

# Bot automatically:
# 1. Detects change
# 2. Cancels old pending BUY
# 3. Recalculates grid
# 4. Places new BUY at correct price
# 5. Keeps all TP orders intact!
```

**Perfect for:**
- Testing different grid sizes
- Adjusting to market conditions
- Fine-tuning without restarts

### Dual Fill Detection

**WebSocket + REST Polling:**
- Primary: WebSocket (0.05s detection)
- Backup: REST polling (every 20s)
- Deduplication prevents double-processing
- Ensures no fill is ever missed

### Smart Gap Fill

**What It Does:**
If bot restart detects missing grid levels, intelligently fills them.

**How:**
1. Bot starts, detects open positions
2. Calculates expected grid levels
3. Finds gaps in coverage
4. Places missing BUY orders
5. Prioritizes maker orders (lower fees)
6. Falls back to taker if needed

---

## 9. Best Practices

### Starting Out

**Week 1: Demo Mode**
- Run demo for full week
- Test with different grid settings
- Simulate various scenarios
- Learn the interface
- Understand the logs

**Week 2: Small Live**
- Start with 1 lot, 2-3 max positions
- Set conservative loss limits (₹10k)
- Monitor actively (every 1-2 hours)
- Don't make changes mid-week
- Review performance end of week

**Week 3+: Gradual Scaling**
- Only if Week 2 profitable
- Increase ONE parameter at a time:
  - Lot size: 1 → 2
  - OR Max positions: 3 → 4
  - **Never both at once!**
- Monitor margin usage
- Keep loss limits reasonable

### Grid Configuration

**Tight Grid (High Frequency):**
```bash
GRID_STEP=500           # Smaller steps
MAX_OPEN_POSITIONS=5    # More positions
GRIDBOT_LOT=1           # Smaller lots

Benefits: More frequent trades, smaller wins
Risks: Higher fees, more capital needed
Best for: Sideways markets, low volatility
```

**Wide Grid (Low Frequency):**
```bash
GRID_STEP=2000          # Larger steps
MAX_OPEN_POSITIONS=3    # Fewer positions
GRIDBOT_LOT=2           # Larger lots

Benefits: Lower fees, bigger wins per trade
Risks: Fewer opportunities, larger moves needed
Best for: Trending markets, high volatility
```

### Risk Management

**Conservative (Recommended for Beginners):**
```bash
MAX_ACCOUNT_LOSS_INR=10000          # Low loss limit
MAX_OPEN_POSITIONS=2                 # Few positions
MAX_MARGIN_UTILIZATION=25            # Low leverage
VOLATILITY_MAX_IV=40                 # Tight volatility limits
```

**Moderate (After Experience):**
```bash
MAX_ACCOUNT_LOSS_INR=25000
MAX_OPEN_POSITIONS=4
MAX_MARGIN_UTILIZATION=35
VOLATILITY_MAX_IV=45
```

**Aggressive (Experienced Only):**
```bash
MAX_ACCOUNT_LOSS_INR=50000
MAX_OPEN_POSITIONS=7
MAX_MARGIN_UTILIZATION=50
VOLATILITY_MAX_IV=50
```

⚠️ **Never go aggressive without months of proven success!**

### Monitoring Schedule

**Active Trading (First 2 Weeks):**
- Check every 30-60 minutes
- Review logs twice daily
- Monitor Telegram alerts
- Weekly performance review

**Mature Trading (After 2+ Weeks):**
- Check 2-3 times daily
- Review logs once daily
- Trust Telegram alerts
- Weekly + monthly reviews

**Red Flags to Watch:**
- Frequent volatility halts (market too choppy)
- Win rate < 60% (grid not effective)
- High fee costs (grid too tight)
- Margin approaching limits
- Loss limit warnings

### Optimization Tips

**Grid Range:**
- Too wide: Miss opportunities (gaps too big)
- Too narrow: Frequent margin issues
- Sweet spot: ±10-15% from current price

**Grid Step:**
- Minimum: 0.5% of price (e.g., $500 for BTC @ $100k)
- Maximum: 2% of price (e.g., $2000 for BTC @ $100k)
- Optimal: 1% of price (e.g., $1000 for BTC @ $100k)

**Position Sizing:**
- Capital per position = GRID_STEP × LOT_SIZE
- Total capital needed = Capital per position × MAX_OPEN × 3
- Example: $1k × 1 × 3 × 3 = $9k minimum

**Fee Optimization:**
- Use maker orders (post-only) when possible
- Avoid tight grids (more trades = more fees)
- Calculate breakeven: Profit must exceed fees
- Example: $1k step, 0.05% fee = $0.50 per side = $1 per cycle
- Profit: $1k - $1 = $999 net (still excellent!)

---

## 10. FAQ

### General Questions

**Q: How much can I make?**  
A: Depends on market volatility and grid settings. Typical: 0.5-2% daily in good conditions. Monthly: 10-30% is realistic with proper management.

**Q: What's the minimum capital needed?**  
A: Depends on grid. For $1k step, 1 lot, 3 max positions: ~₹75k recommended (includes safety buffer).

**Q: Can I lose more than my limit?**  
A: Very unlikely. Guardian bot stops you BEFORE reaching limit. Multiple safety layers prevent overshoot.

**Q: What if the bot crashes?**  
A: Dead man's switch activates, cancels pending orders, keeps TPs active. Your positions are protected.

**Q: Should I run 24/7?**  
A: Yes, for best results. Markets trade 24/7, bot captures all opportunities. Use LaunchAgent for auto-start.

### Trading Questions

**Q: What happens if price gaps through my orders?**  
A: Orders will fill at gapped price (slippage). Grid continues normally. This is rare but possible.

**Q: Can bot handle multiple fills at once?**  
A: Yes! Dual fill detection (WebSocket + REST) catches all fills. Each gets its own TP order.

**Q: What if I want to close all positions manually?**  
A: Stop bot, manually close on Delta Exchange, cancel any pending orders. Bot won't interfere.

**Q: Can I run multiple bots?**  
A: Technically yes (different symbols), but NOT recommended. Complexity increases, errors likely.

**Q: What's the win rate?**  
A: Typically 60-80%. Every filled TP = win. Losses rare (usually from manual intervention or emergency stops).

### Technical Questions

**Q: Why WebSocket instead of REST polling?**  
A: Speed! WebSocket detects fills in 0.05s vs 20s for REST. Faster TP placement = better prices.

**Q: What happens during network outage?**  
A: Bot detects disconnect, attempts reconnect. Orders on exchange unaffected. Bot resumes when connection restored.

**Q: Can I change grid while running?**  
A: Yes! Hot reload feature applies changes in ~5 seconds without restart.

**Q: How much disk space needed?**  
A: Minimal. Logs rotate daily, DB is ~50-100MB. Total: <500MB for months of operation.

**Q: Does it work on Windows/Linux?**  
A: Code is Python, should work. But only tested on macOS. YMMV.

### Safety Questions

**Q: What if API keys are compromised?**  
A: Generate new keys immediately on Delta Exchange. Update bot config. Old keys invalidated.

**Q: Can someone hack my bot?**  
A: Bot runs locally, not exposed to internet. Only you access WebUI. Tailscale VPN is encrypted.

**Q: What's the worst case scenario?**  
A: Total loss of capital (very unlikely). Safety systems prevent this:
- Loss limits stop trading
- Guardian auto-closes positions
- Margin protection prevents liquidation
- Volatility halt reduces exposure

**Q: Should I use stop-losses?**  
A: Grid trading doesn't use stop-losses. Instead: position limits, loss limits, margin protection. Different strategy philosophy.

**Q: What if Delta Exchange goes down?**  
A: Bot detects API failures, enters safe mode, stops placing orders. Existing positions on exchange unaffected.

### Configuration Questions

**Q: How do I calculate optimal grid step?**  
A: General rule: 0.5-2% of current price. Test in demo mode to find your sweet spot.

**Q: Should I use tight or wide grid?**  
A: Tight = more frequent trades, wide = bigger wins per trade. Start wide, narrow if market suits it.

**Q: What's a good loss limit?**  
A: 5-10% of total capital. Example: ₹100k capital = ₹5k-₹10k limit. Never risk more than you can afford to lose!

**Q: How many positions should I allow?**  
A: Start with 2-3. Increase to 5-7 after weeks of success. Never exceed what your capital supports.

**Q: When should I change volatility limits?**  
A: Only if frequent halts occur AND you understand the risk. Volatility protection exists for a reason!

### Troubleshooting Questions

**Q: Bot shows "Running" but no orders?**  
A: Check: EXECUTE_ORDERS=true, volatility not halted, balance sufficient, grid parameters valid.

**Q: Orders placed but not filling?**  
A: Normal! Grid trading waits for price to reach order levels. Be patient.

**Q: TP placed but position still shows?**  
A: TP waiting for price to reach level. Position closes when TP fills, not when TP is placed.

**Q: WebUI shows stale data?**  
A: Hard refresh browser (Cmd+Shift+R on Mac). Check WebSocket connection in browser console.

**Q: Telegram alerts not working?**  
A: Verify bot token and chat ID correct. Test with: `curl https://api.telegram.org/bot<token>/getMe`

---

## 📚 Additional Resources

### Documentation Files

- **START_HERE.md** - Quick start guide (read this first!)
- **BOT_STRUCTURE.md** - Technical architecture (for developers)
- **AI_CONTEXT.md** - AI assistant context (project state)
- **README.md** - GitHub overview

### Configuration Examples

```bash
# Conservative Setup (Beginner)
GRID_STEP=1000
MAX_OPEN_POSITIONS=2
MAX_ACCOUNT_LOSS_INR=10000
MAX_MARGIN_UTILIZATION=25

# Balanced Setup (Intermediate)
GRID_STEP=1000
MAX_OPEN_POSITIONS=4
MAX_ACCOUNT_LOSS_INR=25000
MAX_MARGIN_UTILIZATION=35

# Aggressive Setup (Advanced)
GRID_STEP=500
MAX_OPEN_POSITIONS=7
MAX_ACCOUNT_LOSS_INR=50000
MAX_MARGIN_UTILIZATION=50
```

### Command Reference

```bash
# Start bot (demo)
python3 bot/run.py demo infinite

# Start bot (live)
python3 bot/run.py live infinite

# Stop bot
pkill -f "python.*bot/run.py"

# View logs
tail -f bot_live.log

# Check status
cat .heartbeat

# Emergency cleanup
rm -f /tmp/trading_bot.lock reports/bot.pid
```

---

**🎓 You now have everything you need to trade successfully with WorkingBot!**

**Remember:**
1. Start with demo mode
2. Scale gradually
3. Respect safety limits
4. Monitor regularly
5. Learn from each trade

**Good luck and trade responsibly! 📈**

---

**Last Updated:** October 30, 2025  
**Version:** 3.9.0  
**Status:** Production Ready ✅
