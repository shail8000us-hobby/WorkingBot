# Phase 1 Summary — MMM Coordination Audit

**Status**: ✅ COMPLETE
**Date**: 2026-04-27
**Auditor**: Claude (per user 2026-04-27 — Codex unavailable, single-voice execution)
**Source plan**: [`/MMM_COORDINATION_PLAN.md`](../../../MMM_COORDINATION_PLAN.md)

Phase 1 produced 5 deliverables answering 5 questions about the MMM algorithm's coordination state. This is the consolidated summary.

---

## Phase 1 deliverables

| # | File | Question answered |
|---|---|---|
| 1 | [01_straddle_whipsaw_bypass.md](01_straddle_whipsaw_bypass.md) | Why is smart whipsaw bypassed for STRADDLE_WITH_ADJUSTMENT? Should it be? |
| 2 | [02_premium_aware_shift_feasibility.md](02_premium_aware_shift_feasibility.md) | Does the codebase have the primitives for arbiter Tier 1 defensive shift? |
| 3 | [03_decision_map.md](03_decision_map.md) | What gates exist in the heartbeat? Where are the coordination gaps? |
| 4 | [04_gamma_engine_audit.md](04_gamma_engine_audit.md) | Is user's dissatisfaction with gamma engine valid? What needs fixing? |
| 5 | [05_stale_detection_feasibility.md](05_stale_detection_feasibility.md) | What's needed to implement Rule 6 (stale = danger)? |

---

## Headline findings

### Finding A — The arbiter is a thin coordinator, not a new engine

Phase 1 confirms that **all primitives the arbiter needs already exist** in the codebase:

- Premium-aware strike search (`find_new_strike` in `mmm_strike_shift.py`)
- Premium-aware lot sizing (`calculate_lots_to_sell` in `mmm_engine.py`)
- Strike activation (`activate_new_strike`)
- ATM shield boundary enforcement (via `min_otm_distance` parameter)
- Existing parameters (`shift_target_premium`, `shift_premium_tolerance`, etc.)

**Phase 3 is orchestration, not invention.** Arbiter implementation estimate: ~150 lines of new code + ~30 lines of helpers + 7 one-line instrumentation insertions + 8-10 sealed tests.

### Finding B — Coordination gaps are pervasive but stem from one structural pattern

The decision map (Task 1) surfaced 10 coordination gaps. **9 of them have the same root cause**: signals computed by one module (`_breakeven_zone`, `_gamma_regime`, `_margin_tier`) are read by ZERO blocking gates. Only the multiplier in `calculate_lots_to_sell` reads `_breakeven_zone`.

The fix pattern is identical for all 9: arbiter activates at Tier 1, mutates `_skip_to_pnl` and routes a defensive action based on the missing signal coordination.

The 10th gap (STRADDLE_WITH_ADJUSTMENT whipsaw bypass) is a separate one-line surgical fix from Task 3.

### Finding C — Gamma engine is not broken, but two surgical fixes needed

Of user's three gamma complaints (Phase 2 / B3):
- **Lot-size complaint**: misattributed. Lot scaling IS implemented and correct. The visible problem was driven by time-progression of γ_per_contract, not lot count.
- **DTE complaint**: structurally correct. Engine has only 2 DTE bands (≤30 min tighten, ≤2 hr hedge-relax). 5-DTE treated like 2-hour DTE. Real gap.
- **EMERGENCY = noise complaint**: structurally correct. Current action is `self.pause(...)` which is exactly the wrong response. Should be defensive close.

Two targeted fixes:
1. Add DTE relax ladder in `_update_gamma_cap` (15 lines, no arbiter dependency)
2. EMERGENCY → arbiter Tier 1 defensive close (30 lines, hooks into broader arbiter)

No gamma rewrite needed.

### Finding D — Stale detection is trivial to add

Breakeven engine already uses the right pattern (`computed_at` field). 7 modules need single-line timestamp writes following the same pattern. One helper function in `mmm_state.py`. Pattern is reusable for any future signal.

### Finding E — STRADDLE_WITH_ADJUSTMENT bypass is partially wrong

Current bypass at `mmm_whipsaw_smart.py:697-711` over-applies "§0 rule 6" parity. Two of four behaviours are correct (scalar bypasses), two are wrong (block + token budget bypass). User's stated intent in Phase 2 / D6 directly aligns with surgical fix.

---

## Cumulative Phase 3 task list (26 candidates)

