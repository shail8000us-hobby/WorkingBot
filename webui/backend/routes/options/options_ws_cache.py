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
from webui.backend.sealed import sealed

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

# Seconds after a fill before running close detection. The exchange REST API
# may transiently return size=0 for a position that is just being adjusted, which
# would produce a false phantom row. Waiting gives the exchange time to settle.
_FILL_CLOSE_DETECT_DELAY = 8.0


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

        # Fallback REST poll loop — P4-E: each refresh is time-bounded so a hung
        # exchange API call never stalls the loop permanently.
        while self._running:
            await asyncio.sleep(_REST_POLL_INTERVAL)
            try:
                await asyncio.wait_for(
                    self._refresh_positions(reason="fallback-60s"),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                log.warning("[OptionsWSCache] Fallback REST refresh timed out (30 s) — will retry next cycle")
            except Exception as exc:
                log.warning(f"[OptionsWSCache] Fallback REST refresh failed: {exc}")

    # ------------------------------------------------------------------
    # WebSocket event handlers
    # ------------------------------------------------------------------

    @sealed
    async def _on_l1_orderbook(self, message: dict) -> None:
        """Update mark price from l1_orderbook push (~500 ms cadence).

        SEALED — v1.0.0 — May 1, 2026
        DO NOT MODIFY. This function is critical for max_loss safety checks.

        BUG HISTORY: On 2026-04-28, a 1000x PnL deflation bug was introduced via
        formula (mark-entry)*size*0.001. This caused max_loss checks to fail,
        preventing automatic position squareoff. The bug was FIXED on 2026-05-01
        by removing the incorrect recalculation. This sealed decorator prevents
        any future modification that could reintroduce the bug.

        RULE: Never recalculate unrealized_pnl from mark/entry prices here.
        The API already returns correct unrealized_pnl in USD. Updating mark_price
        for display is fine, but do NOT touch unrealized_pnl field.
        """
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
                    # NOTE: Do NOT recalculate unrealized_pnl here.
                    # The formula (mark - entry) * size * 0.001 deflates PnL by 1000x
                    # (bug introduced 2026-04-28 with incorrect multiplier assumption).
                    # API unrealized_pnl is already correct in USD; updating mark_price
                    # for display is sufficient. Max loss checks and other safety systems
                    # depend on accurate unrealized_pnl from the exchange API.
        except Exception as exc:
            log.debug(f"[OptionsWSCache] l1_orderbook handler error: {exc}")

    async def _on_fill(self, message: dict) -> None:
        """Fill event received — refresh positions (with cooldown)."""
        now = time.time()
        if now - self._last_fill_refresh < _FILL_REFRESH_COOLDOWN:
            return  # Too soon — a refresh is already in flight or just completed

        self._last_fill_refresh = now
        log.debug("[OptionsWSCache] Fill event received — refreshing positions (no close detection)")
        try:
            # Skip close detection on the immediate fill refresh — the exchange REST
            # may transiently return size=0 for positions being adjusted, causing false phantoms.
            # A delayed follow-up runs after _FILL_CLOSE_DETECT_DELAY seconds with detection enabled.
            await self._refresh_positions(reason="fill-event")
            asyncio.ensure_future(self._delayed_close_detect_refresh())
        except Exception as exc:
            log.warning(f"[OptionsWSCache] Fill-triggered refresh failed: {exc}")

    async def _delayed_close_detect_refresh(self) -> None:
        """Runs _FILL_CLOSE_DETECT_DELAY seconds after a fill to perform close detection once settled."""
        await asyncio.sleep(_FILL_CLOSE_DETECT_DELAY)
        try:
            await self._refresh_positions(reason="fill-followup")
        except Exception as exc:
            log.debug(f"[OptionsWSCache] Delayed close-detect refresh failed: {exc}")

    async def _reconcile_close_pnl(
        self,
        symbol: str,
        entry_price: float,
        prev_size: float,
        ex_realized: float,
        prev_cumulative: float,
        close_ts: float,
    ) -> None:
        """
        P4-B: 5 s after a close is detected, fetch actual fill prices from the
        exchange and replace the mark-price estimate with the exact fill-based PnL.

        Algorithm:
          - Fetch fills in a ±30 s window around close_ts.
          - Filter to closing-direction fills for this symbol (BUY for short, SELL for long).
          - Compute weighted-average close price from those fills.
          - Replace the stored cumulative_realized_pnl if the corrected value differs
            from what was recorded by more than $0.01.
        """
        await asyncio.sleep(5.0)
        try:
            # Use a ±60 s window to account for exchange API latency and delayed
            # close detection. The 5 s sleep before this call means fills up to
            # ~65 s before close_ts are included, which covers even slow fills.
            start_us = int((close_ts - 60) * 1_000_000)
            end_us = int((close_ts + 60) * 1_000_000)

            resp = await self._rest_client._request_with_retry(
                method="GET",
                path="/v2/fills",
                params={"start_time": start_us, "end_time": end_us, "page_size": 100},
            )
            fills = resp.get("result", [])
            if not isinstance(fills, list) or not fills:
                return

            is_short = prev_size < 0
            closing_side = "buy" if is_short else "sell"

            sym_fills = [
                f for f in fills
                if (
                    f.get("product", {}).get("symbol", "") == symbol
                    or f.get("product_symbol", "") == symbol
                ) and f.get("side", "").lower() == closing_side
            ]

            if not sym_fills:
                log.debug(f"[OptionsWSCache] Reconciliation: no {closing_side} fills for {symbol}")
                return

            total_size = sum(abs(float(f.get("size", 0) or 0)) for f in sym_fills)
            if total_size == 0:
                return
            total_value = sum(
                abs(float(f.get("size", 0) or 0)) *
                float(f.get("price", 0) or f.get("fill_price", 0) or 0)
                for f in sym_fills
            )
            avg_close_price = total_value / total_size
            if avg_close_price == 0:
                return

            abs_size = abs(prev_size)
            if is_short:
                final_pnl = (entry_price - avg_close_price) * abs_size * 0.001
            else:
                final_pnl = (avg_close_price - entry_price) * abs_size * 0.001

            reconciled = prev_cumulative + ex_realized + final_pnl

            from .closed_position_store import get_closed_position_store
            store = get_closed_position_store()
            current = store.get_cumulative_pnl(symbol)
            if abs(reconciled - current) > 0.01:
                log.info(
                    f"[OptionsWSCache] Fills-reconciled {symbol}: "
                    f"${current:+.4f} → ${reconciled:+.4f} "
                    f"(avg_fill=${avg_close_price:.4f} entry=${entry_price:.4f})"
                )
                store.update_reconciled_pnl(symbol, reconciled)
            else:
                log.debug(f"[OptionsWSCache] Reconciliation {symbol}: mark-price estimate already accurate (Δ<$0.01)")
        except Exception as exc:
            log.debug(f"[OptionsWSCache] Fills reconciliation for {symbol} failed: {exc}")

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

    @sealed
    async def _refresh_positions(self, reason: str = "") -> None:
        """Fetch all options positions via REST and merge with cached mark prices.

        SEALED — v1.0.0 — May 1, 2026
        DO NOT MODIFY. This function is critical for max_loss safety checks.

        BUG HISTORY: On 2026-04-28, a 1000x PnL deflation bug was introduced via
        the loop at lines 463-467 that recalculated:
            pos["unrealized_pnl"] = (mark - entry) * size * 0.001
        This deflated all PnL values by 1000x, causing max_loss checks to fail.
        The bug was FIXED on 2026-05-01 by removing the entire recalculation loop.
        This sealed decorator prevents any future modification that could
        reintroduce the bug.

        RULE: Never recalculate unrealized_pnl from mark/entry prices.
        The API already returns correct unrealized_pnl in USD. Updating mark_price
        for display is fine, but do NOT touch unrealized_pnl field.
        """
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
            # Skipped on "fill-event" refreshes: exchange may transiently show size=0 for
            # positions being adjusted. The "fill-followup" refresh (8s later) runs detection
            # once the exchange state has settled.
            if self._prev_positions and reason != "fill-event":
                try:
                    from .closed_position_store import get_closed_position_store
                    store = get_closed_position_store()
                    # P4-A: one refresh_id per detection pass — prevents fill-followup
                    # and periodic refresh from double-accumulating the same close.
                    refresh_id = str(round(time.time(), 1))
                    close_ts = time.time()
                    for sym, prev_pos in self._prev_positions.items():
                        prev_size = float(prev_pos.get("size", 0) or 0)
                        curr_size = exchange_map.get(sym, 0)
                        if prev_size != 0 and curr_size == 0:
                            # Total realized PnL at close =
                            #   realized_pnl  (exchange cumulative from all partial exits)
                            # + unrealized_pnl (PnL on the final lot being closed now)
                            # Both fields come from the last REST snapshot of this position,
                            # so they are in USD and already include the lot multiplier.
                            ex_realized = float(prev_pos.get("realized_pnl", 0) or 0)
                            ex_unrealized = float(prev_pos.get("unrealized_pnl", 0) or 0)
                            realized = ex_realized + ex_unrealized
                            if realized == 0:
                                # Fallback: manual calculation from mark/entry prices
                                mark = float(prev_pos.get("mark_price", 0) or 0)
                                entry = float(prev_pos.get("entry_price", 0) or 0)
                                if mark == 0:
                                    mark = entry
                                realized = (mark - entry) * prev_size * 0.001
                            store.record_close(prev_pos, realized, refresh_id=refresh_id)
                            # P4-B: schedule fills reconciliation 5 s later to replace the
                            # mark-price estimate with the actual exchange fill price.
                            prev_cumulative = store.get_cumulative_pnl(sym) - realized
                            asyncio.ensure_future(self._reconcile_close_pnl(
                                symbol=sym,
                                entry_price=float(prev_pos.get("entry_price", 0) or 0),
                                prev_size=prev_size,
                                ex_realized=ex_realized,
                                prev_cumulative=prev_cumulative,
                                close_ts=close_ts,
                            ))
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
                # Exchange's own cumulative realized PnL for this position (includes
                # all partial exits since the position was first opened).
                p["realized_pnl"] = float(p.get("realized_pnl", 0) or 0)
                new_positions[symbol] = p

            with self._lock:
                # Only update _prev_positions when close detection was allowed to run.
                # On "fill-event" refreshes, detection is skipped intentionally (exchange
                # may transiently show size=0 during adjustments). If we also overwrote
                # _prev_positions here, the delayed fill-followup would find _prev empty
                # and never detect the close. Keeping the pre-fill snapshot lets the
                # fill-followup (8 s later) correctly see the size→0 transition.
                if reason != "fill-event":
                    self._prev_positions = dict(new_positions)
                self._positions = new_positions
                # Merge any fresher mark prices from WS — but DO NOT recalculate unrealized_pnl.
                # The API already returns correct unrealized_pnl in USD. Recalculating it with
                # (mark - entry) * size * 0.001 deflates it 1000x, causing max_loss checks to fail
                # when they should trigger. The mark price update is for display only (bid/ask in UI);
                # PnL tracking must always use the API value.
                for sym, mark in self._mark_prices.items():
                    if sym in self._positions:
                        self._positions[sym]["mark_price"] = mark
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
