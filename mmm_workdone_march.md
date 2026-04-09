# MMM Algo — Work Done (March 2026)

> **MANDATORY**: Every AI session that touches MMM code must READ this file at the start and ADD a new entry at the end.
> Format: `## YYYY-MM-DD — <short title>` followed by bullet points of what changed and why.

---

## 2026-03-03 — Cleanup + Lot Recycling Plan

- Added detailed lot recycling implementation plan (`MMM_LOT_RECYCLING_IMPLEMENTATION_PLAN.md`)
- Noted API cache fix in docs
- Pre-professional-cleanup snapshot

---

## 2026-03-07 — User Requested Commit

- General state save

---

## 2026-03-10 — Improvement Plan P1 + T-plan implementations

- `feat(mmm)`: implemented items from MMM_IMPROVEMENT_PLAN: P1-A/B/D, IMP-3/4/5/6/8/9/10/12
- `fix`: calculate_lots_to_sell unpacking mismatch in mmm_monitor
- `chore`: perp pre-adjustment delta projection (T4-3)
- `fix`: 2 audit bugs + completed T-plan items

---

## 2026-03-11 — Operator Strike Controls + Scaler + 5 Deep Audit Fixes

- `feat`: Operator Strike Controls — Set Active Strike, Close Strike, Position Inject endpoints
- `feat`: MMM Scaler module added
- `fix(mmm)`: 5 bugs found in deep audit (mmm_api, mmm_engine)
- `fix`: WebUI performance regression and PE orphan adoption bug

---

## 2026-03-12 — ATM Shield + Audit Fixes + Wind-Down Corrections

- `feat`: ATM Shield — proactive close & retreat on ATM proximity
- `fix(mmm)`: wind_down_on_atm and close_at_atm use active_strike not original_strike
- `fix(mmm)`: partial fill, ATM guard, regime, shift cooldown, whipsaw audit fixes

---

## 2026-03-14 — Comprehensive Sealing + Observer Pattern

- Comprehensive sealing across MMM modules
- MMM observer pattern implemented
- Options improvements

---

## 2026-03-15 — Close-at-5 Watcher + TTL Fix + New Modules

- `feat(mmm)`: close-at-5 watcher (automatic position closing at premium threshold)
- TTL fix for stale being-closed flags
- Settings 400 error fix
- Patience, breakeven, gamma modules added

---

## 2026-03-17 — Gamma Severity Multiplier + Patience Overhaul

- `feat(mmm,patience)`: enable gamma severity multiplier by default
- Patience UI/algorithm overhauled

---

## 2026-03-18 — Trade Transparency System (4 phases) + Global Exit All

- `feat(mmm)`: Trade Transparency System Phase 1+2 — audit log, attribution buckets (pnl_initial, pnl_adjustment, pnl_harvest, pnl_recycle)
- `feat(mmm)`: Phase 3 — Trade Audit tab in MMMDashboard
- `feat(mmm)`: Phase 4 — perp hedge, Mode B, reconcile alert in audit panel
- `fix(mmm)`: audit panel data bugs — key mismatches + 409 error
- `fix(mmm)`: suppress audit mismatch noise for pre-deployment sessions
- `feat(mmm)`: Global Exit All endpoint + live bid/ask price feed on dashboard
- `fix(mmm)`: TDZ error — move live-price useEffect after fullSession declaration

---

## 2026-03-19 — Short Straddle DTE Preset

- `feat(mmm)`: SHORT_STRADDLE dynamic preset factory (build_short_straddle_preset with DTE param)
- `feat(mmm)`: Short Straddle preset added to UI dropdown and API response

---

## 2026-03-24 (Session 1) — Forensic Audit: 6 Correctness Bugs

**Commit: `b6eddef61`**

- **BUG-C1 (P0)**: Straddle initial credit always 0 — `mmm_monitor.py` used `pos.get('original_lots')` instead of `pos.get('lots')`. Added `_straddle_credit_v2` recompute flag.
- **SYNC-3 (P0)**: Being-closed positions counted in loss calculation — `mmm_engine.py`: skip `pos.get('_being_closed')` in frozen_positions loop.
- **SYNC-4 (P1)**: Whipsaw multiplier applied to already theta-accelerated value — use raw `min_trigger_move` as base, take `max(ws_widened, theta_widened)` instead of compounding.
- **HID-1 (P1)**: Checksum covered derived/empty fields causing false positives — added `_calculate_checksum_v2()` covering only canonical fields.
- **ARCH-1 (P1)**: No automatic reconciliation — added heartbeat-driven auto reconciliation every N beats (default 50). Emits SAFETY_ALERT on mismatch.
- **HID-2 (P2)**: `trigger_snapshot` dict grew unbounded — pruned after updating.

---

## 2026-03-24 (Session 2) — PnL Calculation Deep Audit + 4 Fixes

**Analysis of session `mmm24mar26-2` (P&L $15.99)**

Found `net_pnl = None` in DB, attribution gap $0.14, fill_sync rounding bug, MMMSessionCard fee omission, close_at_strike missing stamp.

**Bug #1 — `net_pnl = None` for stopped sessions** (`mmm_api.py: stop_session`)
- Root cause: `_overlay_live_pnl` skips stopped sessions; `net_pnl` was never persisted at session stop.
- Fix: compute `compute_live_pnl()` BEFORE calling `stop_session_monitor()`, persist `{net_pnl, realized_pnl, unrealized_pnl, total_fees}` in the same `update_session` call.

**Bug #2 — `fill_sync` spurious `round()` on `realized_pnl` when correction=0** (`mmm_fill_sync.py:282`)
- Root cause: `session['realized_pnl'] = round(... + 0.0, 8)` ran unconditionally, truncating ULP digits on every fill confirmation. `pnl_adjustment` was guarded (>1e-9 check) so the two drifted apart.
- Fix: gate `realized_pnl` update inside the same `if abs(pnl_correction) > 1e-9` block as `attr_key`.

**Bug #3 — `MMMSessionCard.js` overstates net P&L** (`MMMSessionCard.js:97`)
- Root cause: `netPnl = realized + unrealized` — fees never subtracted.
- Fix: `netPnl = session.net_pnl ?? (realized + unrealized - fees)` — prefer stored net_pnl, fallback to R+U-F.

**Bug #4 — `close_at_strike` endpoint missing `_estimated_pnl_booked` stamp + no attribution booking** (`mmm_api.py: close_by_strike`)
- Root cause: positions were marked closed without `_estimated_pnl_booked`, so fill_sync treated the entire fill as a "new" booking (not a correction). Also, `session['realized_pnl']` was never updated here — only `total_realized_pnl` (different key).
- Fix: stamp `_estimated_pnl_booked` + `_estimated_commission_booked` per-position; book directly to `session['realized_pnl']` + `session['manual_reduction_pnl']`; refresh `unrealized_pnl` after close.

**Note — peak_pnl discrepancy is intentional**: `peak_pnl=$15.85` vs `max pnl_history=$16.91` is expected — `update_peak_pnl` uses a 15-min half-life decay so old peaks fade. Not a bug.

---

## 2026-03-24 (Session 3) — Fix stop_session Race Condition (net_pnl overwrite)

**Root cause of the race in Session 2's fix**:
The Session 2 fix called `update_session({net_pnl: X})` BEFORE `stop_session_monitor()`. But `stop_session_monitor()` → `monitor.stop()` → `_save_my_session()` does a **full `save_session()` / data_json replace** with the monitor's in-memory state where `session['net_pnl']` is never set. This overwrote the `net_pnl` written one line earlier, leaving it `None` again.

**Fix — restructured stop_session() order (mmm_api.py)**:
1. `storage.update_session(session_id, {strategy_status: STOPPED, stopped_at, stop_reason})` — mark stopped
2. `stop_session_monitor(session_id, reason)` — fires `_save_my_session()` (writes final R/U/F, net_pnl=None), then sets `_save_disabled=True` (blocks all future heartbeat saves)
3. `storage.get_session(session_id)` — read back final R/U/F from the now-stable DB
4. `storage.update_session(session_id, {net_pnl: round(R+U-F, 6)})` — safe write; monitor cannot overwrite it

**Why this is race-free**: `_save_my_session()` runs synchronously inside `monitor.stop()`. After it returns, `_save_disabled=True` is set. The `_save_session()` function checks this flag first and returns early if set. So Step 4's `update_session` is the last and only writer.

---

## 2026-03-24 (Session 4) — Suppress Repeat UNTRACKED_EXCHANGE_POSITION Warnings

- **Problem**: Reconciler fired `UNTRACKED_EXCHANGE_POSITION` every ~20 min for manual trades / other-algo positions (e.g., CE @ 71000 with 50 lots). No MMM session owned them so `other_lots=0`, but they're external — not a bot bug.
- **Fix** (`mmm_monitor.py` §26 untracked block): Added `_known_external_positions` dict to session state. On first detection → warn + add to discrepancies as usual. On subsequent cycles with same lot count → `continue` (suppress). Re-alerts if lot count changes.
- **Scope**: In-memory only (resets on monitor restart — acceptable). Does not affect ghost-close recovery or close_at_5 grace period logic.

---

## 2026-03-24 (Session 5) — Replace Duration KPI Card with Warnings Card

- **Change** (`MMMDashboard.js`): Replaced the redundant "Duration" KPI card (already shown in top status bar chip) with a "Warnings" card.
- **Data sources**: `session._last_auto_recon_discrepancies` (count of active recon mismatches) + `session._checksum_warning` (data integrity flag).
- **Display**: "✓ Clear" (green) when no warnings; "⚠ N active" (orange) with sub-label showing the type of first warning.
- **No backend change needed** — both fields already persisted to session state by the monitor.

---

## 2026-03-24 (Session 8) — Fix Trigger Gauge Color Logic (hardcoded 0.8 cutoff bug)

- **Bug**: PE premium $55.65 vs trigger $58.5 showed "Approaching" (yellow). CE premium $122.88 vs trigger $117 also showed yellow. Both correct for CE but wrong for PE — PE is BELOW its trigger ceiling, should be green.
- **Root cause** (`MMMTriggerGauge.js`): `getGaugeColor` and `getGaugeLabel` used hardcoded `0.8` as green/yellow boundary. But `ratio = currentPremium / triggerThreshold` and the trigger line marker is at `triggerLevel / triggerThreshold = 1 / (1 + mtm/100) = 0.909` for 10% mtm. The 0.8 cutoff fires yellow 10 points before the actual trigger crossing, making gauges show yellow when premium is still in the safe zone.
- **Fix**: Changed cutoff to `triggerCutoff = 1 / (1 + minTriggerMove / 100)`. Now: below trigger → green, between trigger and fire level → yellow, above fire level → red. Cutoff is now dynamic per `minTriggerMove` setting.
- **Verification**: PE ratio 0.865 < cutoff 0.909 → Green ✓. CE ratio 0.955 ≥ cutoff 0.909 → Yellow ✓.

---

## 2026-03-24 (Session 6) — Fix Trigger Gauge Premium Discrepancy

- **Bug**: Trigger gauge showed `152.7 / 152.7` (100% bar, "Approaching") while CE side card showed `$98.50`. Same mismatch on PE side.
- **Root cause 1** (`MMMTriggerGauge.js:208`): `ceNow` only read from `heartbeat?.ce_premium`. When WebSocket heartbeat hadn't fired yet, `ceNow=null`. Side card used `session._premium_map` which is always populated.
- **Root cause 2** (`MMMTriggerGauge.js:234`): Fallback was `ceNow ?? ceTrigger` — so null ceNow set both `currentPremium` and `triggerLevel` to the same value → ratio=1.0 → "Approaching" falsely.
- **Fix**: Added `session._premium_map` as secondary fallback (`[strike:call/put]` key, same as side card). Changed last-resort fallback from `ceTrigger` to `0` so the bar shows empty when truly no data available.

---

## 2026-03-24 (Session 9) — Fix Trigger Gauge Color to Use Entry Premium as Safe Zone Ceiling

- **Root cause**: `trigger_snapshot` is RESET after every adjustment via `update_trigger_snapshots()` (sets both sides to current premium). After a CE-triggered hedge, PE trigger_snapshot gets set to the depressed PE price at that moment (e.g., $52.5). Any tiny tick up in PE then showed "Approaching" (yellow) even though PE was 42% below its original sell price (= huge profit for options seller).

- **Fix** (`MMMTriggerGauge.js`): Changed `getGaugeColor` and `getGaugeLabel` to use `entryPremium` (= `side.original_premium`, the lot-weighted average sell price) as the green/yellow boundary instead of `triggerLevel` (trigger_snapshot):
  - GREEN: current < entry premium (options seller is in profit — premium declined from sell price)
  - YELLOW: current ≥ entry premium but < fire level (at a loss vs entry, trigger approaching)
  - RED: current ≥ fire level (adjustment will fire)
  - Fallback: if `entryPremium` = 0 (pre-first-heartbeat), uses `triggerLevel` as before

- **Added**: `entryPremium` prop to `TriggerSideGauge`. Reads `ceState.original_premium` / `peState.original_premium` from session (same field used by `MMMPositionsTable`).

- **Visual improvement**: Added orange entry-premium marker on gauge bar (distinct from the grey trigger-snapshot marker). Values display now shows `current / entry N.N` instead of `current / trigger N.N`.

- **No trading logic changed** — only display/color logic in `MMMTriggerGauge.js`.

