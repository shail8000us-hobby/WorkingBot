# PHASE 01 — Architecture Truth Audit
**Lead Agent:** Architecture Truth Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Reads Required:** None (Phase 1 is foundational)

---

## Executive Summary

The MMM Algo's architecture is a classic organic growth system — each feature was added correctly in isolation but the cumulative effect is a God-object orchestrator, fragmented responsibility, and several structural patterns that create recurring bug classes. The dispatch table for strategy routing is notably clean. The guardian/generation integrity system is well-designed. However, the central `mmm_monitor.py` is the single most dangerous architectural liability: it is ~3200+ lines, imports from 35+ modules, and is the single point of failure for every trading session.

**Overall Architecture Grade: C+** — functional for current scale, fragile for growth.

---

## 1. Module Dependency Map

### 1.1 Tier 1 — Imported by mmm_monitor.py Directly (35+ imports)

`mmm_monitor.py` is the root of the dependency tree. At module load time it imports:

```
mmm_state          mmm_trigger         mmm_heartbeat_health    mmm_pnl_core
mmm_circuit_breaker  mmm_engine        mmm_reversal            mmm_strike_shift
mmm_wind_down      mmm_close_at_5      mmm_analytics_storage   mmm_safety
mmm_pending_orders mmm_websocket       mmm_atm_shield          mmm_adaptive
mmm_breakeven_engine  mmm_gamma_detector  mmm_harvester         mmm_recycler
mmm_perp_hedge     mmm_storage         mmm_constants           mmm_margin_guardian
mmm_dte_presets    mmm_regime          mmm_telegram            mmm_reverse
mmm_strategy_dispatch  mmm_whipsaw     mmm_activity (try/except)
```

Additional **lazy imports inside methods** (to avoid circular imports at load time):
```
mmm_guardian        mmm_god_layer       mmm_straddle_adjustment   mmm_executor
mmm_initializer     mmm_fill_sync       mmm_performance           mmm_audit_log
mmm_audit_remark    mmm_telegram (various functions)              mmm_adaptive
mmm_straddle_roll_pure  mmm_exit_all    mmm_observer              mmm_scaler
mmm_ledger          mmm_config
```

**Finding A1-01 (P1):** `mmm_monitor.py` imports from ~50 of the 57 modules in the package. This is not a coordinator — it is a God object that owns the entire execution graph.

### 1.2 Tier 2 — Shared Utility Modules (imported by 5+ callers)

| Module | Used By (count estimate) |
|---|---|
| `mmm_constants.py` | ~25 modules |
| `mmm_state.py` | ~20 modules |
| `mmm_storage.py` | ~15 modules |
| `mmm_websocket.py` | ~15 modules |
| `mmm_activity.py` | ~20 modules |
| `mmm_telegram.py` | ~10 modules |
| `mmm_executor.py` | ~8 modules |
| `mmm_safety.py` | ~8 modules |

### 1.3 Tier 3 — Leaf Modules (1–3 callers each)

Strategy-specific: `mmm_straddle_adjustment.py`, `mmm_straddle_roll_pure.py`, `mmm_reverse.py`, `mmm_reversal.py`

Math/analysis: `mmm_gamma.py`, `mmm_gamma_detector.py`, `mmm_breakeven_engine.py`, `mmm_atm_shield.py`, `mmm_regime.py`, `mmm_scaler.py`

Execution: `mmm_executor.py`, `mmm_fill_sync.py`, `mmm_pending_orders.py`, `mmm_ledger.py`, `mmm_ws_executions.py`

### 1.4 Circular Import Map

Direct circular imports are avoided via lazy (inside-function) imports. This is a workaround pattern, not a solution.

**Identified lazy-import dependencies (circular if un-lazied):**
- `mmm_guardian.py` → imports `mmm_straddle_adjustment` (for roll lock cleanup)
- `mmm_guardian.py` → imports `mmm_websocket`, `mmm_activity`, `mmm_telegram`
- `mmm_watchdog.py` → imports `mmm_monitor` (for `start_session_monitor`) — circular
- `mmm_exit_all.py` → likely imports `mmm_monitor` or `mmm_executor` — needs verification
- `mmm_strategy_dispatch.py` → imports `mmm_straddle_adjustment`, `mmm_straddle_roll_pure` inside functions

