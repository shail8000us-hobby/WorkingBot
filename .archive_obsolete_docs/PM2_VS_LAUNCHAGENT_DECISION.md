# PM2 vs LaunchAgent: Guardian Management Strategy

**Date:** November 10, 2025  
**Decision:** Use LaunchAgent for Guardian, PM2 for Trading Bot

---

## Issue Encountered

After implementing Guardian LaunchAgent, PM2 started **duplicate guardian processes**:
- LaunchAgent guardian: PID 10745 ✅
- PM2 guardian-live: PID 16167 ❌
- PM2 guardian-demo: PID 16170 ❌

**Result:** 3 guardian processes running simultaneously (wasteful, confusing)

---

## Solution Applied

**Removed guardian from PM2 ecosystem:**
```bash
pm2 stop guardian-live guardian-demo
pm2 delete guardian-live guardian-demo
pm2 save
```

**Result:** Only LaunchAgent guardian remains (PID 10745)

---

## PM2 vs LaunchAgent Comparison

### LaunchAgent (macOS Native)

**Advantages:**
- ✅ **System-level integration** - starts on boot automatically
- ✅ **Runs without user login** - survives logout/reboot
- ✅ **Native process management** - macOS handles it
- ✅ **Persistent across sessions** - always running
- ✅ **Lower overhead** - no PM2 daemon needed
- ✅ **Simple logs** - stdout/stderr to files

**Disadvantages:**
- ❌ Platform-specific (macOS only)
- ❌ No built-in monitoring dashboard
- ❌ Harder to check status (launchctl commands)
- ❌ No live log viewing (tail -f required)

**Best For:**
- System services
- Background daemons
- Services that must survive reboots
- Long-running processes

### PM2 (Process Manager)

**Advantages:**
- ✅ **Cross-platform** (Linux, macOS, Windows)
- ✅ **Rich dashboard** - `pm2 monit`, `pm2 status`
- ✅ **Easy log viewing** - `pm2 logs`
- ✅ **Cluster mode** - multiple instances
- ✅ **Environment management** - per-process env vars
- ✅ **Ecosystem file** - config-based setup

**Disadvantages:**
- ❌ PM2 daemon must be running
- ❌ Additional overhead (PM2 process)
- ❌ May not survive system reboot (depends on startup script)
- ❌ User-session dependent (unless configured otherwise)

**Best For:**
- Development workflow
- Multiple app instances
- Apps needing easy restarts
- When you need monitoring dashboard

---

## Current Architecture

### ✅ RECOMMENDED SETUP

#### LaunchAgent Managed (System-Level)
```
1. WebUI (com.gridbot.webui)
   - Port: 5555
   - Auto-start: Yes
   - Auto-restart: On crash
   
2. Guardian Bot (com.gridbot.guardian)
   - Monitors: Trading bot health
   - Auto-start: Yes
   - Auto-restart: Always
   - Priority: High (Nice: -5)
```

#### PM2 Managed (User-Level)
```
1. Trading Bot (gridbot-live)
   - Main trading logic
   - PID: 16164
   - Status: online
   
2. Heartbeat (heartbeat)
   - System monitoring
   - PID: 16173
   - Status: online
```

---

## Why This Split?

### WebUI → LaunchAgent ✅
**Reason:** Must be accessible even when not logged in
- Remote access requirement
- System monitoring 24/7
- Independent of user session

### Guardian → LaunchAgent ✅
**Reason:** Must protect trading bot at all times
- System-level protection
- Cannot fail if PM2 crashes
- Higher priority than PM2 processes
- Survives PM2 restarts

### Trading Bot → PM2 ✅
**Reason:** Benefits from PM2 features
- Easy restart during development
- Live log viewing (`pm2 logs gridbot-live`)
- Status monitoring (`pm2 status`)
- Environment variable management
- Quick stop/start during testing

### Heartbeat → PM2 ✅
**Reason:** Optional monitoring component
- Not critical for system operation
- Easy to enable/disable
- Benefits from PM2 log management

---

## Commands Reference

### LaunchAgent Commands

**Check Status:**
```bash
launchctl list | grep gridbot
```

**Start Service:**
```bash
launchctl start com.gridbot.webui
launchctl start com.gridbot.guardian
```

**Stop Service:**
```bash
launchctl stop com.gridbot.webui
launchctl stop com.gridbot.guardian
```

**View Logs:**
```bash
tail -f logs/launchagent_webui.log
tail -f logs/guardian_launchd.log
```

**Restart Service:**
```bash
launchctl stop com.gridbot.guardian && launchctl start com.gridbot.guardian
```

### PM2 Commands

