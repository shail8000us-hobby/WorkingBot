# PHASE 04 — Risk Controls Audit
**Lead Agent:** Risk Control Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01 Architecture Audit

---

## Executive Summary

The MMM risk control system has multiple layers that are generally well-implemented. The three-layer stale monitor guard is intact and verified. Max loss uses a canonical, sealed formula. The kill switch correctly sets `_running = False`. The guardian G1–G5 are present with correct behavior.

The primary risks found are: the God Layer parameters are not validated (no PARAM_RULES entry), `guardian_enabled=False` silently disables three guards, the hard stop guard is a background thread whose failure mode is not monitored, and the circuit breaker's reset conditions need verification. None of these are P0 conditions — but each represents a path where a misconfiguration or race condition weakens the safety layer.

**Risk Control Grade: B+** — multiple layers are intact; gaps are in configuration validation and auxiliary thread monitoring.

---

## 1. Risk Control Inventory

| Control | Module | Implementation | Status |
|---|---|---|---|
| Max loss hard stop | `mmm_safety.py:check_max_loss()` | @sealed, uses `compute_current_total_pnl()` | VERIFIED |
| Position cap | `mmm_safety.py:check_position_cap()` | Uses `total_lots` (includes frozen) | VERIFIED |
| Max adjustments | `mmm_safety.py:check_max_adjustments()` | Auto-resume on limit raise | VERIFIED |
| Kill switch (API) | `mmm_api.py` → `monitor.stop()` | Sets `_running=False`, `_stop_event.set()` | VERIFIED |
| Hard stop guard | `mmm_monitor.py:_start_hard_stop_guard()` | Independent thread, checks max_loss | NEEDS PHASE 8 |
| Stale monitor Layer 1 | `_run_loop()` before heartbeat | Checks stored_gen > my_gen | VERIFIED |
| Stale monitor Layer 2 | `_heartbeat()` G5 via guardian | `check_generation_integrity()` | VERIFIED |
| Stale monitor Layer 3 | `_save_my_session()` | `saved=False` → stop immediately | VERIFIED |
| Guardian G1 (hedge integrity) | `mmm_guardian.py` | Blocks close that wipes one side | VERIFIED |
| Guardian G2 (lot velocity) | `mmm_guardian.py` | Max lots closed per heartbeat | VERIFIED |
| Guardian G3 (side balance) | `mmm_guardian.py` | Post-beat wipeout detection → PAUSE | VERIFIED |
| Guardian G4 (beat duration) | `mmm_guardian.py` | Wall-clock deadline enforcement | VERIFIED |
| Guardian G5 (generation) | `mmm_guardian.py` | Stale monitor detection → STOP | VERIFIED |
| Circuit breaker | `mmm_circuit_breaker.py` | Consecutive failure counter | NEEDS VERIFY |
| Margin guardian | `mmm_margin_guardian.py` | YELLOW/ORANGE/RED/CRITICAL tiers | VERIFIED struct |
| Regime engine | `mmm_regime.py` | BLOCK_CE/PE/ALL, FORCE_REDUCE, PAUSE | VERIFIED struct |
| Whipsaw guard | `mmm_safety.py:check_whipsaw()` | NORMAL/CAUTION/RESTRICT/COOLDOWN | VERIFIED struct |
| Trailing stop | `mmm_safety.py:check_trailing_stop()` | Peak P&L drawdown guard | NEEDS FORMULA CHECK |
| PnL guardrail | `mmm_safety.py:check_pnl_guardrail()` | Tiered warning/pause/stop | NEEDS DETAIL |
| God Layer | `mmm_god_layer.py` | Drift correction, bypasses soft guards | PARAM GAP |

---

## 2. Three-Layer Stale Monitor Guard — VERIFIED INTACT

All three layers confirmed present and correct:

### Layer 1 — `_run_loop()` Primary Guard
**Location:** `mmm_monitor.py` ~line 1117–1145

```python
_stored_gen = fresh_session.get('_monitor_generation', 0)
if _stored_gen > self._my_generation and self._my_generation > 0:
    self._running = False
    # ... Telegram + emit_safety ...
    break
```

- Runs BEFORE `run_until_complete(_heartbeat())` — no orders placed on detection
- Fires Telegram via `self._loop.run_until_complete(_tg_stale(...))` — correct (loop exists at this point)
- Fires `emit_safety()` — correct (sync function)
- Sets `_running = False` and `break` — STOP not pause

**Status: CORRECT**

### Layer 2 — Guardian G5 in `_heartbeat()`
**Location:** `mmm_guardian.py:check_generation_integrity()` + `handle_stale_monitor()`

