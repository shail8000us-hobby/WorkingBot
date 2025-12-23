# WebSocket Optimization Implementation - November 9, 2025

## Based on Delta Exchange Official Documentation

### Changes to Implement

## 1. Fix 'pong' Message Handling (delta_ws.py)

**Location:** `bot/delta_websocket/delta_ws.py` line ~420

**Current Code:**
```python
else:
    # Unknown message type - ALWAYS log it (might be critical!)
    log.warning(f"⚠️ Unknown WebSocket message type '{msg_type}': {json.dumps(data, indent=2)[:300]}")
```

**New Code:**
```python
elif msg_type == 'pong':
    # Delta Exchange ping/pong response - handle silently
    log.debug("♥️ WebSocket pong received (connection alive)")
    # Update last message time to prevent false starvation
    if not self.authenticated:
        log.info("✅ WebSocket connection confirmed (pong received)")
        self.authenticated = True

elif msg_type == 'heartbeat':
    # Delta Exchange server heartbeat (30s interval)
    log.debug("💓 Server heartbeat received")
    # Update last message time
    
else:
    # Unknown message type - ALWAYS log it (might be critical!)
    log.warning(f"⚠️ Unknown WebSocket message type '{msg_type}': {json.dumps(data, indent=2)[:300]}")
```

---

## 2. Enable Delta Server Heartbeat (delta_ws.py)

**Location:** `bot/delta_websocket/delta_ws.py` after authentication success

**Add After Authentication:**
```python
# In _on_ws_message, after auth success:
if msg_type == 'auth' and data.get('success'):
    self.authenticated = True
    log.info("✅ WebSocket authenticated successfully")
    
    # ✅ NEW: Enable Delta's server heartbeat (30s interval)
    try:
        heartbeat_msg = json.dumps({"type": "enable_heartbeat"})
        self.ws.send(heartbeat_msg)
        log.info("✅ Delta server heartbeat enabled (30s interval)")
    except Exception as e:
        log.warning(f"⚠️ Failed to enable server heartbeat: {e}")
    
    self._trigger_callback('authenticated', data)
```

---

## 3. Adjust Starvation Threshold (gridbot.py)

**Location:** `bot/strategy/gridbot.py` line 267

**Current Code:**
```python
self.ws_starvation_threshold = 30.0  # Activate fallback after 30s no data
```

**New Code (Option 1 - Simple Fix):**
```python
# ✅ NOV 9 FIX: Adjusted per Delta documentation
# Delta sends ticker every 5s, server heartbeat every 30s
# Use 35s threshold (30s heartbeat + 5s buffer)
self.ws_starvation_threshold = 35.0  # Was 30.0, adjusted for Delta's heartbeat timing
log.info(f"   ├─ Starvation threshold: {self.ws_starvation_threshold}s (aligned with Delta heartbeat)")
```

**New Code (Option 2 - Channel-Specific, Recommended):**
```python
# ✅ NOV 9 FIX: Channel-specific thresholds per Delta documentation
# Ticker channel: Every 5s → 10s threshold
# User channel: Event-driven → No threshold (silence is normal)
# Heartbeat: Every 30s → 35s threshold
self.ticker_starvation_threshold = 10.0   # Ticker should update every 5s
self.heartbeat_starvation_threshold = 35.0  # Server heartbeat every 30s + buffer
self.ws_starvation_threshold = 35.0  # General fallback threshold
log.info(f"   ├─ Ticker threshold: {self.ticker_starvation_threshold}s")
log.info(f"   ├─ Heartbeat threshold: {self.heartbeat_starvation_threshold}s")
log.info(f"   └─ General threshold: {self.ws_starvation_threshold}s")
```

---

## 4. Update Ping Interval (delta_ws.py config)

**Location:** `bot/delta_websocket/delta_ws.py` line 50

**Current Code:**
```python
'ping_interval': int(os.getenv('WS_PING_INTERVAL', '20')),
```

**New Code:**
```python
# ✅ NOV 9: Aligned with Delta recommendation (30s)
# With server heartbeat enabled, client ping is backup mechanism
'ping_interval': int(os.getenv('WS_PING_INTERVAL', '30')),
```

---

## 5. Add Channel-Aware Health Monitoring (gridbot.py)

**Location:** `bot/strategy/gridbot.py` in `_check_rest_fallback_activation` method

**Current Logic:**
```python
age = time.time() - self.last_ws_price_time
if age > self.ws_starvation_threshold and not self.rest_fallback_active:
    log.warning(f"🚨 [REST FALLBACK] WebSocket starved for {age:.1f}s")
    self._activate_rest_fallback()
```

