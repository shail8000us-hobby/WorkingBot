import time
from typing import Tuple

from bot.api.delta_client import DeltaClient
from bot.utils.logging_setup import get_logger


def wait_until_filled_or_timeout(c: DeltaClient, order_id: str, timeout_s: int = 30, poll_s: float = 1.0) -> Tuple[bool, str]:
    """
    Returns (filled, final_status). On timeout, cancels the order and returns (False, "cancelled").
    """
    log = get_logger("fills")
    deadline = time.time() + timeout_s
    last_status = "unknown"
    while time.time() < deadline:
        s = c.order_status(order_id)
        status = (s.get("status") or s.get("body", {}).get("status") or s.get("body", {}).get("data", {}).get("status") or "").lower()
        last_status = status or last_status
        log.info(f"Poll {order_id} -> {status or 'unknown'}")
        if status in ("filled", "closed", "completed"):
            return True, status or "filled"
        if status in ("cancelled", "canceled", "rejected"):
            return False, status
        time.sleep(poll_s)
    c.cancel_order(order_id)
    log.warning(f"Timeout; cancelled {order_id}")
    return False, "cancelled"