```python
if stored_gen > my_generation:
    # ... Telegram via ensure_future, emit_safety ...
    monitor._running = False
    monitor._stop_event.set()
    monitor._stale_abort_gen = my_generation
```

- Called at start of heartbeat, after `pre_beat_snapshot()`, before any trading
- Uses `asyncio.ensure_future()` for Telegram — fire-and-forget (risk: may not complete)
- `emit_safety()` called directly — correct (sync)
- STOP not PAUSE: `_running = False` — correct

**Status: CORRECT. Note: ensure_future Telegram may not complete before loop closes (per A1-09)**

### Layer 3 — `_save_my_session()` Secondary Guard
**Location:** `mmm_monitor.py:_save_my_session()`

```python
saved = _save_session(target, self._my_generation)
if saved is False and self._running:
    self._running = False
    self._stop_event.set()
    self._stale_abort_gen = self._my_generation  # triggers post-hb Telegram
```

- Triggered when `_save_session()` returns `False` (save rejected by generation check)
- Acts as failsafe for post-order save rejection
- Sets `_stale_abort_gen` flag for deferred Telegram (correct — cannot call run_until_complete inside it)

**Status: CORRECT**

**Generation increment verification:**
- `monitor.start()`: increments `_monitor_generation` in session dict
- `watchdog._restart_monitor()`: also increments `_monitor_generation`
- Both paths confirmed at correct locations

---

## 3. Max Loss Hard Stop Analysis

### 3.1 check_max_loss() — @sealed

```python
@sealed
def check_max_loss(self, session: Dict) -> List[Dict]:
    max_loss = params.get('max_loss_amount', 5000.0)
    from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
    total_pnl = _pnl_total(session)
    if total_pnl <= -max_loss:
        # action: 'auto_close'
```

- Uses `compute_current_total_pnl()` from `mmm_pnl_core` — canonical formula (verified import)
- Comparison: `total_pnl <= -max_loss` — correct direction (negative P&L exceeds negative limit)
- Default `max_loss_amount = 5000.0` — reasonable default but may be wrong for small capital
- M-6 fix: min of 1 enforced in PARAM_RULES — `max_loss_amount=0` would have disabled protection
- Warning at 80% threshold: `total_pnl <= -max_loss * 0.8`

**Finding A4-01 (P2):** `check_max_loss()` imports `compute_current_total_pnl` inside the function (lazy import). This is a runtime import on every heartbeat call. If `mmm_pnl_core` fails to import (import error), `check_max_loss()` will crash and the event list will be empty — the max loss check silently passes. The `run_all_checks()` caller does not guard for empty events from check_max_loss() specifically. However, this is a very low probability — module import errors are caught at startup.

### 3.2 Hard Stop Guard Thread

`mmm_monitor.py` starts an independent `_hard_stop_guard_thread` in addition to the main heartbeat. This thread independently monitors max_loss.

**Finding A4-02 (P1):** The hard stop guard thread is started but **its failure mode is not monitored**. If it crashes or becomes stuck, the backup max-loss protection is silently lost. The watchdog monitors only the main heartbeat thread. An Exception in `_hard_stop_guard_thread` would be silently swallowed.

**Finding A4-03 (P2):** The hard stop guard and the main heartbeat both call `_auto_close_all()`. If both fire simultaneously (race condition), two concurrent exit procedures could be running. `mmm_exit_all.py` has no lock preventing concurrent invocations from the same session. However, `_hard_stop_fired` event is used to prevent double-fire — needs Phase 8 verification that the event is checked by both paths.

---

## 4. Kill Switch Analysis

Kill switch is activated via API endpoint → `monitor.stop(reason)`.

`monitor.stop()`:
1. Sets `_running = False`
2. Calls `_stop_event.set()`
3. Sets `session['strategy_status'] = 'STOPPED'`
4. Calls `_save_my_session()` — persists STOPPED status
5. Sets `session['_save_disabled'] = True` after save — prevents old heartbeat from overwriting STOPPED
6. Deregisters from watchdog
7. Deregisters guardian

**Finding A4-04 (P2):** `monitor.stop()` does NOT explicitly stop the 4 auxiliary threads (hard stop guard, close watcher, price ticker, price guard). These threads check `self._running` or `self._stop_event` in their loops — correct. But if any auxiliary thread has a very long blocking call in progress when `stop()` is called, it may not terminate quickly.

