# Profit Target Exit + Structured Clean Restart — Implementation Plan

**Created:** 2026-04-30  
**Branch:** SSR  
**Status:** Planning  
**Priority:** Phase 1 first, Phase 2 only after Phase 1 is stable in live trading

---

## Design Principles

> **Clarity > Execution Cost.**  
> Never trade system integrity for small fee savings.  
> The MMM algo is calibrated for a clean, symmetric book. Mixed-entry, mixed-strike, partial-lot books break BE engine, gamma geometry, arbiter signals, and P&L tracking. Do not introduce structural distortion to save execution fees.

**Smart Trim is explicitly rejected.** Reasons:
- Breaks MMM assumption of clean symmetric structure → BE, gamma, arbiter may misfire
- Mark price used for trim decisions ≠ real execution price → wrong selection bias
- Partial lot closing reintroduces P&L tracking bugs (GAP-1 to GAP-42)
- Old positions + new restart logic = undefined system state ("Frankenstein book")
- After trim, position book cannot be cleanly visualized → system loses interpretability
- Gamma and breakeven geometry become unreliable after mixed-entry trimming

**Two valid modes only:**
- **Phase 1 — Hard Exit**: Close everything. Session ends. Profit locked.
- **Phase 2 — Structured Clean Restart**: Close everything cleanly, wait for full confirmation, then start a fresh symmetric entry with operator-specified lots and premium. Zero ambiguity. Clean book. All subsystems start from known state.

---

## Phase 1 — Hard Profit Target Exit

### Goal
When `compute_current_total_pnl(session)` >= `profit_target_usd × (1 + buffer%)`, call `_auto_close_all()` and close the session cleanly.

### Why buffer?
The P&L at trigger time includes **unrealized MTM**. When buy-back orders execute you face:
- Bid-ask spread (you buy at the ask, not mark)
- Slippage on simultaneous multi-lot close
- Price movement during fill time

Triggering at `target × 1.08` (default 8% buffer) means you realize approximately `target` after fills settle.

### New Params

| Param | Default | Hot-Reload | Description |
|---|---|---|---|
| `profit_target_usd` | `0.0` | ✅ Yes | Dollar target. `0` = disabled. |
| `profit_target_buffer_pct` | `8.0` | ✅ Yes | Overshoot buffer % to account for close slippage. |

### Logic — Where to Add

**File:** `mmm_monitor.py` — inside `_heartbeat()`, after fill sync + guardian checks, before regime/trigger evaluation.

```python
async def _check_profit_target(self, session, ce_now, pe_now):
    target = session.get('params', {}).get('profit_target_usd', 0.0)
    if not target or target <= 0:
        return False

    buffer_pct = session.get('params', {}).get('profit_target_buffer_pct', 8.0)
    trigger_at = target * (1 + buffer_pct / 100.0)

    current_pnl = compute_current_total_pnl(session)
    if current_pnl < trigger_at:
        return False

    restart_enabled = session.get('params', {}).get('profit_target_restart_enabled', False)
    if restart_enabled:
        return await self._execute_clean_restart(session, ce_now, pe_now, current_pnl)

    # Hard exit
    log_activity(session, 'profit_target_hit', {
        'target_usd': target,
        'trigger_at': trigger_at,
        'current_pnl': current_pnl,
        'mode': 'hard_exit',
    })
    await self._auto_close_all(session, ce_now, pe_now, reason='profit_target')
    self._running = False
    return True
```

Call site in `_heartbeat()`:
```python
# After fill sync + guardian, before regime block
if await self._check_profit_target(session, ce_now, pe_now):
    return
```

### Activity Types
- `profit_target_hit` — hard exit triggered
- Category: `safety` (same as `max_loss_hit`)
- Fields: `target_usd`, `trigger_at`, `current_pnl`, `mode`

### Telegram Alert (Hard Exit)
```
🎯 Profit target hit — squaring off all positions
Target: $30.00 | Trigger at: $32.40 (8% buffer)
Current P&L: $33.12 | Session: {session_id}
```

### UI — MMMSettingsDialog.js
New section under **Risk Controls**:
```
🎯 Profit Target
  profit_target_usd             [numeric, 0=disabled]
  profit_target_buffer_pct      [numeric, default 8.0]
  profit_target_restart_enabled [bool toggle — enables Phase 2 clean restart]
```

### Sealed Tests (Phase 1, min 6)

