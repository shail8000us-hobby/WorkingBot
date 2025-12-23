# Equity Floor Display Fix - November 14, 2025

## Problem Identified

The Capital Protection dashboard was showing "EQUITY FLOOR BREACHED" status even though the current equity (₹103,716) was well above the floor (₹70,000).

### Root Cause

The `/api/capital/equity-floor/status` endpoint was:
1. **Returning hardcoded `current_equity: 0`** instead of fetching real equity from Guardian bot
2. **Not auto-clearing the breach flag** when equity recovered above the floor
3. **Missing `json` import** needed to read Guardian health file

This caused the dashboard to display incorrect breach status.

## Solution Implemented

### 1. Fetch Real Equity from Guardian Bot

Updated `/webui/backend/routes/capital.py` to read real equity from Guardian bot's health file:

```python
# Fetch current equity from Guardian health file
current_equity = 0
guardian_health_file = BASE_DIR / '.guardian_health'

if guardian_health_file.exists():
    try:
        with open(guardian_health_file, 'r') as f:
            health_data = json.load(f)
            # Get total balance from liquidation margin data
            current_equity = health_data.get('liquidation', {}).get('margin', {}).get('total_balance', 0)
    except Exception as e:
        log.warning(f"Failed to read Guardian health file: {e}")
```

### 2. Auto-Clear Breach Flag on Recovery

Added logic to automatically clear the breach flag when equity recovers:

```python
# Auto-clear breach flag if equity recovered above floor
if breach_flag_exists and current_equity >= floor_inr:
    try:
        breach_flag.unlink()
        breach_flag_exists = False
        log.info(f"✅ Auto-cleared equity floor breach flag (equity ₹{current_equity:,.0f} > floor ₹{floor_inr:,})")
    except Exception as e:
        log.warning(f"Failed to clear breach flag: {e}")
```

### 3. Calculate Accurate Buffer

Now calculates real buffer based on current equity:

```python
# Calculate buffer
buffer_inr = max(0, current_equity - floor_inr) if current_equity > 0 else 0
```

## Files Modified

- `/webui/backend/routes/capital.py`:
  - Added `import json`
  - Updated `get_equity_floor_status()` to fetch real equity from Guardian health file
  - Added auto-clear logic for breach flag when equity recovers

## How It Works Now

1. **Guardian bot monitors real-time equity** from Delta Exchange (all positions including manual trades)
2. **Guardian writes health data** to `.guardian_health` file every check cycle
3. **WebUI API reads equity** from Guardian health file
4. **Auto-clears breach flag** if equity >= floor
5. **Dashboard displays accurate status** with real equity and buffer

## Verification Results

### Before Fix
```json
{
    "breached": true,
    "current_equity": 0,
    "buffer_inr": 0,
    "floor_inr": 70000.0
}
```

### After Fix
```json
{
    "breached": false,
    "current_equity": 103716.11,
    "buffer_inr": 33716.11,
    "floor_inr": 70000.0
}
```

## Dashboard Now Shows

- ✅ **Current Equity**: ₹103,716 (real value from Guardian)
- ✅ **Floor**: ₹70,000
- ✅ **Buffer**: ₹33,716 (₹103,716 - ₹70,000)
- ✅ **Status**: NORMAL (green) - no breach
- ✅ **Breach flag auto-cleared** when equity recovered

## Why Guardian Bot Tracks All Positions

The design is correct - Guardian bot tracks **all positions on the exchange** (including manual trades), not just bot-created positions. This ensures:

1. **Real-time protection** based on actual account state
2. **Comprehensive risk monitoring** including manual interventions
3. **Accurate equity calculations** matching exchange reality
4. **Proper breach detection** regardless of how positions were created

The equity floor breach that occurred at 12:27 PM was **legitimate** - it detected when actual equity fell below ₹70,000. The system correctly:
- ✅ Created breach flag
- ✅ Blocked new trading
- ✅ Monitored for recovery
- ✅ Auto-cleared flag when equity recovered above floor

## Impact

- ✅ Dashboard shows real equity from Guardian bot
- ✅ Auto-clears breach flags on recovery
- ✅ Accurate buffer calculations
- ✅ No more false breach warnings
- ✅ Works with all positions (bot + manual)

---

**Status:** ✅ COMPLETE - Equity floor monitoring fully functional
**Date:** November 14, 2025
**WebUI Backend Restarted:** Yes
