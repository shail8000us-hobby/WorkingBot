# Issue: WebUI Failed to Start After clean_restart_with_guardian.sh

## Problem
After running `./clean_restart_with_guardian.sh`, WebUI LaunchAgent showed status "-" (crashed) and port 5555 was not listening.

## Root Cause
**Flask Debug Mode Reloader + Instance Lock Conflict**

The issue occurred because:
1. `debug_mode = True` was set based on `FLASK_ENV != 'production'`
2. This enabled Flask's reloader (`use_reloader=True`)
3. Flask's reloader spawns a **child process** to monitor code changes
4. The child process tried to acquire the instance lock
5. The instance lock was already held by the parent
6. The child process detected "instance already running" and exited with error
7. Flask interpreted this as a startup failure

**Key Code:**
```python
# BEFORE (problematic)
flask_env = os.getenv('FLASK_ENV', 'development')  # defaults to 'development'
debug_mode = (flask_env != 'production')

socketio.run(
    app,
    host='0.0.0.0',
    port=5555,
    debug=debug_mode,        # True in development
    use_reloader=debug_mode  # True = spawns child process
)
```

## Solution Applied
**Disabled Debug Mode and Reloader for LaunchAgent**

Changed `app.py` to:
```python
# FIXED
socketio.run(
    app,
    host='0.0.0.0',
    port=WEBUI_PORT,
    debug=False,           # Disabled to prevent reloader
    use_reloader=False,    # Critical: reloader conflicts with instance lock
    allow_unsafe_werkzeug=True
)
```

## Why This Fix Works
1. **No reloader** = no child process spawned
2. **Single process** acquires instance lock once
3. **Production-like behavior** even in development environment
4. **Instance lock** works as intended

## Verification
```bash
$ launchctl list | grep gridbot.webui
12519   0       com.gridbot.webui  ✅

$ lsof -i :5555
Python  12519  ssr  ... *:5555 (LISTEN)  ✅

$ cat .webui_instance_5555.lock
12519
Port: 5555
Started: Mon Nov 10 15:02:01 2025  ✅

$ curl http://localhost:5555/api/health
{"status":"healthy","timestamp":"..."}  ✅
```

## Trade-offs
**Before:**
- ✅ Auto-reload on code changes (convenient for development)
- ❌ Conflicts with instance lock
- ❌ Can't run via LaunchAgent reliably

**After:**
- ✅ Works with instance lock
- ✅ Runs reliably via LaunchAgent
- ✅ Production-ready
- ❌ Must restart manually to see code changes

## Alternative Solutions (Not Implemented)

### Option 1: Conditional Instance Lock
Only enable instance lock when `use_reloader=False`
```python
if not use_reloader:
    instance_lock.acquire()
```
**Rejected:** Defeats purpose of instance lock

### Option 2: Environment Variable Check
```python
running_via_launchagent = os.getenv('LAUNCHED_BY_LAUNCHAGENT')
if running_via_launchagent:
    use_reloader = False
```
**Rejected:** Too complex, requires plist modification

### Option 3: Lock File Per Process
Use PID-specific locks
**Rejected:** Doesn't prevent duplicates (both processes would succeed)

## Recommendation
For development with auto-reload:
```bash
# Temporary development mode (bypasses LaunchAgent)
launchctl stop com.gridbot.webui
FLASK_ENV=development python3 webui/backend/app.py
```

For production (LaunchAgent):
```bash
# Normal startup - no reloader
./start_main_bot.sh
```

## Status
✅ **FIXED** - WebUI now starts reliably via LaunchAgent  
✅ **TESTED** - Port 5555 listening, health check passing  
✅ **DEPLOYED** - Running with PID 12519

## Files Modified
- `webui/backend/app.py` - Disabled debug mode and reloader in socketio.run()

---

**Date:** November 10, 2025, 15:02  
**Issue:** Flask reloader + instance lock conflict  
**Fix:** Disabled reloader for LaunchAgent compatibility
