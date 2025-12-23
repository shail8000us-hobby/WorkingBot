import os
import sys
import logging
from dotenv import load_dotenv
from pathlib import Path

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config

try:
    import ccxt
except Exception as e:
    raise RuntimeError("ccxt is required. Install with: pip install ccxt python-dotenv requests") from e

log = logging.getLogger("runner")

def ensure_ccxt():
    """
    Initialize and return a CCXT Delta exchange instance with correct base URL and credentials.
    Returns a live, rate-limited client with markets loaded.
    
    Configuration from YAML:
    - api.live_private_url or api.demo_private_url (based on trading_mode)
    - API credentials from environment (DELTA_API_KEY, DELTA_API_SECRET)
    """
    # Load YAML configuration
    yaml_config = get_config()
    
    # API credentials from environment (security - never in YAML)
    api_key = (os.getenv("DELTA_API_KEY") or "").strip()
    api_secret = (os.getenv("DELTA_API_SECRET") or "").strip()
    
    # Get API URL from YAML based on trading mode
    if yaml_config.trading_mode == 'demo':
        base_url = yaml_config.api.demo_private_url.rstrip("/")
    else:
        base_url = yaml_config.api.live_private_url.rstrip("/")

    if not api_key or not api_secret:
        log.warning("CCXT: Missing DELTA_API_KEY or DELTA_API_SECRET — private calls will fail.")

    # Construct exchange
    ex = ccxt.delta({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        # delta is futures-only; setting options is harmless
        "options": {"defaultType": "future"},
    })

    # Force base url for both public/private (India cluster by default)
    ex.urls["api"] = {"public": base_url, "private": base_url}
    log.info("CCXT: Using base URL: %s", base_url)

    # Load markets once
    try:
        ex.load_markets()
        log.info("CCXT: Markets loaded (%d symbols).", len(getattr(ex, "symbols", []) or []))
    except Exception as e:
        log.error("CCXT: load_markets failed: %s", e)
        raise

    return ex
