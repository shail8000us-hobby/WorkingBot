# Ultra-Granular Refactoring Plan — `async_gridbot.py`

**Date:** March 2, 2026  
**Supersedes:** `REFACTORING_PLAN_ASYNC_GRIDBOT.md` (high-level, 9 phases)  
**Purpose:** Break the 9-phase plan into **42 micro-phases** so each step is tiny, testable, and reversible  
**Philosophy:** Move 1-2 methods per micro-phase. Verify after EVERY step. Never rush.

---

## 📊 Current Status (Last Updated: Mar 2, 2026)

| Phase | Commits | Result | Notes |
|-------|---------|--------|-------|
| **P0: Setup** | f3eb264, a67c4b7 | ✅ **DONE** | Branch `refactor/split-gridbot` + backup + checklist script |
| **P1: GuardianHandler** | bf47445…e3acdd5 (8 commits) | ✅ **DONE** | `guardian_handler.py` 690 lines, `async_gridbot.py` −583 lines |
| **🧪 Full Bot Test P1** | 80a8a97 | ✅ **PASSED** (after 1 bug fix) | See bug report below |
| **P2: HealthMonitor** | 8a03d0f…905e95f (7 commits) | ✅ **DONE** | `health_monitor.py` 563 lines, `async_gridbot.py` −373 lines |
| **🧪 Full Bot Test P2** | 11e0dc8 | ✅ **PASSED** (after 1 bug fix) | See bug report below |
| **P3: ExchangeSync** | dcc3858…cf91d89 (8 commits) | ✅ **DONE** | `exchange_sync.py` 822 lines, `async_gridbot.py` −709 lines |
| **🧪 Full Bot Test P3** | — | ✅ **PASSED** (0 bugs) | Clean start→stop→start, no tracebacks |
| **P4: WSLifecycle** | 856f049…e8a439a (8 commits + 2 bugfixes) | ✅ **DONE** | `ws_lifecycle.py` 576 lines, `async_gridbot.py` −500 lines |
| **🧪 Full Bot Test P4** | — | ✅ **PASSED** (after 2 bug fixes) | Clean start→stop→start, zero errors |
| P5–P9 | — | ⬜ Not started | — |

### 🐛 Bug Found During P1 Full Bot Test

**File:** `bot/strategy/simple_state_coordinator.py` line 161 (`_get_guardian_status`)

**Error (repeated every ~1 second until fixed):**
```
ERROR | bot.strategy.simple_state_coordinator:_get_guardian_status:164 -
Error reading Guardian status: 'AsyncGridBot' object has no attribute '_read_guardian_signal'
```

**Root Cause:** `simple_state_coordinator.py` still called `self.bot._read_guardian_signal()` which was moved to `GuardianHandler` in P1.2.

**Fix:** `self.bot._read_guardian_signal()` → `self.bot.guardian.read_signal()` (same `tuple[str, str]` return signature)

**Committed:** `80a8a976c` — "Fix: simple_state_coordinator use guardian.read_signal() after P1 extraction"

**Lesson for future phases:** When moving methods, `grep -rn` the entire `bot/` tree (not just `async_gridbot.py`) for the old method name, since `simple_state_coordinator.py`, `health_monitor.py` etc. can also hold references.

### 🐛 Bug Found During P2 Full Bot Test

**File:** `bot/strategy/async_gridbot.py` line 1325 (`start()` → `health_monitor.set_runtime_refs()`)

**Error (bot crashed at startup, before any tasks launched):**
```
AttributeError: 'AsyncGridBot' object has no attribute '_format_pending_order_info'
```

**Root Cause:** `async_gridbot.py` passed `_format_pending_order_callback=self._format_pending_order_info` to `set_runtime_refs()`. This method was moved to `HealthMonitor` in P2.3. Note: the callback is dead code (never read inside `health_monitor.py` — the method is called internally as `self._format_pending_order_info()`), but the stale reference still crashed the bot.

**Fix:** `self._format_pending_order_info` → `self.health_monitor._format_pending_order_info`

**Committed:** `11e0dc81e` — "Fix: async_gridbot pass health_monitor._format_pending_order_info after P2 extraction"

**Lesson:** When passing `self.method` as a callback to `set_runtime_refs()`, the method may have already been moved. Always grep the `set_runtime_refs()` call block for any `self._xxx` references from the extracted class.

### 🐛 Bug #1 Found During P4 Full Bot Test

**Error:** `AttributeError: 'AsyncGridBot' object has no attribute 'ws_lifecycle'`

**Root Cause:** `self._rest_fallback_active = False` was set at line 569 in `__init__`, before `ws_lifecycle` was constructed at line 703. The property proxy setter tried `self.ws_lifecycle._rest_fallback_active = value` which failed because `ws_lifecycle` didn't exist yet.

**Fix:** Removed early assignment — WSLifecycle owns this state and initializes it in its own `__init__`.

**Committed:** `91a5b9ea3` — "P4 Fix: remove early _rest_fallback_active init that conflicts with ws_lifecycle proxy"

### 🐛 Bug #2 Found During P4 Full Bot Test

**Error:** `'NoneType' object has no attribute 'price_data_flowing'` from `human_log.price_data_flowing()`

**Root Cause:** Wrong import path in ws_lifecycle.py: `from bot.utils.human_log import human_log` instead of `from bot.utils.human_logger import human_log`. This silently set `human_log = None`.

**Fix:** Corrected import path + added `if human_log:` guards on all 5 call sites.

**Committed:** `e8a439abb` — "P4 Fix: correct human_log import path + add None guards in ws_lifecycle"

**Lesson:** Always verify import paths by grepping the existing codebase for the canonical import. Add defensive None guards on optional singletons.

---

## How This Plan Works

Each **Macro Phase** (1-8) from the original plan is split into numbered **micro-phases**.
Naming: `P1.1`, `P1.2`, ... `P1.8` = sub-steps of Phase 1 (GuardianHandler).

Each micro-phase has:
1. **What Moves** — exactly which method(s) to copy
2. **What Changes** — exact edits in async_gridbot.py
3. **Verify** — syntax check + import check (30 seconds)
4. **Commit** — one commit per micro-phase

After every **Macro Phase** completes: run the **FULL BOT TEST** (start bot, verify heartbeat, price updates, Guardian signal, stop cleanly).

---

## Quick Reference — All 42 Micro-Phases

