"""
Continuous Learning System - Phase 5 of ML Autonomous Trading Engine

Implements reinforcement learning from trade outcomes and model performance monitoring.
The AI continuously improves by learning from each trade result.

Created: January 18, 2026
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import json
import math
import random

# Import dependencies
try:
    from .trade_logger import trade_logger
    from .style_profiler import style_profiler
except ImportError:
    from trade_logger import trade_logger
    from style_profiler import style_profiler


@dataclass
class TradeExperience:
    """Single experience for reinforcement learning"""
    
    # State when trade was taken
    state: Dict = field(default_factory=dict)
    
    # Action taken
    action: Dict = field(default_factory=dict)
    
    # Reward received
    reward: float = 0.0
    
    # Next state (after trade closed)
    next_state: Dict = field(default_factory=dict)
    
    # Metadata
    trade_id: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """Performance metrics for model monitoring"""
    
    # Win/loss
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # PnL
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # AI-specific
    style_match_avg: float = 0.0
    confidence_avg: float = 0.0
    prediction_accuracy: float = 0.0
    
    # Time period
    period_start: str = ""
    period_end: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dict with NaN values sanitized for JSON."""
        result = asdict(self)
        # Sanitize NaN/Inf values which are not valid JSON
        for key, value in result.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    result[key] = 0.0
        return result