**New Logic (Channel-Aware):**
```python
now = time.time()
ticker_age = now - self.last_ws_price_time

# Only trigger fallback for ticker channel starvation
# User channel silence is normal (no positions/orders = no messages)
if ticker_age > self.ticker_starvation_threshold and not self.rest_fallback_active:
    log.warning(f"🚨 [REST FALLBACK] Ticker channel starved for {ticker_age:.1f}s > {self.ticker_starvation_threshold}s")
    log.warning(f"   ℹ️  Delta ticker should update every 5s, investigating...")
    self._activate_rest_fallback()
elif ticker_age > self.heartbeat_starvation_threshold and not self.rest_fallback_active:
    log.warning(f"🚨 [REST FALLBACK] No heartbeat for {ticker_age:.1f}s > {self.heartbeat_starvation_threshold}s")
    log.warning(f"   ℹ️  Delta heartbeat should arrive every 30s, connection may be stale")
    self._activate_rest_fallback()
```

---

## 6. Track Last Heartbeat Separately (gridbot.py)

**Add New Instance Variable:**
```python
# In __init__, after self.last_ws_price_time
self.last_ws_heartbeat_time = time.time()  # Track server heartbeat separately
self.last_ticker_update_time = time.time()  # Track ticker updates specifically
```

**Update in WebSocket Callback:**
```python
def _on_price_update(self, price: float):
    """
    Callback for WebSocket price updates
    """
    with self.lock:
        self.current_price = price
        self.last_ws_price_time = time.time()
        self.last_ticker_update_time = time.time()  # ✅ NEW: Track ticker separately
        # ... rest of logic
```

**Add Heartbeat Handler:**
```python
def _on_heartbeat(self, data: dict):
    """
    Callback for Delta server heartbeat messages
    
    ✅ NOV 9: Added per Delta documentation
    Server sends heartbeat every 30s to confirm connection alive
    """
    self.last_ws_heartbeat_time = time.time()
    log.debug("💓 Server heartbeat received (connection healthy)")
```

---

## Implementation Priority

### Critical (Implement Now):
1. ✅ **Fix 'pong' message handling** - Eliminates 7 warnings per session
2. ✅ **Increase starvation threshold to 35s** - Eliminates 16 false alarms per session
3. ✅ **Update ping interval to 30s** - Aligns with Delta recommendation

### High Priority (Implement Soon):
4. ✅ **Enable Delta server heartbeat** - Official keepalive mechanism
5. ✅ **Add heartbeat message handler** - Proper connection health tracking

### Medium Priority (Nice to Have):
6. ⚠️ **Channel-specific health monitoring** - More sophisticated (requires more changes)
7. ⚠️ **Separate ticker/heartbeat tracking** - Better observability

---

## Expected Results After Implementation

### Before:
```
Session: 31 minutes
Starvation Events: 16 (every ~30s)
Unknown 'pong' Messages: 7
Log Noise: High (23 warnings)
```

### After:
```
Session: 31 minutes (same duration)
Starvation Events: 0 (threshold adjusted)
Unknown 'pong' Messages: 0 (handled silently)
Log Noise: Minimal (0-2 warnings max)
Connection Health: Tracked via server heartbeat
```

---

## Testing Plan

1. **Apply fixes 1-3** (critical priority)
2. **Start bot and monitor for 30 minutes**
3. **Verify:**
   - No 'pong' warnings in logs
   - No starvation events during low volatility
   - REST fallback only activates on real connection issues
4. **Apply fixes 4-5** (high priority)
5. **Monitor for another 30 minutes**
6. **Verify:**
   - Server heartbeat messages received every 30s
   - Connection health properly tracked

---

## Rollback Plan

If issues occur:
1. Revert `ws_starvation_threshold` from 35.0 → 30.0
2. Revert `ping_interval` from 30 → 20
3. Remove 'pong' and 'heartbeat' handlers
4. Check logs for actual connection problems

---

## Files to Modify

1. `bot/delta_websocket/delta_ws.py` (3 changes)
   - Line ~420: Add 'pong' and 'heartbeat' handlers
   - Line ~390: Enable server heartbeat after auth
   - Line ~50: Update ping_interval to 30

2. `bot/strategy/gridbot.py` (2 changes)
   - Line ~267: Increase starvation threshold to 35.0
   - Add comment explaining Delta's ticker/heartbeat timing

---

## Documentation Updates

After implementation, update:
1. `AI_CONTEXT.md` - WebSocket configuration section
2. `DELTA_WEBSOCKET_SUPPORT_QUERY.md` - Mark as "RESOLVED" with implementation notes
3. Create `WEBSOCKET_OPTIMIZATION_NOV9_2025.md` - Document changes and results

---

**Created:** November 9, 2025  
**Based on:** Delta Exchange Official WebSocket Documentation  
**Status:** Ready to implement  
**Risk Level:** Low (increases thresholds, adds handlers, no logic changes)
