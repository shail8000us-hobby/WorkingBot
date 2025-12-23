# bot/strategy/gbot.py  (GridBot v1.7.3 — Delta Exchange Production Ready)

from __future__ import annotations
import os
import time
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

log = logging.getLogger("runner")

# --- Colors (safe fallback if missing utils/colors.py) ---
try:
    from bot.utils.colors import green, red, cyan, orange
except Exception:
    def _wrap(code: str):
        def _c(s: str) -> str:
            return f"\033[{code}m{s}\033[0m"
        return _c
    green, red, cyan, orange = _wrap("92"), _wrap(
        "91"), _wrap("96"), _wrap("38;5;208")

# --- Configurable constants ---
TICK_SIZE = float(os.getenv("GRIDBOT_TICK_SIZE", "0.5")
                  )              # BTC tick size tolerance
# 98% fill = complete
FILL_THRESHOLD = float(os.getenv("GRIDBOT_FILL_THRESHOLD", "0.98"))
MAX_RETRIES = int(os.getenv("GRIDBOT_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("GRIDBOT_RETRY_DELAY", "2.0")
                    )          # Backoff base (Delta-friendly)
# Cooling period after errors
COOLDOWN_SECONDS = int(os.getenv("GRIDBOT_COOLDOWN_SECONDS", "30"))

# Tagging: prefix recognized across sessions; session_tag is unique per run
GBOT_PREFIX = os.getenv("GRIDBOT_TAG_PREFIX", "GBOT_")

# --- Helpers ---


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fmt_px(x: Union[float, int, None]) -> str:
    if x is None:
        return "N/A"
    try:
        return f"{float(x):.1f}"
    except (ValueError, TypeError):
        return "N/A"


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _within_band(px: float, lo: float, hi: float) -> bool:
    return lo <= px <= hi


def _grid_next_after_start(ref: float, step: float) -> float:
    return ref - step


def _tp_for_entry(entry_px: float, step: float) -> float:
    return entry_px + step


def _next_lower_after_buy(entry_px: float, step: float) -> float:
    return entry_px - step


def _session_tag() -> str:
    return f"{GBOT_PREFIX}{int(time.time())}"


def _has_ccxt(dc: Any) -> Any:
    for name in ("ex", "exchange", "ccxt", "client"):
        ex = getattr(dc, name, None)
        if ex is not None:
            return ex
    return None


def _is_delta(ex: Any) -> bool:
    try:
        return getattr(ex, "id", "") == "delta"
    except Exception:
        return False


def _is_rate_limit_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(k in s for k in ("rate limit", "too many requests", "429", "throttle", "limit exceeded"))


def _retry_operation(func, *args, max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY, **kwargs):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait = delay * \
                    (3 ** attempt) if _is_rate_limit_error(e) else delay * \
                    (2 ** attempt)
                log.warning(
                    f"op retry {attempt+1}/{max_retries} in {wait}s: {e}")
                time.sleep(wait)
            else:
                log.error(f"op failed after {max_retries} attempts: {e}")
    raise last_exception if last_exception else RuntimeError("retry failed")


class GridBot:
    """
    GridBot v1.7.3 - Delta Exchange Production Ready

    - Delta Exchange integration (client_order_id, reduce_only, integer lot)
    - Robust two-path fill confirmation (by trades or by order status)
    - Retry & cooldown with backoff; resilient heartbeat
    - Bootstrap across sessions (GBOT_* prefix)
    - Clean client-ID tracking and tranche lifecycle
    - Safer comparisons with TICK_SIZE tolerance
    - Fixed: Delta Exchange fetchOrder() compatibility issue
    """

    def __init__(self, dc, symbol, lower, upper, step, ref, lot, max_open=5, hb_sec=5):
        self.dc, self.ex = dc, _has_ccxt(dc)
        if not self.ex:
            raise RuntimeError("GridBot: CCXT handle missing")

        # Params with validation
        self.symbol = str(symbol)
        self.lower = _safe_float(lower)
        self.upper = _safe_float(upper)
        self.step = _safe_float(step)
        self.ref = _safe_float(ref)
        # Delta requires integer contract size
        self.lot = int(_safe_float(lot))
        self.max_open = _safe_int(max_open, 5)
        # Minimum 5s heartbeat for Delta
        self.hb_sec = max(5, _safe_int(hb_sec, 5))

        if self.step <= 0:
            raise ValueError("Step must be positive")
        if self.lower >= self.upper:
            raise ValueError("Lower < Upper required")
        if not _within_band(self.ref, self.lower, self.upper):
            raise ValueError("Ref must be within bounds")
        if self.lot <= 0:
            raise ValueError("Lot must be positive integer")
        if self.max_open > 10:
            raise ValueError(
                "Max open positions should not exceed 10 for safety")

        # Tagging & compatibility
        self.session_tag = _session_tag()
        self.is_delta_exchange = _is_delta(self.ex)
        if not self.is_delta_exchange:
            log.warning(
                "Exchange is not Delta - some features may not work correctly")

        # State
        self.open_tranches: List[Dict[str, Any]] = []
        self.pending_buy: Optional[Dict[str, Any]] = None
        self.last_trades_since: Optional[int] = None
        self.cooldown_until = 0
        self._active_client_ids: set[str] = set()
        self._last_ticker: Dict[str, float] = {}

        log.info(
            f"GridBot initializing for {symbol} with lot size {self.lot} (integer)")
        self._bootstrap_state()

    # ---------------- Bootstrap ----------------
    def _bootstrap_state(self):
        log.info("grid: bootstrap…")
        try:
            oo = _retry_operation(self.ex.fetch_open_orders, self.symbol)
        except Exception as e:
            log.error(f"bootstrap: fetch_open_orders failed: {e}")
            oo = []

        buys, sells = [], []
        for o in oo:
            try:
                cid = self._get_client_order_id(o)
                # accept any GBOT_* from previous sessions
                if cid and cid.startswith(GBOT_PREFIX):
                    self._active_client_ids.add(cid)
                    side = str(o.get("side", "")).lower()
                    if side == "buy":
                        buys.append(o)
                    elif side == "sell":
                        sells.append(o)
            except Exception as e:
                log.warning(
                    f"bootstrap: error processing order {o.get('id', '?')}: {e}")

        restored = 0
        for so in sells:
            try:
                if not self._is_reduce_only(so):
                    continue
                px = _safe_float(so.get("price"))
                if px <= 0:
                    continue
                entry = px - self.step

                # grid alignment (tolerant)
                steps = round((self.ref - entry) / self.step)
                expected_entry = self.ref - steps * self.step
                if abs(entry - expected_entry) > TICK_SIZE:
                    continue
                if not _within_band(entry, self.lower, self.ref):
                    continue

                cid = self._get_client_order_id(so)
                self.open_tranches.append({
                    "buy_px": entry,
                    "qty": self.lot,
                    "tp_px": px,
                    "tp_id": so.get("id"),
                    "tp_client_id": cid or ""
                })
                restored += 1
            except Exception as e:
                log.warning(
                    f"bootstrap: error processing TP {so.get('id', '?')}: {e}")

        if buys:
            try:
                b = sorted(buys, key=lambda x: _safe_float(x.get("price")))[0]
                self.pending_buy = {
                    "px": _safe_float(b.get("price")),
                    "order_id": b.get("id"),
                    "client_id": self._get_client_order_id(b)
                }
            except Exception as e:
                log.warning(f"bootstrap: error restoring pending buy: {e}")

        self.last_trades_since = _now_ms() - 60_000
        log.info(orange(
            f"grid: bootstrap complete  restored={restored}  pending={bool(self.pending_buy)}"))

    # ---------------- Main loop ----------------
    def run(self):
        log.info(
            orange(f"grid: loop start for {self.symbol} (lot size: {self.lot})"))
        last_last = None
        consecutive_errors = 0
        max_consecutive_errors = 10

        while True:
            try:
                self._tick()

                # Heartbeat with position summary
                try:
                    t = self._fetch_ticker_safe()
                    if t:
                        last, bid, ask = t.get("last", 0), t.get(
                            "bid", 0), t.get("ask", 0)
                        d = None if last_last is None else last - last_last
                        last_last = last
                        if d is None:
                            arrow = " "
                        elif abs(d) < 0.01:
                            arrow = " → 0"
                        elif d > 0:
                            arrow = green(f" ▲ +{_fmt_px(d)}")
                        else:
                            arrow = red(f" ▼ {_fmt_px(d)}")
                        spread = max(
                            0, ask - bid) if ask > 0 and bid > 0 else 0

                        open_count = len(self.open_tranches)
                        pending_info = f" | pending: {_fmt_px(self.pending_buy['px'])}" if self.pending_buy else ""
                        exposure = open_count * self.lot

                        log.info(
                            f"[HB] last={_fmt_px(last)} {arrow}  bid={green(_fmt_px(bid))} ask={cyan(_fmt_px(ask))} | "
                            f"open: {open_count}/{self.max_open} (exposure: {exposure} lots){pending_info}"
                        )
                        self._last_ticker = t
                except Exception as e:
                    log.warning(f"heartbeat: {e}")

                consecutive_errors = 0
                time.sleep(self.hb_sec)

            except KeyboardInterrupt:
                log.info("grid: stopped by user")
                self._cleanup_on_exit()
                break
            except Exception as e:
                consecutive_errors += 1
                log.error(
                    f"grid: loop error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                log.debug(traceback.format_exc())
                if consecutive_errors >= max_consecutive_errors:
                    log.critical("grid: too many consecutive errors, exiting")
                    break
                time.sleep(min(self.hb_sec * consecutive_errors, 60))

    def _fetch_ticker_safe(self) -> Optional[Dict[str, float]]:
        try:
            ticker = self.ex.fetch_ticker(self.symbol) or {}
            return {k: _safe_float(ticker.get(k)) for k in ("last", "bid", "ask", "high", "low", "open", "close")}
        except Exception as e:
            log.warning(f"ticker failed: {e}")
            return None

    # ---------------- One tick ----------------
    def _tick(self):
        try:
            self._confirm_pending_buy()
        except Exception as e:
            log.error(f"confirm pending buy: {e}")
        try:
            self._confirm_tp_fills()
        except Exception as e:
            log.error(f"confirm TP fills: {e}")
        try:
            self._ensure_pending_buy()
        except Exception as e:
            log.error(f"ensure pending buy: {e}")

    # ---------------- Confirm pending BUY ----------------
    def _confirm_pending_buy(self):
        if not self.pending_buy:
            return
        pend = self.pending_buy
        confirmed, avg_px, fills = False, _safe_float(pend["px"]), []

        # A) confirm by trades (order→fills)
        try:
            ok_tr, avg_px_tr, fill_ids = self._try_confirm_by_trades(pend)
            if ok_tr:
                confirmed, avg_px, fills = True, avg_px_tr, fill_ids
        except Exception as e:
            log.warning(f"trade confirm failed: {e}")

        # B) confirm by order status (only for non-Delta exchanges)
        if not confirmed and not self.is_delta_exchange:
            try:
                ok_o, avg_px_o = self._try_confirm_by_order(pend)
                if ok_o:
                    confirmed, avg_px = True, avg_px_o
            except Exception as e:
                log.warning(f"order confirm failed: {e}")

        if not confirmed:
            return

        # Place TP SELL (do not clear pending until TP succeeds)
        tp_px = _tp_for_entry(avg_px, self.step)
        try:
            tp_id, tp_cid = self._place_tp_sell(tp_px)
            if tp_id:
                self.open_tranches.append({
                    "buy_px": avg_px,
                    "qty": self.lot,
                    "buy_id": pend.get("order_id"),
                    "buy_client_id": pend.get("client_id", ""),
                    "tp_px": tp_px,
                    "tp_id": tp_id,
                    "tp_client_id": tp_cid or ""
                })
                log.info(green(
                    f"grid: BUY confirmed @{_fmt_px(avg_px)} (ord={pend.get('order_id')}, fills={fills or 'OK'}) → TP @{_fmt_px(tp_px)}"))
                # cleanup & next rung
                cid = pend.get("client_id", "")
                if cid:
                    self._active_client_ids.discard(cid)
                self.pending_buy = None
                if len(self.open_tranches) < self.max_open:
                    nxt = _next_lower_after_buy(avg_px, self.step)
                    if nxt >= self.lower:
                        self._ensure_pending_at_price(nxt)
            else:
                log.error("TP placement failed; keeping pending buy for retry")
        except Exception as e:
            log.error(f"error after buy confirm: {e}")

    # ---------------- Confirm TP fills ----------------
    def _confirm_tp_fills(self):
        if not self.open_tranches:
            return
        try:
            trades = _retry_operation(
                self.ex.fetch_my_trades, self.symbol, self.last_trades_since, max_retries=2)
            if trades:
                latest = max((_safe_int(tr.get("timestamp"))
                             for tr in trades), default=0)
                self.last_trades_since = max(
                    self.last_trades_since or 0, latest + 1)
            else:
                self.last_trades_since = _now_ms()
        except Exception as e:
            log.warning(f"fetch trades failed: {e}")
            return

        tp_by_id = {
            t["tp_id"]: t for t in self.open_tranches if t.get("tp_id")}
        filled_tp_ids: List[str] = []
        for tr in trades or []:
            try:
                if str(tr.get("side", "")).lower() != "sell":
                    continue
                oid = self._get_trade_order_id(tr)
                if oid and oid in tp_by_id:
                    filled_tp_ids.append(oid)
            except Exception as e:
                log.warning(f"trade process err {tr.get('id', '?')}: {e}")

        for tp_id in filled_tp_ids:
            try:
                tranche = tp_by_id[tp_id]
                entry_px = _safe_float(tranche["buy_px"])
                tp_client_id = tranche.get("tp_client_id", "")
                if tp_client_id:
                    self._active_client_ids.discard(tp_client_id)
                # remove & log
                self.open_tranches = [
                    t for t in self.open_tranches if t.get("tp_id") != tp_id]
                log.info(green(
                    f"grid: SELL TP filled @{_fmt_px(tranche['tp_px'])} (entry {_fmt_px(entry_px)}) - PROFIT TAKEN"))
                # reset pending and rearm same rung
                self._cancel_pending_if_any()
                if _within_band(entry_px, self.lower, self.upper):
                    self._ensure_pending_at_price(entry_px)
            except Exception as e:
                log.error(f"process filled TP {tp_id}: {e}")

    # ---------------- Ensure pending BUY ----------------
    def _ensure_pending_buy(self):
        if time.time() < self.cooldown_until or self.pending_buy:
            return
        if len(self.open_tranches) >= self.max_open:
            return

        last = self._last_ticker.get("last")
        if last is None:
            t = self._fetch_ticker_safe()
            last = t.get("last") if t else None
        if last and not _within_band(last, self.lower, self.upper):
            return

        if not self.open_tranches:
            px = _grid_next_after_start(self.ref, self.step)
        else:
            highest = max(_safe_float(t["buy_px"]) for t in self.open_tranches)
            px = max(self.lower, _next_lower_after_buy(highest, self.step))

        if px > self.ref or px < self.lower:
            return
        self._ensure_pending_at_price(px)

    def _ensure_pending_at_price(self, px: float):
        if px > self.ref:
            return
        if self._has_open_order_at("buy", px):
            return

        # Client IDs include prefix (recognized across sessions) + session tag salt
        cid = f"{GBOT_PREFIX}BUY_{int(px*10)}_{self.session_tag.split('_')[-1]}"

        # Delta Exchange specific parameters (no extra positional args)
        params = {"client_order_id": cid}
        try:
            o = _retry_operation(self.ex.create_order, self.symbol,
                                 "limit", "buy", self.lot, px, params, max_retries=2)
            oid = o.get("id")
            if oid:
                self._active_client_ids.add(cid)
                self.pending_buy = {
                    "px": px, "order_id": oid, "client_id": cid}
                log.info(
                    orange(f"grid: placed BUY {self.lot} @{_fmt_px(px)} (id={oid})"))
            else:
                log.error("create_order returned no id")
                self._enter_cooldown()
        except Exception as e:
            log.error(f"place BUY @{_fmt_px(px)} failed: {e}")
            self._enter_cooldown()

    def _place_tp_sell(self, px: float) -> Tuple[Optional[str], Optional[str]]:
        cid = f"{GBOT_PREFIX}TP_{int(px*10)}_{self.session_tag.split('_')[-1]}"

        # Delta Exchange specific parameters for reduce-only (no extra positional args)
        params = {"client_order_id": cid, "reduce_only": True}
        try:
            o = _retry_operation(self.ex.create_order, self.symbol,
                                 "limit", "sell", self.lot, px, params, max_retries=2)
            oid = o.get("id")
            if oid:
                self._active_client_ids.add(cid)
                log.info(
                    orange(f"grid: placed TP SELL {self.lot} @{_fmt_px(px)} (id={oid})"))
                return oid, cid
            else:
                log.error("TP create_order returned no id")
                return None, None
        except Exception as e:
            log.error(f"place TP @{_fmt_px(px)} failed: {e}")
            self._enter_cooldown()
            return None, None

    def _cancel_pending_if_any(self):
        if not self.pending_buy:
            return
        oid = self.pending_buy.get("order_id")
        cid = self.pending_buy.get("client_id", "")
        self.pending_buy = None
        if oid:
            try:
                _retry_operation(self.ex.cancel_order, oid,
                                 self.symbol, max_retries=2)
                log.info(orange(f"grid: canceled pending BUY {oid}"))
            except Exception as e:
                log.warning(f"cancel {oid} failed: {e}")
        if cid:
            self._active_client_ids.discard(cid)

    # ---------------- Confirm helpers ----------------
    def _try_confirm_by_trades(self, pend: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        try:
            # Fetch trades from a longer time window to ensure we catch the fill
            since = self.last_trades_since - 30000 if self.last_trades_since else _now_ms() - \
                300000  # 5 minutes back
            trades = _retry_operation(
                self.ex.fetch_my_trades, self.symbol, since, max_retries=2)
        except Exception as e:
            log.warning(f"fetch trades for confirm failed: {e}")
            return (False, _safe_float(pend["px"]), [])

        oid = pend.get("order_id")
        cid = pend.get("client_id", "")
        acc_qty, px_qty = 0.0, 0.0
        fids: List[str] = []

        for tr in trades or []:
            try:
                if str(tr.get("side", "")).lower() != "buy":
                    continue

                # Match by order ID or client order ID
                trade_oid = self._get_trade_order_id(tr)
                trade_cid = str((tr.get("info") or {}).get(
                    "client_order_id", ""))

                if not ((oid and trade_oid == oid) or (cid and trade_cid == cid)):
                    continue

                q = _safe_float(tr.get("amount"))
                p = _safe_float(tr.get("price"))
                if q > 0 and p > 0:
                    acc_qty += q
                    px_qty += q * p
                    fid = tr.get("id")
                    if fid:
                        fids.append(str(fid))
            except Exception as e:
                log.warning(f"trade parse error {tr.get('id', '?')}: {e}")

        if acc_qty >= self.lot * FILL_THRESHOLD:
            avg = px_qty / max(acc_qty, 1e-10)
            return (True, avg, fids)
        return (False, _safe_float(pend["px"]), [])

    def _try_confirm_by_order(self, pend: Dict[str, Any]) -> Tuple[bool, float]:
        # Skip order status confirmation for Delta Exchange since fetchOrder() is not supported
        if self.is_delta_exchange:
            return (False, _safe_float(pend["px"]))

        oid = pend.get("order_id")
        if not oid:
            return (False, _safe_float(pend["px"]))
        try:
            o = _retry_operation(self.ex.fetch_order, oid,
                                 self.symbol, max_retries=2)
        except Exception as e:
            log.warning(f"fetch_order {oid} failed: {e}")
            return (False, _safe_float(pend["px"]))

        status = str(o.get("status", "")).lower()
        # Delta Exchange order statuses
        if status in ("closed", "filled", "completely_filled"):
            avg = _safe_float(o.get("average") or o.get("price") or pend["px"])
            return (True, avg)
        return (False, _safe_float(pend["px"]))

    def _has_open_order_at(self, side: str, price: float) -> bool:
        try:
            oo = _retry_operation(self.ex.fetch_open_orders,
                                  self.symbol, max_retries=2)
        except Exception as e:
            log.warning(f"open_orders failed: {e}")
            return False
        for o in oo or []:
            try:
                s = str(o.get("side", "")).lower()
                px = _safe_float(o.get("price"))
                cid = self._get_client_order_id(o)
                if s == side.lower() and abs(px - price) <= TICK_SIZE and cid and cid.startswith(GBOT_PREFIX):
                    return True
            except Exception as e:
                log.warning(f"order check err {o.get('id', '?')}: {e}")
        return False

    def _is_reduce_only(self, o: Dict[str, Any]) -> bool:
        try:
            info = o.get("info") or {}
            return bool(
                o.get("reduceOnly") or
                o.get("reduce_only") or
                info.get("reduce_only") or
                info.get("reduceOnly")
            )
        except Exception:
            return False

    def _enter_cooldown(self, sec: int = None):
        if sec is None:
            sec = COOLDOWN_SECONDS
        self.cooldown_until = int(time.time()) + sec
        log.warning(f"grid: cooldown {sec}s until {self.cooldown_until}")

    def _get_client_order_id(self, order: Dict[str, Any]) -> str:
        # Delta Exchange uses client_order_id
        return str(order.get("client_order_id") or order.get("clientOrderId") or "")

    def _get_trade_order_id(self, trade: Dict[str, Any]) -> Optional[str]:
        # Delta Exchange trade structure - check multiple possible fields
        return (trade.get("order_id") or
                trade.get("order") or
                trade.get("orderId") or
                (trade.get("info") or {}).get("order_id"))

    def _cleanup_on_exit(self):
        log.info("grid: cleanup…")
        try:
            self._cancel_pending_if_any()
            total_exposure = len(self.open_tranches) * self.lot
            log.info(f"grid: final state — {len(self.open_tranches)} open tranches, "
                     f"total exposure: {total_exposure} lots, {len(self._active_client_ids)} active ids")
        except Exception as e:
            log.error(f"cleanup error: {e}")


# ---------------- Entrypoint ----------------
def run_grid_strategy(dc, symbol, lower, upper, step, ref, lot, max_open=5, hb_sec=5):
    try:
        lot = int(float(lot))  # enforce integer lots for Delta
        if lot <= 0:
            raise ValueError("Lot size must be positive integer")

        log.info(orange(
            f"grid: init  symbol={symbol} LOWER={lower} UPPER={upper} STEP={step} REF={ref} LOT={lot} max_open={max_open}"))
        log.info(
            orange(f"grid: MAXIMUM EXPOSURE WILL BE {max_open * lot} LOTS"))

        # quick validation
        if any(v is None for v in (symbol, lower, upper, step, ref, lot)):
            raise ValueError("all parameters must be provided")
        if float(lower) >= float(upper):
            raise ValueError("Lower < Upper required")
        if not (float(lower) <= float(ref) <= float(upper)):
            raise ValueError("Ref within bounds required")
        if float(step) <= 0 or lot <= 0:
            raise ValueError("Step/Lot must be positive")

        GridBot(dc, symbol, lower, upper, step,
                ref, lot, max_open, hb_sec).run()
    except Exception as e:
        log.critical(f"grid: fatal init error: {e}")
        log.debug(traceback.format_exc())
        raise
