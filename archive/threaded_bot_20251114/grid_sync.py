import os
import time
import typing
from pathlib import Path

import ccxt

from bot.config.aliases import upgrade_mapping
from bot.state.store import StateStore

SYMBOL = os.getenv("DELTA_SYMBOL", "BTC/USD:USD")

# Non-grid knobs still from env (these are not part of grid_config.env)
MAX_RUNGS    = int(os.getenv("MAX_CONCURRENT_TRANCHES", "5"))
SYNC_SEC     = float(os.getenv("GRID_SYNC_SEC", "10"))
COOLDOWN_SEC = SYNC_SEC * 2
LOT_DEFAULT  = float(os.getenv("GRIDBOT_LOT", "1"))  # fallback if state.json missing LOT

CID_PREFIX = "GBOT_"
STATE_PATH = Path("state.json")
STATE_STORE = StateStore(STATE_PATH, default={})

def _now_ms() -> int:
    return int(time.time() * 1000)

def _client() -> ccxt.Exchange:
    api_key = os.getenv('DELTA_API_KEY')
    api_secret = os.getenv('DELTA_API_SECRET')
    
    if not api_key or not api_secret:
        raise ValueError("DELTA_API_KEY and DELTA_API_SECRET environment variables must be set")
    
    try:
        ex = ccxt.delta({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        ex.urls['api'] = {
            'public':  'https://api.india.delta.exchange',
            'private': 'https://api.india.delta.exchange'
        }
        return ex
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Delta Exchange client: {e}") from e

def _load_state() -> dict:
    try:
        return STATE_STORE.load()
    except Exception:
        return {}


def _save_state(d: dict) -> None:
    try:
        STATE_STORE.save(d)
    except Exception:
        pass

def _grid_from_state(state: dict) -> typing.Tuple[float, float, float, float, float]:
    """Return (LOWER, UPPER, STEP, REF, LOT) strictly from state.json with safe fallbacks."""
    upgrade_mapping(state, record=False)
    LOWER = float(state.get("GRIDBOT_LOWER")) if state.get("GRIDBOT_LOWER") is not None else 100000.0
    UPPER = float(state.get("GRIDBOT_UPPER")) if state.get("GRIDBOT_UPPER") is not None else 112500.0
    STEP  = float(state.get("GRIDBOT_STEP"))  if state.get("GRIDBOT_STEP")  is not None else 500.0
    REF   = float(state.get("GRIDBOT_REF")) if state.get("GRIDBOT_REF") is not None else 108800.0
    LOT   = float(state.get("GRIDBOT_LOT")) if state.get("GRIDBOT_LOT") is not None else LOT_DEFAULT
    
    # Validate grid parameters
    if UPPER <= LOWER:
        raise ValueError(f"GRIDBOT_UPPER ({UPPER}) must be greater than GRIDBOT_LOWER ({LOWER})")
    if STEP <= 0:
        raise ValueError(f"GRIDBOT_STEP ({STEP}) must be positive")
    if not (LOWER <= REF <= UPPER):
        raise ValueError(f"GRIDBOT_REF ({REF}) must be between GRIDBOT_LOWER ({LOWER}) and GRIDBOT_UPPER ({UPPER})")
    if LOT <= 0:
        raise ValueError(f"GRIDBOT_LOT ({LOT}) must be positive")
    
    return LOWER, UPPER, STEP, REF, LOT

def _get_ticker(ex) -> dict:
    try:
        return ex.fetch_ticker(SYMBOL) or {}
    except Exception:
        return {}

def _our(order: dict) -> bool:
    cid = order.get('clientOrderId') or (order.get('info') or {}).get('client_order_id')
    return isinstance(cid, str) and cid.startswith(CID_PREFIX)

def _our_open_orders(ex) -> list:
    try:
        oo = ex.fetch_open_orders(SYMBOL) or []
    except Exception:
        oo = []
    return [o for o in oo if _our(o)]

def _fetch_order(ex, order_id: str) -> typing.Optional[dict]:
    try:
        return ex.fetch_order(order_id, SYMBOL)
    except Exception:
        return None

def _place_limit_buy(ex, price: float, lot: float, log) -> typing.Optional[str]:
    cid = f"{CID_PREFIX}{_now_ms()}_BUY"
    try:
        o = ex.create_order(
            SYMBOL, type="limit", side="buy", amount=lot, price=price,
            params={"clientOrderId": cid, "client_order_id": cid}
        )
        log.info(f"grid: placed BUY {lot} @ {price} (id={o.get('id')})")
        return o.get('id') or None
    except Exception as e:
        log.warning(f"grid: place BUY @ {price} failed: {e}")
        return None

def _cleanup_filled_tps(ex, ladder: list, step: float, log) -> list:
    """Remove tranches whose TP orders have been filled"""
    remaining = []
    for tr in ladder:
        tp_id = tr.get('tp_id')
        if tp_id:
            od = _fetch_order(ex, tp_id)
            if od:
                status = (od.get('status') or '').lower()
                # Delta Exchange uses 'closed' or 'filled' for completed orders
                if status in ('closed', 'filled'):
                    tp_price = float(tr['entry']) + step
                    entry_price = float(tr['entry'])
                    profit = (tp_price - entry_price) * float(tr.get('size', 0))
                    log.info(f"grid: ✅ TP FILLED @ {tp_price:.1f} (entry {entry_price:.1f}) - PROFIT: {profit:.2f} USD 🎉")
                    continue  # Don't add to remaining (remove this tranche)
        remaining.append(tr)
    return remaining

def _ensure_reduce_only_tp(ex, tranche: dict, step: float, lot: float, log) -> None:
    target = float(tranche['entry']) + step
    oo = _our_open_orders(ex)
    # keep an existing correct TP if present
    for o in oo:
        if o.get('side') != 'sell':
            continue
        px = o.get('price')
        try:
            px = float(px) if px is not None else None
        except Exception:
            px = None
        # Use more reasonable tolerance for crypto prices (0.5 USD)
        if px is not None and abs(px - target) < 0.5:
            tranche['tp_id'] = o.get('id')
            return
    # else create it
    cid = f"{CID_PREFIX}{_now_ms()}_TP"
    try:
        o = ex.create_order(
            SYMBOL, type="limit", side="sell", amount=lot, price=target,
            params={"reduce_only": True, "clientOrderId": cid, "client_order_id": cid}
        )
        tranche['tp_id'] = o.get('id')
        log.info(f"grid: placed TP SELL {lot} @ {target} reduce_only (id={tranche['tp_id']})")
    except Exception as e:
        log.warning(f"grid: place TP SELL @ {target} failed: {e}")

def _cancel(ex, order_id: str, log) -> None:
    try:
        ex.cancel_order(order_id, SYMBOL)
        log.info(f"grid: canceled stray order {order_id}")
    except Exception as e:
        log.warning(f"grid: cancel failed for {order_id}: {e}")

def _clean_book(ex, want_buy_px: typing.Optional[float], step: float, tranches: list, log) -> None:
    wanted_sell = set(float(t['entry']) + step for t in tranches)
    oo = _our_open_orders(ex)
    kept_buy = False
    # Use reasonable price tolerance for crypto (0.5 USD instead of 1e-9)
    price_tolerance = 0.5
    for o in oo:
        side = o.get('side')
        price = o.get('price')
        try:
            price = float(price) if price is not None else None
        except Exception:
            price = None
        keep = False
        if side == 'buy' and want_buy_px is not None and price is not None:
            if abs(price - want_buy_px) < price_tolerance and not kept_buy:
                kept_buy = True
                keep = True
        elif side == 'sell' and price is not None:
            if any(abs(price - ws) < price_tolerance for ws in wanted_sell):
                keep = True
        if not keep and o.get('id'):
            _cancel(ex, o['id'], log)

def _active(last: float, lower: float, upper: float) -> bool:
    return last is not None and (lower <= last <= upper)

def _next_entry_price(tranches: list, ref: float, step: float) -> float:
    if not tranches:
        return ref - step
    lowest = min(float(t['entry']) for t in tranches)
    return lowest - step

def _within_bounds(px: float, lower: float) -> bool:
    return px >= lower

def _tranches(state: dict, lot: float) -> list:
    arr = state.get("LADDER")
    if isinstance(arr, list):
        for t in arr:
            t.setdefault('size', lot)
            t.setdefault('tp_id', None)
            t.setdefault('created_at', _now_ms())
        return arr
    return []

def _set_tranches(state: dict, arr: list) -> None:
    state["LADDER"] = arr

def _pending_entry(state: dict) -> dict:
    pe = state.get("PENDING_ENTRY")
    if isinstance(pe, dict):
        return pe
    return {"price": None, "order_id": None}

def _set_pending_entry(state: dict, price: typing.Optional[float], order_id: typing.Optional[str]) -> None:
    state["PENDING_ENTRY"] = {"price": price, "order_id": order_id}

def sync_once(state: dict, log) -> None:
    """
    Reads grid strictly from state.json (populated by dashboard/set_grid.sh).
    Maintains one pending BUY at next rung, and one reduce-only TP per filled tranche.
    Respects active range and max concurrent tranches.
    """
    # Load fresh config but preserve runtime state
    fresh_config = _load_state()
    
    # Only update grid parameters, not runtime tracking (LADDER, PENDING_ENTRY, COOLDOWN_UNTIL, etc.)
    grid_params = ["GRIDBOT_LOWER", "GRIDBOT_UPPER", "GRIDBOT_STEP", "GRIDBOT_REF", "GRIDBOT_LOT"]
    for key in grid_params:
        if key in fresh_config:
            state[key] = fresh_config[key]

    LOWER, UPPER, STEP, REF, LOT = _grid_from_state(state)

    ex = _client()
    t = _get_ticker(ex)
    last = t.get('last')
    try:
        last = float(last) if last is not None else None
    except Exception:
        last = None

    active = _active(last, LOWER, UPPER)
    state["ACTIVE"] = bool(active)
    if not active:
        _save_state(state)
        return

    if STEP <= 0 or LOT <= 0 or UPPER <= LOWER:
        _save_state(state)
        return

    now = time.time()
    cd_until = state.get("COOLDOWN_UNTIL")
    if isinstance(cd_until, (int, float)) and now < cd_until:
        _save_state(state)
        return

    ladder = _tranches(state, LOT)
    pending = _pending_entry(state)

    # CRITICAL: Clean up filled TPs BEFORE other operations to prevent infinite growth
    ladder = _cleanup_filled_tps(ex, ladder, STEP, log)

    # Track/ingest pending order status (did it fill/cancel?)
    if pending.get("order_id"):
        od = _fetch_order(ex, pending["order_id"])
        if od:
            status = (od.get('status') or '').lower()
            filled = float(od.get('filled') or 0.0)
            px = od.get('price')
            try:
                px = float(px) if px is not None else pending.get("price")
            except Exception:
                px = pending.get("price")
            if status == "closed" and filled > 0:
                ladder.append({"entry": float(px), "size": LOT, "tp_id": None, "created_at": _now_ms()})
                log.info(f"grid: ✅ BUY FILLED @ {px:.1f} | Active tranches: {len(ladder)}/{MAX_RUNGS}")
                log.info(f"grid: 📊 New tranche created - Entry: {px:.1f}, Size: {LOT}, TP will be: {px + STEP:.1f}")
                pending = {"price": None, "order_id": None}
            elif status == "canceled":
                log.info("grid: ⚠️ Pending BUY canceled; will re-arm if needed")
                pending = {"price": None, "order_id": None}

    # Ensure exactly one reduce-only TP per tranche
    for tr in ladder:
        _ensure_reduce_only_tp(ex, tr, STEP, LOT, log)

    # Respect max concurrent tranches
    if len(ladder) >= MAX_RUNGS:
        log.warning(f"grid: ⚠️ MAX TRANCHES REACHED ({len(ladder)}/{MAX_RUNGS}) - No new BUYs until TP fills")
        if pending.get("order_id"):
            od = _fetch_order(ex, pending["order_id"])
            if od and (od.get('status') or '').lower() == 'open':
                _cancel(ex, pending["order_id"], log)
        pending = {"price": None, "order_id": None}
        _set_tranches(state, ladder)
        _set_pending_entry(state, pending.get("price"), pending.get("order_id"))
        _save_state(state)
        return

    # Compute next rung from state grid
    next_px = _next_entry_price(ladder, REF, STEP)
    if not _within_bounds(next_px, LOWER):
        log.warning(f"grid: ⛔ Next BUY price {next_px:.1f} below LOWER bound {LOWER:.1f} - Grid stopped")
        log.info(f"grid: Keeping existing {len(ladder)} tranche(s) with TPs active")
        _clean_book(ex, None, STEP, ladder, log)  # keep TPs only
        _set_tranches(state, ladder)
        _set_pending_entry(state, None, None)
        _save_state(state)
        return

    # Keep book minimal (one BUY at next_px + TPs)
    _clean_book(ex, next_px, STEP, ladder, log)

    # If pending BUY already open at next_px, we're good
    if pending.get("order_id"):
        od = _fetch_order(ex, pending["order_id"])
        if od and (od.get('status') or '').lower() == 'open':
            try:
                od_px = float(od.get('price') or next_px)
            except Exception:
                od_px = next_px
            # Use reasonable price tolerance (0.5 USD)
            if abs(od_px - next_px) < 0.5:
                _set_tranches(state, ladder)
                _set_pending_entry(state, next_px, pending["order_id"])
                _save_state(state)
                return
            else:
                _cancel(ex, pending["order_id"], log)
                pending = {"price": None, "order_id": None}

    # Place new pending BUY at next_px
    new_id = _place_limit_buy(ex, next_px, LOT, log)
    if new_id is None:
        state["COOLDOWN_UNTIL"] = time.time() + COOLDOWN_SEC
        log.warning(f"grid: entering cooldown until {state['COOLDOWN_UNTIL']:.0f}")
        _set_tranches(state, ladder)
        _set_pending_entry(state, None, None)
        _save_state(state)
        return

    _set_tranches(state, ladder)
    _set_pending_entry(state, next_px, new_id)
    _save_state(state)
