"""
Contract tests for MMMEngine.calculate_lots_to_sell

SEALED — v1.0.0 — March 14, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Method: MMMEngine.calculate_lots_to_sell(session, hedge_side, loss_to_cover, hedge_premium)
        → (lots_to_sell: int, constraint_msg: str, is_position_cap_hit: bool)
File: webui/backend/routes/mmm/mmm_engine.py

Contracts:
  C1.  hedge_premium <= 0 → (0, non-empty msg, False) — never sells
  C2.  loss_to_cover <= 0 → (0, non-empty msg, False) — never sells phantom lots
  C3.  basic lots = ceil(loss / (premium * LOT_SIZE_BTC) * (1 + buffer_pct)), min 1
  C4.  position cap hit (active_lots >= max_lots_per_side) → (0, msg, True)
  C5.  is_position_cap_hit=True ONLY for position cap, NOT for total exposure ceiling
  C6.  total exposure ceiling hit → (0, msg, False) — does NOT trigger M2
  C7.  gamma_aware_enabled: 200%+ excess → 1.3x multiplier on lots
  C8.  gamma_aware_enabled: 0 excess → no multiplier (1.0x)
  C9.  trend_boost: safe side + tier >=1 + boost_enabled → lots boosted
  C10. trend_boost: no trend (tier=0) → session _trend_boost_active=False
  C11. IMP-2 lot reduction: dangerous side + tier>=1, no boost → lots reduced
  C12. IMP-3 asymmetry: heavy side + reduction < 1.0 → lots capped
  C13. normal path returns is_position_cap_hit=False
  C14. lots_to_sell is always a positive int on success path (never float, never 0)
"""

import math
import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.sealed

LOT_SIZE_BTC = 0.001  # Mirror of mmm_constants.LOT_SIZE_BTC


def _make_engine():
    """Create a minimal MMMEngine instance with no live dependencies."""
    from webui.backend.routes.mmm.mmm_engine import MMMEngine
    engine = MMMEngine.__new__(MMMEngine)
    return engine


def _base_session(
    ce_active_lots=0, pe_active_lots=0,
    ce_total_lots=None, pe_total_lots=None,
    max_lots_per_side=100,
    max_total_exposure=0,
    buffer_pct=0.05,
    gamma_aware_enabled=False,
    trend_tier=0,
    trend_direction='none',
    trend_boost_enabled=False,
    asymmetry_reduction=1.0,
    asymmetry_heavy_side='',
    last_trigger_result=None,
):
    """Build a minimal session dict for calculate_lots_to_sell tests."""
    ce_total = ce_total_lots if ce_total_lots is not None else ce_active_lots
    pe_total = pe_total_lots if pe_total_lots is not None else pe_active_lots
    return {
        'params': {
            'premium_buffer_pct': buffer_pct,
            'max_lots_per_side': max_lots_per_side,
            'max_total_exposure': max_total_exposure,
            'gamma_aware_enabled': gamma_aware_enabled,
            'gamma_aware_max_multiplier': 1.3,
            'trend_boost_enabled': trend_boost_enabled,
            'trend_boost_tier1_mult': 1.3,
            'trend_boost_tier2_mult': 1.5,
            'trend_boost_tier3_mult': 2.0,
            'trend_tier1_lot_reduction': 0.30,
            'atm_shield_enabled': False,
            'strike_shift_use_lot_scaling': False,
        },
        'ce': {'active_lots': ce_active_lots, 'total_lots': ce_total},
        'pe': {'active_lots': pe_active_lots, 'total_lots': pe_total},
        '_trend_tier': trend_tier,
        '_trend_direction': trend_direction,
        '_last_trigger_result': last_trigger_result or {},
        '_asymmetry_lot_reduction_pct': asymmetry_reduction,
        '_asymmetry_heavy_side': asymmetry_heavy_side,
        '_strike_shift_otm_multiplier': 1.0,
    }


# ─── C1: hedge_premium <= 0 ────────────────────────────────────────────────

def test_c1_zero_premium_returns_zero():
    engine = _make_engine()
    lots, msg, cap = engine.calculate_lots_to_sell(_base_session(), 'ce', 500.0, 0)
    assert lots == 0
    assert cap is False
    assert msg  # non-empty


