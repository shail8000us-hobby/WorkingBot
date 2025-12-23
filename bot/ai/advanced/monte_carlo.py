"""
Monte Carlo Simulation Module
Performs advanced risk analysis using Monte Carlo methods
"""

import numpy as np
from typing import Dict, List, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """
    Monte Carlo simulation for portfolio risk analysis
    
    Features:
    - VaR calculation with confidence intervals
    - Portfolio value distribution
    - Probability scenarios
    - Stress testing
    """
    
    def __init__(self, num_simulations: int = 10000):
        """
        Initialize Monte Carlo simulator
        
        Args:
            num_simulations: Number of Monte Carlo simulations to run
        """
        self.num_simulations = num_simulations
        logger.info(f"MonteCarloSimulator initialized with {num_simulations} simulations")
    
    def simulate_portfolio_returns(
        self,
        current_value: float,
        mean_return: float,
        volatility: float,
        time_horizon_days: int = 30
    ) -> np.ndarray:
        """
        Simulate portfolio returns using geometric Brownian motion
        
        Args:
            current_value: Current portfolio value
            mean_return: Expected daily return (annualized)
            volatility: Return volatility (annualized)
            time_horizon_days: Simulation time horizon in days
            
        Returns:
            Array of simulated portfolio values
        """
        # Convert annualized metrics to daily
        daily_return = mean_return / 252  # 252 trading days
        daily_volatility = volatility / np.sqrt(252)
        
        # Generate random returns
        random_returns = np.random.normal(
            daily_return,
            daily_volatility,
            (self.num_simulations, time_horizon_days)
        )
        
        # Calculate cumulative returns
        cumulative_returns = np.exp(np.cumsum(random_returns, axis=1))
        
        # Calculate final portfolio values
        final_values = current_value * cumulative_returns[:, -1]
        
        return final_values
    
    def calculate_var_cvar(
        self,
        simulated_values: np.ndarray,
        current_value: float,
        confidence_levels: List[float] = [0.95, 0.99]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR) from simulations
        
        Args:
            simulated_values: Array of simulated portfolio values
            current_value: Current portfolio value
            confidence_levels: List of confidence levels (e.g., 0.95, 0.99)
            
        Returns:
            Dictionary with VaR and CVaR for each confidence level
        """
        results = {}
        
        # Calculate returns
        returns = (simulated_values - current_value) / current_value
        
        for confidence in confidence_levels:
            # VaR: percentile of loss distribution
            var_percentile = (1 - confidence) * 100
            var_return = np.percentile(returns, var_percentile)
            var_value = var_return * current_value
            
            # CVaR: expected loss beyond VaR
            tail_losses = returns[returns <= var_return]
            cvar_return = np.mean(tail_losses) if len(tail_losses) > 0 else var_return
            cvar_value = cvar_return * current_value
            
            confidence_pct = int(confidence * 100)
            results[f"var_{confidence_pct}"] = {
                "value": float(var_value),
                "return_pct": float(var_return * 100),
                "confidence": confidence
            }
            results[f"cvar_{confidence_pct}"] = {
                "value": float(cvar_value),
                "return_pct": float(cvar_return * 100),
                "confidence": confidence
            }
        
        return results
    
    def calculate_probability_scenarios(
        self,
        simulated_values: np.ndarray,
        current_value: float
    ) -> Dict[str, float]:
        """
        Calculate probability of various profit/loss scenarios
        
        Args:
            simulated_values: Array of simulated portfolio values
            current_value: Current portfolio value
            
        Returns:
            Dictionary with probability of different scenarios
        """
        returns = (simulated_values - current_value) / current_value
        
        scenarios = {
            "prob_profit": float(np.sum(returns > 0) / len(returns)),
            "prob_loss": float(np.sum(returns < 0) / len(returns)),
            "prob_loss_gt_5pct": float(np.sum(returns < -0.05) / len(returns)),
            "prob_loss_gt_10pct": float(np.sum(returns < -0.10) / len(returns)),
            "prob_loss_gt_20pct": float(np.sum(returns < -0.20) / len(returns)),
            "prob_profit_gt_5pct": float(np.sum(returns > 0.05) / len(returns)),
            "prob_profit_gt_10pct": float(np.sum(returns > 0.10) / len(returns)),
            "prob_profit_gt_20pct": float(np.sum(returns > 0.20) / len(returns)),
        }
        
        return scenarios
    
    def calculate_distribution_stats(
        self,
        simulated_values: np.ndarray,
        current_value: float
    ) -> Dict[str, float]:
        """
        Calculate statistical properties of the simulated distribution
        
        Args:
            simulated_values: Array of simulated portfolio values
            current_value: Current portfolio value
            
        Returns:
            Dictionary with distribution statistics
        """
        returns = (simulated_values - current_value) / current_value
        
        stats = {
            "mean_return": float(np.mean(returns)),
            "median_return": float(np.median(returns)),
            "std_return": float(np.std(returns)),
            "min_return": float(np.min(returns)),
            "max_return": float(np.max(returns)),
            "skewness": float(self._calculate_skewness(returns)),
            "kurtosis": float(self._calculate_kurtosis(returns)),
            "mean_value": float(np.mean(simulated_values)),
            "median_value": float(np.median(simulated_values)),
            "percentile_5": float(np.percentile(simulated_values, 5)),
            "percentile_25": float(np.percentile(simulated_values, 25)),
            "percentile_75": float(np.percentile(simulated_values, 75)),
            "percentile_95": float(np.percentile(simulated_values, 95)),
        }
        
        return stats
    
    def stress_test(
        self,
        current_value: float,
        mean_return: float,
        volatility: float,
        scenarios: List[Dict[str, float]] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Perform stress testing under extreme market conditions
        
        Args:
            current_value: Current portfolio value
            mean_return: Expected return
            volatility: Return volatility
            scenarios: List of stress scenarios (optional)
            
        Returns:
            Dictionary with stress test results
        """
        if scenarios is None:
            # Default stress scenarios
            scenarios = [
                {"name": "market_crash", "return_shock": -0.20, "vol_multiplier": 2.0},
                {"name": "high_volatility", "return_shock": 0.0, "vol_multiplier": 3.0},
                {"name": "black_swan", "return_shock": -0.30, "vol_multiplier": 4.0},
                {"name": "bull_market", "return_shock": 0.15, "vol_multiplier": 0.5},
            ]
        
        results = {}
        
        for scenario in scenarios:
            name = scenario["name"]
            return_shock = scenario.get("return_shock", 0.0)
            vol_multiplier = scenario.get("vol_multiplier", 1.0)
            
            # Apply stress scenario
            stressed_return = mean_return + return_shock
            stressed_volatility = volatility * vol_multiplier
            
            # Run simulation
            simulated_values = self.simulate_portfolio_returns(
                current_value,
                stressed_return,
                stressed_volatility,
                time_horizon_days=30
            )
            
            # Calculate metrics
            returns = (simulated_values - current_value) / current_value
            var_95 = np.percentile(returns, 5) * current_value
            
            results[name] = {
                "mean_return": float(np.mean(returns)),
                "worst_case": float(np.min(returns)),
                "best_case": float(np.max(returns)),
                "var_95": float(var_95),
                "prob_loss": float(np.sum(returns < 0) / len(returns)),
                "return_shock": return_shock,
                "vol_multiplier": vol_multiplier
            }
        
        return results
    
    def run_full_analysis(
        self,
        current_value: float,
        mean_return: float,
        volatility: float,
        time_horizon_days: int = 30
    ) -> Dict:
        """
        Run complete Monte Carlo analysis
        
        Args:
            current_value: Current portfolio value
            mean_return: Expected return (annualized)
            volatility: Return volatility (annualized)
            time_horizon_days: Simulation time horizon
            
        Returns:
            Complete analysis results
        """
        logger.info(f"Running Monte Carlo analysis: {self.num_simulations} simulations")
        
        # Run simulations
        simulated_values = self.simulate_portfolio_returns(
            current_value,
            mean_return,
            volatility,
            time_horizon_days
        )
        
        # Calculate all metrics
        var_cvar = self.calculate_var_cvar(simulated_values, current_value)
        probabilities = self.calculate_probability_scenarios(simulated_values, current_value)
        distribution = self.calculate_distribution_stats(simulated_values, current_value)
        stress_tests = self.stress_test(current_value, mean_return, volatility)
        
        results = {
            "simulation_params": {
                "num_simulations": self.num_simulations,
                "current_value": current_value,
                "mean_return": mean_return,
                "volatility": volatility,
                "time_horizon_days": time_horizon_days,
                "timestamp": datetime.now().isoformat()
            },
            "var_cvar": var_cvar,
            "probabilities": probabilities,
            "distribution": distribution,
            "stress_tests": stress_tests,
            "summary": self._generate_summary(
                var_cvar,
                probabilities,
                distribution,
                stress_tests
            )
        }
        
        logger.info("Monte Carlo analysis complete")
        return results
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """Calculate skewness of distribution"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        return np.mean(((data - mean) / std) ** 3)
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """Calculate kurtosis of distribution"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def _generate_summary(
        self,
        var_cvar: Dict,
        probabilities: Dict,
        distribution: Dict,
        stress_tests: Dict
    ) -> Dict[str, str]:
        """Generate human-readable summary"""
        summary = {}
        
        # VaR summary
        var_95 = var_cvar.get("var_95", {}).get("value", 0)
        summary["var_95_summary"] = (
            f"95% confident that losses won't exceed ₹{abs(var_95):,.0f} "
            f"({var_cvar.get('var_95', {}).get('return_pct', 0):.1f}%)"
        )
        
        # Probability summary
        prob_profit = probabilities.get("prob_profit", 0) * 100
        summary["probability_summary"] = (
            f"{prob_profit:.1f}% chance of profit, "
            f"{probabilities.get('prob_loss_gt_10pct', 0) * 100:.1f}% chance of >10% loss"
        )
        
        # Distribution summary
        mean_return = distribution.get("mean_return", 0) * 100
        std_return = distribution.get("std_return", 0) * 100
        summary["distribution_summary"] = (
            f"Expected return: {mean_return:.1f}% ± {std_return:.1f}%"
        )
        
        # Stress test summary
        worst_scenario = min(
            stress_tests.values(),
            key=lambda x: x.get("worst_case", 0)
        )
        summary["stress_test_summary"] = (
            f"Worst stress scenario: {worst_scenario.get('worst_case', 0) * 100:.1f}% loss"
        )
        
        return summary


# Singleton instance
_monte_carlo_simulator = None


def get_monte_carlo_simulator(num_simulations: int = 10000) -> MonteCarloSimulator:
    """Get singleton Monte Carlo simulator instance"""
    global _monte_carlo_simulator
    if _monte_carlo_simulator is None:
        _monte_carlo_simulator = MonteCarloSimulator(num_simulations)
    return _monte_carlo_simulator