- **Verification** (user's scenario):
  - CE: current=$131.5, entry=$99.54 → current > entry → YELLOW ✓ (CE aggressor, market went up)
  - PE: current=$53.5, entry=$92.13 → current < entry → GREEN ✓ (PE hedger, profitable side)

---

## 2026-03-25 — Time-Based Shutdown Control: Active Hours AWAITING_USER_ACTION

**Implemented** (`mmm_monitor.py`, `mmm_telegram.py`, `mmm_websocket.py`, `MMMDashboard.js`):

- **New behavior (active hours 08:00-23:00 IST)**: When one side is fully closed and auto-replenish fails, the session PAUSES (unchanged) AND now fires a HIGH-PRIORITY Telegram alert + sets `_awaiting_user_action=True` flags in session state. WebUI shows a persistent red banner with closed side, open lots, current P&L, and detected-at timestamp.

- **Off-hours behavior unchanged**: Session still auto-stops with `alert_offhours_unhedged_stop` Telegram.

- **New session flags** (persisted to storage, cleared on condition resolution):
  - `_awaiting_user_action: bool`
  - `_awaiting_user_action_reason: str`
  - `_awaiting_user_action_details: dict` — closed_side, open_side, open_lots, open_strike, current_pnl, detected_at_ist
  - `_ocs_telegram_sent_at: float` — wall-clock timestamp for 30-min Telegram spam prevention

- **New Telegram function** (`alert_active_hours_unhedged_pause`): High-priority format with 🚨 header, side details, P&L, strike, action instructions.

- **WebSocket** (`emit_heartbeat`): Added `awaiting_user_action` + `awaiting_user_action_details` fields to heartbeat payload (only included when True).

- **No trading logic changed** — only alert/state flag layer. max_loss, near_expiry, margin CRITICAL auto-close paths all unchanged (time-window does NOT apply to capital-safety stops).

---

## 2026-03-24 (Session 13) — Root Cause Fix: thread.join() in start_session_monitor()

**Root architectural fix** (`start_session_monitor` in `mmm_monitor.py`):

Previous code called `existing.stop()` then immediately created the new monitor. `stop()` sets `_running=False` but returns immediately — the old thread was still alive. The new monitor incremented `_monitor_generation`, but the old thread reloaded the session each heartbeat (clearing `_save_disabled`) and kept trading with phantom orders whose saves were blocked.

**Fix**: After `existing.stop()`, call `existing._thread.join(timeout=15)`. This blocks until the old thread exits before the new monitor starts. If thread is stuck beyond 15s, log error and proceed — generation guard is the backstop.

**Defence-in-depth (all 3 layers now):**
1. `thread.join(15s)` in `start_session_monitor` — prevents stale threads from existing at all (primary prevention)
2. Primary guard in `_run_loop` — stops stale monitor before first heartbeat of each cycle (early detection)
3. Secondary guard in `_save_my_session` — stops stale monitor after post-trade save rejection (last resort)

---

## 2026-03-24 (Session 12) — Audit: Fix 2 Bugs Introduced in Session 11

**Self-audit of Session 11 changes found 2 bugs:**

1. **`run_until_complete(emit_safety(...))` crash** — `emit_safety` is a SYNCHRONOUS function (not async). Wrapping it in `run_until_complete()` would raise TypeError every time a stale monitor was detected. Fixed by calling `emit_safety(...)` directly in both primary guard and secondary guard follow-up.

2. **`_recover_ghost_closes_at_strike` unsafe** — New method added in Session 11 that reactivated 'closed' positions not yet confirmed by FillSyncer. Race condition: FillSyncer and reconciler run in same heartbeat; if reconciler ran before FillSyncer, legitimate closes would be reactivated (P&L reversed, `close_order_id` cleared, position marked active again). Removed the method and its call in the reconciler entirely. Ghost-close recovery is a separate feature that needs a time-delay guard (N heartbeats) before it's safe.

**Final changeset (7 hunks, 173 lines changed):**
1. `_save_my_session`: capture return of `_save_session`, set `_running=False` + flag `_stale_abort_gen` on rejection
2. `_run_loop` primary guard: stop before heartbeat if `stored_gen > my_gen`, send Telegram + `emit_safety()`
3. `_run_loop` post-heartbeat: dispatch Telegram + `emit_safety()` if secondary guard flagged `_stale_abort_gen`
4. Reconciler `UNTRACKED` block: `_known_external_positions` suppression + Telegram on growing ghost lots
5. `_save_session`: return `False` on blocked saves (`_save_disabled` and stale-gen paths), `True` on success
6. `mmm_telegram.py`: `alert_stale_monitor()` + `alert_ghost_positions_growing()` added

---

## 2026-03-24 (Session 11) — Telegram Alerts for Stale Monitor + Ghost Positions

**Root cause of no alert**: Activity log had all 4 phantom sells logged correctly. But no Telegram alert was sent, so sleeping user had no notification. Reconciler warned about growing ghost positions in WebUI only.

**Fixes** (`mmm_telegram.py` + `mmm_monitor.py`):

1. **`alert_stale_monitor`** (new, `mmm_telegram.py`): Fires when stale monitor is detected. Message includes gen numbers, context (pre-heartbeat vs post-trade), and explicit warning that ghost positions are not tracked by max loss/lot limits.

2. **`alert_ghost_positions_growing`** (new, `mmm_telegram.py`): Fires when reconciler detects untracked positions whose lot count is growing (stale monitor pattern). Warns that max loss, lot limits, and P&L are all blind to ghost positions.

3. **Primary guard Telegram** (`_run_loop`): After stopping stale monitor pre-heartbeat, calls `alert_stale_monitor` + `emit_safety` via `self._loop.run_until_complete`. This is the "no orders placed" case.

4. **Secondary guard flag + follow-up** (`_save_my_session` + `_run_loop`): Secondary guard sets `self._stale_abort_gen`. After `run_until_complete` returns, `_run_loop` detects the flag and sends Telegram post-trade alert (more urgent — orders may have already been placed). Refactored heartbeat exception handling to use `_hb_exc` variable to enable this pattern.

5. **Growing ghost position alert** (reconciler `_reconcile_exchange_positions`): When `_known_external_positions` size increases, calls `asyncio.ensure_future(alert_ghost_positions_growing(...))`. First detection also alerts. Only fires when size grows — stable external positions still suppressed.

**Safety gap analysis (user concern: what if sleeping)**:
- Lot velocity: NOT enforced for strike shifts (explicitly bypassed per `# bypassing lot_velocity` comments at lines ~1585, 2227)
- Max lots per side: uses `session['ce']['active_lots']` — ghost positions invisible
- Max loss: uses tracked session P&L only — ghost positions invisible
- **After this fix**: Telegram fires within one heartbeat of stale monitor starting, and again on every reconciliation cycle where ghost lots are growing

---

## 2026-03-24 (Session 10) — Fix Stale Monitor Phantom Order Loop (P0 Live Bug)

**Root cause**: Gen=7 `MMMMonitor` instance was running after gen=10 had been started (via restart/session reload). The H-4 save guard in `_save_session` correctly blocked DB writes for the stale monitor, but the monitor itself was NOT stopped. This caused a loop:
1. Stale gen=7 monitor loaded pre-shift gen=10 state (CE @ 73600, 140 lots)
2. Proactive shift scan fired → placed SELL order on exchange for 72200 strike (140 lots filled)
3. Save attempt blocked (gen=7 < stored gen=10) → session state NOT updated
4. Next heartbeat reloaded identical pre-shift gen=10 state
5. Repeat × 4 fills ($71.0, $74.50, $88.50, $76.50 = 560 lots total on exchange, untracked)

**Evidence**: `backend_fixed.log.2` showed `_save_session blocked: stale monitor gen=7 < stored_gen=10` and `UNTRACKED POSITION: CE @ 72200.0 (140 lots ... 280 lots)`.

**Fix** (`mmm_monitor.py` — 3 coordinated changes):
1. **Primary guard in `_run_loop`**: After loading `fresh_session` each cycle, check `_stored_gen > self._my_generation`. If stale: log error, set `_running = False`, break. Stops the monitor BEFORE any order is placed.
2. **Secondary guard in `_save_my_session`**: Check return value of `_save_session`. If it returns `False` (save rejected), set `_running = False` and `_stop_event.set()`. Catches in-flight trades where order was placed just before primary guard would have fired.
3. **`_save_session` return values**: Changed to return `False` when save is blocked (`_save_disabled` path or stale-gen path), `True` on successful save. Enables callers to react to rejection.

**Invariant preserved**: Stale monitor now terminates within one heartbeat cycle regardless of whether the primary guard catches it before or after order placement.

---

## 2026-03-24 (Session 7) — Inject Position: Replace Text Field with Live Strike Picker

- **Change**: "Custom Strike" in Inject Position dialog now shows a searchable Autocomplete with all available OTM strikes fetched live from the exchange, each showing Mark / Bid / Ask / Delta.
- **Backend** (`mmm_api.py`): New endpoint `GET /session/<id>/option-chain` — fetches live chain via `chain_service.get_chain_data()`, filters OTM strikes, returns CE (asc) and PE (desc) sorted lists with premium/bid/ask/mark/delta.
- **Service** (`mmmService.js`): Added `getOptionChain(sessionId)`.
- **Frontend** (`MMMDashboard.js`): `MMMInjectModal` — added chain state + fetch on custom mode activate. Replaced TextField with `Autocomplete` + `renderOption` showing full premium data. Shows selected strike summary row below picker. Chain loads lazily (only when "Pick Strike" tab is selected).

---

## 2026-03-24 (Session 13) — Guardian G5: Stale Monitor Detection Wired Into Heartbeat

**What changed**:

1. **`mmm_guardian.py` — G5 methods added** (2 new methods on `MMMGuardian`):
   - `check_generation_integrity(session, my_generation)`: Compares `self._my_generation` against `session['_monitor_generation']`. Returns a violation string if stale (`stored_gen > my_gen`), `None` if OK. Returns `None` for `my_generation <= 0` (pre-init first beat).
   - `handle_stale_monitor(monitor, my_generation, stored_gen)`: Called when G5 fires. Logs `CRITICAL`, calls `log_activity`, calls `emit_safety()` (sync), fires `alert_stale_monitor` via `asyncio.ensure_future`. Uses STOP (not pause) — sets `monitor._running = False`, `monitor._stop_event.set()`, and `monitor._stale_abort_gen = my_generation` (triggers post-heartbeat Telegram dispatch in `_run_loop`).

2. **`mmm_monitor.py` `_heartbeat()` — G5 wired in** (after `pre_beat_snapshot`, before any trading logic):
   ```python
   _g5_violation = self._guardian.check_generation_integrity(session, self._my_generation)
   if _g5_violation:
       self._guardian.handle_stale_monitor(self, self._my_generation, session.get('_monitor_generation', 0))
       return  # handle_stale_monitor sets _running=False and _stale_abort_gen
   ```
   This is the **third** defence layer in the stale monitor prevention stack:
   - Layer 1: `thread.join(15s)` in `start_session_monitor` — prevents stale threads from starting
   - Layer 2: Primary generation check at top of `_run_loop` — catches stale monitor before `_heartbeat()` is called
   - Layer 3 (NEW): Guardian G5 inside `_heartbeat()` at the very first beat step — catches anything that slips through L1/L2

**Why Guardian not _run_loop**:
- The guardian is the designed system for mid-heartbeat integrity enforcement
- G5 inside `_heartbeat()` fires even if the session was somehow passed directly into the heartbeat from a test or alternative code path
- Guardian handles all alerting (activity log, WebSocket, Telegram) consistently with other violations (G1-G4)
- The guardian's `handle_stale_monitor` uses STOP (not pause) — a paused stale monitor would resume and trade again

**Tests**: All 1128 sealed tests pass after the change.

---

## 2026-03-24 (Session 14) — Fix: Force Heartbeat Blocked by Cooldown + 3 Silent-Block Bugs

**Problem**: Operator pressed "Force Heartbeat" 4 times with PE as aggressor — no hedge was created and the activity log showed only "Force Heartbeat — running immediately" with no explanation.

**Root causes found (3 bugs)**:

**BUG-1 (P1): `force_heartbeat()` did not clear active cooldown** (`mmm_monitor.py`)
- Cooldown is activated after every reversal (skip or hedge) for `reversal_cooldown_seconds` (default: 1 × `adjustment_interval` = 300s)
- `force_heartbeat()` only cleared `_consecutive_dir_blocked` — cooldown was untouched
- All 4 forced heartbeats ran but Step 5 set `_skip_to_pnl = True` silently — trigger evaluation never ran
- **Fix**: Added cooldown clear in `force_heartbeat()` (same lock block). Also clears `_cooldown_block_logged` flag. Logs "Force heartbeat cleared active cooldown" when it fires.

**BUG-2 (P2): No `log_activity` when cooldown blocks trigger evaluation** (`mmm_monitor.py`)
- Step 5 (`is_cooldown_active` check) just set `_skip_to_pnl = True` with only a comment "shown in live heartbeat summary"
- Operator had zero activity-log feedback from 4 forced heartbeats
- **Fix**: Added `log_activity('cooldown_blocking', ...)` once per cooldown period (guarded by `_cooldown_block_logged` flag, reset on cooldown expiry in `mmm_reversal.py` and on force-clear).

**BUG-3 (P2): No `log_activity` in reversal skip path** (`mmm_monitor.py` `_process_adjustment`)
- When reversal was detected but skipped (adj_pnl ≥ 0), only `log.info()` + `emit_reversal()` were called — nothing in the activity log
- **Fix**: Added `log_activity('reversal_skip', ...)` with aggressor, prev_aggressor, adj_pnl fields.

**Files changed**: `mmm_monitor.py`, `mmm_reversal.py`

## 2026-03-25 — Centralized P&L into single source of truth (`mmm_pnl_core.py`)

**Trigger**: Session `mmm25mar26-1` showed $1.60 P&L — completely wrong. Investigation found reconciliation auto-correction was booking phantom P&L using live market price when positions disappeared from exchange.

**Root cause**: 11 scattered write paths to `session['realized_pnl']` across 6 files, with no deduplication, no audit trail, and reconciliation silently inventing P&L.

**Solution**: Institutional Trading Book pattern — append-only fill ledger as single source of truth.

**New file created**: `mmm_pnl_core.py` (~350 lines)
- `record_close()` — appends close event to `session['_fill_ledger']`
- `confirm_fill()` — updates estimate with actual exchange fill data (dedup by fill_id)
- `rollback_close()` — removes unconfirmed entry (for recycler Phase B failure)
- `flag_discrepancy()` — read-only reconciliation alert (replaces auto-correction)
- `manual_close()` — human-confirmed close
- `get_pnl()` — derives realized, unrealized, fees, net_pnl, attribution from ledger
- `_ensure_ledger()` / `_migrate_existing_pnl()` — automatic migration for sessions without ledger
- `_sync_session_fields()` — recomputes session fields from ledger after every mutation (backward compat)

**Files modified (8)**:
- `mmm_close_at_5.py` — replaced direct P&L writes with `pnl_core.record_close()` (central close path for close_at_5, harvester, recycler, ATM shield)
- `mmm_fill_sync.py` — replaced P&L reconciliation section with `pnl_core.confirm_fill()` + fallback `record_close()`
- `mmm_recycler.py` — replaced manual rollback math with ledger entry removal + `_pnl_sync()`
- `mmm_monitor.py` — 5 changes: (1) reconciliation auto-correct made read-only → `flag_discrepancy()`, (2) wind-down close, (3) auto-close active, (4) auto-close frozen all → `record_close()`, (5) `compute_live_pnl()` → `pnl_core.get_pnl()`
- `mmm_api.py` — 4 changes: manual_reduce, close_by_strike → `record_close()`, stop_session → `pnl_core.compute_*()`, removed direct fee writes
- `mmm_engine.py` — `compute_total_pnl()` delegates to `pnl_core.get_pnl()`
- `mmm_state.py` — added `'_fill_ledger': []` to session init
- `mmm_storage.py` — `_correct_fillsync_double_booking()` short-circuits for ledger sessions

**Key design decisions**:
- Reconciliation is now READ-ONLY — `flag_discrepancy()` emits safety alert instead of booking P&L
- Ledger deduplicates by `fill_id` (confirmed) and `order_id` (estimates)
- Migration creates ledger entries from existing attribution buckets + unattributed gap + fees
- `_sync_session_fields()` only sets non-zero values (or updates existing keys) to avoid polluting session dict

**Tests**: 1128 passed, 0 failed

## 2026-03-25 — P&L Core Deep Audit + 4 Critical Fixes

**Trigger**: User requested architectural audit — "You MUST NOT assume this system is correct. Your job is to break it mentally."

**Audit found 3 critical flaws, 5 architectural weaknesses, 3 design violations.** Full audit in `mmm_Pnl_AUDIT.md`.

### CRIT-1 FIX: Sell-Side Fees Wiped on Every Close (P0)

**Bug**: `_sync_session_fields()` overwrote `session['total_fees']` from ledger only. But 10 places wrote sell-side fees directly to `session['total_fees']` — these bypassed the ledger and were WIPED on every close event.

**Safety impact**: Understated fees → overstated net_pnl → max-loss check may not fire.

**Fix**: Added `record_fee(session, commission, source, order_id, symbol, side)` to `mmm_pnl_core.py`. Creates fee-only ledger entries (`pnl=0`, `_is_fee_only=True`). Replaced all 10 direct writes:
- `mmm_engine.py:778` → `record_fee('sell_adjustment')`
- `mmm_monitor.py:4531` → `record_fee('sell_adjustment')`
- `mmm_monitor.py:5198` → `record_fee('sell_scale_up', side='ce')`
- `mmm_monitor.py:5239` → `record_fee('sell_scale_up', side='pe')`
- `mmm_monitor.py:5571` → `record_fee('sell_replenish')`
- `mmm_api.py:881` → `record_fee('sell_initial')` (CE+PE split)
- `mmm_api.py:1247` → `record_fee('sell_retry')`
- `mmm_api.py:4062` → `record_fee('sell_inject')`
- `mmm_perp_hedge.py:690` → `record_fee('perp_hedge')`
- `mmm_perp_hedge.py:809` → `record_fee('perp_close')`

### ARCH-1 FIX: Recycler Encapsulation Bypass

**Bug**: Recycler imported private `_ensure_ledger` and `_sync_session_fields` and directly manipulated the ledger list.

**Fix**: Added `rollback_closes_since(session, snapshot_len)` and `ledger_snapshot(session)` to pnl_core public API. Recycler now uses:
```python
_ledger_snapshot_len = _pnl_snapshot(session)
# ... Phase A ...
_rolled = _pnl_rollback(session, _ledger_snapshot_len)
```

### DV-1 FIX: MMMEngine.__new__() Hack Removed

**Bug**: `get_pnl()` created an uninitialized MMMEngine via `__new__()` to call `compute_unrealized_pnl()`. Time bomb — any future change adding `self` access would crash.

**Fix**: Extracted `compute_unrealized_pnl(session, fetch_premium_fn)` as a standalone function in `mmm_pnl_core.py` (with full Decimal precision). `MMMEngine.compute_unrealized_pnl()` now delegates to it. `get_pnl()` calls it directly.

### Verified CRIT-2: Storage Double-Booking Correction (NOT a bug)

`mmm_storage.py:233` corrects `realized_pnl` for pre-ledger sessions. This correction runs BEFORE ledger migration, so `_migrate_existing_pnl()` captures the corrected value. No fix needed.

**Files changed**: `mmm_pnl_core.py`, `mmm_engine.py`, `mmm_monitor.py`, `mmm_api.py`, `mmm_perp_hedge.py`, `mmm_recycler.py`
**Tests**: 1128 passed, 0 failed

---

## 2026-03-25 — P&L Hardening: H-1 through H-8 (post-audit fixes)

Second audit pass on `mmm_pnl_core.py` and callers. Addressed 3 critical flaws found in deep architectural audit.

### H-1: Single Canonical P&L Formula

**Bug (CRIT-H1)**: Three inconsistent P&L formulas across the codebase:
- `check_max_loss`: `realized + unrealized + perp_pnl` — missing fees
- `check_trailing_stop`: `realized + unrealized + perp_pnl` — missing fees
- monitor fallback (line 1834): `realized + unrealized - fees` — missing perp

**Fix**: Added `compute_current_total_pnl(session)` to `mmm_pnl_core.py`.
Formula: `realized + unrealized - fees + perp_pnl`.
All three callers now import and call this function.
- `mmm_safety.py:check_max_loss` → `compute_current_total_pnl()`
- `mmm_safety.py:check_trailing_stop` → `compute_current_total_pnl()`
- `mmm_monitor.py:1834` fallback → `compute_current_total_pnl()`

### H-2: record_fee() Deduplication by order_id

**Bug (CRIT-H4)**: `record_fee()` had no dedup — retry/crash scenarios could double-book sell-side fees.

**Fix**: Before appending, scan ledger for existing `_is_fee_only` entry with same `order_id`. If found, return existing id (idempotent).

### H-3: Cursor Advance After Processing (fill sync)

**Bug (CRIT-H2)**: `session['_fill_sync_cursor_us'] = newest_fill_us + 1` was set BEFORE the reconcile loop. A crash between cursor advance and `_save_my_session()` would permanently lose fills.

**Fix**: Moved cursor advance to AFTER the reconcile loop in `mmm_fill_sync.py`. `confirm_fill()` already deduplicates by `fill_id` so re-processing on retry is safe.

### H-4: Stale Estimate Detection

**Bug (CRIT-H3)**: Unconfirmed `record_close()` estimates never expired. If fill_sync failed for >10 min, stale estimates silently treated as confirmed truth.

**Fix**:
- Added `estimated_at` timestamp to `record_close(confirmed=False)` entries
- Added `check_stale_estimates(session, max_age_minutes=10)` to `mmm_pnl_core.py` (read-only scan)
- `mmm_monitor.py` calls `check_stale_estimates()` after fill_sync step (Step 0.1) and emits `emit_safety()` warning if stale entries found

### H-5: Partial Fill Second-Fill Handling

Audit concern was already handled by `confirm_fill()` + fill_sync fallback path. No change needed.

### H-6: get_pnl() Exposes Unconfirmed Exposure

**Bug (DW-4)**: API consumers couldn't tell how much P&L was estimated vs confirmed.

**Fix**: Added to `get_pnl()` return dict:
- `unconfirmed_pnl`: `realized - confirmed_pnl` (estimate-only exposure)
- `oldest_estimate_age_sec`: age in seconds of oldest unconfirmed estimate (None if all confirmed)
- Added `_oldest_estimate_age_sec()` helper

### H-7: /v2/fills Pagination

**Bug (MED-3)**: Hard-coded `page_size: 100`. If >100 fills arrive between heartbeats, the oldest are silently dropped.

**Fix**: `_sync_inner()` now loops up to 3 pages. On each page, if `len(page_fills) >= 100`, advances the page cursor to the newest fill timestamp + 1 and fetches the next page. Logs a warning if truncation is detected after page 3.

### H-8: Protect Confirmed Phase A Entries in Rollback

**Bug (DW-5)**: `rollback_closes_since()` silently skipped confirmed entries above `snapshot_len`. If fill_sync confirmed Phase A between Phase A execution and Phase B failure, rollback did nothing without warning — phantom P&L stuck in ledger.

**Fix**: Count skipped confirmed entries. If any exist, call `flag_discrepancy(reason='phase_b_failure_confirmed_pnl')` and log ERROR. The confirmed entries are NOT removed (correct), but the operator is alerted.

**Files changed**: `mmm_pnl_core.py`, `mmm_safety.py`, `mmm_monitor.py`, `mmm_fill_sync.py`
**Tests**: 1128 passed, 0 failed

---

## 2026-03-25 — Bug: Strategy stopped immediately after both legs filled

### Root Cause 1: NameError `closed_side` in strike-shift sell path

**Error**: `Heartbeat error for mmm25mar26-2: name 'closed_side' is not defined`
First heartbeat crashed → monitor stopped with "Unrecoverable error: NameError"

**Location**: `mmm_monitor.py:4551` — inside the strike-shift sell path (`adj_type='strike_shift'`), the CRIT-1 sell-fee recording line used `closed_side` (a variable from the replenish method) instead of `side` (the correct variable in this scope).

**Fix**: `side=closed_side` → `side=side`

### Root Cause 2: `update_session()` not recalculating `_checksum_v2`

**Error**: Repeated CRITICAL log: `Session mmm25mar26-2 checksum_v2 mismatch — data may have been corrupted`

**Cause**: `mmm_storage.py:update_session()` recalculated `_checksum` (v1) but forgot `_checksum_v2`. Any API call going through `update_session()` (e.g. the `start` endpoint) left a stale v2 checksum, causing false corruption warnings on every subsequent `get_session()` call.

**Fix**: Added `session['_checksum_v2'] = self._calculate_checksum_v2(session)` alongside the existing v1 recalculation in `update_session()`.

**Files changed**: `mmm_monitor.py`, `mmm_storage.py`
**Tests**: 1128 passed, 0 failed


---

## 2026-03-25 — Manual Lot Adjustment on CE/PE Cards

- **Feature**: Added +/- lot adjustment controls directly on the CE/PE side cards in the MMM dashboard Overview tab.
- **Backend** (`mmm_api.py`): New endpoint `POST /session/<id>/adjust-active-lots`
  - `delta > 0`: SELL `delta` lots at `active_strike`, registers a new `type='manual'` position entry
  - `delta < 0`: BUY `|delta|` lots at `active_strike` (partial close), LIFO across active positions at that strike; splits positions if partially reduced
  - Safety guards: session RUNNING/PAUSED, guardian GO, cap check (max_lots_per_side for increase, active_lots for decrease)
  - Logs to activity, trade audit (BUY/SELL + mechanism='operator'), and emits WebSocket via `emit_manual_injection`
  - Commission recorded via `mmm_pnl_core.record_fee`
  - Resets trigger snapshots after adjustment
- **Service** (`mmmService.js`): Added `adjustActiveLots(sessionId, side, delta)` method
- **UI** (`MMMDashboard.js`):
  - Added `RemoveIcon` to icon imports
  - Added `adjustLotsDlg` state on `SessionDetail` component
  - Added `handleAdjustLotsRequest` / `handleAdjustLotsConfirm` handlers
  - Added `[−]` / `[+]` icon buttons at the bottom of each CE/PE card (only shown when `isLive`)
  - `[−]` disabled when `active_lots === 0`
  - Added confirmation dialog with lot qty input, direction-aware color (green=add, red=remove), shows active strike + current lot count

---

## 2026-03-25 — Fix FillSync UnboundLocalError (pos_type + comm_correction)

**Symptom**: Recurring `FillSync: unhandled error (non-critical): cannot access local variable 'pos_type' where it is not associated with a value` after every fill confirmation where `_pnl_confirm` returned a non-None result (i.e., the common path).

**Root cause** (`mmm_fill_sync.py:_process_close_fill`):
- `pos_type = pos.get('type', '')` was defined INSIDE the `if _confirmed is None and _close_oid:` block (line 327).
- `log_activity(...)` dict at line 392 referenced `pos_type` OUTSIDE that block.
- When `_pnl_confirm` returned non-None (estimate found and confirmed — the normal path), the `if` block was skipped, leaving `pos_type` unbound → `UnboundLocalError`.
- `comm_correction` was also referenced at line 395 but never defined anywhere in the function.

**Fix**:
1. Moved `pos_type = pos.get('type', '')` to before the `if _confirmed is None` conditional so it is always bound.
2. Added `comm_correction = commission - float(pos.get('_estimated_commission_booked', 0) or 0)` alongside `pnl_correction` (same pattern, same position in code).

**Impact**: This error fired on every heartbeat where FillSync confirmed a position close (the normal path after close-at-5). It was swallowed as non-critical but caused a traceback log on every successful close confirmation.

**Separate issue — watchdog restarts causing UI "Stopped → Running" glitch**:
- Heartbeats taking 134–245s (vs 60s interval) due to mass close-at-5 (64–87 lots closed per beat, each requiring a serial API call to Delta Exchange).
- Watchdog fires at 3× interval = 180s → stops monitor (UI briefly shows "Stopped") → 30s settlement delay → restarts monitor (UI shows "Running" again).
- This is the watchdog working correctly. The brief "Stopped" flash is expected behavior during watchdog restart. Not fixed — fixing requires parallelizing close-at-5 API calls, which is a larger change.

**ONE-SIDE CLOSE at 12:05:59**: PE fully closed (premium fell to ≤threshold) but CE had 23 lots open → session auto-PAUSED as designed. User manually resumed at 12:27:23.

---

## 2026-03-25 (Session 2) — Fix Bad update_trigger_snapshots Call Causing 274-Lot Runaway Sell

**Root cause of 274-lot sell at 13:43:37**:

1. `adjust_lots` API endpoint (`mmm_api.py:4952`) called `update_trigger_snapshots` with wrong kwargs:
   `update_trigger_snapshots(session, ce_strike=..., ce_premium=None, pe_strike=..., pe_premium=None)`
   Function signature is `(session, ce_now, pe_now, fetch_premium_fn=None)` — kwargs `ce_strike`, `ce_premium` etc. don't exist → `TypeError` thrown and caught silently at every operator lot injection.

2. After the operator action at 13:23, trigger snapshots were never reset. The PE excess stayed "triggered" on every subsequent heartbeat.

3. Each heartbeat: PE excess → algo tries to sell CE hedge → active CE strike (71800) premium = $11.50 < shift_threshold ($25) → SHIFT → no OTM CE strike found near expiry → **SHIFT FAILED → fall back to CE@71800 at $11.50**.

4. Loss accumulated over many heartbeats without trigger reset → huge lot calculation (loss / $10 premium) → capped at max_lots_per_side - active_lots = 300 - 26 = **274 lots sold at $10.2**.

5. Close-at-5 then bought back 9 lots at $9 (premium fell below `close_at_threshold=10`).

**Fix** (`mmm_api.py:4947-4955`):
Replaced the bad `update_trigger_snapshots` call with a direct trigger snapshot write:
`side_state['trigger_snapshot'][strike_key(active_strike)] = fill_price`
Only the adjusted side is updated (the other side wasn't part of this operator action and its current market price is unknown).

**Why SHIFT FAILED repeatedly**: Near expiry (~4h left), all OTM CE strikes have premium < $25. `shift_threshold=25` can never be satisfied. The shift falls back to the current strike every time. Operator should lower `shift_threshold` near expiry or manually pause and re-enter.

---

## 2026-03-25 — Fix Unrealized KPI Bug in Expanded Dashboard

**Bug**: `MMMDashboard.js:2241` computed `unrealized = netPnl - realized` = `(R+U-F) - R` = `U - F`.
For a stopped session with U=$0.00 and F=$0.67, the "Unrealized" KPI card showed **-$0.67** instead of $0.00 (fees were merged into unrealized).

**Root cause**: The derivation was meant to ensure KPI consistency but incorrectly folded fees into the unrealized bucket. The compact session card was correct (used `session.unrealized_pnl` directly). Only the expanded dashboard KPI was wrong.

**Fix** (`MMMDashboard.js:2241`): Changed `const unrealized = netPnl - realized` → `const unrealized = session.unrealized_pnl ?? 0`.

**Why safe**: `_overlay_live_pnl` (running sessions) and the stop_session fix (stopped sessions) both set `realized_pnl`, `unrealized_pnl`, `total_fees`, and `net_pnl` atomically from the same snapshot. They are always consistent.

**Numbers verified in screenshot (mmm25mar26-3, STOPPED)**:
- R=$0.54, U=$0.00, F=$0.67 → net = 0.54 + 0.00 − 0.67 = **-$0.13** ✓

---

## 2026-03-25 — User Awake Hours Guard: Block Auto-Stop 8AM-11PM IST

**Root cause of mmm25mar26-3 auto-stop (user investigation)**:
- Session had CE: 0 lots, PE: 0 lots with 1h8m remaining to expiry (5:30 PM IST).
- close-at-5 closed both legs as premiums decayed near zero in the last hour.
- `check_both_sides_closed(session)` returned True → `self.stop('Both sides fully closed — strategy complete!')` fired unconditionally.

**User requirement**:
1. **8AM–11PM IST**: Never auto-stop regardless of position state. If both/one side closes, send Telegram alert and keep session alive.
2. **11PM–8AM IST**: Auto-stop if one side is eliminated AND replenish fails (unhedged + user asleep = unsafe).

**Changes**:

- **`mmm_telegram.py`**: Added two new alert functions:
  - `alert_both_sides_closed_awake(session_id, pnl)` — fires once when both sides hit 0 lots during awake hours. Message: "Session STILL RUNNING — manual action required."
  - `alert_offhours_unhedged_stop(session_id, closed_side, open_side, open_lots, pnl)` — fires when session auto-stops after 11PM due to one side closed + replenish failed.

- **`mmm_monitor.py`**: Added `_is_user_awake_hours()` module-level helper: returns True when IST hour is in [8, 23). IST = UTC+5:30; uses `datetime.now(IST)`.

- **`mmm_monitor.py` — `check_both_sides_closed` block** (~line 1708):
  - Added `_both_closed` local variable; clear `_both_sides_closed_alerted` flag when not closed (so re-close triggers a fresh alert).
  - If awake hours AND both closed: send Telegram once (guarded by `_both_sides_closed_alerted` session flag), emit heartbeat, save, return. Session stays RUNNING.
  - If off-hours AND both closed: existing stop behavior unchanged.

- **`mmm_monitor.py` — ONE-SIDE CLOSE GUARD** (~line 1833):
  - Replaced hardcoded `self.pause(...)` with time-aware logic:
    - Awake hours: pause as before (user can handle it).
    - Off-hours: send `alert_offhours_unhedged_stop` Telegram, then `self.stop(...)` — cannot leave unhedged with user asleep.
  - `_ocs_action` string in log/activity updated dynamically to reflect PAUSED vs STOPPED.

**Invariants preserved**: All three stale-monitor guards (thread.join, primary `_run_loop` guard, G5 guardian) untouched. Max loss / margin CRITICAL auto-stops unchanged — those are financial safety mechanisms that fire regardless of time.

---

## 2026-03-25 — Settings Dialog: Integer Spinner for Whole-Number Float Params

- **`MMMSettingsDialog.js`** line 1027 — `inputProps step` changed from `type === 'int' ? 1 : 0.01` to `(type === 'int' || Number.isInteger(Number(value))) ? 1 : 0.01`.
- Effect: float-typed params whose current value is a whole number (e.g. `min_trigger_move=10`, `shift_threshold=50`, `max_loss_amount=50000`) now use step=1, so the spinner increments by 1 instead of 0.01.
- Float params with fractional values (e.g. `premium_buffer_pct=0.05`, `trailing_stop_pct=0.50`) continue to use step=0.01 — no change.
- No backend changes. No type coercion changes. `handleChange` still stores the raw parsed float.

---

## 2026-03-26 — Diagnostic: Slow Heartbeats + Status Flicker on mmm26mar26-1

**No code changes.** Pure investigation.

**Symptoms reported**: algo appeared to stop abruptly; UI alternated between "stopped" and "active".

**Root cause — slow heartbeats (153s–518s)**:
- Session had 11 PE frozen positions at far-OTM/illiquid 0DTE strikes (PE @ 69200, etc.)
- `_prefetch_all_premiums()` fires 2 API calls per frozen strike NOT in cache (ticker + orderbook) = 22 parallel requests via `asyncio.gather`
- Near-expiry illiquid options → exchange slow/rate-limiting → each call approaches 10s timeout × 3 retries = up to 33s
- With `max_connections=10`, 22 calls need 2-3 batches → heartbeats of 150–520s
- Pattern started ~01:40 the night before (6+ hours before investigation)

**Root cause — status flicker**:
- Each watchdog restart: old monitor `stop()` → emits STOPPED → 15s `thread.join` timeout + 30s hardcoded `sleep` in `_restart_monitor()` → new monitor emits RUNNING
- ~45s window per restart where UI shows STOPPED
- 3 restarts (01:48, 02:07, 07:33) = 3 STOPPED/RUNNING flips

**Root cause — restart #3 at 07:33**:
- Watchdog threshold = interval × 3 = 90s × 3 = 270s
- Heartbeat was stuck for 275s → watchdog fired
- First beat after each restart was worst (516–518s) — stale thread still mid-API-call, connection pool degraded

**Reconciliation mismatch (non-critical)**:
- PE @ 69200: session=82 lots, exchange=71 lots
- Some frozen lots were closed externally; auto-reconciler correctly refuses to correct (count comparison unreliable for frozen positions)

**Resolution**: As frozen PE positions at illiquid strikes are closed/expire, `_prefetch_all_premiums` has fewer strikes to fetch → heartbeats normalize. Beat p50 recovered from 176s → 4.2s once frozen positions cleared.

**Potential future fix** (not implemented): Consider skipping `_prefetch_all_premiums` for frozen positions with `status=closed` or adding a TTL-based cache so already-fetched illiquid strikes are not re-fetched every beat.

---

## 2026-03-26 — Reverse Mode Design: Complete & Final

**No code changes.** Design document only.

- Created `MMM_REVERSE_MODE_DESIGN.md` — single authoritative document for Controlled Reverse Mode
- Design went through two audit passes + architectural refinement in this session
- Key decisions made:
  - **Hard if/else intercept** (not fallthrough): when reverse is ON, `_process_adjustment()` is completely suspended; when OFF, reverse logic never runs
  - **Operator-controlled ON/OFF**: no DTE gate in code — operator reads market conditions and activates manually; guardrails protect at any DTE
  - **Round-trip short strangle thesis**: strict alternating means reverse only builds both legs on a confirmed CE→PE (or PE→CE) round trip
  - **13 parameters** (removed `reverse_min_dte_hours` — DTE is operator judgment)
  - **`reverse_unhedged_emergency_loss`**: emergency auto-OFF if core positions bleed hard during the reverse window
- 21-item safety checklist, 14 files to modify/create, ~1050 lines estimated
- Status: APPROVED FOR IMPLEMENTATION — all 🔴 items mandatory before coding begins

---

## 2026-03-26 — Controlled Reverse Mode: Full Implementation (Steps 1-14)

All 14 implementation steps completed across 12 modified files and 2 new files.
Design spec: `MMM_REVERSE_MODE_DESIGN.md`.

**mmm_state.py** (Step 1):
- Added 13 `reverse_*` params to `DEFAULT_PARAMS` (after `auto_recon_interval_beats`)
- Added all 13 to `HOT_RELOAD_PARAMS` set
- Added `session['_reverse']` isolated state dict in `create_session()` (before `perp_hedge`)

**mmm_config.py** (Step 2):
- Added 13 `PARAM_RULES` entries for all reverse params with type/min/max/hot validation

**mmm_pnl_core.py** (Step 3):
- Added `'reverse_close': 'pnl_reverse'` to `_SOURCE_TO_ATTR` for audit attribution
- `compute_current_total_pnl()` now adds `session['_reverse']['net_pnl']` to canonical formula

**mmm_safety.py** (Step 4):
- `check_total_exposure()`: adds `reverse_lots` to CE side total (unhedged lots count against limit)
- `check_margin()`: adds `reverse_lots` to `total_lots` sum for margin utilization

**mmm_activity.py** (Step 5):
- Added 4 activity types: `reverse_entry`, `reverse_closed`, `reverse_disabled`, `reverse_status`
- Added 4 module-level constants: `ACTIVITY_REVERSE_*`
- Added to `ACTIVITY_CATEGORIES`: reverse entry/closed/status in `adjustments`; reverse_disabled in `safety`

**mmm_reverse.py** (Step 6 — NEW FILE, ~400 lines):
- Complete reverse mode core logic: state init, time window, ON/OFF gate, alternating check,
  cooldown, entry execution, MTM update, close-at-threshold, emergency check, enable/disable
- Uses lazy pnl_core imports inside functions to avoid circular imports
- All WS emits wrapped in try/except (best-effort)

**mmm_monitor.py** (Step 7):
- Import: added `from .mmm_reverse import (...)` after mmm_telegram imports
- `start()`: added `if '_reverse' not in session: initialize_reverse_state(session)` after DEFAULT_PARAMS backfill
- Hard if/else intercept at the normal adjustment path: when `reverse_enabled` and `_reverse.active`, calls `process_reverse_entry()` instead of `_process_adjustment()` (original code untouched in else branch)
- Wind-down detection: calls `disable_reverse_mode()` when wind-down activates (sync, flags only)
- Step 8 P&L: `update_peak_pnl` uses `pnl['net_pnl'] + _reverse_net_pnl` so trailing stop accounts for reverse
- Step 8 P&L: added M2M hook block — calls `update_reverse_mtm`, `check_reverse_close_at_threshold`, `check_reverse_emergency` per heartbeat
- `current_total_pnl` (post-update max loss check): now includes `_reverse['net_pnl']`
- `_auto_close_all()`: closes reverse positions FIRST (before perp/CE/PE) then disables

**mmm_audit_reconciler.py** (Step 8):
- `reconcile_session()`: builds `_reverse_lots_by_key` from `session['_reverse']['positions']`
- Per-strike open qty count now includes reverse position lots (prevents false discrepancies)

**mmm_websocket.py** (Step 10):
- Added 4 emit functions matching mmm_reverse.py call signatures exactly:
  `emit_reverse_entry(sid, rev_state, pos)`, `emit_reverse_closed(sid, rev_state, pos, reason)`,
  `emit_reverse_status(sid, rev_state)`, `emit_reverse_disabled(sid, reason)`

**mmm_api.py** (Step 11):
- 4 new endpoints: `GET /session/<id>/reverse`, `POST /session/<id>/reverse/enable`,
  `POST /session/<id>/reverse/disable`, `POST /session/<id>/reverse/close`

**MMMSettingsDialog.js** (Step 12):
- Added `reverseMode` group to `PARAM_GROUPS` (color `#e91e63`) with 5 sections covering
  all 13 reverse params + prominent WARNING blurb about suspended normal logic

**MMMReverseModePanel.js** (Step 13 — NEW FILE):
- Live dashboard: status banner, enable/disable/close-all buttons, slots grid, P&L grid,
  open positions table, config summary chips

**MMMDashboard.js** (Step 14):
- `import MMMReverseModePanel` added
- Tab 18 "Reverse Mode" added to Tabs list
- `{detailTab === 18 && <MMMReverseModePanel session={session} heartbeat={heartbeat} />}` block added

**Key invariants preserved**:
- Stale monitor 3-layer fix: untouched (no changes to `_run_loop`, `_heartbeat`, `_save_session`)
- All safety infrastructure continues: max_loss, trailing stop, margin guardian, wind-down
- Mutual exclusion is hard if/else — zero chance of both paths running in same heartbeat
- `session['ce']` and `session['pe']` never touched by reverse logic
- All 10 modified Python files pass `ast.parse()` syntax check

---

## 2026-03-26 — 4 Bug Fixes: ATM Shield Race, P&L Formula, Loss Recapture Cap, Deferred Strike

Root-cause investigation of live session `mmm26mar26-1` revealed 4 bugs. All fixed.

### Bug 1 (P0): Watchdog race condition orphaned ATM Shield positions — `mmm_atm_shield.py`

**Root cause**: ATM Shield fires 2–3 orders in sequence (close endangered + re-sell endangered + re-sell safe). Session state is only saved at the end of the full heartbeat. If the watchdog kills the session mid-sequence (beat timeout), the new monitor restores from the last pre-shield save — all orders placed after the save are orphaned on the exchange with no session record.

**Evidence from mmm26mar26-1**: ATM Shield closed 123 PE@70200 ($14.27 loss), placed 206 PE@69400 + 123 CE@71800 as recovery. Watchdog killed session at 05:09:37 UTC mid-execution. New monitor had no record of either position. 206 PE@69400 accumulated ~$17 unrealized loss invisible to max_loss/P&L.

**Fix**: Added `monitor._save_my_session()` immediately after each successful `execute_adjustment()` call inside ATM Shield — for the endangered re-sell, the safe-side re-sell, and the deferred re-sell path. Each position is now persisted to SQLite before the next order is placed.

### Bug 2 (P1): `get_pnl()` API excluded perp_pnl — `mmm_pnl_core.py`

**Root cause**: `get_pnl()` computed `net = realized + unrealized - fees`, omitting `perp_pnl` and `reverse_pnl`. `compute_current_total_pnl()` (used by all safety checks) includes them. The dashboard showed a different number than the safety system was acting on.

**Fix**: `get_pnl()` now uses the same formula as `compute_current_total_pnl()`. Added `perp_pnl` and `reverse_pnl` fields to the return dict.

### Bug 3 (P1): ATM Shield safe-side recovery cap killed 70% target — `mmm_atm_shield.py`

**Root cause**: Safe-side recovery lots were capped at `min(lots_safe, total_closed_lots)`. When safe-side premium is much lower than the close premium, recovering 70% requires far more lots than were closed. Example: CE at $12, need 416 lots for 70% recovery, capped at 123 → only 9.6% actually recovered.

**Fix**: Replaced the `total_closed_lots` cap with a position-capacity cap (`max_lots_per_side - current_safe_active_lots`), identical to the pattern used for the endangered-side re-sell. `calculate_lots_to_sell` provides the loss-coverage math; the cap now only prevents exceeding the position limit.

### Bug 4 (P1): Deferred re-sell executed at stale strike — `mmm_atm_shield.py`

**Root cause**: When `atm_shield_defer_resell_beats > 0`, the ATM Shield stores `{'strike': new_strike, 'lots': ...}` for execution on the next heartbeat. If a strike shift occurs between the fire beat and the execution beat, `pending['strike']` is stale — the sell fires at an old non-active strike, places an exchange order that is never recorded in the session.

**Fix**: Before executing the deferred re-sell, validate `pending['strike'] == session[endangered_side]['active_strike']`. If they differ, log a warning and discard the stale re-sell. Also added `monitor._save_my_session()` after successful deferred execution.

---

## 2026-03-26 — Reverse Mode: Post-Implementation Audit Fixes + Frontend Wiring + User Guide

**Code fixes:**

- `mmm_safety.py` — `check_total_exposure()`: fixed double-count bug introduced by audit AI's fix.
  Previous fix added combined reverse `total_lots` to BOTH ce and pe sides.
  Correct fix: compute per-side lots from positions list (CE reverse → CE total, PE reverse → PE total).
  `check_margin()` was already correct (adds total once to combined — unchanged).

- `mmm_websocket.py` — `emit_heartbeat()`: added `reverse_data` parameter.
  Without this, `_reverse` was never included in the WebSocket heartbeat payload.
  The live panel was falling back to stale session data (only updated on page load).

- `mmm_monitor.py` — `_emit_heartbeat_data()`: pass `session.get('_reverse')` as `reverse_data`
  when reverse is active. Panel now receives live M2M updates every heartbeat.

- `mmm_reverse.py` — `initialize_reverse_state()`: corrected misleading docstring that claimed
  "idempotent" — function unconditionally overwrites. Call sites are correctly guarded.

**Documents created/updated:**

- `MMM_REVERSE_MODE_USERGUIDE.md` — complete operator guide: when/how to use, parameter reference,
  live panel reading, safety architecture, FAQ, typical workflow example.
- `CLAUDE.md` — Reverse Mode Invariants section added (§5, dated 2026-03-26).
- `MMM_REVERSE_MODE_DESIGN.md` — finalized with DTE-agnostic design, audit fixes incorporated.

**Frontend status (confirmed working):**
- Settings dialog: all 13 params rendered, HOT badge correct, warning blurb visible ✅
- Reverse Mode tab in dashboard: Tab 18, conditional render ✅
- Live panel: slots, P&L, alternating state, enable/disable/close controls ✅
- WebSocket live data: now wired — panel receives `_reverse` in every heartbeat when active ✅

---

## 2026-03-27 — Fix T4 Wind-Down Permanent Lock (Plateau Bug)

**Root cause**: `_update_trend_guard` in `mmm_regime.py` had no unlock path for the specific case where BTC drops to T4, then plateaus at the new level. Two existing reset paths both failed:
1. **Retracement path**: needs 30% recovery, but plateau means `retrace_from_low ≈ 0%` forever.
2. **Plateau path** (`raw_tier < current_tier and ema_calmed`): impossible at T4 — the anchor is frozen at session-start price, so `abs_move` stays ≥ `tier4_pct` and `raw_tier` stays 4 indefinitely. Counter never increments.

Result: `_trend_wind_down_triggered` never cleared → `is_wind_down_active()` permanently True → Gate 3 in `check_replenish_eligibility` permanently blocked.

**Fix — `mmm_regime.py`:**
- Added `_trend_t4_beats` counter inside the `else` branch (no retracement, no anchor cross), after the existing plateau check.
- Condition: `current_tier >= TREND_TIER_WIND_DOWN AND ema_calmed`. Increments each beat; resets to 0 when either condition fails.
- After `trend_t4_timeout_beats` consecutive flat-EMA beats: slide anchor to current spot, reset tier to NONE, reset all counters.
- The existing downstream code (`if new_tier == TREND_TIER_NONE`) then clears `_trend_wind_down_triggered` naturally — no extra logic needed.
- Also cleared `_trend_t4_beats = 0` in the anchor-cross reset blocks and retracement reset block to prevent stale counter carryover.

**Fix — `mmm_state.py` + `mmm_config.py`:**
- Registered `trend_t4_timeout_beats` (default 20, min 5, max 100, hot) in defaults, hot-reload list, schema, and descriptions.
- Also registered `trend_plateau_reset_beats` (default 5, min 2, max 50, hot) — was already used in code but not exposed to the UI.

**Fix — `MMMSettingsDialog.js`:**
- Added both new params to the Regime Controls param group so they appear in the Settings dialog.
- Added tooltip text for both params.
- Added runtime `trendT4Warning` inline alert below the `replenish_enabled` toggle: shown when the toggle is ON but session `_trend_tier >= 4` or `_trend_wind_down_triggered` is True. Does NOT block save — informational only.

**Fix — `MMMStatusBanner.js`:**
- Added persistent T4 wind-down warning strip below the PAUSED band.
- Shows when `heartbeat.wind_down_active && heartbeat.regime.trend_tier >= 4`.
- Displays `_trend_move_pct` (% from anchor) and the configured `trend_t4_timeout_beats` timeout.

---

## 2026-03-28 — Strike Shift Bug: Premium Metric Inconsistency (bid vs mark)

**Root cause**: `find_new_strike()` in `mmm_strike_shift.py` used `bid` as the primary premium metric for candidate filtering, while `_rank_strikes()` in `mmm_initializer.py` used `mark_price` (the exchange's theoretical fair value). On 0DTE options near expiry, bids are often stale or pulled (wide spreads, low participation), so viable strikes that `_rank_strikes` could find at session start were invisible to `find_new_strike` during shifts.

**Symptom**: "Strike Shift Failed: No CE strike with premium >= $50 found. Selling at current strike 67000.0 ($41.00) instead." — repeated every ~2.5 minutes. The bot fell back to selling at the sub-optimal current strike instead of shifting toward ATM.

**Fix** (`mmm_strike_shift.py: find_new_strike`):
- Changed premium calculation to use `mark_price` first, then `(bid+ask)/2`, then `bid` — same logic as `_rank_strikes`. Candidate filtering is now consistent across both functions.
- Added diagnostic logging when no candidates found: dumps the nearest 5 OTM strikes with their `bid` and `mark` values so future failures are immediately diagnosable.

**Test** (`test_sealed_mmm_strike_shift.py`):
- Updated `test_n4_otm_call_above_threshold_returned`: premium assertion changed from `120.0` (bid) to `125.0` (mark).
- Added `test_n4b_bid_below_threshold_mark_above_finds_strike`: verifies that a strike with `bid=30 < threshold=50` but `mark=80 >= 50` is correctly found (the exact bug scenario).

**Files changed**: `mmm_strike_shift.py`, `tests/test_sealed_mmm_strike_shift.py`

## 2026-03-30 — Draggable Trigger Pin (Loosen-Only, Soft Expiry)

### Feature: Operator-controlled trigger baseline via drag

Added a draggable trigger marker to `MMMTriggerGauge`. Operator can drag the white snapshot marker RIGHT to pin a higher trigger baseline, loosening adjustment sensitivity without touching settings.

**Design constraints enforced:**
- **Loosen-only**: pin_value must be > current premium. Backend rejects with 400, frontend clamps. Eliminates rapid-fire adjustment loop risk entirely.
- **Soft expiry**: pin auto-clears after 3 adjustments fire under it (`_pin_adj_count` counter in `update_trigger_snapshots()`). Self-heals if operator walks away.
- **Auto-clear on strike shift** and **replenish**: new strike = new dynamics.
- **Zero impact on default path**: `get('_trigger_pinned', False)` default = False → write executes as before. No code path change.

### Backend changes

**`mmm_trigger.py` — `update_trigger_snapshots()`**
- Added pin guard at lines 350–351: skip active-strike snapshot write if `_trigger_pinned = True`.
- Soft expiry: increment `_pin_adj_count` each time guard fires; auto-clear pin at count >= 3.
- Frozen-position snapshots unguarded — serve incremental loss tracking, not operator control.

**`mmm_strike_shift.py` — `activate_new_strike()`**
- Added `side_state.pop('_trigger_pinned/value/adj_count', None)` — auto-clear on shift.

**`mmm_monitor.py` — `_process_replenish()`**
- Added same three pop() calls immediately after `side_state['active_strike'] = strike`.

**`mmm_api.py` — new `POST /session/<id>/pin-trigger`**
- Set path: fetch live premium, enforce `value > current_premium`, set pin fields + snapshot.
- Clear path: pop all three pin fields, resume ratchet.
- Logs `pin_trigger` / `unpin_trigger` activity. Emits `mmm_trigger_pin_changed` WS event.
- Follows same pattern as `set-active-strike` endpoint.

### Frontend changes

**`MMMTriggerGauge.js`**
- `TriggerSideGauge`: added drag handlers (onMouseDown → mousemove/mouseup on document).
- Loosen-only enforced client-side: `newValue = Math.max(rawValue, currentPremium)`.
- Pinned marker: cyan `#00bcd4`, lock icon 🔒, ratchet-disabled tooltip with countdown.
- Error snackbar on API failure — marker snaps back to server value.
- `_trigger_pinned`, `_pin_adj_count` props from `MMMTriggerGauge` parent via session state.

**`mmmService.js`**
- Added `pinTrigger(sessionId, side, value, clear=false)`.

### New session fields (per side)
- `_trigger_pinned`: bool
- `_pinned_trigger_value`: float
- `_pin_adj_count`: int (0–3, then auto-clear)

**Tests**: 52/52 sealed tests pass (trigger + strike_shift suites). No regressions.

**Files changed**: `mmm_trigger.py`, `mmm_strike_shift.py`, `mmm_monitor.py`, `mmm_api.py`, `MMMTriggerGauge.js`, `mmmService.js`

---

## 2026-03-30 — Trigger pin inline Unlock button + margin utilization fix

### Frontend

**`MMMTriggerGauge.js` — pin status line**
- Changed status line from plain text `🔒 Trigger locked at $X · unlocks after N adj`
  to `🔒 Locked at $X · [Unlock] · auto in N adj` where `Unlock` is an inline clickable
  span (underlined, PIN_COLOR, cursor pointer) calling the existing `handleUnpin` function.
- `handleUnpin` was already implemented — status line just needed to wire it up.

### Backend

**`mmm_margin_guardian.py` — `fetch_margin_utilization()`**
- Added `balance_minus_available` as a diagnostic field in the returned dict and in the
  `mmm_api.py` `/exchange/margin` response.
- Clarified comment: on Delta Exchange, `blocked_margin` can be NEGATIVE when option
  premium received exceeds gross margin requirement (portfolio margin mode). This is a
  healthy over-collateralized state — when blocked < 0, the actual liquidation risk is
  near-zero, and the 0% utilization reading is correct from a risk standpoint.
- `balance - available = blocked_margin` always (they are equal). Added primary check
  for `balance_minus_available > 0` for clarity, with original fallback chain unchanged.
- The exchange UI's "Initial Margin" (e.g., $375) is the GROSS requirement before
  netting premium credit. The API's `blocked_margin` is NET. Both are valid views;
  the dashboard shows the net risk metric which is correct for margin guardian purposes.
- `fetch_margin_utilization()` is NOT sealed (only `evaluate_margin_tier()` is sealed).
  This modification is valid.

**Note**: When `blocked_margin` is negative, the dashboard correctly shows 0% utilization.
The exchange UI's higher % is a gross/informational figure. No tier actions can/should fire

---

## 2026-03-30 — Expose proactive_shift_enabled toggle in Settings UI

- `mmm_config.py`: Added `proactive_shift_enabled` to `VALID_PARAMS` as `{type: bool, hot: True}` and to the help text section.
- `MMMSettingsDialog.js`: Added `proactive_shift_enabled` to the Trigger & Adjustment group params list (between `shift_target_premium` and `pre_sell_shift_enabled`) and added its help text to `FIELD_HELP`.
- Frontend rebuilt successfully.
- **Why**: Session mmm30mar26-1 post-mortem showed the proactive shift moved CE to 67200 at 22:42 (BTC ~65500-66000), and overnight BTC rally hit that strike triggering ATM Shield for -47.27 units. Operator needs a hot-reload toggle to disable proactive shifting without restarting the session.

---

## 2026-03-30 — Fix "Total Premium" display to show net (gross sells minus buybacks)

### Problem
`total_premium_collected` only accumulated on sells (entry + adjustments) and was never decremented when positions were bought back (close_at_5, ATM shield, wind-down). Dashboard showed inflated "Total Premium" that never decreased even after full position closures.

### Fix
- `mmm_pnl_core.py`: Added `compute_net_premium(session)` — iterates the fill ledger, sums `close_premium × lots × LOT_SIZE_BTC` for all non-migration entries by side, subtracts from gross totals. Returns `{total, ce, pe}`.
- `mmm_pnl_core.py`: `get_pnl()` now returns `net_premium_collected`, `ce_net_premium`, `pe_net_premium` in its result dict.
- `mmm_api.py`: Restructured `_overlay_live_pnl()` — removed early return on empty monitors, now processes ALL sessions. Running sessions get net premium from `compute_live_pnl()` (fresh in-memory ledger); stopped sessions get it computed from stored fill ledger.
- `MMMDashboard.js`: `totalPremium`, `cePremiumCollected`, `pePremiumCollected` now read `net_premium_collected`/`ce_net_premium`/`pe_net_premium` with fallback to gross fields for old sessions without ledger data. Label changed "Total Premium" → "Net Premium".

### Invariants preserved
- `total_premium_collected` (gross) unchanged — still used by `mmm_breakeven_engine.py`'s `breakeven_dte_pnl_clamp_pct` ratio logic.
- `compute_net_premium` skips `_is_migration` entries (which have `close_premium=0`) so migrated sessions display gross (unchanged behavior for historical data).
when the account is in a net credit state — the current behavior is correct.

---

## 2026-03-30 — Fix 4 Replenish Bugs: Wrong Strike Search + Dead-Monitor Guard

**Root cause investigation** of session `mmm30mar26-1` (PE fully closed, "Human Action Required" banner):

Logs showed `SHIFT FAILED: No OTM PE strike with premium >= $30` repeating for 13 minutes before close. Replenish never appeared in logs at all. Four bugs found:

### Bug 1: Wrong threshold (`shift_threshold` used instead of `replenish_min_premium`)
`find_new_strike` in `mmm_strike_shift.py` uses `shift_threshold` to filter candidates. When called from replenish, the correct threshold is `replenish_min_premium` — a lower bar for hedge coverage vs the higher shift quality bar. A strike acceptable for re-entry ($14 > $10 threshold) could be invisible if `shift_threshold` is higher.

### Bug 2: Old active_strike excluded from replenish candidates
`find_new_strike` skips `old_active_strike` (`abs(strike - old_strike) < 1`). For a shift this is correct — you're moving away from the current position. For replenish where PE has **0 lots**, the old active strike is a valid re-entry target and often the nearest-to-ATM candidate with the most remaining premium. This exclusion directly blocked the best available PE strike.

### Bug 3: Frozen strikes from 31 adjustments blocked near-ATM candidates
`find_new_strike` skips strikes with active frozen positions. With 31 adjustments, multiple PE frozen positions at various strikes silently blocked near-ATM replenish candidates. For replenish, a fresh entry at a strike with existing frozen lots is fine — they're tracked separately.

### Bug 4: Replenish never ran — fired inside watchdog-killed heartbeat
Watchdog stopped monitor at 16:38:43 (`_running=False`, `save_disabled=True`, `status→STOPPED`). The 85s heartbeat was still executing. At 16:39:06 it reached ONE-SIDE CLOSE, called `_process_replenish`, which hit Gate 2 (`status=STOPPED`) and returned False silently (INFO level log). `self.pause()` was called but `_save_my_session` was blocked by `save_disabled`. The unhedged state was never persisted to DB. New monitor started fresh from DB as RUNNING with no `_ocs_flag` — same loop on next restart.

### Fixes (`mmm_monitor.py` only — `mmm_strike_shift.py` net zero change)

**`mmm_monitor.py` — `_process_replenish()` (bugs 1, 2, 3):**
- Replaced `find_new_strike` with `self.initializer.get_full_chain(expiry)` + `self.initializer._rank_strikes(chain, opt_type, desired, chain_spot, above_spot, expiry, 'BTC')` — the same scoring used at session start.
- `preview_strikes()` was considered but rejected: it requires BOTH CE and PE to succeed simultaneously, which blocks PE replenish whenever CE has no suitable strike. We only need the closed side's chain.
- `above_spot=True` for CE (OTM calls above spot), `above_spot=False` for PE (OTM puts below spot). Each replenish only scans its own side of the chain.
- `desired_premium` = `params.get('desired_{closed_side}_premium', params.get('replenish_min_premium', 30.0))`.
- Chain's own `spot_price` used for OTM filter (fetched atomically with chain data).
- `replenish_min_premium` floor check still runs after `_rank_strikes` returns (unchanged).

**`mmm_monitor.py` — ONE-SIDE CLOSE GUARD (bug 4):**
- Added `_should_stop() or session.get('_save_disabled')` check at the top of the ONE-SIDE CLOSE for loop.
- If true: log warning, `break` — skip replenish and pause entirely. Let the next healthy monitor restart handle it cleanly from DB state.

**Tests**: 52/52 sealed (strike_shift + trigger); 1143 total passed, 0 new failures (10 pre-existing margin guardian failures unrelated to this work).


---

## 2026-03-30 — Fix: Replenish Bypassed Lot Velocity Limit (60 lots sold vs limit 30)

**Session**: `mmm31mar26-1` — PE side closed fully, replenish triggered, sold 60 PE lots in one shot despite `lot_velocity_limit=30`.

**Root causes (3 bugs):**

**Bug 1: No velocity gate in `check_replenish_eligibility`**
`mmm_replenish.py` had 10 gates but none checked `lot_velocity_limit`. Replenish fired freely even when the rolling window was already at the limit.
- **Fix**: Added Gate 11 — computes `lots_in_window` from `adjustment_history` (same logic as `check_lot_velocity`). Returns `False, 'lot_velocity_limit (...)'` if `lots_in_window >= limit`.

**Bug 2: No per-sell velocity cap in `_process_replenish`**
Even with an empty window (0 lots), `determine_replenish_lots(match_active)` returned 60 (matching CE's `active_lots`). A 60-lot single sell exceeded the 30-lot limit with no check.
- **Fix**: In `mmm_monitor.py` after `determine_replenish_lots`, compute velocity headroom (`limit - lots_in_window`). If `lots > headroom`, cap to `max(1, headroom)` and log the cap.

**Bug 3: Replenish lots not counted in future velocity checks**
After a replenish fill, lots were recorded in `_replenish_history` only. The `check_lot_velocity` function reads `adjustment_history` — so replenish lots were invisible to the velocity window, allowing the next replenish or adjustment to ignore the already-sold lots.
- **Fix**: After successful fill in `_process_replenish`, append an entry to `adjustment_history` with `aggressor='REPLENISH'` (matches existing exclusion list — OPERATOR/STRADDLE_ROLL are excluded, REPLENISH counts normally). Pruned to 200 entries same as regular adjustments.

**Files changed**: `mmm_replenish.py`, `mmm_monitor.py`

---

## 2026-03-30 (Session 2) — Fix: Regular Adjustment Also Bypassed Lot Velocity Limit (40 lots vs limit 30)

**Session**: `mmm31mar26-1` — CE adjustment fired 40 lots at 7:28 PM despite `lot_velocity_limit=30`.

**Root cause**: Same design gap as the replenish fix (Session 1 today), but in the regular `_process_adjustment` path.

`check_lot_velocity` in the safety stage only sets `_skip_to_pnl=True` when `lots_in_window >= limit`. It does NOT cap the per-sell amount. So:
- Window empty (0 lots), limit=30, `calculate_lots_to_sell` returns 40 → velocity check passes (0 < 30) → 40 lots sold → window now 40 (over limit in one shot).

**Fix**: Added velocity headroom cap in `_process_adjustment` after the IMP-5 consecutive-dir block and before `lots <= 0` check. Same pattern as replenish fix:
- Compute `lots_in_window` from `adjustment_history` (same window/params as `check_lot_velocity`)
- `_headroom = limit - lots_in_window`
- If `lots > _headroom`: cap to `max(1, _headroom)`, log the cap, append note to `constraint_msg`

This is the third location (after Gate 11 in `check_replenish_eligibility` and the headroom cap in `_process_replenish`) where the velocity headroom must be enforced. The safety-stage check is a gate-keeper but cannot substitute for per-sell capping since it can only see lots ALREADY in the window, not the lots about to be sold.

**Files changed**: `mmm_monitor.py`


---

## 2026-03-31 — Fix: P&L Calculation Incomplete False-Positive Pause (3 bugs)

**Context**: Session `mmm31mar26-1` paused with "P&L calculation incomplete — data unreliable". Never seen before, no Telegram warning was sent. Root cause was a cascade of 3 bugs.

**Bug 1 — `being_closed_lots_at` over-subtraction in `mmm_pnl_core.py`**
The 128-lot CE position had `_being_closed=True`, so `being_closed_lots_at[67800.0]=128`. The original code applied this FULL 128 deduction to EVERY fill at that strike via `max(0, lots - closing)`. With fills of 128/30/1/1 lots at 67800, all 4 were reduced to 0, making `_total_positions=0` for CE. With 0 CE positions, the 1 PE premium fetch became 1/1=100% failure rate, triggering the >50% incomplete threshold.
- **Fix** (`mmm_pnl_core.py`): Replaced flat deduction with a **depleting counter** `_remaining_bc = dict(being_closed_lots_at)`. Each fill at a given strike deducts from `_remaining_bc[strike]` in FIFO order via `_deduct = min(lots, _remaining_bc.get(strike, 0))`. The 128-lot fill consumes all 128 being-closed lots; the subsequent 30/1/1-lot fills get `_deduct=0` and count fully. `_total_positions` correctly becomes 5 (not 1).

**Bug 2 — Stale `_being_closed=True` with `_being_closed_at=None` in session DB**
The 128-lot CE position had `_being_closed=True, _being_closed_at=None`. The TTL auto-clear fires when `_being_closed_at` is None OR stale (>180s), but log shows it was cleared at 06:52:14 then re-set in the same heartbeat cycle. This left the position flagged as being-closed indefinitely.
- **Fix**: Direct sqlite3 update on `mmm_sessions.db` to clear `_being_closed` and `_being_closed_at` from the stuck CE position. Verified all CE positions show `_being_closed: false`.

**Bug 3 — SL/TP/Max-loss monitors never writing back to shared positions cache**
`_positions_cache` in `options_control.py` is populated ONLY by HTTP GET `/api/options/positions`. Three background monitors (`sl_tp_monitor`, `take_profit_manager`, `max_loss_manager`) each call `get_cached_positions(max_age=15)` every 5 seconds. When the browser tab is closed, the cache goes stale — every 5s check triggers a direct exchange REST call per monitor. Logs showed 5149+ "positions cache stale" warnings in one day.
- **Fix** (`options_control.py`): Added `update_positions_cache(positions)` writer function that updates `_positions_cache['data']` and `['time']`.
- **Fix** (`sl_tp_monitor.py`, `take_profit_manager.py`, `max_loss_manager.py`): After each successful direct fetch, call `update_positions_cache(fetched)`. Now: first stale check fetches + populates cache; next two 5s checks find cache age <15s → no fetch. Rate drops from 1 fetch/5s to ~1 fetch/15s per monitor.

**Files changed**: `mmm_pnl_core.py`, `mmm_sessions.db` (data fix), `options_control.py`, `sl_tp_monitor.py`, `take_profit_manager.py`, `max_loss_manager.py`

---

## 2026-03-31 (Review) — Harden _being_closed flag: timestamp missing in 4 setters

During post-fix review of the 2026-03-31 session, found that Bug 2 (stale `_being_closed` flag) could recur via a different path: 4 out of 6 call sites that set `_being_closed=True` never set `_being_closed_at`. This left positions with no timestamp, which `_check_stale_being_closed` treats as "infinitely stale" and auto-clears — but `close_position`'s inline stale check (`if set_at and ...`) treated `set_at=0` as falsy and would NOT auto-clear, creating an inconsistency.

**Missing `_being_closed_at` sites fixed:**
- `mmm_api.py` line ~4701 (manual close-strike endpoint)
- `mmm_api.py` line ~5217 (manual adjust-lots endpoint)
- `mmm_monitor.py` line ~3462 (wake-detection group close)
- `mmm_monitor.py` line ~5251 (harvester pre-mark)

All four now set `_being_closed_at = time.monotonic()` immediately after `_being_closed = True`. Added `import time` to `mmm_api.py` (was missing).

**Inconsistent stale check fixed:**
- `mmm_close_at_5.py` `close_position()` inline check at line ~334 changed from `if set_at and time.monotonic() - set_at > TTL` to `if not set_at or time.monotonic() - set_at > TTL` — now consistent with `_check_stale_being_closed`.

**Files changed**: `mmm_api.py`, `mmm_monitor.py`, `mmm_close_at_5.py`

---

## 2026-04-02 — Hedge break fix: replenish bypasses regime/wind-down, resets state on success

**Incident:** `mmm02apr26-1` — CE fully closed by close_at_5, replenish blocked by `BLOCK_ALL_SELLS` regime (Gate 6), session auto-stopped with PE=124 lots unhedged at 06:53 IST.

**Root cause:** `check_replenish_eligibility` had Gate 3 (wind-down active), Gate 4 (wind-down triggered flags), Gate 6 (regime BLOCK_ALL_SELLS) blocking replenish. Replenish is a defensive hedge-restoration action — these gates apply only to offensive adjustment sells.

**Fix 1 — `mmm_replenish.py` `check_replenish_eligibility`:**
- Removed Gate 3 (`wind_down_active` flag check — was: `params.get('wind_down_enabled') and session.get('_wind_down_active')`)
- Removed Gate 4 (`_atm_wind_down_triggered`, `_vol_wind_down_triggered`, `_trend_wind_down_triggered` flag checks)
- Removed Gate 6 (`_regime_action == BLOCK_ALL_SELLS` block)
- Added HEDGE RESTORATION PRINCIPLE docstring explaining why these gates are intentionally absent
- Remaining active gates: 1 (master switch), 2 (session status), 5 (margin), 7 (count cap), 8 (cooldown), 9 (near-expiry), 10 (open side has lots), 11 (lot velocity)

**Fix 2 — `mmm_monitor.py` `_process_close_at_5`:**
- Added `_orig_pos_closed_{side}` flag set when a position with `type='original'` closes.
- This allows ONE-SIDE CLOSE GUARD to trigger replenish even before all lots reach 0, when the anchor position closes.

**Fix 3 — `mmm_monitor.py` ONE-SIDE CLOSE GUARD:**
- Trigger condition extended: fires on `check_side_fully_closed(session, _cs) OR session.get(f'_orig_pos_closed_{_cs}')`.
- Flag cleared after successful replenish and in the else branch.

**Fix 4 — `mmm_monitor.py` `_process_replenish()`:**
- After every successful replenish, added full regime/trend state reset (clean slate = new session start):
  - Trend: `_trend_anchor_spot` reset to current spot, `_trend_regime='NORMAL'`, `_trend_tier=0`, `_trend_direction='none'`, calm/plateau/T4 beat counters zeroed, EMA/high/low/since popped.
  - Vol: `_vol_regime='NORMAL'`, `_vol_regime_beats_below=0`, `_vol_wind_down_triggered=False`.
  - Wind-down: `_atm_wind_down_triggered=False`.
  - Regime action: `_regime_action` key popped.
  - Consecutive block: `_consecutive_dir_blocked=False`, counts/side reset.
  - One-side-closed flags: `_one_side_closed_ce`, `_one_side_closed_pe`, `_orig_pos_closed_ce`, `_orig_pos_closed_pe` all popped.
  - Awaiting user action flags cleared.

**Fix 5 — `tests/test_sealed_mmm_replenish.py`:**
- 4 sealed tests updated to reflect new design (Gates 3/4/6 removed):
  - `test_blocked_when_atm_wind_down` → `test_eligible_despite_atm_wind_down` (now asserts ok=True)
  - `test_blocked_when_vol_wind_down` → `test_eligible_despite_vol_wind_down` (now asserts ok=True)
  - `test_blocked_when_trend_wind_down` → `test_eligible_despite_trend_wind_down` (now asserts ok=True)
  - `test_blocked_when_regime_blocks_all_sells` → `test_eligible_despite_regime_block_all_sells` (now asserts ok=True)

**Test result:** 1225 passed, 0 failed.

**Files changed:** `mmm_replenish.py`, `mmm_monitor.py`, `tests/test_sealed_mmm_replenish.py`

---

## 2026-04-02 (Session 2) — MMM Final Hardening: retry system, watchdog, stop lock, partial fill

**Objective:** Eliminate all remaining execution-level failure risks from the replenish system.

**New params added to DEFAULT_PARAMS + HOT_RELOAD_PARAMS (`mmm_state.py`):**
- `replenish_retry_max=3` — fast-path retries within one `_process_replenish` call
- `replenish_retry_delay_sec=2` — seconds between retry attempts
- `replenish_max_reprice_attempts=2` — reprice cycles per smart_execute call (caps each attempt to ~2 min)

**Fix 1 — `mmm_replenish.py` Gate 2: PAUSED allowed during OCS recovery**
- PAUSED sessions are now eligible for replenish when `_replenish_ocs_active=True`
- This flag is set by the OCS guard before each replenish attempt, so the watchdog can fire even after a PAUSE
- STOPPED is still always blocked (no monitor running = no replenish)
- Added 2 new sealed tests: PAUSED+OCS=eligible; STOPPED+OCS=still blocked

**Fix 2 — `mmm_monitor.py` `_process_replenish()`: retry system + partial fill**
- Steps 3-5 (spot fetch + strike find + execute) now wrapped in retry loop (up to `replenish_retry_max` attempts)
- Retry policy: retry on no_spot, no_strike, fast execution failure (no order placed). Hard stop on: premium<min (market condition), execution failure with active order (risk of duplicate).
- Fixed `result.get('size', lots)` → `result.get('filled_size', lots_to_sell)` — was always using requested lots, not actual fill
- Partial fill detection: if `filled_lots < lots_to_sell`, sets `_replenish_lots_remaining_{side}` and `_replenish_ocs_active=True` — OCS watchdog tops up on next heartbeat
- Partial fill top-up: if `_replenish_lots_remaining_{side} > 0`, uses remaining lots instead of recalculating full amount
- All `result.` references in Step 6 updated to `_exec_result.`

**Fix 3 — `mmm_monitor.py` OCS guard: watchdog expansion + stop lock**
- OCS trigger now fires on: (a) side fully closed [existing], OR (b) `_replenish_ocs_active` + `_replenish_lots_remaining_{cs} > 0` [new — partial fill top-up]
- Sets `_replenish_ocs_active=True` before each replenish attempt (enables Gate 2 bypass in replenish.py)
- STOP LOCK: in off-hours path, if `_os_lots > 0`, converts STOP → PAUSE with explanatory reason. STOP only if truly 0 open lots.
- `else` branch (side regains lots) now also clears `_replenish_ocs_active` and `_replenish_lots_remaining_{cs}`
- Regime reset block now also pops `_replenish_ocs_active` and `_replenish_lots_remaining_{closed_side}`

**Failure Point Map addressed:**
| Failure | Before | After |
|---|---|---|
| No spot price | return False | retry up to 3× with 2s delay |
| No strike / chain fail | return False | retry up to 3× with 2s delay |
| API rejection (fast) | return False | retry up to 3× with 2s delay |
| Partial fill | registered as full fill (bug) | partial registered, remainder queued |
| Off-hours STOP with open lots | killed monitor, no recovery | PAUSE — monitor keeps running, watchdog retries |
| PAUSED blocks replenish (Gate 2) | blocked on all subsequent beats | allowed when `_replenish_ocs_active=True` |
| Silent failure | log only | OCS watchdog retries every heartbeat |

**Test result:** 1227 passed (+2 new tests), 0 failed.

**Files changed:** `mmm_state.py`, `mmm_replenish.py`, `mmm_monitor.py`, `tests/test_sealed_mmm_replenish.py`

---

## 2026-04-03 (Session 1) — Gamma HARD hedger exemption

**Problem:** When gamma hits the HARD limit while market is going down, `_compute_regime_action` returned `ACTION_BLOCK_ALL_SELLS`. This blocked the CE hedge sell even though CE is the safe side when market goes down (PE is the aggressor). "Regime blocked CE sell: Gamma HARD" was appearing in logs.

**Root cause:** Priority 4 in `_compute_regime_action` (`mmm_regime.py:808`) always returned `ACTION_BLOCK_ALL_SELLS` for gamma=HARD with no regard for market direction or which side is the danger side.

**Fix — `mmm_regime.py` `_compute_regime_action` Priority 4:**
- Vol is already confirmed NORMAL at Priority 4 (HIGH/ELEVATED handled at P3/P3b).
- When `_trend_regime == TREND_DOWN` (market going down): return `ACTION_BLOCK_PE_SELLS` — PE is the aggressor/danger side, CE hedge is free.
- When `_trend_regime == TREND_UP` (market going up): return `ACTION_BLOCK_CE_SELLS` — CE is the aggressor/danger side, PE hedge is free.
- When `_trend_regime == TREND_NORMAL` (no clear direction): return `ACTION_BLOCK_ALL_SELLS` — conservative fallback unchanged.

**Fix — `mmm_regime.py` `should_block_sell`:**
- Updated reason strings for `ACTION_BLOCK_CE_SELLS` and `ACTION_BLOCK_PE_SELLS` blocks: when gamma=HARD, emits "Gamma HARD (market up/down, X is aggressor side)" instead of "Trend UP/DOWN Tier X" for accurate log attribution.

**Tests — `tests/test_sealed_mmm_regime.py`:**
- Renamed `test_c_cra_6_gamma_hard` → `test_c_cra_6_gamma_hard_no_trend` (gamma HARD + TREND_NORMAL → BLOCK_ALL_SELLS still passes).
- Added `test_c_cra_6b_gamma_hard_trend_down_blocks_pe_only`: asserts BLOCK_PE_SELLS.
- Added `test_c_cra_6c_gamma_hard_trend_up_blocks_ce_only`: asserts BLOCK_CE_SELLS.

**Test result:** 1229 passed (+2 new tests), 0 failed.

**Files changed:** `mmm_regime.py`, `tests/test_sealed_mmm_regime.py`

---

## 2026-04-03 (Session 2) — Gamma improvements: Tier B/C/D (institutional approach)

**Objective:** Fix the root cause of gamma HARD over-blocking near expiry. Three tiers:
- Tier B: per-side dollar gamma — block only the ATM (danger) side, allow the OTM (hedge) side
- Tier C: DTE-aware hedge limit relaxation — near expiry, the hedge limit is relaxed for hedge sells
- Tier D: Delta rescue — when within N minutes to expiry, a forced hedge sell overrides any gamma block

**Tier B — `mmm_regime.py` `_update_gamma_cap` + `_compute_regime_action`:**
- `_update_gamma_cap`: added per-side gamma computation. Splits `positions` list (tuples of `(greek_gamma, lots, opt)`) by `opt == 'C'` (CE) and `opt == 'P'` (PE). Stores `_ce_dollar_gamma` and `_pe_dollar_gamma` in session.
- `_compute_regime_action` Priority 4 (gamma=HARD): replaced trend-direction proxy with 3-step logic:
  - Step 1 (Tier B): if one side's dollar gamma ≥ `gamma_side_imbalance_ratio` × the other → block that side only (it's near ATM). Default ratio: 1.5.
  - Step 2 (Tier C): if balanced gamma AND in DTE relax window AND dollar_gamma < relaxed hedge limit → use trend as tiebreaker.
  - Step 3: BLOCK_ALL_SELLS (conservative fallback).
- `should_block_sell`: updated directional block reason strings to show per-side dollar gamma values when gamma is HARD.
- `get_regime_status`: added `ce_dollar_gamma`, `pe_dollar_gamma`, `gamma_hard_limit_hedge`, `gamma_dte_relax_active`, `delta_rescue_count` to details dict.

**Tier C — `mmm_regime.py` `_update_gamma_cap`:**
- After near-expiry multiplier applies, computes `hard_limit_hedge = hard_limit × gamma_dte_hedge_multiplier` when `minutes_to_expiry <= gamma_dte_relax_hours × 60`.
- Stores `_gamma_dte_relax_active` (bool) and `_gamma_hard_limit_hedge_effective` in session.
- In the DTE window (e.g., last 2h): hedge sell limit is 2× the standard hard limit. Outside window: same as standard.
- Example: standard hard=5000, in last 2h → hedge hard=10000. If dollar_gamma=6000: HARD by standard, but below hedge limit → directional block instead of BLOCK_ALL.

**Tier D — `mmm_monitor.py` `_heartbeat` (adjustment flow, ~line 2780):**
- After `should_block_sell` returns `blocked=True`, before the block is acted on: check if `regime_action not in (ACTION_FORCE_REDUCE, ACTION_PAUSE)` AND `minutes_to_expiry <= gamma_rescue_window_minutes`.
- If both True: override `blocked = False`, log `delta_rescue` activity + emit_safety warning, increment `_delta_rescue_count`, store `_delta_rescue_last_at`.
- Wind-down and margin blocks are NOT overridden (they come in the elif chain below).
- Only FORCE_REDUCE (gamma emergency) and PAUSE survive the rescue.

**New params — `mmm_state.py` DEFAULT_PARAMS + HOT_RELOAD_PARAMS:**
- `gamma_side_imbalance_ratio: 1.5` — one side must contribute ≥ 1.5× the other's dollar gamma to be considered dominant
- `gamma_dte_relax_hours: 2.0` — hours before expiry where hedge limit is relaxed
- `gamma_dte_hedge_multiplier: 2.0` — multiply hard_limit by this for hedge sells in DTE window
- `gamma_rescue_window_minutes: 120` — minutes to expiry within which delta rescue fires

**Tests — `tests/test_sealed_mmm_regime.py` (+7 new tests, 2 tests updated):**
- Replaced trend-proxy tests (6b/6c) with per-side gamma tests
- `test_c_cra_6_gamma_hard_no_side_data_blocks_all`: no per-side data → BLOCK_ALL_SELLS (conservative)
- `test_c_cra_6b_gamma_hard_pe_dominant_blocks_pe_only`: PE $Γ=2500, CE $Γ=1000 → BLOCK_PE_SELLS
- `test_c_cra_6c_gamma_hard_ce_dominant_blocks_ce_only`: CE $Γ=2500, PE $Γ=1000 → BLOCK_CE_SELLS
- `test_c_cra_6d_gamma_hard_balanced_gamma_blocks_all`: ratio 1.1 < 1.5 → BLOCK_ALL_SELLS
- `test_c_cra_6e_gamma_hard_only_pe_positions_blocks_pe`: CE=0, PE=3000 → BLOCK_PE_SELLS
- `test_c_cra_6f_dte_relax_trend_down_breaks_tie_blocks_pe`: balanced + DTE relax + TREND_DOWN → BLOCK_PE_SELLS
- `test_c_cra_6g_dte_relax_above_hedge_limit_blocks_all`: above relaxed limit → BLOCK_ALL_SELLS
- `test_c_cra_6h_dte_relax_no_trend_blocks_all`: DTE relax + TREND_NORMAL → BLOCK_ALL_SELLS

**Test result:** 1234 passed (+5 net new tests), 0 failed.

**Files changed:** `mmm_regime.py`, `mmm_monitor.py`, `mmm_state.py`, `tests/test_sealed_mmm_regime.py`

---

## 2026-04-03 (Session 3) — Deep review: vol=ELEVATED+gamma=HARD bug fix + config validation

**Bug found in Session 2 review:**

Priority 4 of `_compute_regime_action` now runs before Priority 5 (vol=ELEVATED check). When both `vol=ELEVATED` AND `gamma=HARD`, the new code returned a directional block (BLOCK_PE_SELLS or BLOCK_CE_SELLS) instead of BLOCK_ALL_SELLS. This bypassed the vol=ELEVATED safety check entirely — trigger evaluation would run and hedge sells could proceed during elevated vol, which is dangerous.

**Fix — `mmm_regime.py` `_compute_regime_action` Priority 4:**
- Added guard at the top of the GAMMA_HARD block: `if vol_regime == VOL_ELEVATED: return ACTION_BLOCK_ALL_SELLS`
- This ensures compound risk (vol elevated + gamma hard) always stays at maximum block
- Tier B/C exemptions (per-side gamma, DTE relax) only apply when vol is NORMAL

**New sealed test:**
- `test_c_cra_5b_vol_elevated_gamma_hard_blocks_all`: vol=ELEVATED + gamma=HARD + PE dominant per-side gamma + DTE relax active → still BLOCK_ALL_SELLS. This would have been BLOCK_PE_SELLS without the fix.

**Missing from Session 2 — fixed now:**
- `mmm_config.py` PARAM_SCHEMA: 4 new params were not validated. Added with proper types and bounds:
  - `gamma_side_imbalance_ratio`: float, min=1.1, max=10.0
  - `gamma_dte_relax_hours`: float, min=0.25, max=6.0
  - `gamma_dte_hedge_multiplier`: float, min=1.0, max=5.0
  - `gamma_rescue_window_minutes`: float, min=0, max=480
- `mmm_config.py` descriptions: added human-readable descriptions for all 4 new params
- Docstring in `_compute_regime_action`: updated Priority 4 entry to reflect new behavior

**Test result:** 1235 passed (+1 new test), 0 failed.

**Files changed:** `mmm_regime.py`, `mmm_config.py`, `tests/test_sealed_mmm_regime.py`

---

## 2026-04-03 (Session 4) — WebUI: 4 new gamma params added to MMMSettingsDialog

**Params added to `regimeControls.params` array in `MMMSettingsDialog.js`** (after `gamma_near_expiry_multiplier`):
- `gamma_side_imbalance_ratio` — Tier B imbalance ratio
- `gamma_dte_relax_hours` — Tier C DTE relax window
- `gamma_dte_hedge_multiplier` — Tier C relaxed hedge multiplier
- `gamma_rescue_window_minutes` — Tier D delta rescue window

**Also added:** 4 detailed tooltip strings in `PARAM_TOOLTIPS` const explaining each param's purpose, default, and operating range.

**Frontend rebuilt:** `npm run build` — all bundle sizes within budget. Build timestamp: 2026-04-03 09:20.

**Location in UI:** These 4 params appear in the **Regime Controls** section (orange heading), just after `gamma_near_expiry_multiplier`, before the trend params. All 4 show hot-reload badges and `(?)` tooltip icons.

**Backend confirmed:** `/api/mmm/params/info` returns all 4 params with correct types, bounds, and `hot_reload: true`.

**Files changed:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`

---

## 2026-04-03 — Settings Navigator System

- `feat(mmm-ui)`: Replaced the single long-scroll settings dialog with a 3-mode navigator UX
- **Navigator screen** (default on open): 21 section cards in a 3-column grid, each showing title, param count badge, and 2-line blurb. Clicking a card opens that section. My Controls card shown at top when params are pinned.
- **Section view**: Left sidebar lists all 21 sections with color accents and counts — click any to switch instantly without going back. Main area shows only the selected section's params. Back button in title bar returns to navigator.
- **Search mode**: Unchanged — flat param list across all groups, exactly as before.
- **Bottom bar**: Shows "← Navigator" button instead of Cancel when in section view (without active search), so user can always return.
- Zero logic changes: handleSave, handleChange, renderParam, PARAM_GROUPS, PARAM_TOOLTIPS, pinning, conflict warnings, adaptive badges all untouched.
- **Files changed:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`

---

## 2026-04-03 (Session 5) — Critical bug fix: per-side gamma opt string mismatch

**Root cause:** `mmm_monitor.py` `_calculate_portfolio_delta()` built `gamma_positions` tuples using `opt = 'call'` or `'put'` (line ~9343). But `_update_gamma_cap()` in `mmm_regime.py` filtered using `opt == 'C'` and `opt == 'P'`. Nothing ever matched → `_ce_dollar_gamma` and `_pe_dollar_gamma` always 0.0 → Tier B (per-side imbalance) never fired → always fell through to Step 3 (BLOCK_ALL_SELLS). This meant the entire Tier B/C/D feature built in Sessions 1–4 was silently broken in production.

**Symptom:** "Regime blocked PE sell: Gamma HARD" when market was going UP (PE is hedger, CE is aggressor). Per-side gamma was 0/0, so BLOCK_ALL_SELLS blocked both sides. The regime status API confirmed `_ce_dollar_gamma: 0.0`, `_pe_dollar_gamma: 0.0`, `gamma_data positions: 0`.

**Fix — `mmm_monitor.py` ~line 9465:**
- Added `opt_char = 'C' if opt == 'call' else 'P'`
- Changed `gamma_positions.append((greek_gamma, lots, opt))` → `gamma_positions.append((greek_gamma, lots, opt_char))`

**New sealed test — `test_c_ugc_opt_string_call_put_produces_per_side_gamma`:**
- Calls `_update_gamma_cap` directly with `'C'`/`'P'` opt strings (the canonical form)
- Verifies CE and PE dollar gamma are > 0 and CE dominates when CE positions have higher gamma
- Seals the opt string contract so this regression cannot silently recur

**After fix — verified live:** `_ce_dollar_gamma: 3430.68`, `_pe_dollar_gamma: 2561.29`. BLOCK_ALL_SELLS now fires because ratio (1.34) is below the 1.5 threshold — correct behavior. User can hot-reload `gamma_side_imbalance_ratio` to 1.2 to get directional block at this imbalance level.

**Test result:** 1236 passed (+1 new test), 0 failed.

**Files changed:** `mmm_monitor.py`, `tests/test_sealed_mmm_regime.py`

---

## 2026-04-03 — Settings Navigator: Category Color System

- `feat(mmm-ui)`: Added semantic category color system to Settings Navigator
- **4 categories defined** with distinct color families: CRITICAL (red #ef4444), CORE (blue #3b82f6), EXECUTION (green #10b981), ADVANCED (purple #a855f7)
- **Navigator grid sorted** by category: CRITICAL first (Safety, Margin Guardian, Expiry, Wind-Down, ATM Shield, Lot Velocity, Consecutive Direction), then CORE, EXECUTION, ADVANCED
- **Category divider rows** separate each group with colored dot + label + gradient rule (e.g. "⚠ Risk & Safety", "⚙ Core Strategy")
- **Each card** gets category-tinted bg + category-colored border + small CRITICAL/CORE/EXECUTION/ADVANCED badge — replaces the flat `#1c2128` uniform look
- **Sidebar dots**: tiny 6px colored dot before each section name in the section-view sidebar (colored by category, dim when not active)
- Zero logic changes. Zero backend changes. All 21 PARAM_GROUPS keys covered in SECTION_CATEGORY map.
- Build: clean (warnings pre-existing, all bundle sizes within budget)
- **Files changed:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`

---

## 2026-04-03 — Settings Search: Grouped Results + Rich Matching

- `feat(mmm-ui)`: Completely replaced flat search results with grouped-by-section view
- **Search field**: Added Search icon (left adornment), × clear button (right, appears when text present), blue border highlight when active, better placeholder text
- **Grouped results**: Each matching section gets its own header (colored bar + title + category badge + "N matches" chip + "→ open section" icon button)
- **Rich matching**: Now searches param key + backend description + PARAM_TOOLTIPS text + section title. Previously only matched param key + description. Typing "atm" now finds all ATM Shield params, ATM-related tooltips in Safety/Triggers, etc.
- **Summary bar**: "12 params across 3 sections" shown at top of results
- **Empty state**: Icon + message + hint text instead of plain text
- **"→" button**: Clicking it clears search and opens that section directly
- Zero logic changes. Build clean.
- **Files changed:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`

---

## 2026-04-03 (Session 6) — Critical fix: anchor-direction as Step 1 for gamma HARD blocking

**Root cause discovered (deeper than Session 5):** Even with per-side gamma correctly populated (`'C'`/`'P'` fix in Session 5), the per-side gamma approach is FUNDAMENTALLY WRONG for same-strike straddles. When CE and PE are at the same strike (67000), they have identical gamma-per-lot by put-call parity. The only difference in TOTAL dollar gamma is lot count — PE had 143 lots vs CE 100 lots, making PE's total gamma 44% higher even though CE (calls) were ITM (spot > strike). The algo was comparing the wrong thing.

**Real diagnostic (live session):**
- CE: 100 lots, strike 67000, dollar gamma $3527 → $35.27/lot
- PE: 143 lots, strike 67000, dollar gamma $5018 → $35.09/lot  
- Spot: $67,214 (CE is ITM) — market going UP → CE is aggressor
- But PE total gamma > CE total gamma purely because more lots
- Step 1 (per-side gamma) failed to fire (1.44 < 1.5 threshold)
- → BLOCK_ALL_SELLS → PE hedge blocked → wrong

**Fix — `mmm_regime.py` Priority 4 — new Step 1 (anchor direction):**
New ordering:
1. **Anchor direction** (primary): `(spot - anchor) / anchor × 100 >= gamma_directional_min_pct` → market UP → BLOCK_CE_SELLS; market DOWN → BLOCK_PE_SELLS. Dead-band prevents flip-flopping.
2. **Per-side gamma imbalance** (tiebreaker when flat): unchanged
3. **DTE relax** (near expiry): unchanged
4. **BLOCK_ALL_SELLS** (fallback): unchanged

**New param:** `gamma_directional_min_pct: 0.10` — minimum % move from anchor for Step 1 to fire. Added to DEFAULT_PARAMS, HOT_RELOAD_PARAMS, PARAM_SCHEMA, descriptions, and MMMSettingsDialog.js.

**New sealed tests (3):**
- `test_c_cra_6i_anchor_up_blocks_ce`: +0.30% from anchor, PE has MORE total gamma (lot asymmetry) → Step 1 fires → BLOCK_CE_SELLS (not BLOCK_PE)
- `test_c_cra_6j_anchor_down_blocks_pe`: -0.30% from anchor, CE has MORE total gamma → Step 1 fires → BLOCK_PE_SELLS (not BLOCK_CE)  
- `test_c_cra_6k_anchor_flat_falls_to_gamma_imbalance`: +0.075% (inside dead-band) → Step 1 skips → Step 2 fires on PE dominant gamma

**Test result:** 1239 passed (+3 new tests), 0 failed. Frontend rebuilt, backend restarted.

**Files changed:** `mmm_regime.py`, `mmm_state.py`, `mmm_config.py`, `tests/test_sealed_mmm_regime.py`, `webui/frontend/src/components/mmm/MMMSettingsDialog.js`

---

## 2026-04-03 (Session 7) — Audit + fix of mmm_gamma.py extraction (4 bugs)

**Context:** A previous AI wrote the gamma extraction plan describing `mmm_gamma.py` as future work. Audit revealed it had already been created in the same session — and had 4 bugs introduced during the extraction.

**Bug 1 + 2 — `GammaData` had vestigial `ce_dollar_gamma`/`pe_dollar_gamma` fields always = 0:**
- `compute_gamma_data` accepted `spot_price` but was called with `0.0` (hardcoded in monitor)
- `if spot_price > 0` guard meant ce/pe dollar gamma in GammaData were always 0
- `_update_gamma_cap` recomputed them correctly from `positions` using its own spot_price — duplicate computation, one always wrong
- **Fix:** Removed `spot_price` param from `compute_gamma_data` (raw data only — no dollar gamma). Removed `ce_dollar_gamma`/`pe_dollar_gamma` from `GammaData` TypedDict. Dollar gamma belongs solely in `_update_gamma_cap` which has spot_price.

**Bug 3 — GAMMA constants defined in two files:**
- Both `mmm_gamma.py` and `mmm_regime.py` independently defined `GAMMA_NORMAL = 'NORMAL'` etc
- **Fix:** Removed from `mmm_regime.py`. Added `from .mmm_gamma import GAMMA_NORMAL, GAMMA_SOFT, GAMMA_HARD, GAMMA_EMERGENCY`. Single source.

**Bug 4 — `_safe_greek` duplicated:**
- Defined as module-level in `mmm_gamma.py` and redefined as inner function in `_calculate_portfolio_delta`
- **Fix:** Removed local redefinition. Added to `mmm_gamma` import in monitor's try block.

**Tests:** Updated `test_sealed_mmm_gamma.py` — `test_c_cgd_1/2/3` updated to 2-arg `compute_gamma_data` signature; `test_c_cgd_2` rewritten to test positions list instead of removed GammaData fields. **1248 passed, 0 failed.**

**Plan file:** `docs/plan_gamma_extraction.md` rewritten — now accurately describes completed work, all 4 bugs and their fixes, remaining cosmetic cleanup items, and final architecture diagram.

**Files changed:** `mmm_gamma.py`, `mmm_monitor.py`, `mmm_regime.py`, `tests/test_sealed_mmm_gamma.py`, `docs/plan_gamma_extraction.md`

---

## 2026-04-03 (Session 8) — Fix gamma_dte_relax_hours min=0 inconsistency

**Bug found in audit:** `mmm_config.py` had `'gamma_dte_relax_hours': {'min': 0.25}` but the frontend tooltip said "Set to 0 to disable". User couldn't actually set it to 0 — API validation would reject with min-violation error.

**Fix:**
- `mmm_config.py` line 104: changed `min: 0.25` → `min: 0`
- `mmm_gamma.py` `_update_gamma_cap` line 263: added `dte_relax_hours > 0` guard so `0` actually disables Tier C (DTE relax window never activates)
- `mmm_config.py` tooltip line 547: updated to say "Set to 0 to disable Tier C entirely"

**Files changed:** `mmm_config.py`, `mmm_gamma.py`

---

## 2026-04-04 — OCS auto-resume after hedge restored

- **`mmm_monitor.py`**: Added auto-resume logic in the ONE-SIDE CLOSE GUARD for two paths:
  1. After full replenish succeeds (line ~1870): if session is paused and `_paused_reason` contains `'{CS} fully closed'`, call `self.resume()`.
  2. In the else branch when the closed side regains lots externally (line ~2020): same check and resume.
- **Why:** Session mmm04apr26-1 was paused off-hours by the stop-lock (CE closed, PE=100 lots protected). Auto-replenish restored CE=100 lots, clearing all OCS flags, but no auto-resume fired. The existing auto-resume at line 2365 only covers 'Regime pause' and 'Gamma emergency' — OCS pauses had no auto-resume path.
- Both resume paths are guarded: `self._paused=True` + pause reason must match `'{cs.upper()} fully closed'` to prevent resuming sessions paused for unrelated reasons.

**Files changed:** `mmm_monitor.py`

---

## 2026-04-04 — Gamma cap incremental budget fix

- **`mmm_regime.py` `check_projected_gamma`**: Added incremental gamma budget path. When `gamma_incremental_limit > 0` AND current portfolio dollar gamma already ≥ hard_limit, switch from "total projected vs hard_limit" to "incremental added by this trade vs gamma_incremental_limit". If the trade's incremental dollar gamma ≤ budget, allow it.
- **`mmm_config.py`**: Registered `gamma_incremental_limit` (float, 0–5000, hot-reloadable, default 0 = disabled / preserves prior block-all behavior).
- **Why**: With near-ATM 0DTE positions (e.g. CE 67000 + PE 66800 at spot 66836), portfolio dollar gamma is ~$10,000 all day — 2× the $5,000 hard_limit. The prior logic (`projected > hard_limit → block`) entered a "once breached, always blocked" freeze, disabling all adjustments for the entire session. Fix: when already in breach, evaluate each trade on its marginal gamma cost, not the total.
- **How to activate**: Set `gamma_incremental_limit = 500` (allows trades adding ≤$500 incremental gamma). Leave at 0 to keep old behavior.
- **Backward compatible**: default=0 means zero behavior change until explicitly configured.

**Files changed:** `mmm_regime.py`, `mmm_config.py`

---

## 2026-04-04 — Guardian violation: Telegram alert + auto-heal

**Root cause**: Session paused with "Guardian violations: 1 invariant(s) breached" (G3 — side wipeout) but no Telegram alert fired and no auto-heal existed. CE=30 lots, PE=100 lots visible in UI — hedge was intact, G3 fired momentarily (likely during fill processing state sync where positions show 0 before fills applied).

- **`mmm_telegram.py`**: Added `alert_guardian_violation()` and `alert_guardian_healed()` — same pattern as `alert_stale_monitor`.
- **`mmm_guardian.py`**: 
  - `handle_violations()`: Added `asyncio.ensure_future(alert_guardian_violation(...))` — was previously only emitting via WebSocket, no Telegram.
  - Added `check_g3_healed(session)`: Returns True if both sides have `total_lots > 0` (G3 condition resolved). Used by auto-heal path.
- **`mmm_monitor.py`**: Added auto-heal block before "Step 4" (both-sides-up check). If paused reason starts with `'Guardian violations:'` and `check_g3_healed()` returns True → `log_activity('guardian_auto_heal')` + Telegram `alert_guardian_healed` + `self.resume('Guardian healed — both sides have positions')`.

**Why**: G3 can fire transiently (fill sync window), permanently stalling a healthy session. Auto-heal mirrors the existing regime-pause auto-resume pattern. Real wipeouts (side truly at 0) do NOT heal — session correctly stays paused.

**Files changed:** `mmm_telegram.py`, `mmm_guardian.py`, `mmm_monitor.py`

---

## 2026-04-04 — Strike shift: fix fallback + stale cache causing wrong-strike orders

**Root cause**: When `find_new_strike` returned None (no viable new strike found), `_process_strike_shift` fell back to `_process_shift_fallback` which sold at the CURRENT DECAYED active strike (e.g. PE 66400 @ $8.8 — far below shift_target_premium of $50). Additionally, `find_new_strike` used cached chain data (TTL 5-10s) which could be stale, causing it to miss available strikes like 66800 @ $54 that were visible on the exchange.

- **`mmm_monitor.py` — `_process_strike_shift` (shift failure path)**: Removed the `_process_shift_fallback` call when no suitable strike is found. Now logs a warning and returns without placing any order. Will retry next heartbeat. Selling at a decayed sub-threshold strike defeats the purpose of the premium floor.

- **`mmm_monitor.py` — `_process_strike_shift` (before `find_new_strike`)**: Added cache invalidation (`chain_service.invalidate_cache`) immediately before calling `find_new_strike`. Shifts are infrequent and critical — fresh API data is always used. If the first scan returns no candidates, a second attempt is made with freshly fetched spot price + invalidated cache.

**Files changed:** `mmm_monitor.py`

---

## 2026-04-04 — Shift: continuous background pre-scan for instant strike readiness

**User request**: "even if bot is not firing any order it keeps scanning the option chain so that this problem never arises"

- **`mmm_strike_shift.py` — `pre_scan_shift_candidates(initializer, session, spot_price)`**: New function. Runs `find_new_strike` for both CE and PE every heartbeat (regardless of whether any adjustment fires). Stores the best candidate for each side in `session['_shift_candidates']` with timestamp, shift_threshold, and shift_target_premium at scan time.

- **`mmm_monitor.py` — `_heartbeat`**: Calls `pre_scan_shift_candidates` immediately after `_prefetch_all_premiums`, before any trading decisions. This runs every heartbeat unconditionally. Uses the cached spot price (fresh from the heartbeat's `_fetch_spot_price`).

- **`mmm_monitor.py` — `_process_strike_shift`**: When a shift fires, first checks `session['_shift_candidates'][side]`. If the candidate is ≤60s old AND was found under the same shift_threshold/shift_target_premium config → use it directly (no chain API call). If stale, missing, or config changed → fall back to the existing cache-invalidated fresh scan + retry-with-fresh-spot path.

**Effect**: The chain is scanned once per heartbeat proactively. By the time a shift fires (same heartbeat), the answer is already known. The stale-cache problem that caused 66400@$8.8 to be sold instead of 66800@$54 is eliminated.

**Files changed:** `mmm_strike_shift.py`, `mmm_monitor.py`

---

## 2026-04-04 — Shift: live premium validation before order placement (0DTE guard)

**User request**: Before placing the shift order, verify the selected strike's current premium is still near shift_target_premium±tolerance. If it drifted, rescan.

- **`mmm_config.py`**: Registered `shift_premium_tolerance` (float, 0–500, hot, default 10).
- **`mmm_state.py`**: Added default `shift_premium_tolerance: 10.0` and added to hot-reload whitelist.
- **`mmm_monitor.py` — `_process_strike_shift`**: After `new_strike_info` is resolved (from pre-scan or fresh scan) and BEFORE `freeze_current_positions`, fetches the candidate's live premium via `chain_service.get_option_ticker`. If `|live_premium - shift_target_premium| > tolerance`: logs `shift_candidate_stale`, flushes chain cache, rescans. If rescan finds a better strike → uses it. If rescan finds nothing → proceeds with original candidate (best available). Tolerance=0 disables the check.

**Why**: 0DTE premiums move fast. A pre-scan finding 66800@$54 can be stale by $10+ within the same heartbeat cycle. The live check catches this before freezing positions (irreversible step).

**Files changed:** `mmm_config.py`, `mmm_state.py`, `mmm_monitor.py`

---

## 2026-04-04 — Deep audit + fixes + WebUI update + STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md

**Post-implementation audit of all session changes. 5 bugs found and fixed:**

1. **CRITICAL — `NameError` in `_process_strike_shift`** (`mmm_monitor.py`): `params` was used at line ~4816 (validation block) but not defined until line ~4896. Moved `params = session.get('params', {})` to method top, removed duplicate at old location.

2. **MEDIUM — `check_g3_healed` used `total_lots` (wrong)** (`mmm_guardian.py`): `total_lots` includes frozen positions from old strikes. A side with only frozen lots and `active_lots=0` is still unhedged — G3 would incorrectly report healed. Changed to `active_lots > 0` on both sides.

3. **MEDIUM — Auto-heal didn't set `_skip_to_pnl`** (`mmm_monitor.py`): After guardian auto-heal called `self.resume()`, `_skip_to_pnl` was not set to True. The algo could immediately fire a trade in the same heartbeat as the heal, before the operator sees the Telegram alert. Added `_skip_to_pnl = True` after `resume()`.

4. **MEDIUM — Rescan used stale spot_price** (`mmm_monitor.py`): Inside the live validation block, the rescan called `find_new_strike` with the `spot_price` fetched at method entry (potentially stale). Added `_rescan_spot = await self._fetch_spot_price()` before rescan.

5. **LOW — Pre-scan failures at debug level** (`mmm_monitor.py`): Raised to `warning` so silent failures are visible in monitoring.

**WebUI update** (`MMMSettingsDialog.js`): Added `shift_premium_tolerance` to Trigger & Adjustment section with full description tooltip, immediately after `shift_target_premium`.

**Documentation**: Created `STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md` — full reference for the shift mechanism, root cause of the incident, all invariants, and debugging guide for future issues.

**Files changed:** `mmm_monitor.py`, `mmm_guardian.py`, `mmm_strike_shift.py`, `mmm_config.py`, `mmm_state.py`, `mmm_telegram.py`, `MMMSettingsDialog.js`, `STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md`

---

## 2026-04-04 — Final audit pass: 3 more bugs fixed

**Second-pass audit after context compaction — found and fixed 3 additional issues:**

1. **MEDIUM — Warm candidate path skipped gamma OTM constraint** (`mmm_monitor.py`): `pre_scan_shift_candidates` calls `find_new_strike` with `min_otm_distance=0` (gamma zone is unknown at pre-scan time). In `_process_strike_shift`, the warm candidate was accepted without checking if the strike respects `_gamma_shift_min_otm` (the OTM floor computed from gamma DANGER zone). Added OTM distance check: CE requires `strike >= spot + min_otm`, PE requires `strike <= spot - min_otm`. If violated, `_otm_ok = False` — falls through to fresh scan with proper constraint. (Logged via `mmm_guardian.py` INV-7.)

2. **MEDIUM — `else:` branch made gamma OTM fallback unreachable** (`mmm_monitor.py`): When warm candidate existed but failed the OTM check (`_otm_ok = False`), `new_strike_info` remained None but the `else:` (fresh scan) was unreachable because the outer `if _candidate:` was True. Result: bot would immediately hit `shift_no_strike` without ever attempting a fresh scan. Fixed by changing `else:` → `if not new_strike_info:` so the fresh scan fires for all cases where no warm candidate was accepted.

3. **LOW — `_sr_params` dead duplicate** (`mmm_monitor.py`): Line 4888 had `_sr_params = session.get('params', {})` which was redundant — `params` was already defined at method top. Changed to use `params` directly.

**Documentation updated:** `STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md` — audit table updated with 3 new bugs, INV-7 added for warm candidate OTM constraint.

**Files changed:** `mmm_monitor.py`, `mmm_strike_shift.py` (warning log level), `STRIKESHIFT_CRITICAL_CHANGES_04APRIL.md`

---

## 2026-04-04 — Performance audit + 3 optimizations for 0DTE speed

**Problem:** The pre-scan added earlier this session introduced latency because:
1. `get_full_chain` uses synchronous `requests` (blocks asyncio event loop, 100-400ms)
2. Chain cache TTL = 10s → cold on every heartbeat > 10s → 1 extra blocking REST call per beat
3. Pre-scan ran for BOTH sides every heartbeat regardless of whether shift was imminent
4. When candidate was rejected (gamma OTM), `invalidate_cache` caused a 2nd chain fetch for same data

**3 fixes implemented:**

**Fix 1 — Proximity guard in `pre_scan_shift_candidates` (HIGH):** Added `ce_premium`/`pe_premium` parameters. Added `SHIFT_SCAN_PROXIMITY_FACTOR = 4.0` constant. If both premiums are above `shift_threshold × 4.0`, function returns immediately (microseconds, zero REST calls). Per-side: skip sides individually above threshold. With threshold=$25, scan only when premium < $100. Call site in `_heartbeat` now passes `ce_now`/`pe_now`.

**Fix 2 — Skip cache flush when pre-scan is fresh (MEDIUM):** In `_process_strike_shift`, the `if not new_strike_info:` fresh-scan path now checks `_prescan_age` (age of pre-scan from session). If pre-scan ran < 30s ago, skip `invalidate_cache` — chain data is already fresh. Only flush on the final retry (always). Eliminates double REST call when gamma OTM check rejects a warm candidate.

**Fix 3 — Reuse pre-scan spot in `_process_strike_shift` (LOW):** Pre-scan stores spot + timestamp in `session['_last_prescan_spot']` / `session['_last_prescan_ts']`. `_process_strike_shift` checks if cached spot is < 10s old; if so, skips `_fetch_spot_price()`. Saves 1 async call when shift fires in same heartbeat as pre-scan.

**Net result for 0DTE:** In normal conditions (premium >> threshold), zero extra REST calls vs. old code. When approaching shift territory (premium < 4x threshold), 1 extra REST call per heartbeat with a warm candidate ready. At shift time, order fires with zero extra REST calls (warm candidate path).

**Files changed:** `mmm_strike_shift.py`, `mmm_monitor.py`

---

## 2026-04-04 — Fix blocking chain/ticker REST calls in async event loop (permanent)

**Problem:** All chain service calls (`get_full_chain`, `get_option_ticker`, `find_new_strike`, `pre_scan_shift_candidates`) use the synchronous `requests` library internally. When called directly in the asyncio event loop they block the entire event loop thread for 100-400ms per call — stalling all WebSocket handlers, API routes, and timer callbacks during that window.

**Root cause:** `chain_service.py` is sealed and uses `requests` (sync). The fix must be at every call site in `mmm_monitor.py`.

**Fix:** All 7 blocking call sites wrapped in `asyncio.get_running_loop().run_in_executor(None, ...)` which moves the blocking REST call to a thread pool executor. The event loop stays free while the chain fetch runs in a thread; the heartbeat `await`s the result before continuing.

Changed sites:
1. `pre_scan_shift_candidates` call in `_heartbeat_inner` — `functools.partial` + `run_in_executor`
2. `find_new_strike` in pre-sell shift path
3. `find_new_strike` attempt 1 in `_process_strike_shift` fresh-scan
4. `find_new_strike` retry in `_process_strike_shift`
5. `chain_service.get_option_ticker` in live premium validation block
6. `find_new_strike` in validation rescan
7. `initializer.get_full_chain` in replenish path

Added `import functools` to top-level imports.

**Thread safety:** `run_in_executor` dispatches to Python's default ThreadPoolExecutor. Since each call is individually `await`ed before the heartbeat continues, there is no concurrent mutation of the session dict. The chain `_cache` dict has GIL-protected basic operations. No new concurrency risks introduced.

**Files changed:** `mmm_monitor.py`

---

## 2026-04-04 — Critical production audit of all session changes

**Full audit of every changed line in this session for real-money production readiness.**

**All 4 change areas audited:**

**Guardian auto-heal:** Confirmed correct. `_pause_reason` captured into local variable BEFORE `resume()` clears it from session. `self._paused = False` set by `resume()` — downstream `if self._paused:` blocks correctly skip. Regime auto-resume and guardian G3 auto-heal are mutually exclusive (controlled by `_pause_reason` prefix). G3 is the only guardian violation that calls `monitor.pause()` — auto-heal correctly targets G3 only. `_skip_to_pnl = True` prevents same-beat trading after heal. `ensure_future` for Telegram is correct (called from within async heartbeat context, event loop is running).

**Strike shift mechanism:** Confirmed correct. `params` at method top. `_otm_ok = False` falls through to `if not new_strike_info:` (not missed by `else:` branch). Validation BEFORE freeze. No fallback to decayed strike.

**Two bugs fixed by audit:**
1. `_last_prescan_ts` was set BEFORE executor ran — if proximity guard skipped actual chain fetch, the timestamp was misleadingly fresh. Fixed: timestamp now set AFTER executor completes.
2. Log message showed `age=1743811234s` when candidate was never scanned (`_scanned_at=0`). Fixed: shows `'never scanned'` for clarity.

**run_in_executor:** Confirmed correct. 7 sites. Each `await`ed before heartbeat proceeds — no concurrent session mutation. GIL-protected dict reads in executor thread. `asyncio.get_running_loop()` correct. `functools.partial` for keyword args.

**Files changed:** `mmm_monitor.py`

---

## 2026-04-04 — M-01 Audit: 6 bugs fixed in mmm_monitor.py

Created `mmm_audit_plan.md` — systematic 51-module audit registry with tier ordering (P0→P3), 7-category checklist (A=Correctness, B=StateIntegrity, C=Concurrency, D=CrossModule, E=Safety, F=Performance, G=TestCoverage), copy-paste audit prompt, and progress tracker.

Completed full audit of M-01 (`mmm_monitor.py`, 10,110 lines). Found 8 issues; fixed 6:

**BUG-1 (CRITICAL) — `_save_session` returns `None` on exception, not `False`**
- Python `is False` identity check fails for `None` — the `_save_my_session` secondary stale-monitor guard silently no-ops on exception, breaking Layer 2 of the stale monitor defence.
- Fix: added `return False` in the `except Exception` block.

**BUG-2 (P1) — 7 early-return paths used inline `realized + unrealized - fees` instead of `compute_current_total_pnl()`**
- Excludes `perp_pnl` and `reverse_pnl`. Trailing stop and max-loss watermark silently understated.
- Affected: H-16, C-1, C-2, H-2, H-5 (×2), Robust-v2-Fix#7.
- Fix: module-level `from .mmm_pnl_core import compute_current_total_pnl as _pnl_total`; all 7 inline formulas replaced.

**BUG-3 (P1) — `asyncio.gather(ce_task, pe_task, return_exceptions=False)` in `_auto_close_all`**
- One side's exception cancels the sibling task — during emergency close, both sides may not get closed.
- Fix: `return_exceptions=True`; each result checked with `isinstance(result, Exception)`.

**BUG-4 (P2) — `session.get('_gamma_emergency_wind_down')` never set anywhere**
- Dead condition in regime block — never true. Misleading intent.
- Fix: removed the dead clause.

**BUG-5 (P2) — `_process_proactive_wind_down` is a dead method (never called)**
- Fully implemented but has zero callers. Maintenance hazard.
- Fix: deleted the entire method (~50 lines).

**BUG-6 (P2) — Stale price log hardcodes `{3}` instead of `MAX_STALE_CONSECUTIVE`**
- Fix: import `MAX_STALE_CONSECUTIVE` from `mmm_heartbeat_health`; use in f-string.

**BUG-7 (deferred) — Lot velocity window duplicated across `mmm_safety.py` and `mmm_monitor.py`**
- Requires coordinated change to `mmm_safety.py` — do in a dedicated session.

**BUG-8 (deferred) — No sealed tests for `mmm_monitor.py` (P0 module)**
- Large separate effort — write tests in a dedicated session.

**Files changed:** `mmm_monitor.py`, `mmm_audit_plan.md` (created)

---

## 2026-04-04 — M-02 Audit: 3 bugs fixed in mmm_engine.py

Completed audit of M-02 (`mmm_engine.py`, 1,072 lines). Found 4 issues; fixed 3; 1 deferred.

**BUG-1 (P1) — `reconcile_pnl` compared options-only `tracked` against perp+reverse-inclusive `actual`** (`reconcile_pnl`, line ~1042)
- `actual = pnl['net_pnl']` includes `perp_pnl + reverse_pnl`; `tracked` was options-only.
- Discrepancy = `|perp_pnl + reverse_pnl|` — fired every heartbeat when perp/reverse active.
- Effect: spurious WARNING log + `session['unrealized_pnl']` overwritten every beat even when correct.
- Fix: `actual = pnl['realized'] + pnl['unrealized'] - pnl['fees']` — compare options sub-totals directly.

**BUG-2 (P2) — `calculate_reversal_loss` had no explicit None check for `fetch_premium_fn` return** (`calculate_reversal_loss`, lines ~283-316)
- `calculate_standard_loss` had an explicit `if p_current is None:` guard; `calculate_reversal_loss` did not.
- If `current = None`: `_D(None)` → `Decimal('None')` → `InvalidOperation` → caught by except — safe end result but misleading log message.
- Fix: split each `try` block into fetch + compute; added `if current is None: _fetch_errors += 1; continue` between them. Applied in both the `adjustment_fills` loop and the `frozen_positions` loop.

**BUG-3 (P3) — Commission `or` chain was falsy-unsafe** (`execute_adjustment`, line ~776)
- `float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)` — if `paid_commission=0.0` (valid zero), `0.0` is falsy so `commission` key was checked instead.
- Fix: `float(_od['paid_commission'] if 'paid_commission' in _od else _od.get('commission', 0))` — key presence check, not truthiness.

**BUG-4 (deferred) — No sealed tests for `calculate_standard_loss`, `calculate_reversal_loss`, `execute_adjustment`, `reconcile_pnl`.**
- Only `calculate_lots_to_sell` (entry #72) is sealed. 9 non-sealed unit tests exist. Large effort — dedicated session.

**Files changed:** `mmm_engine.py`

---

## 2026-04-04 — M-03 Audit: 2 bugs fixed in mmm_guardian.py

Completed audit of M-03 (`mmm_guardian.py`, 386 lines). Found 3 issues; fixed 2; 1 deferred.

**BUG-1 (P2) — `handle_stale_monitor` skipped `_cleanup_roll_lock`** (lines ~291-305)
- `monitor.stop()` calls `_cleanup_roll_lock(sid)` to release straddle roll locks when the monitor exits.
- The G5 path in `handle_stale_monitor` deliberately bypasses `monitor.stop()` (to avoid emitting `status_change` with the stale session's data). But this also skipped `_cleanup_roll_lock`.
- Effect: if the successor monitor attempted a straddle roll, `_cleanup_roll_lock` would block waiting for the lock that the stale monitor never released. Roll would time out.
- Fix: added explicit `_cleanup_roll_lock(sid)` call after `monitor._running = False`.

**BUG-2 (P3) — `record_close` silently accepted any `side` string** (line ~147)
- `self._beat_closed_lots[side] = ...` with no validation — a misspelled side like `'CE'` would silently create a separate key in the dict, making the velocity check blind to those closes.
- Fix: normalize `side = side.lower()` + validate `if side not in ('ce', 'pe'): log.warning + return`.

**BUG-3 (deferred) — No sealed tests for any guardian function (G1–G5).**
- `check_close_allowed`, `handle_stale_monitor`, `check_generation_integrity`, `check_beat_velocity` all untested. → DEF-04.

**Files changed:** `mmm_guardian.py`

---

## 2026-04-04 — M-04 Audit: 1 bug fixed in mmm_safety.py

Completed audit of M-04 (`mmm_safety.py`, 1,194 lines). Found 2 issues; fixed 1; 1 deferred.

**BUG-1 (P2) — `check_pnl_guardrail` used inline P&L formula missing fees and reverse_pnl** (lines ~878-883)
- Formula: `realized + unrealized + perp_pnl` — missing `- total_fees` and `+ reverse_pnl`.
- `check_max_loss` (line 215) and `check_trailing_stop` (line 1057) already used `compute_current_total_pnl`.
- Effect: guardrail fires against an inflated P&L (fees not subtracted), and completely ignores reverse mode P&L.
- Fix: replaced inline formula with `from .mmm_pnl_core import compute_current_total_pnl as _pnl_total; total_pnl = _pnl_total(session)` — consistent with the other two safety checks.

**BUG-2 (deferred) — No sealed tests for `check_lot_velocity`, `check_whipsaw`, `update_peak_pnl`.**
- Complex adaptive logic (score decay, rolling window, spot-move validation) untested. → DEF-05.

**Files changed:** `mmm_safety.py`

---

## 2026-04-04 — M-11/12/13/14 Audit: close_at_5 + strike_shift + harvester + recycler

Audited 4 modules in a single session (user confirmed it was safe to run all at once). 1 bug fixed across the 4 modules.

**mmm_close_at_5.py — BUG-1 (P3): falsy-unsafe commission extraction** (line ~480)
- `float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)` — identical `or` chain bug as M-02 BUG-3.
- If `paid_commission=0.0` (valid zero commission for maker orders), Python treats `0.0` as falsy and falls through to `commission`.
- Fix: `float(_od['paid_commission'] if 'paid_commission' in _od else _od.get('commission', 0))` — key presence check.

**mmm_strike_shift.py** — CLEAN. All prior audit fixes verified: `_initial_hedge_premium` preservation, frozen-strike exclusion in `find_new_strike`, trigger_snapshot cleanup, symbol update via singleton.

**mmm_harvester.py** — CLEAN. `active_lots` (not `total_lots`) used for asymmetry calculation; in-flight guard via `being_closed_ids` pre-built set; `None/≤0` premium check on fetch.

**mmm_recycler.py** — CLEAN. Phase B recomputes lots from actual Phase A results (not pre-planned). Rollback uses deep-copied canonical position objects (not sparse view dicts). Viability 3-check (ratio, net lot gain, affordability) correct.

**Files changed:** `mmm_close_at_5.py`

## 2026-04-04 — Batch A audit complete: M-05, M-06, M-07, M-08

**Session goal:** Systematic audit of the 4 remaining P0 modules in Batch A.

**mmm_executor.py** — 3 bugs fixed:
- BUG-1 (CRITICAL/P2): `emergency_execute()` — when exchange reports `state='filled'` but `unfilled_size == size` (0 lots actually filled, exchange data race on reduce_only orders), the code was setting `filled_size = size` and returning `success=True`. This mirrors the smart_execute path (lines 432-457) which correctly returns `_failure()` for this case. A false success here falsely marks the position closed in session state while the exchange still has the short open — critical for max-loss and margin situations. Fix: return `_failure()` with descriptive message identical to smart_execute behavior.
- BUG-2 (P3): `execute_adjustment()` was missing a `session_id` parameter. Both inner `smart_execute()` calls were passed `session_id=None`, so all activity log entries from adjustments (buy-to-close + sell-to-open cycles) had no session context. Fix: add `session_id: str = None` parameter and thread it through both calls.
- BUG-3 (P3): Cancel-during-reprice path used an inline fill-price validation block (legacy Robust v2 Fix #22) instead of the `_parse_fill_price()` helper. The inline version omitted the `price <= 0 or price > 1_000_000` range check. Fix: replace inline block with `_parse_fill_price()` call inside try/except ValueError.

**mmm_margin_guardian.py** — CLEAN. Margin formula (`balance - available` primary, with blocked/portfolio/pos+order fallbacks) correct. Tier evaluation thresholds use proper `.get(key, default)` (no falsy-unsafe `or` chains). `estimate_lots_to_close()` proportional reduction math correct. `MarginGuardian.check()` consecutive-critical escalation path correct.

**mmm_circuit_breaker.py** — CLEAN. Three-state machine (CLOSED/OPEN/HALF_OPEN) with exponential backoff (`RESET_TIMEOUT * 2^(depth-1)`, capped at 300s) correct. `_consecutive_opens` correctly tracks re-open-after-probe-failure count (used for `should_alert`). Sliding window deque safe. `summary()` reads fields outside `_lock` but is display-only.

**mmm_fill_sync.py** — 1 bug fixed:
- BUG-1 (P3): `_get_session_symbols()` called `self._monitor.initializer.build_symbol()` with no guard on `self._monitor.initializer`. If the monitor's initializer is None (not yet initialized or initialization failed), this raises `AttributeError` which is silently swallowed by the `sync()` wrapper — entire fill sync fails for that heartbeat with no warning. Fix: use `getattr(self._monitor, 'initializer', None)`, fall back to stored `pos.get('symbol')` strings when initializer is None, and emit a warning so the failure is visible.

**Files changed:** `mmm_executor.py`, `mmm_fill_sync.py`

---

## 2026-04-04: Batch B Systematic Safety Audit (5 P1 Modules)
**Modules Audited:** M-09 `mmm_perp_hedge.py`, M-10 `mmm_replenish.py`, M-15 `mmm_wind_down.py`, M-16 `mmm_exit_all.py`, M-17 `mmm_reverse.py`
**Result:** 8 bugs found and fixed across 3 modules (2 modules CLEAN).

**Key Fixes:**
1. **CRITICAL (M-16):** Added missing reverse and perp position closing to `run_exit_all()` before options exit rounds, ensuring no positions are orphaned during an emergency exit.
2. **P2 (M-16):** Added missing `_cleanup_roll_lock(sid)` before calling `monitor.stop()` to prevent straddle roll lock from blocking successor sessions.
3. **P2 (M-16):** Added `return_exceptions=True` to `asyncio.gather` for exit rounds so single-task failures do not abort the entire emergency close.
4. **P3 (M-09, M-17):** Replaced 3 falsy-unsafe commission `or` chains with key-presence checks (matching M-02 fix pattern).
5. **P3 (M-17):** Refactored inline P&L formula `_compute_core_only_pnl` to derive from `compute_current_total_pnl() - reverse_pnl`, preventing formula drift.


---

## 2026-04-04: Batch C Systematic Safety Audit (8 P2 Modules)
**Modules Audited:** M-18 to M-25 (`mmm_pnl_core`, `mmm_regime`, `mmm_state`, `mmm_storage`, `mmm_gamma`, `mmm_gamma_detector`, `mmm_breakeven_engine`, `mmm_scaler`)
**Result:** 7 bugs found and fixed across 5 modules (3 modules CLEAN). 1248/1248 tests passing.

**Key Fixes:**
1. **P1 (M-24, M-23):** `mmm_breakeven_engine` and `mmm_gamma_detector` read phantom `_perp_state` key that was never populated. Perp hedge was silently excluded from all breakeven and gamma curvature calculations. Fixed to read `perp_hedge` with correct signed-lots logic.
2. **P1 (M-25):** `mmm_scaler.py` scale-up eligibility used inline `realized + unrealized`, ignoring perp+reverse P&L. Could allow scale-up into a net-losing session. Fixed to call canonical `compute_current_total_pnl()`.
3. **P2 (M-20, M-21):** `mmm_state.py:get_session_summary`, `mmm_storage.py:list_session_summaries`, and `_row_to_summary_fallback` all computed dashboard `net_pnl` inline, missing perp+reverse. Fixed via `compute_current_total_pnl()` or SQL extract.
4. **P2 (M-20):** `_trend_plateau_beats` and `_trend_t4_beats` missing from `create_session` init.
5. **P3 (M-21):** Singleton `get_storage()` lacked thread safety. Added double-checked lock.

**Files changed:** `mmm_scaler.py`, `mmm_breakeven_engine.py`, `mmm_gamma_detector.py`, `mmm_state.py`, `mmm_storage.py`

---

## 2026-04-04 — MMMX plan corrected to monthly strategy model

- Updated `mmmx_plan.md` to preserve approved MMMX isolation architecture while replacing 0DTE-style behavior with true monthly-options logic.
- Removed 0DTE carryover concepts from plan scope (`mmmx_strike_shift.py`, close-at-5 style exit model) and replaced with monthly trigger/action model (delta drift + IV expansion + roll/reduce/close-all).
- Enforced hard safety requirement in plan: `close_at_dte` is mandatory close behavior with minimum allowed value 7 (no warning-only behavior below 7 DTE).
- Added explicit implementation/verification requirements for monthly engine math, trigger priority order, heartbeat cadence (24h base, 1h post-trigger), initializer failure handling, API surface, frontend MVP risk panels, and isolation checks.

---

## 2026-04-04: Batch D Systematic Safety Audit (8 P2 Modules)
**Modules Audited:** M-26 to M-33 (`mmm_adaptive`, `mmm_atm_shield`, `mmm_reversal`, `mmm_pending_orders`, `mmm_adopter`, `mmm_trigger`, `mmm_initializer`, `mmm_straddle_roll`)
**Result:** 3 bugs found and fixed across 3 modules (5 modules CLEAN). 1248/1248 tests passing.

**Key Fixes:**
1. **P1 (M-33):** `mmm_straddle_roll.py` Gate 10 loss abort used inline `realized + unrealized + perp_pnl`, missing `total_fees` and `reverse_pnl`. Same pattern as M-01 BUG-2. Loss abort gate saw inflated P&L → fires too late in losing sessions. Fixed → `compute_current_total_pnl()`.
2. **P3 (M-32):** `mmm_initializer.py` `_extract_ticker_data` had 4 falsy-unsafe `or` chains — `0.0` (valid zero bid) treated as falsy. Same pattern as M-02 BUG-3. Fixed → key-presence checks.
3. **P3 (M-30):** `mmm_adopter.py` `fetch_exchange_btc_options` silently swallowed Greeks/ticker fetch exceptions with bare `except Exception: pass`. Fixed → `log.debug()` for operator visibility.

**Clean modules:** `mmm_adaptive.py` (stateless scoring engine), `mmm_atm_shield.py` (deferred re-sell correct), `mmm_reversal.py` (Decimal + cooldown correct), `mmm_pending_orders.py` (thread-safe, dual stale thresholds), `mmm_trigger.py` (%-based math, zero-snapshot guard, operator pin auto-expiry).

**Files changed:** `mmm_straddle_roll.py`, `mmm_initializer.py`, `mmm_adopter.py`

---

## 2026-04-06 — Strike Shift Observability: Cache + Remark Fixes

**Trigger:** User noticed strike shift activity showed "NONE" for old premium and no reason was shown in WebUI activity log for why the shift occurred.

**Root Cause 1 (chain_service.py):** `invalidate_cache('BTC', expiry)` only cleared `chain_BTC_{expiry}` but NOT `tickers_BTC`. The retry path in mmm_monitor re-called `get_chain_data` → `_get_option_tickers` immediately hit the still-live 5s tickers cache → returned same stale/empty data → "Nearest OTM strikes: NONE". Fix: also invalidate `tickers_{underlying}` whenever a specific-chain cache is cleared.

**Root Cause 2 (mmm_strike_shift.py / mmm_monitor.py):** `activate_new_strike` was always using `fill_premium` (the NEW strike's fill price) as `old_premium` in the STRIKE_SHIFT remark. The old-strike premium was never captured before being overwritten. Fix:
- Added `old_premium: float = 0.0` parameter to `activate_new_strike`.
- Captured `_old_strike_premium = hedge_premium` in `_process_shift()` before the new-strike logic runs.
- Passed `old_premium=_old_strike_premium` to `activate_new_strike` and into `log_activity('strike_shift', ...)` and `log_activity('adjustment_complete', ...)` messages.
- WebUI activity log now shows: "old premium $X.XX < threshold $Y threshold" with the correct pre-shift premium.

**Files changed:** `chain_service.py`, `mmm_strike_shift.py`, `mmm_monitor.py`

---

## 2026-04-06 — Fix: Cross-Side Velocity Block Preventing PE Replenish

**Live session**: `mmm06apr26-1` — PE=0 lots, CE=397 lots open. Session PAUSED. `replenish_enabled=True`, premiums available, cooldown elapsed, no regime/margin blocks — but replenish still not firing.

**Root cause found in logs and session DB:**
- PE fully closed at 10:09 IST → ONE-SIDE CLOSE GUARD fired → tried `_process_replenish(pe, ce)`
- Gate 11 (lot velocity) **blocked replenish** because `adjustment_history` had a CE strike_shift at 04:25 that sold 228 lots — counted against the 200-lot velocity limit
- **The count was cross-side**: CE lots sold in the window were counted against PE replenish velocity
- PE-side velocity was actually 0/200 — completely safe to replenish

**Why it's wrong:** Gate 11 was computing `lots_in_window` across ALL sides combined. A CE adjustment consumes CE velocity budget, not PE velocity. The hedge restoration principle (established in 2026-04-02 incident) already removed regime/wind-down gates from replenish; the same reasoning applies to cross-side velocity: each side's velocity is independent.

**Fix (2 files):**

1. **`mmm_replenish.py` Gate 11** — added `if _adj.get('side', '') != closed_side: continue` filter. Now only counts same-side lots. Reason updated to include side label.

2. **`mmm_monitor.py` `_process_replenish()` headroom cap** — same filter added. Headroom is now per-side (not combined).

**Effect on current session:** PE-side velocity = 0 lots / 200 limit → Gate 11 passes → replenish will fire on next heartbeat after backend restart.

**Tests added to `test_sealed_mmm_replenish.py`** (25 → 28 contracts):
- `test_blocked_when_same_side_velocity_exceeded` — same-side block still works
- `test_cross_side_velocity_does_not_block_replenish` — CE lots don't block PE replenish (the exact incident)
- `test_eligible_when_same_side_velocity_under_limit` — eligible when under limit

**Test result:** 1251 passed, 0 failed.

**Files changed:** `mmm_replenish.py`, `mmm_monitor.py`, `tests/test_sealed_mmm_replenish.py`

---

## 2026-04-06 — Fix: Replenish→ATM Shield Cycle (PE Closed Immediately After Replenish)

**Live incident (mmm06apr26-1):** PE replenished at 12:29:40 (sold @ 92.0), closed again at 12:32:26 (bought @ 99.5 — loss). PE ended at 0 lots with CE=228 lots unhedged. Session paused. Broker fees wasted on 2 round-trips.

**Root cause: Replenish picked strike 68600, which was already within ATM Shield's proximity threshold.**

Timeline:
1. 12:06:57 IST — ATM Shield fired on PE (BTC falling toward 68600). Shield closed PE @ 119.5, re-sell blocked (probably vol/gamma regime or no suitable farther-OTM strike).
2. 12:29:40 IST — `_process_replenish` ran. Used `_rank_strikes` (selects by `|premium - desired|`) → best match at strike 68600 (premium ~92).
3. At that moment, BTC spot ~69000. PE dist = (69000-68600)/69000 = 0.58%. ATM shield threshold = 0.5% (base) × 1.0 (time_mult at 5h to expiry) = 0.5%. Dist 0.58% > 0.5% → position passed proximity check at entry time.
4. 12:30 heartbeat (next beat) — BTC had dropped to ~68960. PE dist = (68960-68600)/68960 = 0.52%. Still outside 0.5% threshold.
5. BTC continued falling (PE premium 92→99.5 = 8.2% rise in put price) → dist dropped below 0.5% → shield fired, closed PE @ 12:32:26.

**Why the re-sell failed after shield:** `sells_possible = False` because `vol_gamma_blocked=True` (gamma regime HARD/EMERGENCY near expiry) OR `find_new_strike` returned None (no liquid strike at 1.5% OTM target). Either way, shield close without re-sell → PE=0.

**The bug:** `_rank_strikes` has no awareness of the ATM Shield proximity threshold. It finds the "best premium match" regardless of OTM distance safety. The replenish→shield cycle burns fees and re-creates the problem it was trying to solve.

**Fix (`mmm_monitor.py` `_process_replenish`):**

Added Step 3b-ATM (proximity guard) after `_rank_strikes` selects a candidate:
1. Compute `eff_prox_pct = atm_shield_proximity_pct × time_mult` (mirrors ATM Shield's own formula)
2. Apply 2× safety buffer: `safe_pct = eff_prox_pct × 2.0` — gives the position room to survive at least one heartbeat interval even if spot moves against it
3. If candidate dist ≤ safe_pct:
   a. Call `find_new_strike(min_otm_distance = spot × safe_pct / 100)` — same function ATM Shield uses to find safer strikes
   b. If a safe strike found → use it instead of the premium-matched candidate
   c. If no safe strike → `return False` (PAUSE takes over) — better to pause than to burn fees in a cycle

**At 5h to expiry:** `eff_prox_pct = 0.5 × 1.0 = 0.5%`, `safe_pct = 1.0%`. Strike 68600 at 0.58% OTM would be blocked (0.58% ≤ 1.0%). System attempts `find_new_strike` with min 1.0% OTM. If no viable strike → PAUSE (correct — better than cycling).

**Tests:** 28 passed (all replenish sealed tests still pass, no regressions).

**Files changed:** `mmm_monitor.py`

---

## 2026-04-06 — MMMX Strict Analysis + Phase Planning (No Code Changes)

- Completed a strict line-by-line analysis pass for MMMX design artifacts before implementation planning.
- Re-read and cross-mapped core MMMX strategy + architecture docs for consistency and implementation readiness:
  - `MMMX_COMPLETE.md`
  - `MMMX_IMPLEMENTATION_PLAN.md`
  - `mmmx_brain.md`
  - `mmmx_plan.md`
  - `MMMX_WEBUI_DESIGN.md`
- Produced planning artifacts (in chat) covering: separate strategy logic map, separate system architecture map, wiring verification with conflict/missing risk flags, failure-path traces, and micro-phase decomposition + handoff structure.
- No runtime/code behavior changed in this session; this was a pre-implementation design validation and sequencing pass to reduce integration surprises.

---

## 2026-04-06 — MMMX Document Normalization (Contradiction Cleanup)

- Updated `MMMX_COMPLETE.md` to remove internal contradictions and lock implementation semantics:
  - Deployment queue retracement changed to **directional retracement** (against queue direction) instead of absolute distance.
  - Hard-stop-vs-shield behavior unified to **atomic step completion + immediate next control-boundary hard stop** (no mid-step interrupt).
  - Trigger table fixed: `NEAR_ITM (>=0.70)` now maps to `close_all` for consistency with delta gates.
  - Removed stale heartbeat reference to `side loss` trigger (already removed from design).
  - Hedge close policy clarified: hard stop leaves hedges orphaned; DTE_CLOSE flow closes hedges only after shorts are confirmed closed.
  - Fee/P&L formulas normalized to avoid ambiguity: fees deducted exactly once at portfolio level.
- Updated `MMMX_IMPLEMENTATION_PLAN.md` to mirror the same normalized rules:
  - Trigger table row for `NEAR_ITM` aligned to `close_all`.
  - Queue retracement edge-case row updated to directional retracement wording.
  - Isolation contract strengthened: MMM read-only helpers must be accessed via MMMX-local adapters; direct non-adapter MMM imports fail CI isolation scan.
- Why: reduce coder ambiguity before implementation and prevent divergent behavior between strategy spec and implementation plan.

---

## 2026-04-06 — MMMX Escalation Wording Cleanup (Telegram-only)

- Updated `MMMX_IMPLEMENTATION_PLAN.md` to remove mixed SMS/Telegram escalation wording and standardize naked-position escalation to Telegram `CRITICAL` at both 30-minute and 2-hour checkpoints.
  - Section 3.8: changed watchdog line to Telegram-only.
  - Phase 9 build checklist: removed "Telegram + SMS hook" phrasing.
  - Section 9 A9: renamed ambiguity label and clarified no secondary gateway is configured in-repo.
- Updated `MMMX_COMPLETE.md` to align escalation language in the naked-timeout flow from "SMS/emergency" to "Telegram CRITICAL alert".
- Why: eliminate channel ambiguity before implementation so runtime behavior, alerts, and tests all align to one escalation path.

## 2026-04-06 — MMMX Phase 2: Execution Engine (4 new files, 40 tests)

- `mmmx_executor.py` (new): MMMX's only exchange-facing module. `smart_execute()` with sha256 deterministic client_order_id (dedup within minute), preflight margin check (SELL blocked >= 80%, BUY blocked >= 95%), `_being_closed` TTL guard, limit reprice loop (mid → bid/ask in second half), mid-loop margin check (>= 85% falls to market, >= 95% aborts), emergency_execute fallback (IOC). `emergency_execute()` standalone IOC path for crash/margin breach. `ExecutionResult` dataclass with `to_dict()`. Zero `routes.mmm.*` imports.
- `mmmx_circuit_breaker.py` (new): 3-state fault isolator (CLOSED/HALF_OPEN/OPEN) keyed by session_id. Thread-safe with lock. N=3 consecutive failures → HALF_OPEN; probe failure → OPEN; 5s cooldown → HALF_OPEN for next probe; probe success → CLOSED.
- `mmmx_margin_guardian.py` (new): Read-only adapter over MMM's `fetch_margin_utilization`. The ONLY mmmx file allowed to import from `routes.mmm.*`. Async `current_utilization()` (caches last value on error), sync `estimated_margin_for_order()`. Singleton via `get_margin_guardian()`.
- `mmmx_reconciler.py` (new): Partial fill tracker. `track_partial_fill()` records residuals in-memory + audit log. `tick_partials(session)` retries each residual each heartbeat (smart_execute for < 20 lots, emergency_execute for >= 20 lots). `reconcile_with_exchange(session)` compares DB positions vs live exchange (Phase 9 manual trigger). `get_pending_residuals()`, `clear_all_residuals()` for monitoring and tests.
- `tests/test_phase2.py` (new): 40 tests — all Phase 2 exit criteria passing. Patching done at correct module boundaries (lazy imports respected).
- `MMMX_IMPLEMENTATION_PLAN.md`: Phase 2 marked ✅ COMPLETE (2026-04-06, 109 total tests). Phase 3 NEXT AI prompt added.
- Total test count: 109/109 passing (69 Phase 1 + 40 Phase 2). MMM isolation scan clean.

## 2026-04-06 — MMMX Phase 3: Monitoring Core (3 files touched, 36 tests)

- `mmmx_safety.py` (new): Pre-beat safety checks — pure function, no I/O. `pre_beat_check(session, stored_gen, my_generation) → SafetyVerdict`. Priority order: (1) STALE_GENERATION → abort; (2) status not in RUNNING/PAUSED → skip_beat; (3) _pnl_calculation_incomplete → skip_beat; (4) expiry_datetime=None (dte=-1.0) → abort EXPIRY_PAST; (5) naked positions → log warning only. PAUSED passes the status guard (trigger evaluator handles skipping PAUSED separately).
- `mmmx_trigger.py` (new): Priority-ordered trigger evaluator — pure function, no async, no I/O. `evaluate(session, metrics) → Optional[TriggerHit]`. 7-priority table: DTE_CLOSE → HARD_STOP → IV_CATASTROPHE → NEAR_ITM → PORTFOLIO_DELTA → DELTA_DRIFT → IV_SPIKE. First match wins. Returns None if status != RUNNING. `TriggerHit` dataclass: trigger_name, reason, severity, data. Helper scanners: `_scan_near_itm()` (abs delta fallback to entry_delta), `_scan_delta_drift()` (skips legs without current_delta).
- `mmmx_monitor.py` (updated): Replaced `_heartbeat_stub` with full `async def _heartbeat()` hot-path. Steps: (1) G5 generation guard; (2) `safety.pre_beat_check()` — abort/skip as directed; (3) `compute_portfolio_pnl/delta/lot_imbalance/dte` + `recalc_hard_stop`; (4) PnLIncompleteError → set flag, bump beat, save; (5) `trigger.evaluate()`; (6) dispatch: HARD_STOP/DTE_CLOSE → `_dispatch_close_all()`, others log-only; (7) emit_heartbeat + save. Added `_dispatch_close_all(session, reason)` — emergency_execute for all ACTIVE legs (buy-to-close), audit all fills (success AND failure), transition_status(COMPLETE), emit_safety (sync), Telegram, save. `_run_loop` now calls `asyncio.run(_heartbeat())`. Added `_stale_abort_gen` field to `__init__`.
- `tests/test_phase3.py` (new): 36 tests. TestSafetyVerdict (9 tests), TestTriggerEvaluate (15 tests), TestMonitorHeartbeat (5 tests), TestMMMIsolation (5 tests). Isolation check uses regex (actual import lines only) rather than raw string search to avoid false positives from docstrings.
- Key design decisions: isolation docstrings say "MMM namespace" not "routes.mmm.*" to avoid confusing isolation scanner; PAUSED status is allowed by safety (not status guard) but trigger evaluator skips PAUSED; compute_dte_days clamps to 0.0 for past datetimes — EXPIRY_PAST abort only fires when expiry_datetime=None.
- `MMMX_IMPLEMENTATION_PLAN.md`: Phase 3 marked ✅ COMPLETE (2026-04-06, 36 tests). Phase 4 NEXT AI prompt added.
- Total test count: 145/145 passing (69 Phase 1 + 40 Phase 2 + 36 Phase 3). MMM isolation scan clean.

## 2026-04-06 — MMMX Phase 4+5: Audit Log + ATM Shield (60 new tests, 249 total)

- `mmmx_audit_log.py` (new, Phase 4): Append-only JSONL audit log. `MMMXAuditLog` class with background writer thread. `enqueue_event()` — non-blocking; `flush()` — blocks until queue drained; `get_audit_log()` singleton. Zero `routes.mmm.*` imports. (Phase 4 details from prior session.)
- `tests/test_phase4.py` (new): Phase 4 exit criteria tests. (From prior session.)
- `mmmx_atm_shield.py` (new, Phase 5): Full ATM Shield implementation per spec.
  - `evaluate(session, spot)` — scans all ACTIVE CE/PE legs; OTM% = `(strike-spot)/spot*100` (CE), `(spot-strike)/spot*100` (PE); candidate if OTM% < threshold.
  - `sort_by_priority(candidates)` — G38: sorts by worst unrealized_pnl first.
  - `multi_shield_margin_precheck(candidates)` — G38 stub; always True for now.
  - `allocate_reserve(session, loss_usd, ce_premium, pe_premium)` — G39: `ce_needed = ceil(loss×0.30 / (ce_prem×LOT_SIZE_BTC))`; `pe_needed = ceil(loss×0.70 / (pe_prem×LOT_SIZE_BTC))`; per-side independent capping to reserve; `partial=True` if either side short-filled; `exhausted=True` if both sides = 0.
  - `execute_shield(session, candidate, executor, audit, spot, save_fn)` — 6-step sequence: buyback (10 limit + 1 market); if buyback fails → abort (no naked); sell new (10 limit + 1 market); if sell fails → session PAUSED + naked logged + no recovery tranche; allocate reserve + create recovery tranche; recalc hard stop; G13 mid-beat persist via `save_fn`.
  - `evaluate_and_fire(session, spot, executor, audit, save_fn)` — G38 multi-shield: evaluates, sorts, pre-checks margin, fires sequentially; stops cascade on naked.
  - `create_recovery_tranche(session, parent_tranche, ...)` — sibling tranche with string IDs ("2A", "2B"); full first-class citizen; `tranches_deployed`/`tranches_remaining` NOT changed.
  - Import pollution fix: `_engine.recalc_hard_stop()` called via module attr (not bound name) to survive test patching.
  - Zero `routes.mmm.*` imports confirmed.
- `mmmx_reconciler.py` (updated, Phase 5): Added `check_naked_watchdog(session, executor) → List[Dict]`. G37: `>30 min` → `emergency_execute` + Telegram; `>2 hr` → CRITICAL alert + Telegram. Resolved positions removed from `_naked_positions`.
- `mmmx_monitor._heartbeat` (updated, Phase 5): Added steps 4b (naked watchdog) and 4c (ATM shield evaluation) between trigger dispatch and emit+save. ATM shield only fires if `spot_price` is present in metrics (no live feed in Phase 5).
- `tests/test_phase5.py` (new): 60 tests covering all Phase 5 exit criteria — evaluate, sort, allocate_reserve, execute_shield (success/buyback-abort/naked paths), evaluate_and_fire (multi-shield, cascade, reserve exhaustion), recovery tranche citizenship, G37 naked watchdog (all thresholds), isolation, state invariants.
- Total test count: 249/249 passing. MMM isolation scan clean.

## 2026-04-06 — MMMX Phase 7: Premium Listener + Tier-0 CBs + Heartbeat Watchdog + Hedger

- `mmmx_premium_listener.py` (new): `PremiumListener` class with its own daemon watchdog thread.
  - `subscribe(session)`: collects CE/PE symbols from active tranches; initialises `live_quotes` and `_listener_force_count`.
  - `on_tick(tick, session)`: updates `session['live_quotes']`; calls `evaluate_cbs()`.
  - `evaluate_cbs(tick, session)` (async): evaluates all 4 Tier-0 circuit breakers:
    - `CB_PREMIUM_JUMP`: leg premium > 50% above entry_premium → `force_heartbeat()`
    - `CB_DELTA_BLOWOUT`: abs(portfolio_delta) > emergency_delta (0.70) → `force_heartbeat()`
    - `CB_IV_FLASH_SPIKE`: IV/iv_rank > iv_catastrophe_pct (80%) → `force_heartbeat()`
    - `CB_NEAR_ITM`: any active position delta >= 0.72 → `await executor.emergency_execute()` (50% reduce) THEN `force_heartbeat()`. Only CB that executes orders directly.
  - `force_heartbeat(session, reason)`: sets `session['_force_check']=True`, increments `_listener_force_count`, signals `monitor.signal_force_check()` (lazy import to avoid circular).
  - `check_stale_ws(session)`: 5-min watchdog — WS stale → Telegram WARNING + force_heartbeat; WS AND monitor both stale → Telegram CRITICAL.
  - Registry: `_mmmx_listeners` dict with `RLock` (prevents deadlock when `stop()` is called inside `start_session_listener()`).
  - `start_session_listener(session_id, my_generation, executor)`, `stop_session_listener`, `get_listener`.

- `mmmx_hedger.py` (new): Deferred hedge execution after Tr5+ deployment.
  - `schedule_post_deploy(session, tranche_id, deployed_at)`: appends PENDING entry to `session['_hedge_schedule']`; only if `tranches_deployed >= 5` AND `hedging_enabled=True`. Tr1–Tr4 produce no entries.
  - `tick(session, executor, audit)` (async): iterates PENDING entries; executes CE+PE buys via `smart_execute` when `now >= execute_after`; creates hedge via `make_hedge()`; appends to `session['hedges']`; marks entry EXECUTED. On CE or PE failure: marks FAILED, no hedge created.
  - `update_hedge_pnl(session, live_quotes)`: LONG unrealised P&L = (current − entry) × lots × LOT_SIZE_BTC for all ACTIVE hedges. Skips ORPHANED.
  - `detect_displacement(session, repositioned_parent_id)`: marks associated hedge ORPHANED + logs + Telegram. Does NOT close. Hard-stop path calls this → hedges stay ORPHANED.

- `mmmx_monitor.py` (updated):
  - `MMMXMonitor.__init__`: added `_force_wake_event = threading.Event()`.
  - `stop()`: now also sets `_force_wake_event` so sleeping thread wakes immediately.
  - `signal_force_check()` (new method): sets `_force_wake_event`. Called by `PremiumListener.force_heartbeat()`.
  - `_run_loop` sleep: replaced `_stop_event.wait(beat_secs)` with `_force_wake_event.wait(beat_secs)` + clear. When listener fires a CB, monitor wakes immediately instead of sleeping for up to 1 hour.
  - `_heartbeat` step 5d (new): calls `mmmx_hedger.tick()` then `update_hedge_pnl()`. Inserted between profit booking (5c) and emit+save (6).
  - Deployment step 5b: now captures `_deployed_tranche` return value from `execute_tranche_deploy()`; calls `schedule_post_deploy()` on success.
  - `start_session_monitor()`: also starts `PremiumListener` with same generation + executor.
  - `stop_session_monitor()`: also calls `stop_session_listener()`.

- `tests/test_phase7.py` (new): 65 tests covering all Phase 7 exit criteria across 14 test classes.
- Total test count: 385/385 passing (320 prior + 65 Phase 7). Zero regressions.

## 2026-04-06 — Phase 8: UI + Hot Reload (WebUI Integration)

- `webui/backend/routes/mmmx/mmmx_config.py`:
  - Fixed `hedge_distance_pct` min bound: `1.0` → `10.0` (bug per spec Section 5.1).
  - Added `split_hot_reload_patch(patch) → (applied, rejected)`: splits a hot-reload patch without raising. Disallowed keys → rejected with reason; invalid values → rejected with validation message. `validate_hot_reload_patch()` still raises (backward compat preserved).

- `webui/backend/routes/mmmx/mmmx_api.py`:
  - Reworked `PATCH /params` (hot_reload_params): now uses `split_hot_reload_patch` for partial success. Applied keys merged, rejected keys returned. `hard_stop_multiplier` change triggers `recalc_hard_stop()`. Response: `{ok, applied, rejected, audit_id}`. HTTP 422 only when ALL keys rejected.
  - Added `POST /pause`: stops monitor ONLY (NOT `stop_session_monitor()` — that would kill listener). Premium Listener stays alive during pause.
  - Added `POST /resume`: calls `start_session_monitor()` which bumps generation and co-starts listener.
  - Added `GET /scan_strikes`: returns `{reason: "no_live_chain"}` when no live chain available (chain=[] short-circuits scan_strikes).
  - Added `POST /deploy_tranche1`: calls `deploy_manual_tranche1` via `asyncio.run`.
  - Added `POST /profit_book`: calls `queue_close`; returns updated `_profit_booking_queue`.
  - Added `POST /reconcile`: calls `reconcile_with_exchange`; returns `ReconciliationReport` as JSON via `dataclasses.asdict`.

- Frontend (new files):
  - `webui/frontend/src/components/mmmx/mmmxService.js`: REST client (all 15 API functions).
  - `webui/frontend/src/components/mmmx/MMMXContext.js`: React context + `MMMXProvider` + `useMMMX`. Subscribes to all 12 `mmmx_*` WS events. Exposes `{session, tranches, hedges, risk, activity, isConnected}`.
  - `webui/frontend/src/components/mmmx/useMMMXWebSocket.js`: thin hook connecting socket to context.
  - `webui/frontend/src/components/mmmx/MMMXDashboard.js`: 7-tab MUI dashboard (Status, Tranches, Hedges, Risk, Adjustments, Profit Booking, Parameters). Hot-reload param editor with allowlist lock icons + diff preview.
  - `webui/frontend/src/pages/MMMXPage.js`: thin page wrapper (MMMXProvider + MMMXDashboard).

- Frontend wiring:
  - `navigationSections.js`: added `mmmx` entry to Algorithms group with `TrendingUp` icon.
  - `App.js`: added `const MMMXPage = React.lazy(...)` + `<Route path="/mmmx" .../>`.

- `tests/test_phase8.py` (new): 43 tests across 8 test classes. All 428 tests pass (385 prior + 43 Phase 8). Zero regressions.

## 2026-04-06 — Phase 9: Fault Tolerance (Watchdog, Reconciliation, Restart)

- `webui/backend/routes/mmmx/mmmx_watchdog.py` (new):
  - `MMMXWatchdog` class: supervisor daemon thread polling every 30s. On each tick:
    - Loads session status for each registered monitor. Only restarts RUNNING sessions.
    - Dead monitor (RUNNING) → `_restart_monitor()` calls `start_session_monitor()` (bumps generation).
    - Dead/None listener (RUNNING) → `_restart_listener()` calls `start_session_listener()` with current gen.
    - PAUSED/COMPLETE/ERROR sessions: no restart (intentional dead threads).
  - Telegram alerts deduped with 300s TTL per session+component key.
  - `get_watchdog()` singleton (global `_watchdog_instance`).
  - Isolation: ZERO imports from routes.mmm.*.

- `webui/backend/routes/mmmx/init_mmmx.py` (new):
  - `on_startup()`: called at Flask startup.
    1. Loads all sessions from DB.
    2. RUNNING sessions → `transition_status(PAUSED, reason="startup_landing")` + Telegram alert.
    3. Clears expired `_being_closed` guards (older than BEING_CLOSED_TTL_SECS=180s).
    4. `_whipsaw` state restored automatically (persisted in session dict — no mutation needed).
    5. Starts the global watchdog.

- `webui/backend/routes/mmmx/mmmx_reconciler.py` (extended):
  - Added `apply_recon_confirmation(session, operator_decision)`:
    - `accept_db`: logs audit event; DB state confirmed correct; no mutation.
    - `accept_exchange`: closes matching DB tranche leg (status→CLOSED, close_reason→recon_accept_exchange).
    - `manual_close`: adds divergence to `session._naked_positions` for watchdog tracking.
    - Unknown action → ValueError.
  - Added `_force_close_db_leg()`: helper matching by "symbol:tranche_id:leg" divergence_id format.

- `webui/backend/routes/mmmx/mmmx_api.py` (extended):
  - Added `POST /api/mmmx/session/<id>/confirm-reconcile`:
    - Validates action (accept_db | accept_exchange | manual_close). 422 on bad action.
    - Calls `apply_recon_confirmation(session, body)`. Saves session. Returns `{ok, session_id}`.
  - Updated `GET /api/mmmx/health`: added `watchdog_alive` and `last_watchdog_tick` fields.

- Frontend:
  - `mmmxService.js`: added `confirmReconcile(id, divergenceId, action, notes)`.
  - `MMMXDashboard.js` (extended):
    - Added 8th tab "Reconcile": shows ReconciliationReport with per-divergence action buttons
      (Accept DB / Accept Exchange / Manual Close) calling POST /confirm-reconcile.
    - Status tab: added watchdog status chip (alive/dead), last tick timestamp, monitor counts.
      Fetched from GET /health on session status change.

- `tests/test_phase9.py` (new): 35 tests across 8 test classes. All 463 tests pass (428 prior + 35 Phase 9). Zero regressions.

## 2026-04-06 — MMMX Production Wiring (Post-Phase-9)

- `webui/backend/app.py`: Registered `mmmx_bp` Blueprint, called `init_mmmx_websocket(socketio)` and `init_mmmx()` immediately after the MMM block. MMMX REST API is now live at `/api/mmmx/*` when the backend starts.

- `webui/backend/routes/mmmx/mmmx_iv_adapter.py` (new): Read-only IV rank adapter wrapping `services/patience_iv.get_current_iv_percentile()`. Exposes `get_iv_rank()`. Zero `routes.mmm.*` imports — isolation clean. Resolves Ambiguity A8 from the implementation plan.

- `webui/backend/routes/mmmx/mmmx_monitor.py`: Replaced hardcoded `iv_rank: None` and `spot_price: None` in the heartbeat metrics dict with live values. `iv_rank` comes from `mmmx_iv_adapter.get_iv_rank()`; `spot_price` from `options_chain.chain_service._get_spot_price('BTC')`. Both are None-safe — failures are swallowed and callers already guard with `or 0.0`.

- Frontend build refreshed: `npm run build` confirmed all 70 JS files within budget. MMMX lazy chunk (`8540.e3704a34.chunk.js`) confirmed present. Navigation entry, `/mmmx` route, and MMMXPage already wired in prior phase.

- All 463 MMMX tests pass. MMM isolation scan clean.

## 2026-04-06 — MMMX Control Terminal Architecture Analysis (No Runtime Changes)

- Per mandatory process, completed deep read/audit before design output:
  - Specs: `MMMX_COMPLETE.md`, `MMMX_IMPLEMENTATION_PLAN.md` (full pass)
  - Existing MMM UI control surface: `MMMDashboard.js`, `MMMContext.js`, `mmmService.js`, `MMMSettingsDialog.js`, `MMMConfigPanel.js`, `MMMStatusBanner.js`, `MMMPositionsTable.js`, `MMMBothSidesAlert.js`, plus all dashboard-imported risk/safety/audit panels.
  - Existing MMMX WebUI baseline: `MMMXDashboard.js`, `MMMXContext.js`, `mmmxService.js`, `useMMMXWebSocket.js`.

- Produced a mission-critical MMMX WebUI control-interface architecture focused on operator safety and failure visibility:
  - WebSocket-first live state/event model,
  - trigger-priority-aware operator workflows,
  - explicit escalation/acknowledgement ladder for naked/partial/orphan states,
  - hot-reload governance grouped by risk domain,
  - edge-case runbooks (recovery tranches, residual fills, reserve depletion, orphan hedges, restart+reconcile).

- No production backend/frontend trading logic was modified in this session.

## 2026-04-07 — MMMX WebUI Specification Document (`mmmx_webUI.md`)

- Created new documentation file: `mmmx_webUI.md` (repository root).
- Document defines mission-critical MMMX control-terminal design only (no code changes), including:
  - terminal layout (session rail, command strip, execution core, risk stack),
  - WebSocket-first live event/state contract,
  - control gating + confirmation tiers,
  - incident severity/escalation model,
  - hot-reload governance by risk domain,
  - edge-case operator runbooks (recovery tranches, partial fills, reserve depletion, orphan hedges, restart+reconcile),
  - explicit “NOT DEFINED IN SPEC” list for unresolved product decisions.
- No backend or frontend runtime behavior was modified in this session.

  ## 2026-04-07 — MMMX WebUI Gap Analysis + Completion Addendum (Doc-Only)

  - Updated `mmmx_webUI.md` with a **critical gap-analysis completion addendum** (no redesign of existing sections 1–14):
    - Added identified safety/state/execution/decision/stress/health gaps with severity and current-state flags.
    - Added full design for 10 mandatory missing control components:
      1) Global Kill Switch System,
      2) State Integrity Monitor,
      3) Order Lifecycle Timeline,
      4) Critical Mode UI,
      5) Operator Error Prevention Layer,
      6) System Health Score Engine,
      7) Delta/Change Tracking Panel,
      8) Action Recommendation Engine,
      9) Trigger Explanation Panel,
      10) Incident Auto-Focus System.
    - For each component, documented: purpose, location, data, visual design, operator interaction, failure behavior, event wiring, and per-scenario failure-test expectations (API failure / WS disconnect / partial data / stale state).
    - Added integration mapping to existing MMMX tabs/panels and explicit cross-component safety completion gates.

  - Explicitly flagged unresolved dependencies as `NOT DEFINED IN SPEC` where contracts are missing (e.g., per-order lifecycle events, trigger-evaluation payload schema, command-ack correlation schema, integrity checksum/version contract).

  - Document-only session: no backend/frontend runtime trading logic changed.

