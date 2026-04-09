# AIMMM — Short Straddle Strategy Reference

**Preset name:** `SHORT_STRADDLE` (`_preset_source = 'SHORT_STRADDLE'`)
**Created:** 2026-04-09
**Branch:** SSR

---

## What Is the Short Straddle?

Sell ATM CE + ATM PE simultaneously at the same strike. Collect premium from both sides.
Roll when spot moves by total premium collected (CE premium + PE premium in points).
Hard stop closes everything if max_loss is breached.

### Example
- BTC at 85,000. Sell CE @ 85,000 for ₹200 and PE @ 85,000 for ₹200. Total premium = 400 pts.
- If BTC moves to 85,400 (up 400 pts) OR 84,600 (down 400 pts) → roll fires.
- Roll: buy back both legs, sell new CE + PE at new ATM (85,000 or 84,600).
- Trigger resets to new CE + PE fill prices after each roll.

### Key Differences from Strangle
| | Strangle (0DTE/5DTE) | Short Straddle |
|---|---|---|
| Entry | CE and PE at different OTM strikes | CE and PE at same ATM strike |
| Adjustment | Individual leg shifts when premium decays | Full roll — both legs closed + re-entered |
| Roll trigger | Per-leg: premium threshold | Both legs: spot moves ≥ CE+PE premium pts |
| Wind-down | Enabled (closes OTM leg near expiry) | Disabled (fights roll) |
| Harvest | Enabled (partial lot profit-taking) | Disabled (breaks CE/PE symmetry) |
| Regime controls | Trend/vol/gamma guards active | Not applicable |
| Session duration | 0DTE: up to 36h, 5DTE: multi-day | 1h minimum, 24h maximum |

---

## Operator Controls at Session Creation (Required)

| Parameter | Description | Notes |
|-----------|-------------|-------|
| `initial_lots` | Lots per side (CE and PE each) | Minimum 1, no default |
| `straddle_roll_max_per_session` | How many rolls allowed | Required — no preset default, operator must decide |
| `expiry` | Option expiry date | Must be ≥ 1h away |

---

## Active Settings Groups (5 of 21)

These are the only groups visible and editable in Strategy Settings for a SHORT_STRADDLE session. All others are 🔒 locked.

### 1. Core Parameters
**Key params:** `initial_lots`, `adjustment_interval`, `max_loss_amount`

- `initial_lots` — Lots per side. CE and PE each get this count.
- `adjustment_interval` — Heartbeat interval in seconds. Default 120s for straddle.
- `max_loss_amount` — Hard stop in USD. When total P&L ≤ -this value, ALL positions closed immediately with taker (IOC) orders.

### 2. Close-at-Expiry
**Key params:** `auto_close_mins`, `stop_adjustment_mins`, `close_at_threshold`, `theta_acceleration_window`

- `auto_close_mins` — Auto-close ALL positions N minutes before expiry. Default 10 for straddle (vs 5 for strangle). Critical final safety net.
- `stop_adjustment_mins` — Stop new adjustments N minutes before expiry.
- `close_at_threshold` — Close any position worth ≤ this premium. Default $5.

### 3. Adaptive Interval
**Key params:** `adaptive_interval_enabled`

- Automatically shortens heartbeat as expiry approaches.
- Works alongside the 5s Price Guard — Price Guard handles fast spot moves, Adaptive Interval handles time-based escalation.

### 4. Close-at-5 Watcher
**Key params:** `close_at_watcher_force_enabled`, `close_at_watch_hours_before_expiry`, `close_at_watch_interval`

- Background thread that polls bid prices and forces heartbeat when premium decays to close_at_threshold.
- Default: activates in last 3h before expiry.
- Can be force-enabled for full-session monitoring.

### 5. Breakeven Engine
**Key params:** `breakeven_control_enabled`, zone thresholds, aggression

- Calculates BTC spot price where total P&L becomes negative.
- Monitoring tool — shows on dashboard how far spot can move before going into loss.
- No side effects on order placement (observation only unless `breakeven_control_enabled=True`).

