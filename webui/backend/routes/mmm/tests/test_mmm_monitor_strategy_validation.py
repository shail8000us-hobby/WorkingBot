import pytest
from unittest.mock import patch

from webui.backend.routes.mmm.mmm_monitor import start_session_monitor, stop_session_monitor


class _DummyMonitor:
    def __init__(self, session_id, session):
        self.session_id = session_id
        self.session = session
        self.started = False
        self._thread = None
        self._my_generation = 0

    def start(self):
        self.started = True

    def stop(self, _reason='stopped'):
        self.started = False


def test_start_session_monitor_blocks_when_strategy_validation_fails():
    """start_session_monitor must raise ValueError (not silently warn) on violations.

    2026-04-17: behavior upgraded from warn+continue to block+raise so callers
    cannot accidentally start a monitor on a structurally invalid session.
    """
    session_id = 'mmm-strategy-start-check-1'
    session = {
        'session_id': session_id,
        'strategy_type': 'STRADDLE_ROLL',
        'params': {},
        'ce': {},
        'pe': {},
    }

    with patch('webui.backend.routes.mmm.mmm_monitor.MMMMonitor', _DummyMonitor), \
         patch('webui.backend.routes.mmm.mmm_monitor.validate_session_for_strategy', return_value=['boom']) as mock_validate, \
         patch('webui.backend.routes.mmm.mmm_monitor.emit_safety') as mock_emit_safety:
        with pytest.raises(ValueError, match='boom'):
            start_session_monitor(session_id, session)

    mock_validate.assert_called_once()
    mock_emit_safety.assert_called_once()
