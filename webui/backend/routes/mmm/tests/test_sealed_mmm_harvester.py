"""
Sealed contract tests for mmm_harvester (#88)

Functions sealed:
  - get_effective_harvest_params(session, side) → dict
  - scan_harvestable_positions(session, fetch_premium_fn) → list

File: webui/backend/routes/mmm/mmm_harvester.py

Audit outcome (2026-03-20):
  - No bugs found in either function.
  - AUDIT FIX BUG2 already applied: active_lots (not total_lots) used for
    asymmetry ratio calculation in get_effective_harvest_params.
  - AUDIT FIX BUG5 already applied: active_lots (not total_lots) used for
    capacity pressure in scan_harvestable_positions.
  - Observation (out of scope): harvest_max_per_beat override returned by
    get_effective_harvest_params is NOT applied inside scan_harvestable_positions.
    Caller (mmm_monitor) is responsible for slicing the returned list.

Contracts:

  [get_effective_harvest_params — 10 contracts]
  G1.  rebalance_enabled=False → {}
  G2.  Both sides 0 lots → {}
  G3.  other_side=0, my_side under pressure (> pressure_threshold) → extreme boost
  G4.  other_side=0, my_side NOT under pressure → {}
  G5.  Extreme asymmetry + high pressure → extreme boost (_boost_level='extreme')
  G6.  Moderate asymmetry + moderate pressure → moderate boost (_boost_level='moderate')
  G7.  High asymmetry but low pressure → {}
  G8.  Low asymmetry, high pressure → {}
  G9.  Uses active_lots (not total_lots): high total_lots but low active_lots
       does NOT trigger M3 boost
  G10. base_profit_pct * 0.6 is floored at 20.0

  [scan_harvestable_positions — 13 contracts]
  H1.  harvest_enabled=False → []
  H2.  Side pressure below harvest_pressure_threshold → side skipped → []
  H3.  No frozen positions on eligible side → []
  H4.  Frozen lots <= 0 → skipped
  H5.  Frozen entry_premium <= 0 → skipped
  H6.  Frozen strike <= 0 → skipped
  H7.  pos_id in being_closed_ids → skipped
  H8.  Position frozen too recently (age < harvest_min_age_mins) → skipped
  H9.  fetch_premium_fn returns None → skipped
  H10. fetch_premium_fn raises → skipped, no crash
  H11. profit_pct below harvest_profit_pct → skipped
  H12. Eligible position returned with all close_position()-compatible fields
  H13. Sorted by harvest_score descending (highest score first)
"""

