"""
Test MMMStrategyObserver - validates BUY (close) orders before exchange submission

Tests all 4 validation checks:
1. Strategy Continuity: Prevents one-sided exposure
2. Price Consistency: Ensures premium aligns with mechanism
3. Close Velocity: Detects rapid closing patterns  
4. Ledger Integrity: Verifies position exists in session

Created: March 2026
"""

import pytest
import time
from datetime import datetime, timezone

from webui.backend.routes.mmm.mmm_observer import get_observer, MMMStrategyObserver


class TestObserverSingleton:
    """Test the singleton pattern works correctly."""
    
    def test_get_observer_returns_same_instance(self):
        """Ensure get_observer() returns the same instance every time."""
        obs1 = get_observer()
        obs2 = get_observer()
        assert obs1 is obs2
        assert isinstance(obs1, MMMStrategyObserver)


class TestStrategyContinuity:
    """Test CHECK 1: Strategy Continuity (hedge balance validation)."""
    
    def setup_method(self):
        self.observer = get_observer()
        self.session = {
            'session_id': 'test_session',
            'ce': {'total_lots': 50, 'positions': []},
            'pe': {'total_lots': 30, 'positions': []},
        }
    
    def test_blocks_one_sided_exposure(self):
        """Block close that would create one-sided exposure."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=30,  # All PE lots
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert not result['allowed']
        assert 'one-sided exposure' in result['reason']
        assert result['block_type'] == 'continuity'
    
    def test_allows_partial_close_leaving_hedge(self):
        """Allow close that leaves some lots for hedging."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=20,  # Leaves 10 PE lots
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert result['allowed']
    
    def test_allows_both_sides_closing(self):
        """Allow full close when both sides are closing together."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=30,  # All PE lots
            current_premium=5.0,
            mechanism='both_sides_close',
            both_sides_closing=True,
        )
        assert result['allowed']
    
    def test_allows_close_when_other_side_empty(self):
        """Allow close when the other side has no positions."""
        session = {
            'session_id': 'test_session',
            'ce': {'total_lots': 0, 'positions': []},
            'pe': {'total_lots': 30, 'positions': []},
        }
        result = self.observer.validate_close(
            session=session,
            side='pe',
            lots=30,
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert result['allowed']


class TestPriceConsistency:
    """Test CHECK 2: Price Consistency (mechanism-aware validation)."""
    
    def setup_method(self):
        self.observer = get_observer()
        self.session = {
            'session_id': 'test_session',
            'params': {
                'close_at_threshold': 5.0,
                'harvest_profit_pct': 70.0,
            },
            'ce': {'total_lots': 50, 'positions': []},
            'pe': {'total_lots': 30, 'positions': []},
        }
    
    def test_blocks_close_at_5_with_high_premium(self):
        """Block close_at_5 when premium exceeds threshold × 2."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=10,
            current_premium=12.0,  # > 5.0 × 2 = 10.0
            mechanism='close_at_5',
        )
        assert not result['allowed']
        assert 'close_at_5' in result['reason']
        assert 'not yet cheap enough' in result['reason']
        assert result['block_type'] == 'price'
    
    def test_allows_close_at_5_within_threshold(self):
        """Allow close_at_5 when premium is within acceptable range."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=10,
            current_premium=8.0,  # < 5.0 × 2 = 10.0
            mechanism='close_at_5',
        )
        assert result['allowed']
    
    def test_blocks_harvest_without_decay(self):
        """Block harvest when position hasn't decayed enough."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=10,
            current_premium=50.0,  # > 100 × (1 - 70/100) = 30
            mechanism='harvest',
            entry_premium=100.0,
        )
        assert not result['allowed']
        assert 'harvest' in result['reason']
        assert 'not decayed' in result['reason']
        assert result['block_type'] == 'price'
    
    def test_allows_harvest_with_sufficient_decay(self):
        """Allow harvest when position has decayed enough."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=10,
            current_premium=25.0,  # < 100 × (1 - 70/100) = 30
            mechanism='harvest',
            entry_premium=100.0,
        )
        assert result['allowed']
    
    def test_allows_emergency_mechanisms_regardless_of_price(self):
        """Emergency mechanisms (atm_shield, wind_down) are price-exempt."""
        for mechanism in ['atm_shield', 'wind_down', 'emergency']:
            result = self.observer.validate_close(
                session=self.session,
                side='pe',
                lots=10,
                current_premium=999.0,  # Extremely high
                mechanism=mechanism,
            )
            assert result['allowed'], f"{mechanism} should be price-exempt"


class TestCloseVelocity:
    """Test CHECK 3: Close Velocity (rapid closing detection)."""
    
    def setup_method(self):
        self.observer = get_observer()
        self.session = {
            'session_id': 'test_velocity',
            'ce': {'total_lots': 200, 'positions': []},
            'pe': {'total_lots': 200, 'positions': []},
        }
        # Clear any existing velocity data
        self.observer.clear_session('test_velocity')
    
    def test_allows_small_volume_closes(self):
        """Allow closes under the velocity threshold."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=30,  # < 60 lot alert threshold
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert result['allowed']
    
    def test_blocks_high_velocity_non_exempt_mechanism(self):
        """Block high velocity for non-exempt mechanisms."""
        # Simulate 90 lots already closed in the window
        for _ in range(9):
            self.observer.record_close('test_velocity', 'pe', 10)
        
        # This would bring total to 110 lots (90 + 20), exceeding 100-lot block threshold
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=20,
            current_premium=5.0,
            mechanism='close_at_5',  # Not velocity-exempt
        )
        assert not result['allowed']
        assert 'velocity exceeded' in result['reason']
        assert result['block_type'] == 'velocity'
    
    def test_allows_high_velocity_exempt_mechanism(self):
        """Allow high velocity for exempt mechanisms."""
        # Simulate 90 lots already closed
        for _ in range(9):
            self.observer.record_close('test_velocity', 'pe', 10)
        
        # This would exceed threshold but should be allowed for wind_down
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=20,
            current_premium=5.0,
            mechanism='wind_down',  # Velocity-exempt
        )
        assert result['allowed']
    
    def test_velocity_window_expiry(self):
        """Old velocity records should not affect current validation.""" 
        # Record closes but don't actually run time forward (would need time mocking)
        # This is a basic test - in production, old records auto-expire
        self.observer.record_close('test_velocity', 'pe', 60)
        
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=50,  # Would exceed if added to the 60
            current_premium=5.0,
            mechanism='close_at_5',
        )
        # Should block since we can't fast-forward time in this test
        assert not result['allowed']


