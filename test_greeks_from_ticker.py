#!/usr/bin/env python3
"""
Test fetching Greeks from Delta Exchange ticker endpoint
Greeks are available in /tickers/{symbol} endpoint, not in positions endpoint
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bot.api.delta_client import DeltaClient

def get_open_positions():
    """Fetch all open positions"""
    client = DeltaClient()
    response = client._req('GET', '/v2/positions/margined')
    
    if response.get('success'):
        positions = response.get('result', [])
        return [p for p in positions if int(p.get('size', 0)) != 0]
    return []

def get_ticker_with_greeks(symbol):
    """Fetch ticker data including Greeks for a specific symbol"""
    client = DeltaClient()
    try:
        response = client._req('GET', f'/v2/tickers/{symbol}')
        if response.get('success'):
            return response.get('result')
    except Exception as e:
        print(f"Error fetching ticker for {symbol}: {e}")
    return None

def fetch_greeks_for_positions():
    """Fetch Greeks for all open positions"""
    print("=" * 80)
    print("FETCHING GREEKS FOR OPEN POSITIONS")
    print("=" * 80)
    
    positions = get_open_positions()
    
    if not positions:
        print("No open positions found")
        return []
    
    print(f"\nFound {len(positions)} open position(s)\n")
    
    positions_with_greeks = []
    
    for i, position in enumerate(positions, 1):
        product_symbol = position.get('product_symbol')
        product_id = position.get('product_id')
        size = int(position.get('size', 0))
        entry_price = float(position.get('entry_price', 0))
        mark_price = float(position.get('mark_price', 0))
        
        print(f"\n{'='*80}")
        print(f"POSITION {i}: {product_symbol}")
        print(f"{'='*80}")
        print(f"Product ID: {product_id}")
        print(f"Size: {size} ({'long' if size > 0 else 'short'})")
        print(f"Entry Price: ${entry_price:,.2f}")
        print(f"Mark Price: ${mark_price:,.2f}")
        
        # Determine if it's an option
        is_option = any(x in product_symbol for x in ['C-', 'P-'])
        contract_type = "OPTION" if is_option else "FUTURE"
        print(f"Type: {contract_type}")
        
        # Fetch ticker data for Greeks
        print(f"\nFetching ticker data for {product_symbol}...")
        ticker_data = get_ticker_with_greeks(product_symbol)
        
        if ticker_data:
            print("✅ Ticker data received")
            
            # Extract Greeks
            greeks = ticker_data.get('greeks', {})
            
            if greeks and is_option:
                print("\n📊 GREEKS (per contract):")
                delta = float(greeks.get('delta', 0))
                vega = float(greeks.get('vega', 0))
                theta = float(greeks.get('theta', 0))
                gamma = float(greeks.get('gamma', 0))
                rho = float(greeks.get('rho', 0))
                
                print(f"   Delta: {delta:.6f}")
                print(f"   Vega:  {vega:.6f}")
                print(f"   Theta: {theta:.6f}")
                print(f"   Gamma: {gamma:.6f}")
                print(f"   Rho:   {rho:.6f}")
                
                # Calculate position Greeks (Greeks × Size)
                pos_delta = delta * size
                pos_vega = vega * abs(size)
                pos_theta = theta * abs(size)
                pos_gamma = gamma * abs(size)
                
                print(f"\n📈 POSITION GREEKS (Greeks × Size):")
                print(f"   Position Delta: {pos_delta:.4f}")
                print(f"   Position Vega:  {pos_vega:.4f}")
                print(f"   Position Theta: {pos_theta:.4f}")
                print(f"   Position Gamma: {pos_gamma:.4f}")
                
                positions_with_greeks.append({
                    'symbol': product_symbol,
                    'product_id': product_id,
                    'size': size,
                    'entry_price': entry_price,
                    'mark_price': mark_price,
                    'type': contract_type,
                    'greeks': {
                        'delta': delta,
                        'vega': vega,
                        'theta': theta,
                        'gamma': gamma,
                        'rho': rho
                    },
                    'position_greeks': {
                        'delta': pos_delta,
                        'vega': pos_vega,
                        'theta': pos_theta,
                        'gamma': pos_gamma
                    }
                })
            elif not is_option:
                print("\nℹ️  Greeks not applicable (FUTURE contract)")
            else:
                print("\n⚠️  Greeks data not available in ticker response")
                print(f"Available keys: {list(ticker_data.keys())}")
        else:
            print("❌ Could not fetch ticker data")
    
    return positions_with_greeks

def get_portfolio_greeks_summary(positions_with_greeks):
    """Calculate total portfolio Greeks"""
    if not positions_with_greeks:
        print("\n⚠️  No option positions with Greeks data")
        return
    
    print("\n" + "=" * 80)
    print("PORTFOLIO GREEKS SUMMARY")
    print("=" * 80)
    
    total_delta = sum(p['position_greeks']['delta'] for p in positions_with_greeks)
    total_vega = sum(p['position_greeks']['vega'] for p in positions_with_greeks)
    total_theta = sum(p['position_greeks']['theta'] for p in positions_with_greeks)
    total_gamma = sum(p['position_greeks']['gamma'] for p in positions_with_greeks)
    
    print(f"\nTotal Option Positions: {len(positions_with_greeks)}")
    print(f"\n📊 PORTFOLIO GREEKS:")
    print(f"   Portfolio Delta: {total_delta:.4f}")
    print(f"   Portfolio Vega:  {total_vega:.4f}")
    print(f"   Portfolio Theta: {total_theta:.4f}")
    print(f"   Portfolio Gamma: {total_gamma:.4f}")
    
    print(f"\n💡 RISK INTERPRETATION:")
    if total_delta > 0:
        print(f"   Delta: Bullish exposure (+{total_delta:.2f})")
    elif total_delta < 0:
        print(f"   Delta: Bearish exposure ({total_delta:.2f})")
    else:
        print(f"   Delta: Neutral exposure")
    
    if abs(total_vega) > 100:
        print(f"   Vega: HIGH volatility sensitivity ({total_vega:.2f})")
    elif abs(total_vega) > 50:
        print(f"   Vega: Moderate volatility sensitivity ({total_vega:.2f})")
    else:
        print(f"   Vega: Low volatility sensitivity ({total_vega:.2f})")
    
    print(f"   Theta: ${total_theta:.2f} daily time decay")

if __name__ == "__main__":
    try:
        # Fetch Greeks for individual positions
        positions_with_greeks = fetch_greeks_for_positions()
        
        # Get portfolio-level Greeks summary
        get_portfolio_greeks_summary(positions_with_greeks)
        
        print("\n" + "=" * 80)
        print("✅ Test Complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
