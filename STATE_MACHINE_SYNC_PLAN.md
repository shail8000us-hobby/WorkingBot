# GridBot State Machine Synchronization Plan
**Date**: November 20, 2025  
**Status**: Implementation Ready  
**Approach**: Single Process State Machine

---

## Executive Summary

**Problem**: Recovery, Async Bot, and Reconciliation systems are independent but need coordination.

**Solution**: Single bot process with explicit state machine. No IPC, no coordination files, no race conditions.

---

## Architecture Overview

### Current System (Problematic)
```
Recovery Process (standalone, not integrated)
    ↓ (coordination via files?)
Async Bot Process (bot/strategy/async_gridbot.py)
    ↓ (coordination via files?)
Reconciliation Process (standalone, not integrated)
```

**Issues**:
- Recovery exists but NOT integrated with bot
- Reconciliation exists but integration unclear
- No coordination mechanism
- Potential race conditions

### New System (State Machine)
```
Single Bot Process (bot/strategy/async_gridbot.py)
    ↓
State Machine (5 states)
    ├─→ WAITING_FOR_GUARDIAN
    ├─→ RECOVERY_CHECK
    ├─→ RECOVERY_IN_PROGRESS
    ├─→ ASYNC_TRADING (current bot logic)
    └─→ HALTED
    
Reconciliation (async task in same process)
    └─→ Runs every 5 minutes, skips if RECOVERY_IN_PROGRESS
```

**Benefits**:
- ✅ Single process (no IPC)
- ✅ No race conditions (state machine enforces)
- ✅ Simpler PM2 (one bot process)
- ✅ Easier debugging (single process)
- ✅ Better performance (no process switching)

---

## State Machine Design

### States

```python
class BotState(Enum):
    WAITING_FOR_GUARDIAN = "waiting_for_guardian"
    RECOVERY_CHECK = "recovery_check"
    RECOVERY_IN_PROGRESS = "recovery_in_progress"
    ASYNC_TRADING = "async_trading"
    HALTED = "halted"
```

### State Transitions

```
START
  ↓
WAITING_FOR_GUARDIAN
  ↓ (Guardian GO)
RECOVERY_CHECK
  ↓
  ├─→ No missed grids → ASYNC_TRADING
  └─→ Missed grids → RECOVERY_IN_PROGRESS
                        ↓
                      ASYNC_TRADING
                        ↓ (Guardian HALT)
                      HALTED
                        ↓ (Guardian GO)
                      RECOVERY_CHECK
```

### State Handlers

**WAITING_FOR_GUARDIAN**:
- Poll Guardian status every 5s
- If GO → transition to RECOVERY_CHECK
- If HALT → stay in this state

**RECOVERY_CHECK**:
- Check for missed grids (using existing recovery engines)
- If found → transition to RECOVERY_IN_PROGRESS
- If none → transition to ASYNC_TRADING

**RECOVERY_IN_PROGRESS**:
- Execute recovery (place market + TP orders)
- Use existing `bot/strategy/recovery/` engines
- On complete → transition to ASYNC_TRADING
- On Guardian HALT → transition to HALTED

**ASYNC_TRADING**:
- Run existing async bot logic (current implementation)
- Monitor Guardian every tick
- If HALT → transition to HALTED
- Continue normal grid trading

**HALTED**:
- Stop all trading
- Poll Guardian every 5s
- If GO → transition to RECOVERY_CHECK

---

## Implementation Plan

### Phase 1: State Machine Core (2-3 hours)

**File**: `bot/state/state_machine.py` (NEW)

**Components**:
```python
class BotStateMachine:
    def __init__(self, bot_instance)
    async def run()
    async def _transition(next_state)
    
    # State handlers
    async def _handle_waiting()
    async def _handle_recovery_check()
    async def _handle_recovery()
    async def _handle_trading()
    async def _handle_halted()
```

**State Persistence**: `data/bot_state.json`
```json
{
  "current_state": "async_trading",
  "last_transition": "2025-11-20T14:30:00Z",
  "transition_reason": "recovery_complete",
  "guardian_status": "GO",
  "mode": "LONG"
}
```

### Phase 2: Integrate Recovery Engines (2-3 hours)

**Existing Files** (already implemented):
- `bot/strategy/recovery/base_recovery_engine.py` (729 lines)
- `bot/strategy/recovery/startup_recovery.py` (165 lines)
- `bot/strategy/recovery/guardian_recovery.py` (174 lines)

