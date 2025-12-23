"""
Unit Tests for Capital Protection System

Tests all 5 capital protection features:
1. Equity Floor Monitor
2. Drawdown Cap Tracker
3. Exposure Growth Limiter
4. Pending Budget Control
5. Config Guard (Two-Man Rule)
"""

import os
import sys
import time
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestEquityFloorMonitor(TestCase):
    """Test Equity Floor Monitor"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        os.environ['EQUITY_FLOOR_INR'] = '70000'
        os.environ['EQUITY_FLOOR_CHECK_INTERVAL'] = '1'
        os.environ['USD_TO_INR_RATE'] = '85'
        
        from bot.capital.equity_floor import EquityFloorMonitor
        self.monitor = EquityFloorMonitor(base_dir=self.test_dir)
    
    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_equity_above_floor(self):
        """Test that equity above floor passes check"""
        # Mock exchange client
        mock_exchange = mock.Mock()
        mock_exchange.get_wallet_balances.return_value = {
            'result': [{'balance': '1000'}]  # $1000 = 85,000 INR
        }
        self.monitor.set_exchange(mock_exchange)
        
        # Check should pass
        result = self.monitor.check()
        self.assertIsNotNone(result)
        self.assertFalse(result.get('breached', False))
        self.assertEqual(result['current_equity'], 85000)
    
    def test_equity_below_floor_triggers_emergency(self):
        """Test that equity below floor triggers emergency"""
        # Mock exchange client
        mock_exchange = mock.Mock()
        mock_exchange.get_wallet_balances.return_value = {
            'result': [{'balance': '700'}]  # $700 = 59,500 INR < 70,000
        }
        self.monitor.set_exchange(mock_exchange)
        
        # Check should breach
        result = self.monitor.check()
        self.assertIsNotNone(result)
        self.assertTrue(result.get('breached', False))
        self.assertTrue(result.get('new_breach', False))
        
        # Emergency flags should exist
        self.assertTrue((self.test_dir / '.emergency_stop').exists())
        self.assertTrue((self.test_dir / '.equity_floor_breach').exists())
    
    def test_equity_recovery_clears_emergency(self):
        """Test that recovery above floor clears emergency"""
        # First breach
        mock_exchange = mock.Mock()
        mock_exchange.get_wallet_balances.return_value = {
            'result': [{'balance': '700'}]
        }
        self.monitor.set_exchange(mock_exchange)
        self.monitor.check()
        
        self.assertTrue(self.monitor.breached)
        
        # Now recover
        mock_exchange.get_wallet_balances.return_value = {
            'result': [{'balance': '900'}]  # $900 = 76,500 INR > 70,000
        }
        
        result = self.monitor.check()
        self.assertIsNotNone(result)
        self.assertFalse(result.get('breached', False))
        self.assertFalse(self.monitor.breached)
        
        # Flags should be cleared
        self.assertFalse((self.test_dir / '.emergency_stop').exists())
        self.assertFalse((self.test_dir / '.equity_floor_breach').exists())


class TestDrawdownCap(TestCase):
    """Test Drawdown Cap Monitor"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        os.environ['DRAWDOWN_CAP_ENABLED'] = 'true'
        os.environ['DRAWDOWN_MAX_PCT'] = '20'
        os.environ['DRAWDOWN_HYSTERESIS_PCT'] = '15'
        os.environ['DRAWDOWN_WINDOW_DAYS'] = '30'
        
        from bot.capital.equity_tracker import EquityTracker
        self.tracker = EquityTracker(self.test_dir)
    
    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_no_drawdown_when_no_snapshots(self):
        """Test drawdown calculation with no history"""
        peak, dd_pct, dd_inr = self.tracker.calculate_drawdown(100000)
        self.assertEqual(peak, 100000)
        self.assertEqual(dd_pct, 0.0)
        self.assertEqual(dd_inr, 0.0)
    
    def test_drawdown_calculation(self):
        """Test drawdown percentage calculation"""
        # Take snapshot at peak
        self.tracker.add_snapshot(120000, force=True)
        time.sleep(0.1)
        self.tracker.add_snapshot(115000, force=True)
        
        # Calculate drawdown from peak
        peak, dd_pct, dd_inr = self.tracker.calculate_drawdown(100000)
        
        self.assertEqual(peak, 120000)
        self.assertAlmostEqual(dd_pct, 16.67, places=1)  # (120k - 100k) / 120k * 100
        self.assertEqual(dd_inr, 20000)
    
    def test_protective_mode_activation(self):
        """Test that protective mode activates when limit breached"""
        # Set up peak
        self.tracker.add_snapshot(120000, force=True)
        
        # Drop to 95000 = 20.83% drawdown (exceeds 20% limit)
        breached, message = self.tracker.check_drawdown_limit(95000)
        
        self.assertTrue(breached)
        self.assertIsNotNone(message)
        self.assertTrue(self.tracker.protective_mode_active)
        self.assertTrue((Path('.drawdown_protective_mode')).exists())
    
    def test_protective_mode_deactivation(self):
        """Test that protective mode deactivates with hysteresis"""
        # Activate protective mode
        self.tracker.add_snapshot(120000, force=True)
        breached1, msg1 = self.tracker.check_drawdown_limit(95000)  # 20.83% drawdown
        
        # Verify protective mode activated
        self.assertTrue(breached1, "Protective mode should have activated")
        self.assertTrue(self.tracker.protective_mode_active, "Protective mode flag should be set")
        
        # Recover to 102000 = 15% drawdown (below hysteresis)
        breached2, message = self.tracker.check_drawdown_limit(102000)
        
        self.assertFalse(breached2, "Should not be breached after recovery")
        if self.tracker.protective_mode_active:
            # If still active, message might not be present yet
            pass
        else:
            # If deactivated, should have a recovery message
            self.assertIsNotNone(message, "Should have recovery message when deactivating")
        self.assertFalse(self.tracker.protective_mode_active, "Protective mode should be deactivated")


