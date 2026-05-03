# Last 3 Sessions — Auto-maintained. Full log: mmm_workdone_march.md

---

## 2026-05-03 — Core Design Fix: Remove OCS auto-stop, implement expiry-based graceful exit

**Problem** (root cause of mmm03may26-3 and mmm03may26-2 unexplained stops):
- OCS (One-Side-Close) guard was auto-stopping in two wrong scenarios:
  1. When both sides fully closed (normal balanced hedge state) — line 2264 `self.stop('Both sides fully closed')`
  2. Off-hours with one side closed and other side empty — line 2498 `self.stop('off-hours auto-stop')`
- User requirement: algo should ONLY auto-stop on ONE condition: **contracts no longer exist on exchange** (expiry passed)
- All other auto-stop logic violates the core design

**Three fixes applied** (`mmm_monitor.py`):
1. **Remove both-sides-closed auto-stop (line 2277)**: Both sides closing = normal balanced state, not a stop condition. Changed to comment.
2. **Add expiry-based graceful stop (line 1567-1579)**: Check `minutes_to_expiry` in main heartbeat. If <= 0, gracefully close all positions and stop. This is the ONLY legitimate auto-stop.
3. **Redesign OCS fallback (line 2403-2490)**: When replenish fails, PAUSE (not STOP), both in awake and off-hours. Let watchdog keep retrying replenish with `ocs_emergency=True` flag until: hedge restored OR expiry reached OR user stops.

**Key principle**: Algo runs continuously until 5:30 PM IST contract expiry, using replenish system to maintain hedge balance. Watchdog retries replenish indefinitely. Only stops on: contract expiry OR user manual stop.

**Files**: `mmm_monitor.py` | **Tests**: To verify with live sessions (mmm03may26-4+)

---

## 2026-05-01 — Fix: PE stuck at 0 active / 250 frozen (shift lots=0 unfreeze)

**Root cause** (`mmm_monitor.py` `if lots <= 0: return` guard, formerly line 6650):
- `_auto_promote_atm_strike()` promotes frozen PE lots to active. Proactive shift fires, freeze runs, then `remaining_cap = max(200−250, 0) = 0` → lots=0. Old guard returned WITHOUT rolling back the freeze → all positions stay 'shifted', active_lots=0 every beat.

**Fix**: Before the `return`, restore positions at `old_strike` from 'shifted' → 'active' + recompute. Same pattern as the sell-failure rollback. Activity `shift_lots_zero_unfreeze` added.

**Files**: `mmm_monitor.py`, `mmm_activity.py` | **Tests**: 1788 passing (baseline 1785 + 3 new)

---

## 2026-05-01 — mmm01may26-1 post-mortem: position cap bypass + combined size check + regime default

Three bugs from the 290-lot catastrophic shift in session mmm01may26-1 (P&L: +$9.25 → -$49.67).

**Bug #1 — Proactive shift fallback bypassed position cap** (`mmm_monitor.py`):
- PE had 303 frozen lots (cap=300). `calculate_lots_to_sell` returned 0 (cap exceeded). Fallback at ~line 6524 seeded 290 from `frozen_lots` without re-checking the cap. Delta-neutral match then saw `min(290, 300, inflate_cap)=290`.
- Fix 1a: After `lots = fallback`, added cap re-check using `session[side]['total_lots']`. If `total_lots + lots > max_per_side` → caps to `max(max_per_side - total_lots, 0)`. Logs `proactive_shift_fallback_cap`.
- Fix 1b: Delta-neutral match now uses `remaining_cap = max(max_per_side - total_lots, 0)` instead of raw `max_per_side`.

**Bug #2 — No combined CE+PE position circuit breaker** (`mmm_safety.py`):
- New `check_combined_position_size()`: fires `stop_adjustments` at `max_per_side × 2`, warning at 80%. Called from `run_all_checks()`.

**Config fix — regime_enabled default → True** (`mmm_state.py`):
- `DEFAULT_PARAMS['regime_enabled']` was `False`. Vol/gamma/trend regime was off the entire session. Changed to `True`.

**Activity registry** (`mmm_activity.py`): registered `proactive_shift_fallback_cap` + `arbiter_suppressed_double_sell` (latter was missing from prev session).

**Files**: `mmm_monitor.py`, `mmm_safety.py`, `mmm_state.py`, `mmm_activity.py`, `tests/test_sealed_audit_fixes.py` | **Tests**: 1781 passing (baseline 1773 + 8 new)

---

## 2026-05-01 — Arbiter + proactive shift double-sell guard (mmm01may26-1 post-mortem)

Session mmm01may26-1 sold 310 PE-75000 lots in 11 seconds on flat market — velocity violation.

**Root cause**: Two independent paths fired for the same side in one beat:
1. `_proactive_shift_scan` (line ~3335) sees PE premium < shift_threshold → sells (225 lots)
2. Arbiter (line ~3464) evaluates next → `_check_hedge_decay_shift` fires for same PE condition → `_arbiter_shift_bypass_cooldown=True` bypasses 120s shift_cooldown → sells again (85 lots)

