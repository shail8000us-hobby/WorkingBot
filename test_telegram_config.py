#!/usr/bin/env python3
"""
Test Telegram Configuration for algo_ssr_bot
"""

import os
import sys
from dotenv import load_dotenv

def test_telegram_config():
    """Test the current Telegram configuration"""
    print("🤖 TELEGRAM CONFIGURATION TEST")
    print("===============================")
    print("")
    
    # Load environment variables
    load_dotenv('grid_config.env')
    load_dotenv('secrets/api_keys.env')
    
    # Check trading mode
    trading_mode = os.getenv('TRADING_MODE', 'demo').lower().strip()
    print(f"📊 Trading Mode: {trading_mode.upper()}")
    print("")
    
    # Check credentials based on mode
    if trading_mode == 'live':
        token = os.getenv('LIVE_TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('LIVE_TELEGRAM_CHAT_ID')
        print("🔴 LIVE MODE - Using LIVE_TELEGRAM_* credentials")
    else:
        token = os.getenv('DEMO_TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('DEMO_TELEGRAM_CHAT_ID')
        print("🟢 DEMO MODE - Using DEMO_TELEGRAM_* credentials")
    
    print("")
    
    # Check if credentials are set
    if not token or token == 'YOUR_ALGO_SSR_BOT_TOKEN_HERE':
        print("❌ Bot token not configured")
        print("   Run: ./setup_telegram_algo_ssr_bot.sh")
        return False
    else:
        print(f"✅ Bot token: {token[:10]}...")
    
    if not chat_id or chat_id == '8170794676':
        print("❌ Chat ID not configured")
        print("   Run: ./setup_telegram_algo_ssr_bot.sh")
        return False
    else:
        print(f"✅ Chat ID: {chat_id}")
    
    print("")
    
    # Test sending a message
    print("🧪 Testing Telegram connection...")
    try:
        import urllib.request
        import urllib.parse
        import json
        
        message = f'🤖 GridBot Pro - {trading_mode.upper()} mode test message'
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        req = urllib.request.Request(url, urllib.parse.urlencode(data).encode())
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        
        if result.get('ok'):
            print("✅ Test message sent successfully!")
            print("📱 Check your Telegram for the test message")
            return True
        else:
            print(f"❌ Failed to send test message: {result.get('description', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Telegram: {e}")
        return False

if __name__ == "__main__":
    success = test_telegram_config()
    sys.exit(0 if success else 1)