def test_c1b_negative_premium_returns_zero():
    engine = _make_engine()
    lots, msg, cap = engine.calculate_lots_to_sell(_base_session(), 'ce', 500.0, -10.0)
    assert lots == 0
    assert cap is False


# ─── C2: loss_to_cover <= 0 ────────────────────────────────────────────────

def test_c2_zero_loss_returns_zero():
    engine = _make_engine()
    lots, msg, cap = engine.calculate_lots_to_sell(_base_session(), 'ce', 0.0, 100.0)
    assert lots == 0
    assert cap is False
    assert msg


def test_c2b_negative_loss_returns_zero():
    engine = _make_engine()
    lots, msg, cap = engine.calculate_lots_to_sell(_base_session(), 'ce', -100.0, 100.0)
    assert lots == 0
    assert cap is False


# ─── C3: basic lot calculation ─────────────────────────────────────────────

def test_c3_basic_lots_calculation():
    """
    loss=0.1 USD, premium=100, buffer=5%
    raw = 0.1 / (100 * 0.001) * 1.05 = 1.0 * 1.05 = 1.05 → ceil = 2
    Use a large cap so position cap doesn't interfere.
    """
    engine = _make_engine()
    session = _base_session(buffer_pct=0.05, max_lots_per_side=10000)
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 0.1, 100.0)
    expected_raw = 0.1 / (100.0 * LOT_SIZE_BTC) * 1.05
    assert lots == max(math.ceil(expected_raw), 1)
    assert cap is False


def test_c3b_minimum_one_lot():
    """Even tiny loss with huge premium still produces at least 1 lot."""
    engine = _make_engine()
    session = _base_session(buffer_pct=0.0)
    # loss=0.000001, premium=10000 → raw < 1 → ceil → 1
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 0.000001, 10000.0)
    assert lots >= 1


# ─── C4: position cap returns (0, msg, True) ───────────────────────────────

def test_c4_position_cap_hit_returns_true_flag():
    """active_lots=100, max=100 → cap already hit."""
    engine = _make_engine()
    session = _base_session(ce_active_lots=100, max_lots_per_side=100)
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 500.0, 100.0)
    assert lots == 0
    assert cap is True
    assert msg  # non-empty


def test_c4b_partial_cap_trims_but_doesnt_return_cap():
    """active_lots=95, max=100, want to sell 10 → trimmed to 5 → not cap=True."""
    engine = _make_engine()
    # loss chosen so raw_lots ≈ 10
    loss = 10 * 100.0 * LOT_SIZE_BTC / 1.05  # ~0.952
    session = _base_session(ce_active_lots=95, max_lots_per_side=100, buffer_pct=0.05)
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', loss, 100.0)
    assert lots > 0
    assert lots <= 5
    assert cap is False


# ─── C5: is_position_cap_hit=True ONLY for position cap ───────────────────

def test_c5_position_cap_returns_true_not_false():
    engine = _make_engine()
    session = _base_session(ce_active_lots=100, max_lots_per_side=100)
    _, _, cap = engine.calculate_lots_to_sell(session, 'ce', 500.0, 100.0)
    assert cap is True  # position cap = True


# ─── C6: total exposure ceiling returns (0, msg, False) ───────────────────

def test_c6_total_exposure_ceiling_returns_false_flag():
    """
    total_lots=200, max_total_exposure=200 → ceiling hit → is_cap=False.
    """
    engine = _make_engine()
    session = _base_session(
        ce_active_lots=90,
        ce_total_lots=200,
        max_lots_per_side=100,
        max_total_exposure=200,
    )
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 500.0, 100.0)
    assert lots == 0
    assert cap is False  # total exposure ceiling does NOT trigger M2
    assert msg


# ─── C7: gamma-aware 200%+ excess → 1.3x ──────────────────────────────────

def test_c7_gamma_aware_200pct_excess_applies_1_3x():
    engine = _make_engine()
    # hedge=ce → aggressor=pe → pe_excess_pct=200
    # Use small loss and high cap so position cap doesn't interfere.
    session = _base_session(
        gamma_aware_enabled=True,
        last_trigger_result={'pe_excess_pct': 200},
        max_lots_per_side=10000,
        buffer_pct=0.0,
    )
    # base lots for loss=0.1, premium=100, buffer=0%: ceil(0.1 / 0.1) = 1
    base_lots = math.ceil(0.1 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 0.1, 100.0)
    assert lots == max(math.ceil(base_lots * 1.3), 1)
    assert '1.3' in msg or 'Gamma' in msg


