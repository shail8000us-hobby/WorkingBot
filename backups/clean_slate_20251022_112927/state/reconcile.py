from __future__ import annotations

from typing import Any, Dict, List, Set

from bot.api.delta_client import DeltaClient
from bot.config.aliases import upgrade_mapping
from bot.utils.logging_setup import get_logger


def reconcile_state(dc: DeltaClient, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reconcile local state with the exchange:
      - If DELTA_READ_PRIVATE=false or no keys: shape-only cleanup (what you had).
      - If allowed: fetch open orders and remove any local entries whose order_id is not on exchange.
    """
    log = get_logger("reconcile")
    upgrade_mapping(state, record=False)
    state.setdefault("open_positions", [])
    cleaned: List[Dict[str, Any]] = []

    # 1) Always prune malformed entries
    for p in state["open_positions"]:
        if all(k in p for k in ("price", "qty")):
            cleaned.append(p)
        else:
            log.warning(f"Pruned malformed position: {p}")
    state["open_positions"] = cleaned

    # 2) If private read permitted, cross-check with exchange
    try:
        remote = dc.open_orders()
        if remote:
            remote_ids: Set[str] = {str(o.get("order_id")) for o in remote if o.get("order_id")}
            before = len(state["open_positions"])
            state["open_positions"] = [p for p in state["open_positions"] if str(p.get("order_id")) in remote_ids or p.get("order_id") == "demo"]
            after = len(state["open_positions"])
            if after != before:
                log.info(f"Reconciled with exchange: positions {before} -> {after} (pruned stale locals)")
            else:
                log.info(f"Reconciled with exchange: positions {after} (no change)")
        else:
            log.info("Reconcile: exchange open-orders unavailable or empty; kept local state as-is.")
    except Exception as e:
        log.warning(f"Reconcile skipped due to error: {e}")

    return state

# --- Hot Reload Extension ---
import os, time
from dotenv import dotenv_values

_last_reload_check = 0
_last_config_mtime = None

def maybe_hot_reload(state):
    """Reload grid_config.env if HOT_RELOAD=1 and file changed"""
    global _last_reload_check, _last_config_mtime
    if os.getenv("HOT_RELOAD", "0") != "1":
        return state

    now = time.time()
    if now - _last_reload_check < 5:
        return state
    _last_reload_check = now

    cfg_file = "grid_config.env"
    if not os.path.exists(cfg_file):
        return state

    mtime = os.path.getmtime(cfg_file)
    if _last_config_mtime is not None and mtime <= _last_config_mtime:
        return state
    _last_config_mtime = mtime

    try:
        cfg = dotenv_values(cfg_file)
        new_state = dict(state)
        upgrade_mapping(cfg, record=False)
        upgrade_mapping(new_state, record=False)
        new_state.update({
            "GRIDBOT_LOWER": float(cfg.get("GRIDBOT_LOWER", new_state.get("GRIDBOT_LOWER", 0))),
            "GRIDBOT_UPPER": float(cfg.get("GRIDBOT_UPPER", new_state.get("GRIDBOT_UPPER", 0))),
            "GRIDBOT_STEP": float(cfg.get("GRIDBOT_STEP", new_state.get("GRIDBOT_STEP", 0))),
            "GRIDBOT_REF": float(cfg.get("GRIDBOT_REF", new_state.get("GRIDBOT_REF", 0))),
            "GRIDBOT_LOT": float(cfg.get("GRIDBOT_LOT", new_state.get("GRIDBOT_LOT", 0))),
            "GRID_ACTIVE": True,
            "LAST_SET_AT": int(time.time()),
        })
        print(f"\033[36m[HOT-RELOAD] Grid reloaded from {cfg_file}: {new_state}\033[0m")
        return new_state
    except Exception as e:
        print("Hot reload failed:", e)
        return state
