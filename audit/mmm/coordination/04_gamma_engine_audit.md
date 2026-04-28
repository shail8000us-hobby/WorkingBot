# Phase 1 — Task 2: Gamma Engine Audit

**Status**: Complete
**Date**: 2026-04-27
**Auditor**: Claude
**Scope**: Verify user's stated dissatisfaction with gamma engine. Specifically: DTE-awareness, lot-size-awareness, and whether gamma EMERGENCY produces "noise" or genuine action. Determine whether engine needs redesign or just better wiring.

---

## TL;DR

User's complaints are **partially validated**:

| Complaint | Verdict | Severity |
|---|---|---|
| Not DTE-aware enough | ✅ **CONFIRMED** — engine has only two DTE bands (≤30 min tightening, ≤2 hr hedge relax). Anything from 2+ hours to 5+ days uses identical baseline limits. | HIGH |
| Not position-size-aware enough | ❌ **PARTIALLY WRONG** — lot scaling exists at lines 244-261 of `mmm_gamma.py` and is mathematically correct. But it scales by `max(ce, pe)`, not aggregate. | MEDIUM (cosmetic, not structural) |
| EMERGENCY produces noise (PAUSE), not action | ✅ **CONFIRMED** — `regime_action == FORCE_REDUCE` only PAUSEs the session (line 2940). Does not trigger defensive close. | HIGH |
| Engine fires unnecessarily in last 30 min | ✅ **CONFIRMED** — 0.5x tightening multiplied by structurally-rising end-of-day gamma makes EMERGENCY near-certain for any straddle position. | HIGH |

**Verdict**: the gamma engine does not need a full rewrite. It needs **two structural fixes**:

1. **Add a DTE-relax tier for far-from-expiry sessions** (2-7 DTE), since 5-DTE structurally has low gamma.
2. **Convert EMERGENCY action from PAUSE to a defensive-close routine** — coordinated by the Phase 3 arbiter so it composes with Tier 1 logic.

These can be done as part of Phase 3 alongside the arbiter. No standalone gamma rewrite needed.

---

## 1. Lot-size awareness — validated, but with a nuance

### What's already in place

**Two-stage scaling**:

