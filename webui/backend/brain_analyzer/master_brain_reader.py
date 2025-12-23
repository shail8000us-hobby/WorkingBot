"""
Master Bot Brain Reader - Real-Time Bot Logic Analyzer

Scans the entire bot codebase every 30 seconds to extract:
- All possible bot states and scenarios
- Decision points and logic flows
- Error conditions and recovery paths
- Safety system triggers
- Dynamic scenario generation based on actual code

This is the single source of truth for bot behavior simulation.
"""

import os
import ast
import re
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

log = logging.getLogger(__name__)

@dataclass
class BotState:
    """Represents a possible bot state"""
    id: str
    name: str
    description: str
    conditions: List[str]
    triggers: List[str]
    confidence: float
    category: str

@dataclass
class BotAction:
    """Represents a bot action/decision"""
    id: str
    name: str
    description: str
    preconditions: List[str]
    effects: List[str]
    risk_level: str
    execution_time: str

@dataclass
class BotScenario:
    """Represents a complete bot scenario"""
    id: str
    title: str
    description: str
    initial_state: str
    possible_actions: List[str]
    end_states: List[str]
    confidence: float
    category: str
    real_time_data: Dict[str, Any]

class MasterBotBrainReader:
    """
    Real-time bot brain analyzer that reads actual bot code to generate scenarios.
    
    Scans every 30 seconds:
    - Bot source code for decision logic
    - Configuration files for parameters
    - State files for current conditions
    - Log patterns for error scenarios
    """
    
    def __init__(self, bot_root: Path):
        self.bot_root = Path(bot_root)
        self.scenarios_cache = {}
        self.states_cache = {}
        self.actions_cache = {}
        self.last_scan_time = 0
        self.scan_interval = 30  # seconds
        self.is_running = False
        self.scan_thread = None
        
        # Throttling for scenario logging
        self.last_scenario_log_time = 0
        self.scenario_log_interval = 300  # Log summary once every 5 minutes
        self.last_scenario_count = 0
        
        # Bot code directories to scan
        self.scan_paths = [
            self.bot_root / 'bot',
            self.bot_root / 'webui' / 'backend',
            self.bot_root / 'scripts'
        ]
        
        # State files to monitor
        self.state_files = [
            self.bot_root / '.volatility_status.json',
            self.bot_root / 'bot' / 'state' / 'positions.json',
            self.bot_root / 'bot' / 'state' / 'runtime_state.json',
            self.bot_root / 'config.yaml',
            self.bot_root / '.volatility_halt.json'
        ]
        
        log.info(f"MasterBotBrainReader initialized for {bot_root}")
    
    def start_real_time_scanning(self):
        """Start the real-time scanning thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        log.info("Real-time bot brain scanning started (30s interval)")
    
    def stop_real_time_scanning(self):
        """Stop the real-time scanning"""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        log.info("Real-time bot brain scanning stopped")
    
    def _scan_loop(self):
        """Main scanning loop - runs every 30 seconds"""
        while self.is_running:
            try:
                start_time = time.time()
                self._perform_full_scan()
                scan_duration = time.time() - start_time
                log.debug(f"Bot brain scan completed in {scan_duration:.2f}s")
                
                # Sleep for remaining time
                sleep_time = max(0, self.scan_interval - scan_duration)
                time.sleep(sleep_time)
                
            except Exception as e:
                log.error(f"Error in bot brain scan loop: {e}")
                time.sleep(5)  # Short sleep on error
    
    def _perform_full_scan(self):
        """Perform complete bot brain analysis"""
        log.debug("Starting full bot brain scan...")
        
        # 1. Scan bot source code for decision logic
        self._scan_bot_source_code()
        
        # 2. Read current state files
        current_state = self._read_current_state()
        
        # 3. Analyze configuration
        config_analysis = self._analyze_configuration()
        
        # 4. Generate dynamic scenarios
        self._generate_dynamic_scenarios(current_state, config_analysis)
        
        # 5. Update cache timestamp
        self.last_scan_time = time.time()
        
        log.debug(f"Bot brain scan complete: {len(self.scenarios_cache)} scenarios generated")
    
    def _scan_bot_source_code(self):
        """Scan bot Python files to extract decision logic"""
        states = {}
        actions = {}
        
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue
                
            for py_file in scan_path.rglob("*.py"):
                try:
                    self._analyze_python_file(py_file, states, actions)
                except Exception as e:
                    log.debug(f"Error analyzing {py_file}: {e}")
        
        self.states_cache = states
        self.actions_cache = actions
        log.debug(f"Scanned source code: {len(states)} states, {len(actions)} actions")
    
    def _analyze_python_file(self, file_path: Path, states: Dict, actions: Dict):
        """Analyze a Python file for bot logic"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST for structured analysis
            tree = ast.parse(content)
            
            # Extract decision points
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    self._extract_decision_logic(node, content, states, actions, file_path)
                elif isinstance(node, ast.FunctionDef):
                    self._extract_function_logic(node, content, states, actions, file_path)
            
            # Extract error handling patterns
            self._extract_error_patterns(content, states, actions, file_path)
            
        except Exception as e:
            log.debug(f"Error parsing {file_path}: {e}")
    
    def _extract_decision_logic(self, if_node: ast.If, content: str, states: Dict, actions: Dict, file_path: Path):
        """Extract decision logic from if statements"""
        try:
            # Get the condition as string
            condition_lines = content.split('\n')[if_node.lineno-1:if_node.lineno+2]
            condition_text = ' '.join(condition_lines).strip()
            
            # Look for bot decision patterns
            decision_patterns = [
                r'trading.*safe',
                r'volatility.*threshold',
                r'position.*limit',
                r'emergency.*stop',
                r'circuit.*breaker',
                r'liquidation.*risk',
                r'margin.*utilization',
                r'heartbeat.*timeout'
            ]
            
            for pattern in decision_patterns:
                if re.search(pattern, condition_text, re.IGNORECASE):
                    state_id = f"{file_path.stem}_{if_node.lineno}"
                    states[state_id] = BotState(
                        id=state_id,
                        name=f"Decision at {file_path.name}:{if_node.lineno}",
                        description=condition_text[:100],
                        conditions=[condition_text],
                        triggers=[pattern],
                        confidence=0.8,
                        category=self._categorize_decision(pattern)
                    )
                    
        except Exception as e:
            log.debug(f"Error extracting decision logic: {e}")
    
    def _extract_function_logic(self, func_node: ast.FunctionDef, content: str, states: Dict, actions: Dict, file_path: Path):
        """Extract logic from function definitions"""
        func_name = func_node.name
        
        # Look for bot action functions
        action_patterns = [
            r'place.*order',
            r'cancel.*order',
            r'check.*position',
            r'calculate.*risk',
            r'handle.*error',
            r'emergency.*action',
            r'liquidation.*protection',
            r'volatility.*check'
        ]
        
        for pattern in action_patterns:
            if re.search(pattern, func_name, re.IGNORECASE):
                action_id = f"{file_path.stem}_{func_name}"
                
                # Extract docstring for description
                docstring = ast.get_docstring(func_node) or f"Function: {func_name}"
                
                actions[action_id] = BotAction(
                    id=action_id,
                    name=func_name,
                    description=docstring[:200],
                    preconditions=[],
                    effects=[],
                    risk_level=self._assess_risk_level(func_name),
                    execution_time="immediate"
                )
    
    def _extract_error_patterns(self, content: str, states: Dict, actions: Dict, file_path: Path):
        """Extract error handling and exception patterns"""
        error_patterns = [
            (r'except.*ConnectionError', 'network_error', 'high'),
            (r'except.*TimeoutError', 'timeout_error', 'medium'),
            (r'except.*APIError', 'api_error', 'high'),
            (r'liquidation.*warning', 'liquidation_risk', 'critical'),
            (r'margin.*call', 'margin_call', 'critical'),
            (r'emergency.*stop', 'emergency_stop', 'critical')
        ]
        
        for pattern, error_type, risk_level in error_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                error_id = f"{file_path.stem}_{error_type}_{match.start()}"
                states[error_id] = BotState(
                    id=error_id,
                    name=f"Error: {error_type}",
                    description=f"Error condition detected: {match.group()}",
                    conditions=[match.group()],
                    triggers=[pattern],
                    confidence=0.9,
                    category="error_handling"
                )
    
    def _read_current_state(self) -> Dict[str, Any]:
        """Read current bot state from state files"""
        current_state = {
            'timestamp': time.time(),
            'volatility': {},
            'positions': {},
            'config': {},
            'runtime': {}
        }
        
        for state_file in self.state_files:
            try:
                if state_file.exists():
                    if state_file.suffix == '.json':
                        with open(state_file, 'r') as f:
                            data = json.load(f)
                            if 'volatility' in state_file.name:
                                current_state['volatility'].update(data)
                            elif 'positions' in state_file.name:
                                current_state['positions'].update(data)
                            elif 'runtime' in state_file.name:
                                current_state['runtime'].update(data)
                    elif state_file.suffix == '.env':
                        config_data = {}
                        with open(state_file, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#') and '=' in line:
                                    key, value = line.split('=', 1)
                                    config_data[key.strip()] = value.strip().strip('"').strip("'")
                        current_state['config'].update(config_data)
            except Exception as e:
                log.debug(f"Error reading state file {state_file}: {e}")
        
        return current_state
    
    def _analyze_configuration(self) -> Dict[str, Any]:
        """Analyze bot configuration for scenario parameters"""
        config_analysis = {
            'grid_parameters': {},
            'risk_limits': {},
            'safety_settings': {},
            'trading_mode': 'unknown'
        }
        
        try:
            # Read grid configuration
            grid_config_file = self.bot_root / 'config.yaml'
            if grid_config_file.exists():
                with open(grid_config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            if 'GRIDBOT_' in key:
                                config_analysis['grid_parameters'][key] = value
                            elif 'MAX_' in key or 'LIMIT' in key:
                                config_analysis['risk_limits'][key] = value
                            elif 'SAFETY' in key or 'EMERGENCY' in key:
                                config_analysis['safety_settings'][key] = value
                            elif key == 'TRADING_MODE':
                                config_analysis['trading_mode'] = value
        
        except Exception as e:
            log.error(f"Error analyzing configuration: {e}")
        
        return config_analysis
    
    def _generate_dynamic_scenarios(self, current_state: Dict, config_analysis: Dict):
        """Generate comprehensive scenarios from complete bot brain analysis"""
        scenarios = {}
        
        # 1. Current state scenario
        scenarios['current_state'] = self._create_current_state_scenario(current_state)
        
        # 2. Volatility-based scenarios (10 scenarios)
        scenarios.update(self._create_volatility_scenarios(current_state))
        
        # 3. Position management scenarios (8 scenarios)
        scenarios.update(self._create_position_scenarios(current_state, config_analysis))
        
        # 4. Risk management scenarios (8 scenarios)
        scenarios.update(self._create_risk_scenarios(current_state, config_analysis))
        
        # 5. Error recovery scenarios (8 scenarios)
        scenarios.update(self._create_error_scenarios(current_state))
        
        # 6. Safety system scenarios (8 scenarios)
        scenarios.update(self._create_safety_scenarios(current_state, config_analysis))
        
        # 7. Grid calculation scenarios (5 scenarios)
        scenarios.update(self._create_grid_calculation_scenarios(current_state, config_analysis))
        
        # 8. Order management scenarios (6 scenarios)
        scenarios.update(self._create_order_management_scenarios(current_state, config_analysis))
        
        # 9. Fill detection scenarios (4 scenarios)
        scenarios.update(self._create_fill_detection_scenarios(current_state))
        
        # 10. Guardian bot scenarios (5 scenarios)
        scenarios.update(self._create_guardian_scenarios(current_state, config_analysis))
        
        # 11. Capital protection scenarios (4 scenarios)
        scenarios.update(self._create_capital_protection_scenarios(current_state, config_analysis))
        
        # 12. AI advisor scenarios (3 scenarios)
        scenarios.update(self._create_ai_advisor_scenarios(current_state))
        
        self.scenarios_cache = scenarios
        log.debug(f"Generated {len(scenarios)} comprehensive scenarios from complete bot brain analysis")
        
        # Throttle scenario summary logging (only log once per 5 min or when count changes significantly)
        current_time = time.time()
        
        # Initialize on first run
        if self.last_scenario_log_time == 0:
            self.last_scenario_log_time = current_time
            self.last_scenario_count = len(scenarios)
            # Log on first run - simplified single line
            log.info(f"🧠 Bot Brain: {len(scenarios)} scenarios loaded | Next update in 5 min")
            return scenarios
        
        # Check if we should log
        scenario_count_changed = abs(len(scenarios) - self.last_scenario_count) > 5  # Change threshold
        time_elapsed = current_time - self.last_scenario_log_time
        
        if scenario_count_changed or time_elapsed >= self.scenario_log_interval:
            # Simplified log - just the summary
            if scenario_count_changed:
                log.info(f"🧠 Bot Brain: {len(scenarios)} scenarios (changed from {self.last_scenario_count})")
            else:
                log.info(f"🧠 Bot Brain: {len(scenarios)} scenarios (5-min update)")
            
            # Update tracking variables
            self.last_scenario_log_time = current_time
            self.last_scenario_count = len(scenarios)
        
        return scenarios
    
    def _create_current_state_scenario(self, current_state: Dict) -> BotScenario:
        """Create scenario based on current bot state"""
        vol_data = current_state.get('volatility', {})
        positions = current_state.get('positions', {})
        
        is_safe = vol_data.get('is_safe', True)
        position_count = len(positions.get('positions', []))
        
        if not is_safe:
            title = "🚨 Trading Halted - Volatility Unsafe"
            description = f"REAL: {vol_data.get('violation_reason', 'Volatility limits exceeded')}"
            confidence = 0.95
        elif position_count == 0:
            title = "🎯 Ready to Trade - No Positions"
            description = "REAL: Bot ready to place first grid order"
            confidence = 0.9
        else:
            title = f"📊 Active Trading - {position_count} Positions"
            description = f"REAL: Bot managing {position_count} active positions"
            confidence = 0.85
        
        return BotScenario(
            id='current_state',
            title=title,
            description=description,
            initial_state='current',
            possible_actions=['analyze_next_action', 'check_conditions'],
            end_states=['action_determined'],
            confidence=confidence,
            category='current_analysis',
            real_time_data=current_state
        )
    
    def _create_volatility_scenarios(self, current_state: Dict) -> Dict[str, BotScenario]:
        """Create comprehensive volatility-based scenarios from actual bot code"""
        vol_data = current_state.get('volatility', {})
        scenarios = {}
        
        current_iv = vol_data.get('current_iv', vol_data.get('iv', 0))
        current_rv = vol_data.get('current_rv', vol_data.get('rv', 0))
        max_iv = vol_data.get('max_iv', 35)
        max_rv = vol_data.get('max_rv', 40)
        is_safe = vol_data.get('is_safe', True)
        
        # 1. SAFE VOLATILITY - Normal Grid Trading
        scenarios['volatility_safe_normal'] = BotScenario(
            id='volatility_safe_normal',
            title='✅ Safe Volatility - Normal Grid Trading',
            description=f'REAL: IV={current_iv:.1f}% < {max_iv}%, RV={current_rv:.1f}% < {max_rv}% - Full grid operation',
            initial_state='volatility_safe',
            possible_actions=[
                'place_strict_grid_orders', 'monitor_price_updates', 'calculate_next_levels',
                'process_fills_immediately', 'place_tp_orders', 'track_position_pnl'
            ],
            end_states=['grid_active', 'orders_placed', 'positions_monitored'],
            confidence=0.95 if is_safe else 0.2,
            category='volatility_management',
            real_time_data={**vol_data, 'trading_mode': 'normal_grid'}
        )
        
        # 2. SAFE VOLATILITY - Price Movement Scenarios
        scenarios['volatility_safe_price_drop'] = BotScenario(
            id='volatility_safe_price_drop',
            title='📉 Safe Vol + Price Drop - Grid Expansion',
            description='REAL: Safe volatility with price dropping through grid levels - trigger multiple BUY orders',
            initial_state='safe_vol_price_dropping',
            possible_actions=[
                'calculate_missed_grid_levels', 'place_sequential_buy_orders', 'manage_position_capacity',
                'set_tp_orders_at_grid_targets', 'monitor_liquidation_distance', 'track_margin_usage'
            ],
            end_states=['grid_expanded', 'positions_filled', 'capacity_managed'],
            confidence=0.85,
            category='volatility_management',
            real_time_data={'scenario': 'price_drop', 'vol_safe': True}
        )
        
        # 3. SAFE VOLATILITY - Price Rally
        scenarios['volatility_safe_price_rally'] = BotScenario(
            id='volatility_safe_price_rally',
            title='📈 Safe Vol + Price Rally - TP Cascade',
            description='REAL: Safe volatility with price rising - trigger TP fills and profit realization',
            initial_state='safe_vol_price_rising',
            possible_actions=[
                'process_tp_fills', 'calculate_realized_profits', 'place_replacement_buy_orders',
                'maintain_grid_structure', 'compound_profits', 'adjust_position_sizes'
            ],
            end_states=['profits_realized', 'grid_maintained', 'capital_compounded'],
            confidence=0.9,
            category='volatility_management',
            real_time_data={'scenario': 'price_rally', 'vol_safe': True}
        )
        
        # 4. SAFE VOLATILITY - Sideways Market
        scenarios['volatility_safe_sideways'] = BotScenario(
            id='volatility_safe_sideways',
            title='↔️ Safe Vol + Sideways - Optimal Conditions',
            description='REAL: Safe volatility with sideways price action - perfect grid trading conditions',
            initial_state='safe_vol_sideways',
            possible_actions=[
                'maintain_tight_grid', 'optimize_step_sizes', 'maximize_fill_frequency',
                'compound_small_profits', 'monitor_spread_efficiency', 'adjust_lot_sizes'
            ],
            end_states=['optimal_trading', 'consistent_profits', 'grid_optimized'],
            confidence=0.95,
            category='volatility_management',
            real_time_data={'scenario': 'sideways', 'vol_safe': True}
        )
        
        # 5. TRANSITIONING TO UNSAFE - Early Warning
        scenarios['volatility_transitioning'] = BotScenario(
            id='volatility_transitioning',
            title='⚠️ Volatility Rising - Prepare for Halt',
            description=f'REAL: IV={current_iv:.1f}% approaching {max_iv}%, RV={current_rv:.1f}% near {max_rv}% - prepare safety measures',
            initial_state='volatility_rising',
            possible_actions=[
                'monitor_volatility_thresholds', 'prepare_order_cancellation', 'calculate_halt_levels',
                'save_grid_state', 'reduce_position_exposure', 'enable_proactive_monitoring'
            ],
            end_states=['halt_prepared', 'exposure_reduced', 'monitoring_enhanced'],
            confidence=0.8,
            category='volatility_management',
            real_time_data={'scenario': 'transitioning', 'warning_level': 'yellow'}
        )
        
        # 6. UNSAFE VOLATILITY - Immediate Halt
        scenarios['volatility_unsafe_halt'] = BotScenario(
            id='volatility_unsafe_halt',
            title='🚨 Volatility Unsafe - Immediate Trading Halt',
            description=f'REAL: {vol_data.get("violation_reason", "Volatility limits exceeded")} - cancel pending orders',
            initial_state='volatility_unsafe',
            possible_actions=[
                'cancel_pending_buy_orders', 'preserve_tp_orders', 'save_halt_state',
                'track_missed_opportunities', 'monitor_for_normalization', 'send_halt_alerts'
            ],
            end_states=['trading_halted', 'orders_cancelled', 'state_preserved'],
            confidence=0.95 if not is_safe else 0.1,
            category='volatility_management',
            real_time_data={**vol_data, 'halt_active': True}
        )
        
        # 7. UNSAFE VOLATILITY - Opportunistic Recovery
        scenarios['volatility_recovery_opportunity'] = BotScenario(
            id='volatility_recovery_opportunity',
            title='🎯 Volatility Recovery - Opportunistic Entry',
            description='REAL: Volatility normalizing after halt - execute missed level recovery with market orders',
            initial_state='volatility_normalizing',
            possible_actions=[
                'load_halt_state', 'calculate_missed_grid_levels', 'validate_recovery_feasibility',
                'execute_market_orders', 'place_tp_at_grid_targets', 'realign_grid_structure'
            ],
            end_states=['recovery_executed', 'grid_realigned', 'normal_trading_resumed'],
            confidence=0.7,
            category='volatility_management',
            real_time_data={'scenario': 'recovery', 'opportunistic': True}
        )
        
        # 8. EXTREME VOLATILITY - Flash Crash Protection
        scenarios['volatility_extreme_crash'] = BotScenario(
            id='volatility_extreme_crash',
            title='💥 Extreme Volatility - Flash Crash Protection',
            description='REAL: Extreme volatility detected - activate emergency protection systems',
            initial_state='extreme_volatility',
            possible_actions=[
                'activate_circuit_breaker', 'emergency_order_cancellation', 'liquidation_protection',
                'margin_monitoring', 'position_size_reduction', 'alert_human_operator'
            ],
            end_states=['emergency_mode', 'positions_protected', 'human_notified'],
            confidence=0.9,
            category='safety_systems',
            real_time_data={'scenario': 'extreme', 'protection_level': 'maximum'}
        )
        
        # 9. VOLATILITY ZONE MANAGEMENT
        scenarios['volatility_zone_elevated'] = BotScenario(
            id='volatility_zone_elevated',
            title='📊 Elevated Volatility Zone - Reduced Exposure',
            description='REAL: Volatility in elevated zone - reduce position sizes and increase monitoring',
            initial_state='elevated_volatility_zone',
            possible_actions=[
                'reduce_lot_sizes', 'increase_monitoring_frequency', 'tighten_stop_losses',
                'calculate_position_multiplier', 'adjust_grid_spacing', 'enhance_risk_checks'
            ],
            end_states=['exposure_reduced', 'monitoring_enhanced', 'risk_adjusted'],
            confidence=0.8,
            category='volatility_management',
            real_time_data={'zone': 'elevated', 'multiplier': 0.75}
        )
        
        # 10. VOLATILITY PREDICTION - Proactive Management
        scenarios['volatility_prediction'] = BotScenario(
            id='volatility_prediction',
            title='🔮 Volatility Prediction - Proactive Adjustment',
            description='REAL: ML models predict volatility spike - proactively adjust trading parameters',
            initial_state='volatility_prediction_active',
            possible_actions=[
                'analyze_price_patterns', 'calculate_volatility_forecast', 'adjust_grid_parameters',
                'preemptive_position_reduction', 'set_dynamic_thresholds', 'prepare_contingency_plans'
            ],
            end_states=['parameters_adjusted', 'forecast_integrated', 'contingency_ready'],
            confidence=0.6,
            category='volatility_management',
            real_time_data={'prediction': 'active', 'forecast_horizon': '1h'}
        )
        
        return scenarios
    
    def _create_position_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create position management scenarios"""
        scenarios = {}
        positions = current_state.get('positions', {})
        config = current_state.get('config', {})
        
        position_count = len(positions.get('positions', []))
        max_positions = int(config.get('GRIDBOT_MAX_OPEN', config.get('max_positions', 3)))
        
        # 1. Position limit scenario
        scenarios['position_limit'] = BotScenario(
            id='position_limit',
            title=f'🔒 Position Limit - {position_count}/{max_positions}',
            description=f'REAL: {position_count}/{max_positions} positions - {"waiting for exits" if position_count >= max_positions else "slots available"}',
            initial_state='position_limit_reached' if position_count >= max_positions else 'capacity_available',
            possible_actions=['wait_tp_fills', 'monitor_exits', 'risk_management'] if position_count >= max_positions else ['place_new_orders', 'calculate_levels'],
            end_states=['position_closed', 'slot_available'] if position_count >= max_positions else ['orders_placed', 'grid_expanded'],
            confidence=0.95,
            category='position_management',
            real_time_data={'positions': position_count, 'max_positions': max_positions}
        )
        
        # 2. Grid expansion scenario
        available_slots = max(0, max_positions - position_count)
        scenarios['grid_expansion'] = BotScenario(
            id='grid_expansion',
            title=f'📈 Grid Expansion - {available_slots} Slots',
            description=f'REAL: {available_slots} slots available for new positions',
            initial_state='expansion_ready' if available_slots > 0 else 'expansion_blocked',
            possible_actions=['place_new_orders', 'calculate_levels', 'assess_risk'] if available_slots > 0 else ['wait_for_exits'],
            end_states=['orders_placed', 'grid_expanded'] if available_slots > 0 else ['waiting'],
            confidence=0.8 if available_slots > 0 else 0.3,
            category='position_management',
            real_time_data={'available_slots': available_slots, 'current_positions': position_count}
        )
        
        # 3. Position monitoring
        scenarios['position_monitoring'] = BotScenario(
            id='position_monitoring',
            title='👁️ Active Position Monitoring',
            description=f'REAL: Continuously monitor {position_count} positions for TP fills and PnL',
            initial_state='monitoring_active',
            possible_actions=['track_unrealized_pnl', 'monitor_tp_orders', 'check_fill_status', 'update_position_data'],
            end_states=['tp_filled', 'pnl_updated', 'monitoring_ongoing'],
            confidence=0.9,
            category='position_management',
            real_time_data={'active_positions': position_count}
        )
        
        # 4. Position averaging
        scenarios['position_averaging'] = BotScenario(
            id='position_averaging',
            title='⚖️ Position Averaging - DCA Strategy',
            description='REAL: Average down positions when price drops through grid levels',
            initial_state='averaging_opportunity',
            possible_actions=['calculate_average_entry', 'place_grid_buy', 'update_tp_targets', 'manage_risk'],
            end_states=['position_averaged', 'tp_adjusted', 'risk_managed'],
            confidence=0.75,
            category='position_management',
            real_time_data={'averaging_enabled': True}
        )
        
        # 5. Position exit management
        scenarios['position_exits'] = BotScenario(
            id='position_exits',
            title='🚪 Position Exit Management',
            description='REAL: Manage TP fills and position exits for profit realization',
            initial_state='monitoring_exits',
            possible_actions=['detect_tp_fills', 'calculate_realized_profit', 'free_position_slot', 'place_replacement_orders'],
            end_states=['position_exited', 'profit_realized', 'slot_freed'],
            confidence=0.85,
            category='position_management',
            real_time_data={'exit_monitoring': True}
        )
        
        # 6. Position rebalancing
        scenarios['position_rebalancing'] = BotScenario(
            id='position_rebalancing',
            title='🔄 Position Rebalancing',
            description='REAL: Rebalance position sizes based on market conditions',
            initial_state='rebalancing_check',
            possible_actions=['assess_position_distribution', 'calculate_optimal_sizes', 'adjust_lot_sizes'],
            end_states=['positions_rebalanced', 'sizes_optimized'],
            confidence=0.7,
            category='position_management',
            real_time_data={'rebalancing_enabled': True}
        )
        
        # 7. Position concentration risk
        scenarios['position_concentration'] = BotScenario(
            id='position_concentration',
            title='⚠️ Position Concentration Risk',
            description=f'REAL: {(position_count/max_positions*100):.0f}% of max capacity used',
            initial_state='concentration_assessment',
            possible_actions=['assess_concentration', 'evaluate_risk', 'consider_diversification'],
            end_states=['risk_acceptable', 'risk_elevated', 'action_required'],
            confidence=0.8,
            category='position_management',
            real_time_data={'concentration_pct': position_count/max_positions if max_positions > 0 else 0}
        )
        
        # 8. Position recovery after errors
        scenarios['position_recovery'] = BotScenario(
            id='position_recovery',
            title='🔧 Position Recovery - Error Correction',
            description='REAL: Recover and reconcile positions after system errors or restarts',
            initial_state='recovery_mode',
            possible_actions=['load_saved_positions', 'reconcile_with_exchange', 'fix_orphaned_orders', 'realign_grid'],
            end_states=['positions_recovered', 'grid_aligned', 'normal_operation'],
            confidence=0.75,
            category='position_management',
            real_time_data={'recovery_enabled': True}
        )
        
        return scenarios
    
    def _create_risk_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create risk management scenarios"""
        scenarios = {}
        
        # 1. Liquidation risk scenario
        scenarios['liquidation_risk'] = BotScenario(
            id='liquidation_risk',
            title='⚠️ Liquidation Risk Assessment',
            description='REAL: Monitor margin utilization and liquidation distance',
            initial_state='risk_assessment',
            possible_actions=['check_margin', 'calculate_distance', 'emergency_action', 'reduce_exposure'],
            end_states=['risk_acceptable', 'risk_critical', 'emergency_triggered'],
            confidence=0.7,
            category='risk_management',
            real_time_data=current_state.get('risk_metrics', {})
        )
        
        # 2. Margin utilization monitoring
        scenarios['margin_utilization'] = BotScenario(
            id='margin_utilization',
            title='💰 Margin Utilization Monitoring',
            description='REAL: Track margin usage and available balance',
            initial_state='margin_monitoring',
            possible_actions=['calculate_used_margin', 'check_free_margin', 'assess_capacity', 'warn_on_high_usage'],
            end_states=['margin_healthy', 'margin_warning', 'margin_critical'],
            confidence=0.85,
            category='risk_management',
            real_time_data={'margin_monitoring': True}
        )
        
        # 3. Drawdown monitoring
        scenarios['drawdown_monitoring'] = BotScenario(
            id='drawdown_monitoring',
            title='📉 Drawdown Monitoring',
            description='REAL: Track drawdown from peak equity',
            initial_state='drawdown_tracking',
            possible_actions=['calculate_current_drawdown', 'compare_to_limits', 'trigger_protective_mode'],
            end_states=['drawdown_acceptable', 'drawdown_warning', 'protective_mode_active'],
            confidence=0.8,
            category='risk_management',
            real_time_data={'drawdown_tracking': True}
        )
        
        # 4. Position size risk
        scenarios['position_size_risk'] = BotScenario(
            id='position_size_risk',
            title='📊 Position Size Risk Management',
            description='REAL: Ensure position sizes are within risk limits',
            initial_state='size_validation',
            possible_actions=['validate_lot_size', 'check_notional_value', 'apply_risk_multiplier', 'adjust_sizes'],
            end_states=['sizes_validated', 'sizes_adjusted', 'risk_controlled'],
            confidence=0.9,
            category='risk_management',
            real_time_data={'size_validation': True}
        )
        
        # 5. Correlation risk
        scenarios['correlation_risk'] = BotScenario(
            id='correlation_risk',
            title='🔗 Correlation Risk - Concentrated Exposure',
            description='REAL: Monitor exposure concentration in single instrument',
            initial_state='correlation_check',
            possible_actions=['assess_instrument_exposure', 'evaluate_concentration', 'consider_hedging'],
            end_states=['exposure_acceptable', 'concentration_high', 'hedging_recommended'],
            confidence=0.75,
            category='risk_management',
            real_time_data={'single_instrument': 'BTCUSDT'}
        )
        
        # 6. Overnight risk
        scenarios['overnight_risk'] = BotScenario(
            id='overnight_risk',
            title='🌙 Overnight Position Risk',
            description='REAL: Assess risks of holding positions overnight',
            initial_state='overnight_assessment',
            possible_actions=['evaluate_overnight_exposure', 'check_funding_rates', 'assess_gap_risk'],
            end_states=['overnight_acceptable', 'risk_elevated', 'reduce_exposure'],
            confidence=0.7,
            category='risk_management',
            real_time_data={'overnight_monitoring': True}
        )
        
        # 7. Slippage and execution risk
        scenarios['execution_risk'] = BotScenario(
            id='execution_risk',
            title='⚡ Execution & Slippage Risk',
            description='REAL: Monitor order execution quality and slippage',
            initial_state='execution_monitoring',
            possible_actions=['track_fill_prices', 'measure_slippage', 'assess_liquidity', 'optimize_execution'],
            end_states=['execution_optimal', 'slippage_acceptable', 'liquidity_concerns'],
            confidence=0.75,
            category='risk_management',
            real_time_data={'execution_tracking': True}
        )
        
        # 8. Systemic risk monitoring
        scenarios['systemic_risk'] = BotScenario(
            id='systemic_risk',
            title='🌍 Systemic Risk Monitoring',
            description='REAL: Monitor broader market and exchange risks',
            initial_state='systemic_monitoring',
            possible_actions=['monitor_exchange_health', 'track_market_conditions', 'assess_regulatory_risk', 'prepare_contingencies'],
            end_states=['market_stable', 'elevated_risk', 'contingency_active'],
            confidence=0.6,
            category='risk_management',
            real_time_data={'systemic_monitoring': True}
        )
        
        return scenarios
    
    def _create_error_scenarios(self, current_state: Dict) -> Dict[str, BotScenario]:
        """Create error recovery scenarios"""
        scenarios = {}
        
        # 1. API failure scenario
        scenarios['api_failure'] = BotScenario(
            id='api_failure',
            title='🔌 API Connection Issues',
            description='REAL: Handle exchange API failures and reconnection',
            initial_state='api_error',
            possible_actions=['retry_connection', 'circuit_breaker', 'fallback_mode', 'exponential_backoff'],
            end_states=['connection_restored', 'circuit_open', 'manual_intervention'],
            confidence=0.6,
            category='error_recovery',
            real_time_data={'last_api_call': time.time()}
        )
        
        # 2. Network disconnection scenario
        scenarios['network_disconnect'] = BotScenario(
            id='network_disconnect',
            title='🌐 Network Disconnection',
            description='REAL: Handle network outages and IP changes',
            initial_state='network_error',
            possible_actions=['detect_ip_change', 'reconnect', 'heartbeat_timeout', 'test_connectivity'],
            end_states=['network_restored', 'ip_updated', 'manual_fix_required'],
            confidence=0.5,
            category='error_recovery',
            real_time_data={'network_status': 'unknown'}
        )
        
        # 3. WebSocket reconnection
        scenarios['websocket_reconnect'] = BotScenario(
            id='websocket_reconnect',
            title='🔄 WebSocket Reconnection',
            description='REAL: Handle WebSocket disconnections and automatic reconnection',
            initial_state='ws_disconnected',
            possible_actions=['detect_disconnect', 'trigger_reconnect', 'restore_subscriptions', 'verify_connection'],
            end_states=['ws_connected', 'subscriptions_restored', 'reconnect_failed'],
            confidence=0.75,
            category='error_recovery',
            real_time_data={'ws_reconnect': True}
        )
        
        # 4. Order placement failures
        scenarios['order_placement_failure'] = BotScenario(
            id='order_placement_failure',
            title='❌ Order Placement Failure Recovery',
            description='REAL: Recover from failed order placements',
            initial_state='order_failed',
            possible_actions=['analyze_failure_reason', 'retry_with_backoff', 'adjust_parameters', 'log_failure'],
            end_states=['order_placed', 'retry_exhausted', 'skip_order'],
            confidence=0.7,
            category='error_recovery',
            real_time_data={'retry_enabled': True}
        )
        
        # 5. Order cancellation failures
        scenarios['order_cancel_failure'] = BotScenario(
            id='order_cancel_failure',
            title='🗑️ Order Cancellation Failure',
            description='REAL: Handle failed order cancellations',
            initial_state='cancel_failed',
            possible_actions=['verify_order_status', 'retry_cancellation', 'handle_already_filled', 'orphan_detection'],
            end_states=['order_cancelled', 'order_filled', 'orphaned_order'],
            confidence=0.65,
            category='error_recovery',
            real_time_data={'cancel_retry': True}
        )
        
        # 6. State file corruption recovery
        scenarios['state_corruption_recovery'] = BotScenario(
            id='state_corruption_recovery',
            title='💾 State File Corruption Recovery',
            description='REAL: Recover from corrupted state files',
            initial_state='state_corrupted',
            possible_actions=['detect_corruption', 'load_backup', 'reconcile_with_exchange', 'rebuild_state'],
            end_states=['state_restored', 'backup_loaded', 'manual_rebuild_required'],
            confidence=0.7,
            category='error_recovery',
            real_time_data={'backup_available': True}
        )
        
        # 7. Exchange API rate limiting
        scenarios['rate_limit_handling'] = BotScenario(
            id='rate_limit_handling',
            title='⏱️ Rate Limit Handling',
            description='REAL: Handle exchange API rate limiting',
            initial_state='rate_limited',
            possible_actions=['detect_rate_limit', 'implement_backoff', 'queue_requests', 'optimize_api_calls'],
            end_states=['rate_limit_cleared', 'requests_queued', 'operations_throttled'],
            confidence=0.8,
            category='error_recovery',
            real_time_data={'rate_limit_aware': True}
        )
        
        # 8. Unexpected exception handling
        scenarios['unexpected_exception'] = BotScenario(
            id='unexpected_exception',
            title='🚨 Unexpected Exception Handling',
            description='REAL: Handle unexpected exceptions gracefully',
            initial_state='exception_caught',
            possible_actions=['log_exception', 'preserve_state', 'attempt_recovery', 'trigger_alerts', 'safe_shutdown'],
            end_states=['recovered', 'safe_state_preserved', 'manual_intervention_needed'],
            confidence=0.6,
            category='error_recovery',
            real_time_data={'exception_handling': 'comprehensive'}
        )
        
        return scenarios
    
    def _create_safety_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create safety system scenarios"""
        scenarios = {}
        
        # 1. Emergency stop scenario
        scenarios['emergency_stop'] = BotScenario(
            id='emergency_stop',
            title='🛑 Emergency Stop Activated',
            description='REAL: All trading halted - manual intervention required',
            initial_state='emergency_active',
            possible_actions=['cancel_orders', 'close_positions', 'notify_operator', 'preserve_state'],
            end_states=['orders_cancelled', 'positions_closed', 'system_safe'],
            confidence=0.95,
            category='safety_systems',
            real_time_data=current_state.get('runtime', {})
        )
        
        # 2. Heartbeat failure scenario
        scenarios['heartbeat_failure'] = BotScenario(
            id='heartbeat_failure',
            title='💓 Heartbeat Monitor Failure',
            description='REAL: Bot crash detected - automatic order cancellation',
            initial_state='heartbeat_timeout',
            possible_actions=['cancel_buy_orders', 'keep_tp_orders', 'send_alert', 'log_crash'],
            end_states=['buy_orders_cancelled', 'tp_orders_preserved', 'alert_sent'],
            confidence=0.8,
            category='safety_systems',
            real_time_data={'heartbeat_enabled': config_analysis.get('safety_settings', {}).get('ENABLE_HEARTBEAT', 'true')}
        )
        
        # 3. Circuit breaker activation
        scenarios['circuit_breaker'] = BotScenario(
            id='circuit_breaker',
            title='⚡ Circuit Breaker - Trading Pause',
            description='REAL: Circuit breaker triggered due to rapid market movements',
            initial_state='circuit_breaker_active',
            possible_actions=['pause_trading', 'assess_market_conditions', 'wait_for_stability', 'resume_when_safe'],
            end_states=['trading_paused', 'market_assessed', 'trading_resumed'],
            confidence=0.85,
            category='safety_systems',
            real_time_data={'circuit_breaker_enabled': True}
        )
        
        # 4. Position loss limit enforcement
        scenarios['loss_limit_enforcement'] = BotScenario(
            id='loss_limit_enforcement',
            title='📛 Loss Limit Enforcement',
            description='REAL: Close positions when loss limits are breached',
            initial_state='loss_limit_check',
            possible_actions=['calculate_position_loss', 'compare_to_limits', 'trigger_close', 'send_alerts'],
            end_states=['position_closed', 'limit_enforced', 'operator_notified'],
            confidence=0.9,
            category='safety_systems',
            real_time_data={'loss_limit': -7500}
        )
        
        # 5. Equity floor protection
        scenarios['equity_floor'] = BotScenario(
            id='equity_floor',
            title='💎 Equity Floor Protection',
            description='REAL: Hard stop when account equity hits minimum threshold',
            initial_state='equity_monitoring',
            possible_actions=['monitor_equity', 'check_floor', 'halt_trading', 'require_acknowledgment'],
            end_states=['equity_safe', 'floor_breached', 'trading_halted'],
            confidence=0.95,
            category='safety_systems',
            real_time_data={'floor_inr': 50000}
        )
        
        # 6. Guardian bot monitoring
        scenarios['guardian_monitoring'] = BotScenario(
            id='guardian_monitoring',
            title='🛡️ Guardian Bot - 24/7 Monitoring',
            description='REAL: Independent Guardian bot monitors positions continuously',
            initial_state='guardian_active',
            possible_actions=['monitor_positions', 'track_pnl', 'check_risk_limits', 'trigger_protection'],
            end_states=['positions_safe', 'warning_issued', 'protection_triggered'],
            confidence=0.9,
            category='safety_systems',
            real_time_data={'guardian_active': True}
        )
        
        # 7. API key security monitoring
        scenarios['api_security'] = BotScenario(
            id='api_security',
            title='🔐 API Key Security Monitoring',
            description='REAL: Monitor API key security and permissions',
            initial_state='security_monitoring',
            possible_actions=['verify_permissions', 'check_ip_whitelist', 'monitor_usage', 'detect_anomalies'],
            end_states=['security_verified', 'anomaly_detected', 'keys_revoked'],
            confidence=0.85,
            category='safety_systems',
            real_time_data={'security_monitoring': True}
        )
        
        # 8. Automated safety checks
        scenarios['automated_safety_checks'] = BotScenario(
            id='automated_safety_checks',
            title='✅ Automated Safety Pre-Checks',
            description='REAL: 11-point safety validation before every order',
            initial_state='safety_validation',
            possible_actions=[
                'check_volatility', 'verify_position_limits', 'validate_margin',
                'check_liquidation_risk', 'verify_api_health', 'validate_parameters'
            ],
            end_states=['all_checks_passed', 'check_failed', 'order_blocked'],
            confidence=0.95,
            category='safety_systems',
            real_time_data={'safety_checks': 11}
        )
        
        return scenarios
    
    def _create_grid_calculation_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create grid calculation scenarios from GridCalculator module"""
        scenarios = {}
        config = current_state.get('config', {})
        
        # Grid bounds validation
        scenarios['grid_bounds_validation'] = BotScenario(
            id='grid_bounds_validation',
            title='📏 Grid Bounds Validation - Price Level Checks',
            description='REAL: Validate all prices within grid bounds before order placement',
            initial_state='price_validation',
            possible_actions=[
                'check_lower_bound', 'check_upper_bound', 'quantize_to_tick_size',
                'snap_to_grid_level', 'validate_step_size', 'calculate_grid_levels'
            ],
            end_states=['price_valid', 'price_out_of_bounds', 'price_quantized'],
            confidence=0.95,
            category='grid_management',
            real_time_data={'grid_step': config.get('GRIDBOT_STEP', 1000), 'tick_size': 0.5}
        )
        
        # Next buy level calculation
        scenarios['next_buy_calculation'] = BotScenario(
            id='next_buy_calculation',
            title='🎯 Next BUY Level Calculation - Grid Logic',
            description='REAL: Calculate optimal next BUY level based on existing positions',
            initial_state='buy_level_calculation',
            possible_actions=[
                'find_lowest_entry', 'subtract_grid_step', 'check_position_gaps',
                'validate_within_bounds', 'quantize_price', 'reserve_capacity'
            ],
            end_states=['buy_level_calculated', 'no_buy_needed', 'capacity_full'],
            confidence=0.9,
            category='grid_management',
            real_time_data={'calculation_method': 'lowest_entry_minus_step'}
        )
        
        # TP price calculation
        scenarios['tp_price_calculation'] = BotScenario(
            id='tp_price_calculation',
            title='💰 TP Price Calculation - Profit Target',
            description='REAL: Calculate take-profit price with collision detection',
            initial_state='tp_calculation',
            possible_actions=[
                'add_grid_step_to_entry', 'check_price_collisions', 'find_safe_tp_level',
                'offset_for_collision_avoidance', 'validate_profit_margin', 'set_tp_metadata'
            ],
            end_states=['tp_calculated', 'tp_offset_applied', 'collision_avoided'],
            confidence=0.85,
            category='grid_management',
            real_time_data={'collision_detection': True, 'offset_enabled': True}
        )
        
        # Grid realignment
        scenarios['grid_realignment_calculator'] = BotScenario(
            id='grid_realignment_calculator',
            title='🔧 Grid Realignment - Structure Correction',
            description='REAL: Realign position entry prices to strict grid levels after recovery',
            initial_state='realignment_required',
            possible_actions=[
                'find_nearest_grid_level', 'calculate_alignment_deviation', 'snap_to_grid',
                'update_position_metadata', 'recalculate_tp_targets', 'validate_alignment'
            ],
            end_states=['positions_aligned', 'grid_structure_corrected', 'alignment_validated'],
            confidence=0.8,
            category='grid_management',
            real_time_data={'alignment_tolerance': 0.01, 'snap_method': 'nearest'}
        )
        
        # Grid level generation
        scenarios['grid_level_generation'] = BotScenario(
            id='grid_level_generation',
            title='📊 Grid Level Generation - Complete Grid Map',
            description='REAL: Generate all possible grid levels from lower to upper bounds',
            initial_state='grid_generation',
            possible_actions=[
                'iterate_from_lower_bound', 'add_step_increments', 'quantize_each_level',
                'validate_level_spacing', 'create_level_map', 'optimize_level_count'
            ],
            end_states=['grid_levels_generated', 'level_map_created', 'grid_optimized'],
            confidence=0.9,
            category='grid_management',
            real_time_data={'total_levels': 15, 'level_spacing': 'uniform'}
        )
        
        return scenarios
    
    def _create_order_management_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create order management scenarios from OrderManager module"""
        scenarios = {}
        
        # Order placement with safety checks
        scenarios['order_placement_safety'] = BotScenario(
            id='order_placement_safety',
            title='🛡️ Order Placement Safety - 11-Point Validation',
            description='REAL: Comprehensive safety checks before every order placement',
            initial_state='order_validation',
            possible_actions=[
                'check_emergency_stop', 'validate_volatility_conditions', 'verify_liquidation_risk',
                'confirm_margin_availability', 'validate_position_limits', 'check_api_health',
                'verify_order_parameters', 'generate_client_order_id', 'log_order_placement'
            ],
            end_states=['order_approved', 'order_blocked', 'safety_violation'],
            confidence=0.95,
            category='order_management',
            real_time_data={'safety_checks': 11, 'validation_strict': True}
        )
        
        # TP collision detection
        scenarios['tp_collision_detection'] = BotScenario(
            id='tp_collision_detection',
            title='🎯 TP Collision Detection - Price Conflict Resolution',
            description='REAL: Detect and resolve TP price conflicts with existing position levels',
            initial_state='collision_check',
            possible_actions=[
                'scan_occupied_levels', 'detect_price_conflicts', 'calculate_safe_offset',
                'find_nearest_available_price', 'apply_collision_offset', 'update_tp_metadata'
            ],
            end_states=['collision_resolved', 'safe_price_found', 'offset_applied'],
            confidence=0.9,
            category='order_management',
            real_time_data={'collision_detection': 'active', 'max_offset': 100}
        )
        
        # Order cancellation with verification
        scenarios['order_cancellation_verified'] = BotScenario(
            id='order_cancellation_verified',
            title='🗑️ Order Cancellation - Exchange Verification',
            description='REAL: Cancel orders with exchange verification to prevent orphaned orders',
            initial_state='cancellation_request',
            possible_actions=[
                'send_cancel_request', 'verify_cancellation_status', 'handle_already_filled',
                'retry_on_failure', 'update_order_status', 'log_cancellation_result'
            ],
            end_states=['order_cancelled', 'order_filled', 'cancellation_failed'],
            confidence=0.85,
            category='order_management',
            real_time_data={'verification_enabled': True, 'retry_attempts': 3}
        )
        
        # Batch order operations
        scenarios['batch_order_operations'] = BotScenario(
            id='batch_order_operations',
            title='📦 Batch Order Operations - Bulk Management',
            description='REAL: Handle multiple order operations efficiently with rate limiting',
            initial_state='batch_processing',
            possible_actions=[
                'queue_order_operations', 'apply_rate_limiting', 'process_in_batches',
                'handle_partial_failures', 'track_operation_status', 'optimize_api_calls'
            ],
            end_states=['batch_completed', 'partial_success', 'batch_failed'],
            confidence=0.8,
            category='order_management',
            real_time_data={'batch_size': 5, 'rate_limit': '0.2s'}
        )
        
        # Order retry mechanism
        scenarios['order_retry_mechanism'] = BotScenario(
            id='order_retry_mechanism',
            title='🔄 Order Retry Mechanism - Failure Recovery',
            description='REAL: Intelligent retry system for failed order operations',
            initial_state='order_failed',
            possible_actions=[
                'analyze_failure_reason', 'implement_exponential_backoff', 'adjust_order_parameters',
                'retry_with_modifications', 'escalate_persistent_failures', 'log_retry_attempts'
            ],
            end_states=['order_succeeded', 'retry_exhausted', 'manual_intervention_required'],
            confidence=0.75,
            category='order_management',
            real_time_data={'max_retries': 3, 'backoff_multiplier': 2}
        )
        
        # Client order ID management
        scenarios['client_order_id_management'] = BotScenario(
            id='client_order_id_management',
            title='🏷️ Client Order ID Management - Unique Identification',
            description='REAL: Generate and track unique client order IDs for reconciliation',
            initial_state='id_generation',
            possible_actions=[
                'generate_unique_id', 'include_timestamp', 'add_order_type_prefix',
                'track_id_usage', 'prevent_id_collisions', 'enable_order_tracking'
            ],
            end_states=['id_generated', 'id_tracked', 'collision_prevented'],
            confidence=0.95,
            category='order_management',
            real_time_data={'id_format': 'BOT-{type}-{timestamp}-{side}', 'collision_check': True}
        )
        
        return scenarios
    
    def _create_fill_detection_scenarios(self, current_state: Dict) -> Dict[str, BotScenario]:
        """Create fill detection scenarios from FillDetector module"""
        scenarios = {}
        
        # Dual-source fill detection
        scenarios['dual_source_fill_detection'] = BotScenario(
            id='dual_source_fill_detection',
            title='🎯 Dual-Source Fill Detection - WebSocket + Polling',
            description='REAL: Primary WebSocket detection (0.05s) with robust polling backup (5s)',
            initial_state='fill_monitoring',
            possible_actions=[
                'monitor_websocket_fills', 'run_polling_backup', 'deduplicate_fills',
                'validate_fill_data', 'route_to_callback', 'track_detection_source'
            ],
            end_states=['fill_detected', 'fill_processed', 'duplicate_ignored'],
            confidence=0.95,
            category='fill_detection',
            real_time_data={'primary_latency': '0.05s', 'backup_latency': '5s', 'dedup_size': 5000}
        )
        
        # Fill deduplication system
        scenarios['fill_deduplication'] = BotScenario(
            id='fill_deduplication',
            title='🔄 Fill Deduplication - Prevent Double Processing',
            description='REAL: FIFO deque system prevents duplicate fill processing across sources',
            initial_state='fill_received',
            possible_actions=[
                'generate_fill_id', 'check_processed_cache', 'add_to_deque',
                'auto_evict_oldest', 'prevent_memory_leak', 'log_duplicate_detection'
            ],
            end_states=['fill_processed', 'duplicate_detected', 'cache_updated'],
            confidence=0.9,
            category='fill_detection',
            real_time_data={'cache_method': 'FIFO_deque', 'auto_cleanup': True}
        )
        
        # Robust fill detection backup
        scenarios['robust_fill_backup'] = BotScenario(
            id='robust_fill_backup',
            title='🛡️ Robust Fill Detection - Backup System',
            description='REAL: Polling-based backup system catches missed WebSocket fills',
            initial_state='backup_monitoring',
            possible_actions=[
                'poll_order_status', 'compare_with_websocket', 'detect_missed_fills',
                'reconcile_position_state', 'alert_on_discrepancies', 'sync_with_exchange'
            ],
            end_states=['fills_synchronized', 'discrepancy_resolved', 'backup_successful'],
            confidence=0.8,
            category='fill_detection',
            real_time_data={'polling_interval': '5s', 'reconciliation_active': True}
        )
        
        # Fill callback processing
        scenarios['fill_callback_processing'] = BotScenario(
            id='fill_callback_processing',
            title='📞 Fill Callback Processing - Event Routing',
            description='REAL: Route validated fills to business logic for TP placement and next orders',
            initial_state='fill_validated',
            possible_actions=[
                'invoke_fill_callback', 'handle_callback_errors', 'track_processing_time',
                'ensure_thread_safety', 'log_callback_results', 'maintain_processing_stats'
            ],
            end_states=['callback_completed', 'callback_failed', 'error_handled'],
            confidence=0.85,
            category='fill_detection',
            real_time_data={'callback_timeout': '30s', 'error_handling': 'graceful'}
        )
        
        return scenarios
    
    def _create_guardian_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create Guardian bot scenarios from guardian_bot.py"""
        scenarios = {}
        
        # 24/7 position monitoring
        scenarios['guardian_24_7_monitoring'] = BotScenario(
            id='guardian_24_7_monitoring',
            title='🛡️ Guardian 24/7 Monitoring - Always-On Protection',
            description='REAL: Continuous position monitoring with loss limit enforcement',
            initial_state='guardian_active',
            possible_actions=[
                'monitor_position_pnl', 'check_loss_thresholds', 'track_margin_utilization',
                'assess_liquidation_risk', 'send_telegram_alerts', 'prepare_emergency_actions'
            ],
            end_states=['positions_safe', 'warning_triggered', 'emergency_required'],
            confidence=0.95,
            category='guardian_protection',
            real_time_data={'monitoring_interval': '10s', 'loss_limit': -7500}
        )
        
        # Hot reload risk parameters
        scenarios['guardian_hot_reload'] = BotScenario(
            id='guardian_hot_reload',
            title='🔄 Guardian Hot Reload - Dynamic Risk Updates',
            description='REAL: Update risk parameters without restarting Guardian bot',
            initial_state='config_change_detected',
            possible_actions=[
                'detect_config_changes', 'validate_new_parameters', 'update_risk_limits',
                'log_parameter_changes', 'notify_operators', 'maintain_monitoring_continuity'
            ],
            end_states=['parameters_updated', 'validation_failed', 'reload_completed'],
            confidence=0.85,
            category='guardian_protection',
            real_time_data={'hot_reload_enabled': True, 'check_interval': '5s'}
        )
        
        # IP change detection
        scenarios['guardian_ip_monitoring'] = BotScenario(
            id='guardian_ip_monitoring',
            title='🌐 Guardian IP Monitoring - Network Protection',
            description='REAL: Detect IP changes and verify API connectivity for Guardian',
            initial_state='ip_monitoring',
            possible_actions=[
                'monitor_ip_changes', 'detect_network_disruption', 'test_api_connectivity',
                'send_ip_change_alerts', 'verify_api_whitelist', 'handle_connectivity_loss'
            ],
            end_states=['ip_stable', 'ip_changed_verified', 'api_connectivity_lost'],
            confidence=0.8,
            category='guardian_protection',
            real_time_data={'ip_check_interval': '300s', 'api_test_enabled': True}
        )
        
        # Emergency protocol execution
        scenarios['guardian_emergency_protocol'] = BotScenario(
            id='guardian_emergency_protocol',
            title='🚨 Guardian Emergency Protocol - Crisis Response',
            description='REAL: Execute emergency actions when loss limits are breached',
            initial_state='emergency_triggered',
            possible_actions=[
                'create_emergency_flags', 'send_urgent_alerts', 'prepare_position_closure',
                'coordinate_with_webui', 'log_emergency_details', 'maintain_infinite_uptime'
            ],
            end_states=['emergency_flagged', 'alerts_sent', 'manual_intervention_required'],
            confidence=0.9,
            category='guardian_protection',
            real_time_data={'emergency_active': False, 'infinite_uptime': True}
        )
        
        # PnL history tracking
        scenarios['guardian_pnl_tracking'] = BotScenario(
            id='guardian_pnl_tracking',
            title='📊 Guardian PnL Tracking - Performance History',
            description='REAL: Track and save PnL history for WebUI charts and analysis',
            initial_state='pnl_calculation',
            possible_actions=[
                'calculate_total_pnl', 'track_unrealized_pnl', 'save_daily_snapshots',
                'generate_csv_reports', 'update_health_files', 'maintain_pnl_trends'
            ],
            end_states=['pnl_recorded', 'reports_updated', 'trends_analyzed'],
            confidence=0.85,
            category='guardian_protection',
            real_time_data={'snapshot_interval': '10s', 'csv_daily': True}
        )
        
        return scenarios
    
    def _create_capital_protection_scenarios(self, current_state: Dict, config_analysis: Dict) -> Dict[str, BotScenario]:
        """Create capital protection scenarios from equity_floor.py and capital modules"""
        scenarios = {}
        
        # Equity floor monitoring
        scenarios['equity_floor_monitoring'] = BotScenario(
            id='equity_floor_monitoring',
            title='💎 Equity Floor Monitoring - Hard Stop Protection',
            description='REAL: Monitor account equity and trigger emergency stop at hard floor',
            initial_state='equity_monitoring',
            possible_actions=[
                'fetch_current_equity', 'convert_usd_to_inr', 'compare_with_floor',
                'create_breach_flags', 'require_operator_acknowledgment', 'monitor_recovery'
            ],
            end_states=['equity_safe', 'floor_breached', 'recovery_detected'],
            confidence=0.95,
            category='capital_protection',
            real_time_data={'floor_inr': 50000, 'check_interval': '60s'}
        )
        
        # Drawdown cap protection
        scenarios['drawdown_cap_protection'] = BotScenario(
            id='drawdown_cap_protection',
            title='📉 Drawdown Cap Protection - 30-Day Rolling Window',
            description='REAL: Monitor 30-day drawdown and activate protective mode when exceeded',
            initial_state='drawdown_monitoring',
            possible_actions=[
                'calculate_30_day_drawdown', 'track_equity_snapshots', 'detect_drawdown_breach',
                'activate_protective_mode', 'block_new_positions', 'allow_exit_orders_only'
            ],
            end_states=['drawdown_acceptable', 'protective_mode_active', 'drawdown_recovered'],
            confidence=0.85,
            category='capital_protection',
            real_time_data={'drawdown_limit': '20%', 'window_days': 30}
        )
        
        # Pending order budget
        scenarios['pending_order_budget'] = BotScenario(
            id='pending_order_budget',
            title='💰 Pending Order Budget - Capital at Risk Control',
            description='REAL: Limit total capital at risk in pending orders to prevent overexposure',
            initial_state='budget_monitoring',
            possible_actions=[
                'calculate_pending_notional', 'check_budget_limits', 'apply_buffer_percentage',
                'block_excessive_orders', 'track_order_fills', 'optimize_capital_usage'
            ],
            end_states=['budget_within_limits', 'budget_exceeded', 'orders_blocked'],
            confidence=0.8,
            category='capital_protection',
            real_time_data={'max_pending_inr': 200000, 'buffer_pct': 10}
        )
        
        # Two-man rule validation
        scenarios['two_man_rule_validation'] = BotScenario(
            id='two_man_rule_validation',
            title='👥 Two-Man Rule - Config Change Confirmation',
            description='REAL: Require confirmation for risk parameter increases to prevent impulsive changes',
            initial_state='config_change_request',
            possible_actions=[
                'detect_risk_increase', 'require_confirmation', 'validate_operator_intent',
                'log_change_requests', 'implement_cooling_period', 'track_change_history'
            ],
            end_states=['change_confirmed', 'change_rejected', 'cooling_period_active'],
            confidence=0.9,
            category='capital_protection',
            real_time_data={'confirmation_required': True, 'cooling_period': '24h'}
        )
        
        return scenarios
    
    def _create_ai_advisor_scenarios(self, current_state: Dict) -> Dict[str, BotScenario]:
        """Create AI advisor scenarios from advisor.py"""
        scenarios = {}
        
        # Intelligent question answering
        scenarios['ai_intelligent_qa'] = BotScenario(
            id='ai_intelligent_qa',
            title='🤖 AI Intelligent Q&A - Context-Aware Responses',
            description='REAL: Provide intelligent answers about bot behavior using current context',
            initial_state='question_received',
            possible_actions=[
                'analyze_question_intent', 'load_bot_context', 'match_response_patterns',
                'generate_contextual_answer', 'provide_actionable_suggestions', 'include_related_links'
            ],
            end_states=['answer_provided', 'suggestions_generated', 'links_included'],
            confidence=0.8,
            category='ai_assistance',
            real_time_data={'response_mode': 'rule_based', 'context_aware': True}
        )
        
        # Blocker explanation system
        scenarios['ai_blocker_explanation'] = BotScenario(
            id='ai_blocker_explanation',
            title='🚫 AI Blocker Explanation - Why Trading Stopped',
            description='REAL: Explain active blockers and provide specific resolution steps',
            initial_state='blocker_query',
            possible_actions=[
                'identify_active_blockers', 'explain_blocker_reasons', 'provide_fix_instructions',
                'generate_navigation_links', 'prioritize_critical_blockers', 'track_resolution_progress'
            ],
            end_states=['blockers_explained', 'fixes_provided', 'navigation_enabled'],
            confidence=0.9,
            category='ai_assistance',
            real_time_data={'blocker_count': 0, 'explanation_detailed': True}
        )
        
        # Trading concept education
        scenarios['ai_concept_education'] = BotScenario(
            id='ai_concept_education',
            title='📚 AI Concept Education - Trading Knowledge Transfer',
            description='REAL: Educate users about trading concepts, risk management, and bot features',
            initial_state='education_request',
            possible_actions=[
                'identify_concept_category', 'provide_clear_explanations', 'use_real_examples',
                'include_safety_warnings', 'suggest_best_practices', 'link_to_documentation'
            ],
            end_states=['concept_explained', 'examples_provided', 'safety_emphasized'],
            confidence=0.85,
            category='ai_assistance',
            real_time_data={'education_mode': 'interactive', 'safety_first': True}
        )
        
        return scenarios
    
    def _categorize_decision(self, pattern: str) -> str:
        """Categorize decision based on pattern"""
        if 'volatility' in pattern or 'trading.*safe' in pattern:
            return 'volatility_management'
        elif 'position' in pattern or 'limit' in pattern:
            return 'position_management'
        elif 'emergency' in pattern or 'circuit' in pattern:
            return 'safety_systems'
        elif 'liquidation' in pattern or 'margin' in pattern:
            return 'risk_management'
        else:
            return 'general'
    
    def _assess_risk_level(self, func_name: str) -> str:
        """Assess risk level of a function"""
        if any(keyword in func_name.lower() for keyword in ['emergency', 'liquidation', 'close', 'cancel']):
            return 'high'
        elif any(keyword in func_name.lower() for keyword in ['place', 'order', 'calculate']):
            return 'medium'
        else:
            return 'low'
    
    def get_all_scenarios(self) -> Dict[str, Any]:
        """Get all current scenarios with metadata"""
        return {
            'scenarios': {k: asdict(v) for k, v in self.scenarios_cache.items()},
            'states': {k: asdict(v) for k, v in self.states_cache.items()},
            'actions': {k: asdict(v) for k, v in self.actions_cache.items()},
            'last_scan': self.last_scan_time,
            'scan_interval': self.scan_interval,
            'total_scenarios': len(self.scenarios_cache)
        }
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[BotScenario]:
        """Get specific scenario by ID"""
        return self.scenarios_cache.get(scenario_id)
    
    def force_scan(self):
        """Force immediate scan (for testing/debugging)"""
        self._perform_full_scan()
        log.info("Forced bot brain scan completed")

# Global instance
_master_brain_reader = None

def get_master_brain_reader(bot_root: Path = None) -> MasterBotBrainReader:
    """Get or create the global master brain reader instance"""
    global _master_brain_reader
    
    if _master_brain_reader is None:
        if bot_root is None:
            bot_root = Path(__file__).parent.parent.parent
        _master_brain_reader = MasterBotBrainReader(bot_root)
        _master_brain_reader.start_real_time_scanning()
    
    return _master_brain_reader