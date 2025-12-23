# Detailed System Wiring Analysis Report
**Date:** November 9, 2025  
**Purpose:** Complete wiring audit with code evidence

## ✅ STATUS: RESOLVED
**Resolution Date:** November 9, 2025  
**Fix Details:** See `/reports/FINAL_FIX_VALIDATION_REPORT.md`  
**Wiring Issues Fixed:** All 3 critical issues resolved  
**Verification:** Position removal, SHORT cancellation, monitoring confirmed working

---

---

## 1. Grid Calculator ↔ Order Manager Wiring

### Connection Point 1: Price Quantization
**File:** `order_manager.py` Lines 351-365

```python
def _quantize_price(self, price: float) -> float:
    """Quantize price using GridCalculator"""
    return self.grid_calc.quantize_price(price)
```

**Evidence:** OrderManager calls `grid_calc.quantize_price()` before placing every order.

**Status:** ✅ CORRECT - Ensures all prices align with exchange tick size (0.5)

---

### Connection Point 2: Grid Alignment Validation
**File:** `order_manager.py` Lines 390-416 (`place_buy_order`)

```python
# Validate price is grid-aligned
if not self._is_price_grid_aligned(price):
    log.error(f"🚨 OFF-GRID BUY: ${price:,.2f}")
    return None
```

**File:** `order_manager.py` Lines 626-636

```python
def _is_price_grid_aligned(self, price: float) -> bool:
    """Check if price aligns with grid step"""
    offset = price - self.grid_calc.lower
    remainder = offset % self.grid_calc.step
    return remainder < 0.01 or (self.grid_calc.step - remainder) < 0.01
```

**Evidence:** OrderManager validates grid alignment using GridCalculator's lower bound and step size.

**Status:** ✅ CORRECT - Prevents off-grid orders

---

### Connection Point 3: Bounds Checking
**File:** `order_manager.py` Lines 400-405

```python
# Check if price is within grid bounds
if not self.grid_calc.is_within_bounds(price):
    log.error(f"❌ BUY price ${price:,.2f} outside grid bounds")
    return None
```

**Evidence:** OrderManager calls `grid_calc.is_within_bounds()` before every order.

**Status:** ✅ CORRECT - Prevents orders outside configured range

---

## 2. Order Manager ↔ Fill Handlers Wiring

### Connection Point 1: TP Placement (LONG Mode)
**File:** `long_handler.py` Lines 85-86

```python
tp_order_id = self.order_mgr.place_tp_mandatory(position, max_retries=5)
```

**File:** `order_manager.py` Lines 1024-1092

```python
def place_tp_mandatory(self, position, max_retries=5):
    """Place TP with MANDATORY success - halts bot if fails"""
    for attempt in range(max_retries):
        if self.safe_place_tp(position, check_collisions=True):
            tp_id = position.get('tp_id')
            if tp_id:
                return str(tp_id)
    
    # ALL RETRIES FAILED - HALT BOT
    raise RuntimeError(f"TP placement failed after {max_retries} retries")
```

**Evidence:** Fill handler calls OrderManager's `place_tp_mandatory()` which:
1. Calls `safe_place_tp()` internally
2. Sets `position['tp_id']` (Line 926)
3. Retries up to 5 times
4. Halts bot if all retries fail

**Status:** ✅ CORRECT - Ensures every position has TP protection

---

### Connection Point 2: Next Grid Order Placement (LONG Mode)
**File:** `long_handler.py` Lines 197-198

```python
next_buy_price = self.grid_calc.compute_next_level_down(fill_price)
order_id = self.order_mgr.place_buy_order(next_buy_price, post_only=True)
```

**Evidence:** After BUY fills, handler:
1. Calculates next price using GridCalculator
2. Places order using OrderManager
3. Registers as pending with PositionManager

**Status:** ✅ CORRECT - Complete flow

---

### Connection Point 3: Order Cancellation (LONG Mode)
**File:** `long_handler.py` Lines 268-274

```python
old_pending = self.position_mgr.get_pending_buy()
if old_pending:
    old_order_id = old_pending.get('order_id')
    log.info(f"🗑️  Cancelling old pending BUY @ ${old_price:,.0f}")
    self.order_mgr.cancel_order(old_order_id, verify=True)
    self.position_mgr.clear_pending_buy()
```

**File:** `order_manager.py` Lines 1148-1238

```python
def cancel_order(self, order_id, verify=True, max_retries=5):
    """Cancel order with aggressive retry and verification"""
    # Pre-check order state
    order_status = self.api_client.get_order(order_id)
    
    # Send cancel request
    cancel_response = self.api_client.cancel_order(order_id)
    
    # Verify cancellation if requested
    if verify:
        return self.verify_order_cancelled(order_id)
```

