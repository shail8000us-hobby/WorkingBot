"""
MMMX Margin Guardian Adapter

Read-only adapter over the MMM MarginGuardian.

THIS IS THE ONLY mmmx file allowed to import from routes.mmm.* — all other
mmmx_*.py files must stay isolation-clean (zero routes.mmm.* imports).

Exposes:
  get_margin_guardian() → MMMXMarginGuardianAdapter singleton
  current_utilization() → float (0–100 pct, async)
  estimated_margin_for_order(symbol, side, size, price) → float (USD)

Only read paths are exposed. No MMM write functions are ever called.

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 2.
"""

import logging
import os
import sys
import threading
from typing import Optional

# Ensure bot package root is on sys.path (same guard as mmm_executor.py)
_BOT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)

from .mmmx_constants import LOT_SIZE_BTC

log = logging.getLogger('mmmx_margin_guardian')


class MMMXMarginGuardianAdapter:
    """
    Read-only adapter over the MMM margin infrastructure.

    Keeps a cached last-known utilization so synchronous callers (or callers
    that catch an async error) get a reasonable fallback value.
    """

    def __init__(self) -> None:
        self._last_util: float = 0.0
        self._lock = threading.Lock()

    def _create_rest_client(self):
        """Create a fresh AsyncDeltaClient bound to the current event loop."""
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        return AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=bool(creds.get('testnet', False)),
        )

    async def current_utilization(self) -> float:
        """
        Fetch current margin utilization from the exchange (0–100 pct).

        Delegates to MMM's `fetch_margin_utilization` (read-only).
        Falls back to the last-known cached value on error.

        Returns:
            float: margin utilization percentage (0–100+).
        """
        try:
            # Allowed cross-boundary import — this adapter is the designated bridge
            from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization

            rest = self._create_rest_client()
            result = await fetch_margin_utilization(rest)

            if result.get('success'):
                util = float(result.get('utilization_pct', 0.0))
                with self._lock:
                    self._last_util = util
                return util

            log.warning(
                f"[MMMX][MarginGuardian] fetch_margin_utilization returned "
                f"success=False: {result.get('error')}"
            )
        except Exception as exc:
            log.warning(f"[MMMX][MarginGuardian] current_utilization failed: {exc}")

        # Fall back to cached last value
        with self._lock:
            return self._last_util

    def estimated_margin_for_order(
        self,
        symbol: str,
        side: str,
        size: int,
        price: float,
    ) -> float:
        """
        Rough first-order USD margin estimate for a prospective order.

        For BTC options:
          margin ≈ premium_per_btc × lots × LOT_SIZE_BTC

        This is an approximation only — actual margin requirements depend on
        account mode (portfolio margin, cross-margin, etc.).

        Args:
            symbol: Option symbol (e.g. 'C-BTC-100000-280326')
            side:   'buy' | 'sell'
            size:   Number of lots
            price:  Estimated premium (USD per BTC)

        Returns:
            Estimated USD margin required.
        """
        if price <= 0 or size <= 0:
            return 0.0
        return round(price * size * LOT_SIZE_BTC, 4)


# ── Singleton ──────────────────────────────────────────────────────────────────
_instance: Optional[MMMXMarginGuardianAdapter] = None
_init_lock = threading.Lock()


def get_margin_guardian() -> MMMXMarginGuardianAdapter:
    """Return the process-wide adapter singleton."""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = MMMXMarginGuardianAdapter()
    return _instance
