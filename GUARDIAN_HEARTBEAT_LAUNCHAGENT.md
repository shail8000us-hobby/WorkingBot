# Guardian & Heartbeat LaunchAgent Setup

**Last Updated:** December 9, 2025  
**Status:** Production Ready ✅

## 📋 Overview

This document describes the automatic startup configuration for the Guardian Bot and Heartbeat Monitor using macOS LaunchAgents. These services will start automatically at boot and restart if they crash.

## 🎯 What's Included

### Services

1. **Guardian Bot** (`com.workingbot.guardian`)
   - 24/7 risk monitoring
   - Volatility checks (IV/RV)
   - Loss limit enforcement
   - Liquidation distance monitoring
   - Publishes GO/STOP signals to SQL database
   - Auto-restart on crash

2. **Heartbeat Monitor** (`com.workingbot.heartbeat`)
   - Watches bot health via `.heartbeat` file
   - Cancels pending orders if bot crashes
   - Dead man's switch protection
   - Auto-restart on crash

### Management Scripts

- `install_guardian_heartbeat.sh` - Install both services
- `check_guardian_status.sh` - Check service status and logs
- `uninstall_guardian_heartbeat.sh` - Remove both services

### Configuration Files

- `launchagents/com.workingbot.guardian.plist` - Guardian LaunchAgent
- `launchagents/com.workingbot.heartbeat.plist` - Heartbeat LaunchAgent

## 🚀 Installation

### Quick Install

```bash
cd /Users/ssr/Projects/WorkingBot
./install_guardian_heartbeat.sh
```

The installer will:
1. ✅ Check that bot files exist
2. ✅ Create log directories
3. ✅ Copy plist files to `~/Library/LaunchAgents/`
4. ✅ Set proper permissions
5. ✅ Unload any existing services
6. ✅ Load the new services
7. ✅ Verify services are running

### What Happens After Installation

Both services will:
- ✅ Start immediately
- ✅ Start automatically at boot
- ✅ Restart automatically if they crash
- ✅ Wait 30 seconds between restart attempts (throttling)
- ✅ Log to `bot/logs/launchagent_*.log`

## 📊 Service Management

### Check Status

```bash
# Quick status check
./check_guardian_status.sh

# Manual check
launchctl list | grep workingbot
```

### View Logs

```bash
# Guardian logs
tail -f bot/logs/launchagent_guardian.log
tail -f bot/logs/launchagent_guardian_error.log

# Heartbeat logs
tail -f bot/logs/launchagent_heartbeat.log
tail -f bot/logs/launchagent_heartbeat_error.log
```

### Restart Services

```bash
# Restart Guardian
launchctl kickstart -k gui/$(id -u)/com.workingbot.guardian

# Restart Heartbeat
launchctl kickstart -k gui/$(id -u)/com.workingbot.heartbeat
```

### Stop Services

```bash
# Stop Guardian
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Stop Heartbeat
launchctl unload ~/Library/LaunchAgents/com.workingbot.heartbeat.plist
```

### Start Services

```bash
# Start Guardian
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Start Heartbeat
launchctl load ~/Library/LaunchAgents/com.workingbot.heartbeat.plist
```

## 🗑️ Uninstallation

```bash
cd /Users/ssr/Projects/WorkingBot
./uninstall_guardian_heartbeat.sh
```

This will:
1. Unload both services
2. Remove plist files from `~/Library/LaunchAgents/`
3. Keep log files for reference

## 🔧 Configuration

### Guardian Configuration

**File:** `launchagents/com.workingbot.guardian.plist`

**Key Settings:**
- **RunAtLoad:** `true` - Start at boot
- **KeepAlive:** `SuccessfulExit: false` - Restart on crash
- **ThrottleInterval:** `30` seconds - Wait between restarts
- **Nice:** `-5` - Higher priority process
- **TRADING_MODE:** `live` - Uses live trading configuration

### Heartbeat Configuration

**File:** `launchagents/com.workingbot.heartbeat.plist`

**Key Settings:**
- **RunAtLoad:** `true` - Start at boot
- **KeepAlive:** `SuccessfulExit: false` - Restart on crash
- **ThrottleInterval:** `30` seconds - Wait between restarts
- **Nice:** `0` - Normal priority
- **TRADING_MODE:** `live` - Uses live trading configuration

### Environment Variables

Both services have:
- `PYTHONPATH=/Users/ssr/Projects/WorkingBot`
- `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`
- `PYTHONUNBUFFERED=1` - Immediate log output
- `TRADING_MODE=live` - Live trading mode

## 📁 File Locations

### LaunchAgent Files
```
~/Library/LaunchAgents/
├── com.workingbot.guardian.plist
└── com.workingbot.heartbeat.plist
```

### Log Files
```
/Users/ssr/Projects/WorkingBot/bot/logs/
├── launchagent_guardian.log
├── launchagent_guardian_error.log
├── launchagent_heartbeat.log
└── launchagent_heartbeat_error.log
```

### PID Files
```
/Users/ssr/Projects/WorkingBot/
├── .guardian.pid        # Guardian process ID
└── .heartbeat           # Bot heartbeat JSON
```

## 🐛 Troubleshooting

### Guardian Not Starting

```bash
# Check status
./check_guardian_status.sh

# Check error log
tail -50 bot/logs/launchagent_guardian_error.log

# Try manual start
python3 bot/guardian/core/guardian_bot.py

# If manual start works, reload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
```