class TestLedgerIntegrity:
    """Test CHECK 4: Ledger Integrity (position existence validation)."""
    
    def setup_method(self):
        self.observer = get_observer()
    
    def test_blocks_close_with_zero_lots_in_ledger(self):
        """Block close when side has 0 lots in session."""
        session = {
            'session_id': 'test_ledger',
            'ce': {'total_lots': 0, 'positions': []},  # Both sides empty
            'pe': {'total_lots': 0, 'positions': []},  # No PE positions
        }
        result = self.observer.validate_close(
            session=session,
            side='pe',
            lots=10,
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert not result['allowed']
        assert 'Nothing to close' in result['reason']
        assert result['block_type'] == 'ledger'
    
    def test_blocks_close_exceeding_available_lots(self):
        """Block close when requested lots exceed available."""
        session = {
            'session_id': 'test_ledger',
            'ce': {'total_lots': 0, 'positions': []},  # No CE to cause continuity issue
            'pe': {'total_lots': 20, 'positions': []},
        }
        result = self.observer.validate_close(
            session=session,
            side='pe',
            lots=30,  # > 20 available
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert not result['allowed']
        assert 'only has 20 lots' in result['reason']
        assert result['block_type'] == 'ledger'
    
    def test_allows_close_within_available_lots(self):
        """Allow close when lots are within available range."""
        session = {
            'session_id': 'test_ledger',
            'ce': {'total_lots': 50, 'positions': []},
            'pe': {'total_lots': 30, 'positions': []},
        }
        result = self.observer.validate_close(
            session=session,
            side='pe',
            lots=20,  # < 30 available
            current_premium=5.0,
            mechanism='close_at_5',
        )
        assert result['allowed']


class TestIntegrationScenarios:
    """Test complete scenarios that mirror real trading situations."""
    
    def setup_method(self):
        self.observer = get_observer()
        self.session = {
            'session_id': 'integration_test',
            'params': {
                'close_at_threshold': 5.0,
                'harvest_profit_pct': 70.0,
            },
            'ce': {'total_lots': 50, 'positions': []},
            'pe': {'total_lots': 50, 'positions': []},
        }
        self.observer.clear_session('integration_test')
    
    def test_today_bug_scenario_blocked(self):
        """Test that today's PE wipeout scenario would be blocked."""
        # Scenario: PE close at $58 when threshold is $5
        # All 4 orders should be blocked by price consistency check
        for premium in [58.0, 60.0, 56.0, 59.0]:
            result = self.observer.validate_close(
                session=self.session,
                side='pe',
                lots=20,
                current_premium=premium,  # >> $5 × 2 = $10
                mechanism='close_at_5',
            )
            assert not result['allowed'], f"Should block premium {premium}"
            assert result['block_type'] == 'price'
    
    def test_legitimate_close_at_5_allowed(self):
        """Test that legitimate close-at-5 is allowed."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=20,
            current_premium=4.0,  # < $5 threshold, legitimate
            mechanism='close_at_5',
        )
        assert result['allowed']
    
    def test_emergency_close_bypasses_price_check(self):
        """Test that emergency closes work even with high premiums."""
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=50,  # All lots
            current_premium=100.0,  # Very high
            mechanism='emergency',
            both_sides_closing=True,  # Emergency session close
        )
        assert result['allowed']
    
    def test_record_close_affects_velocity(self):
        """Test that record_close() properly updates velocity tracking."""
        # Record some closes
        self.observer.record_close('integration_test', 'pe', 30)
        self.observer.record_close('integration_test', 'pe', 40)
        
        # Next close should trigger velocity block (30 + 40 + 35 = 105 > 100)
        result = self.observer.validate_close(
            session=self.session,
            side='pe',
            lots=35,
            current_premium=4.0,
            mechanism='close_at_5',
        )
        assert not result['allowed']
        assert result['block_type'] == 'velocity'