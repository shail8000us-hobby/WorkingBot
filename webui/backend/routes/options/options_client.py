"""
Options Client Infrastructure

Dedicated event loop, UnifiedAPIClient singleton, and async helpers.
Extracted from options_control.py — see docs/refactoring/OPTIONS_CONTROL_REFACTOR_PLAN.md

DO NOT move the event loop architecture (_get_dedicated_loop / run_coroutine_threadsafe).
It was built specifically to solve "bound to different event loop" errors.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

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
        # Tune BOTH circuit breakers for WebUI: higher thresholds tolerate
        # the burst of concurrent requests on startup (40 tickers at once);
        # shorter timeouts mean the breakers self-heal quickly if they trip.
        # Outer (UnifiedAPIClient)
        _unified_client_singleton.circuit_breaker.failure_threshold = 50
        _unified_client_singleton.circuit_breaker.timeout = 10
        # Inner (AsyncDeltaClient)
        _unified_client_singleton.rest_client._circuit_breaker.failure_threshold = 50
        _unified_client_singleton.rest_client._circuit_breaker.reset_after = 10
        log.info("✅ UnifiedAPIClient singleton created (both CBs: threshold=50, timeout=10s)")
    return _unified_client_singleton


async def with_timeout(coro, timeout_seconds=30):
    """Execute coroutine with timeout to prevent hanging requests"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"Operation timed out after {timeout_seconds}s")
