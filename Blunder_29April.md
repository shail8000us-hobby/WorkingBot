# Blunder_29April.md — Sealed Test Count Underreporting Incident

**Date**: 2026-04-29  
**Severity**: Reporting Error (no code broken, no tests deleted)  
**Discovered by**: User — "why sealed test has reduced, they were more than 1400"

---

## What Happened

Throughout the entire session of 2026-04-29, the AI ran the **wrong pytest command** every time it verified the sealed test suite.

**Command actually used (wrong):**
```bash
python3 -m pytest webui/backend/routes/mmm/tests/ -m sealed -q
```

**Command required per AI_SEAL.md (correct):**
```bash
python3 -m pytest webui/ bot/ -m sealed -v
```

This caused the AI to report 1,202 → 1,206 tests passing across multiple checkpoints in the session, when the real count was 1,632 (pre-session) → 1,647 (post-session with new tests added).

**Tests were never deleted. The count actually increased by 15 this session.**

---

## Impact

| Metric | Reported (wrong) | Actual (correct) |
|--------|-----------------|-----------------|
| Tests at session start | ~1,202 | 1,632 |
| Tests at session end | 1,206 | 1,647 |
| Tests added this session | 4 (appeared to add 4) | 15 (actual) |
| Tests "missing" from report | 441 | 0 |

The 441 tests that were invisible to the wrong command come from:

| Directory | Tests hidden |
|-----------|-------------|
| `bot/strategy/modules/tests/` | 60 (gridbot sealed tests) |
| `bot/guardian/collectors/tests/` | 9 |
| `bot/options/utils/tests/` | ~50 |
| `webui/backend/services/tests/` | ~55 (price alerts, private WS, auto-loop) |
| `webui/backend/routes/options/tests/` | ~90 |
| `webui/backend/routes/ssdh/tests/` | ~50 |
| `webui/backend/routes/tests/` | ~17 |
| `webui/backend/options_chain/tests/` | ~13 |
| `webui/backend/options_strategy/tests/` | ~24 |
| `webui/backend/utils/tests/` | 7 |
| `webui/frontend/tests/` (Jest bridge) | 9 |
| **Total hidden** | **~441** |

---

## Root Cause

The AI habitually scoped pytest to `webui/backend/routes/mmm/tests/` because that is the directory being actively edited. This is a correct shortcut for fast iteration, but it should **never be used as the final verification or reporting command**.

AI_SEAL.md Section "RUN ALL SEALED TESTS" states explicitly:

> ```bash
> python3 -m pytest webui/ bot/ -m sealed -v
> ```
> **This single command covers ALL sealed functions — Python AND JavaScript.**
> Run it before every deployment, every morning, and after any code change.

The AI ignored this instruction at every checkpoint.

---

## Actual Sealed Test State (Correct, as of 2026-04-29 post-session)

**Total: 1,647 passing**

### By file (top files):

| Tests | File |
|-------|------|
| 93 | `webui/backend/routes/mmm/tests/test_sealed_mmm_safety.py` |
| 87 | `webui/backend/routes/mmm/tests/test_sealed_audit_fixes.py` |
| 70 | `webui/backend/routes/mmm/tests/test_sealed_mmm_pnl_core.py` |
| 60 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` |
| 51 | `webui/backend/routes/mmm/tests/test_sealed_mmm_regime.py` |
| 42 | `webui/backend/routes/mmm/tests/test_mmm_adaptive.py` |
| 38 | `webui/backend/services/tests/test_sealed_price_alerts.py` |
| 37 | `webui/backend/routes/mmm/tests/test_sealed_mmm_close_at_5.py` |
| 36 | `webui/backend/routes/mmm/tests/test_sealed_mmm_reversal.py` |
| 36 | `webui/backend/routes/mmm/tests/test_sealed_mmm_replenish.py` |
| 35 | `webui/backend/routes/mmm/tests/test_sealed_mmm_strike_shift.py` |
| 35 | `webui/backend/routes/mmm/tests/test_sealed_mmm_atm_shield.py` |
| 34 | `webui/backend/routes/mmm/tests/test_sealed_mmm_adversarial_isolation.py` |
| 32 | `webui/backend/routes/mmm/tests/test_sealed_mmm_wind_down.py` |
| 31 | `webui/backend/routes/mmm/tests/test_sealed_mmm_dte_presets.py` |
| 30 | `webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py` |
| 28 | `webui/backend/routes/ssdh/tests/test_sealed_ssdh_pnl.py` |
| 26 | `webui/backend/routes/mmm/tests/test_sealed_compute_adaptive_interval.py` |
| 25 | `webui/backend/routes/mmm/tests/test_sealed_margin_guardian.py` |
| 24 | `webui/backend/routes/mmm/tests/test_sealed_mmm_margin_guardian_async.py` |
| ... | *(90 more files)* |

### Breakdown by area:

| Area | Sealed Tests |
|------|-------------|
| MMM Algo (`webui/backend/routes/mmm/tests/`) | 1,206 |
| Bot (`bot/`) | 117 |
| WebUI non-MMM (`webui/` excl. mmm) | 324 |
| **Total** | **1,647** |

---

## New Tests Added This Session (All Passing)

| Class | Tests | File | Covers |
|-------|-------|------|--------|
| `TestArbiterRule8CapacityHardStop` | 4 | `test_sealed_audit_fixes.py` | Arbiter blocks shift when `total_lots >= max_lots_per_side` |
| `TestArbiterRule8ATMShieldHardStop` | 3 | `test_sealed_audit_fixes.py` | Arbiter blocks shift when `_atm_shield_fired` |
| `TestArbiterRule8MonitorWiring` | 3 | `test_sealed_audit_fixes.py` | Source-presence: guard code exists in monitor |
| `TestATMShieldCapUsesFrozenLots` | 4 | `test_sealed_mmm_atm_shield.py` | ATM shield cap uses `total_lots` not `active_lots` |
| **Total new** | **14** | | |

*(Registry shows 15 net — 1 was pre-existing from the mmm_adaptive test file reclassification.)*

---

## Fix

**Immediate**: The correct command has been verified and confirmed working:

```bash
python3 -m pytest webui/ bot/ -m sealed -v
# Output: 1647 passed, 1114 deselected
```

**Protocol fix for future sessions**: The AI must use `webui/ bot/` scope for ALL final verifications and reporting, regardless of which subdirectory is being edited. Narrow scope (`webui/backend/routes/mmm/tests/`) is acceptable during active iteration but must NEVER be reported as the final count.

---

## What Was NOT Blundered

- No sealed tests were deleted.
- No sealed functions were modified without proper UNSEAL/re-seal.
- All 1,647 tests pass.
- The AI_ALREADY_SEALED.md registry is accurate (86 entries, last updated Apr 29, 2026).
- All code fixes from this session (Rule 8, delta-neutral cap, A7-01, ledger option_side, ATM shield cap) are correct and sealed.

---

## Verification Command

```bash
python3 -m pytest webui/ bot/ -m sealed -q
# Expected: 1647 passed
```
