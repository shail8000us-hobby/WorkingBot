"""
MMMX Phase 9 Unit Tests — Fault Tolerance (Watchdog, Reconciliation, Restart)

Covers:
  - Watchdog: dead monitor for RUNNING session → tick() restarts via start_session_monitor()
  - Watchdog: dead listener for RUNNING session → tick() restarts listener
  - Watchdog: PAUSED session with dead monitor → NOT restarted
  - Watchdog: Telegram dedup TTL respected
  - Watchdog: get_watchdog() returns singleton
  - Startup landing: RUNNING session → on_startup() → status=PAUSED, Telegram sent
  - Startup landing: PAUSED session → on_startup() → NOT re-transitioned
  - _being_closed: entry older than TTL → cleared on startup
  - _being_closed: entry within TTL → preserved
  - Reconciliation confirmation: accept_db → divergence resolved (audit logged)
  - Reconciliation confirmation: accept_exchange → DB tranche leg closed
  - Reconciliation confirmation: manual_close → added to _naked_positions
  - Reconciliation confirmation: unknown action → ValueError
  - POST /confirm-reconcile: 200 on valid; 404 on unknown session; 422 on bad action
  - GET /health: includes watchdog_alive and last_watchdog_tick

All 428 prior tests must still pass.
"""

import os
import sys
import time
import threading
import pytest
from unittest.mock import MagicMock, patch, call

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_PKG = 'webui.backend.routes.mmmx'


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_session(status='RUNNING', session_id='test-p9-session-001'):
    return {
        'session_id': session_id,
        'status': status,
        'params': {
            'hard_stop_multiplier': 2.0,
            'close_at_dte': 7,
            'entry_dte_min': 20,
        },
        'tranches': [],
        'hard_stop_usd': 1000.0,
        'total_premium_collected': 0.0,
        '_being_closed': {},
        '_naked_positions': [],
    }


def _mock_storage(session=None):
    s = MagicMock()
    s.load_session.return_value = session
    s.get_generation.return_value = 5
    s.save_session.return_value = True
    return s


def _make_app():
    from flask import Flask
    from webui.backend.routes.mmmx.mmmx_api import mmmx_bp
    app = Flask(__name__)
    app.register_blueprint(mmmx_bp)
    app.config['TESTING'] = True
    return app


