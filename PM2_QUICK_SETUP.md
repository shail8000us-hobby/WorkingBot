# PM2 Process Manager - Quick Setup Guide

## ✅ Problem Solved

The bot management system now has:

1. **✅ Clear Separation** - Each trading instrument has its own PM2 process
2. **✅ Guardian Auto-Start** - Guardian bot automatically starts with LaunchAgent
3. **✅ Easy Management** - Simple scripts for all operations
4. **✅ Production Ready** - Tested configuration with proper logging

## 🎯 What Was Created

### 1. **ecosystem.production.config.js** - PM2 Configuration
Location: `/Users/ssr/Projects/WorkingBot/ecosystem.production.config.js`

Defines 6 separate processes:
- `gridbot-btc-long` - BTC LONG trading
- `gridbot-btc-short` - BTC SHORT trading  
- `gridbot-eth-long` - ETH LONG trading
- `gridbot-eth-short` - ETH SHORT trading
- `guardian-live` - Risk monitoring (auto-restart enabled)
- `webui-backend` - Web interface (auto-restart enabled)

### 2. **pm2_manager.sh** - Management Script
Location: `/Users/ssr/Projects/WorkingBot/pm2_manager.sh`

Easy commands for all operations:
```bash
./pm2_manager.sh start btc-long    # Start BTC LONG
./pm2_manager.sh stop btc-long     # Stop BTC LONG
./pm2_manager.sh status            # Show all processes
./pm2_manager.sh logs btc-long     # View logs
```

### 3. **com.gridbot.guardian.plist** - LaunchAgent for Guardian
Location: `/Users/ssr/Projects/WorkingBot/com.gridbot.guardian.plist`

Ensures guardian bot starts automatically:
- Runs on system boot
- Auto-restarts if it crashes
- Monitors all trading bots 24/7

### 4. **quick_start.sh** - Interactive Setup
Location: `/Users/ssr/Projects/WorkingBot/quick_start.sh`

Interactive menu for easy startup:
```bash
./quick_start.sh
```

### 5. **PM2_PROCESS_MANAGER_GUIDE.md** - Complete Documentation
Location: `/Users/ssr/Projects/WorkingBot/PM2_PROCESS_MANAGER_GUIDE.md`

Full documentation with examples and troubleshooting.

## 🚀 How to Start Trading

### Option 1: Quick Start (Recommended)
```bash
cd /Users/ssr/Projects/WorkingBot
./quick_start.sh
```

Select from the menu:
1. Start Guardian + WebUI (recommended first)
2. Start BTC LONG bot
3. Start all trading bots
etc.

### Option 2: Manual Start
```bash
# Start guardian (monitors all bots)
./pm2_manager.sh start guardian

# Start WebUI
./pm2_manager.sh start webui

# Start BTC LONG trading
./pm2_manager.sh start btc-long

# Check status
./pm2_manager.sh status
```

### Option 3: Start Everything
```bash
./pm2_manager.sh start all
```

## 📊 Check Status

```bash
# View all processes
./pm2_manager.sh status

# Output example:
┌────┬──────────────────┬─────────────┬─────────┬─────────┬──────────┐
│ id │ name             │ mode        │ pid     │ status  │ cpu      │
├────┼──────────────────┼─────────────┼─────────┼─────────┼──────────┤
│ 0  │ gridbot-btc-long │ fork        │ 12345   │ online  │ 0%       │
│ 1  │ guardian-live    │ fork        │ 12346   │ online  │ 0%       │
│ 2  │ webui-backend    │ fork        │ 12347   │ online  │ 0%       │
└────┴──────────────────┴─────────────┴─────────┴─────────┴──────────┘
```

## 📝 View Logs

```bash
# Tail specific bot logs
./pm2_manager.sh logs btc-long

# View all logs
./pm2_manager.sh logs

# Real-time dashboard
./pm2_manager.sh monit
```

## 🛑 Stop Trading

```bash
# Stop specific bot
./pm2_manager.sh stop btc-long

# Stop all trading bots (keep guardian & webui)
./pm2_manager.sh stop all-bots

# Stop everything
./pm2_manager.sh stop all
```

## 🔄 Restart Bots

```bash
# Restart specific bot
./pm2_manager.sh restart btc-long

# Restart all trading bots
./pm2_manager.sh restart all-bots
```

## 🤖 Guardian Auto-Start Setup

To make guardian start automatically on system boot:

