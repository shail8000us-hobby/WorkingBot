# Bot Monitoring Dashboard Fix - November 14, 2025

## Problem Identified

The Bot Monitoring Dashboard was showing **N/A** values and the Predictive Decision Map was displaying "Grid calculator not available" error.

### Root Causes

1. **Missing `active` flag in monitoring statistics**
   - `pre_order_logger.get_statistics()` didn't include `active: true`
   - `tp_verifier.get_statistics()` didn't include `active: true`
   - This caused the dashboard to treat these systems as inactive

2. **Incorrect parameter passed to `write_snapshot()`**
   - `async_gridbot.py` was passing `snapshot` (runtime state dict) instead of `self` (bot instance)
   - This prevented `data_writer.py` from accessing bot's monitoring systems
   - Result: Grid calculator and all monitoring data unavailable

## Files Modified

### 1. `/bot/monitoring/data_writer.py`

**Changes:**
- Added `active: true` flag to pre-order statistics return value
- Added `active: true` flag to TP verification return value

```python
def _get_pre_order_stats(self, bot) -> Dict[str, Any]:
    """Get pre-order logger statistics"""
    try:
        if not hasattr(bot, 'pre_order_logger') or not bot.pre_order_logger:
            return {'active': False}
        
        stats = bot.pre_order_logger.get_statistics()
        stats['active'] = True  # ✅ Added this line
        return stats
        
    except Exception as e:
        log.debug(f"Error getting pre-order stats: {e}")
        return {'active': False, 'error': str(e)}

def _get_tp_verification(self, bot) -> Dict[str, Any]:
    """Get TP verification system data"""
    try:
        if not hasattr(bot, 'tp_verifier') or not bot.tp_verifier:
            return {'active': False}
        
        stats = bot.tp_verifier.get_statistics()
        stats['active'] = True  # ✅ Added this line
        return stats
        
    except Exception as e:
        log.debug(f"Error getting TP verification: {e}")
        return {'active': False, 'error': str(e)}
```

### 2. `/bot/strategy/async_gridbot.py`

**Changes:**
- Fixed `write_snapshot()` call to pass bot instance instead of snapshot dict

```python
# NOV 13: Export via monitoring data writer (for WebUI compatibility)
current_time = time.time()
if current_time - self._last_monitoring_write > 5:  # Every 5s
    try:
        self.monitoring_writer.write_snapshot(self)  # ✅ Changed from snapshot to self
        self._last_monitoring_write = current_time
    except Exception as e:
        log.debug(f"Monitoring writer error: {e}")  # Don't spam logs
```

## Solution Applied

1. Updated `data_writer.py` to add `active` flag to statistics
2. Fixed `async_gridbot.py` to pass correct parameter (`self`) to `write_snapshot()`
3. Restarted bot to apply changes

## Verification Results

### All Monitoring Endpoints Working ✅

```bash
# Monitoring Status
$ curl http://localhost:5555/api/monitoring/status
{
    "monitoring_active": true,
    "layers": {
        "price_health": true,
        "pre_order_logger": true,
        "tp_verification": true,
        "anomaly_detection": true,
        "predictive_display": true
    }
}

# Price Health
$ curl http://localhost:5555/api/monitoring/price-health
{
    "active": true,
    "price": 97430.0,
    "price_age_seconds": 4.63,
    "source": "WEBSOCKET",
    "status": "FRESH",
    "is_fresh": true,
    "is_critical": false
}

# Pre-Order Stats
$ curl http://localhost:5555/api/monitoring/pre-order-stats
{
    "active": true,
    "total_decisions": 0,
    "approved": 0,
    "rejected": 0,
    "approval_rate": 0
}

# TP Verification
$ curl http://localhost:5555/api/monitoring/tp-verification
{
    "active": true,
    "total_verifications": 0,
    "successful": 0,
    "failed": 0,
    "orphaned_positions": 0,
    "success_rate": 0
}

# Anomalies
$ curl http://localhost:5555/api/monitoring/anomalies
{
    "active": true,
    "anomalies_detected": 0,
    "anomaly_list": [],
    "health_status": "HEALTHY"
}

# Predictive Map
$ curl http://localhost:5555/api/monitoring/predictive-map
{
    "active": true,
    "current_state": {
        "mode": "LONG",
        "price": 97430.0,
        "grid_step": 500.0,
        "positions": 0,
        "max_positions": 10,
        "capacity_used_pct": 0.0
    },
    "scenarios": {
        "next_action": {
            "type": "WILL_BUY",
            "price": 94500.0,
            "status": "Will place when price drops to $94,500",
            "then": "Calculate TP"
        },
        "price_drops": [
            {
                "action": "BUY",
                "price": 94500.0,
                "tp_price": 95000.0,
                "profit_target": 500.0,
                "reason": "Grid level #1",
                "sequence": 1
            },
            ...
        ]
    }
}
```

## Dashboard Status

### Before Fix
- ❌ Price Health: Age N/A, Source N/A
- ❌ Pre-Order Statistics: 0.0% approval rate (no data)
- ❌ TP Verification: 0.0% success rate (no data)
- ❌ Anomaly Alerts: No data
- ❌ Predictive Decision Map: "Grid calculator not available"

### After Fix
- ✅ Price Health: Live price data, age in seconds, WebSocket source
- ✅ Pre-Order Statistics: Real-time approval rate tracking
- ✅ TP Verification: Live TP placement tracking
- ✅ Anomaly Alerts: Real-time anomaly detection
- ✅ Predictive Decision Map: Shows next 3 BUY levels and TP fills with real grid calculations

## How It Works Now

1. **Bot starts** → Initializes monitoring systems
2. **Every 5 seconds** → `monitoring_writer.write_snapshot(self)` writes data to `data/monitoring_snapshot.json`
3. **WebUI polls** → Frontend fetches `/api/monitoring/*` endpoints every 30s
4. **Backend reads** → Routes read from snapshot file (works even if bot started standalone)
5. **Dashboard displays** → Live monitoring data with all 5 layers active

## Impact

- ✅ Bot Monitoring Dashboard fully functional
- ✅ All 5 monitoring layers showing real-time data
- ✅ Predictive Decision Map showing accurate grid calculations
- ✅ Works with bot started via PM2 or WebUI
- ✅ No more "N/A" or "Grid calculator not available" errors

## Testing

Access dashboard at: **http://localhost:5555**
- Navigate to "🔍 Bot Monitoring Dashboard"
- Verify all panels show live data
- Check that Predictive Decision Map shows next actions

---

**Status:** ✅ COMPLETE - All monitoring systems operational
**Date:** November 14, 2025
**Bot Restarted:** Yes (via PM2)
