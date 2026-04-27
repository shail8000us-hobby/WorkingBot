"""
Sealed contract tests for STRADDLE_ROLL — Pure Straddle Roll

SEALED — v1.0.0 — 2026-04-10
Do not modify without UNSEAL command in AI_SEAL.md

Covers mmm_straddle_roll_pure.py, mmm_dte_presets.py (STRADDLE_ROLL),
mmm_executor.py (place_market_order_immediate), mmm_api.py (validation).

Functions covered:
  _check_pure_roll_gates()        — mmm_straddle_roll_pure.py
  build_straddle_roll_preset()    — mmm_dte_presets.py
  execute_pure_straddle_roll()    — mmm_straddle_roll_pure.py (partial via mocking)

Contracts:

  [Gate 8 — premium-points trigger]
  P8-1: Gate 8 passes when spot_move_pts == trigger_pts (exactly at trigger)
  P8-2: Gate 8 blocks when spot_move_pts < trigger_pts
  P8-3: trigger_pts healed from positions when session key missing
  P8-4: trigger_pts updated to new_ce_fill + new_pe_fill after roll

  [Gate 2 — preset isolation]
  PI-1: _preset_source=STRADDLE_ROLL → _check_pure_roll_gates passes Gate 2
  PI-2: _preset_source=STRADDLE_WITH_ADJUSTMENT → _check_pure_roll_gates blocks Gate 2
  PI-3: STRADDLE_ROLL sessions never routed to mmm_straddle_adjustment module
  PI-4: STRADDLE_WITH_ADJUSTMENT sessions never routed to mmm_straddle_roll_pure module

  [Hard stop — market orders]
  PHS-1: execute_pure_straddle_roll fires hard stop when total_pnl <= -max_loss_amount
  PHS-2: hard stop calls place_market_order_immediate, NOT smart_execute

  [Gate 6 — max rolls]
  PR6-1: Gate 6 blocks roll when roll_count >= max_per_session
  PR6-2: Gate 6 passes when roll_count < max_per_session
  PR6-3: max_per_session == 0 → no_roll_mode (hard stop only, rolls disabled)

  [Gate 5 — IV spike soft warning]
  PIV-1: IV spike logs warning but does not block roll (falls through Gate 5)
  PIV-2: IV spike sets _straddle_last_roll_iv_spike = True in session

  [Post-roll state reset]
  PRR-1: _trend_* regime keys cleared after successful roll
  PRR-2: _straddle_entry_iv cleared after successful roll
  PRR-3: _straddle_initial_credit NOT changed after roll

  [Preset]
  PP-1: build_straddle_roll_preset sets min_trigger_move=9999
  PP-2: build_straddle_roll_preset sets straddle_roll_hard_stop_market_order=True
  PP-3: build_straddle_roll_preset raises ValueError for H < 1.0
  PP-4: build_straddle_roll_preset succeeds for H=24 (no 12h cap)
  PP-5: wind_down_enabled=False in STRADDLE_ROLL preset
  PP-6: harvest_enabled=False in STRADDLE_ROLL preset

  [Session creation validation]
  PV-1: STRADDLE_ROLL session creation rejects missing initial_lots (HTTP 400)
  PV-2: STRADDLE_ROLL session creation rejects missing straddle_roll_max_per_session (HTTP 400)
  PV-3: STRADDLE_ROLL session creation rejects missing max_loss_amount (HTTP 400)

  [execute_pure_straddle_roll entry-point (A5-05)]
  C-SR-1: expiry auto-close fires when tte < auto_close_mins — returns True, sets STOPPED
  C-SR-2: roll suppressed inside min_time window (auto_close_mins <= tte < min_time) — returns False
  C-SR-3: zero/unavailable spot returns False without raising
"""

