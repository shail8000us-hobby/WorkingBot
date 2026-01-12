"""
Advanced Risk Management System for WorkingBot
==============================================
Dynamic risk parameters, portfolio Greeks, VaR, and real-time risk monitoring.

Imported from OptionBot project with adaptations.
Original: risk/advanced_risk_manager.py

Usage:
    from webui.backend.options_strategy.advanced_risk_manager import AdvancedRiskManager
    
    risk_manager = AdvancedRiskManager()
    
    # Assess portfolio risk
    metrics = risk_manager.assess_portfolio_risk(positions, account_balance)
    
    # Check if should reduce risk
    should_reduce, reason = risk_manager.should_reduce_risk()
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PortfolioGreeks:
    """Aggregated portfolio-level Greeks"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4),
        }


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics snapshot"""
    portfolio_value: float
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_theta: float
    portfolio_vega: float
    var_95: float  # Value at Risk at 95% confidence
    var_99: float  # Value at Risk at 99% confidence
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    risk_level: RiskLevel
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'portfolio_value': round(self.portfolio_value, 2),
            'greeks': {
                'delta': round(self.portfolio_delta, 4),
                'gamma': round(self.portfolio_gamma, 6),
                'theta': round(self.portfolio_theta, 4),
                'vega': round(self.portfolio_vega, 4),
            },
            'risk_metrics': {
                'var_95': round(self.var_95, 2),
                'var_99': round(self.var_99, 2),
                'max_drawdown': round(self.max_drawdown, 4),
                'sharpe_ratio': round(self.sharpe_ratio, 2),
                'sortino_ratio': round(self.sortino_ratio, 2),
            },
            'risk_level': self.risk_level.value,
            'timestamp': self.timestamp.isoformat()
        }


class VolatilityRegimeDetector:
    """
    Detects market volatility regime (high/normal/low).
    
    Used to dynamically adjust risk parameters based on market conditions.
    """
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.volatility_history: List[float] = []
    
    def add_volatility(self, volatility: float):
        """Add volatility observation"""
        if volatility > 0:
            self.volatility_history.append(volatility)
            if len(self.volatility_history) > self.window_size:
                self.volatility_history.pop(0)
    
    def get_regime(self) -> str:
        """
        Get current volatility regime.
        
        Returns:
            'high', 'normal', or 'low'
        """
        if not self.volatility_history:
            return "unknown"
        
        avg_vol = np.mean(self.volatility_history)
        current_vol = self.volatility_history[-1]
        
        if current_vol > avg_vol * 1.5:
            return "high"
        elif current_vol < avg_vol * 0.7:
            return "low"
        else:
            return "normal"
    
    def get_volatility_percentile(self) -> float:
        """Get current volatility as percentile of history"""
        if not self.volatility_history or len(self.volatility_history) < 2:
            return 50.0
        
        current_vol = self.volatility_history[-1]
        sorted_vols = sorted(self.volatility_history)
        
        # Find position in sorted list
        position = 0
        for vol in sorted_vols:
            if vol <= current_vol:
                position += 1
        
        percentile = (position / len(sorted_vols)) * 100
        return percentile


class DynamicRiskParameters:
    """
    Dynamically adjusts risk parameters based on market conditions.
    
    Reduces risk in high volatility or drawdown situations.
    Increases risk in favorable conditions.
    """
    
    def __init__(
        self,
        base_max_delta: float = 0.30,
        base_max_vega: float = 0.20,
        base_max_position_size: float = 5.0,
        base_max_daily_loss: float = 2.0,
    ):
        self.base_max_delta = base_max_delta
        self.base_max_vega = base_max_vega
        self.base_max_position_size = base_max_position_size
        self.base_max_daily_loss = base_max_daily_loss
        
        self.volatility_detector = VolatilityRegimeDetector()
    
    def adjust_parameters(
        self,
        current_volatility: float,
        account_balance: float,
        current_drawdown: float
    ) -> Dict[str, float]:
        """
        Adjust risk parameters based on market conditions.
        
        Args:
            current_volatility: Current market volatility (IV)
            account_balance: Current account balance
            current_drawdown: Current drawdown percentage (negative)
        
        Returns:
            Adjusted risk parameters dictionary
        """
        self.volatility_detector.add_volatility(current_volatility)
        regime = self.volatility_detector.get_regime()
        
        # Volatility adjustment factor
        if regime == "high":
            vol_factor = 0.7  # Reduce risk by 30% in high volatility
        elif regime == "low":
            vol_factor = 1.2  # Increase risk by 20% in low volatility
        else:
            vol_factor = 1.0
        
        # Drawdown adjustment factor
        abs_drawdown = abs(current_drawdown)
        if abs_drawdown > 5:
            drawdown_factor = 0.5  # Reduce risk by 50% if drawdown > 5%
        elif abs_drawdown > 2:
            drawdown_factor = 0.75  # Reduce risk by 25% if drawdown > 2%
        else:
            drawdown_factor = 1.0
        
        # Account balance adjustment (scale with account size)
        # Normalize to $10k base
        balance_factor = min(2.0, max(0.5, account_balance / 10000))
        
        # Combined adjustment factor
        combined_factor = vol_factor * drawdown_factor * balance_factor
        
        return {
            "max_delta": round(self.base_max_delta * combined_factor, 4),
            "max_vega": round(self.base_max_vega * combined_factor, 4),
            "max_position_size": round(self.base_max_position_size * combined_factor, 2),
            "max_daily_loss": round(self.base_max_daily_loss * combined_factor, 2),
            "volatility_regime": regime,
            "adjustment_factor": round(combined_factor, 2),
            "vol_factor": round(vol_factor, 2),
            "drawdown_factor": round(drawdown_factor, 2),
            "balance_factor": round(balance_factor, 2),
        }


class PortfolioRiskCalculator:
    """Static methods for calculating portfolio risk metrics"""
    
    @staticmethod
    def calculate_portfolio_greeks(positions: List[Dict[str, Any]]) -> PortfolioGreeks:
        """
        Calculate aggregate Greeks for portfolio.
        
        Args:
            positions: List of position dicts with delta, gamma, theta, vega, size
            
        Returns:
            PortfolioGreeks with aggregated values
        """
        greeks = PortfolioGreeks()
        
        for position in positions:
            size = position.get("size", 1)
            greeks.delta += position.get("delta", 0) * size
            greeks.gamma += position.get("gamma", 0) * size
            greeks.theta += position.get("theta", 0) * size
            greeks.vega += position.get("vega", 0) * size
            greeks.rho += position.get("rho", 0) * size
        
        return greeks
    
    @staticmethod
    def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk using historical simulation.
        
        Args:
            returns: Historical returns (daily % returns)
            confidence_level: Confidence level (0.95 or 0.99)
        
        Returns:
            VaR value (negative number representing potential loss)
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int(len(sorted_returns) * (1 - confidence_level))
        return sorted_returns[max(0, index)]
    
    @staticmethod
    def calculate_max_drawdown(returns: List[float]) -> float:
        """
        Calculate maximum drawdown from returns series.
        
        Args:
            returns: Historical returns (daily % returns)
        
        Returns:
            Maximum drawdown (negative number)
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        # Convert returns to cumulative growth
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(np.min(drawdown))
    
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            returns: Historical returns (daily % returns)
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            Annualized Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / 252
        excess_returns = np.array(returns) - daily_rf
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        # Annualize
        return float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))
    
    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (only penalizes downside volatility).
        
        Args:
            returns: Historical returns (daily % returns)
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            Annualized Sortino ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / 252
        excess_returns = np.array(returns) - daily_rf
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float(np.mean(excess_returns) * np.sqrt(252))  # No downside = great
        
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0
        
        return float(np.mean(excess_returns) / downside_std * np.sqrt(252))


