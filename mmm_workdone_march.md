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