class ReinforcementLearner:
    """
    Reinforcement learning system for continuous improvement.
    
    Uses experience replay and reward shaping to learn from each trade.
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.replay_buffer_file = self.data_dir / 'replay_buffer.json'
        
        # Replay buffer
        self.replay_buffer: deque = deque(maxlen=1000)
        
        # Learning parameters
        self.learning_rate = 0.01
        self.discount_factor = 0.95
        self.exploration_rate = 0.1
        
        # Q-values (simplified - would use neural network in production)
        self.q_values: Dict[str, Dict[str, float]] = {}
        
        # Load existing data
        self._load_replay_buffer()
    
    def learn_from_trade(
        self, 
        trade: Dict,
        outcome: Dict,
        decision_context: Optional[Dict] = None
    ) -> Dict:
        """
        Learn from a completed trade.
        
        Args:
            trade: Trade details
            outcome: Trade outcome (pnl, duration, etc.)
            decision_context: Context when decision was made
            
        Returns:
            Learning result
        """
        # 1. Reconstruct state
        state = self._reconstruct_state(trade, decision_context)
        
        # 2. Encode action
        action = self._encode_action(trade)
        
        # 3. Calculate reward
        reward = self._calculate_reward(outcome, trade)
        
        # 4. Get current state (for next_state)
        next_state = self._get_current_state()
        
        # 5. Create experience
        experience = TradeExperience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            trade_id=trade.get('trade_id', ''),
            timestamp=datetime.now().isoformat()
        )
        
        # 6. Store in replay buffer
        self.replay_buffer.append(experience)
        self._save_replay_buffer()
        
        # 7. Learn from batch if enough experiences
        if len(self.replay_buffer) >= 10:
            self._train_on_batch()
        
        return {
            'success': True,
            'reward': reward,
            'experience_id': experience.trade_id,
            'buffer_size': len(self.replay_buffer)
        }
    
    def _reconstruct_state(self, trade: Dict, context: Optional[Dict]) -> Dict:
        """Reconstruct market/portfolio state when trade was taken."""
        state = {
            # Time features
            'hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            
            # Trade features
            'option_type': 1 if trade.get('option_type', '').lower() == 'call' else 0,
            'action': 1 if trade.get('action', '').upper() == 'BUY' else 0,
            'quantity': trade.get('quantity', 1),
            
            # Price features
            'strike': trade.get('strike', 0),
            'entry_price': trade.get('price', trade.get('entry_price', 0)),
        }
        
        if context:
            state.update({
                'iv': context.get('iv', 0),
                'spot_price': context.get('spot_price', 0),
                'confidence': context.get('confidence', 0),
                'style_match': context.get('style_match', 0),
            })
        
        return state
    
    def _encode_action(self, trade: Dict) -> Dict:
        """Encode trade action."""
        return {
            'action': trade.get('action', 'BUY'),
            'option_type': trade.get('option_type', 'call'),
            'quantity': trade.get('quantity', 1),
            'strike': trade.get('strike', 0),
        }
    
    def _calculate_reward(self, outcome: Dict, trade: Dict) -> float:
        """
        Calculate reward for reinforcement learning.
        
        Reward function considers:
        - PnL (primary)
        - Risk-adjusted return
        - Style consistency
        - Risk management
        """
        reward = 0.0
        
        # Base PnL reward
        pnl = outcome.get('pnl', 0)
        reward += pnl
        
        # Risk-adjusted component
        risk_taken = outcome.get('risk_taken', trade.get('max_loss', abs(pnl)))
        if risk_taken > 0:
            risk_adjusted = pnl / risk_taken
            reward += risk_adjusted * 10  # Scale factor
        
        # Style consistency bonus/penalty
        style_match = outcome.get('style_match', 0.5)
        if style_match > 0.7:
            reward *= 1.2  # 20% bonus for style-consistent trades
        elif style_match < 0.3:
            reward *= 0.8  # 20% penalty for off-style trades
        
        # Risk violation penalty
        if outcome.get('violated_risk_limits', False):
            reward -= 100  # Heavy penalty
        
        # Learning value bonus (new territory explored)
        if outcome.get('novel_trade', False):
            reward += 5  # Small bonus for exploration
        
        return reward
    
    def _get_current_state(self) -> Dict:
        """Get current market/portfolio state."""
        return {
            'hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _train_on_batch(self, batch_size: int = 10):
        """Train on a batch of experiences (simplified Q-learning)."""
        if len(self.replay_buffer) < batch_size:
            return
        
        # Sample batch
        batch = random.sample(list(self.replay_buffer), min(batch_size, len(self.replay_buffer)))
        
        for exp in batch:
            # Get state key
            state_key = self._state_to_key(exp.state)
            action_key = self._action_to_key(exp.action)
            
            # Initialize Q-values if needed
            if state_key not in self.q_values:
                self.q_values[state_key] = {}
            
            # Get current Q-value
            current_q = self.q_values[state_key].get(action_key, 0)
            
            # Get max Q-value for next state
            next_state_key = self._state_to_key(exp.next_state)
            next_q_values = self.q_values.get(next_state_key, {})
            max_next_q = max(next_q_values.values()) if next_q_values else 0
            
            # Q-learning update
            new_q = current_q + self.learning_rate * (
                exp.reward + self.discount_factor * max_next_q - current_q
            )
            
            self.q_values[state_key][action_key] = new_q
    
    def _state_to_key(self, state: Dict) -> str:
        """Convert state dict to hashable key."""
        # Simplified - use hour and option_type
        hour = state.get('hour', 0)
        opt_type = state.get('option_type', 0)
        return f"h{hour}_t{opt_type}"
    
    def _action_to_key(self, action: Dict) -> str:
        """Convert action dict to hashable key."""
        return f"{action.get('action', 'BUY')}_{action.get('option_type', 'call')}"
    
    def get_action_recommendation(self, state: Dict) -> Dict:
        """Get recommended action based on learned Q-values."""
        state_key = self._state_to_key(state)
        
        # Exploration vs exploitation
        if random.random() < self.exploration_rate:
            # Explore: random action
            action = random.choice(['BUY_call', 'BUY_put', 'SELL_call', 'SELL_put'])
            return {
                'action': action.split('_')[0],
                'option_type': action.split('_')[1],
                'source': 'exploration'
            }
        
        # Exploit: best known action
        q_values = self.q_values.get(state_key, {})
        
        if q_values:
            best_action = max(q_values, key=q_values.get)
            parts = best_action.split('_')
            return {
                'action': parts[0] if len(parts) > 0 else 'BUY',
                'option_type': parts[1] if len(parts) > 1 else 'call',
                'q_value': q_values[best_action],
                'source': 'exploitation'
            }
        
        # No data - return default
        return {
            'action': 'BUY',
            'option_type': 'call',
            'source': 'default'
        }
    
    def get_learning_stats(self) -> Dict:
        """Get learning statistics."""
        return {
            'buffer_size': len(self.replay_buffer),
            'states_learned': len(self.q_values),
            'learning_rate': self.learning_rate,
            'exploration_rate': self.exploration_rate,
            'discount_factor': self.discount_factor
        }
    
    def _save_replay_buffer(self):
        """Save replay buffer to file."""
        try:
            data = [exp.to_dict() for exp in self.replay_buffer]
            with open(self.replay_buffer_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving replay buffer: {e}")
    
    def _load_replay_buffer(self):
        """Load replay buffer from file."""
        if self.replay_buffer_file.exists():
            try:
                with open(self.replay_buffer_file) as f:
                    data = json.load(f)
                self.replay_buffer = deque(
                    [TradeExperience(**exp) for exp in data],
                    maxlen=1000
                )
            except Exception:
                pass


class ModelPerformanceMonitor:
    """
    Monitor AI performance vs manual trades.
    Detects drift and triggers retraining when needed.
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.metrics_file = self.data_dir / 'performance_metrics.json'
        self.alerts_file = self.data_dir / 'performance_alerts.json'
        
        # Thresholds
        self.min_win_rate = 0.40
        self.min_profit_factor = 0.8
        self.max_drawdown = 0.20
        self.min_style_match = 0.5
        
        # Monitoring state
        self._recent_trades: List[Dict] = []
        self._alerts: List[Dict] = []
        self._last_metrics: Optional[PerformanceMetrics] = None
    
    def track_trade(self, trade: Dict, is_ai_trade: bool = True):
        """Track a trade for performance monitoring."""
        trade['is_ai_trade'] = is_ai_trade
        trade['tracked_at'] = datetime.now().isoformat()
        self._recent_trades.append(trade)
        
        # Keep last 100 trades
        self._recent_trades = self._recent_trades[-100:]
    
    def calculate_metrics(self, period_days: int = 30) -> PerformanceMetrics:
        """Calculate performance metrics for a period."""
        cutoff = datetime.now() - timedelta(days=period_days)
        
        # Filter trades in period
        period_trades = [
            t for t in self._recent_trades
            if datetime.fromisoformat(t.get('tracked_at', datetime.now().isoformat())) > cutoff
        ]
        
        if not period_trades:
            # Try to get from trade logger
            trades_df = trade_logger.get_recent_trades(period_days)
            if len(trades_df) > 0:
                period_trades = trades_df.to_dict('records')
        
        metrics = PerformanceMetrics(
            period_start=cutoff.isoformat(),
            period_end=datetime.now().isoformat()
        )
        
        if not period_trades:
            return metrics
        
        # Calculate metrics
        metrics.total_trades = len(period_trades)
        
        # Win/loss - extract PnL values and sanitize NaN/Inf
        raw_pnls = [t.get('pnl', t.get('outcome_pnl', 0)) for t in period_trades]
        pnls = []
        for p in raw_pnls:
            try:
                val = float(p) if p is not None else 0.0
                # Sanitize NaN and Inf values
                if math.isnan(val) or math.isinf(val):
                    val = 0.0
                pnls.append(val)
            except (TypeError, ValueError):
                pnls.append(0.0)
        
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        
        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = len(winners) / len(pnls) if pnls else 0
        
        # PnL
        metrics.total_pnl = sum(pnls)
        metrics.avg_win = sum(winners) / len(winners) if winners else 0
        metrics.avg_loss = abs(sum(losers) / len(losers)) if losers else 0
        metrics.profit_factor = (sum(winners) / abs(sum(losers))) if losers and sum(losers) != 0 else 0
        
        # Drawdown
        cumulative = []
        running = 0
        for pnl in pnls:
            running += pnl
            cumulative.append(running)
        
        if cumulative:
            peak = cumulative[0]
            max_dd = 0
            for val in cumulative:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            metrics.max_drawdown = max_dd
        
        # AI-specific metrics
        style_matches = [t.get('style_match', 0.5) for t in period_trades if 'style_match' in t]
        confidences = [t.get('confidence', 0.5) for t in period_trades if 'confidence' in t]
        
        metrics.style_match_avg = sum(style_matches) / len(style_matches) if style_matches else 0
        metrics.confidence_avg = sum(confidences) / len(confidences) if confidences else 0
        
        # Prediction accuracy
        predictions = [(t.get('predicted_win', False), t.get('pnl', 0) > 0) for t in period_trades if 'predicted_win' in t]
        if predictions:
            correct = sum(1 for pred, actual in predictions if pred == actual)
            metrics.prediction_accuracy = correct / len(predictions)
        
        self._last_metrics = metrics
        self._save_metrics(metrics)
        self._check_alerts(metrics)
        
        return metrics
    
    def detect_model_drift(self) -> Dict:
        """Detect if AI behavior has drifted from trader's style."""
        style = style_profiler.get_cached_profile()
        
        if not style or not self._recent_trades:
            return {
                'drift_detected': False,
                'reason': 'Insufficient data'
            }
        
        # Compare recent AI trades to style profile
        ai_trades = [t for t in self._recent_trades if t.get('is_ai_trade', False)]
        
        if len(ai_trades) < 10:
            return {
                'drift_detected': False,
                'reason': 'Need more AI trades for drift detection'
            }
        
        # Check call/put preference drift
        ai_calls = sum(1 for t in ai_trades if t.get('option_type', '').lower() == 'call')
        ai_call_pref = ai_calls / len(ai_trades)
        call_drift = abs(ai_call_pref - style.call_preference)
        
        # Check timing drift
        ai_hours = [datetime.fromisoformat(t.get('tracked_at', datetime.now().isoformat())).hour for t in ai_trades]
        timing_match = sum(1 for h in ai_hours if h in style.preferred_entry_hours) / len(ai_hours) if style.preferred_entry_hours else 1
        
        drift_detected = call_drift > 0.3 or timing_match < 0.5
        
        return {
            'drift_detected': drift_detected,
            'call_preference_drift': round(call_drift, 2),
            'timing_match': round(timing_match, 2),
            'recommendation': 'Consider retraining model' if drift_detected else 'Model behavior aligned'
        }
    
    def _check_alerts(self, metrics: PerformanceMetrics):
        """Check metrics and generate alerts if needed."""
        alerts = []
        
        if metrics.win_rate < self.min_win_rate:
            alerts.append({
                'type': 'low_win_rate',
                'message': f"Win rate ({metrics.win_rate:.0%}) below threshold ({self.min_win_rate:.0%})",
                'severity': 'warning',
                'timestamp': datetime.now().isoformat()
            })
        
        if metrics.profit_factor > 0 and metrics.profit_factor < self.min_profit_factor:
            alerts.append({
                'type': 'low_profit_factor',
                'message': f"Profit factor ({metrics.profit_factor:.2f}) below threshold ({self.min_profit_factor:.2f})",
                'severity': 'warning',
                'timestamp': datetime.now().isoformat()
            })
        
        if metrics.max_drawdown > self.max_drawdown:
            alerts.append({
                'type': 'high_drawdown',
                'message': f"Drawdown ({metrics.max_drawdown:.0%}) exceeds limit ({self.max_drawdown:.0%})",
                'severity': 'critical',
                'timestamp': datetime.now().isoformat()
            })
        
        if metrics.style_match_avg < self.min_style_match:
            alerts.append({
                'type': 'style_drift',
                'message': f"Style match ({metrics.style_match_avg:.0%}) below threshold ({self.min_style_match:.0%})",
                'severity': 'info',
                'timestamp': datetime.now().isoformat()
            })
        
        self._alerts.extend(alerts)
        self._alerts = self._alerts[-50:]  # Keep last 50
        
        if alerts:
            self._save_alerts()
    
    def should_retrain(self) -> Tuple[bool, str]:
        """Determine if model should be retrained."""
        if not self._last_metrics:
            return False, "No metrics available"
        
        metrics = self._last_metrics
        
        # Check for retraining triggers
        if metrics.win_rate < 0.35:
            return True, f"Win rate ({metrics.win_rate:.0%}) critically low"
        
        if metrics.profit_factor > 0 and metrics.profit_factor < 0.5:
            return True, f"Profit factor ({metrics.profit_factor:.2f}) critically low"
        
        if metrics.max_drawdown > 0.30:
            return True, f"Drawdown ({metrics.max_drawdown:.0%}) too high"
        
        drift = self.detect_model_drift()
        if drift.get('drift_detected'):
            return True, "Model behavior drifted from style"
        
        return False, "Model performing within acceptable range"
    
    def get_alerts(self, severity: Optional[str] = None) -> List[Dict]:
        """Get performance alerts."""
        if severity:
            return [a for a in self._alerts if a.get('severity') == severity]
        return self._alerts
    
    def get_monitoring_summary(self) -> Dict:
        """Get comprehensive monitoring summary."""
        metrics = self._last_metrics
        drift = self.detect_model_drift()
        should_retrain, retrain_reason = self.should_retrain()
        
        return {
            'metrics': metrics.to_dict() if metrics else None,
            'drift_detection': drift,
            'should_retrain': should_retrain,
            'retrain_reason': retrain_reason,
            'recent_alerts': self._alerts[-5:],
            'trades_tracked': len(self._recent_trades)
        }
    
    def _save_metrics(self, metrics: PerformanceMetrics):
        """Save metrics to file."""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving metrics: {e}")
    
    def _save_alerts(self):
        """Save alerts to file."""
        try:
            with open(self.alerts_file, 'w') as f:
                json.dump(self._alerts, f, indent=2)
        except Exception as e:
            print(f"Error saving alerts: {e}")


# Singleton instances
reinforcement_learner = ReinforcementLearner()
model_monitor = ModelPerformanceMonitor()
