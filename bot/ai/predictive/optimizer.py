"""
Institutional-Grade Grid Optimization Module

This module optimizes grid trading parameters using:
- Kelly Criterion for position sizing
- Optimal grid step calculation based on volatility
- Dynamic rebalancing recommendations
- Risk-adjusted parameter optimization

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import json


class GridOptimizer:
    """
    Professional-grade grid parameter optimization engine
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the grid optimizer"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.cache = {}
        self.cache_ttl = 300
        self.last_cache_time = None
    
    # =========================================================================
    # KELLY CRITERION
    # =========================================================================
    
    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing
        
        Formula: f = (p × b - q) / b
        where:
        - f = fraction of capital to risk
        - p = probability of winning (win rate)
        - q = probability of losing (1 - win rate)
        - b = ratio of win to loss (avg_win / avg_loss)
        
        Args:
            win_rate: Win rate as decimal (e.g., 0.65 for 65%)
            avg_win: Average win amount
            avg_loss: Average loss amount
        
        Returns:
            Kelly fraction (0 to 1, typically use 0.25-0.5 of full Kelly)
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        b = avg_win / avg_loss  # Win/loss ratio
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (p * b - q) / b
        
        # Ensure Kelly fraction is between 0 and 1
        kelly_fraction = max(0, min(kelly_fraction, 1))
        
        # Use fractional Kelly (25% of full Kelly for safety)
        conservative_kelly = kelly_fraction * 0.25
        
        return round(conservative_kelly, 4)
    
    def calculate_optimal_position_size(
        self,
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Calculate optimal position size using Kelly Criterion
        
        Args:
            capital: Total trading capital
            win_rate: Historical win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            current_price: Current market price
        
        Returns:
            Dictionary with optimal position size and metrics
        """
        kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
        
        # Calculate capital to risk
        capital_to_risk = capital * kelly_fraction
        
        # Calculate number of contracts/lots
        # Assuming each contract is worth current_price
        optimal_size = int(capital_to_risk / current_price)
        
        # Ensure at least 1 lot
        optimal_size = max(1, optimal_size)
        
        return {
            'kelly_fraction': kelly_fraction,
            'capital_to_risk': round(capital_to_risk, 2),
            'optimal_size': optimal_size,
            'position_value': round(optimal_size * current_price, 2),
            'risk_percentage': round(kelly_fraction * 100, 2)
        }
    
    # =========================================================================
    # GRID STEP OPTIMIZATION
    # =========================================================================
    
    def calculate_optimal_grid_step(
        self,
        current_price: float,
        volatility: float,
        capital: float,
        risk_tolerance: str = 'medium'
    ) -> Dict[str, Any]:
        """
        Calculate optimal grid step based on volatility and capital
        
        Args:
            current_price: Current market price
            volatility: Market volatility (0-1)
            capital: Trading capital
            risk_tolerance: 'low', 'medium', or 'high'
        
        Returns:
            Dictionary with optimal grid parameters
        """
        # Base grid step as percentage of price
        # Higher volatility = wider grid step
        
        risk_multipliers = {
            'low': 0.8,
            'medium': 1.0,
            'high': 1.2
        }
        
        multiplier = risk_multipliers.get(risk_tolerance, 1.0)
        
        # Calculate grid step as percentage
        # Base: 0.5% for low vol, up to 2% for high vol
        base_pct = 0.005 + (volatility * 0.015)
        grid_step_pct = base_pct * multiplier
        
        # Calculate actual grid step in price
        grid_step = current_price * grid_step_pct
        
        # Round to nearest 100 for cleaner numbers
        grid_step = round(grid_step / 100) * 100
        grid_step = max(100, grid_step)  # Minimum 100
        
        # Calculate number of grid levels based on capital
        # Assume each level requires capital / 10
        capital_per_level = capital / 10
        max_levels = int(capital / capital_per_level)
        max_levels = min(max_levels, 20)  # Cap at 20 levels
        
        return {
            'optimal_grid_step': grid_step,
            'grid_step_percentage': round(grid_step_pct * 100, 2),
            'recommended_levels': max_levels,
            'grid_range': round(grid_step * max_levels, 2),
            'upper_bound': round(current_price + (grid_step * max_levels / 2), 2),
            'lower_bound': round(current_price - (grid_step * max_levels / 2), 2)
        }
    
    def calculate_optimal_take_profit(
        self,
        grid_step: float,
        win_rate: float,
        volatility: float
    ) -> Dict[str, Any]:
        """
        Calculate optimal take profit distance
        
        Args:
            grid_step: Current grid step
            win_rate: Historical win rate
            volatility: Market volatility
        
        Returns:
            Dictionary with optimal TP parameters
        """
        # Base TP is 1x grid step
        # Adjust based on win rate and volatility
        
        # If win rate is high, can use tighter TP
        # If volatility is high, use wider TP
        
        win_rate_factor = 1.0 - (win_rate - 0.5) * 0.5  # 0.75 to 1.25
        volatility_factor = 1.0 + volatility * 0.5  # 1.0 to 1.5
        
        optimal_tp_multiplier = win_rate_factor * volatility_factor
        optimal_tp_multiplier = max(0.8, min(optimal_tp_multiplier, 2.0))
        
        optimal_tp = grid_step * optimal_tp_multiplier
        
        return {
            'optimal_tp_distance': round(optimal_tp, 2),
            'tp_multiplier': round(optimal_tp_multiplier, 2),
            'risk_reward_ratio': round(optimal_tp_multiplier, 2)
        }
    
    # =========================================================================
    # DYNAMIC REBALANCING
    # =========================================================================
    
    def should_rebalance_grid(
        self,
        current_grid_step: float,
        optimal_grid_step: float,
        current_volatility: float,
        historical_volatility: float
    ) -> Dict[str, Any]:
        """
        Determine if grid should be rebalanced
        
        Args:
            current_grid_step: Current grid step
            optimal_grid_step: Optimal grid step
            current_volatility: Current market volatility
            historical_volatility: Historical average volatility
        
        Returns:
            Dictionary with rebalancing recommendation
        """
        # Calculate deviation
        step_deviation = abs(optimal_grid_step - current_grid_step) / current_grid_step
        vol_deviation = abs(current_volatility - historical_volatility) / historical_volatility
        
        should_rebalance = False
        reason = ''
        urgency = 'low'
        
        # Rebalance if grid step is off by more than 20%
        if step_deviation > 0.20:
            should_rebalance = True
            reason = f'Grid step deviation: {step_deviation*100:.1f}%'
            urgency = 'high' if step_deviation > 0.30 else 'medium'
        
        # Rebalance if volatility changed significantly
        elif vol_deviation > 0.30:
            should_rebalance = True
            reason = f'Volatility change: {vol_deviation*100:.1f}%'
            urgency = 'medium'
        
        return {
            'should_rebalance': should_rebalance,
            'reason': reason,
            'urgency': urgency,
            'current_grid_step': current_grid_step,
            'optimal_grid_step': optimal_grid_step,
            'step_deviation_pct': round(step_deviation * 100, 2),
            'vol_deviation_pct': round(vol_deviation * 100, 2)
        }
    
    # =========================================================================
    # COMPREHENSIVE OPTIMIZATION
    # =========================================================================
    
    def optimize_grid_parameters(
        self,
        current_price: float,
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        volatility: float,
        risk_tolerance: str = 'medium'
    ) -> Dict[str, Any]:
        """
        Comprehensive grid parameter optimization
        
        Args:
            current_price: Current market price
            capital: Trading capital
            win_rate: Historical win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            volatility: Market volatility (0-1)
            risk_tolerance: 'low', 'medium', or 'high'
        
        Returns:
            Dictionary with all optimized parameters
        """
        # Calculate optimal position size
        position_sizing = self.calculate_optimal_position_size(
            capital, win_rate, avg_win, avg_loss, current_price
        )
        
        # Calculate optimal grid step
        grid_params = self.calculate_optimal_grid_step(
            current_price, volatility, capital, risk_tolerance
        )
        
        # Calculate optimal take profit
        tp_params = self.calculate_optimal_take_profit(
            grid_params['optimal_grid_step'], win_rate, volatility
        )
        
        return {
            'timestamp': datetime.now().isoformat(),
            'position_sizing': position_sizing,
            'grid_parameters': grid_params,
            'take_profit': tp_params,
            'risk_metrics': {
                'volatility': round(volatility, 2),
                'win_rate': round(win_rate * 100, 2),
                'risk_reward_ratio': round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0
            }
        }
    
    # =========================================================================
    # DATA LOADING
    # =========================================================================
    
    def _load_optimization_data(self) -> Dict[str, Any]:
        """
        Load data needed for optimization
        
        Returns:
            Dictionary with optimization data
        """
        try:
            # Load current config
            config_file = self.base_dir / 'config.yaml'
            current_config = {}
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            current_config[key] = value
            
            # Load performance metrics
            from ..analytics import get_performance_analytics
            perf = get_performance_analytics()
            metrics = perf.calculate_all_metrics()
            
            # Load market data
            from .market_regime import get_market_regime_detector
            regime_detector = get_market_regime_detector()
            market_analysis = regime_detector.analyze_market()
            
            return {
                'current_config': current_config,
                'performance_metrics': metrics,
                'market_analysis': market_analysis
            }
        
        except Exception as e:
            return {
                'current_config': {},
                'performance_metrics': {},
                'market_analysis': {}
            }
    
    def get_optimization_recommendations(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive optimization recommendations
        
        Args:
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with optimization recommendations
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Load data
        data = self._load_optimization_data()
        
        # Extract key metrics
        current_price = data['market_analysis'].get('current_price', 111000)
        capital = 100000  # Default, should load from state
        
        perf_metrics = data['performance_metrics']
        win_rate = perf_metrics.get('win_loss_stats', {}).get('win_rate', 60) / 100
        avg_win = perf_metrics.get('win_loss_stats', {}).get('avg_win', 500)
        avg_loss = perf_metrics.get('win_loss_stats', {}).get('avg_loss', 300)
        
        regime = data['market_analysis'].get('regime', {})
        volatility = regime.get('metrics', {}).get('volatility', 0.3)
        
        # Optimize parameters
        optimization = self.optimize_grid_parameters(
            current_price, capital, win_rate, avg_win, avg_loss, volatility
        )
        
        # Update cache
        self.cache = optimization
        self.last_cache_time = datetime.now()
        
        return optimization


# Singleton accessor
_grid_optimizer_instance = None

def get_grid_optimizer() -> GridOptimizer:
    """Get singleton instance of GridOptimizer"""
    global _grid_optimizer_instance
    if _grid_optimizer_instance is None:
        _grid_optimizer_instance = GridOptimizer()
    return _grid_optimizer_instance

