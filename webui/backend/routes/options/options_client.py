"""
Options Client Infrastructure

Dedicated event loop, UnifiedAPIClient singleton, and async helpers.
Extracted from options_control.py — see docs/refactoring/OPTIONS_CONTROL_REFACTOR_PLAN.md

DO NOT move the event loop architecture (_get_dedicated_loop / run_coroutine_threadsafe).
It was built specifically to solve "bound to different event loop" errors.

Named/isolated clients (get_named_client):
Each monitor/algo can own a separate asyncio event loop + httpx connection pool.
Fault isolation: if one loop blocks or deadlocks, the others keep running.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional, Dict

import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dedicated event loop for async operations
# ---------------------------------------------------------------------------
# A single persistent event loop runs in a daemon thread.  ALL async work
# (httpx calls, asyncio locks/events inside the singleton UnifiedAPIClient)
# is submitted to this loop via ``run_coroutine_threadsafe``.  This prevents
# the "<asyncio.locks.Event> is bound to a different event loop" errors that
# occurred when each Flask request created / obtained a different loop.
# ---------------------------------------------------------------------------
_dedicated_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None

# MUST be a real (unpatched) OS lock, NOT an eventlet semaphore.
# _loop_lock is acquired from both eventlet greenlets (Flask requests) AND
# real OS threads (monitor init, IV recorder, asyncio callbacks).
# If this were an eventlet monkey-patched threading.Lock, acquiring it from
# a real OS thread would corrupt the eventlet hub's greenlet scheduler:
#   greenlet.error: Cannot switch to a different thread
try:
    from eventlet.patcher import original as _ev_orig
    _loop_lock = _ev_orig('threading').Lock()
except Exception:
    import threading as _stdlib_threading
    _loop_lock = _stdlib_threading.Lock()


def _get_dedicated_loop() -> asyncio.AbstractEventLoop:
    """Return (and lazily create) the single persistent event loop.

    IMPORTANT: The loop MUST run in a real OS thread, not an eventlet greenlet.
    eventlet.monkey_patch() replaces threading.Thread with a greenlet-based
    implementation.  If the asyncio loop ran in a greenlet, asyncio's own I/O
    selector (kqueue/epoll) would conflict with eventlet's hub, causing hangs.
    We use eventlet.patcher.original('threading') to get the unpatched Thread
    so the loop always gets a genuine OS thread.
    """
    global _dedicated_loop, _loop_thread

    with _loop_lock:
        if _dedicated_loop is not None and not _dedicated_loop.is_closed():
            return _dedicated_loop

        _dedicated_loop = asyncio.new_event_loop()

        # Real OS thread — bypasses eventlet's greenlet substitution.
        try:
            from eventlet.patcher import original as _orig
            _RealThread = _orig('threading').Thread
        except Exception:
            _RealThread = threading.Thread  # fallback when not under eventlet

        _loop_thread = _RealThread(
            target=_dedicated_loop.run_forever,
            daemon=True,
            name="options-async-loop",
        )
        _loop_thread.start()
        return _dedicated_loop


def _run_async(coro, timeout=20):
    """Run an async coroutine cooperatively from a sync Flask/eventlet context.

    Submits *coro* to the dedicated asyncio loop (real OS thread) then POLLs
    ``future.done()`` with a sleep between checks.

    Yield strategy depends on the calling context:
    - Flask/gunicorn greenlet (main OS thread): use eventlet.sleep() so other
      greenlets (health checks, WebSocket heartbeats) continue to be served.
    - Real OS thread (monitors, IV recorder, background tasks): use time.sleep()
      because eventlet.sleep() from a real thread corrupts the eventlet hub.

    Default timeout is 20 s — enough for typical Delta Exchange latency.
    """
    import time as _time

    # Detect whether we're running in the gunicorn eventlet worker thread.
    # gunicorn's eventlet worker runs in the process's main thread; Flask
    # requests are greenlets within it.  Real OS threads we create for monitors
    # and background tasks are NOT the main thread.
    _yield = _time.sleep  # safe default for real OS threads
    try:
        from eventlet.patcher import original as _ev_orig
        _orig_threading = _ev_orig('threading')
        if _orig_threading.current_thread() is _orig_threading.main_thread():
            import eventlet as _ev
            _yield = _ev.sleep
    except Exception:
        pass

    loop = _get_dedicated_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    deadline = _time.time() + timeout
    while not future.done():
        if _time.time() >= deadline:
            future.cancel()
            raise TimeoutError(f"Async operation timed out after {timeout} s")
        _yield(0.01)  # 10ms sleep — prevents CPU spin while staying responsive

    return future.result(timeout=0)  # already done — returns immediately


# Singleton UnifiedAPIClient — creating a new client on every request opens
# aiohttp connection pools and sockets that never close, rapidly exhausting
# the OS file-descriptor limit ([Errno 24] Too many open files).
_unified_client_singleton = None


def get_unified_client():
    """Get a shared (singleton) UnifiedAPIClient with credentials from config.

    The client is created once on first call and reused for all subsequent
    requests.  This prevents runaway file-descriptor accumulation from
    creating a new connection pool on every call.
    """
    global _unified_client_singleton
    if _unified_client_singleton is None:
        from bot.api.unified_api_client import UnifiedAPIClient
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        _unified_client_singleton = UnifiedAPIClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            symbol='BTCUSD',
            enable_websocket=False
        )
        # Circuit breakers: high thresholds tolerate startup bursts; short recovery.
        # Outer (UnifiedAPIClient)
        _unified_client_singleton.circuit_breaker.failure_threshold = 50
        _unified_client_singleton.circuit_breaker.timeout = 10
        # Inner (AsyncDeltaClient)
        _unified_client_singleton.rest_client._circuit_breaker.failure_threshold = 50
        _unified_client_singleton.rest_client._circuit_breaker.reset_after = 10
        log.info("✅ UnifiedAPIClient singleton created (CBs: threshold=50, timeout=10s; "
                 "max_connections=100 — Delta 10k-unit/5min quota, no client throttle)")
    return _unified_client_singleton


async def with_timeout(coro, timeout_seconds=30):
    """Execute coroutine with timeout to prevent hanging requests"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"Operation timed out after {timeout_seconds}s")


