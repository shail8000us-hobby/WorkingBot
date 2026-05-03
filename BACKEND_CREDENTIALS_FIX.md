# Backend Credentials Loading - Permanent Fix

**Date:** 2026-05-03  
**Issue:** Backend WebUI was missing Delta Exchange API credentials, causing all authenticated API calls to fail (401 errors) and making the UI extremely slow.  
**Root Cause:** Environment variables were not being loaded when the backend process started.

## Changes Made

### 1. **webui/backend/app.py** (CRITICAL)
Added automatic environment variable loading at the very start of the application, BEFORE any other imports:
- Loads `.env` file
- Loads `.env.local` file  
- Loads `secrets/api_keys.env` file
- **Fails fast with clear error message** if credentials are missing

```python
def _load_environment_variables():
    """Load environment variables from .env and secrets/api_keys.env"""
    # Checks multiple files in order
    # Validates that DELTA_API_KEY and DELTA_API_SECRET are present
    # Exits with clear error if missing
```

### 2. **Startup Scripts Updated** (All 4 scripts)
All backend startup scripts now load environment variables BEFORE starting Python:

#### a. `start_webui.sh` (Production)
- Added `source .env` before `nohup python3 app.py`
- Added `source secrets/api_keys.env`
- Displays confirmation that API key is loaded

#### b. `webui/start.sh` (Development - Full Stack)
- Added `.env` loading
- Added `secrets/api_keys.env` loading
- Displays trading mode and credentials status

#### c. `webui/backend/start_dev.sh` (Development - Backend Only)
- Added `.env` loading
- Added `secrets/api_keys.env` loading
- Displays development mode status and credentials

#### d. `scripts/webui_startup.sh` (Alternative Startup)
- Added `.env` loading before app.py execution

### 3. **`.env` File Cleanup**
Removed stale `APPLY=bash dashboard/set_grid.sh` entries that were:
- Leftover from old "hotwatch" tool integration
- Not needed for current infrastructure
- Causing unnecessary shell script execution attempts

## How It Works Now

1. **First execution:** Backend starts and loads credentials from `.env` or `secrets/api_keys.env`
2. **Credentials verified:** If credentials are missing, backend exits immediately with a clear error message
3. **API calls work:** All Delta Exchange API calls (positions, orders, etc.) now succeed
4. **UI responsive:** No more blocking retries on failed authentication

## Testing

✅ Confirmed working:
```bash
# API endpoints return data without 401 errors
curl http://localhost:5555/api/futures/positions
curl http://localhost:5555/api/futures/orders
curl http://localhost:5555/api/options/positions
```

## Credentials Location

Credentials should be stored in **ONE** of these files (checked in order):
1. `secrets/api_keys.env` ← **RECOMMENDED** (secure, not in git)
2. `.env` (project root)
3. `.env.local` (local overrides, not in git)

Each file should contain:
```env
DELTA_API_KEY=your_api_key_here
DELTA_API_SECRET=your_api_secret_here
```

For live trading, use:
```env
LIVE_DELTA_API_KEY=your_live_key
LIVE_DELTA_API_SECRET=your_live_secret
```

## Manual Restart

If backend needs manual restart:
```bash
./start_webui.sh restart
# or
bash webui/start_clean.sh
```

Both now automatically load credentials.

## No Manual Env Vars Needed

❌ **Old way (broken):**
```bash
export DELTA_API_KEY=... && export DELTA_API_SECRET=... && python3 app.py
```

✅ **New way (automatic):**
```bash
python3 app.py  # Credentials loaded automatically
```

## Permanent Solution

This fix is **permanent** and requires no manual intervention:
- Scripts automatically load credentials on every start
- App.py validates credentials and fails fast if missing
- No risk of slow UI due to missing credentials

## Files Changed Summary

| File | Change |
|------|--------|
| `webui/backend/app.py` | Added `_load_environment_variables()` function |
| `start_webui.sh` | Added env file sourcing |
| `webui/start.sh` | Added env file sourcing |
| `webui/backend/start_dev.sh` | Added env file sourcing |
| `scripts/webui_startup.sh` | Added env file sourcing |
| `.env` | Removed stale APPLY commands |
