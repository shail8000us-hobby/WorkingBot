#!/usr/bin/env python3
"""
Setup Telegram notifications for price alerts
"""
import asyncio
import aiohttp
from datetime import datetime
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webui', 'backend'))

async def test_telegram():
    token = '8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0'
    chat_id = '8170794676'
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    
    now = datetime.now().strftime('%d %b %Y, %H:%M:%S')
    message = f"""🔔 *WorkingBot Alert System Activated!*

✅ Your Telegram notifications are now configured!

You will receive price alerts here when BTC hits your target prices on the payoff graph.

📊 *How to create alerts:*
Just click anywhere on the payoff graph to set an alert at that price level.

Time: {now}"""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }) as response:
            data = await response.json()
            if data.get('ok'):
                print('✅ Test message sent successfully!')
                return True
            else:
                print(f'❌ Failed: {data}')
                return False

def setup_db():
    """Save credentials to alerts database"""
    try:
        from db.alerts_db import AlertsDB
        AlertsDB.update_settings(
            telegram_bot_token='8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0',
            telegram_chat_id='8170794676',
            enabled_channels='telegram,in_app'
        )
        print('✅ Credentials saved to database!')
        return True
    except Exception as e:
        print(f'❌ Failed to save to DB: {e}')
        return False

if __name__ == '__main__':
    print('Setting up Telegram notifications...')
    
    # Test Telegram
    success = asyncio.run(test_telegram())
    
    if success:
        # Save to DB
        setup_db()
        print('\n✅ Setup complete! You should have received a Telegram message.')
    else:
        print('\n❌ Setup failed. Check your bot token.')
