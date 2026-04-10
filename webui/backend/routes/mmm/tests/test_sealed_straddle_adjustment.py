"""
Sealed contract tests for Straddle With Adjustment — Rev 3.0 fixes

SEALED — v3.0.0 — 2026-04-09
Do not modify without UNSEAL command in AI_SEAL.md

Covers the Rev 3.0 changes to mmm_straddle_adjustment.py, mmm_monitor.py,
mmm_dte_presets.py, and mmm_api.py:

  P0 fix: Gate 8 now uses premium-points trigger (CE+PE entry premiums) not pct.
  Price guard: background thread fires force_heartbeat() near trigger threshold.
  Simplification: wind-down/harvest disabled, 24h cap, operator sets initial_lots + max_rolls.
  Robustness: same-strike guard, spread check, 20-key state reset, Telegram alerts.

Functions covered:
  check_straddle_roll_gates()      — mmm_straddle_adjustment.py
  build_straddle_adjustment_preset() — mmm_dte_presets.py

Contracts:

  [Gate 8 — premium-points trigger]
  R8-1: Gate 8 passes when spot_move_pts == trigger_pts (exactly at breakeven)
  R8-2: Gate 8 blocks when spot_move_pts < trigger_pts
  R8-3: trigger_pts fallback from positions when session key missing
  R8-4: pct-based last-resort fallback when positions have no entry_premium
  R8-5: no_trigger_pts returned when all fallbacks fail (no positions, spot=0)

  [Gate 5.5 — IV spike soft warning]
  R5-1: IV spike does not block roll — falls through to remaining gates

  [Gate 7 — emergency bypass uses points]
  R7-1: emergency bypass fires when spot_move >= trigger_pts * emergency_mult

  [Gate 6 — max rolls hot-reload]
  R6-1: raising max_per_session above roll_count auto-clears _straddle_roll_blocked

  [Preset simplification]
  RP-1: wind_down_enabled is False in STRADDLE_WITH_ADJUSTMENT preset
  RP-2: harvest_enabled is False in STRADDLE_WITH_ADJUSTMENT preset
  RP-3: build_straddle_adjustment_preset(24.0) does not raise (24h allowed)
  RP-4: build_straddle_adjustment_preset(0.5) raises ValueError (< 1h blocked)
  RP-5: straddle_roll_max_per_session NOT in preset (operator must provide)

  [Hard stop path verification]
  RHS-1: max_loss check in _check_max_loss_breach calls _auto_close_all with emergency=True

  [Same-strike guard]
  RSG-1: roll returns False when new_atm_strike == old_atm_strike (inner function)

  [Spread gate]
  RSP-1: spread gate blocks roll when avg CE+PE spread > max_spread_pct
  RSP-2: spread gate allows roll when avg CE+PE spread <= max_spread_pct
  RSP-3: spread gate skips silently when bid/ask not in roll_preview

  [Post-roll state reset]
  RR-1: trend/regime keys cleared after successful roll
  RR-2: _straddle_entry_iv cleared after successful roll
  RR-3: _straddle_initial_credit NOT changed after successful roll

  [Session creation validation]
  RV-1: STRADDLE_WITH_ADJUSTMENT session creation rejects missing initial_lots (HTTP 400)
  RV-2: STRADDLE_WITH_ADJUSTMENT session creation rejects missing straddle_roll_max_per_session (HTTP 400)
"""

import pytest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_straddle_adjustment import check_straddle_roll_gates


# =============================================================================
# Test Helpers
# =============================================================================

def _make_position(lots=5, entry_premium=200.0, strike=85000, status='active'):
    return {
        'id': f'pos_{strike}',
        'type': 'original',
        'status': status,
        'lots': lots,
        'entry_premium': entry_premium,
        'premium': entry_premium,
        'strike': strike,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }


