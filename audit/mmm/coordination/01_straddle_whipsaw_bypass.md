# Phase 1 — Task 3: STRADDLE_WITH_ADJUSTMENT Whipsaw Bypass Investigation

**Status**: Complete
**Date**: 2026-04-27
**Auditor**: Claude
**Scope**: Determine why `mmm_whipsaw_smart.py:697-701` bypasses smart whipsaw for STRADDLE_WITH_ADJUSTMENT, whether the bypass aligns with user intent, and what change is needed in Phase 3.

---

## TL;DR

The bypass is **partially wrong, partially correct**. It bypasses too much.

| Bypass | Correctness | Action |
|---|---|---|
| `trigger_widen_factor = 1.0` | ✅ CORRECT — sound trading rationale | **Keep** |
| `lot_scalar = 1.0` | ✅ CORRECT — sound trading rationale | **Keep** |
| `block = False` | ❌ WRONG — user wants smart whipsaw to BLOCK | **Remove** |
| Skip token budget (lines 707–711) | ❌ WRONG — user wants over-adjustment prevention | **Remove** |

A surgical fix in Phase 3 will preserve the protections that make sense for a straddle (no widening, no lot reduction) while restoring the protections the user explicitly asked for (block on true whipsaw + token budget).

---

## 1. Origin

- **Commit**: `57868541af` ("h" — quick wip commit) by `physicsssr` on 2026-04-20 01:28:33 +0530
- **File touched**: `webui/backend/routes/mmm/mmm_whipsaw_smart.py`
- **Lines added**: 697–701
- **Refined later**: commit `a098486a31` (same day, 11:32:33) added comment + extended bypass to token budget (lines 707–711)

Both commits are by the user themselves. The bypass was a deliberate decision, not an accident.

---

## 2. Documented rationale

### 2.1 The "§0 rule 6" reference

