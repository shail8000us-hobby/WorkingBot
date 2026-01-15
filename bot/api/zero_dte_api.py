"""
Zero DTE REST API
=================

Flask Blueprint for 0DTE bot control and monitoring.

Endpoints:
- POST /session/start - Start new session
- POST /session/stop - Stop session
- GET /status - Get current status
- GET /rebalances - Get rebalancing history
- GET /config - Get configuration
- PUT /config - Update configuration
"""

from flask import Blueprint, request, jsonify
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional
from loguru import logger

from bot.strategy.zero_dte.config import load_config, update_config
from bot.strategy.zero_dte.engine import ZeroDTEEngine
from bot.strategy.zero_dte.monitor import ZeroDTEMonitor
from bot.strategy.zero_dte.state_manager import StateManager


# Create Blueprint
zero_dte_bp = Blueprint('zero_dte', __name__)

# Global engine instance (singleton)
_engine: Optional[ZeroDTEEngine] = None
_monitor: Optional[ZeroDTEMonitor] = None


def get_engine() -> Optional[ZeroDTEEngine]:
    """Get or create engine instance"""
    global _engine
    return _engine


def init_engine(api_client):
    """Initialize engine with API client"""
    global _engine, _monitor
    
    config = load_config()
    _engine = ZeroDTEEngine(api_client, config)
    _monitor = ZeroDTEMonitor(api_client, config, _engine.state_manager)
    
    logger.info("0DTE Engine initialized")
    return _engine


def run_async(f):
    """Decorator to run async functions in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================

@zero_dte_bp.route('/session/start', methods=['POST'])
@run_async
async def start_session():
    """
    Start new 0DTE trading session
    
    Request Body:
    {
        "underlying": "BTC",        // Optional, default from config
        "expiry_date": "2026-01-13", // Optional, default today
        "initial_lots": 5,          // Optional, default from config
        "target_premium_min": 15,   // Optional
        "target_premium_max": 30    // Optional
    }
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized. Please restart backend.'
        }), 500
    
    try:
        data = request.get_json() or {}
        
        result = await engine.start_session(
            underlying=data.get('underlying'),
            expiry_date=data.get('expiry_date'),
            initial_lots=data.get('initial_lots'),
            target_premium_min=data.get('target_premium_min'),
            target_premium_max=data.get('target_premium_max'),
            skip_time_check=data.get('skip_time_check', False)
        )
        
        return jsonify(result)
        
    except RuntimeError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Start session error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/session/stop', methods=['POST'])
