#!/usr/bin/env python3
"""
Production Bot Launcher - YAML Configuration
Launches AsyncGridBot with configuration loaded from config.yaml

Usage:
    python3 launch_bot.py

Environment Variables Required:
    DELTA_API_KEY       - Delta Exchange API key
    DELTA_API_SECRET    - Delta Exchange API secret
    TELEGRAM_BOT_TOKEN  - (Optional) Telegram bot token
    TELEGRAM_CHAT_ID    - (Optional) Telegram chat ID

Configuration:
    All bot parameters are loaded from config.yaml
    See config.yaml for full configuration options
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from secrets
secrets_path = project_root / "secrets" / "api_keys.env"
if secrets_path.exists():
    load_dotenv(secrets_path)

from loguru import logger as log
from config.loader import get_config
from bot.strategy.async_gridbot import AsyncGridBot


def main():
    """Launch bot with YAML configuration"""
    log.info("=" * 80)
    log.info("GRIDBOT PRODUCTION LAUNCHER - YAML CONFIG")
    log.info("=" * 80)
    
    try:
        # Load YAML configuration first
        log.info("📖 Loading configuration from config.yaml...")
        config = get_config()
        
        # Determine which API keys to use based on trading mode
        trading_mode = config.trading_mode.lower()
        
        if trading_mode == 'demo':
            api_key = os.getenv('DEMO_DELTA_API_KEY')
            api_secret = os.getenv('DEMO_DELTA_API_SECRET')
            mode_emoji = "🟢"
            mode_desc = "DEMO/TESTNET MODE"
        else:
            api_key = os.getenv('LIVE_DELTA_API_KEY')
            api_secret = os.getenv('LIVE_DELTA_API_SECRET')
            mode_emoji = "🔴"
            mode_desc = "LIVE MODE - REAL MONEY"
        
        # Also set standard DELTA_API_KEY/SECRET for compatibility
        if api_key:
            os.environ['DELTA_API_KEY'] = api_key
        if api_secret:
            os.environ['DELTA_API_SECRET'] = api_secret
        
        if not api_key or not api_secret:
            log.error("❌ Missing API credentials!")
            log.error(f"   Set {trading_mode.upper()}_DELTA_API_KEY and {trading_mode.upper()}_DELTA_API_SECRET environment variables")
            sys.exit(1)
        
        log.info(f"✅ Configuration loaded successfully")
        log.info(f"{mode_emoji} Trading Mode: {mode_desc}")
        log.info(f"   Version: {config.version}")
        log.info(f"   Symbol: {config.bot.symbol}")
        log.info(f"   Mode: {config.bot.mode}")
        log.info("")
        
        # Initialize bot with YAML config
        log.info("🤖 Initializing AsyncGridBot...")
        bot = AsyncGridBot(
            config=config
        )
        
        log.info("✅ Bot initialized")
        log.info("")
        log.info("🚀 Starting bot...")
        log.info("=" * 80)
        
        # Run bot
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        log.info("\n⏹️ Bot stopped by user")
    except Exception as e:
        log.exception(f"❌ Bot failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
