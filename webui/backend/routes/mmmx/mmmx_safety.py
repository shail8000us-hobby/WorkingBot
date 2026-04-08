"""
MMMX Safety — Pre-Beat Safety Checks

Runs before any trigger evaluation or market action.
All checks are pure (no I/O, no exchange calls).
Returns immediately on first abort condition.

Key function:
    pre_beat_check(session, stored_gen, my_generation) -> SafetyVerdict

SafetyVerdict fields:
    ok (bool)          — True if all checks pass (no abort, no skip)
    skip_beat (bool)   — True if beat should be skipped (non-fatal; monitor continues)
    abort (bool)       — True if monitor should self-stop (fatal condition)
    reason (str)       — Short code describing the check that fired

Priority order:
  1. STALE_GENERATION  — stored_gen != my_generation        → abort
  2. STATUS guard      — status not in RUNNING/PAUSED       → skip_beat
  3. PNL_INCOMPLETE    — _pnl_calculation_incomplete=True   → skip_beat
  4. EXPIRY_PAST       — compute_dte_days(...) < 0          → abort
  5. Naked scan        — _naked_positions not empty         → log warning only

Isolation: ZERO imports from the MMM namespace — mmmx namespace only.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict

log = logging.getLogger('mmmx_safety')


# ── SafetyVerdict ─────────────────────────────────────────────────────────────

@dataclass
class SafetyVerdict:
    """Result of pre_beat_check()."""
    ok: bool = True
    skip_beat: bool = False
    abort: bool = False
    reason: str = ''


# ── Pre-beat check ────────────────────────────────────────────────────────────

def pre_beat_check(
    session: Dict[str, Any],
    stored_gen: int,
    my_generation: int,
) -> SafetyVerdict:
    """
    Run all pre-beat safety checks in priority order.
    Returns immediately on first abort condition.

    Args:
        session:      Fresh session dict loaded from storage.
        stored_gen:   Generation number currently in the DB.
        my_generation: This monitor's generation number.

    Returns:
        SafetyVerdict — callers must check .abort and .skip_beat before proceeding.
    """
    # ── 1. Generation guard ───────────────────────────────────────────────────
    if stored_gen != my_generation:
        log.error(
            f"[mmmx_safety] Generation mismatch: stored={stored_gen}, "
            f"mine={my_generation} — STALE_GENERATION"
        )
        return SafetyVerdict(ok=False, abort=True, reason='STALE_GENERATION')

    # ── 2. Status guard ───────────────────────────────────────────────────────
    status = session.get('status', '')
    if status not in ('RUNNING', 'PAUSED'):
        log.debug(f"[mmmx_safety] Status guard: {status!r} — skipping beat")
        return SafetyVerdict(ok=False, skip_beat=True, reason=f'STATUS_{status}')

    # ── 3. P&L completeness ───────────────────────────────────────────────────
    if session.get('_pnl_calculation_incomplete', False):
        log.warning("[mmmx_safety] PNL_INCOMPLETE — skipping beat")
        return SafetyVerdict(ok=False, skip_beat=True, reason='PNL_INCOMPLETE')

    # ── 4. DTE sanity ─────────────────────────────────────────────────────────
    from .mmmx_engine import compute_dte_days
    expiry = session.get('expiry_datetime')
    dte = compute_dte_days(expiry)
    if dte < 0:
        log.error(
            f"[mmmx_safety] EXPIRY_PAST: dte={dte} for expiry={expiry!r}"
        )
        return SafetyVerdict(ok=False, abort=True, reason='EXPIRY_PAST')

    # ── 5. Naked position scan (warn only — watchdog handles escalation) ──────
    naked = session.get('_naked_positions', [])
    if naked:
        log.warning(
            f"[mmmx_safety] Naked positions detected (count={len(naked)}): "
            + str([p.get('tranche_id') for p in naked])
        )
        # DO NOT abort or skip — naked watchdog handles escalation

    return SafetyVerdict(ok=True)
