from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


@dataclass
class Watchdog:
    max_api_fail: int = 3
    max_stale_s: int = 30
    autosave_every: int = 10
    kill_file: str = "bot/panic.on"

    api_fail: int = 0
    last_price: float | None = None
    last_ts: float = 0.0
    tick_count: int = 0
    
    def __post_init__(self):
        """Load config values after initialization"""
        cfg = get_config()
        self.max_api_fail = cfg.monitoring.watchdog.max_api_fail
        self.max_stale_s = cfg.monitoring.watchdog.max_stale_s
        self.autosave_every = cfg.monitoring.watchdog.autosave_every
        self.kill_file = cfg.monitoring.watchdog.kill_file

    def note_price(self, price: float) -> None:
        now = time.time()
        if self.last_price is None or price != self.last_price:
            self.last_price, self.last_ts = price, now

    def note_api_fail(self) -> None:
        self.api_fail += 1

    def note_api_ok(self) -> None:
        self.api_fail = 0

    def should_halt(self) -> tuple[bool, str]:
        # kill-switch via file
        if os.path.exists(self.kill_file):
            return True, f"Kill switch file present: {self.kill_file}"
        # api failure breaker
        if self.api_fail >= self.max_api_fail:
            return True, f"API failures >= {self.max_api_fail}"
        # stale price breaker
        if self.last_ts and (time.time() - self.last_ts) > self.max_stale_s:
            return True, f"Price stale > {self.max_stale_s}s"
        return False, ""

    def bump_tick(self) -> bool:
        self.tick_count += 1
        return (self.tick_count % self.autosave_every) == 0
