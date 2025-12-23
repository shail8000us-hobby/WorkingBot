#!/usr/bin/env python3
"""
Test script to verify LIVE Telegram bot configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

def test_telegram_bot():
    """Test if the Telegram bot token is valid and can send messages"""
    
    # Get credentials
    bot_token = os.getenv('LIVE_TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('LIVE_TELEGRAM_CHAT_ID')
    
    print("\n" + "="*70)
    print("🤖 TESTING LIVE TELEGRAM BOT CONFIGURATION")
    print("="*70)
    
    if not bot_token:
        print("❌ LIVE_TELEGRAM_BOT_TOKEN not found in environment")
        return False
    
    if not chat_id:
        print("❌ LIVE_TELEGRAM_CHAT_ID not found in environment")
        return False
    
    # Mask token for display
    masked_token = bot_token[:10] + "..." + bot_token[-10:]
    print(f"\n✅ Bot Token: {masked_token}")
    print(f"✅ Chat ID: {chat_id}")
    
    # Test 1: Verify bot token is valid
    print("\n📡 Testing bot token validity...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('ok'):
            bot_info = data.get('result', {})
            print(f"✅ Bot is valid!")
            print(f"   Bot Name: @{bot_info.get('username')}")
            print(f"   Bot ID: {bot_info.get('id')}")
            print(f"   First Name: {bot_info.get('first_name')}")
        else:
            print(f"❌ Bot validation failed: {data}")
            return False
    except Exception as e:
        print(f"❌ Bot validation error: {e}")
        return False
    
    # Test 2: Send a test message
    print("\n📤 Sending test message to Telegram...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        message = (
            "🤖 <b>GridBot Live Trading Test</b>\n\n"
            "✅ Telegram integration is working!\n"
            "🔴 <b>LIVE TRADING MODE</b>\n\n"
            "Bot: @algo_ssr_bot\n"
            "Status: Configured ✅\n\n"
            "This bot will send:\n"
            "• Trade notifications\n"
            "• PnL updates\n"
            "• Error alerts\n"
            "• Position updates\n"
        )
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('ok'):
            print("✅ Test message sent successfully!")
            print(f"   Message ID: {data['result']['message_id']}")
            return True
        else:
            print(f"❌ Failed to send message: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

if __name__ == "__main__":
    success = test_telegram_bot()
    
    print("\n" + "="*70)
    if success:
        print("✅ TELEGRAM CONFIGURATION: WORKING")
        print("="*70)
        print("\n💡 Your bot is ready to send live trading notifications!")
        print("   Check your Telegram app for the test message.\n")
    else:
        print("❌ TELEGRAM CONFIGURATION: FAILED")
        print("="*70)
        print("\n⚠️  Please check:")
        print("   1. Bot token is correct")
        print("   2. Chat ID is correct")
        print("   3. You have started a chat with the bot")
        print("   4. Internet connection is working\n")