## 2026-04-07 — MMMX WebUI Executable Phase Plan Conversion (Doc-Only)

- Created `mmmx_webUI_implementation_plan.md` as a strict conversion of finalized `mmmx_webUI.md` into a granular implementation program (no redesign, no requirement removal).
- Plan includes:
  - full parsed requirement inventory (components, controls, invariants, event dependencies),
  - micro, independently testable phase sequence with strict per-phase fields:
    - phase name,
    - objective,
    - components,
    - data contracts,
    - websocket events,
    - UI states,
    - failure states,
    - strict exit criteria,
  - cross-phase wiring map (N→N+1),
  - dependency graph + per-phase BLOCKED/READY validation,
  - control safety validation matrix (enabled/disabled/blockers/confirmation),
  - event contract validation report with explicit tags:
    `EVENT MISSING`, `EVENT MISMATCH`, `EVENT INSUFFICIENT`,
  - missing backend requirements list,
  - implementation risk register.

- Confirmed and documented live contract drifts in current code (not fixed in this doc-only task), including:
  - `mmmx_whipsaw` (backend emit) vs `mmmx_whipsaw_update` (frontend subscribe),
  - payload shape mismatches for heartbeat/tranche/hedge/circuit-breaker consumer expectations.

- No backend/frontend runtime trading logic was modified in this session.