### Heartbeat Not Starting

```bash
# Check status
./check_guardian_status.sh

# Check error log
tail -50 bot/logs/launchagent_heartbeat_error.log

# Try manual start
python3 bot/heartbeat/monitor.py

# If manual start works, reload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.workingbot.heartbeat.plist
launchctl load ~/Library/LaunchAgents/com.workingbot.heartbeat.plist
```

### Service Keeps Crashing

If a service crashes repeatedly, LaunchAgent will throttle restarts (30 second delay).

**Check logs for errors:**
```bash
# Last 100 lines of error log
tail -100 bot/logs/launchagent_guardian_error.log
tail -100 bot/logs/launchagent_heartbeat_error.log
```

**Common issues:**
1. **Python dependencies missing** - Run `pip3 install -r requirements.txt`
2. **Config file issues** - Check `config.yaml` is valid
3. **API credentials missing** - Check `secrets/api_keys.env`
4. **Database locked** - Bot may be running separately, stop with `pm2 stop all`

### Permission Issues

```bash
# Fix plist permissions
chmod 644 ~/Library/LaunchAgents/com.workingbot.guardian.plist
chmod 644 ~/Library/LaunchAgents/com.workingbot.heartbeat.plist

# Fix script permissions
chmod +x install_guardian_heartbeat.sh
chmod +x check_guardian_status.sh
chmod +x uninstall_guardian_heartbeat.sh
```

## ⚙️ Advanced Configuration

### Change Trading Mode

To change from `live` to `demo`, edit the plist file:

```bash
# Edit Guardian plist
nano ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Change this line:
<key>TRADING_MODE</key>
<string>live</string>

# To:
<key>TRADING_MODE</key>
<string>demo</string>

# Reload service
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
```

### Adjust Restart Throttle

Default is 30 seconds between restart attempts. To change:

```bash
nano ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Change:
<key>ThrottleInterval</key>
<integer>30</integer>

# Reload
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
```

### Change Process Priority

Guardian runs at higher priority (`Nice: -5`). To adjust:

```bash
nano ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Change:
<key>Nice</key>
<integer>-5</integer>

# Range: -20 (highest priority) to 20 (lowest priority)
# Normal processes run at 0
```

## 🔄 Integration with PM2

The trading bot continues to run via PM2 (manual start):

```bash
# Start trading bot (manual)
pm2 start ecosystem.config.js --only gridbot-live

# Guardian and Heartbeat run automatically via LaunchAgent
# They don't need PM2!
```

### Why LaunchAgent for Guardian/Heartbeat?

1. **Start at Boot** - LaunchAgent starts before user login
2. **System Integration** - Better OS integration than PM2
3. **Reliable Restart** - macOS handles crash detection
4. **No PM2 Dependency** - Works even if PM2 fails
5. **Separation of Concerns** - Safety systems independent of trading bot

## 📊 Monitoring

### Health Check Commands

```bash
# Quick check
./check_guardian_status.sh

# Check Guardian PID
cat .guardian.pid
ps -p $(cat .guardian.pid)

# Check Heartbeat file
cat .heartbeat | python3 -m json.tool

# Check SQL signals
sqlite3 data/bot_events_LONG.db "SELECT * FROM guardian_signal ORDER BY timestamp DESC LIMIT 1;"
```

### Expected Output

**Healthy System:**
```
Guardian:
  Status: ✅ LOADED
  PID: 12345
  Process: ✅ RUNNING
  Errors: ✅ No errors

Heartbeat:
  Status: ✅ LOADED
  PID: 12346
  Process: ✅ RUNNING
  Errors: ✅ No errors
```

## 🎯 Quick Reference

```bash
# INSTALL
./install_guardian_heartbeat.sh

# CHECK STATUS
./check_guardian_status.sh
launchctl list | grep workingbot

# VIEW LOGS
tail -f bot/logs/launchagent_guardian.log
tail -f bot/logs/launchagent_heartbeat.log

# RESTART
launchctl kickstart -k gui/$(id -u)/com.workingbot.guardian
launchctl kickstart -k gui/$(id -u)/com.workingbot.heartbeat

# UNINSTALL
./uninstall_guardian_heartbeat.sh
```

## ✅ Success Checklist

After installation, verify:

- [ ] `./check_guardian_status.sh` shows both services RUNNING
- [ ] `launchctl list | grep workingbot` shows 2 services
- [ ] `.guardian.pid` file exists
- [ ] Guardian logs show "🛡️ Guardian Bot Starting"
- [ ] Heartbeat logs show "🔍 Heartbeat Monitor Starting"
- [ ] No errors in `*_error.log` files
- [ ] Services survive a reboot (test with `sudo reboot`)

## 📝 Notes

- **No Manual Start Required** - Services start automatically at boot
- **Independent of PM2** - These services don't use PM2
- **Trading Bot Separate** - Trading bot still uses PM2 (manual start)
- **Log Rotation** - Consider setting up log rotation if logs get large
- **Updates** - After updating bot code, restart services with `launchctl kickstart`

## 🔗 Related Documentation

- `AI_CONTEXT.md` - Complete project overview
- `backend_frontend.md` - Port configuration and WebUI
- `PM2_QUICK_START.md` - PM2 process management for trading bot
- `config.yaml` - Bot configuration file

---

**For Support:** Check logs first, then review troubleshooting section above.

**Last Updated:** December 9, 2025  
**Version:** 1.0  
**Status:** ✅ Production Ready

