# GridBot System Synchronization Plan
**Date**: November 20, 2025  
**Status**: Planning Phase

---

## Executive Summary

Synchronization strategy for three systems coordinated through Guardian signals:
1. **Recovery System** - Handles missed grids on startup/halt recovery
2. **Async Grid Bot** - Main trading logic
3. **Reconciliation System** - Monitors discrepancies every 5 minutes

---

## System Flow

```
USER STARTS BOT (PM2)
    ↓
RECOVERY SYSTEM STARTS (always first)
    ↓
Check Guardian → RED? Wait & poll every 5s until GREEN
                → GREEN? Continue
    ↓
Check Missed Grids → None? Signal Async to start
                   → Found? Place Market+TP orders, then signal Async
    ↓
Set State: recovery_active=False, async_active=True
    ↓
ASYNC GRID BOT STARTS
    ↓
Verify State: async_active=True?
    ↓
Check Guardian → RED? Wait & poll every 5s until GREEN
                → GREEN? Continue
    ↓
Read Reconciliation Report (if exists)
    ↓
Start Normal Grid Trading
    ↓
Monitor Guardian Every Tick → Still GREEN? Continue
                             → RED? Shutdown gracefully
    ↓
On Guardian RED: Set async_active=False, recovery_active=True, Exit
    ↓
PM2 Restarts → RECOVERY LOOP

PARALLEL PROCESS:
Reconciliation runs every 5 minutes
    → Check recovery_in_progress flag
    → If True: Skip cycle
    → If False: Run checks, write report
```

---

## Core Components

### 1. System Coordinator (NEW)

**File**: `bot/state/system_coordinator.py`

**State Schema** (`data/system_state.json`):
```json
{
  "active_system": "recovery" | "async",
  "recovery_active": true | false,
  "async_active": true | false,
  "recovery_in_progress": true | false,
  "guardian_status": "GO" | "HALT",
  "guardian_last_check": "2025-11-20T14:30:00Z",
  "last_transition": "2025-11-20T14:30:00Z",
  "last_transition_reason": "recovery_complete" | "guardian_halt" | "startup",
  "mode": "LONG" | "SHORT"
}
```

**Key Methods**:
```python
class SystemCoordinator:
    def get_active_system() -> str
    def is_recovery_active() -> bool
    def is_async_active() -> bool
    def is_recovery_in_progress() -> bool
    
    def transition_to_async(reason: str)
    def transition_to_recovery(reason: str)
    def set_recovery_in_progress(value: bool)
    
    def get_guardian_status(use_cache: bool = True) -> str
    def wait_for_guardian_green(poll_interval: int = 5)
```

**Features**:
- Atomic file operations with locking
- Guardian status caching (2s TTL)
- State validation on load
- Backup on every transition

---

### 2. Recovery System Enhancement

**File**: `bot/recovery/startup_recovery_engine.py`

**Recovery State** (`data/recovery/recovery_state.json`):
```json
{
  "phase": "idle" | "checking_guardian" | "checking_grids" | "placing_orders" | "complete",
  "missed_grids_found": [92000, 91000, 90000],
  "missed_grids_recovered": [92000, 91000],
  "orders_placed": [
    {"grid": 92000, "order_id": "123", "status": "filled"}
  ],
  "started_at": "2025-11-20T14:30:00Z",
  "last_update": "2025-11-20T14:30:15Z"
}
```

**Flow**:
```python
async def run_recovery():
    coordinator = SystemCoordinator()
    
    # Set flag to prevent reconciliation conflicts
    coordinator.set_recovery_in_progress(True)
    
    # Wait for Guardian GREEN (poll every 5s)
    await coordinator.wait_for_guardian_green()
    
    # Check missed grids
    missed_grids = await check_missed_grids()
    
    # Place orders if needed (persist state after each order)
    if missed_grids:
        await place_recovery_orders(missed_grids)
    
    # Transition to async
    coordinator.set_recovery_in_progress(False)
    coordinator.transition_to_async("recovery_complete")
    
    # Exit (PM2 will start async bot)
    sys.exit(0)
```

**Key Features**:
- Guardian polling with 5s interval
- State persistence after each order (crash recovery)
- Max 3 missed grids (configurable)
- Atomic transition to async

---

### 3. Async Grid Bot Integration

**File**: `bot/strategy/async_gridbot.py`

**Startup Flow**:
```python
async def start():
    coordinator = SystemCoordinator()
    
    # Verify state
    if not coordinator.is_async_active():
        logger.error("State mismatch - recovery should be active")
        sys.exit(1)
    
    # Wait for Guardian GREEN
    await coordinator.wait_for_guardian_green()
    
    # Read reconciliation report
    recon_report = read_reconciliation_report()
    if recon_report and recon_report.get("critical_issues"):
        logger.warning(f"Reconciliation issues: {recon_report}")
    
    # Start Guardian monitoring task
    asyncio.create_task(monitor_guardian())
    
    # Start normal operations
    await run_grid_bot()
```

