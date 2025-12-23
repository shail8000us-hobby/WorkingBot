"""
Interactive Bot Brain Simulator

Single Responsibility: Simulate bot decision-making process interactively.

This module:
1. Reads bot strategy files in real-time (READ-ONLY)
2. Simulates decision tree based on actual bot logic
3. Provides interactive "what-if" scenarios
4. Shows step-by-step decision flow
5. Never interferes with actual bot operations

Key Features:
- Real-time bot brain reading
- Interactive decision simulation
- Step-by-step scenario exploration
- Multiple branching paths
- Confidence scoring for each decision
"""

import logging
import json
import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

log = logging.getLogger(__name__)


class BotBrainReader:
    """Reads and analyzes bot decision-making logic from source files"""
    
    def __init__(self, bot_root: Path):
        self.bot_root = Path(bot_root)
        self.strategy_files = [
            'bot/strategy/gridbot.py',
            'bot/strategy/modules/volatility_handler.py',
            'bot/strategy/modules/grid_calculator.py',
            'bot/strategy/modules/order_manager.py',
            'bot/strategy/modules/position_manager.py',
            'bot/safety/volatility_monitor.py',
            'bot/safety/gatekeeper.py'
        ]
    
    def read_decision_logic(self) -> Dict[str, Any]:
        """Extract decision logic from bot source files"""
        logic = {
            'volatility_checks': [],
            'position_checks': [],
            'order_placement_logic': [],
            'grid_calculations': [],
            'safety_conditions': []
        }
        
        for file_path in self.strategy_files:
            full_path = self.bot_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                        logic.update(self._extract_logic_patterns(content, file_path))
                except Exception as e:
                    log.warning(f"Could not read {file_path}: {e}")
        
        return logic
    
    def _extract_logic_patterns(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract decision patterns from source code"""
        patterns = {}
        
        # Extract volatility conditions
        vol_patterns = re.findall(r'if.*(?:iv|rv|volatility).*[><=].*:', content, re.IGNORECASE)
        if vol_patterns:
            patterns['volatility_conditions'] = vol_patterns
        
        # Extract position checks
        pos_patterns = re.findall(r'if.*(?:position|max_open).*[><=].*:', content, re.IGNORECASE)
        if pos_patterns:
            patterns['position_conditions'] = pos_patterns
        
        # Extract grid calculations
        grid_patterns = re.findall(r'(?:buy_price|sell_price|grid_step).*=.*', content, re.IGNORECASE)
        if grid_patterns:
            patterns['grid_calculations'] = grid_patterns
        
        return patterns


class InteractiveBotSimulator:
    """
    Interactive simulator that follows actual bot decision-making logic.
    
    Provides step-by-step simulation without interfering with bot operations.
    """
    
    def __init__(self, bot_root: Path):
        self.bot_root = Path(bot_root)
        self.brain_reader = BotBrainReader(bot_root)
        self.state_dir = self.bot_root / 'bot' / 'state'
        self.config_file = self.bot_root / 'config.yaml'
    
    def get_current_decision_tree(self) -> Dict[str, Any]:
        """Get the current decision tree based on bot's actual state"""
        try:
            # Read current bot state
            current_state = self._read_bot_state()
            
            # Read bot decision logic
            decision_logic = self.brain_reader.read_decision_logic()
            
            # Generate interactive decision tree
            decision_tree = self._build_decision_tree(current_state, decision_logic)
            
            return {
                'success': True,
                'current_state': current_state,
                'decision_tree': decision_tree,
                'timestamp': __import__('time').time()
            }
            
        except Exception as e:
            log.error(f"Error generating decision tree: {e}")
            return {'success': False, 'error': str(e)}
    
    def simulate_decision_path(self, scenario: str, user_choices: List[str] = None) -> Dict[str, Any]:
        """
        Simulate a specific decision path based on user choices.
        
        Args:
            scenario: Starting scenario ('current', 'volatility_safe', 'volatility_unsafe', etc.)
            user_choices: List of user choices made so far
            
        Returns:
            Next decision point with available options
        """
        try:
            current_state = self._read_bot_state()
            
            # Simulate the scenario
            if scenario == 'current':
                return self._simulate_current_scenario(current_state)
            elif scenario == 'volatility_safe':
                return self._simulate_volatility_safe(current_state, user_choices or [])
            elif scenario == 'volatility_unsafe':
                return self._simulate_volatility_unsafe(current_state, user_choices or [])
            elif scenario == 'position_limit':
                return self._simulate_position_limit(current_state, user_choices or [])
            else:
                return {'success': False, 'error': 'Unknown scenario'}
                
        except Exception as e:
            log.error(f"Error simulating decision path: {e}")
            return {'success': False, 'error': str(e)}
    
    def _read_bot_state(self) -> Dict[str, Any]:
        """Read current bot state from files"""
        state = {}
        
        # Read positions
        pos_file = self.state_dir / 'positions.json'
        if pos_file.exists():
            with open(pos_file, 'r') as f:
                state['positions'] = json.load(f)
        
        # Read volatility status
        vol_file = self.bot_root / '.volatility_status.json'
        if vol_file.exists():
            with open(vol_file, 'r') as f:
                state['volatility'] = json.load(f)
        
        # Read config
        if self.config_file.exists():
            config = {}
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")
            state['config'] = config
        
        return state
    
    def _build_decision_tree(self, state: Dict[str, Any], logic: Dict[str, Any]) -> Dict[str, Any]:
        """Build interactive decision tree based on current state"""
        
        # Get current conditions
        vol_data = state.get('volatility', {})
        is_safe = vol_data.get('is_safe', True)
        positions = state.get('positions', {}).get('positions', [])
        config = state.get('config', {})
        max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
        
        # Root decision node
        root = {
            'id': 'start',
            'title': 'Bot Decision Process',
            'description': 'Starting point of bot decision-making',
            'current_state': {
                'volatility_safe': is_safe,
                'positions_count': len(positions),
                'max_positions': max_positions,
                'trading_halted': not is_safe
            },
            'options': []
        }
        
        # Add volatility branch
        if not is_safe:
            root['options'].append({
                'id': 'volatility_check',
                'title': '🚨 Volatility Check: UNSAFE',
                'description': f"Current: {vol_data.get('violation_reason', 'Volatility limits exceeded')}",
                'action': 'halt_trading',
                'confidence': 0.95,
                'next_options': [
                    {
                        'id': 'simulate_safe',
                        'title': '🔄 Simulate: If volatility becomes SAFE',
                        'description': 'See what bot would do if volatility normalizes',
                        'scenario': 'volatility_safe'
                    },
                    {
                        'id': 'track_missed',
                        'title': '📊 Track missed levels',
                        'description': 'Monitor grid levels missed during halt',
                        'scenario': 'track_missed_levels'
                    }
                ]
            })
        else:
            root['options'].append({
                'id': 'volatility_check',
                'title': '✅ Volatility Check: SAFE',
                'description': f"IV: {vol_data.get('iv', 0):.1f}%, RV: {vol_data.get('rv', 0):.1f}%",
                'action': 'continue_trading',
                'confidence': 0.9,
                'next_options': [
                    {
                        'id': 'check_positions',
                        'title': '📊 Check Position Limits',
                        'description': f'Current: {len(positions)}/{max_positions} positions',
                        'scenario': 'position_check'
                    }
                ]
            })
        
        return root
    
    def _simulate_current_scenario(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate current bot scenario"""
        vol_data = state.get('volatility', {})
        is_safe = vol_data.get('is_safe', True)
        
        if not is_safe:
            return {
                'success': True,
                'scenario': 'current',
                'decision': {
                    'title': '🚨 Trading Halted',
                    'description': f"Volatility unsafe: {vol_data.get('violation_reason', 'Unknown')}",
                    'action': 'halt_all_trading',
                    'confidence': 0.95,
                    'next_options': [
                        {
                            'id': 'simulate_safe',
                            'title': 'What if volatility becomes safe?',
                            'scenario': 'volatility_safe'
                        },
                        {
                            'id': 'simulate_unsafe_continue',
                            'title': 'What if volatility stays unsafe?',
                            'scenario': 'volatility_unsafe'
                        }
                    ]
                }
            }
        else:
            return self._simulate_volatility_safe(state, [])
    
    def _simulate_volatility_safe(self, state: Dict[str, Any], choices: List[str]) -> Dict[str, Any]:
        """Simulate scenario where volatility is safe"""
        positions = state.get('positions', {}).get('positions', [])
        config = state.get('config', {})
        max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
        grid_step = float(config.get('GRIDBOT_STEP', 1000))
        ref_price = float(config.get('GRIDBOT_REF', 110000))
        
        # Step 1: Check positions
        if len(choices) == 0:
            if len(positions) >= max_positions:
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 1,
                    'decision': {
                        'title': '📊 Position Limit Reached',
                        'description': f'Bot has {len(positions)}/{max_positions} positions open',
                        'action': 'wait_for_tp_fills',
                        'confidence': 0.95,
                        'next_options': [
                            {
                                'id': 'wait_tp',
                                'title': 'Wait for TP orders to fill',
                                'description': 'Monitor existing positions for profit taking',
                                'choice': 'wait_tp'
                            },
                            {
                                'id': 'simulate_tp_fill',
                                'title': 'Simulate: TP order fills',
                                'description': 'See what happens when a position closes',
                                'choice': 'tp_filled'
                            }
                        ]
                    }
                }
            else:
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 1,
                    'decision': {
                        'title': '✅ Can Place New Order',
                        'description': f'Slots available: {len(positions)}/{max_positions}',
                        'action': 'check_pending_orders',
                        'confidence': 0.9,
                        'next_options': [
                            {
                                'id': 'no_pending',
                                'title': 'No pending orders',
                                'description': 'Calculate and place new BUY order',
                                'choice': 'place_buy'
                            },
                            {
                                'id': 'has_pending',
                                'title': 'Has pending BUY order',
                                'description': 'Monitor existing order for fill',
                                'choice': 'monitor_pending'
                            }
                        ]
                    }
                }
        
        # Step 2: Handle user choice
        elif len(choices) == 1:
            choice = choices[0]
            
            if choice == 'place_buy':
                # Calculate next BUY price
                if positions:
                    lowest_entry = min([p.get('entry_price', ref_price) for p in positions])
                    next_buy_price = lowest_entry - grid_step
                else:
                    next_buy_price = ref_price - grid_step
                
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 2,
                    'decision': {
                        'title': '💰 Place BUY Order',
                        'description': f'Bot will place BUY order at ₹{next_buy_price:,.0f}',
                        'action': f'place_buy_order({next_buy_price})',
                        'confidence': 0.85,
                        'details': {
                            'price': next_buy_price,
                            'quantity': int(config.get('GRIDBOT_LOT', 1)),
                            'order_type': 'LIMIT',
                            'grid_level': len(positions) + 1
                        },
                        'next_options': [
                            {
                                'id': 'order_placed',
                                'title': 'Order placed successfully',
                                'description': 'Monitor for fill and prepare TP',
                                'choice': 'buy_placed'
                            },
                            {
                                'id': 'order_failed',
                                'title': 'Order placement failed',
                                'description': 'Handle error and retry',
                                'choice': 'buy_failed'
                            }
                        ]
                    }
                }
            
            elif choice == 'monitor_pending':
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 2,
                    'decision': {
                        'title': '👀 Monitor Pending Order',
                        'description': 'Bot monitors existing BUY order for fill',
                        'action': 'monitor_order_fill',
                        'confidence': 0.9,
                        'next_options': [
                            {
                                'id': 'order_filled',
                                'title': 'BUY order filled',
                                'description': 'Place corresponding TP order',
                                'choice': 'buy_filled'
                            },
                            {
                                'id': 'order_timeout',
                                'title': 'Order not filled (timeout)',
                                'description': 'Consider price adjustment',
                                'choice': 'buy_timeout'
                            }
                        ]
                    }
                }
        
        # Step 3: Handle second choice
        elif len(choices) == 2:
            if choices[1] == 'buy_placed' or choices[1] == 'buy_filled':
                # Calculate TP price
                entry_price = ref_price - grid_step  # Simplified
                tp_price = entry_price + grid_step
                
                return {
                    'success': True,
                    'scenario': 'volatility_safe',
                    'step': 3,
                    'decision': {
                        'title': '📈 Place TP Order',
                        'description': f'Bot will place TP (Take Profit) at ₹{tp_price:,.0f}',
                        'action': f'place_tp_order({tp_price})',
                        'confidence': 0.9,
                        'details': {
                            'entry_price': entry_price,
                            'tp_price': tp_price,
                            'profit_target': grid_step,
                            'quantity': int(config.get('GRIDBOT_LOT', 1))
                        },
                        'next_options': [
                            {
                                'id': 'tp_placed',
                                'title': 'TP order placed',
                                'description': 'Return to position monitoring',
                                'choice': 'cycle_complete'
                            },
                            {
                                'id': 'continue_grid',
                                'title': 'Continue grid expansion',
                                'description': 'Check for next BUY opportunity',
                                'choice': 'next_buy'
                            }
                        ]
                    }
                }
        
        return {'success': False, 'error': 'Invalid choice sequence'}
    
    def _simulate_volatility_unsafe(self, state: Dict[str, Any], choices: List[str]) -> Dict[str, Any]:
        """Simulate scenario where volatility remains unsafe"""
        vol_data = state.get('volatility', {})
        
        return {
            'success': True,
            'scenario': 'volatility_unsafe',
            'decision': {
                'title': '🚨 Continue Trading Halt',
                'description': f"Volatility still unsafe: {vol_data.get('violation_reason', 'Unknown')}",
                'action': 'maintain_halt',
                'confidence': 0.95,
                'details': {
                    'current_iv': vol_data.get('iv', 0),
                    'current_rv': vol_data.get('rv', 0),
                    'thresholds': vol_data.get('thresholds', {}),
                    'monitoring_interval': '10 seconds'
                },
                'next_options': [
                    {
                        'id': 'track_missed',
                        'title': 'Track missed grid levels',
                        'description': 'Monitor levels that would have been hit',
                        'choice': 'track_levels'
                    },
                    {
                        'id': 'wait_normalize',
                        'title': 'Wait for normalization',
                        'description': 'Continue monitoring until safe',
                        'choice': 'wait_safe'
                    }
                ]
            }
        }
    
    def _simulate_position_limit(self, state: Dict[str, Any], choices: List[str]) -> Dict[str, Any]:
        """Simulate scenario where position limit is reached"""
        positions = state.get('positions', {}).get('positions', [])
        config = state.get('config', {})
        max_positions = int(config.get('GRIDBOT_MAX_OPEN', 3))
        
        return {
            'success': True,
            'scenario': 'position_limit',
            'decision': {
                'title': '🔒 Position Limit Reached',
                'description': f'Bot has maximum {max_positions} positions open',
                'action': 'wait_for_exits',
                'confidence': 0.95,
                'details': {
                    'current_positions': len(positions),
                    'max_allowed': max_positions,
                    'waiting_for': 'TP order fills'
                },
                'next_options': [
                    {
                        'id': 'monitor_tp',
                        'title': 'Monitor TP orders',
                        'description': 'Wait for profit-taking orders to fill',
                        'choice': 'monitor_exits'
                    },
                    {
                        'id': 'simulate_tp_fill',
                        'title': 'Simulate TP fill',
                        'description': 'See what happens when position closes',
                        'choice': 'tp_fills'
                    }
                ]
            }
        }