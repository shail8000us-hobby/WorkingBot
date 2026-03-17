"""
Sealed contract tests for MMMSafety.check_max_loss_sizing (#77)

Function: check_max_loss_sizing(session) → List[Dict]
  Tied to param: initial_lots

  IMP-6: Warn ONCE per session when max_loss_amount is below the
  suggested minimum for the current position size.

  suggested_min = initial_lots × (ce_entry + pe_entry) × LOT_SIZE_BTC × 0.50

  Contracts:
  - Returns [] if already warned this session (_max_loss_sizing_warned=True)
  - Returns [] if initial_lots <= 0
  - Returns [] if ce_entry or pe_entry <= 0 (premiums unknown at entry)
  - Returns [] if max_loss >= suggested_min (adequately covered)
  - Returns [warn] if max_loss < suggested_min → sets _max_loss_sizing_warned=True
  - warn event: action='warn', level='warning', never blocks trading
  - Idempotent: after firing, never fires again in same session
  - LOT_SIZE_BTC = 0.001

Confirmed working: mmm17mar26-2 (initial_lots param verified at session start)
"""

import pytest
from webui.backend.routes.mmm.mmm_safety import MMMSafety
from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC


def _session(
    initial_lots=10,
    max_loss=5000.0,
    ce_entry=5000.0,
    pe_entry=4000.0,
    already_warned=False,
):
    s = {
        'params': {
            'initial_lots': initial_lots,
            'max_loss_amount': max_loss,
        },
        'ce': {'original_premium': ce_entry},
        'pe': {'original_premium': pe_entry},
    }
    if already_warned:
        s['_max_loss_sizing_warned'] = True
    return s


@pytest.fixture
def safety():
    return MMMSafety()


# ── Contract 1: Once-per-session guard ───────────────────────────────────────

@pytest.mark.sealed
def test_returns_empty_if_already_warned(safety):
    session = _session(max_loss=1.0, already_warned=True)  # tiny max_loss but already warned
    events = safety.check_max_loss_sizing(session)
    assert events == []


@pytest.mark.sealed
def test_does_not_fire_twice(safety):
    session = _session(max_loss=1.0)
    safety.check_max_loss_sizing(session)   # first call — fires and sets flag
    events2 = safety.check_max_loss_sizing(session)  # second call — must be empty
    assert events2 == []


# ── Contract 2: Guard — initial_lots <= 0 ────────────────────────────────────

@pytest.mark.sealed
def test_returns_empty_if_initial_lots_zero(safety):
    events = safety.check_max_loss_sizing(_session(initial_lots=0))
    assert events == []


@pytest.mark.sealed
def test_returns_empty_if_initial_lots_negative(safety):
    events = safety.check_max_loss_sizing(_session(initial_lots=-5))
    assert events == []


# ── Contract 3: Guard — premiums unknown at entry ────────────────────────────

@pytest.mark.sealed
def test_returns_empty_if_ce_entry_zero(safety):
    events = safety.check_max_loss_sizing(_session(ce_entry=0.0))
    assert events == []


@pytest.mark.sealed
def test_returns_empty_if_pe_entry_zero(safety):
    events = safety.check_max_loss_sizing(_session(pe_entry=0.0))
    assert events == []


# ── Contract 4: No warn when max_loss is adequate ────────────────────────────

@pytest.mark.sealed
def test_no_warn_when_max_loss_exceeds_suggested_min(safety):
    # suggested_min = 10 × (5000+4000) × 0.001 × 0.5 = 45.0
    # max_loss=100 > 45 → no warn
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=100.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert events == []


@pytest.mark.sealed
def test_no_warn_when_max_loss_equals_suggested_min(safety):
    # suggested_min = 10 × (5000+4000) × 0.001 × 0.5 = 45.0
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=45.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert events == []


# ── Contract 5: Warn fires when max_loss < suggested_min ─────────────────────

@pytest.mark.sealed
def test_warn_fires_when_max_loss_below_suggested(safety):
    # suggested_min = 10 × (5000+4000) × 0.001 × 0.5 = 45.0
    # max_loss=10 < 45 → warn
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=10.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert len(events) == 1


@pytest.mark.sealed
def test_warn_event_shape(safety):
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=10.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    e = events[0]
    assert e['type'] == 'max_loss_sizing'
    assert e['level'] == 'warning'
    assert e['action'] == 'warn'


@pytest.mark.sealed
def test_warn_sets_session_flag(safety):
    session = _session(initial_lots=10, max_loss=10.0)
    safety.check_max_loss_sizing(session)
    assert session.get('_max_loss_sizing_warned') is True


# ── Contract 6: suggested_min formula is correct ─────────────────────────────

@pytest.mark.sealed
def test_suggested_min_formula(safety):
    # 10 lots × (5000+4000) × 0.001 × 0.5 = 45.0
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=44.99, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert len(events) == 1
    assert events[0]['details']['suggested_min'] == pytest.approx(45.0, rel=1e-3)


@pytest.mark.sealed
def test_suggested_min_scales_with_lots(safety):
    # 20 lots → suggested_min = 90.0
    events = safety.check_max_loss_sizing(_session(
        initial_lots=20, max_loss=1.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert events[0]['details']['suggested_min'] == pytest.approx(90.0, rel=1e-3)


@pytest.mark.sealed
def test_details_contain_correct_values(safety):
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=10.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    d = events[0]['details']
    assert d['max_loss'] == 10.0
    assert d['initial_lots'] == 10
    expected_per_lot = (5000.0 + 4000.0) * LOT_SIZE_BTC
    assert d['premium_per_lot'] == pytest.approx(expected_per_lot, rel=1e-4)


# ── Contract 7: action is always warn — never blocks ─────────────────────────

@pytest.mark.sealed
def test_action_is_never_block_or_auto_close(safety):
    events = safety.check_max_loss_sizing(_session(
        initial_lots=10, max_loss=1.0, ce_entry=5000.0, pe_entry=4000.0,
    ))
    assert events[0]['action'] == 'warn'
    assert events[0]['action'] not in ('auto_close', 'block', 'pause')