**Integration**:
- State machine calls recovery engines in RECOVERY_CHECK state
- Use existing recovery logic (no rewrite needed)
- Recovery engines already have safety mechanisms

**Changes to async_gridbot.py**:
- Add state machine initialization
- Wrap main loop in state machine
- Keep existing trading logic intact

### Phase 3: Guardian Integration (1-2 hours)

**Guardian Check**:
- Use existing Guardian SQL signal (`guardian_signal` table)
- State machine reads signal in WAITING and HALTED states
- Existing bot already has Guardian integration

**No Changes to Guardian**:
- Guardian bot stays unchanged
- Continues writing GO/STOP to SQL
- State machine reads from same table

### Phase 4: Reconciliation Integration (1-2 hours)

**Existing File**: `bot/strategy/reconciliation/reconciliation_runner.py`

**Integration**:
- Run as async task in same process
- Check state machine current state
- Skip if state == RECOVERY_IN_PROGRESS
- Use existing reconciliation logic

### Phase 5: Testing (2-3 hours)

**Test Scenarios**:
1. Startup with Guardian RED → wait → GO → no missed grids → trading
2. Startup with Guardian GO → missed grids → recovery → trading
3. Trading → Guardian HALT → halted → GO → recovery check → trading
4. Reconciliation skips during recovery
5. Crash recovery (state persistence)

---

## File Structure

```
bot/
├── state/
│   ├── __init__.py                    # NEW
│   └── state_machine.py               # NEW (300-400 lines)
│
├── strategy/
│   ├── async_gridbot.py               # MODIFIED (add state machine)
│   │
│   ├── recovery/                      # EXISTING (use as-is)
│   │   ├── base_recovery_engine.py
│   │   ├── startup_recovery.py
│   │   ├── guardian_recovery.py
│   │   └── recovery_monitor.py
│   │
│   └── reconciliation/                # EXISTING (integrate)
│       └── reconciliation_runner.py
│
└── guardian/
    └── guardian_bot.py                # UNCHANGED

data/
├── bot_state.json                     # NEW (state persistence)
├── recovery/                          # EXISTING
│   └── startup_recovery_state.json
└── reconciliation/                    # EXISTING
    └── recon_report.json
```

---

## Code Changes

### 1. New State Machine (bot/state/state_machine.py)

```python
import asyncio
from enum import Enum
from typing import Optional
import json
from pathlib import Path
from datetime import datetime

class BotState(Enum):
    WAITING_FOR_GUARDIAN = "waiting_for_guardian"
    RECOVERY_CHECK = "recovery_check"
    RECOVERY_IN_PROGRESS = "recovery_in_progress"
    ASYNC_TRADING = "async_trading"
    HALTED = "halted"

class BotStateMachine:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.current_state = BotState.WAITING_FOR_GUARDIAN
        self.state_file = Path("data/bot_state.json")
        self._load_state()
    
    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                self.current_state = BotState(data.get("current_state", "waiting_for_guardian"))
    
    def _save_state(self, reason: str):
        data = {
            "current_state": self.current_state.value,
            "last_transition": datetime.utcnow().isoformat(),
            "transition_reason": reason,
            "guardian_status": self.bot._get_guardian_status(),
            "mode": self.bot.mode
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def run(self):
        while True:
            if self.current_state == BotState.WAITING_FOR_GUARDIAN:
                next_state = await self._handle_waiting()
            elif self.current_state == BotState.RECOVERY_CHECK:
                next_state = await self._handle_recovery_check()
            elif self.current_state == BotState.RECOVERY_IN_PROGRESS:
                next_state = await self._handle_recovery()
            elif self.current_state == BotState.ASYNC_TRADING:
                next_state = await self._handle_trading()
            elif self.current_state == BotState.HALTED:
                next_state = await self._handle_halted()
            
            if next_state and next_state != self.current_state:
                await self._transition(next_state)
    
    async def _transition(self, next_state: BotState, reason: str = ""):
        self.bot.logger.info(f"State transition: {self.current_state.value} → {next_state.value}")
        self.current_state = next_state
        self._save_state(reason)
    
    async def _handle_waiting(self) -> Optional[BotState]:
        guardian_status = self.bot._get_guardian_status()
        if guardian_status == "GO":
            return BotState.RECOVERY_CHECK
        await asyncio.sleep(5)
        return None
    
    async def _handle_recovery_check(self) -> BotState:
        # Use existing recovery engines
        missed_grids = await self.bot._check_missed_grids()
        if missed_grids:
            return BotState.RECOVERY_IN_PROGRESS
        return BotState.ASYNC_TRADING
    
    async def _handle_recovery(self) -> BotState:
        # Execute recovery using existing engines
        await self.bot._execute_recovery()
        return BotState.ASYNC_TRADING
    
    async def _handle_trading(self) -> Optional[BotState]:
        # Run one iteration of existing bot logic
        await self.bot._run_trading_iteration()
        
        # Check Guardian
        guardian_status = self.bot._get_guardian_status()
        if guardian_status == "HALT":
            return BotState.HALTED
        
        return None  # Stay in trading
    
    async def _handle_halted(self) -> Optional[BotState]:
        guardian_status = self.bot._get_guardian_status()
        if guardian_status == "GO":
            return BotState.RECOVERY_CHECK
        await asyncio.sleep(5)
        return None
```

