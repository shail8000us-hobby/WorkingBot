# Correct Recovery Engine Architecture

**Date:** November 20, 2025, 1:37 AM  
**Status:** 🔄 **ARCHITECTURAL FIX REQUIRED**

---

## ❌ **What I Did Wrong**

I integrated recovery engine **directly into async_gridbot.py**:

```python
# WRONG: Inside async_gridbot.py
from bot.strategy.recovery import StartupRecoveryEngine, GuardianRecoveryEngine

def __init__(self):
    # ❌ Recovery engines initialized here
    self.startup_recovery = StartupRecoveryEngine(...)
    self.guardian_recovery = GuardianRecoveryEngine(...)

async def start(self):
    # ❌ Recovery executed here
    result = await self.startup_recovery.execute_recovery()
    
async def place_recovery_order(self):
    # ❌ Recovery methods here
    pass
```

**Problems:**
1. Recovery code mixed with normal trading
2. No separation of concerns
3. Can't disable recovery without modifying bot
4. Recovery and normal grid can conflict
5. Violates single responsibility principle

---

## ✅ **Correct Architecture**

### **Principle: Separation of Concerns**

```
Recovery Engine (Standalone)
    ↓ (writes state)
Shared State File (recovery_active.json)
    ↓ (reads state)
Normal Grid Bot (async_gridbot.py)
```

### **How It Should Work:**

#### **1. Recovery Engine (Separate Script)**

**File:** `bot/strategy/recovery/recovery_runner.py` (NEW)

```python
"""
Standalone recovery engine runner.
Runs independently of main bot.
"""

import asyncio
from bot.strategy.recovery import StartupRecoveryEngine, GuardianRecoveryEngine

class RecoveryRunner:
    """
    Standalone recovery engine runner.
    Does NOT integrate with async_gridbot.py
    """
    
    def __init__(self):
        self.state_file = Path("data/recovery/recovery_state.json")
        self.startup_engine = StartupRecoveryEngine(...)
        self.guardian_engine = GuardianRecoveryEngine(...)
    
    async def run_startup_recovery(self):
        """Run startup recovery independently"""
        # Set flag: recovery active
        self._set_recovery_active(True)
        
        try:
            # Execute recovery
            result = await self.startup_engine.execute_recovery()
            
            # Save recovered grids to state file
            self._save_recovered_grids(result['recovered_grids'])
            
        finally:
            # Clear flag: recovery done
            self._set_recovery_active(False)
    
    def _set_recovery_active(self, active: bool):
        """Write recovery state to shared file"""
        state = {
            'recovery_active': active,
            'timestamp': time.time()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)
    
    def _save_recovered_grids(self, grids: List[float]):
        """Save recovered grids so bot knows to skip them"""
        state = self._load_state()
        state['recovered_grids'] = grids
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

# Run as standalone script
if __name__ == "__main__":
    runner = RecoveryRunner()
    asyncio.run(runner.run_startup_recovery())
```

#### **2. Normal Grid Bot (Minimal Changes)**

**File:** `bot/strategy/async_gridbot.py`

```python
"""
Normal grid bot - NO recovery code inside.
Only reads recovery state from file.
"""

class AsyncGridBot:
    
    def __init__(self):
        # ✅ NO recovery engine initialization
        # ✅ NO recovery imports
        self.recovery_state_file = Path("data/recovery/recovery_state.json")
    
    async def _check_and_place_entry_order(self):
        """Place entry order - checks recovery state"""
        
        # Check if recovery is active
        if self._is_recovery_active():
            self.logger.info("⏸️  Recovery active - skipping normal grid order")
            return
        
        # Check if grid already recovered
        if self._is_grid_recovered(target_price):
            self.logger.info(f"✅ Grid {target_price} already recovered - skipping")
            return
        
        # Normal grid logic continues...
        await self._place_order(...)
    
    def _is_recovery_active(self) -> bool:
        """Check if recovery is currently running"""
        try:
            if not self.recovery_state_file.exists():
                return False
            
            with open(self.recovery_state_file) as f:
                state = json.load(f)
            
            return state.get('recovery_active', False)
        except:
            return False  # Assume not active on error
    
    def _is_grid_recovered(self, grid_price: float) -> bool:
        """Check if grid was already recovered"""
        try:
            if not self.recovery_state_file.exists():
                return False
            
            with open(self.recovery_state_file) as f:
                state = json.load(f)
            
            recovered = state.get('recovered_grids', [])
            tolerance = 1.0
            
            return any(abs(g - grid_price) < tolerance for g in recovered)
        except:
            return False
```

#### **3. Shared State File**

**File:** `data/recovery/recovery_state.json`

```json
{
  "recovery_active": false,
  "recovered_grids": [89000, 88500, 88000],
  "timestamp": 1700456789.123,
  "last_session": "startup_20251120_013000"
}
```

---

## 🔄 **Execution Flow**

### **Scenario 1: Bot Startup with Missed Grids**

```bash
# Step 1: Run recovery BEFORE starting bot
python3 -m bot.strategy.recovery.recovery_runner

# Output:
# 🔄 Recovery active - normal grid paused
# 📍 Placing recovery order: $89,000
# 📍 Placing recovery order: $88,500
# 📍 Placing recovery order: $88,000
# ✅ Recovery complete - 3 grids recovered
# ✅ Recovery inactive - normal grid can resume

# Step 2: Start normal bot
python3 -m bot.strategy.async_gridbot

# Bot checks recovery_state.json:
# - recovery_active: False ✅
# - recovered_grids: [89000, 88500, 88000] ✅
# - Skips these grids in normal trading ✅
```

