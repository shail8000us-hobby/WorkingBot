# STRADDLE_WITH_ADJUSTMENT — How It Actually Works

**Created: 2026-04-10**
**Status: ACTIVE PRESET — do not remove**
**Preset string: `STRADDLE_WITH_ADJUSTMENT`**
**Primary files:**
- `mmm_straddle_adjustment.py` — roll logic (gates + execution)
- `mmm_dte_presets.py` — `build_straddle_adjustment_preset()`
- `mmm_monitor.py` — heartbeat, price guard, straddle init block

---

## 1. What This Preset Is

This preset **discovered itself in production** on 2026-04-10 while attempting to implement a pure straddle roll. Two test sessions (`mmm10apr26-2` and `mmm10apr26-3`) ran with the SHORT_STRADDLE preset and the MMM adjustment engine was never disabled — resulting in:

- Sessions started as ATM straddles (1 CE lot + 1 PE lot at the same strike)
- The MMM engine treated each leg as an independent strangle and applied adjustments
- When BTC moved against one leg, the engine added more lots to that leg as a hedge
- Sessions ended with asymmetric positions (1 CE : 5 PE and 1 CE : 3 PE)
- **Despite the asymmetry, P&L was positive and the sessions were profitable**

This proved the strategy has merit. It is now kept, named, and documented as a **deliberate hybrid strategy**: an ATM straddle with MMM strangle-style adjustment logic allowed to run freely on both legs.

---

## 2. Strategy Architecture

```
Session starts: Sell 1 CE + 1 PE at ATM strike (equal lots)
                     │
                     ▼
         MMM heartbeat every 120s (+ price guard every 5s)
                     │
         ┌───────────┴───────────────────────────┐
         │                                       │
    ROLL CHECK (Gate 8)                 ADJUSTMENT ENGINE
    Fires when spot moved               Normal MMM adjustment logic
    ≥ trigger_pts from ATM              runs freely on both sides:
         │                               - Strangle trigger evaluation
    ALL gates pass?                      - Regime gates apply
         │                               - Reversal detection active
    YES → Full 4-leg roll               - Position cap enforced
    (close both, re-enter ATM)          - Lot velocity limits apply
         │
    New trigger_pts = new CE fill + PE fill
```

The key insight: the MMM adjustment engine and the roll mechanism coexist. The engine adds lots to whichever leg is losing; the roll resets the whole position when spot has moved far enough.

---

## 3. What the Roll Does (mmm_straddle_adjustment.py)

### 12 Gates Before Any Trade

| Gate | Name | Logic |
|------|------|-------|
| 0 | In-progress guard | Blocks concurrent roll attempts (session lock) |
| 1 | Master switch | `straddle_roll_enabled = True` |
| 1.5 | Strategy status | Session must be RUNNING or ACTIVE |
| 2 | Preset check | `_preset_source == STRADDLE_WITH_ADJUSTMENT` |
| 2.5 | Leg presence | Both CE and PE must have active positions |
| 3 | Wind-down | Skipped (wind_down_enabled=False in preset) |
| 4 | Time to expiry | Must have ≥ 90 min remaining |
| 5 | Margin | Not at TIER_RED or TIER_CRITICAL |
| 5.5 | IV spike | Soft warning only — does NOT block roll |
| 6 | Max rolls | roll_count < straddle_roll_max_per_session |
| 7 | Cooldown | 15 min cooldown between rolls (emergency bypass at 2× trigger_pts) |
| 8 | Distance trigger | `abs(spot - ATM) ≥ _straddle_roll_trigger_pts` |
| 10 | Loss abort | Total loss < 3× original_credit |

