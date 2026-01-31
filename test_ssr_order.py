#!/usr/bin/env python3
"""Test SSR Order Placement"""
import asyncio
import sys
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

from webui.backend.routes.mv_straddle_routes import get_mv_straddle_handler

def test_ssr_order():
    handler = get_mv_straddle_handler()
    symbol = 'MV-BTC-83800-310126'
    
    # Get ticker
    ticker = handler.get_ticker(symbol)
    print(f"Ticker: {ticker is not None}")
    
    quotes = ticker.get('quotes', {})
    best_bid = float(quotes.get('best_bid') or ticker.get('best_bid') or 0)
    best_ask = float(quotes.get('best_ask') or ticker.get('best_ask') or 0)
    mark_price = float(ticker.get('mark_price') or 0)
    
    print(f"Best Bid: {best_bid}, Best Ask: {best_ask}, Mark: {mark_price}")
    
    # Get product
    product = handler.get_mv_straddle_by_symbol(symbol)
    tick_size = float(product.get('tick_size', '0.1')) if product else 0.1
    print(f"Tick size: {tick_size}")
    
    # Calculate SSR price (standard mode for sell)
    reference_price = best_ask if best_ask > 0 else mark_price
    ssr_price = reference_price + (2 * tick_size)
    ssr_price = round(ssr_price / tick_size) * tick_size
    print(f"SSR Price: {ssr_price}")
    
    # Try to place order
    try:
        result = asyncio.run(handler.place_order(
            symbol=symbol,
            side='sell',
            size=1,
            order_type='limit_order',
            limit_price=ssr_price
        ))
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ssr_order()
