"""
closed_position_store.py — Server-side persistence for closed options positions.

Tracks positions that go from size>0 → size=0 (closed by algo, manual fill, or expiry).
Keeps them until 6 hours after their expiry date so the dashboard can serve them as
phantom rows (is_closed=True, size=0) with their accumulated realized PnL.

This solves two problems:
  1. Positions vanish from the UI when algos close them — phantom rows keep them visible.
  2. Browser localStorage is device-local and can be cleared — server store survives.

The store does NOT inject partial_realized_pnl into live re-entered positions.
That concern is handled client-side (OptionsPanel.js re-entry transfer).

Storage: webui/backend/data/closed_positions.json
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    from eventlet.patcher import original as _ev_orig
    _RealLock = _ev_orig('threading').Lock
except Exception:
    import threading as _stdlib_threading
    _RealLock = _stdlib_threading.Lock

log = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).parent.parent.parent / 'data' / 'closed_positions.json'
_SEEN_PATH = Path(__file__).parent.parent.parent / 'data' / 'seen_positions.json'

# Keep phantom entries for 6 hours after expiry
_POST_EXPIRY_RETAIN_SECS = 6 * 3600

_store_instance: Optional['ClosedPositionStore'] = None
_store_lock = _RealLock()


def _parse_expiry_ts(symbol: str) -> float:
    """Parse expiry UTC timestamp from product_symbol like 'C-BTC-78400-270426' (DDMMYY)."""
    try:
        parts = symbol.split('-')
        if len(parts) < 4:
            return time.time() + 86400
        s = parts[3]  # e.g. "270426"
        day, month, year = int(s[0:2]), int(s[2:4]), 2000 + int(s[4:6])
        return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    except Exception:
        return time.time() + 86400


class ClosedPositionStore:
    """
    Singleton JSON store for closed options positions.
    Thread-safe with unpatched OS lock (safe from eventlet greenlets).
    """

    def __init__(self) -> None:
        self._lock = _RealLock()
        self._data: Dict[str, dict] = {}
        # Last-known live state for each position — persisted across restarts so
        # _prev_positions in the WS cache can be pre-populated and close detection
        # works correctly even after a backend restart.
        self._seen: Dict[str, dict] = {}
        self._seen_dirty: bool = False
        self._load()
        self._load_seen()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if _STORE_PATH.exists():
                with open(_STORE_PATH, 'r') as f:
                    self._data = json.load(f)
                log.info(f"[ClosedPositionStore] Loaded {len(self._data)} entries from {_STORE_PATH}")
                self._purge_expired_unlocked()
        except Exception as exc:
            log.warning(f"[ClosedPositionStore] Load failed ({exc}) — starting empty")
            self._data = {}

    def _save_unlocked(self) -> None:
        try:
            _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_STORE_PATH, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as exc:
            log.error(f"[ClosedPositionStore] Save failed: {exc}")

    def _load_seen(self) -> None:
        try:
            if _SEEN_PATH.exists():
                with open(_SEEN_PATH, 'r') as f:
                    self._seen = json.load(f)
                log.info(f"[ClosedPositionStore] Loaded {len(self._seen)} seen entries from {_SEEN_PATH}")
        except Exception as exc:
            log.warning(f"[ClosedPositionStore] Seen load failed ({exc}) — starting empty")
            self._seen = {}

    def _save_seen_unlocked(self) -> None:
        if not self._seen_dirty:
            return
        try:
            _SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_SEEN_PATH, 'w') as f:
                json.dump(self._seen, f, indent=2, default=str)
            self._seen_dirty = False
        except Exception as exc:
            log.error(f"[ClosedPositionStore] Seen save failed: {exc}")

    def _purge_expired_unlocked(self) -> None:
        """Remove entries whose post-expiry retain window has passed."""
        cutoff = time.time() - _POST_EXPIRY_RETAIN_SECS
        expired = [sym for sym, e in self._data.items() if e.get('expiry_ts', 0) < cutoff]
        for sym in expired:
            del self._data[sym]
        if expired:
            log.info(f"[ClosedPositionStore] Purged {len(expired)} expired entries")

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record_close(self, position: dict, realized_pnl: float) -> None:
        """
        Record that position went to size=0.
        Accumulates cumulative_realized_pnl if the symbol was previously tracked.
        """
        symbol = position.get('product_symbol', '')
        if not symbol:
            return
        with self._lock:
            existing = self._data.get(symbol, {})
            prev_cumulative = existing.get('cumulative_realized_pnl', 0.0)
            new_cumulative = prev_cumulative + realized_pnl
            self._data[symbol] = {
                'symbol': symbol,
                'expiry_ts': _parse_expiry_ts(symbol),
                'cumulative_realized_pnl': new_cumulative,
                'last_realized_pnl': realized_pnl,
                'last_closed_at': datetime.utcnow().isoformat(),
                'last_entry_price': float(position.get('entry_price') or 0),
                'last_mark_price': float(position.get('mark_price') or 0),
                'last_size': float(position.get('size') or 0),
                'greeks': position.get('greeks', {}),
                'is_closed': True,
                'status': 'closed',
            }
            self._save_unlocked()
        log.info(
            f"[ClosedPositionStore] Closed {symbol}: "
            f"realized=${realized_pnl:+.4f}, cumulative=${new_cumulative:+.4f}"
        )

    def dismiss(self, symbol: str) -> bool:
        """Remove a symbol from the store (user dismissed the phantom row)."""
        with self._lock:
            if symbol in self._data:
                del self._data[symbol]
                self._save_unlocked()
                return True
        return False

    def record_seen_batch(self, positions: List[dict]) -> None:
        """
        Update last-known live state for each position after a REST refresh.
        Skips symbols already tracked as 'closed' so we never overwrite realized PnL.
        """
        with self._lock:
            for pos in positions:
                sym = pos.get('product_symbol', '')
                if not sym:
                    continue
                if self._data.get(sym, {}).get('status') == 'closed':
                    continue  # Already closed — don't overwrite
                self._seen[sym] = {
                    'product_symbol': sym,
                    'entry_price': float(pos.get('entry_price') or 0),
                    'mark_price': float(pos.get('mark_price') or 0),
                    'size': float(pos.get('size') or 0),
                    'unrealized_pnl': float(pos.get('unrealized_pnl') or 0),
                    'greeks': pos.get('greeks', {}),
                }
            self._seen_dirty = True

    def flush_seen(self) -> None:
        """Persist seen state to disk. Call once after record_seen_batch, not per-position."""
        with self._lock:
            self._save_seen_unlocked()

    def get_last_seen(self) -> Dict[str, dict]:
        """
        Return last-known live positions (keyed by product_symbol).
        Used by OptionsWSCache to pre-populate _prev_positions on restart so close
        detection works even when the backend was stopped between fills.
        """
        with self._lock:
            return dict(self._seen)

    def cleanup_expired(self) -> None:
        """Public method to trigger expired-entry purge."""
        with self._lock:
            self._purge_expired_unlocked()
            self._save_unlocked()

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_cumulative_pnl(self, symbol: str) -> float:
        with self._lock:
            return self._data.get(symbol, {}).get('cumulative_realized_pnl', 0.0)

    def has_history(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._data

    def get_phantom_positions(self, exclude_symbols: Set[str] = None) -> List[dict]:
        """
        Return closed-position phantom dicts (size=0, is_closed=True) for all
        tracked symbols that:
          - Have not yet expired (or are within the post-expiry retain window)
          - Are not in exclude_symbols (those are already live in the response)

        Each phantom carries realized_pnl and unrealized_pnl = cumulative_realized_pnl
        so the frontend PnL column and payoff graph both show the historical value.
        """
        now = time.time()
        cutoff = now - _POST_EXPIRY_RETAIN_SECS
        exclude = exclude_symbols or set()
        result = []
        with self._lock:
            for sym, entry in self._data.items():
                if sym in exclude:
                    continue
                if entry.get('expiry_ts', 0) < cutoff:
                    continue
                cumulative = entry.get('cumulative_realized_pnl', 0.0)
                result.append({
                    'product_symbol': sym,
                    'size': 0,
                    # original_size = last non-zero size before close (for "CLOSED" row display)
                    'original_size': entry.get('last_size', 0),
                    'entry_price': entry.get('last_entry_price', 0),
                    'mark_price': entry.get('last_mark_price', 0),
                    # unrealized_pnl carries the total realized PnL so the PnL column shows
                    # the right value.  partial_realized_pnl is kept at 0 to avoid double-
                    # counting in PortfolioSummaryStrip (livePnl = unrealized + partial).
                    # The payoff graph uses realized_pnl for is_closed rows (correct).
                    'unrealized_pnl': cumulative,
                    'realized_pnl': cumulative,
                    'partial_realized_pnl': 0,
                    'greeks': entry.get('greeks', {}),
                    'is_closed': True,
                    'status': 'closed',
                    'closed_at': entry.get('last_closed_at', ''),
                    'best_bid': 0,
                    'best_ask': 0,
                    'cashflow': 0,
                    'mid_price': 0,
                })
        return result

    def stats(self) -> dict:
        with self._lock:
            return {
                'tracked': len(self._data),
                'symbols': list(self._data.keys()),
            }


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

def get_closed_position_store() -> ClosedPositionStore:
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = ClosedPositionStore()
    return _store_instance