| # | Task | Source | Type | Lines (est) |
|---|---|---|---|---|
| C1 | Surgical fix to `mmm_whipsaw_smart.py:697-711` | Task 3 | Code | ~10 |
| C2 | Sealed test `test_smart_whipsaw_straddle_block_active` | Task 3 | Test | ~30 |
| C3 | Update `mmm_whipsaw_implementation.md §0 rule 6` | Task 3 | Docs | ~10 |
| C4 | Update memory `feedback_straddle_gamma_bypass.md` | Task 3 | Memory | ~5 |
| C5 | `arbiter_tier1_action()` orchestrator | Task 4 | Code | ~40 |
| C6 | `arbiter_margin_recovery_action()` | Task 4 | Code | ~25 |
| C7 | Wire arbiter into heartbeat (between Step 5.8 and skip-to-PNL gate) | Task 1 | Code | ~15 |
| C8 | Sealed test `test_arbiter_tier1_premium_aware_shift` | Task 4 | Test | ~50 |
| C9 | Sealed test `test_arbiter_respects_atm_shield` | Task 4 | Test | ~40 |
| C10 | Add `_signal_last_updated_ts` writes (7 modules) | Task 5 | Code | ~10 |
| C11 | Decide God Layer disposition | Task 1 | Design | (decision) |
| C12 | Sealed test `test_arbiter_overrides_cooldown_on_breakeven_critical` | Task 1 | Test | ~40 |
| C13 | Sealed test `test_arbiter_overrides_reversal_block_on_breakeven_critical` | Task 1 | Test | ~40 |
| C14 | Audit/fix outdated comment in gamma detector | Task 1 | Comment | ~3 |
| C15 | DTE relax ladder in `_update_gamma_cap` | Task 2 | Code | ~15 |
| C16 | `arbiter_gamma_emergency_action()` (defensive close + shift) | Task 2 | Code | ~30 |
| C17 | Disable `self.pause('Gamma emergency')` when arbiter handles | Task 2 | Code | ~5 |
| C18 | Sealed test `test_arbiter_gamma_emergency_defensive_close` | Task 2 | Test | ~50 |
| C19 | Sealed test `test_gamma_engine_dte_relax_at_5dte` | Task 2 | Test | ~40 |
| C20 | `_gamma_last_updated_ts` (covered by C10) | Task 2 | Code | merged |
| C21 | `record_signal_update()` + `is_signal_fresh()` helpers | Task 5 | Code | ~30 |
| C22 | 7 single-line timestamp writes (covered by C10) | Task 5 | Code | merged |
| C23 | `get_effective_<signal>()` escalation accessors in arbiter | Task 5 | Code | ~20 |
| C24 | `stale_signals` in audit trail JSON | Task 5 | Code | ~5 |
| C25 | Sealed test `test_arbiter_escalates_stale_breakeven_zone` | Task 5 | Test | ~40 |
| C26 | Sealed test `test_arbiter_skip_when_first_beat_warmup` | Task 5 | Test | ~30 |

**Estimated totals**:
- New code: ~290 lines
- Tests: ~360 lines (8 sealed tests)
- Docs/memory updates: ~20 lines

---

## What Phase 3 will look like (preview)

The arbiter is one new module: `webui/backend/routes/mmm/mmm_arbiter.py`.

```python
"""
MMM Coordination Arbiter — Phase 3 implementation of the sealed hierarchy.

Activates only at Tier 0 or Tier 1. At Tier 2/3, this is a no-op — operational
modules run as designed.
"""

class CoordinationArbiter:
    def evaluate(self, session: dict) -> Optional[ArbiterDecision]:
        # Last-30-min check: per Rule 5, no Tier 1 bypass in cool-down period
        if minutes_to_expiry(session) <= 30:
            return None  # arbiter is no-op

        # Warmup: don't activate before signals are fresh
        if session_age_beats(session) < 2:
            return None

        # Stale detection per Rule 6: escalate signals before tier check
        effective_be   = get_effective_breakeven_zone(session)
        effective_gam  = get_effective_gamma_regime(session)
        effective_mar  = get_effective_margin_tier(session)

        # Tier 1 dispatch (Rule 2: act, don't block)
        if effective_be == 'CRITICAL' or effective_gam == 'EMERGENCY' or effective_mar == 'RED':
            return self._tier1_action(session, effective_be, effective_gam, effective_mar)

        # Tier 2/3: no-op
        return None

    def _tier1_action(self, session, be_zone, gamma, margin):
        # Margin RED → margin-recovery moves only (per B2)
        if margin == 'RED':
            return self._margin_recovery_action(session)

        # Gamma EMERGENCY → defensive close + shift (per B3)
        if gamma == 'EMERGENCY':
            return self._gamma_emergency_action(session)

        # Breakeven CRITICAL → premium-aware defensive shift (per B1, D1)
        if be_zone == 'CRITICAL':
            return self._defensive_shift_action(session)

        return None
```