**Check Status:**
```bash
pm2 status
```

**Start Bot:**
```bash
pm2 start gridbot-live
```

**Stop Bot:**
```bash
pm2 stop gridbot-live
```

**View Logs:**
```bash
pm2 logs gridbot-live
pm2 logs --lines 100
```

**Restart Bot:**
```bash
pm2 restart gridbot-live
```

**Monitor:**
```bash
pm2 monit
```

---

## Startup Sequence

### System Boot (Automatic)
```
1. macOS starts
2. LaunchAgent loads WebUI (com.gridbot.webui)
3. LaunchAgent loads Guardian (com.gridbot.guardian)
4. WebUI starts on port 5555
5. Guardian starts monitoring
6. PM2 NOT auto-started (requires pm2 startup command)
```

### Manual Trading Bot Start
```
Option 1: PM2
  pm2 start gridbot-live
  
Option 2: Direct
  nohup python3 -m bot.run > bot.log 2>&1 &
  
Option 3: Scripts
  ./start_bot_safe.sh
```

---

## Migration Notes

### What Changed
**Before:**
- Guardian via PM2 (`guardian-live`, `guardian-demo`)
- 2 guardian processes per project

**After:**
- Guardian via LaunchAgent (1 per project)
- PM2 only manages trading bot + heartbeat

### Migration Steps Taken
1. ✅ Created `com.gridbot.guardian.plist`
2. ✅ Installed LaunchAgent: `~/Library/LaunchAgents/`
3. ✅ Started Guardian via LaunchAgent
4. ✅ Stopped PM2 guardians: `pm2 stop guardian-live guardian-demo`
5. ✅ Deleted from PM2: `pm2 delete guardian-live guardian-demo`
6. ✅ Saved PM2 config: `pm2 save`

### Verification
```bash
$ launchctl list | grep guardian
10745   0       com.gridbot.guardian  ✅

$ pm2 status
gridbot-live    online    ✅
heartbeat       online    ✅
(no guardian)

$ ps aux | grep guardian_bot | grep -v grep
ssr  10745  ... -m bot.guardian.guardian_bot  ✅ (only one)
```

---

## Troubleshooting

### "Multiple guardians running"

**Symptom:**
```bash
$ ps aux | grep guardian
PID 10745  LaunchAgent
PID 16167  PM2 guardian-live
PID 16170  PM2 guardian-demo
```

**Fix:**
```bash
pm2 stop guardian-live guardian-demo
pm2 delete guardian-live guardian-demo
pm2 save
```

### "Guardian not starting via LaunchAgent"

**Check:**
```bash
tail -f logs/guardian_launchd_error.log
launchctl list | grep guardian
```

**Common Issues:**
- Wrong Python path in plist
- Wrong WorkingDirectory
- PYTHONPATH not set

**Fix:**
```bash
launchctl stop com.gridbot.guardian
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist
# Edit plist if needed
launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
```

### "Want guardian in PM2 for monitoring"

**Not Recommended**, but if needed:
```bash
# Stop LaunchAgent
launchctl stop com.gridbot.guardian
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist

# Start via PM2
pm2 start bot/guardian/guardian_bot.py --name guardian-live --interpreter python3
pm2 save
```

---

## Future Considerations

### If Moving to Linux Server
- Replace LaunchAgent with **systemd** services
- Keep PM2 for trading bot
- Example: `sudo systemctl start gridbot-guardian`

### If Need Cluster Mode
- WebUI can't cluster (port conflict)
- Guardian shouldn't cluster (one monitor per bot)
- Trading bot could cluster (multiple strategies)

### If Adding More Bots
- Each needs its own Guardian LaunchAgent
- Use different labels: `com.gridbot.guardian.strategy1`
- PM2 can manage multiple bots easily

---

## Summary

### Current State ✅
```
System-Level (LaunchAgent):
  • WebUI (port 5555)
  • Guardian Bot

User-Level (PM2):
  • Trading Bot (gridbot-live)
  • Heartbeat (monitoring)
```

### Benefits
- ✅ Guardian protected by OS
- ✅ WebUI survives user logout
- ✅ Trading bot easy to restart
- ✅ No duplicate processes
- ✅ Clear separation of concerns

### Commands
```bash
# LaunchAgent
launchctl list | grep gridbot
tail -f logs/guardian_launchd.log

# PM2
pm2 status
pm2 logs gridbot-live
pm2 restart gridbot-live
```

---

**Decision:** LaunchAgent for critical services (WebUI, Guardian), PM2 for trading bot  
**Rationale:** Reliability + flexibility where it matters  
**Status:** ✅ Implemented and verified