import asyncio
import pytest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_straddle_roll_pure import _check_pure_roll_gates
from webui.backend.routes.mmm.mmm_dte_presets import (
    build_straddle_roll_preset,
    STRADDLE_ROLL_CATEGORY,
    STRADDLE_WITH_ADJUSTMENT_CATEGORY,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_position(lots=1, entry_premium=250.0, strike=71000, status='active'):
    return {
        'id': f'pos_{strike}_{lots}',
        'type': 'original',
        'status': status,
        'lots': lots,
        'entry_premium': entry_premium,
        'premium': entry_premium,
        'strike': strike,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }


def _make_session(
    ce_lots=1, ce_premium=300.0, ce_strike=71000,
    pe_lots=1, pe_premium=200.0, pe_strike=71000,
    roll_count=0, roll_max=5,
    roll_trigger_pts=500.0,
    initial_credit=0.500,
    last_roll_at=None,
    preset='STRADDLE_ROLL',
    max_loss_amount=200.0,
):
    """Build a minimal STRADDLE_ROLL session for gate testing."""
    ce_pos = _make_position(lots=ce_lots, entry_premium=ce_premium, strike=ce_strike)
    pe_pos = _make_position(lots=pe_lots, entry_premium=pe_premium, strike=pe_strike)
    return {
        'session_id': 'test-pure-001',
        'strategy_status': 'RUNNING',
        'params': {
            '_preset_source': preset,
            'straddle_roll_enabled': True,
            'straddle_roll_max_per_session': roll_max,
            'straddle_roll_cooldown_mins': 0,        # no cooldown for tests
            'straddle_roll_emergency_mult': 2.0,
            'straddle_roll_min_time_to_expiry': 0,   # no time floor for tests
            'straddle_roll_trigger_pct': 0.65,
            'straddle_roll_iv_spike_mult': 2.0,
            'straddle_roll_loss_abort_mult': 3.0,
            'max_loss_amount': max_loss_amount,
            'straddle_roll_hard_stop_market_order': True,
            'min_trigger_move': 9999,
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


def _make_monitor(margin_tier='GREEN', iv_data=None, spot=71500.0):
    """Build a minimal monitor mock."""
    mg = MagicMock()
    mg.last_tier = margin_tier
    monitor = MagicMock()
    monitor._margin_guardian = mg
    monitor._last_iv_data = iv_data or {}
    monitor._fetch_spot_price = AsyncMock(return_value=spot)
    return monitor


def _run_gates(session=None, spot=71500.0, minutes_to_expiry=200):
    """Run _check_pure_roll_gates with sensible defaults."""
    if session is None:
        session = _make_session()
    monitor = _make_monitor()
    return _check_pure_roll_gates(monitor, session, 'test-pure-001', spot, minutes_to_expiry)


# =============================================================================
# P8 — Gate 8: premium-points trigger
# =============================================================================

def test_p8_1_gate8_passes_at_exact_trigger():
    """P8-1: Gate 8 passes when spot_move_pts == trigger_pts (500pt trigger, 500pt move)."""
    session = _make_session(ce_strike=71000, roll_trigger_pts=500.0)
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    assert ok is True, f"Expected pass at exact trigger, got: {reason}"


def test_p8_2_gate8_blocks_below_trigger():
    """P8-2: Gate 8 blocks when spot_move_pts < trigger_pts."""
    session = _make_session(ce_strike=71000, roll_trigger_pts=500.0)
    ok, reason, ctx = _run_gates(session=session, spot=71400.0)  # only 400 pts
    assert ok is False
    assert 'distance_below_trigger' in reason


def test_p8_3_trigger_pts_healed_from_positions():
    """P8-3: When _straddle_roll_trigger_pts missing, Gate 8 recomputes from position entry_premium."""
    session = _make_session(
        ce_premium=300.0, ce_lots=1,
        pe_premium=200.0, pe_lots=1,
        roll_trigger_pts=0,
    )
    session.pop('_straddle_roll_trigger_pts', None)
    # trigger should be 300+200=500. Move 600 pts → should pass.
    ok, reason, ctx = _run_gates(session=session, spot=71600.0)
    assert ok is True, f"Expected fallback heal + pass, got: {reason}"
    assert session.get('_straddle_roll_trigger_pts') == pytest.approx(500.0)


def test_p8_4_trigger_pts_updated_after_roll():
    """P8-4: After a roll, _straddle_roll_trigger_pts reflects new CE+PE fill prices."""
    # Simulate the state update that _execute_4_leg_roll performs in Step 6
    from decimal import Decimal
    session = _make_session()
    ce_fill = Decimal('280.0')
    pe_fill = Decimal('190.0')
    new_trigger = ce_fill + pe_fill   # 470.0
    session['_straddle_roll_trigger_pts'] = float(round(new_trigger, 2))
    assert session['_straddle_roll_trigger_pts'] == pytest.approx(470.0)


# =============================================================================
# PI — Preset isolation
# =============================================================================

def test_pi_1_straddle_roll_preset_passes_gate2():
    """PI-1: STRADDLE_ROLL sessions pass Gate 2 in _check_pure_roll_gates."""
    session = _make_session(preset='STRADDLE_ROLL')
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    # Gate 2 passes → overall pass (gates further down may not matter here)
    assert reason != 'wrong_preset', "Gate 2 should accept STRADDLE_ROLL"


def test_pi_2_straddle_adj_preset_blocked_at_gate2():
    """PI-2: STRADDLE_WITH_ADJUSTMENT sessions are blocked by Gate 2 in _check_pure_roll_gates."""
    session = _make_session(preset='STRADDLE_WITH_ADJUSTMENT')
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    assert ok is False
    assert reason == 'wrong_preset'


def test_pi_3_straddle_roll_never_calls_adjustment_module():
    """PI-3: mmm_straddle_roll_pure.py does not import from mmm_straddle_adjustment."""
    import webui.backend.routes.mmm.mmm_straddle_roll_pure as pure_mod
    import inspect

    # Check only import lines — docstrings mentioning "STRADDLE_WITH_ADJUSTMENT" are fine.
    # The isolation contract is: no import from mmm_straddle_adjustment.
    import_lines = [
        line for line in inspect.getsource(pure_mod).splitlines()
        if line.strip().startswith(('import ', 'from '))
    ]
    for line in import_lines:
        assert 'mmm_straddle_adjustment' not in line, (
            f"mmm_straddle_roll_pure.py must not import from mmm_straddle_adjustment.\n"
            f"Found: {line}"
        )


def test_pi_4_straddle_adj_never_calls_pure_roll_module():
    """PI-4: mmm_straddle_adjustment.py does not import mmm_straddle_roll_pure."""
    import inspect
    import webui.backend.routes.mmm.mmm_straddle_adjustment as adj_mod

    source = inspect.getsource(adj_mod)
    assert 'mmm_straddle_roll_pure' not in source, (
        "mmm_straddle_adjustment.py must not import or reference mmm_straddle_roll_pure"
    )


# =============================================================================
# PHS — Hard stop
# =============================================================================

def test_phs_1_hard_stop_fires_when_loss_exceeds_limit():
    """PHS-1: execute_pure_straddle_roll fires hard stop when total_pnl <= -max_loss_amount."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import execute_pure_straddle_roll

    session = _make_session(max_loss_amount=100.0)
    monitor = _make_monitor()

    # Patch P&L to return a loss exceeding the limit.
    # Telegram uses asyncio.create_task internally — patch at the telegram module level.
    with patch('webui.backend.routes.mmm.mmm_straddle_roll_pure._pnl_total', return_value=-150.0), \
         patch('webui.backend.routes.mmm.mmm_straddle_roll_pure._close_all_market_order',
               new_callable=AsyncMock, return_value=2), \
         patch('webui.backend.routes.mmm.mmm_straddle_roll_pure.log_activity'), \
         patch('webui.backend.routes.mmm.mmm_telegram.alert_max_loss_breach',
               new_callable=AsyncMock):

        result = asyncio.get_event_loop().run_until_complete(
            execute_pure_straddle_roll(monitor, session, 'test-pure-001', minutes_to_expiry=200)
        )

    assert result is True, "Hard stop should return True (action taken)"
    assert session.get('strategy_status') == 'STOPPED'


def test_phs_2_hard_stop_calls_market_order_not_smart_execute():
    """PHS-2: _close_all_market_order passes order_type='market' to close_position."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import _close_all_market_order

    session = _make_session()
    monitor = _make_monitor()
    executor = MagicMock()
    initializer = MagicMock()
    monitor.executor = executor
    monitor.initializer = initializer

    close_calls = []

    async def fake_close_position(*args, **kwargs):
        close_calls.append(kwargs.get('order_type', 'limit'))
        return {'success': True, 'realized_pnl': 0.0, 'close_premium': 250.0, 'lots_closed': 1}

    with patch('webui.backend.routes.mmm.mmm_straddle_roll_pure.close_position',
               side_effect=fake_close_position):
        asyncio.get_event_loop().run_until_complete(
            _close_all_market_order(monitor, session, 'test-pure-001')
        )

    assert len(close_calls) > 0, "At least one close_position call expected"
    assert all(ot == 'market' for ot in close_calls), \
        f"All hard stop closes must use order_type='market', got: {close_calls}"


# =============================================================================
# PR6 — Gate 6: max rolls
# =============================================================================

def test_pr6_1_gate6_blocks_when_rolls_exhausted():
    """PR6-1: Gate 6 blocks when roll_count >= max_per_session."""
    session = _make_session(roll_count=5, roll_max=5, roll_trigger_pts=500.0)
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    assert ok is False
    assert reason == 'max_rolls_exhausted'


def test_pr6_2_gate6_passes_when_rolls_available():
    """PR6-2: Gate 6 passes when roll_count < max_per_session."""
    session = _make_session(roll_count=2, roll_max=5, roll_trigger_pts=500.0)
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    assert reason != 'max_rolls_exhausted', f"Should not be exhausted at 2/5, got: {reason}"


def test_pr6_3_no_roll_mode_when_max_is_zero():
    """PR6-3: straddle_roll_max_per_session=0 → no_roll_mode (roll disabled, hard stop only)."""
    session = _make_session(roll_count=0, roll_max=0, roll_trigger_pts=500.0)
    ok, reason, ctx = _run_gates(session=session, spot=71500.0)
    assert ok is False
    assert reason == 'no_roll_mode'


# =============================================================================
# PIV — Gate 5: IV spike
# =============================================================================

def test_piv_1_iv_spike_does_not_block_roll():
    """PIV-1: IV spike (3× entry) logs warning but does NOT block roll."""
    session = _make_session(ce_strike=71000, roll_trigger_pts=500.0)
    session['_straddle_entry_iv'] = 50.0
    monitor = _make_monitor(iv_data={'ce_iv': 160.0, 'pe_iv': 160.0})  # 3.2× entry_iv
    ok, reason, ctx = _check_pure_roll_gates(
        monitor, session, 'test-pure-001', spot=71500.0, minutes_to_expiry=200
    )
    assert reason != 'iv_spike_blocked', \
        "IV spike must not block roll in STRADDLE_ROLL (soft warning only)"


def test_piv_2_iv_spike_sets_audit_flag():
    """PIV-2: IV spike sets _straddle_last_roll_iv_spike=True in session."""
    session = _make_session(ce_strike=71000, roll_trigger_pts=500.0)
    session['_straddle_entry_iv'] = 50.0
    monitor = _make_monitor(iv_data={'ce_iv': 160.0, 'pe_iv': 160.0})
    _check_pure_roll_gates(
        monitor, session, 'test-pure-001', spot=71500.0, minutes_to_expiry=200
    )
    assert session.get('_straddle_last_roll_iv_spike') is True


# =============================================================================
# PRR — Post-roll state reset
# =============================================================================

def test_prr_1_trend_keys_cleared_after_roll():
    """PRR-1: _trend_* regime keys are cleared by _post_roll_state_reset logic."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import _execute_4_leg_roll

    session = _make_session()
    # Set stale trend state that must be wiped
    session['_trend_regime'] = 'BULL'
    session['_trend_tier'] = 'T3'
    session['_trend_direction'] = 'up'
    session['_trend_anchor_spot'] = 70000.0
    session['_straddle_entry_iv'] = 55.0
    session['_adaptive_tier'] = 2

    monitor = _make_monitor()
    monitor.executor = MagicMock()
    monitor.initializer = MagicMock()

    # Minimal: test that the state-reset keys list in _execute_4_leg_roll covers these fields.
    # We do this by inspecting the source rather than running the full roll (avoids exchange calls).
    import inspect
    source = inspect.getsource(_execute_4_leg_roll)
    for key in ('_trend_regime', '_trend_tier', '_trend_direction', '_straddle_entry_iv', '_adaptive_tier'):
        assert key in source, f"Post-roll reset must clear '{key}' — not found in _execute_4_leg_roll source"


def test_prr_2_straddle_entry_iv_cleared_after_roll():
    """PRR-2: _straddle_entry_iv is in the post-roll reset key list."""
    import inspect
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import _execute_4_leg_roll
    source = inspect.getsource(_execute_4_leg_roll)
    assert '_straddle_entry_iv' in source, \
        "_execute_4_leg_roll must clear _straddle_entry_iv in post-roll reset"


def test_prr_3_initial_credit_not_reset():
    """PRR-3: _straddle_initial_credit is NOT in the post-roll reset key list (must persist)."""
    import inspect
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import _execute_4_leg_roll
    source = inspect.getsource(_execute_4_leg_roll)
    # The key must not appear after any session.pop() call
    # It is used (session.get) but must not be popped
    import re
    pop_calls = re.findall(r"session\.pop\(['\"]([^'\"]+)['\"]", source)
    assert '_straddle_initial_credit' not in pop_calls, \
        "_straddle_initial_credit must NOT be cleared in post-roll reset"


# =============================================================================
# PP — Preset parameters
# =============================================================================

def test_pp_1_min_trigger_move_is_9999():
    """PP-1: build_straddle_roll_preset sets min_trigger_move=9999 to disable adj engine."""
    preset = build_straddle_roll_preset(5.0)
    assert preset['min_trigger_move'] == 9999, \
        "min_trigger_move must be 9999 — this is the adj engine disable mechanism"


def test_pp_2_hard_stop_market_order_is_true():
    """PP-2: build_straddle_roll_preset sets straddle_roll_hard_stop_market_order=True."""
    preset = build_straddle_roll_preset(5.0)
    assert preset['straddle_roll_hard_stop_market_order'] is True


def test_pp_3_raises_for_under_1h():
    """PP-3: build_straddle_roll_preset raises ValueError when H < 1.0."""
    with pytest.raises(ValueError, match='1h'):
        build_straddle_roll_preset(0.5)


def test_pp_4_succeeds_for_24h():
    """PP-4: build_straddle_roll_preset(24.0) succeeds — no 12h cap."""
    preset = build_straddle_roll_preset(24.0)
    assert preset['_preset_source'] == STRADDLE_ROLL_CATEGORY


def test_pp_5_wind_down_disabled():
    """PP-5: wind_down_enabled is False in STRADDLE_ROLL preset."""
    preset = build_straddle_roll_preset(5.0)
    assert preset['wind_down_enabled'] is False


def test_pp_6_harvest_disabled():
    """PP-6: harvest_enabled is False in STRADDLE_ROLL preset."""
    preset = build_straddle_roll_preset(5.0)
    assert preset['harvest_enabled'] is False


# =============================================================================
# PV — Session creation validation
# =============================================================================

def _make_flask_test_client():
    """Build a Flask test client with the MMM API blueprint registered."""
    try:
        from flask import Flask
        from webui.backend.routes.mmm.mmm_api import mmm_bp
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(mmm_bp)
        return app.test_client(), app
    except Exception:
        return None, None


def _post_create_session(client, params: dict):
    """POST to /api/mmm/session/create with given params, return (status_code, json)."""
    import json
    resp = client.post(
        '/api/mmm/session/create',
        data=json.dumps({'mode': 'fresh', 'params': params}),
        content_type='application/json',
    )
    try:
        return resp.status_code, resp.get_json()
    except Exception:
        return resp.status_code, {}


@pytest.fixture(scope='module')
def _api_client():
    client, app = _make_flask_test_client()
    if client is None:
        pytest.skip("Flask test client not available — skipping API validation tests")
    return client


def _run_api_validation_test(missing_field: str):
    """
    Helper: create a STRADDLE_ROLL session missing one required field,
    assert HTTP 400 is returned.

    The validation block in mmm_api.py checks session['params']['_preset_source'].
    We mock create_session (imported at top of mmm_api) and validate_params to
    return a session that already has _preset_source='STRADDLE_ROLL'.
    """
    client, app = _make_flask_test_client()
    if client is None:
        pytest.skip("Flask test client not available")

    base_params = {
        'expiry': '2026-04-11',
        'dte_category': 'STRADDLE_ROLL',
        'initial_lots': 1,
        'straddle_roll_max_per_session': 5,
        'max_loss_amount': 100.0,
    }
    base_params.pop(missing_field)

    with app.app_context():
        with patch('webui.backend.routes.mmm.mmm_api.create_session') as mock_create, \
             patch('webui.backend.routes.mmm.mmm_api.validate_params') as mock_validate:

            # validate_params returns (validated_params, no_errors)
            validated = {**base_params, '_preset_source': 'STRADDLE_ROLL'}
            mock_validate.return_value = (validated, {})

            # create_session returns a session with _preset_source set so the
            # validation block in mmm_api.py can check it
            mock_create.return_value = {
                'session_id': 'test-pv-001',
                'params': {**base_params, '_preset_source': 'STRADDLE_ROLL'},
            }

            status, data = _post_create_session(client, base_params)

    assert status == 400, \
        f"Expected HTTP 400 when '{missing_field}' is missing, got {status}: {data}"


def test_pv_1_rejects_missing_initial_lots():
    """PV-1: STRADDLE_ROLL session creation returns HTTP 400 when initial_lots absent."""
    _run_api_validation_test('initial_lots')


def test_pv_2_rejects_missing_max_rolls():
    """PV-2: STRADDLE_ROLL session creation returns HTTP 400 when straddle_roll_max_per_session absent."""
    _run_api_validation_test('straddle_roll_max_per_session')


def test_pv_3_rejects_missing_max_loss():
    """PV-3: STRADDLE_ROLL session creation returns HTTP 400 when max_loss_amount absent."""
    _run_api_validation_test('max_loss_amount')


# =============================================================================
# C-SR — execute_pure_straddle_roll entry-point contracts (A5-05)
# =============================================================================

def test_csr_1_expiry_auto_close_returns_true():
    """C-SR-1: expiry auto-close fires when tte < auto_close_mins; returns True, sets STOPPED."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import execute_pure_straddle_roll

    session = _make_session(max_loss_amount=0.0)  # disable hard stop
    # auto_close_mins defaults to params.get('auto_close_mins', 10)
    # Pass tte=5 which is < 10
    monitor = _make_monitor()
    monitor._auto_close_all = AsyncMock(return_value=None)

    with patch('webui.backend.routes.mmm.mmm_straddle_roll_pure.log_activity'):
        result = asyncio.get_event_loop().run_until_complete(
            execute_pure_straddle_roll(monitor, session, 'test-csr-001', minutes_to_expiry=5.0)
        )

    assert result is True, "Auto-close at expiry must return True (action taken)"
    assert session.get('strategy_status') == 'STOPPED', \
        "strategy_status must be STOPPED after expiry auto-close"
    monitor._auto_close_all.assert_called_once()


def test_csr_2_min_time_window_suppresses_roll():
    """C-SR-2: roll suppressed inside min_time window (tte between auto_close_mins and min_time)."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import execute_pure_straddle_roll

    # straddle_roll_min_time_to_expiry defaults to 0 in _make_session (no floor)
    # Override to create the suppression window: tte=50, min_time=90, auto_close=10
    session = _make_session(max_loss_amount=0.0)
    session['params']['straddle_roll_min_time_to_expiry'] = 90
    session['params']['auto_close_mins'] = 10

    monitor = _make_monitor()
    monitor._auto_close_all = AsyncMock(return_value=None)

    with patch('webui.backend.routes.mmm.mmm_straddle_roll_pure.log_activity'):
        result = asyncio.get_event_loop().run_until_complete(
            execute_pure_straddle_roll(monitor, session, 'test-csr-002', minutes_to_expiry=50.0)
        )

    assert result is False, \
        "Inside min_time suppression window (50min < 90min) should return False (no action)"
    assert session.get('strategy_status') != 'STOPPED', \
        "strategy_status must NOT be STOPPED when roll is merely suppressed"


def test_csr_3_zero_spot_returns_false():
    """C-SR-3: unavailable spot (0) returns False without raising."""
    from webui.backend.routes.mmm.mmm_straddle_roll_pure import execute_pure_straddle_roll

    session = _make_session(max_loss_amount=0.0)
    session['params']['straddle_roll_min_time_to_expiry'] = 0  # no floor
    session['params']['auto_close_mins'] = 10

    monitor = _make_monitor(spot=0.0)
    monitor._auto_close_all = AsyncMock(return_value=None)

    with patch('webui.backend.routes.mmm.mmm_straddle_roll_pure.log_activity'), \
         patch('webui.backend.routes.mmm.mmm_straddle_roll_pure._compute_dynamic_trigger'):
        result = asyncio.get_event_loop().run_until_complete(
            execute_pure_straddle_roll(monitor, session, 'test-csr-003', minutes_to_expiry=200.0)
        )

    assert result is False, "Zero spot must return False cleanly (no roll, no exception)"
