# 🚀 START HERE - WorkingBot Quick Start Guide

**Welcome to WorkingBot!** This is your single entry point to get started with the Bitcoin grid trading bot system.

**Last Updated:** October 31, 2025  
**Project Location:** `/Users/shailendrasinghrajawat/Projects/WorkingBot`  
**Version:** 4.0.0 (Modular Architecture)

---

## 🚨 Recent Architecture Update (October 31, 2025)

The GridBot strategy has been refactored from a single 3,492-line file into 7 focused modules for better maintainability and testability. **Everything works the same for users** - just better code quality under the hood.

- See `GRIDBOT_REFACTORING_QUICK_REF.md` for quick overview
- See `ARCHITECTURE_UPDATE_REFACTORED_GRIDBOT.md` for complete details

---

## 📚 Documentation Structure

This project has **3 core documents** - everything you need:

1. **START_HERE.md** ← You are here! (Quick start & onboarding)
2. **USER_MANUAL.md** - Complete user guide (how to use everything)
3. **BOT_STRUCTURE.md** - Technical architecture (for developers)

**Plus:**
- **AI_CONTEXT.md** - Project state and AI assistant context
- **README.md** - GitHub project overview

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites
- macOS (Mac Mini M4 or better)
- Python 3.10+
- Delta Exchange India account with API keys
- Minimum balance: ₹50,000 recommended

### 1. First Time Setup

```bash
# Navigate to project
cd /Users/shailendrasinghrajawat/Projects/WorkingBot

# Install dependencies (one time)
pip3 install -r requirements.txt

# Install WebUI frontend dependencies (one time)
cd webui/frontend && npm install && npm run build && cd ../..
```

### 2. Configure API Keys

Create `secrets/api_keys.env`:
```bash
# Delta Exchange API Credentials
DELTA_API_KEY=your_api_key_here
DELTA_API_SECRET=your_api_secret_here
DELTA_PRIVATE_BASE_URL=https://api.india.delta.exchange
```

### 3. Start the WebUI

```bash
# WebUI runs automatically via LaunchAgent
# Check if running:
launchctl list | grep com.gridbot.webui

# If not running, start it:
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

# Open in browser:
open http://localhost:5555
```

### 4. Start Trading Bot

**Option A: Via WebUI (Recommended)**
1. Open http://localhost:5555/bot-control
2. Verify mode is set to DEMO (for testing) or LIVE (real money)
3. Click "Start Bot" button
4. Monitor the dashboard

**Option B: Via Command Line**
```bash
# Demo mode (paper trading)
python3 bot/run.py demo infinite

# Live mode (real money)
python3 bot/run.py live infinite
```

### 5. Monitor Your Bot

Open WebUI dashboard: http://localhost:5555

**You'll see:**
- 🟢/🔴 Bot status (Running/Stopped)
- 💰 Current BTC price
- 📈 Unrealized P&L
- 📋 Open positions
- 📊 Grid levels
- ⚡ Real-time updates

---

## 🎯 What Is WorkingBot?

WorkingBot is a **professional grid trading bot** for Bitcoin futures on Delta Exchange India.

### Core Concept: Grid Trading

```
Price Movement: $120k → $71k → $90k (Your profit: $4,000+)

Grid Setup:
┌──────────────────────────────────────┐
│  $120k  ← Upper limit               │
│  $110k  ← Reference (start here)    │
│  $109k  ← First BUY order           │
│  ...                                 │
│  $105k  ← Lower limit                │
└──────────────────────────────────────┘

How it works:
1. Bot places BUY orders below current price
2. When price drops, BUY orders fill
3. Bot immediately places SELL orders above entry
4. When price rises, SELL orders fill → PROFIT!
5. Repeat infinitely
```

### Why Grid Trading?
- ✅ Profits in sideways/volatile markets
- ✅ Fully automated (24/7)
- ✅ No predictions needed
- ✅ Consistent small wins
- ⚠️ Requires capital for multiple positions

---

## 🛡️ Safety Features (Your Money is Protected!)

### 1. Capital Protection
- **Max Loss Limit:** ₹25,000 (configurable)
- **Guardian Bot:** Monitors 24/7, auto-stops at ₹20,000
- **Buffer:** ₹5,000 safety margin

### 2. Volatility Protection
- **Auto-Halt:** Stops trading when market too volatile
- **IV/RV Monitoring:** Real-time implied & realized volatility
- **Smart Resume:** Automatically resumes when safe

### 3. Position Limits
- **Max Open Positions:** 3 (default)
- **Max Pending Orders:** 6
- **Lot Size Control:** Prevents over-leverage

