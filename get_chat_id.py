#!/usr/bin/env python3
"""
Get your Telegram Chat ID for algo_ssr_bot
"""

import urllib.request
import urllib.parse
import json
import time

def get_chat_id():
    """Get your chat ID by sending a message to the bot"""
    print("🤖 TELEGRAM CHAT ID HELPER")
    print("==========================")
    print("")
    
    bot_token = "8306669384:AAE0sGh1qvWNiMgSev3K92p3i-x0jCTXcLM"
    
    print("📋 INSTRUCTIONS:")
    print("1. Open Telegram and search for @algo_ssr_bot")
    print("2. Send any message to the bot (e.g., 'Hello')")
    print("3. Wait 10 seconds...")
    print("")
    
    input("Press Enter when you've sent a message to @algo_ssr_bot...")
    
    print("🔍 Checking for messages...")
    
    try:
        # Get updates from the bot
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode())
        
        if data.get('ok') and data.get('result'):
            updates = data['result']
            if updates:
                # Get the latest message
                latest = updates[-1]
                if 'message' in latest and 'chat' in latest['message']:
                    chat_id = latest['message']['chat']['id']
                    username = latest['message']['from'].get('username', 'Unknown')
                    first_name = latest['message']['from'].get('first_name', 'Unknown')
                    
                    print(f"✅ Found your chat ID: {chat_id}")
                    print(f"👤 User: {first_name} (@{username})")
                    print("")
                    print("🔧 Now updating configuration files...")
                    
                    # Update configuration files
                    update_config_files(chat_id)
                    
                else:
                    print("❌ No valid message found")
            else:
                print("❌ No messages found. Please send a message to @algo_ssr_bot first")
        else:
            print("❌ Failed to get updates from bot")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def update_config_files(chat_id):
    """Update configuration files with the chat ID"""
    import os
    
    # Update grid_config.env
    try:
        with open('grid_config.env', 'r') as f:
            content = f.read()
        
        content = content.replace('TELEGRAM_CHAT_ID=8170794676', f'TELEGRAM_CHAT_ID={chat_id}')
        content = content.replace('LIVE_TELEGRAM_CHAT_ID=8170794676', f'LIVE_TELEGRAM_CHAT_ID={chat_id}')
        content = content.replace('DEMO_TELEGRAM_CHAT_ID=8170794676', f'DEMO_TELEGRAM_CHAT_ID={chat_id}')
        
        with open('grid_config.env', 'w') as f:
            f.write(content)
        
        print("✅ Updated grid_config.env")
        
    except Exception as e:
        print(f"❌ Error updating grid_config.env: {e}")
    
    # Update secrets/api_keys.env
    try:
        with open('secrets/api_keys.env', 'r') as f:
            content = f.read()
        
        content = content.replace('TELEGRAM_CHAT_ID=8170794676', f'TELEGRAM_CHAT_ID={chat_id}')
        content = content.replace('LIVE_TELEGRAM_CHAT_ID=8170794676', f'LIVE_TELEGRAM_CHAT_ID={chat_id}')
        content = content.replace('DEMO_TELEGRAM_CHAT_ID=8170794676', f'DEMO_TELEGRAM_CHAT_ID={chat_id}')
        
        with open('secrets/api_keys.env', 'w') as f:
            f.write(content)
        
        print("✅ Updated secrets/api_keys.env")
        
    except Exception as e:
        print(f"❌ Error updating secrets/api_keys.env: {e}")
    
    print("")
    print("🧪 Testing configuration...")
    
    # Test the configuration
    try:
        import subprocess
        result = subprocess.run(['python3', 'test_telegram_config.py'], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except Exception as e:
        print(f"❌ Error testing configuration: {e}")

if __name__ == "__main__":
    get_chat_id()
