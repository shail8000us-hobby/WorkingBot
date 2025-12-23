from dataclasses import dataclass

from bot.utils.logging_setup import get_logger


@dataclass
class GridConfig:
    symbol: str = "BTCUSD"
    lot_size: float = 1.0
    grid_step: float = 500.0
    lower_bound: float = 108000.0
    upper_bound: float = 110000.0
    reference_level: float = 109800.0


class GridStrategy:
    def __init__(self, cfg: GridConfig):
        self.cfg = cfg
        self.log = get_logger("strategy")

    def next_buy_level(self, price: float, ref: float | None = None) -> float | None:
        """
        If price is at/under (reference - step) and within bounds, suggest a buy level.
        Otherwise return None.
        """
        anchor = self.cfg.reference_level if ref is None else ref
        target = anchor - self.cfg.grid_step
        if price <= target and price >= self.cfg.lower_bound:
            return target
        return None

    def paired_sell_price(self, buy_price: float) -> float:
        return buy_price + self.cfg.grid_step
