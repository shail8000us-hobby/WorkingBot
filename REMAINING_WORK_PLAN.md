# Remaining Work Plan — Post-Audit

**Date:** March 1, 2026  
**Context:** Following the full production audit and 25-item fix session  
**Status:** All blockers and high-priority items fixed. This document covers what remains.

---

## First: Corrections to the Audit Report

Two items were marked "not fixed" in the old audit report — but the code **already has these fixes**:

### H4 — WebSocket queue `put_nowait` — ✅ ALREADY FIXED
`async_ws_manager.py` line 747: `self._message_queue.put_nowait(message)` — already uses non-blocking put. No action needed.

### H7 — FillMonitor double sleep — ✅ ALREADY FIXED
`fill_monitor.py` lines 106–108 have an explicit comment:
```python
# FIX H7: This is the only sleep between iterations (BaseMonitor._run has no sleep)
# Correct behavior — one sleep per iteration
await asyncio.sleep(self.check_interval)
```
No action needed.

---

## Actual Remaining Items

| ID | Issue | Risk to Fix | Risk of Not Fixing | Priority | Status |
|----|-------|-------------|-------------------|----------|--------|
| M3 | Shared rate limiter across API clients | Medium | Low–Medium | 3 | ✅ Fixed |
| L2 | No file locking on `save_yaml` | Very Low | Extremely Low | 4 | ✅ Fixed |
| A3 | Missed grid check (multi-step price move) | Medium | Medium | 2 | ✅ Fixed |
| A4 | Adaptive reference price | Low | Low | 5 (user said leave it) | ⏭️ Skip |

---

## Item M3 — Shared Rate Limiter

### Current Behaviour
Each `UnifiedAPIClient` instance creates its own `RateLimiter(max_requests=10, window=1)`.  
Three components (GridBot, RecoveryEngine, ReconciliationEngine) each have independent limiters.

### Actual Risk Assessment
Delta Exchange limit: **10,000 weight units per 5 minutes** ≈ 33 requests/sec.  
Each component is capped at 10 req/sec internally. Combined worst case: ~30 req/sec.  
**Risk of hitting exchange rate limit: Low in normal operation, Medium under recovery + reconciliation + normal trading simultaneously.**

### Is it risky to fix?
**Medium risk.** Requires:
1. Creating a module-level singleton rate limiter
2. Changing `UnifiedAPIClient.__init__` to accept an optional shared limiter
3. Updating all 3 call sites that instantiate `UnifiedAPIClient`

If done wrong: all API calls from all components could serialize through one limiter, slowing everything down unnecessarily.

### Implementation Plan

**Step 1 — Create shared limiter module** (`bot/api/shared_rate_limiter.py`):
```python
from bot.api.rate_limiter import RateLimiter
import threading

_lock = threading.Lock()
_shared_limiter = None

def get_shared_rate_limiter() -> RateLimiter:
    global _shared_limiter
    with _lock:
        if _shared_limiter is None:
            # 25 req/sec shared — leaves headroom vs 33/sec exchange limit
            _shared_limiter = RateLimiter(max_requests=25, window=1)
    return _shared_limiter
```

**Step 2 — Update `UnifiedAPIClient.__init__`**:
```python
# Accept optional shared limiter; fall back to private one if not provided
self.rate_limiter = shared_limiter or RateLimiter(max_requests=10, window=1)
```

**Step 3 — Update call sites** (find them first):
```bash
grep -rn "UnifiedAPIClient(" bot/ --include="*.py"
```
Pass `shared_limiter=get_shared_rate_limiter()` to each instantiation.

**Step 4 — Test**:
- Start bot and trigger a recovery (force missed grid) while reconciliation runs
- Monitor API response codes for 429 (rate limit exceeded)
- Check logs for rate limiter hold times

### Verdict
**Safe to do, but not urgent.** Current independent limiters provide adequate protection for normal operation. Only do this if you observe 429 errors in production.

---

## Item L2 — File Locking on `save_yaml`

### Current Behaviour
`config/loader.py` line 130:
```python
with open(output_path, 'w') as f:
    yaml.dump(data, f, ...)
```
No lock. If Guardian, bot, and WebUI all try to save config simultaneously, one might read a half-written YAML.

### Actual Risk Assessment
Config saves are rare (manual updates only, not automated). Three processes saving config simultaneously is nearly impossible in practice.  
**Risk of corruption: Extremely low (< 1% chance under normal use).**

### Is it risky to fix?
**Very low risk.** 2-line change. Uses standard `fcntl.flock` which is available on macOS and Linux.

### Implementation Plan

**Change in `config/loader.py` `save_yaml()` method:**
```python
import fcntl

def save_yaml(self, config: RootConfig, output_path: Union[str, Path]):
    output_path = Path(output_path)
    data = config.dict(exclude_none=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    lock_path = output_path.with_suffix('.lock')
    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)  # Exclusive lock
        try:
            with open(output_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)  # Release lock
    
    print(f"✅ Configuration saved to: {output_path}")
```

