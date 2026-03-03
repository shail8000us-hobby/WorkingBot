#!/bin/bash
# ============================================================================
# TELEGRAM BOT SETUP SCRIPT - algo_ssr_bot
# ============================================================================
#
# This script helps you configure the algo_ssr_bot Telegram credentials
# for your GridBot Pro trading system.
#
# ============================================================================

echo "🤖 TELEGRAM BOT SETUP - algo_ssr_bot"
echo "======================================"
echo ""

# Check if we're in the right directory
if [ ! -f "grid_config.env" ]; then
    echo "❌ Error: Please run this script from the WorkingBot directory"
    exit 1
fi

echo "📋 STEP 1: Get your Telegram bot token"
echo "--------------------------------------"
echo "1. Open Telegram and search for @BotFather"
echo "2. Send /newbot command"
echo "3. Choose a name for your bot (e.g., 'My GridBot Pro')"
echo "4. Choose a username ending in 'bot' (e.g., 'algo_ssr_bot')"
echo "5. Copy the bot token (format: 123456:ABC-DEF1234ghIkl...)"
echo ""

read -p "📝 Enter your bot token: " BOT_TOKEN

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Error: Bot token cannot be empty"
    exit 1
fi

echo ""
echo "📋 STEP 2: Get your chat ID"
echo "---------------------------"
echo "1. Open Telegram and search for @userinfobot"
echo "2. Send any message to @userinfobot"
echo "3. Copy your chat ID (format: 123456789)"
echo ""

read -p "📝 Enter your chat ID: " CHAT_ID

if [ -z "$CHAT_ID" ]; then
    echo "❌ Error: Chat ID cannot be empty"
    exit 1
fi

echo ""
echo "🔧 STEP 3: Updating configuration files"
echo "---------------------------------------"

# Update grid_config.env
echo "📝 Updating grid_config.env..."
sed -i.bak "s/YOUR_ALGO_SSR_BOT_TOKEN_HERE/$BOT_TOKEN/g" grid_config.env
sed -i.bak "s/8170794676/$CHAT_ID/g" grid_config.env

# Update secrets/api_keys.env
echo "📝 Updating secrets/api_keys.env..."
sed -i.bak "s/YOUR_ALGO_SSR_BOT_TOKEN_HERE/$BOT_TOKEN/g" secrets/api_keys.env
sed -i.bak "s/8170794676/$CHAT_ID/g" secrets/api_keys.env

echo "✅ Configuration files updated!"
echo ""

echo "🧪 STEP 4: Testing Telegram connection"
echo "-------------------------------------"

# Test the Telegram connection
python3 -c "
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('grid_config.env')
load_dotenv('secrets/api_keys.env')

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if not token or token == 'YOUR_ALGO_SSR_BOT_TOKEN_HERE':
    print('❌ Error: Bot token not configured properly')
    sys.exit(1)

if not chat_id or chat_id == '8170794676':
    print('❌ Error: Chat ID not configured properly')
    sys.exit(1)

print(f'✅ Bot token: {token[:10]}...')
print(f'✅ Chat ID: {chat_id}')

# Test sending a message
try:
    import urllib.request
    import urllib.parse
    import json
    
    message = '🤖 GridBot Pro - Telegram setup successful!'
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
        print('✅ Test message sent successfully!')
        print('📱 Check your Telegram for the test message')
    else:
        print(f'❌ Failed to send test message: {result.get(\"description\", \"Unknown error\")}')
        
except Exception as e:
    print(f'❌ Error testing Telegram: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 TELEGRAM SETUP COMPLETE!"
    echo "=========================="
    echo ""
    echo "✅ Bot token configured"
    echo "✅ Chat ID configured"
    echo "✅ Test message sent"
    echo ""
    echo "📱 Your GridBot Pro will now send notifications to Telegram!"
    echo "🔄 Restart the bot to apply the new configuration"
    echo ""
    echo "🚀 Next steps:"
    echo "1. Restart the bot: python3 bot/run.py"
    echo "2. Check Telegram for bot notifications"
    echo "3. Monitor the bot status in WebUI"
else
    echo ""
    echo "❌ TELEGRAM SETUP FAILED"
    echo "========================"
    echo ""
    echo "Please check:"
    echo "1. Bot token is correct"
    echo "2. Chat ID is correct"
    echo "3. Bot is started (message @BotFather: /start)"
    echo "4. Internet connection is working"
    echo ""
    echo "Run this script again to retry"
fi

echo ""
echo "📚 For more help, check the documentation or contact support"