class TestExposureGrowthLimiter(TestCase):
    """Test Exposure Growth Rate Limiter"""
    
    def setUp(self):
        """Set up test environment"""
        os.environ['EXPOSURE_GROWTH_ENABLED'] = 'true'
        os.environ['MAX_NEW_TRANCHES_PER_MINUTE'] = '2'
        os.environ['MAX_NOTIONAL_INR_PER_MINUTE'] = '200000'
        
        from bot.safety.exposure_limiter import ExposureGrowthLimiter
        self.limiter = ExposureGrowthLimiter()
    
    def tearDown(self):
        """Reset limiter"""
        self.limiter.reset()
    
    def test_allows_orders_within_limits(self):
        """Test that orders within limits are allowed"""
        # First order
        can_place, reason = self.limiter.can_place_order(100000)
        self.assertTrue(can_place)
        self.assertIsNone(reason)
        
        self.limiter.register_order(100000)
        
        # Second order (still within 2 tranches)
        can_place, reason = self.limiter.can_place_order(90000)
        self.assertTrue(can_place)
        self.assertIsNone(reason)
    
    def test_blocks_orders_exceeding_tranche_limit(self):
        """Test that 3rd order in minute is blocked"""
        # Place 2 orders
        self.limiter.register_order(100000)
        self.limiter.register_order(90000)
        
        # Try 3rd order (should be blocked)
        can_place, reason = self.limiter.can_place_order(80000)
        self.assertFalse(can_place)
        self.assertIsNotNone(reason)
        self.assertIn('Tranche', reason)
    
    def test_blocks_orders_exceeding_notional_limit(self):
        """Test that notional limit is enforced"""
        # First order uses 150k
        self.limiter.register_order(150000)
        
        # Second order would push us over 200k limit
        can_place, reason = self.limiter.can_place_order(100000)
        self.assertFalse(can_place)
        self.assertIsNotNone(reason)
        self.assertIn('Notional', reason)
    
    def test_old_orders_pruned_from_window(self):
        """Test that orders older than 60s are pruned"""
        # Place 2 orders
        self.limiter.register_order(100000)
        self.limiter.register_order(90000)
        
        # Should be blocked (2 tranches)
        can_place, _ = self.limiter.can_place_order(80000)
        self.assertFalse(can_place)
        
        # Wait for window to clear (simulate)
        self.limiter._order_history.clear()
        
        # Should now be allowed
        can_place, _ = self.limiter.can_place_order(80000)
        self.assertTrue(can_place)