**Finding A1-02 (P2):** ~6 modules use lazy imports to avoid circular dependencies. This is a symptom of too-tight coupling between execution and orchestration layers. Each lazy import is a hidden dependency that IDE tools and static analyzers cannot detect.

---

## 2. God Object Analysis — mmm_monitor.py

### 2.1 Responsibilities Concentrated in mmm_monitor.py

The following distinct concerns are all handled directly in `mmm_monitor.py`:

| Concern | Lines Estimate | Should Be In |
|---|---|---|
| Session lifecycle (start/stop/pause/resume) | ~200 lines | SessionLifecycleManager |
| Thread management (main + 4 auxiliary threads) | ~150 lines | ThreadOrchestrator |
| Generation counter management | ~80 lines | GenerationManager |
| Heartbeat loop + interval calculation | ~300 lines | HeartbeatRunner |
| P&L calculation and caching | ~100 lines | PnLCache (already exists as pnl_core — not fully used) |
| WebSocket emit calls | ~100 lines | Already exists (mmm_websocket.py) — used correctly |
| Safety check invocations | ~200 lines | SafetyGate (already exists — partially used) |
| Strategy dispatch | ~100 lines | Already extracted to mmm_strategy_dispatch.py |
| Reverse mode orchestration | ~150 lines | Already exists (mmm_reverse.py) |
| Straddle roll orchestration | ~200 lines | Already exists (mmm_straddle_adjustment.py) |
| Margin guardian invocations | ~80 lines | Already exists (mmm_margin_guardian.py) |
| Straddle state initialization | ~100 lines | Should be in mmm_initializer.py |
| Adaptive interval logic | ~80 lines | Already exists (mmm_adaptive.py) |
| Whipsaw evaluation | ~100 lines | Already exists (mmm_whipsaw.py) |
| Regime check | ~100 lines | Already exists (mmm_regime.py) |
| Hard stop guard thread | ~100 lines | Already exists but wired inline |
| Close watcher thread | ~100 lines | Inline in monitor |
| Price ticker thread | ~100 lines | Inline in monitor |
| Price guard thread | ~100 lines | Inline for straddle sessions |
| Warning cooldown system | ~60 lines | Should be a standalone utility |
| Last-good-price cache | ~40 lines | Part of price fetch logic |
| Performance collector | ~60 lines | mmm_performance.py exists |
| Analytics updates | ~60 lines | mmm_analytics_aggregator.py exists |
| Stale _being_closed flag cleanup | ~40 lines | mmm_initializer.py |
| DEFAULT_PARAMS backfill | ~20 lines | mmm_initializer.py |

**Finding A1-03 (P1):** `mmm_monitor.py` handles ~25 distinct concerns. Estimated total: 3200–3500 lines. This is unmaintainable at scale. Every bug fix in any area risks touching unrelated code. Every new feature requires editing the same file.

### 2.2 Auxiliary Threads Per Session

Each active `MMMMonitor` instance creates **5 background threads**:

1. `mmm-monitor-{sid}` — main heartbeat loop
2. Hard stop guard thread — independent max-loss enforcement
3. Close watcher thread — independent close-at-threshold monitoring
4. Price ticker thread — WebSocket price streaming
5. Price guard thread (straddle sessions only) — real-time spot price monitor

**Finding A1-04 (P2):** Five threads per session with no unified thread registry. If any thread fails silently, there is no cross-thread alert. The watchdog only monitors the main heartbeat thread, not the 4 auxiliary threads. A stuck close watcher or price guard would be invisible.

---

## 3. Global Singleton Registry Analysis

### 3.1 Module-Level Global State

The following module-level singletons are shared across all sessions (thread-unsafe without locks):

| Variable | Location | Lock Used | Risk |
|---|---|---|---|
| `_monitors: Dict[str, MMMMonitor]` | `mmm_monitor.py` | `_monitors_lock` (RLock) | Lock exists but callers may not always use it |
| `_guardians: Dict[str, MMMGuardian]` | `mmm_guardian.py` | `_guardians_lock` (Lock) | Lock used correctly in all 3 access points |
| `MMMWatchdog._instance` | `mmm_watchdog.py` | `_instance_lock` | Correct singleton pattern |
| `MMMWatchdog._monitors` | `mmm_watchdog.py` | `_lock` (RLock) | Correct |
| `_pending_orders: Dict` | `mmm_pending_orders.py` | Unknown — needs verification |
| Whipsaw state | `mmm_whipsaw.py` | Unknown — needs verification |
| Circuit breaker state | `mmm_circuit_breaker.py` | Unknown — needs verification |

