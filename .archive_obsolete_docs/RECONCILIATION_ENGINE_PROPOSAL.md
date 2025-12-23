# Reconciliation Engine - Standalone System Proposal

**Date:** November 20, 2025, 2:04 AM  
**Status:** 💡 **PROPOSAL**

---

## 🎯 **The Problem**

Currently, reconciliation logic is **embedded** in `async_gridbot.py`:
- 300+ lines of reconciliation code mixed with trading logic
- Runs every 5 minutes inside the bot
- Hard to test independently
- Hard to maintain
- Hard to debug
- Tightly coupled with bot internals

---

## 💡 **The Solution**

Create a **standalone reconciliation engine** similar to the recovery system:

```
reconciliation_runner.py (standalone)
├── Runs independently
├── Reads bot state from files/database
├── Detects discrepancies
├── Writes corrections to action queue
└── Bot reads and executes corrections
```

---

## ✅ **Benefits**

### **1. Separation of Concerns**
- ✅ Reconciliation = Separate process
- ✅ Trading = Clean and focused
- ✅ No code mixing
- ✅ Easy to disable/enable

### **2. Better Testing**
- ✅ Test reconciliation independently
- ✅ Mock bot state easily
- ✅ Test edge cases without running bot
- ✅ Faster test cycles

### **3. Improved Reliability**
- ✅ Reconciliation crash doesn't crash bot
- ✅ Bot crash doesn't stop reconciliation
- ✅ Independent monitoring
- ✅ Separate logging

### **4. Easier Maintenance**
- ✅ Update reconciliation without touching bot
- ✅ Clear boundaries
- ✅ Single responsibility
- ✅ Better code organization

### **5. Scalability**
- ✅ Run reconciliation on different schedule
- ✅ Run multiple reconciliation instances
- ✅ Distribute load
- ✅ Independent scaling

---

## 🏗️ **Architecture**

### **Current (Embedded):**
```
async_gridbot.py (3,725 lines)
├── Trading logic
├── Reconciliation logic ❌ (300+ lines)
│   ├── _reconciliation_loop()
│   ├── _verify_tp_protection()
│   ├── _emergency_tp_placement()
│   ├── _investigate_missing_order()
│   └── _process_missed_fill()
└── Other systems
```

**Problems:**
- Mixed concerns
- Hard to test
- Tightly coupled
- Bot must be running

---

### **Proposed (Standalone):**
```
reconciliation_runner.py (NEW - 400 lines)
├── Load bot state from files
├── Query exchange for truth
├── Detect discrepancies
│   ├── Missed fills
│   ├── Unprotected positions
│   ├── Orphaned orders
│   └── State corruption
├── Generate correction actions
└── Write to action queue

reconciliation_state.json
├── last_check_time
├── discrepancies_found
├── corrections_applied
└── pending_actions

async_gridbot.py (3,400 lines)
├── Trading logic only
├── Read action queue
├── Execute corrections
└── Report status
```

**Benefits:**
- Clean separation
- Easy to test
- Loosely coupled
- Works even if bot is down

---

## 📋 **What Reconciliation Engine Would Do**

### **1. Missed Fill Detection**
```python
# Check for fills that bot missed
for order_id in bot_pending_orders:
    exchange_order = query_exchange(order_id)
    if exchange_order.status == "filled":
        # Bot thinks pending, exchange says filled
        action = {
            "type": "process_missed_fill",
            "order_id": order_id,
            "fill_price": exchange_order.fill_price,
            "fill_size": exchange_order.fill_size
        }
        write_to_action_queue(action)
```

### **2. Unprotected Position Detection**
```python
# Check for positions without TP orders
for position in bot_positions:
    tp_order_id = position.tp_order_id
    exchange_order = query_exchange(tp_order_id)
    
    if not exchange_order or exchange_order.status != "open":
        # Position has no TP protection
        action = {
            "type": "place_emergency_tp",
            "position_id": position.id,
            "entry_price": position.entry_price,
            "tp_price": calculate_tp_price(position)
        }
        write_to_action_queue(action)
```

