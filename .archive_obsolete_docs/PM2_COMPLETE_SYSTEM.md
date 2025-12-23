# PM2 Complete System - GridBot + Guardian + Heartbeat

**Last Updated:** November 3, 2025

---

## 🎯 Complete System Overview

Your trading system has **5 components** that can all run via PM2:

### 1️⃣ **GridBot (Live)** - Main Trading Bot
- **Purpose:** Executes live trades with real money
- **PM2 Name:** `gridbot-live`
- **Auto-restart:** Yes (on crash)
- **Graceful shutdown:** 30 seconds (cancels pending orders)

### 2️⃣ **GridBot (Demo)** - Paper Trading Bot
- **Purpose:** Practice trading with demo account
- **PM2 Name:** `gridbot-demo`
- **Auto-restart:** Yes (on crash)
- **Graceful shutdown:** 30 seconds

### 3️⃣ **Guardian (Live)** - Position Protection
- **Purpose:** Monitors positions and prevents liquidation
- **PM2 Name:** `guardian-live`
- **Auto-restart:** Yes
- **Shutdown:** 15 seconds

### 4️⃣ **Guardian (Demo)** - Demo Position Protection
- **Purpose:** Same as live guardian but for demo account
- **PM2 Name:** `guardian-demo`
- **Auto-restart:** Yes
- **Shutdown:** 15 seconds

### 5️⃣ **Heartbeat Monitor** - Health Monitoring
- **Purpose:** Monitors system health and bot status
- **PM2 Name:** `heartbeat`
- **Auto-restart:** Yes
- **Shutdown:** 5 seconds

---

## 🚀 Quick Start - Running Everything

### Start All Components at Once:
```bash
./pm2_gridbot.sh start all
```

This starts:
- ✅ gridbot-live
- ✅ gridbot-demo
- ✅ guardian-live
- ✅ guardian-demo
- ✅ heartbeat

---

## 🎮 Individual Component Control

### Start Individual Components:
```bash
# Trading bots
./pm2_gridbot.sh start live           # Live trading only
./pm2_gridbot.sh start demo           # Demo trading only

# Guardian protection
./pm2_gridbot.sh start guardian-live  # Live guardian
./pm2_gridbot.sh start guardian-demo  # Demo guardian

# Monitoring
./pm2_gridbot.sh start heartbeat      # Heartbeat monitor
```

### Stop Individual Components:
```bash
./pm2_gridbot.sh stop live            # Stop live trading
./pm2_gridbot.sh stop guardian-live   # Stop live guardian
./pm2_gridbot.sh stop heartbeat       # Stop heartbeat
```

### Stop Everything:
```bash
./pm2_gridbot.sh stop all
```

---

## 📊 Monitoring All Components

### See All Running Processes:
```bash
pm2 list
```

**Example output:**
```
┌────┬──────────────────┬─────────┬──────┬───────────┬──────┬─────────┐
│ id │ name             │ pid     │ ↺    │ status    │ cpu  │ memory  │
├────┼──────────────────┼─────────┼──────┼───────────┼──────┼─────────┤
│ 0  │ gridbot-live     │ 27759   │ 0    │ online    │ 3.7% │ 21.1mb  │
│ 1  │ gridbot-demo     │ 27801   │ 0    │ online    │ 2.1% │ 18.3mb  │
│ 2  │ guardian-live    │ 27845   │ 0    │ online    │ 1.2% │ 12.5mb  │
│ 3  │ guardian-demo    │ 27889   │ 0    │ online    │ 0.8% │ 11.2mb  │
│ 4  │ heartbeat        │ 27923   │ 0    │ online    │ 0.1% │ 8.1mb   │
└────┴──────────────────┴─────────┴──────┴───────────┴──────┴─────────┘
```

### Real-Time Dashboard:
```bash
pm2 monit
```

Shows:
- Live CPU/Memory graphs for each component
- Live log output
- Process status
- Press `q` to exit

---

## 📝 Viewing Logs

### All Logs Together:
```bash
pm2 logs
```

### Individual Component Logs:
```bash
pm2 logs gridbot-live      # Trading bot logs
pm2 logs guardian-live     # Guardian logs
pm2 logs heartbeat         # Heartbeat logs
```

### Via Script:
```bash
./pm2_gridbot.sh logs live
./pm2_gridbot.sh logs guardian-live
./pm2_gridbot.sh logs heartbeat
```

---

## 🔄 Typical Usage Patterns

### 🟢 **Full Production Setup (Live Trading):**
```bash
# Start live trading with full protection
./pm2_gridbot.sh start live           # Trading bot
./pm2_gridbot.sh start guardian-live  # Position protection
./pm2_gridbot.sh start heartbeat      # Health monitoring

# Check status
pm2 list

# Monitor
pm2 monit
```

### 🔵 **Demo/Testing Setup:**
```bash
# Start demo with protection
./pm2_gridbot.sh start demo
./pm2_gridbot.sh start guardian-demo
./pm2_gridbot.sh start heartbeat

# Check status
pm2 list
```

### 🟣 **Full System (Both Live and Demo):**
```bash
# Start everything
./pm2_gridbot.sh start all

# Check status
pm2 list
```

---

## 🛡️ What Each Component Does

### GridBot (Live/Demo):
- ✅ Executes grid trading strategy
- ✅ Places buy/sell orders
- ✅ Manages positions (up to 10)
- ✅ Handles fills and order tracking
- ✅ Graceful shutdown cancels pending orders

