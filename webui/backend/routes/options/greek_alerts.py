"""
Greek Alerts Blueprint  (Feature 5 — Conditional Execution)
============================================================
Independent module for Greek-based alert CRUD.
Minimal invasion — does NOT touch AlertsDB @sealed methods.

Routes:
  GET  /api/options/greek-alerts
  POST /api/options/greek-alerts
  DELETE /api/options/greek-alerts/<id>
  POST /api/options/greek-alerts/check   (manual trigger check)
"""

import json
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

greek_alerts_bp = Blueprint('greek_alerts', __name__)

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------
try:
    from webui.backend.db.alerts_db import (
        create_greek_alert, get_greek_alerts,
        trigger_greek_alert, cancel_greek_alert,
    )
except ImportError:
    from ...db.alerts_db import (
        create_greek_alert, get_greek_alerts,
        trigger_greek_alert, cancel_greek_alert,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@greek_alerts_bp.route('/api/options/greek-alerts', methods=['GET'])
def list_greek_alerts():
    status = request.args.get('status')
    try:
        alerts = get_greek_alerts(status=status)
        return jsonify({'success': True, 'alerts': alerts})
    except Exception as e:
        logger.error("list_greek_alerts: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@greek_alerts_bp.route('/api/options/greek-alerts', methods=['POST'])
def create_greek_alert_route():
    data = request.get_json() or {}
    required = ('symbol', 'metric', 'threshold', 'direction')
    if not all(k in data for k in required):
        return jsonify({'success': False, 'error': 'Missing required fields: symbol, metric, threshold, direction'}), 400

    try:
        alert = create_greek_alert(
            symbol=data['symbol'],
            metric=data['metric'],
            threshold=float(data['threshold']),
            direction=data['direction'],
            action_type=data.get('action_type', 'notify'),
            action_config=json.dumps(data.get('action_config', {})),
            note=data.get('note'),
        )
        return jsonify({'success': True, 'alert': alert})
    except Exception as e:
        logger.error("create_greek_alert_route: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@greek_alerts_bp.route('/api/options/greek-alerts/<alert_id>', methods=['DELETE'])
def delete_greek_alert(alert_id):
    try:
        ok = cancel_greek_alert(alert_id)
        return jsonify({'success': ok})
    except Exception as e:
        logger.error("delete_greek_alert: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@greek_alerts_bp.route('/api/options/greek-alerts/check', methods=['POST'])
def check_greek_alerts():
    """
    Manually evaluate all active Greek alerts against current portfolio Greeks.
    Called by the frontend or a periodic task.
    Body: { position_greeks: {symbol: {delta, theta, gamma, vega}},
            portfolio_delta: float }
    """
    data = request.get_json() or {}
    pos_greeks = data.get('position_greeks', {})
    portfolio_delta = data.get('portfolio_delta', 0.0)

    try:
        active = get_greek_alerts(status='active')
        triggered = []

        for alert in active:
            symbol = alert['symbol']
            metric = alert['metric']
            threshold = float(alert['threshold'])
            direction = alert['direction']

            # Resolve current value
            if metric == 'portfolio_delta':
                current = float(portfolio_delta)
            else:
                greeks = pos_greeks.get(symbol, {})
                current = float(greeks.get(metric, 0.0))

            hit = (direction == 'above' and current >= threshold) or \
                  (direction == 'below' and current <= threshold)

            if hit:
                trigger_greek_alert(alert['id'])
                triggered.append({'id': alert['id'], 'symbol': symbol, 'metric': metric,
                                   'threshold': threshold, 'current': current})
                logger.info("[GreekAlert] Triggered %s %s %s %.4f (current %.4f)",
                            symbol, metric, direction, threshold, current)

        return jsonify({'success': True, 'triggered': triggered, 'checked': len(active)})
    except Exception as e:
        logger.error("check_greek_alerts: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500
