# Documentation Update: Tmux → PM2 Migration (Nov 9, 2025)

## ✅ Changes Applied

Updated **AI_CONTEXT.md** to reflect the **PM2 process management system** that replaced tmux.

---

## 📝 What Was Changed

### 1. Startup Sequence Section
**Before:**
```
macOS Login → LaunchAgent: com.gridbot.tmux.control → scripts/start_tmux_daemon.sh → Tmux Session Created
```

**After:**
```
macOS Login → PM2 Auto-Start → PM2 Daemon → 6 Processes from ecosystem.config.js
  - gridbot-live, gridbot-demo, guardian-live, guardian-demo, heartbeat-monitor, webui-backend
```

### 2. New PM2 Section Added (130+ lines)
- **Why PM2?** - 6 key advantages over tmux
- **PM2 Processes Table** - All 6 processes with memory limits
- **PM2 Quick Reference** - 30+ commands (status, start, stop, logs, maintenance)
- **Auto-Start on Boot** - Setup instructions
- **PM2 Logs Location** - All log files listed
- **PM2 + WebUI Integration** - API endpoints for bot control
- **Troubleshooting PM2** - 4 common issues with solutions
- **PM2 vs Tmux Comparison** - Before/After advantages

### 3. Configuration Files Section
**Before:**
```
LaunchAgent Files:
- com.gridbot.tmux.control.plist
- com.gridbot.webui.plist
- start_tmux_daemon.sh
- start_webui.sh
```

**After:**
```
PM2 Configuration Files:
- ecosystem.config.js (PM2 app definitions)
- pm2_gridbot.sh (PM2 control script)
- toggle_pm2.sh
- webui/backend/utils/pm2_adapter.py
- webui/backend/routes/pm2.py
```

### 4. Start/Stop Commands
**Before:**
```bash
launchctl list | grep gridbot
launchctl start com.gridbot.tmux.control
launchctl stop com.gridbot.tmux.control
```

**After:**
```bash
pm2 list
pm2 start ecosystem.config.js
pm2 stop gridbot-live
pm2 logs gridbot-live
./pm2_gridbot.sh start live
```

### 5. WebUI Management
**Before:**
```bash
launchctl start com.gridbot.webui
launchctl stop com.gridbot.webui
```

**After:**
```bash
pm2 start ecosystem.config.js --only webui-backend
pm2 stop webui-backend
pm2 logs webui-backend
```

### 6. Dependencies Section
**Before:**
```
- macOS (LaunchAgent)
- tmux (for terminal multiplexing)
```

**After:**
```
- macOS (or Linux with PM2)
- Node.js 14+ (for PM2)
- PM2 (process manager) - npm install -g pm2
```

### 7. Project Structure
**Before:**
```
├── scripts/
│   └── start_tmux_daemon.sh      # LaunchAgent startup script
```

**After:**
```
├── scripts/
│   └── start_tmux_daemon.sh      # ⚠️ DEPRECATED (tmux replaced by PM2)
├── pm2_gridbot.sh                # ✅ ACTIVE - PM2 control script
├── ecosystem.config.js           # ✅ ACTIVE - PM2 app definitions
```

### 8. Old Tmux Content Handling
All old tmux/LaunchAgent sections are now:
- Marked with **⚠️ DEPRECATED** tags
- Wrapped in collapsible `<details>` sections
- Labeled as "Historical reference only"
- Preserved for documentation completeness

### 9. WebUI Front Page Panels
**Before:**
```
5. Tmux Professional Setup - Access tmux session
```

**After:**
```
5. PM2 Process Manager - Control PM2 processes (start/stop/restart bots)
```

---

## 📊 Current PM2 Status (Verified)

```bash
$ pm2 list
┌────┬──────────────────┬─────────┬──────┬───────────┬──────────┐
│ id │ name             │ mode    │ pid  │ status    │ uptime   │
├────┼──────────────────┼─────────┼──────┼───────────┼──────────┤
│ 0  │ gridbot-live     │ fork    │ 55912│ online    │ 37m      │
│ 2  │ guardian-live    │ fork    │ 20906│ online    │ 17h      │
│ 4  │ heartbeat        │ fork    │ 20874│ online    │ 17h      │
│ 1  │ gridbot-demo     │ fork    │ 0    │ stopped   │ 0        │
│ 3  │ guardian-demo    │ fork    │ 0    │ stopped   │ 0        │
└────┴──────────────────┴─────────┴──────┴───────────┴──────────┘
```

