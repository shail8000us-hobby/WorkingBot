#!/usr/bin/env python3
"""
Test suite for monitoring system fixes
Tests the new get_recent_decisions() and get_recent_anomalies() methods
"""

import sys
import time
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.monitoring.pre_order_logger import PreOrderDecisionLogger
from bot.monitoring.anomaly_detection import AnomalyDetectionSystem


class TestPreOrderDecisionLogger(unittest.TestCase):
    """Test PreOrderDecisionLogger.get_recent_decisions()"""
    
    def setUp(self):
        """Set up test logger"""
        self.logger = PreOrderDecisionLogger()
    
    def test_get_recent_decisions_empty(self):
        """Test getting recent decisions when none exist"""
        decisions = self.logger.get_recent_decisions()
        self.assertEqual(decisions, [])
        self.assertIsInstance(decisions, list)
    
    def test_get_recent_decisions_single_buy(self):
        """Test getting recent decisions after one BUY decision"""
        # Log a BUY decision
        self.logger.log_buy_decision(
            target_price=100.0,
            current_price=110.0,
            price_age=5.0,
            grid_aligned=True,
            current_positions=5,
            max_positions=10,
            volatility_safe=True,
            grid_step=10.0
        )
        
        decisions = self.logger.get_recent_decisions()
        self.assertEqual(len(decisions), 1)
        
        # Verify decision structure
        decision = decisions[0]
        self.assertEqual(decision['type'], 'BUY')
        self.assertEqual(decision['target_price'], 100.0)
        self.assertEqual(decision['current_price'], 110.0)
        self.assertTrue(decision['approved'])
        self.assertIn('timestamp', decision)
    
    def test_get_recent_decisions_single_sell(self):
        """Test getting recent decisions after one SELL decision"""
        # Log a SELL decision
        self.logger.log_sell_decision(
            target_price=120.0,
            current_price=110.0,
            price_age=5.0,
            grid_aligned=True,
            current_positions=5,
            max_positions=10,
            volatility_safe=True,
            grid_step=10.0
        )
        
        decisions = self.logger.get_recent_decisions()
        self.assertEqual(len(decisions), 1)
        
        # Verify decision structure
        decision = decisions[0]
        self.assertEqual(decision['type'], 'SELL')
        self.assertEqual(decision['target_price'], 120.0)
        self.assertEqual(decision['current_price'], 110.0)
        self.assertTrue(decision['approved'])
    
    def test_get_recent_decisions_rejected(self):
        """Test getting recent decisions with rejections"""
        # Log a rejected BUY (no price)
        self.logger.log_buy_decision(
            target_price=100.0,
            current_price=None,  # No price
            price_age=None,
            grid_aligned=True,
            current_positions=5,
            max_positions=10,
            volatility_safe=True,
            grid_step=10.0,
            reasons=["Price unknown"]
        )
        
        decisions = self.logger.get_recent_decisions()
        self.assertEqual(len(decisions), 1)
        
        decision = decisions[0]
        self.assertFalse(decision['approved'])
        self.assertIsNotNone(decision['reasons'])
        self.assertEqual(decision['reasons'], ["Price unknown"])
    
    def test_get_recent_decisions_multiple(self):
        """Test getting multiple recent decisions"""
        # Log 5 decisions
        for i in range(5):
            self.logger.log_buy_decision(
                target_price=100.0 + i,
                current_price=110.0,
                price_age=5.0,
                grid_aligned=True,
                current_positions=i,
                max_positions=10,
                volatility_safe=True,
                grid_step=10.0
            )
        
        decisions = self.logger.get_recent_decisions()
        self.assertEqual(len(decisions), 5)
        
        # Verify chronological order
        for i, decision in enumerate(decisions):
            self.assertEqual(decision['target_price'], 100.0 + i)
    
    def test_get_recent_decisions_limit(self):
        """Test limit parameter"""
        # Log 10 decisions
        for i in range(10):
            self.logger.log_buy_decision(
                target_price=100.0 + i,
                current_price=110.0,
                price_age=5.0,
                grid_aligned=True,
                current_positions=i,
                max_positions=20,
                volatility_safe=True,
                grid_step=10.0
            )
        
        # Get only last 3
        decisions = self.logger.get_recent_decisions(limit=3)
        self.assertEqual(len(decisions), 3)
        
        # Verify we got the last 3
        self.assertEqual(decisions[0]['target_price'], 107.0)
        self.assertEqual(decisions[1]['target_price'], 108.0)
        self.assertEqual(decisions[2]['target_price'], 109.0)
    
    def test_get_recent_decisions_ring_buffer(self):
        """Test that ring buffer limits to 50 decisions"""
        # Log 60 decisions (exceeds maxlen=50)
        for i in range(60):
            self.logger.log_buy_decision(
                target_price=100.0 + i,
                current_price=110.0,
                price_age=5.0,
                grid_aligned=True,
                current_positions=0,
                max_positions=100,
                volatility_safe=True,
                grid_step=10.0
            )
        
        decisions = self.logger.get_recent_decisions()
        
        # Should only have last 50
        self.assertEqual(len(decisions), 50)
        
        # Should start from decision 10 (0-9 were dropped)
        self.assertEqual(decisions[0]['target_price'], 110.0)
        self.assertEqual(decisions[-1]['target_price'], 159.0)
    
    def test_statistics_unchanged(self):
        """Test that statistics methods still work"""
        # Log some decisions
        self.logger.log_buy_decision(
            target_price=100.0,
            current_price=110.0,
            price_age=5.0,
            grid_aligned=True,
            current_positions=0,
            max_positions=10,
            volatility_safe=True,
            grid_step=10.0
        )
        
        stats = self.logger.get_statistics()
        self.assertEqual(stats['total_decisions'], 1)
        self.assertEqual(stats['approved'], 1)
        self.assertEqual(stats['rejected'], 0)


