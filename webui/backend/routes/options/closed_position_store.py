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
_DISMISSED_PATH = Path(__file__).parent.parent.parent / 'data' / 'dismissed_symbols.json'

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
        # Persisted set of dismissed symbols — survives backend restarts so
        # dismissed phantom rows never reappear (P4-C full fix).
        self._dismissed: Set[str] = set()
        self._load()
        self._load_seen()
        self._load_dismissed()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if _STORE_PATH.exists():
                with open(_STORE_PATH, 'r') as f:
                    self._data = json.load(f)
                before_purge = len(self._data)
                self._purge_expired_unlocked()
                after_purge = len(self._data)
                log.info(f"[ClosedPositionStore] ✅ Loaded {before_purge} entries, kept {after_purge} after purging expired (file: {_STORE_PATH})")
                if before_purge != after_purge:
                    log.info(f"[ClosedPositionStore] Purged {before_purge - after_purge} expired entries")
            else:
                log.warning(f"[ClosedPositionStore] Store file not found at {_STORE_PATH} — starting empty")
                self._data = {}
        except Exception as exc:
            log.error(f"[ClosedPositionStore] ❌ Load failed: {exc}", exc_info=True)
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
            before_load = 0
            if _SEEN_PATH.exists():
                with open(_SEEN_PATH, 'r') as f:
                    self._seen = json.load(f)
                before_load = len(self._seen)
            # Purge seen entries whose post-expiry retain window has passed
            # (same logic as _purge_expired_unlocked for closed entries).
            cutoff = time.time() - _POST_EXPIRY_RETAIN_SECS
            expired = [sym for sym, e in self._seen.items() if e.get('expiry_ts', 0) < cutoff]
            for sym in expired:
                del self._seen[sym]
            after_purge = len(self._seen)
            if expired:
                log.info(f"[ClosedPositionStore] Purged {len(expired)} expired seen entries")
            log.info(f"[ClosedPositionStore] ✅ Seen entries: loaded {before_load}, kept {after_purge} after purging (file: {_SEEN_PATH})")
        except Exception as exc:
            log.error(f"[ClosedPositionStore] ❌ Seen load failed: {exc}", exc_info=True)
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

    def _load_dismissed(self) -> None:
        """Load persisted dismissed symbols set from disk."""
        try:
            before_load = 0
            if _DISMISSED_PATH.exists():
                with open(_DISMISSED_PATH, 'r') as f:
                    raw = json.load(f)
                    self._dismissed = set(raw) if isinstance(raw, list) else set()
                before_load = len(self._dismissed)
            # Purge dismissed entries whose post-expiry retain window has passed
            cutoff = time.time() - _POST_EXPIRY_RETAIN_SECS
            stale = {s for s in self._dismissed if _parse_expiry_ts(s) < cutoff}
            if stale:
                self._dismissed -= stale
                self._save_dismissed_unlocked()
                log.info(f"[ClosedPositionStore] Purged {len(stale)} expired dismissed symbols")
            log.info(f"[ClosedPositionStore] ✅ Dismissed symbols: loaded {before_load}, kept {len(self._dismissed)} after purging (file: {_DISMISSED_PATH})")
        except Exception as exc:
            log.error(f"[ClosedPositionStore] ❌ Dismissed load failed: {exc}", exc_info=True)
            self._dismissed = set()

    def _save_dismissed_unlocked(self) -> None:
        """Persist dismissed symbols set to disk."""
        try:
            _DISMISSED_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_DISMISSED_PATH, 'w') as f:
                json.dump(sorted(self._dismissed), f, indent=2)
        except Exception as exc:
            log.error(f"[ClosedPositionStore] Dismissed save failed: {exc}")

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

    def record_close(self, position: dict, realized_pnl: float, refresh_id: str = None) -> None:
        """
        Record that position went to size=0.
        Accumulates cumulative_realized_pnl if the symbol was previously tracked.

        refresh_id: opaque token (e.g. str(round(time.time(), 1))) passed by the
        caller.  If the same refresh_id was already recorded for this symbol we
        skip the accumulation — prevents double-counting when fill-followup and
        the periodic 60 s refresh both detect the same close.

        120-second idempotency guard: if this symbol was closed within the last
        120 s, a second detector (dashboard immediate vs WS cache fill-followup)
        is firing for the same event — skip to prevent double-accumulation.
        Re-entry closes happen hours apart so they are never affected.
        """
        symbol = position.get('product_symbol', '')
        if not symbol:
            return
        with self._lock:
            existing = self._data.get(symbol, {})
            # P4-A idempotence: same refresh cycle already recorded this close
            if refresh_id and existing.get('last_detect_refresh_id') == refresh_id:
                log.debug(f"[ClosedPositionStore] Skipping duplicate close for {symbol} (refresh_id={refresh_id})")
                return
            # 120 s guard: same close event detected by a second source
            last_closed_ts = existing.get('last_closed_ts', 0)
            if last_closed_ts:
                elapsed = time.time() - last_closed_ts
                if elapsed < 120:
                    log.debug(
                        f"[ClosedPositionStore] Skipping duplicate close for {symbol} "
                        f"(already recorded {elapsed:.0f}s ago)"
                    )
                    return
            prev_cumulative = existing.get('cumulative_realized_pnl', 0.0)
            new_cumulative = prev_cumulative + realized_pnl
            self._data[symbol] = {
                'symbol': symbol,
                'expiry_ts': _parse_expiry_ts(symbol),
                'cumulative_realized_pnl': new_cumulative,
                'last_realized_pnl': realized_pnl,
                'last_closed_at': datetime.utcnow().isoformat(),
                'last_closed_ts': time.time(),
                'last_entry_price': float(position.get('entry_price') or 0),
                'last_mark_price': float(position.get('mark_price') or 0),
                'last_size': float(position.get('size') or 0),
                'greeks': position.get('greeks', {}),
                'is_closed': True,
                'status': 'closed',
                'last_detect_refresh_id': refresh_id,
                'fills_reconciled': False,
            }
            self._save_unlocked()
        log.info(
            f"[ClosedPositionStore] Closed {symbol}: "
            f"realized=${realized_pnl:+.4f}, cumulative=${new_cumulative:+.4f}"
        )

    def update_reconciled_pnl(self, symbol: str, reconciled_pnl: float) -> None:
        """
        Replace cumulative_realized_pnl with a fills-reconciled value.
        Called by options_ws_cache after fetching actual fill prices from the exchange.
        Only updates if the symbol is still in the store (not yet dismissed/expired).
        """
        with self._lock:
            if symbol not in self._data:
                return
            old = self._data[symbol].get('cumulative_realized_pnl', 0.0)
            self._data[symbol]['cumulative_realized_pnl'] = reconciled_pnl
            self._data[symbol]['fills_reconciled'] = True
            self._save_unlocked()
        log.info(f"[ClosedPositionStore] Fills-reconciled {symbol}: ${old:+.4f} → ${reconciled_pnl:+.4f}")

    def dismiss(self, symbol: str) -> bool:
        """
        Remove a symbol from the store (user dismissed the phantom row).
        Also removes from _seen so a backend restart cannot re-detect the same
        close and resurrect the dismissed row (P4-C fix).

        Persists the symbol in _dismissed so it never reappears even after a
        backend restart (full P4-C implementation).
        """
        with self._lock:
            removed = False
            if symbol in self._data:
                del self._data[symbol]
                self._save_unlocked()
                removed = True
            # Remove from _seen so startup close-detection doesn't re-add it
            if symbol in self._seen:
                del self._seen[symbol]
                self._seen_dirty = True
                self._save_seen_unlocked()
            # Persist to dismissed set so it never reappears after restart
            if symbol not in self._dismissed:
                self._dismissed.add(symbol)
                self._save_dismissed_unlocked()
            return removed

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
                    'expiry_ts': _parse_expiry_ts(sym),
                    'entry_price': float(pos.get('entry_price') or 0),
                    'mark_price': float(pos.get('mark_price') or 0),
                    'size': float(pos.get('size') or 0),
                    'unrealized_pnl': float(pos.get('unrealized_pnl') or 0),
                    'realized_pnl': float(pos.get('realized_pnl') or 0),
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

        Symbols already tracked in _data (is_closed=True) are excluded — they have
        already been through record_close(). Including them would cause the startup
        refresh to detect them as closed again and double-accumulate cumulative PnL.
        """
        with self._lock:
            return {sym: data for sym, data in self._seen.items() if sym not in self._data}

    def cleanup_expired(self) -> None:
        """Public method to trigger expired-entry purge."""
        with self._lock:
            self._purge_expired_unlocked()
            self._save_unlocked()
            # Also purge expired dismissed symbols so the set doesn't grow unbounded
            cutoff = time.time() - _POST_EXPIRY_RETAIN_SECS
            stale = {s for s in self._dismissed if _parse_expiry_ts(s) < cutoff}
            if stale:
                self._dismissed -= stale
                self._save_dismissed_unlocked()
                log.info(f"[ClosedPositionStore] cleanup_expired: purged {len(stale)} expired dismissed symbols")

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_cumulative_pnl(self, symbol: str) -> float:
        with self._lock:
            return self._data.get(symbol, {}).get('cumulative_realized_pnl', 0.0)

    def get_all_cumulative_pnl(self) -> Dict[str, float]:
        """Return {symbol: cumulative_realized_pnl} for all tracked symbols under one lock."""
        with self._lock:
            return {sym: entry.get('cumulative_realized_pnl', 0.0) for sym, entry in self._data.items()}

    def has_history(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._data

    def get_dismissed_symbols(self) -> List[str]:
        """
        Return the list of dismissed symbols (persisted across restarts).
        Used by the dashboard endpoint to pre-seed the frontend dismissed set.
        """
        with self._lock:
            return sorted(self._dismissed)

    def get_phantom_positions(self, exclude_symbols: Set[str] = None) -> List[dict]:
        """
        Return closed-position phantom dicts (size=0, is_closed=True) for all
        tracked symbols that:
          - Have not yet expired (or are within the post-expiry retain window)
          - Are not in exclude_symbols (those are already live in the response)
          - Have not been dismissed by the user (P4-C full fix)

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
                if sym in self._dismissed:
                    continue  # P4-C: user dismissed this symbol — never show again
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
                    # Phase 2: all PnL sums use unrealized + realized.
                    # For closed rows: unrealized = 0, realized = full cumulative.
                    # Setting both to cumulative would double-count in every total.
                    'unrealized_pnl': 0,
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
