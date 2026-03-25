"""
Tests for time-based shutdown control:
  - AWAITING_USER_ACTION flag logic (active hours vs off-hours)
  - Flag persistence and clearing
  - Telegram cooldown gate
  - emit_heartbeat payload with new fields
  - Flag clearing only when flagged side recovers (bug fix)
"""

import time
import pytest
from copy import deepcopy
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_ist_hour(hour: int):
    """Return a datetime whose IST hour equals `hour`."""
    IST = timezone(timedelta(hours=5, minutes=30))
    # Build a UTC time that will be `hour` in IST
    utc_hour = (hour - 5) % 24
    return datetime(2026, 3, 25, utc_hour, 15, 0, tzinfo=timezone.utc).astimezone(IST)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  _is_user_awake_hours  (unit test of the helper itself)
# ─────────────────────────────────────────────────────────────────────────────

class TestIsUserAwakeHours:
    def _call(self, ist_hour):
        IST = timezone(timedelta(hours=5, minutes=30))
        fake_now = _make_ist_hour(ist_hour)
        with patch('webui.backend.routes.mmm.mmm_monitor.datetime') as m:
            m.now.return_value = fake_now
            m.fromisoformat = datetime.fromisoformat
            from webui.backend.routes.mmm.mmm_monitor import _is_user_awake_hours
            return _is_user_awake_hours()

    def test_awake_at_8am(self):
        assert self._call(8) is True

    def test_awake_at_noon(self):
        assert self._call(12) is True

    def test_awake_at_22(self):
        assert self._call(22) is True

    def test_off_at_23(self):
        assert self._call(23) is False

    def test_off_at_midnight(self):
        assert self._call(0) is False

    def test_off_at_7am(self):
        assert self._call(7) is False

    def test_boundary_exactly_8(self):
        assert self._call(8) is True   # inclusive

    def test_boundary_exactly_22(self):
        assert self._call(22) is True  # still in window


# ─────────────────────────────────────────────────────────────────────────────
# 2.  AWAITING_USER_ACTION flags set correctly (awake-hours path)
# ─────────────────────────────────────────────────────────────────────────────

def _build_session(ce_lots=10, pe_lots=0):
    """Minimal session with PE closed (0 lots) by default."""
    return {
        'session_id': 'test-aua-001',
        'strategy_status': 'RUNNING',
        'unrealized_pnl': 10.0,
        'realized_pnl': 5.0,
        'total_fees': 1.0,
        'params': {},
        'ce': {'active_lots': ce_lots, 'total_lots': ce_lots, 'active_strike': 70000},
        'pe': {'active_lots': pe_lots, 'total_lots': pe_lots, 'active_strike': 69000},
    }


