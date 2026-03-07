"""
Portfolio Margin WebSocket Client

Connects to Delta Exchange WebSocket for real-time portfolio margin and
wallet margin updates.  Thread-safe with auto-reconnect.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)

WS_URL = 'wss://socket.india.delta.exchange'


class PortfolioMarginWebSocket:
    """WebSocket client for portfolio_margins and margins channels."""

    def __init__(self, auth_payload_fn: Callable[[], Dict[str, str]]):
        """
        Args:
            auth_payload_fn: callable returning {'api-key', 'signature', 'timestamp'}
        """
        self._auth_payload_fn = auth_payload_fn
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False

        # Latest snapshots
        self._portfolio_margin: Dict = {}
        self._wallet_margin: Dict = {}
        self._lock = threading.Lock()

        # Callbacks
        self._on_portfolio_margin = None
        self._on_wallet_margin = None

        # Reconnect config
        self._max_retries = 10
        self._base_delay = 1  # seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def latest_portfolio_margin(self) -> Dict:
        with self._lock:
            return dict(self._portfolio_margin)

    @property
    def latest_wallet_margin(self) -> Dict:
        with self._lock:
            return dict(self._wallet_margin)

    def on_portfolio_margin(self, callback: Callable):
        """Register callback for portfolio_margins channel updates."""
        self._on_portfolio_margin = callback

    def on_wallet_margin(self, callback: Callable):
        """Register callback for margins channel updates."""
        self._on_wallet_margin = callback

    def start(self):
        """Start WebSocket connection in background thread."""
        if self._running:
            log.warning('WebSocket already running')
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name='portfolio-margin-ws',
        )
        self._thread.start()
        log.info('Portfolio margin WebSocket started')

    def stop(self):
        """Stop WebSocket connection."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._connected = False
        log.info('Portfolio margin WebSocket stopped')

    def status(self) -> Dict:
        """Return connection status."""
        return {
            'connected': self._connected,
            'running': self._running,
            'has_portfolio_data': bool(self._portfolio_margin),
            'has_wallet_data': bool(self._wallet_margin),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Main run loop with auto-reconnect."""
        retries = 0
        while self._running:
            try:
                self._connect_and_listen()
                retries = 0  # reset on clean disconnect
            except Exception as exc:
                log.error('WebSocket error: %s', exc)
                self._connected = False
                if not self._running:
                    break
                retries += 1
                if retries > self._max_retries:
                    log.error('Max reconnect retries reached, stopping')
                    self._running = False
                    break
                delay = min(self._base_delay * (2 ** (retries - 1)), 30)
                log.info('Reconnecting in %.1fs (attempt %d/%d)', delay, retries, self._max_retries)
                time.sleep(delay)

    def _connect_and_listen(self):
        """Connect, authenticate, subscribe, and process messages."""
        try:
            import websocket as ws_lib
        except ImportError:
            log.error('websocket-client not installed — pip install websocket-client')
            raise

        log.info('Connecting to %s', WS_URL)
        self._ws = ws_lib.create_connection(WS_URL, timeout=10)
        self._connected = True
        log.info('Connected to Delta Exchange WebSocket')

        # Authenticate
        auth = self._auth_payload_fn()
        auth_msg = json.dumps({
            'type': 'auth',
            'payload': auth,
        })
        self._ws.send(auth_msg)
        resp = json.loads(self._ws.recv())
        if resp.get('type') == 'auth' and resp.get('payload', {}).get('result') == 'success':
            log.info('WebSocket authenticated')
        else:
            log.warning('WebSocket auth response: %s', resp)

        # Subscribe
        sub_msg = json.dumps({
            'type': 'subscribe',
            'payload': {
                'channels': [
                    {'name': 'portfolio_margins', 'symbols': ['.DEXBTUSD']},
                    {'name': 'margins'},
                ],
            },
        })
        self._ws.send(sub_msg)

        # Listen loop
        while self._running:
            try:
                raw = self._ws.recv()
                if not raw:
                    continue
                msg = json.loads(raw)
                self._handle_message(msg)
            except ws_lib.WebSocketTimeoutException:
                continue
            except ws_lib.WebSocketConnectionClosedException:
                log.warning('WebSocket connection closed')
                self._connected = False
                break

    def _handle_message(self, msg: Dict):
        """Route incoming message to handlers."""
        msg_type = msg.get('type', '')
        channel = msg.get('channel', '')

        if channel == 'portfolio_margins':
            data = msg.get('data', msg.get('payload', {}))
            with self._lock:
                self._portfolio_margin = data
            if self._on_portfolio_margin:
                try:
                    self._on_portfolio_margin(data)
                except Exception as exc:
                    log.error('portfolio_margin callback error: %s', exc)

        elif channel == 'margins':
            data = msg.get('data', msg.get('payload', {}))
            with self._lock:
                self._wallet_margin = data
            if self._on_wallet_margin:
                try:
                    self._on_wallet_margin(data)
                except Exception as exc:
                    log.error('wallet_margin callback error: %s', exc)

        elif msg_type == 'subscriptions':
            log.info('Subscribed to: %s', msg.get('payload', {}).get('channels', []))

        elif msg_type == 'error':
            log.error('WS error message: %s', msg)