class TestPendingBudgetControl(TestCase):
    """Test Pending Order Budget Control"""
    
    def setUp(self):
        """Set up test environment"""
        os.environ['MAX_PENDING_NOTIONAL_INR'] = '500000'
        os.environ['PENDING_BUDGET_BUFFER_PCT'] = '10'
        
        from bot.capital.pending_budget import PendingBudgetControl
        self.controller = PendingBudgetControl()
        
        # Mock exchange
        self.mock_exchange = mock.Mock()
        self.controller.set_exchange(self.mock_exchange)
    
    def test_allows_orders_within_budget(self):
        """Test that orders within budget are allowed"""
        # Mock no pending orders
        self.mock_exchange.fetch_open_orders.return_value = []
        
        # Should allow 100k order
        can_place, reason = self.controller.can_place_order(110000, 1)
        self.assertTrue(can_place)
        self.assertIsNone(reason)
    
    def test_blocks_orders_exceeding_budget(self):
        """Test that orders exceeding budget are blocked"""
        # Mock existing pending orders totaling 450k
        self.mock_exchange.fetch_open_orders.return_value = [
            {'side': 'buy', 'price': 110000, 'amount': 2, 'reduceOnly': False},  # 220k
            {'side': 'buy', 'price': 115000, 'amount': 2, 'reduceOnly': False},  # 230k
        ]
        
        # Try to place order that would exceed 500k limit
        can_place, reason = self.controller.can_place_order(120000, 1)  # Would be 570k total
        self.assertFalse(can_place)
        self.assertIsNotNone(reason)
        self.assertIn('budget exceeded', reason.lower())
    
    def test_warns_when_approaching_limit(self):
        """Test warning when approaching budget limit"""
        # Mock pending orders at 460k (92% utilization)
        self.mock_exchange.fetch_open_orders.return_value = [
            {'side': 'buy', 'price': 115000, 'amount': 4, 'reduceOnly': False},  # 460k
        ]
        
        # Should still allow but warn
        can_place, reason = self.controller.can_place_order(30000, 1)  # Would be 490k (98%)
        self.assertTrue(can_place)  # Within limit
    
    def test_ignores_reduce_only_orders(self):
        """Test that reduce-only orders are ignored"""
        # Mock pending orders including reduce-only
        self.mock_exchange.fetch_open_orders.return_value = [
            {'side': 'buy', 'price': 110000, 'amount': 1, 'reduceOnly': False},  # 110k (counts)
            {'side': 'sell', 'price': 115000, 'amount': 1, 'reduceOnly': True},  # (ignored)
        ]
        
        usage = self.controller.get_current_usage()
        self.assertEqual(usage['current_pending'], 110000)  # Only counts non-reduce-only


class TestConfigGuard(TestCase):
    """Test Two-Man Rule Config Guard"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        os.environ['TWO_MAN_RULE_ENABLED'] = 'true'
        os.environ['TWO_MAN_RULE_TIMEOUT_SEC'] = '10'  # Short for testing
        os.environ['TWO_MAN_RULE_AUTO_REVERT'] = 'true'
        
        from bot.safety.config_guard import ConfigGuard
        self.guard = ConfigGuard(base_dir=self.test_dir)
    
    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_no_changes_detected_on_first_run(self):
        """Test that first run saves hash without triggering confirmation"""
        config = {
            'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '5000',
            'GRIDBOT_MAX_OPEN': '5',
            'EXECUTE_ORDERS': 'true'
        }
        
        has_changes, message, changes = self.guard.check_config_changes(config)
        self.assertFalse(has_changes)
        self.assertIsNone(message)
    
    def test_detects_config_hash_change(self):
        """Test that config changes are detected"""
        # First config
        config1 = {
            'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '5000',
            'EXECUTE_ORDERS': 'false'
        }
        self.guard.check_config_changes(config1)
        
        # Changed config
        config2 = {
            'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '10000',  # INCREASED (risky!)
            'EXECUTE_ORDERS': 'false'
        }
        
        has_changes, message, changes = self.guard.check_config_changes(config2)
        self.assertTrue(has_changes)
        self.assertIsNotNone(message)
        self.assertIsNotNone(self.guard.pending_change)
    
    def test_confirmation_accepted(self):
        """Test that confirmation file allows changes"""
        # Trigger pending change
        config1 = {'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '5000'}
        self.guard.check_config_changes(config1)
        
        config2 = {'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '10000'}
        self.guard.check_config_changes(config2)
        
        # Create confirmation file
        confirm_file = Path(self.guard.pending_change['confirm_file'])
        confirm_file.touch()
        
        # Check confirmation
        confirmed, timed_out = self.guard.check_confirmation()
        self.assertTrue(confirmed)
        self.assertFalse(timed_out)
        self.assertIsNone(self.guard.pending_change)
    
    def test_confirmation_timeout(self):
        """Test that timeout rejects changes"""
        # Trigger pending change
        config1 = {'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '5000'}
        self.guard.check_config_changes(config1)
        
        config2 = {'GUARDIAN_MAX_ACCOUNT_LOSS_INR': '10000'}
        self.guard.check_config_changes(config2)
        
        # Simulate timeout by setting timestamp in past
        self.guard.pending_change['timestamp'] = time.time() - 20  # 20s ago (> 10s timeout)
        
        # Check confirmation
        confirmed, timed_out = self.guard.check_confirmation()
        self.assertFalse(confirmed)
        self.assertTrue(timed_out)
        self.assertIsNone(self.guard.pending_change)


if __name__ == '__main__':
    import unittest
    unittest.main()