## 2026-04-07 — MMMX WebUI Implementation Start (Phase 0/2 Foundation + Force Heartbeat)

- Started live implementation from `mmmx_webUI_implementation_plan.md` with an incremental safety-first slice (no redesign):
  - **Phase 0 contract baseline wiring** (frontend runtime validation + drift visibility),
  - **Phase 2 control-safety base** (deterministic lock reasons + stale-context gating),
  - missing manual control path for **Force Heartbeat** endpoint (backend + frontend client wiring).

- **Frontend changes**
  - `webui/frontend/src/components/mmmx/mmmxEventContracts.js` (new)
    - Added event contract registry and payload validator.
    - Added explicit issue typing (`EVENT_MISSING`, `EVENT_MISMATCH`, `EVENT_INSUFFICIENT`) and helpers for circuit-breaker/heartbeat normalization.
  - `webui/frontend/src/components/mmmx/MMMXContext.js`
    - Added contract state (`SYNCED/DRIFT/UNKNOWN`) + violation tracking in context reducer.
    - Added runtime contract validation per websocket event.
    - Fixed emitter/consumer mismatch handling:
      - subscribe to both `mmmx_whipsaw` and legacy `mmmx_whipsaw_update`,
      - normalize circuit breaker state from `state || new_state || old_state`,
      - fallback refresh path when tranche/hedge array payloads are insufficient.
    - Added missing event consumers: `mmmx_naked_position`, `mmmx_session_created`, `mmmx_session_stopped`.
  - `webui/frontend/src/components/mmmx/mmmxControlSafety.js` (new)
    - Added deterministic control enable/disable rules and lock reasons for B/C controls.
    - Added stale-context lock policy (WS disconnected / contract UNKNOWN).
  - `webui/frontend/src/components/mmmx/MMMXDashboard.js`
    - Integrated control-safety locks into session card actions and Status tab controls.
    - Added contract-status visibility chip and control-lock reason panel.
    - Added command pending-state wrapper to block duplicate submissions.
    - Wired Force Heartbeat action in UI controls.
  - `webui/frontend/src/components/mmmx/mmmxService.js`
    - Added `forceHeartbeat(sessionId, reason)` REST client method.

