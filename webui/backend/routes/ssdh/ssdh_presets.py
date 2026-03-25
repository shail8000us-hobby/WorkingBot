"""
SSDH Presets — Default Parameter Sets

One source of truth for default parameter values.
User-provided values override preset defaults.

Created: March 21, 2026
"""

import logging
from copy import deepcopy

log = logging.getLogger('ssdh_presets')

# =============================================================================
# SSDH Preset
# =============================================================================

PRESET_SSDH = {
    'strategy':                     'ssdh',
    'session_window_hours':         4.0,
    'long_hedge_lots_ratio':        2.0,      # 2× long hedge for each short lot
    'trailing_stop_pct':            0.50,     # stop at 50% drawdown from peak
    'wind_down_mins_before_end':    30,       # begin exit 30 min before session end
    'vega_exit_multiplier':         1.50,     # exit if shorts expand 1.5× entry
    'vega_exit_auto':               False,    # warn only by default (don't auto-exit)
    'adjustment_interval':          30,       # heartbeat every 30s at normal P&L
    'adaptive_interval_enabled':    True,
    'adaptive_max_interval':        60,       # slowest: 60s when P&L < 25% of max_loss
    'adaptive_min_interval':        10,       # fastest: 10s when P&L > 50% of max_loss
    'entry_timeout_seconds':        180,      # 3 min to fill all 4 legs
    'min_otm_spread_pct':           0.20,     # reject OTM strike if spread > 20%
    'min_otm_depth_lots':           2,        # OTM must have at least 2 lots depth
    'intraday_max_loss_multiplier': 1.75,     # intraday loss = theoretical × 1.75
    'combined_margin_limit':        0.70,     # cross-engine margin cap at 70%
    'margin_yellow_pct':            0.65,     # warn at 65% margin utilisation
    'circuit_breaker_threshold':    5,        # open circuit after 5 consecutive API errors
    'max_retries_on_fill':          4,        # 4 × 60s = 4-min max per leg
    'guardian_max_beat_sec':        90,       # warn if heartbeat takes > 90s
    'structure_integrity_check':    True,     # verify all 4 legs every heartbeat

    # NOT set here — user provides at session creation:
    #   initial_lots, desired_ce_premium, desired_pe_premium,
    #   long_hedge_premium_target, expiry
    # NOT set here — computed at entry:
    #   max_loss_amount = theoretical_max × intraday_max_loss_multiplier
}

PRESETS = {
    'ssdh': PRESET_SSDH,
}


# =============================================================================
# Preset access functions
# =============================================================================

def get_preset(name: str) -> dict:
    """
    Returns a deep copy of the preset dict.
    Raises ValueError if not found.
    """
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name!r}. Available: {list(PRESETS.keys())}")
    return deepcopy(PRESETS[name])


def list_presets() -> list:
    """
    Returns list of preset metadata dicts.
    Each dict has: name, strategy, description.
    """
    return [
        {
            'name':        'ssdh',
            'strategy':    'ssdh',
            'description': (
                'Short Straddle Double Hedge — sell 1× ATM CE + 1× ATM PE, '
                'buy 2× OTM CE + 2× OTM PE. Net credit with defined max loss.'
            ),
        }
    ]


def apply_preset_to_params(base_params: dict, preset_name: str) -> dict:
    """
    Merges preset defaults into base_params.
    User-provided values in base_params override preset defaults.

    Returns merged params dict (does not mutate base_params).
    """
    preset = get_preset(preset_name)
    # Start from preset defaults, then overlay user-provided values
    merged = {**preset, **base_params}
    return merged