**Guardian Monitoring**:
```python
async def monitor_guardian():
    coordinator = SystemCoordinator()
    while True:
        status = coordinator.get_guardian_status(use_cache=False)
        if status == "HALT":
            logger.warning("Guardian HALT - transitioning to recovery")
            await shutdown_gracefully()
            coordinator.transition_to_recovery("guardian_halt")
            sys.exit(0)
        await asyncio.sleep(1)  # Check every second
```

**Graceful Shutdown**:
```python
async def shutdown_gracefully():
    # Cancel pending tasks
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()
    
    # Drain actor mailboxes
    await position_manager.drain_mailbox()
    await order_manager.drain_mailbox()
    
    # Close connections
    await ws_manager.disconnect()
    await api_client.close()
```

---

### 4. Reconciliation Coordination

**File**: `bot/reconciliation/reconciliation_engine.py`

**Flow**:
```python
async def run_reconciliation():
    coordinator = SystemCoordinator()
    
    # Skip if recovery in progress
    if coordinator.is_recovery_in_progress():
        logger.info("Recovery active - skipping cycle")
        return
    
    # Run checks
    discrepancies = await check_discrepancies()
    
    # Write report for async bot
    write_report(discrepancies)
    
    # Auto-fix minor issues only
    if discrepancies.get("minor_issues"):
        await fix_minor_issues(discrepancies["minor_issues"])
```

**Report Format** (`data/reconciliation/recon_report.json`):
```json
{
  "timestamp": "2025-11-20T14:30:00Z",
  "status": "ok" | "minor_issues" | "critical_issues",
  "discrepancies": {
    "missing_tp_orders": [
      {"position_id": "pos_123", "expected_tp": 93000}
    ],
    "orphan_orders": [
      {"order_id": "ord_456", "reason": "no_matching_position"}
    ]
  },
  "actions_taken": [
    {"action": "placed_tp", "position_id": "pos_123"}
  ],
  "next_check": "2025-11-20T14:35:00Z"
}
```

**Auto-Fix Rules**:
- **Minor (auto-fix)**: Missing TP orders, orphan orders
- **Critical (report only)**: Position mismatches, price discrepancies

---

## Implementation Phases

### Phase 1: System Coordinator (2-3 hours)
**Files**: 
- `bot/state/__init__.py`
- `bot/state/system_coordinator.py`

**Tasks**:
- Implement state management
- Add file locking
- Add Guardian status caching
- Add state validation
- Unit tests

### Phase 2: Recovery Enhancement (3-4 hours)
**Files**:
- `bot/recovery/startup_recovery_engine.py`
- `data/recovery/recovery_state.json`

**Tasks**:
- Add Guardian polling loop
- Add state persistence
- Add recovery_in_progress flag
- Add crash recovery
- Unit tests

### Phase 3: Async Bot Integration (2-3 hours)
**Files**:
- `bot/strategy/async_gridbot.py`

**Tasks**:
- Add startup state verification
- Add Guardian monitoring task
- Add graceful shutdown
- Add reconciliation report reading
- Unit tests

### Phase 4: Reconciliation Coordination (1-2 hours)
**Files**:
- `bot/reconciliation/reconciliation_engine.py`

**Tasks**:
- Add recovery_in_progress check
- Add report writing
- Add minor issue auto-fix
- Unit tests

### Phase 5: PM2 Integration (2-3 hours)
**Files**:
- `start_bot_with_recovery.py`
- `webui/backend/bot/bot_manager.py`

**Tasks**:
- Update startup script
- Update WebUI bot manager
- Configure PM2
- Integration tests

### Phase 6: Testing & Validation (4-6 hours)
**Tests**:
- End-to-end startup flow
- Guardian HALT during trading
- Recovery with missed grids
- Crash recovery
- Reconciliation skip during recovery

**Total Estimated Time**: 14-21 hours

---

## Configuration

### config.yaml Additions

```yaml
system_coordination:
  state_file: "data/system_state.json"
  
  guardian:
    poll_interval_waiting: 5  # seconds
    poll_interval_trading: 1  # seconds
    cache_ttl: 2  # seconds
  
  recovery:
    state_file: "data/recovery/recovery_state.json"
    max_missed_grids: 3
    order_placement_delay: 2  # seconds
    persist_state: true
  
  reconciliation:
    interval: 300  # 5 minutes
    report_file: "data/reconciliation/recon_report.json"
    skip_during_recovery: true
    auto_fix_minor: true
    auto_fix_critical: false
```

---

## Critical Design Decisions

### 1. State Management
**Decision**: JSON file with file locking  
**Reason**: Simple, atomic, easy to debug