import pytest
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_harvester import (
    get_effective_harvest_params,
    scan_harvestable_positions,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _session(ce_active=0, pe_active=0, ce_total=None, pe_total=None,
             params=None, ce_frozen=None, pe_frozen=None,
             ce_positions=None, pe_positions=None):
    p = {
        'harvest_enabled': True,
        'rebalance_enabled': True,
        'max_lots_per_side': 100,
        'harvest_profit_pct': 40.0,
        'harvest_pressure_threshold': 0.6,
        'harvest_min_age_mins': 30,
        'rebalance_asymmetry_threshold': 5.0,
        'rebalance_pressure_threshold': 0.8,
    }
    if params:
        p.update(params)
    return {
        'session_id': 'test-harvest',
        'params': p,
        'ce': {
            'active_lots': ce_active,
            'total_lots': ce_total if ce_total is not None else ce_active,
            'frozen_positions': ce_frozen or [],
            'positions': ce_positions or [],
        },
        'pe': {
            'active_lots': pe_active,
            'total_lots': pe_total if pe_total is not None else pe_active,
            'frozen_positions': pe_frozen or [],
            'positions': pe_positions or [],
        },
    }


def _frozen(strike=90000, lots=5, entry_premium=100.0, pos_id='pos-001',
            frozen_at=None, **kwargs):
    entry = {
        'strike': strike,
        'lots': lots,
        'entry_premium': entry_premium,
        '_pos_id': pos_id,
    }
    if frozen_at is not None:
        entry['frozen_at'] = frozen_at.isoformat()
    entry.update(kwargs)
    return entry


def _old():
    """Timestamp old enough to pass age check (1 hour ago)."""
    return datetime.now(timezone.utc) - timedelta(hours=1)


def _fresh():
    """Timestamp too recent to pass age check (5 minutes ago)."""
    return datetime.now(timezone.utc) - timedelta(minutes=5)


# ─── G1–G10: get_effective_harvest_params ─────────────────────────────────────

def test_g1_rebalance_disabled_returns_empty():
    session = _session(ce_active=90, pe_active=10,
                       params={'rebalance_enabled': False})
    assert get_effective_harvest_params(session, 'ce') == {}


def test_g2_both_sides_zero_lots_returns_empty():
    session = _session(ce_active=0, pe_active=0)
    assert get_effective_harvest_params(session, 'ce') == {}


def test_g3_other_side_zero_my_side_under_pressure_extreme_boost():
    # PE=0, CE=90 of 100 → pressure=0.9 > 0.8 → extreme boost
    session = _session(ce_active=90, pe_active=0)
    result = get_effective_harvest_params(session, 'ce')
    assert result.get('_boosted') is True
    assert result.get('_boost_level') == 'extreme'
    assert 'harvest_profit_pct' in result


def test_g4_other_side_zero_my_side_no_pressure_returns_empty():
    # PE=0, CE=50 of 100 → pressure=0.5 < 0.8 → no boost
    session = _session(ce_active=50, pe_active=0)
    assert get_effective_harvest_params(session, 'ce') == {}


def test_g5_extreme_asymmetry_high_pressure_extreme_boost():
    # CE=90, PE=5 → ratio=18 > 5.0; pressure=0.9 > 0.8 → extreme
    session = _session(ce_active=90, pe_active=5)
    result = get_effective_harvest_params(session, 'ce')
    assert result.get('_boost_level') == 'extreme'
    assert result.get('_boosted') is True
    assert result.get('harvest_max_per_beat') == 5
    assert result.get('harvest_pressure_threshold') == 0.3


def test_g6_moderate_asymmetry_moderate_pressure_moderate_boost():
    # CE=65, PE=20 → ratio=3.25 > 3.0 (5.0*0.6) but <5.0; pressure=0.65 > 0.6
    session = _session(ce_active=65, pe_active=20)
    result = get_effective_harvest_params(session, 'ce')
    assert result.get('_boost_level') == 'moderate'
    assert result.get('_boosted') is True
    assert result.get('harvest_max_per_beat') == 4
    assert result.get('harvest_pressure_threshold') == 0.5


def test_g7_high_asymmetry_low_pressure_returns_empty():
    # CE=30, PE=5 → ratio=6 > 5; but pressure=0.3 < 0.8 → no boost
    session = _session(ce_active=30, pe_active=5)
    assert get_effective_harvest_params(session, 'ce') == {}


def test_g8_low_asymmetry_high_pressure_returns_empty():
    # CE=85, PE=80 → ratio=1.06 < 5; no asymmetry → no boost
    session = _session(ce_active=85, pe_active=80)
    assert get_effective_harvest_params(session, 'ce') == {}


def test_g9_uses_active_lots_not_total_lots():
    # CE: active=10, total=90. PE: active=5, total=5.
    # Using active_lots: ratio = 10/5 = 2.0 < 5.0 → no boost (correct)
    # If using total_lots: ratio = 90/5 = 18 > 5.0 AND pressure=90/100=0.9 → would boost (wrong)
    session = _session(ce_active=10, pe_active=5, ce_total=90, pe_total=5)
    result = get_effective_harvest_params(session, 'ce')
    assert result == {}


def test_g10_base_profit_pct_floored_at_20():
    # harvest_profit_pct=30 → 30*0.6=18 → max(18, 20.0) = 20.0
    session = _session(ce_active=90, pe_active=0,
                       params={'harvest_profit_pct': 30.0,
                               'rebalance_pressure_threshold': 0.8,
                               'max_lots_per_side': 100})
    result = get_effective_harvest_params(session, 'ce')
    # pressure=90/100=0.9 > 0.8 → extreme boost branch
    assert result.get('harvest_profit_pct') == 20.0


# ─── H1–H13: scan_harvestable_positions ──────────────────────────────────────

def test_h1_harvest_disabled_returns_empty():
    frozen = [_frozen(frozen_at=_old())]
    session = _session(ce_active=90, ce_frozen=frozen,
                       params={'harvest_enabled': False})
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h2_pressure_below_threshold_side_skipped():
    # active_lots=10, max=100 → pressure=0.10 < 0.60 → skip
    frozen = [_frozen(frozen_at=_old())]
    session = _session(ce_active=10, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h3_no_frozen_positions_returns_empty():
    # Pressure OK but empty frozen list
    session = _session(ce_active=70, ce_frozen=[])
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h4_frozen_lots_zero_skipped():
    frozen = [_frozen(lots=0, frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h5_frozen_entry_premium_zero_skipped():
    frozen = [_frozen(entry_premium=0.0, frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h6_frozen_strike_zero_skipped():
    frozen = [_frozen(strike=0, frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h7_being_closed_position_skipped():
    pos_entry = {'id': 'p1', '_being_closed': True, 'lots': 5}
    frozen = [_frozen(pos_id='p1', frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen, ce_positions=[pos_entry])
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h8_position_too_young_skipped():
    # frozen 5 minutes ago, min_age=30 → skip
    frozen = [_frozen(frozen_at=_fresh())]
    session = _session(ce_active=70, ce_frozen=frozen,
                       params={'harvest_min_age_mins': 30})
    result = scan_harvestable_positions(session, lambda s, t: 10.0)
    assert result == []


def test_h9_fetch_returns_none_skipped():
    frozen = [_frozen(frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: None)
    assert result == []


def test_h10_fetch_raises_skipped_no_crash():
    def bad_fetch(strike, option_type):
        raise RuntimeError("price unavailable")

    frozen = [_frozen(frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, bad_fetch)
    assert result == []


def test_h11_profit_pct_below_threshold_skipped():
    # entry=100, current=70 → profit_pct=30% < 40% → skip
    frozen = [_frozen(entry_premium=100.0, frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen,
                       params={'harvest_profit_pct': 40.0})
    result = scan_harvestable_positions(session, lambda s, t: 70.0)
    assert result == []


def test_h12_eligible_position_correct_fields():
    # entry=100, current=30 → profit_pct=70% >= 40% → eligible
    frozen = [_frozen(strike=90000, lots=5, entry_premium=100.0, pos_id='p1',
                      frozen_at=_old())]
    session = _session(ce_active=70, ce_frozen=frozen)
    result = scan_harvestable_positions(session, lambda s, t: 30.0)
    assert len(result) == 1
    r = result[0]
    assert r['side'] == 'ce'
    assert r['strike'] == 90000
    assert r['lots'] == 5
    assert r['entry_premium'] == 100.0
    assert r['current_premium'] == 30.0
    assert r['type'] == 'frozen'
    assert r['_pos_id'] == 'p1'
    assert '_harvest_score' in r
    assert '_profit_pct' in r
    assert r['profit'] > 0


def test_h13_sorted_by_harvest_score_descending():
    # pos1 (90000): entry=100, current=10 → profit_pct=90, lots=40
    #   score = 90 * (40/70) ≈ 51.4
    # pos2 (85000): entry=100, current=50 → profit_pct=50, lots=30
    #   score = 50 * (30/70) ≈ 21.4
    # Expected order: 90000 first
    frozen = [
        _frozen(strike=90000, lots=40, entry_premium=100.0, pos_id='p1',
                frozen_at=_old()),
        _frozen(strike=85000, lots=30, entry_premium=100.0, pos_id='p2',
                frozen_at=_old()),
    ]
    prices = {90000: 10.0, 85000: 50.0}
    session = _session(ce_active=70, ce_frozen=frozen)

    def fetch(strike, option_type):
        return prices[strike]

    result = scan_harvestable_positions(session, fetch)
    assert len(result) == 2
    assert result[0]['strike'] == 90000  # higher harvest_score first
    assert result[1]['strike'] == 85000
