"""
Volatility Chart API Endpoints

Professional IV vs RV chart API endpoints for Flask integration.
Add these routes to app.py to enable the volatility chart system.

Usage:
    from volatility_chart_api import register_volatility_chart_api
    register_volatility_chart_api(app, socketio)
"""

from flask import jsonify, request
from typing import Any, Dict
import logging
import time

log = logging.getLogger("volatility_chart_api")


def register_volatility_chart_api(app, socketio):
    """
    Register volatility chart API endpoints with Flask app.
    
    Args:
        app: Flask application instance
        socketio: SocketIO instance for WebSocket support
    """
    
    @app.route('/api/risk/volatility/historical', methods=['GET'])
    def get_volatility_historical():
        """
        Get historical IV/RV data for charting.
        
        Query Parameters:
            timeframe: 'daily' | 'weekly' | 'monthly' (default: 'daily')
            limit: Maximum number of data points (default: 100, max: 500)
        
        Returns:
            JSON with arrays of IV and RV data points
        """
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            
            timeframe = (request.args.get('timeframe', 'daily') or 'daily').lower()
            try:
                limit = int(request.args.get('limit', 100) or 100)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'Invalid limit. Must be an integer.'
                }), 400
            limit = max(1, min(limit, 500))
            
            # Validate timeframe
            if timeframe not in ['daily', 'weekly', 'monthly']:
                return jsonify({
                    'success': False,
                    'error': 'Invalid timeframe. Must be daily, weekly, or monthly'
                }), 400
            
            collector = get_collector()
            data = collector.get_historical_data(timeframe=timeframe, limit=limit)
            
            return jsonify({
                'success': True,
                'data': data,
                'timeframe': timeframe,
                'count': {
                    'iv': len(data.get('iv', [])),
                    'rv': len(data.get('rv', []))
                }
            })
            
        except Exception as e:
            log.error(f"Failed to get historical volatility data: {e}", exc_info=True)
            status_code = getattr(e, 'code', 500)
            return jsonify({
                'success': False,
                'error': str(e),
                'data': {'iv': [], 'rv': []}
            }), status_code
    
    
    @app.route('/api/risk/volatility/latest', methods=['GET'])
    def get_volatility_latest():
        """
        Get latest IV and RV values.
        
        Returns:
            JSON with latest IV and RV values and timestamps
        """
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            
            collector = get_collector()
            latest = collector.get_latest_values()
            
            return jsonify({
                'success': True,
                'data': latest,
                'timestamp': int(time.time() * 1000)
            })
            
        except Exception as e:
            log.error(f"Failed to get latest volatility values: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e),
                'data': {'iv': None, 'rv': {}}
            }), 500
    
    
    @app.route('/api/risk/volatility/stats', methods=['GET'])
    def get_volatility_stats():
        """
        Get volatility statistics and thresholds.
        
        Returns:
            JSON with volatility statistics, thresholds, and safety status
        """
        try:
            from bot.volatility.iv_rv_tracker import get_volatility_tracker
            from bot.volatility.delta_volatility_collector import get_collector
            
            # Get current status from tracker
            tracker = get_volatility_tracker()
            tracker_status = tracker.get_status()
            
            # Get latest values from collector
            collector = get_collector()
            latest = collector.get_latest_values()
            
            return jsonify({
                'success': True,
                'data': {
                    'current': {
                        'iv': tracker_status.get('iv'),
                        'rv': tracker_status.get('rv'),
                        'spread': tracker_status.get('spread')
                    },
                    'latest': latest,
                    'thresholds': tracker_status.get('thresholds', {}),
                    'safety': {
                        'is_safe': tracker_status.get('is_safe', True),
                        'violation_reason': tracker_status.get('violation_reason')
                    },
                    'last_update': tracker_status.get('last_update')
                }
            })
            
        except Exception as e:
            log.error(f"Failed to get volatility stats: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    
    # WebSocket event for real-time volatility updates
    @socketio.on('subscribe_volatility')
    def handle_volatility_subscription():
        """Handle client subscription to real-time volatility updates"""
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            
            log.info("Client subscribed to volatility updates")
            
            # Send initial data
            collector = get_collector()
            latest = collector.get_latest_values()
            
            socketio.emit('volatility_update', {
                'success': True,
                'data': latest,
                'timestamp': int(time.time() * 1000)
            })
            
        except Exception as e:
            log.error(f"Volatility subscription error: {e}")
            socketio.emit('volatility_update', {
                'success': False,
                'error': str(e)
            })
    
    
    @socketio.on('unsubscribe_volatility')
    def handle_volatility_unsubscription():
        """Handle client unsubscription from volatility updates"""
        log.info("Client unsubscribed from volatility updates")
    
    
    def emit_volatility_update():
        """
        Emit volatility update to all connected clients.
        Call this from the collector when new data is available.
        """
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            
            collector = get_collector()
            latest = collector.get_latest_values()
            
            socketio.emit('volatility_update', {
                'success': True,
                'data': latest,
                'timestamp': int(time.time() * 1000)
            })
            
        except Exception as e:
            log.error(f"Failed to emit volatility update: {e}")
    
    
    # Store emit function for collector to call
    app.config['emit_volatility_update'] = emit_volatility_update

    # Configure collector callback for real-time updates
    try:
        from bot.volatility.delta_volatility_collector import get_collector

        collector = get_collector()
        if hasattr(collector, 'set_emit_callback'):
            collector.set_emit_callback(emit_volatility_update)
            log.info("🔌 Volatility collector hooked into SocketIO broadcaster")
    except Exception as callback_error:
        log.warning(f"⚠️  Could not attach volatility emitter callback: {callback_error}")
    
    log.info("✅ Volatility chart API endpoints registered")
    log.info("   - GET /api/risk/volatility/historical")
    log.info("   - GET /api/risk/volatility/latest")
    log.info("   - GET /api/risk/volatility/stats")
    log.info("   - WebSocket: subscribe_volatility / unsubscribe_volatility")
