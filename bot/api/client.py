import os
import time

from bot.utils.logging_setup import get_logger
from config.loader import get_config


class PriceClient:
    """
    Minimal price source for now (mock). Later, we will swap to real Delta ticker.
    """

    def __init__(self):
        self.log = get_logger("api")
        cfg = get_config()
        try:
            # Try GRIDBOT_REF from env first, then fall back to YAML config reference_level
            ref_str = os.getenv("GRIDBOT_REF")
            if ref_str:
                self._px = float(ref_str)
            else:
                self._px = cfg.api.reference_level
        except Exception:
            self._px = 109800.0

    def ticker_price(self, symbol: str) -> float:
        # Tiny bounded wiggle to simulate market movement
        t = int(time.time()) % 10
        wiggle = -2 if t < 5 else 2
        self._px = max(1000.0, self._px + wiggle)
        self.log.debug(f"Mock ticker {symbol} -> {self._px}")
        return self._px
