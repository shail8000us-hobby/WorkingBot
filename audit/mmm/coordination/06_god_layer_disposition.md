# Phase 3 Decision Record — God Layer Disposition

**Date**: 2026-04-28
**Decision**: COORDINATE (do NOT subsume in Phase 3)
**Author**: Claude

---

## Question

Phase 1 audit (`03_decision_map.md`, Gap #4) flagged the God Layer as architecturally redundant with the new Coordination Arbiter:

> God Layer ([mmm_monitor.py:3392-3440](../../../webui/backend/routes/mmm/mmm_monitor.py#L3392-L3440)) implements a Tier-1-like override mechanism (skips lot_velocity, regime BLOCK_SELLS, margin YELLOW, asymmetry). The arbiter implements a more comprehensive version of the same pattern. Decide: subsume God Layer into arbiter, or coordinate explicitly.

The summary recommended subsume. Reconsidering at Phase 3 implementation time.

---

## Decision: coordinate, not subsume

The two systems address **different concerns**, despite surface similarity:

| Aspect | God Layer | Coordination Arbiter |
|---|---|---|
| Trigger | 25-min idle clock + drift detection | Per-beat extreme conditions (BE CRITICAL, gamma EMERGENCY, margin RED) |
| Concern | "Position has drifted; force reactive correction" | "Modules disagree on what to do; resolve per hierarchy" |
| Default | OFF (`god_enabled=False`) | ON (`arbiter_enabled=True`) but in shadow mode |
| Bypasses | lot_velocity, regime BLOCK_SELLS, margin YELLOW, asymmetry | whipsaw, regime, cooldown, asymmetry, soft gamma — but only at Tier 1 |
| Respects | hard stops (PAUSE, STOPPED, margin wind_down, FORCE_REDUCE) | Tier 0 (hard stop, ATM shield, time stop) |

**God Layer is a strategic correction**, not a coordination system. It exists because the heartbeat could go many beats without firing an adjustment if triggers don't crystallize cleanly. After 25 min of inaction with significant P&L drift, God forces the issue. This is a *temporal* concern.

**Arbiter is a coordination system**, not a strategic correction. It activates beat-by-beat when Tier 1 conditions are present, regardless of how long since the last adjustment. This is a *state* concern.

Subsuming God into Arbiter would conflate these concerns and create a more complex decision module. Better to keep them as separate, well-scoped pieces and add a small coordination link.

---

## Coordination link (Phase 4 candidate, not Phase 3)

If both fire in the same beat:

1. **Arbiter Tier 1 acts first** (per Rule 2 — extreme state takes priority)
2. **God Layer skips its correction this beat** if `_arbiter_decision_active == True`

This avoids God forcing a drift correction immediately after the arbiter just executed a defensive shift — which would be redundant and potentially destabilizing.

The link is one if-statement in the God Layer block. Trivial to add. Deferred to Phase 4 because:
- It only matters if both systems are enabled simultaneously (`god_enabled=True` AND `arbiter_live_execution=True`).
- Both are currently in observation/promotion-required mode.
- Adding the link without operator-tested behaviour is premature optimization.

When the user enables either system in live mode, this link should be added.

---

## Status

- **Phase 3**: God Layer untouched. Arbiter coexists alongside it.
- **Phase 4 task**: when promoting either system to live execution, add the coordination link.
- **Long-term**: re-evaluate after replay analysis shows whether God Layer's drift correction is still valuable when arbiter is active. If arbiter handles >90% of cases God would have caught, God can be removed.

This is a deliberate decision to keep two simple systems rather than build one complex one.
