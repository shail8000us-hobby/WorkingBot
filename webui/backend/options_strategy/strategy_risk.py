"""
Strategy Risk Validator
=======================
Pre-execution risk checks for options strategies.

Risk Checks:
- Capital availability
- Position limits
- Portfolio concentration
- Delta exposure
- Greeks limits

Created: January 5, 2026
Phase 3: Automation & Monitoring
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .strategy_models import Strategy, StrategyLeg

log = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCheckStatus(str, Enum):
    """Status of risk check"""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RiskCheckResult:
    """Result of a single risk check"""
    name: str
    status: RiskCheckStatus
    message: str
    value: Optional[float] = None
    limit: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.LOW
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'value': self.value,
            'limit': self.limit,
            'risk_level': self.risk_level.value
        }


@dataclass
class RiskValidationResult:
    """Combined result of all risk checks"""
    passed: bool
    checks: List[RiskCheckResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.LOW
    
    def to_dict(self) -> Dict:
        return {
            'passed': self.passed,
            'checks': [c.to_dict() for c in self.checks],
            'errors': self.errors,
            'warnings': self.warnings,
            'overall_risk': self.overall_risk.value
        }


@dataclass
class RiskLimits:
    """Configurable risk limits"""
    # Capital limits
    max_strategy_cost: float = 10000.0  # Max cost per strategy
    max_total_exposure: float = 50000.0  # Max total options exposure
    min_available_capital_pct: float = 0.2  # Keep 20% capital free
    
    # Position limits
    max_active_strategies: int = 10
    max_strategies_per_underlying: int = 3
    max_legs_per_strategy: int = 6
    
    # Greeks limits
    max_portfolio_delta: float = 500.0  # Absolute delta exposure
    max_portfolio_vega: float = 1000.0  # Vega exposure
    max_negative_theta: float = -200.0  # Daily theta decay limit
    
    # Concentration limits
    max_single_strategy_pct: float = 0.3  # 30% max in single strategy
    max_expiry_concentration_pct: float = 0.5  # 50% max in single expiry
    
    # Leverage limits
    max_notional_leverage: float = 5.0  # 5x max notional
    
    def to_dict(self) -> Dict:
        return {
            'max_strategy_cost': self.max_strategy_cost,
            'max_total_exposure': self.max_total_exposure,
            'min_available_capital_pct': self.min_available_capital_pct,
            'max_active_strategies': self.max_active_strategies,
            'max_strategies_per_underlying': self.max_strategies_per_underlying,
            'max_legs_per_strategy': self.max_legs_per_strategy,
            'max_portfolio_delta': self.max_portfolio_delta,
            'max_portfolio_vega': self.max_portfolio_vega,
            'max_negative_theta': self.max_negative_theta,
            'max_single_strategy_pct': self.max_single_strategy_pct,
            'max_expiry_concentration_pct': self.max_expiry_concentration_pct,
            'max_notional_leverage': self.max_notional_leverage
        }


class StrategyRiskValidator:
    """
    Pre-execution risk validation for strategies
    
    Validates:
    - Capital requirements
    - Position limits
    - Portfolio concentration
    - Greeks exposure
    - Leverage limits
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        self._limits = limits or RiskLimits()
        self._strategy_manager = None
        
    @property
    def strategy_manager(self):
        """Lazy load strategy manager"""
        if self._strategy_manager is None:
            from .strategy_manager import StrategyManager
            self._strategy_manager = StrategyManager()
        return self._strategy_manager
    
    @property
    def limits(self) -> RiskLimits:
        return self._limits
    
    def update_limits(self, new_limits: Dict):
        """Update risk limits"""
        for key, value in new_limits.items():
            if hasattr(self._limits, key):
                setattr(self._limits, key, value)
        log.info(f"Updated risk limits: {new_limits}")
    
    # ==================== Main Validation ====================
    
    def validate_strategy(self, strategy: Strategy) -> RiskValidationResult:
        """
        Run all risk checks on a strategy
        
        Returns:
            RiskValidationResult with pass/fail and details
        """
        result = RiskValidationResult(passed=True)
        
        # Run all checks
        checks = [
            self._check_capital(strategy),
            self._check_position_limits(strategy),
            self._check_concentration(strategy),
            self._check_legs_limit(strategy),
            self._check_delta_exposure(strategy),
            self._check_vega_exposure(strategy),
            self._check_theta_impact(strategy),
            self._check_leverage(strategy),
        ]
        
        result.checks = checks
        
        # Process results
        for check in checks:
            if check.status == RiskCheckStatus.FAILED:
                result.passed = False
                result.errors.append(check.message)
                
            elif check.status == RiskCheckStatus.WARNING:
                result.warnings.append(check.message)
        
        # Determine overall risk level
        result.overall_risk = self._calculate_overall_risk(checks)
        
        log.info(f"Risk validation: {'PASSED' if result.passed else 'FAILED'} "
                 f"({len(result.errors)} errors, {len(result.warnings)} warnings)")
        
        return result
    
    def _calculate_overall_risk(self, checks: List[RiskCheckResult]) -> RiskLevel:
        """Calculate overall risk level from individual checks"""
        risk_levels = [c.risk_level for c in checks if c.status != RiskCheckStatus.SKIPPED]
        
        if not risk_levels:
            return RiskLevel.LOW
        
        # Return highest risk level
        if RiskLevel.CRITICAL in risk_levels:
            return RiskLevel.CRITICAL
        if RiskLevel.HIGH in risk_levels:
            return RiskLevel.HIGH
        if RiskLevel.MEDIUM in risk_levels:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    # ==================== Individual Checks ====================
    
    def _check_capital(self, strategy: Strategy) -> RiskCheckResult:
        """Check if sufficient capital is available"""
        result = RiskCheckResult(
            name="capital_check",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            # Estimate strategy cost
            estimated_cost = strategy.estimated_cost or self._estimate_cost(strategy)
            
            # Check max strategy cost
            if estimated_cost > self._limits.max_strategy_cost:
                result.status = RiskCheckStatus.FAILED
                result.risk_level = RiskLevel.HIGH
                result.message = f"Strategy cost ${estimated_cost:,.0f} exceeds limit ${self._limits.max_strategy_cost:,.0f}"
            else:
                result.message = f"Cost ${estimated_cost:,.0f} within limit"
            
            result.value = estimated_cost
            result.limit = self._limits.max_strategy_cost
            
        except Exception as e:
            result.status = RiskCheckStatus.WARNING
            result.message = f"Could not verify capital: {e}"
        
        return result
    
    def _check_position_limits(self, strategy: Strategy) -> RiskCheckResult:
        """Check position count limits"""
        result = RiskCheckResult(
            name="position_limits",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            active_strategies = self.strategy_manager.get_active_strategies()
            active_count = len(active_strategies)
            
            # Check total strategies limit
            if active_count >= self._limits.max_active_strategies:
                result.status = RiskCheckStatus.FAILED
                result.risk_level = RiskLevel.HIGH
                result.message = f"Max active strategies ({self._limits.max_active_strategies}) reached"
            else:
                # Check per-underlying limit
                underlying_count = sum(
                    1 for s in active_strategies 
                    if s.underlying == strategy.underlying
                )
                
                if underlying_count >= self._limits.max_strategies_per_underlying:
                    result.status = RiskCheckStatus.WARNING
                    result.risk_level = RiskLevel.MEDIUM
                    result.message = f"Max strategies for {strategy.underlying} ({self._limits.max_strategies_per_underlying}) reached"
                else:
                    result.message = f"Active strategies: {active_count}/{self._limits.max_active_strategies}"
            
            result.value = active_count
            result.limit = self._limits.max_active_strategies
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check position limits: {e}"
        
        return result
    
    def _check_concentration(self, strategy: Strategy) -> RiskCheckResult:
        """Check portfolio concentration limits"""
        result = RiskCheckResult(
            name="concentration",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            active_strategies = self.strategy_manager.get_active_strategies()
            
            # Calculate total exposure
            total_exposure = sum(s.total_cost or 0 for s in active_strategies)
            strategy_cost = strategy.estimated_cost or self._estimate_cost(strategy)
            
            if total_exposure == 0:
                result.message = "First strategy, no concentration risk"
                return result
            
            # New total after adding this strategy
            new_total = total_exposure + strategy_cost
            strategy_pct = strategy_cost / new_total
            
            if strategy_pct > self._limits.max_single_strategy_pct:
                result.status = RiskCheckStatus.WARNING
                result.risk_level = RiskLevel.MEDIUM
                result.message = f"Strategy would be {strategy_pct:.0%} of portfolio (limit: {self._limits.max_single_strategy_pct:.0%})"
            else:
                result.message = f"Concentration: {strategy_pct:.0%} (limit: {self._limits.max_single_strategy_pct:.0%})"
            
            result.value = strategy_pct * 100
            result.limit = self._limits.max_single_strategy_pct * 100
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check concentration: {e}"
        
        return result
    
    def _check_legs_limit(self, strategy: Strategy) -> RiskCheckResult:
        """Check number of legs in strategy"""
        result = RiskCheckResult(
            name="legs_limit",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        leg_count = len(strategy.legs)
        
        if leg_count > self._limits.max_legs_per_strategy:
            result.status = RiskCheckStatus.FAILED
            result.risk_level = RiskLevel.MEDIUM
            result.message = f"Too many legs: {leg_count} (max: {self._limits.max_legs_per_strategy})"
        else:
            result.message = f"Legs: {leg_count}/{self._limits.max_legs_per_strategy}"
        
        result.value = leg_count
        result.limit = self._limits.max_legs_per_strategy
        
        return result
    
    def _check_delta_exposure(self, strategy: Strategy) -> RiskCheckResult:
        """Check portfolio delta exposure"""
        result = RiskCheckResult(
            name="delta_exposure",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            # Get current portfolio delta
            active_strategies = self.strategy_manager.get_active_strategies()
            portfolio_delta = sum(s.delta or 0 for s in active_strategies)
            
            # Add this strategy's delta
            strategy_delta = strategy.delta or self._estimate_delta(strategy)
            new_delta = portfolio_delta + strategy_delta
            
            abs_delta = abs(new_delta)
            
            if abs_delta > self._limits.max_portfolio_delta:
                result.status = RiskCheckStatus.WARNING
                result.risk_level = RiskLevel.MEDIUM
                result.message = f"Portfolio delta {new_delta:+.1f} exceeds limit ±{self._limits.max_portfolio_delta}"
            else:
                result.message = f"Delta: {new_delta:+.1f} (limit: ±{self._limits.max_portfolio_delta})"
            
            result.value = new_delta
            result.limit = self._limits.max_portfolio_delta
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check delta: {e}"
        
        return result
    
    def _check_vega_exposure(self, strategy: Strategy) -> RiskCheckResult:
        """Check portfolio vega exposure"""
        result = RiskCheckResult(
            name="vega_exposure",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            active_strategies = self.strategy_manager.get_active_strategies()
            portfolio_vega = sum(s.vega or 0 for s in active_strategies)
            
            strategy_vega = strategy.vega or self._estimate_vega(strategy)
            new_vega = portfolio_vega + strategy_vega
            
            if abs(new_vega) > self._limits.max_portfolio_vega:
                result.status = RiskCheckStatus.WARNING
                result.risk_level = RiskLevel.MEDIUM
                result.message = f"Portfolio vega {new_vega:+.1f} exceeds limit ±{self._limits.max_portfolio_vega}"
            else:
                result.message = f"Vega: {new_vega:+.1f} (limit: ±{self._limits.max_portfolio_vega})"
            
            result.value = new_vega
            result.limit = self._limits.max_portfolio_vega
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check vega: {e}"
        
        return result
    
    def _check_theta_impact(self, strategy: Strategy) -> RiskCheckResult:
        """Check theta decay impact"""
        result = RiskCheckResult(
            name="theta_impact",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            active_strategies = self.strategy_manager.get_active_strategies()
            portfolio_theta = sum(s.theta or 0 for s in active_strategies)
            
            strategy_theta = strategy.theta or self._estimate_theta(strategy)
            new_theta = portfolio_theta + strategy_theta
            
            if new_theta < self._limits.max_negative_theta:
                result.status = RiskCheckStatus.WARNING
                result.risk_level = RiskLevel.MEDIUM
                result.message = f"Daily theta decay ${new_theta:,.0f} exceeds limit ${self._limits.max_negative_theta:,.0f}"
            else:
                result.message = f"Daily theta: ${new_theta:+,.0f}"
            
            result.value = new_theta
            result.limit = self._limits.max_negative_theta
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check theta: {e}"
        
        return result
    
    def _check_leverage(self, strategy: Strategy) -> RiskCheckResult:
        """Check notional leverage"""
        result = RiskCheckResult(
            name="leverage_check",
            status=RiskCheckStatus.PASSED,
            message=""
        )
        
        try:
            # Calculate notional value
            notional = self._calculate_notional(strategy)
            cost = strategy.estimated_cost or self._estimate_cost(strategy)
            
            if cost == 0:
                result.status = RiskCheckStatus.SKIPPED
                result.message = "Cannot calculate leverage without cost"
                return result
            
            leverage = notional / cost if cost > 0 else 0
            
            if leverage > self._limits.max_notional_leverage:
                result.status = RiskCheckStatus.WARNING
                result.risk_level = RiskLevel.MEDIUM
                result.message = f"Leverage {leverage:.1f}x exceeds limit {self._limits.max_notional_leverage}x"
            else:
                result.message = f"Leverage: {leverage:.1f}x (limit: {self._limits.max_notional_leverage}x)"
            
            result.value = leverage
            result.limit = self._limits.max_notional_leverage
            
        except Exception as e:
            result.status = RiskCheckStatus.SKIPPED
            result.message = f"Could not check leverage: {e}"
        
        return result
    
    # ==================== Estimation Helpers ====================
    
    def _estimate_cost(self, strategy: Strategy) -> float:
        """Estimate strategy cost"""
        total = 0.0
        for leg in strategy.legs:
            price = leg.current_price or leg.avg_fill_price or 0
            qty = leg.quantity or 1
            if leg.side == 'buy':
                total += price * qty
            else:
                total -= price * qty
        return abs(total)
    
    def _estimate_delta(self, strategy: Strategy) -> float:
        """Estimate strategy delta"""
        # Simplified: calls have positive delta, puts have negative
        delta = 0.0
        for leg in strategy.legs:
            leg_delta = 0.5 if leg.option_type == 'call' else -0.5
            qty = leg.quantity or 1
            sign = 1 if leg.side == 'buy' else -1
            delta += leg_delta * qty * sign
        return delta
    
    def _estimate_vega(self, strategy: Strategy) -> float:
        """Estimate strategy vega"""
        # Simplified: positive for long options, negative for short
        vega = 0.0
        for leg in strategy.legs:
            leg_vega = 10.0  # Simplified fixed vega per contract
            qty = leg.quantity or 1
            sign = 1 if leg.side == 'buy' else -1
            vega += leg_vega * qty * sign
        return vega
    
    def _estimate_theta(self, strategy: Strategy) -> float:
        """Estimate strategy theta"""
        # Simplified: negative for long options, positive for short
        theta = 0.0
        for leg in strategy.legs:
            leg_theta = -5.0  # Simplified daily theta per contract
            qty = leg.quantity or 1
            sign = 1 if leg.side == 'buy' else -1
            theta += leg_theta * qty * sign
        return theta
    
    def _calculate_notional(self, strategy: Strategy) -> float:
        """Calculate total notional value"""
        notional = 0.0
        for leg in strategy.legs:
            # Strike * quantity (simplified for BTC options)
            notional += leg.strike * (leg.quantity or 1)
        return notional


# Global instance
_validator_instance: Optional[StrategyRiskValidator] = None


def get_risk_validator() -> StrategyRiskValidator:
    """Get singleton risk validator"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = StrategyRiskValidator()
    return _validator_instance


def validate_strategy_risk(strategy: Strategy) -> RiskValidationResult:
    """Convenience function to validate strategy"""
    return get_risk_validator().validate_strategy(strategy)
