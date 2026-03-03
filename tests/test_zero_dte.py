#!/usr/bin/env python3
"""Test script for Zero DTE engine"""
import asyncio
import sys
sys.path.insert(0, '.')

from bot.api.unified_api_client import UnifiedAPIClient
from config.loader import get_api_credentials
from bot.strategy.zero_dte.config import load_config
from bot.strategy.zero_dte.engine import ZeroDTEEngine

async def main():
    api_key, api_secret = get_api_credentials()
    client = UnifiedAPIClient(api_key, api_secret, enable_websocket=False)
    config = load_config()

    print(f'Config loaded: {config.strategy.name}')
    print(f'Premium range: {config.entry.premium_range.min} - {config.entry.premium_range.max}')

    engine = ZeroDTEEngine(client, config)

    try:
        result = await engine.start_session(
            underlying='BTC',
            expiry_date='2026-01-15',
            target_premium_min=0.1,
            target_premium_max=100,
            skip_time_check=True
        )
        print(f'Result: {result}')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
