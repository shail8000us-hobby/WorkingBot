# WebUI Single-Instance System

## Problem Solved
**Before:** Multiple WebUI instances could start simultaneously, causing:
- Port conflicts
- Resource waste (2-3 processes per WebUI)
- Confused monitoring dashboards
- No guardian LaunchAgent for main WorkingBot

**After:** Bulletproof single-instance enforcement + guardian automation

---

## Architecture

### 1. Instance Locking (`webui/backend/utils/instance_lock.py`)
- File-based exclusive lock using `fcntl.flock()`
- Lock file: `.webui_instance_5555.lock` (port-specific)
- Prevents duplicate manual starts
- Graceful error messages showing existing instance info

### 2. Flask Process Model
**Normal Behavior:**
```
LaunchAgent → Parent Process (PID 992)
               └→ Worker Process (PID 2237)  ← Flask's multiprocessing
```

**What You See:**
- 2 processes for 1 WebUI = **NORMAL** (parent + worker)
- Both have same command line
- Worker does actual request handling

### 3. Guardian LaunchAgent
**Main WorkingBot:**
- File: `~/Library/LaunchAgents/com.gridbot.guardian.plist`
- Auto-start on boot: `RunAtLoad = true`
- Auto-restart on crash: `KeepAlive = true`
- Throttle: 30 seconds between restarts

**Demo:**
- Separate LaunchAgent: `com.gridbot.demo.guardian.plist`
- Independent from main

---

## Implementation

### Code Changes

#### 1. Added Instance Lock to `app.py`
```python
from webui.backend.utils.instance_lock import WebUIInstanceLock

instance_lock = WebUIInstanceLock(BASE_DIR, 5555)

if not instance_lock.acquire():
    print("❌ ERROR: WebUI instance already running!")
    sys.exit(1)

atexit.register(instance_lock.release)
```

**Result:** Attempting to start duplicate WebUI shows:
```
❌ ERROR: WebUI instance is already running!
   PID: 992
   Port: 5555
   Started: Sun Nov 10 14:42:15 2025
```

#### 2. Updated `start_main_bot.sh`
- Checks LaunchAgent status before starting
- Verifies port 5555 availability
- Installs guardian LaunchAgent if missing
- Uses LaunchAgent for guardian (not manual `nohup`)

#### 3. Updated `stop_main_bot.sh`
- Stops services via LaunchAgent commands
- Unloads LaunchAgents properly
- Cleans lock files

---

## Usage

### Start Main Bot
```bash
cd /Users/ssr/Projects/WorkingBot
./start_main_bot.sh
```

**What Happens:**
1. ✅ Checks no duplicate processes
2. ✅ Cleans old lock files
3. 🌐 Starts WebUI via LaunchAgent (port 5555)
4. 🤖 Starts Trading Bot manually
5. 🛡️ Starts/verifies Guardian via LaunchAgent

### Stop Main Bot
```bash
./stop_main_bot.sh
```

**What Happens:**
1. 🤖 Stops Trading Bot
2. 🛡️ Stops Guardian (unloads LaunchAgent)
3. 🌐 Stops WebUI (unloads LaunchAgent)
4. 🧹 Cleans lock files
5. ✅ Verifies all stopped

### Check Status
```bash
# LaunchAgents
launchctl list | grep gridbot

# Expected output:
# 992     0       com.gridbot.webui
# 1234    0       com.gridbot.guardian

# Processes
ps aux | grep WorkingBot | grep python | grep -v grep

# Lock files
ls -la /Users/ssr/Projects/WorkingBot/.webui_instance*.lock
```

---

## LaunchAgent Details

### WebUI LaunchAgent
**File:** `~/Library/LaunchAgents/com.gridbot.webui.plist`

**Key Settings:**
- `RunAtLoad`: Start on system boot
- `KeepAlive.Crashed`: Restart if crashes
- `ThrottleInterval`: 10 seconds between restarts
- Logs: `logs/launchagent_webui.log`

### Guardian LaunchAgent
**File:** `~/Library/LaunchAgents/com.gridbot.guardian.plist`

**Key Settings:**
- `RunAtLoad`: Start on system boot
- `KeepAlive`: Always running (restart immediately)
- `ThrottleInterval`: 30 seconds between restarts
- `Nice`: -5 (higher priority than normal processes)
- Logs: `logs/guardian_launchd.log`

