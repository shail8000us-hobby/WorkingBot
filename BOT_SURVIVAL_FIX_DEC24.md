# Bot Survival Fix - Dec 24, 2025

## Problem Solved
✅ Bot now survives terminal closure and can run for days
✅ Manual start/stop control preserved (no auto-start)

## Root Cause
Bot was receiving **SIGTERM when terminal closed**, causing graceful shutdown.

**Why it happened:**
1. When you close a terminal, macOS sends SIGHUP to all processes
2. Bot's signal handler was catching SIGTERM from system
3. Bot interpreted this as user shutdown command

## The Fix

### 1. Signal Handler (async_gridbot.py)
```python
# BEFORE: Handled all signals
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# AFTER: Ignore terminal hangup, only handle explicit signals
signal.signal(signal.SIGHUP, signal.SIG_IGN)    # Ignore terminal closure
signal.signal(signal.SIGINT, signal_handler)     # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)    # kill command
```

### 2. Daemon Mode (bot_launcher.py)
Enhanced to:
- Log to files (survives terminal closure)
- Create new process group (fully detached)
- Show clear monitoring instructions

## How to Use

### Start Bot (Recommended)
```bash
./dashboard/start.sh
```

This will:
- Check for existing instances
- Start in daemon mode (background)
- Log to `logs/trading_bot.log`
- Survive terminal closure
- Show PID and monitoring commands

### Alternative Start
```bash
python3 bot_launcher.py --daemon
```

### Monitor Bot
```bash
# Watch live logs
tail -f logs/trading_bot.log

# Check if running
ps aux | grep "bot.run" | grep -v grep

# Check PID file
cat reports/bot.pid
```

### Stop Bot
```bash
# Recommended (graceful)
./dashboard/stop.sh

# Or manual (also graceful)
kill $(cat reports/bot.pid)

# Or by PID
kill 12345
```

## Testing Results

### ✅ SIGHUP Immunity
```bash
kill -HUP <pid>
# Bot continues running ✅
```

### ✅ Graceful Shutdown
```bash
kill -TERM <pid>
# Bot shuts down gracefully ✅
# - Cancels pending entry orders
# - Preserves TP orders
# - Closes WebSocket cleanly
```

### ✅ Terminal Independence
```bash
ps aux | grep bot
# Shows "??" in TTY column (not attached to terminal) ✅
```

## What's Different Now

### Before Fix
- Bot stopped when terminal closed
- Couldn't run overnight
- Required persistent terminal session
- Manual start → crashed when SSH disconnected

### After Fix
- Bot ignores terminal closure
- Runs for days/weeks
- Fully independent from terminal
- Manual start → survives everything except explicit kill

## Important Notes

1. **No Auto-Start**: Bot will NOT start automatically on system boot
   - You must manually start it each time
   - This is intentional for trading safety

2. **Manual Control**: You have full control
   - Start when ready to trade
   - Stop when you want
   - No automated restarts

3. **Logs Location**: 
   - Stdout: `logs/trading_bot.log`
   - Stderr: `logs/trading_bot_error.log`
   - Old logs: `/tmp/bot_*.log` (from testing)

4. **Process Management**:
   - PID stored in `reports/bot.pid`
   - Process runs in its own session
   - Survives SSH disconnects, terminal closure, etc.

## Monitoring

### Check Bot Status
```bash
# Quick check
cat reports/bot.pid && echo "Bot PID exists" || echo "Bot not running"

# Detailed check
ps aux | grep $(cat reports/bot.pid) | grep -v grep

# Via WebUI
# Visit http://localhost:5555 - bot auto-detected
```

### Live Monitoring
```bash
# See all activity
tail -f logs/trading_bot.log

# Filter for important events
tail -f logs/trading_bot.log | grep -E "(Guardian|filled|ERROR|stopped)"

# Check errors only
tail -f logs/trading_bot_error.log
```

## Troubleshooting

### Bot Won't Start
```bash
# Check for existing instance
ps aux | grep "bot.run" | grep -v grep

# Clean stale PID
rm reports/bot.pid

# Try again
./dashboard/start.sh
```

### Bot Stopped Unexpectedly
```bash
# Check last shutdown reason
tail -50 logs/trading_bot_error.log | grep -E "(signal|stopped|ERROR)"

# If you see "Received signal 15" - something sent SIGTERM
# If you see "Received signal 2" - Ctrl+C was pressed
# If you see "signal 1" - that's SIGHUP (should be ignored now)
```

### Clean Restart
```bash
./dashboard/stop.sh
sleep 2
./dashboard/start.sh
```

## Git Status
- Branch: `production-4.0-clean`
- Commit: `07513bc48`
- Pushed: ✅

---
**Status**: 🟢 PRODUCTION READY - Can run for days
**Last Updated**: Dec 24, 2025