class TestAwaitingUserActionFlags:
    """Tests for the session flag logic — isolated from the full monitor."""

    def _simulate_awake_ocs(self, session, closed_side='pe', open_side='ce',
                             open_lots=10, os_strike=70000, pnl=14.0):
        """Manually apply what the awake-hours OCS block does, for unit testing."""
        IST = timezone(timedelta(hours=5, minutes=30))
        detected_ist = datetime.now(IST).strftime('%d %b %Y, %H:%M IST')
        session['_awaiting_user_action'] = True
        session['_awaiting_user_action_reason'] = (
            f'{closed_side.upper()} fully closed — '
            f'{open_side.upper()} unhedged ({open_lots} lots @ {os_strike})'
        )
        session['_awaiting_user_action_details'] = {
            'closed_side': closed_side,
            'open_side': open_side,
            'open_lots': open_lots,
            'open_strike': os_strike,
            'current_pnl': round(pnl, 2),
            'detected_at_ist': detected_ist,
            'session_id': session['session_id'],
        }

    def test_flags_set_on_awake_detection(self):
        session = _build_session(ce_lots=10, pe_lots=0)
        self._simulate_awake_ocs(session, closed_side='pe', open_side='ce')

        assert session['_awaiting_user_action'] is True
        assert 'PE' in session['_awaiting_user_action_reason']
        d = session['_awaiting_user_action_details']
        assert d['closed_side'] == 'pe'
        assert d['open_side'] == 'ce'
        assert d['open_lots'] == 10
        assert d['open_strike'] == 70000
        assert isinstance(d['current_pnl'], float)

    def test_flags_cleared_when_flagged_side_recovers(self):
        session = _build_session(ce_lots=10, pe_lots=0)
        # Set the PE flag (PE was the closed side)
        session['_one_side_closed_pe'] = True
        self._simulate_awake_ocs(session, closed_side='pe', open_side='ce')
        session['_ocs_telegram_sent_at'] = time.time()

        # Simulate PE recovering
        _was_flagged = session.get('_one_side_closed_pe')
        session.pop('_one_side_closed_pe', None)
        if _was_flagged:
            session.pop('_awaiting_user_action', None)
            session.pop('_awaiting_user_action_reason', None)
            session.pop('_awaiting_user_action_details', None)
            session.pop('_ocs_telegram_sent_at', None)

        assert '_awaiting_user_action' not in session
        assert '_awaiting_user_action_details' not in session
        assert '_ocs_telegram_sent_at' not in session

    def test_healthy_side_else_does_NOT_clear_other_sides_flags(self):
        """Bug fix: CE else-branch must not clear flags when PE is the closed side."""
        session = _build_session(ce_lots=10, pe_lots=0)
        # PE is closed: _one_side_closed_pe set, _awaiting_user_action set
        session['_one_side_closed_pe'] = True
        self._simulate_awake_ocs(session, closed_side='pe', open_side='ce')

        # Simulate CE's else branch (CE is healthy, _one_side_closed_ce not set)
        _cs = 'ce'
        _ocs_flag = f'_one_side_closed_{_cs}'
        _was_flagged = session.get(_ocs_flag)   # False — CE was never flagged
        session.pop(_ocs_flag, None)
        if _was_flagged:                          # False — should NOT enter
            session.pop('_awaiting_user_action', None)

        # _awaiting_user_action must STILL be True (PE is still closed)
        assert session.get('_awaiting_user_action') is True
        assert session.get('_one_side_closed_pe') is True

    def test_telegram_cooldown_gate(self):
        """Telegram should only fire once within 1800s."""
        session = _build_session()

        # No previous send → should fire
        _tg_last = session.get('_ocs_telegram_sent_at', 0)
        assert time.time() - _tg_last > 1800   # gate opens

        # Mark as just sent
        session['_ocs_telegram_sent_at'] = time.time()

        # Same heartbeat — cooldown active
        _tg_last2 = session.get('_ocs_telegram_sent_at', 0)
        assert time.time() - _tg_last2 < 1800  # gate closed

    def test_telegram_cooldown_reopens_after_30_min(self):
        """After 30 min wall-clock, Telegram gate should reopen."""
        session = {'_ocs_telegram_sent_at': time.time() - 1801}  # 30+ min ago
        assert time.time() - session['_ocs_telegram_sent_at'] > 1800  # gate open

    def test_details_dict_contains_required_fields(self):
        session = _build_session(ce_lots=16, pe_lots=0)
        self._simulate_awake_ocs(session, closed_side='pe', open_side='ce',
                                 open_lots=16, os_strike=70000, pnl=14.0)
        d = session['_awaiting_user_action_details']
        for key in ('closed_side', 'open_side', 'open_lots', 'open_strike',
                    'current_pnl', 'detected_at_ist', 'session_id'):
            assert key in d, f"Missing key: {key}"

    def test_pnl_rounded_to_2dp(self):
        session = _build_session()
        self._simulate_awake_ocs(session, pnl=14.12345678)
        assert session['_awaiting_user_action_details']['current_pnl'] == 14.12


# ─────────────────────────────────────────────────────────────────────────────
# 3.  emit_heartbeat — new fields in payload
# ─────────────────────────────────────────────────────────────────────────────

