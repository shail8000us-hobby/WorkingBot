# Implementation Prompt: Short Straddle Roll Fixes
**For: Coding AI implementing STRADDLE_ROLL_FIX_PLAN.md Rev 3.0**
**Auditor: Claude Code (separate session)**
**Date: 2026-04-09**

---

## YOUR ROLE

You are implementing the straddle roll fix plan for a live options trading bot. **Real money is at stake.** Read every instruction carefully. Do not add features not listed. Do not refactor code not mentioned. Do not touch files not in your change list.

After each phase, stop and wait for audit before proceeding.

---

## CODEBASE ORIENTATION

**Bot:** Python Flask backend, async monitor threads, Delta Exchange BTC options.
**Language:** Python 3.x backend, React frontend.
**Working directory:** `/Users/ssr/Projects/WorkingBot/`
**Active branch:** `SSR`

### Critical Files (read before touching anything)
- `webui/backend/routes/mmm/mmm_straddle_roll.py` — the roll logic you will mostly edit
- `webui/backend/routes/mmm/mmm_monitor.py` — ~9000 line monitor, touch carefully
- `webui/backend/routes/mmm/mmm_dte_presets.py` — preset factory, clean edits
- `webui/backend/routes/mmm/mmm_close_at_5.py` — `close_position()` lives here
- `webui/backend/routes/mmm/mmm_executor.py` — order execution engine
- `webui/backend/routes/mmm/mmm_state.py` — DEFAULT_PARAMS and MUTABLE_PARAMS
- `webui/backend/routes/mmm/mmm_api.py` — session creation endpoint
- `webui/backend/services/delta_price_websocket.py` — live BTC WS price feed
- `webui/frontend/src/components/mmm/MMMDashboard.js` — dashboard UI

### Files You Must NOT Touch (production strangle uses these)
```
mmm_engine.py
mmm_constants.py
mmm_wind_down.py        ← module stays, only preset changes
mmm_trigger.py
mmm_replenish.py
mmm_regime.py
mmm_guardian.py
mmm_fill_sync.py
mmm_pnl_core.py
mmm_heartbeat_health.py
webui/backend/routes/mmm/tests/  ← read only, do not edit existing tests
```

### Invariants That Must Never Break
1. Regular strangle sessions (0DTE, 5DTE, SHORT_WINDOW) must behave identically to today.
2. All SHORT_STRADDLE logic is gated behind `params.get('_preset_source') == 'SHORT_STRADDLE'`.
3. `straddle_roll_enabled` defaults to `False` in `mmm_state.py` — this is the second gate.
4. The 3-layer stale monitor protection (thread.join, primary guard, G5) must not be touched.
5. `emit_safety()` is synchronous — never wrap in `run_until_complete()`.
6. Sealed tests baseline = 1312 passed. Must remain at or above this after every phase.

---

## PRE-WORK: READ BEFORE CODING

Do these reads first. Do not skip.

```
1. Read mmm_straddle_roll.py in full
2. Read mmm_dte_presets.py → build_short_straddle_preset() function
3. Read mmm_close_at_5.py → close_position() signature (lines ~223-295)
4. Read mmm_monitor.py lines ~340-410 (straddle init block, search "_straddle_initial_credit")
5. Read mmm_monitor.py lines ~2160-2180 (hard stop auto_close path)
6. Read mmm_monitor.py lines ~766-825 (force_heartbeat + _wait_for_next_heartbeat)
7. Read delta_price_websocket.py lines 1-80 (understand prices dict structure)
8. Read mmm_state.py lines ~638-655 (existing straddle_roll params in DEFAULT_PARAMS)
```

**Key facts discovered in pre-read (verified):**
- `_auto_close_all(emergency=True)` already uses parallel taker IOC orders — this is the EXISTING hard stop path. The max_loss hard stop at monitor line ~2166 already calls `emergency=True`. **FIX-3 for the main hard stop path requires NO code change** — only verification that this path is correct and documentation in comments.
- `force_heartbeat()` already exists at mmm_monitor.py line ~766 and interrupts within 500ms.
- `delta_price_websocket.py` already stores live BTC price in `DeltaPriceWebSocket.prices['BTC']`.
- `check_straddle_roll_gates()` is decorated with `@sealed` — any behavioural change requires a new sealed test.

---

## PHASE 1 — The Fatal Bug + Architecture (implement first, audit before Phase 2)

### CHANGE 1-A: New Session Key `_straddle_roll_trigger_pts` (mmm_monitor.py)

**Location:** Find the straddle init block in `mmm_monitor.py`. Search for `_straddle_initial_credit` to find it. It's inside `if self.session.get('params', {}).get('_preset_source') == SHORT_STRADDLE_CATEGORY:`.

**What to add:** After the block that computes `_straddle_initial_credit`, add computation of `_straddle_roll_trigger_pts`:

