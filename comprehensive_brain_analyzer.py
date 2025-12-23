#!/usr/bin/env python3
"""
Comprehensive Bot Brain Analyzer

This tool analyzes ALL bot decision-making code and creates:
1. Complete scenario coverage map
2. Visual decision flowcharts
3. Gap analysis (missing edge cases)
4. Trading scenario checklist (what's coded vs what's not)

Perfect for non-coders to understand bot logic and identify missing scenarios.
"""

import os
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

@dataclass
class DecisionPath:
    """Represents a decision point in the bot"""
    file: str
    function: str
    line: int
    condition: str
    action_if_true: str
    action_if_false: str
    category: str  # 'order', 'risk', 'volatility', 'position', 'error'
    
@dataclass
class Scenario:
    """Represents a trading scenario"""
    name: str
    coded: bool
    handlers: List[str]
    risk_level: str
    description: str
    missing_coverage: List[str]
    not_applicable: bool = False  # NOV 8: For scenarios not needed by design

class BotBrainAnalyzer:
    """Comprehensive bot brain analyzer"""
    
    def __init__(self, bot_root: Path):
        self.bot_root = bot_root
        self.decision_paths: List[DecisionPath] = []
        self.scenarios: Dict[str, Scenario] = {}
        self.functions: Dict[str, Dict] = {}
        self.error_handlers: Dict[str, List[str]] = defaultdict(list)
        self.state_variables: Set[str] = set()
        
        # Files to analyze
        self.strategy_files = [
            # Core Strategy
            'bot/strategy/gridbot.py',
            'bot/strategy/handlers/long_handler.py',  # ✅ NOV 8: LONG mode partial fills
            'bot/strategy/handlers/short_handler.py',  # ✅ NOV 8: SHORT mode partial fills
            'bot/strategy/modules/position_manager.py',
            'bot/strategy/modules/order_manager.py',
            'bot/strategy/modules/fill_detector.py',
            'bot/strategy/modules/reconciliation.py',
            'bot/strategy/modules/volatility_handler.py',
            'bot/strategy/modules/grid_calculator.py',
            
            # Safety & Risk Systems (NOV 8: Added comprehensive coverage)
            'bot/safety/gatekeeper.py',
            'bot/safety/circuit_breaker.py',
            'bot/safety/blocker_tracker.py',
            'bot/safety/config_guard.py',
            'bot/safety/exposure_limiter.py',
            'bot/safety/loss_limits.py',
            'bot/safety/order_confirmation_guard.py',
            'bot/safety/volatility_monitor.py',
            
            # Capital Management
            'bot/capital/equity_tracker.py',
            'bot/capital/equity_floor.py',
            'bot/capital/pending_budget.py',
            
            # Volatility & Prediction
            'bot/volatility/iv_rv_tracker.py',
            'bot/volatility/predictive_engine.py',
            
            # Guardian Bot (NOV 8: Critical for loss enforcement!)
            'bot/guardian/guardian_bot.py',
            'bot/guardian/risk_enforcer.py',
        ]
        
        # Trading scenarios to check (comprehensive list)
        self.trading_scenarios = {
            # Order Execution Scenarios
            'buy_order_placement': 'BUY order placement logic',
            'sell_order_placement': 'SELL order placement logic',
            'tp_order_placement': 'Take Profit order placement',
            'order_cancellation': 'Order cancellation handling',
            'partial_fill': 'Partial fill processing',
            'full_fill': 'Complete fill processing',
            'fill_confirmation': 'Fill confirmation (WebSocket primary + REST backup)',
            'duplicate_fill_prevention': 'Duplicate fill detection',
            
            # ✅ NOV 8: LONG Mode Scenarios (via LongFillHandler)
            'long_buy_fill': 'LONG mode: BUY order fill handling',
            'long_partial_buy': 'LONG mode: Partial BUY fill processing',
            'long_tp_placement': 'LONG mode: TP (SELL) placement',
            'long_tp_fill': 'LONG mode: TP fill and position close',
            'long_next_grid': 'LONG mode: Next grid BUY placement',
            
            # ✅ NOV 8: SHORT Mode Scenarios (via ShortFillHandler)
            'short_sell_fill': 'SHORT mode: SELL order fill handling',
            'short_partial_sell': 'SHORT mode: Partial SELL fill processing',
            'short_tp_placement': 'SHORT mode: TP (BUY) placement',
            'short_tp_fill': 'SHORT mode: TP fill and position close',
            'short_next_grid': 'SHORT mode: Next grid SELL placement',
            
            # Position Management
            'position_tracking': 'Active position tracking',
            'position_limit_check': 'Max positions limit enforcement',
            'position_reconciliation': 'Position sync with exchange',
            'orphaned_position': 'Orphaned position detection',
            'missing_tp': 'Missing TP order detection',
            'stale_tp': 'Stale TP order handling',
            
            # Price & Grid
            'grid_calculation': 'Grid level calculation',
            'price_update': 'Price update processing',
            'price_gap': 'Large price gap handling',
            'price_stale': 'Stale price detection',
            'grid_boundary': 'Grid boundary enforcement',
            'grid_seeding': 'Initial grid seeding',
            
            # Volatility & Risk
            'volatility_safe': 'Safe volatility conditions',
            'volatility_unsafe': 'Unsafe volatility handling',
            'volatility_recovery': 'Recovery from unsafe volatility',
            'circuit_breaker_open': 'Circuit breaker triggered',
            'circuit_breaker_halfopen': 'Circuit breaker testing',
            'drawdown_protection': 'Drawdown protective mode',
            'margin_check': 'Margin/capital adequacy',
            
            # NOV 8: Advanced Volatility & Risk Scenarios
            'iv_spike': 'Implied Volatility spike detection',
            'rv_spike': 'Realized Volatility spike detection',
            'volatility_prediction': 'Predictive volatility analysis',
            'blocker_active': 'Order blocker activation',
            'blocker_release': 'Order blocker release after cooldown',
            'exposure_limit': 'Position exposure limit enforcement',
            'loss_limit_daily': 'Daily loss limit enforcement',
            'loss_limit_total': 'Total loss limit enforcement',
            'equity_floor': 'Equity floor protection',
            'pending_budget': 'Pending order budget management',
            'config_validation': 'Configuration validation and guards',
            'order_confirmation': 'Order confirmation before placement',
            
            # Network & API
            'websocket_connected': 'WebSocket connection active',
            'websocket_disconnected': 'WebSocket disconnection',
            'websocket_reconnect': 'WebSocket reconnection',
            'api_error': 'API error handling',
            'api_timeout': 'API timeout handling',
            'rate_limiting': 'API rate limit handling',
            
            # Race Conditions & Concurrency
            'concurrent_fills': 'Multiple simultaneous fills',
            'order_throttle': 'Order placement throttling',
            'mutex_lock': 'State lock protection',
            'duplicate_order_prevention': 'Duplicate order prevention',
            
            # Error Scenarios
            'network_error': 'Network connectivity errors',
            'exchange_error': 'Exchange-side errors',
            'insufficient_margin': 'Insufficient margin errors',
            'invalid_price': 'Invalid price errors',
            'order_rejected': 'Order rejection handling',
            
            # State Transitions
            'startup': 'Bot startup initialization',
            'shutdown': 'Bot shutdown cleanup',
            'pause_resume': 'Bot pause/resume',
            'emergency_stop': 'Emergency stop procedure',
            'protective_mode_enter': 'Enter protective mode',
            'protective_mode_exit': 'Exit protective mode',
        }
    
    def analyze_all(self):
        """Run complete analysis"""
        print("🧠 COMPREHENSIVE BOT BRAIN ANALYZER")
        print("=" * 80)
        print()
        
        print("📂 Analyzing bot files...")
        for file_path in self.strategy_files:
            full_path = self.bot_root / file_path
            if full_path.exists():
                print(f"   ✓ {file_path}")
                self._analyze_file(full_path, file_path)
            else:
                print(f"   ✗ {file_path} (not found)")
        
        print()
        print("🔍 Extracting decision paths...")
        self._extract_decision_paths()
        
        print("🎯 Mapping scenarios to code...")
        self._map_scenarios()
        
        print("📊 Analyzing coverage gaps...")
        self._analyze_gaps()
        
        print()
        print(f"✅ Analysis complete!")
        print(f"   - {len(self.decision_paths)} decision points found")
        print(f"   - {len(self.functions)} functions analyzed")
        coded_count = len([s for s in self.scenarios.values() if s.coded and not s.not_applicable])
        na_count = len([s for s in self.scenarios.values() if s.not_applicable])
        applicable_total = len(self.scenarios) - na_count
        print(f"   - {coded_count} / {applicable_total} scenarios covered")
        if na_count > 0:
            print(f"   - {na_count} scenarios N/A (not needed by design)")
        print()
    
    def _analyze_file(self, file_path: Path, rel_path: str):
        """Analyze a Python file"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Extract functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self._analyze_function(node, rel_path, content)
            
            # Extract error handlers
            self._extract_error_handlers(content, rel_path)
            
            # Extract state variables
            self._extract_state_variables(content)
            
        except Exception as e:
            print(f"      Error parsing: {e}")
    
    def _analyze_function(self, func_node: ast.FunctionDef, file_path: str, content: str):
        """Analyze a function for decision logic"""
        func_name = func_node.name
        
        # Count decision points
        decisions = []
        loops = []
        calls = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.If):
                decisions.append(node)
            elif isinstance(node, (ast.While, ast.For)):
                loops.append(node)
            elif isinstance(node, ast.Call):
                calls.append(node)
        
        # Store function metadata
        self.functions[f"{file_path}:{func_name}"] = {
            'file': file_path,
            'name': func_name,
            'line': func_node.lineno,
            'decisions': len(decisions),
            'loops': len(loops),
            'calls': len(calls),
            'complexity': len(decisions) + len(loops) * 2,  # Rough complexity
            'doc': ast.get_docstring(func_node) or ""
        }
    
    def _extract_decision_paths(self):
        """Extract all decision paths from analyzed files"""
        for file_path in self.strategy_files:
            full_path = self.bot_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Find if statements with their conditions
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    # Match if statements
                    if_match = re.match(r'\s*if\s+(.+):', line)
                    if if_match:
                        condition = if_match.group(1).strip()
                        
                        # Categorize the decision
                        category = self._categorize_decision(condition, content)
                        
                        # Try to find what happens in true/false branches
                        action_true = self._find_action(lines, i, indent_level=len(line) - len(line.lstrip()))
                        action_false = "continue" if 'else:' not in '\n'.join(lines[i:i+10]) else self._find_action(lines, i, is_else=True)
                        
                        # Get function context
                        func_name = self._find_function_name(lines, i)
                        
                        self.decision_paths.append(DecisionPath(
                            file=file_path,
                            function=func_name,
                            line=i,
                            condition=condition,
                            action_if_true=action_true,
                            action_if_false=action_false,
                            category=category
                        ))
            
            except Exception as e:
                pass
    
    def _categorize_decision(self, condition: str, full_content: str) -> str:
        """Categorize a decision based on its condition"""
        condition_lower = condition.lower()
        
        if any(kw in condition_lower for kw in ['volatility', 'iv', 'rv']):
            return 'volatility'
        elif any(kw in condition_lower for kw in ['position', 'max_open', 'capacity']):
            return 'position'
        elif any(kw in condition_lower for kw in ['price', 'grid', 'level']):
            return 'grid'
        elif any(kw in condition_lower for kw in ['order', 'buy', 'sell', 'tp']):
            return 'order'
        elif any(kw in condition_lower for kw in ['error', 'exception', 'fail']):
            return 'error'
        elif any(kw in condition_lower for kw in ['margin', 'drawdown', 'capital', 'safety']):
            return 'risk'
        elif any(kw in condition_lower for kw in ['websocket', 'ws', 'connection']):
            return 'network'
        else:
            return 'other'
    
    def _find_action(self, lines: List[str], line_idx: int, indent_level: int = 0, is_else: bool = False) -> str:
        """Find the action taken in a branch"""
        start_idx = line_idx
        if is_else:
            # Find the else: line
            for i in range(line_idx, min(line_idx + 20, len(lines))):
                if 'else:' in lines[i]:
                    start_idx = i
                    break
        
        # Get next few lines
        actions = []
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            line = lines[i].strip()
            if line and not line.startswith('#') and not line.startswith('if') and not line.startswith('else'):
                # Extract meaningful actions
                if any(kw in line for kw in ['log.', 'return', 'raise', 'self.', 'place_', 'cancel_', 'process_']):
                    actions.append(line[:60])
        
        return actions[0] if actions else "unknown"
    
    def _find_function_name(self, lines: List[str], line_idx: int) -> str:
        """Find which function contains this line"""
        for i in range(line_idx - 1, max(0, line_idx - 100), -1):
            if lines[i].strip().startswith('def '):
                match = re.match(r'\s*def\s+(\w+)', lines[i])
                if match:
                    return match.group(1)
        return "unknown"
    
    def _extract_error_handlers(self, content: str, file_path: str):
        """Extract error handling patterns"""
        # Find except blocks
        except_patterns = re.findall(r'except\s+(\w+(?:\s*,\s*\w+)*)\s*(?:as\s+\w+)?:', content)
        for pattern in except_patterns:
            exceptions = [e.strip() for e in pattern.split(',')]
            for exc in exceptions:
                self.error_handlers[exc].append(file_path)
    
    def _extract_state_variables(self, content: str):
        """Extract state variables (self.variable = ...)"""
        state_vars = re.findall(r'self\.(\w+)\s*=', content)
        self.state_variables.update(state_vars)
    
    def _map_scenarios(self):
        """Map trading scenarios to actual code handlers"""
        for scenario_key, scenario_desc in self.trading_scenarios.items():
            handlers = []
            coded = False
            missing = []
            
            # Search for scenario in decision paths, functions, AND file content
            keywords = self._get_scenario_keywords(scenario_key)
            
            # Search in decision paths
            for path in self.decision_paths:
                if any(kw in path.condition.lower() or kw in path.action_if_true.lower() 
                       for kw in keywords):
                    handlers.append(f"{path.file}:{path.function} (line {path.line})")
                    coded = True
            
            # Search in function names and docstrings
            for func_key, func_data in self.functions.items():
                if any(kw in func_data['name'].lower() or kw in func_data['doc'].lower() 
                       for kw in keywords):
                    if func_key not in [h.split(' ')[0] for h in handlers]:
                        handlers.append(f"{func_key} ({func_data['doc'][:50]})")
                        coded = True
            
            # NEW: Search in file content directly for better detection
            if not coded:
                for file_path in self.strategy_files:
                    full_path = self.bot_root / file_path
                    if full_path.exists():
                        try:
                            with open(full_path, 'r') as f:
                                content = f.read().lower()
                                if any(re.search(kw, content) for kw in keywords):
                                    handlers.append(f"{file_path} (content match)")
                                    coded = True
                                    break
                        except Exception:
                            pass
            
            # Determine risk level
            risk = self._assess_risk_level(scenario_key)
            
            # Identify missing coverage
            if not coded:
                missing.append(f"No code found for {scenario_desc}")
            elif len(handlers) == 1:
                # Check if the scenario has built-in redundancy/backup
                has_backup_keywords = any(
                    keyword in ' '.join(handlers).lower() 
                    for keyword in ['backup', 'fallback', 'redundant', 'dual', 'primary.*backup', 'websocket.*rest', 'adaptive.*poll']
                )
                
                # Scenarios that inherently have backup logic even in one handler
                backup_scenarios = [
                    'fill_confirmation',  # Has WebSocket + REST polling
                    'duplicate_fill_prevention',  # Has deque-based deduplication
                    'order_throttle',  # Has time-based throttling
                    'mutex_lock',  # Has threading lock protection
                    'websocket_reconnect',  # Has exponential backoff + REST sync on reconnect
                    'websocket_disconnected',  # Has sync_on_reconnect() + adaptive REST polling
                ]
                
                if scenario_key not in backup_scenarios and not has_backup_keywords:
                    missing.append("Single point of failure - consider adding backup logic")
            
            # NOV 8: Mark scenarios as not applicable by design
            not_applicable_scenarios = {
                'stale_tp': 'TP orders are immutable by design - never modified after placement',
                'loss_limit_daily': 'Daily loss limits not needed - Guardian enforces overall position protection (more conservative)',
                'blocker_release': 'Blockers are detection-only - user must resolve root cause (enable flags, reduce margin, etc). No auto-release.',
                'pause_resume': 'Bot uses stop/start model (EXECUTE_ORDERS flag) not pause/resume. Trading controlled by safety flags.'
            }
            
            is_not_applicable = scenario_key in not_applicable_scenarios
            if is_not_applicable:
                # Override coded status and clear missing coverage
                coded = True  # Mark as "handled" (by design choice)
                missing = [f"N/A: {not_applicable_scenarios[scenario_key]}"]
            
            self.scenarios[scenario_key] = Scenario(
                name=scenario_key,
                coded=coded,
                handlers=handlers,
                risk_level=risk,
                description=scenario_desc,
                missing_coverage=missing,
                not_applicable=is_not_applicable
            )
    
    def _get_scenario_keywords(self, scenario: str) -> List[str]:
        """Get keywords to search for a scenario"""
        keyword_map = {
            'buy_order_placement': ['place_buy', 'buy_order', 'create.*buy'],
            'sell_order_placement': ['place_sell', 'sell_order', 'create.*sell'],
            'tp_order_placement': ['place_tp', 'take_profit', 'tp_order'],
            'order_cancellation': ['cancel', 'delete_order'],
            'partial_fill': ['partial', 'filled.*<', 'remaining', 'unfilled_size'],
            'full_fill': ['filled.*==', 'complete.*fill', 'fill_size.*==.*order_size'],
            'fill_confirmation': ['websocket.*fill', 'process_websocket_fill', 'robust.*fill', 'adaptive.*rest.*poll'],
            'duplicate_fill_prevention': ['dedup', 'duplicate.*fill', 'seen_fills'],
            'concurrent_fills': [
                'fill.*queue', '_process_fill_queue', '_process_single_fill',  # NOV 8: Sequential queue
                'start_processing', 'stop_processing', 'FillProcessor',  # NOV 8: Queue management
                'queue.Queue', 'sequential.*processing', 'FIFO'  # NOV 8: Worker thread
            ],
            'position_tracking': ['position', 'open_positions', 'pos_tracker'],
            'position_limit_check': ['max_open', 'capacity', 'can_open'],
            'position_reconciliation': ['reconcile', 'sync.*position'],
            'orphaned_position': ['orphan', 'missing_tp', 'no_tp'],
            'missing_tp': ['missing.*tp', 'no.*tp', 'ensure.*tp'],
            'volatility_safe': ['volatility.*safe', 'iv.*<', 'rv.*<'],
            'volatility_unsafe': ['volatility.*unsafe', 'iv.*>', 'rv.*>'],
            'circuit_breaker': ['circuit', 'breaker'],
            'drawdown_protection': ['drawdown', 'protective.*mode', 'equity_tracker'],
            'websocket_disconnected': ['disconnect', 'ws.*close', 'sync_on_reconnect', 'reconcile'],
            'websocket_reconnect': ['reconnect', 'ws.*connect', 'exponential.*backoff', '_schedule_reconnect'],
            'api_error': ['apierror', 'api.*error'],
            'order_throttle': ['throttle', 'min_order_gap', 'last_buy_order_time'],
            'mutex_lock': ['state_lock', 'with.*lock', 'acquire'],
            'duplicate_order_prevention': [
                'duplicate.*order', 'already.*pending', 'skipping.*duplicate', 'prevent.*duplicate',
                '_is_duplicate_order', '_record_order_placement', '_recent_orders',  # NOV 8: Order ID deduplication
                'THROTTLE.*Last.*BUY', 'THROTTLE.*Last.*SELL',  # NOV 8: Handler throttle checks
                'last_buy_order_time', 'last_sell_order_time', 'min_order_gap_seconds'  # NOV 8: Timestamp tracking
            ],
            # NOV 8: LONG/SHORT mode specific scenarios
            'long_buy_fill': ['handle_buy_fill', 'LongFillHandler'],
            'long_partial_buy': [
                'partial.*BUY', 'incremental.*fill', 'PARTIAL FILL SUPPORT',  # NOV 8: Partial fill handling
                'BUY incremental fill', 'fill_size.*INCREMENTAL', 'Each partial fill'  # NOV 8: Actual code patterns
            ],
            'long_tp_placement': [
                'safe_place_tp', 'compute_tp_price',  # NOV 8: TP calculation & placement
                'TP placed.*lots', 'TP PLACEMENT',  # NOV 8: Success/failure logs
                'place_tp.*position', 'tp_success'  # NOV 8: Variables
            ],
            'long_tp_fill': ['handle_tp_fill', 'TP.*FILLED.*LONG'],
            'long_next_grid': [
                'get_next_buy_price', 'compute_next_level_down',  # NOV 8: Next grid calculation
                'Place next grid BUY', 'Placing next.*BUY',  # NOV 8: Actual placement
                'next_buy_price', 'place_buy_order.*next'  # NOV 8: Variables & calls
            ],
            'short_sell_fill': ['handle_sell_fill', 'ShortFillHandler'],
            'short_partial_sell': [
                'partial.*SELL', 'incremental.*fill', 'PARTIAL FILL SUPPORT',  # NOV 8: Partial fill handling
                'SELL incremental fill', 'fill_size.*INCREMENTAL', 'Each partial fill'  # NOV 8: Actual code patterns
            ],
            'short_tp_placement': [
                'safe_place_tp', 'compute_tp_price_short',  # NOV 8: TP calculation & placement
                'TP.*BUY.*placed', 'TP PLACEMENT.*SHORT',  # NOV 8: Success/failure logs
                'place_tp.*position', 'tp_success'  # NOV 8: Variables
            ],
            'short_tp_fill': ['handle_tp_fill_short', 'TP.*FILLED.*SHORT'],
            'short_next_grid': [
                'compute_next_level_up',  # NOV 8: Next grid calculation
                'Place next.*SELL', 'Placing next.*SELL',  # NOV 8: Actual placement
                'next_price.*SELL', 'place_sell_order.*next'  # NOV 8: Variables & calls
            ],
            # NOV 8: Price gap handling (market jumped)
            'price_gap': [
                'find_nearest_grid_below', 'find_nearest_grid_above',  # Gap recovery functions
                'current_price.*<.*ref', 'current_price.*>.*ref',  # Market vs REF comparison
                'Market.*below.*REF', 'Market.*above.*REF',  # Log messages
                'nearest grid level.*market'  # Adjustment logic
            ],
            # NOV 8: Advanced Volatility & Risk Detection
            'iv_spike': [
                'iv_threshold', 'implied.*volatility.*>', 'IV.*spike', 'iv.*unsafe',  # Original patterns
                '_check_safety', 'iv.*>.*max_iv', 'IV too high',  # NOV 8: Actual detection code
                'current_iv', 'VOLATILITY_MAX_IV'  # NOV 8: Tracking and config
            ],
            'rv_spike': [
                'rv_threshold', 'realized.*volatility.*>', 'RV.*spike', 'rv.*unsafe',  # Original patterns
                '_check_safety', 'rv.*>.*max_rv', 'RV too high',  # NOV 8: Actual detection code
                'current_rv', 'VOLATILITY_MAX_RV'  # NOV 8: Tracking and config
            ],
            'volatility_prediction': ['predict', 'forecast', 'PredictiveEngine', 'volatility.*trend'],
            'blocker_active': ['BlockerTracker', 'activate_blocker', 'orders.*blocked'],
            'blocker_release': ['release_blocker', 'blocker.*cooldown', 'blocker.*expired'],
            'exposure_limit': [
                'ExposureLimiter', 'max_exposure', 'exposure.*exceeded',  # Original
                'can_place_order', 'max_tranches_per_minute', 'max_notional_per_minute',  # NOV 8: Actual enforcement
                'Tranche rate limit', 'Notional rate limit'  # NOV 8: Limit messages
            ],
            'loss_limit_daily': ['daily.*loss', 'LossLimits', 'loss_today'],
            'loss_limit_total': [
                'LossLimits', 'max_total_loss', 'MAX_ACCOUNT_LOSS',  # NOV 8: Total loss enforcement
                'check_loss_threshold', 'loss.*exceeded', 'LOSS LIMIT BREACHED',  # Guardian enforcement
                'GUARDIAN_MAX_ACCOUNT_LOSS_INR', 'emergency_triggered'  # Emergency stop
            ],
            'equity_floor': ['EquityFloor', 'minimum_equity', 'equity.*below.*floor'],
            'pending_budget': ['PendingBudget', 'reserve_budget', 'budget.*exceeded'],
            'config_validation': [
                'ConfigGuard', 'validate_config', 'invalid.*config',  # Original patterns
                'check_config_changes', '_detect_risky_changes', 'GUARDED_KEYS',  # NOV 8: Actual validation
                'TWO_MAN_RULE', 'risky_changes', 'check_confirmation'  # NOV 8: Risky change detection
            ],
            'order_confirmation': ['OrderConfirmationGuard', 'confirm.*order', 'confirmation.*required'],
            # NOV 8: Protective mode (drawdown protection)
            'protective_mode_enter': [
                'protective.*mode.*active', 'enter.*protective', 'PROTECTIVE MODE ACTIVATED',
                'drawdown_protective_mode', '_protective_mode_flag.*touch'
            ],
            'protective_mode_exit': [
                'exit.*protective', 'protective.*mode.*False', 'unlink.*protective',
                'protective.*mode.*deactivated'
            ],
            # NOV 8: Circuit breaker (network/exchange errors)
            'circuit_breaker_halfopen': [
                '_transition_to_half_open', 'CircuitState.HALF_OPEN', 'testing recovery',  # NOV 8: Half-open state
                'half_open_max_calls', 'timeout expired'  # NOV 8: Recovery testing
            ],
            'circuit_breaker_open': ['CircuitState.OPEN', 'circuit.*open', 'too many.*failures'],
            'api_timeout': [
                'timeout', 'TimeoutError', 'request.*timeout',  # Generic timeouts
                'IGNORED_ERRORS', 'VERIFY_TIMEOUT', 'deadline',  # NOV 8: Timeout handling
                'failure_threshold', 'Circuit breaker'  # NOV 8: Circuit breaker protection
            ],
            'network_error': [
                'NetworkError', 'ConnectionError', 'network.*failed',  # Generic network errors
                'IGNORED_ERRORS', 'CircuitState.OPEN', 'API FAILED',  # NOV 8: Circuit breaker handles these
                'failure_count', '_on_failure'  # NOV 8: Error tracking
            ],
            'exchange_error': [
                'ExchangeError', 'API.*error', 'exchange.*error',  # Generic exchange errors
                'IGNORED_ERRORS', 'insufficient_margin', 'invalid_price',  # NOV 8: Circuit breaker expected errors
                'CircuitBreakerOpen', 'order_not_found'  # NOV 8: Circuit breaker blocks on errors
            ],
            'pause_resume': ['pause', 'resume', 'is_paused'],
        }
        
        return keyword_map.get(scenario, [scenario.replace('_', '.*')])
    
    def _assess_risk_level(self, scenario: str) -> str:
        """Assess risk level if scenario is not handled"""
        critical = ['duplicate_order', 'margin', 'drawdown', 'emergency', 'protective_mode']
        high = ['fill', 'position', 'order_placement', 'throttle', 'mutex']
        medium = ['volatility', 'grid', 'reconciliation', 'websocket']
        
        for kw in critical:
            if kw in scenario:
                return 'CRITICAL'
        for kw in high:
            if kw in scenario:
                return 'HIGH'
        for kw in medium:
            if kw in scenario:
                return 'MEDIUM'
        return 'LOW'
    
    def _analyze_gaps(self):
        """Identify coverage gaps"""
        # Add gap analysis to uncovered scenarios
        uncovered = [s for s in self.scenarios.values() if not s.coded]
        
        for scenario in uncovered:
            if scenario.risk_level in ['CRITICAL', 'HIGH']:
                scenario.missing_coverage.append(
                    f"⚠️ {scenario.risk_level} PRIORITY: Add handler immediately"
                )
    
    def generate_html_report(self, output_path: Path):
        """Generate comprehensive HTML report"""
        
        # Calculate statistics
        total_scenarios = len(self.scenarios)
        covered_scenarios = len([s for s in self.scenarios.values() if s.coded])
        uncovered = [s for s in self.scenarios.values() if not s.coded and not s.not_applicable]
        not_applicable = [s for s in self.scenarios.values() if s.not_applicable]
        critical_gaps = [s for s in uncovered if s.risk_level == 'CRITICAL']
        high_gaps = [s for s in uncovered if s.risk_level == 'HIGH']
        
        # Exclude N/A from total when calculating coverage
        applicable_total = total_scenarios - len(not_applicable)
        coverage_pct = (covered_scenarios / applicable_total * 100) if applicable_total > 0 else 0
        
        # Group scenarios by category
        categories = defaultdict(list)
        for scenario in self.scenarios.values():
            cat = scenario.name.split('_')[0]
            categories[cat].append(scenario)
        
        # Group decisions by category
        decision_stats = defaultdict(int)
        for path in self.decision_paths:
            decision_stats[path.category] += 1
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bot Brain Comprehensive Analysis</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #000000;
            padding: 20px;
            color: #e5e7eb;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: #1a1a1a;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            overflow: hidden;
            border: 1px solid #333;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #0a0a0a;
        }}
        
        .stat-card {{
            background: #1a1a1a;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
            text-align: center;
            border: 1px solid #333;
        }}
        
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .stat-card .label {{
            color: #9ca3af;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .value.good {{ color: #10b981; }}
        .value.warn {{ color: #f59e0b; }}
        .value.danger {{ color: #ef4444; }}
        
        .section {{
            padding: 30px;
            border-bottom: 1px solid #333;
            background: #1a1a1a;
        }}
        
        .section h2 {{
            color: #60a5fa;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-left: 5px solid #3b82f6;
            padding-left: 15px;
        }}
        
        .scenario-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .scenario-card {{
            border: 2px solid #333;
            border-radius: 8px;
            padding: 15px;
            background: #0a0a0a;
        }}
        
        .scenario-card.coded {{
            border-color: #10b981;
            background: #064e3b;
        }}
        
        .scenario-card.missing {{
            border-color: #ef4444;
            background: #7f1d1d;
        }}
        
        .scenario-card.missing.critical {{
            border-color: #dc2626;
            background: #991b1b;
            border-width: 3px;
        }}
        
        .scenario-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .scenario-name {{
            font-weight: bold;
            font-size: 1.1em;
            color: #f3f4f6;
        }}
        
        .badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }}
        
        .badge.coded {{ background: #10b981; color: white; }}
        .badge.missing {{ background: #ef4444; color: white; }}
        .badge.critical {{ background: #dc2626; color: white; }}
        .badge.high {{ background: #f59e0b; color: white; }}
        .badge.medium {{ background: #3b82f6; color: white; }}
        .badge.low {{ background: #6b7280; color: white; }}
        
        .handlers {{
            margin-top: 10px;
            padding: 10px;
            background: #1a1a1a;
            border-radius: 5px;
            font-size: 0.9em;
            border: 1px solid #333;
        }}
        
        .handlers li {{
            margin: 5px 0;
            padding-left: 20px;
            position: relative;
            color: #d1d5db;
        }}
        
        .handlers li:before {{
            content: "→";
            position: absolute;
            left: 0;
            color: #60a5fa;
        }}
        
        .missing-coverage {{
            margin-top: 10px;
            padding: 10px;
            background: #7f1d1d;
            border-left: 3px solid #ef4444;
            font-size: 0.9em;
            color: #fca5a5;
        }}
        
        .decision-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        .decision-table th {{
            background: #1e3a8a;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        
        .decision-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #333;
            color: #d1d5db;
        }}
        
        .decision-table tr:hover {{
            background: #262626;
        }}
        
        .category-tag {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        .cat-order {{ background: #dbeafe; color: #1e40af; }}
        .cat-position {{ background: #d1fae5; color: #065f46; }}
        .cat-volatility {{ background: #fef3c7; color: #92400e; }}
        .cat-risk {{ background: #fee2e2; color: #991b1b; }}
        .cat-network {{ background: #e0e7ff; color: #3730a3; }}
        .cat-error {{ background: #fecaca; color: #7f1d1d; }}
        .cat-grid {{ background: #ddd6fe; color: #5b21b6; }}
        .cat-other {{ background: #e5e7eb; color: #374151; }}
        
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #262626;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
            border: 1px solid #333;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #10b981 0%, #059669 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 1s ease;
        }}
        
        .alert {{
            padding: 15px 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 5px solid;
        }}
        
        .alert.danger {{
            background: #7f1d1d;
            border-color: #dc2626;
            color: #fca5a5;
        }}
        
        .alert.warning {{
            background: #78350f;
            border-color: #f59e0b;
            color: #fcd34d;
        }}
        
        .alert.success {{
            background: #064e3b;
            border-color: #10b981;
            color: #6ee7b7;
        }}
        
        .timestamp {{
            text-align: center;
            padding: 20px;
            color: #6b7280;
            font-size: 0.9em;
            background: #0a0a0a;
            border-top: 1px solid #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Bot Brain Comprehensive Analysis</h1>
            <p>Complete Decision Path Mapping & Scenario Coverage Report</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Coverage</div>
                <div class="value {'good' if coverage_pct >= 80 else 'warn' if coverage_pct >= 60 else 'danger'}">{coverage_pct:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Scenarios Coded</div>
                <div class="value good">{covered_scenarios}/{total_scenarios}</div>
            </div>
            <div class="stat-card">
                <div class="label">Critical Gaps</div>
                <div class="value {'danger' if len(critical_gaps) > 0 else 'good'}">{len(critical_gaps)}</div>
            </div>
            <div class="stat-card">
                <div class="label">High Priority Gaps</div>
                <div class="value {'warn' if len(high_gaps) > 0 else 'good'}">{len(high_gaps)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Decision Points</div>
                <div class="value">{len(self.decision_paths)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Functions Analyzed</div>
                <div class="value">{len(self.functions)}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Overall Coverage</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {coverage_pct}%">
                    {covered_scenarios} / {total_scenarios} Scenarios
                </div>
            </div>
            
            {f'''<div class="alert danger">
                <strong>⚠️ CRITICAL GAPS FOUND!</strong><br>
                {len(critical_gaps)} critical scenarios are not covered. These should be implemented immediately.
            </div>''' if critical_gaps else ''}
            
            {f'''<div class="alert warning">
                <strong>⚠️ HIGH PRIORITY GAPS</strong><br>
                {len(high_gaps)} high-priority scenarios need attention.
            </div>''' if high_gaps else ''}
            
            {f'''<div class="alert success">
                <strong>✅ EXCELLENT COVERAGE!</strong><br>
                Bot has comprehensive scenario coverage. Continue monitoring for new edge cases.
            </div>''' if coverage_pct >= 90 else ''}
        </div>
        
        <div class="section">
            <h2>🎯 Scenario Coverage Matrix</h2>
            <p style="margin-bottom: 20px;">All possible trading scenarios and their implementation status:</p>
            
            <div class="scenario-grid">
"""
        
        # Add all scenarios
        for scenario in sorted(self.scenarios.values(), key=lambda s: (not s.coded, s.risk_level != 'CRITICAL', s.risk_level != 'HIGH', s.name)):
            card_class = 'scenario-card coded' if scenario.coded else f'scenario-card missing {scenario.risk_level.lower()}'
            
            html += f"""
                <div class="{card_class}">
                    <div class="scenario-header">
                        <div class="scenario-name">{scenario.name.replace('_', ' ').title()}</div>
                        <span class="badge {'coded' if scenario.coded else 'missing'}">{('✅ CODED' if scenario.coded else '❌ MISSING')}</span>
                    </div>
                    <div style="margin: 10px 0; color: #666; font-size: 0.9em;">{scenario.description}</div>
                    <div><span class="badge {scenario.risk_level.lower()}">{scenario.risk_level}</span></div>
                    
                    {f'''<div class="handlers">
                        <strong>Handlers:</strong>
                        <ul>
                            {''.join(f'<li>{h}</li>' for h in scenario.handlers[:5])}
                            {f'<li>... and {len(scenario.handlers) - 5} more</li>' if len(scenario.handlers) > 5 else ''}
                        </ul>
                    </div>''' if scenario.coded and scenario.handlers else ''}
                    
                    {f'''<div class="missing-coverage">
                        <strong>⚠️ Missing:</strong>
                        <ul>
                            {''.join(f'<li>{m}</li>' for m in scenario.missing_coverage)}
                        </ul>
                    </div>''' if scenario.missing_coverage else ''}
                </div>
"""
        
        html += """
            </div>
        </div>
        
        <div class="section">
            <h2>🔀 Decision Points by Category</h2>
            <table class="decision-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Decision Points</th>
                        <th>Coverage</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for cat, count in sorted(decision_stats.items(), key=lambda x: x[1], reverse=True):
            html += f"""
                    <tr>
                        <td><span class="category-tag cat-{cat}">{cat.upper()}</span></td>
                        <td>{count} decisions</td>
                        <td>{'✅ Well covered' if count > 5 else '⚠️ Limited coverage' if count > 2 else '❌ Needs more'}</td>
                    </tr>