---

## Locked Settings Groups (16 of 21)

These panels appear grayed out (🔒 LOCKED) and are not clickable. Changing them would have no effect or would actively break the roll mechanism.

| Group | Reason Locked |
|-------|---------------|
| **Trigger & Adjustment** | `min_trigger_move`, `shift_threshold` etc. are per-leg strike-shift params. Straddle rolls BOTH legs together — no individual leg shifting. |
| **Safety Limits** | Whipsaw detection and ITM guard are strangle-specific. Straddle expects one leg to go ITM on every move — ITM guard would fire constantly. |
| **Wind-Down Mode** | `wind_down_enabled=False` in preset. Wind-down closes the profitable (decaying) OTM leg which destroys straddle structure before a roll can fire. |
| **Margin Guardian** | Default thresholds are correct. No operator tuning needed. Changing these could weaken the last margin defense. |
| **Regime Controls** | 37 trend/vol/gamma params for strangle directional intelligence. Straddle is direction-neutral — regime blocking would prevent valid rolls. |
| **ATM Shield** | Actively conflicts with roll. ATM Shield closes + retreats OTM when spot approaches the strike. Straddle should ROLL instead. Both cannot run simultaneously. |
| **Lot Velocity Limiter** | A 4-leg roll counts as 4 rapid lot events. The velocity limiter could throttle or completely block the roll from executing. |
| **Position Lifecycle** | `harvest_enabled=False`. Partial lot closes break CE/PE lot symmetry — asymmetric position is not a straddle. |
| **Balance Control** | CE/PE asymmetry rebalancing is for strangle (legs diverge separately). Straddle maintains symmetry via the roll. |
| **Favorable Scale-Up** | `scale_enabled=False`. Adding new OTM positions during a flat market changes the P&L profile from pure straddle to strangle. |
| **Auto-Replenish Leg** | Replenish re-opens only one side when it reaches 0. That creates a naked position (one-sided exposure). Straddle always closes and re-enters BOTH legs together. |
| **Perp Delta Hedge** | `perp_hedge_enabled=False` in preset. Straddle is inherently delta-neutral at entry — perp hedge is for strangle delta management. |
| **Consecutive Direction Limiter** | No directional selling in straddle. Both sides always sold together. This limiter would never fire and adds confusion. |
| **Adaptive Tuning** | `adaptive_mode` is locked to `'preset'` at session creation. Cannot be changed without session restart. |
| **Gamma Detector** | P&L curvature scanner calibrated for strangle strike distribution. Straddle has symmetric strikes — detector output is misleading. |
| **Controlled Reverse Mode** | Incompatible with straddle roll. Reverse mode suspends normal hedge-sell logic entirely. |

---

## Price Guard (Real-Time Spot Monitor)

Not a settings group — built into the monitor thread for SHORT_STRADDLE sessions.

**How it works:**
1. Background thread polls `session['analytics']['last_spot_price']` every 5 seconds.
2. When `spot_move_pts ≥ trigger_pts - buffer_pts` (default buffer = 50 pts), fires `force_heartbeat()`.
3. Heartbeat runs immediately → checks Gate 8 → if trigger met, executes roll.
4. Total detection-to-execution latency: ~7–10 seconds.

**Hot-reloadable params:** `price_guard_enabled`, `price_guard_interval_secs`, `price_guard_buffer_pts`, `price_guard_cooldown_secs`

These appear in the **Core Parameters** group settings or via direct API hot-reload.

---

## Roll Trigger Logic (Gate 8)

```
trigger_pts = CE_entry_premium + PE_entry_premium  (lot-weighted average)

Roll fires when:  abs(spot - atm_strike) >= trigger_pts
```

**Fallback chain (Gate 8):**
1. `session['_straddle_roll_trigger_pts']` — set at startup and updated after each roll
2. Recompute from `entry_premium` on active positions (if key missing)
3. `straddle_roll_trigger_pct × spot` — last resort percentage fallback
4. `no_trigger_pts` — block roll entirely

