"""
Mode Switcher API Routes - Phase 3
WebUI endpoints for auto LONG/SHORT mode switching
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

mode_switcher_bp = Blueprint('mode_switcher', __name__)


# Lazy import to avoid circular dependencies
def get_services():
    """Get market monitor and mode switcher services"""
    try:
        from bot.market_monitor import get_market_monitor, get_mode_switcher
        return get_market_monitor(), get_mode_switcher()
    except ImportError as e:
        logger.error(f"Failed to import market monitor services: {e}")
        return None, None


@mode_switcher_bp.route('/status', methods=['GET'])
def get_status():
    """Get current mode switcher status"""
    try:
        market_monitor, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({
                'error': 'Mode switcher not available',
                'enabled': False
            }), 503
        
        # Get market snapshot
        market_snapshot = None
        if market_monitor:
            market_snapshot = market_monitor.get_state()
        
        # Get switcher state
        switcher_state = mode_switcher.get_state()
        
        return jsonify({
            'status': 'success',
            'mode_switcher': switcher_state,
            'market': market_snapshot,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting mode switcher status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/enable', methods=['POST'])
def enable_switcher():
    """Enable auto mode switching"""
    try:
        _, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({'error': 'Mode switcher not available'}), 503
        
        import asyncio
        
        # Start switcher if not running
        if not mode_switcher._running:
            loop = asyncio.get_event_loop()
            loop.create_task(mode_switcher.start())
        
        return jsonify({
            'status': 'success',
            'message': 'Mode switcher enabled',
            'state': mode_switcher.get_state()
        })
        
    except Exception as e:
        logger.error(f"Error enabling mode switcher: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/disable', methods=['POST'])
def disable_switcher():
    """Disable auto mode switching"""
    try:
        _, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({'error': 'Mode switcher not available'}), 503
        
        import asyncio
        
        # Stop switcher
        if mode_switcher._running:
            loop = asyncio.get_event_loop()
            loop.create_task(mode_switcher.stop())
        
        return jsonify({
            'status': 'success',
            'message': 'Mode switcher disabled',
            'state': mode_switcher.get_state()
        })
        
    except Exception as e:
        logger.error(f"Error disabling mode switcher: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/configure', methods=['POST'])
def configure():
    """Update mode switcher configuration"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No configuration provided'}), 400
        
        _, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({'error': 'Mode switcher not available'}), 503
        
        # Update configuration
        if 'reference_price' in data:
            mode_switcher.update_reference_price(float(data['reference_price']))
        
        if 'hysteresis' in data:
            mode_switcher.update_hysteresis(float(data['hysteresis']))
        
        if 'switch_delay' in data:
            mode_switcher.switch_delay = int(data['switch_delay'])
        
        if 'long_strategy' in data:
            mode_switcher.long_strategy = data['long_strategy']
        
        if 'short_strategy' in data:
            mode_switcher.short_strategy = data['short_strategy']
        
        return jsonify({
            'status': 'success',
            'message': 'Configuration updated',
            'state': mode_switcher.get_state()
        })
        
    except Exception as e:
        logger.error(f"Error configuring mode switcher: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/manual-override', methods=['POST'])
def manual_override():
    """Set manual mode override"""
    try:
        data = request.get_json()
        
        if not data or 'mode' not in data:
            return jsonify({'error': 'Mode not specified'}), 400
        
        mode = data['mode'].upper()
        if mode not in ['LONG', 'SHORT', 'AUTO']:
            return jsonify({'error': 'Invalid mode. Must be LONG, SHORT, or AUTO'}), 400
        
        _, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({'error': 'Mode switcher not available'}), 503
        
        duration_hours = data.get('duration_hours')
        reason = data.get('reason', 'Manual override from WebUI')
        
        mode_switcher.set_manual_override(mode, duration_hours, reason)
        
        return jsonify({
            'status': 'success',
            'message': f'Manual override set to {mode}',
            'state': mode_switcher.get_state()
        })
        
    except Exception as e:
        logger.error(f"Error setting manual override: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/history', methods=['GET'])
def get_history():
    """Get mode switch history"""
    try:
        hours = request.args.get('hours', default=24, type=int)
        
        _, mode_switcher = get_services()
        
        if not mode_switcher:
            return jsonify({'error': 'Mode switcher not available'}), 503
        
        history = mode_switcher.get_history(hours)
        
        return jsonify({
            'status': 'success',
            'switches': history,
            'count': len(history),
            'hours': hours
        })
        
    except Exception as e:
        logger.error(f"Error getting switch history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@mode_switcher_bp.route('/market-snapshot', methods=['GET'])
def get_market_snapshot():
    """Get current market snapshot"""
    try:
        market_monitor, _ = get_services()
        
        if not market_monitor:
            return jsonify({'error': 'Market monitor not available'}), 503
        
        snapshot = market_monitor.get_snapshot()
        
        return jsonify({
            'status': 'success',
            'snapshot': {
                'timestamp': snapshot.timestamp,
                'current_price': snapshot.current_price,
                'reference_price': snapshot.reference_price,
                'volatility': snapshot.volatility,
                'trend': snapshot.trend,
                'regime': snapshot.regime,
                'rsi': snapshot.rsi
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting market snapshot: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


print("✓ Mode Switcher API routes registered")