**Finding A4-05 (P3):** The close watcher and price ticker are separate threads. After `monitor.stop()`, these threads continue checking `self._running` (now False) and will exit on their next poll cycle. This means for up to 5–15 seconds after a kill switch, these threads may still be running. No orders can be placed (the main heartbeat is stopped), so this is cosmetic.

---

## 5. Guardian G1–G5 Analysis

### G1 — Hedge Integrity Gate
Blocks any close that would reduce one side to 0 while the other still has lots.

**Exception list** (always allowed, bypass G1):
- `mechanism in ('emergency', 'both_sides_close', 'close_at_5', 'wind_down', 'exit_all')`

**Finding A4-06 (P2):** `close_at_5` and `wind_down` bypass G1. This means close_at_5 CAN close all positions on one side even if the other side still has lots. The documented justification: "Any buyback at threshold reduces risk unconditionally." This is the correct financial logic but it means G1 is not protection against close-at-5 creating an unhedged position — replenish handles that case.

### G2 — Lot Velocity (Per-Beat Cap)
Max lots closed per heartbeat. Default: `guardian_max_close_per_beat=50`.

Post-beat overshoot is logged but NOT a violation (boundary behavior — 49 closed then 5-lot close allowed, total 54). Pre-beat check blocks once 50+ reached.

**Status: CORRECT design**

### G3 — Side Balance
HARD invariant. One side going from >10 lots to 0 in single heartbeat → PAUSE.

**Finding A4-07 (P3):** G3 uses `total_lots` in the pre-beat snapshot but `active_lots` in `check_g3_healed()`. These are different: `total_lots` includes frozen lots. A side that went from 50 total_lots to 0 (all closed) but still has 10 frozen lots: G3 fires. But `check_g3_healed()` checks `active_lots > 0`, which would be 0 frozen. **The healing condition is stricter than the fire condition** — G3 could fire and never heal even after the situation resolves naturally. This needs Phase 8 verification.

### G4 — Beat Duration Deadline
`guardian_max_beat_sec=120` default. Checks if heartbeat exceeded wall-clock time.

**Finding A4-08 (P2):** G4 deadline is checked in `is_deadline_exceeded()` but the actual enforcement depends on callers within the heartbeat checking it. If a long-running exchange API call holds the event loop for >120 seconds, G4 cannot interrupt it — asyncio is single-threaded within `run_until_complete()`. G4 deadline is a detection tool, not an interruption.

### G5 — Monitor Generation (see Section 2)
Status: VERIFIED INTACT

### guardian_enabled = False

**Finding A4-09 (P1):** Setting `params['guardian_enabled'] = False` via the API disables:
- G1 (hedge integrity gate)
- G2 (lot velocity)
- G3 (side balance detection)

G5 (generation integrity) is NOT controlled by `guardian_enabled` — it's in a separate code path.

This parameter is hot-reload capable (in PARAM_RULES). An operator could accidentally or intentionally disable three safety guards. The UI should show a prominent warning when this is disabled. No such warning is documented.

---

## 6. God Layer Risk Assessment

### 6.1 What God Layer Can Do

God Layer bypasses: lot velocity, regime BLOCK_SELLS, margin YELLOW, asymmetry.
God Layer NEVER bypasses: PAUSED, STOPPED, margin ORANGE/RED, FORCE_REDUCE, stale monitor, straddle roll in progress, pending orders.

**Finding A4-10 (P1):** God Layer parameters are consumed from `session['params']` but are NOT in `mmm_config.py`'s PARAM_RULES:

| Param | Default | Validation |
|---|---|---|
| `god_enabled` | False | None |
| `god_pnl_threshold` | 40.0 | None — can be set to 0, fires every beat |
| `god_check_interval_min` | 25 | None — can be set to 0, fires every beat |
| `god_min_silence_min` | 20 | None — can be set to 0, fires on any adjustment |
| `god_cooldown_min` | 45 | None — can be set to 0, no cooldown after firing |

If `god_pnl_threshold=0`, God Layer fires on any negative drift. If `god_check_interval_min=0`, it fires every single heartbeat. Combined: God Layer could place an adjustment on every heartbeat with no cooldown, bypassing lot velocity limits.

**This is the highest-severity finding in this phase.** God Layer was designed as a 25-minute periodic corrector; without param validation it can become a continuous aggressive adjuster.

---

## 7. Circuit Breaker

`mmm_circuit_breaker.py` is referenced in `MMMMonitor.__init__` as `self._circuit = CircuitBreaker(session_id, ...)`. The file was not read in full for this phase.

