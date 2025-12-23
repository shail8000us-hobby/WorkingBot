# 🎯 Simple Grid Seeding + LONG/SHORT Toggle - Implementation Plan

**Date**: November 2, 2025  
**Objective**: Implement simple grid seeding (20 lines) + LONG/SHORT toggle button  
**Philosophy**: KISS - Reuse existing code, minimal changes

---

## 📋 PART 1: Simple Grid Seeding Implementation

### Step 1: Add Configuration Parameters (2 minutes)

**File**: `grid_config.env`

```bash
# Add to grid_config.env (anywhere, suggest after GRIDBOT_STEP)

# ═══════════════════════════════════════════════════════════════════════════
# Simple Grid Seeding (Fill Missed Grid Levels)
# ═══════════════════════════════════════════════════════════════════════════

# Number of initial positions to create (0 = disabled)
GRIDBOT_SEED_INITIAL_COUNT=0
# Example: Market at 110k, REF at 115k, COUNT=5
# → Creates 5 grid orders at: 109k, 108k, 107k, 106k, 105k
# Bot will manage TPs automatically using existing logic

# Grid direction (LONG = buy below, SHORT = sell above)
GRIDBOT_GRID_MODE=LONG
# LONG  = Buy positions below current price (bullish)
# SHORT = Sell positions above current price (bearish)
```

---

### Step 2: Add Helper Method to GridBot (5 minutes)

**File**: `bot/strategy/gridbot.py`

**Location**: Add after `__init__()` method, before `start()` method

```python
def seed_missed_grid_levels(self, count: int):
    """
    Simple grid seeding - Fill missed grid levels using existing order functions
    
    For LONG: Place BUY orders below current price
    For SHORT: Place SELL orders above current price
    
    No new modules needed - reuses existing place_buy_order()/place_sell_order()
    Bot handles TPs automatically using existing fill detection logic
    """
    if count <= 0:
        return
    
    current_price = self.current_price
    mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
    
    log.info("=" * 70)
    log.info(f"🌱 SEEDING {count} MISSED GRID LEVELS ({mode} MODE)")
    log.info(f"📍 Current Price: ${current_price:,.0f}")
    log.info("=" * 70)
    
    for i in range(count):
        if mode == 'LONG':
            # Buy below current price (going down)
            level = current_price - (i + 1) * self.grid_calc.step
            
            if level >= self.grid_calc.lower:
                order_id = self.order_mgr.place_buy_order(price=level, post_only=True)
                if order_id:
                    log.info(f"  ✅ Grid BUY placed @ ${level:,.0f}")
            else:
                log.warning(f"  ⚠️  Level ${level:,.0f} below grid lower bound, stopping")
                break
        
        elif mode == 'SHORT':
            # Sell above current price (going up)
            level = current_price + (i + 1) * self.grid_calc.step
            
            if level <= self.grid_calc.upper:
                order_id = self.order_mgr.place_sell_order(price=level, post_only=True)
                if order_id:
                    log.info(f"  ✅ Grid SELL placed @ ${level:,.0f}")
            else:
                log.warning(f"  ⚠️  Level ${level:,.0f} above grid upper bound, stopping")
                break
    
    log.info("=" * 70)
    log.info(f"✅ SEEDING COMPLETE - Bot will manage TPs automatically")
    log.info("=" * 70)
```

---

### Step 3: Call Seeding at Startup (3 minutes)

**File**: `bot/strategy/gridbot.py`

**Location**: In `start()` method, after reconciliation, before placing first order

Find this section (around line 640):
```python
# Only proceed if no pending BUY already exists (from bulk seeding)
if not self.position_mgr.get_pending_buy():
    # 🔒 CRITICAL SAFETY CHECK: Check volatility BEFORE placing initial order
```

**Replace with**:
```python
# ================================================================
# 🌱 SIMPLE GRID SEEDING (if enabled and no positions exist)
# ================================================================
positions = self.position_mgr.get_positions()
seed_count = int(os.getenv('GRIDBOT_SEED_INITIAL_COUNT', '0'))

if not positions and seed_count > 0:
    self.seed_missed_grid_levels(count=seed_count)
    # Seeding placed orders, they'll fill and trigger normal grid logic
    log.info("ℹ️  Grid seeding active - bot will continue normally")
    # Skip placing initial order since we just seeded multiple orders
else:
    # ================================================================
    # NORMAL GRID STARTUP (traditional one-order-at-a-time)
    # ================================================================
    
    # 🔒 CRITICAL SAFETY CHECK: Check volatility BEFORE placing initial order
```

---

### Step 4: Test (5 minutes)

