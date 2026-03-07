# Refactoring Plan — `async_gridbot.py` (5,771 Lines → ~500 Line Orchestrator)

**Date:** March 1, 2026  
**Target File:** `bot/strategy/async_gridbot.py`  
**Current Size:** 5,771 lines, 1 class (`AsyncGridBot`), ~80 methods  
**Goal:** Split into 7 focused modules + slim orchestrator, zero behavior change  
**Approach:** Phase-by-phase extraction with test verification after each phase  

---

## Why This File Must Be Refactored

| Problem | Impact |
|---------|--------|
| 5,771 lines in one file | IDE search takes seconds, git diffs are unreadable |
| ~80 methods in one class | Every method can access/mutate every `self.*` attribute — hidden coupling |
| 15 concurrent async tasks | Race conditions are hard to trace when all tasks live in one file |
| 3 different fill detection paths | WebSocket, Fill Monitor, REST polling — all inline, hard to compare |
| Mix of concerns | Guardian signal reading, price polling, grid math, Telegram alerts — all in one class |
| Any change risks everything | Touching heartbeat code can accidentally break fill processing |

---

## Current Method Inventory (Complete)

Every method in `AsyncGridBot`, grouped by concern. This is the **source of truth** for what moves where.

### Group 1: Constructor & Config (stays in orchestrator)
| Method | Lines | Notes |
|--------|-------|-------|
| `__init__` | 126–663 | 537 lines. 4 config paths (v4/v5/v6/manual). Stays but gets slimmed. |
| `_configure_logging()` | 75–120 | Module-level function, not a method. Stays at file top. |
| `main()` | 5695–5771 | Entry point. Stays at file bottom. |

### Group 2: Guardian Signal & Transition Handling → `guardian_handler.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_read_guardian_signal` | 710–805 | Read GO/STOP from EventStore |
| `_check_guardian_transition_and_retry` | 908–948 | Detect STOP→GO, call retry |
| `_retry_missed_grid_orders` | 951–1063 | Retry specific missed orders |
| `_fill_multi_step_missed_grids` | 1064–1199 | A3: Multi-step gap recovery |
| `_check_guardian_transitions` | 4236–4278 | GO→STOP / STOP→GO response |
| `_cancel_pending_entry_orders` | 4280–4332 | Cancel entries on STOP |
| `_resume_grid_trading` | 4334–4428 | Resume entries on GO |
| `_guardian_health_monitor_loop` | 4098–4130 | 15s health check loop |
| **Total** | | **~520 lines** |

**Instance attributes used:**
- `self._last_guardian_signal`, `self._guardian_transition_time`, `self._missed_grid_orders`
- `self.event_store`, `self.position_actor`, `self.order_actor`, `self.grid_calc`
- `self.mode`, `self.grid_step`, `self.max_positions`, `self.lot_size`
- `self.current_price`, `self._running`, `self.ref_price`

**Why safest first:** Zero order placement logic. Only reads a file/DB, manages a buffer of missed orders, and calls actor methods that are already extracted. Pure signal-handling concern.

### Group 3: Fill Processing & Saga Dispatch → `fill_processor.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_process_fill` | 1970–2098 | Central fill handler (dedup + saga creation) |
| `_track_saga_completion` | 2100–2165 | Track saga results, detect missed orders |
| `_process_missed_fill` (FillMonitor callback) | 2167–2230 | Process fills detected by FillMonitor |
| `_track_order_in_fill_monitor` | 2232–2255 | Register order with FillMonitor |
| `_verify_order_after_placement` | 2257–2410 | Post-order verification (Layer 2) |
| `_handle_order_update` | 2840–2960 | WebSocket `orders` channel handler |
| `_handle_user_trades` | 1947–1968 | Disabled handler (keep stub) |
| `_is_fill_seen` / `_mark_fill_seen` | 888–895 | Fill dedup helpers |
| `_is_order_fill_seen` / `_mark_order_fill_seen` | 897–905 | Order dedup helpers |
| `_cleanup_old_fill_ids` | 907–915 | Dedup cache cleanup |
| `_calculate_next_grid_level` | 5080–5106 | Used by fill processor for next-level calc |
| **Total** | | **~700 lines** |

**Instance attributes used:**
- `self._seen_fill_ids`, `self._fill_id_timestamps`, `self._last_fill_id_cleanup`
- `self.position_actor`, `self.order_actor`, `self.grid_calc`, `self.saga_orchestrator`
- `self.mode`, `self.product_id`, `self.lot_size`, `self.max_positions`
- `self.fill_monitor`, `self.pre_order_logger`, `self.anomaly_detector`
- `self._fills_processed`, `self._sagas_completed`, `self._sagas_failed`
- `self.current_price`, `self._initial_order_placed`