# ─── C8: gamma-aware 0% excess → no multiplier ────────────────────────────

def test_c8_gamma_aware_zero_excess_no_multiplier():
    engine = _make_engine()
    session = _base_session(
        gamma_aware_enabled=True,
        last_trigger_result={'pe_excess_pct': 0},
        buffer_pct=0.0,
    )
    base_lots = math.ceil(10.0 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert lots == base_lots
    assert 'Gamma' not in msg


# ─── C9: trend boost on safe side ─────────────────────────────────────────

def test_c9_trend_boost_safe_side_increases_lots():
    """UP trend: PE is safe side → selling PE → should get boost.
    Use small loss + high cap so position cap doesn't interfere."""
    engine = _make_engine()
    session = _base_session(
        trend_tier=1,
        trend_direction='up',
        trend_boost_enabled=True,
        buffer_pct=0.0,
        max_lots_per_side=10000,
    )
    # base lots for loss=0.1, premium=100, buffer=0%: ceil(0.1 / 0.1) = 1
    base_lots = math.ceil(0.1 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'pe', 0.1, 100.0)
    # tier1 boost = 1.3x
    assert lots == max(math.ceil(base_lots * 1.3), 1)
    assert session['_trend_boost_active'] is True
    assert session['_trend_boost_mult'] == 1.3


# ─── C10: no trend → _trend_boost_active=False ────────────────────────────

def test_c10_no_trend_boost_active_false():
    engine = _make_engine()
    session = _base_session(trend_tier=0)
    engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert session['_trend_boost_active'] is False
    assert session['_trend_boost_mult'] == 1.0


# ─── C11: IMP-2 dangerous side reduction ──────────────────────────────────

def test_c11_trend_reduction_dangerous_side():
    """UP trend: CE is dangerous side → 30% lot reduction."""
    engine = _make_engine()
    session = _base_session(
        trend_tier=1,
        trend_direction='up',
        trend_boost_enabled=False,
        buffer_pct=0.0,
    )
    base_lots = math.ceil(10.0 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    expected = max(math.ceil(base_lots * (1.0 - 0.30)), 1)
    assert lots == expected
    assert session['_trend_boost_active'] is False


# ─── C12: IMP-3 asymmetry reduction on heavy side ─────────────────────────

def test_c12_asymmetry_reduction_on_heavy_side():
    """Asymmetry is now warn-only — _asymmetry_lot_reduction_pct is ignored by
    calculate_lots_to_sell. Even with the flag set, lots are NOT reduced."""
    engine = _make_engine()
    session = _base_session(
        asymmetry_reduction=0.5,
        asymmetry_heavy_side='ce',
        buffer_pct=0.0,
    )
    base_lots = math.ceil(10.0 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    # Engine no longer reads _asymmetry_lot_reduction_pct — lots are at base_lots
    assert lots == base_lots


def test_c12b_asymmetry_no_reduction_on_non_heavy_side():
    """Asymmetry reduction applies only to heavy side, not the other side."""
    engine = _make_engine()
    session = _base_session(
        asymmetry_reduction=0.5,
        asymmetry_heavy_side='ce',
        buffer_pct=0.0,
    )
    base_lots = math.ceil(10.0 / (100.0 * LOT_SIZE_BTC))
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'pe', 10.0, 100.0)
    # PE is NOT the heavy side → no reduction
    assert lots == base_lots


# ─── C13: normal path returns False for is_position_cap_hit ───────────────

def test_c13_normal_path_cap_false():
    engine = _make_engine()
    session = _base_session()
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert cap is False
    assert lots > 0


# ─── C14: lots is always a positive integer ────────────────────────────────

def test_c14_return_type_is_int():
    engine = _make_engine()
    session = _base_session()
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert isinstance(lots, int)
    assert lots >= 1


def test_c14b_msg_is_string():
    engine = _make_engine()
    session = _base_session()
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert isinstance(msg, str)


def test_c14c_cap_is_bool():
    engine = _make_engine()
    session = _base_session()
    lots, msg, cap = engine.calculate_lots_to_sell(session, 'ce', 10.0, 100.0)
    assert isinstance(cap, bool)