**Stage A (session creation)** in [mmm_state.py:1041-1059](../../../webui/backend/routes/mmm/mmm_state.py#L1041-L1059):
```python
_GAMMA_LOT_FACTOR = 250  # $250 dollar-gamma allowance per initial lot at soft limit
merged_params['gamma_soft_limit']      = float(_initial_lots * 250)   # = 2500 for 10 lots
merged_params['gamma_hard_limit']      = float(_initial_lots * 500)   # = 5000 for 10 lots
merged_params['gamma_emergency_limit'] = float(_initial_lots * 1000)  # = 10000 for 10 lots
```

So if user starts with `initial_lots=10`, limits = 2500/5000/10000.
If user starts with `initial_lots=50`, limits = 12500/25000/50000.

**Stage B (every heartbeat)** in [mmm_gamma.py:244-261](../../../webui/backend/routes/mmm/mmm_gamma.py#L244-L261):
```python
_initial_lots = max(int(params.get('initial_lots', 10)), 1)
_ce_lots = session.get('ce', {}).get('active_lots', 0)
_pe_lots = session.get('pe', {}).get('active_lots', 0)
_effective_lots = max(_initial_lots, _ce_lots, _pe_lots)
if _effective_lots > _initial_lots:
    _lot_scale = _effective_lots / _initial_lots
    soft_limit *= _lot_scale
    hard_limit *= _lot_scale
    emergency_limit *= _lot_scale
```

So if harvester grew the book from 10 to 100 lots: `_lot_scale = 10x`, all limits multiplied by 10.

### Why the user perceives this as "not enough"

The lot scaling is mathematically correct. The reason it *feels* wrong is a **timing / proportionality interaction**, not the lot scaling itself:

- `dollar_gamma = portfolio_gamma × spot² × 0.01`
- `portfolio_gamma` scales **linearly** with lot count (sum of γ_per_contract × lots)
- Limits scale **linearly** with lot count

These cancel. So lot scaling alone is fine. **What changes is gamma per contract over time**:

| Time to expiry | γ per ATM contract (rough) |
|---|---|
| 5 days | ~0.0005 |
| 1 day | ~0.002 |
| 4 hours | ~0.005 |
| 1 hour | ~0.015 |
| 15 minutes | ~0.05 |

So `dollar_gamma` rises 100× from 5-DTE to last 15 min, while limits stay constant. The lot-scaling fix doesn't help here — only DTE-awareness does. The user attributed this to "lot-size awareness" because they observed it after harvester grew lots, but the actual driver was **time progression**, not lot count.

### Edge case worth noting

`_effective_lots = max(initial, ce, pe)` uses the larger side. If CE=100, PE=10:
- `max` = 100
- Scale = 10×

This is generous: the limits scale up as if both sides were 100. The PE side gets a free pass on this scaling. **In practice** this is safe because dollar_gamma is computed from the actual position (sum across both sides), so smaller PE contributes less. The scaling just gives more headroom — favoring "don't fire EMERGENCY too easily," which aligns with user intent.

**Verdict**: lot scaling is correctly implemented. User's complaint here is misattributed.

---

## 2. DTE awareness — confirmed gap

### What's already in place

[mmm_gamma.py:266-286](../../../webui/backend/routes/mmm/mmm_gamma.py#L266-L286) implements TWO DTE-aware behaviours:

**A. Near-expiry tightening (last 30 min)** — lines 266-270:
```python
if minutes_to_expiry is not None and minutes_to_expiry <= 30:
    multiplier = params.get('gamma_near_expiry_multiplier', 0.5)
    soft_limit *= multiplier
    hard_limit *= multiplier
    emergency_limit *= multiplier
```

All limits halved in last 30 minutes. **Combined with naturally-rising end-of-day gamma, this makes EMERGENCY almost inevitable for any straddle.**

**B. Hedge limit relaxation (last 2 hours)** — lines 278-286:
```python
if dte_relax_hours > 0 and minutes_to_expiry is not None and minutes_to_expiry <= dte_relax_hours * 60:
    hard_limit_hedge = hard_limit * dte_hedge_mult   # 2.0×
```

Only the **hedge** limit (used by `check_projected_gamma`) is relaxed. The HARD/EMERGENCY regime labels still use the tightened limits. This means: a hedge sell can be allowed by `check_projected_gamma`, but the regime label still says HARD/EMERGENCY and downstream actions (FORCE_REDUCE → PAUSE) still fire.

### What's missing — confirmed by user complaint

There is **NO DTE relaxation for sessions further than 2 hours from expiry**.

| DTE | Limit treatment |
|---|---|
| 5 days | Baseline limits (no DTE adjustment) |
| 1 day | Baseline limits |
| 6 hours | Baseline limits |
| 2 hours | Hedge limit relaxed 2×, regime labels unchanged |
| 30 min | All limits TIGHTENED 0.5× |

So a 5-DTE position with structurally low γ_per_contract uses identical limits to a 2-hour position. This matches user's exact complaint:

> "5-DTE position has structurally low gamma; engine should be relaxed there. 0-DTE is where gamma actually matters."

### Why this is structurally wrong

For 5-DTE, dollar_gamma will naturally be very low because γ_per_contract is small. So even with default limits (2500/5000/10000), 5-DTE rarely hits EMERGENCY *in practice*. The complaint is partially academic — but it manifests when lots grow large via harvester. With 100 lots at 5-DTE, dollar_gamma might still cross hard_limit before lot scaling kicks in (depending on session creation params vs runtime lots).

**More importantly**: user explicitly wants the engine to be **DTE-aware in both directions** — relaxed at 5-DTE, tight at 0-DTE. The current engine is only tight at 0-DTE; it's neutral elsewhere. There's no "this is a 5-DTE session, relax everything proportionally" tier.

### Phase 3 fix proposal — DTE relax ladder

Replace the binary "≤30 min / ≤2 hr / else" logic with a graduated scale:

| Bucket | Effect on limits |
|---|---|
| > 5 days | 1.5× (relax — gamma low) |
| 1-5 days | 1.25× (light relax) |
| 4 hr - 1 day | 1.0× (baseline) |
| 30 min - 4 hr | 1.0× hedge-relaxed (current behaviour) |
| < 30 min | 0.5× (current tighten) |

These exact multipliers are tunable; the structure is the goal. User's hierarchy Rule 5 says last 30 min must keep tightening; we preserve that.

---

## 3. EMERGENCY action — confirmed produces noise

### What happens today when gamma EMERGENCY fires

Trace from session-state to user-visible effect:

1. **`_update_gamma_cap`** sets `_gamma_regime = 'EMERGENCY'` ([mmm_gamma.py:289-290](../../../webui/backend/routes/mmm/mmm_gamma.py#L289-L290))
2. **`_compute_regime_action`** maps to `ACTION_FORCE_REDUCE` ([mmm_regime.py:668-669](../../../webui/backend/routes/mmm/mmm_regime.py#L668-L669))
3. **Monitor handles FORCE_REDUCE** ([mmm_monitor.py:2912-2941](../../../webui/backend/routes/mmm/mmm_monitor.py#L2912-L2941)):
   - For STRADDLE_WITH_ADJUSTMENT: bypassed (correct — straddles are structurally high-γ at ATM)
   - For dangerous_mode: bypassed
   - **For everything else**: `self.pause('Gamma emergency — manual review required')` and `_skip_to_pnl = True`

So the action is: **PAUSE the session and emit safety alert**. No close, no shift, no trim. Just stop and wait for operator.

### What user wants instead

Per Phase 2 / B3:
> "Allow defensive closes (reduce lot count to lower gamma). Allow strike shift (move to lower-gamma strikes). Block new sells that would increase gamma further."

The current PAUSE behaviour does the OPPOSITE of "defensive close" — it stops everything including the closes that would naturally reduce gamma.

### Why this is the noise source

Combine with #2 above: in last 30 min of any expiry day, gamma will likely cross EMERGENCY (because of 0.5× tightening + naturally rising γ). This pauses the session right when:
- Operator is least available (they think the day is done)
- Position should be naturally winding down via close-at-5
- ATM shield handles real ATM crossings
- Hard stop catches losses

The PAUSE just adds friction. Not safety.

### Phase 3 fix — EMERGENCY becomes a defensive-action trigger

Per Phase 2 hierarchy Rule 2 (Tier 1 acts), when gamma EMERGENCY fires:

```
if gamma_regime == EMERGENCY:
    # OLD: pause session
    # NEW: arbiter Tier 1 action — defensive close + strike shift
    arbiter.tier1_gamma_emergency_action(session):
        - Identify which side has higher dollar-gamma (CE vs PE)
        - Close N lots on that side (smallest cap_close lots) until gamma drops below HARD limit
        - If gamma still EMERGENCY after closes, shift the dominant side to a strike with
          lower per-contract gamma (further OTM)
        - Block any new sells that would re-increase gamma
        - Do NOT pause the session; stay running so close-at-5 + ATM shield + hard stop continue
```

This composes cleanly with the broader arbiter. EMERGENCY becomes one of several Tier 1 triggers, all routing into the same "Tier 1 acts" doctrine.

**Important per Phase 2 / D5 (Rule 5)**: in the last 30 min, Tier 1 bypass is DISABLED — meaning even gamma EMERGENCY in last 30 min should NOT trigger arbiter intervention. Operational gates run normally; hard stop + ATM shield + auto-close handle disasters. So the PAUSE behaviour at gamma EMERGENCY in last 30 min is, ironically, **already wrong twice**: too aggressive (pauses unnecessarily) AND not aggressive enough (doesn't actually reduce gamma).

---

## 4. STRADDLE_WITH_ADJUSTMENT bypass — correct

[mmm_monitor.py:2913](../../../webui/backend/routes/mmm/mmm_monitor.py#L2913) bypasses FORCE_REDUCE for STRADDLE_WITH_ADJUSTMENT. This is correct: a straddle is structurally always at-money, and gamma is structurally elevated. Pausing the adjustment IS the danger, not the protection.

This bypass should remain. Phase 3 arbiter respects strategy-specific overrides per Phase 2 / D6.

---

## 5. GAMMA_HARD action — separate, more nuanced

The HARD level (one tier below EMERGENCY) does NOT pause. It produces directional blocks via `_compute_regime_action` ([mmm_regime.py:724-774](../../../webui/backend/routes/mmm/mmm_regime.py#L724-L774)):

- Step 1: anchor-relative direction → block aggressor side
- Step 2: per-side gamma imbalance → block dominant side
- Step 3: DTE relax tiebreaker
- Step 4: fallback BLOCK_ALL_SELLS

This is reasonable behaviour at HARD. The complaint was specifically about EMERGENCY. HARD is fine as-is.

---

## 6. Coordination gaps with the arbiter

Items the arbiter must coordinate:

### Gap A — Gamma EMERGENCY at Tier 1
Arbiter Rule 2 says gamma EMERGENCY → defensive action. Implementation:
1. Compute target reduction (gamma overshoot above EMERGENCY threshold)
2. Identify dominant side (`max(ce_dollar_gamma, pe_dollar_gamma)`)
3. Close lots on dominant side (call existing close infrastructure) until gamma < HARD limit
4. If still EMERGENCY: shift dominant side further OTM
5. Block any new sells that would *increase* gamma

### Gap B — DTE relax ladder
Add a graduated DTE relaxation in `_update_gamma_cap` (NOT an arbiter responsibility — gamma engine internal). Phase 3 task adds this to gamma.py, params drive the curve.

### Gap C — Last-30-min behaviour
Per Rule 5, arbiter is no-op in last 30 min. Gamma EMERGENCY's PAUSE behaviour also gets in the way of natural wind-down. Phase 3 should:
- Keep current 0.5× tightening (informational regime label still useful)
- BUT remove the PAUSE side-effect — let close-at-5 + ATM shield + hard stop work
- This is consistent with "all safety features should work as designed in last 30 min" — the gamma engine's job at expiry is to LABEL danger, not to halt the session

### Gap D — Stale data
`_gamma_regime` and `_portfolio_dollar_gamma` are set every beat by `_update_gamma_cap`. No timestamp. Task 5 (next) will plan stale-detection. Treat stale `_gamma_regime` per Rule 6.

---

## 7. Phase 3 Candidate List (additions)

- **C15**: Add DTE relax ladder to `_update_gamma_cap` (graduated multipliers for >2-hr DTE buckets). Estimated 15 lines.
- **C16**: Implement `arbiter_gamma_emergency_action()` — defensive close + shift, no pause. Reuses existing `find_new_strike` and close infrastructure (~30 lines). Wire from arbiter Tier 1.
- **C17**: Remove the `self.pause('Gamma emergency')` side-effect in [mmm_monitor.py:2940](../../../webui/backend/routes/mmm/mmm_monitor.py#L2940) IF arbiter Tier 1 is active for this beat (i.e., not in last 30 min, not bypassed by strategy). Conditional disable.
- **C18**: Add sealed test `test_arbiter_gamma_emergency_defensive_close` — given gamma EMERGENCY on PE side and breakeven SAFE, arbiter must close PE lots, not pause session.
- **C19**: Add sealed test `test_gamma_engine_dte_relax_at_5dte` — given 5-DTE session and same dollar_gamma, regime should be one tier lower than at 1-DTE.
- **C20**: Add `_gamma_last_updated_ts` write at end of `_update_gamma_cap` (for Rule 6).

---

## 8. Verdict

User's perception of the gamma engine has merit but is partially misattributed:

- **Lot-size complaint**: misattributed. Lot scaling IS implemented and correct. The visible problem was time-driven gamma rise, not lot growth.
- **DTE complaint**: structurally correct. Engine has only 2 DTE bands; 5-DTE is treated like 2-hour DTE. **Real gap.**
- **EMERGENCY = noise complaint**: structurally correct. PAUSE is the wrong response. Should be defensive close. **Real gap.**
- **Last-30-min over-firing**: real and confirmed. Driven by 0.5× tightening + naturally rising γ + PAUSE response. Triple-wrong.

**No full rewrite needed.** Two surgical changes (DTE ladder in gamma.py + EMERGENCY-as-action in arbiter) plus the broader arbiter solve all four user-perceived issues. Total estimated Phase 3 work for gamma items: ~60 lines + 2 sealed tests.