**Why high risk:** This is the core trading logic. Fill dedup, saga creation, and order-state mutation are critical. Must be tested very carefully.

### Group 4: Grid Entry & Order Placement → `grid_engine.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_place_initial_order` | 3074–3355 | Startup order placement (280 lines!) |
| `_check_and_place_entry_order` | 3434–3512 | Ticker-triggered entry check |
| `_place_grid_order` | 3357–3432 | Core grid order placement |
| `seed_missed_grid_levels` | 1527–1600 | Seed multiple grid levels |
| `_comprehensive_safety_check` | 808–886 | Pre-order safety gatekeeper |
| `_is_cooldown_ready` | 685–698 | Cooldown check |
| `_update_last_order_time` | 886–889 | Track last order |
| `_should_recalculate_grid_level` | 1200–1212 | Price-move threshold check |
| `_format_pending_order_info` | 3514–3540 | Format pending order string |
| `_log_detailed_grid_status` | 3542–3640 | Detailed grid status log |
| **Total** | | **~800 lines** |

**Instance attributes used:**
- `self.position_actor`, `self.order_actor`, `self.grid_calc`
- `self.mode`, `self.lot_size`, `self.max_positions`, `self.tp_offset`
- `self.current_price`, `self._initial_order_placed`
- `self._last_order_time`, `self.cooldown_seconds`, `self._last_accepted_order_price`
- `self.price_monitor`, `self.pre_order_logger`, `self.anomaly_detector`
- `self.state_coordinator`, `self._order_placement_lock`

**Why high risk:** Contains the order placement lock, safety checks, and initial order logic. The `_place_initial_order` alone is 280 lines with complex exchange query logic.

### Group 5: Health, Heartbeat & Monitoring → `health_monitor.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_heartbeat_loop` | 3663–3783 | 5s heartbeat + 15s detailed status |
| `_monitoring_loop` | 3784–3862 | 5s monitoring snapshot writer |
| `_health_check_loop` | 4152–4198 | 30s actor/saga/price health checks |
| `_watchdog_loop` | 4543–4598 | 10s event-loop freeze detection |
| `_update_external_heartbeat` | 3643–3662 | Write .heartbeat file |
| `_check_memory_usage` | 4132–4150 | Memory check + GC |
| `_check_websocket_health` | 4152–4196 | WebSocket health check |
| `_should_log` | 669–683 | Log rate limiter |
| **Total** | | **~400 lines** |

**Instance attributes used:**
- `self._running`, `self._start_time`, `self._last_heartbeat_time`
- `self.position_actor`, `self.order_actor`, `self.saga_orchestrator`
- `self.mode`, `self.symbol`, `self.max_positions`
- `self.current_price`, `self._last_price_update`
- `self.grid_calc`, `self.price_monitor`
- `self._fills_processed`, `self._sagas_completed`, `self._sagas_failed`
- `self._log_rate_limiter`, `self._watchdog_timeout`, `self._watchdog_check_interval`

**Why low risk:** Read-only observation loops. They don't place orders or mutate trading state. They read actor state and write JSON files.

### Group 6: WebSocket & REST Fallback → `ws_lifecycle.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_register_ws_handlers` | 1926–1938 | Register WS message handlers |
| `_subscribe_channels` | 1940–1943 | Subscribe to WS channels |
| `_ws_message_loop` | 1945–1955 | Main WS message consumer |
| `_handle_ticker_update` | 2963–3037 | Price update from ticker |
| `_handle_position_update` | 2962–3000 | Position update (liquidation detection) |
| `_rest_fallback_monitor_loop` | 4800–4870 | REST fallback activation |
| `_activate_rest_fallback` | 4872–4895 | Activate REST polling |
| `_deactivate_rest_fallback` | 4897–4920 | Deactivate REST polling |
| `_rest_polling_loop` | 4922–4950 | REST polling loop |
| `_poll_price_via_rest` | 4952–4980 | REST price polling |
| `_poll_pending_orders_via_rest` | 4982–5010 | REST order polling |
| `_check_order_status_rest` | 5012–5060 | Check order via REST |
| `_reconnect_websocket` | 5062–5078 | Force WS reconnect |
| `_fetch_current_price` | 3050–3072 | REST price fetch |
| `get_current_price` | 3038–3050 | Async price getter |
| **Total** | | **~500 lines** |