| # | Micro-Phase | What Moves | Risk | Est. Time |
|---|-------------|-----------|------|-----------|
| — | **P0: Setup** | — | None | 10 min |
| 0.1 | Create branch + backup | — | None | 5 min |
| 0.2 | Create verification checklist | — | None | 5 min |
| — | **P1: GuardianHandler** | **~520 lines** | **Low** | **90 min** |
| 1.1 | Create guardian_handler.py skeleton | Class + `__init__` only | None | 10 min |
| 1.2 | Move `_read_guardian_signal` | 1 method (~95 lines) | Low | 10 min |
| 1.3 | Move `_check_guardian_transition_and_retry` | 1 method (~40 lines) | Low | 10 min |
| 1.4 | Move `_retry_missed_grid_orders` | 1 method (~112 lines) | Low | 15 min |
| 1.5 | Move `_fill_multi_step_missed_grids` | 1 method (~135 lines) | Low | 15 min |
| 1.6 | Move `_check_guardian_transitions` | 1 method (~42 lines) | Low | 10 min |
| 1.7 | Move `_cancel_pending_entry_orders` + `_resume_grid_trading` | 2 methods (~147 lines) | Low | 15 min |
| 1.8 | Move `_guardian_health_monitor_loop` + cleanup orchestrator | 1 method (~32 lines) + wiring | Low | 15 min |
| — | **🧪 FULL BOT TEST** after P1 | — | — | 10 min |
| — | **P2: HealthMonitor** | **~400 lines** | **Low** | **75 min** |
| 2.1 | Create health_monitor.py skeleton | Class + `__init__` only | None | 10 min |
| 2.2 | Move `_update_external_heartbeat` | 1 method (~20 lines) | None | 5 min |
| 2.3 | Move `_heartbeat_loop` | 1 method (~120 lines) | Low | 15 min |
| 2.4 | Move `_monitoring_loop` | 1 method (~78 lines) | Low | 10 min |
| 2.5 | Move `_check_memory_usage` + `_check_websocket_health` | 2 methods (~68 lines) | Low | 10 min |
| 2.6 | Move `_health_check_loop` | 1 method (~66 lines) | Low | 10 min |
| 2.7 | Move `_watchdog_loop` + cleanup orchestrator | 1 method (~55 lines) + wiring | Low | 15 min |
| — | **🧪 FULL BOT TEST** after P2 | — | — | 10 min |
| — | **P3: ExchangeSync** | **~600 lines** | **Medium** | **100 min** |
| 3.1 | Create exchange_sync.py skeleton | Class + `__init__` only | None | 10 min |
| 3.2 | Move `_detect_exchange_state` + `_handle_exchange_maintenance` | 2 methods (~108 lines) | Low | 15 min |
| 3.3 | Move `_exchange_maintenance_monitor` | 1 method (~34 lines) | Low | 10 min |
| 3.4 | Move `_sync_positions_from_exchange` | 1 method (~85 lines) | Medium | 10 min |
| 3.5 | Move `_reconcile_orphaned_orders` | 1 method (~170 lines) | Medium | 20 min |
| 3.6 | Move `_cleanup_misaligned_orders` | 1 method (~43 lines) | Medium | 10 min |
| 3.7 | Move `_reconcile_fills_after_reconnect` + `_ensure_grid_coverage` | 2 methods (~149 lines) | Medium | 15 min |
| 3.8 | Move `_full_exchange_sync` + cleanup orchestrator | 1 method (~190 lines) + wiring | Medium | 15 min |
| — | **🧪 FULL BOT TEST** after P3 | — | — | 10 min |
| — | **P4: WSLifecycle** | **~500 lines** | **Medium** | **90 min** |
| 4.1 | Create ws_lifecycle.py skeleton | Class + `__init__` only | None | 10 min |
| 4.2 | Move `get_current_price` + `_fetch_current_price` | 2 methods (~34 lines) | Low | 10 min |
| 4.3 | Move `_register_ws_handlers` + `_subscribe_channels` + `_ws_message_loop` | 3 methods (~38 lines) | Low | 10 min |
| 4.4 | Move `_handle_ticker_update` + `_handle_position_update` | 2 methods (~178 lines) | Medium | 15 min |
| 4.5 | Move `_reconnect_websocket` | 1 method (~16 lines) | Low | 5 min |
| 4.6 | Move `_rest_fallback_monitor_loop` | 1 method (~70 lines) | Medium | 10 min |
| 4.7 | Move `_activate_rest_fallback` + `_deactivate_rest_fallback` | 2 methods (~48 lines) | Low | 10 min |
| 4.8 | Move REST polling methods + cleanup orchestrator | 4 methods (~100 lines) + wiring | Medium | 20 min |
| — | **🧪 FULL BOT TEST** after P4 | — | — | 10 min |
| — | **P5: FillProcessor** | **~700 lines** | **HIGH** | **120 min** |
| 5.1 | Create fill_processor.py skeleton | Class + `__init__` + dedup state | None | 15 min |
| 5.2 | Move fill dedup helpers (6 methods) | `_is_fill_seen`, etc. (~27 lines) | Low | 10 min |
| 5.3 | Move `_calculate_next_grid_level` | 1 method (~26 lines) | Low | 10 min |
| 5.4 | Move `_track_saga_completion` | 1 method (~65 lines) | Medium | 15 min |
| 5.5 | Move `_process_fill` | 1 method (~230 lines) — THE critical method | **HIGH** | 25 min |
| 5.6 | Move `_track_order_in_fill_monitor` + `_verify_order_after_placement` | 2 methods (~177 lines) | Medium | 15 min |
| 5.7 | Move `_process_missed_fill` (FillMonitor callback) | 1 method (~63 lines) | Medium | 10 min |
| 5.8 | Move `_handle_order_update` + `_handle_user_trades` + cleanup | 2 methods (~120 lines) + wiring | Medium | 20 min |
| — | **🧪 FULL BOT TEST** after P5 + **FILL VERIFICATION** | — | — | **20 min** |
| — | **P6: GridEngine** | **~800 lines** | **HIGH** | **120 min** |
| 6.1 | Create grid_engine.py skeleton | Class + `__init__` + Lock | None | 15 min |
| 6.2 | Move `_is_cooldown_ready` + `_should_recalculate_grid_level` | 2 methods (~28 lines) | Low | 10 min |
| 6.3 | Move `_comprehensive_safety_check` | 1 method (~78 lines) | Medium | 15 min |
| 6.4 | Move `_format_pending_order_info` + `_log_detailed_grid_status` | 2 methods (~126 lines) | Low | 10 min |
| 6.5 | Move `_place_grid_order` | 1 method (~75 lines) | Medium | 15 min |
| 6.6 | Move `_check_and_place_entry_order` | 1 method (~78 lines) | **HIGH** | 15 min |
| 6.7 | Move `seed_missed_grid_levels` | 1 method (~73 lines) | Medium | 10 min |
| 6.8 | Move `_place_initial_order` + cleanup orchestrator | 1 method (~280 lines) + wiring | **HIGH** | 30 min |
| — | **🧪 FULL BOT TEST** after P6 + **ORDER PLACEMENT TEST** | — | — | **20 min** |
| — | **P7: RecoveryActions** | **~500 lines** | **Medium** | **75 min** |
| 7.1 | Create recovery_actions.py skeleton | Class + `__init__` only | None | 10 min |
| 7.2 | Move `_safety_gatekeeper_loop` + `_check_for_unhedged_positions` | 2 methods (~80 lines) | Low | 10 min |
| 7.3 | Move `_fill_polling_fallback_loop` | 1 method (~74 lines) | Medium | 10 min |
| 7.4 | Move `_process_tp_retry_queue` | 1 method (~110 lines) | Medium | 15 min |
| 7.5 | Move `_reconciliation_action_processor` + `_execute_reconciliation_action` | 2 methods (~110 lines) | Medium | 10 min |
| 7.6 | Move `_place_emergency_tp_for_position` + `_process_missed_fill` (recon) | 2 methods (~70 lines) | Medium | 10 min |
| 7.7 | Cleanup orchestrator + final wiring | — | Low | 10 min |
| — | **🧪 FULL BOT TEST** after P7 | — | — | 10 min |
| — | **P8: Slim Orchestrator** | — | **Low** | **45 min** |
| 8.1 | Slim `__init__` (remove moved code) | ~250 lines removed | Low | 15 min |
| 8.2 | Slim `start()` (replace task creation) | ~100 lines simplified | Low | 15 min |
| 8.3 | Slim `stop()` + final cleanup | ~50 lines simplified | Low | 15 min |
| — | **🧪 FULL BOT TEST** after P8 | — | — | 10 min |
| — | **P9: Final Verification** | — | None | 30 min |
| 9.1 | Full cold-start test | — | — | 15 min |
| 9.2 | Merge to SSR branch | — | — | 15 min |

**Total: 42 micro-phases + 8 full bot tests = ~14 hours**

---

## Pre-Start: What You Need

