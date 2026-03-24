"""
IC Configuration — Iron Condor

Default parameters, hot-reload support, and parameter validation.
Mirrors the pattern from mmm_config.py.

Created: 2026-03-24
"""

import logging
from typing import Dict, Any, Tuple, Set

log = logging.getLogger('ic_config')


# ─── Default Parameters (from IC_ALGO_PLAN.md §5) ───────────────────────────

DEFAULT_PARAMS = {
    # --- Entry ---
    'lots': 10,                          # Lots per leg (all 4 legs same size)
    'expiry_dte': 7,                     # Target days-to-expiry at entry
    'wing_width_strikes': 1,             # Fallback: wing = N strikes out from short
    'wing_width_usd': 1000,             # Primary: wing width in USD
    'short_put_delta_target': 0.16,     # Target |delta| for short put (0.16 ≈ 1σ)
    'short_call_delta_target': 0.16,    # Target |delta| for short call
    'strike_interval': 500,             # BTC strike grid interval in USD (hint only — we fetch real chain)

    # --- Heartbeat ---
    'adjustment_interval': 60,          # Seconds between heartbeats
    'rapid_check_interval': 15,         # Faster interval when breach is near

    # --- Exit ---
    'profit_target_pct': 50,            # Close when unrealized P&L ≥ X% of max credit
    'close_at_dte': 1,                  # Force-close when DTE falls below this
    'max_loss_pct': 100,                # Force-close when loss = X% of max loss

    # --- Adjustment Triggers ---
    'breach_pct': 5.0,                  # Adjust when spot is within X% of short strike
    'roll_tested_side_enabled': True,   # Auto-roll the threatened spread
    'roll_untested_side_enabled': True, # Also roll untested side closer for extra credit
    'max_adjustments_per_cycle': 3,     # Hard cap on rolls per cycle
    'adjustment_cooldown_sec': 300,     # Min seconds between adjustments

    # --- New Cycle ---
    'auto_cycle': True,                 # Automatically open next cycle after close
    'cycle_delay_sec': 30,              # Seconds between close and next entry
    'same_expiry_after_roll': True,     # Keep same expiry after roll

    # --- Safety ---
    'max_daily_loss_usd': 500,          # Stop trading today if total loss exceeds this
    'margin_safety_pct': 20,            # Pause if available margin < X% of required
    'circuit_breaker_enabled': True,    # Pause if 3+ adjustments in 1 hour

    # --- Entry Quality ---
    'min_net_credit_per_btc': 10.0,    # Reject entry if net credit < this (USD/BTC)
    'min_credit_to_wing_ratio': 0.03,  # Net credit must be ≥ 3% of wing width

    # --- Mode ---
    'simulate': False,                  # True = log decisions without placing real orders
}


# ─── Hot-Reload Parameters (can be changed without stopping session) ─────────

HOT_RELOAD_PARAMS = {
    'adjustment_interval', 'rapid_check_interval',
    'profit_target_pct', 'close_at_dte', 'max_loss_pct',
    'breach_pct', 'max_adjustments_per_cycle', 'adjustment_cooldown_sec',
    'roll_tested_side_enabled', 'roll_untested_side_enabled',
    'auto_cycle', 'cycle_delay_sec',
    'max_daily_loss_usd', 'margin_safety_pct', 'circuit_breaker_enabled',
    'min_net_credit_per_btc', 'min_credit_to_wing_ratio',
    'simulate',
}


# ─── Parameter validation rules ──────────────────────────────────────────────

