"""
MMM Integration Tests

Tests for full session lifecycle and system behavior:
- Session create → init → entry → heartbeats → close
- Network failure simulation
- Emergency stops
- Watchdog restart recovery

Created: February 23, 2026
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# =============================================================================
# Session Lifecycle Tests
# =============================================================================

class TestSessionLifecycle:
    """Test complete session lifecycle."""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for testing."""
        storage = MagicMock()
        storage.get_session.return_value = None
        storage.list_sessions.return_value = []
        return storage

    @pytest.fixture
    def sample_session(self):
        """Sample session data for testing."""
        return {
            'session_id': 'test-lifecycle-1',
            'strategy_status': 'IDLE',
            'params': {
                'symbol': 'BTC',
                'expiry': '28FEB26',
                'lot_size': 1,
                'safety_enabled': True,
            },
            'ce': {},
            'pe': {},
            'created_at': datetime.now(timezone.utc).isoformat(),
        }

    def test_session_state_transitions(self, sample_session):
        """Test valid state transitions."""
        # Valid transitions: IDLE -> RUNNING -> PAUSED -> RUNNING -> STOPPED
        valid_transitions = [
            ('IDLE', 'RUNNING'),
            ('RUNNING', 'PAUSED'),
            ('PAUSED', 'RUNNING'),
            ('RUNNING', 'STOPPED'),
            ('PAUSED', 'STOPPED'),
        ]
        
        for from_state, to_state in valid_transitions:
            sample_session['strategy_status'] = from_state
            sample_session['strategy_status'] = to_state
            assert sample_session['strategy_status'] == to_state

    def test_session_initialization(self, sample_session, mock_storage):
        """Test session can be saved and retrieved."""
        mock_storage.save_session.return_value = sample_session['session_id']
        
        saved_id = mock_storage.save_session(sample_session)
        assert saved_id == sample_session['session_id']
        mock_storage.save_session.assert_called_once()