- **Backend changes**
  - `webui/backend/routes/mmmx/mmmx_api.py`
    - Added `POST /api/mmmx/session/<id>/force-heartbeat` endpoint.
    - Endpoint behavior:
      - allows RUNNING/PAUSED only,
      - wakes monitor immediately via existing signal path,
      - uses listener path when attached,
      - persists `_force_check` markers best-effort,
      - treats generation-save conflict as non-fatal (`save_ok=false`) because wake signal is already dispatched.

- **Tests**
  - `webui/backend/routes/mmmx/tests/test_phase8.py`
    - Added Force Heartbeat endpoint coverage:
      - success path,
      - listener-attached path,
      - invalid status,
      - dead monitor,
      - unknown session,
      - generation-conflict non-fatal save case.
  - Verification run: `python3 -m pytest webui/backend/routes/mmmx/tests/test_phase8.py -q`
    - **50 passed**, 0 failed.

- Why this slice first:
  - closes high-risk contract drift blind spots before deeper feature rollout,
  - enforces safer operator actions under stale/degraded context,
  - enables explicit manual heartbeat forcing using existing listener/monitor architecture.

## 2026-04-07 — MMMX Trigger Evaluation Contract (winner + ladder)

- Added backend trigger explainability contract so each beat can publish full trigger-priority evaluation, not just the winner:
  - `webui/backend/routes/mmmx/mmmx_trigger.py`
    - introduced `evaluate_with_ladder(session, metrics)` returning `(winner, ladder)`.
    - ladder rows include priority/status/reason/data for all trigger checks.
    - preserved legacy behavior via `evaluate()` delegating to `evaluate_with_ladder()` and returning only winner (backward compatible with existing logic/tests).