PARAM_RULES = {
    # Entry
    'lots':                     {'type': int,   'min': 1,     'max': 1000,   'hot': False},
    'expiry_dte':               {'type': int,   'min': 0,     'max': 30,     'hot': False},
    'wing_width_strikes':       {'type': int,   'min': 1,     'max': 10,     'hot': False},
    'wing_width_usd':           {'type': float, 'min': 100,   'max': 10000,  'hot': False},
    'short_put_delta_target':   {'type': float, 'min': 0.05,  'max': 0.45,   'hot': False},
    'short_call_delta_target':  {'type': float, 'min': 0.05,  'max': 0.45,   'hot': False},
    'strike_interval':          {'type': int,   'min': 100,   'max': 5000,   'hot': False},

    # Heartbeat
    'adjustment_interval':      {'type': int,   'min': 10,    'max': 600,    'hot': True},
    'rapid_check_interval':     {'type': int,   'min': 5,     'max': 120,    'hot': True},

    # Exit
    'profit_target_pct':        {'type': float, 'min': 10,    'max': 100,    'hot': True},
    'close_at_dte':             {'type': float, 'min': 0,     'max': 7,      'hot': True},
    'max_loss_pct':             {'type': float, 'min': 50,    'max': 200,    'hot': True},

    # Adjustment Triggers
    'breach_pct':               {'type': float, 'min': 1.0,   'max': 20.0,   'hot': True},
    'roll_tested_side_enabled': {'type': bool,  'min': None,  'max': None,   'hot': True},
    'roll_untested_side_enabled': {'type': bool, 'min': None, 'max': None,   'hot': True},
    'max_adjustments_per_cycle': {'type': int,  'min': 1,     'max': 20,     'hot': True},
    'adjustment_cooldown_sec':  {'type': int,   'min': 30,    'max': 3600,   'hot': True},

    # New Cycle
    'auto_cycle':               {'type': bool,  'min': None,  'max': None,   'hot': True},
    'cycle_delay_sec':          {'type': int,   'min': 5,     'max': 600,    'hot': True},
    'same_expiry_after_roll':   {'type': bool,  'min': None,  'max': None,   'hot': True},

    # Safety
    'max_daily_loss_usd':       {'type': float, 'min': 10,    'max': 100000, 'hot': True},
    'margin_safety_pct':        {'type': float, 'min': 5,     'max': 80,     'hot': True},
    'circuit_breaker_enabled':  {'type': bool,  'min': None,  'max': None,   'hot': True},

    # Entry Quality
    'min_net_credit_per_btc':   {'type': float, 'min': 1,     'max': 100,    'hot': True},
    'min_credit_to_wing_ratio': {'type': float, 'min': 0.01,  'max': 0.50,   'hot': True},

    # Mode
    'simulate':                 {'type': bool,  'min': None,  'max': None,   'hot': True},
}


# ─── Parameter descriptions (for WebUI) ─────────────────────────────────────

PARAM_DESCRIPTIONS = {
    'lots': 'Number of lots per leg (all 4 legs trade the same quantity)',
    'expiry_dte': 'Target days-to-expiry when entering a new cycle',
    'wing_width_strikes': 'Fallback wing width in number of strikes (if wing_width_usd not set)',
    'wing_width_usd': 'Wing width in USD — directly sets max loss per BTC',
    'short_put_delta_target': 'Target |delta| for the short put (0.16 ≈ 1σ probability OTM)',
    'short_call_delta_target': 'Target |delta| for the short call (0.16 ≈ 1σ probability OTM)',
    'strike_interval': 'Expected BTC strike grid interval in USD (used as hint only; real chain is fetched from API)',
    'adjustment_interval': 'Seconds between heartbeat checks',
    'rapid_check_interval': 'Faster heartbeat interval when spot approaches a short strike',
    'profit_target_pct': 'Close cycle when unrealized P&L reaches this % of max credit',
    'close_at_dte': 'Force-close cycle when DTE drops below this many days (gamma risk)',
    'max_loss_pct': 'Force-close when unrealized loss reaches this % of max loss (100% = at max loss boundary)',
    'breach_pct': 'Trigger adjustment when spot is within this % of a short strike',
    'roll_tested_side_enabled': 'Auto-roll the threatened spread when breach is detected',
    'roll_untested_side_enabled': 'Roll the untested side closer for extra credit when rolling tested side',
    'max_adjustments_per_cycle': 'Hard cap on roll adjustments per cycle — exit cycle if reached',
    'adjustment_cooldown_sec': 'Minimum seconds between consecutive adjustments',
    'auto_cycle': 'Automatically open next cycle after closing the current one',
    'cycle_delay_sec': 'Wait this many seconds between closing a cycle and opening the next',
    'same_expiry_after_roll': 'Keep the same expiry after a roll (vs picking a new one)',
    'max_daily_loss_usd': 'Stop trading for the day if cumulative loss exceeds this USD amount',
    'margin_safety_pct': 'Pause session if available margin drops below this % of required margin',
    'circuit_breaker_enabled': 'Pause session if 3+ adjustments occur within 60 minutes',
    'min_net_credit_per_btc': 'Reject entry if net credit < this USD/BTC (avoids bad risk:reward)',
    'min_credit_to_wing_ratio': 'Net credit must be ≥ this fraction of wing width (risk:reward sanity)',
    'simulate': 'Simulate mode — log all decisions without placing real orders',
}