### 4. Margin Protection
- **Max Margin Usage:** 40%
- **Liquidation Distance:** 60% minimum
- **Emergency Reserve:** Always maintained

### 5. Dead Man's Switch
- **Heartbeat Monitor:** Detects if bot crashes
- **Auto-Cancel:** Cancels all orders if heartbeat stops
- **Safety First:** Protects you even when bot fails

---

## 📊 System Architecture (Simple View)

```
┌─────────────────────────────────────────────┐
│           Your Browser                      │
│  http://localhost:5555 (WebUI)              │
└──────────────┬──────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────┐
│      WorkingBot System (macOS)              │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │  Main Trading Bot                   │    │
│  │  - Places BUY/SELL orders          │    │
│  │  - Monitors fills                   │    │
│  │  - Manages grid                     │    │
│  └────────────────────────────────────┘    │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │  Guardian Bot                       │    │
│  │  - 24/7 safety monitoring          │    │
│  │  - Loss limit protection           │    │
│  │  - Emergency shutdown              │    │
│  └────────────────────────────────────┘    │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │  WebUI Backend                      │    │
│  │  - Dashboard API                    │    │
│  │  - Real-time updates                │    │
│  │  - Configuration                    │    │
│  └────────────────────────────────────┘    │
└──────────────┬──────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────┐
│      Delta Exchange India                   │
│  - BTC Futures Trading                      │
│  - Order Execution                          │
│  - Position Management                      │
└─────────────────────────────────────────────┘
```

---

## 🎮 Essential Commands

### Bot Control

```bash
# Start bot (demo mode)
python3 bot/run.py demo infinite

# Start bot (live mode - real money!)
python3 bot/run.py live infinite

# Stop bot (graceful)
# Use WebUI or kill the process

# Check if bot is running
ps aux | grep "bot/run.py"

# View live logs
tail -f bot_live.log

# View heartbeat (updates every 5s)
watch -n 1 cat .heartbeat
```

### WebUI Control

```bash
# Check WebUI status
launchctl list | grep com.gridbot.webui

# Restart WebUI
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

# Access WebUI
open http://localhost:5555
```

### Emergency Stop

```bash
# Stop everything immediately!
pkill -9 -f "python.*bot/run.py"

# Clean up lock files
rm -f /tmp/trading_bot.lock
rm -f reports/bot.pid

# Verify stopped
ps aux | grep bot
```

---

## 📖 Configuration Quick Reference

Main config file: `grid_config.env` (1535 lines - use WebUI to edit!)

### Key Settings

```bash
# Trading Mode
TRADING_MODE=demo          # demo or live
EXECUTE_ORDERS=false       # false for demo, true for live
I_UNDERSTAND_LIVE=NO       # Must be YES for live trading

# Grid Parameters
GRID_LOWER=105000          # Lower price boundary ($105k)
GRID_UPPER=120000          # Upper price boundary ($120k)
GRID_STEP=1000             # Step size ($1k)
REFERENCE_LEVEL=110000     # Starting reference ($110k)
GRIDBOT_LOT=1              # Lot size (contracts per order)
MAX_OPEN_POSITIONS=3       # Max concurrent positions

# Safety Limits
MAX_ACCOUNT_LOSS_INR=25000      # Max total loss (₹25k)
GUARDIAN_MAX_ACCOUNT_LOSS_INR=20000  # Guardian limit (₹20k)
MAX_MARGIN_UTILIZATION=40       # Max margin % (40%)

# Volatility Limits
VOLATILITY_MAX_IV=45            # Max implied volatility (45%)
VOLATILITY_MAX_RV=55            # Max realized volatility (55%)
VOLATILITY_MAX_SPREAD=10        # Max IV-RV spread (10%)
```

