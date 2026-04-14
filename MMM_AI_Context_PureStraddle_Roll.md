# AI Context — Pure Short Straddle Roll (STRADDLE_ROLL)

**Single source of truth for strategy logic:** `tasks/STRADDLE_ROLL_FIX_PLAN.md`
**Status:** Live and shipping as of 2026-04-10
**Author:** physicsssr + Claude Code

---

## 1. What This Strategy Is

**Pure Short Straddle Roll** = sell ATM straddle → hold for theta → roll when spot moves by collected premium → hard stop if max loss hit → close at expiry.

**That is the entire strategy.** Nothing else runs between rolls.

The MMM adjustment engine is physically present in the codebase but is **never called** for this strategy. It is isolated by two independent guards (see §5).

---

## 2. What This Strategy Is NOT

This strategy **does not use** and **must never inherit** the following MMM strangle mechanisms:
- Trigger & adjustment engine (`_process_adjustment`)
- Strike shift logic
- Wind-down mode
- Profit harvesting (M1)
- Lot recycling (M2)
- Balance control / asymmetry rebalancing (M3)
- ATM Shield
- Regime controls (vol/gamma/trend)
- Perp delta hedge
- Consecutive direction limiter
- Auto-replenish leg
- Whipsaw guard / ITM guard
- Adaptive tuning
- Lot velocity limiter
- Breakeven engine
- Close-at-5 watcher
- Reverse mode

**If you are about to add any of the above to a STRADDLE_ROLL session, stop. It is wrong.**

---

## 3. Strategy Identity

| Field | Value |
|-------|-------|
| `_preset_source` | `'STRADDLE_ROLL'` |
| `dte_category` | `'STRADDLE_ROLL'` |
| Preset constant | `STRADDLE_ROLL_CATEGORY` (in `mmm_dte_presets.py`) |
| Strategy name (UI) | `Short Straddle Roll` |
| MMM adjustment engine | Disabled via `min_trigger_move: 9999` |

---

## 4. Decision Tree (Every Heartbeat)

```
════════════════════════════════════════════════════
 EVERY 5 SECONDS — Price Guard (WebSocket, no API)
════════════════════════════════════════════════════
 Is spot within price_guard_buffer_pts of roll trigger?
   YES → fire force_heartbeat()
 Is estimated loss ≥ 85% of max_loss?
   YES → fire force_heartbeat()
 Rate limit: after firing, wait price_guard_cooldown_secs

════════════════════════════════════════════════════
 EVERY 120s (or immediately on force_heartbeat)
════════════════════════════════════════════════════
 STEP 1 — HARD STOP
   total_pnl ≤ -max_loss_amount?
   → YES: Close ALL with MARKET ORDER. STOP. Telegram CRITICAL.

 STEP 2 — EXPIRY GUARD
   minutes_to_expiry < auto_close_mins (10)?
   → YES: Close all (limit). STOP.
   minutes_to_expiry < straddle_roll_min_time_to_expiry (90)?
   → YES: Hold. Skip roll.

 STEP 3 — ROLL TRIGGER
   abs(spot - atm_strike) ≥ _straddle_roll_trigger_pts?
   → NO: Do nothing. Theta is working.
   → YES: Run gates (margin, cooldown, spread, same-strike, max-rolls, etc.)
          Execute 4-leg roll (LIMIT orders).
          Update _straddle_roll_trigger_pts = new CE_fill + PE_fill.
          Reset _regime_trend, _whipsaw_score, _straddle_entry_iv.
          Telegram: "Roll #N fired."
════════════════════════════════════════════════════
```

---

## 5. Backend Isolation (Two Guards)

### Guard 1 — Preset disable
`build_straddle_roll_preset()` in `mmm_dte_presets.py` sets `min_trigger_move: 9999`.
The strangle trigger at Step 6 of the heartbeat evaluates the condition and silently returns `OUTCOME_NONE` every beat — no code changes to the trigger engine.

### Guard 2 — Heartbeat skip (added 2026-04-11)
In `mmm_monitor.py` Step 5.4, after `execute_pure_straddle_roll()` returns (whether it rolled or not), `_skip_to_pnl = True` is set unconditionally:
```python
elif params.get('_preset_source') == STRADDLE_ROLL_CATEGORY and not self._paused:
    _pure_roll_fired = await execute_pure_straddle_roll(...)
    if _pure_roll_fired:
        _skip_to_pnl = True
    # Always skip MMM trigger/adjustment engine for STRADDLE_ROLL
    _skip_to_pnl = True
```
This means the strangle trigger evaluation (Step 6) and `_process_adjustment` are **never reached** for any STRADDLE_ROLL heartbeat, regardless of market conditions.

