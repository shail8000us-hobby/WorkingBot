from dataclasses import dataclass
from typing import List

from bot.utils.logging_setup import get_logger

log = get_logger("levels")


@dataclass
class LadderCfg:
    grid_step: float
    lower_bound: float
    upper_bound: float
    reference_level: float


def build_buy_ladder(cfg: LadderCfg) -> List[float]:
    step, lo, ref = cfg.grid_step, cfg.lower_bound, cfg.reference_level
    if step <= 0 or lo >= cfg.upper_bound:
        return []
    gap = (ref - lo) % step
    start = ref - (gap if gap != 0 else step)
    out = []
    p = start
    while p >= lo:
        out.append(round(p, 8))
        p -= step
    out.sort()
    return out
