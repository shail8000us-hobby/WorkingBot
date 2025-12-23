# GridBot God Class Refactoring - Master Plan
**Project**: Production GridBot Trading System  
**File**: `bot/strategy/gbot_ws.py` (3,492 lines)  
**Status**: CRITICAL SIZE - 174% over recommended maximum  
**Priority**: Zero downtime tolerance, incremental refactoring required

---

## 📊 CURRENT STATE ANALYSIS

### File Statistics
- **Total Lines**: 3,492 lines (174% over 2,000 line max)
- **Total Methods**: 72 methods in single class
- **Code Smell**: God Class anti-pattern
- **Complexity**: HIGH - manages 12+ responsibilities

### Critical Sections (MUST PRESERVE)
✅ **Lines 2682-2710**: `_sync_on_reconnect()` - FIX #12 (WebSocket reconnect sync)  
✅ **Lines 2740-2785**: `_persist_runtime_state()` - FIX #13 (Runtime state persistence)  
✅ **Lines 1710-1800**: TP collision detection - FIX #8  
✅ **Lines 1935-2000**: Grid realignment - FIX #6  
✅ **Lines 1800-1930**: TP retry queue system  
✅ **Lines 2030-2300**: Volatility recovery system  
✅ **Lines 230-240, 604-615**: Fill deduplication (deque maxlen=5000)  

---

## 🎯 TARGET ARCHITECTURE

### Module Structure
```
bot/strategy/
├─ gridbot.py (200-300 lines)                    # NEW - Main Orchestrator
│  └─ Pure orchestration, no business logic
│
└─ modules/
   ├─ grid_calculator.py (~200 lines)            # PHASE 1 - Pure Logic
   ├─ websocket_handler.py (~300 lines)          # PHASE 2 - Event Routing
   ├─ fill_detector.py (~300 lines)              # PHASE 3 - Fill Processing
   ├─ position_manager.py (~400 lines)           # PHASE 4 - State Management
   ├─ order_manager.py (~400 lines)              # PHASE 5 - Order Operations
   ├─ reconciliation.py (~400 lines)             # PHASE 6 - Exchange Sync
   └─ volatility_handler.py (~500 lines)         # PHASE 7 - Recovery Logic
```

### Dependency Graph
```
┌────────────────────────────────────────────────────────────────┐
│                         GridBot                                 │
│                   (Main Orchestrator)                          │
└────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌──────────────┐      ┌──────────────┐
│GridCalculator │    │PositionMgr   │      │WebSocketHdlr │
│ (Pure Logic)  │←───│(State+Lock)  │──────│(Events)      │
└───────────────┘    └──────────────┘      └──────────────┘
                              ↑                     │
                              │                     ↓
                     ┌────────┴────────┐    ┌──────────────┐
                     ↓                 ↓    │FillDetector  │
            ┌──────────────┐  ┌──────────────┐           │
            │OrderManager  │  │Reconciliation│←──────────┘
            └──────────────┘  └──────────────┘
                     ↑                 ↑
                     └────────┬────────┘
                              ↓
                    ┌──────────────────┐
                    │VolatilityHandler │
                    │  (Most Complex)  │
                    └──────────────────┘

NO CIRCULAR DEPENDENCIES ✅
```

---

## 📋 METHOD CATEGORIZATION (72 Total Methods)

### PHASE 1: GridCalculator (Pure Logic - 5 methods)
- `_compute_target_buy()` - Lines 1147-1164 ✅
- `_quantize()` - Lines 152-154 (helper function) ✅  
- `_tp_for_entry()` - Lines 143-144 (helper function) ✅
- `_next_lower_after_buy()` - Lines 146-147 (helper function) ✅
- `_within_band()` - Lines 140-141 (helper function) ✅