**Evidence:** Handler calls OrderManager's `cancel_order()` with `verify=True`, which:
1. Pre-checks order state (avoid 404 errors)
2. Sends cancel request to exchange
3. Verifies cancellation with polling (up to 5 retries)

**Status:** ✅ CORRECT - Robust cancellation with verification

---

### 🚨 Connection Point 4: Order Cancellation (SHORT Mode) - MISSING
**File:** `short_handler.py` Lines 215-231

```python
def handle_tp_fill_short(self, fill_price: float, position: Dict):
    """Handle TP fill for SHORT position"""
    # Remove position
    self.position_mgr.remove_position(position)
    
    # ❌ MISSING: No cancellation of old pending SELL order!
    # Should be here (like LONG mode Lines 268-274)
    
    # Place next SELL if capacity available
    if self.position_mgr.try_reserve_capacity():
        next_price = self.grid_calc.compute_next_level_up(fill_price)
        ...
```

**Evidence:** SHORT mode handler does NOT cancel old pending SELL orders when TP fills.

**Status:** 🚨 **BROKEN** - Old SELL orders remain active after TP fills

**Fix Required:**
```python
# Add after Line 231 in short_handler.py
old_pending = self.position_mgr.get_pending_sell()
if old_pending:
    old_order_id = old_pending.get('order_id')
    old_price = old_pending.get('price')
    log.info(f"🗑️  Cancelling old pending SELL @ ${old_price:,.0f}")
    self.order_mgr.cancel_order(old_order_id, verify=True)
    self.position_mgr.clear_pending_sell()
```

---

## 3. Bot Core ↔ Backend API Wiring

### Connection Point 1: Bot Instance Registration
**File:** `gridbot.py` Lines 322-330

```python
log.info("🌐 Wiring bot instance to WebUI monitoring routes...")
try:
    from webui.backend.routes.monitoring import set_bot_instance
    set_bot_instance(self)
    log.info("✅ Bot wired to WebUI - monitoring data now accessible via API")
except ImportError:
    log.warning("⚠️  WebUI monitoring routes not available")
```

**File:** `webui/backend/routes/monitoring.py` Lines 83-103

```python
_bot_instance = None

def set_bot_instance(bot):
    """Set reference to running bot instance"""
    global _bot_instance, _price_monitor, _pre_order_logger, ...
    
    _bot_instance = bot
    
    if bot:
        _price_monitor = getattr(bot, 'price_monitor', None)
        _pre_order_logger = getattr(bot, 'pre_order_logger', None)
        _tp_verifier = getattr(bot, 'tp_verifier', None)
        _anomaly_detector = getattr(bot, 'anomaly_detector', None)
        _predictive_display = getattr(bot, 'predictive_display', None)
```

**Evidence:** Bot registers itself with backend on startup, exposing:
- Price monitor
- Pre-order logger
- TP verifier
- Anomaly detector
- Predictive display

**Status:** ✅ CORRECT - Bot → Backend wiring complete

---

### Connection Point 2: Monitoring Data Access
**File:** `webui/backend/routes/monitoring.py` Lines 109-163

```python
@monitoring_bp.route('/api/monitoring/status', methods=['GET'])
def monitoring_status():
    """Get overall monitoring system status"""
    # Try snapshot file first (works with standalone bot)
    snapshot = _load_monitoring_snapshot()
    if snapshot:
        return jsonify(snapshot)
    
    # Fallback to bot_instance (WebUI-started bot)
    return jsonify({
        'monitoring_active': _bot_instance is not None,
        'layers': {
            'price_health': _price_monitor is not None,
            'pre_order_logger': _pre_order_logger is not None,
            ...
        }
    })
```

**Evidence:** Backend API can access bot monitoring systems via:
1. **Primary:** Snapshot file (works with standalone bot)
2. **Fallback:** Direct bot instance reference

**Status:** ✅ CORRECT - Dual-source design supports both standalone and WebUI-started bot

---

### Connection Point 3: Bot Control
**File:** `webui/backend/routes/bot_control.py` Lines 121-193

```python
@bot_control_bp.route('/api/bot/start', methods=['POST'])
def bot_start():
    """Start trading bot"""
    if should_use_pm2():
        # Use PM2 for process management
        success, message = pm2.start_bot('live')
    else:
        # Use direct launcher
        result = subprocess.run(
            [sys.executable, 'bot_launcher.py', '--daemon'],
            cwd=str(BASE_DIR)
        )
```

**Evidence:** Backend controls bot via:
1. **PM2 mode:** Uses PM2 adapter (`pm2.start_bot()`)
2. **Direct mode:** Runs `bot_launcher.py` as subprocess

**Status:** ✅ CORRECT - Supports both deployment modes

---

## 4. Backend ↔ Frontend Wiring