```python
# Compute premium-based roll trigger (points of spot movement to trigger roll).
# This is CE_avg_entry_premium + PE_avg_entry_premium, lot-weighted.
# Stored per-roll: updated in mmm_straddle_roll.py after each successful roll.
ce_state = self.session.get('ce', {})
pe_state = self.session.get('pe', {})
_ce_active = [p for p in ce_state.get('positions', [])
              if p.get('status') == 'active' and p.get('lots', 0) > 0]
_pe_active = [p for p in pe_state.get('positions', [])
              if p.get('status') == 'active' and p.get('lots', 0) > 0]
_ce_lots = sum(p.get('lots', 0) for p in _ce_active)
_pe_lots = sum(p.get('lots', 0) for p in _pe_active)
_ce_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
               for p in _ce_active) / _ce_lots) if _ce_lots > 0 else 0
_pe_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
               for p in _pe_active) / _pe_lots) if _pe_lots > 0 else 0
_trigger_pts = _ce_avg + _pe_avg
if _trigger_pts > 0:
    self.session['_straddle_roll_trigger_pts'] = round(_trigger_pts, 2)
    log.info(
        f"[{self.session_id}] Straddle trigger initialised: "
        f"{_trigger_pts:.2f}pts (CE_avg={_ce_avg:.2f}, PE_avg={_pe_avg:.2f})"
    )
else:
    log.warning(
        f"[{self.session_id}] Could not compute trigger_pts — "
        f"positions may lack entry_premium. Fallback will apply at Gate 8."
    )
```

Also add `setdefault` line alongside the other straddle setdefaults:
```python
self.session.setdefault('_straddle_roll_trigger_pts', 0)
```

**Do NOT change** `_straddle_initial_credit` computation — that is separate and correct.

---

### CHANGE 1-B: Replace Gate 8 in `check_straddle_roll_gates()` (mmm_straddle_roll.py)

**Location:** `mmm_straddle_roll.py`, inside `check_straddle_roll_gates()`, find `# ── Gate 8 — Distance trigger`.

**Remove** the existing Gate 8 block entirely (it checks `distance_pct < straddle_roll_trigger_pct`).

**Replace with this complete Gate 8:**

```python
# ── Gate 8 — Distance trigger (premium-points based) ─────────────────────
# Roll fires when spot has moved ≥ (CE_entry_premium + PE_entry_premium) points.
# This is the financial breakeven of a short straddle seller.
# Fallback chain: session key → live positions → pct-based floor → block.
current_atm_strike = session.get('ce', {}).get('active_strike', 0)
if not current_atm_strike or current_atm_strike <= 0:
    return False, 'invalid_atm_strike', {}

spot_move_pts = abs(spot - current_atm_strike)

trigger_pts = session.get('_straddle_roll_trigger_pts', 0)
if trigger_pts <= 0:
    # Fallback 1: compute live from active positions
    _ce_pos = [p for p in session.get('ce', {}).get('positions', [])
               if p.get('status') == 'active' and p.get('lots', 0) > 0]
    _pe_pos = [p for p in session.get('pe', {}).get('positions', [])
               if p.get('status') == 'active' and p.get('lots', 0) > 0]
    _ce_lots = sum(p.get('lots', 0) for p in _ce_pos)
    _pe_lots = sum(p.get('lots', 0) for p in _pe_pos)
    _ce_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                   for p in _ce_pos) / _ce_lots) if _ce_lots > 0 else 0
    _pe_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                   for p in _pe_pos) / _pe_lots) if _pe_lots > 0 else 0
    trigger_pts = _ce_avg + _pe_avg
    if trigger_pts > 0:
        session['_straddle_roll_trigger_pts'] = round(trigger_pts, 2)
        log.info(f"[{sid}] Gate 8 fallback: healed trigger_pts={trigger_pts:.2f}pts from positions")
    else:
        # Fallback 2: pct-based floor (wrong but better than blocking all rolls)
        pct_fallback = straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
        if pct_fallback > 0:
            trigger_pts = pct_fallback
            log.warning(
                f"[{sid}] Gate 8 pct-fallback: trigger_pts={trigger_pts:.2f}pts "
                f"(no entry_premium on positions — check position state)"
            )
        else:
            return False, 'no_trigger_pts', {}

if spot_move_pts < trigger_pts:
    return False, (
        f'distance_below_trigger ({spot_move_pts:.0f} < {trigger_pts:.0f} pts)'
    ), {}
```

**CRITICAL:** The old Gate 8 also had the ATM strike guard (`if not current_atm_strike`). In the new code this is at the top of Gate 8. Make sure the old ATM strike check that existed BEFORE Gate 8 is not duplicated. Read the existing code carefully to avoid duplicate checks.

---

### CHANGE 1-C: Update Emergency Bypass in Gate 7 (mmm_straddle_roll.py)

**Location:** Gate 7 in `check_straddle_roll_gates()`, find `emergency_bypass`.

**Current code (approximately):**
```python
emergency_bypass = distance_pct >= straddle_roll_trigger_pct * straddle_roll_emergency_mult
```

