"""
Sealed contract tests for MMMSafety.check_max_loss (#76)

Function: check_max_loss(session) → List[Dict]
  - Returns [] when loss is within threshold
  - Returns [warn event]      when total_pnl <= -max_loss_amount * 0.80
  - Returns [auto_close event] when total_pnl <= -max_loss_amount
  - total_pnl = realized + unrealized + perp.realized + perp.unrealized
  - Guard: max_loss_amount <= 0 → returns [max_loss_config critical event] (M-5 FIX)
  - Default max_loss_amount = 5000.0 when param absent

Confirmed working: mmm17mar26-2 session (HARD stop badge visible, closed all positions)
"""

import pytest
from webui.backend.routes.mmm.mmm_safety import MMMSafety


def _session(realized=0.0, unrealized=0.0, perp_r=0.0, perp_u=0.0, max_loss=1000.0):
    s = {
        'params': {'max_loss_amount': max_loss},
        'realized_pnl': realized,
        'unrealized_pnl': unrealized,
        'perp_hedge': {
            'realized_pnl': perp_r,
            'unrealized_pnl': perp_u,
        },
    }
    return s


@pytest.fixture
def safety():
    return MMMSafety()


# ── Contract 1: No loss → no event ──────────────────────────────────────────

@pytest.mark.sealed
def test_no_loss_returns_empty(safety):
    events = safety.check_max_loss(_session(realized=0, unrealized=0))
    assert events == []


@pytest.mark.sealed
def test_positive_pnl_returns_empty(safety):
    events = safety.check_max_loss(_session(realized=200, unrealized=50))
    assert events == []


# ── Contract 2: Below warning threshold → no event ──────────────────────────

@pytest.mark.sealed
def test_below_warning_threshold_no_event(safety):
    # -799 is above 80% of 1000 threshold → no event
    events = safety.check_max_loss(_session(unrealized=-799.0))
    assert events == []


# ── Contract 3: Warning at 80% of threshold ──────────────────────────────────

@pytest.mark.sealed
def test_warning_at_80pct_threshold(safety):
    # -800 == -max_loss * 0.8 → warn
    events = safety.check_max_loss(_session(unrealized=-800.0))
    assert len(events) == 1
    assert events[0]['action'] == 'warn'
    assert events[0]['level'] == 'alert'
    assert events[0]['type'] == 'max_loss'


@pytest.mark.sealed
def test_warning_between_80_and_100_pct(safety):
    events = safety.check_max_loss(_session(unrealized=-900.0))
    assert len(events) == 1
    assert events[0]['action'] == 'warn'


# ── Contract 4: Auto-close at 100% threshold ────────────────────────────────

@pytest.mark.sealed
def test_auto_close_at_exact_threshold(safety):
    # -1000 == -max_loss → auto_close
    events = safety.check_max_loss(_session(unrealized=-1000.0))
    assert len(events) == 1
    assert events[0]['action'] == 'auto_close'
    assert events[0]['level'] == 'critical'


@pytest.mark.sealed
def test_auto_close_beyond_threshold(safety):
    events = safety.check_max_loss(_session(unrealized=-1500.0))
    assert len(events) == 1
    assert events[0]['action'] == 'auto_close'


# ── Contract 5: total_pnl includes all four components ───────────────────────

@pytest.mark.sealed
def test_total_pnl_includes_realized(safety):
    # realized alone pushes past threshold
    events = safety.check_max_loss(_session(realized=-1001.0))
    assert events[0]['action'] == 'auto_close'


@pytest.mark.sealed
def test_total_pnl_includes_perp_realized(safety):
    # -500 options + -501 perp.realized = -1001 → auto_close
    events = safety.check_max_loss(_session(unrealized=-500.0, perp_r=-501.0))
    assert events[0]['action'] == 'auto_close'