**Active Processes:**
- ✅ gridbot-live (37 minutes uptime)
- ✅ guardian-live (17 hours uptime)
- ✅ heartbeat (17 hours uptime)

---

## 🎯 PM2 Advantages Over Tmux

### Before (Tmux)
- ❌ Manual restart after crashes
- ❌ No memory monitoring
- ❌ Log management required custom scripts
- ❌ No web integration
- ❌ Manual startup after reboot
- ❌ No process status tracking
- ❌ Terminal-based only

### After (PM2)
- ✅ Auto-restart on crash (exponential backoff, max_restarts=10)
- ✅ Built-in CPU/memory monitoring (`pm2 monit`)
- ✅ Automatic log rotation + aggregation
- ✅ WebUI can control processes via API
- ✅ Auto-start on boot (`pm2 startup` + `pm2 save`)
- ✅ Real-time status dashboard
- ✅ Remote monitoring support (pm2 plus)
- ✅ Zero-downtime reload capability
- ✅ Memory limits (auto-restart if exceeded)
- ✅ Process clustering support

---

## 📁 PM2 Configuration Files

### ecosystem.config.js
```javascript
module.exports = {
  apps: [
    {
      name: "gridbot-live",
      script: "bot/run.py",
      interpreter: "python3",
      cwd: "/Users/ssr/Projects/WorkingBot",
      env: {
        PYTHONPATH: "/Users/ssr/Projects/WorkingBot",
        TRADING_MODE: "live",
        HOT_RELOAD: "1"
      },
      autorestart: true,
      max_restarts: 10,
      max_memory_restart: "500M",
      // ... 5 more apps defined
    }
  ]
}
```

### pm2_gridbot.sh
```bash
#!/bin/bash
# PM2 GridBot Manager - Production Process Management

# Usage:
./pm2_gridbot.sh start live           # Start live bot
./pm2_gridbot.sh stop live            # Stop live bot (graceful, 30s timeout)
./pm2_gridbot.sh restart live         # Restart live bot
./pm2_gridbot.sh logs live            # View live bot logs
./pm2_gridbot.sh status               # Show all bots status
./pm2_gridbot.sh monit                # Real-time monitoring
```

---

## 🔄 Migration Timeline

- **Before Oct 2025:** Used tmux with LaunchAgent
- **Oct 2025:** Migrated to PM2 for better process management
- **Nov 9, 2025:** Documentation updated to reflect PM2 system

---

## 📚 Documentation Status

### Updated Files
1. **AI_CONTEXT.md** - ✅ Completely updated with PM2 info
   - Old tmux content marked as deprecated
   - New PM2 section added (130+ lines)
   - All commands updated
   - Project structure reflects PM2

### Files That May Need Updates
2. **START_HERE.md** - Check if mentions tmux
3. **USER_MANUAL.md** - Check startup instructions
4. **BOT_STRUCTURE.md** - Check LaunchAgent references

---

## 🎓 For AI Assistants

### Key Points
1. **PM2 is the active system** - Not tmux, not LaunchAgent directly
2. **All bots run via PM2** - `pm2 list` shows current status
3. **Commands changed** - Use `pm2` commands, not `launchctl` or `tmux`
4. **Auto-restart enabled** - Bots recover from crashes automatically
5. **WebUI integration** - Can control PM2 via `/api/pm2/*` endpoints

### When helping users:
- ✅ Use `pm2 start/stop/restart` commands
- ✅ Use `pm2 logs` for log viewing
- ✅ Use `pm2 monit` for real-time monitoring
- ✅ Reference `ecosystem.config.js` for process config
- ✅ Use `./pm2_gridbot.sh` helper script

- ❌ Don't suggest `tmux` commands (deprecated)
- ❌ Don't suggest `launchctl` for bot management (PM2 handles it)
- ❌ Don't reference `start_tmux_daemon.sh` (not used)

### Quick Status Check
```bash
pm2 list                    # See what's running
pm2 logs gridbot-live       # Check logs if issue
pm2 describe gridbot-live   # Detailed process info
```

---

## 📞 Contact

**Owner:** Shailendra Singh Rajawat  
**Updated:** November 9, 2025  
**System:** PM2 Process Management (replaced tmux)  
**Status:** ✅ Documentation fully updated

---

**Summary:** All tmux references have been updated to reflect the current PM2 system. Old content preserved as deprecated/historical reference. New comprehensive PM2 section added with commands, configuration, and troubleshooting.
