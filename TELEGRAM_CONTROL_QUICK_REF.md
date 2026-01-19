# Telegram Bot Control Commands - Quick Reference

**Last Updated:** January 19, 2026, 22:57

---

## ✅ What's Fixed

### 1. **Accurate Data Sources**
- ✅ Reading from `monitoring_snapshot_BTCUSD_LONG.json` (live data)
- ✅ Guardian status from event database (real signals)
- ✅ Real-time P&L (realized + unrealized)
- ✅ Actual positions with correct prices

### 2. **Bot Control Commands Added**
- ✅ `/startbot` - Start the grid bot
- ✅ `/stopbot` - Stop gracefully (30s timeout)
- ✅ `/killbot` - Emergency kill
- ✅ `/restart` - Restart bot

### 3. **Both Bots Running**
- ✅ Grid Bot handler: PID 83694
- ✅ Options Bot handler: PID 83916

---

## 🚀 Quick Start

### 1. Test Status Commands
```
/status    - See current bot state
/positions - List open positions
/pnl       - Check profit/loss
/guardian  - Guardian GO/STOP signal
```

### 2. Control Your Bot
```
/startbot  - Start grid bot
/stopbot   - Stop grid bot (graceful)
/killbot   - Emergency kill (if stuck)
/restart   - Restart bot
```

---

## 📊 Expected Outputs

### `/status` - Current State
```
🤖 Grid Bot Status

Mode: LONG
Symbol: BTCUSD
Current Price: $95,234.50

Positions:
• Open: 5
• Total Size: 25 contracts

Pending BUY: $92,500

🕐 Updated: 22:57:45
```

### `/positions` - Open Positions
```
📊 Open Positions (5)

Position 1:
• Entry: $95,000
• Size: 5
• TP: $95,500

Position 2:
• Entry: $94,500
• Size: 5
• TP: $95,000

...
```

### `/pnl` - Profit & Loss
```
💰 Profit & Loss

Realized P&L: $+245.75
Unrealized P&L: $+68.50
Total P&L: $+314.25

Positions:
• Opened: 10
• Closed: 5

🕐 Updated: 22:59:30
```

### `/guardian` - Risk Status
```
🟢 Guardian Status

Signal: GO
Reason: Market conditions normal
Last Update: 2026-01-19 22:45:30

✅ Trading is active
```

### `/startbot` - Start Bot
```
✅ Grid Bot Started Successfully

🔢 PID: 12345
📊 Check /status to verify

🕐 Started: 22:58:10
```

### `/stopbot` - Stop Bot
```
✅ Bot Stopped Successfully

🔢 PID: 12345
⏱️ Shutdown time: 5s

🕐 Stopped: 23:01:45

Use /startbot to restart
```

### `/killbot` - Emergency Kill
```
💀 Bot Killed (Emergency Stop)

🔢 PID: 12345
🕐 Killed: 23:05:15

⚠️ This was a forceful shutdown.
Check logs for any issues.

Use /startbot to restart
```

### `/restart` - Restart Bot
```
🔄 Bot Restarted Successfully

🔢 Old PID: 12345
🔢 New PID: 12789

📊 Check /status to verify

🕐 Restarted: 23:10:00
```

---

## ⚠️ Safety Notes

### Control Commands
1. **`/startbot`**
   - ✅ Safe - checks if already running
   - Uses official `bot_launcher.py --daemon`
   - Returns PID for monitoring

2. **`/stopbot`**
   - ✅ Safe - graceful SIGTERM
   - Waits up to 30 seconds for clean shutdown
   - Suggests `/killbot` if stuck

3. **`/killbot`**
   - ⚠️ Use with caution
   - Immediate SIGKILL (forceful)
   - Use only if `/stopbot` fails

4. **`/restart`**
   - ✅ Safe - combines stop + start
   - Waits for clean shutdown before restart
   - Falls back to kill if needed

---

## 🔍 Verification

### Check Handlers Are Running
```bash
ps aux | grep telegram_bot_commands
```

Should show:
- Grid bot handler (PID 83694)
- Options bot handler (PID 83916)

### Check Logs
```bash
# Grid bot commands
tail -f logs/telegram_grid_commands.log

# Options bot commands
tail -f logs/telegram_options_commands.log
```

### Test Commands
1. Send `/help` to both bots
2. Send `/status` to grid bot
3. Try a control command if bot is running

---

## 🛠️ Restart Handlers

If you need to restart the command handlers:

```bash
# Stop both handlers
pkill -f telegram_bot_commands

# Start grid bot handler
python3 bot/telegram_bot_commands.py --bot grid > logs/telegram_grid_commands.log 2>&1 &

# Start options bot handler
python3 bot/telegram_bot_commands.py --bot options > logs/telegram_options_commands.log 2>&1 &

# Verify running
ps aux | grep telegram_bot_commands
```

---

## 📞 Support Checklist

If commands aren't working properly:

- [ ] Check handlers are running: `ps aux | grep telegram_bot_commands`
- [ ] Check handler logs: `tail -f logs/telegram_grid_commands.log`
- [ ] Verify bot is running (for status commands): `ps aux | grep bot.run`
- [ ] Verify WebUI is running (for options): `curl http://localhost:5555/health`
- [ ] Check monitoring snapshot exists: `ls -la data/monitoring_snapshot*.json`
- [ ] Check event database exists: `ls -la data/bot_events_*.db`
- [ ] Send `/help` to verify bot responds
- [ ] Restart handlers if needed

---

## ✨ Key Improvements Made

### Data Sources Fixed
- ❌ Old: `system_state.json` (stale)
- ✅ New: `monitoring_snapshot_BTCUSD_LONG.json` (real-time)

### Guardian Fixed
- ❌ Old: `guardian_signal.json` (didn't exist)
- ✅ New: Event database query (real signals)

### P&L Fixed
- ❌ Old: Only basic realized P&L
- ✅ New: Realized + Unrealized + Total

### Control Added
- ✅ Start/Stop/Kill/Restart commands
- ✅ Process management via bot_launcher.py
- ✅ Safety checks and timeouts
- ✅ Real-time status verification

---

## 🎯 Next Steps

1. **Test all commands** in Telegram
2. **Verify data accuracy** - compare with WebUI
3. **Test control commands** when bot is running
4. **Monitor logs** for any issues
5. **Set up monitoring** - keep handlers running 24/7

**Ready to use! Try `/help` in Telegram now.** 🚀
