"""
Monitoring Routes Blueprint

Exposes bot monitoring systems to WebUI via REST API

Routes:
- GET /api/monitoring/price-health - Price freshness status
- GET /api/monitoring/pre-order-stats - Pre-order decision statistics  
- GET /api/monitoring/tp-verification - TP verification status
- GET /api/monitoring/anomalies - Recent anomaly detections
- GET /api/monitoring/predictive-map - Predictive decision map
- GET /api/monitoring/status - Overall monitoring system status

Dependencies:
- Bot monitoring systems (if bot is running)
- Runtime state file (for offline data)

Date: November 8, 2025
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import cache
try:
    from webui.backend.cache import cache, CACHE_TIMEOUTS, make_cache_key
except ImportError:
    from cache import cache, CACHE_TIMEOUTS, make_cache_key

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import YAML config helper
from webui.backend.utils.yaml_config import get_config_value

log = logging.getLogger(__name__)

# Create blueprint
monitoring_bp = Blueprint('monitoring', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
RUNTIME_STATE_FILE = BASE_DIR / "runtime_state.json"
# V5.0: Symbol-specific monitoring snapshots
# MONITORING_SNAPSHOT_FILE is now determined dynamically per symbol

# Global references to bot monitoring systems (set by app.py)
_price_monitor = None
_pre_order_logger = None
_tp_verifier = None
_anomaly_detector = None
_predictive_display = None
_bot_instance = None


def _get_monitoring_file(symbol_name='BTCUSD', mode='LONG'):
    """
    Get path to symbol-specific monitoring snapshot file (v5.0).
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
        mode: Trading mode (e.g., 'LONG', 'SHORT')
    
    Returns:
        Path: Path to monitoring snapshot file
    """
    return BASE_DIR / "data" / f"monitoring_snapshot_{symbol_name}_{mode}.json"


def get_instance_from_request():
    """
    Extract instance from request, supporting both v5.0 and v6.0 formats.
    
    Returns:
        tuple: (instance_name, symbol, mode)
    """
    instance = request.args.get('instance')
    if instance:
        parts = instance.rsplit('_', 1)
        if len(parts) == 2:
            return instance, parts[0], parts[1]
        return instance, instance, 'LONG'
    
    symbol = request.args.get('symbol', 'BTCUSD')
    mode = request.args.get('mode', 'LONG')
    return f"{symbol}_{mode}", symbol, mode


def _load_monitoring_snapshot(symbol_name=None, mode=None):
    """
    Load monitoring data from symbol-specific snapshot file (v5.0).
    
    This allows WebUI to show monitoring data even when bot runs standalone
    (not started from WebUI).
    
    Args:
        symbol_name: Symbol key (default: from config or 'BTCUSD')
        mode: Trading mode (default: from config or 'LONG')
    
    Returns:
        dict: Monitoring data or None if file doesn't exist/is stale
    """
    try:
        # Get symbol from query params or config
        if not symbol_name:
            from webui.backend.utils.yaml_config import get_config_value
            config = get_config_value()
            
            # V5.0: Try symbols config first
            if hasattr(config, 'symbols') and config.symbols:
                # Use first enabled symbol
                for sym_name, sym_config in config.symbols.items():
                    if sym_config.enabled:
                        symbol_name = sym_name
                        mode = sym_config.mode
                        break
                
                if not symbol_name:
                    # No enabled symbols, use first symbol
                    symbol_name = list(config.symbols.keys())[0]
                    mode = config.symbols[symbol_name].mode
            else:
                # V4.0: Single symbol mode
                symbol_name = getattr(config.bot, 'symbol', 'BTCUSD')
                mode = getattr(config.bot, 'mode', 'LONG')
        
        if not mode:
            mode = 'LONG'  # Default mode
        
        monitoring_file = _get_monitoring_file(symbol_name, mode)
        
        if not monitoring_file.exists():
            log.debug(f"Monitoring snapshot not found: {monitoring_file}")
            return None
        
        with open(monitoring_file) as f:
            data = json.load(f)
        
        # Check if data is fresh (< 30s old)
        timestamp = datetime.fromisoformat(data['timestamp'])
        age = (datetime.now() - timestamp).total_seconds()
        
        if age < 30:
            log.debug(f"✅ Loaded monitoring snapshot for {symbol_name} (age: {age:.1f}s)")
            return data
        else:
            log.debug(f"⚠️ Monitoring snapshot for {symbol_name} too old ({age:.1f}s)")
            return None
            
    except Exception as e:
        log.debug(f"Failed to load monitoring snapshot: {e}")
        return None

def set_bot_instance(bot):
    """
    Set reference to running bot instance
    
    Called by app.py when bot starts to wire monitoring systems
    
    Args:
        bot: GridBot instance with monitoring systems
    """
    global _bot_instance, _price_monitor, _pre_order_logger, _tp_verifier, _anomaly_detector, _predictive_display
    
    _bot_instance = bot
    
    if bot:
        _price_monitor = getattr(bot, 'price_monitor', None)
        _pre_order_logger = getattr(bot, 'pre_order_logger', None)
        _tp_verifier = getattr(bot, 'tp_verifier', None)
        _anomaly_detector = getattr(bot, 'anomaly_detector', None)
        _predictive_display = getattr(bot, 'predictive_display', None)
        
        log.info("✅ Monitoring systems wired to WebUI")

# ============================================================================
# Route Handlers
# ============================================================================

@monitoring_bp.route('/api/monitoring/status', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUTS['market'], key_prefix=make_cache_key)
def monitoring_status():
    """
    Get overall monitoring system status
    
    Query Parameters:
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional, defaults to first enabled symbol
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional, defaults from config
    
    Returns status of all 5 monitoring layers.
    First tries to read from shared snapshot file (works with standalone bot),
    falls back to bot_instance (WebUI-started bot).
    
    Example:
        GET /api/monitoring/status?symbol=BTCUSD
        Response: {
            "monitoring_active": true,
            "symbol": "BTCUSD",
            "mode": "LONG",
            "layers": {
                "price_health": true,
                "pre_order_logger": true,
                "tp_verification": true,
                "anomaly_detection": true,
                "predictive_display": true
            }
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first (works with standalone bot)
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot:
            return jsonify({
                'monitoring_active': snapshot.get('monitoring_active', False),
                'symbol': snapshot.get('symbol', symbol or 'BTCUSD'),
                'mode': snapshot.get('mode', mode or 'LONG'),
                'layers': {
                    'price_health': snapshot['layers'].get('price_health', {}).get('active', False),
                    'pre_order_logger': snapshot['layers'].get('pre_order_stats', {}).get('active', False),
                    'tp_verification': snapshot['layers'].get('tp_verification', {}).get('active', False),
                    'anomaly_detection': snapshot['layers'].get('anomalies', {}).get('active', False),
                    'predictive_display': snapshot['layers'].get('predictive', {}).get('active', False)
                },
                'timestamp': snapshot.get('timestamp'),
                'source': 'snapshot_file'
            })
        
        # Fallback to bot_instance (WebUI-started bot)
        return jsonify({
            'monitoring_active': _bot_instance is not None,
            'layers': {
                'price_health': _price_monitor is not None,
                'pre_order_logger': _pre_order_logger is not None,
                'tp_verification': _tp_verifier is not None,
                'anomaly_detection': _anomaly_detector is not None,
                'predictive_display': _predictive_display is not None
            },
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting monitoring status: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/price-health', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUTS['market'], key_prefix=make_cache_key)
def price_health():
    """
    Get current price health status
    
    Query Parameters:
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional
    
    Returns:
        Price freshness, age, source, and staleness warnings
    
    Example:
        GET /api/monitoring/price-health?symbol=BTCUSD
        Response: {
            "fresh": true,
            "age_seconds": 2.3,
            "source": "WebSocket",
            "last_update": "2025-11-08T10:30:45",
            "stale_warning": false,
            "critical_warning": false,
            "symbol": "BTCUSD",
            "mode": "LONG"
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'price_health' in snapshot.get('layers', {}):
            data = snapshot['layers']['price_health']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode or 'LONG')
            return jsonify(data), 200
        
        # Fallback to bot_instance
        if not _price_monitor:
            return jsonify({
                'error': 'Price monitor not available - bot may not be running',
                'fresh': None
            }), 503
        
        price_age = _price_monitor.get_price_age()
        is_fresh = _price_monitor.is_price_fresh()
        is_stale = price_age > _price_monitor.stale_threshold if price_age else False
        is_critical = price_age > _price_monitor.critical_threshold if price_age else False
        
        return jsonify({
            'fresh': is_fresh,
            'age_seconds': round(price_age, 2) if price_age else None,
            'source': _price_monitor.last_price_source if hasattr(_price_monitor, 'last_price_source') else 'Unknown',
            'last_update': _price_monitor.last_update_time.isoformat() if hasattr(_price_monitor, 'last_update_time') and _price_monitor.last_update_time else None,
            'stale_warning': is_stale and not is_critical,
            'critical_warning': is_critical,
            'thresholds': {
                'stale': _price_monitor.stale_threshold,
                'critical': _price_monitor.critical_threshold
            },
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting price health: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/pre-order-stats', methods=['GET'])
def pre_order_stats():
    """
    Get pre-order decision statistics
    
    Query Parameters:
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional
    
    Returns:
        Approval/rejection counts and rate
    
    Example:
        GET /api/monitoring/pre-order-stats?symbol=BTCUSD
        Response: {
            "approved": 45,
            "rejected": 3,
            "total": 48,
            "approval_rate": 93.75,
            "symbol": "BTCUSD",
            "mode": "LONG"
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'pre_order_stats' in snapshot.get('layers', {}):
            return jsonify(snapshot['layers']['pre_order_stats']), 200
        
        # Fallback to bot_instance
        if not _pre_order_logger:
            return jsonify({
                'error': 'Pre-order logger not available - bot may not be running',
                'approved': 0,
                'rejected': 0
            }), 503
        
        stats = _pre_order_logger.get_statistics()
        
        return jsonify({
            'approved': stats.get('approved', 0),
            'rejected': stats.get('rejected', 0),
            'total': stats.get('total', 0),
            'approval_rate': stats.get('approval_rate', 0),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting pre-order stats: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/tp-verification', methods=['GET'])
def tp_verification():
    """
    Get TP verification statistics
    
    Query Parameters:
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional
    
    Returns:
        TP verification success rate and orphaned positions
    
    Example:
        GET /api/monitoring/tp-verification?symbol=BTCUSD
        Response: {
            "verified": 42,
            "orphaned": 0,
            "success_rate": 100.0,
            "symbol": "BTCUSD",
            "mode": "LONG"
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'tp_verification' in snapshot.get('layers', {}):
            data = snapshot['layers']['tp_verification']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode or 'LONG')
            return jsonify(data), 200
        
        # Fallback to bot_instance
        if not _tp_verifier:
            return jsonify({
                'error': 'TP verifier not available - bot may not be running',
                'verified': 0,
                'orphaned': 0
            }), 503
        
        # Get statistics from TP verifier
        verified_count = getattr(_tp_verifier, 'verified_count', 0)
        orphaned_count = len(getattr(_tp_verifier, 'orphaned_positions', set()))
        total = verified_count + orphaned_count
        success_rate = (verified_count / total * 100) if total > 0 else 100.0
        
        return jsonify({
            'verified': verified_count,
            'orphaned': orphaned_count,
            'total': total,
            'success_rate': round(success_rate, 2),
            'orphaned_list': list(getattr(_tp_verifier, 'orphaned_positions', set())),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting TP verification stats: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/anomalies', methods=['GET'])
def anomalies():
    """
    Get recent anomaly detections
    
    Query Parameters:
        limit: Maximum number of anomalies to return (default: 10)
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional
    
    Returns:
        List of recent anomalies with severity and type
    
    Example:
        GET /api/monitoring/anomalies?limit=5&symbol=BTCUSD
        Response: {
            "anomalies": [
                {
                    "type": "price_jump",
                    "severity": "HIGH",
                    "message": "Price jumped 5.2% in 25s",
                    "timestamp": "2025-11-08T10:25:30"
                }
            ],
            "count": 1,
            "symbol": "BTCUSD",
            "mode": "LONG"
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'anomalies' in snapshot.get('layers', {}):
            data = snapshot['layers']['anomalies']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode or 'LONG')
            return jsonify(data), 200
        
        # Fallback to bot_instance
        if not _anomaly_detector:
            return jsonify({
                'error': 'Anomaly detector not available - bot may not be running',
                'anomalies': []
            }), 503
        
        limit = request.args.get('limit', default=10, type=int)
        
        # Get recent anomalies (if method exists)
        if hasattr(_anomaly_detector, 'get_recent_anomalies'):
            recent_anomalies = _anomaly_detector.get_recent_anomalies(limit=limit)
        else:
            # Fallback: return empty list
            recent_anomalies = []
        
        return jsonify({
            'anomalies': recent_anomalies,
            'count': len(recent_anomalies),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting anomalies: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/predictive-map', methods=['GET'])
def predictive_map():
    """
    Get predictive decision map
    
    Query Parameters:
        symbol: Symbol name (e.g., 'BTCUSD', 'ETHUSD') - Optional
        mode: Trading mode (e.g., 'LONG', 'SHORT') - Optional
    
    Returns what bot will do next based on price movement
    
    Example:
        GET /api/monitoring/predictive-map?symbol=BTCUSD
        Response: {
            "current_price": 101234,
            "next_buy_levels": [100000, 99000, 98000],
            "next_tp_fills": [101500, 102000, 102500],
            "mode": "LONG",
            "capacity": {"used": 3, "available": 7},
            "symbol": "BTCUSD"
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'predictive' in snapshot.get('layers', {}):
            data = snapshot['layers']['predictive']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode or 'LONG')
            return jsonify(data), 200
        
        # Fallback to bot_instance
        if not _predictive_display or not _bot_instance:
            return jsonify({
                'error': 'Predictive display not available - bot may not be running',
                'next_buy_levels': [],
                'next_tp_fills': []
            }), 503
        
        # Get current bot state
        current_price = getattr(_bot_instance, 'current_price', None)
        grid_mode = getattr(_bot_instance, 'mode', 'LONG')  # Fixed: mode not grid_mode
        grid_step = getattr(_bot_instance.grid_calc, 'step', 0) if hasattr(_bot_instance, 'grid_calc') else 0
        
        # Get positions from position actor (async call needs to be handled properly)
        positions = []
        try:
            if hasattr(_bot_instance, 'position_actor'):
                # For async bot, we can't directly call ask() from sync context
                # Instead, try to get cached state or use snapshot data
                positions = getattr(_bot_instance, '_cached_positions', [])
        except Exception as e:
            log.debug(f"Could not get positions from bot instance: {e}")
            positions = []
        
        max_open = getattr(_bot_instance.position_actor, 'max_positions', 10) if hasattr(_bot_instance, 'position_actor') else 10
        
        # Calculate next levels
        next_levels = []
        if current_price and grid_step:
            if grid_mode == 'LONG':
                # Next 3 BUY levels
                for i in range(1, 4):
                    next_price = current_price - (grid_step * i)
                    next_levels.append({
                        'price': round(next_price, 2),
                        'action': 'BUY',
                        'gap_pct': round((next_price - current_price) / current_price * 100, 2)
                    })
            else:  # SHORT
                # Next 3 SELL levels
                for i in range(1, 4):
                    next_price = current_price + (grid_step * i)
                    next_levels.append({
                        'price': round(next_price, 2),
                        'action': 'SELL',
                        'gap_pct': round((next_price - current_price) / current_price * 100, 2)
                    })
        
        # Calculate next TP fills
        next_tp_fills = []
        for position in positions[:3]:  # First 3 positions
            entry_price = position.get('entry_price', 0)
            tp_price = position.get('tp_price', 0)
            if tp_price:
                next_tp_fills.append({
                    'entry_price': entry_price,
                    'tp_price': tp_price,
                    'profit': round(tp_price - entry_price, 2) if grid_mode == 'LONG' else round(entry_price - tp_price, 2)
                })
        
        return jsonify({
            'current_price': current_price,
            'next_levels': next_levels,
            'next_tp_fills': next_tp_fills,
            'mode': grid_mode,
            'capacity': {
                'used': len(positions),
                'available': max_open - len(positions),
                'max': max_open
            },
            'grid_step': grid_step,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting predictive map: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/advanced-predictions', methods=['GET'])
def advanced_predictions():
    """
    Get advanced bot predictions based on ACTUAL bot code logic
    
    Uses BotPredictionEngine to mirror exact bot behavior from:
    - async_gridbot.py (_check_and_place_entry_order)
    - grid_calculator.py (all grid calculations)
    - fill_processing_saga.py (fill handling, cancellation logic)
    
    Returns real-time predictions:
    - Next pending order (BUY/SELL)
    - What happens when it fills
    - TP placement
    - Old pending order cancellation (FIX NOV 14)
    - Next pending order after TP fills
    
    Example:
        GET /api/monitoring/advanced-predictions
        Response: {
            "next_action": {
                "type": "PENDING_BUY",
                "price": 94500,
                "status": "Will place when price drops to $94,500",
                "then": "Calculate TP @ $95,500"
            },
            "scenarios": {
                "if_pending_fills": {
                    "type": "BUY_FILLED",
                    "actions": [
                        {"sequence": 1, "action": "PLACE_TP", "price": 95500},
                        {"sequence": 2, "action": "CLEAR_PENDING_BUY"},
                        {"sequence": 3, "action": "PLACE_NEW_BUY", "price": 93500}
                    ]
                },
                "if_tp_fills": {
                    "type": "SELL_FILLED",
                    "actions": [
                        {"sequence": 1, "action": "REMOVE_POSITION"},
                        {"sequence": 2, "action": "CLEAR_PENDING_SELL"},
                        {"sequence": 3, "action": "CANCEL_PENDING_BUY", "price": 93500},
                        {"sequence": 4, "action": "PLACE_NEW_BUY", "price": 94500}
                    ]
                }
            }
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode_param = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode_param)
        if snapshot and 'advanced_predictions' in snapshot.get('layers', {}):
            data = snapshot['layers']['advanced_predictions']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode_param or 'LONG')
            return jsonify(data), 200
        
        # Try to read from SQL database (works with standalone bot)
        from webui.backend.utils.bot_state_reader import get_bot_state_from_db
        from webui.backend.utils.bot_prediction_engine import BotPredictionEngine
        
        # Get mode from config
        mode = get_config_value('bot.mode', 'BOT_MODE', 'LONG')
        
        # Get grid config first to get reference price
        grid_lower = get_config_value('grid.geometry.lower', 'GRID_LOWER', 90000)
        grid_upper = get_config_value('grid.geometry.upper', 'GRID_UPPER', 110000)
        grid_step = get_config_value('grid.geometry.step', 'GRID_STEP', 500)
        grid_ref = get_config_value('grid.geometry.reference', 'GRID_REF', 95500)
        
        # Use ref as current price fallback (will be replaced by actual price if available)
        current_price = grid_ref
        
        # Try database with current price AND grid bounds to filter stale/out-of-bounds positions
        db_state = get_bot_state_from_db(mode=mode, current_price=current_price, grid_lower=grid_lower, grid_upper=grid_upper)
        
        if db_state:
            log.info("✅ Reading bot state from SQL database")
            
            # Get grid config
            grid_lower = get_config_value('grid.geometry.lower', 'GRID_LOWER', 90000)
            grid_upper = get_config_value('grid.geometry.upper', 'GRID_UPPER', 110000)
            grid_step = get_config_value('grid.geometry.step', 'GRID_STEP', 500)
            grid_ref = get_config_value('grid.geometry.reference', 'GRID_REF', 95500)
            max_open = get_config_value('grid.limits.max_open_positions', 'MAX_OPEN_POSITIONS', 10)
            tick_size = get_config_value('grid.behavior.tick_size', 'TICK_SIZE', 0.5)
            heartbeat_seconds = get_config_value('bot.heartbeat_seconds', 'HEARTBEAT_SECONDS', 20)
            
            # Get current price from bot instance or use ref as fallback
            current_price = grid_ref  # Default fallback
            
            # Try to get real current price from bot instance
            if _bot_instance:
                bot_current_price = getattr(_bot_instance, 'current_price', None)
                if bot_current_price and bot_current_price > 0:
                    current_price = bot_current_price
                    log.debug(f"Using bot current price: ${current_price:,.0f}")
                else:
                    log.debug(f"Bot current price not available, using ref: ${current_price:,.0f}")
            
            # Try to get from monitoring snapshot as backup
            if current_price == grid_ref and snapshot:
                snapshot_price = snapshot.get('layers', {}).get('price_health', {}).get('current_price')
                if snapshot_price and snapshot_price > 0:
                    current_price = snapshot_price
                    log.debug(f"Using snapshot price: ${current_price:,.0f}")
            
            # Get state from database
            positions = db_state.get('positions', [])
            pending_buy = db_state.get('pending_buy')
            pending_sell = db_state.get('pending_sell')
            
            # Create prediction engine
            predictor = BotPredictionEngine(
                grid_lower=grid_lower,
                grid_upper=grid_upper,
                grid_step=grid_step,
                grid_ref=grid_ref,
                mode=mode,
                max_open=max_open,
                tick_size=tick_size
            )
            
            # Calculate what pending order SHOULD exist
            # NOTE: positions from db_state are already fully filtered by bot_state_reader:
            # - Stale positions (TP reached) removed
            # - Out-of-bounds positions removed  
            # - Invalid positions (LONG entry>price, SHORT entry<price) removed
            warnings = []
            expected_pending_price = None
            
            # Get current market price (use ref as fallback, but try to get real price)
            current_market_price = current_price  # This is using ref price as fallback
            
            if mode == 'LONG':
                # Calculate next buy from GridCalculator logic
                if positions:  # Use already-filtered positions
                    lowest_entry = min(p['entry_price'] for p in positions)
                    
                    # If market is above lowest entry, next buy should be below it
                    # If market is below lowest entry, we might be at capacity or need different logic
                    if current_market_price >= lowest_entry:
                        expected_pending_price = lowest_entry - grid_step
                    else:
                        # Market dropped below our positions, next buy should be near market
                        # Find grid level below current price
                        levels_from_ref = int((grid_ref - current_market_price) / grid_step)
                        expected_pending_price = grid_ref - (levels_from_ref + 1) * grid_step
                else:
                    # No valid positions - first buy should be below current market price
                    # Use current market price instead of ref for more accurate prediction
                    if current_market_price < grid_ref:
                        # Market is below ref, place buy below current market price
                        expected_pending_price = current_market_price - grid_step
                    else:
                        # Market is at/above ref, place buy at ref - step
                        expected_pending_price = grid_ref - grid_step
            else:  # SHORT
                if positions:  # Use already-filtered positions
                    highest_entry = max(p['entry_price'] for p in positions)
                    
                    if current_market_price <= highest_entry:
                        expected_pending_price = highest_entry + grid_step
                    else:
                        levels_from_ref = int((current_market_price - grid_ref) / grid_step)
                        expected_pending_price = grid_ref + (levels_from_ref + 1) * grid_step
                else:
                    # No valid positions - first sell should be above current market price
                    # Use current market price instead of ref for more accurate prediction
                    if current_market_price > grid_ref:
                        # Market is above ref, place sell above current market price
                        expected_pending_price = current_market_price + grid_step
                    else:
                        # Market is at/below ref, place sell at ref + step
                        expected_pending_price = grid_ref + grid_step
            
            # Check for missing pending order (manual cancellation)
            if expected_pending_price and len(positions) < max_open:
                actual_pending = pending_buy if mode == 'LONG' else pending_sell
                
                if not actual_pending:
                    warnings.append({
                        'type': 'MISSING_PENDING_ORDER',
                        'severity': 'error',
                        'message': f'🚨 Expected pending {mode} order @ ${expected_pending_price:,.0f} is MISSING!',
                        'details': f'Database shows no pending {mode.lower()} order, but one should exist. This indicates manual cancellation or bot error.',
                        'action': f'Bot will recreate order on next heartbeat cycle (every {heartbeat_seconds}s). If issue persists, check bot logs.',
                        'timestamp': datetime.now().isoformat()
                    })
                elif abs(actual_pending.get('price', 0) - expected_pending_price) > tick_size:
                    warnings.append({
                        'type': 'WRONG_PENDING_PRICE',
                        'severity': 'warning',
                        'message': f'⚠️ Pending {mode} @ ${actual_pending.get("price"):,.0f} differs from expected ${expected_pending_price:,.0f}',
                        'details': f'Price difference: ${abs(actual_pending.get("price", 0) - expected_pending_price):,.2f}',
                        'action': 'Verify grid configuration matches bot state',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # CRITICAL FIX: positions are already filtered by bot_state_reader
            # No need to create valid_positions - just use positions directly
            
            # VERIFY PENDING ORDERS EXIST ON EXCHANGE (Fix Issue #3)
            # If bot state shows pending order but exchange doesn't have it,
            # the order was manually cancelled - predict as if no pending exists
            verified_pending_buy = None
            verified_pending_sell = None
            
            try:
                # Import here to avoid circular dependency
                from bot.api.async_delta_client import AsyncDeltaClient
                import asyncio
                
                async def verify_pending_orders():
                    """Check if pending orders actually exist on exchange"""
                    nonlocal verified_pending_buy, verified_pending_sell
                    
                    try:
                        client = AsyncDeltaClient()
                        exchange_orders = await client.get_open_orders(product_id=int(product_id))
                        await client.close()
                        
                        # Check if our pending orders exist
                        if pending_buy:
                            order_id = pending_buy.get('order_id')
                            if any(o.get('id') == order_id for o in exchange_orders):
                                verified_pending_buy = pending_buy
                            else:
                                log.warning(f"[PREDICTION] Pending BUY {order_id} not found on exchange - order was cancelled")
                        
                        if pending_sell:
                            order_id = pending_sell.get('order_id')
                            if any(o.get('id') == order_id for o in exchange_orders):
                                verified_pending_sell = pending_sell
                            else:
                                log.warning(f"[PREDICTION] Pending SELL {order_id} not found on exchange - order was cancelled")
                    
                    except Exception as e:
                        log.error(f"[PREDICTION] Failed to verify pending orders: {e}")
                        # On error, trust bot state
                        verified_pending_buy = pending_buy
                        verified_pending_sell = pending_sell
                
                # Run async verification cooperatively — avoid loop.run_until_complete()
                # which blocks the single eventlet worker for the full API call duration.
                try:
                    import eventlet.tpool

                    def _verify_worker():
                        import asyncio as _asyncio
                        _loop = _asyncio.DefaultEventLoopPolicy().new_event_loop()
                        _asyncio.set_event_loop(_loop)
                        try:
                            return _loop.run_until_complete(verify_pending_orders())
                        finally:
                            _loop.close()
                            _asyncio.set_event_loop(None)

                    eventlet.tpool.execute(_verify_worker)
                except Exception as _tp_err:
                    log.debug(f"[PREDICTION] tpool verification error: {_tp_err}")
                    verified_pending_buy = pending_buy
                    verified_pending_sell = pending_sell
            
            except Exception as e:
                log.error(f"[PREDICTION] Exchange verification failed: {e}")
                # Fallback to bot state
                verified_pending_buy = pending_buy
                verified_pending_sell = pending_sell
            
            # Predict next action with VERIFIED pending orders
            next_action = predictor.predict_next_action(
                current_price=current_price,
                positions=positions,  # Already filtered!
                pending_buy=verified_pending_buy,
                pending_sell=verified_pending_sell
            )
            
            # Predict scenarios with VERIFIED pending orders
            scenarios = {}
            if next_action['type'] in ['PENDING_BUY', 'WILL_BUY']:
                fill_price = next_action.get('price')
                if fill_price:
                    scenarios['if_pending_fills'] = predictor.predict_fill_scenario(
                        fill_price=fill_price,
                        fill_type='BUY',
                        positions=positions,  # Already filtered!
                        pending_buy=verified_pending_buy
                    )
            
            if positions:  # Already filtered!
                for pos in positions:  # Already filtered!
                    tp_price = pos.get('tp_price')
                    if tp_price:
                        scenarios['if_tp_fills'] = predictor.predict_fill_scenario(
                            fill_price=tp_price,
                            fill_type='SELL',
                            positions=positions,  # Already filtered!
                            pending_buy=verified_pending_buy
                        )
                        break
            
            # Get full sequence with VERIFIED pending orders
            full_sequence = predictor.predict_sequence(
                current_price=current_price,
                positions=positions,  # Already filtered!
                pending_buy=verified_pending_buy,
                num_steps=5
            )
            
            return jsonify({
                'active': True,
                'source': 'sql_database',
                'current_state': {
                    'price': current_price,
                    'mode': mode,
                    'positions': len(positions),  # Already filtered count!
                    'max_positions': max_open,
                    'pending_buy': verified_pending_buy,  # Exchange-verified!
                    'pending_sell': verified_pending_sell  # Exchange-verified!
                },
                'next_action': next_action,
                'scenarios': scenarios,
                'full_sequence': full_sequence,
                'grid_config': {
                    'lower': grid_lower,
                    'upper': grid_upper,
                    'step': grid_step,
                    'ref': grid_ref
                },
                'warnings': warnings if warnings else None,
                'timestamp': datetime.now().isoformat()
            }), 200
        
        # Fallback: compute from live bot state OR config file
        if not _bot_instance:
            # Try to read from config.yaml if bot not running
            try:
                from webui.backend.utils.bot_prediction_engine import BotPredictionEngine
                
                grid_lower = get_config_value('grid.geometry.lower', 'GRID_LOWER', 90000)
                grid_upper = get_config_value('grid.geometry.upper', 'GRID_UPPER', 110000)
                grid_step = get_config_value('grid.geometry.step', 'GRID_STEP', 500)
                grid_ref = get_config_value('grid.geometry.reference', 'GRID_REF', 95500)
                mode = get_config_value('bot.mode', 'BOT_MODE', 'LONG')
                max_open = get_config_value('grid.limits.max_open_positions', 'MAX_OPEN_POSITIONS', 10)
                
                # Create prediction engine from config
                predictor = BotPredictionEngine(
                    grid_lower=grid_lower,
                    grid_upper=grid_upper,
                    grid_step=grid_step,
                    grid_ref=grid_ref,
                    mode=mode,
                    max_open=max_open,
                    tick_size=0.5
                )
                
                # Get current price from market (if available)
                current_price = grid_ref  # Use ref as fallback
                
                # Predict with empty positions (bot not running)
                next_action = predictor.predict_next_action(
                    current_price=current_price,
                    positions=[],
                    pending_buy=None,
                    pending_sell=None
                )
                
                return jsonify({
                    'active': False,
                    'current_state': {
                        'price': current_price,
                        'mode': mode,
                        'positions': 0,
                        'max_positions': max_open,
                        'pending_buy': None,
                        'pending_sell': None
                    },
                    'next_action': next_action,
                    'scenarios': {},
                    'grid_config': {
                        'lower': grid_lower,
                        'upper': grid_upper,
                        'step': grid_step,
                        'ref': grid_ref
                    },
                    'warning': 'Bot not running - predictions based on config.yaml',
                    'timestamp': datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                log.error(f"Error reading config for predictions: {e}")
                return jsonify({
                    'error': 'Bot not running - cannot generate predictions',
                    'next_action': None
                }), 503
        
        # Import prediction engine
        from webui.backend.utils.bot_prediction_engine import BotPredictionEngine
        
        # Get bot state
        current_price = getattr(_bot_instance, 'current_price', None)
        grid_mode = getattr(_bot_instance, 'grid_mode', 'LONG')
        
        # Get grid config
        grid_calc = getattr(_bot_instance, 'grid_calc', None)
        if not grid_calc:
            return jsonify({'error': 'Grid calculator not available'}), 503
        
        # Get positions and pending orders
        positions = _bot_instance.position_mgr.get_positions() if hasattr(_bot_instance, 'position_mgr') else []
        
        # Get pending orders from state
        state = {}
        if hasattr(_bot_instance, 'position_mgr'):
            state_response = _bot_instance.position_mgr.get_state()
            state = state_response if isinstance(state_response, dict) else {}
        
        pending_buy = state.get('pending_buy')
        pending_sell = state.get('pending_sell')
        max_open = getattr(_bot_instance, 'max_open', 10)
        
        # Check for manual cancellation warning
        # Compare bot's internal state with what should exist
        warnings = []
        
        # Calculate what pending order SHOULD exist based on current state
        expected_pending_price = None
        if grid_mode == 'LONG':
            expected_pending_price = grid_calc.compute_next_buy_level(positions, current_price)
        else:
            expected_pending_price = grid_calc.compute_next_sell_level(positions, current_price)
        
        # Check if expected pending order is missing from bot state
        if expected_pending_price:
            actual_pending = pending_buy if grid_mode == 'LONG' else pending_sell
            
            # Case 1: No pending order in bot state but one should exist
            if not actual_pending:
                warnings.append({
                    'type': 'MISSING_PENDING_ORDER',
                    'severity': 'error',
                    'message': f'🚨 Expected pending {grid_mode} order @ ${expected_pending_price:,.0f} is MISSING!',
                    'details': f'Bot state shows no pending {grid_mode.lower()} order, but one should exist at ${expected_pending_price:,.0f}. This may indicate manual cancellation or a bot error.',
                    'action': f'Bot will attempt to recreate the order on next heartbeat cycle (every {getattr(_bot_instance, "heartbeat_seconds", 20)}s). If issue persists, restart bot.',
                    'timestamp': datetime.now().isoformat()
                })
            # Case 2: Pending order exists but at significantly wrong price (>1 tick difference)
            elif actual_pending.get('price') and abs(actual_pending.get('price', 0) - expected_pending_price) > grid_calc.tick_size:
                warnings.append({
                    'type': 'WRONG_PENDING_PRICE',
                    'severity': 'warning',
                    'message': f'⚠️ Pending {grid_mode} order @ ${actual_pending.get("price"):,.0f} differs from expected ${expected_pending_price:,.0f}',
                    'details': f'Price difference: ${abs(actual_pending.get("price", 0) - expected_pending_price):,.2f}. Grid configuration may have changed, or order was manually modified.',
                    'action': 'Verify grid configuration in config.yaml matches bot state. Bot may auto-correct on next cycle.',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Case 3: Check if bot state has pending order but it shouldn't (capacity full)
        if len(positions) >= max_open:
            actual_pending = pending_buy if grid_mode == 'LONG' else pending_sell
            if actual_pending:
                warnings.append({
                    'type': 'UNEXPECTED_PENDING_ORDER',
                    'severity': 'warning',
                    'message': f'⚠️ Pending {grid_mode} order exists but capacity is full ({len(positions)}/{max_open})',
                    'details': f'Bot has pending order @ ${actual_pending.get("price"):,.0f} but all position slots are occupied.',
                    'action': 'This is unusual. Wait for a position to close (TP fill) or check bot logic.',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Create prediction engine
        predictor = BotPredictionEngine(
            grid_lower=grid_calc.lower,
            grid_upper=grid_calc.upper,
            grid_step=grid_calc.step,
            grid_ref=grid_calc.ref,
            mode=grid_mode,
            max_open=max_open,
            tick_size=grid_calc.tick_size
        )
        
        # Predict next action
        next_action = predictor.predict_next_action(
            current_price=current_price,
            positions=positions,
            pending_buy=pending_buy,
            pending_sell=pending_sell
        )
        
        # Predict scenarios
        scenarios = {}
        
        # Scenario 1: If pending order fills
        if next_action['type'] in ['PENDING_BUY', 'WILL_BUY']:
            fill_price = next_action.get('price')
            if fill_price:
                scenarios['if_pending_fills'] = predictor.predict_fill_scenario(
                    fill_price=fill_price,
                    fill_type='BUY',
                    positions=positions,
                    pending_buy=pending_buy
                )
        
        # Scenario 2: If TP fills
        if positions:
            # Get highest TP (most likely to fill in rising market)
            for pos in positions:
                tp_price = pos.get('tp_price')
                if tp_price:
                    scenarios['if_tp_fills'] = predictor.predict_fill_scenario(
                        fill_price=tp_price,
                        fill_type='SELL',
                        positions=positions,
                        pending_buy=pending_buy
                    )
                    break  # Just show first scenario
        
        # Get full sequence
        full_sequence = predictor.predict_sequence(
            current_price=current_price,
            positions=positions,
            pending_buy=pending_buy,
            num_steps=5
        )
        
        return jsonify({
            'active': True,
            'current_state': {
                'price': current_price,
                'mode': grid_mode,
                'positions': len(positions),
                'max_positions': max_open,
                'pending_buy': pending_buy,
                'pending_sell': pending_sell
            },
            'next_action': next_action,
            'scenarios': scenarios,
            'full_sequence': full_sequence,
            'grid_config': {
                'lower': grid_calc.lower,
                'upper': grid_calc.upper,
                'step': grid_calc.step,
                'ref': grid_calc.ref
            },
            'warnings': warnings,  # Add warnings array
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error generating advanced predictions: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/trading-condition', methods=['GET'])
def trading_condition():
    """
    Get trading condition status from guarding bot features
    
    Returns comprehensive view of all safety checks, blockers, and guardian status.
    Shows what's blocking or allowing trading.
    
    Example:
        GET /api/monitoring/trading-condition
        Response: {
            "trading_allowed": true,
            "total_blockers": 0,
            "critical_blockers": [],
            "warning_blockers": [],
            "safety_config": {
                "execute_orders": true,
                "trading_mode": "demo",
                "guardian_enabled": true
            },
            "guardian_status": {
                "running": true,
                "risk_level": "safe"
            }
        }
    """
    try:
        # Get symbol from query params (v5.0 multi-symbol support)
        symbol = request.args.get('symbol', None)
        mode = request.args.get('mode', None)
        
        # Try snapshot file first
        snapshot = _load_monitoring_snapshot(symbol, mode)
        if snapshot and 'trading_condition' in snapshot.get('layers', {}):
            data = snapshot['layers']['trading_condition']
            data['symbol'] = snapshot.get('symbol', symbol or 'BTCUSD')
            data['mode'] = snapshot.get('mode', mode or 'LONG')
            return jsonify(data), 200
        
        # Fallback: compute directly from blocker tracker
        from bot.safety.blocker_tracker import get_blocker_tracker
        
        tracker = get_blocker_tracker()
        blocker_data = tracker.check_all_blockers()
        
        # Categorize blockers
        critical_blockers = []
        warning_blockers = []
        info_blockers = []
        
        for blocker in blocker_data.get('blockers', []):
            if not blocker.get('active'):
                continue
            
            severity = blocker.get('severity', 'info')
            blocker_info = {
                'name': blocker.get('name', 'Unknown'),
                'category': blocker.get('category', 'UNKNOWN'),
                'message': blocker.get('message', ''),
                'details': blocker.get('details', {})
            }
            
            if severity == 'critical':
                critical_blockers.append(blocker_info)
            elif severity == 'warning':
                warning_blockers.append(blocker_info)
            else:
                info_blockers.append(blocker_info)
        
        # Get safety config
        safety_config = {
            'execute_orders': get_config_value('safety.execute_orders', 'EXECUTE_ORDERS', False),
            'trading_mode': get_config_value('trading_mode', 'TRADING_MODE', 'demo'),
            'guardian_enabled': get_config_value('guardian.enabled', 'GUARDIAN_ENABLED', True),
            'volatility_safety': get_config_value('safety.volatility.enabled', 'VOLATILITY_SAFETY_ENABLED', True),
            'liquidation_protection': get_config_value('liquidation_protection.enabled', 'LIQUIDATION_PROTECTION_ENABLED', True),
            'drawdown_cap': get_config_value('capital_protection.drawdown_cap.enabled', 'DRAWDOWN_CAP_ENABLED', True),
            'order_confirmation': get_config_value('safety.confirmation_guard.enabled', 'ORDER_CONFIRMATION_GUARD_ENABLED', True)
        }
        
        # Get guardian status
        guardian_status = {'running': False}
        try:
            guardian_health_file = BASE_DIR / 'bot' / 'guardian' / '.guardian_health.json'
            if guardian_health_file.exists():
                import time
                with open(guardian_health_file, 'r') as f:
                    health_data = json.load(f)
                
                last_check = health_data.get('last_check_timestamp', 0)
                is_active = (time.time() - last_check) < 60
                
                guardian_status = {
                    'running': is_active,
                    'last_check': health_data.get('last_check_time'),
                    'risk_level': health_data.get('risk_level', 'unknown'),
                    'total_positions': health_data.get('total_positions', 0),
                    'total_loss_inr': health_data.get('total_loss_inr', 0)
                }
        except Exception as e:
            log.debug(f"Could not get guardian status: {e}")
        
        return jsonify({
            'active': True,
            'trading_allowed': blocker_data.get('trading_allowed', False),
            'total_blockers': blocker_data.get('total_blockers', 0),
            'critical_blockers': critical_blockers,
            'warning_blockers': warning_blockers,
            'info_blockers': info_blockers,
            'safety_config': safety_config,
            'guardian_status': guardian_status,
            'timestamp': blocker_data.get('timestamp', datetime.now().isoformat())
        }), 200
        
    except Exception as e:
        log.error(f"Error getting trading condition: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/opportunistic-recovery', methods=['GET'])
def opportunistic_recovery():
    """
    Get opportunistic recovery statistics
    
    Returns:
        Recovery statistics including total recoveries, positions, and capital saved
    
    Example:
        GET /api/monitoring/opportunistic-recovery
        Response: {
            "enabled": true,
            "total_recoveries": 5,
            "total_positions_recovered": 12,
            "total_capital_saved": 15750.0,
            "startup_recoveries": 3,
            "volatility_recoveries": 2,
            "last_recovery_time": "2025-11-16T10:30:00",
            "recent_recoveries": [...]
        }
    """
    try:
        # Check if opportunistic recovery is enabled in config
        recovery_enabled = get_config_value('safety.volatility.opportunistic_recovery.enabled', default=False)
        
        # Try to get stats from bot instance
        if _bot_instance and hasattr(_bot_instance, 'position_actor'):
            try:
                import asyncio
                import eventlet.tpool

                _coro_stats = _bot_instance.position_actor.ask("GET_STATE", {}, timeout=3.0)

                def _state_worker():
                    _loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
                    asyncio.set_event_loop(_loop)
                    try:
                        return _loop.run_until_complete(_coro_stats)
                    finally:
                        _loop.close()
                        asyncio.set_event_loop(None)

                state = eventlet.tpool.execute(_state_worker)

                stats = state.get("opportunistic_recovery_stats", {})
                
                # Get recent recoveries from EventStore if available
                recent_recoveries = []
                if hasattr(_bot_instance, 'event_store'):
                    try:
                        # Query last 10 recovery events from SQL
                        events = _bot_instance.event_store.get_events_by_type(
                            "opportunistic_recovery_started",
                            limit=10
                        )
                        recent_recoveries = [
                            {
                                "timestamp": datetime.fromtimestamp(e.timestamp).isoformat(),
                                "recovery_type": e.data.get("recovery_type"),
                                "correlation_id": e.correlation_id
                            }
                            for e in events
                        ]
                    except Exception as e:
                        log.debug(f"Could not fetch recent recoveries: {e}")
                
                return jsonify({
                    "enabled": recovery_enabled,
                    "total_recoveries": stats.get("total_recoveries", 0),
                    "total_positions_recovered": stats.get("total_positions_recovered", 0),
                    "total_capital_saved": stats.get("total_capital_saved", 0.0),
                    "startup_recoveries": stats.get("startup_recoveries", 0),
                    "volatility_recoveries": stats.get("volatility_recoveries", 0),
                    "last_recovery_time": datetime.fromtimestamp(stats["last_recovery_time"]).isoformat() if stats.get("last_recovery_time") else None,
                    "recent_recoveries": recent_recoveries,
                    "timestamp": datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                log.error(f"Error getting stats from bot: {e}")
        
        # Fallback to zero stats if bot not available
        return jsonify({
            "enabled": recovery_enabled,
            "total_recoveries": 0,
            "total_positions_recovered": 0,
            "total_capital_saved": 0.0,
            "startup_recoveries": 0,
            "volatility_recoveries": 0,
            "last_recovery_time": None,
            "recent_recoveries": [],
            "bot_available": False,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting opportunistic recovery stats: {e}")
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/api/monitoring/opportunistic-positions', methods=['GET'])
def opportunistic_positions():
    """
    Get list of current opportunistic recovery positions
    
    Returns:
        List of positions that were opened via opportunistic recovery
    
    Example:
        GET /api/monitoring/opportunistic-positions
        Response: {
            "positions": [
                {
                    "position_id": "123456789",
                    "grid_entry": 109000,
                    "actual_entry": 106500,
                    "saved_capital": 2500,
                    "tp_price": 110000,
                    "size": 2,
                    "timestamp": "2025-11-16T10:30:00"
                }
            ],
            "total_positions": 1,
            "total_saved": 2500.0
        }
    """
    try:
        if _bot_instance and hasattr(_bot_instance, 'position_actor'):
            try:
                import asyncio
                import eventlet.tpool

                coro2 = _bot_instance.position_actor.ask("GET_STATE", {}, timeout=3.0)

                def _worker2():
                    _loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
                    asyncio.set_event_loop(_loop)
                    try:
                        return _loop.run_until_complete(coro2)
                    finally:
                        _loop.close()
                        asyncio.set_event_loop(None)

                state = eventlet.tpool.execute(_worker2)
                all_positions = state.get("open_tranches", [])
                opp_positions = [
                    {
                        "position_id": p.get("position_id"),
                        "grid_entry": p.get("entry_price"),
                        "actual_entry": p.get("actual_entry", p.get("entry_price")),
                        "saved_capital": p.get("saved_capital", 0),
                        "tp_price": p.get("tp_price"),
                        "size": p.get("size"),
                        "timestamp": datetime.fromtimestamp(p.get("timestamp", 0)).isoformat() if p.get("timestamp") else None
                    }
                    for p in all_positions
                    if p.get("is_opportunistic", False)
                ]
                
                total_saved = sum(p["saved_capital"] for p in opp_positions)
                
                return jsonify({
                    "positions": opp_positions,
                    "total_positions": len(opp_positions),
                    "total_saved": total_saved,
                    "timestamp": datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                log.error(f"Error getting opportunistic positions from bot: {e}")
        
        # Fallback to empty if bot not available
        return jsonify({
            "positions": [],
            "total_positions": 0,
            "total_saved": 0.0,
            "bot_available": False,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        log.error(f"Error getting opportunistic positions: {e}")
        return jsonify({'error': str(e)}), 500


# Export blueprint
__all__ = ['monitoring_bp', 'set_bot_instance']
