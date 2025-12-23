# PM2 Quick Start Guide - GridBot

**Last Updated:** November 3, 2025

---

## 🎯 What is PM2?

PM2 is a **production process manager** that replaces tmux for running your trading bot.

**Why PM2 is Better:**
- ✅ **Auto-restart** - Bot restarts automatically if it crashes
- ✅ **Graceful shutdown** - Waits 30 seconds to cancel pending orders before stopping
- ✅ **Monitoring** - See CPU, memory, restart count in real-time
- ✅ **Logs** - Centralized log management
- ✅ **No tmux needed** - Simpler, more professional

---

## 📍 Where is PM2?

PM2 is installed **globally on your Mac** via npm (Node.js package manager).

**Check if PM2 is installed:**
```bash
pm2 --version
# Should show: 6.0.13
```

**PM2 runs in the background** - no tmux sessions needed!

---

## 🚀 How to Use PM2 with GridBot

### Option 1: Via WebUI (Easiest)

1. **Open WebUI:** http://localhost:5555
2. **Click "Start Bot"** button
3. **That's it!** Bot now runs via PM2 automatically

The WebUI now uses PM2 behind the scenes when `USE_PM2=true` is set.

---

### Option 2: Via Management Script (Recommended)

We created a simple script for you:

```bash
# Start bot
./pm2_gridbot.sh start live

# Stop bot (graceful shutdown)
./pm2_gridbot.sh stop live

# Restart bot
./pm2_gridbot.sh restart live

# View status
./pm2_gridbot.sh status

# View live logs
./pm2_gridbot.sh logs
```

**That's all you need!**

---

### Option 3: Direct PM2 Commands (Advanced)

```bash
# View all bots
pm2 list

# View live logs
pm2 logs gridbot-live

# Real-time monitoring dashboard
pm2 monit

# Stop bot
pm2 stop gridbot-live

# Start bot
pm2 start gridbot-live

# Restart bot
pm2 restart gridbot-live
```

---

## 📊 Understanding PM2 Output

When you run `pm2 list`, you'll see:

```
┌────┬─────────────────┬─────────┬──────┬───────────┬──────┬─────────┐
│ id │ name            │ pid     │ ↺    │ status    │ cpu  │ memory  │
├────┼─────────────────┼─────────┼──────┼───────────┼──────┼─────────┤
│ 0  │ gridbot-live    │ 12345   │ 0    │ online    │ 5%   │ 145mb   │
└────┴─────────────────┴─────────┴──────┴───────────┴──────┴─────────┘
```

**What each column means:**
- **name:** `gridbot-live` (your bot)
- **pid:** Process ID (changes on restart)
- **↺:** Restart count (should be 0 or low)
- **status:** `online` ✅ or `stopped` ❌ or `errored` 🔴
- **cpu:** CPU usage percentage
- **memory:** RAM usage

---

## 🔍 Real-Time Monitoring

**Dashboard view:**
```bash
pm2 monit
```

Shows:
- Live CPU/Memory graphs
- Live log output
- Process info

Press `q` to exit.

---

## 📋 Viewing Logs

**Live logs (follow mode):**
```bash
pm2 logs gridbot-live
```

**Last 100 lines:**
```bash
pm2 logs gridbot-live --lines 100 --nostream
```

**Only errors:**
```bash
pm2 logs gridbot-live --err --lines 50 --nostream
```

**Log files location:**
- **Output:** `reports/pm2-gridbot-live-out.log`
- **Errors:** `reports/pm2-gridbot-live-error.log`

---

## 🛑 Stopping the Bot

**Via WebUI:**
- Click "Stop Bot" button
- Bot shuts down gracefully (30s timeout)

**Via command:**
```bash
./pm2_gridbot.sh stop live
```

**Via PM2 directly:**
```bash
pm2 stop gridbot-live
```

**Important:** PM2 sends SIGTERM (graceful), waits 30 seconds, then SIGKILL if needed.

---