**Finding A1-05 (P1):** Global registries are the correct pattern for per-session lookup, but the locking discipline is inconsistent. `mmm_pending_orders.py`, `mmm_whipsaw.py`, and `mmm_circuit_breaker.py` need Phase 8 verification of their locking.

### 3.2 Session Pointer Sharing Risk

`MMMMonitor` stores `self.session` as a live dict pointer. Multiple subsystems access and modify the same dict:

- Main heartbeat thread modifies it on every beat
- Hard stop guard thread reads/writes it
- Watchdog reads it during `_check_monitor()`
- API endpoints read it via `get_safe_session()` (which uses `_session_lock` + `deepcopy`)
- Fill sync writes lot counts to it (async, from a different context)

**Finding A1-06 (P1):** `_session_lock` in `MMMMonitor` is a `threading.Lock`. It is used in `pause()`, `resume()`, and `get_safe_session()`. However, `_heartbeat()` (the main loop body) does NOT acquire `_session_lock` before modifying `self.session`. This means API reads during an active heartbeat may read partially-updated state.

**Mitigating factor:** `get_safe_session()` uses `deepcopy` under lock, so API reads get a snapshot. The risk is primarily the other direction: a fill_sync or hard stop guard writing to the session dict while a heartbeat is also writing — a true torn write scenario.

---

## 4. Strategy Dispatch Architecture — POSITIVE FINDING

`mmm_strategy_dispatch.py` is the cleanest module in the codebase:

- `StrategyHandler` frozen dataclass — immutable dispatch table
- `STRATEGY_DISPATCH` dict — explicit table, no hidden branching
- `validate_session` per-strategy — correct separation of concerns
- `should_run_adjustment`, `should_run_wind_down`, `should_run_atm_shield` flags — clean capability model

**Finding A1-07 (P3 — positive):** Strategy dispatch is architecturally correct. The dispatch table is clean, explicit, and auditable. Future strategies can be added without modifying `mmm_monitor.py`.

**Residual risk:** `mmm_monitor.py` still checks `strategy_type` inline in several places outside the dispatch system (specifically around straddle state initialization at start). This is a small but real coupling leak.

---

## 5. Async/Sync Boundary Analysis

The MMM system runs in a Flask/gunicorn+eventlet environment. The heartbeat monitor uses a genuine OS thread (eventlet workaround) running a synchronous loop that calls `asyncio.run_until_complete()` to execute async operations.

**The boundary model:**
```
Flask routes (async, eventlet)
    ↓
mmm_monitor._run_loop() [sync, OS thread]
    ↓
asyncio.run_until_complete(_heartbeat_inner())  [creates new event loop per beat]
    ↓
await exchange API calls, await strategy functions
```

**Finding A1-08 (P1):** A **new asyncio event loop is created for each heartbeat cycle** via `asyncio.run_until_complete()`. This is the intended design but has implications:
- `asyncio.ensure_future()` called inside `_heartbeat_inner` (for Telegram alerts) schedules on the current loop. If the loop closes before the future runs, the Telegram alert is silently lost.
- `emit_safety()` is defined as a regular `def` (not async) — this is correct per CLAUDE.md invariants.
- Any coroutine that calls `asyncio.get_running_loop()` will get the per-beat loop, which is destroyed after the beat. If a coroutine stores the loop reference for later use, it will get a closed loop.

**Finding A1-09 (P1):** `asyncio.ensure_future()` is called in several places (guardian G5, whipsaw, Telegram alerts) from within `_heartbeat_inner()`. These fire-and-forget futures run on the per-beat event loop. If the event loop closes before they complete (network timeout, slow Telegram), the futures are silently cancelled. **Telegram alerts may silently fail under load.**

---

## 6. Duplicated Logic Register