1. **No open positions** (or at least none you can't afford to monitor manually)
2. **Guardian bot running** (bot needs it for signal checking)
3. **PM2 available** for start/stop
4. **Git on SSR branch** with clean working tree

---

## Phase 0: Setup — ✅ DONE

### P0.1 — Create Branch + Backup (5 min) ✅

```bash
cd ~/Projects/WorkingBot
git checkout SSR
git pull
git checkout -b refactor/split-gridbot

# Safety backup
cp bot/strategy/async_gridbot.py bot/strategy/async_gridbot.py.pre_refactor_backup

git add bot/strategy/async_gridbot.py.pre_refactor_backup
git commit -m "P0.1: Backup async_gridbot.py before refactoring"
```

### P0.2 — Create Verification Checklist (5 min) ✅

Create file `tests/refactoring_checklist.sh`:

```bash
#!/bin/bash
# Run after EVERY micro-phase
set -e

echo "=== SYNTAX CHECK ==="
python3 -c "import py_compile; py_compile.compile('bot/strategy/async_gridbot.py', doraise=True)"
echo "  ✅ async_gridbot.py syntax OK"

# Check new module if provided as argument
if [ -n "$1" ]; then
    python3 -c "import py_compile; py_compile.compile('$1', doraise=True)"
    echo "  ✅ $1 syntax OK"
fi

echo ""
echo "=== IMPORT CHECK ==="
python3 -c "from bot.strategy.async_gridbot import AsyncGridBot; print('  ✅ AsyncGridBot import OK')"

echo ""
echo "=== ALL CHECKS PASSED ==="
```

```bash
chmod +x tests/refactoring_checklist.sh
git add tests/refactoring_checklist.sh
git commit -m "P0.2: Add refactoring verification script"
```

**FULL BOT TEST after P0:** Not needed (no code changed).

---

## Phase 1: Extract `guardian_handler.py` (~520 lines, LOW risk) — ✅ DONE

### Why First
- Self-contained signal-reading concern
- Zero order placement logic
- If this breaks, worst case = Guardian signal not read → bot safely halts (fail-safe)
- Only reads EventStore and manages a missed-order buffer

### P1.1 — Create GuardianHandler Skeleton (10 min)

Create `bot/strategy/modules/guardian_handler.py` with **only** the class definition and `__init__`:

```python
"""
Guardian Signal Handler — extracted from async_gridbot.py Phase 1

Responsibilities:
- Read Guardian GO/STOP signal from EventStore
- Detect signal transitions (STOP→GO, GO→STOP)
- Manage missed grid orders during STOP periods
- Retry missed orders on GO resume
- Multi-step missed grid recovery (A3 fix)
- Cancel pending entry orders on STOP
- Resume grid trading on GO
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from loguru import logger as log

from bot.strategy.modules.event_store import EventStore, EventType


class GuardianHandler:
    """Handles Guardian signal reading, transitions, and missed-order recovery."""

    def __init__(
        self,
        event_store: EventStore,
        position_actor,       # PositionManagerActor
        order_actor,          # OrderManagerActor
        grid_calc,            # GridCalculator
        mode: str,            # "LONG" or "SHORT"
        grid_step: float,
        max_positions: int,
        lot_size: float,
        ref_price: float,
        should_log_fn: Callable,  # (key: str, interval: float) -> bool
    ):
        self.event_store = event_store
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.grid_calc = grid_calc
        self.mode = mode
        self.grid_step = grid_step
        self.max_positions = max_positions
        self.lot_size = lot_size
        self.ref_price = ref_price
        self._should_log = should_log_fn

        # Guardian state
        self._last_guardian_signal: Optional[str] = None
        self._guardian_transition_time: float = 0
        self._missed_grid_orders: List = []

        # Runtime references (set by orchestrator via set_runtime_refs)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._set_running: Callable = lambda v: None

    def set_runtime_refs(
        self,
        get_running: Callable,        # () -> bool
        get_current_price: Callable,   # () -> Optional[float]
        set_running: Callable,         # (bool) -> None
    ):
        """Wire runtime references after construction."""
        self._get_running = get_running
        self._get_current_price = get_current_price
        self._set_running = set_running
```

**Verify:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
```

**Commit:**
```bash
git add bot/strategy/modules/guardian_handler.py
git commit -m "P1.1: Create GuardianHandler skeleton (class + __init__ only)"
```

---

### P1.2 — Move `_read_guardian_signal` (10 min)

**What:** Copy the `_read_guardian_signal` method (lines 710-805, ~95 lines) from `async_gridbot.py` into `GuardianHandler`.

**Method name in new file:** `read_signal` (drop leading underscore — it's now a public interface)

**Attribute translations needed:**
| In async_gridbot.py | In GuardianHandler |
|---------------------|-------------------|
| `self._last_guardian_signal` | `self._last_guardian_signal` (same — owned here now) |
| `self._guardian_transition_time` | `self._guardian_transition_time` (same) |
| `self._running` (read) | `self._get_running()` |
| `self._running = False` | `self._set_running(False)` |
| `self._should_log(...)` | `self._should_log(...)` (same — callable) |
| `self.event_store` | `self.event_store` (same) |

**In async_gridbot.py:**
1. Add import at top: `from bot.strategy.modules.guardian_handler import GuardianHandler`
2. Add to `__init__`: Create the `GuardianHandler` instance (see P1.1 constructor call)
3. Add to `start()`: Call `self.guardian.set_runtime_refs(...)`
4. Replace ALL calls to `self._read_guardian_signal()` → `self.guardian.read_signal()`
5. Replace ALL reads of `self._last_guardian_signal` → `self.guardian._last_guardian_signal`
6. **DO NOT** delete the original method yet (keep it commented out as backup)

**Find calls:** `grep -n "_read_guardian_signal\|_last_guardian_signal" bot/strategy/async_gridbot.py`

**Verify:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
```

**Commit:**
```bash
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.2: Move _read_guardian_signal to GuardianHandler.read_signal()"
```

---

### P1.3 — Move `_check_guardian_transition_and_retry` (10 min)

**What:** Copy `_check_guardian_transition_and_retry` (lines 908-948, ~40 lines) into `GuardianHandler`.

**Method name:** `check_transition_and_retry`

**Key dependency:** This method calls `self._retry_missed_grid_orders()` — which hasn't moved yet. Two options:
- **Option A (recommended):** Move this method now, but have it call `self.retry_missed_orders()` which we'll add in P1.4. Add a temporary stub: `async def retry_missed_orders(self): pass`
- **Option B:** Skip and combine with P1.4 — but this breaks the "1-2 methods per step" rule.

**Use Option A.** Add a stub that logs a warning if called before P1.4.

**In async_gridbot.py:**
- Replace calls to `self._check_guardian_transition_and_retry()` → `self.guardian.check_transition_and_retry()`
- Comment out the original method

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.3: Move _check_guardian_transition_and_retry to GuardianHandler"
```

---

### P1.4 — Move `_retry_missed_grid_orders` (15 min)

**What:** Copy `_retry_missed_grid_orders` (lines 951-1063, ~112 lines) into `GuardianHandler`.

**Method name:** `retry_missed_orders`

**Attribute translations:**
| In async_gridbot.py | In GuardianHandler |
|---------------------|-------------------|
| `self._missed_grid_orders` | `self._missed_grid_orders` (owned here) |
| `self.current_price` | `self._get_current_price()` |
| `self.position_actor` | `self.position_actor` (same) |
| `self.order_actor` | `self.order_actor` (same) |
| `self.mode` | `self.mode` (same) |
| `self.lot_size` | `self.lot_size` (same) |
| `self.max_positions` | `self.max_positions` (same) |
| `self.grid_calc.step` | `self.grid_calc.step` (same) |

**Remove the stub** added in P1.3. Replace with the real method.

**In async_gridbot.py:**
- Replace calls to `self._retry_missed_grid_orders()` → `self.guardian.retry_missed_orders()`
- Replace reads of `self._missed_grid_orders` → `self.guardian._missed_grid_orders`
- Comment out the original method

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.4: Move _retry_missed_grid_orders to GuardianHandler"
```

---

### P1.5 — Move `_fill_multi_step_missed_grids` (15 min)

**What:** Copy `_fill_multi_step_missed_grids` (lines 1064-1199, ~135 lines) — the A3 fix — into `GuardianHandler`.

**Method name:** `fill_multi_step_missed_grids`

**Key dependency check:** This method calls:
- `self.position_actor.ask("GET_STATE", ...)` ✅ (already passed to handler)
- `self.order_actor.ask("PLACE_ORDER", ...)` ✅ (already passed)
- `self.grid_calc.step` ✅ (already passed)
- `self.mode`, `self.lot_size`, `self.max_positions` ✅

No dependency on methods that haven't moved yet. Clean extraction.

**In async_gridbot.py:**
- Replace calls to `self._fill_multi_step_missed_grids()` → `self.guardian.fill_multi_step_missed_grids()`
- Comment out the original method

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.5: Move _fill_multi_step_missed_grids (A3 fix) to GuardianHandler"
```

---

### P1.6 — Move `_check_guardian_transitions` (10 min)

**What:** Copy `_check_guardian_transitions` (lines 4236-4278, ~42 lines) into `GuardianHandler`.

**Method name:** `check_transitions`

**Key dependency:** This method calls:
- `self._cancel_pending_entry_orders()` — hasn't moved yet
- `self._resume_grid_trading()` — hasn't moved yet

**Strategy:** Use callbacks. Add these to the class:
```python
self._cancel_entries_callback: Optional[Callable] = None
self._resume_grid_callback: Optional[Callable] = None
```

For now, these callbacks will point to the ORIGINAL methods still on the orchestrator:
```python
# In orchestrator start():
self.guardian._cancel_entries_callback = self._cancel_pending_entry_orders
self.guardian._resume_grid_callback = self._resume_grid_trading
```

These callbacks will be updated in P1.7 when those methods move in.

**In async_gridbot.py:**
- Replace calls: `await self._check_guardian_transitions()` → `await self.guardian.check_transitions()`
- Comment out original

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.6: Move _check_guardian_transitions to GuardianHandler"
```

---

### P1.7 — Move `_cancel_pending_entry_orders` + `_resume_grid_trading` (15 min)

**What:** Copy both methods into `GuardianHandler`:
- `_cancel_pending_entry_orders` (lines 4280-4332, ~52 lines) → `cancel_pending_entries`
- `_resume_grid_trading` (lines 4334-4428, ~95 lines) → `resume_grid`

**Why together:** They're always paired (cancel on STOP, resume on GO) and `_check_guardian_transitions` (already moved in P1.6) calls both.

**Attribute translations for `_resume_grid_trading`:**
| In async_gridbot.py | In GuardianHandler |
|---------------------|-------------------|
| `self.current_price` | `self._get_current_price()` |
| `self.api_client` | Need to add `self.api_client` to constructor |
| `self.product_id` | Need to add `self.product_id` to constructor |
| `self.symbol` | Need to add `self.symbol` to constructor |

**Constructor update:** Add `api_client`, `product_id`, `symbol` parameters to `__init__`. Update the constructor call in `async_gridbot.py.__init__` accordingly.

**Update P1.6 callbacks:** Now that both methods live in GuardianHandler, update `check_transitions` to call `self.cancel_pending_entries()` and `self.resume_grid()` directly instead of via callbacks. Remove the callback attributes.

**In async_gridbot.py:**
- Replace: `self._cancel_pending_entry_orders()` → `self.guardian.cancel_pending_entries()`
- Replace: `self._resume_grid_trading()` → `self.guardian.resume_grid()`
- Comment out both original methods

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.7: Move cancel_pending_entries + resume_grid to GuardianHandler"
```

---

### P1.8 — Move `_guardian_health_monitor_loop` + Cleanup (15 min)

**What:**
1. Copy `_guardian_health_monitor_loop` (lines 4098-4130, ~32 lines) → `health_monitor_loop`
2. **Delete** all the commented-out original methods from `async_gridbot.py`
3. Verify the import and constructor wiring is clean

**Delete from async_gridbot.py:**
- The commented-out `_read_guardian_signal`
- The commented-out `_check_guardian_transition_and_retry`
- The commented-out `_retry_missed_grid_orders`
- The commented-out `_fill_multi_step_missed_grids`
- The commented-out `_check_guardian_transitions`
- The commented-out `_cancel_pending_entry_orders`
- The commented-out `_resume_grid_trading`
- The commented-out `_guardian_health_monitor_loop`

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/guardian_handler.py
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "P1.8: Move guardian_health_monitor_loop + cleanup dead code (~520 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 1 (10 min) — ✅ PASSED (Mar 2, 2026)

**Test ran on:** `gridbot-btc-live` (PM2), branch `refactor/split-gridbot`

**Results:**
- ✅ `guardian_handler.py` syntax OK, import OK
- ✅ `async_gridbot.py` syntax OK, import OK
- ✅ `🛡️  Guardian: 🟢 GO` — signal read correctly from `guardian_handler:read_signal:131`
- ✅ `[HB] Positions: 0/20 | Price: $66,392↑ | ✅ ACTIVE` — heartbeat clean
- ✅ No ImportError, AttributeError, or NameError after fix
- ✅ Bot stopped cleanly via `pm2 stop`

**Bug found and fixed before passing** — see `## 📊 Current Status` bug report above.

**Commits in this phase:**
```
f3eb264  P0.1: Backup async_gridbot.py before refactoring
a67c4b7  P0.2: Add refactoring verification script
bf47445  P1.1: Create GuardianHandler skeleton (class + __init__ only)
42c5ff0  P1.2: Move _read_guardian_signal → GuardianHandler.read_signal()
124cf60  P1.3: Move _check_guardian_transition_and_retry
a491310  P1.4: Move _retry_missed_grid_orders
13c32947 P1.5: Move _fill_multi_step_missed_grids (A3 fix)
09815f3  P1.6: Move _check_guardian_transitions
9193435  P1.7: Move cancel_pending_entries + resume_grid
e3acdd5  P1.8: Move guardian_health_monitor_loop + cleanup
80a8a97  Fix: simple_state_coordinator use guardian.read_signal() after P1 extraction
```

**Original guidance (kept for reference):**
```bash
# Start bot
pm2 start ecosystem.config.js --only gridbot-btc

# Wait 60 seconds, then check:
pm2 logs gridbot-btc --lines 50

# Look for:
# ✅ "🛡️  Guardian: 🟢 GO" — signal is being read
# ✅ "[HB]" heartbeat messages
# ✅ No ImportError, AttributeError, or NameError
# ✅ No Python tracebacks

# Stop bot
pm2 stop gridbot-btc

# Verify clean shutdown (no hanging processes)
ps aux | grep async_gridbot
```

**If FAIL:** `git revert HEAD~8..HEAD` reverts all P1 micro-phases.

---

## Phase 2: Extract `health_monitor.py` (~400 lines, LOW risk) — ✅ DONE

### Why Second
- Read-only observation loops — they **never** place orders or mutate trading state
- If broken, bot still trades correctly — just no heartbeat/monitoring
- Clear boundary: write JSON files, log status, nothing else

---

### P2.1 — Create HealthMonitor Skeleton (10 min)

Create `bot/strategy/modules/health_monitor.py`:

```python
"""
Health Monitor — extracted from async_gridbot.py Phase 2

Responsibilities:
- Heartbeat loop (5s cycle, 15s detailed status, 60s grid report)
- Monitoring loop (5s snapshot JSON writes)
- Actor/saga/WebSocket health checks
- Memory usage monitoring
- Event loop watchdog (freeze detection)
- External heartbeat file writer

NOT Responsible For:
- Order placement
- Fill processing
- Guardian signal reading (→ GuardianHandler)
- Exchange sync
"""

import asyncio
import gc
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any
from loguru import logger as log


class HealthMonitor:
    """Read-only health monitoring and heartbeat system."""

    def __init__(
        self,
        position_actor,
        order_actor,
        saga_orchestrator,
        api_client,
        grid_calc,
        price_monitor,
        fill_monitor,
        mode: str,
        symbol: str,
        symbol_name: str,
        max_positions: int,
        instance_name: str,
        config,
        should_log_fn: Callable,
    ):
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.saga_orchestrator = saga_orchestrator
        self.api_client = api_client
        self.grid_calc = grid_calc
        self.price_monitor = price_monitor
        self.fill_monitor = fill_monitor
        self.mode = mode
        self.symbol = symbol
        self.symbol_name = symbol_name
        self.max_positions = max_positions
        self.instance_name = instance_name
        self.config = config
        self._should_log = should_log_fn

        # Watchdog state
        self._watchdog_timeout = 30.0
        self._watchdog_check_interval = 10.0

        # Runtime references (set by orchestrator)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._get_start_time: Callable = lambda: 0
        self._get_fills_processed: Callable = lambda: 0
        self._get_sagas_completed: Callable = lambda: 0
        self._get_sagas_failed: Callable = lambda: 0
        self._get_last_price_update: Callable = lambda: 0
        self._get_initial_order_placed: Callable = lambda: False
        self._get_last_heartbeat_time: Callable = lambda: 0
        self._set_last_heartbeat_time: Callable = lambda v: None
        self._tp_retry_callback: Optional[Callable] = None
        self._check_guardian_transitions_callback: Optional[Callable] = None

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git add bot/strategy/modules/health_monitor.py
git commit -m "P2.1: Create HealthMonitor skeleton (class + __init__ only)"
```

---

### P2.2 — Move `_update_external_heartbeat` (5 min)

**What:** Copy `_update_external_heartbeat` (lines 3643-3662, ~20 lines) → `update_external_heartbeat`

**Dependencies:** `self.mode`, `Path`, `json`, `time` — all available.

**In async_gridbot.py:**
- Replace: `self._update_external_heartbeat()` → `self.health_monitor.update_external_heartbeat()`
- Comment out original

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.2: Move _update_external_heartbeat to HealthMonitor"
```

---

### P2.3 — Move `_heartbeat_loop` (15 min)

**What:** Copy `_heartbeat_loop` (lines 3663-3783, ~120 lines) → `heartbeat_loop`

**Attribute translations:**
| In async_gridbot.py | In HealthMonitor |
|---------------------|-----------------|
| `self._running` | `self._get_running()` |
| `self.current_price` | `self._get_current_price()` |
| `self._start_time` | `self._get_start_time()` |
| `self._fills_processed` | `self._get_fills_processed()` |
| `self._last_heartbeat_time` | `self._get_last_heartbeat_time()` / `self._set_last_heartbeat_time(v)` |
| `self._initial_order_placed` | `self._get_initial_order_placed()` |

**This method calls `self._update_external_heartbeat()`** — already moved in P2.2 ✅. Update to `self.update_external_heartbeat()`.
**This method calls `self._log_detailed_grid_status()`** — still in orchestrator. Use callback `self._log_grid_status_callback`.

**In async_gridbot.py:**
- Replace task creation: `self._heartbeat_loop()` → `self.health_monitor.heartbeat_loop()`
- Comment out original

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.3: Move _heartbeat_loop to HealthMonitor"
```

---

### P2.4 — Move `_monitoring_loop` (10 min)

**What:** Copy `_monitoring_loop` (lines 3784-3862, ~78 lines) → `monitoring_loop`

**Translations:** Same pattern — replace `self._running` with `self._get_running()`, etc.

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.4: Move _monitoring_loop to HealthMonitor"
```

---

### P2.5 — Move `_check_memory_usage` + `_check_websocket_health` (10 min)

**What:** Copy both helper methods:
- `_check_memory_usage` (lines 4132-4150, ~18 lines) → `check_memory_usage`
- `_check_websocket_health` (lines 4152-4196, ~50 lines) → `check_websocket_health`

**Why together:** Both are simple health checks called only from `_health_check_loop` (next step).

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.5: Move _check_memory_usage + _check_websocket_health to HealthMonitor"
```

---

### P2.6 — Move `_health_check_loop` (10 min)

**What:** Copy `_health_check_loop` (lines 4152-4198+, ~66 lines) → `health_check_loop`

**Key dependency:** This method calls:
- `self._check_guardian_transitions()` — already moved to GuardianHandler (Phase 1). Use callback.
- `self._process_tp_retry_queue()` — still in orchestrator (moves in Phase 7). Use callback.
- `self._check_websocket_health()` — already moved in P2.5 ✅
- `self._check_memory_usage()` — already moved in P2.5 ✅

Set callbacks in orchestrator's `start()`:
```python
self.health_monitor._check_guardian_transitions_callback = self.guardian.check_transitions
self.health_monitor._tp_retry_callback = self._process_tp_retry_queue  # stays until P7
```

**In async_gridbot.py:**
- Replace task: `self._health_check_loop()` → `self.health_monitor.health_check_loop()`
- Comment out original

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.6: Move _health_check_loop to HealthMonitor"
```

---

### P2.7 — Move `_watchdog_loop` + Cleanup (15 min)

**What:**
1. Copy `_watchdog_loop` (lines 4543-4598, ~55 lines) → `watchdog_loop`
2. Delete all commented-out Phase 2 methods from `async_gridbot.py`
3. Verify wiring is clean

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/health_monitor.py
git commit -m "P2.7: Move _watchdog_loop + cleanup dead code (~400 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 2 (10 min) — ✅ PASSED (Mar 2, 2026)

**Test ran on:** `gridbot-btc-live` (PM2), branch `refactor/split-gridbot`

**Results:**
- ✅ `health_monitor.py` syntax OK, import OK
- ✅ `async_gridbot.py` syntax OK, import OK
- ✅ `💓 Heartbeat loop started (every 20s)` — from `health_monitor:heartbeat_loop:168`
- ✅ `📊 Monitoring loop started` — from `health_monitor:monitoring_loop:293`
- ✅ `Health check loop started` — from `health_monitor:health_check_loop:439`
- ✅ `🐕 Watchdog started (timeout: 60.0s)` — from `health_monitor:watchdog_loop:515`
- ✅ `[HB] Positions: 0/20 | Price: $66,296 | ✅ ACTIVE` — from `health_monitor:heartbeat_loop:270`
- ✅ Guardian `🟢 GO` reading from `guardian_handler:read_signal:131`
- ✅ 2x cold-start cycle confirmed (start → stop → start)
- ✅ No ImportError, AttributeError, or traceback after fix

**Bug found and fixed before passing** — see `## 📊 Current Status` P2 bug report above.

**Commits in this phase:**
```
8a03d0f  P2.1: Create HealthMonitor skeleton (class + __init__ only)
563d48e  P2.2: Move _update_external_heartbeat to HealthMonitor
6d977bb  P2.3: Move _heartbeat_loop + _format_pending_order_info to HealthMonitor
2c345f8  P2.4: Move _monitoring_loop to HealthMonitor
e81ab20  P2.5: Move _check_memory_usage + _check_websocket_health to HealthMonitor
84f2c8c  P2.6: Move _health_check_loop to HealthMonitor
905e95f  P2.7: Move _watchdog_loop + cleanup dead code (~373 lines extracted)
11e0dc8  Fix: async_gridbot pass health_monitor._format_pending_order_info after P2 extraction
```

**Cumulative progress (P1 + P2):** Original 5,770 → Now 4,815 lines (−955 lines, −16.5%). Modules: `guardian_handler.py` (690 lines) + `health_monitor.py` (563 lines)

**Original guidance (kept for reference):**
```bash
pm2 start ecosystem.config.js --only gridbot-btc
# Wait 30s, check for:
# ✅ [HB] heartbeat messages every 15s
# ✅ Monitoring JSON snapshot written
# ✅ No tracebacks
pm2 stop gridbot-btc
```

---

## Phase 3: Extract `exchange_sync.py` (~600 lines, MEDIUM risk) — ✅ DONE

### Why Third
- Runs mostly at startup (one-time reconciliation) and during maintenance
- Not on the hot trading path
- Medium risk: touches exchange API and position actor

---

### P3.1 — Create ExchangeSync Skeleton (10 min)

Create `bot/strategy/modules/exchange_sync.py`:

```python
"""
Exchange Sync & Reconciliation — extracted from async_gridbot.py Phase 3

Responsibilities:
- Reconcile orphaned orders at startup
- Clean up misaligned grid orders
- Reconcile fills after WebSocket reconnect
- Full exchange sync (8-step orphan/TP recovery)
- Ensure grid coverage
- Detect and handle exchange maintenance
- Sync positions from exchange on startup
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from loguru import logger as log

try:
    from bot.utils.human_log import human_log
except ImportError:
    human_log = None


class ExchangeSync:
    """Exchange state synchronization and reconciliation."""

    def __init__(
        self,
        api_client,
        position_actor,
        order_actor,
        event_store,
        grid_calc,
        mode: str,
        symbol: str,
        product_id: int,
        grid_step: float,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        should_log_fn: Callable,
    ):
        # ... store all params ...
        
        # Runtime callbacks (set by orchestrator)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._process_fill_callback: Optional[Callable] = None
        self._place_grid_order_callback: Optional[Callable] = None
        
    def set_runtime_refs(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/exchange_sync.py
git commit -m "P3.1: Create ExchangeSync skeleton"
```

---

### P3.2 — Move `_detect_exchange_state` + `_handle_exchange_maintenance` (15 min)

**What:** 2 methods (~108 lines total):
- `_detect_exchange_state` (lines 2480-2520) → `detect_exchange_state`
- `_handle_exchange_maintenance` (lines 2522-2588) → `handle_exchange_maintenance`

**Dependencies:** `self.api_client`, `self._get_running()`, `asyncio.sleep` — all available.

**Verify + Commit:**
```bash
git commit -m "P3.2: Move detect_exchange_state + handle_exchange_maintenance"
```

---

### P3.3 — Move `_exchange_maintenance_monitor` (10 min)

**What:** `_exchange_maintenance_monitor` (lines 4200-4234, ~34 lines) → `exchange_maintenance_monitor`

**Calls:** `self.detect_exchange_state()` + `self.handle_exchange_maintenance()` — both already moved ✅

**Verify + Commit:**
```bash
git commit -m "P3.3: Move _exchange_maintenance_monitor"
```

---

### P3.4 — Move `_sync_positions_from_exchange` (10 min)

**What:** `_sync_positions_from_exchange` (lines 5525-5610, ~85 lines) → `sync_positions_from_exchange`

**Dependencies:** `self.api_client.get_positions()`, `self.position_actor.ask("ADD_POSITION", ...)` — available.

**Verify + Commit:**
```bash
git commit -m "P3.4: Move _sync_positions_from_exchange"
```

---

### P3.5 — Move `_reconcile_orphaned_orders` (20 min)

**What:** `_reconcile_orphaned_orders` (lines 1214-1385, ~170 lines) → `reconcile_orphaned_orders`

**This is the BIGGEST method in Phase 3.** Take extra care with attribute translations.

**Dependencies:** `self.api_client`, `self.position_actor`, `self.order_actor`, `self.grid_calc`, `self.mode`, `self.product_id`, `self.lot_size`, `self.tp_offset` — all available.

**Verify + Commit:**
```bash
git commit -m "P3.5: Move _reconcile_orphaned_orders (170 lines)"
```

---

### P3.6 — Move `_cleanup_misaligned_orders` (10 min)

**What:** `_cleanup_misaligned_orders` (lines 1387-1430, ~43 lines) → `cleanup_misaligned_orders`

**Verify + Commit:**
```bash
git commit -m "P3.6: Move _cleanup_misaligned_orders"
```

---

### P3.7 — Move `_reconcile_fills_after_reconnect` + `_ensure_grid_coverage` (15 min)

**What:** 2 methods (~149 lines):
- `_reconcile_fills_after_reconnect` (lines 1432-1525) → `reconcile_fills_after_reconnect`
- `_ensure_grid_coverage` (lines 2782-2838) → `ensure_grid_coverage`

**Key dependency:** `_reconcile_fills_after_reconnect` calls `self._process_fill()` — use callback `self._process_fill_callback()`.
**Key dependency:** `_ensure_grid_coverage` calls `self._place_grid_order()` — use callback `self._place_grid_order_callback()`.

Set these callbacks in orchestrator's `start()`.

**Verify + Commit:**
```bash
git commit -m "P3.7: Move reconcile_fills_after_reconnect + ensure_grid_coverage"
```

---

### P3.8 — Move `_full_exchange_sync` + Cleanup (15 min)

**What:**
1. Copy `_full_exchange_sync` (lines 2590-2780, ~190 lines) → `full_exchange_sync`
2. Delete all commented-out Phase 3 methods from `async_gridbot.py`

**Internal calls:** `_full_exchange_sync` calls `_ensure_grid_coverage` — already moved ✅. Update to `self.ensure_grid_coverage()`.

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/exchange_sync.py
git commit -m "P3.8: Move _full_exchange_sync + cleanup (~600 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 3 (10 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc
# Look for:
# ✅ "🔄 Reconciling orphaned orders" messages
# ✅ "🔄 Syncing positions from exchange" messages
# ✅ No tracebacks
pm2 stop gridbot-btc
```

### ✅ Phase 3 Completion Notes (Mar 2, 2026)

**Commits:** dcc3858cb → cf91d8976 (8 commits)

| Step | Method(s) Moved | Lines |
|------|----------------|-------|
| P3.1 | ExchangeSync skeleton | 68 |
| P3.2 | `detect_exchange_state` + `handle_exchange_maintenance` | ~80 |
| P3.3 | `exchange_maintenance_monitor` | ~40 |
| P3.4 | `sync_positions_from_exchange` | ~60 |
| P3.5 | `reconcile_orphaned_orders` | 155 |
| P3.6 | `cleanup_misaligned_orders` | 46 |
| P3.7 | `reconcile_fills_after_reconnect` + `ensure_grid_coverage` | 149 |
| P3.8 | `full_exchange_sync` + wire `set_runtime_refs` | 190 |

**Final sizes:** `exchange_sync.py` = 822 lines, `async_gridbot.py` = 4,106 lines

**Runtime refs wired:** `_get_running`, `_get_current_price`, `_fetch_current_price_callback`, `_process_fill_callback`

**Attribute translations:**
- `self.grid_calc.step` → `self.grid_step` (constructor param)
- `self.current_price` → `self._get_current_price()` (runtime ref)
- `self._fetch_current_price()` → `self._fetch_current_price_callback()` (runtime ref)
- `self._process_fill()` → `self._process_fill_callback()` (runtime ref)
- `self.exchange_sync.ensure_grid_coverage()` → `self.ensure_grid_coverage()` (internal call within ExchangeSync)

**Bot test:** start → stop → start — zero errors, zero tracebacks. ✅ **PASSED**

**Bugs found:** 0

---

## Phase 4: Extract `ws_lifecycle.py` (~500 lines, MEDIUM risk) — ✅ DONE

### Why Fourth
- WebSocket lifecycle is well-bounded
- REST fallback is a clear alternative data path
- Medium risk: ticker updates trigger entry order checks

---

### P4.1 — Create WSLifecycle Skeleton (10 min)

Create `bot/strategy/modules/ws_lifecycle.py`:

```python
"""
WebSocket Lifecycle & REST Fallback — extracted from async_gridbot.py Phase 4

Responsibilities:
- WebSocket handler registration and channel subscription
- WebSocket message loop consumer
- Ticker update handler (price tracking)
- Position update handler (liquidation detection)
- REST fallback activation/deactivation
- REST price polling and order status checking
- WebSocket reconnection
- Price fetching (both WS and REST)
"""

import asyncio
import time
from typing import Dict, Optional, Callable, Any
from loguru import logger as log

try:
    from bot.utils.human_log import human_log
except ImportError:
    human_log = None


class WSLifecycle:
    """WebSocket connection management and REST fallback."""

    def __init__(
        self,
        api_client,
        position_actor,
        price_monitor,
        mode: str,
        symbol: str,
        product_id: int,
        max_positions: int,
    ):
        # ... store params ...
        
        # WS state
        self.current_price: Optional[float] = None
        self._last_price_update: float = 0
        self._rest_fallback_active: bool = False
        self._rest_fallback_task = None
        self._start_time: float = time.time()
        
        # Callbacks
        self._on_ticker_callback: Optional[Callable] = None   # → grid_engine.check_and_place_entry_order
        self._on_order_update_callback: Optional[Callable] = None  # → fill_processor.handle_order_update
        self._process_fill_callback: Optional[Callable] = None     # → fill_processor.process_fill
        
    def set_callbacks(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/ws_lifecycle.py
git commit -m "P4.1: Create WSLifecycle skeleton"
```

---

### P4.2 — Move `get_current_price` + `_fetch_current_price` (10 min)

**What:** 2 small methods (~34 lines total)

**Verify + Commit:**
```bash
git commit -m "P4.2: Move get_current_price + _fetch_current_price to WSLifecycle"
```

---

### P4.3 — Move WS setup methods (10 min)

**What:** 3 small methods (~38 lines total):
- `_register_ws_handlers` → `register_handlers`
- `_subscribe_channels` → `subscribe_channels`
- `_ws_message_loop` → `message_loop`

**Verify + Commit:**
```bash
git commit -m "P4.3: Move WS setup methods to WSLifecycle"
```

---

### P4.4 — Move `_handle_ticker_update` + `_handle_position_update` (15 min)

**What:** 2 methods (~178 lines total)

**Key dependency:** `_handle_ticker_update` calls `self._check_and_place_entry_order()` — use callback `self._on_ticker_callback()`.

**Key dependency:** `_handle_position_update` calls `self.emergency_stop()` — use callback `self._emergency_stop_callback()`.

**Special note:** These methods update `self.current_price` and `self._last_price_update`. Since these values are needed by the orchestrator and other modules, the WSLifecycle must own them and the orchestrator must reference them:
```python
# In orchestrator:
@property
def current_price(self):
    return self.ws_lifecycle.current_price
```

**Verify + Commit:**
```bash
git commit -m "P4.4: Move _handle_ticker_update + _handle_position_update"
```

---

### P4.5 — Move `_reconnect_websocket` (5 min)

**What:** `_reconnect_websocket` (~16 lines) → `reconnect`

**Verify + Commit:**
```bash
git commit -m "P4.5: Move _reconnect_websocket to WSLifecycle"
```

---

### P4.6 — Move `_rest_fallback_monitor_loop` (10 min)

**What:** `_rest_fallback_monitor_loop` (~70 lines) → `rest_fallback_monitor_loop`

**Calls:** `self._activate_rest_fallback()` + `self._deactivate_rest_fallback()` + `self._reconnect_websocket()` — moving in P4.7 and already moved in P4.5.

**Strategy:** Add stubs for `_activate_rest_fallback` and `_deactivate_rest_fallback` that will be replaced in P4.7.

**Verify + Commit:**
```bash
git commit -m "P4.6: Move _rest_fallback_monitor_loop to WSLifecycle"
```

---

### P4.7 — Move `_activate_rest_fallback` + `_deactivate_rest_fallback` (10 min)

**What:** 2 methods (~48 lines total)

**Replace stubs** from P4.6 with real implementations.

**Verify + Commit:**
```bash
git commit -m "P4.7: Move activate/deactivate REST fallback to WSLifecycle"
```

---

### P4.8 — Move REST Polling Methods + Cleanup (20 min)

**What:** 4 methods (~100 lines total):
- `_rest_polling_loop` → `rest_polling_loop`
- `_poll_price_via_rest` → `poll_price_via_rest`
- `_poll_pending_orders_via_rest` → `poll_pending_orders_via_rest`
- `_check_order_status_rest` → `check_order_status_rest`

Then: Delete all commented-out Phase 4 methods from `async_gridbot.py`.

**Key dependency:** `_check_order_status_rest` calls `self._process_fill()` — use callback `self._process_fill_callback()`.

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/ws_lifecycle.py
git commit -m "P4.8: Move REST polling methods + cleanup (~500 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 4 (10 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc
# Look for:
# ✅ "💚 WebSocket ticker" price updates
# ✅ Price updates flowing in heartbeat
# ✅ "🔄 [REST FALLBACK MONITOR] Loop started"
# ✅ No tracebacks
pm2 stop gridbot-btc
```

### ✅ Phase 4 Completion Notes

**Completed:** Mar 2, 2026
**Commits:** 856f049ce → e8a439abb (8 extraction commits + 2 bugfix commits)
**Result:** `ws_lifecycle.py` = 576 lines, `async_gridbot.py` ≈ 3,669 lines (down from ~4,200 pre-P4)
**Methods extracted:** 16 (get_current_price, fetch_current_price, register_handlers, subscribe_channels, message_loop, reconnect_websocket, rest_fallback_monitor_loop, _handle_ticker_update, _handle_position_update, _activate_rest_fallback, _deactivate_rest_fallback, _rest_polling_loop, _poll_price_via_rest, _poll_pending_orders_via_rest, _check_order_status_rest, set_runtime_refs)
**Property proxies:** 4 (current_price, _last_price, _last_price_update, _rest_fallback_active)
**Runtime callbacks:** 6 (wired via set_runtime_refs before WS connect)
**Bugs found:** 2 (see bug reports above)

---

## Phase 5: Extract `fill_processor.py` (~700 lines, HIGH risk)

### ⚠️ THIS IS THE MOST CRITICAL PHASE

Fill processing is the heart of the trading bot. Get this wrong and:
- Fills are missed → positions without TP → potential loss
- Fills are double-processed → duplicate positions → wrong exposure
- Saga creation fails → no TP placed → potential loss

**RULE: Do NOT delete original methods from async_gridbot.py until the FULL BOT TEST passes.**

---

### P5.1 — Create FillProcessor Skeleton (15 min)

Create `bot/strategy/modules/fill_processor.py`:

```python
"""
Fill Processor — extracted from async_gridbot.py Phase 5

Responsibilities:
- Fill deduplication (fill_id + order_id based)
- Saga dispatch (4 modes: LONG buy/sell, SHORT sell/buy)
- Saga completion tracking (metrics + missed order detection)
- FillMonitor integration (missed fill callback + order tracking)
- Post-order verification (Layer 2 safety)
- WebSocket order update handling (fill detection via orders channel)
- Next grid level calculation

NOT Responsible For:
- Order placement (→ GridEngine)
- Price tracking (→ WSLifecycle)
- Guardian signals (→ GuardianHandler)
- Exchange reconciliation (→ ExchangeSync)
"""

import asyncio
import time
from typing import Dict, List, Optional, Set, Callable, Any
from loguru import logger as log

try:
    from bot.utils.human_log import human_log
except ImportError:
    human_log = None

# Saga imports
from bot.strategy.sagas.saga_coordinator import (
    create_buy_fill_saga,
    create_sell_fill_saga,
    create_tp_buy_fill_saga,
    create_emergency_close_all_saga,
)


class FillProcessor:
    """Central fill processing, deduplication, and saga dispatch."""

    def __init__(
        self,
        position_actor,
        order_actor,
        saga_orchestrator,
        grid_calc,
        event_store,
        fill_monitor,
        pre_order_logger,
        anomaly_detector,
        mode: str,
        product_id: int,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        symbol: str,
    ):
        # ... store all params ...
        
        # Fill dedup state
        self._seen_fill_ids: Set[str] = set()
        self._fill_id_timestamps: Dict[str, float] = {}
        self._last_fill_id_cleanup: float = time.time()
        self._seen_order_fills: Set[str] = set()
        
        # Metrics
        self._fills_processed: int = 0
        self._sagas_completed: int = 0
        self._sagas_failed: int = 0
        
        # Callbacks
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._get_initial_order_placed: Callable = lambda: False
        self._check_and_place_entry_callback: Optional[Callable] = None
        self._track_order_in_fill_monitor_callback: Optional[Callable] = None  # temporary
        
    def set_runtime_refs(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/fill_processor.py
git commit -m "P5.1: Create FillProcessor skeleton with dedup state + metrics"
```

---

### P5.2 — Move Fill Dedup Helpers (10 min)

**What:** 6 small methods (~27 lines total):
- `_is_fill_seen` → `is_fill_seen`
- `_mark_fill_seen` → `mark_fill_seen`
- `_is_order_fill_seen` → `is_order_fill_seen`
- `_mark_order_fill_seen` → `mark_order_fill_seen`
- `_cleanup_old_fill_ids` → `cleanup_old_fill_ids`

**Safe:** These are pure state helpers — no external calls.

**In async_gridbot.py:** The place_recovery_order method (line ~5470) calls `self._mark_fill_seen()` and `self._mark_order_fill_seen()`. Update these to call `self.fill_processor.mark_fill_seen()` and `self.fill_processor.mark_order_fill_seen()`.

**Verify + Commit:**
```bash
git commit -m "P5.2: Move fill dedup helpers (6 methods) to FillProcessor"
```

---

### P5.3 — Move `_calculate_next_grid_level` (10 min)

**What:** `_calculate_next_grid_level` (~26 lines) → `calculate_next_grid_level`

**Dependencies:** `self.grid_calc.lower`, `self.grid_calc.upper`, `self.grid_calc.step`, `self._recovered_grids`

**Note:** `_recovered_grids` is used in the orchestrator's `place_recovery_order`. Since this method uses it, either:
- Pass `_recovered_grids` as a shared reference to FillProcessor, OR
- Keep it on orchestrator and pass it via constructor (preferred — it's a Set, so pass by reference)

**Verify + Commit:**
```bash
git commit -m "P5.3: Move _calculate_next_grid_level to FillProcessor"
```

---

### P5.4 — Move `_track_saga_completion` (15 min)

**What:** `_track_saga_completion` (~65 lines) → `track_saga_completion`

**Dependencies:**
- `self._fills_processed` ✅ (owned by FillProcessor)
- `self._sagas_completed` / `self._sagas_failed` ✅ (owned by FillProcessor)
- `self.fill_monitor.mark_filled(...)` ✅ (passed in constructor)
- `self._verify_order_after_placement(...)` — moves in P5.6. For now, use callback.

**Verify + Commit:**
```bash
git commit -m "P5.4: Move _track_saga_completion to FillProcessor"
```

---

### P5.5 — Move `_process_fill` — THE CRITICAL METHOD (25 min)

**What:** `_process_fill` (~230 lines) → `process_fill`

**THIS IS THE SINGLE MOST IMPORTANT METHOD IN THE ENTIRE BOT.** Take maximum care.

**Step-by-step:**
1. Copy the EXACT method body to FillProcessor
2. Replace `self` references per the translation table
3. **DO NOT** change any logic, any log message, any emoji, any conditional
4. In async_gridbot.py, replace ALL calls to `self._process_fill(data)` with `self.fill_processor.process_fill(data)`
5. Keep the original method commented out (do NOT delete yet)

**Calls made by `_process_fill`:**
- `self._is_fill_seen()` ✅ (moved in P5.2)
- `self._mark_fill_seen()` ✅ (moved in P5.2)
- `self._is_order_fill_seen()` ✅ (moved in P5.2)
- `self._mark_order_fill_seen()` ✅ (moved in P5.2)
- `self._cleanup_old_fill_ids()` ✅ (moved in P5.2)
- `self._track_saga_completion()` ✅ (moved in P5.4)
- Saga creation functions ✅ (imported at top of fill_processor.py)
- `self.position_actor`, `self.order_actor`, `self.saga_orchestrator` ✅ (passed in constructor)

**Who calls `_process_fill`:**
- `_handle_order_update` (WebSocket orders channel) — moves in P5.8
- `_process_missed_fill` (FillMonitor callback) — moves in P5.7
- `_check_order_status_rest` (REST fallback) — already moved to WSLifecycle (P4.8), uses callback
- `_reconcile_fills_after_reconnect` — already moved to ExchangeSync (P3.7), uses callback
- `place_recovery_order` — stays in orchestrator, update to `self.fill_processor.process_fill()`

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/fill_processor.py
git commit -m "P5.5: Move _process_fill (THE critical method) to FillProcessor"
```

---

### P5.6 — Move `_track_order_in_fill_monitor` + `_verify_order_after_placement` (15 min)

**What:** 2 methods (~177 lines):
- `_track_order_in_fill_monitor` (~23 lines) → `track_order_in_fill_monitor`
- `_verify_order_after_placement` (~154 lines) → `verify_order_after_placement`

**Remove the callback** set in P5.4 and replace with direct call.

**Verify + Commit:**
```bash
git commit -m "P5.6: Move fill monitor integration methods to FillProcessor"
```

---

### P5.7 — Move `_process_missed_fill` (FillMonitor callback version) (10 min)

**What:** `_process_missed_fill` (lines 2167-2230, the FillMonitor callback) → `process_missed_fill`

**Dependencies:** Calls `self.process_fill()` — already moved ✅

**Verify + Commit:**
```bash
git commit -m "P5.7: Move _process_missed_fill (FillMonitor callback) to FillProcessor"
```

---

### P5.8 — Move `_handle_order_update` + `_handle_user_trades` + Cleanup (20 min)

**What:**
1. Copy `_handle_order_update` (~120 lines) → `handle_order_update`
2. Copy `_handle_user_trades` (disabled stub, ~18 lines) → `handle_user_trades`
3. Delete all commented-out Phase 5 methods from `async_gridbot.py`
4. Update WSLifecycle's order update callback to point to `fill_processor.handle_order_update`
5. Update ExchangeSync's fill callback to point to `fill_processor.process_fill`

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/fill_processor.py
git commit -m "P5.8: Move _handle_order_update + cleanup (~700 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 5 — EXTENDED (20 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc

# Wait 2+ minutes and check:
pm2 logs gridbot-btc --lines 100

# CRITICAL checks:
# ✅ "🔔 Processing fill" appears when a fill occurs (if market moves)
# ✅ No "⚠️  Duplicate fill" unless there IS a duplicate
# ✅ Saga created successfully (look for "✅ Created saga")
# ✅ TP order placed after entry fill
# ✅ FillMonitor shows in heartbeat output
# ✅ No tracebacks

pm2 stop gridbot-btc
```

**If ANY fill-related issue:** `git revert HEAD~8..HEAD` reverts all Phase 5 micro-phases.

---

## Phase 6: Extract `grid_engine.py` (~800 lines, HIGH risk)

### ⚠️ SECOND MOST CRITICAL PHASE

Grid engine owns order placement and the placement lock. If this breaks:
- Orders placed at wrong prices
- Duplicate orders placed
- Safety checks bypassed
- Initial order fails

---

### P6.1 — Create GridEngine Skeleton (15 min)

Create `bot/strategy/modules/grid_engine.py`:

```python
"""
Grid Engine — extracted from async_gridbot.py Phase 6

Responsibilities:
- Place initial startup order (with exchange sync)
- Place grid orders (core grid stepping)
- Check and place entry orders (ticker-triggered)
- Seed missed grid levels
- Comprehensive safety check (pre-order gatekeeper)
- Cooldown management
- Grid status formatting and logging

Owns:
- asyncio.Lock for order placement (critical section)
- Last order time tracking
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from loguru import logger as log

try:
    from bot.utils.human_log import human_log
except ImportError:
    human_log = None


class GridEngine:
    """Grid order placement, safety checks, and cooldown management."""

    def __init__(
        self,
        api_client,
        position_actor,
        order_actor,
        grid_calc,
        event_store,
        state_coordinator,
        price_monitor,
        pre_order_logger,
        anomaly_detector,
        fill_monitor,
        mode: str,
        product_id: int,
        symbol: str,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        cooldown_seconds: float,
    ):
        # ... store all params ...
        
        # Order placement lock (CRITICAL — prevents concurrent order placement)
        self._order_placement_lock = asyncio.Lock()
        
        # Cooldown state
        self._last_order_time: float = 0
        self._last_accepted_order_price: Optional[float] = None
        
        # Metrics
        self._initial_order_placed: bool = False
        self._entry_halt_count: int = 0
        
        # Callbacks
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._track_order_in_fill_monitor: Optional[Callable] = None
        self._full_exchange_sync: Optional[Callable] = None
        self._read_guardian_signal: Optional[Callable] = None
        
    def set_runtime_refs(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/grid_engine.py
git commit -m "P6.1: Create GridEngine skeleton with Lock + cooldown state"
```

---

### P6.2 — Move `_is_cooldown_ready` + `_should_recalculate_grid_level` (10 min)

**What:** 2 small methods (~28 lines total)

**Verify + Commit:**
```bash
git commit -m "P6.2: Move cooldown + recalculate helpers to GridEngine"
```

---

### P6.3 — Move `_comprehensive_safety_check` (15 min)

**What:** `_comprehensive_safety_check` (~78 lines) → `comprehensive_safety_check`

**Dependencies:**
- `self._read_guardian_signal()` —Callback to GuardianHandler
- `self.state_coordinator.is_safe_to_trade()` ✅
- `self.price_monitor` ✅
- `self.current_price` → `self._get_current_price()`

**Verify + Commit:**
```bash
git commit -m "P6.3: Move _comprehensive_safety_check to GridEngine"
```

---

### P6.4 — Move Formatting Helpers (10 min)

**What:** 2 read-only methods (~126 lines):
- `_format_pending_order_info` → `format_pending_order_info`
- `_log_detailed_grid_status` → `log_detailed_grid_status`

**Safe:** Pure logging, no side effects.

**Verify + Commit:**
```bash
git commit -m "P6.4: Move formatting helpers to GridEngine"
```

---

### P6.5 — Move `_place_grid_order` (15 min)

**What:** `_place_grid_order` (~75 lines) → `place_grid_order`

**Dependencies:**
- `self.order_actor.ask("PLACE_ORDER", ...)` ✅
- `self._track_order_in_fill_monitor(...)` — callback to FillProcessor
- `self._order_placement_lock` ✅ (owned by GridEngine)

**Verify + Commit:**
```bash
git commit -m "P6.5: Move _place_grid_order to GridEngine"
```

---

### P6.6 — Move `_check_and_place_entry_order` (15 min)

**What:** `_check_and_place_entry_order` (~78 lines) → `check_and_place_entry_order`

**This is the hot-path method called on every ticker update.** Take extra care.

**Dependencies:**
- `self.comprehensive_safety_check()` — already moved in P6.3 ✅
- `self.place_grid_order()` — already moved in P6.5 ✅
- `self._last_accepted_order_price` ✅ (owned by GridEngine)
- Guardian state check → callback

**Verify + Commit:**
```bash
git commit -m "P6.6: Move _check_and_place_entry_order to GridEngine"
```

---

### P6.7 — Move `seed_missed_grid_levels` (10 min)

**What:** `seed_missed_grid_levels` (~73 lines) → `seed_missed_grid_levels`

**Verify + Commit:**
```bash
git commit -m "P6.7: Move seed_missed_grid_levels to GridEngine"
```

---

### P6.8 — Move `_place_initial_order` + Cleanup (30 min)

**What:**
1. Copy `_place_initial_order` (~280 lines) → `place_initial_order`
2. Delete all commented-out Phase 6 methods from `async_gridbot.py`
3. Wire callbacks in orchestrator

**THIS IS THE LARGEST SINGLE METHOD EXTRACTION.** 280 lines including:
- Exchange order querying
- Safety checks
- LONG/SHORT mode branching
- TP order placement
- Position registration

**Dependencies:** `self.api_client`, `self.position_actor`, `self.order_actor`, `self.grid_calc`, `self.mode`, `self.product_id`, `self.lot_size`, `self.tp_offset` — all available in GridEngine.

**Also calls:**
- `self._full_exchange_sync()` → callback to ExchangeSync
- `self._comprehensive_safety_check()` → already moved ✅
- `self._track_order_in_fill_monitor()` → callback to FillProcessor

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/grid_engine.py
git commit -m "P6.8: Move _place_initial_order (280 lines) + cleanup (~800 lines extracted)"
```

### 🧪 FULL BOT TEST after Phase 6 — EXTENDED (20 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc

# Wait 2+ minutes. CRITICAL checks:
# ✅ Initial order placed (or existing order adopted)
# ✅ No duplicate orders on exchange
# ✅ Safety check passes ("✅ Safety check passed")
# ✅ Grid entry at correct price level
# ✅ TP order placed at correct offset
# ✅ Cooldown works (no rapid-fire orders)
# ✅ No tracebacks

pm2 stop gridbot-btc
```

**If ANY order-related issue:** `git revert HEAD~8..HEAD` immediately.

---

## Phase 7: Extract `recovery_actions.py` (~500 lines, MEDIUM risk)

---

### P7.1 — Create RecoveryActions Skeleton (10 min)

Create `bot/strategy/modules/recovery_actions.py`:

```python
"""
Recovery Actions — extracted from async_gridbot.py Phase 7

Responsibilities:
- Reconciliation action queue processing (action_queue.json)
- Emergency TP placement for unprotected positions
- Missed fill processing (reconciliation version)
- Safety gatekeeper (periodic safety checks)
- Unhedged position detection
- Fill polling fallback (60s REST polling backup)
- TP retry queue processing
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from loguru import logger as log


class RecoveryActions:
    """Recovery mechanisms, safety loops, and reconciliation actions."""

    def __init__(
        self,
        api_client,
        position_actor,
        order_actor,
        event_store,
        grid_calc,
        fill_monitor,
        mode: str,
        product_id: int,
        symbol: str,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
    ):
        # ... store params ...
        
        # TP retry queue
        self._tp_retry_queue: asyncio.Queue = asyncio.Queue()
        
        # Callbacks
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._process_fill_callback: Optional[Callable] = None
        self._comprehensive_safety_check: Optional[Callable] = None
        
    def set_runtime_refs(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/recovery_actions.py
git commit -m "P7.1: Create RecoveryActions skeleton"
```

---

### P7.2 — Move `_safety_gatekeeper_loop` + `_check_for_unhedged_positions` (10 min)

**Verify + Commit:**
```bash
git commit -m "P7.2: Move safety_gatekeeper + unhedged_positions to RecoveryActions"
```

---

### P7.3 — Move `_fill_polling_fallback_loop` (10 min)

**Verify + Commit:**
```bash
git commit -m "P7.3: Move _fill_polling_fallback_loop to RecoveryActions"
```

---

### P7.4 — Move `_process_tp_retry_queue` (15 min)

**What:** `_process_tp_retry_queue` (~110 lines) → `process_tp_retry_queue`

**Note:** HealthMonitor has a callback for this. Update it to point to `recovery_actions.process_tp_retry_queue`.

**Verify + Commit:**
```bash
git commit -m "P7.4: Move _process_tp_retry_queue to RecoveryActions"
```

---

### P7.5 — Move Reconciliation Action Methods (10 min)

**What:** 2 methods (~110 lines):
- `_reconciliation_action_processor` → `reconciliation_action_processor`
- `_execute_reconciliation_action` → `execute_reconciliation_action`

**Verify + Commit:**
```bash
git commit -m "P7.5: Move reconciliation action processor to RecoveryActions"
```

---

### P7.6 — Move Emergency + Missed Fill Methods (10 min)

**What:** 2 methods (~70 lines):
- `_place_emergency_tp_for_position` → `place_emergency_tp`
- `_process_missed_fill` (reconciliation version, lines 4777-4812) → `process_missed_fill_recon`

**Verify + Commit:**
```bash
git commit -m "P7.6: Move emergency TP + missed fill recon to RecoveryActions"
```

---

### P7.7 — Cleanup Orchestrator (10 min)

**What:**
1. Delete all commented-out Phase 7 methods from `async_gridbot.py`
2. Verify all callback wiring is complete
3. Run syntax + import checks

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh bot/strategy/modules/recovery_actions.py
git commit -m "P7.7: Cleanup orchestrator after RecoveryActions extraction (~500 lines)"
```

### 🧪 FULL BOT TEST after Phase 7 (10 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc
# ✅ "📋 Reconciliation action processor started"
# ✅ "🔒 Running periodic safety check"
# ✅ "🔄 Fill polling fallback started"
# ✅ No tracebacks
pm2 stop gridbot-btc
```

---

## Phase 8: Slim Down Orchestrator (~45 min, LOW risk)

Now `async_gridbot.py` should be ~1500 lines. Goal: get it under 600.

---

### P8.1 — Slim `__init__` (15 min)

**What:** The `__init__` method is ~537 lines. Most of the state initialization code has been moved to the 7 extracted modules. Remove:
- Guardian state init (→ GuardianHandler owns it)
- Fill dedup state init (→ FillProcessor owns it)
- WS state init (→ WSLifecycle owns it)
- Health/watchdog state init (→ HealthMonitor owns it)
- Recovery action state init (→ RecoveryActions owns it)

**Keep in __init__:**
- Config loading (4 paths: v6.0/v5.0/v4.0/manual)
- API client creation
- Actor creation (position_actor, order_actor, saga_orchestrator)
- Grid calculator creation
- Event store creation
- FillMonitor creation
- Each module construction (7 lines, one per module)
- `self._running = False`
- `self._start_time = 0`

**Verify + Commit:**
```bash
git commit -m "P8.1: Slim __init__ — remove state moved to modules"
```

---

### P8.2 — Slim `start()` (15 min)

**What:** The `start()` method is ~222 lines. Simplify task creation to:
```python
tasks = [
    # Guardian
    asyncio.create_task(self.guardian.health_monitor_loop(), name="GuardianMonitor"),
    # Health
    asyncio.create_task(self.health_monitor.heartbeat_loop(), name="Heartbeat"),
    asyncio.create_task(self.health_monitor.monitoring_loop(), name="Monitoring"),
    asyncio.create_task(self.health_monitor.health_check_loop(), name="HealthCheck"),
    asyncio.create_task(self.health_monitor.watchdog_loop(), name="Watchdog"),
    # Exchange
    asyncio.create_task(self.exchange_sync.exchange_maintenance_monitor(), name="ExchangeMonitor"),
    # WebSocket
    asyncio.create_task(self.ws_lifecycle.message_loop(), name="WSMessages"),
    asyncio.create_task(self.ws_lifecycle.rest_fallback_monitor_loop(), name="RestFallback"),
    # Recovery
    asyncio.create_task(self.recovery_actions.reconciliation_action_processor(), name="ReconProcessor"),
    asyncio.create_task(self.recovery_actions.safety_gatekeeper_loop(), name="SafetyGatekeeper"),
    asyncio.create_task(self.recovery_actions.fill_polling_fallback_loop(), name="FillPolling"),
]
```

**Verify + Commit:**
```bash
git commit -m "P8.2: Slim start() — clean task creation via modules"
```

---

### P8.3 — Slim `stop()` + Final Cleanup (15 min)

**What:**
1. Remove any dead imports
2. Remove any unused `self.*` attributes
3. Clean up `stop()` to just cancel tasks, stop actors, disconnect WS
4. Final import cleanup

**Verify + Commit:**
```bash
bash tests/refactoring_checklist.sh
git commit -m "P8.3: Final orchestrator cleanup — target: under 600 lines"
```

### 🧪 FULL BOT TEST after Phase 8 (10 min)

```bash
pm2 start ecosystem.config.js --only gridbot-btc
# Full check: startup, heartbeat, Guardian, fills, shutdown
pm2 stop gridbot-btc
```

---

## Phase 9: Final Verification & Merge

### P9.1 — Full Cold-Start Test (15 min)

```bash
# Count final orchestrator size
wc -l bot/strategy/async_gridbot.py
# Should be < 600 lines

# Count all new modules
wc -l bot/strategy/modules/guardian_handler.py
wc -l bot/strategy/modules/health_monitor.py
wc -l bot/strategy/modules/exchange_sync.py
wc -l bot/strategy/modules/ws_lifecycle.py
wc -l bot/strategy/modules/fill_processor.py
wc -l bot/strategy/modules/grid_engine.py
wc -l bot/strategy/modules/recovery_actions.py

# Total should be ~5200+ lines (same as original minus some dead code)

# Full test sequence:
# 1. Start bot from cold (no state)
pm2 start ecosystem.config.js --only gridbot-btc

# 2. Wait for initial order placement
# 3. Let 1+ fills process (if market moves)
# 4. Trigger Guardian STOP → verify entries cancelled
# 5. Trigger Guardian GO → verify grid resumes
# 6. Kill bot → verify clean shutdown, TP orders preserved
pm2 stop gridbot-btc

# 7. Restart bot → verify orphaned order reconciliation
pm2 start ecosystem.config.js --only gridbot-btc
pm2 stop gridbot-btc

# 8. Check WebUI endpoints
curl -s http://localhost:5555/api/health/detailed | python3 -m json.tool | head
curl -s http://localhost:5555/api/positions | python3 -m json.tool | head

# 9. Independent imports
python3 -c "from bot.strategy.modules.guardian_handler import GuardianHandler; print('OK')"
python3 -c "from bot.strategy.modules.health_monitor import HealthMonitor; print('OK')"
python3 -c "from bot.strategy.modules.exchange_sync import ExchangeSync; print('OK')"
python3 -c "from bot.strategy.modules.ws_lifecycle import WSLifecycle; print('OK')"
python3 -c "from bot.strategy.modules.fill_processor import FillProcessor; print('OK')"
python3 -c "from bot.strategy.modules.grid_engine import GridEngine; print('OK')"
python3 -c "from bot.strategy.modules.recovery_actions import RecoveryActions; print('OK')"
```

---

### P9.2 — Merge to SSR (15 min)

```bash
# Review what changed
git log --oneline refactor/split-gridbot ^SSR

# Merge
git checkout SSR
git merge refactor/split-gridbot --no-ff -m "Refactor: Split async_gridbot.py into 7 modules (42 micro-phases)"

# Push
git push origin SSR

# Cleanup
git branch -d refactor/split-gridbot
```

---

## Rollback Procedures

### Rollback a single micro-phase:
```bash
git revert HEAD
```

### Rollback an entire Macro Phase (e.g., all of Phase 5):
```bash
# Find the commit before Phase 5 started
git log --oneline | head -20
# Revert all Phase 5 commits (8 commits for Phase 5):
git revert HEAD~8..HEAD
```

### Nuclear rollback — start over:
```bash
git checkout SSR
git branch -D refactor/split-gridbot
# The backup file is still there:
cp bot/strategy/async_gridbot.py.pre_refactor_backup bot/strategy/async_gridbot.py
```

---

## Session Planning Guide

### If using Claude CLI (recommended for high-risk phases):

**Session 1 (Low Risk, ~2.5 hours):**
- P0 (setup)
- P1.1 → P1.8 (GuardianHandler)
- Full bot test
- P2.1 → P2.7 (HealthMonitor)
- Full bot test

**Session 2 (Medium Risk, ~3.5 hours):**
- P3.1 → P3.8 (ExchangeSync)
- Full bot test
- P4.1 → P4.8 (WSLifecycle)
- Full bot test

**Session 3 (HIGH Risk, ~2.5 hours, needs market access):**
- P5.1 → P5.8 (FillProcessor)
- Extended bot test with fill verification

**Session 4 (HIGH Risk, ~2.5 hours, needs market access):**
- P6.1 → P6.8 (GridEngine)
- Extended bot test with order placement verification

**Session 5 (Medium Risk, ~2 hours):**
- P7.1 → P7.7 (RecoveryActions)
- P8.1 → P8.3 (Slim orchestrator)
- Full bot tests

**Session 6 (Verification, ~30 min):**
- P9.1 (Full cold-start test)
- P9.2 (Merge to SSR)

---

## Cross-Reference: Module Dependencies

After all phases complete, the callback wiring in `start()` should look like:

```python
# ── Guardian callbacks ──
self.guardian.set_runtime_refs(
    get_running=lambda: self._running,
    get_current_price=lambda: self.ws_lifecycle.current_price,
    set_running=lambda v: setattr(self, '_running', v),
)

# ── Health Monitor callbacks ──
self.health_monitor.set_runtime_refs(
    _get_running=lambda: self._running,
    _get_current_price=lambda: self.ws_lifecycle.current_price,
    _get_start_time=lambda: self._start_time,
    _get_fills_processed=lambda: self.fill_processor._fills_processed,
    _get_sagas_completed=lambda: self.fill_processor._sagas_completed,
    _get_sagas_failed=lambda: self.fill_processor._sagas_failed,
    _get_last_price_update=lambda: self.ws_lifecycle._last_price_update,
    _get_initial_order_placed=lambda: self.grid_engine._initial_order_placed,
    _check_guardian_transitions_callback=self.guardian.check_transitions,
    _tp_retry_callback=self.recovery_actions.process_tp_retry_queue,
    _log_grid_status_callback=self.grid_engine.log_detailed_grid_status,
)

# ── Exchange Sync callbacks ──
self.exchange_sync.set_runtime_refs(
    _get_running=lambda: self._running,
    _get_current_price=lambda: self.ws_lifecycle.current_price,
    _process_fill_callback=self.fill_processor.process_fill,
    _place_grid_order_callback=self.grid_engine.place_grid_order,
)

# ── WS Lifecycle callbacks ──
self.ws_lifecycle.set_callbacks(
    _on_ticker_callback=self.grid_engine.check_and_place_entry_order,
    _on_order_update_callback=self.fill_processor.handle_order_update,
    _process_fill_callback=self.fill_processor.process_fill,
    _emergency_stop_callback=self.emergency_stop,
)

# ── Fill Processor callbacks ──
self.fill_processor.set_runtime_refs(
    _get_running=lambda: self._running,
    _get_current_price=lambda: self.ws_lifecycle.current_price,
    _get_initial_order_placed=lambda: self.grid_engine._initial_order_placed,
    _check_and_place_entry_callback=self.grid_engine.check_and_place_entry_order,
)

# ── Grid Engine callbacks ──
self.grid_engine.set_runtime_refs(
    _get_running=lambda: self._running,
    _get_current_price=lambda: self.ws_lifecycle.current_price,
    _track_order_in_fill_monitor=self.fill_processor.track_order_in_fill_monitor,
    _full_exchange_sync=self.exchange_sync.full_exchange_sync,
    _read_guardian_signal=self.guardian.read_signal,
)

# ── Recovery Actions callbacks ──
self.recovery_actions.set_runtime_refs(
    _get_running=lambda: self._running,
    _get_current_price=lambda: self.ws_lifecycle.current_price,
    _process_fill_callback=self.fill_processor.process_fill,
    _comprehensive_safety_check=self.grid_engine.comprehensive_safety_check,
)
```

---

## Per-Session Context Prompt

When starting a new CLI session for a specific phase, provide this context:

```
I am refactoring bot/strategy/async_gridbot.py (5,771 lines) into 7 modules.

CURRENT STATUS: [Phase X completed. Starting Phase Y.]

PLAN: See REFACTORING_MICRO_PHASES.md (this file)

RULES:
1. ZERO behavior change — pure structural move
2. Copy methods EXACTLY (same log messages, same emojis, same logic)
3. Replace self.attribute references per the translation table
4. Run syntax check after every micro-phase
5. Commit after every micro-phase
6. DO NOT delete original methods until full bot test passes
7. Use callbacks for cross-module calls (modules never import each other)

CURRENT MICRO-PHASE: [P.X.Y]
WHAT TO DO: [exact instructions from this document]
```

---

## Success Criteria

- [ ] `async_gridbot.py` under 600 lines
- [ ] 7 new module files in `bot/strategy/modules/`
- [ ] Every module independently importable
- [ ] Bot starts, runs heartbeat, processes fills, stops cleanly
- [ ] No duplicate fill processing
- [ ] Grid orders at correct prices
- [ ] Guardian transitions work
- [ ] WebUI endpoints return 200
- [ ] REST fallback activates when WebSocket is stale
- [ ] TP orders preserved on shutdown
- [ ] 42 individual git commits (one per micro-phase)
- [ ] Clean merge to SSR branch

---

## Estimated Total: ~14 hours across 6 sessions