---

## 6. File Map

| File | Role |
|------|------|
| `webui/backend/routes/mmm/mmm_straddle_roll_pure.py` | **All roll logic** — hard stop, expiry guard, roll gates, 4-leg execution, post-roll reset |
| `webui/backend/routes/mmm/mmm_dte_presets.py` | `build_straddle_roll_preset()` + `STRADDLE_ROLL_CATEGORY` constant |
| `webui/backend/routes/mmm/mmm_monitor.py` | Step 5.4 routes to `execute_pure_straddle_roll()`; sets `_skip_to_pnl=True` after |
| `webui/backend/routes/mmm/mmm_api.py` | Session creation validation — enforces required fields |
| `webui/backend/routes/mmm/mmm_state.py` | Default params (`straddle_roll_*`, `price_guard_*`) |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | UI settings filtering — locks 18 irrelevant groups |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | Session card badge, creation form (STRADDLE_ROLL form fields) |

**Do NOT modify these files for roll logic:**
`mmm_engine.py`, `mmm_constants.py`, `mmm_trigger.py`, `mmm_replenish.py`,
`mmm_regime.py`, `mmm_guardian.py`, `mmm_fill_sync.py`, `mmm_pnl_core.py`

---

## 7. Session State Fields

| Field | Set by | Meaning |
|-------|--------|---------|
| `_straddle_dynamic_trigger_pts` | Each heartbeat | **Primary trigger** — live CE_mid + PE_mid from WS cache. Shrinks with theta. Cleared after each roll so fresh decay tracking begins. |
| `_straddle_roll_trigger_pts` | Startup + post-roll | **Fixed fallback trigger** — CE_fill + PE_fill at last roll entry. Used when dynamic trigger unavailable. |
| `_straddle_initial_credit` | Session start | Total credit at first entry. Used by loss-abort gate (Gate 10). **Never reset.** |
| `_straddle_roll_count` | Each roll | Rolls fired so far. Checked against `straddle_roll_max_per_session`. |
| `_straddle_last_roll_at` | Each roll | ISO timestamp of last roll. Used for cooldown gate. |
| `_straddle_roll_blocked` | Gate 6 | True when roll count exhausted. Auto-clears if max raised via hot-reload. |
| `_straddle_entry_iv` | First heartbeat | IV at entry. Used for IV spike soft warning. Cleared after each roll. |
| `_straddle_half_roll_state` | Roll execution | Breadcrumb if roll was interrupted mid-way. Startup detects and blocks. |
| `_straddle_roll_in_progress` | Roll lock | True while 4-leg execution is running. Prevents concurrent rolls. |
| `_price_guard_last_loss_estimate` | Heartbeat | Last known estimated loss. Read by price guard (never written by guard). |

---

## 8. Key Parameters

| Param | Default | Hot-reload | Note |
|-------|---------|-----------|------|
| `max_loss_amount` | **REQUIRED** | No | Hard stop threshold. Must be explicit at creation. |
| `initial_lots` | **REQUIRED** | No | Lots per side. Must be explicit at creation. |
| `straddle_roll_max_per_session` | **REQUIRED** | Yes | 0 = hard-stop-only mode (no rolls). |
| `straddle_dynamic_trigger_enabled` | True | Yes | **Use live CE+PE mid sum as trigger (default ON).** Shrinks naturally with theta. |
| `straddle_min_trigger_pts` | 200 | Yes | Hard floor for dynamic trigger. Prevents noise-firing near expiry. |
| `straddle_roll_cooldown_mins` | 15 | Yes | Min gap between rolls. |
| `straddle_roll_emergency_mult` | 2.0 | Yes | Bypass cooldown when spot_move ≥ N× trigger distance. |
| `straddle_roll_max_spread_pct` | 15.0 | Yes | Block roll if bid-ask spread too wide. |
| `straddle_roll_trigger_pct` | 1.0 | Yes | **Last-resort fallback only** — used only when both dynamic and fixed triggers are unavailable. |
| `price_guard_enabled` | True | Yes | Real-time 5s WS guard. |
| `price_guard_buffer_pts` | 50 | Yes | Pre-alert before trigger. |
| `auto_close_mins` | 10 | Yes | Close all N min before expiry. |
| `wind_down_enabled` | **False** | — | Preset-locked. Must stay False. |
| `harvest_enabled` | **False** | — | Preset-locked. Must stay False. |
| `atm_shield_enabled` | **False** | — | Preset-locked. Must stay False. |
| `min_trigger_move` | 9999 | — | Disables strangle adjustment engine. Never change. |

