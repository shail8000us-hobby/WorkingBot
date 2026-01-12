#!/usr/bin/env python3
"""
Diagnose Options Position Fetching Issues

This script tests the position fetching logic and identifies:
- API connectivity issues
- Authentication problems
- Rate limiting errors
- Missing/incomplete positions
- Timeout issues
"""

import asyncio
import logging
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from bot.api.unified_api_client import UnifiedAPIClient
from bot.api.async_delta_client import AsyncDeltaClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)


async def test_direct_api():
    """Test direct API calls"""
    log.info("=" * 60)
    log.info("TEST 1: Direct API Position Fetch")
    log.info("=" * 60)
    
    try:
        client = AsyncDeltaClient()
        
        # Test 1: Get positions for BTC
        log.info("Fetching positions for BTC underlying...")
        positions = await client.get_positions_for_underlying("BTC")
        
        log.info(f"✅ Fetched {len(positions)} total positions")
        
        # Separate by type
        futures = []
        options = []
        
        for pos in positions:
            symbol = pos.get('product_symbol', '')
            if symbol.startswith('C-') or symbol.startswith('P-'):
                options.append(pos)
            else:
                futures.append(pos)
        
        log.info(f"   - Futures: {len(futures)}")
        log.info(f"   - Options: {len(options)}")
        
        if options:
            log.info("\nOptions Positions:")
            for opt in options:
                symbol = opt.get('product_symbol')
                size = opt.get('size', 0)
                entry_price = opt.get('entry_price', 0)
                mark_price = opt.get('mark_price', 0)
                upnl = opt.get('unrealized_pnl', 0)
                log.info(f"   {symbol}: size={size}, entry=${entry_price}, mark=${mark_price}, upnl=${upnl:.2f}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Direct API test failed: {e}")
        log.exception("Full traceback:")
        return False


async def test_unified_client():
    """Test unified client with enrichment"""
    log.info("\n" + "=" * 60)
    log.info("TEST 2: Unified Client with Ticker Enrichment")
    log.info("=" * 60)
    
    try:
        client = UnifiedAPIClient()
        
        log.info("Fetching positions with options separation...")
        data = await client.get_all_positions_with_options()
        
        futures = data.get('futures', [])
        options = data.get('options', [])
        
        log.info(f"✅ Fetched {len(futures)} futures, {len(options)} options")
        
        if options:
            log.info("\nFetching tickers for options...")
            for opt in options:
                symbol = opt.get('product_symbol')
                try:
                    ticker = await client.get_option_ticker(symbol)
                    iv = ticker.get('implied_volatility', 0)
                    mark = ticker.get('mark_price', 0)
                    delta = ticker.get('delta', 0)
                    log.info(f"   {symbol}: IV={iv:.2f}%, mark=${mark}, delta={delta:.3f}")
                except Exception as e:
                    log.warning(f"   ⚠️  {symbol}: Failed to get ticker - {e}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Unified client test failed: {e}")
        log.exception("Full traceback:")
        return False


async def test_rate_limiting():
    """Test rate limiting behavior"""
    log.info("\n" + "=" * 60)
    log.info("TEST 3: Rate Limiting Check")
    log.info("=" * 60)
    
    try:
        client = AsyncDeltaClient()
        
        log.info("Making 5 rapid requests...")
        for i in range(5):
            try:
                positions = await client.get_positions_for_underlying("BTC")
                log.info(f"   Request {i+1}: ✅ Success ({len(positions)} positions)")
                await asyncio.sleep(0.1)  # Small delay
            except Exception as e:
                log.warning(f"   Request {i+1}: ⚠️ Failed - {e}")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Rate limit test failed: {e}")
        return False


async def test_retry_logic():
    """Test retry and error recovery"""
    log.info("\n" + "=" * 60)
    log.info("TEST 4: Retry Logic and Error Recovery")
    log.info("=" * 60)
    
    try:
        client = AsyncDeltaClient()
        
        # Test with invalid underlying (should fail gracefully)
        log.info("Testing with invalid underlying symbol...")
        try:
            positions = await client.get_positions_for_underlying("INVALID")
            log.info(f"   Result: {len(positions)} positions")
        except Exception as e:
            log.info(f"   ✅ Correctly handled error: {type(e).__name__}")
        
        # Test recovery with valid call
        log.info("Testing recovery with valid call...")
        positions = await client.get_positions_for_underlying("BTC")
        log.info(f"   ✅ Recovered: {len(positions)} positions")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Retry logic test failed: {e}")
        return False


async def main():
    """Run all diagnostic tests"""
    log.info("🔍 Options Position Fetch Diagnostics")
    log.info(f"Started at: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', (), None))}")
    
    results = []
    
    # Run tests
    results.append(("Direct API", await test_direct_api()))
    results.append(("Unified Client", await test_unified_client()))
    results.append(("Rate Limiting", await test_rate_limiting()))
    results.append(("Retry Logic", await test_retry_logic()))
    
    # Summary
    log.info("\n" + "=" * 60)
    log.info("DIAGNOSTIC SUMMARY")
    log.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log.info(f"{status} - {test_name}")
    
    log.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        log.info("\n🎉 All tests passed! Position fetching is working correctly.")
        return 0
    else:
        log.warning(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        log.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log.error(f"\n❌ Fatal error: {e}")
        log.exception("Full traceback:")
        sys.exit(1)
