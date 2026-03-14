"""
Delta Exchange Private WebSocket Service

Subscribes to authenticated `orders` and `positions` channels.
Emits SocketIO events when orders fill or positions change so the frontend
can refresh immediately instead of waiting for the next 5s poll.

Events emitted:
  order_filled      — when an order state=closed/filled, triggers pending-orders + positions refresh
  pending_orders_updated — when any order state changes (new, cancelled)
  positions_updated — when a position changes

Uses the same subprocess pattern as DeltaPriceWebSocket to avoid eventlet contamination.
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

try:
    from eventlet.patcher import original as _ev_orig
    _RealThread = _ev_orig('threading').Thread
except Exception:
    import threading
    _RealThread = threading.Thread

_WORKER_SCRIPT = str(Path(__file__).with_name('_ws_private_worker.py'))


class DeltaPrivateWebSocket:
    """
    Authenticated WebSocket client for Delta Exchange order/position feeds.
    Runs as a subprocess to avoid eventlet contamination.
    """

    def __init__(
        self,
        on_order_update: Optional[Callable] = None,
        on_position_update: Optional[Callable] = None,
    ):
        self.running = False
        self.connected = False
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread = None
        self.on_order_update = on_order_update
        self.on_position_update = on_position_update

    def _read_stdout(self):
        proc = self._process
        while self.running and proc and proc.poll() is None:
            try:
                line = proc.stdout.readline()
                if not line:
                    break

                msg = json.loads(line)
                msg_type = msg.get('type')

                if msg_type == 'order_update':
                    if self.on_order_update:
                        try:
                            self.on_order_update(msg)
                        except Exception as e:
                            log.error(f"[PrivateWS] order_update callback error: {e}")

                elif msg_type == 'position_update':
                    if self.on_position_update:
                        try:
                            self.on_position_update(msg)
                        except Exception as e:
                            log.error(f"[PrivateWS] position_update callback error: {e}")

                elif msg_type == 'status':
                    self.connected = msg.get('connected', False)
                    if self.connected:
                        log.info("[PrivateWS] Authenticated connection established")
                    else:
                        log.warning("[PrivateWS] Connection lost")

                elif msg_type == 'error':
                    log.error(f"[PrivateWS] Subprocess error: {msg.get('message')}")

            except json.JSONDecodeError:
                pass
            except (OSError, ValueError):
                break
            except Exception as e:
                log.error(f"[PrivateWS] Stdout read error: {e}")
                time.sleep(0.5)

        self.connected = False
        if self.running:
            log.warning("[PrivateWS] Subprocess stdout closed")

    def start(self, api_key: str, api_secret: str):
        if self.running:
            log.warning("[PrivateWS] Already running")
            return

        self.running = True
        python_exe = sys.executable

        # Pass credentials via environment variables (never via stdin/args)
        env = os.environ.copy()
        env['DELTA_WS_API_KEY'] = api_key
        env['DELTA_WS_API_SECRET'] = api_secret

        self._process = subprocess.Popen(
            [python_exe, _WORKER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )

        self._reader_thread = _RealThread(
            target=self._read_stdout, daemon=True, name='delta-private-ws-reader'
        )
        self._reader_thread.start()
        log.info(f"[PrivateWS] Subprocess started (PID: {self._process.pid})")

    def _send_cmd(self, cmd: dict):
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(json.dumps(cmd) + '\n')
                self._process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def stop(self):
        self.running = False
        self.connected = False
        self._send_cmd({'action': 'stop'})
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        log.info("[PrivateWS] Service stopped")

    def is_connected(self) -> bool:
        return self.connected


_private_ws: Optional[DeltaPrivateWebSocket] = None


@sealed
def start_private_ws_service(socketio_instance, api_key: str, api_secret: str):
    """
    Start the private WebSocket service and wire it to SocketIO.

    Emitted events:
      - 'order_filled'           — order was filled (state=closed/filled)
      - 'pending_orders_updated' — any order state change
      - 'positions_updated'      — position changed
    """
    global _private_ws

    if not api_key or not api_secret:
        log.warning("[PrivateWS] No API credentials — private WS not started")
        return None

    def on_order_update(msg):
        state = msg.get('state', '')
        reason = msg.get('reason', '')
        symbol = msg.get('symbol', '')

        # Always notify frontend to refresh pending orders
        try:
            socketio_instance.emit('pending_orders_updated', {
                'symbol': symbol,
                'state': state,
                'reason': reason,
                'timestamp': msg.get('timestamp'),
            })
        except Exception as e:
            log.error(f"[PrivateWS] emit pending_orders_updated error: {e}")

        # For fills: also trigger positions refresh
        is_fill = state in ('closed', 'filled') or reason in ('fill', 'filled')
        if is_fill:
            try:
                socketio_instance.emit('order_filled', {
                    'symbol': symbol,
                    'order_id': msg.get('order_id'),
                    'timestamp': msg.get('timestamp'),
                })
                log.info(f"[PrivateWS] Fill detected: {symbol} (state={state}, reason={reason})")
            except Exception as e:
                log.error(f"[PrivateWS] emit order_filled error: {e}")

    def on_position_update(msg):
        try:
            socketio_instance.emit('positions_updated', {
                'symbol': msg.get('symbol', ''),
                'size': msg.get('size'),
                'timestamp': msg.get('timestamp'),
            })
        except Exception as e:
            log.error(f"[PrivateWS] emit positions_updated error: {e}")

    _private_ws = DeltaPrivateWebSocket(
        on_order_update=on_order_update,
        on_position_update=on_position_update,
    )
    _private_ws.start(api_key, api_secret)
    log.info("[PrivateWS] Private WebSocket service started")
    return _private_ws