class RiskLimitChecker:
    """Checks if positions violate risk limits"""
    
    def __init__(self):
        self.violations: List[str] = []
    
    def check_limits(
        self,
        portfolio_greeks: PortfolioGreeks,
        limits: Dict[str, float],
        position_value: float,
        daily_pnl: float
    ) -> Tuple[bool, List[str]]:
        """
        Check if portfolio violates risk limits.
        
        Args:
            portfolio_greeks: Current portfolio Greeks
            limits: Risk limits dictionary
            position_value: Total position value
            daily_pnl: Daily P&L
        
        Returns:
            Tuple of (is_within_limits, list_of_violations)
        """
        violations = []
        
        # Check delta limit
        max_delta = limits.get("max_delta", 0.30)
        if abs(portfolio_greeks.delta) > max_delta:
            violations.append(
                f"Delta exposure ({abs(portfolio_greeks.delta):.4f}) exceeds limit ({max_delta})"
            )
        
        # Check vega limit
        max_vega = limits.get("max_vega", 0.20)
        if abs(portfolio_greeks.vega) > max_vega:
            violations.append(
                f"Vega exposure ({abs(portfolio_greeks.vega):.4f}) exceeds limit ({max_vega})"
            )
        
        # Check gamma limit
        max_gamma = limits.get("max_gamma", 0.10)
        if abs(portfolio_greeks.gamma) > max_gamma:
            violations.append(
                f"Gamma exposure ({abs(portfolio_greeks.gamma):.6f}) exceeds limit ({max_gamma})"
            )
        
        # Check theta limit (usually negative)
        min_theta = limits.get("min_theta", -0.50)
        if portfolio_greeks.theta < min_theta:
            violations.append(
                f"Theta exposure ({portfolio_greeks.theta:.4f}) below limit ({min_theta})"
            )
        
        # Check position size limit
        max_position = limits.get("max_position_size", 5.0)
        if position_value > max_position:
            violations.append(
                f"Position size ({position_value:.2f}) exceeds limit ({max_position})"
            )
        
        # Check daily loss limit
        max_daily_loss = limits.get("max_daily_loss", 2.0)
        if daily_pnl < -max_daily_loss:
            violations.append(
                f"Daily loss ({abs(daily_pnl):.2f}) exceeds limit ({max_daily_loss})"
            )
        
        self.violations = violations
        return len(violations) == 0, violations