**Fix** (`mmm_monitor.py`, 3 locations):
- `_process_strike_shift`: sets `session[f'_shift_placed_this_beat_{side}'] = True` on fill success
- Before `_proactive_shift_scan`: pops `_shift_placed_this_beat_ce/pe` each beat
- Arbiter execution block: `_double_sell` guard — if `defensive_shift` + `_shift_placed_this_beat_{arbiter_side}` is True → suppresses `_execute_arbiter_decision`, logs `arbiter_suppressed_double_sell`; `_arbiter_last_action_at` still recorded for next-beat cooldown

**Non-defensive_shift actions (gamma, margin) are not suppressed.** Arbiter cooldown bypass still works when proactive shift was blocked (no fill = flag not set).

**Files**: `mmm_monitor.py` (3 locations), `tests/test_sealed_audit_fixes.py` | **Tests**: 1229 sealed passing (baseline 1225 + 4 new: `TestArbiterDoubleSellPrevention` ×4)

---

## 2026-05-01 — Scissor exit redesign: paired groups + fill-sync + market cleanup + P&L report

**Scissor exit (✂️) completely overhauled** (`mmm_exit_all.py`):
- **Grouped paired close**: 2 CE + 2 PE close simultaneously per group (ATM-closest first). Delta stays balanced — market movement during exit offsets both legs. `fill_timeout=25s` (was 60s). Heartbeat per round + per group.
- **Fill sync after rounds**: `_exit_fill_sync()` pulls exchange fills → sets `_fill_confirmed`. Source of truth for "did exchange execute the close?"
- **Market cleanup**: `_final_market_cleanup()` fires market orders (reduce_only=True) for any position without `_fill_confirmed` after fill sync. Safe with manual/other-algo positions. Second fill sync confirms.
- **P&L report**: `_exit_report_final_pnl()` fires while monitor alive → Telegram + websocket event with net realized P&L, premium collected, buyback cost.
- **Kill switch (⚡) unchanged**: market cleanup phase skipped for kill switch.

**Files**: `mmm_exit_all.py`, `mmm_watchdog.py`, `mmm_close_at_5.py` | **Tests**: 1785 passing

---

## 2026-05-01 — mmm01may26-3 exit failure investigation + exit reliability fixes

Exit hung → zero close orders placed → watchdog killed session (90s threshold vs ~200s needed).
Root cause: `FILL_TIMEOUT=60s` × 10 positions ÷ 3 concurrent = 200s needed; watchdog threshold = `30s×3=90s`.

**3 fixes applied:**
- `mmm_watchdog.py`: EXITING sessions get 300s floor on beat timeout (was same 90s as RUNNING)
- `mmm_exit_all.py`: `_health.record_beat()` at start of each exit round (keeps watchdog alive during multi-round exits)
- `mmm_close_at_5.py` + `mmm_exit_all.py`: `close_position()` gains optional `fill_timeout` param; exit passes 25s cap (was defaulting to 60s)

**Files**: `mmm_watchdog.py`, `mmm_exit_all.py`, `mmm_close_at_5.py` | **Tests**: 1785 passing (no regressions)

---

## 2026-04-30 (rev3) — Audit + seal: profit ratchet fixes for mmm30apr26-1

External AI audit work validated and sealed. Both critical fixes correctly implemented; 1 false-positive non-issue identified; 1 stale comment corrected; 3 new sealed tests added.

**What the external AI did correctly:**
- **Issue 2 fix**: Profit ratchet block (`mmm_monitor.py:3645`) moved outside `if not _skip_to_pnl:` guard. Now fires even when safety/whipsaw/regime/cooldown blocks skip adjustments.
- **Issue 1 fix**: `session.pop('_arbiter_decision_active', None)` added to `_row_to_session()` in `mmm_storage.py:471`. Prevents a mid-beat-saved `True` flag from blocking the ratchet after session restore.

**What the external AI got wrong (Issue 3):** Diagnosed 405 errors on the manual ratchet API. Log inspection shows no such errors — "405" in logs are timestamps/socket.io IDs. Route at `mmm_api.py:8539` is correctly registered. No code change needed.

**Corrections made this session:** Stale `line 3707` comment in `mmm_storage.py` updated to `line ~3656`. Added 3 sealed tests: `test_ratchet_outside_skip_to_pnl_guard`, `TestArbiterFlagClearedOnLoad::test_flag_cleared_in_row_to_session`, `TestArbiterFlagClearedOnLoad::test_flag_not_in_monitor_heartbeat_reset_only`.

**Files**: `mmm_storage.py`, `tests/test_sealed_audit_fixes.py` | **Tests**: 1219 sealed passing (baseline 1216 + 3 new)

---

