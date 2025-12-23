#!/usr/bin/env python3
"""
Bot Entry Point - bot.run module

This module is the entry point called by bot_launcher.py
It initializes and starts the AsyncGridBot.

Usage:
    python3 -m bot.run
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.strategy.async_gridbot import AsyncGridBot, log
from config.loader import get_config, get_api_credentials


async def main():
    """Main entry point for bot execution."""
    try:
        # Get configuration from YAML
        config = get_config()
        
        # Get API credentials from secrets/api_keys.env
        credentials = get_api_credentials(config.trading_mode)
        api_key = credentials['api_key']
        api_secret = credentials['api_secret']
        
        # Get mode and testnet from YAML config
        mode = config.bot.mode
        testnet = (config.trading_mode == 'demo')
        
        log.info("=" * 80)
        log.info("🤖 Starting AsyncGridBot")
        log.info(f"   Mode: {mode}")
        log.info(f"   Trading Mode: {config.trading_mode}")
        log.info(f"   Testnet: {testnet}")
        log.info("=" * 80)
        
        # Create bot instance
        bot = AsyncGridBot(
            api_key=api_key,
            api_secret=api_secret,
            mode=mode,
            testnet=testnet
        )
        
        # Start bot (this blocks until bot stops)
        await bot.start()
        
    except KeyboardInterrupt:
        log.info("\n🛑 Keyboard interrupt received - shutting down gracefully")
    except Exception as e:
        log.error(f"❌ Fatal error in bot execution: {e}")
        import traceback
        log.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Ensure bot stops cleanly
        try:
            if 'bot' in locals():
                await bot.stop()
                log.info("✅ Bot stopped cleanly")
        except Exception as e:
            log.error(f"Error during bot shutdown: {e}")


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Bot shutdown complete")
        sys.exit(0)
