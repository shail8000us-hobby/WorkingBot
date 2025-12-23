# bot/strategy/sed/alerts.py
# GridBotAlerts — notification overlay for gbot v1.7.3
from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter

# Reuse the stable core (no edits to gbot.py)
from bot.strategy.gbot import (
    GridBot,
    _within_band,
    _next_lower_after_buy,
    _tp_for_entry,
)

log = logging.getLogger("runner")

# --- Import Telegram notifier safely ---
try:
    from bot.utils.notifier import TelegramNotifier  # optional helper
except ImportError:
    TelegramNotifier = None
except Exception as e:
    log.warning("notifier import failed (non-ImportError): %s", e)
    TelegramNotifier = None


def _fmt_px(x: Any) -> str:
    """Format price for display in notifications."""
    if x is None:
        return "N/A"
    try:
        return f"{float(x):.1f}"
    except (ValueError, TypeError):
        return "N/A"


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    try:
        return str(v)
    except Exception:
        return default


class GridBotAlerts(GridBot):
    """
    Thin subclass that ONLY adds notifications around successful events.
    Trading logic remains in the parent GridBot (v1.7.3).
    """

    # ---------------- Lifecycle ----------------
    def __init__(self, *args, **kwargs):
        """
        Two robustness tweaks BEFORE the core bot bootstraps:
        1) Ensure markets are loaded.
        2) Normalize/translate the symbol (pretty form <-> product ID) so CCXT accepts it.
        """
        # ---- Load markets early
        ex = None
        try:
            dc = args[0] if args else kwargs.get("dc")
            if dc is not None:
                for name in ("ex", "exchange", "ccxt", "client"):
                    ex = getattr(dc, name, None)
                    if ex is not None:
                        break
            if ex:
                try:
                    ex.load_markets()
                except Exception as e:
                    log.warning("delta load_markets warning: %s", e)
        except Exception as e:
            log.warning("pre-init market load guard failed: %s", e)

        # ---- Normalize symbol (handle BTC/USD:USD vs BTCUSD)
        def _resolve_symbol(sym: str) -> str:
            if not ex or not sym:
                return sym
            try:
                markets = getattr(ex, "markets", {}) or {}
                by_id = getattr(ex, "markets_by_id", {}) or {}

                if sym in markets:
                    return sym  # already a known display symbol

                # Try product-id form (compact)
                compact = sym.replace("/", "").replace(":", "")
                if compact in by_id:
                    return by_id[compact]["symbol"]

                # Search by id among markets values
                for m in markets.values():
                    if m.get("id") == compact:
                        return m["symbol"]

                # Try the other direction: if given is id and display exists
                if sym in by_id:
                    return by_id[sym]["symbol"]
            except Exception as e:
                log.debug("symbol resolve failed for %s: %s", sym, e)
            return sym  # fallback

        try:
            # args layout expected by run_grid_strategy: (dc, symbol, lower, upper, step, ref, lot, ...)
            if args and len(args) >= 2:
                new_args = list(args)
                new_args[1] = _resolve_symbol(_safe_str(args[1]))
                args = tuple(new_args)
            elif "symbol" in kwargs:
                kwargs["symbol"] = _resolve_symbol(
                    _safe_str(kwargs.get("symbol")))
        except Exception as e:
            log.warning("symbol normalization guard failed: %s", e)

        # now let the core initialize and bootstrap
        super().__init__(*args, **kwargs)

        # notifier is optional — never crash if it fails
        self._notifier = None
        if TelegramNotifier:
            try:
                self._notifier = TelegramNotifier()
                if getattr(self._notifier, "enabled", False):
                    log.info("notifier: Telegram enabled")
                else:
                    log.info("notifier: Telegram present but disabled")
            except Exception as e:
                log.warning("notifier: initialization failed: %s", e)

        # small rate-limit to avoid spam (per-process)
        self._last_notification_ts = 0.0
        self._notification_cooldown_sec = 1.0  # 1/sec

        # track seen pending order_ids to avoid duplicate "BUY placed" alerts
        self._seen_pending_ids: Set[str] = set()

    # ---------------- Notifier helper ----------------
    def _notify(self, text: str):
        n = self._notifier
        if not n or not getattr(n, "enabled", False):
            return
        now = time.time()
        if (now - self._last_notification_ts) < self._notification_cooldown_sec:
            return
        try:
            n.send(text)
            self._last_notification_ts = now
            log.debug("notifier: sent -> %s", text)
        except Exception as e:
            log.warning("notifier: send failed: %s", e)

    # ---------------- Hooks around core events ----------------
    def _ensure_pending_at_price(self, px: float):
        before_id = _safe_str(self.pending_buy.get(
            "order_id")) if self.pending_buy else ""
        super()._ensure_pending_at_price(px)
        after_id = _safe_str(self.pending_buy.get(
            "order_id")) if self.pending_buy else ""
        if after_id and after_id != before_id and after_id not in self._seen_pending_ids:
            self._seen_pending_ids.add(after_id)
            try:
                px_txt = _fmt_px(self.pending_buy.get(
                    "px") if self.pending_buy else px)
            except Exception:
                px_txt = _fmt_px(px)
            self._notify(f"BUY placed {self.lot} @ {px_txt} (id={after_id})")

    def _place_tp_sell(self, px: float) -> Tuple[Optional[str], Optional[str]]:
        tp_id, tp_cid = super()._place_tp_sell(px)
        if tp_id:
            try:
                self._notify(
                    f"TP SELL placed {self.lot} @ {_fmt_px(px)} (id={tp_id})")
            except Exception as e:
                log.warning("notifier: TP place format error: %s", e)
        return tp_id, tp_cid

    def _confirm_pending_buy(self):
        had_pending = bool(self.pending_buy)
        super()._confirm_pending_buy()
        if had_pending and not self.pending_buy and self.open_tranches:
            try:
                tr = self.open_tranches[-1]
                buy_px = _safe_float(tr.get("buy_px"))
                tp_px = _safe_float(tr.get("tp_px"))
                self._notify(
                    f"BUY filled @ {_fmt_px(buy_px)} → TP @ {_fmt_px(tp_px)}")
            except Exception as e:
                log.warning(
                    "notifier: error formatting BUY-confirmed notice: %s", e)

    def _confirm_tp_fills(self):
        before_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in self.open_tranches:
            try:
                if isinstance(t, dict):
                    tp_id = _safe_str(t.get("tp_id"), "")
                    if tp_id:
                        before_map[tp_id].append(dict(t))
            except Exception as e:
                log.debug("snapshot before: failed for a tranche: %s", e)

        before_counts = {k: len(v) for k, v in before_map.items()}

        super()._confirm_tp_fills()

        after_counts: Dict[str, int] = Counter()
        for t in self.open_tranches:
            try:
                if isinstance(t, dict):
                    tp_id = _safe_str(t.get("tp_id"), "")
                    if tp_id:
                        after_counts[tp_id] += 1
            except Exception as e:
                log.debug("snapshot after: failed for a tranche: %s", e)

        for tp_id, before_n in before_counts.items():
            after_n = after_counts.get(tp_id, 0)
            diff = before_n - after_n
            if diff > 0:
                for tr in before_map.get(tp_id, [])[:diff]:
                    try:
                        buy_px = _safe_float(tr.get("buy_px"))
                        tp_px = _safe_float(tr.get("tp_px"))
                        self._notify(
                            f"TP filled @ {_fmt_px(tp_px)} (entry {_fmt_px(buy_px)}) — re-armed BUY at entry"
                        )
                    except Exception as e:
                        log.warning(
                            "notifier: TP fill format error for %s: %s", tp_id, e)

    # ---------------- Run wrapper ----------------
    def run(self):
        self._notify("GridBot Alerts: started")
        try:
            super().run()
        except KeyboardInterrupt:
            self._notify("GridBot Alerts: stopped by user")
            raise
        except Exception as e:
            self._notify(f"GridBot Alerts: stopped with error: {str(e)[:120]}")
            raise


# ---------------- Entrypoint mirroring the core ----------------
def run_grid_strategy(dc, symbol, lower, upper, step, ref, lot, max_open=5, hb_sec=5):
    log.info("grid: launching GridBotAlerts (notifications enabled)")
    bot = GridBotAlerts(dc, symbol, lower, upper, step,
                        ref, lot, max_open, hb_sec)
    bot.run()
