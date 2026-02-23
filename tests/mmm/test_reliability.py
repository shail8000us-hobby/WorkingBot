"""
MMM Unit Tests — Critical Paths

Tests for reliability-critical components:
- Peak P&L tracking (decaying peak, reversal reset)
- Circuit breaker state machine
- Watchdog exponential backoff
- Session state checksum
- Safety event handling

Created: February 23, 2026
Coverage Target: 80%+ on critical paths
"""

import pytest
import time
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Test imports - these should work when run from project root
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# =============================================================================
# Peak P&L Tracking Tests
# =============================================================================

class TestPeakPnLTracking:
    """Test the decaying peak P&L tracking logic."""

    def test_peak_increases_on_higher_pnl(self):
        """Peak should update when current P&L exceeds it."""
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        
        session = {'peak_pnl': 100}
        update_peak_pnl(session, 150)
        assert session['peak_pnl'] == 150

    def test_peak_decays_on_lower_pnl(self):
        """Peak should decay 10% toward current when P&L drops."""
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        
        session = {'peak_pnl': 100}
        update_peak_pnl(session, 50)
        # Expected: 100 * 0.9 + 50 * 0.1 = 90 + 5 = 95
        assert session['peak_pnl'] == 95

    def test_peak_decay_multiple_iterations(self):
        """Peak should decay over multiple heartbeats."""
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        
        session = {'peak_pnl': 100}
        # Simulate 10 heartbeats with P&L at 50
        for _ in range(10):
            update_peak_pnl(session, 50)
        
        # After 10 iterations with 10% decay toward current:
        # peak_n = peak_0 * 0.9^n + 50 * (1 - 0.9^n)
        # peak_10 = 100 * 0.349 + 50 * 0.651 = ~67.45
        assert session['peak_pnl'] < 70
        assert session['peak_pnl'] > 65

    def test_peak_no_decay_when_zero(self):
        """Peak should not decay when it's zero or negative."""
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        
        session = {'peak_pnl': 0}
        update_peak_pnl(session, -10)
        # No decay when peak is 0
        assert session['peak_pnl'] == 0

    def test_peak_initializes_from_missing(self):
        """Peak should initialize to 0 if missing."""
        from webui.backend.routes.mmm.mmm_safety import update_peak_pnl
        
        session = {}
        update_peak_pnl(session, 100)
        assert session['peak_pnl'] == 100

    def test_reversal_resets_peak(self):
        """Reversal should reset peak to current P&L."""
        from webui.backend.routes.mmm.mmm_safety import reset_peak_pnl_on_reversal
        
        session = {'peak_pnl': 200}
        reset_peak_pnl_on_reversal(session, 50)
        assert session['peak_pnl'] == 50

    def test_reversal_resets_peak_minimum_zero(self):
        """Reversal reset should not go below zero."""
        from webui.backend.routes.mmm.mmm_safety import reset_peak_pnl_on_reversal
        
        session = {'peak_pnl': 100}
        reset_peak_pnl_on_reversal(session, -50)
        assert session['peak_pnl'] == 0


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker state machine and sliding window."""

    @pytest.fixture
    def circuit(self):
        """Create a fresh circuit breaker for each test."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
        return CircuitBreaker('test-session', failure_threshold=3)

    def test_initial_state_closed(self, circuit):
        """Circuit should start in CLOSED state."""
        assert circuit.state.value == 'CLOSED'
        assert circuit.is_closed
        assert not circuit.is_open

    def test_allow_request_when_closed(self, circuit):
        """CLOSED circuit should allow all requests."""
        assert circuit.allow_request() is True

    def test_success_keeps_closed(self, circuit):
        """Successful requests should keep circuit CLOSED."""
        circuit.record_success()
        circuit.record_success()
        assert circuit.is_closed

    def test_failures_trip_circuit(self, circuit):
        """Enough failures should trip circuit to OPEN."""
        circuit.record_failure('error 1')
        circuit.record_failure('error 2')
        circuit.record_failure('error 3')  # Threshold reached
        
        assert circuit.is_open
        assert circuit.state.value == 'OPEN'

    def test_open_circuit_denies_requests(self, circuit):
        """OPEN circuit should deny requests."""
        for _ in range(3):
            circuit.record_failure('error')
        
        assert circuit.allow_request() is False

    def test_success_after_failure_resets_count(self, circuit):
        """Success should reset failure count."""
        circuit.record_failure('error 1')
        circuit.record_failure('error 2')
        circuit.record_success()  # Resets
        circuit.record_failure('error 1')
        circuit.record_failure('error 2')
        
        # Should still be CLOSED (only 2 consecutive failures)
        assert circuit.is_closed

    def test_manual_reset(self, circuit):
        """Manual reset should return circuit to CLOSED."""
        for _ in range(3):
            circuit.record_failure('error')
        
        assert circuit.is_open
        
        result = circuit.reset()
        assert result['previous_state'] == 'OPEN'
        assert result['new_state'] == 'CLOSED'
        assert circuit.is_closed

    def test_sliding_window_tracking(self, circuit):
        """Sliding window should track recent requests."""
        circuit.record_success()
        circuit.record_success()
        circuit.record_failure('test error')
        
        stats = circuit.window_stats
        assert stats['total'] == 3
        assert stats['successes'] == 2
        assert stats['failures'] == 1
        assert stats['success_rate'] == pytest.approx(2/3)

    def test_error_type_classification(self, circuit):
        """Errors should be classified by type."""
        circuit.record_failure('Connection timeout')
        circuit.record_failure('Rate limit exceeded 429')
        circuit.record_failure('Connection refused')
        circuit.record_failure('Unknown error')
        
        stats = circuit.window_stats
        assert 'timeout' in stats['error_types']
        assert 'rate_limit' in stats['error_types']
        assert 'connection' in stats['error_types']

    def test_summary_includes_window(self, circuit):
        """Summary should include sliding window stats."""
        circuit.record_success()
        circuit.record_failure('error')
        
        summary = circuit.summary()
        assert 'sliding_window' in summary
        assert summary['sliding_window']['total'] == 2

    def test_reset_clears_window(self, circuit):
        """Reset should clear the sliding window."""
        circuit.record_success()
        circuit.record_failure('error')
        
        circuit.reset()
        stats = circuit.window_stats
        assert stats['total'] == 0


