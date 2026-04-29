"""
options_ws_cache.py — WebSocket-backed in-memory position + mark price cache
for options monitors.

Architecture
============
One asyncio event loop runs in a real (unpatched) OS thread — same pattern
as _IsolatedAsyncClient in options_client.py.

Inside that loop, an AsyncWebSocketManager maintains:
  • l1_orderbook ["call_options", "put_options"]
      → mark price updates every ~500 ms on quote change
  • user_trades  ["BTCUSD"]   (authenticated)
      → fill notification → immediately refreshes positions via REST

REST calls are used for:
  • Initial position load at startup
  • On every fill event  (position state changed)
  • Fallback: every 60 s (belt-and-suspenders if fill channel misses an event)

Monitors (sl_tp_monitor, max_loss_manager) call:
    get_ws_cache().get_positions()   → zero REST calls in steady state
    get_ws_cache().get_mark_price(symbol)

If the WS cache is unhealthy (WS disconnected or positions > 2 min stale),
callers fall back to the shared options_control cache → then isolated REST.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-safe primitives — must NOT use eventlet-patched threading.Lock
# ---------------------------------------------------------------------------
try:
    from eventlet.patcher import original as _ev_orig
    _RealLock = _ev_orig('threading').Lock
    _RealThread = _ev_orig('threading').Thread
except Exception:
    import threading as _stdlib_threading
    _RealLock = _stdlib_threading.Lock
    _RealThread = _stdlib_threading.Thread

# ---------------------------------------------------------------------------
# Singleton cache instance + factory lock
# ---------------------------------------------------------------------------
_ws_cache_instance: Optional["_OptionsWSCache"] = None
_ws_cache_lock = _RealLock()

# Cooldown between consecutive fill-triggered REST fetches (seconds).
# Prevents a burst of rapid fills from hammering the API.
_FILL_REFRESH_COOLDOWN = 3.0

# If no REST refresh within this window, consider positions stale.
_STALE_THRESHOLD = 120.0  # 2 minutes

# Fallback REST poll interval when WS is healthy (seconds).
_REST_POLL_INTERVAL = 60.0


class _OptionsWSCache:
    """
    WebSocket-backed position + mark price cache.

    Never instantiate directly — use get_ws_cache().
    """

    def __init__(self) -> None:
        # Positions from REST (refreshed on fills or fallback timer).
        # {product_symbol: position_dict}
        self._positions: Dict[str, Dict] = {}

        # Snapshot of positions from the previous REST refresh.
        # Used to detect size→0 transitions (algo/manual closes) so they can be
        # persisted to ClosedPositionStore before being filtered out.
        # {product_symbol: position_dict}
        self._prev_positions: Dict[str, Dict] = {}

        # Mark prices from l1_orderbook WS messages.
        # {product_symbol: float}
        self._mark_prices: Dict[str, float] = {}

        # Threading primitives (unpatched — safe from real OS threads AND greenlets)
        self._lock = _RealLock()

        self._last_position_refresh: float = 0.0
        self._last_fill_refresh: float = 0.0
        self._running: bool = True

        # Will be set in _main()
        self._ws_manager = None
        self._rest_client = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Start background thread
        self._start()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _start(self) -> None:
        self._loop = asyncio.new_event_loop()
        t = _RealThread(
            target=self._run_thread,
            daemon=True,
            name="options-ws-cache",
        )
        t.start()
        log.info("✅ OptionsWSCache background thread starting…")

    def _run_thread(self) -> None:
        """Entry point for the background OS thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as exc:
            log.error(f"[OptionsWSCache] _main() crashed: {exc}", exc_info=True)

    # ------------------------------------------------------------------
    # Async main loop (runs inside the dedicated event loop)
    # ------------------------------------------------------------------

    async def _main(self) -> None:
        """Set up WS + REST clients, connect, subscribe, then run fallback loop."""
        from bot.api.async_delta_client import AsyncDeltaClient
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        from config.loader import get_api_credentials

        creds = get_api_credentials()

        self._rest_client = AsyncDeltaClient(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            max_connections=10,
        )

        self._ws_manager = AsyncWebSocketManager(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
        )

        # Register message handlers
        self._ws_manager.register_handler("l1_orderbook", self._on_l1_orderbook)
        self._ws_manager.register_handler("user_trades", self._on_fill)

        # On reconnect: re-subscribe l1_orderbook (it's not in the manager's
        # auto-restore list) and refresh positions.
        self._ws_manager.register_reconnect_callback(self._on_reconnect)

        # Pre-populate _prev_positions from the persisted last-seen state so close
        # detection works on the very first refresh even after a backend restart.
        try:
            from .closed_position_store import get_closed_position_store
            seen = get_closed_position_store().get_last_seen()
            if seen:
                with self._lock:
                    self._prev_positions = seen
                log.info(f"[OptionsWSCache] Loaded {len(seen)} seen positions for close detection")
        except Exception as exc:
            log.debug(f"[OptionsWSCache] Seen pre-load failed: {exc}")

        # Initial position fetch (REST) before WS connects so monitors have
        # data immediately even if WS auth takes a few seconds.
        await self._refresh_positions(reason="startup")

        # Connect WebSocket (subscribes to user_trades after auth automatically;
        # l1_orderbook is subscribed below after connect returns).
        try:
            await self._ws_manager.connect()
            await self._ws_manager.subscribe(
                "l1_orderbook", ["call_options", "put_options"]
            )
            await self._ws_manager.subscribe("user_trades", ["BTCUSD"])
            log.info("✅ OptionsWSCache WS connected + subscribed")
        except Exception as exc:
            log.error(f"[OptionsWSCache] WS connect failed: {exc} — will retry on reconnect")

        # Fallback REST poll loop
        while self._running:
            await asyncio.sleep(_REST_POLL_INTERVAL)
            try:
                await self._refresh_positions(reason="fallback-60s")
            except Exception as exc:
                log.warning(f"[OptionsWSCache] Fallback REST refresh failed: {exc}")

    # ------------------------------------------------------------------
    # WebSocket event handlers
    # ------------------------------------------------------------------

    async def _on_l1_orderbook(self, message: dict) -> None:
        """Update mark price from l1_orderbook push (~500 ms cadence)."""
        try:
            data = message.get("data", {})
            symbol = data.get("symbol", "")
            if not (symbol.startswith("C-") or symbol.startswith("P-")):
                return

            bid = float(data.get("best_bid", 0) or 0)
            ask = float(data.get("best_ask", 0) or 0)
            mark_price = data.get("mark_price")

            if mark_price is not None:
                mark = float(mark_price or 0)
            elif bid > 0 and ask > 0:
                mark = (bid + ask) / 2.0
            elif bid > 0:
                mark = bid
            elif ask > 0:
                mark = ask
            else:
                return

            with self._lock:
                self._mark_prices[symbol] = mark
                if symbol in self._positions:
                    self._positions[symbol]["mark_price"] = mark
                    # Recalculate unrealized PnL with fresh mark.
                    # Prices are USD/BTC; 1 lot = 0.001 BTC — must apply LOT_MULT.
                    pos = self._positions[symbol]
                    size = pos.get("size", 0)
                    entry = pos.get("entry_price", 0)
                    if size and entry:
                        pos["unrealized_pnl"] = (mark - entry) * size * 0.001
        except Exception as exc:
            log.debug(f"[OptionsWSCache] l1_orderbook handler error: {exc}")

    async def _on_fill(self, message: dict) -> None:
        """Fill event received — refresh positions (with cooldown)."""
        now = time.time()
        if now - self._last_fill_refresh < _FILL_REFRESH_COOLDOWN:
            return  # Too soon — a refresh is already in flight or just completed

        self._last_fill_refresh = now
        log.debug("[OptionsWSCache] Fill event received — refreshing positions")
        try:
            await self._refresh_positions(reason="fill-event")
        except Exception as exc:
            log.warning(f"[OptionsWSCache] Fill-triggered refresh failed: {exc}")

    async def _on_reconnect(self) -> None:
        """Called by AsyncWebSocketManager after successful reconnection."""
        log.info("[OptionsWSCache] WS reconnected — re-subscribing l1_orderbook + refreshing positions")
        try:
            await self._ws_manager.subscribe(
                "l1_orderbook", ["call_options", "put_options"]
            )
        except Exception as exc:
            log.warning(f"[OptionsWSCache] Re-subscribe l1_orderbook failed: {exc}")
        await self._refresh_positions(reason="ws-reconnect")

    # ------------------------------------------------------------------
    # REST position refresh
    # ------------------------------------------------------------------

    async def _refresh_positions(self, reason: str = "") -> None:
        """Fetch all options positions via REST and merge with cached mark prices."""
        try:
            all_pos = await self._rest_client.get_positions_margined()

            # Build a quick lookup of what the exchange reports RIGHT NOW (including size=0)
            exchange_map: Dict[str, float] = {}
            for p in all_pos:
                sym = p.get("product_symbol", "")
                if sym.startswith("C-") or sym.startswith("P-"):
                    exchange_map[sym] = float(p.get("size", 0) or 0)

            # Detect positions that were open in the previous snapshot but are now gone
            # (size=0 or absent entirely). Save them to ClosedPositionStore.
            if self._prev_positions:
                try:
                    from .closed_position_store import get_closed_position_store
                    store = get_closed_position_store()
                    for sym, prev_pos in self._prev_positions.items():
                        prev_size = float(prev_pos.get("size", 0) or 0)
                        curr_size = exchange_map.get(sym, 0)
                        if prev_size != 0 and curr_size == 0:
                            # Position fully closed — use API-provided unrealized_pnl as realized.
                            # Prices are USD/BTC, size is in lots (1 lot = 0.001 BTC), so
                            # the manual formula needs * 0.001.  The REST unrealized_pnl field
                            # is already in USD and is more accurate (it uses the exchange's own
                            # mark model), so prefer it.
                            realized = float(prev_pos.get("unrealized_pnl", 0) or 0)
                            if realized == 0:
                                # Fallback if unrealized_pnl wasn't populated yet
                                mark = float(prev_pos.get("mark_price", 0) or 0)
                                entry = float(prev_pos.get("entry_price", 0) or 0)
                                if mark == 0:
                                    mark = entry
                                realized = (mark - entry) * prev_size * 0.001
                            store.record_close(prev_pos, realized)
                except Exception as exc:
                    log.debug(f"[OptionsWSCache] ClosedPositionStore update failed: {exc}")

            new_positions: Dict[str, Dict] = {}

            for p in all_pos:
                symbol = p.get("product_symbol", "")
                if not (symbol.startswith("C-") or symbol.startswith("P-")):
                    continue
                size = float(p.get("size", 0) or 0)
                if size == 0:
                    continue
                p["size"] = size
                p["entry_price"] = float(p.get("entry_price", 0) or 0)
                p["mark_price"] = float(p.get("mark_price", 0) or 0)
                p["unrealized_pnl"] = float(p.get("unrealized_pnl", 0) or 0)
                new_positions[symbol] = p

            with self._lock:
                self._prev_positions = dict(self._positions)  # snapshot before overwrite
                self._positions = new_positions
                # Merge any fresher mark prices from WS
                for sym, mark in self._mark_prices.items():
                    if sym in self._positions:
                        self._positions[sym]["mark_price"] = mark
                        pos = self._positions[sym]
                        size = pos.get("size", 0)
                        entry = pos.get("entry_price", 0)
                        if size and entry:
                            pos["unrealized_pnl"] = (mark - entry) * size * 0.001
                self._last_position_refresh = time.time()

            count = len(new_positions)
            log.info(f"[OptionsWSCache] Positions refreshed ({reason}): {count} options")

            # Persist last-known live state so close detection survives backend restarts.
            try:
                from .closed_position_store import get_closed_position_store
                store2 = get_closed_position_store()
                store2.record_seen_batch(list(new_positions.values()))
                store2.flush_seen()
            except Exception as exc2:
                log.debug(f"[OptionsWSCache] Seen-state persist failed: {exc2}")

        except Exception as exc:
            log.error(f"[OptionsWSCache] _refresh_positions({reason}) failed: {exc}")
            raise

    # ------------------------------------------------------------------
    # Public read API (sync — safe to call from any thread/greenlet)
    # ------------------------------------------------------------------

    def get_positions(self) -> List[Dict]:
        """Return a snapshot of all open options positions (thread-safe)."""
        with self._lock:
            return list(self._positions.values())

    def get_mark_price(self, symbol: str) -> Optional[float]:
        """Return cached mark price for *symbol*, or None if unknown."""
        with self._lock:
            mark = self._mark_prices.get(symbol)
            if mark is not None:
                return mark
            pos = self._positions.get(symbol)
            return pos.get("mark_price") if pos else None

    @property
    def is_healthy(self) -> bool:
        """True when WS is connected AND positions are fresh (< 2 min old)."""
        ws_ok = bool(
            self._ws_manager
            and getattr(self._ws_manager, "is_connected", False)
        )
        fresh = (time.time() - self._last_position_refresh) < _STALE_THRESHOLD
        return ws_ok and fresh

    def age_seconds(self) -> float:
        """Seconds since the last successful REST position refresh."""
        if self._last_position_refresh == 0:
            return float("inf")
        return time.time() - self._last_position_refresh

    def stats(self) -> dict:
        """Diagnostic snapshot for /api/options/ws-cache-stats."""
        with self._lock:
            return {
                "healthy": self.is_healthy,
                "position_count": len(self._positions),
                "mark_price_count": len(self._mark_prices),
                "age_seconds": round(self.age_seconds(), 1),
                "ws_connected": bool(
                    self._ws_manager
                    and getattr(self._ws_manager, "is_connected", False)
                ),
            }


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

def get_ws_cache() -> _OptionsWSCache:
    """Return (or lazily create) the shared OptionsWSCache singleton."""
    global _ws_cache_instance
    if _ws_cache_instance is None:
        with _ws_cache_lock:
            if _ws_cache_instance is None:
                _ws_cache_instance = _OptionsWSCache()
    return _ws_cache_instance