| Test | What it verifies |
|---|---|
| `TestProfitTargetDisabled` | `profit_target_usd=0` → no action even when P&L is high |
| `TestProfitTargetNotYetHit` | P&L = target - $1 → no action |
| `TestProfitTargetHitHardExit` | P&L >= trigger → `_auto_close_all` called, `_running=False` |
| `TestProfitTargetBufferMath` | 8% on $30 = trigger at $32.40 |
| `TestProfitTargetActivityLog` | `profit_target_hit` logged with correct fields |
| `TestProfitTargetUsesNetPnL` | `compute_current_total_pnl` used (includes fees) |

### Files Touched (Phase 1)
- `mmm_monitor.py` — `_check_profit_target()` + heartbeat call
- `mmm_state.py` — 2 params in `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS`
- `mmm_config.py` — validators + descriptions
- `mmm_activity.py` — `profit_target_hit` in `ACTIVITY_TYPES` + `ACTIVITY_CATEGORIES`
- `MMMSettingsDialog.js` — new UI section
- `tests/test_sealed_audit_fixes.py` — 6 sealed tests

**Estimated: ~100 lines, 1 session**

---

## Phase 2 — Structured Clean Restart

> **Do not build until Phase 1 has been live-tested in at least 2 real sessions.**

### Goal
After profit target is hit: close ALL positions cleanly, wait for full fill confirmation, then execute a fresh symmetric entry with operator-specified lot count and premium. Every subsystem (BE engine, gamma, arbiter, trigger snapshots, P&L tracking) starts from a clean known state.

### Why Full Close is Non-Negotiable
- Clean close guarantees zero residual exposure before re-entry
- Every subsystem resets to a known state — no inherited geometry, no stale signals
- P&L accounting is unambiguous: profit from Run 1 is realized, Run 2 starts at $0
- Operator can see exactly what happened: close P&L vs. restart entry P&L are separate
- Yes, there is execution cost. That cost buys certainty. **Clarity > execution cost.**

### New Params (Phase 2)

| Param | Default | Hot-Reload | Description |
|---|---|---|---|
| `profit_target_restart_enabled` | `False` | ✅ Yes | Enables structured clean restart mode. |
| `profit_target_restart_lots_per_side` | `50` | ✅ Yes | Lot count for fresh re-entry on each side. |
| `profit_target_restart_target_premium` | `50.0` | ✅ Yes | Premium to target for fresh entry on each side. |
| `profit_target_restart_max_count` | `3` | ✅ Yes | Max restarts per session (then falls back to hard exit). |

### Clean Restart Execution Flow

```
1. Profit target hit, restart_enabled=True
2. Check fallback guards (see below) — go to hard exit if any fires
3. Log activity: profit_target_restart_initiated (pnl_at_trigger, restart_count)
4. Telegram alert: "Profit target hit — closing all, will restart"
5. _auto_close_all() — full square-off, all CE + PE + perp + reverse positions
6. Wait for fill sync to confirm ALL positions closed (max 90s polling loop)
   - If not all closed after 90s → abort restart, hard exit, alert operator
7. Increment _restart_count, append to _restart_log
8. Full state reset (see below)
9. Set desired_ce_premium = restart_target_premium
   Set desired_pe_premium = restart_target_premium
   Set lot_size_ce = restart_lots_per_side
   Set lot_size_pe = restart_lots_per_side
10. Call _initial_entry() — identical to a fresh session start
11. Log activity: profit_target_restarted (new_premium, new_lots, restart_count)
12. Telegram alert: "Clean restart complete — new entry placed"
```

### Fallback Conditions (fall back to Phase 1 hard exit)

| Condition | Reason |
|---|---|
| `_restart_count >= restart_max_count` | Prevent infinite restart loop |
| `current_DTE < 2 hours` | Too close to expiry — not worth re-entry |
| Not all positions confirmed closed within 90s | Cannot start fresh with residual exposure |
| `restart_target_premium < params.get('replenish_min_premium', 20)` | Premium too thin to re-enter |

### Full State Reset After Close (before re-entry)

| Field | Action |
|---|---|
| `session['ce']['positions']` | Cleared (all confirmed closed by fill sync) |
| `session['pe']['positions']` | Cleared |
| `session['ce']['active_lots']` | Reset to 0 |
| `session['pe']['active_lots']` | Reset to 0 |
| `session['adjustment_history']` | Cleared |
| `session['_trigger_snapshots']` | Cleared (re-anchored on fresh entry) |
| `session['_profit_ratchet_hwm']` | Reset to 0 |
| `session['_be_accel']` | Reset |
| `session['_breakeven_zone']` | Reset |
| `session['realized_pnl']` | **NOT reset** — Run 1 P&L is preserved in history |
| `session['_restart_count']` | Incremented |
| `session['_restart_log']` | Entry appended |
| `session['_profit_target_total_extracted']` | Incremented by pnl_at_trigger |
| All params | **NOT reset** — operator params preserved |
| All safety limits | **NOT reset** — max_loss, margin limits preserved |