### PHASE 2: WebSocketHandler (Event Routing - 5 methods)
- `_setup_websocket_callbacks()` - Lines 359-377 ✅
- `_on_price_update()` - Lines 480-502 ✅
- `_on_order_update()` - Lines 744-760 ✅
- `_on_position_update()` - Lines 762-777 ✅
- `_handle_liquidation_alert()` - Lines 820-863 ✅
- `_handle_emergency_alert()` - Lines 865-883 ✅

### PHASE 3: FillDetector (Fill Processing - 3 methods)
- `_on_fill_detected()` - Lines 504-742 ✅ **CRITICAL**
- `_handle_robust_fill()` - Lines 779-818 ✅
- Fill deduplication logic (embedded in _on_fill_detected)

### PHASE 4: PositionManager (State Management - 12 methods)
- `_persist_runtime_state()` - Lines 2740-2785 ✅ **FIX #13**
- `_process_tp_retry_queue()` - Lines 1872-1931 ✅
- `_schedule_tp_retry()` - Lines 1792-1806 ✅
- `_try_reserve_order_capacity()` - Lines 432-461 ✅
- `_release_order_capacity()` - Lines 463-474 ✅
- State variables: `open_tranches`, `pending_buy`, `_tp_retry_queue`, `_reserved_capacity`, `_state_lock`

### PHASE 5: OrderManager (Order Operations - 10 methods)
- `_place_buy_order()` - Lines 2277-2463 ✅
- `_place_tp_sell()` - Lines 2465-2553 ✅
- `_place_tp_sell_with_retry()` - Lines 2555-2591 ✅
- `_cancel_pending_buy()` - Lines 1240-1350 ✅
- `_verify_order_cancelled()` - Lines 1191-1238 ✅
- `_find_safe_tp_price()` - Lines 1710-1728 ✅ **FIX #8**
- `_safe_place_tp()` - Lines 1730-1790 ✅ **FIX #8**
- `_execute_opportunistic_fill()` - Lines 1808-1853 ✅ **Transactional**
- `_place_opportunistic_tp()` - Lines 1855-1870 ✅ **Deprecated wrapper**
- `_generate_client_order_id()` - Lines 2253-2271 ✅

### PHASE 6: Reconciliation (Exchange Sync - 2 methods)
- `_sync_on_reconnect()` - Lines 2682-2708 ✅ **FIX #12**
- `_reconcile_positions_with_exchange()` - **NOT IMPLEMENTED** (called at line 2701)
- `_ensure_single_correct_pending_buy()` - Lines 1166-1189 ✅

### PHASE 7: VolatilityHandler (Complex Recovery - 15 methods)
- `_check_pending_order_safety()` - Lines 977-1062 ✅ **Proactive monitoring**
- `_trigger_volatility_halt()` - Lines 1356-1534 ✅
- `_calculate_missed_levels()` - Lines 1536-1561 ✅
- `_validate_recovery_feasibility()` - Lines 1563-1597 ✅
- `_wait_for_fill()` - Lines 1599-1632 ✅
- `_execute_market_orders()` - Lines 1634-1708 ✅
- `_finalize_recovery()` - Lines 1933-1977 ✅ **FIX #6**
- `_resume_normal_grid()` - Lines 1979-2006 ✅
- `_clear_halt_state()` - Lines 2008-2018 ✅
- `_execute_opportunistic_recovery()` - Lines 2020-2247 ✅ **Main orchestrator**

### Infrastructure (Not Extracted - Stay in GridBot)
- `__init__()` - Lines 170-357 (initialization)
- `connect()` - Lines 2666-2680
- `disconnect()` - Lines 2710-2737
- `cleanup()` - Lines 2941-3133
- `run()` - Lines 3186-3353
- `_setup_initial_grid()` - Lines 2597-2637
- `_check_and_handle_config_changes()` - Lines 2791-2939 (Hot reload)
- `_format_heartbeat_status()` - Lines 3139-3184
- `_handle_shutdown_signal()` - Lines 1064-1092
- `_emergency_cleanup()` - Lines 1094-1105
- Property: `emergency_stop` - Lines 383-426
- Property: `grid_params` - Lines 2643-2660

---