class AdvancedRiskManager:
    """
    Comprehensive advanced risk management system.
    
    Features:
    - Dynamic risk parameter adjustment
    - Portfolio Greeks aggregation
    - VaR and risk metrics calculation
    - Automatic risk level classification
    - Risk reduction recommendations
    
    Example:
        risk_manager = AdvancedRiskManager()
        
        # Add daily return
        risk_manager.add_return(0.02)  # 2% daily return
        
        # Assess portfolio risk
        metrics = risk_manager.assess_portfolio_risk(
            positions=positions,
            limits=limits,
            account_balance=10000,
            current_volatility=0.5,
            daily_pnl=-100,
            position_value=5000
        )
        
        # Check if should reduce risk
        should_reduce, reason = risk_manager.should_reduce_risk()
    """
    
    def __init__(self):
        self.dynamic_params = DynamicRiskParameters()
        self.portfolio_calculator = PortfolioRiskCalculator()
        self.risk_checker = RiskLimitChecker()
        self.risk_history: List[RiskMetrics] = []
        self.returns_history: List[float] = []
    
    def assess_portfolio_risk(
        self,
        positions: List[Dict[str, Any]],
        limits: Dict[str, float],
        account_balance: float,
        current_volatility: float,
        daily_pnl: float,
        position_value: float
    ) -> RiskMetrics:
        """
        Comprehensive portfolio risk assessment.
        
        Args:
            positions: List of open positions with Greeks
            limits: Risk limits dictionary
            account_balance: Current account balance
            current_volatility: Current market volatility
            daily_pnl: Daily P&L
            position_value: Total position value
        
        Returns:
            RiskMetrics object with full assessment
        """
        # Calculate portfolio Greeks
        portfolio_greeks = self.portfolio_calculator.calculate_portfolio_greeks(positions)
        
        # Calculate current drawdown
        current_drawdown = (daily_pnl / account_balance) * 100 if account_balance > 0 else 0
        
        # Adjust risk parameters dynamically
        adjusted_limits = self.dynamic_params.adjust_parameters(
            current_volatility,
            account_balance,
            current_drawdown
        )
        
        # Merge with provided limits
        for key in adjusted_limits:
            if key not in limits:
                limits[key] = adjusted_limits[key]
        
        # Check risk limits
        is_within_limits, violations = self.risk_checker.check_limits(
            portfolio_greeks,
            limits,
            position_value,
            daily_pnl
        )
        
        # Calculate risk metrics from returns history
        var_95 = self.portfolio_calculator.calculate_var(self.returns_history, 0.95)
        var_99 = self.portfolio_calculator.calculate_var(self.returns_history, 0.99)
        max_drawdown = self.portfolio_calculator.calculate_max_drawdown(self.returns_history)
        sharpe_ratio = self.portfolio_calculator.calculate_sharpe_ratio(self.returns_history)
        sortino_ratio = self.portfolio_calculator.calculate_sortino_ratio(self.returns_history)
        
        # Determine risk level
        risk_level = self._determine_risk_level(
            portfolio_greeks,
            adjusted_limits,
            is_within_limits
        )
        
        metrics = RiskMetrics(
            portfolio_value=position_value,
            portfolio_delta=portfolio_greeks.delta,
            portfolio_gamma=portfolio_greeks.gamma,
            portfolio_theta=portfolio_greeks.theta,
            portfolio_vega=portfolio_greeks.vega,
            var_95=var_95,
            var_99=var_99,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            risk_level=risk_level,
            timestamp=datetime.now()
        )
        
        self.risk_history.append(metrics)
        
        # Keep only recent history (last 1000 assessments)
        if len(self.risk_history) > 1000:
            self.risk_history = self.risk_history[-1000:]
        
        return metrics
    
    def _determine_risk_level(
        self,
        greeks: PortfolioGreeks,
        limits: Dict[str, float],
        is_within_limits: bool
    ) -> RiskLevel:
        """Determine risk level based on current exposure"""
        max_delta = limits.get("max_delta", 0.30)
        max_vega = limits.get("max_vega", 0.20)
        
        if not is_within_limits or abs(greeks.delta) > max_delta * 1.5:
            return RiskLevel.CRITICAL
        
        if abs(greeks.delta) > max_delta or abs(greeks.vega) > max_vega:
            return RiskLevel.HIGH
        
        if abs(greeks.delta) > max_delta * 0.7:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def add_return(self, return_value: float):
        """
        Add daily return observation.
        
        Args:
            return_value: Daily return as decimal (0.02 = 2%)
        """
        self.returns_history.append(return_value)
        if len(self.returns_history) > 1000:
            self.returns_history.pop(0)
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Get comprehensive risk report for dashboard"""
        if not self.risk_history:
            return {
                "status": "no_data",
                "message": "No risk assessments performed yet"
            }
        
        latest = self.risk_history[-1]
        recent = self.risk_history[-10:] if len(self.risk_history) >= 10 else self.risk_history
        
        return {
            "current_risk_level": latest.risk_level.value,
            "portfolio_greeks": {
                "delta": latest.portfolio_delta,
                "gamma": latest.portfolio_gamma,
                "theta": latest.portfolio_theta,
                "vega": latest.portfolio_vega,
            },
            "risk_metrics": {
                "var_95": latest.var_95,
                "var_99": latest.var_99,
                "max_drawdown": latest.max_drawdown,
                "sharpe_ratio": latest.sharpe_ratio,
                "sortino_ratio": latest.sortino_ratio,
            },
            "recent_history": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "risk_level": m.risk_level.value,
                    "delta": m.portfolio_delta,
                    "vega": m.portfolio_vega,
                }
                for m in recent
            ],
            "violations": self.risk_checker.violations,
            "returns_count": len(self.returns_history),
            "volatility_regime": self.dynamic_params.volatility_detector.get_regime()
        }
    
    def should_reduce_risk(self) -> Tuple[bool, Optional[str]]:
        """
        Check if risk should be reduced.
        
        Returns:
            Tuple of (should_reduce: bool, reason: str or None)
        """
        if not self.risk_history:
            return False, None
        
        latest = self.risk_history[-1]
        
        if latest.risk_level == RiskLevel.CRITICAL:
            return True, "Risk level is critical"
        
        if latest.max_drawdown < -0.10:  # 10% drawdown
            return True, f"Maximum drawdown ({latest.max_drawdown:.1%}) exceeded threshold"
        
        if len(self.risk_checker.violations) > 0:
            return True, f"Risk limits violated: {self.risk_checker.violations[0]}"
        
        return False, None
    
    def reset(self):
        """Reset risk manager state"""
        self.risk_history.clear()
        self.returns_history.clear()
        self.risk_checker.violations.clear()
        logger.info("AdvancedRiskManager reset")


# Global risk manager instance
risk_manager = AdvancedRiskManager()