The wiring point in `mmm_monitor.py` is between Step 5.8 (Gamma Detector) and the skip-to-PNL gate (D1 in decision map):

```python
# Step 5.8 Gamma Detector ... [existing code]

# ── NEW: Coordination Arbiter ────────────────────────────────
arbiter_decision = self._arbiter.evaluate(session)
if arbiter_decision is not None:
    # Tier 1 active — bypass operational gates, execute defensive action
    _skip_to_pnl = False  # un-skip if upstream block tried to skip
    await self._execute_arbiter_decision(arbiter_decision)

# ── existing skip-to-PNL gate ──
if _skip_to_pnl:
    ...
```

---

## Risks identified during Phase 1

### Risk A — God Layer redundancy
God Layer ([mmm_monitor.py:3392-3440](../../../webui/backend/routes/mmm/mmm_monitor.py#L3392-L3440)) implements a Tier-1-like override mechanism. The arbiter implements a more comprehensive version. **Decision needed in Phase 3**: subsume God Layer into arbiter, or coordinate explicitly.

Recommendation: subsume — reduces conceptual surface area. God's `god_enabled` param becomes `arbiter_enabled` (default True since Phase 3 ships).

### Risk B — Adaptive engine could fight arbiter
Adaptive engine runs at Step 5.3, before arbiter would activate. If adaptive tunes params during Tier 1 events, decisions could distort. **Decision needed in Phase 3**: arbiter freezes adaptive tuning for the beat when Tier 1 fires.

### Risk C — Replay harness rebuild
Phase 4 (replay tuning) will require the audit trail (Rule 7) to reconstruct counterfactuals. This means audit trail format must be stable from Day 1 of Phase 3. Schema changes later = breaks replay history.

### Risk D — Breakeven multiplier composition under arbiter
At Tier 1, arbiter outputs strike + lots directly. At Tier 2 (modules as designed), `calculate_lots_to_sell` still applies breakeven multiplier. Need clear documentation on **which path applies when** so users don't see double-application.

---

## What's complete vs. what's pending

**Complete**:
- ✅ Phase 2 — Sealed hierarchy (7 rules, Phase 2 / Batches A-G)
- ✅ Phase 1 — All 5 audits

**Next** — Phase 3 implementation:
- 26 candidate tasks listed above
- Estimated effort: ~290 lines code + ~360 lines tests + docs
- No GPT delegation needed — Claude handles end-to-end per user request

**After Phase 3** — Phase 4 replay tuning:
- Extend `mmm_whipsaw_replay.py` to consume audit trail
- Tune parameters scientifically against historical sessions
- Ongoing operational discipline, not a one-shot project

---

## User decision points before Phase 3 starts

These are NOT blockers — Claude will proceed with sensible defaults documented above. But user input would shape some choices:

1. **God Layer disposition** (Risk A): subsume or coordinate?
2. **Tier 1 last-30-min override** — Rule 5 says no Tier 1 in last 30 min. Confirm: this includes gamma EMERGENCY too? (My current default: yes, per Rule 5.)
3. **Token budget for STRADDLE_WITH_ADJUSTMENT** (Task 3 audit) — proposed default `tokens_per_session = 10.0` with `refresh_per_hour = 1.0`. Is this appropriate for typical straddle session length?
4. **DTE relax ladder values** (Task 2): proposed buckets are 1.5×/1.25×/1.0×/1.0×/0.5×. Tunable; defaults are starting points.

User can answer these now, or trust defaults — Claude will flag them as `# TUNABLE` in Phase 3 code so they're easy to adjust later.

---

## Final verdict

The MMM coordination problem is **solvable with high precision**. The audit confirms:

- ~290 lines of net new code (one new module + 7 instrumentation lines + small surgical fixes)
- 8 new sealed tests
- 2 documentation updates
- Zero existing modules need rewrite
- Zero new external dependencies

The user's instinct in the original conversation — "I should tune what exists, not build new" — is **correct**. Phase 3 builds one small new piece (the arbiter) that lets every existing module continue doing exactly what it was designed for, without trampling each other's signals.

**Phase 1 complete. Phase 3 fully scoped. Ready to begin implementation when you are.**