The inline comment cites "§0 rule 6". This refers to [mmm_whipsaw_implementation.md:18](../../../mmm_whipsaw_implementation.md#L18):

> **6. No cross-strategy bleed.** `STRADDLE_WITH_ADJUSTMENT` already bypasses legacy whipsaw widening/lot-reduction in `mmm_monitor.py:3356-3363` and `mmm_monitor.py:4918-4929`. The Smart engine must honor the same bypass (gate via `STRATEGY_DISPATCH` flag), not re-introduce the cross-strategy bug.

This rule established **parity with legacy whipsaw bypass**. The smart engine inherited the legacy bypass without re-evaluating whether all of legacy's behaviour was problematic, or only some.

### 2.2 The original (legacy) rationale — the actual trading reasons

Two distinct rationales are documented in monitor comments:

**(a) Trigger widening hurts straddles** — [mmm_monitor.py:3550-3552](../../../webui/backend/routes/mmm/mmm_monitor.py#L3550-L3552)

> "STRADDLE_WITH_ADJUSTMENT: bypassed — whipsaw widens triggers, meaning adjustments fire less often. For straddle, under-adjusting in a whipsaw market compounds the loss on both legs simultaneously."

**(b) Lot reduction hurts straddles** — [mmm_monitor.py:5129-5131](../../../webui/backend/routes/mmm/mmm_monitor.py#L5129-L5131)

> "STRADDLE_WITH_ADJUSTMENT: bypassed — whipsaw conditions in a straddle mean price is bouncing, exactly when both legs need full-size hedging. Halving lots leaves the straddle systematically under-hedged."

Both rationales are **trader-sound and remain valid**. A short straddle has both legs exposed simultaneously; making adjustments less frequent or smaller = more accumulated loss.

### 2.3 What the original rationale does NOT cover

Notably absent from the documented rationale:
- ❌ No reason given for bypassing `block` outright
- ❌ No reason given for bypassing token budget

Reading the code chronologically: legacy whipsaw's bypass was implemented as scalar overrides only (trigger_widen_factor + lot_scalar). When the smart engine was built, `block = False` and token-budget skip were added by **copy-paste extension** — not because trader logic justified them, but because the parity rule said "honor the same bypass."

The smart engine's `block` and `token budget` are NEW features that did not exist in legacy. Mechanically extending the bypass to them was an over-application of the parity rule.

---

## 3. User's stated intent (2026-04-27)

Quoting from Phase 2 / Batch D6:

> "We should use the smart whipsaw — that's a good feature because it protects us from unnecessary increase in position on both sides. Hard stop and smart whipsaw, they are the good combo."

"Unnecessary increase in position" maps directly to:
- **Block** decision (when LOCKDOWN/OBSERVE mode fires, no new sells — exactly the "don't pile on" protection)
- **Token budget** (per-session adjustment cap — prevents runaway over-adjustment within the day)

Neither of these conflicts with the original trader rationale (a) and (b). They protect the straddle from a different failure mode — over-trading — that the scalar bypasses do not address.

---

## 4. Why both the old rationale AND the new intent are correct

The two views appear contradictory but are not. They address different failure modes:

| Failure mode | Bypass needed? | Rationale |
|---|---|---|
| Under-adjusting (trigger widening) | YES bypass | Both straddle legs accumulate loss when adjustments fire late |
| Under-hedging (lot reduction) | YES bypass | Both legs need full-size hedging when price is bouncing through ATM |
| Over-adjusting (token budget) | NO bypass | If both legs flip aggressors many times in a session, write-rate exceeds safe levels — token budget caps it |
| Pile-on during LOCKDOWN (block) | NO bypass | When score is genuinely high (≥0.80), the market is in extreme whipsaw — even a straddle should pause and let conditions clarify rather than write more contracts on both sides |

The original rationale prevents *under*-response. The user's new intent prevents *over*-response. **Both are protections; they don't conflict.** The blanket bypass conflated them.

---

## 5. Existing test coverage

Only one test exercises this code path:

**`test_straddle_bypass`** in [test_mmm_whipsaw_legacy_parity.py:222-233](../../../webui/backend/routes/mmm/tests/test_mmm_whipsaw_legacy_parity.py#L222-L233):

```python
def test_straddle_bypass():
    session = _make_session(_whipsaw_score=10)
    session['params']['strategy_type'] = 'STRADDLE_WITH_ADJUSTMENT'

    decision = LegacyWhipsawEngine().evaluate(session, _ctx())

    assert decision.trigger_widen_factor == 1.0
    assert decision.lot_scalar == 1.0
```

**Critical observation**: this test
- Tests **LegacyWhipsawEngine**, not SmartWhipsawEngine
- Asserts only the two scalar bypasses (`trigger_widen_factor`, `lot_scalar`)
- Does **NOT** assert `block == False`

Therefore: removing `block = False` and the token-budget skip from `mmm_whipsaw_smart.py:697-711` will not break this test. Surgical fix is safe.

No sealed test currently asserts that smart whipsaw must NOT block in straddle mode. Sealed test count baseline (1688) is preserved.

---

## 6. Phase 3 candidate fix

**File**: `webui/backend/routes/mmm/mmm_whipsaw_smart.py`
**Current** (lines 697–711):

```python
# STRADDLE_WITH_ADJUSTMENT bypass (§0 rule 6) — overrides all smart limits
if is_straddle_adj:
    trigger_widen_factor = 1.0
    lot_scalar = 1.0
    block = False

# ── Step 5: token budget ────────────────────────────────────────────
budget = _load_budget(session, tokens_init, refresh_per_hour=refresh_rate, interval_mins=interval_mins)
recent_is_flip = flip_sc > 0.05
token_cost = budget.cost_for_mode(mode, is_flip=recent_is_flip)
if is_straddle_adj:
    # STRADDLE bypass also skips token spend — token budget must not
    # override the §0 rule 6 invariant that gamma never blocks adjustment.
    # No spend, no credit — _load_budget already applied the beat drip.
    pass
elif not block and not budget.spend(token_cost):
```

**Proposed** (Phase 3, NOT applied in Phase 1):

```python
# STRADDLE_WITH_ADJUSTMENT — surgical bypass (Phase 3 ARBITER refinement, 2026-04-27).
# Original §0 rule 6 in mmm_whipsaw_implementation.md was over-applied: it bypassed
# block + token budget which the user actually wants ACTIVE for over-adjustment
# protection. Trader rationale (mmm_monitor.py:3550-3552, 5129-5131) only covers
# trigger_widen_factor + lot_scalar — those bypasses remain.
if is_straddle_adj:
    trigger_widen_factor = 1.0   # bypass: under-adjustment compounds straddle loss
    lot_scalar = 1.0             # bypass: under-hedging leaves straddle exposed
    # block intentionally NOT forced False — let LOCKDOWN/OBSERVE block protect
    # against runaway over-adjustment on both sides (user intent 2026-04-27, Batch D6)

# ── Step 5: token budget ────────────────────────────────────────────
budget = _load_budget(session, tokens_init, refresh_per_hour=refresh_rate, interval_mins=interval_mins)
recent_is_flip = flip_sc > 0.05
token_cost = budget.cost_for_mode(mode, is_flip=recent_is_flip)
# Token budget enforced for ALL strategies including STRADDLE — caps per-session
# adjustment count to prevent runaway over-adjustment.
if not block and not budget.spend(token_cost):
    block = True
    events.append({...})
elif block:
    budget.credit_patience()
```

**New sealed test required** (Phase 3):

```python
def test_smart_whipsaw_straddle_block_active():
    """STRADDLE_WITH_ADJUSTMENT: smart whipsaw can still BLOCK at LOCKDOWN/OBSERVE.
    User intent 2026-04-27: smart whipsaw protects from over-adjustment on both
    sides. Only scalar bypasses (widen/lot) are honored; block is not."""
    session = _make_session()
    session['params']['strategy_type'] = 'STRADDLE_WITH_ADJUSTMENT'
    # Force composite score into LOCKDOWN range
    ...
    decision = SmartWhipsawEngine().evaluate(session, _ctx())
    assert decision.trigger_widen_factor == 1.0  # bypass preserved
    assert decision.lot_scalar == 1.0            # bypass preserved
    assert decision.block_adjustment is True     # block ACTIVE
    assert decision.mode == 'LOCKDOWN'
```

---

## 7. Documentation updates needed (Phase 3)

When applying the fix:

1. **Update `mmm_whipsaw_implementation.md` §0 rule 6**: clarify that bypass is scalar-only, not blanket. Block + token budget remain active.
2. **Update memory `feedback_straddle_gamma_bypass.md`**: currently only documents gamma bypass; add note that smart whipsaw scalar-bypass is correct but block-bypass was wrong.
3. **Update `MMM_LAST_3_SESSIONS.md`**: log the change as a bug fix derived from coordination plan Phase 1.

---

## 8. Risk assessment for the proposed fix

| Risk | Severity | Mitigation |
|---|---|---|
| Smart whipsaw blocks during legitimate straddle adjustment need | Medium | Block only fires at score ≥ 0.60 (OBSERVE) or ≥ 0.80 (LOCKDOWN). For straddle, this means genuine extreme whipsaw — pausing is correct. |
| Token budget exhausts before session end in long straddle session | Low | `tokens_per_session` default = 10.0 with refresh drip = 1.0/hr. For a 6-hr session, ~16 adjustment-equivalents available. Aligns with normal straddle frequency. |
| Tier 1 defensive shift bypassed because token budget exhausted | None | Tier 1 bypasses smart whipsaw entirely (see Rule 2 of sealed hierarchy). Token budget does not gate Tier 1. |

Fix is safe within the sealed hierarchy framework.

---

## 9. Appended to: Phase 3 candidate list

This becomes a Phase 3 implementation task, executed alongside the arbiter build:

- **C1**: Surgical fix to `mmm_whipsaw_smart.py:697-711` — remove `block = False` + remove token-budget skip; preserve scalar bypasses.
- **C2**: Add sealed test `test_smart_whipsaw_straddle_block_active`.
- **C3**: Update `mmm_whipsaw_implementation.md §0 rule 6` to reflect surgical bypass.
- **C4**: Update memory `feedback_straddle_gamma_bypass.md`.