### 2. Modify async_gridbot.py

**Add at top**:
```python
from bot.state.state_machine import BotStateMachine, BotState
```

**Modify main() function**:
```python
async def main():
    bot = AsyncGridBot(mode=mode, config=config)
    
    # Initialize state machine
    state_machine = BotStateMachine(bot)
    
    # Start reconciliation in background
    asyncio.create_task(bot._run_reconciliation_loop(state_machine))
    
    # Run state machine (replaces old main loop)
    await state_machine.run()
```

**Add helper methods to AsyncGridBot**:
```python
async def _run_trading_iteration(self):
    # Extract one iteration of current main loop
    # This is the existing bot logic
    pass

async def _check_missed_grids(self):
    # Use existing recovery engines
    from bot.strategy.recovery.startup_recovery import StartupRecoveryEngine
    engine = StartupRecoveryEngine(self.api_client, self.config, self.mode)
    return await engine.check_missed_grids()

async def _execute_recovery(self):
    # Use existing recovery engines
    from bot.strategy.recovery.startup_recovery import StartupRecoveryEngine
    engine = StartupRecoveryEngine(self.api_client, self.config, self.mode)
    await engine.execute_recovery()

async def _run_reconciliation_loop(self, state_machine):
    while True:
        await asyncio.sleep(300)  # 5 minutes
        
        # Skip if in recovery
        if state_machine.current_state == BotState.RECOVERY_IN_PROGRESS:
            self.logger.info("Skipping reconciliation - recovery in progress")
            continue
        
        # Run reconciliation
        await self._run_reconciliation()
```

---

## Configuration

### config.yaml additions

```yaml
state_machine:
  enabled: true
  state_file: "data/bot_state.json"
  guardian_poll_interval: 5  # seconds
  
recovery:
  enabled: true
  max_missed_grids: 3
  
reconciliation:
  enabled: true
  interval: 300  # 5 minutes
  skip_during_recovery: true
```

---

## Migration Strategy

### Step 1: Implement State Machine
- Create `bot/state/state_machine.py`
- Add state persistence
- Test state transitions

### Step 2: Integrate with Bot
- Modify `async_gridbot.py` main loop
- Extract trading iteration logic
- Add recovery engine calls

### Step 3: Test Thoroughly
- Test all state transitions
- Test Guardian HALT/GO
- Test recovery scenarios
- Test reconciliation skip

### Step 4: Deploy
- Update PM2 config (no changes needed)
- Monitor state transitions
- Verify all systems working

---

## Success Criteria

- [ ] Single bot process running
- [ ] State machine handles all transitions
- [ ] Recovery engines integrated
- [ ] Reconciliation skips during recovery
- [ ] Guardian HALT/GO respected
- [ ] No race conditions
- [ ] State persists across restarts
- [ ] All existing bot features working

---

## Estimated Timeline

- **Phase 1**: State Machine Core - 2-3 hours
- **Phase 2**: Recovery Integration - 2-3 hours
- **Phase 3**: Guardian Integration - 1-2 hours
- **Phase 4**: Reconciliation Integration - 1-2 hours
- **Phase 5**: Testing - 2-3 hours

**Total**: 8-13 hours

---

## Key Advantages

1. **Simplicity**: Single process, no IPC
2. **Safety**: State machine prevents invalid states
3. **Performance**: No process switching overhead
4. **Debugging**: Single process to monitor
5. **Reliability**: No coordination files to corrupt
6. **Maintainability**: Clear state transitions
7. **Testability**: Easy to test each state

---

## Next Steps

1. Review this plan
2. Start Phase 1: Implement state machine
3. Test state transitions
4. Integrate with bot
5. Deploy and monitor