**Replace with:**
```python
# Emergency bypass uses same trigger_pts as Gate 8.
# Compute spot_move_pts here too since Gate 8 hasn't run yet at this point.
# NOTE: current_atm_strike is read at top of Gate 8 — but Gate 7 runs before Gate 8.
# Read it locally here for the bypass check.
_g7_atm = session.get('ce', {}).get('active_strike', 0)
_g7_spot_move = abs(spot - _g7_atm) if _g7_atm > 0 else 0
_g7_trigger = session.get('_straddle_roll_trigger_pts', 0) or (
    straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
)
emergency_bypass = (
    _g7_trigger > 0 and
    _g7_spot_move >= _g7_trigger * straddle_roll_emergency_mult
)
```

---

### CHANGE 1-D: Update `_straddle_roll_trigger_pts` After Successful Roll (mmm_straddle_roll.py)

**Location:** In `_execute_straddle_roll_inner`, find Step 6 — "Update roll tracking state".

**Add to Step 6**, after updating `_straddle_roll_count` and before the event log:

```python
# Update premium-based trigger for NEXT roll — use actual fill prices, not preview.
new_trigger_pts = ce_fill_price_dec + pe_fill_price_dec
session['_straddle_roll_trigger_pts'] = float(round(new_trigger_pts, 2))
log.info(
    f"[{sid}] Roll trigger updated: "
    f"{new_trigger_pts:.2f}pts (CE={float(ce_fill_price_dec):.2f} + PE={float(pe_fill_price_dec):.2f})"
)
```

Note: `ce_fill_price_dec` and `pe_fill_price_dec` are already computed as Decimal above in Step 6. Use the existing variables.

---

### CHANGE 1-E: Add Missing DEFAULT_PARAMS Entry (mmm_state.py)

**Location:** `mmm_state.py`, find the `# ── Straddle Roll ──` section in DEFAULT_PARAMS.

**Add these two lines** to the straddle roll section:
```python
'straddle_roll_price_max_age_secs': 5,   # Gate 9 freshness check (was hardcoded)
'_straddle_roll_trigger_pts': 0,         # computed at session startup
```

Also add `'straddle_roll_price_max_age_secs'` to the `MUTABLE_PARAMS` list (search for the straddle roll section in MUTABLE_PARAMS).

---

### CHANGE 1-F: Real-Time Price Guard (mmm_monitor.py)

**Location:** `mmm_monitor.py`, inside `_run_loop()` method.

**Step 1:** Find `_run_loop()`. After the monitor start log lines and before the main `while self._running:` loop, add the price guard task launch for SHORT_STRADDLE sessions:

```python
# ── Price Guard: real-time trigger monitoring for SHORT_STRADDLE ──────────
# Reads live BTC price from Delta WebSocket (zero API calls) every N seconds.
# Fires force_heartbeat() when spot approaches roll trigger or loss approaches max_loss.
# Only active for SHORT_STRADDLE preset; degrades gracefully if WS unavailable.
_price_guard_task = None
if (self.session.get('params', {}).get('_preset_source') == SHORT_STRADDLE_CATEGORY
        and self.session.get('params', {}).get('price_guard_enabled', True)):
    _price_guard_task = asyncio.ensure_future(
        self._price_guard_loop(), loop=self._loop
    )
    log.info(f"[{self.session_id}] Price guard started for SHORT_STRADDLE session")
```

**Step 2:** In the `while self._running:` block's cleanup/finally section, cancel the task:
```python
if _price_guard_task is not None and not _price_guard_task.done():
    _price_guard_task.cancel()
    try:
        await _price_guard_task
    except asyncio.CancelledError:
        pass
```

**Step 3:** Add the `_price_guard_loop()` method to `MMMMonitor` class. Find a clean location near `force_heartbeat()` (around line 766):

