"""
TradingView Webhook Integration
Receives buy/sell signals from TradingView Pine Script alerts via webhooks
"""
from flask import Blueprint, request, jsonify
import logging
import hmac
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys

# Setup paths
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from db.tradingview_signals_db import TradingViewSignalsDB, init_tradingview_signals_db

logger = logging.getLogger(__name__)

tradingview_bp = Blueprint('tradingview', __name__, url_prefix='/api/tradingview')

# SocketIO instance will be set via init_tradingview_socketio()
_socketio = None

def init_tradingview_socketio(socketio):
    """Initialize SocketIO for TradingView signal broadcasting."""
    global _socketio
    _socketio = socketio
    logger.info("✅ TradingView WebSocket broadcasting enabled")

# Initialize database on module load
init_tradingview_signals_db()

# Security: Optional webhook secret for signature verification
WEBHOOK_SECRET = None  # Set this in your environment or config

def verify_signature(payload: str, signature: str) -> bool:
    """Verify TradingView webhook signature (if configured)."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    
    computed = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed, signature)


@tradingview_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Receive TradingView webhook alerts.
    
    Expected JSON payload from TradingView alert:
    {
        "symbol": "BTCUSD",
        "action": "buy" or "sell",
        "price": 50000.00,
        "timestamp": "2026-02-03T10:30:00Z",
        "strategy": "RSI_Strategy",
        "timeframe": "15m",
        "message": "Strong buy signal",
        "metadata": {
            "rsi": 25.5,
            "volume": 1234.56,
            ... additional indicators
        }
    }
    
    TradingView Pine Script example:
    alertcondition(buySignal, title="Buy Signal", 
        message='{"symbol": "{{ticker}}", "action": "buy", "price": {{close}}, 
                 "timestamp": "{{timenow}}", "strategy": "MyStrategy", 
                 "timeframe": "{{interval}}", "message": "Buy signal triggered"}')
    """
    try:
        # Verify signature if configured
        signature = request.headers.get('X-TradingView-Signature')
        if WEBHOOK_SECRET and signature:
            payload = request.get_data(as_text=True)
            if not verify_signature(payload, signature):
                logger.warning("Invalid webhook signature")
                return jsonify({
                    'success': False,
                    'error': 'Invalid signature'
                }), 401
        
        # Parse webhook data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON payload received'
            }), 400
        
        # Extract required fields
        symbol = data.get('symbol', 'UNKNOWN')
        action = data.get('action', '').lower()
        price = float(data.get('price', 0))
        strategy = data.get('strategy', 'Unknown')
        timeframe = data.get('timeframe', 'Unknown')
        message = data.get('message', '')
        metadata = data.get('metadata', {})
        
        # Validate action
        if action not in ['buy', 'sell', 'close', 'long', 'short']:
            return jsonify({
                'success': False,
                'error': f'Invalid action: {action}. Must be buy, sell, close, long, or short'
            }), 400
        
        # Normalize action to buy/sell
        if action == 'long':
            action = 'buy'
        elif action == 'short':
            action = 'sell'
        
        # Store signal in database
        signal = TradingViewSignalsDB.create_signal(
            symbol=symbol,
            action=action,
            price=price,
            strategy=strategy,
            timeframe=timeframe,
            message=message,
            metadata=metadata,
            source_ip=request.remote_addr
        )
        
        logger.info(f"📊 TradingView {action.upper()} signal received: {symbol} @ ${price:,.2f} ({strategy}/{timeframe})")
        
        # Broadcast signal via WebSocket for real-time UI updates
        if _socketio:
            try:
                _socketio.emit('tradingview_signal', {
                    'id': signal['id'],
                    'symbol': signal['symbol'],
                    'action': signal['action'],
                    'price': signal['price'],
                    'strategy': signal['strategy'],
                    'timeframe': signal['timeframe'],
                    'message': signal['message'],
                    'created_at': signal['created_at']
                })
                logger.info(f"✅ Signal broadcasted via WebSocket")
            except Exception as e:
                logger.error(f"Failed to broadcast signal via WebSocket: {e}")
        
        # Return success response
        return jsonify({
            'success': True,
            'message': f'{action.upper()} signal received',
            'signal': {
                'id': signal['id'],
                'symbol': signal['symbol'],
                'action': signal['action'],
                'price': signal['price'],
                'timestamp': signal['created_at']
            }
        }), 200
        
    except ValueError as e:
        logger.error(f"Invalid data format: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid data format: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error processing TradingView webhook: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tradingview_bp.route('/signals', methods=['GET'])
def get_signals():
    """
    Get TradingView signals with optional filters.
    
    Query params:
    - symbol: Filter by symbol (e.g., BTCUSD)
    - action: Filter by action (buy/sell)
    - strategy: Filter by strategy name
    - timeframe: Filter by timeframe
    - limit: Number of results (default: 100, max: 1000)
    - offset: Pagination offset (default: 0)
    """
    try:
        # Get query parameters
        symbol = request.args.get('symbol')
        action = request.args.get('action')
        strategy = request.args.get('strategy')
        timeframe = request.args.get('timeframe')
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        
        # Get signals from database
        signals = TradingViewSignalsDB.get_signals(
            symbol=symbol,
            action=action,
            strategy=strategy,
            timeframe=timeframe,
            limit=limit,
            offset=offset
        )
        
        # Get total count for pagination
        total_count = TradingViewSignalsDB.count_signals(
            symbol=symbol,
            action=action,
            strategy=strategy,
            timeframe=timeframe
        )
        
        return jsonify({
            'success': True,
            'signals': signals,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching signals: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tradingview_bp.route('/signals/<signal_id>', methods=['GET'])
def get_signal(signal_id):
    """Get a specific signal by ID."""
    try:
        signal = TradingViewSignalsDB.get_signal(signal_id)
        
        if not signal:
            return jsonify({
                'success': False,
                'error': 'Signal not found'
            }), 404
        
        return jsonify({
            'success': True,
            'signal': signal
        })
        
    except Exception as e:
        logger.error(f"Error fetching signal: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tradingview_bp.route('/signals/stats', methods=['GET'])
def get_signal_stats():
    """Get statistics about TradingView signals."""
    try:
        stats = TradingViewSignalsDB.get_signal_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error fetching signal stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tradingview_bp.route('/signals/<signal_id>', methods=['DELETE'])
def delete_signal(signal_id):
    """Delete a specific signal."""
    try:
        success = TradingViewSignalsDB.delete_signal(signal_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Signal not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Signal deleted'
        })
        
    except Exception as e:
        logger.error(f"Error deleting signal: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tradingview_bp.route('/config', methods=['GET'])
def get_config():
    """Get TradingView webhook configuration info."""
    try:
        # Generate webhook URL (you'll need to replace with your actual domain)
        from flask import request
        webhook_url = f"{request.url_root}api/tradingview/webhook"
        
        return jsonify({
            'success': True,
            'config': {
                'webhook_url': webhook_url,
                'webhook_secret_configured': WEBHOOK_SECRET is not None,
                'supported_actions': ['buy', 'sell', 'close', 'long', 'short'],
                'example_payload': {
                    'symbol': 'BTCUSD',
                    'action': 'buy',
                    'price': 50000.00,
                    'timestamp': datetime.utcnow().isoformat(),
                    'strategy': 'RSI_Strategy',
                    'timeframe': '15m',
                    'message': 'Strong buy signal',
                    'metadata': {
                        'rsi': 25.5,
                        'volume': 1234.56
                    }
                },
                'pine_script_example': """
// TradingView Pine Script Alert Example
//@version=5
indicator("My Strategy Signals", overlay=true)

// Your strategy logic here
buyCondition = ta.crossover(ta.rsi(close, 14), 30)
sellCondition = ta.crossunder(ta.rsi(close, 14), 70)

// Plot signals
plotshape(buyCondition, title="Buy", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small)
plotshape(sellCondition, title="Sell", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small)

// Alert conditions with JSON payload
if (buyCondition)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "buy", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(time) + '", "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed above 30", "metadata": {"rsi": ' + str.tostring(ta.rsi(close, 14)) + '}}', alert.freq_once_per_bar)

if (sellCondition)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "sell", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(time) + '", "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed below 70", "metadata": {"rsi": ' + str.tostring(ta.rsi(close, 14)) + '}}', alert.freq_once_per_bar)
"""
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching config: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