## 🔄 Restarting the Bot

**Via WebUI:**
- Click "Restart Bot" button

**Via command:**
```bash
./pm2_gridbot.sh restart live
```

---

## ✅ Current Status

**PM2 Integration:** ✅ Installed and configured

**Check current status:**
```bash
# Check if PM2 is enabled
./toggle_pm2.sh status

# Check if bot is running
pm2 list

# Check WebUI backend
launchctl list | grep gridbot.webui
```

---

## 📱 How It Works with WebUI

```
┌──────────────────────────────────────┐
│  You click "Start Bot" in WebUI      │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  WebUI Backend checks USE_PM2=true   │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Calls: pm2 start ecosystem...       │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  PM2 starts bot process              │
│  • Monitors CPU/Memory               │
│  • Auto-restart on crash             │
│  • Logs to reports/pm2-*.log         │
└──────────────────────────────────────┘
```

---

## 🎛️ Enable/Disable PM2

**Check status:**
```bash
./toggle_pm2.sh status
```

**Disable PM2 (go back to tmux):**
```bash
./toggle_pm2.sh disable
# Then restart WebUI backend:
launchctl restart com.gridbot.webui.enhanced
```

**Enable PM2:**
```bash
./toggle_pm2.sh enable
# Then restart WebUI backend:
launchctl restart com.gridbot.webui.enhanced
```

---

## 🔧 Configuration File

**File:** `ecosystem.gridbot.config.js`

**Key settings:**
- **kill_timeout:** 30000 (30 seconds for graceful shutdown)
- **autorestart:** true (auto-restart on crash)
- **max_memory_restart:** "1G" (restart if memory > 1GB)

**You don't need to edit this** - it's already configured!

---

## 🚨 Troubleshooting

### Bot not starting?

```bash
# 1. Check PM2 status
pm2 list

# 2. Check logs
pm2 logs gridbot-live --lines 50 --nostream --err

# 3. Delete and restart
pm2 delete gridbot-live
./pm2_gridbot.sh start live
```

### WebUI shows "BAD REQUEST"?

```bash
# Restart WebUI backend
launchctl restart com.gridbot.webui.enhanced

# Wait 3 seconds, then try again
```

### Bot keeps restarting?

```bash
# Check error logs
pm2 logs gridbot-live --err --lines 30 --nostream

# Common issues:
# - Another bot already running (stop it first)
# - Missing dependencies (check error logs)
# - Config file issues
```

### Missing dependencies?

```bash
# Install missing Python packages
pip3 install -r requirements.txt
```

---

## 📚 Complete Documentation

**Detailed guides:**
- `PM2_WEBUI_INTEGRATION.md` - Complete WebUI integration docs
- `PM2_VS_TMUX_COMPARISON.md` - Feature comparison

**Just want to use it?** Use this Quick Start guide!

---

## 🎯 Summary - What You Need to Know

**To start bot:**
```bash
# Via WebUI: Click "Start Bot"
# OR via terminal:
./pm2_gridbot.sh start live
```

**To stop bot:**
```bash
# Via WebUI: Click "Stop Bot"  
# OR via terminal:
./pm2_gridbot.sh stop live
```

**To check status:**
```bash
pm2 list
```

**To view logs:**
```bash
pm2 logs gridbot-live
```

**That's it!** You don't need to know anything else to use PM2 effectively.

---

## 🎉 Benefits You'll Notice

1. **No more tmux sessions** - Just start/stop via WebUI
2. **Bot auto-recovers** - Crashes? PM2 restarts it
3. **Pending orders always cancelled** - 30s graceful shutdown
4. **See resource usage** - CPU and memory in real-time
5. **Better logs** - Centralized and easy to view

---

**Need help?** 
- Run: `pm2 list` to see current status
- Run: `pm2 logs gridbot-live` to see what's happening
- Check: http://localhost:5555 to use WebUI

**Production ready means:** Your bot can run reliably 24/7 with automatic crash recovery and proper cleanup!