## 🔥 EXTRACTION ORDER (Safest → Riskiest)

### Phase 1: GridCalculator (RISK: LOW ✅)
**Why First**: Pure functions, zero dependencies, no state, easy to test

### Phase 2: WebSocketHandler (RISK: LOW ✅)
**Why Second**: Event routing only, no complex logic

### Phase 3: FillDetector (RISK: MEDIUM ⚠️)
**Why Third**: Uses state from PositionManager, but logic is clear

### Phase 4: PositionManager (RISK: HIGH 🔥)
**Why Fourth**: Owns the critical `_state_lock`, all other modules depend on it

### Phase 5: OrderManager (RISK: MEDIUM-HIGH 🔥)
**Why Fifth**: Complex API interactions, collision detection logic

### Phase 6: Reconciliation (RISK: MEDIUM ⚠️)
**Why Sixth**: Exchange sync is critical but well-isolated

### Phase 7: VolatilityHandler (RISK: VERY HIGH 🔥🔥🔥)
**Why Last**: Most complex, touches everything, opportunistic recovery logic

---

## 🎯 SUCCESS METRICS

### Code Quality
- ✅ Main file: < 300 lines (currently 3,492)
- ✅ Each module: < 500 lines
- ✅ No circular dependencies
- ✅ Clear separation of concerns

### Functionality (Zero Regressions!)
- ✅ All 72 methods preserved
- ✅ Bot starts successfully
- ✅ Fill detection works (WebSocket + polling)
- ✅ TP placement with collision detection
- ✅ State persistence (runtime_state.json)
- ✅ Reconnect sync (no missed fills)
- ✅ Volatility recovery (halt → recovery)
- ✅ Grid realignment (no drift)
- ✅ TP retry queue (async protection)

### Production Readiness
- ✅ Can deploy incrementally
- ✅ Rollback plan tested
- ✅ Zero downtime
- ✅ All tests pass

---

## 📅 ESTIMATED TIMELINE

| Phase | Module | Complexity | Effort | Status |
|-------|--------|------------|--------|--------|
| 1 | GridCalculator | LOW | 2-3 hours | ⏳ Pending |
| 2 | WebSocketHandler | LOW | 2-3 hours | ⏳ Pending |
| 3 | FillDetector | MEDIUM | 4-5 hours | ⏳ Pending |
| 4 | PositionManager | HIGH | 6-8 hours | ⏳ Pending |
| 5 | OrderManager | MEDIUM-HIGH | 6-8 hours | ⏳ Pending |
| 6 | Reconciliation | MEDIUM | 4-5 hours | ⏳ Pending |
| 7 | VolatilityHandler | VERY HIGH | 8-10 hours | ⏳ Pending |
| **TOTAL** | **7 Modules** | - | **32-42 hours** | - |

**Recommended Pace**: 1 phase per day (1 week total)

---

## 🚨 CRITICAL CONSTRAINTS

1. **ZERO BEHAVIOR CHANGES** - Only restructure, never modify logic
2. **INCREMENTAL EXTRACTION** - One module at a time, test thoroughly
3. **BACKWARD COMPATIBILITY** - Keep old methods as shims during transition
4. **THREAD SAFETY** - Preserve all `_state_lock` usage
5. **PRESERVE RECENT FIXES** - All 13 fixes must work after refactoring
6. **STATE PERSISTENCE** - runtime_state.json must continue working
7. **RECONNECT SYNC** - _sync_on_reconnect must work

---

**Next Steps**: See individual phase documents:
- `REFACTORING_PHASE_1_GridCalculator.md`
- `REFACTORING_PHASE_2_WebSocketHandler.md`
- `REFACTORING_PHASE_3_FillDetector.md`
- `REFACTORING_PHASE_4_PositionManager.md`
- `REFACTORING_PHASE_5_OrderManager.md`
- `REFACTORING_PHASE_6_Reconciliation.md`
- `REFACTORING_PHASE_7_VolatilityHandler.md`