---

## 9. Roll Execution — 4-Leg Sequence

Inside `_execute_4_leg_roll()` in `mmm_straddle_roll_pure.py`:
1. Close ITM leg (limit order)
2. Close OTM leg (limit order)
3. [Optional: re-fetch ATM if spot moved during closes]
4. Sell new CE at ATM (limit order)
5. Sell new PE at ATM (limit order)
6. Update `_straddle_roll_trigger_pts = CE_fill + PE_fill` (fixed fallback for next period)
7. **Clear `_straddle_dynamic_trigger_pts`** so fresh theta decay tracking begins from new entry
8. Reset: `_regime_trend`, `_regime_tier`, `_straddle_entry_iv`, `_adaptive_interval`
9. Telegram: Roll #N notification

**Half-roll detection:** If steps 1–5 fail mid-sequence, `_straddle_half_roll_state` is set. On next startup, `execute_pure_straddle_roll()` detects it, fires Telegram CRITICAL, and blocks the session. Manual recovery required.

---

## 10. Roll Gates (in order)

| Gate | Condition | Blocks if... |
|------|-----------|-------------|
| 0 | In-progress lock | Roll already running (`_straddle_roll_in_progress`) |
| 1 | Master switch | `straddle_roll_enabled` is False |
| 1.5 | Session status | Status not RUNNING or ACTIVE |
| 2 | Strategy identity | `strategy_type != STRADDLE_ROLL` |
| 2.5 | Both legs present | CE or PE has no active positions |
| 3 | Time to expiry | `minutes_to_expiry < straddle_roll_min_time_to_expiry` (90 min) |
| 4 | Margin safety | Margin tier is RED or CRITICAL |
| 5 | IV spike | IV > 2× entry IV → **logs warning only, does NOT block** |
| 6 | Max rolls | `roll_count ≥ straddle_roll_max_per_session`. Auto-clears if max raised. |
| 7 | Cooldown | Last roll < `straddle_roll_cooldown_mins` ago (bypassed at `emergency_mult × trigger`) |
| 8 | **Distance trigger** | `spot_move < effective_trigger_pts`. Effective = **dynamic** (CE_mid + PE_mid, floored at 200 pts) → fallback to fixed → fallback to pct. |
| 9 | ATM preview (inside executor) | Fresh ATM preview required; checks: staleness, same-strike, credit floor, spread |
| 10 | Loss abort (belt) | Belt-and-suspenders: `total_loss > loss_abort_mult × initial_credit` |

---

## 11. Session Creation Rules

Required HTTP fields (400 error if absent):
- `initial_lots` — must be explicitly provided (not defaulted)
- `straddle_roll_max_per_session` — operator must choose (0 = no rolls)
- `max_loss_amount` — hard stop limit

After creation: `max_lots_per_side` is locked to `initial_lots` by `mmm_api.py`. This prevents the position from ever growing beyond the initial straddle size.

---

## 12. UI Settings Panel (MMMSettingsDialog.js)

STRADDLE_ROLL sessions show **3 active groups** in the settings panel:
- **Core Parameters** — `initial_lots`, `adjustment_interval`, `max_loss_amount`
- **Close-at-Expiry** — `auto_close_mins`, `stop_adjustment_mins`, etc.
- **Straddle Roll Settings** — roll limits, spread/trigger, price guard params

All other 18 groups are **greyed out / locked** with 🔒 badge. They cannot be clicked or edited. Detection: `sessionData.params._preset_source === 'STRADDLE_ROLL'`.

---

## 13. Critical Invariants — DO NOT BREAK

1. **`_skip_to_pnl = True`** must always be set after the STRADDLE_ROLL `elif` block in `mmm_monitor.py` Step 5.4. Removing it allows the strangle adjustment engine to fire accidentally.

2. **`min_trigger_move: 9999`** in the preset must never be lowered. It is the first-layer isolation guard.