**Note:** `fcntl` is Unix-only. If Windows support is ever needed, use `msvcrt.locking` or the `filelock` package instead.

### Verdict
**Trivially safe to do.** 6 lines of code change. Can be done any time without risk.

---

## Item A3 — Missed Grid Check for Multi-Step Price Moves

### The Gap (per user's direction: "don't code, suggest logic")
When market drops 2+ grid steps quickly (e.g., $1,000 move with $500 step), the recovery system only fires on the FIRST missed grid. The second and third missed grids are NOT caught because:
- Recovery runs after GO signal resumes
- Each recovery cycle only processes one level at a time
- Fast multi-step moves happen in < 1 second, before recovery can queue them

### Suggested Logic (not coded — user decision)

**Where to add it:** `async_gridbot.py` → `_retry_missed_grid_orders()` or a new `_check_missed_grids_on_resume()` method called at the start of each GO signal handler.

**Algorithm:**
```
1. On receiving GO signal (guardian resumes trading):
   a. Get current market price from WebSocket (last_price)
   b. Get last_known_buy_level from bot state
   c. Calculate how many grid steps market has moved: 
      steps_missed = floor((last_known_buy_level - current_price) / grid_step)
   
2. If steps_missed >= 2:
   a. Build a list of ALL missed grid levels:
      missed_levels = [last_known_buy_level - (i * grid_step) for i in range(1, steps_missed + 1)]
      Filter: only include levels below current price (would have triggered)
      Filter: only include levels above lower_bound
      Filter: skip levels where a position already exists
   
3. For each missed level (from highest to lowest — closest to current price first):
   a. Check max_positions limit — stop if already at max
   b. Place a MARKET BUY for lot_size at that level (same as existing recovery)
   c. Register fill with entry_price SNAPPED to grid level (A1 fix already handles this)
   d. Wait for fill confirmation before proceeding to next level
   e. Apply cooldown between fills (use existing recovery cooldown)
   
4. After all missed levels filled: resume normal grid operation
```