# ---------------------------------------------------------------------------
# Isolated async clients — one dedicated loop + httpx pool per named caller
# ---------------------------------------------------------------------------
# Each monitor/algo that calls get_named_client("sl_tp") / get_named_client("max_loss")
# gets its own asyncio event loop running in its own real OS thread, plus its own
# AsyncDeltaClient (separate httpx connection pool).
#
# Benefits:
# 1. Fault isolation — a blocked/slow loop for one monitor cannot starve another.
# 2. No connection-pool contention — each caller has dedicated connections.
# 3. If one loop deadlocks the others keep running independently.
# ---------------------------------------------------------------------------

# Use original (unpatched) threading.Lock for cross-greenlet/thread safety.
try:
    from eventlet.patcher import original as _ev_orig_nc
    _named_clients_lock = _ev_orig_nc('threading').Lock()
except Exception:
    _named_clients_lock = threading.Lock()

_named_clients: Dict[str, "_IsolatedAsyncClient"] = {}


class _IsolatedAsyncClient:
    """Encapsulates an asyncio event loop + AsyncDeltaClient for one named caller.

    Never create this directly — use get_named_client(name).
    """

    def __init__(self, name: str, max_connections: int = 10):
        self.name = name

        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        self._delta_client = AsyncDeltaClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            max_connections=max_connections,
        )

        # Own event loop in a real (unpatched) OS thread.
        self._loop = asyncio.new_event_loop()
        try:
            from eventlet.patcher import original as _orig
            _RealThread = _orig('threading').Thread
        except Exception:
            _RealThread = threading.Thread

        t = _RealThread(
            target=self._loop.run_forever,
            daemon=True,
            name=f"async-loop-{name}",
        )
        t.start()
        self._thread = t
        log.info(f"✅ IsolatedAsyncClient '{name}' ready (max_connections={max_connections})")

    @property
    def rest_client(self):
        """Direct access to the underlying AsyncDeltaClient."""
        return self._delta_client

    def run_async(self, coro, timeout: float = 20.0):
        """Submit *coro* to this client's dedicated loop and block until done.

        Uses the same yield strategy as the shared _run_async: eventlet.sleep()
        when called from the main eventlet thread, time.sleep() from real OS threads.
        """
        import time as _time

        _yield = _time.sleep
        try:
            from eventlet.patcher import original as _ev_orig2
            _orig_threading = _ev_orig2('threading')
            if _orig_threading.current_thread() is _orig_threading.main_thread():
                import eventlet as _ev
                _yield = _ev.sleep
        except Exception:
            pass

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        deadline = _time.time() + timeout
        while not future.done():
            if _time.time() >= deadline:
                future.cancel()
                raise TimeoutError(f"[{self.name}] Async operation timed out after {timeout}s")
            _yield(0.01)

        return future.result(timeout=0)


def get_named_client(name: str, max_connections: int = 10) -> "_IsolatedAsyncClient":
    """Get (or lazily create) an isolated async client for the given caller name.

    Each name gets its own asyncio event loop thread + httpx connection pool.
    Typical callers:
        get_named_client("sl_tp")       # SL/TP monitor
        get_named_client("max_loss")    # Max-loss monitor
        get_named_client("tp_monitor")  # Take-profit monitor

    The shared singleton (get_unified_client / _run_async) is reserved for
    the options control routes that serve the frontend.
    """
    with _named_clients_lock:
        if name not in _named_clients:
            _named_clients[name] = _IsolatedAsyncClient(name, max_connections=max_connections)
        return _named_clients[name]
