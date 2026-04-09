# Straddle Roll Fix Plan — Rev 3.0
**Created: 2026-04-09**
**Rev 1.0 → 2.0: Quant audit (12 issues found and addressed)**
**Rev 2.0 → 3.0: Architecture overhaul — real-time price guard, market orders on hard stop,
                  wind-down disabled, duration cap removed, hot-reloadable roll limit**
**Author: Claude Code + physicsssr**
**Status: PLANNING — no code written yet**

---

## 0. Executive Summary

The Short Straddle with Roll is being simplified to its essential form: **sell ATM straddle → monitor in real-time → roll when market moves by collected premium → hard stop if loss exceeds limit → close at expiry.**

Nothing else. No wind-down. No harvest. No regime-gated adjustments. No 12-hour cap.

Four classes of change:
1. **P0 Bug** — roll trigger is percentage-based, must be premium-points-based
2. **Architecture** — heartbeat is too slow; add a real-time price guard (5-second checks) using the existing Delta WebSocket feed
3. **Safety** — hard stop must fire market orders (taker), not limit orders
4. **Simplification** — disable wind-down, harvest, duration cap; make roll count operator-controlled and hot-reloadable

**Isolation guarantee:** Every change is behind `_preset_source == 'SHORT_STRADDLE'` or in `mmm_straddle_roll.py`. The regular production strangle (0DTE, 5DTE, SHORT_WINDOW) has zero overlap.

---

## 1. What's Wrong — Ordered by Severity

### 1.1 (P0 — Trading-Breaking) Trigger Is Percentage, Not Premium-Points

**Current:** `roll when abs(spot - atm_strike) / atm_strike >= 0.65%`
At BTC 85,000 → roll fires at 552 pts of movement. If collected 400 pts premium, you're already 152 pts past breakeven — the straddle is losing money before the roll even starts.

**Correct:** `roll when abs(spot - atm_strike) >= CE_entry_premium + PE_entry_premium`
At CE=250, PE=150 → trigger_pts=400. Roll fires exactly at the financial breakeven of the straddle seller.

**Quant note (Rev 2.0):** Due to gamma convexity, the actual old-straddle P&L at the trigger is approximately -2% to -5% of original premium (gamma makes the ITM leg cost slightly more than intrinsic). This is a ~$0.08–$0.20 drag per roll, dramatically better than the current -38% to -55% drag from the percentage trigger.

### 1.2 (P1) Heartbeat Is Too Slow for a High-Risk Short Position

The heartbeat runs every 120 seconds. If BTC moves 400 points in 90 seconds (possible in a volatile session), the system doesn't react for up to 2 minutes. The roll fires 2 minutes late = 2 minutes of extra loss accumulation.

Worse: if BTC drops 1,000 points in 3 minutes and the hard stop should fire, you might only get one heartbeat during that entire crash — the market order needs to execute at the START of the crash, not 2 minutes into it.

### 1.3 (P1) Hard Stop Uses Limit Orders — Wrong for Emergency Close

The `close_position()` function places limit orders at mid-price. In a fast market:
- Bid-ask spread widens to 30-50%
- Mid-price is stale within seconds
- Limit order at mid-price doesn't fill — the ask has moved past it

In a max_loss scenario, the operator's capital protection requires a **market order** that fills immediately at whatever price the exchange offers. Speed is the only metric that matters.

### 1.4 (P1) Wind-Down Is Counterproductive for a Straddle

Wind-down closes positions when premium decays to X% of original. For a straddle:
- If BTC is at ATM and both legs are decaying, wind-down might close the profitable (OTM) leg
- This destroys the straddle structure — you'd have only the losing leg
- The roll already handles repositioning. The hard stop already handles catastrophe. Wind-down is a third mechanism solving a problem that doesn't exist for this strategy.

### 1.5 (P2) Session Duration Capped at 12 Hours Artificially

