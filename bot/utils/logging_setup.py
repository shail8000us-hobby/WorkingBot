import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config


def get_logger(name: str = "bot"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    cfg = get_config()
    level = cfg.logging.level.upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Prevent propagation to root logger (prevents duplicate logs)
    logger.propagate = False
    
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(log_dir / "bot.log", maxBytes=1_000_000, backupCount=5)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
