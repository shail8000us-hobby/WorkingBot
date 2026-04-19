# AUDIT_PROFITABILITY.md

## 1) Executive Summary

This audit focused on **profitability improvements without increasing risk**, across the MMM orchestration path and profit-capture submodules.

Overall assessment:
- Core architecture is robust and safety-heavy (good for capital preservation).
- The largest remaining gains are from **execution ordering, watcher activation semantics, and accounting correctness**.
- Highest ROI fixes are mostly **low-risk behavioral/ordering corrections** rather than strategy rewrites.

Top opportunities (highest ROI first):
1. **Close-at-threshold ordering + cap interaction** (profit capture latency)
2. **Watcher “0 = always on” semantic mismatch** (missed early close windows)
3. **Scale-up partial-fill accounting drift** (distorted decision metrics)

---

## 2) Files Audited

Primary audited files for this profitability pass:
- `webui/backend/routes/mmm/mmm_monitor.py` (11,557 lines) — heartbeat orchestration, close/replenish/scale/reverse flow, watcher loops
- `webui/backend/routes/mmm/mmm_close_at_5.py` (961 lines) — close scan, sorting, execution, fill handling
- `webui/backend/routes/mmm/mmm_trigger.py` (763 lines) — active and frozen trigger logic
- `webui/backend/routes/mmm/mmm_scaler.py` (288 lines) — favorable scale-up eligibility and lot sizing
- `webui/backend/routes/mmm/mmm_replenish.py` (170 lines) — one-side hedge restoration rules
- `webui/backend/routes/mmm/mmm_recycler.py` (590 lines) — recycling viability and two-phase execution
- `webui/backend/routes/mmm/mmm_reverse.py` (822 lines) — reverse-mode entry/close gating
- `webui/backend/routes/mmm/mmm_config.py` (923 lines) — parameter rules and descriptions
- `webui/backend/routes/mmm/mmm_state.py` — runtime defaults (`DEFAULT_PARAMS`)
- `webui/backend/routes/mmm/mmm_dte_presets.py` (702 lines) — DTE-dependent defaults

---

## 3) Findings

### Finding A — Close-at-threshold ordering is not globally profit-first (High ROI)
**Severity:** P1

**Evidence:**
- `mmm_close_at_5.py`: close candidates are sorted by `(side, type, profit)` with `reverse=True`, not by global profit priority.
- `mmm_monitor.py`: close loop is capped by `close_at_max_per_beat` (default 3), so ordering directly determines realized P&L timing.

**Why it matters:**
When many positions are eligible, the cap means only a subset closes per beat. Side/type precedence can delay the **highest-value closes**, increasing rebound risk and reducing realized capture.

**Suggested fix:**
Sort close candidates by a true global profitability key first (e.g., expected realized P&L), with side/type only as tie-breakers.

**Safe implementation notes for Claude:**
- Keep `_being_closed` protection and guardian/observer checks unchanged.
- Change only candidate ordering; do not alter close guards or order placement behavior.

---

### Finding B — `close_at_watch_hours_before_expiry=0` semantic mismatch (High ROI)
**Severity:** P1

**Evidence:**
- `mmm_state.py` + `mmm_config.py` describe `0` as **always on** for close watcher windowing.
- `mmm_monitor.py` watcher loop computes `in_window = hours_before > 0 and ...`, which makes `0` evaluate to **never in window** unless force-enabled separately.

**Why it matters:**
Operators expecting always-on close watcher can miss proactive close triggers outside the expiry window, causing latency and lower close quality.

**Suggested fix:**
Align runtime with docs: treat `hours_before == 0` as always in-window (or equivalent explicit always-on branch).

**Safe implementation notes for Claude:**
- This is scheduling semantics only; no change to trading formulas.
- Preserve force-enabled behavior and both interval knobs.

---

### Finding C — Scale-up premium accounting uses requested lots, not actual fills (Medium-High ROI)
**Severity:** P1

**Evidence:**
- `mmm_monitor.py` scale-up path correctly stores `ce_filled_lots` / `pe_filled_lots` in positions.
- Same path updates premium counters using requested `lots` for premium aggregation and event tracking.

**Why it matters:**
On partial fills, collected premium and session analytics drift upward. That can distort downstream controls (breakeven/profitability interpretation), indirectly blocking or mis-prioritizing profitable actions.

**Suggested fix:**
Use **actual filled lots** for all premium-collected and scale-event accounting fields.

**Safe implementation notes for Claude:**
- Accounting-only change; do not alter execution or cap checks.
- Ensure both CE and PE sides use their own filled lot values.

---

### Finding D — Scale-up lot base anchored to `initial_lots` can under-utilize profitable decay windows
**Severity:** P2