```bash
# Install LaunchAgent
cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist

# Check if running
launchctl list | grep gridbot.guardian

# Should show something like:
# 829     0       com.gridbot.webui.guardian
```

## 🎮 WebUI Integration

The PM2 Process Manager tab in WebUI (http://localhost:5555) will show:

- **By Symbol** section with 4 separate processes:
  - BTC LONG
  - BTC SHORT
  - ETH LONG
  - ETH SHORT
- Individual start/stop controls for each
- Real-time status and memory usage

## 📁 Log Files

Each process has separate log files in `logs/`:

```
logs/pm2-gridbot-btc-long-out.log
logs/pm2-gridbot-btc-long-error.log
logs/pm2-gridbot-btc-short-out.log
logs/pm2-gridbot-btc-short-error.log
logs/pm2-gridbot-eth-long-out.log
logs/pm2-gridbot-eth-long-error.log
logs/pm2-gridbot-eth-short-out.log
logs/pm2-gridbot-eth-short-error.log
logs/pm2-guardian-live-out.log
logs/pm2-guardian-live-error.log
```

## ⚠️ Important Notes

### Trading Bot Auto-Restart: Disabled
Trading bots do **NOT** auto-restart by design:
- Requires manual intervention to diagnose issues
- Prevents runaway processes during errors
- Guardian monitors and alerts on crashes

### Guardian Auto-Restart: Enabled
Guardian **DOES** auto-restart:
- Critical monitoring function
- No order execution risk
- Must stay running 24/7

### Separate Processes = Separate Everything
Each bot has:
- Its own memory space (no conflicts)
- Its own log files (easy debugging)
- Its own configuration (from config.yaml)
- Its own state management

## 🔧 How It Works

### Bot Startup Flow

1. **PM2 starts the bot** with symbol argument:
   ```
   python3 bot/strategy/async_gridbot.py BTCUSD
   ```

2. **Bot reads config.yaml** and finds matching instance:
   ```yaml
   instances:
     BTCUSD_LONG:
       symbol: BTCUSD
       mode: LONG
       enabled: true
       # ... config ...
   ```

3. **Bot uses instance-specific config** for:
   - Grid parameters (lower, upper, step)
   - Position limits
   - Safety thresholds
   - RSI parameters

4. **Bot stores data in separate files**:
   - `data/bot_events_BTCUSD_LONG.db` (SQLite)
   - `data/runtime_state_BTCUSD_LONG.json`
   - `logs/pm2-gridbot-btc-long-out.log`

### Guardian Monitors All Bots

Guardian bot:
- Runs as single process
- Monitors ALL trading instruments
- Publishes GO/STOP signals to database
- Each trading bot reads Guardian signals
- Auto-restarts if it crashes

## 🐛 Troubleshooting

### Bot Won't Start

```bash
# Check PM2 logs
./pm2_manager.sh logs btc-long

# Look for errors like:
# - Config file not found
# - API key missing
# - Port already in use
```

### PM2 Shows "errored" Status

```bash
# Delete and restart
pm2 delete gridbot-btc-long
./pm2_manager.sh start btc-long
```

### Guardian Not Running

```bash
# Check LaunchAgent
launchctl list | grep gridbot.guardian

# View logs
tail -f logs/launchagent-guardian.log

# Reload agent
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
```

### No Processes Show Up

```bash
# PM2 might not be installed or configured
npm install -g pm2

# Or check if PM2 is running
which pm2
pm2 --version
```

## 📚 Next Steps

1. **Start Guardian + WebUI** first:
   ```bash
   ./quick_start.sh
   # Select option 1
   ```

2. **Verify Guardian is working**:
   ```bash
   ./pm2_manager.sh logs guardian
   ```

3. **Start one trading bot** to test:
   ```bash
   ./pm2_manager.sh start btc-long
   ```

4. **Monitor in WebUI**:
   - Open http://localhost:5555
   - Go to "PM2 Process Manager" tab
   - See bot status and controls

5. **Check logs regularly**:
   ```bash
   ./pm2_manager.sh logs btc-long
   ```

## 🎉 Summary

You now have a production-ready multi-instrument trading system with:

✅ **Clear Separation** - Each instrument runs independently  
✅ **Guardian Monitoring** - 24/7 risk monitoring with auto-restart  
✅ **Easy Management** - Simple commands for all operations  
✅ **WebUI Integration** - Visual monitoring and control  
✅ **Proper Logging** - Separate log files per instrument  
✅ **Auto-Recovery** - Guardian restarts automatically

All tools are ready to use. Start trading with confidence! 🚀
