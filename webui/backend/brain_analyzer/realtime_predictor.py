"""
Real-Time Bot Brain Predictor

Single Responsibility: Predict bot's next actions based on current state and market conditions.

This module:
1. Reads ALL bot files silently (no interference)
2. Analyzes current market conditions
3. Predicts what bot will do next in different scenarios
4. Provides real-time decision flow with confidence scores
5. Shows alternative paths based on market changes

Key Features:
- Non-intrusive file reading (read-only)
- Market condition simulation
- Confidence scoring for predictions
- Alternative scenario analysis
- Real-time state monitoring
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class MarketCondition(Enum):
    """Market condition types for prediction scenarios"""
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    EMERGENCY = "emergency"
    POSITION_LIMIT = "position_limit"
    PRICE_CRASH = "price_crash"
    PRICE_PUMP = "price_pump"


@dataclass
class PredictionScenario:
    """A prediction scenario with confidence score"""
    condition: MarketCondition
    next_action: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    estimated_time: str
    price_trigger: Optional[float] = None
    alternative_actions: List[str] = None


class RealTimeBotPredictor:
    """
    Predicts bot's next actions by analyzing current state and market conditions.
    
    This is a READ-ONLY analyzer that doesn't interfere with bot operations.
    """
    
    def __init__(self, bot_root: Path):
        """Initialize predictor with bot root directory"""
        self.bot_root = Path(bot_root)
        self.state_dir = self.bot_root / 'bot' / 'state'
        self.config_file = self.bot_root / 'config.yaml'
        self.strategy_dir = self.bot_root / 'bot' / 'strategy'
        
        # Cache for file monitoring
        self._file_cache = {}
        self._last_scan = 0
        
        log.info(f"RealTimeBotPredictor initialized: {self.bot_root}")
    
    def get_comprehensive_prediction(self) -> Dict[str, Any]:
        """
        Get comprehensive prediction of bot's next actions.
        
        Returns:
            Complete prediction analysis with scenarios and confidence scores
        """
        try:
            # Read current state
            current_state = self._read_complete_state()
            
            # Analyze market conditions
            market_analysis = self._analyze_market_conditions(current_state)
            
            # Generate prediction scenarios
            scenarios = self._generate_prediction_scenarios(current_state, market_analysis)
            
            # Determine most likely next action
            primary_prediction = self._get_primary_prediction(scenarios, current_state)
            
            # Calculate confidence metrics
            confidence_metrics = self._calculate_confidence_metrics(scenarios, current_state)
            
            return {
                'timestamp': time.time(),
                'current_state': current_state,
                'market_analysis': market_analysis,
                'primary_prediction': primary_prediction,
                'alternative_scenarios': scenarios,
                'confidence_metrics': confidence_metrics,
                'next_decision_point': self._estimate_next_decision_time(current_state),
                'risk_factors': self._identify_risk_factors(current_state),
                'monitoring_alerts': self._generate_monitoring_alerts(current_state)
            }
            
        except Exception as e:
            log.error(f"Error generating comprehensive prediction: {e}")
            import traceback
            log.error(traceback.format_exc())
            return {'error': str(e), 'timestamp': time.time()}
    
    def _read_complete_state(self) -> Dict[str, Any]:
        """Read complete bot state from all relevant files"""
        state = {}
        
        try:
            # Runtime state
            runtime_file = self.state_dir / 'positions.json'
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    state['positions'] = json.load(f)
            
            # Volatility status (REAL DATA)
            vol_file = self.bot_root / '.volatility_status.json'
            if vol_file.exists():
                with open(vol_file, 'r') as f:
                    state['volatility'] = json.load(f)
            
            # Volatility halt
            halt_file = self.bot_root / '.volatility_halt.json'
            if halt_file.exists():
                with open(halt_file, 'r') as f:
                    state['halt'] = json.load(f)
            
            # Grid config (REAL DATA)
            if self.config_file.exists():
                config = {}
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip().strip('"').strip("'")
                state['config'] = config
            
            # Recent logs (last 50 lines for context)
            log_file = self.bot_root / 'bot' / 'logs' / 'bot.log'
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        state['recent_logs'] = lines[-50:] if len(lines) > 50 else lines
                except Exception as e:
                    log.warning(f"Could not read log file: {e}")
                    state['recent_logs'] = []
            
            return state
            
        except Exception as e:
            log.error(f"Error reading complete state: {e}")
            return {}
    
    def _analyze_market_conditions(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current market conditions using REAL data"""
        analysis = {
            'condition': 'normal',
            'volatility_level': 'normal',
            'price_trend': 'stable',
            'risk_level': 'low',
            'trading_safe': True
        }
        
        try:
            # Check volatility (REAL DATA from .volatility_status.json)
            vol_data = state.get('volatility', {})
            
            if vol_data:
                iv = vol_data.get('iv', 0)
                rv = vol_data.get('rv', 0)
                is_safe = vol_data.get('is_safe', True)
                violation_reason = vol_data.get('violation_reason', '')
                thresholds = vol_data.get('thresholds', {})
                max_iv = thresholds.get('max_iv', 35)
                max_rv = thresholds.get('max_rv', 40)
                
                if not is_safe:
                    analysis['condition'] = 'high_volatility'
                    analysis['volatility_level'] = 'high'
                    analysis['risk_level'] = 'high'
                    analysis['trading_safe'] = False
                    analysis['violation_reason'] = violation_reason
                
                analysis['current_iv'] = iv
                analysis['current_rv'] = rv
                analysis['iv_percentage'] = (iv / max_iv) * 100 if max_iv > 0 else 0
                analysis['rv_percentage'] = (rv / max_rv) * 100 if max_rv > 0 else 0
            
            # Check halt status
            halt_data = state.get('halt', {})
            if halt_data.get('is_halted'):
                analysis['condition'] = 'high_volatility'
                analysis['trading_safe'] = False
                analysis['missed_levels'] = len(halt_data.get('missed_levels', []))
            
            # Check positions (REAL CONFIG)
            pos_data = state.get('positions', {})
            positions = pos_data.get('positions', [])
            config = state.get('config', {})
            max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
            
            if len(positions) >= max_positions:
                analysis['condition'] = 'position_limit'
                analysis['position_utilization'] = 100.0
            else:
                analysis['position_utilization'] = (len(positions) / max_positions) * 100
            
            # Analyze recent logs for patterns
            recent_logs = state.get('recent_logs', [])
            error_count = sum(1 for line in recent_logs if 'ERROR' in line)
            if error_count > 5:
                analysis['risk_level'] = 'medium'
                analysis['error_frequency'] = 'high'
            
            return analysis
            
        except Exception as e:
            log.error(f"Error analyzing market conditions: {e}")
            return analysis
    
    def _generate_prediction_scenarios(self, state: Dict[str, Any], market: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate prediction scenarios using REAL bot configuration"""
        scenarios = []
        
        try:
            current_condition = market.get('condition')
            pos_data = state.get('positions', {})
            positions = pos_data.get('positions', [])
            pending_buy = pos_data.get('pending_buy_order')
            config = state.get('config', {})
            
            # REAL CONFIG VALUES
            grid_step = float(config.get('GRIDBOT_STEP', 1000))
            ref_price = float(config.get('GRIDBOT_REF', 110000))
            max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
            trading_mode = config.get('TRADING_MODE', 'demo')
            
            # Scenario 1: High volatility (REAL CONDITION)
            if not market.get('trading_safe', True):
                violation = market.get('violation_reason', 'Volatility limits exceeded')
                scenarios.append({
                    'condition': 'high_volatility',
                    'next_action': f"Trading HALTED: {violation}",
                    'confidence': 0.95,
                    'reasoning': f"Real volatility data shows unsafe conditions: {violation}",
                    'estimated_time': "Until volatility normalizes",
                    'alternative_actions': ["Monitor volatility", "Track missed levels"]
                })
            
            # Scenario 2: Normal conditions - check positions
            elif len(positions) >= max_positions:
                scenarios.append({
                    'condition': 'position_limit',
                    'next_action': f"Wait for TP fills (max {max_positions} positions reached)",
                    'confidence': 0.95,
                    'reasoning': f"Currently {len(positions)}/{max_positions} positions open",
                    'estimated_time': "Until market moves up by ₹{:,.0f}".format(grid_step),
                    'alternative_actions': ["Monitor for emergency exit conditions"]
                })
            
            # Scenario 3: Can place new BUY order
            elif pending_buy:
                scenarios.append({
                    'condition': 'normal',
                    'next_action': f"Monitor pending BUY at ₹{pending_buy.get('price', 0):,.0f}",
                    'confidence': 0.9,
                    'reasoning': "Pending BUY order exists, waiting for fill",
                    'estimated_time': "1-30 minutes (market dependent)",
                    'price_trigger': pending_buy.get('price'),
                    'alternative_actions': ["Cancel if volatility spikes"]
                })
            
            else:
                # Calculate next BUY price based on REAL grid logic
                if positions:
                    # Find lowest position, place BUY below it
                    lowest_entry = min([p.get('entry_price', ref_price) for p in positions])
                    next_buy_price = lowest_entry - grid_step
                else:
                    # No positions, start from reference
                    next_buy_price = ref_price - grid_step
                
                scenarios.append({
                    'condition': 'normal',
                    'next_action': f"Place BUY order at ₹{next_buy_price:,.0f}",
                    'confidence': 0.85,
                    'reasoning': f"Grid step: ₹{grid_step:,.0f}, {len(positions)} positions open",
                    'estimated_time': "Within 30 seconds",
                    'price_trigger': next_buy_price,
                    'alternative_actions': ["Adjust for market conditions"]
                })
            
            # Scenario 4: Fill detection and TP placement
            if pending_buy:
                tp_price = pending_buy.get('price', 0) + grid_step
                scenarios.append({
                    'condition': 'normal',
                    'next_action': f"Place TP at ₹{tp_price:,.0f} when BUY fills",
                    'confidence': 0.9,
                    'reasoning': "Automatic TP placement after BUY execution",
                    'estimated_time': "Within 5 seconds of fill",
                    'price_trigger': tp_price,
                    'alternative_actions': ["Retry if TP placement fails"]
                })
            
            return scenarios
            
        except Exception as e:
            log.error(f"Error generating prediction scenarios: {e}")
            return []
    
    def _get_primary_prediction(self, scenarios: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the most likely next action"""
        if not scenarios:
            return {
                'action': 'Monitor market conditions',
                'confidence': 0.5,
                'reasoning': 'No clear prediction available'
            }
        
        # Sort by confidence and select highest
        primary = max(scenarios, key=lambda s: s['confidence'])
        
        return {
            'action': primary['next_action'],
            'confidence': primary['confidence'],
            'reasoning': primary['reasoning'],
            'estimated_time': primary['estimated_time'],
            'price_trigger': primary.get('price_trigger'),
            'condition': primary['condition'],
            'alternative_actions': primary.get('alternative_actions', [])
        }
    
    def _calculate_confidence_metrics(self, scenarios: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence metrics for predictions"""
        if not scenarios:
            return {'overall_confidence': 0.5, 'prediction_quality': 'low'}
        
        confidences = [s['confidence'] for s in scenarios]
        avg_confidence = sum(confidences) / len(confidences)
        max_confidence = max(confidences)
        
        # Determine prediction quality
        quality = 'low'
        if max_confidence > 0.8:
            quality = 'high'
        elif max_confidence > 0.6:
            quality = 'medium'
        
        return {
            'overall_confidence': avg_confidence,
            'max_confidence': max_confidence,
            'prediction_quality': quality,
            'scenario_count': len(scenarios),
            'confidence_range': f"{min(confidences):.1f} - {max(confidences):.1f}"
        }
    
    def _estimate_next_decision_time(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate when the next decision point will occur"""
        try:
            pos_data = state.get('positions', {})
            pending_buy = pos_data.get('pending_buy_order')
            
            if pending_buy:
                return {
                    'type': 'fill_monitoring',
                    'description': 'Monitoring pending BUY for fill',
                    'estimated_seconds': 60,
                    'trigger': 'Market price movement'
                }
            
            vol_data = state.get('volatility', {})
            if vol_data.get('is_safe', True):
                return {
                    'type': 'order_placement',
                    'description': 'Next BUY order placement',
                    'estimated_seconds': 30,
                    'trigger': 'Grid calculation complete'
                }
            else:
                return {
                    'type': 'volatility_check',
                    'description': 'Volatility safety recheck',
                    'estimated_seconds': 10,
                    'trigger': 'Volatility monitor cycle'
                }
                
        except Exception as e:
            log.error(f"Error estimating next decision time: {e}")
            return {
                'type': 'unknown',
                'description': 'Unable to estimate',
                'estimated_seconds': 60
            }
    
    def _identify_risk_factors(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify current risk factors using REAL data"""
        risks = []
        
        try:
            # Volatility risk (REAL DATA)
            vol_data = state.get('volatility', {})
            if not vol_data.get('is_safe', True):
                risks.append({
                    'type': 'volatility',
                    'severity': 'high',
                    'description': f"Volatility unsafe: {vol_data.get('violation_reason', 'Unknown')}",
                    'impact': 'Trading halted'
                })
            
            # Position concentration risk
            pos_data = state.get('positions', {})
            positions = pos_data.get('positions', [])
            config = state.get('config', {})
            max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
            
            if len(positions) >= max_positions * 0.8:  # 80% of max
                risks.append({
                    'type': 'position_concentration',
                    'severity': 'medium',
                    'description': f"High position utilization: {len(positions)}/{max_positions}",
                    'impact': 'Limited new entry capacity'
                })
            
            # Error frequency risk
            recent_logs = state.get('recent_logs', [])
            error_count = sum(1 for line in recent_logs if 'ERROR' in line)
            if error_count > 3:
                risks.append({
                    'type': 'system_errors',
                    'severity': 'medium',
                    'description': f"High error frequency: {error_count} errors in recent logs",
                    'impact': 'Potential system instability'
                })
            
            return risks
            
        except Exception as e:
            log.error(f"Error identifying risk factors: {e}")
            return []
    
    def _generate_monitoring_alerts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate monitoring alerts using REAL data"""
        alerts = []
        
        try:
            # Volatility monitoring (REAL DATA)
            vol_data = state.get('volatility', {})
            if vol_data:
                iv = vol_data.get('iv', 0)
                rv = vol_data.get('rv', 0)
                thresholds = vol_data.get('thresholds', {})
                max_iv = thresholds.get('max_iv', 35)
                max_rv = thresholds.get('max_rv', 40)
                
                if iv > max_iv * 0.8:  # 80% of threshold
                    alerts.append({
                        'type': 'volatility_warning',
                        'message': f"IV approaching limit: {iv:.1f}% (limit: {max_iv}%)",
                        'urgency': 'medium'
                    })
                
                if rv > max_rv * 0.8:
                    alerts.append({
                        'type': 'volatility_warning',
                        'message': f"RV approaching limit: {rv:.1f}% (limit: {max_rv}%)",
                        'urgency': 'high'
                    })
            
            # Position monitoring
            pos_data = state.get('positions', {})
            pending_buy = pos_data.get('pending_buy_order')
            if pending_buy:
                alerts.append({
                    'type': 'order_monitoring',
                    'message': f"Monitoring BUY order at ₹{pending_buy.get('price', 0):,.0f}",
                    'urgency': 'low'
                })
            
            return alerts
            
        except Exception as e:
            log.error(f"Error generating monitoring alerts: {e}")
            return []
    
    def _estimate_current_price(self, state: Dict[str, Any]) -> Optional[float]:
        """Estimate current market price from available data"""
        try:
            # Try to get from recent positions
            pos_data = state.get('positions', {})
            positions = pos_data.get('positions', [])
            if positions:
                # Use most recent position entry price as approximation
                latest_pos = max(positions, key=lambda p: p.get('timestamp', 0))
                return float(latest_pos.get('entry_price', 0))
            
            # Fallback to reference price from REAL config
            config = state.get('config', {})
            return float(config.get('GRIDBOT_REF', 110000))
            
        except Exception as e:
            log.error(f"Error estimating current price: {e}")
            return None