import asyncio
import sys
sys.path.append('/Users/ssr/Projects/WorkingBot')
from bot.api.async_delta_client import AsyncDeltaClient

async def check_exchange():
    from config.loader import get_api_credentials
    creds = get_api_credentials()
    
    client = AsyncDeltaClient(
        api_key=creds.get('api_key', ''),
        api_secret=creds.get('api_secret', ''),
        testnet=creds.get('testnet', False)
    )
    
    print("=== OPEN ORDERS ===")
    orders = await client.get_open_orders()
    for order in orders:
        print(f"Order ID: {order.get('id')}")
        print(f"  Symbol: {order.get('product', {}).get('symbol', 'N/A')}")
        print(f"  Side: {order.get('side')}")
        print(f"  Size: {order.get('size')} ({order.get('unfilled_size')} unfilled)")
        print(f"  Price: ${order.get('limit_price', order.get('price'))}")
        print(f"  State: {order.get('state', order.get('status'))}")
        print()
    
    print("\n=== POSITIONS ===")
    positions = await client.get_positions_for_underlying('BTC')
    for pos in positions:
        symbol = pos.get('product', {}).get('symbol', 'N/A')
        if '-160226' in symbol:  # Today's expiry
            size = pos.get('size', 0)
            entry = pos.get('entry_price', 'N/A')
            print(f"{symbol}: {size} lots @ entry avg ${entry}")

asyncio.run(check_exchange())