```bash
# 1. Set configuration
echo "GRIDBOT_SEED_INITIAL_COUNT=3" >> grid_config.env
echo "GRIDBOT_GRID_MODE=LONG" >> grid_config.env

# 2. Compile
python3 -m py_compile bot/strategy/gridbot.py

# 3. Test run
python3 bot/run.py

# Expected output:
# 🌱 SEEDING 3 MISSED GRID LEVELS (LONG MODE)
# ✅ Grid BUY placed @ $109,000
# ✅ Grid BUY placed @ $108,000
# ✅ Grid BUY placed @ $107,000
# ✅ SEEDING COMPLETE
```

**Total Implementation Time**: ~15 minutes  
**Lines Added**: ~40 lines (vs 3,300 deleted)

---

## 📋 PART 2: LONG/SHORT Toggle Button (WebUI)

### Step 1: Add Backend API Endpoint (10 minutes)

**File**: `webui/backend/routes/config.py` (or create new file `webui/backend/routes/grid_mode.py`)

```python
from flask import Blueprint, jsonify, request
import os
from pathlib import Path

grid_mode_bp = Blueprint('grid_mode', __name__)

CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "grid_config.env"

@grid_mode_bp.route('/api/bot/grid-mode', methods=['GET'])
def get_grid_mode():
    """Get current grid mode (LONG/SHORT)"""
    try:
        mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
        return jsonify({
            'success': True,
            'mode': mode,
            'description': 'LONG = Buy below, SHORT = Sell above'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@grid_mode_bp.route('/api/bot/grid-mode', methods=['POST'])
def toggle_grid_mode():
    """Toggle between LONG and SHORT mode"""
    try:
        data = request.get_json()
        new_mode = data.get('mode', '').upper()
        
        if new_mode not in ['LONG', 'SHORT']:
            return jsonify({
                'success': False,
                'error': 'Mode must be LONG or SHORT'
            }), 400
        
        # Read config file
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Update GRIDBOT_GRID_MODE line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('GRIDBOT_GRID_MODE='):
                lines[i] = f'GRIDBOT_GRID_MODE={new_mode}\n'
                updated = True
                break
        
        # If not found, append
        if not updated:
            lines.append(f'\nGRIDbot_GRID_MODE={new_mode}\n')
        
        # Write back
        with open(CONFIG_FILE, 'w') as f:
            f.writelines(lines)
        
        # Update environment variable
        os.environ['GRIDBOT_GRID_MODE'] = new_mode
        
        return jsonify({
            'success': True,
            'mode': new_mode,
            'message': f'Grid mode switched to {new_mode}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### Step 2: Register Blueprint (2 minutes)

**File**: `webui/backend/routes/__init__.py`

```python
from .grid_mode import grid_mode_bp  # Add this import

__all__ = [
    # ... existing blueprints ...
    'grid_mode_bp',  # Add this
]
```

**File**: `webui/backend/app.py`

```python
# In imports section
from .routes import (
    # ... existing imports ...
    grid_mode_bp  # Add this
)

# In blueprints list
blueprints = [
    # ... existing blueprints ...
    grid_mode_bp,  # Add this
]
```

---

### Step 3: Add React Toggle Component (15 minutes)

**File**: `webui/frontend/src/components/GridModeToggle.jsx` (new file)

```jsx
import React, { useState, useEffect } from 'react';

