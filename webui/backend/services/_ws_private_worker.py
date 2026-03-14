#!/usr/bin/env python3
"""
Standalone WebSocket subprocess worker for Delta Exchange private (authenticated) feeds.

Subscribes to:
  - orders   — real-time order state changes (open, filled, cancelled)
  - positions — real-time position updates

Authentication: HMAC-SHA256 over "GET<timestamp>/live"
Credentials passed via env vars: DELTA_WS_API_KEY, DELTA_WS_API_SECRET

Communication with parent:
  stdout (child → parent): JSON lines — order_update, position_update, status, error
  stdin  (parent → child): JSON lines — stop

No eventlet imports — this is a clean subprocess.
"""

import hashlib
import hmac
import json
import os
import signal
import sys
import threading
import time

WS_URL = 'wss://socket.india.delta.exchange'

sys.stdout.reconfigure(line_buffering=True)

ws_ref = [None]
running = True
_last_heartbeat = [time.time()]
_HEARTBEAT_TIMEOUT = 35


def send_msg(msg: dict):
    try:
        sys.stdout.write(json.dumps(msg) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def cleanup_and_exit(_signum=None, _frame=None):
    global running
    running = False
    if ws_ref[0]:
        try:
            ws_ref[0].close()
        except Exception:
            pass
    os._exit(0)


def _make_auth_payload(api_key: str, api_secret: str) -> dict:
    timestamp = str(int(time.time()))
    prehash = 'GET' + timestamp + '/live'
    sig = hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return {
        "type": "auth",
        "payload": {
            "api-key": api_key,
            "signature": sig,
            "timestamp": timestamp
        }
    }


def on_open(ws):
    ws_ref[0] = ws
    _last_heartbeat[0] = time.time()
    send_msg({'type': 'status', 'connected': True})

    api_key = os.environ.get('DELTA_WS_API_KEY', '')
    api_secret = os.environ.get('DELTA_WS_API_SECRET', '')

    if not api_key or not api_secret:
        send_msg({'type': 'error', 'message': 'Missing DELTA_WS_API_KEY or DELTA_WS_API_SECRET'})
        return

    # Enable heartbeat
    ws.send(json.dumps({"type": "enable_heartbeat"}))

    # Authenticate
    ws.send(json.dumps(_make_auth_payload(api_key, api_secret)))

    # Subscribe to private channels after auth (Delta processes auth synchronously)
    ws.send(json.dumps({
        "type": "subscribe",
        "payload": {
            "channels": [
                {"name": "orders", "symbols": ["all"]},
                {"name": "positions", "symbols": ["all"]}
            ]
        }
    }))


def on_message(ws, message):
    try:
        data = json.loads(message)
        msg_type = data.get('type')

        if msg_type == 'heartbeat':
            _last_heartbeat[0] = time.time()

        elif msg_type == 'orders':
            order = data.get('data', data)
            state = order.get('state', '')
            reason = order.get('reason', '')
            symbol = order.get('product_symbol', order.get('symbol', ''))
            send_msg({
                'type': 'order_update',
                'state': state,
                'reason': reason,
                'symbol': symbol,
                'order_id': order.get('id'),
                'size': order.get('size'),
                'unfilled_size': order.get('unfilled_size'),
                'timestamp': time.time()
            })

        elif msg_type == 'positions':
            pos = data.get('data', data)
            symbol = pos.get('product_symbol', pos.get('symbol', ''))
            send_msg({
                'type': 'position_update',
                'symbol': symbol,
                'size': pos.get('size'),
                'timestamp': time.time()
            })

        elif msg_type in ('subscriptions', 'success'):
            pass  # subscription confirmations — ignore

        elif msg_type == 'error':
            send_msg({'type': 'error', 'message': f"WS error from server: {data}"})

    except Exception:
        pass


def on_error(ws, error):
    send_msg({'type': 'error', 'message': str(error)})


def on_close(ws, close_status_code, close_msg):
    send_msg({'type': 'status', 'connected': False})


def read_commands():
    global running
    while running:
        try:
            line = sys.stdin.readline()
            if not line:
                cleanup_and_exit()
                return
            cmd = json.loads(line.strip())
            if cmd.get('action') == 'stop':
                cleanup_and_exit()
                return
        except json.JSONDecodeError:
            pass
        except (EOFError, BrokenPipeError):
            cleanup_and_exit()
            return
        except Exception:
            pass


def _heartbeat_watchdog():
    while running:
        time.sleep(10)
        age = time.time() - _last_heartbeat[0]
        if age > _HEARTBEAT_TIMEOUT and ws_ref[0]:
            send_msg({'type': 'error', 'message': f'Heartbeat timeout ({age:.0f}s), reconnecting'})
            try:
                ws_ref[0].close()
            except Exception:
                pass


def main():
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    import websocket

    threading.Thread(target=read_commands, daemon=True, name='cmd-reader').start()
    threading.Thread(target=_heartbeat_watchdog, daemon=True, name='hb-watchdog').start()

    max_attempts = 100
    attempt = 0
    while attempt < max_attempts and running:
        try:
            websocket.enableTrace(False)
            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws_ref[0] = ws
            ws.run_forever()
        except Exception as e:
            send_msg({'type': 'error', 'message': f'run_forever exception: {e}'})

        if not running:
            break

        attempt += 1
        send_msg({'type': 'status', 'connected': False})
        time.sleep(5)

    send_msg({'type': 'error', 'message': 'Max reconnection attempts reached'})
    os._exit(1)


if __name__ == '__main__':
    main()