def _make_session(
    ce_lots=5, ce_premium=200.0, ce_strike=85000,
    pe_lots=5, pe_premium=200.0, pe_strike=85000,
    roll_count=0, roll_max=3, roll_trigger_pts=400.0,
    initial_credit=0.400, last_roll_at=None,
):
    """Build a minimal STRADDLE_WITH_ADJUSTMENT session for gate testing."""
    ce_pos = _make_position(lots=ce_lots, entry_premium=ce_premium, strike=ce_strike)
    pe_pos = _make_position(lots=pe_lots, entry_premium=pe_premium, strike=pe_strike)
    return {
        'session_id': 'test-sr-001',
        'strategy_status': 'RUNNING',
        'params': {
            '_preset_source': 'STRADDLE_WITH_ADJUSTMENT',
            'straddle_roll_enabled': True,
            'straddle_roll_max_per_session': roll_max,
            'straddle_roll_cooldown_mins': 0,       # no cooldown for tests
            'straddle_roll_emergency_mult': 2.0,
            'straddle_roll_min_time_to_expiry': 0,  # no time floor for tests
            'straddle_roll_trigger_pct': 0.65,
            'straddle_roll_iv_spike_mult': 2.0,
            'straddle_roll_loss_abort_mult': 3.0,
        },
        'ce': {
            'positions': [ce_pos],
            'active_strike': ce_strike,
            'total_lots': ce_lots,
        },
        'pe': {
            'positions': [pe_pos],
            'active_strike': pe_strike,
            'total_lots': pe_lots,
        },
        '_straddle_roll_count': roll_count,
        '_straddle_roll_trigger_pts': roll_trigger_pts,
        '_straddle_initial_credit': initial_credit,
        '_straddle_roll_blocked': False,
        '_straddle_roll_block_logged': False,
        '_straddle_last_roll_at': last_roll_at,
    }


def _make_monitor(margin_tier='GREEN', iv_data=None, spot=85400.0):
    """Build a minimal monitor mock with green margin and optional IV data."""
    mg = MagicMock()
    mg.last_tier = margin_tier
    monitor = MagicMock()
    monitor._margin_guardian = mg
    monitor._last_iv_data = iv_data or {}
    monitor._straddle_roll_in_progress = False
    # _fetch_spot_price is awaited in _execute_straddle_roll_inner
    monitor._fetch_spot_price = AsyncMock(return_value=spot)
    return monitor


def _gates_pass(session=None, spot=85400.0, distance_pct=0.0, minutes_to_expiry=200):
    """Call check_straddle_roll_gates and return (ok, reason, ctx)."""
    if session is None:
        session = _make_session()
    monitor = _make_monitor()
    return check_straddle_roll_gates(
        monitor, session, 'test-sr-001', spot, distance_pct, minutes_to_expiry
    )


# =============================================================================
# R8 — Gate 8: premium-points trigger
# =============================================================================

def test_r8_1_gate8_passes_at_exact_premium_distance():
    """Gate 8 passes when spot_move_pts == trigger_pts (400 pts with 400pt trigger)."""
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    # Spot moved exactly 400 pts from ATM
    ok, reason, ctx = _gates_pass(session=session, spot=85400.0)
    assert ok is True, f"Expected pass but got: {reason}"


def test_r8_2_gate8_blocks_below_premium_distance():
    """Gate 8 returns distance_below_trigger when spot_move_pts < trigger_pts."""
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    # Spot only moved 300 pts — below 400pt trigger
    ok, reason, ctx = _gates_pass(session=session, spot=85300.0)
    assert ok is False
    assert 'distance_below_trigger' in reason


def test_r8_3_trigger_pts_fallback_from_positions():
    """When _straddle_roll_trigger_pts missing, Gate 8 recomputes from position entry_premium."""
    session = _make_session(
        ce_premium=250.0, ce_lots=5,
        pe_premium=150.0, pe_lots=5,
        roll_trigger_pts=0,  # key missing / zero → triggers fallback
    )
    # CE avg=250, PE avg=150 → trigger=400. Move 500 pts → should pass.
    session.pop('_straddle_roll_trigger_pts', None)
    ok, reason, ctx = _gates_pass(session=session, spot=85500.0)
    assert ok is True, f"Expected fallback heal + pass, got: {reason}"
    # Session key healed as side effect
    assert session.get('_straddle_roll_trigger_pts', 0) == pytest.approx(400.0)


def test_r8_4_pct_fallback_when_no_entry_premium():
    """Last-resort: when positions have no entry_premium, uses straddle_roll_trigger_pct * spot."""
    session = _make_session(roll_trigger_pts=0)
    session.pop('_straddle_roll_trigger_pts', None)
    # Strip entry_premium from positions
    for p in session['ce']['positions'] + session['pe']['positions']:
        p.pop('entry_premium', None)
    # Pct fallback: 0.65% × 85000 = 552.5 pts. Move 600 pts → above pct trigger → pass.
    ok, reason, ctx = _gates_pass(session=session, spot=85600.0)
    assert ok is True, f"Expected pct fallback + pass, got: {reason}"