- Added WebSocket emitter for trigger explainability payloads:
  - `webui/backend/routes/mmmx/mmmx_websocket.py`
    - new `emit_trigger_evaluation(...)` emitting `mmmx_trigger_evaluation` with `session_id`, `beat_number`, `status`, optional `winner`, `ladder`, and optional `metrics`.

- Wired monitor heartbeat to emit trigger evaluation every beat:
  - `webui/backend/routes/mmmx/mmmx_monitor.py`
    - switched trigger evaluation call to `evaluate_with_ladder(...)`.
    - emits `mmmx_trigger_evaluation` before dispatch path, preserving existing HARD_STOP/DTE dispatch behavior.

- Wired frontend contract + consumer path for the new event:
  - `webui/frontend/src/components/mmmx/mmmxEventContracts.js`
    - registered `mmmx_trigger_evaluation` payload contract.
  - `webui/frontend/src/components/mmmx/MMMXContext.js`
    - subscribed to `mmmx_trigger_evaluation`.
    - stores `risk.trigger_winner`, `risk.trigger_ladder`, `risk.last_trigger_eval_at`.
    - pushes lightweight activity entries when a winner is present.
  - `webui/frontend/src/components/mmmx/MMMXDashboard.js`
    - surfaced trigger winner + ladder preview in `Risk` tab.