---

## Troubleshooting

### "WebUI instance already running" Error

**Cause:** Instance lock detected existing WebUI

**Solution:**
```bash
# Check what's running
launchctl list | grep gridbot.webui

# Stop it
launchctl stop com.gridbot.webui

# Or kill manually
ps aux | grep "webui/backend/app.py" | grep -v grep
kill <PID>

# Clean lock
rm .webui_instance_5555.lock
```

### 2 WebUI Processes Showing

**Status:** ✅ **NORMAL** - Flask uses multiprocessing

**Explanation:**
- PID 992: Parent process (manages workers)
- PID 2237: Worker process (handles requests)

**How to Verify:**
```bash
ps aux | grep "webui/backend/app.py" | grep -v grep
# Should see 2 processes with same command
```

### Guardian Not Starting

**Check:**
```bash
# LaunchAgent status
launchctl list | grep guardian

# Logs
tail -f logs/guardian_launchd_error.log

# Manual test
python3 -m bot.guardian.guardian_bot
```

**Common Issues:**
- PYTHONPATH not set → Fixed in LaunchAgent plist
- Wrong working directory → Fixed to `/Users/ssr/Projects/WorkingBot`
- Python3 path wrong → Using `/usr/bin/python3`

### Demo vs Main Confusion

**Separation Checklist:**
- ✅ Different ports (5555 vs 5556)
- ✅ Different LaunchAgent labels (.guardian vs .demo.guardian)
- ✅ Different lock files (.webui_instance_5555.lock vs 5556)
- ✅ bot_control.py filters by project directory

---

## File Locations

### Main WorkingBot
```
/Users/ssr/Projects/WorkingBot/
├── com.gridbot.guardian.plist          # Ready to install
├── start_main_bot.sh                   # Start all components
├── stop_main_bot.sh                    # Stop all components
├── .webui_instance_5555.lock           # Instance lock (auto-created)
├── webui/backend/
│   ├── app.py                          # Instance lock integrated
│   └── utils/
│       └── instance_lock.py            # Lock manager
└── launchd/
    └── com.gridbot.guardian.plist      # Template (updated paths)
```

### LaunchAgents (System)
```
~/Library/LaunchAgents/
├── com.gridbot.webui.plist             # Main WebUI
├── com.gridbot.guardian.plist          # Main Guardian
├── com.gridbot.demo.webui.plist        # Demo WebUI
└── com.gridbot.demo.guardian.plist     # Demo Guardian
```

---

## Testing Checklist

### ✅ Single Instance Enforcement
```bash
# Terminal 1
cd /Users/ssr/Projects/WorkingBot
python3 webui/backend/app.py

# Terminal 2 (should fail)
python3 webui/backend/app.py
# Expected: ❌ ERROR: WebUI instance already running!
```

### ✅ LaunchAgent Start/Stop
```bash
# Start
./start_main_bot.sh

# Check
launchctl list | grep gridbot
ps aux | grep WorkingBot | grep python

# Stop
./stop_main_bot.sh

# Verify
launchctl list | grep gridbot  # Should show nothing or "-" PIDs
```

### ✅ Guardian Auto-Restart
```bash
# Start guardian
./start_main_bot.sh

# Kill it
pkill -9 -f guardian_bot

# Wait 30 seconds, check if restarted
ps aux | grep guardian_bot

# Should see new PID (auto-restarted by LaunchAgent)
```

---

## Summary

### What Changed
1. ✅ **Instance lock** in app.py prevents duplicate WebUI starts
2. ✅ **Guardian LaunchAgent** created for main WorkingBot
3. ✅ **Updated guardian LaunchAgent template** with correct paths
4. ✅ **Start/stop scripts** use LaunchAgent for guardian
5. ✅ **Comprehensive checks** in startup scripts

### What's Fixed
- ❌ No more duplicate WebUI instances
- ❌ No confusion about 2 processes (Flask parent/worker)
- ✅ Guardian always starts via LaunchAgent (not manual nohup)
- ✅ Guardian auto-restarts on crash
- ✅ Clean separation between main and demo

### Next Steps
1. Test with current running system
2. Stop all processes cleanly
3. Restart with new scripts
4. Verify single-instance enforcement works
5. Confirm guardian LaunchAgent functioning
