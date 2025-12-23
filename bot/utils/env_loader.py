"""
Environment Loader with Demo/Live Mode Support

This module handles loading environment variables and automatically
switches between testnet (demo) and live configurations based on TRADING_MODE.

Safety Features:
- Defaults to "demo" mode if not specified
- Validates API keys are set for the selected mode
- Logs clear warnings when in live mode
- Prevents accidental live trading
"""

import os
import sys
import logging
from typing import Literal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

logger = logging.getLogger(__name__)

TradingMode = Literal["demo", "live"]


class ModeConfigurationError(Exception):
    """Raised when trading mode configuration is invalid or incomplete"""
    pass


def load_trading_mode_config() -> TradingMode:
    """
    Load and configure trading mode (demo/live) from environment.
    
    Returns:
        TradingMode: Either "demo" or "live"
        
    Raises:
        ModeConfigurationError: If configuration is invalid or API keys missing
    """
    
    # Get trading mode from YAML config
    cfg = get_config()
    trading_mode = cfg.trading_mode.lower().strip()  # trading_mode is at root level, not in safety
    
    # Validate trading mode
    if trading_mode not in ['demo', 'live']:
        logger.error(f"Invalid TRADING_MODE='{trading_mode}'. Must be 'demo' or 'live'. Defaulting to 'demo' for safety.")
        trading_mode = 'demo'
    
    # Log current mode with visual distinction
    if trading_mode == 'demo':
        logger.info("=" * 80)
        logger.info("🟢 DEMO MODE ENABLED - Using Testnet (Paper Trading)")
        logger.info("=" * 80)
        logger.info("✅ Safe to test - No real money at risk")
        logger.info("📍 API: https://testnet-api.delta.exchange")
        logger.info("💰 Funds: Test/Demo funds only")
        logger.info("=" * 80)
    else:
        logger.warning("=" * 80)
        logger.warning("🔴 LIVE MODE ENABLED - REAL MONEY TRADING!")
        logger.warning("=" * 80)
        logger.warning("⚠️  WARNING: This bot will place REAL orders with REAL money")
        logger.warning("📍 API: https://api.india.delta.exchange")
        logger.warning("💰 Funds: Your actual account balance")
        logger.warning("🛡️  Ensure all safety settings are configured correctly")
        logger.warning("=" * 80)
    
    # Configure API credentials based on mode
    _configure_api_credentials(trading_mode)
    
    # Configure API URLs based on mode
    _configure_api_urls(trading_mode)
    
    return trading_mode


def _configure_api_credentials(mode: TradingMode) -> None:
    """
    Set DELTA_API_KEY and DELTA_API_SECRET based on trading mode.
    
    CRITICAL: Loads API credentials from secrets/api_keys.env (NOT from YAML)
    for security reasons. YAML config only stores URLs and settings.
    
    Args:
        mode: Trading mode ("demo" or "live")
        
    Raises:
        ModeConfigurationError: If required API keys are missing
    """
    
    # Load secrets from secrets/api_keys.env
    secrets_file = PROJECT_ROOT / "secrets" / "api_keys.env"
    if not secrets_file.exists():
        raise ModeConfigurationError(
            f"❌ Secrets file not found: {secrets_file}\n"
            "Create secrets/api_keys.env with your API credentials."
        )
    
    # Load environment variables from secrets file
    from dotenv import load_dotenv
    load_dotenv(secrets_file, override=True, verbose=False)
    
    if mode == 'demo':
        # Load testnet credentials from secrets file
        api_key = os.getenv('DEMO_DELTA_API_KEY', '').strip()
        api_secret = os.getenv('DEMO_DELTA_API_SECRET', '').strip()
        
        if not api_key or api_key == 'your_testnet_api_key_here':
            raise ModeConfigurationError(
                "❌ DEMO MODE ERROR: DEMO_DELTA_API_KEY not set in secrets/api_keys.env\n"
                "\n"
                "To get testnet API keys:\n"
                "1. Go to https://testnet.delta.exchange\n"
                "2. Create a new account (separate from live)\n"
                "3. Navigate to: Account Settings → API Management\n"
                "4. Click 'Create New API Key'\n"
                "5. Copy API Key and Secret\n"
                "6. Add to secrets/api_keys.env:\n"
                "   DEMO_DELTA_API_KEY=<your_key>\n"
                "   DEMO_DELTA_API_SECRET=<your_secret>\n"
            )
        
        if not api_secret or api_secret == 'your_testnet_api_secret_here':
            raise ModeConfigurationError(
                "❌ DEMO MODE ERROR: DEMO_DELTA_API_SECRET not set in secrets/api_keys.env"
            )
        
        # Set as current credentials
        os.environ['DELTA_API_KEY'] = api_key
        os.environ['DELTA_API_SECRET'] = api_secret
        
        # Get product ID and symbol from YAML config (not secrets)
        cfg = get_config()
        demo_product_id = str(cfg.api.demo.product_id)
        demo_symbol = os.getenv('DEMO_DELTA_SYMBOL') or os.getenv('LIVE_DELTA_SYMBOL') or 'BTCUSD'
        os.environ['DELTA_PRODUCT_ID'] = demo_product_id
        os.environ['DELTA_SYMBOL'] = demo_symbol
        
        logger.info(f"✅ Loaded DEMO credentials from secrets file (Key: {api_key[:8]}...)")
        logger.info(f"✅ DEMO Product ID: {demo_product_id}, Symbol: {demo_symbol}")
        
    else:  # live mode
        # Load live credentials from secrets file
        api_key = os.getenv('LIVE_DELTA_API_KEY', '').strip()
        api_secret = os.getenv('LIVE_DELTA_API_SECRET', '').strip()
        
        if not api_key:
            raise ModeConfigurationError(
                "❌ LIVE MODE ERROR: LIVE_DELTA_API_KEY not set in secrets/api_keys.env\n"
                "Ensure your live API keys are configured before trading with real money."
            )
        
        if not api_secret:
            raise ModeConfigurationError(
                "❌ LIVE MODE ERROR: LIVE_DELTA_API_SECRET not set in secrets/api_keys.env"
            )
        
        # Set as current credentials
        os.environ['DELTA_API_KEY'] = api_key
        os.environ['DELTA_API_SECRET'] = api_secret
        
        # Get product ID and symbol from YAML config (not secrets)
        cfg = get_config()
        live_product_id = str(cfg.api.live.product_id)
        live_symbol = os.getenv('LIVE_DELTA_SYMBOL') or 'BTCUSD'
        os.environ['DELTA_PRODUCT_ID'] = live_product_id
        os.environ['DELTA_SYMBOL'] = live_symbol
        
        logger.warning(f"🔴 Loaded LIVE credentials from secrets file (Key: {api_key[:8]}...)")
        logger.warning(f"🔴 LIVE Product ID: {live_product_id}, Symbol: {live_symbol}")


