"""
TradingView Webhook Integration — World-Class Edition
=====================================================
Robust, production-grade webhook receiver for TradingView alerts.

Features:
  - Flexible payload parsing (JSON, plain-text, TradingView placeholders)
  - TradingView IP whitelisting (optional but recommended)
  - Signal deduplication with configurable window
  - Full request logging (every request, success or failure)
  - Health monitoring & diagnostics
  - Tunnel/ngrok auto-detection for public URL
  - Test signal endpoint for pipeline verification
  - WebSocket broadcasting for real-time UI updates
  - Dedicated logger (always writes, regardless of global log level)
  - Rate limiting per IP
"""
from flask import Blueprint, request, jsonify
import logging
import hmac
import hashlib
import json
import re
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import sys
import traceback

# Setup paths
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from db.tradingview_signals_db import TradingViewSignalsDB, init_tradingview_signals_db

# ──────────────────────────────────────────────────────────
#  Dedicated TradingView Logger (always logs, independent of global level)
# ──────────────────────────────────────────────────────────
tv_logger = logging.getLogger("tradingview")
tv_logger.setLevel(logging.DEBUG)

# File handler — dedicated TV log
_log_dir = Path(__file__).parent.parent / 'logs'
_log_dir.mkdir(parents=True, exist_ok=True)
_fh = logging.FileHandler(str(_log_dir / 'tradingview_webhook.log'))
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
))
tv_logger.addHandler(_fh)

# Also add stdout handler for immediate visibility
_sh = logging.StreamHandler()
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter('%(asctime)s [TV] %(message)s', datefmt='%H:%M:%S'))
tv_logger.addHandler(_sh)

logger = tv_logger  # alias for shorter code

# ──────────────────────────────────────────────────────────
#  Blueprint
# ──────────────────────────────────────────────────────────
tradingview_bp = Blueprint('tradingview', __name__, url_prefix='/api/tradingview')

# ──────────────────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────────────────
# Official TradingView webhook source IPs (as of 2024-2025)
# See: https://www.tradingview.com/support/solutions/43000529348
TRADINGVIEW_IPS = {
    '52.89.214.238',
    '34.212.75.30',
    '54.218.53.128',
    '52.32.178.7',
}

# Set to True to ONLY accept webhooks from TradingView IPs (recommended for production)
# Set to False to accept from any IP (useful for testing with curl/Postman)
ENFORCE_IP_WHITELIST = False

# Deduplication: ignore identical signals within this many seconds
DEDUP_WINDOW_SECONDS = 30

# Rate limiting: max requests per IP per minute
RATE_LIMIT_PER_MINUTE = 60

# Webhook secret (optional, set via env var)
WEBHOOK_SECRET = os.getenv('TRADINGVIEW_WEBHOOK_SECRET')

# SocketIO instance (set via init function)
_socketio = None

# Rate limiter state
_rate_limiter = defaultdict(list)

# Valid actions
VALID_ACTIONS = {'buy', 'sell', 'close', 'long', 'short'}

# Action normalization map
ACTION_NORMALIZE = {
    'long': 'buy',
    'short': 'sell',
    'buy': 'buy',
    'sell': 'sell',
    'close': 'close',
}


def init_tradingview_socketio(socketio):
    """Initialize SocketIO for TradingView signal broadcasting."""
    global _socketio
    _socketio = socketio
    logger.info("TradingView WebSocket broadcasting enabled")


# Initialize database on module load
init_tradingview_signals_db()
logger.info("TradingView webhook module loaded")


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────

def _check_rate_limit(ip: str) -> bool:
    """Return True if request is within rate limit."""
    now = time.time()
    cutoff = now - 60
    _rate_limiter[ip] = [t for t in _rate_limiter[ip] if t > cutoff]
    if len(_rate_limiter[ip]) >= RATE_LIMIT_PER_MINUTE:
        return False
    _rate_limiter[ip].append(now)
    return True


