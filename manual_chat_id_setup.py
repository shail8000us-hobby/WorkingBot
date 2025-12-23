#!/usr/bin/env python3
"""
Manual Chat ID Setup for algo_ssr_bot
"""

def manual_setup():
    print("🤖 MANUAL TELEGRAM CHAT ID SETUP")
    print("=================================")
    print("")
    print("📋 STEP 1: Get your Chat ID")
    print("1. Open Telegram")
    print("2. Search for @userinfobot")
    print("3. Send any message to @userinfobot")
    print("4. Copy your chat ID (it will be a number like 123456789)")
    print("")
    
    chat_id = input("📝 Enter your chat ID: ").strip()
    
    if not chat_id.isdigit():
        print("❌ Error: Chat ID must be a number")
        return False
    
    print(f"✅ Chat ID: {chat_id}")
    print("")
    print("🔧 Updating configuration files...")
    
    # Update configuration files
    update_config_files(chat_id)
    
    return True

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
    manual_setup()
