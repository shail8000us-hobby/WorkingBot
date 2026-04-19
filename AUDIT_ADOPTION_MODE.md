# AUDIT_ADOPTION_MODE.md

Date: 2026-04-18  
Scope: Adopted inventory mode (audit-only, no code changes)

## 1) Executive Summary

Adopted inventory mode has strong runtime protections in several areas (ownership isolation in reconciliation, strategy preflight on normal starts, and layered monitor safety architecture). However, there is one **critical trust-boundary gap** in the adopt API: payload fields (`symbol`, `strike`, `side`, `expiry`) are accepted without strict cross-validation. This can create mismatched internal state and lead to unmanaged real positions and wrong-contract behavior after start.

Overall assessment:
- ✅ Good: anti-auto-adopt posture, discrepancy tracking, strategy preflight on normal starts.
- ⚠️ Medium: cap checks at start for adopted sessions are incomplete (active-only).
- 🚨 Critical: payload congruence validation missing in adopt path.

## 2) Files Audited

- `webui/backend/routes/mmm/mmm_adopter.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_engine.py`
- `webui/backend/routes/mmm/mmm_trigger.py`
- `webui/backend/routes/mmm/mmm_state.py`
- `webui/backend/routes/mmm/mmm_strategy_dispatch.py`
- `webui/backend/routes/mmm/__init__.py`
- `webui/frontend/src/components/mmm/MMMAdoptPanel.js`
- `webui/frontend/src/components/mmm/mmmService.js`
- `webui/backend/routes/mmm/tests/test_sealed_mmm_adopter.py`
- `webui/backend/routes/mmm/tests/test_mmm_strategy_dispatch.py`
- `webui/backend/routes/mmm/tests/test_mmm_monitor_strategy_validation.py`
- `MMM_LAST_3_SESSIONS.md`

## 3) Findings

### F1 — **P0**: Adopt payload trust allows symbol/strike/side/expiry mismatch (wrong classification + strike mismatch + stale inherited positions)

**What I observed**
- Adopt endpoint validates required fields but does not validate consistency between fields:
  - No strict check that `symbol` encodes submitted `side`.
  - No strict check that `symbol` strike equals submitted `strike`.
  - No strict check that each position symbol expiry equals requested adopt/session expiry.
- Classification uses submitted `side`; state stores submitted `strike` and submitted `symbol` as-is.
- Runtime paths frequently rebuild symbols from `active_strike + session expiry`.

**Risk path**
- A mismatched payload can seed state where the adopted live contract and the contract used by runtime logic diverge.
- Reconciliation then compares against rebuilt symbols/expiry and may treat real positions as missing/untracked, while local state is auto-corrected away.
- Result: real exchange positions can remain open but unmanaged.

**Requested dimensions covered**: wrong classification, strike mismatch, stale inherited positions.

---

### F2 — **P1**: `trigger_mode=current_prices` silently degrades to entry baseline on ticker failure (trigger snapshot issue)

**What I observed**
- Adopt flow initializes trigger snapshots from entry prices in builder.
- API then tries to overwrite with live marks when `trigger_mode=current_prices`.
- If live fetch fails, behavior is warning-only; baseline remains entry-price fallback.

**Why this matters**
- Frontend defaults to `current_prices`.
- A transient fetch failure can silently set a stale baseline and cause immediate/early trigger behavior after start.

**Requested dimensions covered**: trigger snapshot issues.

---

### F3 — **P1**: Monitor auto-restore intentionally bypasses hard strategy-start gate (invalid strategy starts + recovery mode need)

**What I observed**
- `start_session_monitor(..., context='monitor_start')` blocks invariant violations.
- `context='monitor_restore'` warns/emits safety but allows monitor start in degraded shape.
- Backend init restore path uses `context='monitor_restore'` for active sessions.

**Why this matters**
- After restart, structurally invalid sessions can resume running without an explicit operator recovery workflow/state.
- This is intentional for continuity but operationally risky for strategy-shape-critical sessions.

**Requested dimensions covered**: invalid strategy starts, recovery mode need.

---

### F4 — **P2**: Adopted-start cap preflight is active-only; total exposure ceiling is not preflighted (caps after adopt)

**What I observed**
- Start preflight for adopted sessions checks `active_lots > max_lots_per_side`.
- It does not preflight `total_lots` vs `max_total_exposure` nor active+frozen over-cap scenarios.
- Engine later enforces active cap and total exposure during adjustments.

