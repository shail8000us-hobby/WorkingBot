import os
import sys
import logging
from dataclasses import dataclass

# --- logging ---
os.makedirs("bot/logs", exist_ok=True)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot/logs/bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("runner")

# --- env ---
try:
    from dotenv import load_dotenv
    env_path = os.getenv("ENV_PATH", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        log.info(f"env: loaded {env_path}")
    # Load API keys from secrets
    if os.path.exists("secrets/api_keys.env"):
        load_dotenv("secrets/api_keys.env")
        log.info("env: loaded secrets/api_keys.env")
except Exception as e:
    log.warning(f"dotenv load warning: {e}")

# Load config from YAML
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.loader import get_config

cfg = get_config()

# bridge: map YAML config → environment variables for ccxt
os.environ["DELTA_API_KEY"] = os.getenv("DELTA_API_KEY", "")
os.environ["DELTA_API_SECRET"] = os.getenv("DELTA_API_SECRET", "")

# Get base URL based on trading mode
if cfg.trading_mode.value == 'demo':
    os.environ["DELTA_BASE_URL"] = cfg.api.demo.base_url
else:
    os.environ["DELTA_BASE_URL"] = cfg.api.live.base_url

# Map YAML grid config to GRIDBOT_* environment variables for legacy code
os.environ["GRIDBOT_SYMBOL"] = cfg.bot.symbol
os.environ["GRIDBOT_LOWER"] = str(cfg.grid.lower_bound)
os.environ["GRIDBOT_UPPER"] = str(cfg.grid.upper_bound)
os.environ["GRIDBOT_STEP"] = str(cfg.grid.step)
os.environ["GRIDBOT_REF"] = str(cfg.grid.reference_level)
os.environ["GRIDBOT_LOT"] = str(cfg.bot.lot_size)
os.environ["GRIDBOT_MAX_OPEN"] = str(cfg.bot.max_open_orders)
os.environ["GRIDBOT_HB_SEC"] = str(cfg.monitoring.heartbeat.check_interval)

log.info("✅ Dashboard config loaded from YAML")

# --- ccxt exchange setup ---
import ccxt

def make_delta():
    base = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange").rstrip("/")
    ex = ccxt.delta({
        "apiKey": os.getenv("DELTA_API_KEY"),
        "secret": os.getenv("DELTA_API_SECRET"),
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })
    # force base for both public/private
    ex.urls["api"] = {"public": base, "private": base}
    return ex

@dataclass
class DC:
    ex: object

# --- strategy ---
from bot.strategy.gbot_clean import run_grid_strategy

def envf(key, default):
    v = os.getenv(key, str(default))
    try:
        return type(default)(v)
    except Exception:
        return default

def main():
    # required inputs (now sourced from GRIDBOT_* which may come from grid_config.env)
    symbol   = os.getenv("GRIDBOT_SYMBOL", "BTC/USD:USD")
    lower    = envf("GRIDBOT_LOWER", 114000.0)
    upper    = envf("GRIDBOT_UPPER", 117000.0)
    step     = envf("GRIDBOT_STEP",  500.0)
    ref      = envf("GRIDBOT_REF",   116000.0)
    lot      = envf("GRIDBOT_LOT",   1)
    max_open = envf("GRIDBOT_MAX_OPEN", 5)
    hb_sec   = envf("GRIDBOT_HB_SEC", 10)

    ex = make_delta()
    try:
        markets = ex.load_markets()
        log.info(f"grid: attached ccxt handle: {ex.id}")
        log.info(f"grid: online  symbol={symbol}  LOWER={lower}  UPPER={upper}  STEP={step}  REF={ref}  LOT={float(lot)}  max_open={max_open}")
        _ = markets.get(symbol)
    except Exception as e:
        log.warning(f"ccxt init warning: {e}")

    dc = DC(ex=ex)
    run_grid_strategy(dc, symbol, lower, upper, step, ref, lot, max_open=max_open, hb_sec=hb_sec)

if __name__ == "__main__":
    sys.exit(main())