```python
async def _price_guard_loop(self):
    """
    Real-time price monitor for SHORT_STRADDLE sessions.
    
    Reads live BTC price from Delta Exchange WebSocket (no REST API calls).
    Fires force_heartbeat() when:
      - Spot approaches roll trigger (within price_guard_buffer_pts)
      - Estimated loss approaches max_loss (above 85% threshold)
    
    Rate-limited: after firing, waits price_guard_cooldown_secs before firing again.
    Degrades gracefully: if WS price unavailable, does nothing (regular heartbeat continues).
    
    Architecture: This task DETECTS only. It never modifies session state or places orders.
    All order logic remains inside the heartbeat, which this task wakes up early.
    """
    params = self.session.get('params', {})
    interval_secs = params.get('price_guard_interval_secs', 5)
    buffer_pts = params.get('price_guard_buffer_pts', 50)
    cooldown_secs = params.get('price_guard_cooldown_secs', 30)
    max_loss = params.get('max_loss_amount', 3000.0)
    
    _last_fired_at = 0.0  # wall-clock time of last force_heartbeat
    
    log.debug(f"[{self.session_id}] Price guard loop started "
              f"(interval={interval_secs}s, buffer={buffer_pts}pts)")
    
    try:
        while self._running:
            await asyncio.sleep(interval_secs)
            
            if not self._running:
                break
            
            # ── Read live BTC price from WebSocket ───────────────────────
            try:
                from webui.backend.services.delta_price_websocket import get_price_websocket
                ws = get_price_websocket()
                if ws is None:
                    continue
                
                current_spot = ws.prices.get('BTC', 0)
                last_update = ws.last_update.get('BTC', 0)
                
                # Skip if WS data is stale (> 30 seconds old)
                if current_spot <= 0 or (time.time() - last_update) > 30:
                    log.debug(f"[{self.session_id}] Price guard: WS data stale or missing, skipping")
                    continue
                    
            except Exception as _ws_err:
                log.debug(f"[{self.session_id}] Price guard: WS read error: {_ws_err}")
                continue
            
            # ── Rate limit check ─────────────────────────────────────────
            if (time.time() - _last_fired_at) < cooldown_secs:
                continue
            
            # ── Read current session state (read-only) ───────────────────
            session = self.session
            atm_strike = session.get('ce', {}).get('active_strike', 0)
            trigger_pts = session.get('_straddle_roll_trigger_pts', 0)
            last_loss_estimate = session.get('_price_guard_last_loss_estimate', 0)
            
            should_fire = False
            fire_reason = ''
            
            # ── Check 1: Roll trigger approach ───────────────────────────
            if atm_strike > 0 and trigger_pts > 0:
                spot_move = abs(current_spot - atm_strike)
                approach_threshold = trigger_pts - buffer_pts
                if spot_move >= approach_threshold:
                    should_fire = True
                    fire_reason = (
                        f'roll_approach: spot_move={spot_move:.0f}pts, '
                        f'trigger={trigger_pts:.0f}pts, '
                        f'buffer={buffer_pts}pts'
                    )
            
            # ── Check 2: Loss approaching max_loss ───────────────────────
            if not should_fire and max_loss > 0 and last_loss_estimate < 0:
                loss_pct = abs(last_loss_estimate) / max_loss
                if loss_pct >= 0.85:
                    should_fire = True
                    fire_reason = (
                        f'loss_approach: {abs(last_loss_estimate):.2f} '
                        f'= {loss_pct:.0%} of max_loss {max_loss:.2f}'
                    )
            
            # ── Fire if needed ───────────────────────────────────────────
            if should_fire:
                log.info(
                    f"[{self.session_id}] Price guard firing force_heartbeat: {fire_reason}"
                )
                self.force_heartbeat()
                _last_fired_at = time.time()
                
    except asyncio.CancelledError:
        log.debug(f"[{self.session_id}] Price guard loop cancelled")
        raise
    except Exception as _pg_err:
        log.error(
            f"[{self.session_id}] Price guard loop error: {_pg_err}",
            exc_info=True
        )
        # Do not re-raise — price guard failure must not crash the monitor
```

**Step 4:** At the end of the `_heartbeat()` method, before `self._save_my_session(session)`, add the loss estimate update:

```python
# Update price guard loss estimate (read by _price_guard_loop — write once per heartbeat)
try:
    from .mmm_pnl_core import compute_current_total_pnl as _pnl_total_pg
    _pg_pnl = _pnl_total_pg(session)
    session['_price_guard_last_loss_estimate'] = _pg_pnl
except Exception:
    pass
```

Find the right spot: this should be near the end of `_heartbeat()`, after P&L is computed, before the final save.

**Add to mmm_state.py DEFAULT_PARAMS:**
```python
# Price Guard (SHORT_STRADDLE real-time monitoring)
'price_guard_enabled': True,
'price_guard_interval_secs': 5,
'price_guard_buffer_pts': 50,
'price_guard_cooldown_secs': 30,
```

Add all four to MUTABLE_PARAMS as well.

---

### PHASE 1 VERIFICATION

After all 1-A through 1-F changes:

1. Run sealed tests: `cd /Users/ssr/Projects/WorkingBot && python -m pytest webui/backend/routes/mmm/tests/ -x -q`
2. Confirm ≥ 1312 tests pass, zero failures.
3. Verify `_straddle_roll_trigger_pts` appears in DEFAULT_PARAMS.
4. Verify Gate 8 no longer references `distance_pct < straddle_roll_trigger_pct` as the primary check.
5. Stop. Report results. Wait for audit before Phase 2.

---

## PHASE 2 — Simplification (implement after Phase 1 audit passes)

### CHANGE 2-A: Disable Wind-Down and Harvest in SHORT_STRADDLE Preset (mmm_dte_presets.py)

**Location:** `build_short_straddle_preset()` function.

Find `'wind_down_enabled': True` and change to `False`.
Find `'harvest_enabled': True` and change to `False`.

Add a clear comment above each:
```python
# SHORT_STRADDLE: wind-down disabled. Roll handles repositioning;
# hard stop handles capital protection. Wind-down would close the
# profitable (decaying) hedge leg, destroying straddle structure.
'wind_down_enabled': False,

# SHORT_STRADDLE: harvest disabled. Harvesting the OTM leg breaks
# straddle symmetry. Both legs must close together on roll or expiry.
'harvest_enabled': False,
```