def _verify_signature(payload: str, signature: str) -> bool:
    """Verify TradingView webhook signature (if configured)."""
    if not WEBHOOK_SECRET:
        return True
    computed = hmac.new(
        WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _is_tradingview_ip(ip: str) -> bool:
    """Check if request comes from a known TradingView IP."""
    return ip in TRADINGVIEW_IPS


def _detect_tunnel_url() -> str:
    """Detect public tunnel URL (ngrok, cloudflared, etc.)."""
    # Try ngrok API
    try:
        import urllib.request
        resp = urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=2)
        data = json.loads(resp.read())
        for tunnel in data.get('tunnels', []):
            public_url = tunnel.get('public_url', '')
            if public_url.startswith('https://'):
                return public_url
            if public_url.startswith('http://'):
                return public_url
    except Exception:
        pass

    # Try cloudflared
    try:
        result = subprocess.run(
            ['cloudflared', 'tunnel', 'info', '--output', 'json'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            url = info.get('hostname', '')
            if url:
                return f"https://{url}"
    except Exception:
        pass

    return ''


def _parse_tradingview_payload(raw_body: str, content_type: str) -> dict:
    """
    Parse TradingView webhook payload with maximum flexibility.
    
    TradingView can send:
    1. Valid JSON (ideal case)
    2. JSON with TradingView placeholders already resolved
    3. Plain text (from alert message body)
    4. Malformed JSON (missing quotes, trailing commas)
    5. Key=value pairs
    6. Simple "BUY BTCUSD 50000" format
    
    This parser handles ALL of these cases.
    """
    if not raw_body or not raw_body.strip():
        return {}

    body = raw_body.strip()

    # ── Strategy 1: Standard JSON parse ──
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # ── Strategy 2: Fix common JSON issues and retry ──
    try:
        fixed = body
        # Remove trailing commas before } or ]
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        # Fix single quotes to double quotes
        fixed = fixed.replace("'", '"')
        # Fix unquoted keys: {symbol: "BTCUSD"} -> {"symbol": "BTCUSD"}
        fixed = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1 "\2":', fixed)
        data = json.loads(fixed)
        if isinstance(data, dict):
            logger.info("Parsed payload after JSON fixing")
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # ── Strategy 3: Extract JSON from within text ──
    # TradingView sometimes wraps JSON in alert text
    json_match = re.search(r'\{[^{}]*\}', body)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                logger.info("Extracted JSON from within text body")
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Strategy 4: Key=value pairs ──
    # e.g., "symbol=BTCUSD action=buy price=50000"
    kv_pattern = re.findall(r'(\w+)\s*[=:]\s*([^\s,]+)', body)
    if len(kv_pattern) >= 2:
        result = {}
        for k, v in kv_pattern:
            k_lower = k.lower()
            # Try to convert numeric values
            try:
                v = float(v) if '.' in v else int(v)
            except (ValueError, TypeError):
                pass
            result[k_lower] = v
        if 'symbol' in result or 'action' in result:
            logger.info("Parsed key=value payload format")
            return result

    # ── Strategy 5: Simple text format ──
    # e.g., "BUY BTCUSD 50000" or "sell ETHUSD at 3500"
    text_pattern = re.match(
        r'(buy|sell|long|short|close)\s+(\w+)\s+(?:at\s+)?(\d+(?:\.\d+)?)',
        body, re.IGNORECASE
    )
    if text_pattern:
        logger.info("Parsed simple text format: ACTION SYMBOL PRICE")
        return {
            'action': text_pattern.group(1).lower(),
            'symbol': text_pattern.group(2).upper(),
            'price': float(text_pattern.group(3)),
        }

    # ── Strategy 6: Reverse format "SYMBOL ACTION PRICE" ──
    text_pattern2 = re.match(
        r'(\w+)\s+(buy|sell|long|short|close)\s+(?:at\s+)?(\d+(?:\.\d+)?)',
        body, re.IGNORECASE
    )
    if text_pattern2:
        logger.info("Parsed text format: SYMBOL ACTION PRICE")
        return {
            'symbol': text_pattern2.group(1).upper(),
            'action': text_pattern2.group(2).lower(),
            'price': float(text_pattern2.group(3)),
        }

    # ── Strategy 7: Just action word ──
    for action_word in VALID_ACTIONS:
        if action_word in body.lower():
            result = {'action': action_word, 'message': body}
            # Try to find a price
            price_match = re.search(r'(\d+(?:\.\d+)?)', body)
            if price_match:
                result['price'] = float(price_match.group(1))
            # Try to find a symbol
            symbol_match = re.search(r'\b([A-Z]{3,10}(?:USD|USDT|BTC|ETH|PERP)?)\b', body)
            if symbol_match:
                result['symbol'] = symbol_match.group(1)
            logger.info(f"Extracted action '{action_word}' from text body")
            return result

    # ── Fallback: return raw body as message ──
    logger.warning(f"Could not parse payload, storing as raw message")
    return {'message': body, 'action': 'unknown', 'symbol': 'UNKNOWN', 'price': 0}


# ──────────────────────────────────────────────────────────
#  Core Webhook Endpoint
# ──────────────────────────────────────────────────────────

@tradingview_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Receive TradingView webhook alerts.
    
    Accepts:
      - JSON payloads (preferred)
      - Plain text payloads
      - Various malformed formats
    
    Pipeline: receive → validate → parse → deduplicate → store → broadcast → respond
    """
    start_time = time.time()
    source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if source_ip and ',' in source_ip:
        source_ip = source_ip.split(',')[0].strip()
    content_type = request.content_type or 'unknown'
    raw_body = ''
    signal_id = None
    error_msg = None
    response_code = 200

    try:
        # ── Step 1: Get raw body ──
        raw_body = request.get_data(as_text=True)
        logger.info(f"━━━ WEBHOOK RECEIVED ━━━ IP={source_ip} CT={content_type} Size={len(raw_body)}b")
        logger.debug(f"Raw body: {raw_body[:500]}")

        # ── Step 2: Rate limiting ──
        if not _check_rate_limit(source_ip):
            error_msg = 'Rate limit exceeded'
            response_code = 429
            logger.warning(f"RATE LIMITED: {source_ip}")
            return jsonify({'success': False, 'error': error_msg}), response_code

        # ── Step 3: IP verification (if enabled) ──
        if ENFORCE_IP_WHITELIST and not _is_tradingview_ip(source_ip):
            error_msg = f'IP {source_ip} not in TradingView whitelist'
            response_code = 403
            logger.warning(f"BLOCKED IP: {source_ip} (not in TradingView whitelist)")
            return jsonify({'success': False, 'error': 'Unauthorized IP'}), response_code

        # ── Step 4: Signature verification (if configured) ──
        signature = request.headers.get('X-TradingView-Signature')
        webhook_secret = request.args.get('secret')
        if WEBHOOK_SECRET:
            sig_to_check = signature or webhook_secret
            if not sig_to_check or not _verify_signature(raw_body, sig_to_check):
                error_msg = 'Invalid webhook signature'
                response_code = 401
                logger.warning(f"INVALID SIGNATURE from {source_ip}")
                return jsonify({'success': False, 'error': error_msg}), response_code

        # ── Step 5: Parse payload (flexible) ──
        data = _parse_tradingview_payload(raw_body, content_type)

        if not data:
            error_msg = 'Empty or unparseable payload'
            response_code = 400
            logger.error(f"PARSE FAILED: empty payload from {source_ip}")
            return jsonify({'success': False, 'error': error_msg}), response_code

        # ── Step 6: Extract & validate fields ──
        symbol = str(data.get('symbol', data.get('ticker', 'UNKNOWN'))).upper().strip()
        action = str(data.get('action', data.get('side', data.get('direction', '')))).lower().strip()
        
        # ── Step 6.1: Handle TradingView placeholder not substituted ──
        # If action contains {{...}}, TradingView didn't substitute the variable
        if '{{' in action or '}}' in action:
            logger.warning(f"TradingView placeholder NOT substituted: {action}")
            # Try to extract from order_id, order_action, or other fields
            order_id = str(data.get('order_id', '')).lower()
            order_action = str(data.get('order_action', '')).lower()
            
            # Check order_id first (user's script uses "Buy" / "Sell" as IDs)
            if 'buy' in order_id or order_id == 'buy':
                action = 'buy'
                logger.info(f"Extracted action 'buy' from order_id: {order_id}")
            elif 'sell' in order_id or order_id == 'sell':
                action = 'sell'
                logger.info(f"Extracted action 'sell' from order_id: {order_id}")
            elif 'long' in order_id:
                action = 'long'
                logger.info(f"Extracted action 'long' from order_id: {order_id}")
            elif 'short' in order_id:
                action = 'short'
                logger.info(f"Extracted action 'short' from order_id: {order_id}")
            # Check order_action field
            elif order_action in VALID_ACTIONS:
                action = order_action
                logger.info(f"Extracted action '{action}' from order_action field")
            else:
                error_msg = (
                    f'TradingView placeholder {{{{strategy.order.action}}}} not substituted. '
                    f'Make sure alert is created from Strategy Tester (not chart alert). '
                    f'Or use hardcoded action like "buy" or "sell" in the message.'
                )
                response_code = 400
                logger.error(f"PLACEHOLDER ERROR: {error_msg}")
                return jsonify({'success': False, 'error': error_msg, 'hint': 'Create alert from Strategy Tester panel'}), response_code
        
        try:
            price = float(data.get('price', data.get('close', 0)))
        except (ValueError, TypeError):
            price = 0.0

        strategy = str(data.get('strategy', data.get('indicator', data.get('name', 'Unknown'))))
        timeframe = str(data.get('timeframe', data.get('interval', data.get('tf', 'Unknown'))))
        message = str(data.get('message', data.get('msg', data.get('text', ''))))
        metadata = data.get('metadata', data.get('meta', data.get('extra', {})))
        if not isinstance(metadata, dict):
            metadata = {'raw': str(metadata)}

        # Validate action
        if action not in VALID_ACTIONS and action != 'unknown':
            error_msg = f'Invalid action: {action}. Must be: {", ".join(VALID_ACTIONS)}'
            response_code = 400
            logger.warning(f"INVALID ACTION: '{action}' from {source_ip}")
            return jsonify({'success': False, 'error': error_msg}), response_code

        if action == 'unknown':
            error_msg = 'Could not determine action (buy/sell) from payload'
            response_code = 400
            logger.warning(f"UNKNOWN ACTION from {source_ip}: {raw_body[:200]}")
            return jsonify({'success': False, 'error': error_msg}), response_code

        # Normalize action
        action = ACTION_NORMALIZE.get(action, action)

        # ── Step 7: Deduplication ──
        if TradingViewSignalsDB.is_duplicate(symbol, action, strategy, timeframe, DEDUP_WINDOW_SECONDS):
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"DEDUP: Ignoring duplicate {action.upper()} {symbol} ({strategy}/{timeframe}) within {DEDUP_WINDOW_SECONDS}s window")
            TradingViewSignalsDB.log_webhook_request(
                source_ip=source_ip, method=request.method,
                content_type=content_type, raw_body=raw_body,
                parsed_ok=True, error_message='Duplicate signal (deduplicated)',
                response_code=200, processing_ms=elapsed_ms,
            )
            return jsonify({
                'success': True,
                'message': 'Duplicate signal ignored (deduplication)',
                'deduplicated': True,
            }), 200

        # ── Step 8: Store signal ──
        signal = TradingViewSignalsDB.create_signal(
            symbol=symbol, action=action, price=price,
            strategy=strategy, timeframe=timeframe,
            message=message, metadata=metadata,
            source_ip=source_ip,
        )
        signal_id = signal['id'] if signal else None

        tv_or_ext = "TradingView" if _is_tradingview_ip(source_ip) else "External"
        logger.info(
            f"✅ SIGNAL STORED [{tv_or_ext}]: {action.upper()} {symbol} @ ${price:,.2f} "
            f"({strategy}/{timeframe}) ID={signal_id}"
        )

        # ── Step 9: Broadcast via WebSocket ──
        if _socketio and signal:
            try:
                _socketio.emit('tradingview_signal', {
                    'id': signal['id'],
                    'symbol': signal['symbol'],
                    'action': signal['action'],
                    'price': signal['price'],
                    'strategy': signal['strategy'],
                    'timeframe': signal['timeframe'],
                    'message': signal['message'],
                    'created_at': signal['created_at'],
                    'source_ip': source_ip,
                    'is_tradingview': _is_tradingview_ip(source_ip),
                })
                logger.debug("Signal broadcasted via WebSocket")
            except Exception as e:
                logger.error(f"WebSocket broadcast failed: {e}")

        # ── Step 10: Return success ──
        elapsed_ms = (time.time() - start_time) * 1000
        response_code = 200
        return jsonify({
            'success': True,
            'message': f'{action.upper()} signal received and stored',
            'signal': {
                'id': signal_id,
                'symbol': symbol,
                'action': action,
                'price': price,
                'timestamp': signal['created_at'] if signal else datetime.utcnow().isoformat(),
            }
        }), 200

    except Exception as e:
        error_msg = str(e)
        response_code = 500
        logger.error(f"WEBHOOK ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Internal error: {error_msg}'}), 500

    finally:
        # Always log the raw request
        elapsed_ms = (time.time() - start_time) * 1000
        try:
            TradingViewSignalsDB.log_webhook_request(
                source_ip=source_ip, method=request.method,
                content_type=content_type, raw_body=raw_body,
                parsed_ok=(error_msg is None), signal_id=signal_id,
                error_message=error_msg, response_code=response_code,
                processing_ms=elapsed_ms,
            )
        except Exception:
            pass

        # Update health counters
        try:
            TradingViewSignalsDB.set_health('last_webhook_at', datetime.utcnow().isoformat())
            TradingViewSignalsDB.set_health('last_webhook_ip', source_ip)
            TradingViewSignalsDB.set_health('last_webhook_status', str(response_code))
        except Exception:
            pass


# ──────────────────────────────────────────────────────────
#  Signal List / Filter Endpoint
# ──────────────────────────────────────────────────────────

@tradingview_bp.route('/signals', methods=['GET'])
def get_signals():
    """Get TradingView signals with optional filters."""
    try:
        symbol = request.args.get('symbol')
        action = request.args.get('action')
        strategy = request.args.get('strategy')
        timeframe = request.args.get('timeframe')
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))

        signals = TradingViewSignalsDB.get_signals(
            symbol=symbol, action=action, strategy=strategy,
            timeframe=timeframe, limit=limit, offset=offset
        )
        total_count = TradingViewSignalsDB.count_signals(
            symbol=symbol, action=action, strategy=strategy, timeframe=timeframe
        )

        return jsonify({
            'success': True,
            'signals': signals,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count,
            }
        })
    except Exception as e:
        logger.error(f"Error fetching signals: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@tradingview_bp.route('/signals/<signal_id>', methods=['GET'])
def get_signal(signal_id):
    """Get a specific signal by ID."""
    try:
        signal = TradingViewSignalsDB.get_signal(signal_id)
        if not signal:
            return jsonify({'success': False, 'error': 'Signal not found'}), 404
        return jsonify({'success': True, 'signal': signal})
    except Exception as e:
        logger.error(f"Error fetching signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@tradingview_bp.route('/signals/stats', methods=['GET'])
def get_signal_stats():
    """Get statistics about TradingView signals."""
    try:
        stats = TradingViewSignalsDB.get_signal_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@tradingview_bp.route('/signals/<signal_id>', methods=['DELETE'])
def delete_signal(signal_id):
    """Delete a specific signal."""
    try:
        success = TradingViewSignalsDB.delete_signal(signal_id)
        if not success:
            return jsonify({'success': False, 'error': 'Signal not found'}), 404
        return jsonify({'success': True, 'message': 'Signal deleted'})
    except Exception as e:
        logger.error(f"Error deleting signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────────
#  Health & Diagnostics
# ──────────────────────────────────────────────────────────

@tradingview_bp.route('/health', methods=['GET'])
def get_health():
    """
    Comprehensive health check for the TradingView pipeline.
    Returns server status, tunnel status, last signal info, and more.
    """
    try:
        health_data = TradingViewSignalsDB.get_health()
        stats = TradingViewSignalsDB.get_signal_stats()

        # Detect tunnel URL
        tunnel_url = _detect_tunnel_url()
        tunnel_active = bool(tunnel_url)

        # Build webhook URL
        if tunnel_url:
            webhook_url = f"{tunnel_url}/api/tradingview/webhook"
        else:
            webhook_url = f"{request.url_root}api/tradingview/webhook"

        # Calculate time since last signal
        last_signal_at = health_data.get('last_signal_at', {}).get('value')
        if last_signal_at:
            try:
                last_dt = datetime.fromisoformat(last_signal_at)
                seconds_ago = (datetime.utcnow() - last_dt).total_seconds()
                last_signal_age = f"{int(seconds_ago)}s ago" if seconds_ago < 3600 else f"{int(seconds_ago/3600)}h ago"
            except Exception:
                last_signal_age = 'unknown'
        else:
            last_signal_age = 'never'

        # Calculate time since last webhook
        last_webhook_at = health_data.get('last_webhook_at', {}).get('value')
        if last_webhook_at:
            try:
                last_dt = datetime.fromisoformat(last_webhook_at)
                seconds_ago = (datetime.utcnow() - last_dt).total_seconds()
                last_webhook_age = f"{int(seconds_ago)}s ago" if seconds_ago < 3600 else f"{int(seconds_ago/3600)}h ago"
            except Exception:
                last_webhook_age = 'unknown'
        else:
            last_webhook_age = 'never'

        return jsonify({
            'success': True,
            'health': {
                'server_running': True,
                'webhook_url': webhook_url,
                'tunnel_active': tunnel_active,
                'tunnel_url': tunnel_url or None,
                'ip_whitelist_enabled': ENFORCE_IP_WHITELIST,
                'webhook_secret_configured': WEBHOOK_SECRET is not None,
                'dedup_window_seconds': DEDUP_WINDOW_SECONDS,
                'rate_limit_per_minute': RATE_LIMIT_PER_MINUTE,
                'tradingview_ips': list(TRADINGVIEW_IPS),
                'last_signal_at': last_signal_at,
                'last_signal_age': last_signal_age,
                'last_signal_symbol': health_data.get('last_signal_symbol', {}).get('value'),
                'last_signal_action': health_data.get('last_signal_action', {}).get('value'),
                'last_webhook_at': last_webhook_at,
                'last_webhook_age': last_webhook_age,
                'last_webhook_ip': health_data.get('last_webhook_ip', {}).get('value'),
                'last_webhook_status': health_data.get('last_webhook_status', {}).get('value'),
                'total_signals': stats.get('total_signals', 0),
                'signals_24h': stats.get('last_24h', 0),
            }
        })
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'health': {'server_running': True, 'error': str(e)}
        }), 500


@tradingview_bp.route('/webhook-logs', methods=['GET'])
def get_webhook_logs():
    """Get recent webhook request logs for debugging."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        logs = TradingViewSignalsDB.get_webhook_logs(limit=limit)
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.error(f"Error fetching webhook logs: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@tradingview_bp.route('/test-signal', methods=['POST'])
def send_test_signal():
    """
    Send a test signal through the full pipeline.
    Useful for verifying the entire system works end-to-end.
    """
    try:
        test_data = {
            'symbol': 'BTCUSD',
            'action': 'buy',
            'price': 99999.99,
            'strategy': 'Pipeline_Test',
            'timeframe': '1m',
            'message': f'Test signal at {datetime.utcnow().isoformat()}',
            'metadata': {'test': True, 'source': 'diagnostic'},
        }

        # Override with user-provided data if any
        user_data = request.get_json(silent=True) or {}
        for key in ['symbol', 'action', 'price', 'strategy', 'timeframe', 'message']:
            if key in user_data:
                test_data[key] = user_data[key]

        signal = TradingViewSignalsDB.create_signal(
            symbol=test_data['symbol'],
            action=test_data['action'],
            price=float(test_data['price']),
            strategy=test_data['strategy'],
            timeframe=test_data['timeframe'],
            message=test_data['message'],
            metadata=test_data['metadata'],
            source_ip='test-pipeline',
        )

        logger.info(f"TEST SIGNAL: {test_data['action'].upper()} {test_data['symbol']} @ ${test_data['price']:,.2f}")

        # Broadcast via WebSocket
        if _socketio and signal:
            try:
                _socketio.emit('tradingview_signal', {
                    'id': signal['id'],
                    'symbol': signal['symbol'],
                    'action': signal['action'],
                    'price': signal['price'],
                    'strategy': signal['strategy'],
                    'timeframe': signal['timeframe'],
                    'message': signal['message'],
                    'created_at': signal['created_at'],
                    'source_ip': 'test-pipeline',
                    'is_tradingview': False,
                    'is_test': True,
                })
            except Exception as e:
                logger.error(f"Test signal WebSocket broadcast failed: {e}")

        return jsonify({
            'success': True,
            'message': 'Test signal sent through full pipeline',
            'signal': signal,
        })

    except Exception as e:
        logger.error(f"Test signal error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────────
#  Configuration / Setup Info
# ──────────────────────────────────────────────────────────

@tradingview_bp.route('/config', methods=['GET'])
def get_config():
    """Get TradingView webhook configuration and setup instructions."""
    try:
        tunnel_url = _detect_tunnel_url()
        if tunnel_url:
            webhook_url = f"{tunnel_url}/api/tradingview/webhook"
        else:
            webhook_url = f"{request.url_root}api/tradingview/webhook"

        return jsonify({
            'success': True,
            'config': {
                'webhook_url': webhook_url,
                'tunnel_active': bool(tunnel_url),
                'tunnel_url': tunnel_url or None,
                'webhook_secret_configured': WEBHOOK_SECRET is not None,
                'ip_whitelist_enabled': ENFORCE_IP_WHITELIST,
                'supported_actions': list(VALID_ACTIONS),
                'dedup_window_seconds': DEDUP_WINDOW_SECONDS,
                'example_payload': {
                    'symbol': 'BTCUSD',
                    'action': 'buy',
                    'price': 50000.00,
                    'timestamp': datetime.utcnow().isoformat(),
                    'strategy': 'RSI_Strategy',
                    'timeframe': '15m',
                    'message': 'Strong buy signal',
                    'metadata': {'rsi': 25.5, 'volume': 1234.56}
                },
                'alternative_formats': [
                    '{"symbol": "BTCUSD", "action": "buy", "price": 50000}',
                    'BUY BTCUSD 50000',
                    'symbol=BTCUSD action=buy price=50000',
                    'BTCUSD buy at 50000',
                ],
                'pine_script_example': """// TradingView Pine Script Alert Example
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
    alert('{"symbol": "' + syminfo.ticker + '", "action": "buy", "price": ' + str.tostring(close) + ', "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed above 30"}', alert.freq_once_per_bar)

if (sellCondition)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "sell", "price": ' + str.tostring(close) + ', "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed below 70"}', alert.freq_once_per_bar)
""",
                'setup_steps': [
                    '1. Start ngrok tunnel: ngrok http 5555',
                    '2. Copy the HTTPS URL from ngrok',
                    '3. In TradingView, create an alert on your indicator',
                    '4. Set Webhook URL to: <ngrok-url>/api/tradingview/webhook',
                    '5. Set the alert message to a JSON payload (see example above)',
                    '6. Click Create Alert',
                    '7. Test with the "Send Test Signal" button in the WebUI',
                ],
            }
        })
    except Exception as e:
        logger.error(f"Error fetching config: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────────
#  Cleanup Endpoint
# ──────────────────────────────────────────────────────────

@tradingview_bp.route('/cleanup', methods=['POST'])
def run_cleanup():
    """Run database cleanup for old logs and processed signals."""
    try:
        logs_deleted = TradingViewSignalsDB.cleanup_old_logs(days=30)
        signals_deleted = TradingViewSignalsDB.cleanup_old_signals(days=90)
        return jsonify({
            'success': True,
            'cleaned': {
                'webhook_logs_deleted': logs_deleted,
                'old_signals_deleted': signals_deleted,
            }
        })
    except Exception as e:
        logger.error(f"Cleanup error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
