#!/usr/bin/env python3
"""
Bot Entry Point - bot.run module

V6.0 MULTI-INSTANCE ARCHITECTURE: Instance = Symbol + Mode

This module is the entry point called by bot_launcher.py
It initializes and starts the AsyncGridBot for a specific instance.

Usage:
    # V6.0: Instance mode (recommended)
    python3 -m bot.run --instance BTCUSD_LONG    # Run BTCUSD LONG instance
    python3 -m bot.run --instance BTCUSD_SHORT   # Run BTCUSD SHORT instance
    python3 -m bot.run -i ETHUSD_LONG            # Run ETHUSD LONG instance
    
    # Legacy: Symbol mode (uses mode from config)
    python3 -m bot.run --symbol BTCUSD           # Uses mode from symbols.BTCUSD.mode
    
    # V6.0 enables running LONG and SHORT on same symbol simultaneously:
    # Terminal 1: python3 -m bot.run --instance BTCUSD_LONG
    # Terminal 2: python3 -m bot.run --instance BTCUSD_SHORT
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.strategy.async_gridbot import AsyncGridBot, log
from config.loader import (
    get_config, get_api_credentials, get_instance_config, 
    get_all_instances, make_instance_name
)


def parse_args():
    """Parse command-line arguments for v6.0 multi-instance support."""
    parser = argparse.ArgumentParser(
        description='GridBot Trading Bot - Multi-Instance Support (v6.0)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
V6.0 Instance-Centric Architecture:
  Instance = Symbol + Mode (e.g., BTCUSD_LONG, BTCUSD_SHORT)
  
  This enables running LONG and SHORT on the same symbol simultaneously!

Examples:
  python3 -m bot.run --instance BTCUSD_LONG    Run BTCUSD LONG instance
  python3 -m bot.run --instance BTCUSD_SHORT   Run BTCUSD SHORT instance
  python3 -m bot.run -i ETHUSD_LONG            Short form
  
Legacy (v5.0 compatibility):
  python3 -m bot.run --symbol BTCUSD           Uses mode from config

Note: Each instance runs as a separate process with its own database.
      BTCUSD_LONG uses: data/bot_events_BTCUSD_LONG.db
      BTCUSD_SHORT uses: data/bot_events_BTCUSD_SHORT.db
        """
    )
    parser.add_argument(
        '--instance', '-i',
        type=str,
        default=None,
        metavar='INSTANCE',
        help='Instance to run (e.g., BTCUSD_LONG, BTCUSD_SHORT). Format: SYMBOL_MODE'
    )
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default=None,
        metavar='SYMBOL',
        help='[LEGACY] Symbol to trade. Uses mode from config. Prefer --instance for v6.0.'
    )
    return parser.parse_args()


async def main(instance_name: str = None, symbol_name: str = None):
    """Main entry point for bot execution.
    
    V6.0 ARCHITECTURE: Prefers instance_name over symbol_name.
    
    Args:
        instance_name: Instance to run (e.g., "BTCUSD_LONG"). Takes priority.
        symbol_name: [Legacy] Symbol to trade. Mode comes from config.
    """
    try:
        # Get configuration from YAML
        config = get_config()
        
        # Get API credentials from secrets/api_keys.env
        credentials = get_api_credentials(config.trading_mode)
        api_key = credentials['api_key']
        api_secret = credentials['api_secret']
        testnet = (config.trading_mode == 'demo')
        
        # V6.0: Resolve instance configuration
        if instance_name:
            # Direct instance mode (preferred)
            instance_config = get_instance_config(instance_name)
            if not instance_config:
                log.error(f"❌ Instance '{instance_name}' not found or disabled in config.yaml")
                log.error(f"   Available instances: {list(get_all_instances(enabled_only=False).keys())}")
                sys.exit(1)
            mode = instance_config.mode.value
            resolved_symbol = instance_config.symbol
            resolved_instance = instance_name
        elif symbol_name:
            # V5.0 legacy: Get mode from symbols config
            if config.symbols and symbol_name in config.symbols:
                symbol_config = config.symbols[symbol_name]
                mode = symbol_config.mode.value
                resolved_symbol = symbol_name
                resolved_instance = make_instance_name(symbol_name, mode)
                log.warning(f"⚠️  Legacy mode: --symbol is deprecated. Use --instance {resolved_instance}")
            elif config.instances:
                # Try to find first matching instance for this symbol
                for name, inst in config.instances.items():
                    if inst.symbol == symbol_name and inst.enabled:
                        mode = inst.mode.value
                        resolved_symbol = symbol_name
                        resolved_instance = name
                        log.warning(f"⚠️  Legacy mode: Using instance {resolved_instance} for symbol {symbol_name}")
                        break
                else:
                    log.error(f"❌ No enabled instance found for symbol '{symbol_name}'")
                    sys.exit(1)
            else:
                log.error(f"❌ Symbol '{symbol_name}' not found in config")
                sys.exit(1)
        else:
            # No instance or symbol specified - find first enabled instance
            enabled = get_all_instances(enabled_only=True)
            if enabled:
                resolved_instance = list(enabled.keys())[0]
                instance_config = enabled[resolved_instance]
                mode = instance_config.mode.value
                resolved_symbol = instance_config.symbol
                log.info(f"📌 No instance specified, using first enabled: {resolved_instance}")
            elif config.bot:
                # Fallback to legacy single-symbol mode
                mode = config.bot.mode
                resolved_symbol = config.bot.symbol
                resolved_instance = make_instance_name(resolved_symbol, mode)
                log.warning(f"⚠️  Using legacy config.bot settings: {resolved_instance}")
            else:
                log.error("❌ No enabled instances found and no legacy config.bot settings")
                sys.exit(1)
        
        log.info("=" * 80)
        log.info("🤖 Starting AsyncGridBot (v6.0 Multi-Instance)")
        log.info(f"   Instance: {resolved_instance}")
        log.info(f"   Symbol: {resolved_symbol}")
        log.info(f"   Mode: {mode}")
        log.info(f"   Trading Mode: {config.trading_mode}")
        log.info(f"   Testnet: {testnet}")
        log.info("=" * 80)
        
        # Create bot instance with v6.0 instance_name
        bot = AsyncGridBot(
            api_key=api_key,
            api_secret=api_secret,
            mode=mode,
            testnet=testnet,
            symbol_name=resolved_symbol,       # Symbol for API calls
            instance_name=resolved_instance    # V6.0: Instance for database/logs
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
    # Parse command-line arguments
    args = parse_args()
    
    # Run the async main function with v6.0 instance or legacy symbol
    try:
        asyncio.run(main(instance_name=args.instance, symbol_name=args.symbol))
    except KeyboardInterrupt:
        print("\n✅ Bot shutdown complete")
        sys.exit(0)