### **3. Orphaned Order Detection**
```python
# Check for orders on exchange that bot doesn't know about
exchange_orders = get_all_open_orders()
bot_order_ids = get_bot_tracked_orders()

for order in exchange_orders:
    if order.id not in bot_order_ids:
        # Orphaned order - bot doesn't know about it
        action = {
            "type": "cancel_orphaned_order",
            "order_id": order.id,
            "reason": "not_tracked_by_bot"
        }
        write_to_action_queue(action)
```

### **4. State Corruption Detection**
```python
# Check for impossible states
for position in bot_positions:
    if position.entry_price is None:
        action = {
            "type": "flag_corrupted_position",
            "position_id": position.id,
            "reason": "null_entry_price"
        }
        write_to_action_queue(action)
```

---

## 🔧 **Implementation Plan**

### **Phase 1: Create Standalone Engine (2 hours)**

**File:** `bot/strategy/reconciliation/reconciliation_runner.py`

```python
#!/usr/bin/env python3
"""
Standalone Reconciliation Engine
Runs independently to detect and correct discrepancies
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Any

class ReconciliationEngine:
    """Standalone reconciliation engine"""
    
    def __init__(self, config):
        self.config = config
        self.api_client = None
        self.state_file = Path("data/reconciliation/state.json")
        self.action_queue_file = Path("data/reconciliation/action_queue.json")
        
    async def run(self):
        """Main reconciliation loop"""
        while True:
            try:
                # Load bot state
                bot_state = self.load_bot_state()
                
                # Query exchange for truth
                exchange_state = await self.query_exchange_state()
                
                # Detect discrepancies
                discrepancies = self.detect_discrepancies(bot_state, exchange_state)
                
                # Generate correction actions
                actions = self.generate_correction_actions(discrepancies)
                
                # Write to action queue
                self.write_action_queue(actions)
                
                # Update state
                self.update_state(discrepancies, actions)
                
                # Wait for next check
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                log.error(f"Reconciliation error: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute
    
    def detect_discrepancies(self, bot_state, exchange_state):
        """Detect all types of discrepancies"""
        discrepancies = []
        
        # 1. Missed fills
        discrepancies.extend(self.detect_missed_fills(bot_state, exchange_state))
        
        # 2. Unprotected positions
        discrepancies.extend(self.detect_unprotected_positions(bot_state, exchange_state))
        
        # 3. Orphaned orders
        discrepancies.extend(self.detect_orphaned_orders(bot_state, exchange_state))
        
        # 4. State corruption
        discrepancies.extend(self.detect_state_corruption(bot_state))
        
        return discrepancies
```

---

### **Phase 2: Update Bot to Read Action Queue (1 hour)**

**File:** `bot/strategy/async_gridbot.py`

```python
class AsyncGridBot:
    
    async def _reconciliation_action_processor(self):
        """Process actions from reconciliation engine"""
        while self._running:
            try:
                actions = self.read_action_queue()
                
                for action in actions:
                    await self.execute_reconciliation_action(action)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                log.error(f"Action processor error: {e}")
                await asyncio.sleep(30)
    
    async def execute_reconciliation_action(self, action):
        """Execute a reconciliation action"""
        action_type = action.get("type")
        
        if action_type == "process_missed_fill":
            await self._process_missed_fill(
                action["order_id"],
                action["side"],
                action["fill_price"],
                action["fill_size"]
            )
        
        elif action_type == "place_emergency_tp":
            await self._place_emergency_tp(
                action["position_id"],
                action["tp_price"]
            )
        
        elif action_type == "cancel_orphaned_order":
            await self.order_actor.ask("CANCEL_ORDER", {
                "order_id": action["order_id"]
            })
        
        # Mark action as completed
        self.mark_action_completed(action["id"])
```

---

### **Phase 3: Remove Old Reconciliation Code (30 minutes)**

Remove from `async_gridbot.py`:
- ❌ `_reconciliation_loop()` (100 lines)
- ❌ `_verify_tp_protection()` (80 lines)
- ❌ `_emergency_tp_placement()` (60 lines)
- ❌ `_investigate_missing_order()` (40 lines)
- ❌ `_process_missed_fill()` (30 lines)