`build_short_straddle_preset()` raises a `ValueError` for H > 12. On low-volatility weekends, operators want to run a straddle for an entire Saturday (24h+). All scaled parameters already have max clamps — the cap is unnecessary.

### 1.6 (P2) Max Rolls Is a Fixed Preset Default, Not Operator-Controlled

Currently defaulting to 3. Should be operator-configured at session creation with no preset opinion. Also: hot-reload must be explicitly documented (the mechanism already exists in Gate 6 but the documentation and UI don't make it visible).

### 1.7 (P2) Trigger Doesn't Update After Each Roll

After Roll #1, new premiums collected are CE=230 + PE=170 = 400 pts new trigger. But `straddle_roll_trigger_pct` still uses the original percentage. The next roll fires at the wrong distance relative to the new premium.

---

## 2. Strategy Philosophy — The Simplified Decision Tree

After all fixes, the complete strategy logic is:

```
════════════════════════════════════════════════════════
 EVERY 5 SECONDS — Price Guard (reads WS, no API calls)
════════════════════════════════════════════════════════
 ┌─ Is spot within [safety_buffer] pts of roll trigger?
 │   YES → Fire force_heartbeat immediately
 └─ Is estimated loss ≥ 85% of max_loss?
     YES → Fire force_heartbeat immediately
 
════════════════════════════════════════════════════════
 EVERY 120s (or immediately when Price Guard fires)
════════════════════════════════════════════════════════

 STEP 1 — HARD STOP (checked before anything else)
   Is total P&L loss ≥ max_loss_amount?
   → YES: Close ALL positions with MARKET ORDER immediately
          STOP session. Telegram CRITICAL. Done. No re-entry ever.

 STEP 2 — EXPIRY GUARD
   Is time_to_expiry < 10 min?
   → YES: Close all positions at limit. Stop. Done.
   Is time_to_expiry < 90 min?
   → YES: Skip roll evaluation. Hold.

 STEP 3 — THE ROLL
   Has spot moved ≥ _straddle_roll_trigger_pts from ATM?
   → NO: Do nothing. Theta is working.
   → YES: Run all gates (margin, cooldown, spread, same-strike, etc.)
          Execute 4-leg roll with LIMIT orders.
          Update trigger to new CE_fill + PE_fill.
          Reset regime/IV/interval state.
          Telegram: "Roll #N fired."

 OTHERWISE → nothing. Wait for next check.
════════════════════════════════════════════════════════
```

That's the entire strategy. No wind-down. No harvest. No regime-gated adjustments.

---

## 3. Isolation Boundary — Files Not Touched

| Component | Reason Safe |
|-----------|-------------|
| `mmm_engine.py` | Core strangle P&L formulas |
| `mmm_constants.py` | LOT_SIZE_BTC |
| `mmm_wind_down.py` | Module stays — just disabled in preset |
| `mmm_trigger.py` | Strangle-specific trigger logic |
| `mmm_replenish.py` | Strangle-specific, N/A for straddle |
| `mmm_regime.py` | Strangle uses this; straddle resets it post-roll |
| `mmm_guardian.py` | G1–G5 unchanged |
| `mmm_fill_sync.py` | Unchanged |
| `mmm_pnl_core.py` | P&L formulas unchanged |
| `mmm_heartbeat_health.py` | Unchanged |
| All sealed test files | 1312 baseline must hold |

---

## 4. Fix Plan

---

### FIX-1 (P0): Replace Percentage Trigger with Premium-Points Trigger

**Files:** `mmm_straddle_roll.py`, `mmm_monitor.py` (startup init block)

#### 4.1.1 New session key: `_straddle_roll_trigger_pts`

Computed once at session startup (in the straddle init block in `mmm_monitor.py`):
```
For each active position on each side:
  ce_avg_premium = weighted_avg(pos.entry_premium, pos.lots) across all active CE positions
  pe_avg_premium = weighted_avg(pos.entry_premium, pos.lots) across all active PE positions
  _straddle_roll_trigger_pts = ce_avg_premium + pe_avg_premium
```

Updated after every successful roll (in Step 6 of `_execute_straddle_roll_inner`):
```
_straddle_roll_trigger_pts = result_ce.fill_price + result_pe.fill_price
(actual fill prices from the new ATM sell — not mid-price estimate)
```

The fallback chain for Gate 8 when this key is missing (legacy sessions or hot-reload):
1. Compute live from current active positions (same formula as startup)
2. If still zero (no entry_premium on positions), fall back to `straddle_roll_trigger_pct% × spot`
3. If still zero: return `'no_trigger_pts'` and block roll

#### 4.1.2 Gate 8 replacement

Remove `distance_pct < straddle_roll_trigger_pct` check.
Replace with:
```
spot_move_pts = abs(spot - current_atm_strike)
if spot_move_pts < trigger_pts:
    return False, f'distance_below_trigger ({spot_move_pts:.0f} < {trigger_pts:.0f} pts)', {}
```

#### 4.1.3 Emergency bypass rewritten to points

```
emergency_bypass = spot_move_pts >= trigger_pts * straddle_roll_emergency_mult
```
`straddle_roll_emergency_mult` default = 2.0 means: if spot has moved 2× the trigger distance, bypass cooldown regardless. Same semantics, now in points not percent.

#### 4.1.4 `straddle_roll_trigger_pct` — kept as last-resort fallback only

Remains in `mmm_state.py` defaults. Never the primary path after this fix. Not shown prominently in UI.

#### 4.1.5 Add missing DEFAULT_PARAMS entry

Add to `mmm_state.py`:
```python
'straddle_roll_price_max_age_secs': 5,   # currently hardcoded in Gate 9
```

---

### FIX-2 (ARCH): Real-Time Price Guard

**Files:** `mmm_monitor.py`

**What exists that we use:**
- `delta_price_websocket.py` — already running as a background subprocess, already has `prices['BTC']` updated in real-time via WebSocket. Zero API calls to read it.
- `monitor.force_heartbeat()` — already exists, interrupts the heartbeat wait within 500ms.
- `_wait_for_next_heartbeat()` — already polls at 500ms intervals for exactly this kind of interruption.

**What we add:**
A `_price_guard_loop()` async coroutine spawned inside `_run_loop()` for SHORT_STRADDLE sessions only.

**Behaviour:**
```
Every 5 seconds:
  1. Read current_spot from get_price_websocket().prices.get('BTC', 0)
     If data age > 30 seconds (WS may be stale/disconnected): skip check, log warning
  
  2. Check ROLL APPROACH:
     spot_move = abs(current_spot - session['ce']['active_strike'])
     trigger_pts = session.get('_straddle_roll_trigger_pts', 0)
     safety_buffer = params.get('price_guard_buffer_pts', 50)
     if spot_move >= (trigger_pts - safety_buffer) and spot_move < trigger_pts * 2:
         → fire force_heartbeat()
  
  3. Check LOSS APPROACH:
     last_known_loss = session.get('_price_guard_last_loss_estimate', 0)
     if last_known_loss >= max_loss_amount * 0.85:
         → fire force_heartbeat()
  
  4. Rate limit: after any force_heartbeat(), wait 30 seconds before next check
     (prevents spamming during a fast trending move)
```

**How `_price_guard_last_loss_estimate` is maintained:**
Updated by the heartbeat at the end of each run (not by the price guard itself). The price guard reads it as a simple scalar — no lock needed because it only reads, never writes.

**Architecture principle:** The price guard detects, the heartbeat acts. The price guard never touches orders, never modifies session state. If the WebSocket is disconnected (stale data), the guard does nothing and the regular 120s heartbeat continues as normal fallback.

**New params:**
```python
'price_guard_enabled': True,           # master switch for SHORT_STRADDLE
'price_guard_interval_secs': 5,        # how often to check
'price_guard_buffer_pts': 50,          # how many pts before trigger to pre-alert
'price_guard_cooldown_secs': 30,       # minimum gap between force-heartbeat fires
```

**Result of this change:**
- Detection latency: 0–5 seconds (from BTC hitting threshold to force_heartbeat firing)
- Execution latency: 0–500ms (force_heartbeat → heartbeat loop starts)
- Order latency: 2–5 seconds (heartbeat API calls + order placement)
- Total: **~7–10 seconds** from BTC crossing trigger to roll executing

Versus current: **0–120 seconds** (average 60 seconds).

---

### FIX-3 (SAFETY): Hard Stop Uses Market Orders

**Files:** `mmm_close_at_5.py` (`close_position()`), `mmm_executor.py`, `mmm_monitor.py` (hard stop call sites)

**Context:** The hard stop is triggered inside `_auto_close_all()` in `mmm_monitor.py`. It calls `close_position()` for each active position. Currently this places a limit order at mid-price.

**Change:** Add `order_type: str = 'limit'` parameter to `close_position()`.

When called from the max_loss hard stop path: `close_position(..., order_type='market')`.
When called from normal roll execution: `close_position(...)` — limit, no change.

**Where `order_type='market'` applies (all SHORT_STRADDLE):**
1. `_auto_close_all()` when triggered by max_loss breach — always market
2. Half-roll emergency: OTM leg failed to close during a roll — always market (naked position risk)
3. Operator "Global Exit All" button — already has a force flag, extend to use market order

**Where limit orders remain (unchanged):**
1. Roll execution (Steps 2 and 3 in `_execute_straddle_roll_inner`) — limit, better fill
2. Wind-down closes — N/A (wind-down disabled for SHORT_STRADDLE)
3. Normal close_at_5 / auto_close — limit (not emergency, time allows better fill)

**In `mmm_executor.py`:** The executor builds the Delta Exchange API request. Add `order_type` to the order payload: `'order_type': 'market_order'` vs `'limit_order'`. Delta Exchange supports both.

**Why not always market:** Market orders on BTC options can have 0.5–2% slippage in normal conditions. For a 400-point premium position, that's $1.70 per lot wasted. Limit orders at mid-price save this in non-emergency scenarios. Only use market when time = money (hard stop, naked position emergency).

---

### FIX-4: Disable Wind-Down for SHORT_STRADDLE

**File:** `mmm_dte_presets.py` (`build_short_straddle_preset()`)

**Single change in the preset:**
```python
'wind_down_enabled': False,   # was True
```

**Why:**
- Wind-down closes the profitable (decaying) leg when premium falls below a threshold
- For a straddle, the decaying leg IS your hedge — closing it leaves you with only the losing leg
- The roll handles repositioning; the hard stop handles capital protection; auto_close_mins handles expiry exit
- Wind-down adds a fourth mechanism that solves no problem unique to the straddle

**What remains active (these are NOT wind-down):**
- `auto_close_mins: 10` — close all positions 10 minutes before expiry (clean exit mechanism, separate from wind-down)
- Hard stop — fires on max_loss regardless of wind-down setting

**No other changes needed.** Since `wind_down_enabled=False`, `is_wind_down_active()` always returns False. Gate 3 (which we were going to remove in Rev 2.0) can stay in `check_straddle_roll_gates()` — it will never trigger because wind-down is disabled. This is SIMPLER than removing the gate (fewer code changes, less risk of breaking the gate logic for other session types).

**Also disable harvest:**
```python
'harvest_enabled': False,   # was True
```
Harvest partially closes individual profitable lots when they've decayed enough. For a straddle, harvesting the OTM leg breaks the symmetric structure. Both legs must live and die together (close on roll or close on expiry).

---

### FIX-5: Remove 12-Hour Session Duration Cap

**File:** `mmm_dte_presets.py` (`build_short_straddle_preset()`)

**Remove:**
```python
if H > 12:
    raise ValueError(f"Short straddle preset supports ≤12h (got {H:.1f}h). ...")
```

**Replace with:**
```python
if H > 24:
    log.warning(f"[SHORT_STRADDLE] Long session: {H:.1f}h. "
                f"All scaled parameters hit max clamps above 12h. "
                f"Verify settings before starting.")
```

**Keep lower bound unchanged:** `if H < 1.0: raise ValueError(...)` — below 1 hour, gamma risk is extreme and theta is insufficient.

**Why safe to remove upper bound:**
All parameters are scaled as `clamp(H * factor, min_val, max_val)`. Above 12h, every scaled param is already at its max value. A 24h session and a 12h session produce identical parameter sets. The cap was protecting nothing.

**Use case this enables:** Saturday/Sunday low-volatility sessions where an operator wants to run the straddle for a full day (8 AM IST to next day 8 AM IST = ~24h). With weekly BTC options, sessions can be multiple days.

---

### FIX-6: Max Rolls — Operator-Controlled, Hot-Reloadable, No Default Opinion

**Files:** `mmm_dte_presets.py`, `mmm_state.py`, `MMMDashboard.js`

**Change in preset:** Remove the hardcoded default of 3 from `build_short_straddle_preset()`. The operator must explicitly provide this.

**Session creation validation (in `mmm_api.py`):**
```
If _preset_source == SHORT_STRADDLE and 'straddle_roll_max_per_session' not in raw_body:
    Return HTTP 400: "straddle_roll_max_per_session is required for SHORT_STRADDLE.
                      Set to 0 for hard-stop-only mode (no rolls), or 1-10 for rolling."
```

**Special value: 0** = hard stop only mode. No rolls ever. Operator wants pure theta decay with max_loss as the only exit before expiry.

**Hot-reloadable (already works, just needs documentation):**
Gate 6 in `check_straddle_roll_gates()` already auto-clears the block flag when the operator raises `max_per_session` mid-session:
```python
if roll_count < straddle_roll_max_per_session:
    session['_straddle_roll_blocked'] = False
    session['_straddle_roll_block_logged'] = False
```
If you're at 3/3 rolls exhausted and change to 5, the block clears on the next heartbeat. This is already working — no code change needed, only documentation and UI visibility.

**UI change (MMMDashboard.js):** Add the roll count chip tooltip: *"Hot-reloadable: change max_per_session in session settings to add more rolls mid-session."*

---

### FIX-7: Remove IV Spike Gate as Hard Block (Soften to Warning)

**File:** `mmm_straddle_roll.py` (Gate 5.5)

**Context:** Gate 5.5 blocks roll if current IV > 2× the entry IV (`_straddle_entry_iv`).

**Problem:** When BTC makes a large move (exactly when the roll trigger fires), IV spikes. High IV = high option premium = the new straddle will collect MORE premium. Blocking the roll when premium is high is counterproductive.

The original intent was to block rolling into a dangerous spike (crash + IV panic). But the margin gate (Gate 5) and loss abort (Gate 10) already handle that scenario.

**Change:** Convert Gate 5.5 from a hard block to a **soft warning** that logs and annotates the roll but does not block it:
```python
if entry_iv > 0 and current_iv > entry_iv * straddle_roll_iv_spike_mult:
    log.warning(f"[{sid}] IV spike detected ({current_iv:.1f} > {entry_iv:.1f} × "
                f"{straddle_roll_iv_spike_mult}×) — proceeding with roll, IV noted in audit")
    session['_straddle_last_roll_iv_spike'] = True  # audit flag
    # Do NOT return False — let roll proceed
```

This preserves the audit trail without blocking a legitimate repositioning action.

---

### FIX-8: Post-Roll Clean State Reset

**File:** `mmm_straddle_roll.py` (Step 6 of `_execute_straddle_roll_inner`)

After a successful roll, the session carries stale state from the old straddle. Reset:

```python
# Regime — new straddle starts at neutral
session.pop('_regime_trend', None)
session.pop('_regime_tier', None)
session['_regime_spot_price'] = spot
session['_regime_consecutive_dir'] = 0
session['_whipsaw_score'] = 0
session.pop('_reversal_cooldown_until', None)

# Entry IV — recaptured on next heartbeat for new straddle
session.pop('_straddle_entry_iv', None)

# Adaptive heartbeat — reset to base interval for attentive monitoring
session['_adaptive_current_interval'] = params.get('adjustment_interval', 120)

# Trigger snapshot — new ATM fill prices are the new baseline
session['trigger_snapshot'] = {
    'ce': result_ce.get('fill_price', 0),
    'pe': result_pe.get('fill_price', 0),
}
```

**Do NOT reset:**
- `_straddle_initial_credit` — full-session loss abort baseline (Gate 10)
- `_straddle_roll_count` — needed for max_rolls gate
- `_straddle_cumulative_credit` — analytics
- `max_loss_amount` — session-level safety net
- `realized_pnl` / `unrealized_pnl` — P&L accounting is continuous

---

### FIX-9: Same-Strike Roll Guard

**File:** `mmm_straddle_roll.py` (after Gate 9, before Step 2)

```python
if new_atm_strike == current_atm_strike:
    log.info(f"[{sid}] Roll skipped: new ATM == old ATM ({new_atm_strike}) "
             f"— spot movement didn't cross a strike boundary")
    return False
```

No positions touched, no cost. BTC needs to move past the next strike grid point before rolling is worthwhile.

---

### FIX-10: Re-Fetch ATM After Closing Both Legs

**File:** `mmm_straddle_roll.py` (between Step 3 and Step 4)

The 4-leg sequential close takes 1–3 seconds. If BTC keeps trending during close execution, the "new ATM" computed before closing may be stale. After both legs are closed, re-fetch spot and re-compute ATM if move > 25% of trigger:

```python
fresh_spot = await monitor._fetch_spot_price()
if fresh_spot and fresh_spot > 0:
    move_during_close = abs(fresh_spot - spot)
    if move_during_close > trigger_pts * 0.25:
        fresh_preview = monitor.initializer.preview_atm_straddle(expiry)
        if fresh_preview and fresh_preview.get('success'):
            new_atm_strike = fresh_preview.get('atm_strike', new_atm_strike)
            new_ce_premium = fresh_preview.get('ce', {}).get('mid_price', new_ce_premium)
            new_pe_premium = fresh_preview.get('pe', {}).get('mid_price', new_pe_premium)
            spot = fresh_spot
```

---

### FIX-11: Spread Check Before Roll Re-Entry

**File:** `mmm_straddle_roll.py` (Gate 9 inline)

```python
max_spread_pct = params.get('straddle_roll_max_spread_pct', 15.0)
ce_spread_pct = (ce_ask - ce_bid) / ce_bid * 100 if ce_bid > 0 else 999
pe_spread_pct = (pe_ask - pe_bid) / pe_bid * 100 if pe_bid > 0 else 999
if ce_spread_pct > max_spread_pct or pe_spread_pct > max_spread_pct:
    log.warning(f"[{sid}] Roll blocked: spread too wide "
                f"(CE {ce_spread_pct:.1f}%, PE {pe_spread_pct:.1f}% > {max_spread_pct}%)")
    return False
```

New params in `mmm_state.py` and preset: `straddle_roll_max_spread_pct: 15.0`

---

### FIX-12: Telegram on Successful Roll + Startup Half-Roll Alert

**File:** `mmm_straddle_roll.py` (Step 8), `mmm_monitor.py` (startup)

**On successful roll:** Fire Telegram INFO:
```
🔄 Roll #N: {old_atm}→{new_atm}
Spot: {spot} | Moved: {spot_move_pts:.0f}pts (trigger was {trigger_pts:.0f}pts)
New credit: ${new_roll_credit:.3f} | Next trigger: ±{new_trigger_pts:.0f}pts from {new_atm}
```

**On startup half-roll detected:** Fire Telegram CRITICAL:
```
🚨 HALF-ROLL ON STARTUP: {half_roll_state}
Session {sid} BLOCKED — manual recovery required.
Check open positions on exchange before doing anything.
```

---

### FIX-13: Session Creation Validation for SHORT_STRADDLE

**File:** `mmm_api.py`

Two required fields that must be explicitly set in the HTTP request body:
1. `initial_lots` — if absent or < 1: reject with HTTP 400
2. `straddle_roll_max_per_session` — if absent: reject with HTTP 400 (operator must choose)

Detection: check `'initial_lots' in raw_body` (not just the merged params) to distinguish "user explicitly sent 1" from "user forgot and got preset default 1".

---

### FIX-14: UI Updates

**File:** `MMMDashboard.js`

1. Roll badge: Show `±{trigger_pts} pts` instead of `trigger %`
2. Roll tooltip: Show full roll stats — old ATM, new ATM, trigger at time of roll, new trigger
3. Roll exhaustion: "Hot-reloadable: change max_per_session in settings to add more rolls"
4. Price guard status: Show "⚡ Price guard active" indicator on the session card when guard is running

---

## 5. New/Modified Parameters Summary

| Parameter | Default | Description | Hot-reloadable? |
|-----------|---------|-------------|-----------------|
| `price_guard_enabled` | `True` | Enable real-time price guard for SHORT_STRADDLE | Yes |
| `price_guard_interval_secs` | `5` | Price guard check interval | Yes |
| `price_guard_buffer_pts` | `50` | Force-HB when within N pts of trigger | Yes |
| `price_guard_cooldown_secs` | `30` | Min gap between force-HBs | Yes |
| `straddle_roll_max_per_session` | **REQUIRED** | No default — operator must set | Yes (Gate 6 auto-clears) |
| `straddle_roll_max_spread_pct` | `15.0` | Max bid-ask spread allowed on re-entry | Yes |
| `straddle_roll_price_max_age_secs` | `5` | ATM preview max age (was hardcoded) | Yes |
| `wind_down_enabled` | `False` | Disabled for SHORT_STRADDLE | No |
| `harvest_enabled` | `False` | Disabled for SHORT_STRADDLE | No |

---

## 6. Implementation Order

```
Phase 1 — Fix the Fatal Bug + Safety (must complete before any real trade)
  FIX-1:  Premium-points trigger (P0)              ← DO FIRST
  FIX-3:  Hard stop uses market orders (SAFETY)    ← DO SECOND
  FIX-2:  Real-time price guard (ARCH)             ← DO THIRD (builds on FIX-1)

Phase 2 — Simplification (remove unnecessary features)
  FIX-4:  Disable wind-down and harvest in preset  ← independent
  FIX-5:  Remove 12h duration cap                  ← independent
  FIX-6:  Max rolls operator-controlled            ← independent
  FIX-7:  Soften IV spike gate to warning          ← independent

Phase 3 — Post-Roll State + Robustness
  FIX-8:  Post-roll clean state reset              ← after FIX-1
  FIX-9:  Same-strike roll guard                   ← independent
  FIX-10: Re-fetch ATM after closes                ← independent
  FIX-11: Spread check                             ← independent
  FIX-12: Telegram alerts                          ← after FIX-1 (needs trigger_pts)

Phase 4 — Operations
  FIX-13: Session creation validation              ← after FIX-6 (requires required fields)
  FIX-14: UI updates                               ← after FIX-1 (needs trigger_pts in session)

Testing:
  After Phase 1: All 1312 sealed tests pass
  After Phase 2: Paper session with 1 lot, observe roll and stop behaviour
  After Phase 3: Simulate fast crash scenario (manual force-heartbeat with mock spot)
  After Phase 4: Full end-to-end live test at minimum lots before real size
```

---

## 7. Files Changed

| File | What Changes | Strangle affected? |
|------|-------------|-------------------|
| `mmm_straddle_roll.py` | Gate 8 (trigger pts), Gate 5.5 (soften), FIX-9/10/11/12, post-roll reset | No |
| `mmm_monitor.py` | Price guard coroutine, trigger_pts init, market-order call on hard stop, startup half-roll Telegram | No — all gated on SHORT_STRADDLE |
| `mmm_executor.py` | `order_type` parameter pass-through for market/limit | Strangle never calls with market — backward-compatible |
| `mmm_close_at_5.py` | `close_position()` gains `order_type='limit'` default param | Backward-compatible |
| `mmm_dte_presets.py` | Remove 12h cap, disable wind_down+harvest, remove hardcoded max_rolls, add price guard params | Only SHORT_STRADDLE preset changed |
| `mmm_state.py` | Add: `price_guard_*` params, `straddle_roll_max_spread_pct`, `straddle_roll_price_max_age_secs` | New params with safe defaults |
| `mmm_api.py` | Session creation validation (initial_lots + max_rolls required) | No — gated on SHORT_STRADDLE |
| `MMMDashboard.js` | Trigger display in points, price guard badge, roll tooltip, hot-reload hint | No — display only |

**Files NOT changed:** `mmm_engine.py`, `mmm_constants.py`, `mmm_wind_down.py`, `mmm_trigger.py`, `mmm_replenish.py`, `mmm_regime.py`, `mmm_guardian.py`, `mmm_fill_sync.py`, `mmm_pnl_core.py`, all test files.

---

## 8. New Sealed Tests Required

| Test | What it verifies |
|------|-----------------|
| `test_trigger_pts_initial_computation` | `_straddle_roll_trigger_pts` = CE_avg + PE_avg on startup |
| `test_trigger_pts_fires_at_premium_distance` | Gate 8 passes when spot_move == trigger_pts |
| `test_trigger_pts_does_not_fire_early` | Gate 8 blocks when spot_move < trigger_pts |
| `test_trigger_pts_updated_after_roll` | Key reflects new fill prices after roll completes |
| `test_trigger_pts_fallback_chain` | Fallback: live positions → pct_fallback → block |
| `test_wind_down_does_not_affect_straddle` | Roll proceeds when `wind_down_enabled=False` |
| `test_hard_stop_uses_market_order` | `close_position` called with `order_type='market'` when max_loss fires |
| `test_normal_roll_uses_limit_order` | Roll close uses default limit order |
| `test_same_strike_guard` | Roll blocked when new_atm == old_atm |
| `test_spread_gate_blocks_wide_market` | Roll blocked when spread > max_spread_pct |
| `test_iv_spike_does_not_block_roll` | IV spike only logs warning, does not block |
| `test_post_roll_regime_reset` | Regime keys cleared after successful roll |
| `test_price_guard_fires_force_heartbeat` | Guard calls force_heartbeat() when spot approaches trigger |
| `test_price_guard_respects_cooldown` | Guard doesn't spam after firing |
| `test_session_creation_requires_initial_lots` | HTTP 400 when initial_lots absent for SHORT_STRADDLE |
| `test_session_creation_requires_max_rolls` | HTTP 400 when max_rolls absent for SHORT_STRADDLE |
| `test_max_rolls_hot_reload` | Raising max_rolls mid-session clears block on next heartbeat |
| `test_duration_above_12h_allowed` | No error for H=24 session |

---

## 9. Pre-Trade Checklist (After All Phases Complete)

- [ ] Dashboard shows `±N pts` trigger, not `trigger %`
- [ ] Price guard badge visible on session card
- [ ] Create 1-lot test session → verify `initial_lots` validation fires if absent
- [ ] Verify `straddle_roll_max_per_session` validation fires if absent
- [ ] Paper session: observe roll fires within 10 seconds of trigger crossing
- [ ] Paper session: verify post-roll trigger updates to new_CE + new_PE
- [ ] Simulate crash: verify hard stop fires market order (check executor logs)
- [ ] Verify 24h session creation works without error
- [ ] All 1312+ sealed tests pass
- [ ] Git diff confirms zero changes to strangle-serving files
