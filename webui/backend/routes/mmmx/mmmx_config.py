"""
MMMX Config — Parameter Validation & Hot-Reload Allowlist

Spec: MMMX_COMPLETE.md Section 5 (Hot-Reload), MMMX_IMPLEMENTATION_PLAN.md Section 1.

Rules:
  - validate_params() is the gate before create_session() or any param update.
  - close_at_dte >= 7 is a HARD CONSTRAINT — rejected here, no exceptions.
  - HOT_RELOAD_ALLOWLIST defines which params can change while RUNNING/PAUSED.
  - Entry-gate params (DTE range, IV rank) are NOT hot-reloadable.
"""

import logging
from typing import Any, Dict, List, Tuple

from .mmmx_constants import CLOSE_AT_DTE_HARD_MIN

log = logging.getLogger('mmmx_config')

# ── Hot-reload allowlist ───────────────────────────────────────────────────────
# Keys present here can be patched via PATCH /api/mmmx/session/<id>/params
# while the session is RUNNING or PAUSED.
# Entry gates (entry_dte_min/max, entry_iv_rank_min) are NOT in this list.
HOT_RELOAD_ALLOWLIST = {
    'tranche_deploy_move_pct',
    'tranche_deploy_iv_delta',
    'hard_stop_multiplier',
    'adjustment_interval_hours',
    'delta_drift_threshold',
    'portfolio_delta_threshold',
    'near_itm_delta',
    'emergency_delta',
    'iv_spike_threshold_pct',
    'iv_catastrophe_pct',
    'atm_protect_threshold',
    'atm_shield_max_shifts',
    'fairness_gate_enabled',
    'fairness_threshold_pct',
    'max_deployments_per_day',
    'profit_booking_enabled',
    'profit_booking_targets',
    'hedging_enabled',
    'hedge_distance_pct',
    'hedge_execution_delay_minutes',
    'hedge_capacity_threshold_lots',
    'close_at_dte',
    'profit_target_pct',
    'profit_target_enabled',
    'whipsaw_window_mins',
    'whipsaw_spot_move_pct',
    'whipsaw_caution_score',
    'whipsaw_restrict_score',
    'whipsaw_cooldown_score',
    'whipsaw_cooldown_interval_hours',
    'otm_distance_pct',
}

# ── Validation rules: (min, max, type) ────────────────────────────────────────
_NUMERIC_BOUNDS: Dict[str, Tuple] = {
    'entry_dte_min':                  (1,    90,    int),
    'entry_dte_max':                  (1,    90,    int),
    'entry_iv_rank_min':              (0,    100,   (int, float)),
    'total_budget_lots':              (10,   1000,  int),
    'tranche_pct':                    (1,    50,    (int, float)),
    'otm_distance_pct':               (1.0,  50.0,  (int, float)),
    'tranche_deploy_move_pct':        (0.1,  20.0,  (int, float)),
    'tranche_deploy_iv_delta':        (1,    100,   (int, float)),
    'hard_stop_multiplier':           (1.0,  5.0,   (int, float)),
    'adjustment_interval_hours':      (0.25, 24.0,  (int, float)),
    'delta_drift_threshold':          (0.01, 1.0,   (int, float)),
    'portfolio_delta_threshold':      (0.01, 1.0,   (int, float)),
    'near_itm_delta':                 (0.1,  1.0,   (int, float)),
    'emergency_delta':                (0.1,  1.0,   (int, float)),
    'iv_spike_threshold_pct':         (1,    200,   (int, float)),
    'iv_catastrophe_pct':             (1,    300,   (int, float)),
    'atm_protect_threshold':          (0.5,  20.0,  (int, float)),
    'atm_shield_max_shifts':          (1,    10,    int),
    'fairness_threshold_pct':         (0.5,  50.0,  (int, float)),
    'max_deployments_per_day':        (1,    10,    int),
    'profit_target_pct':              (1,    100,   (int, float)),
    'hedge_distance_pct':             (10.0, 50.0,  (int, float)),
    'hedge_execution_delay_minutes':  (1,    60,    (int, float)),
    'hedge_capacity_threshold_lots':  (0,    100,   (int, float)),
    'close_at_dte':                   (CLOSE_AT_DTE_HARD_MIN, 60, int),
    'whipsaw_window_mins':            (5,    120,   (int, float)),
    'whipsaw_spot_move_pct':          (0.05, 5.0,   (int, float)),
    'whipsaw_caution_score':          (1,    10,    int),
    'whipsaw_restrict_score':         (1,    10,    int),
    'whipsaw_cooldown_score':         (1,    10,    int),
    'whipsaw_cooldown_interval_hours': (0.25, 24.0, (int, float)),
}

_BOOL_PARAMS = {
    'fairness_gate_enabled', 'profit_booking_enabled',
    'hedging_enabled', 'profit_target_enabled',
}

_LIST_PARAMS = {
    'profit_booking_targets',
}


class ConfigError(ValueError):
    """Raised when param validation fails."""
    pass