**After each roll:** `_straddle_roll_trigger_pts` is updated to the actual CE + PE fill prices (not preview prices).

---

## Hard Stop Path

When `total_pnl ≤ -max_loss_amount`:
1. `alert_max_loss_breach()` fires Telegram alert
2. `_auto_close_all(reason, emergency=True)` is called
3. `emergency=True` → parallel taker IOC orders on all positions
4. Session status set to `STOPPED` — no re-entry

No retry, no limit orders — full taker execution to guarantee fill.

---

## Session Creation Checklist (Before Real Money)

- [ ] Select expiry ≥ 1h away (use tomorrow's expiry for day sessions, or Saturday weekly)
- [ ] Set `initial_lots` (start with 1 for first live test)
- [ ] Set `straddle_roll_max_per_session` (recommend 3 for a 24h session)
- [ ] Verify `max_loss_amount` is set to your actual risk tolerance
- [ ] Verify `auto_close_mins = 10` (or set manually)
- [ ] After session creation: open Config Panel → preview ATM straddle → confirm CE and PE premiums
- [ ] Check `_straddle_roll_trigger_pts` = CE_premium + PE_premium in session state
- [ ] Verify `⚡ Guard` chip appears on session card (price guard active)
- [ ] Verify `🔄 Rolls: 0/N` badge shows correct max_rolls

---

## Key Session State Keys

| Key | Description |
|-----|-------------|
| `_straddle_initial_credit` | Total credit collected at session start (CE+PE premium × lots × 0.001). Never changes. |
| `_straddle_roll_trigger_pts` | Current roll trigger in BTC points. Updated after each roll. |
| `_straddle_roll_count` | Number of rolls completed this session. |
| `_straddle_cumulative_credit` | Running total of all credits collected (initial + all rolls). |
| `_straddle_last_roll_at` | ISO timestamp of last roll. |
| `_straddle_roll_blocked` | True when max_rolls exhausted (session paused). |
| `_straddle_last_roll_iv_spike` | Set when Gate 5.5 IV spike was noted (audit trail only, not a block). |

---

## Files Changed in Rev 3.0 (2026-04-09)

| File | Change Summary |
|------|---------------|
| `mmm_straddle_roll.py` | Gate 8 premium-points trigger, IV spike soft warning, same-strike guard, spread check, post-roll state reset, Telegram alert |
| `mmm_monitor.py` | `_straddle_roll_trigger_pts` init, `_price_guard_loop` thread, shift fallback floor, bid cache bug fix |
| `mmm_dte_presets.py` | wind_down=False, harvest=False, 24h cap, max_rolls removed from preset |
| `mmm_state.py` | New DEFAULT_PARAMS + HOT_RELOAD_PARAMS for price guard, spread check |
| `mmm_api.py` | Require initial_lots + straddle_roll_max_per_session at session creation |
| `mmm_telegram.py` | `alert_straddle_roll_executed()` |
| `MMMDashboard.js` | Roll badge shows actual trigger pts, `⚡ Guard` chip, max_rolls field in creation form |
| `MMMSettingsDialog.js` | 16 of 21 settings groups locked for SHORT_STRADDLE with orange banner |
| `test_sealed_straddle_roll_rev3.py` | 23 new sealed tests (total suite: 1281) |

---

## Quick Reference: What the Operator Controls

In a live SHORT_STRADDLE session, the operator has these levers:

| Action | How |
|--------|-----|
| Change max rolls | Hot-reload `straddle_roll_max_per_session` → takes effect next heartbeat |
| Change hard stop | Hot-reload `max_loss_amount` in Core Parameters |
| Change heartbeat speed | Hot-reload `adjustment_interval` in Core Parameters |
| Disable price guard | Hot-reload `price_guard_enabled=False` |
| Change price guard buffer | Hot-reload `price_guard_buffer_pts` |
| Force immediate heartbeat | Force Heartbeat button on dashboard |
| Close all positions | Stop Session button → auto_close_all with emergency=True |
| Pause (prevent new rolls) | Pause button → strategy_status=PAUSED |
