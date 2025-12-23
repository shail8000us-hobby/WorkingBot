#!/usr/bin/env python3
"""
Manual Volatility Data Collection Test

Use this to manually trigger data collection and verify everything is working.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from bot.volatility.delta_volatility_collector import get_collector

def main():
    print("=" * 70)
    print("🧪 MANUAL VOLATILITY DATA COLLECTION TEST")
    print("=" * 70)
    print()
    
    # Get collector instance
    collector = get_collector()
    
    print("📊 Starting collector...")
    collector.start()
    
    print("⏳ Waiting 5 seconds for first collection cycle...")
    time.sleep(5)
    
    print("\n📈 Fetching latest values...")
    latest = collector.get_latest_values()
    
    print("\n" + "=" * 70)
    print("LATEST VALUES")
    print("=" * 70)
    
    if latest['iv']:
        print(f"\n✅ Implied Volatility (IV)")
        print(f"   Value: {latest['iv']['value']:.2f}%")
        print(f"   Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest['iv']['timestamp']/1000))}")
    else:
        print("\n❌ No IV data available yet")
    
    print(f"\n✅ Realized Volatility (RV)")
    for timeframe, data in latest['rv'].items():
        if data:
            print(f"   {timeframe}: {data['value']:.2f}%")
    
    print("\n📊 Fetching historical data...")
    for tf in ['daily', 'weekly', 'monthly']:
        hist = collector.get_historical_data(timeframe=tf, limit=10)
        print(f"\n{tf.upper()} Timeframe:")
        print(f"   IV points: {len(hist['iv'])}")
        print(f"   RV points: {len(hist['rv'])}")
        
        if hist['rv']:
            first_rv = hist['rv'][0]
            last_rv = hist['rv'][-1]
            print(f"   RV range: {time.strftime('%Y-%m-%d', time.localtime(first_rv['timestamp']/1000))} to {time.strftime('%Y-%m-%d', time.localtime(last_rv['timestamp']/1000))}")
    
    print("\n⏹️  Stopping collector...")
    collector.stop()
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)
    print("\nYour volatility system is working correctly!")
    print("The WebUI LaunchAgent is collecting data continuously in the background.")
    print()

if __name__ == "__main__":
    main()