**Evidence:**
- `mmm_scaler.py` computes scale lots from `initial_lots * scale_lots_pct`, independent of current exposure/headroom.

**Why it matters:**
Sessions that evolve to larger (but still safe) books can remain under-scaled during favorable theta decay periods, leaving premium capture on the table.

**Suggested fix:**
Add optional lot-base mode (e.g., `initial|active|headroom`) while retaining conservative default.

**Safe implementation notes for Claude:**
- Keep existing cap and total exposure checks as hard limits.
- Default behavior should remain backward compatible.

---

### Finding E — Frozen fallback trigger default can be too sensitive at high lot counts (Fee drag risk)
**Severity:** P2

**Evidence:**
- `mmm_trigger.py` frozen fallback fires when total frozen loss exceeds `min_frozen_trigger_dollar`.
- `mmm_state.py` default is `0.2`.

**Why it matters:**
In high-lot sessions, very small premium noise across many frozen lots can exceed a low absolute threshold, producing adjustment churn and fee drag.

**Suggested fix:**
Use an exposure-aware floor (or higher static default per DTE profile), e.g. dynamic threshold tied to lots and lot size.

**Safe implementation notes for Claude:**
- Preserve active-trigger-first mutual exclusion.
- Keep frozen fallback as secondary safety net, not primary trigger path.

---

### Finding F — Reverse-mode blocked entries are silently dropped (missed opportunity)
**Severity:** P2

**Evidence:**
- `mmm_reverse.py` logs “trigger silently dropped” on alternating/cooldown gates.
- No deferred one-beat intent queue exists.

**Why it matters:**
If gate clears shortly after a drop, potentially profitable reverse entries are not revisited.

**Suggested fix:**
Add an optional short-TTL deferred intent (1 beat) when blocked by cooldown/alternation.

**Safe implementation notes for Claude:**
- Keep all reverse-mode invariants and strict isolation in `mmm_reverse.py`.
- Do not route deferred reverse into normal adjustment path.

---

### Finding G — Recycle minimum net lot gain default can over-block small books
**Severity:** P3

**Evidence:**
- `mmm_recycler.py` viability requires `net_lot_gain >= recycle_min_lot_gain`.
- `mmm_state.py` default is `5`.

**Why it matters:**
For smaller sessions, viable recycle opportunities that free 1–3 lots may be rejected, leaving cap pressure unresolved and reducing profitable maneuverability.

**Suggested fix:**
Use a size-aware threshold (e.g., proportional to `max_lots_per_side`) with floor `1`.

**Safe implementation notes for Claude:**
- Keep premium ratio and affordability checks unchanged.
- Only tune the lot-gain gate function/default.

---

## 4) Severity (P0 / P1 / P2 / P3)

- **P0:** None found in this profitability-only pass.
- **P1:** A, B, C
- **P2:** D, E, F
- **P3:** G

Summary count:
- P1: 3
- P2: 3
- P3: 1

---

## 5) Why It Matters

These issues mainly impact profitability through:
- **Delayed profit realization** (ordering/cap/watcher activation)
- **Fee drag from avoidable churn** (over-sensitive fallback triggers)
- **Decision-quality drift** (partial-fill accounting mismatch)
- **Opportunity under-capture** (static scaling and strict recycle thresholds)

None of the recommended top fixes require weakening core safety layers.

---

## 6) Suggested Fix (Prioritized, Risk-Safe)

1. **Fix close ordering under cap** (A) — immediate ROI, minimal behavior risk.
2. **Fix watcher 0-hour semantic mismatch** (B) — low-risk operational correction.
3. **Fix scale partial-fill accounting** (C) — correctness fix, improves decisions.
4. Add optional/parameterized improvements for D/E/G with conservative defaults.
5. Add optional deferred reverse intent for F behind feature flag.

---

## 7) Safe Implementation Notes for Claude

- Preserve stale monitor protections and generation guards as-is.
- Preserve reverse hard mutual exclusion (`reverse` vs normal adjustment).
- Do not alter max-loss, stop, guardian, or margin emergency behavior.
- Prefer additive feature flags / parameterized defaults over hard behavior flips.
- For profitability changes, keep order execution semantics unchanged unless explicitly intended.

Recommended implementation order:
1. A → B → C (safe, high ROI)
2. D/E/G parameterization
3. F optional deferred intent (feature-flagged)

---

## 8) Final Score /10

**Profitability Efficiency Score: 7.8 / 10**

Rationale:
- Strong safety architecture and robust execution guards already in place.
- Remaining drag is concentrated in a handful of ordering/threshold/accounting details that are fixable without increasing risk.
