---
name: MMM Coordination Plan
description: Master plan to fix MMM module coordination — replace one-by-one tuning loop with global arbitration layer
status: Phase 2 in progress
created: 2026-04-27
---

# MMM Coordination Plan

> **Purpose**: Persist the strategic plan agreed in conversation on 2026-04-27 so future sessions can resume without re-deriving it.
> **DO NOT DELETE**. Update the **Status** section and the **Phase 2 answers** section as work progresses.

---

## Why this exists (the diagnosis)

The MMM algorithm is a system of independent expert modules:

| Module | Local objective |
|---|---|
| Whipsaw (`mmm_whipsaw_smart.py`) | Don't trade in noise |
| Regime (`mmm_regime.py`) | Don't trade against trend |
| Gamma (`mmm_gamma.py`) | Don't blow up on gamma |
| Breakeven (`mmm_breakeven_engine.py`) | Protect near BE lines |
| Close-at-5 (`mmm_close_at_5.py`) | Reduce end-of-day risk |
| Harvester / Recycler / Scaler | Earn more premium |
| Strike Shift (`mmm_strike_shift.py`) | Move strikes when stressed |
| Reverse (`mmm_reverse.py`) | Reverse position overlay |
| ATM Shield (`mmm_atm_shield.py`) | Block ATM exposure |
| Adaptive (`mmm_adaptive.py`) | Tune triggers dynamically |

Each module is built well **in isolation**. The problem is that none of them know about each other's signals, and the winner of any conflict is determined by **execution order in the heartbeat**, not by considered judgment about which signal should dominate.

**Symptom example (2026-04-27)**: PE became ATM after 1000-pt drop. Breakeven engine wrote `_breakeven_zone='CRITICAL'` to session. Smart whipsaw, evaluating later in the same beat, did not read that signal — `_check_pressure_override()` only checks `_margin_tier` and `_smart_ws_loss_velocity`. Result: whipsaw blocked the very adjustment that was needed to protect the position.

This is not a tuning bug. This is a **coordination bug**. No amount of parameter tuning fixes "module A doesn't read module B's output." Tuning loops break only when coordination is made explicit.

---

## The 4-phase plan