### Guardian (Live/Demo):
- 🛡️ Monitors margin utilization
- 🛡️ Tracks liquidation distance
- 🛡️ Monitors mark-to-market (MTM)
- 🛡️ Sends alerts if positions are at risk
- 🛡️ Can emergency close positions if needed

### Heartbeat:
- 💓 Updates `.heartbeat` file every 5 seconds
- 💓 Confirms system is alive
- 💓 Tracks process health
- 💓 Used by monitoring tools

---

## 🔐 Component Dependencies

### Live Trading Setup:
```
GridBot-Live (Required)
    ↓
Guardian-Live (Recommended - protection)
    ↓
Heartbeat (Optional - monitoring)
```

### Can Run Independently:
- ✅ GridBot alone (no guardian)
- ✅ Guardian alone (monitors existing positions)
- ✅ Heartbeat alone (just monitoring)

### Recommended Setup:
```bash
# For live trading, always run:
./pm2_gridbot.sh start live
./pm2_gridbot.sh start guardian-live
./pm2_gridbot.sh start heartbeat
```

---

## 📂 Log File Locations

All logs saved to `reports/` directory:

### GridBot Logs:
- `reports/pm2-gridbot-live-out.log` - Live bot output
- `reports/pm2-gridbot-live-error.log` - Live bot errors
- `reports/pm2-gridbot-demo-out.log` - Demo bot output
- `reports/pm2-gridbot-demo-error.log` - Demo bot errors

### Guardian Logs:
- `reports/pm2-guardian-live-out.log` - Live guardian output
- `reports/pm2-guardian-live-error.log` - Live guardian errors
- `reports/pm2-guardian-demo-out.log` - Demo guardian output
- `reports/pm2-guardian-demo-error.log` - Demo guardian errors

### Heartbeat Logs:
- `reports/pm2-heartbeat-out.log` - Heartbeat output
- `reports/pm2-heartbeat-error.log` - Heartbeat errors

---

## ⚙️ Configuration File

All components configured in: `ecosystem.gridbot.config.js`

**Key settings for each component:**

| Component | Kill Timeout | Auto-Restart | Memory Limit |
|-----------|-------------|--------------|--------------|
| GridBot   | 30s         | Yes          | 1GB          |
| Guardian  | 15s         | Yes          | 512MB        |
| Heartbeat | 5s          | Yes          | 256MB        |

---

## 🔧 Advanced Commands

### Restart All Components:
```bash
./pm2_gridbot.sh restart all
```

### Restart Individual Component:
```bash
./pm2_gridbot.sh restart live
./pm2_gridbot.sh restart guardian-live
```

### Flush All Logs:
```bash
./pm2_gridbot.sh flush
```

### Save Current State (Auto-restart after reboot):
```bash
./pm2_gridbot.sh save
```

### Enable Auto-Start on Mac Reboot:
```bash
./pm2_gridbot.sh startup
# Follow the instructions shown
```

---

## 📱 WebUI Integration

### WebUI Bot Control:
When you use the WebUI (http://localhost:5555):

- **"Start Bot"** → Starts `gridbot-live` via PM2
- **"Stop Bot"** → Gracefully stops via PM2 (30s timeout)
- **"Restart Bot"** → PM2 restart

### WebUI Status:
The WebUI shows:
- ✅ Bot running status
- ✅ PM2 managed indicator
- ✅ CPU and memory usage
- ✅ Restart count

**WebUI automatically uses PM2** when `USE_PM2=true` is set.

---

## 🚨 Troubleshooting

### Component Won't Start?
```bash
# 1. Check status
pm2 list

# 2. Check logs
pm2 logs <component-name> --err --lines 50 --nostream

# 3. Delete and restart
pm2 delete <component-name>
./pm2_gridbot.sh start <component-name>
```

### All Components Restarting?
```bash
# Check error logs
pm2 logs --err --lines 100 --nostream

# Common issues:
# - Missing Python packages
# - Config file errors
# - Port conflicts
```

### Check Specific Component Health:
```bash
pm2 describe gridbot-live
pm2 describe guardian-live
pm2 describe heartbeat
```

---

## ✅ Health Check Commands

### Quick Status Check:
```bash
pm2 list
```

### Detailed Check:
```bash
# Check all components are online
pm2 list | grep online

# Check restart counts (should be 0 or low)
pm2 list

# Check logs for errors
pm2 logs --err --lines 20 --nostream
```

---

## 🎯 Summary - What You Need to Know

### To Start Everything:
```bash
./pm2_gridbot.sh start all
```

### To Check Status:
```bash
pm2 list
```

### To View Logs:
```bash
pm2 logs
```

### To Stop Everything:
```bash
./pm2_gridbot.sh stop all
```

### To Monitor Real-Time:
```bash
pm2 monit
```

**That's it!** You now have a complete production-ready trading system with:
- ✅ Auto-restart on crashes
- ✅ Graceful shutdown with order cancellation
- ✅ Position protection via Guardian
- ✅ Health monitoring via Heartbeat
- ✅ Real-time monitoring and logs
- ✅ Can run 24/7 reliably

---

## 📚 Related Documentation

- **PM2_QUICK_START.md** - Quick start guide
- **PM2_WEBUI_INTEGRATION.md** - WebUI integration details
- **PM2_VS_TMUX_COMPARISON.md** - Why PM2 is better than tmux

---

**Need Help?**
- Run: `./pm2_gridbot.sh help`
- Check: `pm2 list` for status
- View: `pm2 logs` for what's happening

**Your complete trading system is now production-ready with PM2!** 🚀