# ══════════════════════════════════════════════════════════════════════════════
# Watchdog: core behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestWatchdogTick:

    def _make_dead_monitor(self):
        """Monitor with is_alive() == False."""
        m = MagicMock()
        m.is_alive.return_value = False
        return m

    def _make_alive_monitor(self):
        m = MagicMock()
        m.is_alive.return_value = True
        return m

    def test_dead_monitor_running_session_restarts(self):
        """tick() detects dead monitor for RUNNING session → calls start_session_monitor."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        session = _make_session(status='RUNNING')
        mock_storage = _mock_storage(session)
        dead_monitor = self._make_dead_monitor()

        new_monitor = MagicMock()
        new_monitor._my_generation = 6

        with patch(f'{_PKG}.mmmx_watchdog.get_watchdog'), \
             patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={'sid': dead_monitor}), \
             patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.start_session_monitor', return_value=new_monitor) as mock_start, \
             patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=self._make_alive_monitor()), \
             patch(f'{_PKG}.mmmx_watchdog.MMMXWatchdog._send_restart_alert'):

            wd = MMMXWatchdog()
            wd.tick()

        mock_start.assert_called_once_with('sid')

    def test_dead_monitor_paused_session_not_restarted(self):
        """Watchdog must NOT restart monitors for PAUSED sessions."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        session = _make_session(status='PAUSED')
        mock_storage = _mock_storage(session)
        dead_monitor = self._make_dead_monitor()

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={'sid': dead_monitor}), \
             patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.start_session_monitor') as mock_start:

            wd = MMMXWatchdog()
            wd.tick()

        mock_start.assert_not_called()

    def test_dead_monitor_complete_session_not_restarted(self):
        """Watchdog must NOT restart monitors for COMPLETE sessions."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        session = _make_session(status='COMPLETE')
        mock_storage = _mock_storage(session)
        dead_monitor = self._make_dead_monitor()

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={'sid': dead_monitor}), \
             patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.start_session_monitor') as mock_start:

            wd = MMMXWatchdog()
            wd.tick()

        mock_start.assert_not_called()

    def test_dead_listener_running_session_restarts(self):
        """tick() detects dead listener for RUNNING session → calls start_session_listener."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        session = _make_session(status='RUNNING')
        mock_storage = _mock_storage(session)
        alive_monitor = self._make_alive_monitor()
        dead_listener = MagicMock()
        dead_listener.is_alive.return_value = False

        new_listener = MagicMock()

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={'sid': alive_monitor}), \
             patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=dead_listener), \
             patch(f'{_PKG}.mmmx_premium_listener.start_session_listener', return_value=new_listener) as mock_start_l, \
             patch(f'{_PKG}.mmmx_executor.get_executor', return_value=MagicMock()), \
             patch(f'{_PKG}.mmmx_watchdog.MMMXWatchdog._send_restart_alert'):

            wd = MMMXWatchdog()
            wd.tick()

        # Verify listener was restarted with correct session_id and generation
        assert mock_start_l.called
        call_kwargs = mock_start_l.call_args[1]
        assert call_kwargs['session_id'] == 'sid'
        assert call_kwargs['my_generation'] == mock_storage.get_generation.return_value

    def test_none_listener_running_session_restarts(self):
        """tick() detects None listener for RUNNING session → restarts listener."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        session = _make_session(status='RUNNING')
        mock_storage = _mock_storage(session)
        alive_monitor = self._make_alive_monitor()

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={'sid': alive_monitor}), \
             patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=None), \
             patch(f'{_PKG}.mmmx_premium_listener.start_session_listener') as mock_start_l, \
             patch(f'{_PKG}.mmmx_executor.get_executor', return_value=MagicMock()), \
             patch(f'{_PKG}.mmmx_watchdog.MMMXWatchdog._send_restart_alert'):

            wd = MMMXWatchdog()
            wd.tick()

        assert mock_start_l.called

    def test_tick_updates_last_tick_at(self):
        """tick() updates last_tick_at timestamp."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={}):
            wd = MMMXWatchdog()
            assert wd.last_tick_at is None
            wd.tick()
            assert wd.last_tick_at is not None

    def test_empty_monitors_no_crash(self):
        """tick() with no registered monitors runs cleanly."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={}):
            wd = MMMXWatchdog()
            wd.tick()  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# Watchdog: Telegram dedup
# ══════════════════════════════════════════════════════════════════════════════

class TestWatchdogTelegramDedup:

    def test_first_alert_sends(self):
        """First restart alert for a session is sent."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        mock_send = MagicMock()
        with patch(f'{_PKG}.mmmx_telegram.send_alert', mock_send):
            wd = MMMXWatchdog()
            wd._send_restart_alert('test-session-aaa', 'monitor')
        mock_send.assert_called_once()

    def test_second_alert_within_ttl_suppressed(self):
        """Second alert within dedup TTL is suppressed."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        mock_send = MagicMock()
        with patch(f'{_PKG}.mmmx_telegram.send_alert', mock_send):
            wd = MMMXWatchdog()
            wd._send_restart_alert('test-session-bbb', 'monitor')
            wd._send_restart_alert('test-session-bbb', 'monitor')  # should be suppressed

        assert mock_send.call_count == 1

    def test_alert_after_ttl_expired_sends(self):
        """Alert after dedup TTL has expired is sent again."""
        from webui.backend.routes.mmmx.mmmx_watchdog import MMMXWatchdog

        mock_send = MagicMock()
        with patch(f'{_PKG}.mmmx_telegram.send_alert', mock_send):
            wd = MMMXWatchdog()
            wd._alert_dedup_ttl = 1  # 1 second TTL for test
            wd._send_restart_alert('test-session-ccc', 'monitor')
            time.sleep(1.1)
            wd._send_restart_alert('test-session-ccc', 'monitor')

        assert mock_send.call_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# Watchdog: singleton
# ══════════════════════════════════════════════════════════════════════════════

class TestWatchdogSingleton:

    def test_get_watchdog_returns_same_instance(self):
        """get_watchdog() always returns the same singleton."""
        # Reset singleton for test isolation
        import webui.backend.routes.mmmx.mmmx_watchdog as _wd_module
        _wd_module._watchdog_instance = None

        from webui.backend.routes.mmmx.mmmx_watchdog import get_watchdog
        a = get_watchdog()
        b = get_watchdog()
        assert a is b

    def test_get_watchdog_creates_mmmx_watchdog(self):
        """get_watchdog() returns an MMMXWatchdog instance."""
        import webui.backend.routes.mmmx.mmmx_watchdog as _wd_module
        _wd_module._watchdog_instance = None

        from webui.backend.routes.mmmx.mmmx_watchdog import get_watchdog, MMMXWatchdog
        wd = get_watchdog()
        assert isinstance(wd, MMMXWatchdog)


# ══════════════════════════════════════════════════════════════════════════════
# Startup landing
# ══════════════════════════════════════════════════════════════════════════════

class TestStartupLanding:

    def test_running_session_landed_paused(self):
        """RUNNING session is transitioned to PAUSED on startup."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        session = _make_session(status='RUNNING', session_id='startup-test-001')
        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()), \
             patch(f'{_PKG}.init_mmmx._send_startup_telegram') as mock_tg:

            on_startup()

        assert session['status'] == 'PAUSED'
        mock_tg.assert_called_once_with('startup-test-001')

    def test_paused_session_not_retransitioned(self):
        """PAUSED session stays PAUSED — not double-transitioned."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        session = _make_session(status='PAUSED', session_id='startup-test-002')
        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()), \
             patch(f'{_PKG}.init_mmmx._send_startup_telegram') as mock_tg:

            on_startup()

        # transition_status raises ValueError for PAUSED→PAUSED so it is caught;
        # session remains PAUSED
        assert session['status'] == 'PAUSED'
        mock_tg.assert_not_called()

    def test_watchdog_started_on_startup(self):
        """on_startup() starts the global watchdog."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        mock_storage = _mock_storage()
        mock_storage.list_sessions.return_value = []
        mock_watchdog = MagicMock()

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=mock_watchdog):

            on_startup()

        mock_watchdog.start.assert_called_once()

    def test_telegram_sent_for_landed_session(self):
        """on_startup() sends Telegram when a RUNNING session is landed."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup, _send_startup_telegram

        session = _make_session(status='RUNNING', session_id='startup-tg-003')
        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        sent = []

        def fake_send(session_id):
            sent.append(session_id)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()), \
             patch(f'{_PKG}.init_mmmx._send_startup_telegram', side_effect=fake_send):

            on_startup()

        assert 'startup-tg-003' in sent


# ══════════════════════════════════════════════════════════════════════════════
# _being_closed TTL cleanup
# ══════════════════════════════════════════════════════════════════════════════

class TestBeingClosedCleanup:

    def test_expired_entry_cleared(self):
        """_being_closed entry older than TTL is cleared on startup."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        old_ts = time.time() - 400  # older than BEING_CLOSED_TTL_SECS (180)
        session = _make_session(status='PAUSED', session_id='bc-test-001')
        session['_being_closed'] = {'tr1': old_ts}

        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()):

            on_startup()

        assert 'tr1' not in session['_being_closed']

    def test_fresh_entry_preserved(self):
        """_being_closed entry within TTL is preserved on startup."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        fresh_ts = time.time() - 30  # well within 180s TTL
        session = _make_session(status='PAUSED', session_id='bc-test-002')
        session['_being_closed'] = {'tr2': fresh_ts}

        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()):

            on_startup()

        assert 'tr2' in session['_being_closed']

    def test_empty_being_closed_no_crash(self):
        """Session with no _being_closed dict does not crash on_startup."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        session = _make_session(status='PAUSED', session_id='bc-test-003')
        session.pop('_being_closed', None)

        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()):

            on_startup()  # must not raise

    def test_mixed_entries_selective_cleanup(self):
        """Expired entries removed, fresh entries kept."""
        from webui.backend.routes.mmmx.init_mmmx import on_startup

        old_ts   = time.time() - 400
        fresh_ts = time.time() - 30
        session  = _make_session(status='PAUSED', session_id='bc-test-004')
        session['_being_closed'] = {'old_tr': old_ts, 'fresh_tr': fresh_ts}

        mock_storage = _mock_storage(session)
        mock_storage.list_sessions.return_value = [session]

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=MagicMock()):

            on_startup()

        assert 'old_tr' not in session['_being_closed']
        assert 'fresh_tr' in session['_being_closed']


