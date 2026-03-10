"""
Delta Exchange WebSocket Price Service

Connects to Delta Exchange WebSocket API to fetch real-time BTC and ETH index prices.
Broadcasts prices to frontend clients via Socket.IO.

Architecture: Uses multiprocessing to run websocket-client in a separate process,
avoiding eventlet monkey-patching conflicts. Prices are sent back via a pipe.

Created: January 18, 2026
Author: SSR Bot
"""

import json
import logging
import time
import threading
import multiprocessing
import os
import signal
from typing import Dict, Optional, Callable

log = logging.getLogger(__name__)

# Delta Exchange India WebSocket URL and index symbols
WS_URL = 'wss://socket.india.delta.exchange'
BTC_INDEX = '.DEXBTUSD'
ETH_INDEX = '.DEETHUSD'


def _ws_subprocess(pipe_conn, cmd_conn):
    """
    WebSocket client that runs in a separate process (no eventlet).
    Sends price/ticker updates back to the parent via pipe_conn.
    Receives subscribe/unsubscribe commands via cmd_conn.
    """
    # Reset signal handlers in child
    signal.signal(signal.SIGTERM, lambda s, f: _cleanup_and_exit(ws_ref))
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    import websocket as _websocket

    ws_ref = [None]  # mutable ref for signal handler
    subscribed_options = set()

    def _cleanup_and_exit(ref):
        if ref[0]:
            try:
                ref[0].close()
            except Exception:
                pass
        os._exit(0)

    def on_open(ws):
        ws_ref[0] = ws
        pipe_conn.send({'type': 'status', 'connected': True})

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

        # Re-subscribe to any pending options tickers
        if subscribed_options:
            ws.send(json.dumps({
                "type": "subscribe",
                "payload": {
                    "channels": [{
                        "name": "v2/ticker",
                        "symbols": list(subscribed_options)
                    }]
                }
            }))

    def on_message(ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'v2/spot_price':
                symbol = data.get('s')
                price = data.get('p')
                if symbol and price is not None:
                    asset = None
                    if symbol == BTC_INDEX:
                        asset = 'BTC'
                    elif symbol == ETH_INDEX:
                        asset = 'ETH'
                    if asset:
                        pipe_conn.send({
                            'type': 'price',
                            'symbol': asset,
                            'price': float(price),
                            'timestamp': time.time()
                        })

            elif msg_type == 'v2/ticker':
                sym = data.get('symbol')
                if sym:
                    pipe_conn.send({
                        'type': 'ticker',
                        'symbol': sym,
                        'best_bid': float(data.get('best_bid_price', 0) or 0),
                        'best_ask': float(data.get('best_ask_price', 0) or 0),
                        'mark_price': float(data.get('mark_price', 0) or 0),
                        'timestamp': time.time()
                    })
        except Exception:
            pass

    def on_error(ws, error):
        try:
            pipe_conn.send({'type': 'error', 'message': str(error)})
        except Exception:
            pass

    def on_close(ws, close_status_code, close_msg):
        try:
            pipe_conn.send({'type': 'status', 'connected': False})
        except Exception:
            pass

    # Command reader thread — checks for subscribe/unsubscribe commands
    def _read_commands():
        while True:
            try:
                if cmd_conn.poll(1.0):
                    cmd = cmd_conn.recv()
                    action = cmd.get('action')
                    symbols = cmd.get('symbols', [])

                    if action == 'subscribe' and symbols and ws_ref[0]:
                        subscribed_options.update(symbols)
                        ws_ref[0].send(json.dumps({
                            "type": "subscribe",
                            "payload": {
                                "channels": [{"name": "v2/ticker", "symbols": symbols}]
                            }
                        }))

                    elif action == 'unsubscribe' and symbols and ws_ref[0]:
                        subscribed_options.difference_update(symbols)
                        ws_ref[0].send(json.dumps({
                            "type": "unsubscribe",
                            "payload": {
                                "channels": [{"name": "v2/ticker", "symbols": symbols}]
                            }
                        }))

                    elif action == 'stop':
                        _cleanup_and_exit(ws_ref)
            except (EOFError, BrokenPipeError):
                _cleanup_and_exit(ws_ref)
            except Exception:
                pass

    # Start command reader in a daemon thread
    import threading as _threading
    cmd_thread = _threading.Thread(target=_read_commands, daemon=True)
    cmd_thread.start()

    # Main reconnection loop
    max_attempts = 100
    attempt = 0
    while attempt < max_attempts:
        try:
            _websocket.enableTrace(False)
            ws = _websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws_ref[0] = ws
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            pass

        attempt += 1
        time.sleep(5)  # Wait before reconnect

    pipe_conn.send({'type': 'error', 'message': 'Max reconnection attempts reached'})
    os._exit(1)


class DeltaPriceWebSocket:
    """
    WebSocket client for Delta Exchange index prices.

    Runs websocket-client in a subprocess to avoid eventlet compatibility issues.
    Parent process reads prices from a pipe and invokes callbacks.
    """

    def __init__(self, on_price_update: Optional[Callable] = None, on_ticker_update: Optional[Callable] = None):
        self.running = False
        self.connected = False
        self._process: Optional[multiprocessing.Process] = None
        self._pipe_parent = None
        self._pipe_child = None
        self._cmd_parent = None
        self._cmd_child = None
        self._reader_thread = None

        # Price storage
        self.prices: Dict[str, float] = {'BTC': 0.0, 'ETH': 0.0}
        self.last_update: Dict[str, float] = {'BTC': 0.0, 'ETH': 0.0}

        # Options ticker subscriptions
        self.subscribed_options: Dict[str, bool] = {}
        self.subscribed_options_lock = threading.Lock()

        # Callbacks
        self.on_price_update = on_price_update
        self.on_ticker_update = on_ticker_update

        self.reconnect_attempts = 0

    def _read_pipe(self):
        """Read messages from the subprocess pipe and dispatch callbacks."""
        while self.running:
            try:
                if self._pipe_parent.poll(1.0):
                    msg = self._pipe_parent.recv()
                    msg_type = msg.get('type')

                    if msg_type == 'price':
                        asset = msg['symbol']
                        price = msg['price']
                        self.prices[asset] = price
                        self.last_update[asset] = msg['timestamp']

                        if self.on_price_update:
                            try:
                                self.on_price_update(asset, price)
                            except Exception as e:
                                log.error(f"[DeltaWS] Price callback error: {e}")

                    elif msg_type == 'ticker':
                        if self.on_ticker_update:
                            try:
                                self.on_ticker_update(msg['symbol'], msg)
                            except Exception as e:
                                log.error(f"[DeltaWS] Ticker callback error: {e}")

                    elif msg_type == 'status':
                        self.connected = msg.get('connected', False)
                        if self.connected:
                            log.info("[DeltaWS] Connection established (subprocess)")
                            self.reconnect_attempts = 0
                        else:
                            log.warning("[DeltaWS] Connection lost (subprocess)")

                    elif msg_type == 'error':
                        log.error(f"[DeltaWS] Subprocess error: {msg.get('message')}")

            except (EOFError, BrokenPipeError):
                log.warning("[DeltaWS] Pipe closed, subprocess may have exited")
                self.connected = False
                break
            except Exception as e:
                log.error(f"[DeltaWS] Pipe read error: {e}")
                time.sleep(1)

    def start(self):
        """Start the WebSocket subprocess and pipe reader."""
        if self.running:
            log.warning("[DeltaWS] Already running")
            return

        self.running = True

        # Create pipes: price pipe (child->parent), command pipe (parent->child)
        self._pipe_parent, self._pipe_child = multiprocessing.Pipe(duplex=False)
        self._cmd_child, self._cmd_parent = multiprocessing.Pipe(duplex=False)

        # Start subprocess
        self._process = multiprocessing.Process(
            target=_ws_subprocess,
            args=(self._pipe_child, self._cmd_child),
            daemon=True,
            name='delta-price-ws'
        )
        self._process.start()

        # Close child ends in parent
        self._pipe_child.close()
        self._cmd_child.close()

        # Start pipe reader thread
        self._reader_thread = threading.Thread(
            target=self._read_pipe, daemon=True, name='delta-ws-reader'
        )
        self._reader_thread.start()

        log.info(f"[DeltaWS] WebSocket subprocess started (PID: {self._process.pid})")

    def stop(self):
        """Stop the WebSocket subprocess."""
        self.running = False
        self.connected = False

        if self._cmd_parent:
            try:
                self._cmd_parent.send({'action': 'stop'})
            except Exception:
                pass

        if self._process and self._process.is_alive():
            try:
                self._process.terminate()
                self._process.join(timeout=5)
                if self._process.is_alive():
                    self._process.kill()
            except Exception:
                pass

        log.info("[DeltaWS] WebSocket service stopped")

    def get_price(self, symbol: str) -> Optional[float]:
        if symbol in self.prices and self.prices[symbol] > 0:
            return self.prices[symbol]
        return None

    def get_all_prices(self) -> Dict[str, float]:
        return self.prices.copy()

    def is_connected(self) -> bool:
        return self.connected

    def get_status(self) -> Dict:
        return {
            'connected': self.connected,
            'running': self.running,
            'prices': self.prices.copy(),
            'last_update': self.last_update.copy(),
            'reconnect_attempts': self.reconnect_attempts,
            'subscribed_options': list(self.subscribed_options.keys())
        }

    def subscribe_options(self, symbols: list):
        if not symbols:
            return
        with self.subscribed_options_lock:
            for symbol in symbols:
                self.subscribed_options[symbol] = True
        if self._cmd_parent:
            try:
                self._cmd_parent.send({'action': 'subscribe', 'symbols': symbols})
            except Exception as e:
                log.error(f"[DeltaWS] Error sending subscribe command: {e}")

    def unsubscribe_options(self, symbols: list):
        if not symbols:
            return
        with self.subscribed_options_lock:
            for symbol in symbols:
                self.subscribed_options.pop(symbol, None)
        if self._cmd_parent:
            try:
                self._cmd_parent.send({'action': 'unsubscribe', 'symbols': symbols})
            except Exception as e:
                log.error(f"[DeltaWS] Error sending unsubscribe command: {e}")


# Global instance
_price_ws: Optional[DeltaPriceWebSocket] = None


def get_price_websocket() -> DeltaPriceWebSocket:
    """Get global WebSocket instance (singleton)"""
    global _price_ws
    if _price_ws is None:
        _price_ws = DeltaPriceWebSocket()
    return _price_ws


def start_price_service(socketio_instance):
    """
    Start the price WebSocket service and connect it to Socket.IO

    Args:
        socketio_instance: Flask-SocketIO instance for broadcasting
    """
    price_ws = get_price_websocket()

    def broadcast_price(symbol: str, price: float):
        if symbol == 'BTC':
            try:
                from pathlib import Path
                import sys
                backend_dir = str(Path(__file__).parent.parent)
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                from services.price_alert_monitor import get_price_alert_monitor
                get_price_alert_monitor().update_price(price)
            except Exception as e:
                log.error(f"[DeltaWS] Failed to update alert monitor: {e}")

        try:
            socketio_instance.emit('market_price_update', {
                'symbol': symbol,
                'price': price,
                'timestamp': time.time()
            })
        except Exception as e:
            log.error(f"[DeltaWS] Error broadcasting price: {e}")

    def broadcast_ticker(symbol: str, ticker_data: dict):
        try:
            socketio_instance.emit('options_ticker_update', {
                'symbol': symbol,
                'best_bid': ticker_data['best_bid'],
                'best_ask': ticker_data['best_ask'],
                'mark_price': ticker_data['mark_price'],
                'timestamp': ticker_data['timestamp']
            })
        except Exception as e:
            log.error(f"[DeltaWS] Error broadcasting ticker: {e}")

    price_ws.on_price_update = broadcast_price
    price_ws.on_ticker_update = broadcast_ticker
    price_ws.start()

    log.info("[DeltaWS] Price broadcast service started")
    return price_ws
