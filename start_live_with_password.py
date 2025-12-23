#!/usr/bin/env python3
"""
SAFE START - LIVE TRADING (WITH PASSWORD)
This script prompts for password before starting LIVE (real money) bot
"""

import os
import sys
import subprocess
import getpass

def print_header():
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                          ║")
    print("║          🔐 LIVE TRADING - PASSWORD REQUIRED                             ║")
    print("║                                                                          ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

def print_warning():
    print("⚠️" * 40)
    print("⚠️  WARNING: LIVE TRADING (REAL MONEY)")
    print("⚠️" * 40)
    print()
    print("You are about to start trading with REAL MONEY.")
    print("Please confirm you understand the risks.")
    print()

def main():
    print_header()
    print_warning()
    
    # Confirm intent
    confirm = input("Type 'YES' to confirm you want to trade with REAL MONEY: ").strip()
    
    if confirm != "YES":
        print()
        print("❌ Confirmation failed. Bot will NOT start.")
        print("💡 To trade safely, use demo mode:")
        print("   python3 start_demo_safe.py")
        sys.exit(0)
    
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔐 Enter your LIVE trading password:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Get password (hidden input)
    password = getpass.getpass("Password: ").strip()
    
    if not password:
        print()
        print("❌ No password provided. Bot will NOT start.")
        print("💡 Set password in secrets/api_keys.env:")
        print("   LIVE_TRADING_PASSWORD=your_secure_password")
        sys.exit(1)
    
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 Starting LIVE bot with provided password...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Set environment
    env = os.environ.copy()
    env["TRADING_MODE"] = "live"
    env["LIVE_TRADING_PASSWORD"] = password
    env["HOT_RELOAD"] = "1"
    env["PYTHONPATH"] = os.getcwd()
    
    # Start bot
    try:
        subprocess.Popen(
            [sys.executable, "bot/run.py"],
            stdout=open("bot/logs/bot.log", "a"),
            stderr=subprocess.STDOUT,
            env=env
        )
        print("✅ LIVE bot started successfully!")
        print()
        print("╔══════════════════════════════════════════════════════════════════════════╗")
        print("║                                                                          ║")
        print("║          ⚠️  LIVE TRADING ACTIVE (REAL MONEY)                            ║")
        print("║                                                                          ║")
        print("║  Monitor carefully:                                                      ║")
        print("║  • View logs: tail -f bot/logs/bot.log                                  ║")
        print("║  • Web UI:    http://localhost:5555                                     ║")
        print("║  • Stop bot:  touch .bot_shutdown                                       ║")
        print("║                                                                          ║")
        print("║  All safety features active:                                            ║")
        print("║  ✅ Volatility Safety                                                    ║")
        print("║  ✅ Capital Protection                                                   ║")
        print("║  ✅ Liquidation Guard                                                    ║")
        print("║  ✅ IP Monitoring                                                        ║")
        print("║                                                                          ║")
        print("║  Trade responsibly! 💰                                                   ║")
        print("║                                                                          ║")
        print("╚══════════════════════════════════════════════════════════════════════════╝")
        
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("❌ Cancelled by user")
        sys.exit(0)