### **Scenario 2: Guardian Recovery**

```bash
# Guardian detects STOP → GO transition
# Guardian calls recovery runner:
python3 -m bot.strategy.recovery.recovery_runner --mode guardian

# Recovery runs independently
# Sets recovery_active = True
# Bot pauses normal grid logic
# Recovery completes
# Sets recovery_active = False
# Bot resumes normal grid logic
```

---

## 🎯 **Benefits of Correct Architecture**

### **1. Separation of Concerns**
- ✅ Recovery = Separate module
- ✅ Normal grid = Unchanged
- ✅ No mixing of logic
- ✅ Easy to disable/enable

### **2. No Conflicts**
- ✅ Recovery runs, normal grid pauses
- ✅ No duplicate orders
- ✅ No race conditions
- ✅ Clear state management

### **3. Maintainability**
- ✅ Easy to debug (separate logs)
- ✅ Easy to test (independent)
- ✅ Easy to modify (no side effects)
- ✅ Easy to disable (just don't run)

### **4. Flexibility**
- ✅ Can run recovery manually
- ✅ Can run recovery on schedule
- ✅ Can run recovery from Guardian
- ✅ Can run recovery from WebUI

---

## 🔧 **Implementation Plan**

### **Step 1: Remove Recovery from async_gridbot.py**

```python
# Remove these lines:
from bot.strategy.recovery import ...  # DELETE
self.startup_recovery = ...  # DELETE
self.guardian_recovery = ...  # DELETE
await self.startup_recovery.execute_recovery()  # DELETE
async def place_recovery_order(self):  # DELETE
async def _guardian_recovery_monitor(self):  # DELETE
```

### **Step 2: Add State Checks to async_gridbot.py**

```python
# Add these methods:
def _is_recovery_active(self) -> bool:
    """Check recovery state file"""
    
def _is_grid_recovered(self, grid_price: float) -> bool:
    """Check if grid already recovered"""

# Modify order placement:
async def _check_and_place_entry_order(self):
    if self._is_recovery_active():
        return  # Skip during recovery
    
    if self._is_grid_recovered(target_price):
        return  # Skip recovered grids
    
    # Normal logic...
```

### **Step 3: Create Standalone Recovery Runner**

```python
# New file: bot/strategy/recovery/recovery_runner.py
class RecoveryRunner:
    """Standalone recovery engine"""
    
    async def run_startup_recovery(self):
        """Run startup recovery independently"""
        
    async def run_guardian_recovery(self):
        """Run guardian recovery independently"""
```

### **Step 4: Update Startup Script**

```bash
# Old way (WRONG):
python3 -m bot.strategy.async_gridbot
# Recovery runs inside bot ❌

# New way (CORRECT):
# 1. Run recovery first (if needed)
python3 -m bot.strategy.recovery.recovery_runner --startup

# 2. Start normal bot
python3 -m bot.strategy.async_gridbot
# Bot checks state file, skips recovered grids ✅
```

---

## 📊 **Comparison**

### **Old Architecture (Wrong):**

```
async_gridbot.py (4,800 lines)
├── Normal grid logic
├── Recovery engine code ❌
├── Recovery helper methods ❌
├── Recovery monitor task ❌
└── Mixed concerns ❌
```

**Problems:**
- Mixed concerns
- Hard to disable
- Conflicts possible
- Complex debugging

### **New Architecture (Correct):**

```
recovery_runner.py (300 lines)
├── Standalone recovery
├── State file management
└── Independent execution ✅

recovery_state.json
├── recovery_active flag
└── recovered_grids list ✅

async_gridbot.py (4,500 lines)
├── Normal grid logic
├── State file checks ✅
└── Skip recovered grids ✅
```

**Benefits:**
- Clear separation
- Easy to disable
- No conflicts
- Simple debugging

---

## 🚀 **Migration Steps**

### **1. Create Recovery Runner (30 min)**
- Create `recovery_runner.py`
- Implement state file management
- Add startup/guardian modes

### **2. Modify async_gridbot.py (15 min)**
- Remove recovery imports
- Remove recovery initialization
- Remove recovery methods
- Add state file checks

### **3. Test Separately (30 min)**
- Test recovery runner standalone
- Test bot with recovery state
- Test coordination

### **4. Fix Critical Bugs (30 min)**
- Add max grids enforcement
- Add position checks
- Add pending order checks
- Add fail-safe error handling

**Total Time:** 2 hours

---

## ✅ **Summary**

**You were 100% correct!**

The recovery engine should be:
- ✅ **Separate** from async_gridbot.py
- ✅ **Standalone** script/module
- ✅ **Coordinated** via state file
- ✅ **Mutually exclusive** with normal grid

**I will now:**
1. Remove recovery code from async_gridbot.py
2. Create standalone recovery_runner.py
3. Add state file coordination
4. Fix the critical bugs
5. Test separately

**This is the correct architecture!** 🎯

---

**Created:** November 20, 2025, 1:37 AM  
**Status:** 🔄 **ARCHITECTURAL FIX IN PROGRESS**  
**Estimated Time:** 2 hours