### Group 7: Exchange Sync & Reconciliation → `exchange_sync.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_reconcile_orphaned_orders` | 1214–1385 | Startup orphan reconciliation (170 lines) |
| `_cleanup_misaligned_orders` | 1387–1430 | Cancel misaligned grid orders |
| `_reconcile_fills_after_reconnect` | 1432–1525 | Post-reconnect fill reconciliation |
| `_full_exchange_sync` | 2590–2780 | Complete exchange sync (190 lines) |
| `_ensure_grid_coverage` | 2782–2838 | Verify grid buy order exists |
| `_detect_exchange_state` | 2480–2520 | Check exchange online/maintenance |
| `_handle_exchange_maintenance` | 2522–2588 | Wait and recover from maintenance |
| `_exchange_maintenance_monitor` | 4200–4234 | 60s exchange state monitor |
| `_sync_positions_from_exchange` | 5525–5610 | Startup position sync |
| **Total** | | **~600 lines** |

### Group 8: Reconciliation Actions, Recovery, Safety → `recovery_actions.py`
| Method | Lines | Description |
|--------|-------|-------------|
| `_reconciliation_action_processor` | 4600–4667 | Process action_queue.json |
| `_execute_reconciliation_action` | 4669–4740 | Execute single recon action |
| `_place_emergency_tp_for_position` | 4742–4775 | Emergency TP placement |
| `_process_missed_fill` (recon version) | 4777–4812 | Process missed fill from recon |
| `_safety_gatekeeper_loop` | 3940–3960 | 5-min periodic safety check |
| `_check_for_unhedged_positions` | 3962–4030 | Detect positions without TP |
| `_fill_polling_fallback_loop` | 3864–3938 | 60s fill polling backup |
| `_process_tp_retry_queue` | 4430–4540 | TP retry queue processor |
| **Total** | | **~500 lines** |

### Group 9: Startup, Shutdown, Signals, Notifications (stays in orchestrator)
| Method | Lines | Description |
|--------|-------|-------------|
| `start()` | 1606–1828 | Main startup sequence (222 lines) |
| `stop()` | 1830–1925 | Graceful shutdown |
| `emergency_stop()` | 5380–5405 | Emergency close all |
| `_setup_signal_handlers` | 5506–5525 | SIGINT/SIGTERM/SIGHUP |
| `_send_startup_notification` | 5110–5140 | Telegram startup alert |
| `_send_shutdown_notification` | 5340–5378 | Telegram shutdown alert |
| `_cancel_pending_orders_on_shutdown` | 5142–5300 | Cancel entries on stop |
| `_write_shutdown_signal` | 5302–5340 | Write recon shutdown signal |
| `_load_recovery_state` | 5407–5420 | Clean-slate (no-op now) |
| `place_recovery_order` | 5422–5520 | Recovery order placement |
| `get_open_orders` | 5512–5524 | Get orders for recovery |
| `_check_missed_grids` | 5612–5670 | Check missed grids |
| `_execute_recovery` | 5672–5710 | Execute recovery orders |
| `_run_trading_iteration` | 5712 | No-op placeholder |
| `_run_reconciliation_loop` | 5714–5726 | Simple recon loop |
| **Total** | | **~500 lines (stays)** |

---

## Target Architecture After Refactoring

```
bot/strategy/
├── async_gridbot.py              ← Slim orchestrator (~500 lines)
│   • __init__() — wire modules
│   • start() — startup sequence
│   • stop() — shutdown
│   • main() — entry point
│
├── modules/
│   ├── grid_calculator.py        ← Already exists ✅ (pure math, no changes)
│   ├── event_store.py            ← Already exists ✅
│   ├── mode_state_manager.py     ← Already exists ✅
│   ├── guardian_handler.py       ← NEW (Phase 1) ~520 lines
│   ├── health_monitor.py         ← NEW (Phase 2) ~400 lines
│   ├── exchange_sync.py          ← NEW (Phase 3) ~600 lines
│   ├── ws_lifecycle.py           ← NEW (Phase 4) ~500 lines
│   ├── fill_processor.py         ← NEW (Phase 5) ~700 lines
│   ├── grid_engine.py            ← NEW (Phase 6) ~800 lines
│   └── recovery_actions.py       ← NEW (Phase 7) ~500 lines
```

---

## Phase-by-Phase Extraction Plan

### ⚠️ CRITICAL RULES FOR EVERY PHASE

