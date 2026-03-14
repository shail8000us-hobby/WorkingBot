#!/usr/bin/env python3
"""
Standalone WebSocket subprocess worker for Delta Exchange price feeds.

This script runs as a completely separate process launched via subprocess.Popen.
It has ZERO imports from eventlet or any parent module — guaranteeing a clean
Python environment with no monkey-patching contamination.

Communication with the parent process:
  - stdout: child -> parent (JSON lines: price, ticker, status, error messages)
  - stdin:  parent -> child (JSON lines: subscribe, unsubscribe, stop commands)

Usage (called by DeltaPriceWebSocket.start(), never directly):
  python3 _ws_subprocess_worker.py
"""

import json
import os
import signal
import sys
import threading
import time

# Delta Exchange India WebSocket URL and index symbols
WS_URL = 'wss://socket.india.delta.exchange'
BTC_INDEX = '.DEXBTUSD'
ETH_INDEX = '.DEETHUSD'

# Ensure stdout is line-buffered for real-time communication
sys.stdout.reconfigure(line_buffering=True)

ws_ref = [None]
running = True

# Heartbeat tracking — Delta sends heartbeat every 5s; if we miss 7 (35s), reconnect
_last_heartbeat = [time.time()]
_HEARTBEAT_TIMEOUT = 35


def send_msg(msg: dict):
    """Send a JSON message to the parent via stdout."""
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


def on_open(ws):
    ws_ref[0] = ws
    _last_heartbeat[0] = time.time()
    send_msg({'type': 'status', 'connected': True})

    # Enable server heartbeat (sent every 5s — lets us detect stale connections)
    ws.send(json.dumps({"type": "enable_heartbeat"}))

    # Subscribe to BTC and ETH spot prices
    ws.send(json.dumps({
        "type": "subscribe",
        "payload": {
            "channels": [{
                "name": "v2/spot_price",
                "symbols": [BTC_INDEX, ETH_INDEX]
            }]
        }
    }))

    # Subscribe to ALL call and put options via category names.
    # l1_orderbook pushes every ~500ms on quote change — much faster than v2/ticker.
    ws.send(json.dumps({
        "type": "subscribe",
        "payload": {
            "channels": [{
                "name": "l1_orderbook",
                "symbols": ["call_options", "put_options"]
            }]
        }
    }))


def on_message(ws, message):
    try:
        data = json.loads(message)
        msg_type = data.get('type')

        if msg_type == 'heartbeat':
            _last_heartbeat[0] = time.time()

        elif msg_type == 'v2/spot_price':
            symbol = data.get('s')
            price = data.get('p')
            if symbol and price is not None:
                asset = None
                if symbol == BTC_INDEX:
                    asset = 'BTC'
                elif symbol == ETH_INDEX:
                    asset = 'ETH'
                if asset:
                    send_msg({
                        'type': 'price',
                        'symbol': asset,
                        'price': float(price),
                        'timestamp': time.time()
                    })

        elif msg_type == 'l1_orderbook':
            sym = data.get('symbol')
            if sym:
                send_msg({
                    'type': 'ticker',
                    'symbol': sym,
                    'best_bid': float(data.get('best_bid', 0) or 0),
                    'best_ask': float(data.get('best_ask', 0) or 0),
                    'mark_price': 0,
                    'timestamp': time.time()
                })
    except Exception:
        pass


def on_error(ws, error):
    send_msg({'type': 'error', 'message': str(error)})


def on_close(ws, close_status_code, close_msg):
    send_msg({'type': 'status', 'connected': False})


def read_commands():
    """Read commands from stdin (parent -> child)."""
    global running
    while running:
        try:
            line = sys.stdin.readline()
            if not line:
                # Parent closed stdin — exit
                cleanup_and_exit()
                return

            cmd = json.loads(line.strip())
            action = cmd.get('action')

            if action == 'stop':
                cleanup_and_exit()
                return

            # subscribe/unsubscribe for individual symbols (legacy/future use)
            symbols = cmd.get('symbols', [])
            if action == 'subscribe' and symbols and ws_ref[0]:
                ws_ref[0].send(json.dumps({
                    "type": "subscribe",
                    "payload": {
                        "channels": [{"name": "l1_orderbook", "symbols": symbols}]
                    }
                }))

            elif action == 'unsubscribe' and symbols and ws_ref[0]:
                ws_ref[0].send(json.dumps({
                    "type": "unsubscribe",
                    "payload": {
                        "channels": [{"name": "l1_orderbook", "symbols": symbols}]
                    }
                }))

        except json.JSONDecodeError:
            pass
        except (EOFError, BrokenPipeError):
            cleanup_and_exit()
            return
        except Exception:
            pass


def _heartbeat_watchdog():
    """Close the WS if we stop receiving heartbeats — forces a reconnect."""
    while running:
        time.sleep(10)
        age = time.time() - _last_heartbeat[0]
        if age > _HEARTBEAT_TIMEOUT and ws_ref[0]:
            send_msg({'type': 'error', 'message': f'Heartbeat timeout ({age:.0f}s), forcing reconnect'})
            try:
                ws_ref[0].close()
            except Exception:
                pass


def main():
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    import websocket

    # Start command reader and heartbeat watchdog as daemon threads
    threading.Thread(target=read_commands, daemon=True, name='cmd-reader').start()
    threading.Thread(target=_heartbeat_watchdog, daemon=True, name='hb-watchdog').start()

    # Main reconnection loop
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
        time.sleep(5)  # Wait before reconnect

    send_msg({'type': 'error', 'message': 'Max reconnection attempts reached'})
    os._exit(1)


if __name__ == '__main__':
    main()