const GridModeToggle = () => {
  const [mode, setMode] = useState('LONG');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchMode();
  }, []);

  const fetchMode = async () => {
    try {
      const res = await fetch('http://localhost:5555/api/bot/grid-mode');
      const data = await res.json();
      if (data.success) {
        setMode(data.mode);
      }
    } catch (err) {
      console.error('Error fetching grid mode:', err);
    }
  };

  const toggleMode = async () => {
    const newMode = mode === 'LONG' ? 'SHORT' : 'LONG';
    setLoading(true);
    setMessage('');

    try {
      const res = await fetch('http://localhost:5555/api/bot/grid-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });

      const data = await res.json();
      
      if (data.success) {
        setMode(newMode);
        setMessage(`✅ Switched to ${newMode} mode`);
        setTimeout(() => setMessage(''), 3000);
      } else {
        setMessage(`❌ Error: ${data.error}`);
      }
    } catch (err) {
      setMessage(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Grid Mode
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {mode === 'LONG' 
              ? '📈 Buying below current price (Bullish)' 
              : '📉 Selling above current price (Bearish)'}
          </p>
        </div>

        <button
          onClick={toggleMode}
          disabled={loading}
          className={`
            px-6 py-3 rounded-lg font-semibold text-white transition-all
            ${mode === 'LONG' 
              ? 'bg-green-600 hover:bg-green-700' 
              : 'bg-red-600 hover:bg-red-700'}
            ${loading ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}
          `}
        >
          {loading ? '⏳ Switching...' : (
            <>
              {mode === 'LONG' ? '🟢 LONG' : '🔴 SHORT'}
              <span className="ml-2 text-xs">
                (click to toggle)
              </span>
            </>
          )}
        </button>
      </div>

      {message && (
        <div className={`mt-4 p-3 rounded ${
          message.includes('✅') 
            ? 'bg-green-100 text-green-800' 
            : 'bg-red-100 text-red-800'
        }`}>
          {message}
        </div>
      )}

      <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
        <p className="text-sm text-yellow-800 dark:text-yellow-200">
          ⚠️ <strong>Important:</strong> Changing mode will affect NEW orders only. 
          Existing positions will continue with their current TPs.
        </p>
      </div>
    </div>
  );
};

export default GridModeToggle;
```

---

### Step 4: Add to WebUI (5 minutes)

**File**: `webui/frontend/src/App.js`

```jsx
// Import at top
import GridModeToggle from './components/GridModeToggle';

// In the Configuration section, add a new CollapsibleCard:
<CollapsibleCard
  id="grid-mode"
  title="🔄 Grid Mode (LONG/SHORT)"
  subtitle="Toggle between bullish (buy) and bearish (sell) strategies"
  accent="purple"
  defaultOpen={true}
>
  <GridModeToggle />
</CollapsibleCard>
```

---

### Step 5: Test WebUI (5 minutes)

```bash
# 1. Start backend
launchctl start com.gridbot.webui

# 2. Start frontend (if not running)
cd webui/frontend
npm start

# 3. Open browser
http://localhost:3000

# 4. Go to Configuration tab
# 5. Find "Grid Mode (LONG/SHORT)" section
# 6. Click the toggle button
# 7. Verify it switches between LONG and SHORT
# 8. Check grid_config.env file updated
```

---

## 📊 Implementation Summary

### Part 1: Simple Grid Seeding
- **Files Modified**: 2 (gridbot.py, grid_config.env)
- **Lines Added**: ~40 lines
- **Time**: ~15 minutes
- **Result**: Fill missed grid levels with existing functions

### Part 2: LONG/SHORT Toggle
- **Files Created**: 2 (grid_mode.py, GridModeToggle.jsx)
- **Files Modified**: 3 (routes/__init__.py, app.py, App.js)
- **Lines Added**: ~150 lines
- **Time**: ~40 minutes
- **Result**: Toggle between LONG and SHORT in WebUI

### Total Implementation
- **Total Time**: ~1 hour
- **Total Lines**: ~190 lines
- **vs Bulk Seeding**: 3,300 lines deleted, 190 lines added = **94% code reduction**

---

## 🎯 Expected Behavior

### Scenario 1: LONG Mode with Seeding
```bash
GRIDBOT_GRID_MODE=LONG
GRIDBOT_SEED_INITIAL_COUNT=3
```

**Current Price**: $110,000  
**Result**:
- Bot places 3 BUY orders: $109k, $108k, $107k
- Orders fill as market drops
- Bot automatically places TPs using existing logic
- Grid continues normally

### Scenario 2: SHORT Mode with Seeding
```bash
GRIDBOT_GRID_MODE=SHORT
GRIDBOT_SEED_INITIAL_COUNT=3
```

**Current Price**: $110,000  
**Result**:
- Bot places 3 SELL orders: $111k, $112k, $113k
- Orders fill as market rises
- Bot automatically places TPs using existing logic
- Grid continues normally

### Scenario 3: Toggle Mode in WebUI
1. Bot running in LONG mode
2. User clicks "LONG" button → switches to "SHORT"
3. Config file updated
4. NEW orders use SHORT logic
5. Existing positions unchanged

---

## ⚠️ Important Notes

1. **Restart Required**: After changing mode via WebUI, restart bot for seeding to use new mode
2. **Existing Positions**: Mode toggle doesn't affect existing positions/orders
3. **Seeding Runs Once**: At startup, if no positions exist
4. **Uses Existing Logic**: All TP management handled by existing fill detection

---

## 🚀 Next Steps

1. Implement Part 1 (Simple Seeding) - 15 min
2. Test with LONG mode - 5 min
3. Test with SHORT mode - 5 min
4. Implement Part 2 (Toggle Button) - 40 min
5. Test WebUI toggle - 10 min

**Total**: ~75 minutes for complete implementation

---

**Ready to proceed?** Let me know which part you want to implement first!