**⚠️ IMPORTANT:** Edit via WebUI (http://localhost:5555/config) for validation!

---

## 🚨 Common First-Time Issues

### 1. "ModuleNotFoundError: No module named 'bot'"

**Solution:**
```bash
# Add project to Python path
export PYTHONPATH=/Users/shailendrasinghrajawat/Projects/WorkingBot:$PYTHONPATH
python3 bot/run.py demo infinite
```

### 2. WebUI Won't Start

**Check:**
```bash
# Is it running?
launchctl list | grep com.gridbot.webui

# Check logs
tail -50 ~/Library/Logs/com.gridbot.webui.log

# Restart
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
```

### 3. API Keys Not Working

**Verify:**
1. Keys are correct in `secrets/api_keys.env`
2. IP is whitelisted on Delta Exchange
3. Keys have trading permissions
4. Using India endpoint: https://api.india.delta.exchange

### 4. Bot Starts Then Stops Immediately

**Check logs:**
```bash
tail -100 bot_live.log | grep ERROR
```

**Common causes:**
- Invalid grid parameters
- Insufficient balance
- API authentication failed
- Volatility too high

---

## 📱 Mobile Access (via Tailscale)

Access WebUI from anywhere securely!

```bash
# Install Tailscale (one time)
# Download from: https://tailscale.com/download/mac

# Get your machine's Tailscale IP
tailscale status

# Access from mobile/laptop
http://100.107.230.67:5555  # Your Tailscale IP
```

**Benefits:**
- ✅ Secure VPN (encrypted)
- ✅ No port forwarding needed
- ✅ Works on cellular & WiFi
- ✅ Monitor from anywhere

---

## 🎓 Learning Path

### Week 1: Demo Mode (Paper Trading)
**Goal:** Understand how grid trading works

- [ ] Start bot in demo mode
- [ ] Watch it place orders (no real money!)
- [ ] Monitor for 24+ hours
- [ ] Observe fills and profits
- [ ] Experiment with different grid settings

**Safe to experiment!** Demo mode uses fake money.

### Week 2: Small Live Trading
**Goal:** Gain confidence with real money

- [ ] Start with 1 lot, 3 max positions
- [ ] Set strict loss limits (₹10,000)
- [ ] Monitor actively (every 1-2 hours)
- [ ] Run for full week
- [ ] Review performance

**Risk:** ₹10,000 max loss (protected by limits)

### Week 3+: Scale Gradually
**Goal:** Optimize for profit

- [ ] Only if Week 2 profitable
- [ ] Increase lot size OR max positions (not both!)
- [ ] Monitor margin usage
- [ ] Keep loss limits reasonable
- [ ] Review weekly performance

**Never rush scaling!** Steady growth beats risky bets.

---

## 🆘 Help & Support

### Documentation
- **User Manual:** `USER_MANUAL.md` - Complete guide
- **Architecture:** `BOT_STRUCTURE.md` - Technical details
- **AI Context:** `AI_CONTEXT.md` - Project state

### Quick Answers

**Q: Is my money safe?**  
A: Yes! Multiple safety systems protect you (see Safety Features above).

**Q: Can I lose more than my limit?**  
A: Very unlikely. Guardian Bot stops you BEFORE limit is reached.

**Q: What if bot crashes?**  
A: Dead man's switch cancels all pending orders automatically.

**Q: How much can I make?**  
A: Depends on market volatility. Typical: 0.5-2% per day in good conditions.

**Q: Should I start with demo or live?**  
A: **ALWAYS start with demo mode** to learn how it works!

### Emergency Contacts

**Critical Issue?**
1. Stop bot immediately: `pkill -9 -f "python.*bot/run.py"`
2. Check positions on Delta Exchange
3. Manually close positions if needed
4. Review logs: `tail -200 bot_live.log`

---

## ✅ First-Time Checklist

Before starting live trading:

- [ ] Tested in demo mode for 24+ hours
- [ ] Understand how grid trading works
- [ ] API keys configured and tested
- [ ] Grid parameters reviewed
- [ ] Loss limits set appropriately
- [ ] Sufficient account balance (₹50k+)
- [ ] Know how to stop bot (emergency)
- [ ] WebUI accessible and working
- [ ] Telegram alerts configured (optional)
- [ ] Read USER_MANUAL.md safety section

**Only check "Ready" when ALL boxes checked!**

---

## 🚀 You're Ready!

**Next Steps:**

1. **Read More:** Open `USER_MANUAL.md` for detailed guide
2. **Start Demo:** Run bot in demo mode to learn
3. **Explore WebUI:** http://localhost:5555
4. **Join Trading:** When ready, switch to live mode (carefully!)

**Remember:**
- Start small (1 lot, 3 positions)
- Monitor actively at first
- Respect loss limits
- Scale gradually
- Learn from each trade

---

**Good luck trading! 🎯**

---

**Documentation Index:**
- 📖 **START_HERE.md** ← You are here (Onboarding)
- 📚 **USER_MANUAL.md** - Complete user guide
- 🏗️ **BOT_STRUCTURE.md** - Technical architecture
- 🤖 **AI_CONTEXT.md** - AI assistant context

**Last Updated:** October 30, 2025  
**Version:** 3.9.0  
**Status:** Production Ready ✅
