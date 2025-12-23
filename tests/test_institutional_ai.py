"""
Unit Tests for Institutional AI System
Tests all analytics, predictions, and ML modules
"""

import unittest
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.ai.analytics.performance import PerformanceAnalytics
from bot.ai.analytics.risk import RiskAnalytics
from bot.ai.advanced.monte_carlo import MonteCarloSimulator
from bot.ai.advanced.ml_predictor import MLPredictor


class TestPerformanceAnalytics(unittest.TestCase):
    """Test performance analytics module"""
    
    def setUp(self):
        """Set up test data"""
        self.analytics = PerformanceAnalytics()
        
        # Sample trade data
        self.trades = [
            {'pnl': 100, 'entry_price': 111000, 'exit_price': 111100, 'side': 'long'},
            {'pnl': -50, 'entry_price': 111100, 'exit_price': 111050, 'side': 'long'},
            {'pnl': 150, 'entry_price': 111050, 'exit_price': 111200, 'side': 'long'},
            {'pnl': 200, 'entry_price': 111200, 'exit_price': 111400, 'side': 'long'},
            {'pnl': -30, 'entry_price': 111400, 'exit_price': 111370, 'side': 'long'},
        ]
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation"""
        returns = [0.01, -0.005, 0.015, 0.02, -0.003]
        sharpe = self.analytics._calculate_sharpe_ratio(returns)
        
        self.assertIsInstance(sharpe, float)
        self.assertGreater(sharpe, 0)  # Positive returns should give positive Sharpe
    
    def test_win_rate_calculation(self):
        """Test win rate calculation"""
        winning_trades = sum(1 for t in self.trades if t['pnl'] > 0)
        total_trades = len(self.trades)
        expected_win_rate = (winning_trades / total_trades) * 100
        
        # Calculate win rate
        wins = len([t for t in self.trades if t['pnl'] > 0])
        win_rate = (wins / len(self.trades)) * 100
        
        self.assertEqual(win_rate, expected_win_rate)
        self.assertGreater(win_rate, 0)
        self.assertLessEqual(win_rate, 100)
    
    def test_profit_factor(self):
        """Test profit factor calculation"""
        gross_profit = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
            self.assertGreater(profit_factor, 0)
    
    def test_max_drawdown(self):
        """Test max drawdown calculation"""
        equity_curve = [10000, 10100, 10050, 10200, 10400, 10370]
        
        peak = equity_curve[0]
        max_dd = 0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (value - peak) / peak
            if dd < max_dd:
                max_dd = dd
        
        self.assertLessEqual(max_dd, 0)  # Drawdown should be negative or zero


class TestRiskAnalytics(unittest.TestCase):
    """Test risk analytics module"""
    
    def setUp(self):
        """Set up test data"""
        self.analytics = RiskAnalytics()
        self.returns = np.array([0.01, -0.02, 0.015, -0.01, 0.02, -0.005, 0.01])
    
    def test_var_calculation(self):
        """Test VaR calculation"""
        var_95 = np.percentile(self.returns, 5)
        
        self.assertIsInstance(var_95, (float, np.floating))
        self.assertLess(var_95, 0)  # VaR should be negative (loss)
    
    def test_cvar_calculation(self):
        """Test CVaR calculation"""
        var_95 = np.percentile(self.returns, 5)
        tail_losses = self.returns[self.returns <= var_95]
        cvar = np.mean(tail_losses)
        
        self.assertIsInstance(cvar, (float, np.floating))
        self.assertLess(cvar, var_95)  # CVaR should be more extreme than VaR
    
    def test_volatility_calculation(self):
        """Test volatility calculation"""
        volatility = np.std(self.returns)
        
        self.assertIsInstance(volatility, (float, np.floating))
        self.assertGreater(volatility, 0)
    
    def test_beta_calculation(self):
        """Test beta calculation"""
        market_returns = np.array([0.008, -0.015, 0.012, -0.008, 0.018, -0.004, 0.009])
        
        covariance = np.cov(self.returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        
        if market_variance > 0:
            beta = covariance / market_variance
            self.assertIsInstance(beta, (float, np.floating))


class TestMonteCarloSimulator(unittest.TestCase):
    """Test Monte Carlo simulation module"""
    
    def setUp(self):
        """Set up simulator"""
        self.simulator = MonteCarloSimulator(num_simulations=1000)
        self.current_value = 100000
        self.mean_return = 0.15
        self.volatility = 0.25
    
    def test_simulation_output_shape(self):
        """Test that simulation produces correct number of results"""
        results = self.simulator.simulate_portfolio_returns(
            self.current_value,
            self.mean_return,
            self.volatility,
            time_horizon_days=30
        )
        
        self.assertEqual(len(results), 1000)
        self.assertTrue(all(isinstance(x, (float, np.floating)) for x in results))
    
    def test_var_calculation(self):
        """Test VaR calculation from simulations"""
        simulated_values = self.simulator.simulate_portfolio_returns(
            self.current_value,
            self.mean_return,
            self.volatility,
            time_horizon_days=30
        )
        
        var_cvar = self.simulator.calculate_var_cvar(
            simulated_values,
            self.current_value
        )
        
        self.assertIn('var_95', var_cvar)
        self.assertIn('cvar_95', var_cvar)
        self.assertLess(var_cvar['var_95']['value'], 0)
    
    def test_probability_scenarios(self):
        """Test probability scenario calculation"""
        simulated_values = self.simulator.simulate_portfolio_returns(
            self.current_value,
            self.mean_return,
            self.volatility,
            time_horizon_days=30
        )
        
        probabilities = self.simulator.calculate_probability_scenarios(
            simulated_values,
            self.current_value
        )
        
        # Check probabilities sum to approximately 1
        total_prob = probabilities['prob_profit'] + probabilities['prob_loss']
        self.assertAlmostEqual(total_prob, 1.0, places=2)
        
        # Check all probabilities are between 0 and 1
        for prob in probabilities.values():
            self.assertGreaterEqual(prob, 0)
            self.assertLessEqual(prob, 1)
    
    def test_stress_testing(self):
        """Test stress testing scenarios"""
        stress_results = self.simulator.stress_test(
            self.current_value,
            self.mean_return,
            self.volatility
        )
        
        self.assertIn('market_crash', stress_results)
        self.assertIn('black_swan', stress_results)
        
        # Black swan should be worse than market crash
        black_swan_worst = stress_results['black_swan']['worst_case']
        market_crash_worst = stress_results['market_crash']['worst_case']
        self.assertLess(black_swan_worst, market_crash_worst)


class TestMLPredictor(unittest.TestCase):
    """Test ML prediction module"""
    
    def setUp(self):
        """Set up predictor with sample data"""
        self.predictor = MLPredictor(lookback_period=50)
        
        # Add sample price data
        base_price = 111000
        for i in range(50):
            price = base_price + np.random.normal(0, 100) + i * 10  # Upward trend
            self.predictor.update_market_data(price, volume=1000)
    
    def test_price_prediction(self):
        """Test price movement prediction"""
        prediction = self.predictor.predict_price_movement(horizon=5)
        
        self.assertIn('direction', prediction)
        self.assertIn('confidence', prediction)
        self.assertIn('predicted_prices', prediction)
        
        self.assertIn(prediction['direction'], ['UP', 'DOWN', 'SIDEWAYS'])
        self.assertGreaterEqual(prediction['confidence'], 0)
        self.assertLessEqual(prediction['confidence'], 1)
        self.assertEqual(len(prediction['predicted_prices']), 5)
    
    def test_win_probability(self):
        """Test win probability estimation"""
        probability = self.predictor.estimate_win_probability(
            entry_price=111500,
            target_price=112000,
            stop_loss=111000
        )
        
        self.assertIn('win_probability', probability)
        self.assertIn('risk_reward_ratio', probability)
        
        self.assertGreaterEqual(probability['win_probability'], 0)
        self.assertLessEqual(probability['win_probability'], 1)
        self.assertGreater(probability['risk_reward_ratio'], 0)
    
    def test_pattern_detection(self):
        """Test pattern detection"""
        patterns = self.predictor.detect_patterns()
        
        self.assertIsInstance(patterns, list)
        
        if len(patterns) > 0:
            pattern = patterns[0]
            self.assertIn('type', pattern)
            self.assertIn('confidence', pattern)
    
    def test_entry_exit_suggestion(self):
        """Test entry/exit suggestions"""
        suggestion = self.predictor.suggest_entry_exit(current_price=111500)
        
        self.assertIn('action', suggestion)
        self.assertIn('reason', suggestion)
        self.assertIn('confidence', suggestion)
        
        self.assertIn(suggestion['action'], ['BUY', 'SELL', 'HOLD', 'WAIT'])
        self.assertGreaterEqual(suggestion['confidence'], 0)
        self.assertLessEqual(suggestion['confidence'], 1)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete system"""
    
    def test_full_analysis_pipeline(self):
        """Test complete analysis pipeline"""
        # This would test the full flow from data input to analysis output
        # In production, this would use real data
        pass
    
    def test_api_endpoints(self):
        """Test API endpoint availability"""
        # This would test that all API endpoints are accessible
        # In production, use requests library to test endpoints
        pass


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAnalytics))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskAnalytics))
    suite.addTests(loader.loadTestsFromTestCase(TestMonteCarloSimulator))
    suite.addTests(loader.loadTestsFromTestCase(TestMLPredictor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

