"""
Sealed contract tests for mmm_atm_shield (#81)

Functions sealed (Type 1 — logic contracts):
  - _compute_time_mult(minutes_to_expiry) → float
  - _compute_effective_proximity(params, time_mult) → float
  - _compute_effective_target_otm(params, time_mult, shield_count) → float
  - check_atm_proximity(session, spot, params, time_mult) → (Optional[str], float)
  - _check_shield_gates(session, side, params, margin_tier, minutes_to_expiry) → (bool, str)

Infrastructure tests (Type 2 — execute_atm_shield calling chain; async, no @sealed):
  - infra-1: disabled → exits before fetching spot (no unnecessary I/O)
  - infra-2: spot=0 → never fires, spot WAS fetched (not an early exit)
  - infra-3: both sides in proximity → defers to close_at_ATM (returns False)
  - infra-4: cooldown blocks re-fire within 10 min window
  - infra-5: exhaustion (count >= max) blocks re-fire permanently for that side

34 contracts total.
"""

import asyncio
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from webui.backend.routes.mmm.mmm_atm_shield import (
    _compute_time_mult,
    _compute_effective_proximity,
    _compute_effective_target_otm,
    check_atm_proximity,
    _check_shield_gates,
    execute_atm_shield,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _base_params(**overrides):
    p = {
        'atm_shield_enabled': True,
        'atm_shield_proximity_pct': 0.5,
        'atm_shield_target_otm_pct': 1.0,
        'atm_shield_cooldown_mins': 10,
        'atm_shield_max_per_session': 3,
        'auto_close_mins': 5,
        'adjustment_interval': 300,
        'max_lots_per_side': 100,
        'shift_threshold': 50.0,
        'stop_adjustment_mins': 15,
        'atm_shield_partial_pct': 1.0,
        'atm_shield_defer_resell_beats': 0,
        'atm_shield_loss_split_aggressor': 0.3,
    }
    p.update(overrides)
    return p


def _base_session(
    ce_strike=90000.0,
    pe_strike=80000.0,
    ce_lots=5,
    pe_lots=5,
    strategy_status='RUNNING',
    **param_overrides,
):
    return {
        'session_id': 'test-shield-sealed',
        'strategy_status': strategy_status,
        'params': _base_params(**param_overrides),
        'ce': {
            'active_lots': ce_lots,
            'active_strike': ce_strike,
            'total_lots': ce_lots,
            'positions': [
                {'id': 'p1', 'status': 'active', 'lots': ce_lots,
                 'strike': ce_strike, 'entry_premium': 100.0},
            ],
        },
        'pe': {
            'active_lots': pe_lots,
            'active_strike': pe_strike,
            'total_lots': pe_lots,
            'positions': [
                {'id': 'p2', 'status': 'active', 'lots': pe_lots,
                 'strike': pe_strike, 'entry_premium': 100.0},
            ],
        },
    }


def _make_monitor(session=None, spot=85000.0, minutes_to_expiry=360.0,
                  margin_tier='GREEN'):
    m = MagicMock()
    m.session = session if session is not None else _base_session()
    m._fetch_spot_price = AsyncMock(return_value=spot)
    m._get_minutes_to_expiry = MagicMock(return_value=minutes_to_expiry)
    mg = MagicMock()
    mg.last_tier = margin_tier
    m._margin_guardian = mg
    m.executor = MagicMock()
    m.initializer = MagicMock()
    return m


# ── _compute_time_mult (5 contracts) ─────────────────────────────────────────

@pytest.mark.sealed
def test_time_mult_far_expiry_clamped_to_one():
    """360 min (6h) → 3.0/6.0=0.5, clamped to minimum 1.0."""
    assert _compute_time_mult(360) == pytest.approx(1.0)


@pytest.mark.sealed
def test_time_mult_two_hours():
    """120 min → 3.0/2.0=1.5, unclamped."""
    assert _compute_time_mult(120) == pytest.approx(1.5)


@pytest.mark.sealed
def test_time_mult_one_hour():
    """60 min → 3.0/1.0=3.0, at the max clamp."""
    assert _compute_time_mult(60) == pytest.approx(3.0)


@pytest.mark.sealed
def test_time_mult_very_close_expiry_clamped_to_three():
    """20 min → hours clamped to floor 0.5, 3.0/0.5=6.0, clamped to max 3.0."""
    assert _compute_time_mult(20) == pytest.approx(3.0)


@pytest.mark.sealed
def test_time_mult_zero_minutes_uses_floor():
    """0 min → hours floor=0.5, result clamped to 3.0."""
    assert _compute_time_mult(0) == pytest.approx(3.0)


# ── _compute_effective_proximity (3 contracts) ───────────────────────────────

@pytest.mark.sealed
def test_effective_proximity_scales_with_time_mult():
    """base=0.5, mult=2.0 → 1.0."""
    assert _compute_effective_proximity({'atm_shield_proximity_pct': 0.5}, 2.0) == pytest.approx(1.0)


@pytest.mark.sealed
def test_effective_proximity_no_scaling():
    """base=0.5, mult=1.0 → 0.5."""
    assert _compute_effective_proximity({'atm_shield_proximity_pct': 0.5}, 1.0) == pytest.approx(0.5)


@pytest.mark.sealed
def test_effective_proximity_uses_default_base():
    """Missing key → defaults to 0.5."""
    assert _compute_effective_proximity({}, 1.0) == pytest.approx(0.5)


# ── _compute_effective_target_otm (4 contracts) ──────────────────────────────

@pytest.mark.sealed
def test_target_otm_first_fire_no_progressive_widening():
    """count=0: progressive_mult=1.0, result=base*time_mult*1.0."""
    assert _compute_effective_target_otm({'atm_shield_target_otm_pct': 1.0}, 1.0, 0) == pytest.approx(1.0)


@pytest.mark.sealed
def test_target_otm_second_fire_widens_by_half():
    """count=1: progressive_mult=1.5."""
    assert _compute_effective_target_otm({'atm_shield_target_otm_pct': 1.0}, 1.0, 1) == pytest.approx(1.5)


@pytest.mark.sealed
def test_target_otm_third_fire_widens_more_with_time_mult():
    """count=2, time_mult=2.0: 1.0 * 2.0 * 2.0 = 4.0."""
    assert _compute_effective_target_otm({'atm_shield_target_otm_pct': 1.0}, 2.0, 2) == pytest.approx(4.0)


@pytest.mark.sealed
def test_target_otm_uses_default_base():
    """Missing key → default base=1.0."""
    assert _compute_effective_target_otm({}, 1.0, 0) == pytest.approx(1.0)


# ── check_atm_proximity (8 contracts) ────────────────────────────────────────

@pytest.mark.sealed
def test_proximity_ce_endangered():
    """CE @ 0.4% above spot → endangered (< eff_proximity=0.5%)."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 50200.0},
        'pe': {'active_lots': 5, 'active_strike': 46000.0},  # 8% away — safe
    }
    side, dist = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side == 'ce'
    assert dist == pytest.approx(0.4)


@pytest.mark.sealed
def test_proximity_pe_endangered():
    """PE @ 0.4% below spot → endangered."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 54000.0},  # safe
        'pe': {'active_lots': 5, 'active_strike': 49800.0},
    }
    side, dist = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side == 'pe'
    assert dist == pytest.approx(0.4)


