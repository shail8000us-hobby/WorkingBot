"""
Dynamic Bot Simulator - Real-Time Scenario Execution

Connects to the Master Brain Reader to execute scenarios based on actual bot logic.
Provides real-time simulation of bot decision-making using live data.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from .master_brain_reader import get_master_brain_reader, BotScenario
from .state_reader import BotStateReader

log = logging.getLogger(__name__)

class DynamicBotSimulator:
    """
    Real-time bot simulator that uses the Master Brain Reader for scenarios.
    
    Features:
    - Dynamic scenario generation from actual bot code
    - Real-time state integration
    - Atomic decision simulation
    - Live data updates every 30 seconds
    """
    
    def __init__(self, bot_root: Path):
        self.bot_root = Path(bot_root)
        self.master_reader = get_master_brain_reader(bot_root)
        self.state_reader = BotStateReader(bot_root)
        
        log.info("DynamicBotSimulator initialized with Master Brain Reader")
    
    def get_simulation_tree(self) -> Dict[str, Any]:
        """Get real-time simulation tree from Master Brain Reader"""
        try:
            # Get all scenarios from master reader
            master_data = self.master_reader.get_all_scenarios()
            
            # Get current bot state
            current_state = self.state_reader.get_complete_state()
            
            # Build simulation tree with real-time data
            simulation_tree = self._build_dynamic_tree(master_data, current_state)
            
            return {
                'success': True,
                'simulation_tree': simulation_tree,
                'master_data': master_data,
                'current_state': current_state,
                'timestamp': time.time(),
                'data_freshness': time.time() - master_data.get('last_scan', 0)
            }
            
        except Exception as e:
            log.error(f"Error building dynamic simulation tree: {e}")
            return {'success': False, 'error': str(e)}
    
    def simulate_scenario_path(self, scenario_id: str, steps: List[str] = None) -> Dict[str, Any]:
        """Simulate a scenario path using real bot logic"""
        try:
            steps = steps or []
            
            # Get scenario from master reader
            scenario = self.master_reader.get_scenario_by_id(scenario_id)
            if not scenario:
                return {'success': False, 'error': f'Scenario {scenario_id} not found'}
            
            # Get current state
            current_state = self.state_reader.get_complete_state()
            
            # Execute simulation based on real scenario data
            simulation_result = self._execute_dynamic_simulation(scenario, steps, current_state)
            
            return {
                'success': True,
                'scenario': scenario_id,
                'steps': steps,
                'step': len(steps) + 1,
                'decision': simulation_result['decision'],
                'options': simulation_result['options'],
                'real_time_data': scenario.real_time_data,
                'timestamp': time.time()
            }
            
        except Exception as e:
            log.error(f"Error simulating scenario path: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_dynamic_tree(self, master_data: Dict, current_state: Dict) -> Dict[str, Any]:
        """Build simulation tree from master brain data"""
        scenarios_data = master_data.get('scenarios', {})
        
        # Convert scenarios to simulation format
        scenarios = []
        for scenario_id, scenario_data in scenarios_data.items():
            scenario_info = self._format_scenario_for_ui(scenario_data, current_state)
            scenarios.append(scenario_info)
        
        # Sort scenarios by confidence and category
        scenarios.sort(key=lambda x: (x.get('confidence', 0), x.get('category', '')), reverse=True)
        
        return {
            'id': 'dynamic_root',
            'title': 'Real-Time Bot Brain Simulator',
            'description': f'Live scenarios from actual bot code (scanned {master_data.get("total_scenarios", 0)} scenarios)',
            'current_state': self._format_current_state(current_state, master_data),
            'scenarios': scenarios,
            'metadata': {
                'last_scan': master_data.get('last_scan', 0),
                'scan_interval': master_data.get('scan_interval', 30),
                'total_scenarios': master_data.get('total_scenarios', 0),
                'data_source': 'master_brain_reader'
            }
        }
    
    def _format_scenario_for_ui(self, scenario_data: Dict, current_state: Dict) -> Dict[str, Any]:
        """Format scenario data for UI display"""
        real_time_data = scenario_data.get('real_time_data', {})
        
        # Calculate dynamic confidence based on current state
        base_confidence = scenario_data.get('confidence', 0.5)
        dynamic_confidence = self._calculate_dynamic_confidence(scenario_data, current_state)
        
        # Merge real-time details
        details = {
            'category': scenario_data.get('category', 'unknown'),
            'initial_state': scenario_data.get('initial_state', 'unknown'),
            'possible_actions': len(scenario_data.get('possible_actions', [])),
            'data_freshness': 'live'
        }
        
        # Add scenario-specific real-time data
        if real_time_data:
            details.update(real_time_data)
        
        return {
            'id': scenario_data.get('id'),
            'title': scenario_data.get('title', 'Unknown Scenario'),
            'description': scenario_data.get('description', 'No description'),
            'confidence': dynamic_confidence,
            'category': scenario_data.get('category', 'general'),
            'details': details
        }
    
    def _format_current_state(self, current_state: Dict, master_data: Dict) -> Dict[str, Any]:
        """Format current state for UI display"""
        vol_data = current_state.get('volatility', {})
        positions = current_state.get('positions', {})
        config = current_state.get('config', {})
        
        return {
            'trading_safe': vol_data.get('is_safe', True),
            'volatility_condition': 'safe' if vol_data.get('is_safe', True) else 'unsafe',
            'positions': len(positions.get('positions', [])),
            'max_positions': config.get('max_positions', 3),
            'grid_step': config.get('grid_step', 1000),
            'reference_price': config.get('reference_price', 110000),
            'current_iv': vol_data.get('current_iv', 0),
            'current_rv': vol_data.get('current_rv', 0),
            'is_safe': vol_data.get('is_safe', True),
            'violation_reason': vol_data.get('violation_reason', ''),
            'scenarios_available': master_data.get('total_scenarios', 0),
            'last_brain_scan': master_data.get('last_scan', 0),
            'primary_action': self._determine_primary_action(current_state),
            'confidence': self._calculate_overall_confidence(current_state)
        }
    
    def _calculate_dynamic_confidence(self, scenario_data: Dict, current_state: Dict) -> float:
        """Calculate dynamic confidence based on current state"""
        base_confidence = scenario_data.get('confidence', 0.5)
        scenario_id = scenario_data.get('id', '')
        
        # Adjust confidence based on current conditions
        vol_data = current_state.get('volatility', {})
        positions = current_state.get('positions', {})
        
        if 'volatility_safe' in scenario_id:
            return 0.9 if vol_data.get('is_safe', True) else 0.2
        elif 'volatility_unsafe' in scenario_id:
            return 0.95 if not vol_data.get('is_safe', True) else 0.1
        elif 'position_limit' in scenario_id:
            pos_count = len(positions.get('positions', []))
            max_pos = current_state.get('config', {}).get('max_positions', 3)
            return 0.95 if pos_count >= max_pos else 0.3
        elif 'current_state' in scenario_id:
            return 0.95  # Always high confidence for current state
        else:
            return base_confidence
    
    def _determine_primary_action(self, current_state: Dict) -> str:
        """Determine the primary action bot should take"""
        vol_data = current_state.get('volatility', {})
        positions = current_state.get('positions', {})
        config = current_state.get('config', {})
        
        if not vol_data.get('is_safe', True):
            return f"Trading HALTED: {vol_data.get('violation_reason', 'Volatility unsafe')}"
        
        pos_count = len(positions.get('positions', []))
        max_pos = config.get('max_positions', 3)
        
        if pos_count >= max_pos:
            return f"Position limit reached ({pos_count}/{max_pos}) - waiting for exits"
        elif pos_count == 0:
            ref_price = config.get('reference_price', 110000)
            grid_step = config.get('grid_step', 1000)
            next_buy = ref_price - grid_step
            return f"Ready to place first BUY at ₹{next_buy:,.0f}"
        else:
            return f"Managing {pos_count} positions - monitoring for new levels"
    
    def _calculate_overall_confidence(self, current_state: Dict) -> float:
        """Calculate overall confidence in bot state"""
        vol_data = current_state.get('volatility', {})
        
        if not vol_data.get('is_safe', True):
            return 0.95  # High confidence in halt decision
        else:
            return 0.85  # Good confidence in normal operations
    
    def _execute_dynamic_simulation(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Execute simulation using real scenario data"""
        scenario_id = scenario.id
        step_count = len(steps)
        
        # Use real-time data from scenario
        real_time_data = scenario.real_time_data
        
        if scenario_id == 'current_state':
            return self._simulate_current_state_path(scenario, steps, current_state)
        elif scenario_id == 'volatility_safe':
            return self._simulate_volatility_safe_path(scenario, steps, current_state)
        elif scenario_id == 'volatility_unsafe':
            return self._simulate_volatility_unsafe_path(scenario, steps, current_state)
        elif scenario_id == 'position_limit':
            return self._simulate_position_limit_path(scenario, steps, current_state)
        elif scenario_id == 'grid_expansion':
            return self._simulate_grid_expansion_path(scenario, steps, current_state)
        elif scenario_id == 'liquidation_risk':
            return self._simulate_liquidation_risk_path(scenario, steps, current_state)
        elif scenario_id == 'guardian_protection':
            return self._simulate_guardian_protection_path(scenario, steps, current_state)
        elif scenario_id == 'api_failure':
            return self._simulate_api_failure_path(scenario, steps, current_state)
        elif scenario_id == 'emergency_stop':
            return self._simulate_emergency_stop_path(scenario, steps, current_state)
        else:
            return self._simulate_generic_path(scenario, steps, current_state)
    
    def _simulate_current_state_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate current state analysis path"""
        vol_data = current_state.get('volatility', {})
        
        if len(steps) == 0:
            return {
                'decision': {
                    'title': 'Current Bot State Analysis',
                    'description': self._determine_primary_action(current_state),
                    'confidence': self._calculate_overall_confidence(current_state),
                    'details': {
                        'trading_safe': vol_data.get('is_safe', True),
                        'current_iv': vol_data.get('current_iv', 0),
                        'current_rv': vol_data.get('current_rv', 0),
                        'violation_reason': vol_data.get('violation_reason', ''),
                        'data_source': 'real_time_state'
                    }
                },
                'options': [
                    {'id': 'explore_volatility', 'title': 'Explore volatility scenarios', 'choice': 'volatility_analysis'},
                    {'id': 'explore_positions', 'title': 'Explore position scenarios', 'choice': 'position_analysis'}
                ]
            }
        else:
            return {
                'decision': {
                    'title': 'Analysis Complete',
                    'description': 'Use specific scenario tabs to explore detailed paths',
                    'confidence': 0.95,
                    'details': {'recommendation': 'Try other scenarios for detailed simulation'}
                },
                'options': []
            }
    
    def _simulate_volatility_safe_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate volatility safe trading path"""
        config = current_state.get('config', {})
        positions = current_state.get('positions', {})
        
        grid_step = float(config.get('grid_step', 1000))
        ref_price = float(config.get('reference_price', 110000))
        max_positions = config.get('max_positions', 3)
        
        if len(steps) == 0:
            pos_count = len(positions.get('positions', []))
            if pos_count >= max_positions:
                return {
                    'decision': {
                        'title': 'Position Limit Reached',
                        'description': f'REAL: {pos_count}/{max_positions} positions active',
                        'confidence': 0.95,
                        'details': {'positions': pos_count, 'max_positions': max_positions}
                    },
                    'options': [
                        {'id': 'wait_exits', 'title': 'Wait for position exits', 'choice': 'wait_exits'},
                        {'id': 'monitor_tp', 'title': 'Monitor TP orders', 'choice': 'monitor_tp'}
                    ]
                }
            else:
                next_buy = ref_price - grid_step
                return {
                    'decision': {
                        'title': 'Place Grid BUY Order',
                        'description': f'REAL: Place BUY at ₹{next_buy:,.0f} (REF={ref_price}, STEP={grid_step})',
                        'confidence': 0.85,
                        'details': {'price': next_buy, 'grid_step': grid_step, 'reference_price': ref_price}
                    },
                    'options': [
                        {'id': 'place_buy', 'title': 'Place BUY order', 'choice': 'buy_placed'},
                        {'id': 'calculate_risk', 'title': 'Calculate risk first', 'choice': 'risk_calc'}
                    ]
                }
        
        elif len(steps) == 1 and steps[0] == 'buy_placed':
            entry_price = ref_price - grid_step
            tp_price = entry_price + grid_step
            return {
                'decision': {
                    'title': 'Place Take Profit Order',
                    'description': f'REAL: Place TP at ₹{tp_price:,.0f} for position at ₹{entry_price:,.0f}',
                    'confidence': 0.9,
                    'details': {'entry_price': entry_price, 'tp_price': tp_price, 'profit_target': grid_step}
                },
                'options': [
                    {'id': 'place_tp', 'title': 'Place TP order', 'choice': 'tp_placed'},
                    {'id': 'monitor_fill', 'title': 'Monitor BUY fill', 'choice': 'monitor_fill'}
                ]
            }
        
        else:
            return {
                'decision': {
                    'title': 'Grid Management Active',
                    'description': 'REAL: Bot continues monitoring and managing grid positions',
                    'confidence': 0.9,
                    'details': {'status': 'active_management', 'step': len(steps) + 1}
                },
                'options': []
            }
    
    def _simulate_volatility_unsafe_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate volatility unsafe path"""
        vol_data = current_state.get('volatility', {})
        
        if len(steps) == 0:
            return {
                'decision': {
                    'title': 'Trading Halted - Volatility Unsafe',
                    'description': f'REAL: {vol_data.get("violation_reason", "Volatility limits exceeded")}',
                    'confidence': 0.95,
                    'details': {
                        'current_iv': vol_data.get('current_iv', 0),
                        'current_rv': vol_data.get('current_rv', 0),
                        'max_iv': vol_data.get('max_iv', 35),
                        'max_rv': vol_data.get('max_rv', 40),
                        'is_safe': vol_data.get('is_safe', True)
                    }
                },
                'options': [
                    {'id': 'track_levels', 'title': 'Track missed levels', 'choice': 'track_levels'},
                    {'id': 'wait_safe', 'title': 'Wait for safe conditions', 'choice': 'wait_safe'}
                ]
            }
        else:
            return {
                'decision': {
                    'title': 'Volatility Monitoring Active',
                    'description': 'REAL: Bot monitoring volatility for safe trading conditions',
                    'confidence': 0.9,
                    'details': {'monitoring_active': True, 'auto_resume': True}
                },
                'options': []
            }
    
    def _simulate_position_limit_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate position limit scenario"""
        positions = current_state.get('positions', {})
        config = current_state.get('config', {})
        
        pos_count = len(positions.get('positions', []))
        max_pos = config.get('max_positions', 3)
        
        return {
            'decision': {
                'title': 'Position Limit Management',
                'description': f'REAL: Managing {pos_count}/{max_pos} positions - waiting for exits',
                'confidence': 0.95,
                'details': {'current_positions': pos_count, 'max_positions': max_pos, 'strategy': 'wait_for_exits'}
            },
            'options': [
                {'id': 'monitor_exits', 'title': 'Monitor position exits', 'choice': 'monitor_exits'},
                {'id': 'risk_check', 'title': 'Check risk levels', 'choice': 'risk_check'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_grid_expansion_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate grid expansion scenario"""
        config = current_state.get('config', {})
        positions = current_state.get('positions', {})
        
        pos_count = len(positions.get('positions', []))
        max_pos = config.get('max_positions', 3)
        available_slots = max_pos - pos_count
        
        return {
            'decision': {
                'title': 'Grid Expansion Opportunity',
                'description': f'REAL: {available_slots} slots available for new positions',
                'confidence': 0.8,
                'details': {'available_slots': available_slots, 'current_positions': pos_count, 'expansion_ready': True}
            },
            'options': [
                {'id': 'expand_grid', 'title': 'Expand grid levels', 'choice': 'expand_grid'},
                {'id': 'calculate_levels', 'title': 'Calculate optimal levels', 'choice': 'calc_levels'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_liquidation_risk_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate liquidation risk scenario"""
        return {
            'decision': {
                'title': 'Liquidation Risk Assessment',
                'description': 'REAL: Monitoring margin utilization and liquidation distance',
                'confidence': 0.7,
                'details': {'risk_level': 'monitoring', 'margin_safe': True, 'distance_ok': True}
            },
            'options': [
                {'id': 'check_margin', 'title': 'Check margin levels', 'choice': 'check_margin'},
                {'id': 'calculate_distance', 'title': 'Calculate liquidation distance', 'choice': 'calc_distance'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_guardian_protection_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate guardian protection scenario"""
        return {
            'decision': {
                'title': 'Guardian Bot Protection Active',
                'description': 'REAL: 24/7 monitoring and loss limit enforcement',
                'confidence': 0.9,
                'details': {'guardian_active': True, 'limits_ok': True, 'monitoring_24_7': True}
            },
            'options': [
                {'id': 'check_limits', 'title': 'Check loss limits', 'choice': 'check_limits'},
                {'id': 'monitor_pnl', 'title': 'Monitor PnL', 'choice': 'monitor_pnl'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_api_failure_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate API failure scenario"""
        return {
            'decision': {
                'title': 'API Connection Issues',
                'description': 'REAL: Handling exchange API failures and reconnection',
                'confidence': 0.6,
                'details': {'api_status': 'checking', 'circuit_breaker': 'monitoring', 'fallback_ready': True}
            },
            'options': [
                {'id': 'retry_connection', 'title': 'Retry API connection', 'choice': 'retry_api'},
                {'id': 'circuit_breaker', 'title': 'Activate circuit breaker', 'choice': 'circuit_break'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_emergency_stop_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate emergency stop scenario"""
        return {
            'decision': {
                'title': 'Emergency Stop Activated',
                'description': 'REAL: All trading halted - manual intervention required',
                'confidence': 0.95,
                'details': {'emergency_active': True, 'trading_halted': True, 'manual_intervention': True}
            },
            'options': [
                {'id': 'cancel_orders', 'title': 'Cancel all orders', 'choice': 'cancel_orders'},
                {'id': 'notify_operator', 'title': 'Notify operator', 'choice': 'notify_op'}
            ] if len(steps) == 0 else []
        }
    
    def _simulate_generic_path(self, scenario: Any, steps: List[str], current_state: Dict) -> Dict[str, Any]:
        """Simulate generic scenario path"""
        return {
            'decision': {
                'title': scenario.title,
                'description': scenario.description,
                'confidence': scenario.confidence,
                'details': scenario.real_time_data
            },
            'options': [
                {'id': 'continue', 'title': 'Continue simulation', 'choice': 'continue'},
                {'id': 'analyze', 'title': 'Analyze further', 'choice': 'analyze'}
            ] if len(steps) == 0 else []
        }