# Option B Implementation Guide - Use NEW Standalone Recovery

**Date:** November 20, 2025, 1:52 AM  
**Status:** 🔄 **IN PROGRESS** - File corruption detected, manual fix required

---

## 🚨 **CRITICAL: File Corruption Detected**

**File:** `bot/strategy/async_gridbot.py`  
**Error:** IndentationError at line 1037  
**Cause:** Incomplete removal of OLD recovery system

---

## 🛠️ **Manual Fix Required**

### **Step 1: Fix async_gridbot.py Syntax Error**

**Location:** Lines 1034-1046

**Current (BROKEN):**
```python
    # ========================================================================
    # CLEANUP MISALIGNED ORDERS
    # ========================================================================
        """Check for missed grid levels at startup and fill opportunistically with full safety checks.
        
        Returns:
            bool: True if recovery was executed, False otherwise
        """
        try:
            state = await self.position_actor.ask("GET_STATE", {}, timeout=3.0)
```

**Should Be:**
```python
    # ========================================================================
    # CLEANUP MISALIGNED ORDERS
    # ========================================================================
    
    async def _cleanup_misaligned_orders(self) -> None:
        try:
            log.info("🔄 Checking for misaligned grid orders...")
```

**Action:**
1. Open `bot/strategy/async_gridbot.py`
2. Go to line 1034
3. Delete lines 1037-1430 (entire OLD recovery system)
4. Ensure `_cleanup_misaligned_orders` method starts properly at line 1037

---

### **Step 2: Remove OLD Recovery System Completely**

**Delete these sections from async_gridbot.py:**

#### **Section 1: Recovery Flags (Line ~321)**
```python
# DELETE THESE LINES:
self._opportunistic_recovery_active = False
self._recovery_orders = {}
```

#### **Section 2: Recovery Config (Line ~350)**
```python
# DELETE THESE LINES:
self._startup_opportunistic_max = getattr(config.safety.volatility.opportunistic_recovery, 'max_orders_startup', 5)
self._startup_opportunistic_delay_ms = getattr(config.safety.volatility.opportunistic_recovery, 'execution_delay_ms', 300)
```

#### **Section 3: Recovery Methods (Lines 1038-1430)**
```python
# DELETE THESE ENTIRE METHODS:
async def _check_startup_opportunistic_recovery(self) -> bool:
async def _place_recovery_tp(self, grid_price: float, fill_price: float, order_id: str) -> bool:
async def _execute_startup_recovery(self, grid_levels: List[float]) -> None:
async def _check_runtime_opportunistic_recovery(self) -> bool:
async def _place_opportunistic_tp(self, position_data: Dict[str, Any]) -> bool:
```

#### **Section 4: Recovery Checks in start() (Line ~1464)**
```python
# DELETE THESE LINES:
# Check Guardian status and opportunistic recovery
opp_recovery_enabled = getattr(config.safety.volatility.opportunistic_recovery, 'enabled', False)
if opp_recovery_enabled:
    log.info(f"✅ Opportunistic Recovery: ENABLED (IV threshold: {config.safety.volatility.opportunistic_recovery.iv_threshold}%)")
    await self._check_startup_opportunistic_recovery()
else:
    log.info("ℹ️  Opportunistic Recovery: DISABLED")
```

#### **Section 5: Recovery Check in _process_fill (Line ~1836)**
```python
# DELETE THESE LINES:
if self._opportunistic_recovery_active:
    log.info(f"⏭️  RECOVERY MODE ACTIVE - Skipping saga for order {order_id}")
    log.info(f"   Recovery system will handle TP placement")
    return
```

#### **Section 6: Recovery Check in _check_and_place_entry_order (Line ~2622)**
```python
# DELETE THESE LINES:
if self._opportunistic_recovery_active:
    log.debug("⏸️  Normal grid operations suspended - Recovery in progress")
    return
```

#### **Section 7: Recovery Status in Logging (Line ~2825)**
```python
# DELETE THESE LINES:
elif self._opportunistic_recovery_active:
    trading_status = " | 🔄 RECOVERY MODE"
```

---

### **Step 3: Keep NEW Recovery System Files**