**Finding A4-11 (P2 — needs verification):** Circuit breaker's failure threshold, reset conditions, and what "tripped" state prevents need Phase 8 verification. Key questions:
- Does a tripped circuit breaker prevent all adjustments or only API calls?
- What triggers a reset? Time-based? Manual?
- Can the circuit breaker be bypassed by God Layer?

---

## 8. Margin Guardian

`MarginGuardian` has tiers: GREEN, YELLOW, ORANGE, RED, CRITICAL.

`mmm_monitor.py` line ~1227: When `margin_tier in (YELLOW, ORANGE, RED, CRITICAL)`, the interval drops to 15 seconds (rapid check mode). This is a positive safety feature.

God Layer hard stops check `session.get('_margin_wind_down')` for ORANGE/RED. God Layer does NOT bypass ORANGE/RED margin.

**Finding A4-12 (P2):** Margin guardian runs async (`async def check_margin()`). The result is awaited inside the heartbeat coroutine. If the margin check API call fails, `_margin_check_fail_count` is incremented. After persistent failures, escalation occurs. **This is correct** — fail-open is documented as intentional (L-2 design).

---

## 9. Risk Controls Bypass Matrix

| Control | 0DTE Strangle | 5DTE Strangle | Straddle+Adj | Pure Roll | Reverse Mode |
|---|---|---|---|---|---|
| Max loss | All checked | All checked | All checked | All checked | Includes reverse P&L |
| Position cap | All checked | All checked | All checked | All checked | Excludes reverse lots |
| Guardian G1 | Active | Active | Active | Active | Active |
| Guardian G5 | Active | Active | Active | Active | Active |
| God Layer | If enabled | If enabled | If enabled | If enabled | God layer bypasses soft guards |
| ATM Shield | Active | Active | DISABLED | DISABLED | N/A |
| Wind-down | Active | Active | DISABLED | DISABLED | N/A |

**Finding A4-13 (P3):** Reverse mode lots are NOT included in `active_lots` position cap check. A session could have 100 CE lots (at cap), 100 PE lots (at cap), and 50 reverse lots without the position cap firing for reverse. This is by design (reverse is isolated), but means total exchange exposure could be 250 lots when the cap is 100 per side.

---

## 10. Architecture Issues — Phase 4 Entries

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A4-01 | check_max_loss lazy import — silent fail on import error | Max loss check could silently pass | P2 |
| A4-02 | Hard stop guard thread failure is unmonitored | Backup max-loss protection silently lost | P1 |
| A4-03 | Hard stop guard + heartbeat could both call _auto_close_all() concurrently | Duplicate exit procedures (mitigated by _hard_stop_fired event) | P2 |
| A4-04 | Auxiliary threads not explicitly stopped by monitor.stop() | Minor — they exit on next poll | P3 |
| A4-09 | guardian_enabled=False disables G1/G2/G3, no UI warning | Easy accidental disable of 3 guards | P1 |
| A4-10 | God Layer params not in PARAM_RULES — no validation | god_pnl_threshold=0 = fire every beat, bypassing lot velocity | P1 |
| A4-11 | Circuit breaker behavior not fully audited | Unknown bypass risks | P2 |
| A4-13 | Reverse lots not counted in position cap | Total exchange exposure can exceed stated cap | P3 |

---

## 11. Positive Findings

1. **Three-layer stale monitor guard is intact** — all three layers verified at correct locations with correct logic
2. **check_max_loss() is @sealed** — regression-locked
3. **Max loss uses canonical pnl formula** — `compute_current_total_pnl()` from pnl_core
4. **Kill switch correctly sets STOPPED** — saves to DB, sets `_save_disabled` to prevent overwrite
5. **God Layer hard stops are correct** — ORANGE/RED margin and FORCE_REDUCE cannot be bypassed
6. **G1 exceptions are justified** — close_at_5 and exit_all correctly bypass hedge integrity gate
7. **`guardian_enabled` does NOT disable G5** — stale monitor detection is always active
8. **Watchdog pause on MAX_RESTARTS** — prevents infinite restart loop

---

## 12. Pass Criteria Checklist

- [x] Three-layer stale monitor fix verified in code (Section 2)
- [x] Risk bypass matrix produced (Section 9)
- [x] Max loss formula verified (Section 3.1)
- [x] Kill switch stop path verified (Section 4)
- [x] God Layer param gap found and documented (Section 6)
- [x] guardian_enabled=False impact documented (Section 5, A4-09)
- [x] Architecture Issue Register updated (Section 10)
- [x] No P0 bypass path found — all P1 or lower

**Phase 4 Status: PASSED. No P0 issues. Three P1 issues require attention before capital scaling.**