**Do NOT change** `auto_close_mins: 10` — this is the clean expiry exit, not wind-down.
**Do NOT touch** `mmm_wind_down.py` — the module stays intact for other strategies.

---

### CHANGE 2-B: Remove 12-Hour Session Duration Cap (mmm_dte_presets.py)

**Location:** `build_short_straddle_preset()`, near the top where H is validated.

**Remove** the block:
```python
if H > 12:
    raise ValueError(
        f"Short straddle preset supports ≤12h (got {H:.1f}h). ..."
    )
```

**Replace with:**
```python
if H > 24:
    log.warning(
        f"[SHORT_STRADDLE] Long session: {H:.1f}h detected. "
        f"All scaled parameters are already at their max clamp values above 12h. "
        f"Verify settings before starting."
    )
```

**Change the lower bound** from `if H < 2` to `if H < 1.0`:
```python
if H < 1.0:
    raise ValueError(
        f"Short straddle requires ≥1h to expiry (got {H:.1f}h). "
        f"Below 1h, gamma risk dominates and theta is insufficient."
    )
```

---

### CHANGE 2-C: Max Rolls — Required Field, No Preset Default (mmm_dte_presets.py + mmm_api.py)

**In `build_short_straddle_preset()`:**
Remove or comment out `'straddle_roll_max_per_session': 3` from the returned dict.
Add a comment: `# straddle_roll_max_per_session: NOT SET — operator must provide at session creation.`

**In `mmm_api.py`**, find the session creation endpoint (likely `POST /session` or similar).
Add this validation block AFTER params are merged but BEFORE the session is created:

```python
# SHORT_STRADDLE requires explicit operator choices for critical params
raw_body = request.get_json() or {}
if merged_params.get('_preset_source') == 'SHORT_STRADDLE':
    if 'initial_lots' not in raw_body or raw_body.get('initial_lots', 0) < 1:
        return jsonify({
            'error': (
                'SHORT_STRADDLE requires explicit initial_lots in request body. '
                'The preset default of 1 lot is not appropriate for real trading. '
                'Example: "initial_lots": 11'
            )
        }), 400
    if 'straddle_roll_max_per_session' not in raw_body:
        return jsonify({
            'error': (
                'SHORT_STRADDLE requires explicit straddle_roll_max_per_session. '
                'Set to 0 for pure theta mode (no rolls), or 1+ for rolling. '
                'Example: "straddle_roll_max_per_session": 3'
            )
        }), 400
```

---

### CHANGE 2-D: Soften IV Spike Gate from Hard Block to Warning (mmm_straddle_roll.py)

**Location:** Gate 5.5 in `check_straddle_roll_gates()`. Find the block ending with `return False, 'iv_spike', {}`.

**Replace** the `return False, 'iv_spike', {}` with:
```python
log.warning(
    f"[{sid}] IV spike noted (current={current_iv:.1f} > "
    f"{entry_iv:.1f} × {straddle_roll_iv_spike_mult}) "
    f"— proceeding with roll. High IV = higher new premium. "
    f"Margin gate (Gate 5) is the real protection."
)
session['_straddle_last_roll_iv_spike'] = True  # audit trail
# Do NOT block — fall through to remaining gates
```

**Critical:** This MUST be inside the existing `if entry_iv > 0 and current_iv > entry_iv * straddle_roll_iv_spike_mult:` block. Only replace the `return` statement inside it. Keep the outer `if` condition intact.

---

### PHASE 2 VERIFICATION

1. Run sealed tests — still ≥ 1312 passing.
2. Manually verify: calling `build_short_straddle_preset(24.0)` raises no error and returns a valid dict.
3. Verify: calling `build_short_straddle_preset(0.5)` raises ValueError.
4. Stop. Report results. Wait for audit before Phase 3.

---

## PHASE 3 — Post-Roll State + Robustness

### CHANGE 3-A: Post-Roll Clean State Reset (mmm_straddle_roll.py)

**Location:** `_execute_straddle_roll_inner()`, Step 6 "Update roll tracking state". Add AFTER the trigger_pts update from CHANGE 1-D, BEFORE the event log:

```python
# ── Post-roll clean reset — new straddle starts from neutral state ────────
# Regime state is stale (reflects the move that caused the roll — now accepted).
session.pop('_regime_trend', None)
session.pop('_regime_tier', None)
session['_regime_spot_price'] = spot
session['_regime_consecutive_dir'] = 0
session['_whipsaw_score'] = 0
session.pop('_reversal_cooldown_until', None)

# Entry IV — will be lazily re-captured on next heartbeat for the new straddle.
# Without this clear, Gate 5.5 compares against old calm-market IV forever.
session.pop('_straddle_entry_iv', None)

# Adaptive heartbeat — reset to base interval. Old straddle may have widened
# to 600s interval; new ATM straddle needs attentive 120s monitoring.
session['_adaptive_current_interval'] = params.get('adjustment_interval', 120)

# Trigger snapshot — new ATM fill prices are the baseline for UI gauges.
session['trigger_snapshot'] = {
    'ce': float(ce_fill_price_dec),
    'pe': float(pe_fill_price_dec),
}
```