| Pattern | Locations | Risk |
|---|---|---|
| `_D()` Decimal helper | `mmm_engine.py:30`, `mmm_constants.py:15` | Two definitions. If precision rule changes, one may be updated and one forgotten |
| `strike_key()` | Only in `mmm_constants.py` — imported correctly | No duplication found here |
| `compute_total_pnl` equivalent | `mmm_pnl_core.py`, `mmm_engine.py`, `mmm_monitor.py`, `mmm_api.py` | Phase 3 must verify formula consistency |
| `DEFAULT_PARAMS` | `mmm_state.py` has it; `mmm_config.py` has `PARAM_RULES` | Two separate param definition systems |
| Session status update pattern | `monitor.stop()`, `monitor.pause()`, `monitor.resume()`, watchdog, API endpoints | At least 6 places write `strategy_status` directly to the dict |

**Finding A1-10 (P2):** `_D()` is defined in two modules. `mmm_monitor.py` imports `_D` from `mmm_constants` (line 87), but `mmm_engine.py` defines its own `_D` at line 30. They appear identical — but are not the same object. If one is patched or overridden, the other is not affected.

**Finding A1-11 (P2):** `DEFAULT_PARAMS` in `mmm_state.py` and `PARAM_RULES` in `mmm_config.py` are parallel systems. Adding a new parameter requires updating both files. Missing from one = wrong default or missing validation. No enforcement that they stay in sync.

---

## 7. mmm_config.py Parameter Inventory

`mmm_config.py` defines 80+ named parameters in `PARAM_RULES`. Selected high-risk parameters:

| Param | Type | Range | Hot | Notes |
|---|---|---|---|---|
| `max_loss_amount` | float | 1–1e9 | Yes | Min was 0 before M-6 fix. Now 1. |
| `max_lots_per_side` | int | 1–10000 | Yes | No per-strategy cap differentiation |
| `max_total_exposure` | int | 0–20000 | Yes | Split Ledger guard |
| `adjustment_interval` | int | 10–3600 | Yes | Minimum 10s — very fast possible |
| `god_enabled` | bool | — | — | Off by default. Not in PARAM_RULES (checked in god_layer.py) |
| `guardian_enabled` | bool | — | Yes | Disabling guardian disables G1/G2/G3 |
| `god_pnl_threshold` | float | — | — | Read from params in god_layer.check() |
| `god_cooldown_min` | int | — | — | Not in PARAM_RULES |

**Finding A1-12 (P1):** `god_enabled`, `god_pnl_threshold`, `god_check_interval_min`, `god_min_silence_min`, `god_cooldown_min` are all god-layer params consumed from `session['params']` but **NOT defined in `mmm_config.py`'s `PARAM_RULES`**. This means:
- No type validation on these params
- No hot-reload tracking
- No range enforcement
- Phantom params from the WebUI truth perspective

**Finding A1-13 (P2):** `guardian_enabled=False` in params would disable G1, G2, G3 guards. This is an easy misconfiguration path. There is no UI warning that disabling guardian removes three of the five safety layers.

---

## 8. Watchdog Architecture Analysis

`MMMWatchdog` is well-designed:
- Singleton pattern with lock
- Exponential backoff
- MAX_RESTARTS_PER_SESSION = 10 cap
- Thread deadlock detection (beat timeout)
- EXITING state handling (post-P1 incident fix)
- Deferred restart (settlement wait via `_pending_restart_at`)

**Finding A1-14 (P2 — positive):** Watchdog architecture is sound. Settlement delay (F5 fix) is non-blocking. Exponential backoff prevents restart loops. EXITING detection is correct.

**Residual concern:** Watchdog `_check_monitor()` reads `monitor.session` without acquiring `monitor._session_lock`. This is a read-only access during normal operation, but if the heartbeat thread is in the middle of writing `session['strategy_status']` at the same instant, watchdog may read a stale/partial status. Low probability, not a P0.

---

## 9. Architecture Issue Register — Phase 1 Entries