"""
        
        html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>📋 Top Complex Functions</h2>
            <p style="margin-bottom: 15px;">Functions with highest decision complexity (need most attention):</p>
            <table class="decision-table">
                <thead>
                    <tr>
                        <th>Function</th>
                        <th>File</th>
                        <th>Decisions</th>
                        <th>Loops</th>
                        <th>Complexity</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        # Sort functions by complexity
        top_functions = sorted(self.functions.values(), key=lambda f: f['complexity'], reverse=True)[:15]
        
        for func in top_functions:
            html += f"""
                    <tr>
                        <td><strong>{func['name']}</strong></td>
                        <td>{func['file'].split('/')[-1]}</td>
                        <td>{func['decisions']}</td>
                        <td>{func['loops']}</td>
                        <td><strong>{func['complexity']}</strong></td>
                    </tr>
"""
        
        html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🛡️ Error Handling Coverage</h2>
            <p>Exception types being handled:</p>
            <div style="margin-top: 15px;">
"""
        
        for exc_type, files in sorted(self.error_handlers.items()):
            html += f"""
                <div style="margin: 10px 0; padding: 10px; background: #f9fafb; border-radius: 5px;">
                    <strong>{exc_type}</strong> - handled in {len(files)} file(s)
                    <div style="font-size: 0.9em; color: #666; margin-top: 5px;">
                        {', '.join(set(f.split('/')[-1] for f in files))}
                    </div>
                </div>
"""
        
        html += """
            </div>
        </div>
        
        <div class="section">
            <h2>💡 Recommendations</h2>
            <div style="line-height: 1.8;">
"""
        
        # Generate recommendations
        if critical_gaps:
            html += f"""
                <div class="alert danger">
                    <strong>🚨 CRITICAL: Implement these scenarios immediately:</strong>
                    <ul style="margin-top: 10px;">
                        {''.join(f'<li>{s.name.replace("_", " ").title()} - {s.description}</li>' for s in critical_gaps)}
                    </ul>
                </div>
"""
        
        if high_gaps:
            html += f"""
                <div class="alert warning">
                    <strong>⚠️ HIGH PRIORITY: Add these scenarios soon:</strong>
                    <ul style="margin-top: 10px;">
                        {''.join(f'<li>{s.name.replace("_", " ").title()} - {s.description}</li>' for s in high_gaps[:5])}
                    </ul>
                </div>
"""
        
        if coverage_pct >= 90:
            html += """
                <div class="alert success">
                    <strong>✅ EXCELLENT:</strong> Your bot has comprehensive scenario coverage!<br>
                    Continue monitoring for new edge cases as you discover them.
                </div>
"""
        
        # Add specific trading recommendations
        html += """
                <div class="alert warning">
                    <strong>📌 GENERAL RECOMMENDATIONS:</strong>
                    <ul style="margin-top: 10px;">
                        <li><strong>Add logging:</strong> Every decision point should have log.info() for debugging</li>
                        <li><strong>Test edge cases:</strong> Use chaos testing for network failures, API errors</li>
                        <li><strong>Add metrics:</strong> Track how often each decision path is taken</li>
                        <li><strong>Document assumptions:</strong> Add comments explaining why decisions are made</li>
                        <li><strong>Regular reviews:</strong> Re-run this analysis monthly to catch new scenarios</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div class="timestamp">
            Generated: """ + str(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + """<br>
            Analysis Tool: Comprehensive Bot Brain Analyzer v1.0
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        print(f"\n✅ HTML report generated: {output_path}")
    
    def generate_checklist(self, output_path: Path):
        """Generate a simple text checklist for non-coders"""
        
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("BOT DECISION LOGIC CHECKLIST\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("This checklist shows WHAT your bot can handle vs. what it CAN'T.\n")
            f.write("Use this to identify gaps and add missing scenarios.\n\n")
            
            # Group by category
            categories = {
                'Order Execution': [],
                'Position Management': [],
                'Price & Grid': [],
                'Volatility & Risk': [],
                'Network & API': [],
                'Race Conditions': [],
                'Errors': [],
                'State Transitions': []
            }
            
            for scenario in self.scenarios.values():
                if 'order' in scenario.name or 'buy' in scenario.name or 'sell' in scenario.name or 'tp' in scenario.name:
                    cat = 'Order Execution'
                elif 'position' in scenario.name:
                    cat = 'Position Management'
                elif 'grid' in scenario.name or 'price' in scenario.name:
                    cat = 'Price & Grid'
                elif 'volatility' in scenario.name or 'circuit' in scenario.name or 'drawdown' in scenario.name or 'margin' in scenario.name:
                    cat = 'Volatility & Risk'
                elif 'websocket' in scenario.name or 'api' in scenario.name or 'network' in scenario.name:
                    cat = 'Network & API'
                elif 'concurrent' in scenario.name or 'throttle' in scenario.name or 'mutex' in scenario.name or 'duplicate' in scenario.name:
                    cat = 'Race Conditions'
                elif 'error' in scenario.name or 'rejected' in scenario.name:
                    cat = 'Errors'
                else:
                    cat = 'State Transitions'
                
                categories[cat].append(scenario)
            
            for cat_name, scenarios in categories.items():
                if not scenarios:
                    continue
                
                f.write(f"\n{'=' * 80}\n")
                f.write(f"{cat_name.upper()}\n")
                f.write(f"{'=' * 80}\n\n")
                
                for s in sorted(scenarios, key=lambda x: (not x.coded, x.risk_level)):
                    # NOV 8: Show N/A status for scenarios not applicable by design
                    if s.not_applicable:
                        status = "⚪ N/A"
                    else:
                        status = "✅ CODED" if s.coded else "❌ MISSING"
                    risk = f"[{s.risk_level}]"
                    
                    f.write(f"{status} {risk:12} {s.description}\n")
                    
                    if s.not_applicable and s.missing_coverage:
                        # Show why it's N/A
                        f.write(f"    ℹ️  {s.missing_coverage[0]}\n")
                    elif s.coded and s.handlers:
                        f.write(f"    📍 Handled in: {s.handlers[0].split(':')[0]}\n")
                    elif s.missing_coverage:
                        f.write(f"    ⚠️  {s.missing_coverage[0]}\n")
                    
                    f.write("\n")
        
        print(f"✅ Text checklist generated: {output_path}")


def main():
    """Main entry point"""
    bot_root = Path(__file__).parent
    
    # Create analyzer
    analyzer = BotBrainAnalyzer(bot_root)
    
    # Run analysis
    analyzer.analyze_all()
    
    # Generate reports
    output_dir = bot_root / 'analysis'
    output_dir.mkdir(exist_ok=True)
    
    html_path = output_dir / 'bot_brain_comprehensive_report.html'
    checklist_path = output_dir / 'bot_logic_checklist.txt'
    
    analyzer.generate_html_report(html_path)
    analyzer.generate_checklist(checklist_path)
    
    print()
    print("=" * 80)
    print("📊 REPORTS GENERATED:")
    print("=" * 80)
    print(f"   1. Visual Report: {html_path}")
    print(f"   2. Text Checklist: {checklist_path}")
    print()
    print("💡 TIP: Open the HTML report in your browser to see:")
    print("   - Complete scenario coverage matrix")
    print("   - What's coded vs. what's missing")
    print("   - Risk levels for each gap")
    print("   - Specific files/functions handling each scenario")
    print()
    print("Use the checklist to identify scenarios to code in advance!")
    print("=" * 80)


if __name__ == '__main__':
    main()