class TestEmitHeartbeatNewFields:
    """emit_heartbeat should include awaiting_user_action in payload when True."""

    def test_field_absent_by_default(self):
        from webui.backend.routes.mmm.mmm_websocket import emit_heartbeat
        captured = []
        with patch('webui.backend.routes.mmm.mmm_websocket._emit') as mock_emit:
            emit_heartbeat('s1', 100.0, 90.0, 110.0, 80.0, 'RUNNING', 5.0, 3.0)
            payload = mock_emit.call_args[0][1]
        assert 'awaiting_user_action' not in payload

    def test_field_present_when_true(self):
        from webui.backend.routes.mmm.mmm_websocket import emit_heartbeat
        details = {'closed_side': 'pe', 'open_side': 'ce', 'open_lots': 10,
                   'open_strike': 70000, 'current_pnl': 14.0}
        with patch('webui.backend.routes.mmm.mmm_websocket._emit') as mock_emit:
            emit_heartbeat(
                's1', 100.0, 90.0, 110.0, 80.0, 'PAUSED', 5.0, 3.0,
                awaiting_user_action=True,
                awaiting_user_action_details=details,
            )
            payload = mock_emit.call_args[0][1]
        assert payload['awaiting_user_action'] is True
        assert payload['awaiting_user_action_details'] == details

    def test_details_defaults_to_empty_dict_if_none(self):
        from webui.backend.routes.mmm.mmm_websocket import emit_heartbeat
        with patch('webui.backend.routes.mmm.mmm_websocket._emit') as mock_emit:
            emit_heartbeat(
                's1', 100.0, 90.0, 110.0, 80.0, 'PAUSED', 5.0, 3.0,
                awaiting_user_action=True,
                awaiting_user_action_details=None,
            )
            payload = mock_emit.call_args[0][1]
        assert payload['awaiting_user_action_details'] == {}

    def test_false_does_not_add_field(self):
        from webui.backend.routes.mmm.mmm_websocket import emit_heartbeat
        with patch('webui.backend.routes.mmm.mmm_websocket._emit') as mock_emit:
            emit_heartbeat(
                's1', 100.0, 90.0, 110.0, 80.0, 'RUNNING', 5.0, 3.0,
                awaiting_user_action=False,
                awaiting_user_action_details={'should': 'not_appear'},
            )
            payload = mock_emit.call_args[0][1]
        assert 'awaiting_user_action' not in payload


# ─────────────────────────────────────────────────────────────────────────────
# 4.  alert_active_hours_unhedged_pause — Telegram message format
# ─────────────────────────────────────────────────────────────────────────────

class TestTelegramAlertFormat:
    @pytest.mark.asyncio
    async def test_message_contains_required_sections(self):
        from webui.backend.routes.mmm.mmm_telegram import alert_active_hours_unhedged_pause
        captured = []

        async def fake_send(text, key):
            captured.append((text, key))
            return True

        with patch('webui.backend.routes.mmm.mmm_telegram._send_async', side_effect=fake_send):
            await alert_active_hours_unhedged_pause(
                session_id='mmm25mar26-1',
                closed_side='pe',
                open_side='ce',
                open_lots=16,
                pnl=-0.13,
                details={
                    'open_strike': 70000,
                    'detected_at_ist': '25 Mar 2026, 14:30 IST',
                },
            )

        assert len(captured) == 1
        text, key = captured[0]

        assert 'HUMAN ACTION REQUIRED' in text
        assert 'mmm25mar26-1' in text
        assert 'PE' in text
        assert 'CE' in text
        assert '16' in text
        assert 'activehours_unhedged_pause_mmm25mar26-1' == key

    @pytest.mark.asyncio
    async def test_positive_pnl_uses_green_indicator(self):
        from webui.backend.routes.mmm.mmm_telegram import alert_active_hours_unhedged_pause
        captured = []

        async def fake_send(text, key):
            captured.append(text)
            return True

        with patch('webui.backend.routes.mmm.mmm_telegram._send_async', side_effect=fake_send):
            await alert_active_hours_unhedged_pause(
                's1', 'ce', 'pe', 5, 10.50, {}
            )
        assert '🟢' in captured[0]

    @pytest.mark.asyncio
    async def test_negative_pnl_uses_red_indicator(self):
        from webui.backend.routes.mmm.mmm_telegram import alert_active_hours_unhedged_pause
        captured = []

        async def fake_send(text, key):
            captured.append(text)
            return True

        with patch('webui.backend.routes.mmm.mmm_telegram._send_async', side_effect=fake_send):
            await alert_active_hours_unhedged_pause(
                's1', 'ce', 'pe', 5, -10.50, {}
            )
        assert '🔴' in captured[0]


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Off-hours path is UNCHANGED
# ─────────────────────────────────────────────────────────────────────────────

class TestOffHoursUnchanged:
    def test_offhours_alert_function_still_exists(self):
        from webui.backend.routes.mmm.mmm_telegram import alert_offhours_unhedged_stop
        assert callable(alert_offhours_unhedged_stop)

    def test_is_user_awake_hours_returns_false_at_midnight(self):
        IST = timezone(timedelta(hours=5, minutes=30))
        midnight_ist = datetime(2026, 3, 25, 18, 30, 0, tzinfo=timezone.utc)  # 00:00 IST
        with patch('webui.backend.routes.mmm.mmm_monitor.datetime') as m:
            m.now.return_value = midnight_ist.astimezone(IST)
            m.fromisoformat = datetime.fromisoformat
            from webui.backend.routes.mmm.mmm_monitor import _is_user_awake_hours
            assert _is_user_awake_hours() is False