def validate_params(params: Dict[str, Any], hot_only: bool = False) -> Tuple[Dict[str, Any], list]:
    """
    Validate and coerce parameter values.

    Args:
        params: Dictionary of parameter name → value
        hot_only: If True, reject non-hot-reloadable parameters

    Returns:
        Tuple of (validated_params, errors)
    """
    validated = {}
    errors = []

    for key, value in params.items():
        if key not in PARAM_RULES:
            # Skip unknown params (may come from frontend/defaults merge)
            continue

        rule = PARAM_RULES[key]

        # Check hot-reload restriction
        if hot_only and not rule['hot']:
            errors.append(f"Parameter '{key}' cannot be changed while running (not hot-reloadable)")
            continue

        # Type coercion
        try:
            if rule['type'] == bool:
                if isinstance(value, str):
                    validated[key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    validated[key] = bool(value)
            elif rule['type'] == int:
                validated[key] = int(value)
            elif rule['type'] == float:
                validated[key] = float(value)
            elif rule['type'] == str:
                validated[key] = str(value)
        except (ValueError, TypeError):
            errors.append(
                f"Parameter '{key}': invalid type. "
                f"Expected {rule['type'].__name__}, got {type(value).__name__}"
            )
            continue

        # Range validation
        if rule['min'] is not None and validated[key] < rule['min']:
            errors.append(f"Parameter '{key}': {validated[key]} below minimum {rule['min']}")
            continue
        if rule['max'] is not None and validated[key] > rule['max']:
            errors.append(f"Parameter '{key}': {validated[key]} above maximum {rule['max']}")
            continue

    # Cross-parameter validation
    _interdependency_checks(validated, errors)

    return validated, errors


def _interdependency_checks(validated: Dict[str, Any], errors: list):
    """Validate cross-parameter relationships."""
    # rapid_check_interval must be < adjustment_interval
    rapid = validated.get('rapid_check_interval')
    normal = validated.get('adjustment_interval')
    if rapid is not None and normal is not None and rapid >= normal:
        errors.append(
            f"rapid_check_interval ({rapid}) must be < adjustment_interval ({normal})"
        )

    # profit_target_pct must be > 0 and <= 100
    ptp = validated.get('profit_target_pct')
    if ptp is not None and ptp <= 0:
        errors.append(f"profit_target_pct ({ptp}) must be > 0")

    # breach_pct sanity: should not be > 15%
    breach = validated.get('breach_pct')
    if breach is not None and breach > 15:
        errors.append(
            f"breach_pct ({breach}) > 15% is unusually wide — adjustments may never trigger"
        )


def get_hot_reload_params() -> Set[str]:
    """Return set of parameter names that support hot-reload."""
    return {k for k, v in PARAM_RULES.items() if v.get('hot', False)}


def get_param_info() -> Dict[str, Dict]:
    """Return parameter metadata for WebUI display."""
    info = {}
    for key, rule in PARAM_RULES.items():
        info[key] = {
            'type': rule['type'].__name__,
            'min': rule['min'],
            'max': rule['max'],
            'hot_reload': rule['hot'],
            'description': PARAM_DESCRIPTIONS.get(key, ''),
        }
    return info
