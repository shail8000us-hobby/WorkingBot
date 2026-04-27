#!/usr/bin/env python3
"""
Standalone WebSocket subprocess worker — authenticated executions channel.

Connects to Delta Exchange with API credentials, subscribes to the private
user_trades channel, and forwards every fill event to the parent process as a
JSON line on stdout.

Communication:
  stdin  ← parent sends: {"action": "stop"}
  stdout → child sends:  {"type": "execution", "trade": {...}}
                         {"type": "status", "connected": bool, "authenticated": bool}
                         {"type": "error", "message": "..."}

Credentials passed via environment variables:
  DELTA_EXEC_API_KEY    — Delta Exchange API key
  DELTA_EXEC_API_SECRET — Delta Exchange API secret
  DELTA_EXEC_WS_URL     — WebSocket URL (default: wss://socket.india.delta.exchange)
"""

import hashlib
import hmac
import json
import os
import signal
import sys
import threading
import time

WS_URL    = os.environ.get('DELTA_EXEC_WS_URL', 'wss://socket.india.delta.exchange')
API_KEY    = os.environ.get('DELTA_EXEC_API_KEY', '')
API_SECRET = os.environ.get('DELTA_EXEC_API_SECRET', '')

sys.stdout.reconfigure(line_buffering=True)

ws_ref   = [None]
running  = True
authed   = [False]

_last_msg_time = [time.time()]
_HEARTBEAT_TIMEOUT = 45  # seconds


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


def _make_auth_msg() -> dict:
    timestamp = str(int(time.time()))
    signature_data = 'GET' + timestamp + '/live'
    sig = hmac.new(
        API_SECRET.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return {
        "type": "auth",
        "payload": {
            "api-key": API_KEY,
            "signature": sig,
            "timestamp": timestamp,
        },
    }


def _subscribe_user_trades():
    ws = ws_ref[0]
    if not ws:
        return
    ws.send(json.dumps({
        "type": "subscribe",
        "payload": {
            "channels": [{"name": "user_trades"}]
        }
    }))


def on_open(ws):
    ws_ref[0] = ws
    authed[0] = False
    _last_msg_time[0] = time.time()
    send_msg({'type': 'status', 'connected': True, 'authenticated': False})

    ws.send(json.dumps({"type": "enable_heartbeat"}))

    if not API_KEY or not API_SECRET:
        send_msg({'type': 'error', 'message': 'Missing API credentials — cannot authenticate'})
        return

    ws.send(json.dumps(_make_auth_msg()))


def on_message(ws, message):
    try:
        _last_msg_time[0] = time.time()
        data = json.loads(message)
        msg_type = data.get('type', '')

        if msg_type == 'heartbeat':
            return

        if msg_type == 'auth':
            if data.get('success'):
                authed[0] = True
                send_msg({'type': 'status', 'connected': True, 'authenticated': True})
                _subscribe_user_trades()
            else:
                send_msg({'type': 'error', 'message': f'Auth failed: {data}'})
            return

        # Alt auth success format Delta uses occasionally
        if msg_type == 'success' and 'Authenticated' in str(data.get('message', '')):
            authed[0] = True
            send_msg({'type': 'status', 'connected': True, 'authenticated': True})
            _subscribe_user_trades()
            return

        if msg_type == 'subscriptions':
            return  # subscription confirmation, no action needed

        if msg_type in ('v2/user_trades', 'user_trades'):
            trades = data.get('trades') or data.get('data') or []
            if isinstance(trades, dict):
                trades = [trades]
            for trade in trades:
                if isinstance(trade, dict):
                    send_msg({'type': 'execution', 'trade': trade})
            return

        # Forward any other private data as-is (future-proofing)
        if msg_type not in ('pong', 'heartbeat'):
            send_msg({'type': 'raw', 'data': data})

    except Exception:
        pass


def on_error(ws, error):
    send_msg({'type': 'error', 'message': str(error)})


def on_close(ws, close_status_code, close_msg):
    authed[0] = False
    send_msg({'type': 'status', 'connected': False, 'authenticated': False})


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
        age = time.time() - _last_msg_time[0]
        if age > _HEARTBEAT_TIMEOUT and ws_ref[0]:
            send_msg({'type': 'error', 'message': f'Executions WS heartbeat timeout ({age:.0f}s), reconnecting'})
            try:
                ws_ref[0].close()
            except Exception:
                pass


def main():
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    import websocket

    threading.Thread(target=read_commands, daemon=True, name='exec-cmd-reader').start()
    threading.Thread(target=_heartbeat_watchdog, daemon=True, name='exec-hb-watchdog').start()

    attempt = 0
    max_attempts = 200

    while attempt < max_attempts and running:
        try:
            websocket.enableTrace(False)
            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            ws_ref[0] = ws
            ws.run_forever()
        except Exception as e:
            send_msg({'type': 'error', 'message': f'run_forever: {e}'})

        if not running:
            break

        attempt += 1
        send_msg({'type': 'status', 'connected': False, 'authenticated': False})
        backoff = min(5 * attempt, 60)
        time.sleep(backoff)

    send_msg({'type': 'error', 'message': 'Max reconnect attempts reached'})
    os._exit(1)


if __name__ == '__main__':
    main()