**Do NOT add resets for:** `_straddle_initial_credit`, `_straddle_roll_count`, `_straddle_cumulative_credit`, `max_loss_amount`, `realized_pnl`, `unrealized_pnl`.

---

### CHANGE 3-B: Same-Strike Roll Guard (mmm_straddle_roll.py)

**Location:** In `_execute_straddle_roll_inner()`, AFTER the `roll_preview` is validated and `new_atm_strike` is confirmed valid (after the existing ATM strike check, around line 390-410), and BEFORE Step 2 (close ITM leg).

Add:
```python
# ── Same-strike guard: don't roll if new ATM == old ATM ──────────────────
# BTC may move enough to trigger but not enough to cross to the next strike.
# Rolling at the same strike pays 4 legs of fees for zero repositioning benefit.
if new_atm_strike == current_atm_strike:
    log.info(
        f"[{sid}] Roll skipped: new ATM {new_atm_strike:.0f} == old ATM "
        f"(spot={spot:.0f}, dist={distance_pct:.2f}%) — "
        f"spot didn't cross a strike boundary"
    )
    return False
```

---

### CHANGE 3-C: Re-Fetch ATM After Closing Both Legs (mmm_straddle_roll.py)

**Location:** In `_execute_straddle_roll_inner()`, find where Step 3 (OTM leg close) ends and Step 4 (CE re-entry) begins. The Step 3 success comment reads: `# SUCCESS: Both legs closed — update breadcrumb (CRITICAL FIX C-3)`.

Add this block AFTER the breadcrumb update, BEFORE Step 4:

```python
# ── Re-fetch ATM after closes — market may have moved during 4-leg execution ──
# If BTC moved significantly during the 1-3 seconds of sequential closes,
# the preview ATM may no longer be ATM. Re-fetch only if move > 25% of trigger.
try:
    _fresh_spot = await monitor._fetch_spot_price()
    if _fresh_spot and _fresh_spot > 0:
        _move_during_close = abs(_fresh_spot - spot)
        _refetch_threshold = trigger_pts * 0.25 if trigger_pts > 0 else 100
        if _move_during_close > _refetch_threshold:
            log.info(
                f"[{sid}] Spot moved {_move_during_close:.0f}pts during close execution "
                f"— re-fetching ATM preview"
            )
            _fresh_preview = monitor.initializer.preview_atm_straddle(expiry)
            if _fresh_preview and _fresh_preview.get('success'):
                _fresh_atm = _fresh_preview.get('atm_strike', 0)
                if _fresh_atm and _fresh_atm > 0:
                    new_atm_strike = _fresh_atm
                    new_ce_premium = _fresh_preview.get('ce', {}).get('mid_price', new_ce_premium)
                    new_pe_premium = _fresh_preview.get('pe', {}).get('mid_price', new_pe_premium)
                    spot = _fresh_spot
                    log.info(f"[{sid}] ATM re-fetched: {new_atm_strike:.0f} (spot={spot:.0f})")
except Exception as _refetch_err:
    log.debug(f"[{sid}] ATM re-fetch skipped: {_refetch_err}")
    # Continue with original preview data — not critical
```

---

### CHANGE 3-D: Spread Check Before Roll Re-Entry (mmm_straddle_roll.py)

**Location:** In `_execute_straddle_roll_inner()`, in the Gate 9 validation block where `new_ce_premium` and `new_pe_premium` are extracted from `roll_preview`. Find this block and add immediately after the premium validation:

```python
# ── Spread check — don't roll into a wide-market fill ────────────────────
_max_spread_pct = params.get('straddle_roll_max_spread_pct', 15.0)
_ce_bid = roll_preview.get('ce', {}).get('bid', 0)
_ce_ask = roll_preview.get('ce', {}).get('ask', 0)
_pe_bid = roll_preview.get('pe', {}).get('bid', 0)
_pe_ask = roll_preview.get('pe', {}).get('ask', 0)
_ce_spread_pct = ((_ce_ask - _ce_bid) / _ce_bid * 100) if _ce_bid > 0 else 999
_pe_spread_pct = ((_pe_ask - _pe_bid) / _pe_bid * 100) if _pe_bid > 0 else 999
if _ce_spread_pct > _max_spread_pct or _pe_spread_pct > _max_spread_pct:
    log.warning(
        f"[{sid}] Roll blocked: bid-ask spread too wide "
        f"(CE={_ce_spread_pct:.1f}%, PE={_pe_spread_pct:.1f}% "
        f"> max={_max_spread_pct:.0f}%) — skipping roll"
    )
    return False
```

Add `'straddle_roll_max_spread_pct': 15.0` to `mmm_state.py` DEFAULT_PARAMS and MUTABLE_PARAMS, and to `build_short_straddle_preset()` return dict.

---

### CHANGE 3-E: Telegram Alerts (mmm_straddle_roll.py + mmm_monitor.py)

**On successful roll** — in Step 8 of `_execute_straddle_roll_inner()`, AFTER `log_activity(...)`, add:

```python
# Telegram: notify operator of successful roll (significant market event)
try:
    from .mmm_telegram import send_telegram_alert
    _new_trigger_pts = session.get('_straddle_roll_trigger_pts', 0)
    send_telegram_alert(
        f"🔄 Straddle Roll #{roll_count+1}: {old_atm_strike:.0f}→{new_atm_strike:.0f}\n"
        f"Spot: {spot:.0f} | Moved: {distance_pct:.2f}%\n"
        f"New credit: ${new_roll_credit:.3f} | Next trigger: ±{_new_trigger_pts:.0f}pts",
        level='info',
        session_id=sid,
    )
except Exception:
    pass  # fire-and-forget: Telegram failure must never crash the roll
```

**On startup half-roll detected** — in `mmm_monitor.py`, find the `MMMMonitor.__init__` block that checks `_straddle_half_roll_state`. It already logs CRITICAL and calls `log_activity`. Add a Telegram call AFTER those existing calls:

```python
# Add after the existing log.critical + log_activity block for half-roll
try:
    from .mmm_telegram import send_telegram_alert
    send_telegram_alert(
        f"🚨 HALF-ROLL DETECTED ON STARTUP\n"
        f"Session: {self.session_id}\n"
        f"State: {half_roll_state}\n"
        f"Session BLOCKED — manual recovery required.\n"
        f"Check open positions on exchange before proceeding.",
        level='critical',
        session_id=self.session_id,
    )
except Exception:
    pass
```

**Verify:** Check how `send_telegram_alert` is called elsewhere in the codebase to confirm the signature. Do not guess — read an existing call site first.

---

### CHANGE 3-F: Hard Stop Verification (mmm_monitor.py — READ-ONLY CHECK)

**No code change required.** Verify that the existing hard stop path calls `emergency=True`:

Find line ~2166 in `mmm_monitor.py`:
```python
await self._auto_close_all(reason, emergency=True)
```

This is already correct. `emergency=True` uses `emergency_execute` in `mmm_executor.py` which places taker IOC orders (parallel, not sequential). Confirm this line exists and is unmodified.

**However:** Check the HALF-ROLL failure paths in `mmm_straddle_roll.py`. When a half-roll occurs (ITM closed, OTM close failed), the code sets `session['strategy_status'] = 'STOPPED'` and returns `False`. The naked CE position is NOT auto-closed — it requires manual operator action. This is the current design (halt and alert, not close). The Telegram from CHANGE 3-E partially addresses this. Document in a code comment that manual close is required on half-roll.

---

### PHASE 3 VERIFICATION

1. Run sealed tests — ≥ 1312 passing.
2. Verify trigger_pts is updated after roll in `_straddle_roll_trigger_pts` (check Step 6 output).
3. Stop. Report results. Wait for audit before Phase 4.

---

## PHASE 4 — UI Updates (mmm_dashboard.js)

### CHANGE 4-A: Show Trigger in Points on Roll Badge

**Location:** `MMMDashboard.js`, find the roll badge section (around line 2405–2421, search `_straddle_roll_count`).

**Current tooltip/label** shows roll count and last roll time.

**Change 1:** In the roll chip label, add trigger display:
```jsx
label={`🔄 Rolls: ${session._straddle_roll_count}/${session.params?.straddle_roll_max_per_session ?? '?'}`}
```
(Replace the hardcoded `|| 3` with `?? '?'` since max_rolls is now operator-required, not preset default.)

**Change 2:** In the Tooltip title for the roll badge, show trigger info:
```jsx
<Tooltip title={
  <>
    {session._straddle_last_roll_at
      ? `Last roll: ${new Date(session._straddle_last_roll_at).toLocaleTimeString()}`
      : 'No roll yet'
    }
    {session._straddle_roll_trigger_pts > 0 && (
      ` | Next trigger: ±${Math.round(session._straddle_roll_trigger_pts)} pts`
    )}
    {' • Hot-reloadable: change max_per_session in settings to add more rolls'}
  </>
}>
```

**Change 3:** In the straddle roll info tooltip (around line 1014), update the description text from `"spot moves ≥ trigger %"` to `"spot moves ≥ CE+PE entry premium pts"`.

**Change 4:** Add a price guard indicator — find the session card area and add near the roll badge:
```jsx
{session.params?._preset_source === 'SHORT_STRADDLE' &&
  session.params?.price_guard_enabled &&
  session.strategy_status === 'RUNNING' && (
    <Chip
      label="⚡ Guard"
      size="small"
      sx={{
        fontSize: '0.65rem',
        bgcolor: 'rgba(76,175,80,0.15)',
        color: '#66bb6a',
        fontFamily: 'monospace',
      }}
    />
  )
}
```

---

### PHASE 4 VERIFICATION

1. Run `cd webui/frontend && npm run build` and verify zero build errors.
2. Verify roll badge shows `?` for max_rolls instead of hardcoded `3`.
3. Stop. Report complete implementation. Wait for full audit.

---