**Total removal:** ~310 lines

---

### **Phase 4: Create WebUI Integration (30 minutes)**

**File:** `webui/backend/routes/reconciliation.py`

```python
@bp.route('/status', methods=['GET'])
def get_reconciliation_status():
    """Get reconciliation engine status"""
    state = load_reconciliation_state()
    
    return jsonify({
        'success': True,
        'last_check': state.get('last_check_time'),
        'discrepancies_found': state.get('discrepancies_found', 0),
        'corrections_applied': state.get('corrections_applied', 0),
        'pending_actions': len(state.get('pending_actions', []))
    })
```

---

## 📊 **Expected Results**

### **File Size Reduction:**
```
async_gridbot.py
├── Before: 3,725 lines
├── After: 3,400 lines
└── Reduction: 325 lines (8.7% smaller)

reconciliation_runner.py (NEW)
└── 400 lines (standalone)
```

### **Benefits:**
- ✅ 8.7% smaller bot file
- ✅ Cleaner separation
- ✅ Independent testing
- ✅ Better reliability
- ✅ Easier maintenance

---

## 🔄 **How It Works**

### **Reconciliation Engine (Standalone):**
```bash
# Run reconciliation engine
python3 -m bot.strategy.reconciliation.reconciliation_runner

# Output:
# 🔍 RECONCILIATION ENGINE - STANDALONE MODE
# 📊 Checking bot state vs exchange state...
# ✅ No discrepancies found
# ⏰ Next check in 5 minutes
```

### **Bot (Reads Action Queue):**
```bash
# Bot runs normally
python3 -m bot.strategy.async_gridbot

# Bot logs:
# 📋 Reconciliation action received: process_missed_fill
# ✅ Processed missed fill for order 123456
# 📋 Reconciliation action received: place_emergency_tp
# ✅ Placed emergency TP for position 789012
```

### **WebUI (Shows Status):**
```
Reconciliation Engine Status:
- Last Check: 2 minutes ago
- Discrepancies Found: 2
- Corrections Applied: 2
- Pending Actions: 0
```

---

## 🎯 **Comparison**

### **Current (Embedded):**
| Aspect | Status |
|--------|--------|
| Separation | ❌ Mixed with bot |
| Testing | ❌ Hard to test |
| Reliability | ⚠️ Bot crash = no reconciliation |
| Maintenance | ❌ Tightly coupled |
| Scalability | ❌ Limited |
| Code Size | ❌ 3,725 lines |

### **Proposed (Standalone):**
| Aspect | Status |
|--------|--------|
| Separation | ✅ Completely separate |
| Testing | ✅ Easy to test |
| Reliability | ✅ Independent processes |
| Maintenance | ✅ Loosely coupled |
| Scalability | ✅ Highly scalable |
| Code Size | ✅ 3,400 lines (bot) + 400 lines (engine) |

---

## 🚀 **Implementation Timeline**

### **Total Time: 4 hours**

1. **Phase 1:** Create standalone engine (2 hours)
2. **Phase 2:** Update bot to read actions (1 hour)
3. **Phase 3:** Remove old code (30 minutes)
4. **Phase 4:** WebUI integration (30 minutes)

---

## ✅ **Recommendation**

**YES, create a standalone reconciliation engine!**

**Reasons:**
1. ✅ Cleaner architecture
2. ✅ Better separation of concerns
3. ✅ Easier to test and maintain
4. ✅ More reliable (independent processes)
5. ✅ Follows same pattern as recovery system
6. ✅ Reduces bot complexity by 8.7%

**This would solve many issues once and for all!**

---

## 📋 **Next Steps**

If you approve, I will:
1. Create `bot/strategy/reconciliation/reconciliation_runner.py`
2. Implement all reconciliation logic
3. Update `async_gridbot.py` to read action queue
4. Remove old reconciliation code
5. Create WebUI integration
6. Test the complete system
7. Document usage

**Should I proceed with implementation?**

---

**Created:** November 20, 2025, 2:04 AM  
**Status:** 💡 **AWAITING APPROVAL**  
**Estimated Time:** 4 hours