**These files should remain:**
- ✅ `bot/strategy/recovery/base_recovery_engine.py`
- ✅ `bot/strategy/recovery/startup_recovery.py`
- ✅ `bot/strategy/recovery/guardian_recovery.py`
- ✅ `bot/strategy/recovery/recovery_monitor.py`
- ✅ `bot/strategy/recovery/recovery_runner.py` (NEW - standalone)
- ✅ `bot/strategy/recovery/__init__.py`

---

### **Step 4: Update WebUI Backend**

**File:** `webui/backend/routes/recovery.py`

**Replace entire file with:**

```python
"""
Recovery system API endpoints - Standalone Recovery System.
Reads from recovery_state.json file.
Created: November 20, 2025
"""

from flask import Blueprint, jsonify, request
import json
from pathlib import Path
import time

bp = Blueprint('recovery', __name__, url_prefix='/api/recovery')

# State file path
RECOVERY_STATE_FILE = Path("data/recovery/recovery_state.json")


def load_recovery_state():
    """Load recovery state from file"""
    try:
        if RECOVERY_STATE_FILE.exists():
            with open(RECOVERY_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    
    return {
        'recovery_active': False,
        'recovered_grids': [],
        'timestamp': None,
        'last_recovery': None
    }


@bp.route('/health', methods=['GET'])
def get_recovery_health():
    """Get recovery system health status"""
    try:
        state = load_recovery_state()
        
        return jsonify({
            'success': True,
            'available': True,
            'health': {
                'status': 'active' if state.get('recovery_active') else 'idle',
                'last_recovery': state.get('last_recovery'),
                'recovered_grids_count': len(state.get('recovered_grids', []))
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'available': False
        }), 500


@bp.route('/combined-status', methods=['GET'])
def get_combined_status():
    """Get combined monitoring and recovery status"""
    try:
        state = load_recovery_state()
        
        return jsonify({
            'success': True,
            'monitoring': {
                'available': True,
                'status': 'operational'
            },
            'recovery': {
                'available': True,
                'active': state.get('recovery_active', False),
                'recovered_grids': state.get('recovered_grids', []),
                'last_recovery': state.get('last_recovery'),
                'timestamp': state.get('timestamp')
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/history', methods=['GET'])
def get_recovery_history():
    """Get recent recovery sessions"""
    try:
        state = load_recovery_state()
        
        return jsonify({
            'success': True,
            'sessions': [{
                'session_id': 'latest',
                'timestamp': state.get('last_recovery'),
                'recovered_count': len(state.get('recovered_grids', [])),
                'grids': state.get('recovered_grids', [])
            }] if state.get('last_recovery') else []
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/clear-state', methods=['POST'])
def clear_recovery_state():
    """Clear recovery state"""
    try:
        if RECOVERY_STATE_FILE.exists():
            RECOVERY_STATE_FILE.unlink()
        
        return jsonify({'success': True, 'message': 'Recovery state cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### **Step 5: Update WebUI Frontend**

**File:** `webui/frontend/src/components/panels/MonitoringRecoveryPanel.js`

**Update to show standalone recovery status:**

```javascript
// Around line 100-150, update the recovery section:

{data.recovery && data.recovery.available && (
  <Grid item xs={12} md={6}>
    <Card>
      <CardHeader 
        title="🔄 Standalone Recovery System"
        subheader={`Last recovery: ${data.recovery.last_recovery ? new Date(data.recovery.last_recovery * 1000).toLocaleString() : 'Never'}`}
      />
      <CardContent>
        <Box sx={{ mb: 2 }}>
          <Chip 
            label={data.recovery.active ? "Recovery Active" : "Idle"}
            color={data.recovery.active ? "warning" : "success"}
            icon={data.recovery.active ? <Refresh /> : <CheckCircle />}
          />
        </Box>
        
        {data.recovery.recovered_grids && data.recovery.recovered_grids.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Recovered Grids: {data.recovery.recovered_grids.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {data.recovery.recovered_grids.map(g => `$${g.toLocaleString()}`).join(', ')}
            </Typography>
          </Box>
        )}
        
        <Box sx={{ mt: 2 }}>
          <Button 
            size="small" 
            startIcon={<Delete />}
            onClick={() => handleClearState()}
          >
            Clear State
          </Button>
        </Box>
      </CardContent>
    </Card>
  </Grid>
)}
```

---

## 🚀 **How to Use the NEW Standalone Recovery System**

### **Manual Recovery (Before Bot Start):**

```bash
# Step 1: Run standalone recovery
python3 -m bot.strategy.recovery.recovery_runner