## TESTING REQUIREMENTS

After all phases, add these sealed tests in a new file:
`webui/backend/routes/mmm/tests/test_sealed_straddle_roll_rev3.py`

Test stubs (implement each as a proper pytest function):

```python
def test_trigger_pts_computed_at_startup():
    """_straddle_roll_trigger_pts = lot-weighted CE_avg + PE_avg from positions."""

def test_gate8_fires_at_premium_distance():
    """Gate 8 passes when spot_move_pts == trigger_pts."""

def test_gate8_blocks_before_premium_distance():
    """Gate 8 returns distance_below_trigger when spot_move_pts < trigger_pts."""

def test_trigger_pts_updated_after_roll():
    """_straddle_roll_trigger_pts is updated to new fill prices after roll."""

def test_trigger_pts_fallback_from_positions():
    """Fallback: when key missing, recomputes from active position entry_premium."""

def test_trigger_pts_pct_fallback_when_no_entry_premium():
    """Last-resort fallback uses straddle_roll_trigger_pct × spot."""

def test_gate8_blocks_on_no_trigger_pts():
    """Gate 8 returns no_trigger_pts when all fallbacks fail."""

def test_gate7_emergency_bypass_uses_points():
    """Emergency bypass triggers at trigger_pts × emergency_mult, not pct."""

def test_wind_down_disabled_does_not_block_roll():
    """Roll proceeds normally when wind_down_enabled=False (Gate 3 never fires)."""

def test_hard_stop_uses_emergency_true():
    """_auto_close_all is called with emergency=True on max_loss breach (verify call site)."""

def test_same_strike_guard_blocks_roll():
    """Roll returns False when new_atm_strike == current_atm_strike."""

def test_spread_gate_blocks_wide_market():
    """Roll blocked when CE or PE spread > straddle_roll_max_spread_pct."""

def test_spread_gate_allows_normal_market():
    """Roll proceeds when CE and PE spread < straddle_roll_max_spread_pct."""

def test_iv_spike_does_not_block_roll():
    """Gate 5.5 IV spike logs warning but does not return False."""

def test_post_roll_regime_state_cleared():
    """After successful roll: _regime_trend, _regime_tier, _whipsaw_score are cleared."""

def test_post_roll_entry_iv_cleared():
    """After successful roll: _straddle_entry_iv is popped."""

def test_post_roll_initial_credit_preserved():
    """After successful roll: _straddle_initial_credit is NOT changed."""

def test_session_duration_above_12h_allowed():
    """build_short_straddle_preset(24.0) does not raise ValueError."""

def test_session_duration_below_1h_blocked():
    """build_short_straddle_preset(0.5) raises ValueError."""

def test_max_rolls_hot_reload():
    """Raising straddle_roll_max_per_session clears _straddle_roll_blocked in Gate 6."""

def test_session_creation_rejects_missing_initial_lots():
    """POST /session with SHORT_STRADDLE and no initial_lots returns HTTP 400."""

def test_session_creation_rejects_missing_max_rolls():
    """POST /session with SHORT_STRADDLE and no straddle_roll_max_per_session returns HTTP 400."""

def test_price_guard_fires_near_trigger():
    """_price_guard_loop calls force_heartbeat when spot approaches trigger."""

def test_price_guard_respects_cooldown():
    """_price_guard_loop does not fire again within cooldown_secs after firing."""

def test_price_guard_skips_stale_ws_data():
    """_price_guard_loop does nothing when WS data age > 30 seconds."""
```

---

## IMPLEMENTATION RULES (read again before starting)

1. **One change at a time.** Complete and test each CHANGE before moving to the next.
2. **Read before editing.** For every file you touch, read the relevant function first.
3. **No unrequested changes.** If you see something unrelated that looks wrong, note it in your report but do not fix it.
4. **No new files** except the test file in Phase 4 testing.
5. **No renames or refactors.** Add code, don't restructure existing code.
6. **Backward-compatible parameters only.** All new params have safe defaults. Existing sessions without new keys must behave identically to today.
7. **Preserve all existing comments.** Especially `# CRITICAL FIX C-1`, `# CRITICAL FIX C-2`, `# CRITICAL FIX C-3`, `# HIGH-RISK FIX H-1`, `# HIGH-RISK FIX H-2` in `mmm_straddle_roll.py` — these document known fixes. Do not remove them.
8. **Sealed function rule.** `check_straddle_roll_gates()` is `@sealed`. Any behavioral change to it requires a new sealed test before deployment.
9. **Gate numbering.** Do not renumber existing gates. If you add a new gate-like check, document it inline but do not call it "Gate N" (all gate numbers are taken).
10. **Stop at phase boundaries.** Do not cascade phases. Audit happens between phases.

---

## REPORTING FORMAT

After each phase, report in this format:

```
PHASE N COMPLETE

Files changed:
- file_path: description of change (lines X-Y)

Tests run: N passed, 0 failed
Sealed test count: N (was 1312)

Issues found (if any):
- [describe anything unexpected encountered]

Ready for audit: YES/NO
```
