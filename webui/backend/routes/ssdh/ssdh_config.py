"""
SSDH Config — Parameter Validation and Hot-Reload

Validates session parameters against PARAM_RULES.
Defines which params are hot-reloadable during a live session.

Created: March 21, 2026
"""

import re
import logging
from typing import Tuple, List

log = logging.getLogger('ssdh_config')

# =============================================================================
# Hot vs Cold parameter classification
# =============================================================================

HOT_RELOAD_PARAMS = [
    'max_loss_amount',
    'trailing_stop_pct',
    'vega_exit_multiplier',
    'vega_exit_auto',
    'margin_yellow_pct',
    'combined_margin_limit',
    'max_retries_on_fill',
    'circuit_breaker_threshold',
    'guardian_max_beat_sec',
    'adjustment_interval',
    'adaptive_interval_enabled',
    'adaptive_max_interval',
    'adaptive_min_interval',
]

# Locked at session creation — cannot be changed mid-session
COLD_PARAMS = [
    'initial_lots',
    'desired_ce_premium',
    'desired_pe_premium',
    'long_hedge_premium_target',
    'long_hedge_lots_ratio',
    'expiry',
    'entry_timeout_seconds',
    'min_otm_spread_pct',
    'min_otm_depth_lots',
    'intraday_max_loss_multiplier',
    'structure_integrity_check',
]

# =============================================================================
# Validation rules
# =============================================================================

PARAM_RULES = {
    'initial_lots':                {'type': int,   'min': 1,     'max': 100,   'hot': False},
    'desired_ce_premium':          {'type': float, 'min': 10.0,  'max': 50000, 'hot': False},
    'desired_pe_premium':          {'type': float, 'min': 10.0,  'max': 50000, 'hot': False},
    'long_hedge_premium_target':   {'type': float, 'min': 5.0,   'max': 5000,  'hot': False},
    'long_hedge_lots_ratio':       {'type': float, 'min': 1.0,   'max': 5.0,   'hot': False},
    'expiry':                      {'type': str,   'pattern': r'^\d{8}$',      'hot': False},  # ddmmyyyy
    'max_loss_amount':             {'type': float, 'min': 1.0,   'max': 100000,'hot': True},
    'trailing_stop_pct':           {'type': float, 'min': 0.1,   'max': 1.0,   'hot': True},
    'vega_exit_multiplier':        {'type': float, 'min': 1.0,   'max': 5.0,   'hot': True},
    'vega_exit_auto':              {'type': bool,                              'hot': True},
    'adjustment_interval':         {'type': int,   'min': 10,    'max': 300,   'hot': True},
    'adaptive_interval_enabled':   {'type': bool,                              'hot': True},
    'adaptive_max_interval':       {'type': int,   'min': 10,    'max': 300,   'hot': True},
    'adaptive_min_interval':       {'type': int,   'min': 5,     'max': 60,    'hot': True},
    'margin_yellow_pct':           {'type': float, 'min': 0.3,   'max': 0.95,  'hot': True},
    'combined_margin_limit':       {'type': float, 'min': 0.3,   'max': 0.95,  'hot': True},
    'max_retries_on_fill':         {'type': int,   'min': 1,     'max': 10,    'hot': True},
    'circuit_breaker_threshold':   {'type': int,   'min': 1,     'max': 20,    'hot': True},
    'guardian_max_beat_sec':       {'type': int,   'min': 30,    'max': 300,   'hot': True},
    'entry_timeout_seconds':       {'type': int,   'min': 60,    'max': 600,   'hot': False},
    'min_otm_spread_pct':          {'type': float, 'min': 0.05,  'max': 0.50,  'hot': False},
    'min_otm_depth_lots':          {'type': int,   'min': 1,     'max': 20,    'hot': False},
    'intraday_max_loss_multiplier':{'type': float, 'min': 1.0,   'max': 3.0,   'hot': False},
    'structure_integrity_check':   {'type': bool,                              'hot': False},
}

