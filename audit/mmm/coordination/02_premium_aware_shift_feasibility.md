# Phase 1 — Task 4: Premium-Aware Shift Feasibility

**Status**: Complete
**Date**: 2026-04-27
**Auditor**: Claude
**Scope**: Determine whether the arbiter's Tier 1 defensive action ("find strike at target premium, sell minimum lots") can reuse existing logic, and what (if anything) needs to be built new in Phase 3.

---

## TL;DR

**Excellent news for Phase 3.** All four building blocks already exist. The arbiter is pure orchestration — no new lot-math, no new strike-scanning, no new chain-querying. Estimated arbiter Tier 1 implementation: **~50 lines**, reusing four existing functions.

The current bug (cheap-policy pile-up visible in the mmm28apr26-1 screenshot) is **not** because the math is wrong. It's because the algo sells at the **existing** far-OTM strike when premium has decayed there, instead of **shifting first**, then sizing at the better strike. The arbiter fixes this by enforcing shift-first sequencing at Tier 1.

---

## 1. Existing capabilities — what's already built

### 1.1 `find_new_strike()` — premium-target-aware strike search

**File**: [mmm_strike_shift.py:193-372](../../../webui/backend/routes/mmm/mmm_strike_shift.py#L193)
**Signature**: `find_new_strike(initializer, session, side, spot_price, min_otm_distance=0.0) → Optional[Dict]`
**Returns**: `{'strike': X, 'premium': Y, 'symbol': Z, 'distance_from_spot': D, 'is_frozen_strike': bool}` or `None`

Already implements:
- ✅ Reads `shift_target_premium` (default $100) from session params at line 358
- ✅ Sorts candidates by `abs(premium - target_premium)` at line 360 — picks the strike whose premium is closest to target
- ✅ Enforces `shift_threshold` floor (line 217) — ignores strikes below threshold
- ✅ Respects ATM Shield via `min_otm_distance` parameter (lines 282-286)
- ✅ Two-pass scan: prefers non-frozen strikes, falls back to frozen if needed (lines 311-318)
- ✅ Side-aware: `'ce'` or `'pe'`, returns OTM strike on the requested side
- ✅ Uses mark_price as primary premium signal, falls back to mid (bid+ask)/2 (lines 263-270)
- ✅ Skips current active strike (line 289)
- ✅ Diagnostic logging when no candidate found (lines 327-352)

**Gap for Tier 1 use**: does NOT use `shift_premium_tolerance`. Sorts by proximity but has no "reject candidates outside band" filter. Acceptable for Tier 1 — arbiter can validate the returned premium is within tolerance after the call.

### 1.2 `calculate_lots_to_sell()` — premium-aware lot sizing

**File**: [mmm_engine.py:380-end](../../../webui/backend/routes/mmm/mmm_engine.py#L380)
**Signature**: `calculate_lots_to_sell(session, hedge_side, loss_to_cover, hedge_premium) → Tuple[int, str, bool]`
**Returns**: `(lots_to_sell, constraint_message, is_position_cap_hit)`

Core formula (line 416):
```python
raw_lots = loss_to_cover / (hedge_premium * LOT_SIZE_BTC) * (1 + buffer_pct)
```

Already includes:
- ✅ Premium-per-lot scaling: `hedge_premium` directly inverse-scales lot count → higher premium = fewer lots
- ✅ Premium buffer: `premium_buffer_pct` (default 5%) for safety margin
- ✅ Gamma-aware multiplier (T3-2) — scales lots by aggressor excess_pct (1.1× / 1.2× / 1.3×)
- ✅ **Breakeven multiplier** (lines 452-461) — reads `_breakeven_multiplier` from session, scales lots in DANGER/CRITICAL zones
- ✅ Gamma severity multiplier (WARNING / DANGER zones)
- ✅ Position cap enforcement (`max_lots_per_side`)
- ✅ Edge cases: returns 0 if `hedge_premium <= 0` or `loss_to_cover <= 0`

This function is **the right primitive** for Tier 1 lot sizing. No changes needed.

### 1.3 `pre_scan_shift_candidates()` — pre-computed shift candidates

**File**: [mmm_strike_shift.py:510](../../../webui/backend/routes/mmm/mmm_strike_shift.py#L510)
Pre-scans both sides during heartbeat, caches candidate strike + target premium per side. Arbiter can read these without re-scanning the chain.

### 1.4 `activate_new_strike()` — execute the shift

**File**: [mmm_strike_shift.py:375](../../../webui/backend/routes/mmm/mmm_strike_shift.py#L375)
Updates session state to point to the new active strike, freezes old positions, etc.

---

## 2. Why the current bug (cheap-policy pile-up) happens despite these building blocks

The screenshot scenario (mmm28apr26-1, 2026-04-27):
- PE 77000: 50 lots @ $211 entry, mark $499 (in distress)
- CE 78800: 150 lots @ $56 entry, mark $44 (cheap policies accumulated)

The algo's normal adjustment path:
1. Trigger fires → adjustment engine activates
2. Computes `loss_to_cover` from PE side
3. Calls `calculate_lots_to_sell('ce', loss_to_cover, hedge_premium=$44)` — **at the existing CE strike's decayed premium**
4. Math: low hedge_premium → high lot count → 50 forced CE lots written

`calculate_lots_to_sell` math is **correct** — to "cover" loss with $44 premium, you need many lots. The bug is **the order of operations**:

```
WRONG (current):  trigger → calculate_lots(at existing strike) → sell N lots at $44
RIGHT (Tier 1):   trigger → find_new_strike(target=$100) → shift → calculate_lots(at new strike) → sell N/2 lots at $100
```

The shift module fires **independently** from the adjustment engine, on its own threshold (`shift_threshold_pct`). Whether shift fires *before* or *after* a defensive adjustment is not coordinated. In the screenshot's case, the shift didn't fire because spot hadn't crossed `shift_threshold_pct` yet — but the breakeven was already CRITICAL. The two modules made independent decisions; the result is cheap-policy accumulation.

**This is exactly the coordination problem the arbiter is designed to fix.**

---

## 3. Phase 3 arbiter Tier 1 logic — design

The arbiter at Tier 1 (breakeven CRITICAL fires) executes this sequence as **one atomic decision**:

```python
def arbiter_tier1_action(session, threatened_side):
    """
    Tier 1 defensive action: shift opposite side to target-premium strike,
    then sell minimum lots needed.
    Returns (action_dict) or None if no action possible.
    """
    opposite_side = 'pe' if threatened_side == 'ce' else 'ce'

    # 1. Compute loss to cover (unrealized loss on threatened side)
    loss_to_cover = compute_unrealized_loss(session, threatened_side)
    if loss_to_cover <= 0:
        return None

    # 2. Check current opposite-side strike — is it still at target premium?
    current_premium = current_premium_at_active_strike(session, opposite_side)
    target = params.get('shift_target_premium', 100.0)
    tolerance = params.get('shift_premium_tolerance', 10.0)

    if abs(current_premium - target) <= tolerance:
        # Existing strike is still good — sell at current strike
        new_strike = session[opposite_side]['active_strike']
        hedge_premium = current_premium
        action_type = 'sell_at_current'
    else:
        # Existing strike has drifted — shift first
        spot = session.get('_regime_spot_price', 0)
        atm_shield_dist = compute_atm_shield_distance(session)  # respect Tier 0
        candidate = find_new_strike(
            initializer, session, opposite_side, spot,
            min_otm_distance=atm_shield_dist
        )
        if not candidate:
            return None  # no viable strike — bot signals operator
        new_strike = candidate['strike']
        hedge_premium = candidate['premium']
        action_type = 'shift_and_sell'

    # 3. Compute lots at the chosen strike's premium
    lots, constraint_msg, _ = engine.calculate_lots_to_sell(
        session, opposite_side, loss_to_cover, hedge_premium
    )
    if lots <= 0:
        return None

    return {
        'type': action_type,
        'side': opposite_side,
        'strike': new_strike,
        'premium': hedge_premium,
        'lots': lots,
        'reason': 'TIER_1_DEFENSIVE_SHIFT',
        'constraint': constraint_msg,
    }
```

**~40 lines, pure orchestration.** All four primitives already exist. No new math.

The action is then executed by reusing the existing shift+sell pipeline:
- If `action_type == 'shift_and_sell'`: call `freeze_current_positions` + `activate_new_strike` + sell
- If `action_type == 'sell_at_current'`: just sell

---

## 4. Settings already in place

User's existing parameters fully cover Tier 1's needs:

| Param | Default | Purpose |
|---|---|---|
| `shift_target_premium` | 100.0 | Target premium per lot when shifting/defending |
| `shift_premium_tolerance` | 10.0 | Acceptance band around target |
| `shift_threshold` | 50.0 | Floor — ignore strikes below this premium |
| `premium_buffer_pct` | 0.05 | 5% safety margin on lot count |
| `max_lots_per_side` | 100 | Hard cap on per-side position |

No new settings needed for Phase 3. The arbiter reads these existing params.

---

## 5. ATM Shield interaction

`find_new_strike` accepts `min_otm_distance` parameter (line 198) — caller can pass the ATM shield's safety distance to enforce the boundary. The arbiter at Tier 1 will:

1. Read `_atm_shield_distance` from session (when ATM shield is enabled)
2. Pass it as `min_otm_distance` to `find_new_strike`
3. If ATM shield blocks all viable candidates, arbiter returns `None` and falls back to (per Rule 1) hard stop / operator action — Tier 0 is never bypassed.

This satisfies Rule 1 (Tier 0 absolute) automatically through the existing parameter.

---

## 6. STRADDLE_WITH_ADJUSTMENT compatibility

For STRADDLE_WITH_ADJUSTMENT, ATM shield is bypassed (positions are ATM by design — see Phase 2 / D6 + Task 3 audit). The arbiter Tier 1 logic must respect this:

```python
if session.get('params', {}).get('strategy_type') == 'STRADDLE_WITH_ADJUSTMENT':
    atm_shield_dist = 0.0  # ATM shield bypassed for straddle
else:
    atm_shield_dist = compute_atm_shield_distance(session)
```

This is the same logic already in place elsewhere in the codebase. Arbiter inherits it.

---

## 7. What COULD go wrong — known edge cases

### 7.1 No viable strike (chain illiquid, near expiry)
`find_new_strike` returns `None`. Arbiter returns `None`. No defensive action this beat. **Acceptable** — operator sees the audit log and can intervene. Tier 0 (hard stop) is the safety net per Rule 1.

### 7.2 Margin RED + Tier 1 simultaneously
Per Phase 2 / B2: in margin RED, only margin-recovery moves allowed. Arbiter Tier 1 logic must check this:
```python
if session.get('_margin_tier') == 'RED':
    # Skip new sells; trigger buyback of cheap OTM on fat side instead
    return arbiter_margin_recovery_action(session)
```
Also pure orchestration; primitives exist (close-at-5 pipeline can be invoked for buyback).

### 7.3 Last 30 min before expiry
Per Phase 2 / D5 (Rule 5): no Tier 1 bypass in last 30 min. Arbiter checks `minutes_to_expiry` at the top:
```python
if session.get('_minutes_to_expiry', 999) <= 30:
    return None  # Tier 1 disabled — operational modules run as designed
```

### 7.4 Stale `_breakeven_zone`
Per Phase 2 / G1 (Rule 6): treat stale as escalated. Arbiter checks signal timestamp:
```python
if signal_age_beats(session, '_breakeven_zone') > 1:
    log_stale_event(...)
    # Treat zone as escalated for arbiter purposes
```
This requires Task 5 (stale-detection) to add timestamps to relevant signals.

---

## 8. Phase 3 candidate list (additions)

- **C5**: Implement `arbiter_tier1_action()` orchestrator (~40 lines) — see §3 above
- **C6**: Implement `arbiter_margin_recovery_action()` for Tier 1 ∩ margin RED case
- **C7**: Wire arbiter into `mmm_monitor.py` heartbeat at the right point (TBD by gate map in Task 1)
- **C8**: Add sealed test: `test_arbiter_tier1_premium_aware_shift` — given breakeven CRITICAL on PE side and CE strike at decayed $44 premium, arbiter must produce a SHIFT decision (not sell-more-cheap-lots)
- **C9**: Add sealed test: `test_arbiter_respects_atm_shield` — Tier 1 active + ATM shield enabled → returned strike respects min_otm_distance

---

## 9. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `find_new_strike` returns a strike that's too close to spot | Low | ATM shield (Tier 0) enforces min distance via existing parameter |
| `calculate_lots_to_sell` over-multiplies (gamma + breakeven combined) | Low | Existing `max_lots_per_side` cap. T3-2 caps gamma_mult at 1.3 (line 430). Breakeven multiplier capped at 3.0 by `breakeven_aggression_max`. Combined max ~4×. With $100 premium and small loss, output stays reasonable. |
| Multiple Tier 1 fires per beat (BE flips between sides) | Medium | Arbiter is called once per beat; if zone flips mid-beat, next beat sees the new state. 5-min interval limits flap rate. |
| `pre_scan_shift_candidates` pre-cache is stale | Low | Cache invalidates on `_chain_data` change. Arbiter can call `find_new_strike` directly to bypass cache if needed. |

All risks are mitigatable with existing infrastructure.

---

## 10. Verdict

**Feasibility: HIGH.** Phase 3 arbiter Tier 1 logic is ~40-line orchestration over four mature, well-tested primitives. The math is right; the gap is sequencing. The arbiter fixes sequencing.
