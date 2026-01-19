#!/usr/bin/env python3
"""
Quick script to check available BTC option expiries on Delta Exchange
"""
import asyncio
import os
from datetime import datetime

async def check_available_expiries():
    from bot.api.unified_api_client import UnifiedAPIClient
    
    # Load credentials
    api_key = os.getenv('DELTA_API_KEY')
    api_secret = os.getenv('DELTA_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ No credentials! Set DELTA_API_KEY and DELTA_API_SECRET")
        return
    
    # Create client
    client = UnifiedAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        testnet=False,  # Use LIVE API to see real options
        enable_websocket=False
    )
    
    print("=" * 70)
    print("BTC OPTIONS - AVAILABLE EXPIRY DATES")
    print("=" * 70)
    print()
    
    # Get all products
    products = await client.rest_client.get_products()
    
    # Find BTC call options and extract unique expiries
    expiries = set()
    for product in products:
        if product.get('contract_type') == 'call_options':  # Use contract_type, not product_type
            underlying_asset = product.get('underlying_asset', {})
            if isinstance(underlying_asset, dict):
                symbol = underlying_asset.get('symbol', '')
            else:
                symbol = str(underlying_asset)
            
            if symbol == 'BTC':
                settlement_time = product.get('settlement_time')
                if settlement_time:
                    expiries.add(settlement_time)
    
    # Sort and display
    expiries = sorted(list(expiries))
    
    if not expiries:
        print("❌ No BTC options found!")
        print("   Check if Delta Exchange India has options listed")
        return
    
    print(f"Found {len(expiries)} unique expiry dates:\n")
    
    for i, expiry in enumerate(expiries[:20], 1):  # Show first 20
        # Parse and format
        dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        date_str = dt.strftime('%Y-%m-%d')
        day_name = dt.strftime('%A')
        time_str = dt.strftime('%H:%M IST')
        
        # Calculate DTE
        now = datetime.now(dt.tzinfo)
        days_to_expiry = (dt.date() - now.date()).days
        
        if days_to_expiry == 0:
            dte_label = "0DTE (Today)"
        elif days_to_expiry == 1:
            dte_label = "1DTE (Tomorrow)"
        else:
            dte_label = f"{days_to_expiry}DTE"
        
        print(f"{i:2d}. {date_str} ({day_name}) - {dte_label} - Settlement: {time_str}")
    
    if len(expiries) > 20:
        print(f"\n... and {len(expiries) - 20} more expiries")
    
    print()
    print("=" * 70)
    print("Use one of these dates in your session start request")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(check_available_expiries())