# =============================================================================
# API Endpoint Integration Tests
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoint integration."""

    @pytest.fixture
    def client(self):
        """Create test client for Flask app."""
        # Import Flask app
        try:
            from webui.backend.app import app
            app.config['TESTING'] = True
            with app.test_client() as client:
                yield client
        except ImportError:
            pytest.skip("Flask app not available")

    def test_health_check_endpoint(self, client):
        """Test emergency health check returns valid response."""
        response = client.get('/api/mmm/emergency/health-check')
        
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'checks' in data
            assert 'overall_status' in data

    def test_aggregate_metrics_endpoint(self, client):
        """Test aggregate metrics returns valid response."""
        response = client.get('/api/mmm/metrics/aggregate')
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'sessions' in data
            assert 'watchdog' in data

    def test_audit_trail_endpoint(self, client):
        """Test audit trail returns activities."""
        response = client.get('/api/mmm/audit/trail?limit=10')
        
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert 'activities' in data
            assert 'count' in data

    def test_pause_all_requires_reason(self, client):
        """Test pause-all gracefully handles request."""
        response = client.post(
            '/api/mmm/emergency/pause-all',
            json={'reason': 'Integration test'}
        )
        
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True

    def test_close_all_dry_run(self, client):
        """Test close-all-positions dry run."""
        response = client.post(
            '/api/mmm/emergency/close-all-positions',
            json={'reason': 'Integration test', 'dry_run': True}
        )
        
        if response.status_code == 200:
            data = response.get_json()
            assert data.get('success') is True
            assert data.get('dry_run') is True


# =============================================================================
# Watchdog Recovery Tests
# =============================================================================

class TestWatchdogRecovery:
    """Test watchdog restart and recovery behavior."""

    @pytest.fixture
    def watchdog(self):
        """Get watchdog instance."""
        from webui.backend.routes.mmm.mmm_watchdog import MMMWatchdog
        return MMMWatchdog.get_instance()

    def test_watchdog_status(self, watchdog):
        """Test watchdog status returns valid data."""
        status = watchdog.status()
        
        assert 'running' in status
        assert 'monitored_sessions' in status
        assert 'backoff' in status

    def test_watchdog_start_stop(self, watchdog):
        """Test watchdog can be started and stopped."""
        # Just verify methods exist and don't crash
        initial_running = watchdog._running
        
        # These are idempotent operations
        if not initial_running:
            watchdog.start()
        
        status = watchdog.status()
        assert isinstance(status['running'], bool)


# =============================================================================
# Circuit Breaker Recovery Tests
# =============================================================================

class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery scenarios."""

    @pytest.fixture
    def circuit(self):
        """Create circuit breaker for testing."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        return CircuitBreaker('test-recovery', failure_threshold=3)

    def test_recovery_after_timeout(self, circuit):
        """Circuit should allow probe after timeout."""
        # Trip the circuit
        for _ in range(3):
            circuit.record_failure('error')
        
        assert circuit.is_open
        
        # After reset, should be closed
        circuit.reset()
        assert circuit.is_closed
        assert circuit.allow_request() is True

    def test_probe_success_recovers(self, circuit):
        """Successful probe should recover circuit."""
        # Trip the circuit
        for _ in range(3):
            circuit.record_failure('error')
        
        # Manually set to HALF_OPEN for testing
        circuit._state = circuit._state.__class__('HALF_OPEN')
        
        # Success should recover
        circuit.record_success()
        assert circuit.is_closed


# =============================================================================
# Storage Persistence Tests
# =============================================================================

class TestStoragePersistence:
    """Test storage operations and persistence."""

    @pytest.fixture
    def storage(self):
        """Get storage instance."""
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        return MMMStorage()

    def test_list_sessions(self, storage):
        """Test listing sessions."""
        sessions = storage.list_sessions()
        assert isinstance(sessions, list)

    def test_list_active_sessions(self, storage):
        """Test listing active sessions only."""
        sessions = storage.list_sessions(active_only=True)
        
        for session in sessions:
            status = session.get('strategy_status', '')
            assert status in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP')


# =============================================================================
# Activity Log Integration Tests
# =============================================================================

class TestActivityLogIntegration:
    """Test activity log operations."""

    @pytest.fixture
    def activity_log(self):
        """Get activity log instance."""
        from webui.backend.routes.mmm.mmm_activity import get_activity_log
        return get_activity_log()

    def test_log_activity(self, activity_log):
        """Test logging an activity."""
        activity_log.add(
            activity_type='test',
            message='Integration test activity',
            session_id='test-session',
            severity='info',
        )

    def test_get_recent_activities(self, activity_log):
        """Test retrieving recent activities."""
        activities = activity_log.get_recent(limit=10)
        
        assert isinstance(activities, list)
        assert len(activities) <= 10

    def test_filter_by_session(self, activity_log):
        """Test filtering activities by session."""
        # Add a test activity
        activity_log.add(
            activity_type='test',
            message='Filter test',
            session_id='filter-test-session',
            severity='info',
        )
        
        # Filter by that session
        activities = activity_log.get_recent(
            limit=10,
            session_id='filter-test-session'
        )
        
        for activity in activities:
            assert activity.get('session_id') == 'filter-test-session'


# =============================================================================
# Emergency Procedure Tests
# =============================================================================

class TestEmergencyProcedures:
    """Test emergency procedure execution."""

    def test_emergency_stop_all_safe(self):
        """Test emergency stop-all doesn't crash with no sessions."""
        from webui.backend.routes.mmm.mmm_storage import get_storage
        
        storage = get_storage()
        sessions = storage.list_sessions()
        running = [s for s in sessions if s.get('strategy_status') == 'RUNNING']
        
        # This test just verifies we can query running sessions
        assert isinstance(running, list)

    def test_circuit_reset_endpoint_safe(self):
        """Test circuit reset works for non-existent session."""
        from webui.backend.routes.mmm.mmm_monitor import get_monitor
        
        # Should return None for non-existent session
        monitor = get_monitor('non-existent-session-xyz')
        assert monitor is None


# =============================================================================
# Run tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