class TestAnomalyDetectionSystem(unittest.TestCase):
    """Test AnomalyDetectionSystem.get_recent_anomalies()"""
    
    def setUp(self):
        """Set up test anomaly detector"""
        self.detector = AnomalyDetectionSystem()
    
    def test_get_recent_anomalies_empty(self):
        """Test getting recent anomalies when none detected"""
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(anomalies, [])
        self.assertIsInstance(anomalies, list)
    
    def test_get_recent_anomalies_order_without_tp(self):
        """Test anomaly detection for orders without TPs"""
        # Track 3 filled orders without TPs
        for i in range(3):
            order_id = f"order_{i}"
            self.detector.track_order_placement(order_id, 100.0, "BUY")
            self.detector.track_order_fill(order_id)
        
        # Wait for grace period to expire
        time.sleep(11)
        
        # Run check
        anomaly = self.detector.check_orders_without_tp()
        
        # Should detect anomaly
        self.assertIsNotNone(anomaly)
        
        # Check stored anomalies
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(len(anomalies), 1)
        
        anomaly = anomalies[0]
        self.assertEqual(anomaly['type'], 'MULTIPLE_ORDERS_WITHOUT_TP')
        self.assertEqual(anomaly['severity'], 'CRITICAL')
        self.assertGreaterEqual(anomaly['count'], 3)
    
    def test_get_recent_anomalies_price_jump(self):
        """Test anomaly detection for price jumps"""
        # Simulate price jump (need to populate price_history first)
        self.detector.price_history.append({'price': 100.0, 'timestamp': time.time() - 1})
        self.detector.price_history.append({'price': 110.0, 'timestamp': time.time()})
        
        anomaly = self.detector.check_price_jump(110.0, 100.0)
        
        # Should detect anomaly (10% jump)
        self.assertIsNotNone(anomaly)
        
        # Check stored anomalies
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(len(anomalies), 1)
        
        anomaly = anomalies[0]
        self.assertEqual(anomaly['type'], 'ABNORMAL_PRICE_JUMP')
        self.assertEqual(anomaly['severity'], 'HIGH')
    
    def test_get_recent_anomalies_order_rate(self):
        """Test anomaly detection for excessive order rate"""
        # Track 10 orders in quick succession
        now = time.time()
        for i in range(10):
            self.detector.order_timestamps.append(now + i)
        
        # Check rate
        anomaly = self.detector.check_order_placement_rate()
        
        # Should detect anomaly
        self.assertIsNotNone(anomaly)
        
        # Check stored anomalies
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(len(anomalies), 1)
        
        anomaly = anomalies[0]
        self.assertEqual(anomaly['type'], 'EXCESSIVE_ORDER_RATE')
        self.assertEqual(anomaly['severity'], 'MEDIUM')
    
    def test_get_recent_anomalies_websocket_stale(self):
        """Test anomaly detection for stale WebSocket"""
        # Set last update to 2 minutes ago
        last_update = time.time() - 120
        
        # Check staleness
        anomaly = self.detector.check_websocket_staleness(last_update)
        
        # Should detect anomaly
        self.assertIsNotNone(anomaly)
        
        # Check stored anomalies
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(len(anomalies), 1)
        
        anomaly = anomalies[0]
        self.assertEqual(anomaly['type'], 'WEBSOCKET_STALE')
        self.assertEqual(anomaly['severity'], 'CRITICAL')
    
    def test_get_recent_anomalies_multiple(self):
        """Test multiple anomalies"""
        # Create price jump (need to populate history)
        self.detector.price_history.append({'price': 100.0, 'timestamp': time.time() - 1})
        self.detector.price_history.append({'price': 110.0, 'timestamp': time.time()})
        self.detector.check_price_jump(110.0, 100.0)
        
        # Create excessive order rate
        now = time.time()
        for i in range(10):
            self.detector.order_timestamps.append(now + i)
        self.detector.check_order_placement_rate()
        
        # Should have 2 anomalies
        anomalies = self.detector.get_recent_anomalies()
        self.assertEqual(len(anomalies), 2)
    
    def test_get_recent_anomalies_limit(self):
        """Test limit parameter"""
        # Create 5 price jumps
        for i in range(5):
            self.detector.check_price_jump(100.0 + i * 10, 100.0 + (i - 1) * 10)
        
        # Get only last 2
        anomalies = self.detector.get_recent_anomalies(limit=2)
        self.assertLessEqual(len(anomalies), 2)
    
    def test_get_recent_anomalies_ring_buffer(self):
        """Test that ring buffer limits to 100 anomalies"""
        # Create 110 anomalies (exceeds maxlen=100)
        for i in range(110):
            # Create price jumps
            self.detector.detected_anomalies.append({
                'type': 'TEST',
                'number': i,
                'timestamp': time.time()
            })
        
        # Request all anomalies (no limit)
        anomalies = self.detector.get_recent_anomalies(limit=200)
        
        # Should only have last 100 (ring buffer max)
        self.assertEqual(len(anomalies), 100)
        
        # Should start from anomaly 10 (0-9 were dropped)
        self.assertEqual(anomalies[0]['number'], 10)
        self.assertEqual(anomalies[-1]['number'], 109)
    
    def test_get_recent_anomalies_with_limit_50(self):
        """Test with limit parameter smaller than buffer"""
        # Create only 60 anomalies
        for i in range(60):
            self.detector.detected_anomalies.append({
                'type': 'TEST',
                'number': i,
                'timestamp': time.time()
            })
        
        # Request last 50
        anomalies = self.detector.get_recent_anomalies(limit=50)
        
        # Should get last 50
        self.assertEqual(len(anomalies), 50)
        self.assertEqual(anomalies[0]['number'], 10)
        self.assertEqual(anomalies[-1]['number'], 59)
    
    def test_statistics_unchanged(self):
        """Test that statistics methods still work"""
        # Track an order
        self.detector.track_order_placement("order_1", 100.0, "BUY")
        
        stats = self.detector.get_statistics()
        self.assertEqual(stats['recent_orders_tracked'], 1)
        self.assertEqual(stats['recent_tps_tracked'], 0)


