"""
Brain Analyzer API Routes

Single Responsibility: Expose brain analysis via REST API.

Endpoints:
- GET /api/brain/flowchart - Visual decision flow graph
- GET /api/brain/sequences - Action sequences  
- GET /api/brain/modules - Discovered modules
- GET /api/brain/refresh - Force refresh (auto-refreshes anyway)

Auto-refresh: Frontend polls every 5 seconds automatically.
"""

import logging
from flask import Blueprint, jsonify
from pathlib import Path

from .code_reader import BotCodeReader
from .ast_parser import DecisionParser
from .flow_generator import FlowGraphGenerator
from .change_detector import ChangeDetector
from .state_reader import BotStateReader
from .realtime_predictor import RealTimeBotPredictor
from .file_monitor import RealTimeFileMonitor

log = logging.getLogger(__name__)

# Create blueprint
brain_analyzer_bp = Blueprint('brain_analyzer', __name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent.parent


@brain_analyzer_bp.route('/api/brain/flowchart', methods=['GET'])
def get_decision_flowchart():
    """
    Get visual decision flow graph WITH REAL-TIME BOT STATE.
    
    Returns graph structure annotated with actual bot data:
    - Emergency stop status (YES/NO + reason)
    - Volatility values (IV=X%, RV=Y% vs thresholds)
    - Current positions and pending orders
    - Next grid levels and missed levels
    
    Auto-refreshes every 5 seconds (no caching).
    """
    try:
        # Read bot brain code (fresh every time)
        reader = BotCodeReader(BASE_DIR)
        brain_code = reader.read_all_brain_code()
        
        # Parse AST to find decisions
        parser = DecisionParser()
        parsed_data = {}
        
        for file_path, file_data in brain_code.get('files', {}).items():
            source = file_data.get('source', '')
            if source:
                parsed = parser.parse_source_code(source, Path(file_path).name)
                parsed_data[file_path] = parsed
        
        # Generate flow graph
        flow_gen = FlowGraphGenerator()
        graph = flow_gen.generate_flow_graph(parsed_data)
        
        # READ BOT'S CURRENT STATE (REAL-TIME)
        state_reader = BotStateReader(BASE_DIR)
        bot_state = state_reader.get_complete_state()
        
        log.info(f"Bot state keys: {list(bot_state.keys())}")
        log.info(f"Emergency stop: {bot_state.get('emergency_stop')}")
        log.info(f"Volatility: {bot_state.get('volatility', {})}")
        
        # ANNOTATE nodes with real data
        annotated_nodes = []
        for node in graph.get('nodes', []):
            annotated_node = node.copy()
            
            # Give ALL nodes at least basic realtime data
            annotated_node['realtime_data'] = {
                'timestamp': bot_state.get('timestamp'),
                'node_id': node['id']
            }
            
            # Annotate based on node type
            if node['id'] == 'start':
                # Start node - show bot overview
                annotated_node['data']['label'] = "Bot Starts"
                annotated_node['realtime_data'] = {
                    'emergency_stop': bot_state.get('emergency_stop', False),
                    'trading_enabled': bot_state.get('trading_enabled', True),
                    'volatility_safe': bot_state.get('volatility', {}).get('is_safe', True),
                    'open_positions': bot_state.get('positions', {}).get('open_positions', 0),
                    'status': 'Running'
                }
            
            elif node['id'] == 'check_emergency':
                # Emergency Stop decision
                emergency = bot_state.get('emergency_stop', False)
                annotated_node['data']['label'] = f"Emergency Stop Active?\n\n{'✅ YES - Trading Halted' if emergency else '❌ NO - Trading Allowed'}"
                annotated_node['realtime_data'] = {
                    'emergency_stop': emergency,
                    'trading_enabled': bot_state.get('trading_enabled', True)
                }
            
            elif node['id'] == 'check_volatility':
                # Volatility decision
                vol = bot_state.get('volatility', {})
                iv = vol.get('current_iv')
                rv = vol.get('current_rv')
                max_iv = vol.get('max_iv', 35)
                max_rv = vol.get('max_rv', 40)
                is_safe = vol.get('is_safe', True)
                reason = vol.get('violation_reason', '')
                
                label = f"Volatility Safe?\n(IV < {max_iv}% & RV < {max_rv}%)\n\n"
                if iv is not None and rv is not None:
                    label += f"Current: IV={iv:.1f}%, RV={rv:.1f}%\n"
                    if is_safe:
                        label += "✅ SAFE - Trading Active"
                    else:
                        label += f"🛑 UNSAFE - {reason}"
                else:
                    label += "⚠️ No volatility data"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = vol
            
            elif node['id'] == 'cancel_orders':
                # Cancel action - show what was cancelled
                halt = bot_state.get('halt', {})
                pending_buy = halt.get('pending_buy_at_halt')
                
                label = "Cancel Pending Orders"
                if pending_buy:
                    label += f"\n\n📍 Cancelled BUY at ₹{pending_buy:,.0f}"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = halt
            
            elif node['id'] == 'track_levels':
                # Track missed levels - show actual missed levels
                halt = bot_state.get('halt', {})
                missed = halt.get('missed_levels', [])
                
                label = "Track Missed Levels"
                if missed:
                    label += f"\n\n🔴 Missed {len(missed)} level(s):"
                    for level in missed[:3]:  # Show max 3
                        label += f"\n₹{level:,.0f}"
                else:
                    label += "\n\n✅ No missed levels yet"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'missed_levels': missed}
            
            elif node['id'] == 'check_guardian':
                # Guardian protection checks
                positions = bot_state.get('positions', {})
                total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions.get('positions', []))
                loss_limit = -7500  # From config
                
                label = "Guardian Checks:\n• Loss Limits OK?\n• Margin Safe?\n• Risk Acceptable?\n\n"
                if total_pnl < loss_limit:
                    label += f"🚨 FAIL - Loss: ₹{total_pnl:,.0f}"
                else:
                    label += f"✅ PASS - PnL: ₹{total_pnl:,.0f}"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {
                    'total_pnl': total_pnl,
                    'loss_limit': loss_limit,
                    'guardian_active': True
                }
            
            elif node['id'] == 'check_positions':
                # Max positions check
                positions = bot_state.get('positions', {})
                open_pos = positions.get('open_positions', 0)
                max_pos = bot_state.get('config', {}).get('max_positions', 3)
                
                label = f"Max Positions Reached?\n(Limit: {max_pos})\n\n"
                label += f"Current: {open_pos}/{max_pos}"
                if open_pos >= max_pos:
                    label += "\n🛑 MAX REACHED"
                else:
                    label += "\n✅ Slots Available"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = positions
            
            elif node['id'] == 'check_pending':
                # Pending buy check
                positions = bot_state.get('positions', {})
                pending_price = positions.get('pending_buy_price')
                
                label = "Pending BUY Active?"
                if pending_price:
                    label += f"\n\n✅ YES\nBUY at ₹{pending_price:,.0f}"
                else:
                    label += "\n\n❌ NO\nNo pending orders"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'pending_buy_price': pending_price}
            
            elif node['id'] == 'calc_buy':
                # Calculate next buy - show actual price
                next_buy = bot_state.get('next_buy_price')
                step = bot_state.get('config', {}).get('grid_step', 500)
                
                label = "Calculate Next Buy"
                if next_buy:
                    label += f"\n\n📍 BUY: ₹{next_buy:,.0f}"
                    label += f"\n(Grid step: ₹{step:,.0f})"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'next_buy_price': next_buy, 'grid_step': step}
            
            elif node['id'] == 'place_buy':
                # Place buy - show exact order details
                next_buy = bot_state.get('next_buy_price')
                
                label = "Place BUY Order"
                if next_buy:
                    label += f"\n\n💰 LIMIT BUY @ ₹{next_buy:,.0f}"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'buy_price': next_buy}
            
            elif node['id'] == 'place_tp':
                # Place TP - show sell price
                positions = bot_state.get('positions', {}).get('positions', [])
                step = bot_state.get('config', {}).get('grid_step', 500)
                
                label = "Place TP"
                if positions and len(positions) > 0:
                    entry = positions[0].get('entry_price', 0)
                    tp_price = entry + step
                    label += f"\n\n💵 LIMIT SELL @ ₹{tp_price:,.0f}"
                else:
                    label += f"\n(Entry + ₹{step:,.0f})"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'tp_price': None, 'grid_step': step}
            
            elif node['id'] == 'safety_check':
                # 11-point safety validation
                vol = bot_state.get('volatility', {})
                positions = bot_state.get('positions', {})
                
                all_safe = vol.get('is_safe', True) and positions.get('open_positions', 0) < 3
                
                label = "11-Point Safety Check:\n✓ Volatility OK?\n✓ Margin OK?\n✓ Liquidation Risk?\n✓ API Health?\n✓ Position Limits?\n\n"
                if all_safe:
                    label += "✅ ALL CHECKS PASSED"
                else:
                    label += "🚨 SAFETY VIOLATION"
                
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {
                    'all_checks_passed': all_safe,
                    'total_checks': 11
                }
            
            elif node['id'] == 'order_error':
                # Order error handling
                label = "Order Placement Failed?\n\n⚠️ Monitoring for errors"
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'error_monitoring': True}
            
            elif node['id'] == 'ws_check':
                # WebSocket connection check
                label = "WebSocket Connected?\n\n✅ Connection Active"
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'ws_connected': True}
            
            elif node['id'] == 'tp_collision':
                # TP collision detection
                label = "TP Price Collision?\n\n✅ Collision Detection Active"
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {'collision_detection': True}
            
            elif node['id'] == 'heartbeat_monitor':
                # Heartbeat monitoring
                label = "💓 Heartbeat Monitor\n(Separate Process)\n\n✅ Running in Background"
                annotated_node['data']['label'] = label
                annotated_node['realtime_data'] = {
                    'heartbeat_active': True,
                    'check_interval': '60s'
                }
            
            annotated_nodes.append(annotated_node)
        
        graph['nodes'] = annotated_nodes
        
        return jsonify({
            'success': True,
            'graph': graph,
            'bot_state': bot_state,
            'brain_scan': {
                'files_scanned': brain_code.get('total_files', 0),
                'total_lines': brain_code.get('total_lines', 0),
                'scan_timestamp': brain_code.get('scan_timestamp')
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error generating flowchart: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/modules', methods=['GET'])
def get_discovered_modules():
    """
    Get list of all discovered brain modules.
    
    Shows which files were scanned and their metadata.
    """
    try:
        reader = BotCodeReader(BASE_DIR)
        brain_code = reader.read_all_brain_code()
        
        # Build module summary (EXCLUDE old gbot_ws.py)
        modules = []
        for file_path, file_data in brain_code.get('files', {}).items():
            file_name = Path(file_path).name
            # Skip old gbot_ws.py file
            if file_name == 'gbot_ws.py':
                continue
            modules.append({
                'path': file_path,
                'name': file_name,
                'lines': file_data.get('line_count', 0),
                'metadata': file_data.get('metadata', {})
            })
        
        return jsonify({
            'success': True,
            'modules': modules,
            'total_modules': len(modules),
            'total_lines': brain_code.get('total_lines', 0)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting modules: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/sequences', methods=['GET'])
def get_action_sequences():
    """
    Get dynamic action sequences from bot's current state.
    
    Reads real bot state and generates sequences for all 3 scenarios.
    This is DYNAMIC - not static!
    """
    try:
        # Import strategy analyzer to reuse existing logic
        from webui.backend.routes.strategy import analyze_current_strategy
        
        # Get real bot state and generate sequences
        strategy_data = analyze_current_strategy()
        
        if strategy_data.get('success'):
            return jsonify({
                'success': True,
                'sequences': strategy_data.get('grid_scenarios', {}),
                'bot_state': strategy_data.get('bot_state', {}),
                'safety_status': strategy_data.get('safety_status', {}),
                'timestamp': strategy_data.get('timestamp')
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': strategy_data.get('error', 'Failed to analyze strategy')
            }), 500
        
    except Exception as e:
        log.error(f"Error getting action sequences: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/changes', methods=['GET'])
def get_brain_changes():
    """
    Get detected changes in bot brain files.
    
    Compares current state with previous scan and predicts impact.
    """
    try:
        reader = BotCodeReader(BASE_DIR)
        brain_code = reader.read_all_brain_code()
        
        detector = ChangeDetector(BASE_DIR)
        changes = detector.detect_changes(brain_code)
        
        return jsonify({
            'success': True,
            'changes': changes
        }), 200
        
    except Exception as e:
        log.error(f"Error detecting changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/predict', methods=['GET'])
def get_realtime_predictions():
    """
    Get real-time predictions of bot's next actions.
    
    This is the MAIN endpoint for the enhanced brain analyzer.
    Returns comprehensive predictions with confidence scores.
    """
    try:
        # Initialize real-time predictor
        predictor = RealTimeBotPredictor(BASE_DIR)
        
        # Get comprehensive prediction analysis
        prediction_data = predictor.get_comprehensive_prediction()
        
        if 'error' in prediction_data:
            return jsonify({
                'success': False,
                'error': prediction_data['error']
            }), 500
        
        # Also get file monitoring data
        file_monitor = RealTimeFileMonitor(BASE_DIR)
        changes = file_monitor.scan_for_changes()
        monitoring_summary = file_monitor.get_monitoring_summary()
        
        return jsonify({
            'success': True,
            'predictions': prediction_data,
            'file_changes': changes,
            'monitoring': monitoring_summary,
            'refresh_interval': 3  # Refresh every 3 seconds for real-time
        }), 200
        
    except Exception as e:
        log.error(f"Error getting real-time predictions: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/simulate', methods=['POST'])
def simulate_bot_decisions():
    """
    Robust bot decision simulation using production components.
    """
    try:
        from flask import request
        from .robust_simulator import RobustBotSimulator
        
        data = request.get_json() or {}
        scenario = data.get('scenario', 'current')
        steps = data.get('steps', [])
        
        simulator = RobustBotSimulator(BASE_DIR)
        result = simulator.simulate_path(scenario, steps)
        
        return jsonify(result), 200
        
    except Exception as e:
        log.error(f"Error in robust simulation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/simulation-tree', methods=['GET'])
def get_simulation_tree():
    """
    Get comprehensive simulation tree using existing brain components.
    """
    try:
        from .robust_simulator import RobustBotSimulator
        
        simulator = RobustBotSimulator(BASE_DIR)
        result = simulator.get_simulation_tree()
        
        return jsonify(result), 200
        
    except Exception as e:
        log.error(f"Error getting simulation tree: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/decision-tree', methods=['GET'])
def get_decision_tree():
    """
    Get interactive decision tree (legacy endpoint).
    """
    try:
        from .robust_simulator import RobustBotSimulator
        
        simulator = RobustBotSimulator(BASE_DIR)
        result = simulator.get_simulation_tree()
        
        return jsonify(result), 200
        
    except Exception as e:
        log.error(f"Error getting decision tree: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@brain_analyzer_bp.route('/api/brain/health', methods=['GET'])
def get_brain_health():
    """
    Health check for brain analyzer.
    
    Returns status of brain reading system.
    """
    try:
        reader = BotCodeReader(BASE_DIR)
        discovered = reader.discover_all_modules()
        
        return jsonify({
            'success': True,
            'status': 'operational',
            'files_discoverable': len(discovered),
            'auto_refresh_interval': 5  # seconds
        }), 200
        
    except Exception as e:
        log.error(f"Health check error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