### State Fields Added (Phase 2)

| Field | Location | Notes |
|---|---|---|
| `session['_restart_count']` | session | Number of clean restarts fired |
| `session['_restart_log']` | session | `[{at, pnl_at_close, new_lots, new_premium, restart_count}]` |
| `session['_profit_target_total_extracted']` | session | Cumulative USD locked in across all restarts |

### Activity Types (Phase 2)
- `profit_target_restart_initiated` — close triggered, fields: `pnl_at_trigger`, `restart_count`
- `profit_target_restarted` — fresh entry placed, fields: `new_lots`, `new_premium`, `restart_count`
- `profit_target_restart_fallback` — guard fired, fell back to hard exit, fields: `reason`

### Telegram Alerts (Phase 2)
```
🎯 Profit target hit — closing all for clean restart (#2)
P&L locked: $33.12 | Cumulative extracted: $63.00
Closing all positions now...

✅ Clean restart complete
New entry: 50 lots CE @ $50 | 50 lots PE @ $50
Restart #2 of 3 max
```

### UI Additions (Phase 2, under same 🎯 Profit Target section)
```
  --- Clean Restart ---
  profit_target_restart_enabled           [bool toggle]
  profit_target_restart_lots_per_side     [numeric, default 50, HOT]
  profit_target_restart_target_premium    [numeric, default 50.0, HOT]
  profit_target_restart_max_count         [numeric, default 3]
```

### Sealed Tests (Phase 2, min 8)

| Test | What it verifies |
|---|---|
| `TestCleanRestartRouting` | `restart_enabled=True` routes to restart, `False` routes to hard exit |
| `TestCleanRestartFallbackMaxCount` | `_restart_count >= max` → hard exit |
| `TestCleanRestartFallbackDTE` | DTE < 2h → hard exit |
| `TestCleanRestartFallbackCloseTimeout` | Positions not confirmed closed in 90s → abort, hard exit |
| `TestCleanRestartFallbackMinPremium` | `restart_target_premium < min` → hard exit |
| `TestCleanRestartStateReset` | All positions/lots/history cleared; realized_pnl preserved; params intact |
| `TestCleanRestartLogAccumulates` | `_restart_log` entry added, `_profit_target_total_extracted` updated |
| `TestCleanRestartParamOverride` | `desired_ce/pe_premium` and `lot_size_ce/pe` updated to restart values |

---

## Build Order

```
Phase 1
  [x] Plan written
  [ ] mmm_state.py — 2 params
  [ ] mmm_config.py — validators
  [ ] mmm_activity.py — profit_target_hit
  [ ] mmm_monitor.py — _check_profit_target() + heartbeat call
  [ ] MMMSettingsDialog.js — UI section (with restart_enabled toggle)
  [ ] test_sealed_audit_fixes.py — 6 sealed tests
  [ ] Live test: 1 paper session, then 2 real sessions
  [ ] mmm_workdone_march.md — session log entry

Phase 2 (only after Phase 1 live-tested)
  [ ] mmm_state.py — 4 new params + 3 new state fields
  [ ] mmm_config.py — validators
  [ ] mmm_activity.py — 3 new activity types
  [ ] mmm_monitor.py — _execute_clean_restart() + fallback guards + close-confirm loop
  [ ] MMMSettingsDialog.js — clean restart param group
  [ ] test_sealed_audit_fixes.py — 8+ sealed tests
  [ ] Live test: 2 real sessions with restart_max_count=1
  [ ] mmm_workdone_march.md — session log entry
```

---

## Open Questions Before Phase 2 Build

1. After restart, should `profit_target_usd` for the next run be the **same** ($30) or a **scaled-down** value (e.g., 50% — "Run 1 gave $30, now just grab $15 more")?
2. Should `_profit_target_total_extracted` be shown on the main MMM dashboard?
3. If `_initial_entry()` fails after clean close (e.g., no valid strikes), should it retry or alert and stop?

---

*File: `tasks/PROFIT_TARGET_EXIT_PLAN.md` — maintained alongside implementation*