**Gate 9** (ATM viability) runs inline after all gates pass:
- Preview freshness check (< 5 seconds old)
- Same-strike guard (won't roll to the same strike)
- Minimum credit check (new credit ≥ 30% of original)
- Spread check (avg bid-ask spread < 15%)

### Roll Execution: 4 Legs, Sequentially

```
Step 1: Fetch live spot price
Step 2: Close ITM leg first (dynamic: CE if spot ≥ ATM, PE if spot < ATM)
        → If close fails: abort, return False
        → Set half-roll breadcrumb: ce_closed_pe_open or pe_closed_ce_open
Step 3: Close OTM leg
        → If close fails: CRITICAL — session STOPPED, Telegram alert fired
        → Set breadcrumb: both_closed_no_reentry
Step 4: Sell new CE at new ATM (roll_lots)
        → If fails: CRITICAL — session STOPPED
        → Set breadcrumb: ce_entered_pe_pending
Step 5: Sell new PE at new ATM (matching PE lots to CE fill)
        → If fails: CRITICAL — NAKED CE — session STOPPED, Telegram alert
Step 6: Update state
        - Increment _straddle_roll_count
        - Update _straddle_roll_trigger_pts = CE_fill + PE_fill
        - Update _straddle_cumulative_credit
        - Clear half-roll breadcrumb
Step 7: Audit log
Step 8: Activity log + Telegram + post-roll state reset
```

### Post-Roll State Reset (after every successful roll)

These session keys are cleared so the new position starts fresh:
- All `_trend_*` regime keys (trend_regime, tier, direction, anchor, etc.)
- `_straddle_entry_iv` (recaptured on next heartbeat)
- `_adaptive_tier`, `_adaptive_interval`

These are intentionally NOT reset:
- `_straddle_initial_credit` — full-session loss abort baseline
- `_straddle_roll_count` — cumulative roll counter
- `_straddle_cumulative_credit` — analytics
- `max_loss_amount` — session-level hard stop
- P&L accounting fields

---

## 4. Trigger Logic

### Primary: `_straddle_roll_trigger_pts`

Computed at session startup in `mmm_monitor.py` init block:
```
ce_avg = weighted_avg(entry_premium × lots) over all active CE positions
pe_avg = weighted_avg(entry_premium × lots) over all active PE positions
_straddle_roll_trigger_pts = ce_avg + pe_avg
```

**Important**: Because the MMM adjustment engine can add more lots at different entry premiums, the trigger_pts reflects the blended average across ALL positions (not just the original entry).

Updated after every successful roll:
```
_straddle_roll_trigger_pts = CE_actual_fill + PE_actual_fill
```
(Actual fill prices from the new ATM sell — not mid-price estimate.)

### Fallback Chain (Gate 8)

1. Use `_straddle_roll_trigger_pts` from session (primary)
2. Recompute live from active positions (if key missing)
3. Fall back to `straddle_roll_trigger_pct % × spot` (last resort, logs warning)
4. If all fail: return `no_trigger_pts`, block roll

---

## 5. What the MMM Adjustment Engine Does

Between rolls, the standard MMM heartbeat runs. This means:

**What can happen to positions:**
- If spot moves against CE: engine may sell more PE lots as hedge (reversal adjustment)
- If spot moves against PE: engine may sell more CE lots as hedge
- Regime gates can pause adjustments (BLOCK_CE_SELLS, FORCE_REDUCE, etc.)
- Whipsaw protection limits rapid lot additions
- Position cap (`max_lots_per_side: 5`) prevents runaway lot accumulation
- Lot velocity limit controls the rate of new lot additions

**Result**: sessions naturally develop asymmetric CE/PE positions over the session lifetime. The roll resets this asymmetry by closing ALL positions on BOTH sides and re-entering equal lots at the new ATM.

**What is disabled:**
- `wind_down_enabled: False` — prevents premature leg closure before roll
- `harvest_enabled: False` — prevents partial lot buyback breaking straddle symmetry
- `atm_shield_enabled: False` — ATM shield would immediately fire on the first BTC move (both legs START at ATM)
- `perp_hedge_enabled: False` — options-only strategy
- `scale_enabled: False` — no scaler intervention

---

## 6. Price Guard (Real-Time Monitoring)

A background thread runs every 5 seconds for STRADDLE_WITH_ADJUSTMENT sessions:

```
Every 5 seconds:
  1. Read spot from WebSocket (rejects if data > 30s stale)
  2. If spot_move ≥ (trigger_pts - 50pts) AND spot_move < trigger_pts × 2:
     → Fire force_heartbeat() — triggers immediate heartbeat
  3. If last_known_loss ≥ max_loss × 85%:
     → Fire force_heartbeat()
  4. After any fire: wait 30s cooldown before next fire
```

This reduces detection latency from 0–120 seconds to 0–5 seconds when BTC approaches the roll trigger.

---

## 7. Preset Parameters (at 5h session, all auto-scaled)

| Parameter | Value | Notes |
|-----------|-------|-------|
| `initial_lots` | 1 | Always 1 — operator may override |
| `max_lots_per_side` | 5 | Position cap for adjustments |
| `max_total_exposure` | 10 | Total lot ceiling |
| `adjustment_interval` | 120s | Heartbeat frequency |
| `min_trigger_move` | 50 pts | High — limits spurious adjustments |
| `max_loss_amount` | 3000 | Hard stop (USD). Operator may override |
| `straddle_roll_enabled` | True | Roll mechanism active |
| `straddle_roll_cooldown_mins` | 15 | Min gap between rolls |
| `straddle_roll_max_per_session` | **REQUIRED** | Operator must set — not defaulted |
| `straddle_roll_trigger_pct` | auto (0.5–1.5%) | Last-resort fallback only |
| `straddle_roll_min_credit_pct` | 30% | New roll must collect ≥30% of original credit |
| `straddle_roll_max_spread_pct` | 15% | Max bid-ask spread on re-entry |
| `price_guard_enabled` | True | 5s real-time monitoring |
| `price_guard_buffer_pts` | 50 | Force-HB when 50pts from trigger |
| `wind_down_enabled` | False | Disabled — fights roll |
| `harvest_enabled` | False | Disabled — breaks leg symmetry |
| `atm_shield_enabled` | False | Disabled — would fire immediately |
| `perp_hedge_enabled` | False | Options-only |

---

## 8. Session Creation Requirements

Two params must be explicitly set by the operator when creating a session:

1. **`initial_lots`** — minimum 1. Not defaulted — operator must decide.
2. **`straddle_roll_max_per_session`** — how many rolls allowed. Set to 0 for pure adjustment mode (no rolls). Not defaulted — operator must decide.

If either is missing: API returns HTTP 400.

**Hot-reloadable at runtime:** `straddle_roll_max_per_session` can be raised mid-session to unlock additional rolls. Gate 6 auto-clears the blocked flag on the next heartbeat.

---

## 9. Known Behaviors from First Live Test (2026-04-10)

**What worked well:**
- Both sessions profitable (P&L $0.55 and $0.71 on 1-lot test positions)
- Adjustment engine correctly hedged when BTC moved away from entry ATM
- Price guard active, wind-down correctly disabled
- Roll trigger logic computed and stored correctly

**What to watch:**
- `_straddle_roll_trigger_pts` uses the blended average across all positions (including adjustment lots). After several adjustments, the trigger_pts may inflate significantly (e.g., 1168 pts on session -2 vs ~840 pts theoretical for original premium). This means the roll fires later than a pure straddle would.
- Heavy adjustment accumulation (5 PE lots vs 1 CE lot) can hit `max_lots_per_side` cap and block further adjustments. Consider raising `max_lots_per_side` if you want more adjustment room.
- `asymmetry` safety warning fires repeatedly when CE:PE ratio diverges — this is expected and informational for STRADDLE_WITH_ADJUSTMENT.

---

## 10. Difference from Pure Straddle Roll (STRADDLE_ROLL — planned)

| Aspect | STRADDLE_WITH_ADJUSTMENT | STRADDLE_ROLL (planned) |
|--------|--------------------------|-------------------------|
| CE:PE ratio | Can diverge via adjustments | Always equal (1:1) |
| Between-roll action | MMM adjustment engine active | Nothing — only monitor |
| P&L character | Delta-hedged via adjustments | Pure theta decay |
| Risk profile | Lower directional risk | Higher directional risk |
| Trigger_pts calc | Blended avg across all positions | Pure CE + PE fill price |
| Files | `mmm_straddle_adjustment.py` | New file: `mmm_straddle_roll_pure.py` |
| Preset | `STRADDLE_WITH_ADJUSTMENT` | `STRADDLE_ROLL` (new) |
