import asyncio
import os
import sys

# Add the project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.api.unified_api_client import get_unified_client

async def main():
    client = get_unified_client()
    try:
        # fetch options positions
        positions_response = await client.get_all_positions_with_options()
        options = positions_response.get('options', [])
        print(f"Found {len(options)} option positions")
        
        for pos in options[:2]:
            symbol = pos.get('product_symbol')
            size = pos.get('size')
            print(f"\n--- {symbol} ---")
            print(f"Size in contracts: {size}")
            
            ticker = await client.get_ticker(symbol)
            greeks = ticker.get('greeks', {})
            print(f"Raw API Greeks for {symbol}:")
            print(greeks)
            
            if greeks:
                delta = float(greeks.get('delta', 0))
                # compute how web ui does it:
                lot_mult = 0.001
                calc_delta = delta * size * lot_mult
                print(f"Web UI Calculated Delta: {calc_delta}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