**Why this matters**
- Session can start in a state where exposure is already high and future hedging/sells are constrained by ceilings.
- This can produce “running but unable to adjust effectively” conditions.

**Requested dimensions covered**: caps after adopt.

---

### F5 — **P2**: Ownership-overlap check can fail open on storage exceptions (mixed ownership edge case)

**What I observed**
- `validate_adoptable` performs cross-session symbol overlap checks.
- On exceptions, it appends a warning and continues (not hard-fail).

**Why this matters**
- During storage faults/races, adoption can proceed without definitive ownership isolation confirmation.

**Requested dimensions covered**: mixed ownership.

---

### F6 — **P3**: Test coverage gap at API/integration boundary for adversarial adopt payloads

**What I observed**
- Strong unit coverage exists for adopter contracts and strategy dispatch rules.
- No evidence of route-level tests for malformed/mismatched adopt payload contracts (symbol-side-strike-expiry congruence) and no restore-degraded acceptance workflow tests.

**Why this matters**
- High-impact failures in trust-boundary logic are less likely to be caught pre-release.

## 4) Severity (P0/P1/P2/P3)

- **P0**
  - F1: Adopt payload congruence gap (symbol/strike/side/expiry mismatch acceptance)

- **P1**
  - F2: Silent fallback from current-price trigger initialization to entry-price baseline
  - F3: Auto-restore degraded starts without explicit recovery state/ack flow

- **P2**
  - F4: Incomplete cap preflight for adopted sessions (active-only)
  - F5: Overlap check fail-open when storage check errors

- **P3**
  - F6: Missing integration tests for adversarial adopt payloads/recovery workflows

## 5) Why It Matters

- This system executes real-money orders; trust-boundary defects are not cosmetic.
- Adopt mode is an import of already-live exposure; if mapping is wrong, subsequent protection logic can operate on the wrong contract set.
- A session that “looks healthy” but is misaligned with actual exchange inventory is the highest-risk failure mode because risk controls become non-representative.

## 6) Suggested Fix

Priority order (safe rollout):

1. **Hard-validate adopt payload congruence at API boundary (block on mismatch)**
   - Parse `symbol` server-side and derive canonical `side`, `strike`, `expiry`.
   - Reject if any submitted field conflicts with symbol-derived canonical values.
   - Reject mixed-expiry position lists unless explicitly supported by design.

2. **Make `trigger_mode=current_prices` explicit-failure behavior**
   - If live trigger seed fails for any active side, either:
     - fail adoption, or
     - return `success=false` with structured reason requiring explicit operator override.

3. **Add explicit recovery state for restore violations**
   - On restore-time invariant violations, set a non-trading recovery/degraded status requiring operator acknowledgment before normal trading actions.

4. **Extend start preflight for adopted sessions**
   - Validate both `active_lots` and `total_lots` against configured ceilings.
   - Include `max_total_exposure` preflight checks.

5. **Make overlap check fail-closed on storage exceptions**
   - Return error instead of warning when ownership isolation cannot be verified.

6. **Add route-level integration tests**
   - Symbol-side mismatch, symbol-strike mismatch, symbol-expiry mismatch.
   - Mixed-expiry payload attempt.
   - `current_prices` fetch failure behavior.
   - Restore-degraded behavior and required recovery flow.

## 7) Safe Implementation Notes for Claude

- Do **not** weaken stale monitor generation guards or hard-stop guard invariants in `mmm_monitor.py`.
- Keep reverse-mode invariants untouched (no cross-contamination into core CE/PE ledgers).
- Preserve existing anti-auto-adopt reconciliation philosophy: log/alert external positions, do not auto-claim them.
- Implement fixes at API validation boundary first (smallest blast radius), then preflight, then workflow/status enhancements.
- Add tests before broad refactors; verify with route-level tests + monitor restore tests.

## 8) Final Score /10

**6.2 / 10**

Rationale:
- + Good operational safety scaffolding and clear anti-auto-adopt runtime stance.
- + Existing strategy preflight and ownership reconciliation are substantial.
- − Critical trust-boundary validation gap in adopt payload congruence.
- − Recovery/start behavior has edge paths that can run degraded without explicit operator recovery workflow.