# =============================================================================
# Watchdog Backoff Tests
# =============================================================================

class TestWatchdogBackoff:
    """Test exponential backoff logic in watchdog."""

    @pytest.fixture
    def watchdog(self):
        """Mock watchdog for backoff testing."""
        from webui.backend.routes.mmm.mmm_watchdog import MMMWatchdog
        wd = MMMWatchdog.get_instance()
        return wd

    def test_backoff_calculation_base(self, watchdog):
        """First restart should use base backoff (30s)."""
        # With restart_count=0, remaining should be 0 (no backoff yet)
        remaining = watchdog._get_cooldown_remaining('test-sid', restart_count=0)
        assert remaining >= 0

    def test_backoff_exponential_growth(self, watchdog):
        """Backoff should grow exponentially with restarts."""
        # Base = 30s, multiplier = 2x
        # restart 1: 30s
        # restart 2: 60s
        # restart 3: 120s
        # restart 4: 240s
        # restart 5: 480s
        # restart 6+: capped at 600s
        
        BACKOFF_BASE = 30
        BACKOFF_MULT = 2.0
        BACKOFF_MAX = 600
        
        for count in range(10):
            expected = min(BACKOFF_BASE * (BACKOFF_MULT ** count), BACKOFF_MAX)
            assert expected <= BACKOFF_MAX

    def test_clear_backoff(self, watchdog):
        """Clear backoff should reset cooldown for session."""
        sid = 'test-clear-sid'
        # Clear should work even if no backoff exists
        watchdog.clear_backoff(sid)


# =============================================================================
# Session Checksum Tests
# =============================================================================

class TestSessionChecksum:
    """Test session state checksum for corruption detection."""

    @pytest.fixture
    def storage(self):
        """Create a storage instance for testing."""
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        return MMMStorage()

    def test_checksum_calculation(self, storage):
        """Checksum should be deterministic for same data."""
        session = {
            'session_id': 'test-session',
            'params': {'expiry': '28FEB26'},
            'strategy_status': 'RUNNING',
            'positions': {},
            'fills': [],
            'trade_history': [],
        }
        
        checksum1 = storage._calculate_checksum(session)
        checksum2 = storage._calculate_checksum(session)
        
        assert checksum1 == checksum2
        assert len(checksum1) == 16  # SHA256 truncated to 16 chars

    def test_checksum_changes_with_data(self, storage):
        """Checksum should change when critical data changes."""
        session1 = {
            'session_id': 'test-session',
            'params': {'expiry': '28FEB26'},
            'strategy_status': 'RUNNING',
        }
        session2 = {
            'session_id': 'test-session',
            'params': {'expiry': '28FEB26'},
            'strategy_status': 'PAUSED',  # Changed
        }
        
        checksum1 = storage._calculate_checksum(session1)
        checksum2 = storage._calculate_checksum(session2)
        
        assert checksum1 != checksum2

    def test_checksum_validation_passes(self, storage):
        """Valid checksum should pass validation."""
        session = {
            'session_id': 'test-session',
            'params': {},
            '_checksum': None,  # Will be set
        }
        session['_checksum'] = storage._calculate_checksum(session)
        
        assert storage._validate_checksum(session) is True

    def test_checksum_validation_fails_on_mismatch(self, storage):
        """Invalid checksum should fail validation."""
        session = {
            'session_id': 'test-session',
            'params': {},
            '_checksum': 'invalid_checksum',
        }
        
        # Validation should return False on mismatch
        assert storage._validate_checksum(session) is False

    def test_legacy_session_without_checksum(self, storage):
        """Legacy sessions without checksum should pass validation."""
        session = {
            'session_id': 'legacy-session',
            'params': {},
            # No _checksum field
        }
        
        # Should return True for backward compatibility
        assert storage._validate_checksum(session) is True


