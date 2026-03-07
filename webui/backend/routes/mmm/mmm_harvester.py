"""
MMM Profit Harvesting (M1) + Asymmetry Rebalancing (M3) — Money Mind & Method

M1: Every heartbeat, scans frozen/shifted positions and closes them early
when they have decayed enough to be profitable. Frees lot capacity before
the position book hits the max-lot wall.

M3: When asymmetry ratio is high (one side dominates), relaxes harvest
thresholds on the dominant side to aggressively free capacity and prevent
the one-sided accumulation death spiral.

See MMM_LOT_RECYCLING_IMPLEMENTATION_PLAN.md §3 (M1) and §5 (M3).

Created: March 3, 2026
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from .mmm_constants import LOT_SIZE_BTC, _D, _LOT

log = logging.getLogger('mmm_harvester')


# =============================================================================
# §3.3 / §5.2: M3 Asymmetry-Aware Threshold Modifier
# =============================================================================

def get_effective_harvest_params(session: Dict, side: str) -> Dict:
    """
    M3: Relax harvest thresholds when side asymmetry is extreme.

    When one side has >> lots than the other AND is near capacity, we
    aggressively harvest frozen positions on the dominant side to prevent
    the one-sided accumulation death spiral.

    Args:
        session: Full session dict
        side: 'ce' or 'pe' — the side being evaluated for harvesting

    Returns:
        Dict of overridden params (partial), or {} to use defaults.
    """
    params = session.get('params', {})

    if not params.get('rebalance_enabled', True):
        return {}

    ce_lots = session.get('ce', {}).get('total_lots', 0)
    pe_lots = session.get('pe', {}).get('total_lots', 0)
    max_lots = max(params.get('max_lots_per_side', 100), 1)

    my_lots = ce_lots if side == 'ce' else pe_lots
    other_lots = pe_lots if side == 'ce' else ce_lots

    asymmetry = my_lots / max(other_lots, 1)
    pressure = my_lots / max_lots

    asym_threshold = params.get('rebalance_asymmetry_threshold', 5.0)
    pressure_threshold = params.get('rebalance_pressure_threshold', 0.8)
    base_profit_pct = params.get('harvest_profit_pct', 40.0)

    if asymmetry > asym_threshold and pressure > pressure_threshold:
        # Extreme asymmetry — aggressively harvest dominant side
        return {
            'harvest_profit_pct': max(base_profit_pct * 0.6, 20.0),
            'harvest_max_per_beat': 5,
            'harvest_pressure_threshold': 0.3,
            '_boosted': True,
            '_boost_level': 'extreme',
        }
    elif asymmetry > (asym_threshold * 0.6) and pressure > 0.6:
        # Moderate asymmetry — slightly relax
        return {
            'harvest_profit_pct': max(base_profit_pct * 0.8, 25.0),
            'harvest_max_per_beat': 4,
            'harvest_pressure_threshold': 0.5,
            '_boosted': True,
            '_boost_level': 'moderate',
        }

    return {}  # Use defaults


# =============================================================================
# §3.2-3.3: Harvest Eligibility Scan
# =============================================================================

def scan_harvestable_positions(
    session: Dict,
    fetch_premium_fn,
) -> List[Dict[str, Any]]:
    """
    §3.2: Scan frozen/shifted positions for profit harvesting eligibility.

    A frozen position is eligible for harvesting if ALL of these are true:
      1. type is 'frozen' (status='shifted' in positions ledger)
      2. profit_pct >= harvest_profit_pct  (entry - current) / entry * 100
      3. position_age >= harvest_min_age_mins
      4. capacity_pressure >= harvest_pressure_threshold (total / max >= threshold)

    Args:
        session: Full session dict
        fetch_premium_fn: callable(strike, option_type) → current_premium

    Returns:
        List of harvestable positions sorted by harvest_score descending.
        Each entry is compatible with close_position() from mmm_close_at_5.
    """
    params = session.get('params', {})

    if not params.get('harvest_enabled', True):
        return []

    max_lots = max(params.get('max_lots_per_side', 100), 1)
    harvest_min_age_mins = params.get('harvest_min_age_mins', 30)
    session_id = session.get('session_id', '?')
    now = datetime.now(timezone.utc)

    harvestable = []

    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'
        total_side_lots = side_state.get('total_lots', 0)

        # Get effective params (M3 asymmetry override) — once per side
        overrides = get_effective_harvest_params(session, side_key)

        harvest_profit_pct = overrides.get(
            'harvest_profit_pct',
            params.get('harvest_profit_pct', 40.0),
        )
        harvest_pressure_threshold = overrides.get(
            'harvest_pressure_threshold',
            params.get('harvest_pressure_threshold', 0.6),
        )

        # §3.2 criterion 4: Check capacity pressure
        capacity_pressure = total_side_lots / max_lots
        if capacity_pressure < harvest_pressure_threshold:
            log.debug(
                f"[{session_id}] {side_key.upper()} harvest: "
                f"pressure {capacity_pressure:.2f} < threshold "
                f"{harvest_pressure_threshold:.2f} — skipping"
            )
            continue

        frozen_positions = side_state.get('frozen_positions', [])
        if not frozen_positions:
            continue

        # Pre-build set of in-flight position IDs (O(1) lookup instead of O(N) scan)
        being_closed_ids = {
            p.get('id') for p in side_state.get('positions', [])
            if p.get('_being_closed')
        }

        for frozen in frozen_positions:
            lots = frozen.get('lots', 0)
            entry_prem = frozen.get('entry_premium', 0)
            strike = frozen.get('strike', 0)
            pos_id = frozen.get('_pos_id')
            frozen_at_str = frozen.get('frozen_at', '')

            if lots <= 0 or entry_prem <= 0 or strike <= 0:
                continue

            # Skip positions marked _being_closed (in-flight guard)
            if pos_id and pos_id in being_closed_ids:
                log.debug(
                    f"[{session_id}] Harvest: skipping pos_id={pos_id} "
                    f"(_being_closed in-flight guard)"
                )
                continue

            # §3.2 criterion 3: Position age check
            if frozen_at_str:
                try:
                    frozen_dt = datetime.fromisoformat(frozen_at_str)
                    if frozen_dt.tzinfo is None:
                        frozen_dt = frozen_dt.replace(tzinfo=timezone.utc)
                    age_mins = (now - frozen_dt).total_seconds() / 60
                    if age_mins < harvest_min_age_mins:
                        log.debug(
                            f"[{session_id}] Harvest: {side_key.upper()} @ {strike} "
                            f"too young ({age_mins:.1f}m < {harvest_min_age_mins}m)"
                        )
                        continue
                except (ValueError, TypeError):
                    pass  # Can't parse age, proceed anyway

            # §3.2 criterion 2: Fetch current premium and check profit_pct
            try:
                current = fetch_premium_fn(strike, option_type)
            except Exception as e:
                log.warning(
                    f"[{session_id}] Harvest: error fetching "
                    f"{side_key.upper()} @ {strike}: {e}"
                )
                continue

            if current is None or current <= 0:
                continue

            profit_pct = (entry_prem - current) / entry_prem * 100
            if profit_pct < harvest_profit_pct:
                continue

            # §3.3: Calculate harvest score
            lot_weight = lots / max(total_side_lots, 1)
            harvest_score = profit_pct * lot_weight

            harvestable.append({
                # Fields required by close_position()
                'side': side_key,
                'strike': strike,
                'lots': lots,
                'entry_premium': entry_prem,
                'current_premium': current,
                'type': 'frozen',
                'profit': float(
                    (_D(entry_prem) - _D(current)) * _D(lots) * _LOT
                ),
                '_pos_id': pos_id,
                # Harvest metadata
                '_harvest_score': harvest_score,
                '_profit_pct': profit_pct,
                '_capacity_pressure': capacity_pressure,
                '_asymmetry_boosted': overrides.get('_boosted', False),
                '_boost_level': overrides.get('_boost_level', ''),
            })

    # Sort by harvest score descending (most profitable + largest first)
    harvestable.sort(key=lambda p: p.get('_harvest_score', 0), reverse=True)

    if harvestable:
        log.info(
            f"[{session_id}] Harvest scan: {len(harvestable)} position(s) eligible"
        )
    else:
        log.debug(f"[{session_id}] Harvest scan: no positions eligible")

    return harvestable