- Added tests for the new contract slice:
  - `webui/backend/routes/mmmx/tests/test_phase10.py`
    - validates trigger ladder semantics (priority winner + blocked rows + backward compatibility), websocket emitter payload shape, and monitor heartbeat wiring for trigger evaluation emission.

- Verification runs:
  - `python3 -m pytest webui/backend/routes/mmmx/tests/test_phase10.py -q` → **5 passed**.
  - `python3 -m pytest webui/backend/routes/mmmx/tests/test_phase3.py webui/backend/routes/mmmx/tests/test_phase8.py -q` → **86 passed**.

## 2026-04-07 — MMMX Phase 7 unblock: Granular Order Lifecycle Stream

- `webui/backend/routes/mmmx/mmmx_websocket.py`
  - Added granular lifecycle emitters required by Phase 7 execution timeline contract:
    `mmmx_order_intent`, `mmmx_order_ack`, `mmmx_order_partial`, `mmmx_order_retry`, `mmmx_order_filled`, `mmmx_order_failed`.
  - Added shared `_order_payload_base(...)` to keep payload shape consistent across events.

- `webui/backend/routes/mmmx/mmmx_executor.py`
  - Instrumented `smart_execute()` and `emergency_execute()` to emit end-to-end lifecycle transitions:
    intent at order start, ack on placement, retry on reprices/fallback loops, partial on residual fills,
    filled on successful completion, failed on terminal errors.
  - Added fallback correlation plumbing (`origin_client_order_id`) for limit→emergency escalation visibility.
  - Added terminal-failure guard in emergency path to prevent duplicate `mmmx_order_failed` terminal emits.

- `webui/backend/routes/mmmx/mmmx_hedger.py`
  - Passed `session_id` and `tranche_id` into hedge `smart_execute()` calls so lifecycle telemetry is attributable per session/tranche.

- `webui/backend/routes/mmmx/mmmx_premium_listener.py`
  - Passed `session_id` and `tranche_id` into CB_NEAR_ITM emergency-reduce execution calls for full lifecycle attribution.

- `webui/frontend/src/components/mmmx/mmmxEventContracts.js`
  - Registered payload contracts for all 6 lifecycle events to eliminate `EVENT MISSING` for this stream.

- `webui/frontend/src/components/mmmx/MMMXContext.js`
  - Added `execution` state (`timeline`, `last_event_at`) and reducer support for lifecycle events.
  - Subscribed to all 6 lifecycle websocket events and routed them into timeline state (session-scoped).

- `webui/frontend/src/components/mmmx/MMMXDashboard.js`
  - Added new **Execution** tab with lifecycle timeline rendering and filters (stage/side/symbol).
  - Shows attempt/mode/IDs/fill-residual/reason metadata for operator troubleshooting.

- `webui/backend/routes/mmmx/tests/test_phase11.py` (new)
  - Added Phase 11 tests for lifecycle emitters + executor wiring:
    emitter payload checks, smart_execute intent/ack/fill flow, preflight-failure flow,
    partial-fill emission, and emergency retry/fail flow.

- Verification:
  - `python3 -m pytest webui/backend/routes/mmmx/tests/test_phase11.py webui/backend/routes/mmmx/tests/test_phase2.py webui/backend/routes/mmmx/tests/test_phase10.py -q`
  - Result: **50 passed**, 0 failed.

## 2026-04-07 — MMMX Section 20 Closures (Integrity + Kill Progress + Critical UX)

- `webui/backend/routes/mmmx/mmmx_integrity.py` (new)
  - Added deterministic integrity signature builder (`state_version`, `state_checksum`, schema, generated timestamp) for snapshot/stream drift detection.

- `webui/backend/routes/mmmx/mmmx_api.py`
  - `GET /session/<id>` now includes `_integrity` payload.
  - `POST /kill-switch` now emits lifecycle progress (`accepted`, per-session `session_result`, `completed`) and returns `correlation_id` for UI tracking.

- `webui/backend/routes/mmmx/mmmx_monitor.py`
  - Heartbeat now computes integrity signature each beat and emits it in websocket heartbeat extras.

- `webui/backend/routes/mmmx/mmmx_websocket.py`
  - Added `emit_kill_switch_progress(...)` event emitter.

- `webui/backend/routes/mmmx/mmmx_trigger.py`
  - Enriched trigger ladder rows with `threshold`, `value`, `excluded_by`, and `would_status` metadata for operator explainability.

- `webui/backend/routes/mmmx/tests/test_phase8.py`
  - Added API assertion coverage for `_integrity` snapshot payload shape.

- `webui/backend/routes/mmmx/tests/test_phase9.py`
  - Added kill-switch lifecycle telemetry assertions (`accepted → session_result → completed`) + `correlation_id` checks.

- `webui/backend/routes/mmmx/tests/test_phase10.py`
  - Added assertions for new trigger ladder explainability fields.

- `webui/frontend/src/components/mmmx/mmmxEventContracts.js`
  - Added heartbeat optional `integrity` contract and `mmmx_kill_switch_progress` contract.

- `webui/frontend/src/components/mmmx/MMMXContext.js`
  - Added stream/snapshot integrity state tracking with mismatch detection and drift promotion.
  - Added kill-switch progress subscription/state updates.

- `webui/frontend/src/components/mmmx/MMMXDashboard.js`
  - Added command-strip kill-switch progress chip + progress bar.
  - Added Status-tab State Integrity Monitor card (stream vs snapshot versions/checksums + mismatch display).
  - Added incident ETA chips, critical panel ETA chips, and dedicated critical-mode emergency layout.
  - Extended Trigger Engine rendering with exclusion + would-status context.

- `mmmx_webUI.md`
  - Updated Section 20 progress matrix: closed prior partials for A1, B1, D2, E1, E3 and updated Section 19 gate re-check summary.

- Verification:
  - `python3 -m pytest -q webui/backend/routes/mmmx/tests/test_phase8.py webui/backend/routes/mmmx/tests/test_phase9.py webui/backend/routes/mmmx/tests/test_phase10.py`
  - Result: **95 passed, 8 warnings**, 0 failed.

## 2026-04-07 — MMMX WebUI Final Consistency Closure (Doc Sync)

- `mmmx_webUI.md`
  - Closed stale “NOT DEFINED” contract notes that were already implemented in code.
  - Section 16.1 updated: kill-switch command progress contract now documented as implemented via `mmmx_kill_switch_progress` with correlation lifecycle (`accepted → session_result → completed`).
  - Section 16.3 updated: granular order lifecycle events now documented as implemented (`mmmx_order_intent/ack/partial/retry/filled/failed`).
  - Section 16.9 updated: trigger explanation payload event now documented as implemented (`mmmx_trigger_evaluation`).
  - Section 17.2 rewritten from generic unresolved list to resolved-state notes for whipsaw drift normalization, lifecycle events, and trigger-evaluation payload; left only one genuinely open item: unified non-kill command-ack schema.

- Why:
  - User requested checking for remaining work in `mmmx_webUI.md`; this pass removes stale contradictions between spec text and implemented MMMX backend/frontend behavior.

## 2026-04-07 — MMMX WebUI Full Refactor: 3500-line monolith → modular component tree

### What changed and why

- **Root cause**: `MMMXDashboard.js` was a 3,500-line monolith containing all tabs, dialogs, helpers, constants, and derivation functions inline. This made it unmaintainable and error-prone (e.g., whipsaw score bug silently returned 0 after page reload).

### Files created

**Utilities:**
- `utils/mmmxConstants.js` — All shared constants: STATUS_CFG, scfg, HEDGE_COLOR, ORDER_EVENT_META, HOT_RELOAD_ALLOWLIST, INCIDENT_RANK, INCIDENT_COLOR
- `utils/mmmxFormatters.js` — Pure formatting/time utilities: fmt, pnlColor, computeDTE, heartbeatAge, sessionDisplayName, computeUpcomingExpiries, deriveWhipsawLevel (new — matches Python backend get_level() exactly)
- `utils/mmmxDerivations.js` — All derived state: deriveIntegrityState, deriveConfidence, buildIncidentQueue, deriveSystemHealth, deriveRecommendations

**Core UI:**
- `MMMXErrorBoundary.js` — Class component error boundary; wraps all tab panels so one crash can't blank the dashboard
- `MMMXSessionCard.js` — Session list card with DTE animation (pulse at ≤7 DTE, fast pulse at ≤3 DTE)
- `MMMXTopCommandStrip.js` — Status strip with WS/integrity/health/confidence/incident chips + kill buttons
- `MMMXIncidentQueuePanel.js` — Scrollable incident list with ETA countdown chips
- `MMMXCriticalModePanel.js` — Emergency layout panel shown on L3+ incidents
- `MMMXCreateSessionDialog.js` — Create session + Deploy Tranche 1 dialogs (live expiry picker from Delta Exchange)

**Tabs (10 original):**
- `tabs/MMMXStatusTab.js`, `MMMXTranchesTab.js`, `MMMXHedgesTab.js`, `MMMXTriggerEngineTab.js`
- `tabs/MMMXRiskTab.js`, `MMMXExecutionTab.js`, `MMMXAdjustmentsTab.js`
- `tabs/MMMXProfitBookingTab.js`, `MMMXParametersTab.js`, `MMMXReconcileTab.js`

**Phase 3 panels (7 new):**
- `panels/MMMXSafetyPanel.js` — Filters activity by type==='safety', severity-colored list
- `panels/MMMXTradeAuditPanel.js` — Paginated trade audit log from `/session/:id/audit`
- `panels/MMMXFeesCapitalPanel.js` — fees_tracking.* stats + budget/capital utilisation
- `panels/MMMXRegimePanel.js` — Whipsaw state machine score bar + ATM shield event trail (uses session._whipsaw_score, shield_event_history, shield_fire_count)
- `panels/MMMXDeltaExposurePanel.js` — Per-tranche CE/PE entry_delta/current_delta breakdown + portfolio delta bar
- `panels/MMMXPnLChart.js` — Pure SVG sparkline of P&L + delta over heartbeat history (no chart library)
- `panels/MMMXPerformancePanel.js` — Analytics summary: premium efficiency, fee ratio, hedge cost, P&L std dev

**Dashboard shell:**
- `MMMXDashboard.js` — Slimmed from 3,321 → 646 lines (orchestration only). Now has 17 tabs total (10 original + 7 new), visibility-aware polling for session list, Snackbar action feedback, MMMXErrorBoundary wrapping on every tab, auto-focus incident routing updated for Safety/Regime tabs.

### Bugs fixed