_BOOL_TRUE_STRINGS  = {'true', '1', 'yes', 'on'}
_BOOL_FALSE_STRINGS = {'false', '0', 'no', 'off'}


def _coerce(value, target_type):
    """
    Type-coerce value to target_type.
    str→bool: 'true'/'false'/'1'/'0' etc.
    str→int / str→float: standard cast.
    Returns coerced value, or raises ValueError on failure.
    """
    if isinstance(value, target_type):
        return value

    if target_type is bool:
        if isinstance(value, str):
            if value.lower() in _BOOL_TRUE_STRINGS:
                return True
            if value.lower() in _BOOL_FALSE_STRINGS:
                return False
        if isinstance(value, int):
            return bool(value)
        raise ValueError(f"Cannot coerce {value!r} to bool")

    if target_type is int:
        return int(float(str(value)))

    if target_type is float:
        return float(str(value))

    if target_type is str:
        return str(value)

    raise ValueError(f"Unknown target type: {target_type}")


def validate_params(params: dict, hot_only: bool = False) -> Tuple[dict, List[str]]:
    """
    Validates params against PARAM_RULES.

    If hot_only=True, only validates HOT_RELOAD_PARAMS (ignores cold params entirely).
    Type-coerces: str→bool, str→int, str→float where rule type matches.

    Returns (validated_params, errors).
    errors is [] if all valid.
    validated_params contains type-coerced values.
    """
    validated = {}
    errors = []

    rules_to_check = {
        k: v for k, v in PARAM_RULES.items()
        if (not hot_only) or v.get('hot', False)
    }

    for key, rule in rules_to_check.items():
        if key not in params:
            if not hot_only:
                # Only required if not hot_only mode
                # Some params are optional (have defaults from preset)
                pass
            continue

        raw = params[key]
        target_type = rule['type']

        # Type coercion
        try:
            value = _coerce(raw, target_type)
        except (ValueError, TypeError) as e:
            errors.append(f"{key}: cannot coerce {raw!r} to {target_type.__name__}: {e}")
            continue

        # Pattern check (str params only)
        if 'pattern' in rule:
            if not re.match(rule['pattern'], str(value)):
                errors.append(f"{key}: value {value!r} does not match pattern {rule['pattern']}")
                continue

        # Range check
        if 'min' in rule and value < rule['min']:
            errors.append(f"{key}: {value} < minimum {rule['min']}")
            continue
        if 'max' in rule and value > rule['max']:
            errors.append(f"{key}: {value} > maximum {rule['max']}")
            continue

        validated[key] = value

    # Pass through unknown params (not in PARAM_RULES at all).
    # In hot_only mode, skip known cold params even if not validated.
    for key, value in params.items():
        if key not in rules_to_check and key not in validated:
            if hot_only and key in PARAM_RULES:
                continue  # cold param — silently skip in hot_only mode
            validated[key] = value

    return validated, errors


def apply_hot_reload(session: dict, new_params: dict) -> Tuple[bool, List[str]]:
    """
    Applies hot-reloadable params from new_params to session['params'].
    Only updates keys that are in HOT_RELOAD_PARAMS.
    Validates each hot param before applying.

    Returns (success, errors).
    """
    hot_subset = {k: v for k, v in new_params.items() if k in HOT_RELOAD_PARAMS}
    if not hot_subset:
        return True, []

    validated, errors = validate_params(hot_subset, hot_only=True)
    if errors:
        return False, errors

    session['params'].update(validated)
    log.info("Hot-reload applied: %s", list(validated.keys()))
    return True, []


def compute_intraday_max_loss(theoretical_max: float, multiplier: float) -> float:
    """
    Returns theoretical_max × multiplier.
    Used to set max_loss_amount from the structure's theoretical max.
    """
    return float(theoretical_max) * float(multiplier)