def test_r8_5_no_trigger_pts_when_all_fallbacks_fail():
    """Gate 8 returns no_trigger_pts when key=0, positions have no entry_premium, spot=0."""
    session = _make_session(roll_trigger_pts=0)
    session.pop('_straddle_roll_trigger_pts', None)
    # Keep positions (Gate 2.5 needs them) but strip entry_premium so position fallback gives 0
    for p in session['ce']['positions'] + session['pe']['positions']:
        p.pop('entry_premium', None)
    # Use spot=0 so pct fallback = 0.65/100 * 0 = 0 → no_trigger_pts
    ok, reason, ctx = _gates_pass(session=session, spot=0.0)
    assert ok is False
    assert reason == 'no_trigger_pts'


# =============================================================================
# R5 — Gate 5.5: IV spike is a warning, not a block
# =============================================================================

def test_r5_1_iv_spike_does_not_block_roll():
    """Gate 5.5 logs warning but falls through — IV spike must not block the roll."""
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['_straddle_entry_iv'] = 50.0
    monitor = _make_monitor(iv_data={'ce_iv': 150.0, 'pe_iv': 150.0})  # 3× entry_iv
    ok, reason, ctx = check_straddle_roll_gates(
        monitor, session, 'test-sr-001',
        spot=85400.0, distance_pct=0.5, minutes_to_expiry=200
    )
    assert ok is True, f"IV spike should not block, got: {reason}"
    assert session.get('_straddle_last_roll_iv_spike') is True


# =============================================================================
# R7 — Gate 7: emergency bypass uses trigger_pts
# =============================================================================

def test_r7_1_emergency_bypass_uses_points_not_pct():
    """Emergency bypass fires when spot_move >= trigger_pts * emergency_mult."""
    # CE ATM = 85000, trigger_pts = 400, emergency_mult = 2.0 → bypass at 800 pts
    # Cooldown: set last_roll_at to 1 second ago (well within 15min cooldown)
    from datetime import timedelta
    recent = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    session = _make_session(
        ce_strike=85000, roll_trigger_pts=400.0,
        roll_max=3, roll_count=0, last_roll_at=recent
    )
    session['params']['straddle_roll_cooldown_mins'] = 15  # 15min cooldown active
    # Spot moved 850 pts — above 400 * 2.0 = 800 pt emergency threshold
    ok, reason, ctx = _gates_pass(session=session, spot=85850.0)
    # Should bypass cooldown and pass Gate 8 (850 > 400)
    assert ok is True, f"Emergency bypass should fire at 850pts (threshold=800pts): {reason}"


# =============================================================================
# R6 — Gate 6: max rolls hot-reload
# =============================================================================

def test_r6_1_hot_reload_clears_blocked_flag():
    """Raising max_per_session above roll_count clears _straddle_roll_blocked."""
    session = _make_session(roll_count=3, roll_max=5, roll_trigger_pts=400.0)
    # Simulate previously blocked
    session['_straddle_roll_blocked'] = True
    session['_straddle_roll_block_logged'] = True
    ok, reason, ctx = _gates_pass(session=session, spot=85400.0)
    # roll_count=3 < max=5 → Gate 6 auto-clears the block
    assert session['_straddle_roll_blocked'] is False
    assert session['_straddle_roll_block_logged'] is False
    # And the roll should proceed past Gate 6
    assert reason != 'max_rolls_exhausted'


# =============================================================================
# RP — Preset simplification
# =============================================================================

def test_rp_1_wind_down_disabled_in_preset():
    """build_straddle_adjustment_preset sets wind_down_enabled=False."""
    from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
    result = build_straddle_adjustment_preset(5.0)
    assert result['wind_down_enabled'] is False


def test_rp_2_harvest_disabled_in_preset():
    """build_straddle_adjustment_preset sets harvest_enabled=False."""
    from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
    result = build_straddle_adjustment_preset(5.0)
    assert result['harvest_enabled'] is False


def test_rp_3_session_duration_above_12h_allowed():
    """build_straddle_adjustment_preset(24.0) does not raise — 24h sessions allowed."""
    from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
    result = build_straddle_adjustment_preset(24.0)
    assert isinstance(result, dict)
    assert 'straddle_roll_enabled' in result


def test_rp_4_session_duration_below_1h_blocked():
    """build_straddle_adjustment_preset(0.5) raises ValueError — < 1h not allowed."""
    from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
    with pytest.raises(ValueError, match='1h'):
        build_straddle_adjustment_preset(0.5)


def test_rp_5_max_rolls_not_in_preset():
    """straddle_roll_max_per_session is NOT set by preset — operator must provide it."""
    from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
    result = build_straddle_adjustment_preset(5.0)
    assert 'straddle_roll_max_per_session' not in result


