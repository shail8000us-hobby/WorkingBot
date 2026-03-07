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
_loop_lock = threading.Lock()


def _get_dedicated_loop() -> asyncio.AbstractEventLoop:
    """Return (and lazily create) the single persistent event loop."""
    global _dedicated_loop, _loop_thread

    with _loop_lock:
        if _dedicated_loop is not None and not _dedicated_loop.is_closed():
            return _dedicated_loop

        _dedicated_loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(
            target=_dedicated_loop.run_forever,
            daemon=True,
            name="options-async-loop",
        )
        _loop_thread.start()
        return _dedicated_loop


def _run_async(coro):
    """Run an async coroutine from sync Flask context.

    Submits *coro* to a **dedicated persistent event loop** running in a
    background daemon thread and blocks until the result is available.

    This guarantees that all asyncio-bound objects (httpx ``AsyncClient``,
    ``asyncio.Event``, ``asyncio.Lock``, etc.) created by the singleton
    ``UnifiedAPIClient`` always execute on the **same** loop, eliminating
    the "bound to a different event loop" errors.
    """
    loop = _get_dedicated_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


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