def _configure_api_urls(mode: TradingMode) -> None:
    """
    Set DELTA_PUBLIC_BASE_URL, DELTA_PRIVATE_BASE_URL, and DELTA_WEBSOCKET_URL based on trading mode.
    
    Args:
        mode: Trading mode ("demo" or "live")
    """
    
    if mode == 'demo':
        # Testnet URLs from YAML
        cfg = get_config()
        public_url = cfg.api.demo.public_url
        private_url = cfg.api.demo.private_url
        ws_url = cfg.api.demo.websocket_url
        
        os.environ['DELTA_PUBLIC_BASE_URL'] = public_url
        os.environ['DELTA_PRIVATE_BASE_URL'] = private_url
        os.environ['DELTA_BASE_URL'] = public_url  # For CCXT compatibility
        os.environ['DELTA_WEBSOCKET_URL'] = ws_url
        
        logger.info(f"✅ HTTP: {public_url}")
        logger.info(f"✅ WebSocket: {ws_url}")
        
    else:  # live mode
        # Production URLs from YAML
        cfg = get_config()
        public_url = cfg.api.live.public_url
        private_url = cfg.api.live.private_url
        ws_url = cfg.api.live.websocket_url
        
        os.environ['DELTA_PUBLIC_BASE_URL'] = public_url
        os.environ['DELTA_PRIVATE_BASE_URL'] = private_url
        os.environ['DELTA_BASE_URL'] = public_url  # For CCXT compatibility
        os.environ['DELTA_WEBSOCKET_URL'] = ws_url
        
        logger.warning(f"🔴 HTTP: {public_url}")
        logger.warning(f"🔴 WebSocket: {ws_url}")


def get_current_mode() -> TradingMode:
    """
    Get the current trading mode from config.
    
    Returns:
        TradingMode: Either "demo" or "live"
    """
    cfg = get_config()
    return cfg.trading_mode.lower().strip()


def is_demo_mode() -> bool:
    """Check if currently in demo mode"""
    return get_current_mode() == 'demo'


def is_live_mode() -> bool:
    """Check if currently in live mode"""
    return get_current_mode() == 'live'


def get_mode_display_info() -> dict:
    """
    Get formatted display information about current trading mode.
    
    Returns:
        dict: Contains 'mode', 'emoji', 'color', 'description', 'api_url'
    """
    mode = get_current_mode()
    cfg = get_config()
    
    if mode == 'demo':
        return {
            'mode': 'demo',
            'emoji': '🟢',
            'color': 'green',
            'description': 'DEMO MODE - Paper Trading (Testnet)',
            'api_url': cfg.api.demo.public_url,
            'risk_level': 'SAFE - No real money',
            'funds_type': 'Test/Demo funds'
        }
    else:
        return {
            'mode': 'live',
            'emoji': '🔴',
            'color': 'red',
            'description': 'LIVE MODE - REAL MONEY TRADING',
            'api_url': cfg.api.live.public_url,
            'risk_level': '⚠️  HIGH RISK - Real money at stake',
            'funds_type': 'Real account balance'
        }