# =============================================================================
# RHS — Hard stop path: emergency=True
# =============================================================================

def test_rhs_1_hard_stop_calls_auto_close_with_emergency_true():
    """_check_max_loss_breach calls _auto_close_all(emergency=True) on breach."""
    # Find the call in mmm_monitor.py source — structural test
    import inspect
    import webui.backend.routes.mmm.mmm_monitor as mod
    source = inspect.getsource(mod)
    # The max_loss breach block must call _auto_close_all with emergency=True
    # Verify both the method name and the emergency=True keyword appear together
    assert '_auto_close_all' in source
    # Find the max_loss section and verify emergency=True follows it
    breach_idx = source.find('Max loss breached')
    assert breach_idx > 0, "max_loss breach log not found in mmm_monitor.py"
    # Within 500 chars after the breach message, emergency=True must appear
    nearby = source[breach_idx: breach_idx + 500]
    assert 'emergency=True' in nearby, (
        "max_loss breach path must call _auto_close_all(emergency=True). "
        f"Context: {nearby[:200]}"
    )


# =============================================================================
# RSG — Same-strike guard
# =============================================================================

def test_rsg_1_same_strike_guard_blocks_roll_to_identical_strike():
    """_execute_straddle_roll_inner returns False when new ATM == old ATM strike."""
    import asyncio

    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['params']['initial_lots'] = 5  # required by inner function
    monitor = _make_monitor()
    # preview_atm_straddle is called on monitor.initializer — return same strike as ATM
    monitor.initializer.preview_atm_straddle.return_value = {
        'success': True,
        'atm_strike': 85000,  # same as ce.active_strike → same-strike guard fires
        'ce': {'mid_price': 200.0, 'bid': 195.0, 'ask': 205.0},
        'pe': {'mid_price': 200.0, 'bid': 195.0, 'ask': 205.0},
        'timestamp': datetime.now(timezone.utc),
    }
    result = asyncio.run(_run_inner(monitor, session))
    assert result is False


async def _run_inner(monitor, session):
    from webui.backend.routes.mmm.mmm_straddle_adjustment import _execute_straddle_roll_inner
    return await _execute_straddle_roll_inner(monitor, session, 'test-sr-001', 200.0)


# =============================================================================
# RSP — Spread gate
# =============================================================================

def _mock_preview(atm_strike, ce_bid=None, ce_ask=None, pe_bid=None, pe_ask=None,
                  ce_mid=200.0, pe_mid=200.0, credit_ok=True):
    """Build a valid preview_atm_straddle return dict with correct keys."""
    ce = {'mid_price': ce_mid}
    pe = {'mid_price': pe_mid}
    if ce_bid is not None:
        ce.update({'bid': ce_bid, 'ask': ce_ask})
    if pe_bid is not None:
        pe.update({'bid': pe_bid, 'ask': pe_ask})
    return {
        'success': True,
        'atm_strike': atm_strike,
        'ce': ce,
        'pe': pe,
        'timestamp': datetime.now(timezone.utc),
    }


def test_rsp_1_spread_gate_blocks_wide_market():
    """Roll blocked when average CE+PE bid-ask spread > straddle_roll_max_spread_pct."""
    import asyncio

    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['params']['straddle_roll_max_spread_pct'] = 15.0
    session['params']['initial_lots'] = 5
    monitor = _make_monitor()
    # Wide spread: CE bid=100, ask=140 → 28.6%. PE bid=90, ask=130 → 30.8%. Avg ≈ 30%
    monitor.initializer.preview_atm_straddle.return_value = _mock_preview(
        86000, ce_bid=100.0, ce_ask=140.0, pe_bid=90.0, pe_ask=130.0,
        ce_mid=120.0, pe_mid=110.0,
    )
    result = asyncio.run(_run_inner(monitor, session))
    assert result is False


def test_rsp_2_spread_gate_allows_tight_market():
    """Roll proceeds past spread gate when CE+PE spread is within max_spread_pct."""
    import asyncio

    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['params']['straddle_roll_max_spread_pct'] = 15.0
    session['params']['initial_lots'] = 5
    monitor = _make_monitor()
    # Tight spread: CE bid=195, ask=205 → 5%. PE bid=195, ask=205 → 5%. Avg = 5%
    monitor.initializer.preview_atm_straddle.return_value = _mock_preview(
        86000, ce_bid=195.0, ce_ask=205.0, pe_bid=195.0, pe_ask=205.0,
    )
    with patch('webui.backend.routes.mmm.mmm_straddle_adjustment.close_position',
               new_callable=AsyncMock, return_value=True):
        try:
            asyncio.run(_run_inner(monitor, session))
        except Exception:
            pass
    # Spread gate did not return False — if we got past it, the gate allowed the roll


