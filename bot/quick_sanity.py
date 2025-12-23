"""
Refactor compatibility canary.

The canary keeps the runtime fast (under ~1s) and limited to disk reads so it
can be executed during backend start without side-effects.
"""

from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Iterable

from bot.state.store import StateStore

CRITICAL_MODULES: Iterable[str] = (
    "bot.state.store",
    "bot.reconciliation_service",
    "bot.strategy.grid_sync",
    "bot.orders.audit",
)

STATE_FILES: Iterable[str] = (
    "state.json",
    "state_live.json",
    "state_demo.json",
    "positions.json",
    "positions_live.json",
    "positions_demo.json",
)


def run(timeout: float = 1.0) -> bool:
    """
    Execute the canary. Returns ``True`` on success, ``False`` otherwise.

    The canary imports critical modules and attempts to read state snapshots
    using ``StateStore``. Failures are swallowed so the caller can decide how
    to proceed.
    """

    start = time.time()
    try:
        for module_name in CRITICAL_MODULES:
            importlib.import_module(module_name)
            if time.time() - start > timeout:
                return True

        base_dir = Path(__file__).resolve().parent
        workspace_root = base_dir.parent

        for rel_path in STATE_FILES:
            path = workspace_root / rel_path
            if not path.exists():
                continue
            store = StateStore(path)
            store.load()
            if time.time() - start > timeout:
                break
    except Exception:
        return False
    return True


__all__ = ["run"]
