"""
MMM WebSocket Executions Service

Subscribes to Delta Exchange's private user_trades WebSocket channel.
Records every fill into the persistent sub-ledger (mmm_ledger.py) in real time.

Architecture:
  - Subprocess worker (_ws_executions_worker.py) holds the WS connection.
    Subprocess is isolated from eventlet monkey-patching (same pattern as the
    price-feed worker).
  - Parent process manages the subprocess and owns the in-memory registry.
  - Registry: {client_order_id → {session_id, symbol, side, lots}} maps known
    orders to their session. Rebuilt from active session state on start.
  - On every execution event: look up registry → record_fill() in ledger.

Fill routing without registry entry (e.g. after crash, old coids):
  The coid format is "mmm_{sess_tag}_{side_tag}_{ts}". We cannot reliably
  reverse-map sess_tag back to session_id, so unknown coids are logged at
  WARNING level and skipped (they will be caught by fill_sync REST fallback).
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger('mmm_ws_executions')

try:
    from eventlet.patcher import original as _ev_orig
    _RealThread = _ev_orig('threading').Thread
    _RealLock   = _ev_orig('threading').Lock
except Exception:
    import threading as _th
    _RealThread = _th.Thread
    _RealLock   = _th.Lock

_WORKER_SCRIPT = str(Path(__file__).parent.parent.parent / 'services' / '_ws_executions_worker.py')


class MMMExecutionsWS:
    """
    Manages the authenticated executions WS subprocess and routes fills to the ledger.

    Singleton — call get_executions_ws() to get the instance.
    """

    def __init__(self):
        self.running    = False
        self.connected  = False
        self.authed     = False

        self._process: Optional[subprocess.Popen] = None
        self._reader_thread = None

        # coid → {session_id, symbol, side, lots}
        self._registry: Dict[str, dict] = {}
        self._reg_lock = _RealLock()
        # Track when each coid was registered so stale entries can be evicted.
        # Key: session_id → last order timestamp. Evict sessions absent for > 24h.
        self._reg_timestamps: Dict[str, float] = {}

        self._reconnect_count = 0

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def register_order(
        self,
        client_order_id: str,
        session_id: str,
        symbol: str,
        side: str,
        lots: int,
    ) -> None:
        """
        Register a pending order so execution events can be routed to the right session.
        Call this immediately after generating the coid, before placing the order.
        """
        if not client_order_id or not session_id:
            return
        with self._reg_lock:
            self._registry[client_order_id] = {
                'session_id': session_id,
                'symbol':     symbol,
                'side':       side.lower(),
                'lots':       lots,
            }
            self._reg_timestamps[session_id] = time.time()
            # Evict stale sessions (no new orders for > 24h) to prevent unbounded growth
            if len(self._registry) > 5000:
                self._evict_stale_sessions()

    def unregister_order(self, client_order_id: str) -> None:
        with self._reg_lock:
            self._registry.pop(client_order_id, None)

    def evict_session(self, session_id: str) -> int:
        """
        Remove all registry entries for a session.
        Call this when a session stops/completes so its coids don't accumulate.
        Returns the number of entries removed.
        """
        removed = 0
        with self._reg_lock:
            stale = [k for k, v in self._registry.items() if v['session_id'] == session_id]
            for k in stale:
                del self._registry[k]
                removed += 1
            self._reg_timestamps.pop(session_id, None)
        if removed:
            log.debug('[ExecWS] Evicted %d coid(s) for stopped session %s', removed, session_id)
        return removed

    def _evict_stale_sessions(self) -> None:
        """Evict sessions whose last order was registered more than 24h ago."""
        cutoff = time.time() - 86400
        stale_sids = {sid for sid, ts in self._reg_timestamps.items() if ts < cutoff}
        for sid in stale_sids:
            keys = [k for k, v in self._registry.items() if v['session_id'] == sid]
            for k in keys:
                del self._registry[k]
            del self._reg_timestamps[sid]
        if stale_sids:
            log.info('[ExecWS] Evicted coids for %d stale session(s): %s', len(stale_sids), stale_sids)

    def rebuild_registry_from_sessions(self) -> int:
        """
        Scan all active sessions and re-populate the registry from stored coids.
        Called at startup to recover from a crash that wiped in-memory state.
        Returns number of coids registered.
        """
        count = 0
        try:
            from .mmm_storage import get_storage
            storage   = get_storage()
            active_ids = storage.get_active_session_ids()
            for sid in active_ids:
                try:
                    session = storage.get_session(sid)
                    if not session:
                        continue
                    for sk in ('ce', 'pe'):
                        side_state = session.get(sk, {})
                        for pos in side_state.get('positions', []):
                            # Open (sell) coid
                            coid = pos.get('client_order_id', '')
                            if coid and coid not in self._registry:
                                self._registry[coid] = {
                                    'session_id': sid,
                                    'symbol':     pos.get('symbol', side_state.get('symbol', '')),
                                    'side':       'sell',
                                    'lots':       pos.get('lots', 0),
                                }
                                count += 1
                            # Close (buy) coid
                            close_coid = pos.get('close_client_order_id', '')
                            if close_coid and close_coid not in self._registry:
                                self._registry[close_coid] = {
                                    'session_id': sid,
                                    'symbol':     pos.get('symbol', side_state.get('symbol', '')),
                                    'side':       'buy',
                                    'lots':       pos.get('lots', 0),
                                }
                                count += 1
                except Exception as e:
                    log.warning('[ExecWS] rebuild_registry: error for session %s: %s', sid, e)
        except Exception as e:
            log.warning('[ExecWS] rebuild_registry failed: %s', e)
        log.info('[ExecWS] Registry rebuilt: %d coid(s) from active sessions', count)
        return count

    def start(self) -> None:
        if self.running:
            log.warning('[ExecWS] Already running')
            return

        # Get credentials
        try:
            from config.loader import get_api_credentials
            creds = get_api_credentials()
            api_key    = creds.get('api_key', '')
            api_secret = creds.get('api_secret', '')
        except Exception as e:
            log.error('[ExecWS] Cannot load API credentials: %s', e)
            return

        if not api_key or not api_secret:
            log.error('[ExecWS] API key/secret empty — executions WS will not start')
            return

        # Rebuild registry before starting
        self.rebuild_registry_from_sessions()

        # Build env for subprocess
        worker_env = os.environ.copy()
        worker_env['DELTA_EXEC_API_KEY']    = api_key
        worker_env['DELTA_EXEC_API_SECRET'] = api_secret
        # WS URL from config — mode-aware, mirrors DeltaWebSocket in bot/delta_websocket/delta_ws.py
        try:
            from config.loader import get_config
            cfg = get_config()
            mode = str(getattr(cfg, 'trading_mode', 'live')).lower()
            ws_url = cfg.api.live_ws_url if 'live' in mode else cfg.api.demo_ws_url
        except Exception:
            ws_url = 'wss://socket.india.delta.exchange'
        worker_env['DELTA_EXEC_WS_URL'] = ws_url

        self.running = True
        self._process = subprocess.Popen(
            [sys.executable, _WORKER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=worker_env,
        )

        self._reader_thread = _RealThread(
            target=self._read_stdout, daemon=True, name='mmm-exec-ws-reader'
        )
        self._reader_thread.start()

        log.info('[ExecWS] Executions WS subprocess started (PID %s)', self._process.pid)

    def stop(self) -> None:
        self.running   = False
        self.connected = False
        self.authed    = False
        self._send_cmd({'action': 'stop'})
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        log.info('[ExecWS] Stopped')

    def get_status(self) -> dict:
        with self._reg_lock:
            reg_size = len(self._registry)
        return {
            'running':    self.running,
            'connected':  self.connected,
            'authed':     self.authed,
            'registry_size': reg_size,
            'reconnects': self._reconnect_count,
        }

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _send_cmd(self, cmd: dict) -> None:
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(json.dumps(cmd) + '\n')
                self._process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def _read_stdout(self) -> None:
        proc = self._process
        while self.running and proc and proc.poll() is None:
            try:
                line = proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                self._dispatch(msg)
            except json.JSONDecodeError:
                pass
            except (OSError, ValueError):
                break
            except Exception as e:
                log.error('[ExecWS] Reader error: %s', e)
                time.sleep(0.5)

        self.connected = False
        self.authed    = False
        if self.running:
            log.warning('[ExecWS] Subprocess exited unexpectedly — scheduling restart')
            # Auto-restart: spawn a new process after a short delay.
            # Use a daemon thread so it doesn't block shutdown.
            restart_thread = _RealThread(
                target=self._restart_subprocess, daemon=True, name='mmm-exec-ws-restart'
            )
            restart_thread.start()

    def _restart_subprocess(self) -> None:
        """Restart the executions WS subprocess after it exits unexpectedly."""
        attempt = 0
        max_attempts = 20
        while self.running and attempt < max_attempts:
            attempt += 1
            delay = min(5 * attempt, 60)
            log.info('[ExecWS] Restart attempt %d/%d in %ds', attempt, max_attempts, delay)
            time.sleep(delay)
            if not self.running:
                return
            try:
                # Get fresh credentials for the new process
                from config.loader import get_api_credentials
                creds = get_api_credentials()
                api_key    = creds.get('api_key', '')
                api_secret = creds.get('api_secret', '')
                if not api_key or not api_secret:
                    log.error('[ExecWS] No credentials for restart — aborting')
                    return

                worker_env = os.environ.copy()
                worker_env['DELTA_EXEC_API_KEY']    = api_key
                worker_env['DELTA_EXEC_API_SECRET'] = api_secret
                try:
                    from config.loader import get_config
                    cfg = get_config()
                    mode = str(getattr(cfg, 'trading_mode', 'live')).lower()
                    worker_env['DELTA_EXEC_WS_URL'] = (
                        cfg.api.live_ws_url if 'live' in mode else cfg.api.demo_ws_url
                    )
                except Exception:
                    worker_env['DELTA_EXEC_WS_URL'] = 'wss://socket.india.delta.exchange'

                self._process = subprocess.Popen(
                    [sys.executable, _WORKER_SCRIPT],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    env=worker_env,
                )
                self._reconnect_count += 1
                log.info('[ExecWS] Subprocess restarted (PID %s)', self._process.pid)
                # Hand off to a new reader thread and return from this one
                self._reader_thread = _RealThread(
                    target=self._read_stdout, daemon=True, name='mmm-exec-ws-reader'
                )
                self._reader_thread.start()
                return
            except Exception as e:
                log.error('[ExecWS] Restart attempt %d failed: %s', attempt, e)

        log.error('[ExecWS] Max restart attempts (%d) reached — giving up', max_attempts)

    def _dispatch(self, msg: dict) -> None:
        msg_type = msg.get('type')

        if msg_type == 'status':
            self.connected = msg.get('connected', False)
            self.authed    = msg.get('authenticated', False)
            if self.connected and self.authed:
                log.info('[ExecWS] Connected and authenticated')
            elif not self.connected:
                self._reconnect_count += 1

        elif msg_type == 'execution':
            self._handle_execution(msg.get('trade', {}))

        elif msg_type == 'error':
            log.warning('[ExecWS] Worker error: %s', msg.get('message'))

    def _handle_execution(self, trade: dict) -> None:
        """Route a single trade/fill event to the ledger."""
        if not trade:
            return

        fill_id        = str(trade.get('id', '') or '')
        order_id       = str(trade.get('order_id', '') or '')
        client_oid     = str(trade.get('client_order_id', '') or '')
        symbol         = str(trade.get('symbol', '') or '')
        raw_side       = str(trade.get('side', '') or '').lower()
        commission     = float(trade.get('commission', 0) or 0)

        try:
            price = float(trade.get('price', 0) or 0)
        except (ValueError, TypeError):
            price = 0.0
        try:
            qty = abs(int(float(trade.get('size', 0) or 0)))
        except (ValueError, TypeError):
            qty = 0

        if not fill_id or price <= 0 or qty <= 0:
            return

        # Normalise side: Delta may send 'buy'/'sell' already
        side = raw_side if raw_side in ('buy', 'sell') else None
        if not side:
            log.warning('[ExecWS] Unexpected fill side=%r fill_id=%s', raw_side, fill_id)
            return

        # Resolve session from registry
        with self._reg_lock:
            entry = self._registry.get(client_oid)

        if not entry:
            # Not in registry — log and skip (fill_sync REST fallback will catch it)
            log.warning(
                '[ExecWS] Unknown coid=%s fill_id=%s sym=%s %s %d@%.2f — not in registry, skipping ledger',
                client_oid, fill_id, symbol, side.upper(), qty, price,
            )
            return

        session_id    = entry['session_id']
        ledger_symbol = entry.get('symbol') or symbol

        try:
            from .mmm_ledger import record_fill
            inserted = record_fill(
                session_id=session_id,
                symbol=ledger_symbol,
                side=side,
                qty=qty,
                price=price,
                fill_id=fill_id,
                order_id=order_id,
                client_order_id=client_oid,
                commission=commission,
            )
            if inserted:
                log.info(
                    '[ExecWS] Ledger ✓  sid=%s sym=%s %s %d@%.2f fill_id=%s',
                    session_id, ledger_symbol, side.upper(), qty, price, fill_id,
                )
            else:
                log.debug('[ExecWS] Duplicate fill skipped: fill_id=%s', fill_id)
        except Exception as e:
            log.error('[ExecWS] record_fill error (fill_id=%s): %s', fill_id, e)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[MMMExecutionsWS] = None
_instance_lock = _RealLock()


def get_executions_ws() -> MMMExecutionsWS:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MMMExecutionsWS()
    return _instance
