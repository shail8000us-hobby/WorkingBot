from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


def color(s: str, c: str) -> str:
    codes = {
        "red": "\033[31m",
        "grn": "\033[32m",
        "ylw": "\033[33m",
        "dim": "\033[2m",
        "clr": "\033[0m",
    }
    return f"{codes.get(c, '')}{s}{codes['clr']}"


def preflight(logger=None):
    """Hard stop if execute_orders=true and user hasn't set i_understand_live=YES."""
    cfg = get_config()
    exec_orders = cfg.safety.execute_orders
    understood = cfg.safety.i_understand_live.upper() == "YES"
    mode = "LIVE" if exec_orders else "DRY"
    note = f"Mode={mode}  execute_orders={exec_orders}  i_understand_live={cfg.safety.i_understand_live}"
    if exec_orders and not understood:
        msg = f"SAFETY BLOCK: {note} — set i_understand_live=YES to allow live execution."
        if logger:
            logger.error(msg)
        else:
            print(color(msg, "red"), file=sys.stderr)
        sys.exit(2)
    # Optional, log a friendly banner when safe
    ok = f"SAFETY OK: {note}"
    if logger:
        logger.info(ok)
    else:
        print(color(ok, "grn"))
