"""
Robust Interactive Bot Simulator

Production-ready simulator that integrates with existing brain analyzer components.
Uses strategy analysis, decision flow, and action sequences for comprehensive simulation.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)


class RobustBotSimulator:
    """
    Production-ready bot simulator using existing brain analyzer infrastructure.
    
    Integrates with:
    - Strategy analysis endpoints
    - Decision flow graph
    - Action sequences
    - Real-time predictor
    """
    
    def __init__(self, bot_root: Path):
        self.bot_root = Path(bot_root)
        
        # Import existing components
        from .realtime_predictor import RealTimeBotPredictor
        from .flow_generator import FlowGraphGenerator
        from .state_reader import BotStateReader
        
        self.predictor = RealTimeBotPredictor(bot_root)
        self.flow_generator = FlowGraphGenerator()
        self.state_reader = BotStateReader(bot_root)
    
    def get_simulation_tree(self) -> Dict[str, Any]:
        """Get comprehensive simulation tree using existing components"""
        try:
            # Get current predictions
            predictions = self.predictor.get_comprehensive_prediction()
            if 'error' in predictions:
                return {'success': False, 'error': predictions['error']}
            
            # Get bot state
            bot_state = self.state_reader.get_complete_state()
            
            # Get strategy analysis
            strategy_data = self._get_strategy_analysis()
            
            # Build simulation tree
            simulation_tree = self._build_simulation_tree(predictions, bot_state, strategy_data)
            
            return {
                'success': True,
                'simulation_tree': simulation_tree,
                'current_state': bot_state,
                'predictions': predictions,
                'timestamp': time.time()
            }
            
        except Exception as e:
            log.error(f"Error building simulation tree: {e}")
            return {'success': False, 'error': str(e)}
    
    def simulate_path(self, scenario: str, steps: List[str] = None) -> Dict[str, Any]:
        """Simulate specific decision path using existing logic"""
        try:
            steps = steps or []
            
            # Get current state and predictions
            predictions = self.predictor.get_comprehensive_prediction()
            bot_state = self.state_reader.get_complete_state()
            strategy_data = self._get_strategy_analysis()
            
            # Simulate based on scenario
            if scenario == 'current':
                return self._simulate_current_path(predictions, bot_state, steps)
            elif scenario == 'volatility_safe':
                return self._simulate_volatility_safe_path(bot_state, strategy_data, steps)
            elif scenario == 'volatility_unsafe':
                return self._simulate_volatility_unsafe_path(bot_state, steps)
            elif scenario == 'position_limit':
                return self._simulate_position_limit_path(bot_state, strategy_data, steps)
            elif scenario == 'grid_expansion':
                return self._simulate_grid_expansion_path(bot_state, strategy_data, steps)
            else:
                return {'success': False, 'error': f'Unknown scenario: {scenario}'}
                
        except Exception as e:
            log.error(f"Error simulating path: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_strategy_analysis(self) -> Dict[str, Any]:
        """Get strategy analysis using existing endpoint logic"""
        try:
            # Import strategy analysis function
            from webui.backend.routes.strategy import analyze_current_strategy
            return analyze_current_strategy()
        except Exception as e:
            log.error(f"Error getting strategy analysis: {e}")
            return {}
    
    def _build_simulation_tree(self, predictions: Dict, bot_state: Dict, strategy_data: Dict) -> Dict[str, Any]:
        """Build comprehensive simulation tree"""
        
        market_analysis = predictions.get('market_analysis', {})
        primary_prediction = predictions.get('primary_prediction', {})
        
        # Root node based on REAL current state
        config = bot_state.get('config', {})
        vol_data = bot_state.get('volatility', {})
        positions = bot_state.get('positions', {}).get('positions', [])
        
        root = {
            'id': 'root',
            'title': 'REAL Bot Decision Simulator',
            'current_state': {
                'trading_safe': market_analysis.get('trading_safe', True),
                'volatility_condition': market_analysis.get('condition', 'normal'),
                'positions': len(positions),
                'max_positions': config.get('max_positions', 3),
                'primary_action': primary_prediction.get('action', 'Unknown'),
                'confidence': primary_prediction.get('confidence', 0),
                'grid_step': config.get('grid_step', 1000),
                'reference_price': config.get('reference_price', 110000),
                'current_iv': vol_data.get('current_iv', 0),
                'current_rv': vol_data.get('current_rv', 0),
                'is_safe': vol_data.get('is_safe', True),
                'violation_reason': vol_data.get('violation_reason', '')
            },
            'scenarios': []
        }
        
        # Add scenario branches
        root['scenarios'] = [
            self._build_current_scenario(predictions, bot_state),
            self._build_volatility_safe_scenario(bot_state, strategy_data),
            self._build_volatility_unsafe_scenario(bot_state),
            self._build_position_limit_scenario(bot_state, strategy_data),
            self._build_grid_expansion_scenario(bot_state, strategy_data)
        ]
        
        return root
    
    def _build_current_scenario(self, predictions: Dict, bot_state: Dict) -> Dict[str, Any]:
        """Build current state scenario using REAL bot state"""
        market_analysis = predictions.get('market_analysis', {})
        primary_prediction = predictions.get('primary_prediction', {})
        
        # Get REAL configuration and state
        config = bot_state.get('config', {})
        vol_data = bot_state.get('volatility', {})
        positions = bot_state.get('positions', {}).get('positions', [])
        
        return {
            'id': 'current',
            'title': '📊 Current State Analysis',
            'description': f"REAL Bot State: {primary_prediction.get('action', 'Unknown')}",
            'confidence': primary_prediction.get('confidence', 0),
            'details': {
                'condition': market_analysis.get('condition', 'normal'),
                'trading_safe': market_analysis.get('trading_safe', True),
                'violation_reason': market_analysis.get('violation_reason', ''),
                'next_action': primary_prediction.get('action', 'Unknown'),
                'estimated_time': primary_prediction.get('estimated_time', 'Unknown'),
                'grid_step': config.get('grid_step', 1000),
                'reference_price': config.get('reference_price', 110000),
                'max_positions': config.get('max_positions', 3),
                'current_positions': len(positions),
                'current_iv': vol_data.get('current_iv', 0),
                'current_rv': vol_data.get('current_rv', 0),
                'is_safe': vol_data.get('is_safe', True)
            },
            'next_steps': self._get_current_next_steps(predictions, bot_state)
        }
    
    def _build_volatility_safe_scenario(self, bot_state: Dict, strategy_data: Dict) -> Dict[str, Any]:
        """Build volatility safe scenario using REAL grid configuration"""
        config = bot_state.get('config', {})
        positions = bot_state.get('positions', {}).get('positions', [])
        
        # Use REAL grid configuration from config.yaml
        grid_step = float(config.get('grid_step', 1000))
        ref_price = float(config.get('reference_price', 110000))
        max_positions = config.get('max_positions', 3)
        
        # Calculate next buy price based on REAL positions
        if positions:
            lowest_entry = min([p.get('entry_price', ref_price) for p in positions])
            next_buy_price = lowest_entry - grid_step
        else:
            next_buy_price = ref_price - grid_step
        
        return {
            'id': 'volatility_safe',
            'title': '✅ Volatility Safe Scenario',
            'description': f'Normal trading with STEP={grid_step}, REF={ref_price}',
            'confidence': 0.9,
            'details': {
                'condition': 'normal',
                'positions_available': max_positions - len(positions),
                'next_buy_price': next_buy_price,
                'grid_step': grid_step,
                'reference_price': ref_price,
                'max_positions': max_positions,
                'can_trade': True
            },
            'next_steps': self._get_volatility_safe_steps(bot_state, next_buy_price, grid_step)
        }
    
    def _build_volatility_unsafe_scenario(self, bot_state: Dict) -> Dict[str, Any]:
        """Build volatility unsafe scenario using REAL volatility data"""
        vol_data = bot_state.get('volatility', {})
        
        # Use REAL volatility data from .volatility_status.json
        current_iv = vol_data.get('current_iv', vol_data.get('iv', 0))
        current_rv = vol_data.get('current_rv', vol_data.get('rv', 0))
        max_iv = vol_data.get('max_iv', 35)
        max_rv = vol_data.get('max_rv', 40)
        
        return {
            'id': 'volatility_unsafe',
            'title': '🚨 Volatility Unsafe Scenario',
            'description': f'REAL: IV={current_iv:.1f}%, RV={current_rv:.1f}% - Trading halted',
            'confidence': 0.95,
            'details': {
                'condition': 'high_volatility',
                'violation_reason': vol_data.get('violation_reason', 'Volatility limits exceeded'),
                'current_iv': current_iv,
                'current_rv': current_rv,
                'max_iv_threshold': max_iv,
                'max_rv_threshold': max_rv,
                'is_safe': vol_data.get('is_safe', True),
                'trading_halted': True
            },
            'next_steps': self._get_volatility_unsafe_steps(bot_state)
        }
    
    def _build_position_limit_scenario(self, bot_state: Dict, strategy_data: Dict) -> Dict[str, Any]:
        """Build position limit scenario using REAL configuration"""
        positions = bot_state.get('positions', {}).get('positions', [])
        config = bot_state.get('config', {})
        max_positions = config.get('max_positions', 3)
        grid_step = config.get('grid_step', 1000)
        
        return {
            'id': 'position_limit',
            'title': '🔒 Position Limit Scenario',
            'description': f'REAL: Max positions reached ({len(positions)}/{max_positions}) - GRIDBOT_MAX_OPEN={max_positions}',
            'confidence': 0.95,
            'details': {
                'condition': 'position_limit',
                'current_positions': len(positions),
                'max_positions': max_positions,
                'grid_step': grid_step,
                'reference_price': config.get('reference_price', 110000),
                'waiting_for_exits': True,
                'position_details': [{
                    'entry_price': p.get('entry_price', 0),
                    'quantity': p.get('quantity', 0),
                    'pnl': p.get('pnl', 0)
                } for p in positions] if positions else []
            },
            'next_steps': self._get_position_limit_steps(bot_state)
        }
    
    def _build_grid_expansion_scenario(self, bot_state: Dict, strategy_data: Dict) -> Dict[str, Any]:
        """Build grid expansion scenario using REAL configuration"""
        config = bot_state.get('config', {})
        positions = bot_state.get('positions', {}).get('positions', [])
        
        grid_step = float(config.get('grid_step', 1000))
        max_positions = config.get('max_positions', 3)
        lot_size = config.get('lot_size', 1)
        
        # Calculate potential expansion based on REAL settings
        available_slots = max_positions - len(positions)
        expansion_levels = min(3, available_slots)
        total_exposure = grid_step * expansion_levels * lot_size
        
        return {
            'id': 'grid_expansion',
            'title': '📈 Grid Expansion Scenario',
            'description': f'REAL: Fill {expansion_levels} levels (STEP={grid_step}, LOT={lot_size})',
            'confidence': 0.8,
            'details': {
                'condition': 'grid_expansion',
                'grid_step': grid_step,
                'lot_size': lot_size,
                'expansion_levels': expansion_levels,
                'available_slots': available_slots,
                'current_positions': len(positions),
                'max_positions': max_positions,
                'total_exposure': total_exposure,
                'reference_price': config.get('reference_price', 110000)
            },
            'next_steps': self._get_grid_expansion_steps(bot_state)
        }
    
    def _simulate_current_path(self, predictions: Dict, bot_state: Dict, steps: List[str]) -> Dict[str, Any]:
        """Simulate current state path"""
        primary_prediction = predictions.get('primary_prediction', {})
        market_analysis = predictions.get('market_analysis', {})
        
        if len(steps) == 0:
            return {
                'success': True,
                'scenario': 'current',
                'step': 1,
                'decision': {
                    'title': 'Current Bot State',
                    'description': primary_prediction.get('action', 'Unknown action'),
                    'confidence': primary_prediction.get('confidence', 0),
                    'reasoning': primary_prediction.get('reasoning', 'No reasoning available'),
                    'details': {
                        'trading_safe': market_analysis.get('trading_safe', True),
                        'condition': market_analysis.get('condition', 'normal'),
                        'estimated_time': primary_prediction.get('estimated_time', 'Unknown')
                    }
                },
                'options': [
                    {
                        'id': 'explore_safe',
                        'title': 'Explore if volatility becomes safe',
                        'choice': 'volatility_safe'
                    },
                    {
                        'id': 'explore_unsafe',
                        'title': 'Explore if volatility stays unsafe',
                        'choice': 'volatility_unsafe'
                    }
                ]
            }
        
        return {'success': False, 'error': 'Invalid step sequence'}
    
    def _simulate_volatility_safe_path(self, bot_state: Dict, strategy_data: Dict, steps: List[str]) -> Dict[str, Any]:
        """Simulate volatility safe trading path using REAL configuration"""
        config = bot_state.get('config', {})
        positions = bot_state.get('positions', {}).get('positions', [])
        
        # Use REAL configuration values
        grid_step = float(config.get('grid_step', 1000))
        ref_price = float(config.get('reference_price', 110000))
        max_positions = config.get('max_positions', 3)
        lot_size = config.get('lot_size', 1)
        
        if len(steps) == 0:
            # Step 1: Check position availability
            if len(positions) >= max_positions:
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 1,
                    'decision': {
                        'title': 'Position Limit Reached',
                        'description': f'REAL: Bot has {len(positions)}/{max_positions} positions (MAX_OPEN={max_positions})',
                        'confidence': 0.95,
                        'action': 'wait_for_tp_fills',
                        'details': {
                            'current_positions': len(positions),
                            'max_positions': max_positions,
                            'grid_step': grid_step,
                            'reference_price': ref_price
                        }
                    },
                    'options': [
                        {'id': 'wait_tp', 'title': 'Wait for TP fills', 'choice': 'wait_tp'},
                        {'id': 'simulate_tp', 'title': 'Simulate TP fill', 'choice': 'tp_filled'}
                    ]
                }
            else:
                next_buy_price = ref_price - grid_step if not positions else min([p.get('entry_price', ref_price) for p in positions]) - grid_step
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 1,
                    'decision': {
                        'title': 'Place BUY Order',
                        'description': f'REAL: BUY at ₹{next_buy_price:,.0f} (REF={ref_price}, STEP={grid_step})',
                        'confidence': 0.85,
                        'action': f'place_buy_order({next_buy_price})',
                        'details': {
                            'price': next_buy_price,
                            'quantity': lot_size,
                            'grid_level': len(positions) + 1,
                            'grid_step': grid_step,
                            'reference_price': ref_price
                        }
                    },
                    'options': [
                        {'id': 'place_buy', 'title': 'Place BUY order', 'choice': 'buy_placed'},
                        {'id': 'monitor_pending', 'title': 'Monitor pending order', 'choice': 'monitor_buy'}
                    ]
                }
        
        elif len(steps) == 1 and steps[0] == 'buy_placed':
            # Step 2: BUY order placed, now place TP
            entry_price = ref_price - grid_step
            tp_price = entry_price + grid_step
            
            return {
                'success': True,
                'scenario': 'volatility_safe',
                'step': 2,
                'decision': {
                    'title': 'Place TP Order',
                    'description': f'REAL: TP at ₹{tp_price:,.0f} (Entry + STEP = {entry_price} + {grid_step})',
                    'confidence': 0.9,
                    'action': f'place_tp_order({tp_price})',
                    'details': {
                        'entry_price': entry_price,
                        'tp_price': tp_price,
                        'profit_target': grid_step,
                        'lot_size': lot_size
                    }
                },
                'options': [
                    {'id': 'tp_placed', 'title': 'TP order placed', 'choice': 'tp_placed'},
                    {'id': 'continue_grid', 'title': 'Continue grid expansion', 'choice': 'next_level'}
                ]
            }
        
        elif len(steps) == 2 and steps[1] == 'tp_placed':
            # Step 3: TP placed, now place next BUY
            next_buy_price = ref_price - (grid_step * 2)
            
            return {
                'success': True,
                'scenario': 'volatility_safe',
                'step': 3,
                'decision': {
                    'title': 'Place Next BUY Order',
                    'description': f'REAL: Next BUY at ₹{next_buy_price:,.0f} (Grid Level 2)',
                    'confidence': 0.85,
                    'action': f'place_buy_order({next_buy_price})',
                    'details': {
                        'price': next_buy_price,
                        'quantity': lot_size,
                        'grid_level': 2,
                        'positions_after': len(positions) + 2
                    }
                },
                'options': [
                    {'id': 'second_buy_placed', 'title': 'Second BUY placed', 'choice': 'second_buy_placed'},
                    {'id': 'wait_first_fill', 'title': 'Wait for first BUY to fill', 'choice': 'wait_fill'}
                ]
            }
        
        elif len(steps) >= 3:
            # Step 4+: Grid monitoring
            return {
                'success': True,
                'scenario': 'volatility_safe',
                'step': len(steps) + 1,
                'decision': {
                    'title': 'Grid Monitoring Mode',
                    'description': 'REAL: Bot now monitors positions and waits for fills',
                    'confidence': 0.95,
                    'action': 'monitor_grid_positions()',
                    'details': {
                        'active_positions': min(len(steps) - 1, max_positions),
                        'pending_orders': min(len(steps) - 1, max_positions) * 2,
                        'next_action': 'wait_for_fills_or_new_levels'
                    }
                },
                'options': []  # No more options - simulation complete
            }
        
        return {'success': False, 'error': 'Invalid step sequence for volatility_safe'}
    
    def _simulate_volatility_unsafe_path(self, bot_state: Dict, steps: List[str]) -> Dict[str, Any]:
        """Simulate volatility unsafe path using REAL volatility data"""
        vol_data = bot_state.get('volatility', {})
        config = bot_state.get('config', {})
        
        # Use REAL volatility values
        current_iv = vol_data.get('current_iv', vol_data.get('iv', 0))
        current_rv = vol_data.get('current_rv', vol_data.get('rv', 0))
        
        return {
            'success': True,
            'scenario': 'volatility_unsafe',
            'step': 1,
            'decision': {
                'title': 'Trading Halted - REAL Data',
                'description': f"REAL: {vol_data.get('violation_reason', 'Unknown')} (IV={current_iv:.1f}%, RV={current_rv:.1f}%)",
                'confidence': 0.95,
                'action': 'halt_all_trading',
                'details': {
                    'current_iv': current_iv,
                    'current_rv': current_rv,
                    'max_iv_threshold': vol_data.get('max_iv', 35),
                    'max_rv_threshold': vol_data.get('max_rv', 40),
                    'violation_reason': vol_data.get('violation_reason', 'Unknown'),
                    'is_safe': vol_data.get('is_safe', True),
                    'monitoring_interval': config.get('check_interval', 10),
                    'grid_step': config.get('grid_step', 1000),
                    'reference_price': config.get('reference_price', 110000)
                }
            },
            'options': [
                {'id': 'track_missed', 'title': 'Track missed levels', 'choice': 'track_levels'},
                {'id': 'wait_normalize', 'title': 'Wait for normalization', 'choice': 'wait_safe'}
            ]
        }
    
    def _simulate_position_limit_path(self, bot_state: Dict, steps: List[str]) -> Dict[str, Any]:
        """Simulate position limit scenario"""
        positions = bot_state.get('positions', {}).get('positions', [])
        config = bot_state.get('config', {})
        
        return {
            'success': True,
            'scenario': 'position_limit',
            'step': 1,
            'decision': {
                'title': 'Position Limit Reached',
                'description': f'Maximum {config.get("max_positions", 3)} positions open',
                'confidence': 0.95,
                'action': 'wait_for_exits',
                'details': {
                    'current_positions': len(positions),
                    'max_positions': config.get('max_positions', 3),
                    'waiting_for': 'TP fills'
                }
            },
            'options': [
                {'id': 'monitor_tp', 'title': 'Monitor TP orders', 'choice': 'monitor_exits'},
                {'id': 'simulate_exit', 'title': 'Simulate position exit', 'choice': 'position_closed'}
            ]
        }
    
    def _simulate_grid_expansion_path(self, bot_state: Dict, steps: List[str]) -> Dict[str, Any]:
        """Simulate grid expansion scenario"""
        config = bot_state.get('config', {})
        grid_step = float(config.get('grid_step', 1000))
        
        return {
            'success': True,
            'scenario': 'grid_expansion',
            'step': 1,
            'decision': {
                'title': 'Grid Expansion Simulation',
                'description': 'Simulate multiple grid levels being filled',
                'confidence': 0.8,
                'action': 'expand_grid_levels',
                'details': {
                    'grid_step': grid_step,
                    'levels_to_fill': 3,
                    'total_capital': grid_step * 3
                }
            },
            'options': [
                {'id': 'fill_3_levels', 'title': 'Fill 3 grid levels', 'choice': 'fill_levels'},
                {'id': 'gradual_fill', 'title': 'Gradual level filling', 'choice': 'gradual_expansion'}
            ]
        }
    
    # Helper methods for building next steps
    def _get_current_next_steps(self, predictions: Dict, bot_state: Dict) -> List[Dict]:
        return [
            {'id': 'explore_scenarios', 'title': 'Explore different scenarios', 'type': 'branch'}
        ]
    
    def _get_volatility_safe_steps(self, bot_state: Dict, next_buy_price: float, grid_step: float) -> List[Dict]:
        config = bot_state.get('config', {})
        lot_size = config.get('lot_size', 1)
        return [
            {'id': 'place_buy', 'title': f'Place BUY at ₹{next_buy_price:,.0f} (LOT={lot_size})', 'type': 'action'},
            {'id': 'place_tp', 'title': f'Place TP at ₹{next_buy_price + grid_step:,.0f} (STEP={grid_step})', 'type': 'action'}
        ]
    
    def _get_volatility_unsafe_steps(self, bot_state: Dict) -> List[Dict]:
        return [
            {'id': 'halt_trading', 'title': 'Halt all trading', 'type': 'action'},
            {'id': 'track_missed', 'title': 'Track missed levels', 'type': 'monitoring'}
        ]
    
    def _get_position_limit_steps(self, bot_state: Dict) -> List[Dict]:
        return [
            {'id': 'wait_tp', 'title': 'Wait for TP fills', 'type': 'waiting'},
            {'id': 'monitor_exits', 'title': 'Monitor position exits', 'type': 'monitoring'}
        ]
    
    def _get_grid_expansion_steps(self, bot_state: Dict) -> List[Dict]:
        return [
            {'id': 'fill_levels', 'title': 'Fill multiple levels', 'type': 'action'},
            {'id': 'manage_exposure', 'title': 'Manage capital exposure', 'type': 'risk_management'}
        ]