**Key safety guardrails to include:**
- Hard cap: Never fill more than `max_positions - current_positions` missed grids
- Price check: Before each fill, re-verify current price is still below the missed level (don't buy if price has already bounced above it)
- Cooldown: 500ms minimum between each missed grid fill
- Max missed grids per recovery cycle: cap at 5 to prevent runaway buying

**Where existing infrastructure helps:**
- `_retry_missed_grid_orders()` already has the structure for this
- `_ensure_grid_coverage()` already does position gap analysis
- Recovery engine saga (`fill_processing_saga.py`) already handles grid-snap (A1 fix)
- The `_seen_recovery_sagas` dedup set (A1 fix) prevents double-processing

**Risk of implementing:** Medium — touching recovery flow which is critical path. Requires careful testing with simulated multi-step price moves.

### Verdict
**User's call — the infrastructure is ready, only the multi-level loop needs adding.** If you want to proceed, this is ~30 lines of code inside the existing recovery method.

---

## Item A4 — Adaptive Reference Price

**Status: User said "leave it".** No action. The current behavior (first BUY placed at ref - step regardless of how far market has moved) is acceptable given the recovery system handles re-entry.

---

## Priority Order for Implementation

If you decide to proceed with any remaining work:

1. **L2 first** — 6 lines, zero risk, can be done in 5 minutes
2. **A3 second** — Most trading impact, medium risk, requires testing  
3. **M3 third** — Only needed if you observe 429 rate-limit errors in production logs
4. **A4** — Skip (user direction)

---

## Pre-Implementation Checklist

Before touching any remaining items:

- [ ] Verify bot has been running in production for at least 24 hours without issues
- [ ] Check logs for any 429 (rate limit) errors: `grep "429\|rate.limit" bot.live.log`
- [ ] Run a manual recovery test: stop bot, let price move 2+ steps, restart and verify recovery
- [ ] Confirm monitoring_snapshot.json is being written correctly
- [ ] Backup current state: `git stash` or create a branch before starting

---

## Quick Risk Summary

| Item | Lines Changed | Files Touched | Can Break | Verdict |
|------|--------------|---------------|-----------|---------|
| L2 | ~6 | 1 | Almost nothing | ✅ Do it anytime |
| M3 | ~20 | 4+ | API call rate behavior | ⚠️ Only if 429s seen |
| A3 | ~30 | 1 | Recovery flow (critical path) | ⚠️ Test thoroughly first |
| A4 | 0 | 0 | Nothing | ⏭️ Skip |

**Overall: Not risky if done carefully and in order. L2 is a no-brainer. A3 needs a dedicated test session.**

---

## Refactoring Plan — `async_gridbot.py` (5,700+ lines)

### The Problem
`bot/strategy/async_gridbot.py` is the single largest file in the project at 5,700+ lines. It handles:
- WebSocket connection lifecycle
- Fill processing and saga orchestration
- Grid order placement logic
- Guardian signal handling and recovery
- Position reconciliation triggers
- Health monitoring, heartbeats, and snapshot writing
- Initial entry logic and grid seeding
- Price staleness detection and REST fallback
- Order verification and dedup
- 15+ concurrent async tasks

This makes it:
- **Hard to reason about** — changes in one concern can silently break another
- **Hard to test** — no way to test grid logic without spinning up the full event loop
- **Merge-conflict prone** — any two changes will likely touch the same file
- **Slow to load in editors** — IDE features degrade at this file size

### Proposed Module Split

The file naturally breaks into 7 focused modules. Each module is a class or set of functions that receives its dependencies via constructor injection (no globals):

```
bot/strategy/
├── async_gridbot.py          → Slim orchestrator (~500 lines)
│                                Only __init__, run(), shutdown()
│                                Wires modules together, owns the event loop
│
├── modules/
│   ├── grid_calculator.py     → Already extracted ✅
│   ├── ws_lifecycle.py        → WebSocket connect/reconnect/fallback (~400 lines)
│   ├── fill_processor.py      → Fill handling, saga dispatch, dedup (~600 lines)
│   ├── grid_engine.py         → Entry logic, grid seeding, order placement (~800 lines)
│   ├── guardian_handler.py    → Signal reading, STOP/GO transitions, 
│   │                            missed order retry, A3 multi-step (~300 lines)
│   ├── health_monitor.py      → Heartbeat, snapshot, staleness checks (~400 lines)
│   └── reconciliation.py      → Periodic recon trigger, position sync (~300 lines)
```

### Extraction Order (safest to riskiest)

1. **`guardian_handler.py`** — Fully self-contained: reads a file, manages a buffer. Zero coupling to order placement. Extract `_check_guardian_transition`, `_retry_missed_grid_orders`, `_fill_multi_step_missed_grids`, `_read_guardian_signal`.

2. **`health_monitor.py`** — Reads state, writes JSON. No side effects on trading. Extract `_write_monitoring_snapshot`, `_health_check_loop`, heartbeat logic.

3. **`ws_lifecycle.py`** — WebSocket connect/disconnect/fallback/reconnect logic. Already partially isolated behind `UnifiedAPIClient`.

4. **`fill_processor.py`** — Fill callback, saga orchestration, fill dedup, `_process_missed_fill`. This is the highest-risk extraction because it touches order state.

5. **`grid_engine.py`** — Entry placement, `_check_and_place_entry_order`, `_ensure_grid_coverage`, grid seeding. Core trading logic — extract last.

### Extraction Pattern (for each module)

```python
# 1. Create the new module with explicit dependencies
class GuardianHandler:
    def __init__(self, position_actor, order_actor, grid_calc, 
                 signal_file_path, mode, grid_step, max_positions, lot_size):
        ...

# 2. In async_gridbot.py, instantiate it
self.guardian = GuardianHandler(
    position_actor=self.position_actor,
    order_actor=self.order_actor,
    grid_calc=self.grid_calc,
    signal_file_path=self._guardian_signal_file,
    mode=self.mode,
    grid_step=self.grid_step,
    max_positions=self.max_positions,
    lot_size=self.lot_size
)

# 3. Replace inline calls
# Before: await self._check_guardian_transition()
# After:  await self.guardian.check_transition()
```

### Rules During Refactoring

1. **One module at a time** — extract, test, commit, then move to next
2. **No behavior changes** — pure structural moves. If a bug is found, fix it in a separate commit
3. **Keep backward compat** — the orchestrator's public API (`run()`, `shutdown()`) must not change
4. **Integration test after each extraction** — start bot, verify grid places, verify fills, verify recovery
5. **Git branch** — do all refactoring on a `refactor/split-gridbot` branch, merge only after full live test

### Estimated Effort

| Module | Lines | Risk | Time |
|--------|-------|------|------|
| guardian_handler.py | ~300 | Low | 1 hour |
| health_monitor.py | ~400 | Low | 1 hour |
| ws_lifecycle.py | ~400 | Medium | 1.5 hours |
| fill_processor.py | ~600 | High | 2 hours |
| grid_engine.py | ~800 | High | 2.5 hours |
| Orchestrator trim | ~500 remain | Medium | 1 hour |
| **Total** | | | **~9 hours** |

### When to Do This

- **Not now.** The bot is about to go into production. Refactoring is best done during a scheduled maintenance window.
- **Trigger:** When the next feature request requires touching 3+ concerns inside `async_gridbot.py`, or when a bug takes >30 minutes to locate due to file size.
- **Prerequisite:** Set up at least a basic integration test harness (simulated fills, mock WebSocket) before starting extractions.