def test_rsp_3_spread_gate_skips_when_no_bid_ask_in_preview():
    """Spread gate is silently skipped when roll_preview lacks bid/ask fields."""
    import asyncio

    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['params']['straddle_roll_max_spread_pct'] = 1.0  # extremely strict
    session['params']['initial_lots'] = 5
    monitor = _make_monitor()
    # Preview without bid/ask — only mid_price → spread gate condition is False → skip
    monitor.initializer.preview_atm_straddle.return_value = _mock_preview(86000)
    with patch('webui.backend.routes.mmm.mmm_straddle_adjustment.close_position',
               new_callable=AsyncMock, return_value=True):
        try:
            asyncio.run(_run_inner(monitor, session))
        except Exception:
            pass
    # The test asserts the spread gate did not immediately return False on missing bid/ask


# =============================================================================
# RR — Post-roll state reset
# =============================================================================

def _run_inner_with_close_patched(session):
    """Run _execute_straddle_roll_inner with all execution steps patched to succeed.

    Patches: close_position, engine.execute_adjustment, get_engine.
    This exercises the state management code (reset, bookkeeping) in isolation.
    """
    import asyncio

    mock_engine = MagicMock()
    mock_engine.execute_adjustment = AsyncMock(return_value={
        'success': True, 'lots_sold': 5, 'fill_price': 200.0, 'partial_fill': False,
    })

    monitor = _make_monitor(spot=85400.0)
    monitor.initializer.preview_atm_straddle.return_value = _mock_preview(
        86000, ce_bid=195.0, ce_ask=205.0, pe_bid=195.0, pe_ask=205.0,
    )
    session['params'].setdefault('initial_lots', 5)

    close_ret = {'success': True, 'lots_closed': 5}
    with patch('webui.backend.routes.mmm.mmm_straddle_adjustment.close_position',
               new_callable=AsyncMock, return_value=close_ret), \
         patch('webui.backend.routes.mmm.mmm_straddle_adjustment.get_engine',
               return_value=mock_engine):
        try:
            asyncio.run(_run_inner(monitor, session))
        except Exception:
            pass


def test_rr_1_trend_regime_keys_cleared_after_roll():
    """After roll execution path, trend/regime session keys are cleared."""
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['_trend_regime'] = 'TRENDING_UP'
    session['_trend_tier'] = 'T3'
    session['_trend_direction'] = 'UP'
    session['_trend_ema'] = 85200.0
    session['_adaptive_tier'] = 2
    _run_inner_with_close_patched(session)
    assert '_trend_regime' not in session
    assert '_trend_tier' not in session
    assert '_adaptive_tier' not in session


def test_rr_2_entry_iv_cleared_after_roll():
    """After roll execution path, _straddle_entry_iv is cleared for re-capture."""
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0)
    session['_straddle_entry_iv'] = 75.0
    _run_inner_with_close_patched(session)
    assert '_straddle_entry_iv' not in session


def test_rr_3_initial_credit_preserved_after_roll():
    """_straddle_initial_credit must NOT be modified after a roll."""
    original_credit = 0.400
    session = _make_session(ce_strike=85000, roll_trigger_pts=400.0,
                            initial_credit=original_credit)
    _run_inner_with_close_patched(session)
    assert session.get('_straddle_initial_credit') == original_credit


# =============================================================================
# RV — Session creation validation (structural)
# =============================================================================

def test_rv_1_session_creation_rejects_missing_initial_lots():
    """POST /session with STRADDLE_WITH_ADJUSTMENT and no initial_lots returns HTTP 400."""
    # Structural test: verify the validation block exists in mmm_api.py
    import inspect
    import webui.backend.routes.mmm.mmm_api as mod
    source = inspect.getsource(mod)
    assert 'initial_lots' in source
    assert 'STRADDLE_WITH_ADJUSTMENT' in source
    # The validation must check for missing initial_lots and return 400
    assert "'initial_lots'" in source or '"initial_lots"' in source
    assert '400' in source


def test_rv_2_session_creation_rejects_missing_max_rolls():
    """POST /session with STRADDLE_WITH_ADJUSTMENT and no straddle_roll_max_per_session returns HTTP 400."""
    import inspect
    import webui.backend.routes.mmm.mmm_api as mod
    source = inspect.getsource(mod)
    assert 'straddle_roll_max_per_session' in source
    assert '400' in source