1. **ZERO behavior change** — pure structural move, not a refactor of logic
2. **One module per phase** — never extract two modules in the same session
3. **Copy-first, then redirect** — copy methods to new file, make orchestrator call new file, then delete old methods
4. **Run bot after each phase** — start it, wait for at least 1 heartbeat cycle + 1 fill (if market moves), then proceed
5. **Git commit after each phase** — separate commit per phase for easy rollback
6. **Never rename parameters** — keep exact same function signatures
7. **Keep logging identical** — same log messages, same emojis, same format
8. **No import changes in other files** — only `async_gridbot.py` changes its imports

---

## Phase 0: Pre-Refactoring Setup (15 min)

### 0.1 Create the test checklist file
Create `tests/refactoring_checklist.md` — a manual verification checklist that you run after each phase.

### 0.2 Checklist Content
```markdown
# Post-Phase Verification Checklist

Run after EVERY phase extraction. ALL must pass.

## Syntax Check
- [ ] `python3 -c "import py_compile; py_compile.compile('bot/strategy/async_gridbot.py', doraise=True)"`
- [ ] `python3 -c "import py_compile; py_compile.compile('bot/strategy/modules/<new_module>.py', doraise=True)"`

## Import Check  
- [ ] `python3 -c "from bot.strategy.async_gridbot import AsyncGridBot; print('Import OK')"`

## Bot Startup Test (CRITICAL)
- [ ] Start bot: `pm2 start ecosystem.config.js --only gridbot-btc`
- [ ] Wait for: `✅ AsyncGridBot started successfully` in logs
- [ ] Verify: `[HB]` heartbeat messages appear every 15s
- [ ] Verify: Guardian signal is being read (`🛡️  Guardian: 🟢 GO`)
- [ ] Verify: Price updates flowing (`💚 WebSocket ticker`)
- [ ] Verify: No Python tracebacks in logs for 2 minutes
- [ ] Stop bot: `pm2 stop gridbot-btc`

## WebUI Endpoint Test
- [ ] `curl -s http://localhost:5555/api/positions | python3 -m json.tool | head`
- [ ] `curl -s http://localhost:5555/api/health/detailed | python3 -m json.tool | head`