@pytest.mark.sealed
def test_total_pnl_includes_perp_unrealized(safety):
    events = safety.check_max_loss(_session(unrealized=-500.0, perp_u=-501.0))
    assert events[0]['action'] == 'auto_close'


@pytest.mark.sealed
def test_total_pnl_all_four_summed(safety):
    # 250 + 250 + 250 + 251 = 1001 → auto_close
    events = safety.check_max_loss(_session(
        realized=-250.0, unrealized=-250.0, perp_r=-250.0, perp_u=-251.0,
    ))
    assert events[0]['action'] == 'auto_close'


@pytest.mark.sealed
def test_perp_positive_offsets_loss(safety):
    # -1001 options + +200 perp = -801 → warn only, not auto_close
    events = safety.check_max_loss(_session(unrealized=-1001.0, perp_r=200.0))
    assert len(events) == 1
    assert events[0]['action'] == 'warn'


# ── Contract 6: auto_close event details are correct ─────────────────────────

@pytest.mark.sealed
def test_auto_close_details_contain_correct_values(safety):
    events = safety.check_max_loss(_session(realized=-600.0, unrealized=-500.0, max_loss=1000.0))
    e = events[0]
    assert e['details']['total_pnl'] == pytest.approx(-1100.0)
    assert e['details']['max_loss'] == 1000.0
    assert e['details']['realized'] == -600.0
    assert e['details']['unrealized'] == -500.0


@pytest.mark.sealed
def test_auto_close_details_include_perp_pnl(safety):
    events = safety.check_max_loss(_session(unrealized=-1001.0, perp_r=-50.0, perp_u=-20.0))
    e = events[0]
    assert 'perp_pnl' in e['details']
    assert e['details']['perp_pnl'] == pytest.approx(-70.0)


# ── Contract 7: Guard — max_loss_amount <= 0 → CRITICAL config event ─────────

@pytest.mark.sealed
def test_max_loss_zero_emits_config_warning(safety):
    # M-5 FIX: max_loss=0 → critical config event (was silent before)
    events = safety.check_max_loss(_session(unrealized=-999999.0, max_loss=0.0))
    assert len(events) == 1
    assert events[0]['type'] == 'max_loss_config'
    assert events[0]['level'] == 'critical'
    assert events[0]['action'] == 'warn'


@pytest.mark.sealed
def test_max_loss_negative_emits_config_warning(safety):
    events = safety.check_max_loss(_session(unrealized=-999999.0, max_loss=-500.0))
    assert len(events) == 1
    assert events[0]['type'] == 'max_loss_config'
    assert events[0]['level'] == 'critical'


# ── Contract 8: Default max_loss when param absent ───────────────────────────

@pytest.mark.sealed
def test_default_max_loss_5000_when_param_absent(safety):
    session = {
        'params': {},  # no max_loss_amount key
        'realized_pnl': 0,
        'unrealized_pnl': -4999.0,
        'perp_hedge': {'realized_pnl': 0.0, 'unrealized_pnl': 0.0},
    }
    events = safety.check_max_loss(session)
    # -4999 < 80% of 5000 = 4000 → warn
    assert len(events) == 1
    assert events[0]['action'] == 'warn'


@pytest.mark.sealed
def test_default_max_loss_fires_at_5000(safety):
    session = {
        'params': {},
        'realized_pnl': 0,
        'unrealized_pnl': -5001.0,
        'perp_hedge': {'realized_pnl': 0.0, 'unrealized_pnl': 0.0},
    }
    events = safety.check_max_loss(session)
    assert events[0]['action'] == 'auto_close'


# ── Contract 9: Exactly one event returned (never two) ───────────────────────

@pytest.mark.sealed
def test_only_one_event_returned_on_breach(safety):
    events = safety.check_max_loss(_session(unrealized=-2000.0))
    assert len(events) == 1


@pytest.mark.sealed
def test_only_one_event_returned_on_warning(safety):
    events = safety.check_max_loss(_session(unrealized=-850.0))
    assert len(events) == 1
