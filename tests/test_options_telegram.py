#!/usr/bin/env python3
"""
Test script for Options Telegram Notifications
Sends test messages to verify bot configuration

Usage:
    python test_options_telegram.py
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.options.notifications.options_notifier import get_options_notifier
from config.loader import get_config

def main():
    print("=" * 70)
    print("OPTIONS TELEGRAM NOTIFICATION TEST")
    print("=" * 70)
    print()
    
    try:
        # Load config
        cfg = get_config()
        print(f"✅ Config loaded")
        print(f"   Trading Mode: {cfg.trading_mode}")
        print()
        
        # Get options bot credentials
        options_token = cfg.telegram.options_bot_token if hasattr(cfg.telegram, 'options_bot_token') else None
        options_chat = cfg.telegram.options_chat_id if hasattr(cfg.telegram, 'options_chat_id') else None
        
        if not options_token or not options_chat:
            print("❌ Options bot token/chat ID not configured")
            print("   Please add to config.yaml:")
            print("   telegram:")
            print("     options_bot_token: YOUR_TOKEN")
            print("     options_chat_id: YOUR_CHAT_ID")
            return 1
        
        print(f"✅ Options bot configured")
        print(f"   Token: {options_token[:20]}...")
        print(f"   Chat ID: {options_chat}")
        print()
        
        # Initialize notifier
        notifier = get_options_notifier(token=options_token, chat_id=options_chat)
        
        if not notifier.enabled:
            print("❌ Notifier is disabled")
            return 1
        
        print(f"✅ Notifier initialized")
        print(f"   Mode: {notifier.mode_prefix}")
        print()
        
        # Send test messages
        print("📤 Sending test messages...")
        print()
        
        # Test 1: Simple message
        print("1. Simple test message...")
        notifier.send("🧪 TEST: Options Bot is working!")
        print("   ✅ Sent")
        print()
        
        # Test 2: Position opened
        print("2. Position opened notification...")
        test_position = {
            'product_symbol': 'C-BTC-113000-300126',
            'greeks': {
                'delta': 0.65,
                'gamma': 0.001,
                'vega': 12.5,
                'theta': -0.5,
            }
        }
        notifier.notify_position_opened(
            position=test_position,
            fill_price=190.00,
            size=10,
            side='sell',
            order_type='market'
        )
        print("   ✅ Sent")
        print()
        
        # Test 3: Position closed with profit
        print("3. Position closed notification...")
        notifier.notify_position_closed(
            symbol='C-BTC-113000-300126',
            entry_price=190.00,
            exit_price=210.00,
            size=10,
            pnl=200.00,
            pnl_pct=10.53,
            hold_time='6h 23m',
            side='buy',
            order_type='market',
            greeks={'delta': 0.68},
            spot_price=105450
        )
        print("   ✅ Sent")
        print()
        
        # Test 4: Take profit alert
        print("4. Take profit alert...")
        notifier.notify_take_profit(
            symbol='C-BTC-113000-300126',
            target_pct=15.00,
            actual_pct=15.24,
            entry=190.00,
            current=219.00,
            profit=290.00,
            size=10,
            fill_price=219.50,
            final_profit=295.00,
            final_pct=15.53
        )
        print("   ✅ Sent")
        print()
        
        # Test 5: Expiry warning
        print("5. Expiry warning...")
        notifier.notify_expiry_warning(
            symbol='C-BTC-113000-300126',
            hours_remaining=23.75,
            expiry_str='Jan 30, 2026 12:00 UTC',
            size=10,
            pnl=145.00,
            pnl_pct=7.63,
            in_the_money=True,
            intrinsic_value=2450.00
        )
        print("   ✅ Sent")
        print()
        
        # Test 6: Liquidity warning
        print("6. Liquidity warning...")
        notifier.notify_liquidity_warning(
            symbol='C-BTC-118000-300126',
            spread_pct=12.5,
            best_bid=70.00,
            best_ask=80.00,
            mid_price=75.00,
            volume=5,
            size=5,
            entry=85.00,
            current_loss=-50.00,
            loss_pct=-11.76
        )
        print("   ✅ Sent")
        print()
        
        print("=" * 70)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 70)
        print()
        print("Check your Telegram to verify messages arrived.")
        print()
        
        return 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
