"""
Decision Engine - Phase 4 of ML Autonomous Trading Engine

Autonomous decision-making system that evaluates signals and makes trading decisions
based on trader's style, risk limits, and market conditions.

Created: January 18, 2026
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import uuid

# Import dependencies
try:
    from .style_profiler import style_profiler, TradingStyleDNA
    from .opportunity_scanner import TradingSignal, opportunity_scanner
    from .regime_detector import regime_detector
except ImportError:
    from style_profiler import style_profiler, TradingStyleDNA
    from opportunity_scanner import TradingSignal, opportunity_scanner
    from regime_detector import regime_detector


class AutonomyLevel(Enum):
    """Level of AI autonomy"""
    ADVISORY = "advisory"  # Only suggest, never execute
    SEMI_AUTO = "semi_auto"  # Execute with approval
    FULL_AUTO = "full_auto"  # Execute automatically


class DecisionAction(Enum):
    """Possible decision actions"""
    EXECUTE = "execute"  # Proceed with trade
    REJECT = "reject"  # Reject the signal
    WAIT = "wait"  # Wait for better conditions
    REDUCE_SIZE = "reduce_size"  # Execute with smaller size
    MANUAL_REVIEW = "manual_review"  # Needs human review


@dataclass
class RiskLimits:
    """Risk limits for autonomous trading"""
    
    # Position limits
    max_position_size: int = 10
    max_positions: int = 5
    max_daily_trades: int = 20
    
    # Loss limits
    max_loss_per_trade: float = 100.0  # USD
    max_daily_loss: float = 500.0  # USD
    max_drawdown_pct: float = 10.0  # Percentage
    
    # Risk limits
    max_portfolio_risk: float = 0.20  # 20% of portfolio
    max_single_trade_risk: float = 0.05  # 5% of portfolio
    
    # Confidence thresholds
    min_confidence: float = 0.6
    min_style_match: float = 0.5
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DecisionResult:
    """Result of decision evaluation"""
    
    decision_id: str = ""
    signal_id: str = ""
    
    # Decision
    action: str = "manual_review"
    adjusted_quantity: int = 0
    
    # Confidence
    confidence: float = 0.0
    style_match: float = 0.0
    risk_score: float = 0.0
    
    # Reasoning
    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Timing
    suggested_wait_until: Optional[str] = None
    
    # Metadata
    evaluated_at: str = ""
    expires_at: str = ""
    status: str = "pending"  # pending, approved, rejected, executed, expired
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CircuitBreakerStatus:
    """Status of circuit breakers"""
    
    is_tripped: bool = False
    reason: str = ""
    tripped_at: Optional[str] = None
    auto_reset_at: Optional[str] = None
    
    # Individual breakers
    consecutive_losses: int = 0
    daily_loss: float = 0.0
    daily_trades: int = 0
    
    # Thresholds
    max_consecutive_losses: int = 3
    max_daily_loss: float = 500.0
    max_daily_trades: int = 20
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DecisionEngine:
    """
    Autonomous decision-making engine.
    
    Evaluates trading signals and decides whether to execute based on:
    - Trading style match
    - Risk assessment
    - Market conditions
    - Portfolio state
    - Circuit breakers
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.decisions_file = self.data_dir / 'decisions.json'
        self.circuit_breaker_file = self.data_dir / 'circuit_breaker.json'
        self.config_file = self.data_dir / 'decision_engine_config.json'
        
        # Configuration
        self.autonomy_level = AutonomyLevel.ADVISORY
        self.risk_limits = RiskLimits()
        self.circuit_breaker = CircuitBreakerStatus()
        
        # State
        self._pending_decisions: List[DecisionResult] = []
        self._decision_history: List[DecisionResult] = []
        
        # Load config
        self._load_config()
        self._load_circuit_breaker()
    
    def evaluate_signal(self, signal: TradingSignal) -> DecisionResult:
        """
        Comprehensive signal evaluation.
        
        Steps:
        1. Check circuit breakers
        2. Style compatibility check
        3. Risk assessment
        4. Market conditions check
        5. Final decision
        """
        decision = DecisionResult(
            decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
            signal_id=signal.signal_id,
            evaluated_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
        )
        
        # 1. Check circuit breakers
        if self.circuit_breaker.is_tripped:
            decision.action = DecisionAction.REJECT.value
            decision.reasoning.append(f"Circuit breaker tripped: {self.circuit_breaker.reason}")
            return decision
        
        # 2. Style compatibility check
        style = style_profiler.get_cached_profile()
        style_match = self._check_style_compatibility(signal, style)
        decision.style_match = style_match
        
        if style_match < self.risk_limits.min_style_match:
            decision.action = DecisionAction.REJECT.value
            decision.reasoning.append(f"Low style match ({style_match:.0%}) - below threshold ({self.risk_limits.min_style_match:.0%})")
            decision.warnings.append("This trade doesn't match your typical trading style")
            return decision
        else:
            decision.reasoning.append(f"Style match: {style_match:.0%}")
        
        # 3. Risk assessment
        risk_result = self._assess_risk(signal, style)
        decision.risk_score = risk_result['score']
        
        if not risk_result['acceptable']:
            decision.action = DecisionAction.REJECT.value
            decision.reasoning.append(f"Risk violation: {risk_result['reason']}")
            decision.warnings.extend(risk_result.get('warnings', []))
            return decision
        
        decision.reasoning.extend(risk_result.get('reasoning', []))
        
        # 4. Market conditions check
        regime = regime_detector.get_cached_regime()
        if regime:
            trend_pref = style.trend_preference if style else "neutral"
            should_trade, reason = regime_detector.should_trade_now(trend_pref)
            
            if not should_trade:
                decision.action = DecisionAction.WAIT.value
                decision.reasoning.append(f"Market conditions unfavorable: {reason}")
                decision.suggested_wait_until = (datetime.now() + timedelta(hours=1)).isoformat()
                return decision
            
            decision.reasoning.append(f"Market conditions: {reason}")
        
        # 5. Timing check
        timing_ok, timing_reason = self._check_timing(style)
        if not timing_ok:
            decision.action = DecisionAction.WAIT.value
            decision.reasoning.append(timing_reason)
            decision.suggested_wait_until = self._suggest_better_timing(style)
            return decision
        
        # 6. Calculate final confidence
        decision.confidence = self._calculate_confidence(
            signal.confidence,
            style_match,
            risk_result['score']
        )
        
        if decision.confidence < self.risk_limits.min_confidence:
            decision.action = DecisionAction.MANUAL_REVIEW.value
            decision.reasoning.append(f"Confidence ({decision.confidence:.0%}) below threshold - needs review")
            decision.warnings.append("Consider reviewing this trade manually")
        else:
            decision.action = DecisionAction.EXECUTE.value
            decision.adjusted_quantity = signal.quantity
            decision.reasoning.append(f"All checks passed - confidence {decision.confidence:.0%}")
        
        # 7. Check position sizing
        if risk_result.get('reduce_size'):
            decision.action = DecisionAction.REDUCE_SIZE.value
            decision.adjusted_quantity = risk_result['suggested_quantity']
            decision.reasoning.append(f"Reduced position size to {decision.adjusted_quantity}")
        
        # Store decision
        self._pending_decisions.append(decision)
        self._save_decision(decision)
        
        return decision
    
    def _check_style_compatibility(
        self, 
        signal: TradingSignal, 
        style: Optional[TradingStyleDNA]
    ) -> float:
        """Check how well signal matches trading style."""
        if not style:
            return 0.5
        
        scores = []
        
        # Option type match
        if signal.option_type == 'call':
            scores.append(style.call_preference)
        else:
            scores.append(1 - style.call_preference)
        
        # Action match (buy/sell)
        if signal.action == 'BUY':
            scores.append(style.buy_preference)
        else:
            scores.append(1 - style.buy_preference)
        
        # Size match
        if style.avg_position_size > 0:
            size_ratio = signal.quantity / style.avg_position_size
            if 0.5 <= size_ratio <= 2.0:
                scores.append(1.0)
            else:
                scores.append(0.5)
        else:
            scores.append(0.5)
        
        # Timing match
        current_hour = datetime.now().hour
        if style.preferred_entry_hours and current_hour in style.preferred_entry_hours:
            scores.append(1.0)
        else:
            scores.append(0.5)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _assess_risk(
        self, 
        signal: TradingSignal,
        style: Optional[TradingStyleDNA]
    ) -> Dict:
        """Assess risk of the trade."""
        result = {
            'acceptable': True,
            'score': 1.0,
            'reason': '',
            'reasoning': [],
            'warnings': [],
            'reduce_size': False,
            'suggested_quantity': signal.quantity
        }
        
        # Check position size
        if signal.quantity > self.risk_limits.max_position_size:
            result['reduce_size'] = True
            result['suggested_quantity'] = self.risk_limits.max_position_size
            result['reasoning'].append(f"Position size capped at {self.risk_limits.max_position_size}")
            result['score'] *= 0.8
        
        # Check max loss
        if signal.max_loss > self.risk_limits.max_loss_per_trade:
            result['acceptable'] = False
            result['reason'] = f"Max loss ${signal.max_loss:.0f} exceeds limit ${self.risk_limits.max_loss_per_trade:.0f}"
            return result
        
        # Check daily loss
        if self.circuit_breaker.daily_loss + signal.max_loss > self.risk_limits.max_daily_loss:
            result['acceptable'] = False
            result['reason'] = f"Would exceed daily loss limit"
            return result
        
        # Check daily trades
        if self.circuit_breaker.daily_trades >= self.risk_limits.max_daily_trades:
            result['acceptable'] = False
            result['reason'] = "Daily trade limit reached"
            return result
        
        # Check risk/reward
        if signal.risk_reward < 1.0:
            result['warnings'].append(f"Risk/reward ratio {signal.risk_reward:.1f} is below 1:1")
            result['score'] *= 0.7
        elif signal.risk_reward >= 2.0:
            result['reasoning'].append(f"Good risk/reward ratio: {signal.risk_reward:.1f}:1")
        
        # Check confidence
        if signal.confidence < 0.5:
            result['warnings'].append(f"Low signal confidence: {signal.confidence:.0%}")
            result['score'] *= 0.8
        
        result['reasoning'].append(f"Risk assessment passed (score: {result['score']:.0%})")
        
        return result
    
    def _check_timing(self, style: Optional[TradingStyleDNA]) -> Tuple[bool, str]:
        """Check if timing is appropriate."""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        
        if style:
            # Check preferred hours
            if style.preferred_entry_hours and current_hour not in style.preferred_entry_hours:
                return False, f"Current hour ({current_hour}:00) is outside preferred hours"
            
            # Check preferred days
            if style.preferred_days and current_day not in style.preferred_days:
                return False, f"Current day is outside preferred trading days"
        
        return True, "Timing is appropriate"
    
    def _suggest_better_timing(self, style: Optional[TradingStyleDNA]) -> str:
        """Suggest when to trade next."""
        if style and style.preferred_entry_hours:
            next_hour = min(style.preferred_entry_hours)
            now = datetime.now()
            suggested = now.replace(hour=next_hour, minute=0, second=0)
            if suggested <= now:
                suggested += timedelta(days=1)
            return suggested.isoformat()
        
        return (datetime.now() + timedelta(hours=1)).isoformat()
    
    def _calculate_confidence(
        self, 
        signal_confidence: float,
        style_match: float,
        risk_score: float
    ) -> float:
        """Calculate overall decision confidence."""
        # Weighted average
        weights = {
            'signal': 0.4,
            'style': 0.3,
            'risk': 0.3
        }
        
        confidence = (
            signal_confidence * weights['signal'] +
            style_match * weights['style'] +
            risk_score * weights['risk']
        )
        
        return min(1.0, confidence)
    
    def approve_decision(self, decision_id: str) -> Dict:
        """Approve a pending decision for execution."""
        for decision in self._pending_decisions:
            if decision.decision_id == decision_id:
                decision.status = "approved"
                self._save_decision(decision)
                return {
                    'success': True,
                    'message': f"Decision {decision_id} approved",
                    'decision': decision.to_dict()
                }
        
        return {'success': False, 'error': 'Decision not found'}
    
    def reject_decision(self, decision_id: str, reason: str = "") -> Dict:
        """Reject a pending decision."""
        for decision in self._pending_decisions:
            if decision.decision_id == decision_id:
                decision.status = "rejected"
                if reason:
                    decision.reasoning.append(f"Rejected: {reason}")
                self._save_decision(decision)
                return {
                    'success': True,
                    'message': f"Decision {decision_id} rejected"
                }
        
        return {'success': False, 'error': 'Decision not found'}
    
    def get_pending_decisions(self) -> List[DecisionResult]:
        """Get all pending decisions."""
        now = datetime.now()
        pending = []
        
        for decision in self._pending_decisions:
            if decision.status == "pending":
                expires = datetime.fromisoformat(decision.expires_at) if decision.expires_at else now + timedelta(hours=1)
                if expires > now:
                    pending.append(decision)
                else:
                    decision.status = "expired"
        
        return pending
    
    def record_trade_outcome(self, trade_result: Dict):
        """Record trade outcome to update circuit breakers."""
        pnl = trade_result.get('pnl', 0)
        
        # Update circuit breaker stats
        self.circuit_breaker.daily_trades += 1
        
        if pnl < 0:
            self.circuit_breaker.consecutive_losses += 1
            self.circuit_breaker.daily_loss += abs(pnl)
            
            # Check breakers
            if self.circuit_breaker.consecutive_losses >= self.circuit_breaker.max_consecutive_losses:
                self._trip_circuit_breaker(f"{self.circuit_breaker.consecutive_losses} consecutive losses")
            
            if self.circuit_breaker.daily_loss >= self.circuit_breaker.max_daily_loss:
                self._trip_circuit_breaker(f"Daily loss ${self.circuit_breaker.daily_loss:.0f} exceeded limit")
        else:
            self.circuit_breaker.consecutive_losses = 0
        
        self._save_circuit_breaker()
    
    def _trip_circuit_breaker(self, reason: str):
        """Trip circuit breaker."""
        self.circuit_breaker.is_tripped = True
        self.circuit_breaker.reason = reason
        self.circuit_breaker.tripped_at = datetime.now().isoformat()
        self.circuit_breaker.auto_reset_at = (datetime.now() + timedelta(hours=24)).isoformat()
        self._save_circuit_breaker()
    
    def reset_circuit_breaker(self, manual: bool = False) -> Dict:
        """Reset circuit breaker."""
        if manual or (self.circuit_breaker.auto_reset_at and 
                     datetime.now() > datetime.fromisoformat(self.circuit_breaker.auto_reset_at)):
            self.circuit_breaker.is_tripped = False
            self.circuit_breaker.reason = ""
            self.circuit_breaker.tripped_at = None
            self.circuit_breaker.consecutive_losses = 0
            self._save_circuit_breaker()
            return {'success': True, 'message': 'Circuit breaker reset'}
        
        return {
            'success': False, 
            'error': f"Cannot reset until {self.circuit_breaker.auto_reset_at}"
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at midnight)."""
        self.circuit_breaker.daily_trades = 0
        self.circuit_breaker.daily_loss = 0.0
        self._save_circuit_breaker()
    
    def get_circuit_breaker_status(self) -> CircuitBreakerStatus:
        """Get current circuit breaker status."""
        return self.circuit_breaker
    
    def set_autonomy_level(self, level: str) -> Dict:
        """Set autonomy level."""
        try:
            self.autonomy_level = AutonomyLevel(level)
            self._save_config()
            return {'success': True, 'level': level}
        except ValueError:
            return {'success': False, 'error': f"Invalid level: {level}"}
    
    def set_risk_limits(self, limits: Dict) -> Dict:
        """Update risk limits."""
        for key, value in limits.items():
            if hasattr(self.risk_limits, key):
                setattr(self.risk_limits, key, value)
        self._save_config()
        return {'success': True, 'limits': self.risk_limits.to_dict()}
    
    def get_engine_status(self) -> Dict:
        """Get decision engine status."""
        return {
            'autonomy_level': self.autonomy_level.value,
            'risk_limits': self.risk_limits.to_dict(),
            'circuit_breaker': self.circuit_breaker.to_dict(),
            'pending_decisions': len(self.get_pending_decisions()),
            'is_active': not self.circuit_breaker.is_tripped
        }
    
    def _save_decision(self, decision: DecisionResult):
        """Save decision to file."""
        try:
            decisions = []
            if self.decisions_file.exists():
                with open(self.decisions_file) as f:
                    decisions = json.load(f)
            
            # Update or add
            found = False
            for i, d in enumerate(decisions):
                if d.get('decision_id') == decision.decision_id:
                    decisions[i] = decision.to_dict()
                    found = True
                    break
            
            if not found:
                decisions.append(decision.to_dict())
            
            # Keep last 100
            decisions = decisions[-100:]
            
            with open(self.decisions_file, 'w') as f:
                json.dump(decisions, f, indent=2)
        except Exception as e:
            print(f"Error saving decision: {e}")
    
    def _save_circuit_breaker(self):
        """Save circuit breaker state."""
        try:
            with open(self.circuit_breaker_file, 'w') as f:
                json.dump(self.circuit_breaker.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving circuit breaker: {e}")
    
    def _load_circuit_breaker(self):
        """Load circuit breaker state."""
        if self.circuit_breaker_file.exists():
            try:
                with open(self.circuit_breaker_file) as f:
                    data = json.load(f)
                self.circuit_breaker = CircuitBreakerStatus(**data)
            except Exception:
                pass
    
    def _save_config(self):
        """Save configuration."""
        try:
            config = {
                'autonomy_level': self.autonomy_level.value,
                'risk_limits': self.risk_limits.to_dict()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _load_config(self):
        """Load configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    config = json.load(f)
                self.autonomy_level = AutonomyLevel(config.get('autonomy_level', 'advisory'))
                if 'risk_limits' in config:
                    self.risk_limits = RiskLimits(**config['risk_limits'])
            except Exception:
                pass


# Singleton instance
decision_engine = DecisionEngine()
