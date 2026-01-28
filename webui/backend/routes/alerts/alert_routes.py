"""
Price Alert API Routes
Endpoints for managing price alerts and notification settings
"""
from flask import Blueprint, request, jsonify
import asyncio
from datetime import datetime
import logging
import sys
from pathlib import Path

# Ensure proper import path
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from db.alerts_db import AlertsDB, init_alerts_db
from services.notifications import NotificationService, TelegramNotifier

logger = logging.getLogger(__name__)

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

# Initialize notification service
_notification_service = None

def get_notification_service():
    """Get or create notification service with current settings."""
    global _notification_service
    settings = AlertsDB.get_settings()
    if _notification_service is None:
        _notification_service = NotificationService(settings)
    else:
        _notification_service.update_settings(settings)
    return _notification_service


# ============================================================================
# ALERT CRUD ENDPOINTS
# ============================================================================

@alerts_bp.route('', methods=['GET'])
def list_alerts():
    """Get all alerts, optionally filtered by status and expiry."""
    try:
        status = request.args.get('status')  # active, triggered, cancelled
        expiry_date = request.args.get('expiry_date') # Filter by specific expiry
        
        alerts = AlertsDB.get_all_alerts(status=status, expiry_date=expiry_date)
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('', methods=['POST'])
def create_alert():
    """Create a new price alert."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'target_price' not in data:
            return jsonify({'success': False, 'error': 'target_price is required'}), 400
        if 'direction' not in data or data['direction'] not in ['above', 'below', 'cross']:
            return jsonify({'success': False, 'error': 'direction must be above, below, or cross'}), 400
        
        alert = AlertsDB.create_alert(
            target_price=float(data['target_price']),
            direction=data['direction'],
            note=data.get('note'),
            expected_pnl_expiry=data.get('expected_pnl_expiry'),
            expected_pnl_target=data.get('expected_pnl_target'),
            symbol=data.get('symbol', 'BTCUSD'),
            is_repeating=data.get('is_repeating', False),
            notification_channels=data.get('notification_channels', 'telegram,in_app'),
            expiry_date=data.get('expiry_date')
        )
        
        logger.info(f"Created alert {alert['id']} at ${alert['target_price']}")
        
        return jsonify({
            'success': True,
            'alert': alert,
            'message': f"Alert created for ${alert['target_price']:,.0f}"
        })
        
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/<alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Get a specific alert by ID."""
    try:
        alert = AlertsDB.get_alert(alert_id)
        if not alert:
            return jsonify({'success': False, 'error': 'Alert not found'}), 404
        return jsonify({'success': True, 'alert': alert})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/<alert_id>', methods=['PATCH'])
def update_alert(alert_id):
    """Update an alert (e.g., cancel it)."""
    try:
        data = request.get_json()
        
        # Only allow updating certain fields
        allowed_fields = ['status', 'note', 'is_repeating', 'notification_channels']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400
        
        alert = AlertsDB.update_alert(alert_id, **update_data)
        if not alert:
            return jsonify({'success': False, 'error': 'Alert not found'}), 404
        
        return jsonify({'success': True, 'alert': alert})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/<alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    """Delete an alert."""
    try:
        success = AlertsDB.delete_alert(alert_id)
        if not success:
            return jsonify({'success': False, 'error': 'Alert not found'}), 404
        return jsonify({'success': True, 'message': 'Alert deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/<alert_id>/cancel', methods=['POST'])
def cancel_alert(alert_id):
    """Cancel an active alert."""
    try:
        alert = AlertsDB.cancel_alert(alert_id)
        if not alert:
            return jsonify({'success': False, 'error': 'Alert not found'}), 404
        return jsonify({'success': True, 'alert': alert, 'message': 'Alert cancelled'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# NOTIFICATION SETTINGS ENDPOINTS
# ============================================================================

@alerts_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get notification settings."""
    try:
        settings = AlertsDB.get_settings()
        # Mask sensitive data
        if settings.get('telegram_bot_token'):
            token = settings['telegram_bot_token']
            settings['telegram_bot_token'] = f"{token[:10]}...{token[-4:]}" if len(token) > 14 else '***'
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/settings', methods=['PUT'])
def update_settings():
    """Update notification settings."""
    try:
        data = request.get_json()
        
        # Validate and clean data
        allowed_fields = ['telegram_bot_token', 'telegram_chat_id', 'ntfy_topic', 
                         'ntfy_server', 'enabled_channels']
        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
        
        settings = AlertsDB.update_settings(**update_data)
        
        # Reinitialize notification service
        get_notification_service()
        
        return jsonify({'success': True, 'settings': settings, 'message': 'Settings updated'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/test/telegram', methods=['POST'])
def test_telegram():
    """Send a test Telegram message."""
    try:
        # Allow passing token/chat_id for testing before saving
        data = request.get_json() or {}
        
        settings = AlertsDB.get_settings()
        token = data.get('telegram_bot_token') or settings.get('telegram_bot_token')
        chat_id = data.get('telegram_chat_id') or settings.get('telegram_chat_id')
        
        if not token or not chat_id:
            return jsonify({
                'success': False, 
                'error': 'Telegram bot token and chat ID are required'
            }), 400
        
        notifier = TelegramNotifier(token, chat_id)
        
        # Run async in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, message = loop.run_until_complete(notifier.send_test_message())
        finally:
            loop.close()
        
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/test/ntfy', methods=['POST'])
def test_ntfy():
    """Send a test ntfy notification."""
    try:
        service = get_notification_service()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, message = loop.run_until_complete(service.test_ntfy())
        finally:
            loop.close()
        
        return jsonify({'success': success, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_bp.route('/telegram/chat-id', methods=['GET'])
def get_telegram_chat_id():
    """
    Helper to get chat ID. User should:
    1. Send any message to the bot
    2. Call this endpoint
    """
    try:
        settings = AlertsDB.get_settings()
        token = settings.get('telegram_bot_token')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Set bot token first, then send a message to your bot'
            }), 400
        
        notifier = TelegramNotifier(token, '')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            chat_id = loop.run_until_complete(notifier.get_chat_id())
        finally:
            loop.close()
        
        if chat_id:
            return jsonify({
                'success': True,
                'chat_id': chat_id,
                'message': f'Found chat ID: {chat_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No messages found. Send a message to your bot first.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