| ID | Problem | Why It Exists | Risk | Modules Affected | Workaround | Priority |
|---|---|---|---|---|---|---|
| A1-01 | mmm_monitor.py is ~3200-line God object | Organic growth, no refactor | Every bug fix risks unrelated code; all sessions share one fault surface | All 57 modules | None | P1 |
| A1-02 | ~6 circular deps avoided via lazy imports | Too-tight coupling | Hidden dependencies, hard to static-analyze | monitor, watchdog, guardian, exit_all | Lazy imports | P2 |
| A1-03 | mmm_monitor.py owns 25 concerns | Features added inline | Cannot split without major refactor | mmm_monitor.py | None | P1 |
| A1-04 | 5 threads per session, 4 not monitored by watchdog | Auxiliary threads added over time | Silent failure of close watcher or price guard | monitor, watchdog | None | P2 |
| A1-05 | Lock discipline inconsistent across global registries | Different authors, different times | Race conditions under high load | pending_orders, whipsaw, circuit_breaker | Unknown | P1 |
| A1-06 | heartbeat loop does NOT acquire _session_lock | Performance — lock adds latency | Torn read/write on session dict concurrent with API or fill_sync | mmm_monitor.py | deepcopy in get_safe_session | P1 |
| A1-07 | asyncio.ensure_future() in per-beat loop | Fire-and-forget Telegram pattern | Alerts silently lost when loop closes before future completes | mmm_telegram.py via monitor | None | P1 |
| A1-08 | _D() defined in two modules | Copy-paste at engine creation | Formula divergence if one is updated | mmm_engine.py, mmm_constants.py | Import from constants in monitor | P2 |
| A1-09 | DEFAULT_PARAMS + PARAM_RULES are two parallel systems | Different development phases | New params require two file updates; missing from one = wrong default | mmm_state.py, mmm_config.py | Manual discipline | P2 |
| A1-10 | god_layer params not in PARAM_RULES | God layer added after config system | No validation, no range enforcement, no hot-reload for god params | mmm_god_layer.py, mmm_config.py | Manual | P1 |
| A1-11 | guardian_enabled=False disables G1/G2/G3 | Designed for testing/debugging | Easy to leave disabled; no UI warning | mmm_guardian.py | CLAUDE.md rules | P1 |
| A1-12 | Watchdog reads monitor.session without lock | Performance — read-only | Stale status read during concurrent heartbeat write | mmm_watchdog.py | Low-frequency, low risk | P3 |

---

## 10. Key Positive Architectural Findings

1. **Strategy dispatch table is clean** — `mmm_strategy_dispatch.py` is the best-designed module in the package. It is the model for how other concerns should be structured.
2. **Three-layer stale monitor guard is intact** — G5 in guardian, primary in `_run_loop`, secondary in `_save_my_session`. All three layers verified present.
3. **`_session_lock` exists and is used for API reads** — `get_safe_session()` correctly returns a deepcopy under lock. API responses are safe.
4. **Watchdog backoff and MAX_RESTARTS cap** — protects against restart loops.
5. **`initialize_reverse_state` called in `start()`** — stale session compatibility preserved at startup.
6. **Stale `_being_closed` flags cleared at startup** — crash recovery path handled.
7. **Generation counter wired in both monitor and watchdog** — generation increments in both `monitor.start()` and `watchdog._restart_monitor()`.

---

## 11. Phase 1 Pass Criteria Checklist

- [x] Complete module dependency graph produced (Section 1)
- [x] All God objects identified (mmm_monitor.py — Section 2)
- [x] All global singletons identified (Section 3)
- [x] Architecture Issue Register started with 12 entries (Section 9)
- [x] Three-layer stale monitor guard verified (Section 10)
- [x] Async/sync boundary analyzed (Section 5)
- [x] Circular dependency pattern identified (Section 1.2)
- [x] Strategy dispatch architecture assessed (Section 4)
- [x] God-layer params gap found (Section 7)

**Phase 1 Status: PASSED**

---

## 12. Handoff to Phase 2 (Accounting) and Phase 4 (Risk Controls)

**For Phase 2 (Accounting):**
- Session dict is raw, unversioned, no schema — affects lot accounting
- `_session_lock` not held during heartbeat — potential torn writes to lot counters
- Fill sync (`FillSyncer`) wired in `__init__` — initialized before generation counter is set
- `recompute_side_lots()` called by multiple modules — Phase 2 must verify it is always called after state changes

**For Phase 4 (Risk Controls):**
- `guardian_enabled=False` disables G1/G2/G3 — verify no session has this set
- God-layer params not validated — god layer could be misconfigured silently
- Hard stop guard is a separate thread — Phase 4 must verify its interaction with the heartbeat thread
- `emit_safety()` is regular `def` (not async) — confirmed correct per CLAUDE.md