# Output:
# 🔄 STARTUP RECOVERY - STANDALONE MODE
# 🔒 Recovery active - normal grid trading paused
# 📊 Current market price: $88,866
# 📋 Found 3 missed grids: ['$89,000', '$88,500', '$88,000']
# 📍 Recovering grid 1/3: $89,000
# ✅ Grid $89,000 recovered successfully
# ...
# ✅ RECOVERY COMPLETE: 3/3 grids recovered
# 🔓 Recovery inactive - normal grid trading can resume

# Step 2: Start normal bot
python3 -m bot.strategy.async_gridbot

# Bot will check recovery_state.json and skip recovered grids
```

### **Check Recovery Status:**

```bash
# View state file
cat data/recovery/recovery_state.json

# Output:
{
  "recovery_active": false,
  "recovered_grids": [89000.0, 88500.0, 88000.0],
  "timestamp": 1700456789.123,
  "last_recovery": 1700456789.123
}
```

### **Clear Recovery State:**

```bash
# Remove state file to allow re-recovery
rm data/recovery/recovery_state.json
```

---

## ✅ **Benefits of Option B**

### **1. Clean Separation**
- ✅ Recovery = Standalone script
- ✅ Normal grid = Unchanged
- ✅ No code mixing
- ✅ Easy to maintain

### **2. No Conflicts**
- ✅ Recovery runs first
- ✅ Bot reads state file
- ✅ Skips recovered grids
- ✅ No race conditions

### **3. Better Control**
- ✅ Manual recovery before bot start
- ✅ Can test recovery independently
- ✅ Clear state management
- ✅ Audit trail in state file

### **4. WebUI Integration**
- ✅ Reads from state file
- ✅ Shows recovery status
- ✅ Displays recovered grids
- ✅ Can clear state

---

## 📋 **Implementation Checklist**

### **Phase 1: Fix Syntax Errors**
- [ ] Fix async_gridbot.py line 1037 indentation
- [ ] Remove OLD recovery methods (lines 1038-1430)
- [ ] Remove recovery flags and config
- [ ] Remove recovery checks in start()
- [ ] Remove recovery checks in _process_fill()
- [ ] Remove recovery checks in _check_and_place_entry_order()
- [ ] Test: `python3 -m py_compile bot/strategy/async_gridbot.py`

### **Phase 2: Update WebUI**
- [ ] Replace webui/backend/routes/recovery.py
- [ ] Update webui/frontend/src/components/panels/MonitoringRecoveryPanel.js
- [ ] Test: Start WebUI and check recovery panel
- [ ] Verify: Panel shows "Idle" status

### **Phase 3: Test Standalone Recovery**
- [ ] Run: `python3 -m bot.strategy.recovery.recovery_runner`
- [ ] Verify: recovery_state.json created
- [ ] Verify: Grids recovered successfully
- [ ] Check: WebUI shows recovered grids

### **Phase 4: Test Bot Integration**
- [ ] Start bot after recovery
- [ ] Verify: Bot reads recovery_state.json
- [ ] Verify: Bot skips recovered grids
- [ ] Verify: Normal grid trading works

### **Phase 5: Documentation**
- [ ] Update logic.md to reflect Option B
- [ ] Create user guide for standalone recovery
- [ ] Document state file format
- [ ] Add troubleshooting section

---

## 🎯 **Current Status**

**Completed:**
- ✅ Created standalone recovery_runner.py
- ✅ Added state file coordination methods to async_gridbot.py
- ✅ Identified all OLD recovery code to remove

**In Progress:**
- 🔄 Fixing async_gridbot.py syntax errors
- 🔄 Removing OLD recovery system

**Pending:**
- ⏳ Update WebUI backend
- ⏳ Update WebUI frontend
- ⏳ Test standalone recovery
- ⏳ Test bot integration
- ⏳ Update documentation

---

## 🚨 **Next Steps**

1. **IMMEDIATE:** Fix async_gridbot.py syntax error (manual edit required)
2. **THEN:** Remove all OLD recovery code
3. **THEN:** Update WebUI to read state file
4. **THEN:** Test complete system
5. **FINALLY:** Update documentation

**Estimated Time:** 2 hours

---

**Created:** November 20, 2025, 1:52 AM  
**Status:** 🔄 **MANUAL FIX REQUIRED**  
**Priority:** 🔴 **HIGH**