# ══════════════════════════════════════════════════════════════════════════════
# Reconciliation confirmation
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyReconConfirmation:

    def _make_session_with_tranche(self):
        """Session with one ACTIVE tranche."""
        s = _make_session(status='RUNNING', session_id='recon-test-001')
        s['tranches'] = [{
            'tranche_id': 1,
            'ce': {'symbol': 'BTC-CALL-50000', 'status': 'ACTIVE', 'lots': 10},
            'pe': {'symbol': 'BTC-PUT-45000',  'status': 'ACTIVE', 'lots': 10},
        }]
        return s

    def test_accept_db_logs_audit(self):
        """accept_db calls _audit_event and does not mutate session state."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {'divergence_id': 'BTC-CALL-50000:1:ce', 'action': 'accept_db', 'notes': ''}

        with patch(f'{_PKG}.mmmx_reconciler._audit_event') as mock_audit:
            apply_recon_confirmation(session, decision)

        mock_audit.assert_called_once()
        args = mock_audit.call_args[0]
        assert args[1] == 'RECON_ACCEPT_DB'
        # CE should still be ACTIVE — accept_db doesn't close it
        assert session['tranches'][0]['ce']['status'] == 'ACTIVE'

    def test_accept_exchange_closes_db_leg(self):
        """accept_exchange forces DB tranche leg to CLOSED."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {
            'divergence_id': 'BTC-CALL-50000:1:ce',
            'action': 'accept_exchange',
            'notes': 'confirmed missing on exchange',
        }

        with patch(f'{_PKG}.mmmx_reconciler._audit_event'):
            apply_recon_confirmation(session, decision)

        ce = session['tranches'][0]['ce']
        assert ce['status'] == 'CLOSED'
        assert ce.get('close_reason') == 'recon_accept_exchange'
        assert 'closed_at' in ce

    def test_accept_exchange_by_symbol_only(self):
        """accept_exchange works when only symbol is provided (no tranche_id)."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {
            'divergence_id': 'BTC-PUT-45000',  # symbol only
            'action': 'accept_exchange',
            'notes': '',
        }

        with patch(f'{_PKG}.mmmx_reconciler._audit_event'):
            apply_recon_confirmation(session, decision)

        # PE has the matching symbol
        pe = session['tranches'][0]['pe']
        assert pe['status'] == 'CLOSED'

    def test_manual_close_adds_to_naked_positions(self):
        """manual_close adds the divergence to session._naked_positions."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {
            'divergence_id': 'BTC-CALL-50000:1:ce',
            'action': 'manual_close',
            'notes': 'Will close manually tomorrow',
        }

        with patch(f'{_PKG}.mmmx_reconciler._audit_event'):
            apply_recon_confirmation(session, decision)

        naked = session.get('_naked_positions', [])
        assert len(naked) == 1
        assert naked[0]['divergence_id'] == 'BTC-CALL-50000:1:ce'
        assert naked[0]['source'] == 'recon_manual_close'
        assert 'naked_since' in naked[0]

    def test_manual_close_audit_event_fired(self):
        """manual_close fires RECON_MANUAL_CLOSE audit event."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {'divergence_id': 'x', 'action': 'manual_close', 'notes': ''}

        with patch(f'{_PKG}.mmmx_reconciler._audit_event') as mock_audit:
            apply_recon_confirmation(session, decision)

        categories = [c[0][1] for c in mock_audit.call_args_list]
        assert 'RECON_MANUAL_CLOSE' in categories

    def test_unknown_action_raises_value_error(self):
        """Unknown action raises ValueError."""
        from webui.backend.routes.mmmx.mmmx_reconciler import apply_recon_confirmation

        session = self._make_session_with_tranche()
        decision = {'divergence_id': 'x', 'action': 'explode', 'notes': ''}

        with pytest.raises(ValueError, match='Unknown action'):
            apply_recon_confirmation(session, decision)


# ══════════════════════════════════════════════════════════════════════════════
# POST /confirm-reconcile endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestConfirmReconcileEndpoint:

    def test_valid_accept_db_returns_200(self):
        """POST /confirm-reconcile with valid body → 200."""
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='recon-ep-001')
        mock_storage = _mock_storage(session)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_reconciler.apply_recon_confirmation') as mock_apply, \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/recon-ep-001/confirm-reconcile',
                    json={'divergence_id': 'sym:1:ce', 'action': 'accept_db', 'notes': ''},
                )

        assert res.status_code == 200
        data = res.get_json()
        assert data['ok'] is True
        mock_apply.assert_called_once()

    def test_unknown_session_returns_404(self):
        """POST /confirm-reconcile for unknown session → 404."""
        app = _make_app()
        mock_storage = _mock_storage(session=None)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage):
            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/no-such-session/confirm-reconcile',
                    json={'divergence_id': 'x', 'action': 'accept_db', 'notes': ''},
                )

        assert res.status_code == 404

    def test_invalid_action_returns_422(self):
        """POST /confirm-reconcile with bad action → 422."""
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='recon-ep-002')
        mock_storage = _mock_storage(session)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage):
            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/recon-ep-002/confirm-reconcile',
                    json={'divergence_id': 'x', 'action': 'nuke', 'notes': ''},
                )

        assert res.status_code == 422

    def test_missing_action_returns_422(self):
        """POST /confirm-reconcile with missing action → 422."""
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='recon-ep-003')
        mock_storage = _mock_storage(session)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage):
            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/recon-ep-003/confirm-reconcile',
                    json={'divergence_id': 'x'},
                )

        assert res.status_code == 422

    def test_accept_exchange_action_accepted(self):
        """POST /confirm-reconcile with accept_exchange → 200."""
        app = _make_app()
        session = _make_session(status='PAUSED', session_id='recon-ep-004')
        mock_storage = _mock_storage(session)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_reconciler.apply_recon_confirmation'), \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/recon-ep-004/confirm-reconcile',
                    json={'divergence_id': 'sym:1:pe', 'action': 'accept_exchange', 'notes': ''},
                )

        assert res.status_code == 200

    def test_manual_close_action_accepted(self):
        """POST /confirm-reconcile with manual_close → 200."""
        app = _make_app()
        session = _make_session(status='PAUSED', session_id='recon-ep-005')
        mock_storage = _mock_storage(session)

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_reconciler.apply_recon_confirmation'), \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post(
                    '/api/mmmx/session/recon-ep-005/confirm-reconcile',
                    json={'divergence_id': 'sym:1:pe', 'action': 'manual_close', 'notes': 'x'},
                )

        assert res.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /health — watchdog fields
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthWatchdogFields:

    def test_health_includes_watchdog_alive(self):
        """GET /health response includes watchdog_alive field."""
        app = _make_app()

        mock_monitors = {}
        mock_watchdog = MagicMock()
        mock_watchdog.is_alive.return_value = True
        mock_watchdog.last_tick_at = '2026-04-06T10:00:00+00:00'

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value=mock_monitors), \
             patch(f'{_PKG}.mmmx_websocket.get_ws_health', return_value={}), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=mock_watchdog):

            with app.test_client() as c:
                res = c.get('/api/mmmx/health')

        assert res.status_code == 200
        data = res.get_json()['data']
        assert 'watchdog_alive' in data
        assert data['watchdog_alive'] is True

    def test_health_includes_last_watchdog_tick(self):
        """GET /health response includes last_watchdog_tick field."""
        app = _make_app()

        tick_ts = '2026-04-06T10:00:00+00:00'
        mock_watchdog = MagicMock()
        mock_watchdog.is_alive.return_value = True
        mock_watchdog.last_tick_at = tick_ts

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={}), \
             patch(f'{_PKG}.mmmx_websocket.get_ws_health', return_value={}), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=mock_watchdog):

            with app.test_client() as c:
                res = c.get('/api/mmmx/health')

        data = res.get_json()['data']
        assert data['last_watchdog_tick'] == tick_ts

    def test_health_watchdog_dead(self):
        """GET /health correctly reports watchdog_alive=False when watchdog is not running."""
        app = _make_app()

        mock_watchdog = MagicMock()
        mock_watchdog.is_alive.return_value = False
        mock_watchdog.last_tick_at = None

        with patch(f'{_PKG}.mmmx_monitor.get_all_monitors', return_value={}), \
             patch(f'{_PKG}.mmmx_websocket.get_ws_health', return_value={}), \
             patch(f'{_PKG}.mmmx_watchdog.get_watchdog', return_value=mock_watchdog):

            with app.test_client() as c:
                res = c.get('/api/mmmx/health')

        data = res.get_json()['data']
        assert data['watchdog_alive'] is False
        assert data['last_watchdog_tick'] is None


# ══════════════════════════════════════════════════════════════════════════════
# POST /kill-switch endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestKillSwitchEndpoint:

    def test_session_scope_kill_switch_stops_one_session(self):
        """POST /kill-switch scope=session stops target session and returns summary."""
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='kill-ep-001')
        mock_storage = _mock_storage(session)

        def _set_complete(s, new_status, reason=''):
            s['status'] = new_status

        monitor = MagicMock()
        monitor.is_alive.return_value = False

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.stop_session_monitor') as mock_stop, \
             patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=monitor), \
             patch(f'{_PKG}.mmmx_state.transition_status', side_effect=_set_complete), \
             patch(f'{_PKG}.mmmx_websocket.emit_status_change'), \
             patch(f'{_PKG}.mmmx_websocket.emit_session_stopped'), \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post('/api/mmmx/kill-switch', json={
                    'scope': 'session',
                    'session_id': 'kill-ep-001',
                })

        assert res.status_code == 200
        data = res.get_json()['data']
        assert data['scope'] == 'session'
        assert data['requested_count'] == 1
        assert data['stopped_count'] == 1
        assert data['failed_count'] == 0
        mock_stop.assert_called_once_with('kill-ep-001', reason='operator kill switch')

    def test_session_scope_requires_session_id(self):
        """POST /kill-switch scope=session without session_id returns 422."""
        app = _make_app()

        with app.test_client() as c:
            res = c.post('/api/mmmx/kill-switch', json={'scope': 'session'})

        assert res.status_code == 422

    def test_global_scope_only_targets_active_sessions(self):
        """POST /kill-switch scope=global stops RUNNING/PAUSED/GATES_PASSED sessions only."""
        app = _make_app()

        running = _make_session(status='RUNNING', session_id='kill-global-run')
        paused = _make_session(status='PAUSED', session_id='kill-global-pause')
        gates = _make_session(status='GATES_PASSED', session_id='kill-global-gates')
        draft = _make_session(status='DRAFT', session_id='kill-global-draft')
        done = _make_session(status='COMPLETE', session_id='kill-global-done')

        sessions = [running, paused, gates, draft, done]
        by_id = {s['session_id']: s for s in sessions}

        mock_storage = MagicMock()
        mock_storage.list_sessions.return_value = sessions
        mock_storage.load_session.side_effect = lambda sid: by_id.get(sid)
        mock_storage.get_generation.return_value = 5
        mock_storage.save_session.return_value = True

        def _set_complete(s, new_status, reason=''):
            s['status'] = new_status

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.stop_session_monitor') as mock_stop, \
             patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=None), \
             patch(f'{_PKG}.mmmx_state.transition_status', side_effect=_set_complete), \
             patch(f'{_PKG}.mmmx_websocket.emit_status_change'), \
             patch(f'{_PKG}.mmmx_websocket.emit_session_stopped'), \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post('/api/mmmx/kill-switch', json={'scope': 'global'})

        assert res.status_code == 200
        data = res.get_json()['data']
        assert data['scope'] == 'global'
        assert data['requested_count'] == 3
        assert data['stopped_count'] == 3
        assert data['failed_count'] == 0
        assert mock_stop.call_count == 3

    def test_kill_switch_emits_progress_lifecycle(self):
        """Kill switch emits accepted -> session_result -> completed progress events."""
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='kill-progress-001')
        mock_storage = _mock_storage(session)

        def _set_complete(s, new_status, reason=''):
            s['status'] = new_status

        monitor = MagicMock()
        monitor.is_alive.return_value = False

        with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=mock_storage), \
             patch(f'{_PKG}.mmmx_monitor.stop_session_monitor'), \
             patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=monitor), \
             patch(f'{_PKG}.mmmx_state.transition_status', side_effect=_set_complete), \
             patch(f'{_PKG}.mmmx_websocket.emit_status_change'), \
             patch(f'{_PKG}.mmmx_websocket.emit_session_stopped'), \
             patch(f'{_PKG}.mmmx_websocket.emit_kill_switch_progress') as mock_progress, \
             patch(f'{_PKG}.mmmx_activity.log_activity'):

            with app.test_client() as c:
                res = c.post('/api/mmmx/kill-switch', json={
                    'scope': 'session',
                    'session_id': 'kill-progress-001',
                })

        assert res.status_code == 200
        data = res.get_json()['data']
        assert isinstance(data.get('correlation_id'), str)
        assert data['correlation_id'].startswith('kill-')

        stages = [kwargs.get('stage') for _, kwargs in mock_progress.call_args_list]
        assert stages[0] == 'accepted'
        assert 'session_result' in stages
        assert stages[-1] == 'completed'