@pytest.mark.sealed
def test_proximity_both_safe_returns_none():
    """Both sides 2% away → no endangered side."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 51000.0},  # 2%
        'pe': {'active_lots': 5, 'active_strike': 49000.0},  # 2%
    }
    side, dist = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side is None
    assert dist == pytest.approx(0.0)


@pytest.mark.sealed
def test_proximity_skips_side_with_zero_lots():
    """CE active_lots=0 → not checked even if within proximity."""
    session = {
        'ce': {'active_lots': 0, 'active_strike': 50100.0},  # close but no lots
        'pe': {'active_lots': 5, 'active_strike': 49000.0},  # safe
    }
    side, _ = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side is None


@pytest.mark.sealed
def test_proximity_boundary_distance_is_endangered():
    """Exactly at eff_proximity (<=) → side IS endangered."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 50250.0},  # exactly 0.5%
        'pe': {'active_lots': 0, 'active_strike': 49750.0},
    }
    side, dist = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side == 'ce'
    assert dist == pytest.approx(0.5)


@pytest.mark.sealed
def test_proximity_time_mult_widens_the_trigger_zone():
    """CE @ 0.8% away, time_mult=2.0 → eff_prox=1.0% → CE endangered."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 50400.0},  # 0.8%
        'pe': {'active_lots': 0, 'active_strike': 49000.0},
    }
    side, _ = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 2.0)
    assert side == 'ce'


@pytest.mark.sealed
def test_proximity_ce_checked_before_pe():
    """Loop order: ce first. If CE is endangered, returns CE even if PE also endangered."""
    session = {
        'ce': {'active_lots': 5, 'active_strike': 50200.0},  # 0.4% endangered
        'pe': {'active_lots': 5, 'active_strike': 49800.0},  # 0.4% also endangered
    }
    side, _ = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side == 'ce'


@pytest.mark.sealed
def test_proximity_missing_side_key_returns_none():
    """Missing ce/pe keys → treated as 0 lots, returns (None, 0)."""
    session = {}
    side, dist = check_atm_proximity(session, 50000.0, {'atm_shield_proximity_pct': 0.5}, 1.0)
    assert side is None
    assert dist == pytest.approx(0.0)


# ── _check_shield_gates (10 contracts) ───────────────────────────────────────

@pytest.mark.sealed
def test_gates_disabled():
    session = {'session_id': 'x', 'strategy_status': 'RUNNING'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(atm_shield_enabled=False), 'GREEN', 360.0)
    assert ok is False
    assert reason == 'disabled'


@pytest.mark.sealed
def test_gates_strategy_not_running():
    session = {'session_id': 'x', 'strategy_status': 'PAUSED'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(), 'GREEN', 360.0)
    assert ok is False
    assert 'status=PAUSED' in reason


@pytest.mark.sealed
def test_gates_margin_red_blocks():
    session = {'session_id': 'x', 'strategy_status': 'RUNNING'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(), 'RED', 360.0)
    assert ok is False
    assert 'margin=RED' in reason


@pytest.mark.sealed
def test_gates_margin_critical_blocks():
    session = {'session_id': 'x', 'strategy_status': 'RUNNING'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(), 'CRITICAL', 360.0)
    assert ok is False
    assert 'margin=CRITICAL' in reason


@pytest.mark.sealed
def test_gates_within_auto_close_window():
    """4 min to expiry, auto_close_mins=5 → blocked."""
    session = {'session_id': 'x', 'strategy_status': 'RUNNING'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(auto_close_mins=5), 'GREEN', 4.0)
    assert ok is False
    assert reason == 'within auto_close window'


@pytest.mark.sealed
def test_gates_cooldown_not_elapsed_blocks():
    """Fired 2 min ago, cooldown=10 min → still in cooldown."""
    recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    session = {'session_id': 'x', 'strategy_status': 'RUNNING',
               '_atm_shield_last_fire_ce': recent}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(atm_shield_cooldown_mins=10), 'GREEN', 360.0)
    assert ok is False
    assert 'cooldown' in reason


@pytest.mark.sealed
def test_gates_cooldown_elapsed_allows():
    """Fired 15 min ago, cooldown=10 min → allowed."""
    old = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    session = {'session_id': 'x', 'strategy_status': 'RUNNING',
               '_atm_shield_last_fire_ce': old}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(atm_shield_cooldown_mins=10), 'GREEN', 360.0)
    assert ok is True
    assert reason == 'ok'


@pytest.mark.sealed
def test_gates_exhausted_blocks():
    """count=3, max_per_session=3 → exhausted."""
    session = {'session_id': 'x', 'strategy_status': 'RUNNING',
               '_atm_shield_count_ce': 3}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(atm_shield_max_per_session=3), 'GREEN', 360.0)
    assert ok is False
    assert 'exhausted' in reason
    assert '3/3' in reason


@pytest.mark.sealed
def test_gates_proactive_shift_already_ran_blocks():
    session = {'session_id': 'x', 'strategy_status': 'RUNNING',
               '_proactive_shifted_ce': True}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(), 'GREEN', 360.0)
    assert ok is False
    assert 'proactive shift already ran' in reason


@pytest.mark.sealed
def test_gates_all_clear_returns_ok():
    """No blockers present → (True, 'ok')."""
    session = {'session_id': 'x', 'strategy_status': 'RUNNING'}
    ok, reason = _check_shield_gates(session, 'ce', _base_params(), 'GREEN', 360.0)
    assert ok is True
    assert reason == 'ok'


# ── Infrastructure contracts — execute_atm_shield (5 contracts) ──────────────
# execute_atm_shield is async — @sealed not applicable.
# These tests verify the calling chain: what prevents the shield from
# silently misfiring or silently failing under bad environment conditions.

@pytest.mark.sealed
def test_atm_shield_infra_disabled_exits_before_fetching_spot():
    """When disabled, exits before any I/O — spot price is never fetched."""
    session = _base_session(atm_shield_enabled=False)
    monitor = _make_monitor(session=session, spot=85000.0)
    result = asyncio.run(execute_atm_shield(monitor, 100.0, 100.0))
    assert result is False
    monitor._fetch_spot_price.assert_not_called()


@pytest.mark.sealed
def test_atm_shield_infra_returns_false_when_spot_zero():
    """spot=0 → shield never fires; spot WAS fetched (not an early exit via disabled)."""
    session = _base_session(ce_strike=100.0, pe_strike=50.0)
    monitor = _make_monitor(session=session, spot=0.0)
    result = asyncio.run(execute_atm_shield(monitor, 100.0, 100.0))
    assert result is False
    monitor._fetch_spot_price.assert_called_once()


@pytest.mark.sealed
def test_atm_shield_infra_defers_when_both_sides_in_proximity():
    """Both CE and PE within proximity → returns False, defers to close_at_ATM.
    spot=85000, CE@85300 (0.35%), PE@84700 (0.35%), eff_prox=0.5%."""
    session = _base_session(ce_strike=85300.0, pe_strike=84700.0)
    monitor = _make_monitor(session=session, spot=85000.0)
    result = asyncio.run(execute_atm_shield(monitor, 100.0, 100.0))
    assert result is False


@pytest.mark.sealed
def test_atm_shield_infra_cooldown_blocks_refire():
    """After a fire, 10-min cooldown must prevent re-fire on next heartbeat.
    CE is still in proximity (0.4%), but _atm_shield_last_fire_ce was set 1 min ago."""
    # CE@85340 → dist=(85340-85000)/85000*100=0.4% < eff_prox=0.5% → endangered
    session = _base_session(ce_strike=85340.0, pe_strike=80000.0)
    session['_atm_shield_last_fire_ce'] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()
    monitor = _make_monitor(session=session, spot=85000.0)
    result = asyncio.run(execute_atm_shield(monitor, 100.0, 100.0))
    assert result is False


@pytest.mark.sealed
def test_atm_shield_infra_exhaustion_blocks_refire():
    """Once _atm_shield_count_ce >= max_per_session, shield never fires for CE."""
    # CE@85340 → endangered, but count=3 == max=3
    session = _base_session(ce_strike=85340.0, pe_strike=80000.0)
    session['_atm_shield_count_ce'] = 3  # max_per_session=3 by default
    monitor = _make_monitor(session=session, spot=85000.0)
    result = asyncio.run(execute_atm_shield(monitor, 100.0, 100.0))
    assert result is False
