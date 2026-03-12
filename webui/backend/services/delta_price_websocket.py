"""
Delta Exchange WebSocket Price Service

Connects to Delta Exchange WebSocket API to fetch real-time BTC and ETH index prices.
Broadcasts prices to frontend clients via Socket.IO.

Architecture: Uses subprocess.Popen to run a standalone worker script in a completely
separate Python process with ZERO eventlet contamination.  Communication is via
JSON lines over stdin (parent→child commands) and stdout (child→parent data).

Created: January 18, 2026
Author: SSR Bot
"""

import json
import logging
import os
import subprocess
import sys
import time
from typing import Dict, Optional, Callable
from pathlib import Path

log = logging.getLogger(__name__)

# Use real OS thread/lock — after eventlet.monkey_patch() the standard
# threading primitives are green and won't work from a real OS thread.
try:
    from eventlet.patcher import original as _ev_orig
    _RealThread = _ev_orig('threading').Thread
    _RealLock = _ev_orig('threading').Lock
except Exception:
    import threading
    _RealThread = threading.Thread
    _RealLock = threading.Lock

# Path to the standalone worker script (no eventlet imports)
_WORKER_SCRIPT = str(Path(__file__).with_name('_ws_subprocess_worker.py'))


class DeltaPriceWebSocket:
    """
    WebSocket client for Delta Exchange index prices.

    Runs a standalone worker script via subprocess.Popen to guarantee zero
    eventlet contamination.  Communication uses JSON lines over stdin/stdout.
    """

    def __init__(self, on_price_update: Optional[Callable] = None, on_ticker_update: Optional[Callable] = None):
        self.running = False
        self.connected = False
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread = None

        # Price storage
        self.prices: Dict[str, float] = {'BTC': 0.0, 'ETH': 0.0}
        self.last_update: Dict[str, float] = {'BTC': 0.0, 'ETH': 0.0}

        # Options ticker subscriptions
        self.subscribed_options: Dict[str, bool] = {}
        self.subscribed_options_lock = _RealLock()

        # Callbacks
        self.on_price_update = on_price_update
        self.on_ticker_update = on_ticker_update

        self.reconnect_attempts = 0

    def _read_stdout(self):
        """Read JSON lines from the subprocess stdout and dispatch callbacks.

        Runs in a REAL OS thread (not a green thread).
        """
        proc = self._process
        while self.running and proc and proc.poll() is None:
            try:
                line = proc.stdout.readline()
                if not line:
                    break  # EOF — subprocess exited

                msg = json.loads(line)
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

            except json.JSONDecodeError:
                pass
            except (OSError, ValueError):
                break
            except Exception as e:
                log.error(f"[DeltaWS] Stdout read error: {e}")
                time.sleep(0.5)

        self.connected = False
        if self.running:
            log.warning("[DeltaWS] Subprocess stdout closed, process may have exited")

    def start(self):
        """Start the WebSocket subprocess and stdout reader."""
        if self.running:
            log.warning("[DeltaWS] Already running")
            return

        self.running = True

        # Use the same Python interpreter that is running this process
        python_exe = sys.executable

        # Launch the standalone worker script — clean process, no eventlet
        self._process = subprocess.Popen(
            [python_exe, _WORKER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # line-buffered
        )

        # Start stdout reader in a REAL OS thread
        self._reader_thread = _RealThread(
            target=self._read_stdout, daemon=True, name='delta-ws-reader'
        )
        self._reader_thread.start()

        log.info(f"[DeltaWS] WebSocket subprocess started (PID: {self._process.pid})")

    def _send_cmd(self, cmd: dict):
        """Send a JSON command to the subprocess via stdin."""
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(json.dumps(cmd) + '\n')
                self._process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def stop(self):
        """Stop the WebSocket subprocess."""
        self.running = False
        self.connected = False

        self._send_cmd({'action': 'stop'})

        if self._process:
            try:
                self._process.terminate()
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
        self._send_cmd({'action': 'subscribe', 'symbols': symbols})

    def unsubscribe_options(self, symbols: list):
        if not symbols:
            return
        with self.subscribed_options_lock:
            for symbol in symbols:
                self.subscribed_options.pop(symbol, None)
        self._send_cmd({'action': 'unsubscribe', 'symbols': symbols})


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