- `MMMXContext.js` line 117: `s?._whipsaw?.score ?? 0` → `s?._whipsaw_score ?? 0` — whipsaw score was always 0 after page reload until next WS event (nested field `_whipsaw` doesn't exist; backend uses flat `_whipsaw_score`)
- `MMMXContext.js`: Added `pnlHistory` state accumulation (PUSH_PNL_SNAPSHOT on every heartbeat) — enables PnL sparkline chart without backend changes

### Invariants preserved

- No changes to MMM algo logic (mmm_monitor, mmm_engine, etc.)
- No changes to MMMX backend (routes/mmmx/*)
- No new backend endpoints required for Phase 1–3
- Tiered confirmation system (A/B/C) preserved exactly
- All original control safety gating preserved exactly

## 2026-04-07 — MMMX WebUI Phase 4/5: Risk Rail + Health Radar

- Implemented **Phase 4 persistent right risk rail** in `webui/frontend/src/components/mmmx/MMMXDashboard.js`:
  - Upgraded layout from 2-column to 3-column (`left list` + `center detail` + fixed `right 220px risk rail`).
  - Added new right rail shell with LIVE/STALE connectivity chip.
  - Kept existing tab indices 0–16 unchanged.

- Added new panel `webui/frontend/src/components/mmmx/panels/MMMXRiskRail.js`:
  - Sectioned risk widgets in outlined cards: portfolio delta, whipsaw, circuit breaker, hard-stop utilization, CE/PE reserve levels.
  - Added pure-SVG mini P&L sparkline (last 20 points from `pnlHistory`).
  - Added reserve history mini-sparklines (CE/PE) using new `reserveHistory` context data.
  - Graceful empty-state handling (`No session` / `No history yet`).

- Implemented **Phase 5a health radar tab** with new panel `webui/frontend/src/components/mmmx/panels/MMMXHealthRadar.js`:
  - Pure SVG radar/spider chart with 6 dimensions (Connectivity, Heartbeat, Delta Balance, Whipsaw, Reserve, P&L Health).
  - Added overall health score badge with threshold coloring.

- Updated `webui/frontend/src/components/mmmx/MMMXDashboard.js`:
  - Imported/wired `MMMXRiskRail` and `MMMXHealthRadar`.
  - Added new tab label **Health Radar** at index **17**.
  - Added `TabPanel` index 17 wrapped in `MMMXErrorBoundary`.

- Updated `webui/frontend/src/components/mmmx/MMMXContext.js` for **Phase 5b reserve history accumulation**:
  - Added `reserveHistory` to init state (`[{ at, ce, pe }]`, max 100).
  - Added reducer action `PUSH_RESERVE_SNAPSHOT`.
  - Added heartbeat dispatch (immediately after `PUSH_PNL_SNAPSHOT`) to capture reserve snapshots using heartbeat values with session fallback.
  - Exposed `reserveHistory` in context value alongside `pnlHistory`.

- Validation:
  - Ran frontend diagnostics on all modified/new files via VS Code problems check.
  - Result: **No errors** in `MMMXDashboard.js`, `MMMXContext.js`, `MMMXRiskRail.js`, `MMMXHealthRadar.js`.

## 2026-04-07 — MMMX Phase 4/5 verification pass (no additional code changes)

- Re-checked `MMMXDashboard.js`, `MMMXContext.js`, `panels/MMMXRiskRail.js`, and `panels/MMMXHealthRadar.js` against the Phase 4/5 task requirements.
- Confirmed the required 3-column layout, persistent right risk rail, Health Radar tab at index 17, reserve history accumulation, and reserve sparklines are already implemented and wired.
- Ran diagnostics on all target MMMX files; result was clean with no reported errors.


## 2026-04-07 — MMMX scan_strikes endpoint fix (strike preview always pending)

- Fixed `webui/backend/routes/mmmx/mmmx_api.py` — `scan_strikes_endpoint`:
  - Bug 1: Endpoint rejected DRAFT status with 409 — but the Status tab only calls scan_strikes on DRAFT sessions. Added DRAFT to the allowed status set.
  - Bug 2: Endpoint passed `chain=[], spot=None` hardcoded, so `scan_strikes()` always returned None → always `no_live_chain`. Now fetches live chain via `OptionsChainService`.
  - Bug 3: Expiry format mismatch — session stores DDMMYY (6-char) but chain service `_build_chain` needs DDMMYYYY (8-char). Added conversion.
  - Bug 4: Response format mismatch — frontend expects `{ce: {...}, pe: {...}}` but endpoint returned `{ce_candidates: [...], pe_candidates: [...]}`. Fixed response format to include `ce`, `pe` flat objects with `mark_price` and `iv` fields.
- Updated `webui/backend/routes/mmmx/tests/test_phase8.py`:
  - Updated `TestScanStrikes` to patch `OptionsChainService` instead of `scan_strikes` directly.
  - Updated `test_draft_session_returns_409` → `test_draft_session_now_allowed` (200 not 409).
  - Added `test_draft_no_expiry_returns_no_expiry_set` for new no_expiry_set path.
  - Updated `ce_candidates` → `ce: None` assertion.

## 2026-04-07 — MMMX scan_strikes expiry not found (follow-up fix)

- Root cause: `mmmx_state.py` `create_session()` initialized `expiry_ddmmyy: None` and never read `target_expiry_ddmmyy` from the incoming params. So all new sessions were stored with `expiry_ddmmyy=None` even when user selected an expiry in the dialog.
- The `list_sessions` query in storage already had the fallback (`blob.get('expiry_ddmmyy') or blob.get('params.target_expiry_ddmmyy')`), which is why the sidebar showed DTE correctly — but `load_session` returns raw JSON, so the scan_strikes endpoint got `None`.
- Fix 1: `mmmx_state.py` — `create_session()` now pops `target_expiry_ddmmyy` from merged_params and sets it as root-level `expiry_ddmmyy`.
- Fix 2: `mmmx_api.py` `scan_strikes_endpoint` — added fallback to `params.target_expiry_ddmmyy` for existing sessions already in the DB with the old schema.

---

## 2026-04-08 — Fix Reversal-Skip Loop: Three Hedge Failures

**Investigation trigger**: Session `mmm08apr26-1` stuck at P&L -$108 with 3 consecutive `reversal_skip` events. No PE sold to hedge CE losses despite 30 adjustments. Spot was rising, CE @ 72800 losing, but algo kept skipping.

**Root cause analysis** (via DB read + code trace): Three compounding failure modes:

### FM2 — Frozen Position Profit Masking (primary cause)
`calculate_reversal_loss` (mmm_engine.py) aggregated P&L across ALL CE adj positions (active strike 72800 + frozen strike 73000). Frozen CE @ 73000 (entry 64.0, now ~15) was so profitable it offset the active CE @ 72800 loss (entry 69.5, now ~80), making net `adjustment_pnl` positive → `should_skip_reversal_adjustment` returned True → no PE sold.

**Fix**: Track `active_strike_pnl` (fills at current active strike only) separately from `total_adj_pnl` (all positions). `calculate_reversal_loss` now returns 4 values: `(loss_to_cover, active_strike_pnl, total_adj_pnl, incomplete)`. Skip gate changed to: skip iff BOTH `active_strike_pnl >= 0 AND total_adj_pnl >= 0`. Frozen profits at old strikes can no longer block hedging of genuine active-strike losses.

### FM3 — Trigger Reset After Reversal Skip (loss amnesia)
`handle_reversal_skip_transition` called `update_trigger_snapshots(ce_now, pe_now)` even when no hedge was placed, ratcheting the CE trigger from entry (69.5) up to current price (80+). Subsequent standard-formula beats computed loss as `(current - 80)`, losing the 10.5-point accumulated loss from entry.

**Fix**: After calling `update_trigger_snapshots`, restore the aggressor's trigger snapshot to `min(old_trigger, agg_now)` — the trigger can only ratchet DOWN after a skip, never UP. Loss baseline from entry is preserved for the next hedge.

### FM1 — Consecutive Reversal-Skip Circuit Breaker (safety net)
CE skips → `last_aggressor=CE` → PE triggers → PE skips → `last_aggressor=PE` → CE triggers → reversal loop repeats indefinitely.

**Fix**: Added `_consecutive_reversal_skip_count` counter, incremented in `handle_reversal_skip_transition`, reset to 0 on successful hedge execution. If count reaches `reversal_skip_force_through` param (default: 3), bypass reversal detection and force standard formula regardless of direction.

**Files changed**:
- `mmm_engine.py` — `calculate_reversal_loss`: 4-value return, `active_strike_pnl` tracked separately
- `mmm_reversal.py` — `should_skip_reversal_adjustment`: new signature (active, total); skip gate = both >= 0. `handle_reversal_skip_transition`: increments counter, aggressor trigger no-ratchet-up
- `mmm_monitor.py` — circuit breaker before `detect_reversal`; updated call sites; `_consecutive_reversal_skip_count` reset on hedge success
- `tests/test_sealed_mmm_reversal.py` — updated S1-S3 → S1-S6; added H5-H6 contracts
- `tests/test_sealed_calculate_loss.py` — updated C-RL-* for 4-value return; added C-RL-11 (FM2 key case)
- `tests/test_mmm_reversal.py` — updated `should_skip_reversal_adjustment` call sites

**Test result**: 1257 passed, 0 failed.

## 2026-04-08 — Fix Strike Shift Failed: No-Hedge Loop When All OTM Options Are Cheap

**Root cause**: `_process_strike_shift` had a `return` after emitting the "Strike Shift Failed" warning when `find_new_strike` returned None. `_process_shift_fallback` existed (with full logic to sell at the decayed strike) but was **never called** — dead code. This caused an indefinite no-hedge loop near expiry or after a large market move when all OTM CE strikes have premium < `shift_threshold` ($50).

**Scenario**: PE triggered → CE is hedge → CE @ 72800 premium = $16.22 (below $50 threshold) → `find_new_strike` returns None (all OTM calls cheap) → no hedge executed → repeats every heartbeat.

**Fix**:
- `mmm_monitor.py`: After `find_new_strike` returns None (post all scan retries), call `_process_shift_fallback(side, loss, hedge_premium, ce_now, pe_now)` instead of silently returning. Gated by new param `shift_fallback_enabled` (default `True`). Updated `emit_safety` message to say "Activating fallback" instead of "Retrying next heartbeat".
- `mmm_state.py`: Added `'shift_fallback_enabled': True` to `DEFAULT_PARAMS` and to `HOT_RELOAD_PARAMS`.
- `mmm_config.py`: Added `shift_fallback_enabled` to `HOT_RELOAD_PARAMS` dict (hot=True) and to descriptions.

**Files changed**:
- `mmm_monitor.py` — `_process_strike_shift`: call `_process_shift_fallback` when no new strike found
- `mmm_state.py` — `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS`: added `shift_fallback_enabled`
- `mmm_config.py` — `HOT_RELOAD_PARAMS` + descriptions: added `shift_fallback_enabled`

**Test result**: 1257 passed, 0 failed.

## 2026-04-08 — Dangerous Mode: Operator-Controlled Safety Gate Bypass

**Problem**: During 0DTE expiry (typically after 11 AM IST when positions become near-ATM), all safety gates (cooldowns, regime blocks, whipsaw, consecutive direction limits) prevent timely hedging. The algo was designed for 5DTE with recovery time; near expiry these protections become obstacles.

**Solution**: `dangerous_mode` — a hot-reloadable param (default OFF) that bypasses all time-based and strategy-level blockers. Operator activates manually when fast response is needed. Max loss hard stop, ITM guard, auto-close near expiry, and margin ORANGE wind-down remain active regardless.

**Bypassed when ON:**
1. Reversal cooldown (is_cooldown_active check, Step 5)
2. Whipsaw cooldown (stop_adjustments safety action)
3. Consecutive direction block (IMP-5 limiter)
4. Strike shift cooldown (shift_cooldown_sec)
5. Regime FORCE_REDUCE (gamma emergency pause → skipped, log only)
6. Regime ACTION_PAUSE (vol/trend pause → skipped, log only)
7. Regime ACTION_BLOCK_ALL_SELLS (→ skipped, trigger evaluation continues)
8. Margin YELLOW sell-block (→ skipped, ORANGE wind-down still enforced)
9. Asymmetry 7:1 block (_asymmetry_blocked_side check)
10. FM1 reversal-skip circuit breaker (_consecutive_reversal_skip_count)

**Still enforced in dangerous mode:**
- max_loss hard stop (auto_close action — never bypassed)
- auto-close near expiry (auto_close action — never bypassed)
- ITM guard (selling ITM options is never correct near expiry)
- Margin ORANGE/RED wind-down (margin critical → still forces buyback)

**Files changed:**
- `mmm_state.py` — `dangerous_mode: False` in DEFAULT_PARAMS and HOT_RELOAD_PARAMS
- `mmm_config.py` — added to HOT_RELOAD_PARAMS dict (hot=True) + description
- `mmm_monitor.py` — bypass logic wired at all 10 gate locations; `_dangerous_mode` computed once early in heartbeat
- `MMMDashboard.js` — Dangerous Mode button (RUNNING/PAUSED sessions only), red banner when active, CONFIRM dialog requiring user to type "CONFIRM" before enabling; DISABLE button in banner to turn off instantly

**Test result:** 1257 passed, 0 failed.

## 2026-04-09 — Fix close_at_threshold: Reprice Must Not Exceed Threshold

**Problem**: When `close_at_threshold` fires a buy-back order (premium ≤ threshold, e.g. 15), if the order doesn't fill within 60s the reprice loop in `smart_execute` fetches fresh market quotes and reprices to the new mid-price — with no awareness of the configured threshold. If the premium bounces from 12 → 16 → 21 during retries, the algo was placing buy orders at 16, 18, 21, etc., defeating the purpose of the threshold.

**Root cause**: `smart_execute` is a generic execution engine. It had no concept of a price ceiling for buy orders. The `close_at_5` caller never passed a cap, so repricing was unconstrained.

**Fix**: Added `max_buy_price: float = None` parameter to `smart_execute` in `mmm_executor.py`:
1. **Initial placement guard** — Before placing the first order, if `mid_price > max_buy_price`, abort immediately (handles premium bounce between scan and execution).
2. **Reprice loop guard** — In each reprice iteration, after fetching fresh quotes, if `new_mid > max_buy_price`, cancel the pending order and return failure. The next heartbeat's scan will re-evaluate whether the position is still closeable.

In `mmm_close_at_5.py`, `close_position` now sets `_max_buy_price = close_at_threshold` for `mechanism == 'close_at_5'` and passes it to `smart_execute`. Other mechanisms (harvest, recycler, wind_down, etc.) pass `None` and are unaffected.

**Files changed**:
- `mmm_executor.py` — `smart_execute`: added `max_buy_price` param, initial placement guard, reprice loop guard
- `mmm_close_at_5.py` — `close_position`: extract threshold from session params, pass as `max_buy_price` for `close_at_5` mechanism only

**Test result**: 1258 passed, 0 failed.

## 2026-04-09 — Fix close_at_5: Bid Price Never Used for Active Strikes Despite close_at_use_bid=True

**Problem**: Positions at the active CE/PE strike were not being closed by close_at_5 even when their bid price was well below `close_at_threshold`. The operator could see bid = $2.49 on a position with threshold = 15, but close_at_5 never fired.

**Root cause**: In `_prefetch_all_premiums`, active strikes were seeded into `cache` (mark price cache) from `ce_now`/`pe_now` BEFORE `to_fetch` was computed:
```python
cache[(active_pe, 'put')] = pe_now   # seeded
to_fetch = [... if key not in cache]  # active_pe excluded
bid_cache = {}                         # never gets active_pe entry
```
`_fetch_one` (the only place bid prices are fetched and stored into `bid_cache`) was never called for active strikes. When `_make_bid_fetch_fn` looked up the active strike, `bid_cache` had no entry, so it fell back to `mark_cache` (mark price). If mark > threshold but bid < threshold, the position was NOT added to `closeable` → close_at_5 silently skipped it.

**Fix** (`mmm_monitor.py` — `_prefetch_all_premiums`):
- Moved active strike fallbacks into `_active_fallbacks` dict (no longer seeded before `to_fetch`)
- Changed `to_fetch = list(strike_pairs)` — includes ALL strikes, active ones included
- Active strikes now go through `_fetch_one` → bid price fetched → stored in `bid_cache`
- After fetch loop, apply `_active_fallbacks` to mark cache only (not bid_cache) for any failed fetches
- `_make_bid_fetch_fn` now returns actual bid price for active strikes when `close_at_use_bid=True`

**Cost**: 1-2 extra ticker + orderbook API calls per heartbeat (for active CE and PE strikes). These were already being fetched in `_fetch_premiums_with_fallback` at heartbeat start, so the exchange sees 2× requests for active strikes. Acceptable tradeoff to fix the correctness bug.

**Files changed**: `mmm_monitor.py` — `_prefetch_all_premiums` only

**Test result**: 1258 passed, 0 failed.

## 2026-04-09 — Fix Replenish ATM Guard: Wrong Premium Threshold in Fallback Scan

**Root cause**: When the best replenish candidate is too close to ATM (< 2× ATM shield proximity), the ATM guard tries to find a safer farther-OTM strike. The fallback scan called `find_new_strike()` which uses `shift_threshold` (e.g. $50) to filter candidates. But `replenish_min_premium` is typically lower ($30). So a perfectly viable CE strike like 71600 at $35 would be REJECTED by `find_new_strike` → no safe strike found → replenish blocked → "Human Action Required" banner.

**Live symptom (2026-04-09)**: BTC spot ~70,850. CE closed by close_at_5. Best CE candidate: 71200 (0.49% OTM). ATM buffer requires >= 1.0% OTM. `find_new_strike` then scanned for a safer strike but filtered by `shift_threshold=$50`. CE @ 71600 (~$35) and 71800 (~$21) were both below $50 → no safe strike found → replenish blocked every heartbeat.

**Fix** (`mmm_monitor.py` — `_process_replenish`):
- Hoisted `_desired`, `_opt_type`, `_above_spot`, `_chain_result`, `_chain_spot` variables to before the `if not strike_info:` strangle block so the ATM guard can reuse the already-fetched chain data.
- Replaced `find_new_strike()` call in ATM guard with a direct chain filter + `_rank_strikes` call:
  - Filter chain to strikes with OTM distance >= `_min_abs_dist` (the safe boundary)
  - Use `_rank_strikes` with `_desired` (= `replenish_min_premium`) as premium threshold
  - If safe strike found with premium >= `min_premium` → use it (correct behavior)
  - Falls back to `find_new_strike` only in straddle mode where chain data isn't pre-fetched

**Result**: Replenish can now find CE @ 71600 ($35) as a safe re-entry when 71200 is too close to ATM and `replenish_min_premium=$30`.

**Files changed**: `mmm_monitor.py` — `_process_replenish` (ATM guard fallback only)

**Tests**: 28/28 sealed replenish tests pass. 0 regressions.

## 2026-04-09 — Fix 3 Bugs in mmm_replenish.py + mmm_safety.py

**Bug analysis from reported list of 14 potential bugs. 3 confirmed real and fixed.**

**BUG-1 (P1 — replenish.py): Gate 10 used `total_lots` instead of `active_lots`**
- `total_lots = active + frozen`. If open side had 20 frozen lots (all mid-close from wind-down) and 0 active, Gate 10 passed and replenish sold a new hedge leg — but PE was about to fully close, leaving a dangling unhedged CE leg.
- **Fix**: Gate 10 now checks `active_lots` only. Reason string unchanged (`'open_side_has_no_lots'`) so sealed test still passes.

**BUG-2 (P2 — replenish.py): Gate 9 caught `ImportError` in `except Exception`**
- If `mmm_initializer` failed to import (circular import, missing module), Gate 9 was silently bypassed with a warning. Replenish could then fire 2 minutes before expiry.
- **Fix**: Split into two try blocks — `ImportError` is a hard block (`return False, 'gate9_import_error'`), parse exceptions remain soft-skip with warning.

**BUG-3 (P2 — safety.py): Whipsaw guard silently disabled after history truncation**
- If `adjustment_history` was compacted and `len(algo_history) < _whipsaw_last_checked_idx`, the guard condition `len > last_idx` was permanently False. History had to regrow past the old stale index before whipsaw detection resumed — potentially thousands of heartbeats.
- **Fix**: Added `elif last_checked_idx > len(algo_history):` bounds reset with warning log.

**Bugs confirmed real but NOT fixed (require sealed test unseal):**
- Bug 1 (report): `check_asymmetry()` uses `total_lots` — includes frozen lots → false 7:1 hard block during wind-down. Needs C-AS-2 through C-AS-8 test updates.
- Bug 7 (report): `check_pnl_guardrail` fires at 80%+ overlapping with `check_max_loss`. Needs C-PG-3 and C-PG-5 test updates.

**Bugs confirmed NOT real:**
- Bug 3 (report): `block_heavy_side_sells` intentionally excluded from `should_block_adjustment()` — C-SBA-5 seals this. `mmm_monitor.py:2216` already handles it with custom code.
- Bug 5 (report): `match_active` lot sizing is intentional — matching current active lots is the correct hedge amount.
- Bug 9 (report): `update_peak_pnl` as module-level function is correct — all callers import it directly, no method call.

**Tests**: 119 passed, 0 failed (sealed_mmm_replenish + sealed_mmm_safety).

**Files changed**: `mmm_replenish.py`, `mmm_safety.py`

## 2026-04-09 — Straddle Roll Fix Plan Rev 2.0 — Quant Audit (PLANNING ONLY, no code)

**What**: Critical review of STRADDLE_ROLL_FIX_PLAN.md Rev 1.0, upgraded to Rev 2.0 with 12 findings.

**Code files read for audit** (no changes made): `mmm_straddle_roll.py`, `mmm_monitor.py` (init block + heartbeat Step 5.4), `mmm_dte_presets.py` (SHORT_STRADDLE preset), `mmm_state.py` (DEFAULT_PARAMS), `mmm_wind_down.py` (is_wind_down_active), `mmm_api.py` (session creation).

**12 findings added to plan**:
- Q-1: "Roll fires at exact breakeven" claim corrected — gamma/time value creates ~2-5% drag per roll. Still dramatically better than old % trigger.
- Q-2 (FIX-1.5): `_straddle_entry_iv` must reset after roll — old entry IV causes Gate 5.5 to false-block new straddle.
- Q-3: Adaptive heartbeat interval must reset from possibly 600s back to base 120s after roll.
- Q-4 (ROBUST-4): Same-strike roll guard — if new ATM == old ATM, skip roll to avoid paying execution costs for zero benefit.
- Q-5 (ROBUST-5): Telegram alert on successful roll — operator needs to know market moved ≥400 pts.
- Q-6 (ROBUST-6): Re-fetch ATM after closing both legs — market may move during 4-leg sequential execution.
- Q-7: FIX-4 detection mechanism made concrete — check `'initial_lots' in raw_body` to distinguish default from explicit.
- Q-8: `straddle_roll_price_max_age_secs` missing from DEFAULT_PARAMS (referenced in Gate 9 code but not in mmm_state.py).
- Q-9: Table header "rupee terms" → "USD terms" (Delta Exchange is USD-settled).
- Q-10: Added §5.4 with realistic profitability analysis across 5 scenarios with actual dollar numbers.
- Q-11: Wind-down race condition analyzed and proven safe (existing guards handle it).
- Q-12: Gate 8 fallback path made concrete with 3-level cascade (live positions → pct-based → block).

**Profitability conclusion**: Strategy is viable. Profitable in ranging markets (~60-70% of sessions), slightly positive even with 3 rolls in trending markets, loss-capped in crashes. Only losing scenario is extreme repeated whipsaw (3 rolls) where collected premium doesn't offset gamma drag — rare and bounded.

**No code files changed. Planning only.** File changed: `tasks/STRADDLE_ROLL_FIX_PLAN.md`

---

## 2026-04-09 — Straddle Roll Rev 3.0 implementation + sealed tests

### Code changes (by another coding AI, audited by Claude Code):

**`mmm_straddle_roll.py`**
- Gate 8 replaced: now uses `_straddle_roll_trigger_pts` (CE+PE entry premiums in points) instead of `distance_pct >= trigger_pct`. 3-level fallback: session key → live position entry_premium → pct-based floor → `no_trigger_pts` block.
- Gate 5.5 IV spike: converted from hard block to soft warning + `_straddle_last_roll_iv_spike` audit flag. High IV = higher new premium; margin gate (Gate 5) is the real protection.
- Gate 7 emergency bypass: now uses `trigger_pts × emergency_mult` (was pct × mult). Consistent with Gate 8.
- Same-strike guard (CHANGE 3-B): skips roll if `new_atm_strike == old_atm_strike`. Prevents paying execution costs for zero benefit.
- Spread check (CHANGE 3-D): blocks roll if avg CE+PE bid-ask spread > `straddle_roll_max_spread_pct` (default 15%). Skipped silently if preview has no bid/ask.
- Post-roll trigger update (CHANGE 1-C): `_straddle_roll_trigger_pts` updated to actual CE+PE fill prices after each roll.
- Post-roll state reset (CHANGE 3-A): 20 keys popped after successful roll — trend/regime/IV/adaptive state cleared for clean slate at new ATM.
- Telegram alert (CHANGE 3-E): `alert_straddle_roll_executed()` called after successful roll (fire-and-forget).

**`mmm_monitor.py`**
- CHANGE 1-A: `_straddle_roll_trigger_pts` computed at session startup from lot-weighted CE+PE entry premiums. Resume-safe (skips if already > 0).
- CHANGE 1-D: `_run_price_guard_loop()` background thread started for SHORT_STRADDLE sessions. Reads `session['analytics']['last_spot_price']` every 5s, fires `force_heartbeat()` when within `price_guard_buffer_pts` (50pts) of trigger. Cooldown 30s.
- Bonus (out-of-scope): shift fallback premium floor (`shift_fallback_min_premium=25`), replenish ATM guard chain re-scan fix, bid cache active-strike bug fix.

**`mmm_dte_presets.py`**
- `build_short_straddle_preset()`: min hours lowered from 2h → 1h; max hours raised from 12h (ValueError) → 24h (warning only, no raise).
- `wind_down_enabled`: False (was True). Wind-down closes profitable OTM leg, fighting roll mechanism.
- `harvest_enabled`: False (was True). Partial closes break straddle symmetry.
- `straddle_roll_max_per_session`: removed from preset — operator must provide explicitly.
- Added `straddle_roll_max_spread_pct: 15.0`.

**`mmm_state.py`**
- Added to DEFAULT_PARAMS: `_straddle_roll_trigger_pts`, `price_guard_enabled`, `price_guard_interval_secs`, `price_guard_buffer_pts`, `price_guard_cooldown_secs`, `straddle_roll_max_spread_pct`, `straddle_roll_price_max_age_secs`, `shift_fallback_min_premium`.
- All new params added to HOT_RELOAD_PARAMS.

**`mmm_api.py`**
- SHORT_STRADDLE session creation now rejects (HTTP 400) if `initial_lots` or `straddle_roll_max_per_session` not in request body. Both are intentionally omitted from preset.

**`mmm_telegram.py`**
- Added `alert_straddle_roll_executed()` + async impl.

**`tests/test_sealed_mmm_dte_presets.py`** and **`test_sealed_mmm_strike_shift.py`**: updated sealed contracts for changed behavior (H<1 threshold, H>24 warning, wind-down/harvest flags).

### New sealed tests (Claude Code, this session):
- `tests/test_sealed_straddle_roll_rev3.py`: 23 new tests covering Gate 8 premium-points trigger (5 tests), IV spike soft warning, emergency bypass, hot-reload, preset flags, hard stop path, same-strike guard, spread gate, post-roll reset, API validation. All 23 pass.
- Suite: 1281 passed (was 1258 before this session; +23 new).

### Invariants preserved:
- Three-layer stale monitor protection: untouched.
- Reverse mode: untouched.
- Regular strangle (0DTE, 5DTE, SHORT_WINDOW): zero code path overlap — all changes gated behind `_preset_source == 'SHORT_STRADDLE'` and `straddle_roll_enabled=True`.

---

## 2026-04-09 — Phase 4: UI updates (MMMDashboard.js)

**`webui/frontend/src/components/mmm/MMMDashboard.js`**
- CHANGE 4-A (preset description): Updated straddle roll description from "spot moves ≥ trigger %" to "spot moves ≥ CE+PE entry premium pts". Removed hardcoded "Max 3 rolls" — now shows "operator (required)". Added "⚡ Price Guard: 5s real-time spot monitor".
- CHANGE 4-B (roll badge): `|| 3` replaced with `?? '?'` — shows `?` when operator hasn't set max_rolls (not possible after API validation, but defensive). Tooltip now shows `Next trigger: ±N pts` from `_straddle_roll_trigger_pts` session key.
- CHANGE 4-C (price guard chip): New `⚡ Guard` chip shown when session is RUNNING + SHORT_STRADDLE + price_guard not disabled. Green color, monospace, tooltip explains 5s monitoring.
- Frontend build: clean, all bundles within budget.