def validate_params(params: Dict[str, Any]) -> None:
    """
    Validate a full params dict.

    Raises ConfigError (subclass of ValueError) describing ALL failures found.
    close_at_dte < 7 always raises, regardless of other errors.

    Call this before create_session() or before applying a hot-reload patch.
    """
    errors: List[str] = []

    # ── Hard constraint first ─────────────────────────────────────────────────
    if 'close_at_dte' in params:
        val = params['close_at_dte']
        try:
            val = int(val)
        except (TypeError, ValueError):
            val = -1
        if val < CLOSE_AT_DTE_HARD_MIN:
            errors.append(
                f"close_at_dte={val} violates HARD MINIMUM of {CLOSE_AT_DTE_HARD_MIN}. "
                "No exceptions — position gamma risk in final week is unacceptable."
            )

    # ── Numeric bounds ────────────────────────────────────────────────────────
    for key, (lo, hi, expected_type) in _NUMERIC_BOUNDS.items():
        if key not in params:
            continue
        raw = params[key]
        if not isinstance(raw, expected_type):
            errors.append(f"{key}: expected {expected_type}, got {type(raw).__name__} ({raw!r})")
            continue
        if not (lo <= raw <= hi):
            errors.append(f"{key}={raw} out of range [{lo}, {hi}]")

    # ── Boolean params ────────────────────────────────────────────────────────
    for key in _BOOL_PARAMS:
        if key in params and not isinstance(params[key], bool):
            errors.append(f"{key}: must be bool, got {type(params[key]).__name__}")

    # ── List params ───────────────────────────────────────────────────────────
    if 'profit_booking_targets' in params:
        tgts = params['profit_booking_targets']
        if not isinstance(tgts, list):
            errors.append("profit_booking_targets must be a list")
        elif not all(isinstance(t, (int, float)) and 0 < t <= 100 for t in tgts):
            errors.append(
                "profit_booking_targets must be a list of floats in (0, 100]"
            )

    # ── Cross-field constraints ───────────────────────────────────────────────
    if 'entry_dte_min' in params and 'entry_dte_max' in params:
        if params['entry_dte_min'] >= params['entry_dte_max']:
            errors.append(
                f"entry_dte_min ({params['entry_dte_min']}) must be < "
                f"entry_dte_max ({params['entry_dte_max']})"
            )

    if 'near_itm_delta' in params and 'emergency_delta' in params:
        if params['near_itm_delta'] >= params['emergency_delta']:
            errors.append(
                f"near_itm_delta ({params['near_itm_delta']}) must be < "
                f"emergency_delta ({params['emergency_delta']})"
            )

    if 'whipsaw_caution_score' in params and 'whipsaw_restrict_score' in params:
        if params['whipsaw_caution_score'] >= params['whipsaw_restrict_score']:
            errors.append("whipsaw_caution_score must be < whipsaw_restrict_score")

    if 'whipsaw_restrict_score' in params and 'whipsaw_cooldown_score' in params:
        if params['whipsaw_restrict_score'] >= params['whipsaw_cooldown_score']:
            errors.append("whipsaw_restrict_score must be < whipsaw_cooldown_score")

    if errors:
        raise ConfigError(
            f"MMMX param validation failed ({len(errors)} error(s)):\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


def validate_hot_reload_patch(patch: Dict[str, Any]) -> None:
    """
    Validate a hot-reload patch dict.

    Raises ConfigError if any key is not in HOT_RELOAD_ALLOWLIST
    or if any value fails validate_params() rules.
    """
    disallowed = [k for k in patch if k not in HOT_RELOAD_ALLOWLIST]
    if disallowed:
        raise ConfigError(
            f"The following params are NOT hot-reloadable: {disallowed}. "
            "Stop the session and create a new one to change entry-gate params."
        )
    # Reuse validate_params for value checks (it ignores keys not in patch)
    validate_params(patch)


def split_hot_reload_patch(
    patch: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Split a hot-reload patch into accepted and rejected dicts without raising.

    - Keys not in HOT_RELOAD_ALLOWLIST → rejected with "not hot-reloadable" reason.
    - Keys in allowlist but failing value validation → rejected with the validation message.
    - All other keys → applied.

    Returns:
        (applied: {key: value}, rejected: {key: reason_str})
    """
    applied: Dict[str, Any] = {}
    rejected: Dict[str, str] = {}

    for key, value in patch.items():
        if key not in HOT_RELOAD_ALLOWLIST:
            rejected[key] = (
                f"'{key}' is not hot-reloadable. "
                "Stop the session and create a new one to change entry-gate params."
            )
            continue
        try:
            validate_params({key: value})
            applied[key] = value
        except ConfigError as exc:
            rejected[key] = str(exc)

    return applied, rejected


def diff_params(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a dict of keys whose value changed between old and new.
    Used by mmmx_param_audit to log exactly what changed.
    """
    return {
        k: {'old': old.get(k), 'new': new[k]}
        for k in new
        if new[k] != old.get(k)
    }