### 2. Guardian Polling
**Decision**: 5s when waiting, 1s during trading  
**Reason**: Balance between responsiveness and API load

### 3. Recovery Limits
**Decision**: Max 3 missed grids  
**Reason**: Prevent over-trading, alert user if exceeded

### 4. Reconciliation Auto-Fix
**Decision**: Auto-fix minor only  
**Reason**: Safe operations only, report critical issues

### 5. Crash Recovery
**Decision**: Persist recovery state, resume on restart  
**Reason**: Prevent duplicate orders, maintain integrity

---

## Error Handling

### Guardian API Failure
- Retry 3 times with exponential backoff
- Default to HALT (safe)
- Log error, notify user

### State File Corruption
- Load backup state
- If no backup, initialize to recovery mode (safe)
- Log critical error

### Recovery Crash Mid-Operation
- Read recovery_state.json on restart
- Resume from last successful order
- Don't duplicate orders

### Both Systems Active (State Corruption)
- Force to recovery mode (safe)
- Log critical error
- Notify user

---

## State Transition Matrix

| Current | Event | Next | Action |
|---------|-------|------|--------|
| Recovery | Guardian GREEN + No Missed | Async | Signal async, exit |
| Recovery | Guardian GREEN + Missed | Async | Place orders, signal async, exit |
| Recovery | Guardian RED | Recovery | Wait, poll every 5s |
| Async | Guardian GREEN | Async | Continue trading |
| Async | Guardian RED | Recovery | Shutdown, exit |
| Async | Crash | Recovery | PM2 restarts recovery |
| Recovery | Crash | Recovery | Resume from state file |

---

## Success Criteria

### Must Have
- [ ] No race conditions
- [ ] Clean state transitions
- [ ] Guardian HALT respected immediately (<5s)
- [ ] Recovery completes successfully
- [ ] Reconciliation skips during recovery
- [ ] Crash recovery works

### Should Have
- [ ] Zero duplicate orders
- [ ] Zero orphan orders
- [ ] <10s recovery (no missed grids)
- [ ] <30s recovery (with missed grids)

---

## Open Questions

### 1. Guardian HALT Duration
**Question**: What if Guardian stays RED for hours?  
**Recommendation**: Timeout after 2 hours, send critical alert

### 2. Recovery Order Fills
**Question**: What if recovery orders don't fill immediately?  
**Recommendation**: Transition to async immediately, async handles pending orders

### 3. Multiple Bot Instances
**Question**: What if user starts multiple instances?  
**Recommendation**: Use state file lock to prevent

### 4. State File Backup Frequency
**Question**: How often to backup?  
**Recommendation**: On every state transition

---

## Next Steps

1. **Review this document** - Confirm approach
2. **Answer open questions** - Make final decisions
3. **Start Phase 1** - Implement SystemCoordinator
4. **Iterate through phases** - Build, test, deploy

---

## File Structure

```
bot/
├── state/
│   ├── __init__.py
│   └── system_coordinator.py          # NEW
├── recovery/
│   └── startup_recovery_engine.py     # MODIFIED
├── strategy/
│   └── async_gridbot.py               # MODIFIED
└── reconciliation/
    └── reconciliation_engine.py       # MODIFIED

data/
├── system_state.json                  # NEW
├── system_state.json.backup           # NEW
├── recovery/
│   └── recovery_state.json            # NEW
└── reconciliation/
    └── recon_report.json              # NEW

start_bot_with_recovery.py             # MODIFIED
webui/backend/bot/bot_manager.py       # MODIFIED
```

---

## Monitoring

### Key Metrics
- State transitions per day
- Guardian HALT/GO transitions
- Missed grids detected
- Recovery success rate
- Reconciliation discrepancies

### Log Levels
- **ERROR**: System failures, state corruption
- **WARNING**: Guardian HALT, reconciliation issues
- **INFO**: State transitions, recovery actions
- **DEBUG**: Guardian polls (disable in production)

### Alerts
- **Critical**: State corruption, Guardian unreachable >5min
- **Warning**: >3 missed grids, Guardian HALT >1hr
- **Info**: State transitions, recovery complete

---

## Testing Strategy

### Unit Tests
- SystemCoordinator state transitions
- Recovery Guardian polling
- Async Guardian monitoring
- Reconciliation recovery check

### Integration Tests
- Full startup flow (no missed grids)
- Full startup flow (with missed grids)
- Guardian HALT during trading
- Crash during recovery
- Crash during async trading

### Chaos Tests
- Rapid Guardian GO/HALT cycles
- Concurrent state access
- Network failures
- Multiple restart attempts

---

## Rollout Plan

1. **Development** (2-3 days) - Implement all phases
2. **Testing** (1-2 days) - Demo mode, simulate scenarios
3. **Shadow Mode** (2-3 days) - Run alongside existing bot
4. **Production** (Gradual) - Deploy, monitor 24hrs, full rollout
