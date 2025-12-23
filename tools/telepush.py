#!/usr/bin/env python3
import os, sys, requests
from dotenv import load_dotenv
load_dotenv('.env.reports')
TOKEN=os.getenv('TELEGRAM_BOT_TOKEN'); CHAT_ID=os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_alert(message, urgent=False):
    """Send a Telegram alert message"""
    if not TOKEN or not CHAT_ID:
        print('Warning: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID - skipping Telegram alert')
        return False
    
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': message, 'disable_web_page_preview': True},
            timeout=10
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f'Warning: Failed to send Telegram alert: {e}')
        return False

# CLI usage
if __name__ == '__main__':
    if not TOKEN or not CHAT_ID:
        print('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID')
        sys.exit(1)
    msg = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else '(empty)'
    success = send_telegram_alert(msg)
    print('ok' if success else 'failed')
    sys.exit(0 if success else 1)
