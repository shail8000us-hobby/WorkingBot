"""
Sealed contract tests for mmm_wind_down (#80)

Functions sealed:
  - is_wind_down_active(session) → bool
  - compute_wind_down_action(session, aggressor_side, ce_now, pe_now) → dict
  - get_lifo_close_fills(side_state, lots_to_close) → list
  - apply_lifo_removals(side_state, close_records) → float
  - get_wind_down_close_threshold(session) → float

LIVE confirmation: mmm20mar26-1 (Mar 19, 2026)
  - _trend_wind_down_triggered=True fired via Tier 4 downtrend (-4.1%, anchor 73889 → 70860)
  - wind_down_enabled=False in params — regime path correctly bypassed master switch
  - 7 wind-down buyback rounds executed; _wind_down_mode=True confirmed in session state

31 contracts total.
"""

import pytest
from copy import deepcopy
from datetime import datetime, timezone

from webui.backend.routes.mmm.mmm_wind_down import (
    is_wind_down_active,
    compute_wind_down_action,
    get_lifo_close_fills,
    apply_lifo_removals,
    get_wind_down_close_threshold,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _base_session(
    wind_down_enabled=True,
    wind_down_hours=2.0,
    wind_down_on_atm=False,
    atm_triggered=False,
    expiry='20122099',   # far future — never inside time window
    close_threshold=20.0,
    normal_threshold=5.0,
    ce_lots=5,
    pe_lots=5,
):
    now = _now_iso()
    return {
        'session_id': 'test-wd-sealed',
        'params': {
            'expiry': expiry,
            'wind_down_enabled': wind_down_enabled,
            'wind_down_hours_before_expiry': wind_down_hours,
            'wind_down_on_atm': wind_down_on_atm,
            'wind_down_buyback_pct': 0.25,
            'wind_down_min_lots_to_keep': 0,
            'wind_down_floor_action': 'skip',
            'wind_down_close_threshold': close_threshold,
            'close_at_threshold': normal_threshold,
        },
        '_atm_wind_down_triggered': atm_triggered,
        'ce': {
            'side': 'ce',
            'active_lots': ce_lots,
            'total_lots': ce_lots,
            'original_lots': ce_lots,
            'adjustment_fills': [],
            'frozen_positions': [],
            'positions': [{
                'id': 'ce_orig', 'strike': 74000, 'lots': ce_lots,
                'entry_premium': 150.0, 'premium': 150.0,
                'type': 'original', 'status': 'active', 'created_at': now,
            }],
        },
        'pe': {
            'side': 'pe',
            'active_lots': pe_lots,
            'total_lots': pe_lots,
            'original_lots': pe_lots,
            'adjustment_fills': [],
            'frozen_positions': [],
            'positions': [{
                'id': 'pe_orig', 'strike': 68000, 'lots': pe_lots,
                'entry_premium': 130.0, 'premium': 130.0,
                'type': 'original', 'status': 'active', 'created_at': now,
            }],
        },
    }


@pytest.fixture
def live_mmm20mar26_session():
    """
    Real session state from mmm20mar26-1 (Mar 19, 2026 ~10 AM IST).

    BTC dropped -4.1% from anchor 73889 → 70860 over 30+ hours.
    Trend engine classified Tier 4 DOWN and set _trend_wind_down_triggered=True.
    wind_down_enabled=False in params — proves regime flag bypasses master switch.
    _vol_wind_down_triggered=False — confirms it was trend-only, not vol.
    7 buyback rounds in _wind_down_history; _wind_down_mode=True in session.
    """
    return {
        'session_id': 'mmm20mar26-1',
        '_trend_wind_down_triggered': True,
        '_vol_wind_down_triggered': False,
        '_atm_wind_down_triggered': False,
        '_trend_tier': 4,
        '_trend_direction': 'down',
        '_trend_move_pct': -4.099,
        '_trend_anchor_spot': 73889.33,
        '_wind_down_mode': True,
        'params': {
            'expiry': '20032026',
            'wind_down_enabled': False,           # master switch OFF — regime must bypass
            'wind_down_hours_before_expiry': 2.0,
            'wind_down_on_atm': False,
            'wind_down_buyback_pct': 0.25,
            'wind_down_min_lots_to_keep': 0,
            'wind_down_floor_action': 'skip',
            'wind_down_close_threshold': 20.0,
            'close_at_threshold': 5.0,
        },
    }


# ─── is_wind_down_active ──────────────────────────────────────────────────────

@pytest.mark.sealed
def test_trend_flag_bypasses_master_switch_live(live_mmm20mar26_session):
    """LIVE mmm20mar26-1: _trend_wind_down_triggered=True overrides wind_down_enabled=False."""
    assert is_wind_down_active(live_mmm20mar26_session) is True


@pytest.mark.sealed
def test_vol_flag_bypasses_master_switch():
    """_vol_wind_down_triggered=True → active even with master switch off."""
    s = _base_session(wind_down_enabled=False)
    s['_vol_wind_down_triggered'] = True
    assert is_wind_down_active(s) is True


@pytest.mark.sealed
def test_trend_flag_bypasses_master_switch():
    """_trend_wind_down_triggered=True → active even with master switch off."""
    s = _base_session(wind_down_enabled=False)
    s['_trend_wind_down_triggered'] = True
    assert is_wind_down_active(s) is True


@pytest.mark.sealed
def test_no_regime_flags_master_switch_off_returns_false():
    """No regime flags + master switch off → False (normal idle)."""
    s = _base_session(wind_down_enabled=False)
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_vol_flag_false_trend_flag_false_uses_master_switch(live_mmm20mar26_session):
    """When both regime flags cleared, master switch governs. LIVE session with flags removed → False."""
    s = deepcopy(live_mmm20mar26_session)
    s['_trend_wind_down_triggered'] = False
    s['_vol_wind_down_triggered'] = False
    # params.wind_down_enabled is False in live session → must return False
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_master_switch_off_blocks_time_gate():
    """wind_down_enabled=False with past expiry → still False (master switch wins over time gate)."""
    s = _base_session(wind_down_enabled=False, wind_down_hours=2.0, expiry='20032020')
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_hours_zero_with_master_switch_always_active():
    """wind_down_enabled=True, hours=0 → permanently active (manual WebUI toggle)."""
    s = _base_session(wind_down_enabled=True, wind_down_hours=0.0)
    assert is_wind_down_active(s) is True


@pytest.mark.sealed
def test_time_gate_past_expiry_active():
    """Expiry already passed (2020) → hours_remaining < 0 ≤ 2h threshold → active."""
    s = _base_session(wind_down_enabled=True, wind_down_hours=2.0, expiry='20032020')
    assert is_wind_down_active(s) is True


@pytest.mark.sealed
def test_time_gate_far_future_expiry_inactive():
    """Expiry Dec 2099 → thousands of hours remaining → not within 2h threshold."""
    s = _base_session(wind_down_enabled=True, wind_down_hours=2.0, expiry='20122099')
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_atm_flag_plus_on_atm_param_activates():
    """wind_down_on_atm=True + _atm_wind_down_triggered=True → active."""
    s = _base_session(
        wind_down_enabled=True,
        wind_down_on_atm=True,
        atm_triggered=True,
        wind_down_hours=2.0,
        expiry='20122099',   # far from time gate
    )
    assert is_wind_down_active(s) is True


@pytest.mark.sealed
def test_atm_flag_set_but_on_atm_param_false_stays_inactive():
    """_atm_wind_down_triggered=True but wind_down_on_atm=False → not active."""
    s = _base_session(
        wind_down_enabled=True,
        wind_down_on_atm=False,
        atm_triggered=True,
        wind_down_hours=2.0,
        expiry='20122099',
    )
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_atm_flag_requires_master_switch():
    """ATM trigger blocked when master switch off (unlike regime flags)."""
    s = _base_session(wind_down_enabled=False, wind_down_on_atm=True, atm_triggered=True)
    assert is_wind_down_active(s) is False


@pytest.mark.sealed
def test_missing_expiry_string_returns_false():
    """Missing expiry with time gate enabled → False (safe fallback, no crash)."""
    s = _base_session(wind_down_enabled=True, wind_down_hours=2.0)
    s['params']['expiry'] = ''
    assert is_wind_down_active(s) is False


# ─── compute_wind_down_action ─────────────────────────────────────────────────

@pytest.mark.sealed
def test_buyback_action_returned():
    """Normal trigger → action='buyback', lots_to_close > 0."""
    s = _base_session()
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['action'] == 'buyback'
    assert result['lots_to_close'] > 0
    assert result['at_floor'] is False


@pytest.mark.sealed
def test_buyback_pct_50_of_8_equals_4():
    """50% of 8 available lots = math.floor(8*0.5) = 4."""
    s = _base_session(ce_lots=8)
    s['params']['wind_down_buyback_pct'] = 0.50
    s['ce']['active_lots'] = 8
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['lots_to_close'] == 4


@pytest.mark.sealed
def test_minimum_one_lot_bought_back():
    """Even with low pct and few lots, always at least 1 lot (max(1, floor(...)))."""
    s = _base_session(ce_lots=1)
    s['params']['wind_down_buyback_pct'] = 0.10   # 10% of 1 = 0.1 → floor=0 → max(1,0)=1
    s['ce']['active_lots'] = 1
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['lots_to_close'] == 1


@pytest.mark.sealed
def test_floor_action_skip_when_at_min_keep():
    """active_lots == min_lots_to_keep → at_floor=True, action='skip', lots=0."""
    s = _base_session(ce_lots=3)
    s['params']['wind_down_min_lots_to_keep'] = 3
    s['params']['wind_down_floor_action'] = 'skip'
    s['ce']['active_lots'] = 3
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['action'] == 'skip'
    assert result['at_floor'] is True
    assert result['lots_to_close'] == 0


@pytest.mark.sealed
def test_floor_action_normal_passes_through():
    """floor_action='normal' → action='normal' at floor."""
    s = _base_session(ce_lots=2)
    s['params']['wind_down_min_lots_to_keep'] = 2
    s['params']['wind_down_floor_action'] = 'normal'
    s['ce']['active_lots'] = 2
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['action'] == 'normal'


@pytest.mark.sealed
def test_lots_to_close_never_exceeds_available():
    """100% pct with 2 available lots → close exactly 2, never more."""
    s = _base_session(ce_lots=2)
    s['params']['wind_down_buyback_pct'] = 1.0
    s['ce']['active_lots'] = 2
    result = compute_wind_down_action(s, 'ce', 150.0, 130.0)
    assert result['lots_to_close'] <= 2


@pytest.mark.sealed
def test_pe_side_also_works():
    """compute_wind_down_action works on PE side (not CE-only)."""
    s = _base_session(pe_lots=6)
    s['pe']['active_lots'] = 6
    result = compute_wind_down_action(s, 'pe', 150.0, 130.0)
    assert result['action'] == 'buyback'
    assert result['side'] == 'pe'


# ─── get_lifo_close_fills ─────────────────────────────────────────────────────

def _side_with_adj_and_orig(lots_adj=3, lots_orig=2):
    now = _now_iso()
    return {
        'side': 'ce',
        'active_lots': lots_adj + lots_orig,
        'total_lots': lots_adj + lots_orig,
        'positions': [
            {
                'id': 'ce_orig', 'strike': 74000, 'lots': lots_orig,
                'entry_premium': 150.0, 'type': 'original',
                'status': 'active', 'created_at': now,
            },
            {
                'id': 'ce_adj_001', 'strike': 75000, 'lots': lots_adj,
                'entry_premium': 170.0, 'type': 'adjustment',
                'status': 'active', 'created_at': now,
            },
        ],
    }


@pytest.mark.sealed
def test_lifo_adjustment_before_original():
    """LIFO: adjustment record comes before original in close list."""
    side = _side_with_adj_and_orig(lots_adj=3, lots_orig=2)
    records = get_lifo_close_fills(side, lots_to_close=3)
    sources = [r['source'] for r in records]
    assert 'adjustment' in sources
    if 'original' in sources:
        assert sources.index('adjustment') < sources.index('original')


@pytest.mark.sealed
def test_lifo_total_lots_matches_requested():
    """Sum of lots in close records equals lots_to_close."""
    side = _side_with_adj_and_orig(lots_adj=3, lots_orig=2)
    records = get_lifo_close_fills(side, lots_to_close=2)
    assert sum(r['lots'] for r in records) == 2


@pytest.mark.sealed
def test_lifo_spans_multiple_positions():
    """Closing 5 lots (adj=3, orig=2) spans both positions."""
    side = _side_with_adj_and_orig(lots_adj=3, lots_orig=2)
    records = get_lifo_close_fills(side, lots_to_close=5)
    assert sum(r['lots'] for r in records) == 5
    sources = {r['source'] for r in records}
    assert 'adjustment' in sources
    assert 'original' in sources


@pytest.mark.sealed
def test_lifo_pos_id_present_in_every_record():
    """Every record must carry _pos_id for ID-based atomic removal."""
    side = _side_with_adj_and_orig(lots_adj=3, lots_orig=0)
    records = get_lifo_close_fills(side, lots_to_close=2)
    for rec in records:
        assert '_pos_id' in rec
        assert rec['_pos_id'] is not None


# ─── apply_lifo_removals ──────────────────────────────────────────────────────

def _simple_side(lots=5, premium=150.0):
    now = _now_iso()
    return {
        'side': 'ce',
        'active_lots': lots,
        'total_lots': lots,
        'original_lots': lots,
        'adjustment_fills': [],
        'frozen_positions': [],
        'positions': [{
            'id': 'ce_orig', 'strike': 74000, 'lots': lots,
            'entry_premium': premium, 'premium': premium,
            'type': 'original', 'status': 'active', 'created_at': now,
        }],
    }


@pytest.mark.sealed
def test_apply_reduces_lots():
    """Close 2 of 5 lots → position has 3 lots remaining."""
    side = _simple_side(lots=5)
    records = [{'lots': 2, 'premium': 150.0, 'strike': 74000, '_pos_id': 'ce_orig'}]
    apply_lifo_removals(side, records)
    assert side['positions'][0]['lots'] == 3


@pytest.mark.sealed
def test_apply_full_close_marks_status_closed():
    """Close all lots → position status='closed', closed_at set."""
    side = _simple_side(lots=3)
    records = [{'lots': 3, 'premium': 150.0, 'strike': 74000, '_pos_id': 'ce_orig'}]
    apply_lifo_removals(side, records)
    pos = side['positions'][0]
    assert pos['status'] == 'closed'
    assert pos['closed_at'] is not None


@pytest.mark.sealed
def test_apply_returns_weighted_average_premium():
    """Weighted average premium of closed lots returned correctly."""
    side = _simple_side(lots=5, premium=150.0)
    records = [{'lots': 5, 'premium': 150.0, 'strike': 74000, '_pos_id': 'ce_orig'}]
    avg = apply_lifo_removals(side, records)
    assert avg == pytest.approx(150.0, abs=0.01)


@pytest.mark.sealed
def test_apply_empty_records_is_noop():
    """Empty close_records → no mutation, returns 0.0."""
    side = _simple_side(lots=5)
    original_lots = side['positions'][0]['lots']
    avg = apply_lifo_removals(side, [])
    assert avg == 0.0
    assert side['positions'][0]['lots'] == original_lots


@pytest.mark.sealed
def test_apply_missing_pos_id_no_crash():
    """Record with _pos_id=None → silently skipped, no crash, lots unchanged."""
    side = _simple_side(lots=5)
    records = [{'lots': 2, 'premium': 150.0, 'strike': 74000, '_pos_id': None}]
    apply_lifo_removals(side, records)
    assert side['positions'][0]['lots'] == 5


# ─── get_wind_down_close_threshold ───────────────────────────────────────────

@pytest.mark.sealed
def test_close_threshold_elevated_when_active(live_mmm20mar26_session):
    """LIVE mmm20mar26-1: wind-down active → returns wind_down_close_threshold (20.0)."""
    threshold = get_wind_down_close_threshold(live_mmm20mar26_session)
    assert threshold == 20.0


@pytest.mark.sealed
def test_close_threshold_normal_when_inactive():
    """Wind-down not active → returns close_at_threshold (5.0)."""
    s = _base_session(wind_down_enabled=True, wind_down_hours=2.0, expiry='20122099')
    threshold = get_wind_down_close_threshold(s)
    assert threshold == 5.0


@pytest.mark.sealed
def test_close_threshold_normal_when_disabled():
    """Master switch off → returns normal close_at_threshold."""
    s = _base_session(wind_down_enabled=False)
    threshold = get_wind_down_close_threshold(s)
    assert threshold == s['params']['close_at_threshold']