### Phase 1 — Map the gate graph (3 days, GPT-delegated)
Produce `MMM_DECISION_MAP.md`: every gate/blocker/multiplier in heartbeat execution order, with for each entry:
- **Reads** (signals consumed)
- **Writes** (session state produced)
- **Blocks** (downstream modules it can stop)
- **Bypassed by** (signals that override it)
- **Missing inputs** (signals it should consume but doesn't)

GPT (Codex 5.3 X-High) does the auditing; Claude validates and integrates.

**Phase 1 deep-dive task (added 2026-04-27, B3 follow-up)**: audit `mmm_gamma.py` + `mmm_gamma_detector.py` against user's complaints:
1. Does `_update_gamma_cap` actually re-scale soft/hard/emergency thresholds beat-by-beat as `max(ce.active_lots, pe.active_lots)` grows? Is the scaling proportional or capped?
2. Does the DTE relax window (Tier C 2× hard limit near expiry) correctly relax for 5-DTE while staying tight for 0-DTE?
3. Is gamma EMERGENCY firing in scenarios where the position is structurally fine (e.g., 5-DTE STRADDLE_WITH_ADJUSTMENT, or after harvester grew lots 5×)?
4. When gamma EMERGENCY fires, does it block adjustments that would actually *reduce* gamma (defensive closes, strike shifts)?

If user's perception is correct (engine produces noise), Phase 1 surfaces it and Phase 3 arbiter routes around it OR a structural fix is queued. Do not patch gamma.py in isolation; this is part of the coordination problem.

### Phase 2 — Define the risk hierarchy (1–2 days, user judgment)
**Currently active phase.** User answers a structured set of "when A conflicts with B, who wins?" questions. Answers become tiers:

```
Tier 0 — Always wins, never bypassed (max_loss, ATM shield, hard time stops)
Tier 1 — Bypasses everything below (breakeven=CRITICAL, margin=RED, gamma=EMERGENCY)
Tier 2 — Bypasses Tier 3+ (breakeven=DANGER, margin=ORANGE, loss_velocity_high)
Tier 3 — Operational gates (regime, whipsaw, gamma_soft, asymmetry)
Tier 4 — Sizing/timing (lot_scalar, trigger_widen, cooldown)
```

Output: `MMM_RISK_HIERARCHY.md` — sealed contract.

### Phase 3 — Build the arbiter (2–3 days, code)
A single `arbitrate_decision(session, candidate_decisions)` function runs at the start of the adjustment phase:
1. Collects each module's local decision (block / allow / scale)
2. Filters them through the Tier hierarchy
3. Returns ONE final decision

Existing modules unchanged internally. They propose; arbiter disposes. ~200 lines, replaces dozens of scattered if-checks.

### Phase 4 — Replay-driven tuning (ongoing, scientific)
Extend `mmm_whipsaw_replay.py` into a full session replay harness:
- Replays historical sessions against current code
- Reports: adjustments blocked/allowed (by module), counterfactual P&L if block removed, tier-conflict events
- Parameter tuning becomes: change → replay 30 sessions → diff outcomes → keep or revert

Tuning happens **only within the hierarchy**. Never re-introduce tuning that contradicts a Tier rule.

---

## Status

| Phase | Status | Owner | Completed |
|---|---|---|---|
| Phase 1 — Gate map | ✅ **COMPLETE** | Claude | 2026-04-27 |
| Phase 2 — Risk hierarchy | ✅ **COMPLETE** | User + Claude | 2026-04-27 |
| Phase 3 — Arbiter | ✅ **COMPLETE** (shadow mode) | Claude | 2026-04-28 |
| Phase 4 — Replay tuning + live promotion | **NEXT** | Claude (when user ready) | — |

**Phase 3 deliverables (2026-04-28)**:
- New module: `webui/backend/routes/mmm/mmm_arbiter.py` (~280 lines)
- Surgical fixes: smart whipsaw straddle bypass narrowed; gamma DTE relax ladder added
- Stage 1 instrumentation: 7 timestamp insertions + helper module + latent `_margin_tier` write bug fix
- Wire-in: heartbeat between Step 5.8 and skip-to-PNL gate; gamma EMERGENCY pause conditionally disabled
- Sealed tests: **22 new** in `test_sealed_audit_fixes.py` (total MMM-area sealed: 1166 passing, baseline 1144)
- Documentation: `MMM_LAST_3_SESSIONS.md`, `mmm_workdone_march.md`, `mmm_whipsaw_implementation.md §0 rule 6`, memory `feedback_straddle_gamma_bypass.md`
- God Layer disposition: COORDINATE (decision in `audit/mmm/coordination/06_god_layer_disposition.md`)

**Phase 3 mode**: ✅ **LIVE** (no shadow). Per user directive 2026-04-28 ("I dont believe on shadow mode, make it live"), the arbiter executes Tier 1 actions directly via existing tested order-placement infrastructure:
- `defensive_shift` → `_process_strike_shift(opposite_side, loss, ce_now, pe_now)` with cooldown bypass
- `gamma_emergency_close` → `close_position(mechanism='emergency')` on top-N dominant-gamma positions
- `margin_recovery_buyback` → `close_position(mechanism='emergency')` on cheapest OTM positions

**WebUI toggle**: `arbiter_enabled` master switch in MMMSettingsDialog → "⚖️ Coordination Arbiter (Phase 3 — Live)" section under Advanced. Default ON. Hot-reloadable (no backend restart needed). Tunable DTE relax multipliers also exposed.

**Sealed tests**: 1173 MMM-area passing (baseline 1144 + 29 new across rev1+rev2) / 0 failed. Includes 3 regression guards in `TestArbiterLiveExecutionWired` that fail loudly if shadow mode is silently reintroduced.

**Phase 1 deliverables**: `audit/mmm/coordination/`
- [00_PHASE_1_SUMMARY.md](audit/mmm/coordination/00_PHASE_1_SUMMARY.md) — consolidated findings + 26 Phase 3 tasks
- [01_straddle_whipsaw_bypass.md](audit/mmm/coordination/01_straddle_whipsaw_bypass.md)
- [02_premium_aware_shift_feasibility.md](audit/mmm/coordination/02_premium_aware_shift_feasibility.md)
- [03_decision_map.md](audit/mmm/coordination/03_decision_map.md)
- [04_gamma_engine_audit.md](audit/mmm/coordination/04_gamma_engine_audit.md)
- [05_stale_detection_feasibility.md](audit/mmm/coordination/05_stale_detection_feasibility.md)

---

## SEALED HIERARCHY (Phase 2 output, 2026-04-27)

The seven sealed rules of the MMM coordination contract. Phase 3 must implement these exactly; Phase 4 must tune within them.

### Rule 1 — Tier 0 is absolute
Hard stop, ATM shield (when enabled), time-based hard stop near expiry. Once fired, **nothing** overrides them. Tier 0 conditions enforce themselves; arbiter ensures no module's local decision contradicts them.

### Rule 2 — Tier 1 acts; it does not block
When breakeven CRITICAL, margin RED, gamma EMERGENCY (post-redesign), or loss_velocity high fires:
- Bypass Tier 3 operational gates (whipsaw, regime BLOCK_ALL, asymmetry, cooldowns)
- Pause harvester / recycler / scaler for that beat
- Trigger **premium-aware defensive shift**: find opposite-side strike with premium ≈ `shift_target_premium ± shift_premium_tolerance`, sell minimum lots needed
- Respect Tier 0 boundaries (ATM shield, hard stop, margin RED constraint)

### Rule 3 — Tier 2 is silent (the "fell on the road" rule)
Breakeven DANGER, margin ORANGE, gamma HARD: modules work as designed. Arbiter does not intervene. Existing multipliers/scalars/blocks apply normally.

### Rule 4 — Premium quality > premium quantity (insurance company doctrine)
When defending, write **fewer high-premium policies**, not many cheap policies. The risk in a black swan scales with **contract count**, not premium value. The arbiter's Tier 1 action selects strikes by premium target, not by lot count.

### Rule 5 — Last 30 minutes is cool-down (no Tier 1 bypass)
In the last 30 minutes before expiry, Tier 1 bypass is DISABLED. All operational modules run as designed. Tier 0 (auto-close, hard stop, ATM shield) handles disasters. Last 30 min = noise; don't compound it with aggressive defense.

### Rule 6 — Stale data is dangerous
Any signal not refreshed in current or prior beat → escalate to next-higher tier for arbiter purposes. Log STALE event. Never silently fall back to normal pipeline.

### Rule 7 — Audit everything the arbiter changes
Concise activity-log line + structured JSON audit trail per beat where arbiter activated. Audit trail feeds Phase 4 replay tuning.

### Strategy-specific overrides
| Strategy | Tier 0 | Tier 1 logic | Whipsaw | Gamma | ATM shield |
|---|---|---|---|---|---|
| Default (Short Strangle, etc.) | ACTIVE | ACTIVE | ACTIVE (Tier 3) | ACTIVE | ACTIVE if enabled |
| **STRADDLE_WITH_ADJUSTMENT** | ACTIVE | ACTIVE | **ACTIVE** ⚠️ (currently bypassed in code — see D6 flag) | BYPASSED | BYPASSED |
| **Reverse mode** | ACTIVE | Isolated (no arbiter) | (own logic) | (own logic) | (own logic) |

⚠️ **STRADDLE_WITH_ADJUSTMENT whipsaw**: code currently bypasses, user wants active. Phase 1 audit task before Phase 3 wires it correctly.

---

## Phase 1 task list (input from Phase 2)

When starting Phase 1, the auditor must produce:

1. **`MMM_DECISION_MAP.md`** — every gate's reads/writes/blocks/bypassed-by/missing-inputs in heartbeat order
2. **Gamma engine deep-dive** (B3 follow-up) — verify DTE-awareness and lot-size-awareness work correctly; report on whether emergency thresholds adapt as harvester grows position
3. **STRADDLE_WITH_ADJUSTMENT whipsaw bypass investigation** (D6 flag) — git blame, motivating incident, removability assessment
4. **Premium-aware shift feasibility check** — does `find_strike_with_premium()` logic already exist somewhere in mmm_strike_shift.py? What needs to be built vs reused for Tier 1 defensive shift?
5. **Stale-detection feasibility** — current state writes don't always include timestamps. Identify which signals need timestamping for Rule 6.

**Owner: Claude** (user decision 2026-04-27 — Codex unavailable; user wants single consistent voice for this delicate work).

---

## Phase 2 — Risk hierarchy questions

The questions are organized in batches. User answers in chat; Claude transcribes answers into the **Phase 2 answers** section below.

### Batch A — Tier 0 (always wins)
A1. When **max_loss** is hit, should anything be allowed to override (e.g., a near-breakeven defensive close)?
A2. When **ATM shield** fires, should any module override it (e.g., harvester, scaler)?
A3. When **time-based hard stop** fires (e.g., 15 min before expiry auto-close), can anything override it?
A4. Is there any other condition you would call "absolute" — never overridable?

### Batch B — Tier 1 (critical position risk)
B1. **Breakeven CRITICAL** (<0.5% from BE): which Tier 3 gates should be ignored — whipsaw? regime? gamma soft? all of them?
B2. **Margin RED**: same question — which gates ignore?
B3. **Gamma EMERGENCY**: should defensive *close* adjustments still run, or should everything stop?
B4. **Loss velocity > $X/min**: at what threshold do you want this to trigger Tier 1? ($50/min is current.)
B5. When two Tier 1 conditions conflict (e.g., breakeven=CRITICAL on PE side, margin=RED can't add lots): who wins?

### Batch C — Tier 2 (high risk, not yet critical)
C1. **Breakeven DANGER** (0.5–1.0% from BE): bypass whipsaw? or only the asymmetric +1 gate penalty?
C2. **Margin ORANGE**: same question.
C3. **Gamma HARD** (1× hard limit reached, not 2× emergency): bypass whipsaw? bypass regime?
C4. Should Tier 2 conditions also affect lot sizing (e.g., still allow adjustment but cap lots), or just affect blocking?

### Batch C2 — Module-pair conflicts (most decision-shaping questions)
P1. **Regime vs Breakeven**: regime says BLOCK_PE_SELLS (TREND_DOWN+VOL_ELEVATED); breakeven says CRITICAL on PE side. Who wins? (My intuition: breakeven, because regime's job is to avoid bad sells in trending markets, but breakeven's job is preventing actual loss.)
P2. **Whipsaw vs Breakeven**: today's bug. Confirm: breakeven DANGER/CRITICAL always overrides whipsaw block?
P3. **Whipsaw vs Harvester**: whipsaw says block; harvester wants to close-and-rebook a profitable position. Should harvester run? (Risk-reducing close, but premium-driven.)
P4. **Whipsaw vs Strike Shift**: whipsaw blocks; strike shift wants to move strikes (defensive). Run?
P5. **Whipsaw vs Close-at-5**: closes are always risk-reducing — should they bypass all whipsaw/regime gates?
P6. **Regime vs Strike Shift**: regime BLOCK_ALL_SELLS but shift needs to sell new strikes. Run?
P7. **Gamma cap vs Breakeven**: gamma cap reached, but breakeven CRITICAL needs more lots for protection. Who wins?

### Batch D — Module-specific (Tier 3+)
D1. **Harvester**: should it run during DANGER zone? CRITICAL? Or only SAFE/WARNING?
D2. **Recycler**: same.
D3. **Scaler** (scaling up): allow during DANGER? CRITICAL? Or never above WARNING?
D4. **Reverse mode** (when active): does reverse follow the same hierarchy, or is it isolated (its own contract)?
D5. **Strike shift**: bypass whipsaw? bypass regime? bypass gamma? Or only some?

### Batch E — Sizing & multiplier composition
E1. **Breakeven multiplier (2.06x) + whipsaw lot_scalar (0.5x)**: do they multiply (1.03x), or does breakeven's multiplier override?
E2. **Gamma soft cap (reduce lots) + breakeven multiplier (increase lots)**: who wins?
E3. **Trigger widen (whipsaw says 1.5x trigger) + breakeven (tighter triggers near BE)**: which dominates?

### Batch F — Time-based and strategy-specific
F1. **Last 30 min before expiry**: should the hierarchy tighten (more restrictive) or loosen (more permissive)?
F2. **ODTE sessions specifically**: different hierarchy from multi-DTE? If so, how?
F3. **STRADDLE_WITH_ADJUSTMENT**: currently bypasses gamma + whipsaw. Should it follow the global hierarchy or keep its own?
F4. **Reverse mode active**: same question — global hierarchy or isolated?

### Batch G — Edge cases
G1. **Stale data**: if `_breakeven_zone` was set 3+ beats ago and engine hasn't recomputed (stale), should the override still fire?
G2. **Conflicting Tier 0 conditions**: max_loss says STOP, but ATM shield says CLOSE — close happens first, then stop?
G3. When the arbiter changes a decision, who logs it (which module)? Single log line per beat or per-module?

---

## Phase 2 — Answers

> Format: question_id → answer → Claude notes

### Batch A — TIER 0 (absolute, non-overridable)

**Guiding philosophy (user, 2026-04-27)**: "Survival is more important than earning." Hard stop + ATM shield are the two most important safety features. They must work exactly as designed; nothing in the system overrides them.

- **A1. Max loss hit** → **immediate market-order exit, absolute. No further trades, no defensive close attempts, no strike shift. Final decision.**
- **A2. ATM shield** → when **enabled**, works per design — no module may alter or bypass it. When **disabled** (user toggle), normal adjustments proceed (ATM shield has no effect because it's off; this is not a bypass).
- **A3. Time-based hard stop near expiry** → non-negotiable. If config says auto-close at T-15min, it closes at T-15min. No override.
- **A4. Other Tier 0 conditions**: implied by user's safety-first philosophy. Need confirmation in a follow-up — candidates: generation guard (stale monitor protection — sealed), manual emergency stop, lot velocity ceiling. **Will revisit before sealing the hierarchy.**

**Tier 0 invariant**: Once a Tier 0 condition fires, the arbiter's job is to enforce it without exception. No Tier 1+ signal — including breakeven CRITICAL, gamma EMERGENCY, or pressure override — can change a Tier 0 outcome.

### Batch B — TIER 1 (critical position risk → ACTION, not blocking)

**Core philosophical reframe (user, 2026-04-27)**:
> "Breakeven CRITICAL, gamma EMERGENCY, lot velocity — these are good safety features in normal conditions. But in EXTREME conditions, they should NOT block — they should TRIGGER ACTION. Stop the bleeding. Hard stop + ATM shield are the safety net; they will catch us if everything else fails."

> Analogy: "If someone falls in a ditch, you don't shout 'this person is injured!' — you call the ambulance. If a person is sick, bacteria killing them, you don't stop treatment — you give good bacteria to kill the bad."

**This is a structural shift**: today, breakeven CRITICAL is a passive zone classification (multiplier + informational). The user wants it as an **active trigger** that initiates defensive action, not a blocker.

---

**B1. Breakeven CRITICAL** — ACTIVE DEFENSE TRIGGER, not blocker

When CRITICAL fires on side X (e.g., PE under threat after big drop):
- **Bypass** all Tier 3 operational gates (whipsaw, regime block, asymmetry, cooldown). The position is bleeding; do not block adjustment.
- **Action**: aggressively sell the OPPOSITE side (the safer, OTM side). Rationale: re-balance the structure, generate premium to offset incoming loss on the threatened side.
- **Trust**: hard stop and ATM shield are still active — they will catch the position if action is too late or wrong.
- **Follow-up safeguard**: after aggressive opposite-side selling, **strike shift** becomes critical. If market reverses against the newly-loaded safe side, shift must be free to fire. **Strike shift constraints must be LOOSENED, not tightened, in this state.**

**Open question**: aggression *magnitude* — see Batch C question on this.

---

**B2. Margin RED**

User's normal trading style keeps margin out of red. If it does hit red:
- **(a) Block all NEW sells** — capital physically can't accept more lots. Confirmed correct.
- **PLUS recovery move**: allow **buying back cheap OTM strikes** to reduce margin requirement. This is a defensive close that frees margin and returns the system to normal trading capacity.
- Rule: in margin RED, the only allowed *new* trades are margin-reducing closes/buybacks; everything else blocked until margin returns to ORANGE/SAFE.

---

**B3. Gamma EMERGENCY** — USER IS NOT SATISFIED WITH CURRENT GAMMA ENGINE

User's specific complaints (must be investigated in Phase 1):
1. **Not DTE-aware enough**: 5-DTE position has structurally low gamma; engine should be relaxed there. 0-DTE is where gamma actually matters; engine should be tight there. User feels engine treats them similarly.
2. **Not position-size-aware enough**: started with 10 lots, harvester grew to 100 lots — engine's emergency thresholds don't adapt. (Note: rev4 added scaling via `_update_gamma_cap` using `max(ce.active_lots, pe.active_lots)` vs `initial_lots` — but user perception is this is not sufficient.)
3. **Behaviour**: gamma EMERGENCY currently produces "noise" (blocks). Should produce **defensive close action** instead.

**Tier 1 rule for gamma EMERGENCY (subject to engine redesign)**:
- Allow **defensive closes** (reduce lot count to lower gamma).
- Allow **strike shift** (move to lower-gamma strikes).
- Block new sells that would *increase* gamma further.

**Phase 1 deliverable** (added): deep-dive audit of `mmm_gamma.py` + `mmm_gamma_detector.py` — verify DTE scaling and position-size scaling actually work as intended, not just nominally implemented. User has explicit dissatisfaction; investigate before tuning.

---

**B4. Loss velocity** — WORKING FINE, no change needed

- Operator-tunable at session start.
- When it blocks, it surfaces in the activity log → operator can override.
- Current $50/min threshold is operator's choice, not a system default to second-guess.
- **Decision**: loss velocity stays as Tier 1 with current behaviour. No tuning needed.

---

**B5. Tier 1 conflict resolution — the master principle**

User's principle (verbatim spirit):
> "All these safety features are good in normal market conditions. In EXTREME market conditions, we should bypass them because our first priority is to save the position. The bot has to understand this is the extreme situation — act swiftly, not restrict operation."

**Tier 1 = ACT, not BLOCK.**

When Tier 1 conditions fire:
1. Tier 3 operational gates (whipsaw, regime, asymmetry, cooldown) → **bypass**.
2. Defensive action paths (opposite-side sells, strike shift, defensive close, margin buyback) → **unblock and run aggressively**.
3. Tier 0 (hard stop, ATM shield, time stop) → **still active**. They are the safety net.

When two Tier 1 conditions fire together:
- **Breakeven CRITICAL + margin RED**: cannot add lots. Therefore: strike shift + defensive close on the threatened side. (Buyback cheap OTMs on the *fat* side to free margin, then sell aggressively on the *threatened side's opposite*.)
- **Gamma EMERGENCY + breakeven CRITICAL**: gamma says reduce, BE says protect. **Reduce wins** (per safety-first). Concrete: defensive close + strike shift, not "add more lots for protection." This is the one Tier-1 conflict where the action shape *changes* depending on which condition is louder.
- **Loss velocity high alone (BE safe, gamma safe)**: surfaces in activity log; operator decides. Bot does not auto-act.

---

**Tier 1 invariant (sealed)**:
> Tier 1 fires → operational gates bypassed → defensive action initiated → Tier 0 remains the absolute safety net.

The arbiter's job at Tier 1: **transform** module decisions, not just **filter** them. A whipsaw "block" becomes "allow"; a regime "block" becomes "allow"; a gamma "soft cap" is overridden by breakeven multiplier — but the *action taken* is still subject to Tier 0 limits.

### Batch C — TIER 2 (elevated, not extreme → modules work as designed)

**Core principle (user, 2026-04-27)**: Operational modules (whipsaw, regime, gamma soft, etc.) are designed for normal markets and elevated conditions. They are good at filtering noise in those regimes. The arbiter must NOT second-guess them at Tier 2. Bypass behaviour is reserved for Tier 1 (extreme) only.

User's analogy:
> "If a person fell on the road for any reason, you ask 'are you OK?' — you don't call the ambulance. Same here — elevated risk, not extreme: modules work as per their design."

**This dramatically simplifies the arbiter**: it only intervenes at Tier 1 and Tier 0. At Tier 2 and Tier 3, modules run unchanged.

---

**C1. Breakeven DANGER** → modules work as designed.
- No bypass of whipsaw / regime / gamma soft
- Breakeven multiplier (1.3–2.0x) still amplifies lot size when an adjustment naturally fires
- This was already the design intent; no change needed

**C2. Gamma HARD** → modules work as designed. No bypass.

**C3. Margin ORANGE** → modules work as designed. No proactive recovery action.
- (Margin RED is the action trigger, not ORANGE.)

**C4. Tier 2 philosophy** → silent. Informational. Operational gates run normally.
- The "act don't block" principle applies to Tier 1 only.
- Tier 2 = "elevated, monitor" — no transformation by arbiter.

---

**Tier 2 invariant (sealed)**:
> At Tier 2, the arbiter is a no-op. All decisions flow from operational modules with their existing logic. The only state checks the arbiter performs at Tier 2 are (a) is Tier 1 about to fire? (b) is Tier 0 about to fire?

**Architectural consequence**: the arbiter is a **thin layer** that activates only when Tier 0 or Tier 1 conditions are present. In the common case (normal/elevated markets), it does nothing — preserving every module's existing design.

### Batch D — TIER 1 ACTION MECHANICS — premium-aware defense

**Master doctrine (user, 2026-04-27)**: the user describes themselves as an insurance company. Each option contract sold = one policy = one liability in a black swan event. The catastrophic-event exposure scales with **number of contracts**, not their value. Therefore:

> **One $100-premium policy is structurally safer than five $20-premium policies, even though both collect the same premium.**

**The current bug** (visible in mmm28apr26-1 screenshot, 2026-04-27): when PE became distressed (entry $211, mark $499), the algo defended by adding 50 forced CE lots at strike 78800 with premium $44. This created **150 cheap policies** total on the CE side. In a market reversal, those 150 contracts pay out simultaneously — the exact "black swan" risk the user has spent the entire algo design avoiding (close-at-5 sweeps cheap premium daily; harvester rebooks expensive premium). Defense logic is *contradicting* the rest of the system's premium hygiene.

---

**D1. Tier 1 action magnitude → PREMIUM-PER-LOT MODE (not lot-count mode)**

When Tier 1 fires (breakeven CRITICAL on side X), the defensive action is:

1. Compute target premium offset (related to unrealized loss on side X and the existing `shift_premium` setting)
2. Find the strike on the opposite side where **premium per lot ≈ shift_premium target**
3. Sell the **minimum lot count** at that strike sufficient to deliver the target offset
4. If no existing strike meets the target premium, **shift proactively** — open a new closer-to-spot strike where premium per lot ≈ target

**Reject the following common-but-wrong approaches**:
- ❌ Match-mode (rebalance lot counts) — creates cheap-policy pile-up
- ❌ Pure multiplier on existing strike — same problem
- ❌ Adding lots at current far-OTM strike when premium has decayed — ANTI-PATTERN per user trading philosophy

**Upper cap / safety net**: ATM shield (Tier 0) already prevents shifting too close to spot. Hard stop catches over-loss. Margin tier catches over-leverage. So the bot can move aggressively within these limits without additional Tier-1-specific caps.

---

**D2. Strike shift sequencing under Tier 1**

Strike shift is **the primary Tier 1 action**, not a separate or follow-up action. Under the doctrine above:

- Defending = finding the right strike with the right premium = strike shift IS the defensive sell.
- Old framing ("sell aggressively, then shift if needed") is wrong — it lets cheap policies accumulate first.
- New framing: **proactive shift IS the defense**. The arbiter's Tier 1 output is "shift to strike S and sell N lots there," delivered as one decision.

**Constraints during Tier 1** (relaxed):
- Whipsaw: bypassed
- Regime BLOCK_ALL_SELLS: bypassed (this is precisely the case regime is wrong about — see CLAUDE.md §2026-04-02 hedge_break incident)
- Cooldown on shifts: bypassed (multiple shifts per beat allowed if needed to reach target premium)
- ATM shield boundary (Tier 0): respected — bot will not shift inside ATM band
- Margin (Tier 1): respected — if margin RED, recovery move (buy back cheap OTM) runs first

---

**D3. Harvester / Recycler / Scaler — WORKING AS DESIGNED, no Tier 1 changes**

User confirmed: these three are working perfectly in normal market conditions. They are designed for normal markets and they execute their design well.

- **At Tier 2 (elevated)**: they continue as designed.
- **At Tier 1 (extreme)**: arbiter takes over with the shift-and-sell-higher-premium plan; harvester/recycler/scaler should not run side-by-side because their growth/income objectives conflict with defense. **Implementation**: arbiter's Tier 1 phase pauses these modules for that beat. They resume the next beat if Tier 1 has cleared.
- **No changes to module internals.** The pause is an arbiter responsibility, not a module change.

---

**D4. Reverse mode — ISOLATED, not arbitrated**

User confirmed: reverse mode is a separate optional engine. The arbiter does NOT touch it. Reverse continues with its own internal logic (mmm_reverse.py) per CLAUDE.md §5.

**Exception**: Tier 0 (hard stop, ATM shield, time stop) still apply to reverse positions because Tier 0 is sealed at the system level. CLAUDE.md §5 already specifies the close order (reverse → perp → core) which the arbiter must respect when Tier 0 fires.

---

**D5. Last 30 minutes before expiry — NO TIER 1 BYPASS**

Critical decision (user, 2026-04-27):
> "In last thirty minutes, all safety features should work perfectly. There is no need to bypass anything in the last thirty minutes. Last thirty minutes is the cool down time."

User reasoning:
- 90%+ of the day's profit has already been collected
- Positions are intended to expire worthless
- No reason to add aggression at this point
- Last 30 min = NOISE, not signal
- Safety features (gamma, regime, time-stop) are specifically designed for end-of-day dynamics
- Waiting for hard stop / ATM shield to catch problems in last 30 min is wrong thinking — those are last-resort, not first-resort

**Rule**: in the last 30 minutes before expiry, **Tier 1 bypass behaviour is DISABLED**. Operational gates run normally. Time-based hard stop (Tier 0) handles the close. The arbiter at Tier 1 in last 30 min becomes a no-op (reverts to Tier 2 behaviour: modules as designed).

This is a clean rule and dramatically reduces risk of late-session "death spiral" defense attempts.

---

**D6. STRADDLE_WITH_ADJUSTMENT — partial bypass with smart whipsaw ACTIVE**

User clarification (2026-04-27):
> "Straddle with adjustment is a strategy where we sell ATM call and put. There is no need for ATM shield because they are already ATM, and ATM gamma is structurally extremely high — that's why gamma is bypassed too. But we SHOULD use the smart whipsaw — that's a good feature because it protects us from unnecessary increase in position on both sides. Hard stop and smart whipsaw — they are the good combo."

**Decided rules for STRADDLE_WITH_ADJUSTMENT**:
| Feature | State for STRADDLE_WITH_ADJUSTMENT |
|---|---|
| Hard stop (Tier 0) | ACTIVE |
| ATM shield (Tier 0) | BYPASSED (positions are ATM by design) |
| Time-based hard stop (Tier 0) | ACTIVE |
| Gamma engine (Tier 1/3) | BYPASSED (ATM gamma is structural) |
| Smart whipsaw (Tier 3) | **ACTIVE** ← user explicit |
| Regime engine | ACTIVE (designed for elevated/normal) |
| Tier 1 defensive shift logic | ACTIVE |

**⚠️ CODE-VS-INTENT DISCREPANCY (FLAGGED FOR PHASE 1 AUDIT)**:

`mmm_whipsaw_smart.py:697-701` currently bypasses smart whipsaw for STRADDLE_WITH_ADJUSTMENT (forces `block = False`, `trigger_widen_factor = 1.0`, `lot_scalar = 1.0`). This contradicts the user's stated intent above.

Phase 1 deep-dive task: (a) identify when this bypass was introduced (git blame), (b) find the incident/test that motivated it, (c) determine whether the bypass is removeable or there's a real protection issue. Phase 3 arbiter must align with the user's stated rule — smart whipsaw ACTIVE for straddle.

Existing memory `feedback_straddle_gamma_bypass.md` documents only the gamma bypass — needs update after Phase 1 finds the truth about whipsaw bypass origin.

---

### Batch G — Edge cases (final batch)

**G1. Stale data / state freshness — TREAT STALE AS DANGEROUS**

User principle (2026-04-27):
> "As a trader, I never put my money on the blind spot. Otherwise that would be gambling. If some data is not refreshing in a beat, we should assume it as a danger."

**Rule**: if any signal the arbiter consumes (`_breakeven_zone`, `_margin_tier`, `_gamma_regime`, `_smart_ws_loss_velocity`) has not been refreshed within the current beat (or the immediately preceding beat as a 1-beat tolerance), the arbiter must:
1. Escalate the signal's severity to the next-higher tier (e.g., stale `_breakeven_zone='WARNING'` → treated as DANGER for arbiter purposes only; module's own state untouched)
2. Log it as a STALE event in the audit trail
3. Continue with the escalated decision (do NOT silently fall back to normal pipeline)

Implementation: each signal write must include a timestamp; arbiter checks `_signal_last_updated_ts` against current beat. Will be specified in Phase 3.

This rule is consistent with safety-first philosophy: when in doubt, assume the worse state.

---

**G2. Tier 0 simultaneous fire — close order**

Not explicitly addressed by user. **Default rule** (subject to user override): when multiple Tier 0 conditions fire in same beat, execute in this order:
1. ATM shield (if it would block a trade) — applied to current beat's pending trades
2. Time stop (if active) — closes positions per CLAUDE.md §5 close order (reverse → perp → core)
3. Hard stop (max_loss) — market-order exit per A1

Rationale: ATM shield is a per-beat gate; time stop is a closing operation; hard stop is the ultimate exit. Execution is naturally ordered.

If user wants different order, flag in future review.

---

**G3. Logging — concise summary + detailed audit trail**

User decision (2026-04-27):
> "Whenever the arbiter changes a decision, it should write down in activity or session logs so we can audit it and improve in future. Without data we cannot improve. So option (c) — concise summary and detailed audit trail."

**Rules**:

1. **Activity log (operator-visible)**: one concise line per beat where arbiter activated.
   ```
   [ARBITER] Tier 1 (BE=CRITICAL/PE) → shift CE to 78400 @ $98 prem, 3 lots
   ```

2. **Audit trail (structured JSON to session log)**: per-module decision record + arbiter override.
   ```json
   {
     "beat": 63,
     "tier_active": 1,
     "trigger": "_breakeven_zone=CRITICAL",
     "modules": {
       "whipsaw":  {"original": "BLOCK", "arbiter": "BYPASS", "reason": "Tier 1 active"},
       "regime":   {"original": "BLOCK_ALL_SELLS", "arbiter": "BYPASS", "reason": "Tier 1 active"},
       "harvester": {"original": "WOULD_RUN", "arbiter": "PAUSED", "reason": "Tier 1 paused"}
     },
     "action": {"type": "shift_and_sell", "side": "ce", "strike": 78400, "premium": 98, "lots": 3},
     "premium_target": 100,
     "tolerance": 10
   }
   ```

3. **Storage**: append to existing `mmm_activity_log.json` (visible in WebUI) AND to a new structured arbiter audit file `data/arbiter_audit_<sid>.jsonl` for replay/analysis.

4. **Phase 4 dependency**: the replay harness will consume the audit trail to reconstruct counterfactuals and parameter-tuning evidence.

---

### Batch E — Sizing / multiplier composition (resolved by D1)

Composition rules collapse cleanly under premium-per-lot mode:
- **E1, E2, E3 — RESOLVED**: at Tier 1, lot count is determined by `target_premium / premium_per_lot_at_chosen_strike`. Breakeven multiplier, whipsaw lot scalar, gamma lot reduction — all moot. The arbiter's Tier 1 output is one decision: strike + lots. At Tier 2 and below, existing multiplier composition logic is unchanged.

---

### Batch F — Time / strategy specifics (partial)

- **F1. Last 30 min tightening — RESOLVED (D5)**: Tier 1 bypass disabled.
- **F2. ODTE-specific hierarchy — implicit from D5**: ODTE sessions naturally hit "last 30 min" rule sooner; same logic applies. No separate ODTE hierarchy needed.
- **F3. STRADDLE_WITH_ADJUSTMENT — pending**, see D6.
- **F4. Reverse mode — RESOLVED (D4)**: isolated.

---

### Batch G — Edge cases (deferred to final batch)

- G1. _pending_ (stale data / staleness window for `_breakeven_zone`)
- G2. _pending_ (Tier 0 simultaneous fire — close order)
- G3. _pending_ (logging / audit when arbiter changes a decision)

---

## Operating notes for future sessions

1. **Read this file FIRST in any MMM coordination work.** It is the source of truth for the plan.
2. **Do not start coding the arbiter (Phase 3) until Phase 2 answers are complete.** Without the hierarchy, the arbiter is just another scattered if-check.
3. **Phase 2 is user-judgment work**, not code work. Claude's role is to ask precise questions and transcribe answers, not to suggest answers.
4. **If a new conflict scenario arises during Phase 1 mapping**, add it as a question in Phase 2 and ask the user — do not infer.
5. **Today's bug** (whipsaw ↛ breakeven) — DO NOT patch in isolation. It will be solved by Phase 3 when the arbiter is built. If user wants temporary protection in the meantime, add a minimal fix and mark it as a Phase 3 candidate for removal.

---

## Cross-references

- Memory index: `/Users/ssr/.claude/projects/-Users-ssr-Projects-WorkingBot/memory/MEMORY.md`
- MMM master context: `mmm_context.md` (in memory)
- Last 3 sessions: `MMM_LAST_3_SESSIONS.md`
- Full work log: `mmm_workdone_march.md`
- Project rules: `CLAUDE.md`