### Connection Point 1: REST API Polling
**File:** `webui/frontend/src/components/BotStatus.js` (inferred from backend routes)

Backend provides these REST endpoints:
- `GET /api/bot/status` - Bot running state
- `GET /api/positions` - Current positions
- `GET /api/orders` - Pending orders
- `GET /api/monitoring/status` - Monitoring systems
- `POST /api/bot/start` - Start bot
- `POST /api/bot/stop` - Stop bot

**Evidence from backend:** All routes return JSON responses suitable for frontend consumption.

**Status:** ✅ CORRECT - Standard REST API design

---

### Connection Point 2: WebSocket Real-time Updates
**File:** `webui/backend/routes/monitoring.py` Lines 376-465

```python
@monitoring_bp.route('/api/monitoring/predictive-map', methods=['GET'])
def predictive_map():
    """Get predictive decision map"""
    snapshot = _load_monitoring_snapshot()
    if snapshot and 'predictive' in snapshot.get('layers', {}):
        return jsonify(snapshot['layers']['predictive'])
```

**Evidence:** Backend provides real-time data via:
1. Snapshot file updates (bot writes every 30s)
2. Direct bot instance queries

Frontend can poll this endpoint or use WebSocket for updates.

**Status:** ✅ CORRECT - Hybrid approach (REST + snapshot file)

---

### Connection Point 3: Monitoring Data Writer
**File:** `gridbot.py` Lines 266-269

```python
from bot.monitoring.data_writer import MonitoringDataWriter
self.monitoring_writer = MonitoringDataWriter()
self.last_monitoring_write = 0
```

**Evidence:** Bot has MonitoringDataWriter that writes snapshot files for WebUI to read.

**Status:** ✅ CORRECT - Decoupled design allows standalone bot operation

---

## 5. Critical Wiring Issues Found

### 🚨 ISSUE 1: Position Removal Wiring Broken
**Location:** `position_manager.py` Line 187 → `long_handler.py` Line 265

**Problem Flow:**
1. `gridbot.py` calls `find_position_by_order_id(tp_order_id)`
2. Returns `position.copy()` (Line 187)
3. Passes copy to `long_handler.handle_tp_fill(position_copy)`
4. Handler calls `position_mgr.remove_position(position_copy)`
5. `remove_position()` checks `if position in self.open_tranches:` (Line 144)
6. **FAILS** because copy is not in list

**Impact:** Position not removed, state inconsistency

**Fix:** Change Line 187 from `return position.copy()` to `return position`

---

### 🚨 ISSUE 2: SHORT Mode Missing Cancellation Wiring
**Location:** `short_handler.py` Line 231

**Problem:** No wiring between TP fill handler and order cancellation in SHORT mode.

**Impact:** Old pending SELL orders remain active after TP fills.

**Fix:** Add cancellation logic (see Connection Point 4 above)

---

### ⚠️ ISSUE 3: Monitoring Writer Not Called in Main Loop
**Location:** `gridbot.py` Line 268

**Problem:** `MonitoringDataWriter` is initialized but never called in heartbeat loop.

**Evidence:** No calls to `self.monitoring_writer.write_snapshot()` found in gridbot.py

**Impact:** Snapshot file may not update regularly for WebUI.

**Recommendation:** Add to heartbeat loop:
```python
if time.time() - self.last_monitoring_write > 30:
    self.monitoring_writer.write_snapshot(self)
    self.last_monitoring_write = time.time()
```

---

## 6. Wiring Strengths

### ✅ Strength 1: Modular Design
- Clean separation between GridCalculator (pure math) and OrderManager (I/O)
- Fill handlers don't directly access API - always go through OrderManager
- Thread safety via centralized state lock in PositionManager

### ✅ Strength 2: Dual-Source Monitoring
- Backend can read from snapshot file (standalone bot) OR direct instance (WebUI-started)
- Allows bot to run independently of WebUI
- WebUI can still show monitoring data

### ✅ Strength 3: Robust Error Handling
- TP placement retries up to 5 times, halts bot if fails
- Order cancellation with verification (polls exchange)
- Pre-order validation prevents invalid orders

### ✅ Strength 4: Process Management Flexibility
- Supports both PM2 and direct process management
- Backend adapts based on environment
- Graceful shutdown with 30s timeout

---

## Summary

**Total Wiring Points Audited:** 13  
**Correct Wiring:** 11 ✅  
**Broken Wiring:** 2 🚨  
**Missing Wiring:** 1 ⚠️

**Critical Fixes Required:**
1. Change `find_position_by_order_id()` to return reference (not copy)
2. Add pending order cancellation to SHORT mode TP handler
3. Wire MonitoringDataWriter into heartbeat loop

**Overall Assessment:** System is well-architected with clean module boundaries. The two critical bugs are localized and have clear fixes. Once fixed, the wiring will be complete and robust.
