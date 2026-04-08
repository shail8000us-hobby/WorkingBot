"""
MMMX Audit Log — Append-Only Trade & Order Journal

Write-only queue → background daemon thread → SQLite (mmmx_sessions.db audit_log table).
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1.

Design:
  - enqueue_trade() / enqueue_event() return in < 1µs (queue.put_nowait).
  - Background daemon flushes every _FLUSH_SECS or after _BATCH_SIZE entries.
  - INSERT OR IGNORE on idempotency_key prevents duplicate rows on crash/restart.
  - No UPDATE or DELETE ever issued.
  - atexit handler flushes remaining queue on shutdown.

Usage:
    from .mmmx_audit_log import get_audit_log
    get_audit_log().enqueue_trade(session_id=..., action='SELL', ...)
    get_audit_log().enqueue_event(session_id=..., category='TRIGGER', ...)
"""

import atexit
import json
import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .mmmx_constants import LOT_SIZE_BTC

log = logging.getLogger('mmmx_audit_log')

_BATCH_SIZE = 10
_FLUSH_SECS = 2.0
_MAX_QUEUE  = 2000


class MMMXAuditLog:
    """Append-only, queue-backed audit log."""

    def __init__(self, storage=None):
        self._storage = storage
        self._queue: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._writer_loop,
            name='mmmx_audit_writer',
            daemon=True,
        )
        self._thread.start()
        atexit.register(self._flush_on_exit)

    def set_storage(self, storage) -> None:
        self._storage = storage

    # ── Public enqueue API ─────────────────────────────────────────────────────

    def enqueue_trade(
        self,
        session_id: str,
        action: str,               # 'BUY' | 'SELL'
        symbol: str,
        lots: int,
        price: float,
        tranche_id,
        side: str,                 # 'ce' | 'pe'
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        generation: Optional[int] = None,
        filled_size: Optional[int] = None,
        fees_paid: float = 0.0,
        extra: Optional[Dict] = None,
    ) -> None:
        """
        Record an order fill (BUY or SELL) that touches real money.
        Idempotency key: client_order_id (if provided).
        """
        idempotency_key = client_order_id or order_id
        usd_value = price * lots * LOT_SIZE_BTC
        data = {
            'action':          action,
            'symbol':          symbol,
            'lots':            lots,
            'filled_size':     filled_size if filled_size is not None else lots,
            'price':           price,
            'usd_value':       round(usd_value, 4),
            'tranche_id':      str(tranche_id),
            'side':            side,
            'order_id':        order_id,
            'client_order_id': client_order_id,
            'fees_paid':       fees_paid,
            **(extra or {}),
        }
        self._enqueue(
            session_id=session_id,
            event_type='TRADE',
            data=data,
            idempotency_key=idempotency_key,
            generation=generation,
        )

    def enqueue_event(
        self,
        session_id: str,
        category: str,              # 'TRIGGER' | 'SAFETY' | 'SHIELD' | 'DEPLOY' | ...
        message: str,
        data: Optional[Dict] = None,
        generation: Optional[int] = None,
    ) -> None:
        """Record an operational state change (trigger fired, shield event, etc.)."""
        self._enqueue(
            session_id=session_id,
            event_type=f'EVENT:{category}',
            data={'message': message, **(data or {})},
            generation=generation,
        )

    # ── Internal ───────────────────────────────────────────────────────────────

    def _enqueue(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> None:
        entry = {
            'session_id':       session_id,
            'event_type':       event_type,
            'data':             data,
            'idempotency_key':  idempotency_key,
            'generation':       generation,
            'created_at':       datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            log.error(
                f"MMMX audit queue full ({_MAX_QUEUE})! Dropping event {event_type} "
                f"for session {session_id}."
            )

    def _writer_loop(self) -> None:
        batch = []
        while not self._stop_event.is_set():
            try:
                entry = self._queue.get(timeout=_FLUSH_SECS)
                batch.append(entry)
                while len(batch) < _BATCH_SIZE:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                pass

            if batch:
                self._write_batch(batch)
                batch = []

    def _write_batch(self, batch) -> None:
        if self._storage is None:
            return
        for entry in batch:
            try:
                self._storage.append_audit_event(
                    session_id=entry['session_id'],
                    event_type=entry['event_type'],
                    data=entry['data'],
                    idempotency_key=entry.get('idempotency_key'),
                    generation=entry.get('generation'),
                )
            except Exception as exc:
                log.error(f"Failed to write audit entry: {exc}")

    def _flush_on_exit(self) -> None:
        """Flush remaining queue entries on process shutdown."""
        batch = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._write_batch(batch)


# ── Singleton ──────────────────────────────────────────────────────────────────
_instance: Optional[MMMXAuditLog] = None
_init_lock = threading.Lock()


def get_audit_log(storage=None) -> MMMXAuditLog:
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = MMMXAuditLog(storage=storage)
    elif storage is not None and _instance._storage is None:
        _instance.set_storage(storage)
    return _instance