@run_async
async def stop_session():
    """
    Stop current session and close all positions
    
    Request Body:
    {
        "reason": "manual"  // Optional: manual, emergency
    }
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    if not engine.is_running:
        return jsonify({
            'success': False,
            'error': 'No active session'
        }), 400
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'manual')
        
        result = await engine.stop_session(reason)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Stop session error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/session/active', methods=['GET'])
def get_active_session():
    """Get active session info"""
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    if not engine.is_running:
        return jsonify({
            'success': True,
            'session': None
        })
    
    try:
        session = engine.state_manager.get_session(engine.session_id)
        positions = engine.state_manager.get_positions(engine.session_id)
        
        return jsonify({
            'success': True,
            'session': {
                'session_id': engine.session_id,
                'status': 'active',
                'underlying': session.get('underlying'),
                'expiry_date': session.get('expiry_date'),
                'start_time': session.get('start_time'),
                'positions': {
                    'ce': {
                        'strike': positions.get('CE', {}).get('strike'),
                        'lots': positions.get('CE', {}).get('lots'),
                        'premium': positions.get('CE', {}).get('current_premium')
                    },
                    'pe': {
                        'strike': positions.get('PE', {}).get('strike'),
                        'lots': positions.get('PE', {}).get('lots'),
                        'premium': positions.get('PE', {}).get('current_premium')
                    }
                },
                'pnl': {
                    'realized': session.get('realized_pnl', 0),
                    'unrealized': session.get('unrealized_pnl', 0)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Get active session error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# STATUS ENDPOINTS
# =============================================================================

@zero_dte_bp.route('/status', methods=['GET'])
@run_async
async def get_status():
    """
    Get comprehensive current status
    
    Returns real-time data including:
    - Position details
    - Premium balance
    - P&L
    - Greeks
    - Time to expiry
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    if not engine.is_running:
        return jsonify({
            'success': True,
            'is_active': False,
            'session_id': None
        })
    
    try:
        global _monitor
        if _monitor:
            data = await _monitor.get_current_data(engine.session_id)
            return jsonify({
                'success': True,
                'is_active': True,
                **data
            })
        else:
            # Fallback to engine status
            status = engine.get_status()
            return jsonify({
                'success': True,
                **status
            })
            
    except Exception as e:
        logger.error(f"Get status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# HISTORY ENDPOINTS
# =============================================================================

@zero_dte_bp.route('/rebalances', methods=['GET'])
def get_rebalances():
    """
    Get rebalancing history
    
    Query Params:
    - session_id: Filter by session (optional, defaults to active)
    - limit: Max records to return (default 20)
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    try:
        session_id = request.args.get('session_id')
        limit = int(request.args.get('limit', 20))
        
        if not session_id and engine.is_running:
            session_id = engine.session_id
        
        if not session_id:
            return jsonify({
                'success': True,
                'rebalances': []
            })
        
        rebalances = engine.state_manager.get_rebalances(session_id, limit)
        
        # Format for frontend
        formatted = []
        for r in rebalances:
            formatted.append({
                'id': r['id'],
                'timestamp': r['timestamp'],
                'type': r['rebalance_type'],
                'reason': r['trigger_reason'],
                'before': {
                    'ce_lots': r.get('ce_lots_before'),
                    'pe_lots': r.get('pe_lots_before'),
                    'imbalance': r.get('imbalance_pct_before')
                },
                'after': {
                    'ce_lots': r.get('ce_lots_after'),
                    'pe_lots': r.get('pe_lots_after'),
                    'imbalance': r.get('imbalance_pct_after')
                },
                'action': r.get('action_taken'),
                'status': r.get('execution_status')
            })
        
        return jsonify({
            'success': True,
            'rebalances': formatted
        })
        
    except Exception as e:
        logger.error(f"Get rebalances error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/trades', methods=['GET'])
def get_trades():
    """
    Get trade history
    
    Query Params:
    - session_id: Filter by session (optional)
    - limit: Max records (default 50)
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    try:
        session_id = request.args.get('session_id')
        limit = int(request.args.get('limit', 50))
        
        if not session_id and engine.is_running:
            session_id = engine.session_id
        
        if not session_id:
            return jsonify({
                'success': True,
                'trades': []
            })
        
        trades = engine.state_manager.get_trades(session_id, limit)
        
        return jsonify({
            'success': True,
            'trades': trades
        })
        
    except Exception as e:
        logger.error(f"Get trades error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/snapshots', methods=['GET'])
def get_snapshots():
    """
    Get monitoring snapshots for charting
    
    Query Params:
    - session_id: Filter by session (optional)
    - limit: Max records (default 100)
    """
    engine = get_engine()
    if not engine:
        return jsonify({
            'success': False,
            'error': 'Engine not initialized'
        }), 500
    
    try:
        session_id = request.args.get('session_id')
        limit = int(request.args.get('limit', 100))
        
        if not session_id and engine.is_running:
            session_id = engine.session_id
        
        if not session_id:
            return jsonify({
                'success': True,
                'snapshots': []
            })
        
        snapshots = engine.state_manager.get_snapshots(session_id, limit)
        
        return jsonify({
            'success': True,
            'snapshots': snapshots
        })
        
    except Exception as e:
        logger.error(f"Get snapshots error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@zero_dte_bp.route('/expiries', methods=['GET'])
@run_async
async def get_expiries():
    """
    Get available expiry dates for options
    
    Query Params:
    - underlying: BTC or ETH (default: BTC)
    
    Returns list of expiries with DTE (days to expiry)
    """
    engine = get_engine()
    
    try:
        underlying = request.args.get('underlying', 'BTC').upper()
        
        # Try to fetch from API
        if engine and engine.api_client:
            try:
                # Fetch available option expiries from Delta Exchange
                # Using the options chain endpoint
                expiries_data = await engine.api_client.get_option_expiries(underlying)
                
                if expiries_data:
                    today = datetime.now().date()
                    expiries = []
                    
                    for exp in expiries_data:
                        exp_date = datetime.strptime(exp['expiry_date'], '%Y-%m-%d').date()
                        dte = (exp_date - today).days
                        
                        if dte >= 0:  # Only future expiries
                            expiries.append({
                                'date': exp['expiry_date'],
                                'dte': dte,
                                'symbol': exp.get('symbol', exp['expiry_date']),
                                'settlement_time': '17:30'
                            })
                    
                    # Sort by date
                    expiries.sort(key=lambda x: x['date'])
                    
                    return jsonify({
                        'success': True,
                        'underlying': underlying,
                        'expiries': expiries[:14]  # Limit to 2 weeks
                    })
                    
            except Exception as api_err:
                logger.warning(f"Failed to fetch expiries from API: {api_err}")
        
        # Fallback: Generate daily expiries (Delta Exchange has daily options)
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        expiries = []
        
        for i in range(14):  # Next 2 weeks
            exp_date = today + timedelta(days=i)
            date_str = exp_date.strftime('%Y-%m-%d')
            
            expiries.append({
                'date': date_str,
                'dte': i,
                'symbol': f"{underlying}-{date_str}",
                'settlement_time': '17:30'
            })
        
        return jsonify({
            'success': True,
            'underlying': underlying,
            'expiries': expiries,
            'source': 'generated'
        })
        
    except Exception as e:
        logger.error(f"Get expiries error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        config = load_config()
        
        # Return key settings (not full config)
        return jsonify({
            'success': True,
            'config': {
                'entry': {
                    'default_underlying': config.entry.default_underlying,
                    'initial_lots': config.entry.initial_lots,
                    'strike_offset_pct': config.entry.strike_offset_pct,
                    'premium_range': {
                        'min': config.entry.premium_range.min,
                        'max': config.entry.premium_range.max
                    }
                },
                'rebalancing': {
                    'imbalance_threshold_pct': config.rebalancing.imbalance_threshold_pct,
                    'min_lot_adjustment': config.rebalancing.adjustment.min_lot_adjustment,
                    'max_lot_adjustment': config.rebalancing.adjustment.max_lot_adjustment
                },
                'rollover': {
                    'min_premium_threshold': config.rollover.min_premium_threshold,
                    'target_premium': {
                        'min': config.rollover.target_premium.min,
                        'max': config.rollover.target_premium.max
                    }
                },
                'exit': {
                    'both_legs_below': config.exit.both_legs_below,
                    'forced_exit_time': config.exit.forced_exit_time,
                    'stop_loss_amount': config.exit.stop_loss_amount
                },
                'risk': {
                    'guardian_enabled': config.risk.guardian_enabled,
                    'max_margin_utilization_pct': config.risk.max_margin_utilization_pct
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Get config error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zero_dte_bp.route('/config', methods=['PUT'])
def update_config_endpoint():
    """
    Update configuration
    
    Request Body: Partial config updates
    {
        "rebalancing": {
            "imbalance_threshold_pct": 15
        },
        "exit": {
            "stop_loss_amount": 3000
        }
    }
    """
    try:
        updates = request.get_json()
        
        if not updates:
            return jsonify({
                'success': False,
                'error': 'No updates provided'
            }), 400
        
        new_config = update_config(updates)
        
        # Reload engine config if running
        engine = get_engine()
        if engine:
            engine.config = new_config
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated'
        })
        
    except Exception as e:
        logger.error(f"Update config error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# HEALTH CHECK
# =============================================================================

@zero_dte_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    engine = get_engine()
    
    return jsonify({
        'success': True,
        'status': 'healthy',
        'engine_initialized': engine is not None,
        'session_active': engine.is_running if engine else False
    })