3. **Hard stop uses market orders** (`straddle_roll_hard_stop_market_order: True`). Never change to limit orders for the hard stop path — they don't fill in fast markets.

4. **`wind_down_enabled`, `harvest_enabled`, `atm_shield_enabled` must stay `False`**. Wind-down closes the OTM leg (your hedge). Harvest does the same. ATM Shield conflicts with the roll.

5. **`_straddle_initial_credit` must never be reset** between rolls. It is the full-session loss abort baseline (Gate 10). Resetting it removes the session-level safety net.

6. **CE:PE ratio is always 1:1.** Do not add logic that changes lot sizes between sides. The straddle structure requires exact symmetry.

7. **4-leg roll is atomic.** Never add partial roll logic (roll one side only). A half-roll leaves a naked position and fires the CRITICAL Telegram alert on restart.

---

## 14. Dynamic Trigger — Design & Fallback Chain

**Why dynamic:** The old fixed trigger (`CE_fill + PE_fill` at entry, e.g. 1196 pts) is frozen for the entire holding period. After theta decay the position only has `current_mark` pts of cushion, not the original 1196. Rolling at the original distance means the straddle runs too far ITM before a roll fires.

**New design (added 2026-04-13):** Each heartbeat, `_compute_dynamic_trigger()` reads the live WS bid/ask mid for both the active CE and PE legs. `effective_trigger = CE_mid + PE_mid`, floored at `straddle_min_trigger_pts` (default 200) to prevent noise-fire near expiry.

**Fallback chain** (in order, all handled inside `_get_effective_trigger_pts()`):
1. **Dynamic** (`_straddle_dynamic_trigger_pts`) — if `straddle_dynamic_trigger_enabled=True` and WS prices are fresh
2. **Fixed** (`_straddle_roll_trigger_pts`) — entry premium at last roll; set on every roll completion
3. **Healed fixed** — re-derived from `entry_premium` on current positions if `_straddle_roll_trigger_pts` is 0
4. **Pct fallback** (`straddle_roll_trigger_pct × spot`) — absolute last resort; should never be reached in normal operation

**Price source — MUST be fresh ATM, NOT existing position prices:** Using the existing position's mid prices at the old ATM strike is mathematically broken:
```
existing_CE_mid + existing_PE_mid = |spot - K| + time_value  >  |spot - K|  always
```
This means `spot_move < trigger` forever (time_value never goes to zero before `straddle_roll_min_time_to_expiry` blocks the roll). The correct source is `preview_atm_straddle()` — the fresh ATM premiums at the current spot's nearest strike. Fresh ATM premiums shrink with theta and are not inflated by intrinsic value. (Bug fixed 2026-04-13.)

**Post-roll reset:** After a successful roll, `_straddle_dynamic_trigger_pts` is cleared from the session dict. The next heartbeat recomputes it fresh from the new ATM entry, so theta decay tracking starts from zero on the new straddle.

---

## 15. Relation to STRADDLE_WITH_ADJUSTMENT

| Aspect | STRADDLE_ROLL | STRADDLE_WITH_ADJUSTMENT |
|--------|--------------|-------------------------|
| `_preset_source` | `STRADDLE_ROLL` | `STRADDLE_WITH_ADJUSTMENT` |
| Implementation file | `mmm_straddle_roll_pure.py` | `mmm_straddle_adjustment.py` |
| MMM adjustment engine | Never runs | Runs between rolls |
| Roll trigger | **Dynamic**: live CE_mid + PE_mid (floored at 200 pts). Fixed (`_straddle_roll_trigger_pts`) used as fallback. | Percentage (`straddle_roll_trigger_pct`) |
| Hard stop orders | Market (taker) | Limit (mid-price) |
| Wind-down | Disabled | Enabled |
| Position growth | Locked to initial_lots | Can grow via adjustments |
| When to use | Pure theta + roll only | ATM straddle + MMM hedge logic |

These two strategies are **mutually exclusive**. A session has exactly one `_preset_source`. Never merge their logic.

---

## 16. Source of Truth

For all detailed logic, quant reasoning, fix plans, and implementation order:

**`tasks/STRADDLE_ROLL_FIX_PLAN.md`** — Rev 4.0

That document explains *why* each decision was made. When debugging or extending, read it before touching any STRADDLE_ROLL code.

Work log for all changes: `mmm_workdone_march.md`
