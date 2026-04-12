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


def test_start_session_monitor_warns_when_strategy_validation_fails():
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
        monitor = start_session_monitor(session_id, session)

    assert isinstance(monitor, _DummyMonitor)
    assert monitor.started is True
    mock_validate.assert_called_once()
    mock_emit_safety.assert_called_once()

    stop_session_monitor(session_id, 'test cleanup')
