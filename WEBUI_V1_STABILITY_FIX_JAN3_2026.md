# WebUI V1 Stability Fix - January 3, 2026

## Issue
User reported 500 Internal Server Errors in webUI console preventing stable operation:
- `/api/robustness/loss-limits` returning 500 error
- `/api/robustness/audit/report?days=7` returning 500 error

## Root Causes

### 1. Missing `capital_protection.max_loss_inr` in Config
**Problem:**
- Legacy code in `bot/safety/loss_limits.py`, `bot/position_tracker.py`, and `bot/risk/guards.py` tried to access `cfg.capital_protection.max_loss_inr`
- Config v6.0 restructured loss limits to per-instance `instances.SYMBOL_MODE.safety.max_account_loss_inr`
- The `CapitalProtection` model existed but didn't have `max_loss_inr` field
- Actual config.yaml didn't have `max_loss_inr` under `capital_protection`

**Solution:**
1. Added `max_loss_inr` field to `CapitalProtection` model in `config/models.py` as backward compatibility field
2. Added `max_loss_inr: 10000` to `capital_protection` section in `config.yaml`
3. Updated `bot/safety/loss_limits.py` to support v6.0 multi-instance architecture:
   - Reads `SYMBOL` and `MODE` from environment variables
   - Tries to load from `cfg.instances[SYMBOL_MODE].safety.max_account_loss_inr`
   - Falls back to safe defaults (10000 INR trader, 9000 INR guardian) if not found

**Files Changed:**
- `/Users/ssr/Projects/WorkingBot/config/models.py` (added `max_loss_inr` field)
- `/Users/ssr/Projects/WorkingBot/config.yaml` (added `max_loss_inr: 10000`)
- `/Users/ssr/Projects/WorkingBot/bot/safety/loss_limits.py` (v6.0 multi-instance support)

### 2. Missing Import in `bot/orders/audit.py`
**Problem:**
- `bot/orders/audit.py` used `get_config()` on lines 232 and 285
- No `from config.loader import get_config` import statement
- Python raised `NameError: name 'get_config' is not defined`

**Solution:**
- Added `from config.loader import get_config` to imports in `bot/orders/audit.py`

**Files Changed:**
- `/Users/ssr/Projects/WorkingBot/bot/orders/audit.py` (added import)

### 3. Incorrect Config Path Access
**Problem:**
- `bot/orders/audit.py` line 233 accessed `cfg.safety.trading_mode`
- `trading_mode` is a top-level field in RootConfig, not under `safety`
- AttributeError: `'SafetyConfig' object has no attribute 'trading_mode'`

**Solution:**
- Changed `cfg.safety.trading_mode.lower()` to `cfg.trading_mode.value.lower()`
- `trading_mode` is an enum, so use `.value` to get string

**Files Changed:**
- `/Users/ssr/Projects/WorkingBot/bot/orders/audit.py` (fixed config path)

## Verification

### Before Fix:
```bash
$ curl http://localhost:5555/api/robustness/loss-limits
{"error":"'CapitalProtection' object has no attribute 'max_loss_inr'","success":false}

$ curl "http://localhost:5555/api/robustness/audit/report?days=7"
{"error":"name 'get_config' is not defined","success":false,"report":{}}
```

### After Fix:
```bash
$ curl http://localhost:5555/api/robustness/loss-limits
{"config":{"buffer_inr":1000.0,"buffer_percent":10.0,"guardian_limit_inr":9000.0,"is_valid":true,"trader_limit_inr":10000.0,"validated":false},"success":true}

$ curl "http://localhost:5555/api/robustness/audit/report?days=7"
{"success":true,"report":{...}}
```

## Architecture Notes

### Config V6.0 Multi-Instance Loss Limits
The loss limits system now supports v6.0 multi-instance architecture:

**Per-Instance Limits** (Primary):
```yaml
instances:
  BTCUSD_LONG:
    safety:
      max_account_loss_inr: 10000  # Instance-specific limit
```

**Global Backward Compatibility** (Fallback):
```yaml
capital_protection:
  max_loss_inr: 10000  # Global fallback for legacy code
```

The `bot/safety/loss_limits.py` module:
1. Reads `SYMBOL` and `MODE` from environment (set by PM2 processes)
2. Looks up instance-specific limit: `cfg.instances[BTCUSD_LONG].safety.max_account_loss_inr`
3. Falls back to safe defaults if instance config not found
4. Guardian limit defaults to 90% of trader limit

## Impact
- ✅ `/api/robustness/loss-limits` endpoint working
- ✅ `/api/robustness/audit/report` endpoint working
- ✅ WebUI console no longer shows 500 errors
- ✅ V1 webUI stabilized for continued use until V3 is ready

## Testing
1. Restart webUI backend: `launchctl stop/start com.gridbot.production.webui`
2. Test loss-limits: `curl http://localhost:5555/api/robustness/loss-limits`
3. Test audit: `curl "http://localhost:5555/api/robustness/audit/report?days=7"`
4. Load webUI in browser: http://localhost:5555
5. Check console: No 500 errors should appear

## Related Files
- `webui/backend/routes/robustness.py` - API endpoints (no changes needed)
- `bot/safety/loss_limits.py` - Loss limits validator (updated for v6.0)
- `bot/orders/audit.py` - Order audit system (import and config path fixed)
- `config/models.py` - Config schema (added backward compat field)
- `config.yaml` - Active config (added max_loss_inr)

## Branch
All changes made in `BTEH` branch (current working branch).

## Date
January 3, 2026 - 9:50 PM IST
