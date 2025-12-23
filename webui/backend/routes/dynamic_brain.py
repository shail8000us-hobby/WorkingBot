"""
Dynamic Brain API Routes

Provides endpoints for the Master Brain Reader and Dynamic Simulator.
Real-time bot brain analysis and scenario simulation.
"""

import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

try:
    from ..brain_analyzer.master_brain_reader import get_master_brain_reader
    from ..brain_analyzer.dynamic_simulator import DynamicBotSimulator
except ImportError:
    from webui.backend.brain_analyzer.master_brain_reader import get_master_brain_reader
    from webui.backend.brain_analyzer.dynamic_simulator import DynamicBotSimulator

log = logging.getLogger(__name__)

# Create blueprint
dynamic_brain_bp = Blueprint('dynamic_brain', __name__)

# Initialize components
bot_root = Path(__file__).parent.parent.parent.parent
master_reader = get_master_brain_reader(bot_root)
dynamic_simulator = DynamicBotSimulator(bot_root)

@dynamic_brain_bp.route('/api/brain/master/scenarios', methods=['GET'])
def get_master_scenarios():
    """Get all scenarios from Master Brain Reader"""
    try:
        scenarios_data = master_reader.get_all_scenarios()
        
        return jsonify({
            'success': True,
            'data': scenarios_data,
            'timestamp': scenarios_data.get('last_scan', 0),
            'total_scenarios': scenarios_data.get('total_scenarios', 0)
        })
        
    except Exception as e:
        log.error(f"Error getting master scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/master/force-scan', methods=['POST'])
def force_master_scan():
    """Force immediate scan of bot brain"""
    try:
        master_reader.force_scan()
        scenarios_data = master_reader.get_all_scenarios()
        
        return jsonify({
            'success': True,
            'message': 'Bot brain scan completed',
            'total_scenarios': scenarios_data.get('total_scenarios', 0),
            'last_scan': scenarios_data.get('last_scan', 0)
        })
        
    except Exception as e:
        log.error(f"Error forcing master scan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/dynamic/simulation-tree', methods=['GET'])
def get_dynamic_simulation_tree():
    """Get real-time simulation tree from Dynamic Simulator"""
    try:
        simulation_tree = dynamic_simulator.get_simulation_tree()
        
        if not simulation_tree.get('success'):
            return jsonify(simulation_tree), 500
        
        return jsonify(simulation_tree)
        
    except Exception as e:
        log.error(f"Error getting dynamic simulation tree: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/dynamic/simulate', methods=['POST'])
def simulate_dynamic_scenario():
    """Simulate scenario using Dynamic Simulator"""
    try:
        data = request.get_json()
        scenario_id = data.get('scenario')
        steps = data.get('steps', [])
        
        if not scenario_id:
            return jsonify({
                'success': False,
                'error': 'Scenario ID required'
            }), 400
        
        simulation_result = dynamic_simulator.simulate_scenario_path(scenario_id, steps)
        
        if not simulation_result.get('success'):
            return jsonify(simulation_result), 500
        
        return jsonify(simulation_result)
        
    except Exception as e:
        log.error(f"Error simulating dynamic scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/master/status', methods=['GET'])
def get_master_status():
    """Get Master Brain Reader status"""
    try:
        scenarios_data = master_reader.get_all_scenarios()
        
        return jsonify({
            'success': True,
            'status': {
                'is_running': master_reader.is_running,
                'scan_interval': master_reader.scan_interval,
                'last_scan': scenarios_data.get('last_scan', 0),
                'total_scenarios': scenarios_data.get('total_scenarios', 0),
                'total_states': len(scenarios_data.get('states', {})),
                'total_actions': len(scenarios_data.get('actions', {})),
                'data_freshness': 'live' if master_reader.is_running else 'stale'
            }
        })
        
    except Exception as e:
        log.error(f"Error getting master status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/master/scenario/<scenario_id>', methods=['GET'])
def get_scenario_details(scenario_id):
    """Get detailed information about a specific scenario"""
    try:
        scenario = master_reader.get_scenario_by_id(scenario_id)
        
        if not scenario:
            return jsonify({
                'success': False,
                'error': f'Scenario {scenario_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'scenario': {
                'id': scenario.id,
                'title': scenario.title,
                'description': scenario.description,
                'initial_state': scenario.initial_state,
                'possible_actions': scenario.possible_actions,
                'end_states': scenario.end_states,
                'confidence': scenario.confidence,
                'category': scenario.category,
                'real_time_data': scenario.real_time_data
            }
        })
        
    except Exception as e:
        log.error(f"Error getting scenario details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/master/categories', methods=['GET'])
def get_scenario_categories():
    """Get all scenario categories with counts"""
    try:
        scenarios_data = master_reader.get_all_scenarios()
        scenarios = scenarios_data.get('scenarios', {})
        
        categories = {}
        for scenario_data in scenarios.values():
            category = scenario_data.get('category', 'unknown')
            if category not in categories:
                categories[category] = {
                    'count': 0,
                    'scenarios': []
                }
            categories[category]['count'] += 1
            categories[category]['scenarios'].append({
                'id': scenario_data.get('id'),
                'title': scenario_data.get('title'),
                'confidence': scenario_data.get('confidence', 0)
            })
        
        return jsonify({
            'success': True,
            'categories': categories,
            'total_categories': len(categories)
        })
        
    except Exception as e:
        log.error(f"Error getting scenario categories: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/interactive/scenarios', methods=['GET'])
def get_interactive_scenarios():
    """Get user-friendly scenarios for interactive simulator"""
    try:
        scenarios_data = master_reader.get_all_scenarios()
        scenarios = scenarios_data.get('scenarios', {})
        
        # Group by category with user-friendly formatting
        interactive_data = {
            'categories': {},
            'featured_scenarios': [],
            'current_state': {},
            'stats': {
                'total_scenarios': len(scenarios),
                'last_scan': scenarios_data.get('last_scan', 0),
                'data_freshness': 'live'
            }
        }
        
        # Category mapping with icons and descriptions
        category_info = {
            'volatility_management': {
                'icon': '🌊',
                'name': 'Volatility Management',
                'description': 'How bot handles market volatility and trading safety'
            },
            'position_management': {
                'icon': '📊',
                'name': 'Position Management', 
                'description': 'Grid position tracking and capacity management'
            },
            'risk_management': {
                'icon': '⚠️',
                'name': 'Risk Management',
                'description': 'Liquidation protection and margin monitoring'
            },
            'safety_systems': {
                'icon': '🛡️',
                'name': 'Safety Systems',
                'description': 'Emergency stops and circuit breakers'
            },
            'order_management': {
                'icon': '📝',
                'name': 'Order Management',
                'description': 'Order placement, cancellation, and verification'
            },
            'fill_detection': {
                'icon': '🎯',
                'name': 'Fill Detection',
                'description': 'Real-time fill monitoring and processing'
            },
            'grid_management': {
                'icon': '📏',
                'name': 'Grid Management',
                'description': 'Grid calculations and level management'
            },
            'guardian_protection': {
                'icon': '👮',
                'name': 'Guardian Protection',
                'description': '24/7 monitoring and loss limit enforcement'
            },
            'capital_protection': {
                'icon': '💎',
                'name': 'Capital Protection',
                'description': 'Equity floor and drawdown protection'
            },
            'error_recovery': {
                'icon': '🔧',
                'name': 'Error Recovery',
                'description': 'API failures and network disconnection handling'
            },
            'ai_assistance': {
                'icon': '🤖',
                'name': 'AI Assistance',
                'description': 'Intelligent Q&A and trading guidance'
            },
            'current_analysis': {
                'icon': '🔍',
                'name': 'Current Analysis',
                'description': 'Real-time bot state and conditions'
            }
        }
        
        # Process scenarios by category
        for scenario_data in scenarios.values():
            category = scenario_data.get('category', 'unknown')
            category_meta = category_info.get(category, {
                'icon': '❓',
                'name': category.replace('_', ' ').title(),
                'description': 'Bot decision scenario'
            })
            
            if category not in interactive_data['categories']:
                interactive_data['categories'][category] = {
                    **category_meta,
                    'scenarios': [],
                    'count': 0
                }
            
            # Format scenario for UI
            formatted_scenario = {
                'id': scenario_data.get('id'),
                'title': scenario_data.get('title', '').replace('REAL: ', ''),
                'description': scenario_data.get('description', '').replace('REAL: ', ''),
                'confidence': scenario_data.get('confidence', 0),
                'category': category,
                'real_time_data': scenario_data.get('real_time_data', {}),
                'possible_actions': scenario_data.get('possible_actions', []),
                'end_states': scenario_data.get('end_states', [])
            }
            
            interactive_data['categories'][category]['scenarios'].append(formatted_scenario)
            interactive_data['categories'][category]['count'] += 1
            
            # Add high-confidence scenarios to featured
            if scenario_data.get('confidence', 0) >= 0.8:
                interactive_data['featured_scenarios'].append(formatted_scenario)
        
        # Get current state from current_analysis scenario
        current_scenario = scenarios.get('current_state')
        if current_scenario:
            interactive_data['current_state'] = {
                'title': current_scenario.get('title', '').replace('REAL: ', ''),
                'description': current_scenario.get('description', '').replace('REAL: ', ''),
                'confidence': current_scenario.get('confidence', 0),
                'data': current_scenario.get('real_time_data', {})
            }
        
        return jsonify({
            'success': True,
            'data': interactive_data
        })
        
    except Exception as e:
        log.error(f"Error getting interactive scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/trading/scenarios', methods=['GET'])
def get_trading_scenarios():
    """Get simplified trading scenarios - only Trading Active or Trading Halted"""
    try:
        # Get current volatility status
        volatility_file = bot_root / '.volatility_status.json'
        positions_file = bot_root / 'bot' / 'state' / 'positions.json'
        
        is_trading_active = True
        halt_reason = None
        
        try:
            if volatility_file.exists():
                import json
                with open(volatility_file, 'r') as f:
                    vol_data = json.load(f)
                    is_trading_active = vol_data.get('is_safe', True)
                    if not is_trading_active:
                        halt_reason = vol_data.get('violation_reason', 'Volatility limits exceeded')
        except Exception as e:
            log.debug(f"Error reading volatility status: {e}")
        
        # Get positions data
        positions_data = []
        try:
            if positions_file.exists():
                import json
                with open(positions_file, 'r') as f:
                    pos_data = json.load(f)
                    positions_data = pos_data.get('positions', [])
        except Exception as e:
            log.debug(f"Error reading positions: {e}")
        
        if is_trading_active:
            scenario = {
                'id': 'trading_active',
                'title': '✅ Trading Active',
                'description': 'Bot is actively trading - placing orders and managing positions',
                'status': 'active',
                'icon': '🟢',
                'color': '#4caf50',
                'details': {
                    'active_positions': len(positions_data),
                    'trading_mode': 'Normal Grid Trading',
                    'next_action': 'Monitor for fills and place next orders'
                }
            }
        else:
            scenario = {
                'id': 'trading_halted',
                'title': '🚨 Trading Halted',
                'description': f'Trading stopped: {halt_reason}',
                'status': 'halted',
                'icon': '🔴',
                'color': '#f44336',
                'details': {
                    'halt_reason': halt_reason,
                    'active_positions': len(positions_data),
                    'next_action': 'Wait for conditions to normalize'
                }
            }
        
        return jsonify({
            'success': True,
            'current_scenario': scenario,
            'is_trading_active': is_trading_active
        })
        
    except Exception as e:
        log.error(f"Error getting trading scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dynamic_brain_bp.route('/api/brain/trading/details/<scenario_id>', methods=['GET'])
def get_trading_details(scenario_id):
    """Get detailed trading information for active/halted scenario"""
    try:
        step = int(request.args.get('step', 0))
        
        if scenario_id == 'trading_active':
            return _get_active_trading_details(step)
        elif scenario_id == 'trading_halted':
            return _get_halted_trading_details(step)
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid scenario ID'
            }), 400
            
    except Exception as e:
        log.error(f"Error getting trading details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_active_trading_details(step):
    """Get details for active trading scenario"""
    # Read positions and pending orders
    positions_file = bot_root / 'bot' / 'state' / 'positions.json'
    
    positions = []
    pending_buy = None
    grid_config = {}
    
    try:
        if positions_file.exists():
            import json
            with open(positions_file, 'r') as f:
                data = json.load(f)
                positions = data.get('positions', [])
                pending_buy = data.get('pending_buy')
    except Exception as e:
        log.debug(f"Error reading positions: {e}")
    
    try:
        # Load config from YAML
        from config.loader import get_config
        cfg = get_config()
        
        # Convert to flat dict for compatibility
        grid_config = {
            'GRIDBOT_LOWER': str(cfg.grid.geometry.lower),
            'GRIDBOT_UPPER': str(cfg.grid.geometry.upper),
            'GRIDBOT_STEP': str(cfg.grid.geometry.step),
            'GRIDBOT_REFERENCE_LEVEL': str(cfg.grid.geometry.reference_level),
            'GRIDBOT_SYMBOL': cfg.bot.symbol,
            'GRIDBOT_LOT_SIZE': str(cfg.bot.lot_size)
        }
    except Exception as e:
        log.debug(f"Error reading config: {e}")
    
    if step == 0:
        return jsonify({
            'success': True,
            'step': 1,
            'title': '📊 Current Trading Status',
            'description': 'Bot is actively managing grid positions',
            'data': {
                'active_positions': len(positions),
                'pending_buy_order': 'Yes' if pending_buy else 'No',
                'grid_step': grid_config.get('GRIDBOT_STEP', 'Unknown'),
                'max_positions': grid_config.get('GRIDBOT_MAX_OPEN', 'Unknown')
            },
            'next_button': 'Show Next BUY Order'
        })
    
    elif step == 1:
        next_buy_price = 'Calculating...'
        if pending_buy:
            next_buy_price = f"₹{float(pending_buy.get('price', 0)):,.0f}"
        elif positions:
            # Calculate next buy level
            lowest_entry = min(float(pos.get('entry_price', 0)) for pos in positions)
            step_size = float(grid_config.get('GRIDBOT_STEP', 1000))
            next_buy_price = f"₹{(lowest_entry - step_size):,.0f}"
        
        return jsonify({
            'success': True,
            'step': 2,
            'title': '🎯 Next BUY Order',
            'description': 'Next order that will be placed when price drops',
            'data': {
                'next_buy_price': next_buy_price,
                'order_status': 'Pending' if pending_buy else 'Will be placed',
                'lot_size': grid_config.get('GRIDBOT_LOT', 'Unknown')
            },
            'next_button': 'Show Target Prices'
        })
    
    elif step == 2:
        target_prices = []
        for pos in positions[:3]:  # Show first 3 positions
            entry = float(pos.get('entry_price', 0))
            step_size = float(grid_config.get('GRIDBOT_STEP', 1000))
            target = entry + step_size
            target_prices.append({
                'entry_price': f"₹{entry:,.0f}",
                'target_price': f"₹{target:,.0f}",
                'profit': f"₹{step_size * float(grid_config.get('GRIDBOT_LOT', 1)):,.0f}"
            })
        
        return jsonify({
            'success': True,
            'step': 3,
            'title': '💰 Target Prices (Take Profit)',
            'description': 'Current positions and their profit targets',
            'data': {
                'target_orders': target_prices,
                'total_positions': len(positions)
            },
            'next_button': 'Back to Overview'
        })
    
    else:
        # Reset to step 0
        return _get_active_trading_details(0)

def _get_halted_trading_details(step):
    """Get details for halted trading scenario"""
    volatility_file = bot_root / '.volatility_status.json'
    
    vol_data = {}
    try:
        if volatility_file.exists():
            import json
            with open(volatility_file, 'r') as f:
                vol_data = json.load(f)
    except Exception as e:
        log.debug(f"Error reading volatility: {e}")
    
    if step == 0:
        return jsonify({
            'success': True,
            'step': 1,
            'title': '🚨 Why Trading is Halted',
            'description': vol_data.get('violation_reason', 'Volatility limits exceeded'),
            'data': {
                'current_iv': f"{vol_data.get('current_iv', 0):.1f}%",
                'max_iv': f"{vol_data.get('max_iv', 35):.1f}%",
                'current_rv': f"{vol_data.get('current_rv', 0):.1f}%",
                'max_rv': f"{vol_data.get('max_rv', 40):.1f}%"
            },
            'next_button': 'What Happens Next?'
        })
    
    elif step == 1:
        return jsonify({
            'success': True,
            'step': 2,
            'title': '⏳ Waiting for Conditions',
            'description': 'Bot will resume trading when volatility normalizes',
            'data': {
                'action': 'Monitor volatility levels',
                'resume_condition': 'IV < 35% AND RV < 40%',
                'current_positions': 'Protected (TP orders remain active)'
            },
            'next_button': 'Back to Overview'
        })
    
    else:
        # Reset to step 0
        return _get_halted_trading_details(0)

# Legacy compatibility - redirect old endpoints to new dynamic ones
@dynamic_brain_bp.route('/api/brain/simulation-tree', methods=['GET'])
def legacy_simulation_tree():
    """Legacy endpoint - redirects to dynamic simulation tree"""
    return get_dynamic_simulation_tree()

@dynamic_brain_bp.route('/api/brain/simulate', methods=['POST'])
def legacy_simulate():
    """Legacy endpoint - redirects to dynamic simulation"""
    return simulate_dynamic_scenario()

log.info("Dynamic Brain API routes initialized with Master Brain Reader and Simplified Trading Simulator")