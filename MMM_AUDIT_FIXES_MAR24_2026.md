# MMM Forensic Audit — Fix Tracker
**Date**: 24 March 2026
**Auditor**: Senior Quant Architect + Distributed Systems Engineer role
**Branch**: SSR
**Status**: IN PROGRESS

---

## Audit Summary

Full forensic architectural audit of the MMM (Money Mind & Method) short-straddle theta-decay harvesting system.
12 distinct issues found across 6 severity levels.
6 issues selected for safe implementation; 3 deemed too risky/complex for this session.

---

## Issues & Fix Status

### P0 — CRITICAL BUGS (affect correctness of live trading)

#### BUG-C1: Straddle Initial Credit Always Zero
- **File**: `webui/backend/routes/mmm/mmm_monitor.py`
- **Lines**: ~344–352 (credit calculation) + ~334 (guard)
- **Root Cause**: `pos.get('original_lots', 0)` used but position dicts have key `lots`, not `original_lots`. `original_lots` is a side-state aggregate field, not a per-position field. Result: credit always 0, meaning Gate 9 (credit quality) and Gate 10 (realized P&L vs credit) are permanently bypassed.
- **Fix**: Change both `original_lots` → `lots`. Add version flag `_straddle_credit_v2` so existing sessions with stale zero-credit get recomputed on next heartbeat.
- **Status**: ✅ FIXED

#### SYNC-3: Being-Closed Positions Counted in Loss Calculation
- **File**: `webui/backend/routes/mmm/mmm_engine.py`
- **Lines**: ~156–163 (frozen_positions loop)
- **Root Cause**: When a close order is placed, `_being_closed=True` is stamped on the position dict. The loss engine iterates `frozen_positions` (derived view of positions with `_being_closed` included) without skipping this flag. For one heartbeat interval (~30s), the position is counted as open loss even though a close order is in flight. This can trigger a second close attempt.
- **Fix**: Add `if pos.get('_being_closed'): continue` in the frozen positions loop.
- **Status**: ✅ FIXED

---

### P1 — SYNC ISSUES (affect trigger/hedge accuracy)

#### SYNC-4: Whipsaw Multiplier Applied to Already-Accelerated Base
- **File**: `webui/backend/routes/mmm/mmm_monitor.py`
- **Lines**: ~2328–2334
- **Root Cause**: Whipsaw logic reads `_effective_min_trigger_move` as its base value. This field may already have theta-acceleration applied (doubling the base trigger near expiry). Multiplying again compounds multiplicatively rather than additively. A theta×whipsaw scenario yields 4× the intended trigger width.
- **Fix**: Always use `params.get('min_trigger_move', 10.0)` as the base. Apply `max(whipsaw_widened, theta_accelerated)` to preserve whichever is larger rather than multiplying them together.
- **Status**: ✅ FIXED

#### HID-1: Checksum Covers Derived/Empty Fields
- **File**: `webui/backend/routes/mmm/mmm_storage.py`
- **Lines**: ~257–273
- **Root Cause**: `_calculate_checksum()` includes `ce_frozen`/`pe_frozen` (derived views rebuilt from `positions[]` on load — can differ from save due to `_being_closed` transient flag) and `fills`/`trade_history`/`positions` (always `[]`/`{}` in MMM sessions). Legitimate state changes that don't affect canonical data appear as corruption. True corruption that only hits derived views is missed.
- **Fix**: Introduce `_checksum_v2` covering only canonical fields: `session_id`, `params`, `strategy_status`, `ce.positions[]`, `pe.positions[]`, `realized_pnl`, `total_fees`. Save both v1 (for backward compat) and v2. On load, prefer v2 if present.
- **Status**: ✅ FIXED

---

### P1 — ARCHITECTURE GAPS

#### ARCH-1: No Automatic Reconciliation
- **File**: `webui/backend/routes/mmm/mmm_monitor.py` (heartbeat), `mmm_state.py` (DEFAULT_PARAMS)
- **Root Cause**: `mmm_audit_reconciler.reconcile_session()` exists but is only triggered by a manual REST API call. Silent drift between exchange state and bot state can go undetected indefinitely.
- **Fix**: Add auto-reconcile every N beats (default 50, ~25 min). On mismatch, emit `SAFETY_ALERT` to Telegram and log. Add `auto_recon_interval_beats` to `DEFAULT_PARAMS`.
- **Status**: ✅ FIXED

---

### P2 — HIDDEN BUGS (degrade over time)

#### HID-2: Trigger Snapshot Entries Never Pruned
- **File**: `webui/backend/routes/mmm/mmm_trigger.py`
- **Lines**: `update_trigger_snapshots()` ~309–401
- **Root Cause**: `trigger_snapshot` dict accumulates entries for every strike ever active. Closed positions' strikes are never removed. In long-running sessions with many rolls/adjustments, this dict grows unboundedly and stale entries could theoretically match a re-opened position at the same strike with an incorrect (historical) baseline.
- **Fix**: After updating, prune entries for strikes that have no open (non-closed) positions in either CE or PE side.
- **Status**: ✅ FIXED

---

## Issues NOT Fixed This Session (too risky / fundamental design)

| ID | Issue | Reason Deferred |
|----|-------|-----------------|
| BUG-C2 | Pending order state lost on crash | Requires new SQLite table + migration |
| BUG-C3 | Fill sync cursor advances past unmatched external closes | Fundamental cursor design, needs broader rework |
| SYNC-1 | Crash window between order placement and state save | Inherent architecture, needs saga/WAL pattern |
| SYNC-2 | Stale premium data triggers with mismatched legs | Partially mitigated by data confidence gate |
| ARCH-2 | Heartbeat creates new event loop per cycle | Performance only, no correctness impact |
| ARCH-3 | Circuit breaker state not persisted | Low impact; resets on restart |

---

## Test Plan
- Run full pytest suite after all fixes
- Verify: BUG-C1 fixed by checking `_straddle_initial_credit` is non-zero when positions exist
- Verify: SYNC-3 fixed by checking `_being_closed` positions skipped
- Verify: Checksum v2 written and loaded correctly
- Verify: No new test failures introduced

---

## Git
- Commit message: `fix(mmm): forensic audit fixes - straddle credit, loss calc, whipsaw, checksum, auto-recon, snapshot pruning`
- Tag: `Morning 24 March 2026`