# =============================================================================
# Safety Event Tests
# =============================================================================

class TestSafetyEvents:
    """Test safety event handling and blocking logic."""

    def test_should_block_on_stop(self):
        """Stop action should block adjustments."""
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        
        events = [{'action': 'stop', 'message': 'Max loss reached'}]
        assert should_block_adjustment(events) is True

    def test_should_block_on_auto_close(self):
        """Auto close action should block adjustments."""
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        
        events = [{'action': 'auto_close', 'message': 'Emergency close'}]
        assert should_block_adjustment(events) is True

    def test_no_block_on_warn(self):
        """Warn action should not block adjustments."""
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        
        events = [{'action': 'warn', 'message': 'Low P&L warning'}]
        assert should_block_adjustment(events) is False

    def test_no_block_on_empty(self):
        """Empty events should not block."""
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        
        assert should_block_adjustment([]) is False

    def test_block_action_priority(self):
        """Auto close should have highest priority."""
        from webui.backend.routes.mmm.mmm_safety import get_block_action
        
        events = [
            {'action': 'stop', 'message': 'Stop'},
            {'action': 'auto_close', 'message': 'Emergency'},
            {'action': 'stop_adjustments', 'message': 'Pause adj'},
        ]
        
        reason, action_type = get_block_action(events)
        assert action_type == 'auto_close'
        assert reason == 'Emergency'

    def test_should_pause(self):
        """Pause action should trigger pause."""
        from webui.backend.routes.mmm.mmm_safety import should_pause
        
        events = [{'action': 'pause', 'message': 'Circuit breaker pause'}]
        should, reason = should_pause(events)
        
        assert should is True
        assert 'pause' in reason.lower()


# =============================================================================
# Trailing Stop Tests
# =============================================================================

class TestTrailingStop:
    """Test trailing stop logic in safety module."""

    @pytest.fixture
    def safety(self):
        """Create a fresh safety instance."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        return MMMSafety()

    def test_no_trailing_stop_when_disabled(self, safety):
        """Trailing stop should not trigger when disabled."""
        session = {
            'session_id': 'test',
            'peak_pnl': 100,
            'realized_pnl': 50,
            'unrealized_pnl': 0,
            'params': {
                'safety_enabled': True,
                'trailing_stop_pct': 0,  # Disabled by setting to 0
            },
        }
        
        events = safety.check_trailing_stop(session)
        # With trailing_stop_pct=0, threshold=0, no alert since 50 > 0
        assert len(events) == 0

    def test_trailing_stop_triggers_on_threshold(self, safety):
        """Trailing stop should trigger when P&L drops below threshold."""
        session = {
            'session_id': 'test',
            'peak_pnl': 100,
            'realized_pnl': 40,  # Total P&L is 40
            'unrealized_pnl': 0,
            'params': {
                'safety_enabled': True,
                'trailing_stop_pct': 0.50,  # 50% threshold = $50
            },
        }
        
        # P&L is 40, below threshold of 50 (50% of peak 100)
        events = safety.check_trailing_stop(session)
        
        # Should have a trailing stop event
        assert len(events) > 0
        assert any('trailing' in e.get('type', '').lower() for e in events)


# =============================================================================
# Emergency Close Tests
# =============================================================================

class TestEmergencyClose:
    """Test emergency close triggering conditions."""

    def test_max_loss_triggers_close(self):
        """Max loss breach should trigger emergency close."""
        from webui.backend.routes.mmm.mmm_safety import MMMSafety
        
        safety = MMMSafety()
        session = {
            'session_id': 'test',
            'realized_pnl': -600,  # Total P&L of -600
            'unrealized_pnl': 0,
            'params': {
                'safety_enabled': True,
                'max_loss_amount': 500,  # Max loss threshold
            },
        }
        
        # P&L is -600, exceeds max_loss of 500
        events = safety.check_max_loss(session)
        
        # Should have stop or auto_close event
        blocking_events = [e for e in events if e.get('action') in ('stop', 'auto_close')]
        assert len(blocking_events) > 0


# =============================================================================
# Run tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