## Smoke Test Summary
- [ ] Bot starts without errors
- [ ] Bot stops cleanly (no hanging processes)
- [ ] No `ImportError` or `AttributeError` in logs
- [ ] Fill processing works (if market moves during test)
```

### 0.3 Create git branch
```bash
git checkout -b refactor/split-gridbot
```

### 0.4 Snapshot current file
```bash
cp bot/strategy/async_gridbot.py bot/strategy/async_gridbot.py.pre_refactor_backup
```

---

## Phase 1: Extract `guardian_handler.py` (Easiest, ~1 hour)

### Why First
- Self-contained signal reading concern
- Zero order placement logic
- Only reads EventStore and manages missed-order buffer
- If this breaks, worst case is Guardian signal not read → bot safely halts

### Step 1.1: Create the new module file

Create `bot/strategy/modules/guardian_handler.py` with this exact structure:

```python
"""
Guardian Signal Handler — extracted from async_gridbot.py

Responsibilities:
- Read Guardian GO/STOP signal from EventStore
- Detect signal transitions (STOP→GO, GO→STOP)
- Manage missed grid orders during STOP
- Retry missed orders on GO resume
- A3: Multi-step missed grid recovery
- Cancel pending entry orders on STOP
- Resume grid trading on GO

NOT Responsible For:
- Order placement logic (delegates to order_actor)
- Price tracking
- WebSocket management
- Fill processing
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from loguru import logger as log

from bot.strategy.modules.event_store import EventStore, EventType


class GuardianHandler:
    """Handles Guardian signal reading, transitions, and missed-order recovery."""

    def __init__(
        self,
        event_store: EventStore,
        position_actor,      # PositionManagerActor
        order_actor,          # OrderManagerActor
        grid_calc,            # GridCalculator
        mode: str,            # "LONG" or "SHORT"
        grid_step: float,
        max_positions: int,
        lot_size: float,
        ref_price: float,
        log_rate_limiter: Dict[str, float],  # shared reference to bot's rate limiter dict
        should_log_fn,        # callable: (key, interval) -> bool
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
        self._log_rate_limiter = log_rate_limiter
        self._should_log = should_log_fn

        # State
        self._last_guardian_signal: Optional[str] = None
        self._guardian_transition_time: float = 0
        self._missed_grid_orders: List = []

        # External references (set by orchestrator after construction)
        self._running_ref = None       # lambda: -> bool (checks bot._running)
        self._current_price_ref = None # lambda: -> Optional[float]
        self._set_running_fn = None    # callable: (bool) -> None

    def set_runtime_refs(self, running_ref, current_price_ref, set_running_fn):
        """Set runtime references after construction."""
        self._running_ref = running_ref
        self._current_price_ref = current_price_ref
        self._set_running_fn = set_running_fn
```

### Step 1.2: Copy methods exactly (no changes)

Copy these methods from `async_gridbot.py` into the `GuardianHandler` class:
- `_read_guardian_signal` → rename to `read_signal`
- `_check_guardian_transition_and_retry` → rename to `check_transition_and_retry`
- `_retry_missed_grid_orders` → rename to `retry_missed_orders`
- `_fill_multi_step_missed_grids` → rename to `fill_multi_step_missed_grids`
- `_check_guardian_transitions` → rename to `check_transitions`
- `_cancel_pending_entry_orders` → rename to `cancel_pending_entries`
- `_resume_grid_trading` → rename to `resume_grid`
- `_guardian_health_monitor_loop` → rename to `health_monitor_loop`

**For every method:**
1. Replace `self.current_price` → `self._current_price_ref()`
2. Replace `self._running` (read) → `self._running_ref()`
3. Replace `self._running = False` → `self._set_running_fn(False)`
4. Replace `self._should_log(key, interval)` calls → keep same (it's already a callable)
5. Keep ALL log messages exactly the same (including emojis)

### Step 1.3: Update the orchestrator

In `async_gridbot.py`:

1. Add import at top:
```python
from bot.strategy.modules.guardian_handler import GuardianHandler
```

2. In `__init__`, after grid_calc initialization, add:
```python
self.guardian = GuardianHandler(
    event_store=self.event_store,
    position_actor=self.position_actor,
    order_actor=self.order_actor,
    grid_calc=self.grid_calc,
    mode=self.mode,
    grid_step=self.grid_step,
    max_positions=self.max_positions,
    lot_size=self.lot_size,
    ref_price=self.ref_price,
    log_rate_limiter=self._log_rate_limiter,
    should_log_fn=self._should_log,
)
```

3. In `start()`, before starting tasks, add:
```python
self.guardian.set_runtime_refs(
    running_ref=lambda: self._running,
    current_price_ref=lambda: self.current_price,
    set_running_fn=lambda v: setattr(self, '_running', v),
)
```

4. Replace all calls:
```python
# Before:                                    # After:
await self._read_guardian_signal()           → await self.guardian.read_signal()
await self._check_guardian_transition_and_retry() → await self.guardian.check_transition_and_retry()
await self._retry_missed_grid_orders()       → await self.guardian.retry_missed_orders()
await self._fill_multi_step_missed_grids()   → await self.guardian.fill_multi_step_missed_grids()
await self._check_guardian_transitions()     → await self.guardian.check_transitions()
await self._cancel_pending_entry_orders()    → await self.guardian.cancel_pending_entries()
await self._resume_grid_trading()            → await self.guardian.resume_grid()
self._guardian_health_monitor_loop()         → self.guardian.health_monitor_loop()
self._last_guardian_signal                   → self.guardian._last_guardian_signal
self._missed_grid_orders                     → self.guardian._missed_grid_orders
```

5. Delete the original methods from `async_gridbot.py`

### Step 1.4: Verify
Run the full verification checklist from Phase 0.

### Step 1.5: Commit
```bash
git add bot/strategy/modules/guardian_handler.py bot/strategy/async_gridbot.py
git commit -m "Phase 1: Extract GuardianHandler from async_gridbot.py (~520 lines)"
```

---

## Phase 2: Extract `health_monitor.py` (~1 hour)

### Why Second
- Read-only observation loops — they don't place orders
- If broken, bot still trades correctly (just no heartbeat/monitoring)
- Clear boundary: these methods write JSON and log status, nothing else

### What Moves
| Method | New Name |
|--------|----------|
| `_heartbeat_loop` | `heartbeat_loop` |
| `_monitoring_loop` | `monitoring_loop` |
| `_health_check_loop` | `health_check_loop` |
| `_watchdog_loop` | `watchdog_loop` |
| `_update_external_heartbeat` | `update_external_heartbeat` |
| `_check_memory_usage` | `check_memory_usage` |
| `_check_websocket_health` | `check_websocket_health` |
| `_should_log` | Stays in orchestrator (shared utility) |

### Class Design
```python
class HealthMonitor:
    def __init__(
        self,
        position_actor,
        order_actor,
        saga_orchestrator,
        api_client,
        grid_calc,
        price_monitor,
        mode: str,
        symbol: str,
        symbol_name: str,
        max_positions: int,
        instance_name: str,
        config,
        should_log_fn,
    ):
        ...

    def set_runtime_refs(self, running_ref, current_price_ref, 
                         start_time_ref, fills_ref, sagas_completed_ref,
                         sagas_failed_ref, last_price_update_ref,
                         initial_order_placed_ref, heartbeat_time_ref):
        """Lambdas pointing to bot attributes."""
        ...
```

### Dependency Note
`_health_check_loop` calls `_check_guardian_transitions` and `_process_tp_retry_queue`. After Phase 1, guardian is already extracted. `_process_tp_retry_queue` will be extracted in Phase 7, so leave a temporary delegation call:
```python
# In health_check_loop:
await self._tp_retry_callback()  # Set during set_runtime_refs
```

### Verification
Same checklist. Verify `[HB]` heartbeat messages still appear.

### Commit
```bash
git commit -m "Phase 2: Extract HealthMonitor from async_gridbot.py (~400 lines)"
```

---

## Phase 3: Extract `exchange_sync.py` (~1.5 hours)

### Why Third
- Startup reconciliation and exchange sync are heavy but isolated
- They run once at startup and during maintenance — not on the hot path
- Medium risk: they interact with exchange API and position actor

### What Moves
| Method | New Name |
|--------|----------|
| `_reconcile_orphaned_orders` | `reconcile_orphaned_orders` |
| `_cleanup_misaligned_orders` | `cleanup_misaligned_orders` |
| `_reconcile_fills_after_reconnect` | `reconcile_fills_after_reconnect` |
| `_full_exchange_sync` | `full_exchange_sync` |
| `_ensure_grid_coverage` | `ensure_grid_coverage` |
| `_detect_exchange_state` | `detect_exchange_state` |
| `_handle_exchange_maintenance` | `handle_exchange_maintenance` |
| `_exchange_maintenance_monitor` | `exchange_maintenance_monitor` |
| `_sync_positions_from_exchange` | `sync_positions_from_exchange` |

### Class Design
```python
class ExchangeSync:
    def __init__(
        self,
        api_client,           # UnifiedAPIClient
        position_actor,
        order_actor,
        event_store,
        grid_calc,
        fill_processor,       # For processing missed fills (added after Phase 5)
        mode: str,
        symbol: str,
        product_id: int,
        grid_step: float,
        lot_size: float,
    ):
        ...
```

### Important
- `_full_exchange_sync` calls `_ensure_grid_coverage` — both move together, so internal calls work.
- `_reconcile_fills_after_reconnect` calls `_process_fill` — this method is in fill_processor (Phase 5). **For now, use a callback**: `self._process_fill_callback`.

### Verification
- Start bot, verify `🔄 Reconciling orphaned orders` messages appear
- Start bot with existing open orders, verify they're adopted correctly

### Commit
```bash
git commit -m "Phase 3: Extract ExchangeSync from async_gridbot.py (~600 lines)"
```

---

## Phase 4: Extract `ws_lifecycle.py` (~1 hour)

### Why Fourth
- WebSocket lifecycle is well-bounded
- REST fallback is a clear alternative data path
- Medium risk: ticker updates trigger `_check_and_place_entry_order` 

### What Moves
All Group 6 methods above.

### Critical Callback
`_handle_ticker_update` calls `_check_and_place_entry_order` (grid engine). Use callback pattern:
```python
self._on_ticker_callback = None  # Set by orchestrator
```

In orchestrator's `start()`:
```python
self.ws_lifecycle.set_ticker_callback(self.grid_engine.check_and_place_entry_order)
```

### Verification
- Verify price updates flowing in logs
- Verify REST fallback activates when WebSocket is slow (simulate by brief disconnect)

### Commit  
```bash
git commit -m "Phase 4: Extract WSLifecycle from async_gridbot.py (~500 lines)"
```

---

## Phase 5: Extract `fill_processor.py` (~2 hours)

### Why Fifth (HIGH RISK)
- Core fill dedup and saga dispatch
- Multiple detection sources feed into it (WebSocket, FillMonitor, REST polling)
- Must maintain exact dedup behavior

### What Moves
All Group 3 methods above.

### Critical Dependencies
- Saga creation functions (`create_buy_fill_saga`, etc.) — imported from existing saga modules
- `human_log` — imported from existing utility
- `_is_fill_seen`, `_mark_fill_seen` — move along with dedup state

### Testing Plan (Extra Thorough)
1. Start bot
2. Wait for a fill to occur (or trigger one via manual order)
3. Verify: fill is processed ONCE (check for `🔔 Processing fill` log)
4. Verify: TP order is placed (check for `✅ Position closed` or `✅ New position opened`)
5. Verify: NO duplicate fill processing (search logs for `⏭️  Skipping already processed`)
6. Check FillMonitor is still tracking orders

### Commit
```bash
git commit -m "Phase 5: Extract FillProcessor from async_gridbot.py (~700 lines)"
```

---

## Phase 6: Extract `grid_engine.py` (~2 hours)

### Why Sixth (HIGHEST RISK)
- Contains order placement lock (`_order_placement_lock`)
- Contains the massive `_place_initial_order` (280 lines)
- Contains safety gatekeeper integration

### What Moves
All Group 4 methods above.

### Critical Design Decision
The `asyncio.Lock` must live in the grid engine, not the orchestrator:
```python
class GridEngine:
    def __init__(self, ...):
        self._order_placement_lock = asyncio.Lock()
```

### Testing Plan (Extra Thorough)
1. Start bot with NO existing positions or orders → verify initial order placed
2. Start bot WITH existing exchange orders → verify they're adopted (not duplicated)
3. Let a fill occur → verify next grid order is placed at correct level
4. Let Guardian go STOP then GO → verify grid resumes correctly
5. Verify: only ONE pending order at any time (never two buys)

### Commit
```bash
git commit -m "Phase 6: Extract GridEngine from async_gridbot.py (~800 lines)"
```

---

## Phase 7: Extract `recovery_actions.py` (~1 hour)

### What Moves
All Group 8 methods above.

### Verification
- Verify reconciliation action processor runs (look for `📋 Reconciliation action processor started`)
- Verify safety gatekeeper runs (look for `🔒 Running periodic safety check`)
- Verify fill polling runs (look for `🔄 Fill polling fallback started`)

### Commit
```bash
git commit -m "Phase 7: Extract RecoveryActions from async_gridbot.py (~500 lines)"
```

---

## Phase 8: Slim Down Orchestrator (~1 hour)

### What's Left
Only `start()`, `stop()`, `__init__()`, signal handlers, and wiring code.

### Actions
1. Remove all dead code, unused imports
2. Clean up `__init__` — it should only:
   - Load config
   - Create actors, grid_calc, api_client, event_store
   - Create each extracted module (7 constructors)
   - Initialize metrics counters
3. `start()` should only:
   - Wire runtime refs
   - Call startup sequence
   - Create async tasks (one per module loop)
   - Wait for shutdown
4. `stop()` should only:
   - Cancel tasks
   - Stop actors
   - Disconnect WebSocket

### Target Size
Under 500 lines total.

### Commit
```bash
git commit -m "Phase 8: Slim orchestrator to ~500 lines"
```

---

## Phase 9: Final Verification & Merge (~1 hour)

### Full Test Suite
1. Start bot from cold (no state, no positions)
2. Wait for initial order placement
3. Let 1+ fills process (verify TP placed)
4. Trigger Guardian STOP → verify entries cancelled
5. Trigger Guardian GO → verify grid resumes
6. Kill bot → verify clean shutdown, TP orders preserved
7. Restart bot → verify orphaned order reconciliation
8. Check WebUI endpoints still work
9. Let bot run for 30 minutes unattended

### Code Review
- `grep -r "self\._" bot/strategy/async_gridbot.py | wc -l` — should be < 50 attribute references
- No method should be > 100 lines in the orchestrator
- Every module should be importable independently: `python3 -c "from bot.strategy.modules.guardian_handler import GuardianHandler"`

### Merge
```bash
git checkout SSR
git merge refactor/split-gridbot
git push
```

---

## Dependency Graph Between Modules

```
                    ┌──────────────┐
                    │ Orchestrator │  (async_gridbot.py)
                    │   ~500 LOC   │
                    └──────┬───────┘
                           │ creates & wires
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐
  │ GuardianHandler│ │ GridEngine   │ │ FillProcessor│
  │   Phase 1     │ │  Phase 6     │ │   Phase 5    │
  └───────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
          │ reads signal   │ places orders  │ dispatches sagas
          ▼                ▼                ▼
  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐
  │  EventStore   │ │ OrderActor   │ │SagaOrchestrator│
  │ (existing)    │ │ (existing)   │ │ (existing)   │
  └───────────────┘ └──────────────┘ └──────────────┘
          
  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐
  │ HealthMonitor │ │ WSLifecycle  │ │ ExchangeSync │
  │   Phase 2     │ │  Phase 4     │ │   Phase 3    │
  └───────────────┘ └──────────────┘ └──────────────┘
          │                │                │
          │ observes       │ feeds prices   │ syncs state
          ▼                ▼                ▼
  ┌────────────────────────────────────────────────┐
  │          PositionActor (existing)              │
  └────────────────────────────────────────────────┘
```

**Key Rule:** Modules never import each other directly. They communicate via the orchestrator or via callbacks set during wiring.

---

## Inter-Module Communication Pattern

Modules don't call each other. The orchestrator wires callbacks:

```python
# In orchestrator's start():

# FillProcessor needs to call check_and_place_entry_order after fill
self.fill_processor.set_post_fill_callback(self.grid_engine.check_and_place_entry_order)

# WSLifecycle needs to call check_and_place_entry_order on ticker update  
self.ws_lifecycle.set_ticker_callback(self.grid_engine.check_and_place_entry_order)

# WSLifecycle needs to call process_fill on order update
self.ws_lifecycle.set_order_update_callback(self.fill_processor.handle_order_update)

# ExchangeSync needs process_fill for reconciliation
self.exchange_sync.set_fill_callback(self.fill_processor.process_fill)

# GuardianHandler needs cancel_pending and resume_grid from grid_engine
self.guardian.set_grid_callbacks(
    cancel_fn=self.grid_engine.cancel_pending_entries,
    resume_fn=self.grid_engine.resume_grid,
)

# HealthMonitor needs tp_retry from recovery_actions
self.health_monitor.set_tp_retry_callback(self.recovery_actions.process_tp_retry_queue)
```

---

## Risk Mitigation Summary

| Risk | Mitigation |
|------|-----------|
| Breaking fill dedup | Phase 5 has extra test: monitor logs for duplicate `🔔 Processing fill` |
| Breaking order placement | Phase 6 has 5-point test suite for grid entry scenarios |
| Breaking Guardian signal | Phase 1 — if signal reading breaks, bot safely halts (fail-safe) |
| Circular imports | Modules never import each other. Communication via callbacks only. |
| Attribute access errors | Each module gets explicit deps via constructor, not `self.bot.*` |
| Race conditions | `asyncio.Lock` ownership stays with grid_engine (same as today) |
| Rollback needed | Each phase = 1 git commit. `git revert` any single phase. |
| Multiple failure points | Run full checklist after EACH phase, not just at the end |

---

## Time Estimate

| Phase | Time | Risk Level |
|-------|------|------------|
| Phase 0: Setup | 15 min | None |
| Phase 1: GuardianHandler | 1 hr | Low |
| Phase 2: HealthMonitor | 1 hr | Low |
| Phase 3: ExchangeSync | 1.5 hr | Medium |
| Phase 4: WSLifecycle | 1 hr | Medium |
| Phase 5: FillProcessor | 2 hr | **High** |
| Phase 6: GridEngine | 2 hr | **High** |
| Phase 7: RecoveryActions | 1 hr | Medium |
| Phase 8: Slim Orchestrator | 1 hr | Low |
| Phase 9: Full Verification | 1 hr | None |
| **Total** | **~12 hours** | |

**Recommendation:** Do phases 1-2 in one session (2 hours, low risk). Then phases 3-4 in another (2.5 hours, medium risk). Then phases 5-6 in a dedicated session with market access for live testing (4 hours, high risk). Phases 7-9 as cleanup (3 hours).

---

## When NOT to Start This

- Never start during live trading hours with open positions
- Never start without a working Guardian bot
- Never start without git branch protection
- Never start if any audit fix is pending
- Never combine with feature work — refactoring only

---

## Success Criteria

- [ ] `async_gridbot.py` is under 600 lines
- [ ] Every new module is independently importable
- [ ] Bot passes all 9 verification checklist items
- [ ] Bot runs for 1 hour unattended without errors
- [ ] No method in any file exceeds 100 lines
- [ ] WebUI endpoints all return 200
- [ ] Guardian health monitoring works
- [ ] Fill processing dedup works (no double fills)
- [ ] Grid order placement works (correct levels)
- [ ] Shutdown preserves TP orders