class TestMonitoringIntegration(unittest.TestCase):
    """Test integration between monitoring components"""
    
    def test_monitoring_loop_compatibility(self):
        """Test that methods work as expected in monitoring loop"""
        logger = PreOrderDecisionLogger()
        detector = AnomalyDetectionSystem()
        
        # Simulate monitoring loop calls
        decisions = logger.get_recent_decisions() if logger else []
        anomalies = detector.get_recent_anomalies() if detector else []
        
        self.assertIsInstance(decisions, list)
        self.assertIsInstance(anomalies, list)
    
    def test_monitoring_loop_with_data(self):
        """Test monitoring loop with actual data"""
        logger = PreOrderDecisionLogger()
        detector = AnomalyDetectionSystem()
        
        # Log some decisions
        logger.log_buy_decision(
            target_price=100.0,
            current_price=110.0,
            price_age=5.0,
            grid_aligned=True,
            current_positions=0,
            max_positions=10,
            volatility_safe=True,
            grid_step=10.0
        )
        
        # Track some orders
        detector.track_order_placement("order_1", 100.0, "BUY")
        
        # Get monitoring data (as in async_gridbot._monitoring_loop)
        monitoring_data = {
            "recent_decisions": logger.get_recent_decisions() if logger else [],
            "anomalies": detector.get_recent_anomalies() if detector else []
        }
        
        self.assertEqual(len(monitoring_data['recent_decisions']), 1)
        self.assertEqual(len(monitoring_data['anomalies']), 0)
        
        # Verify structure
        self.assertIn('type', monitoring_data['recent_decisions'][0])
        self.assertIn('approved', monitoring_data['recent_decisions'][0])


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPreOrderDecisionLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestAnomalyDetectionSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestMonitoringIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
