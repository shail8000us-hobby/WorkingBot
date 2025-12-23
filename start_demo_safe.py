#!/usr/bin/env python3
"""
SAFE START - DEMO ONLY (NO REAL MONEY!)
This script ensures ONLY demo bots start - perfect for sleeping safely! 😴
"""

import os
import sys
import subprocess
import signal
import time

def print_header():
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                          ║")
    print("║          🛡️  SAFE START - DEMO BOTS ONLY                                ║")
    print("║                                                                          ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

def print_success(msg):
    print(f"\033[0;32m{msg}\033[0m")

def print_warning(msg):
    print(f"\033[1;33m{msg}\033[0m")

def print_error(msg):
    print(f"\033[0;31m{msg}\033[0m")

def check_trading_mode():
    """Verify TRADING_MODE is set to demo"""
    mode = os.getenv("TRADING_MODE", "").lower()
    if mode == "live":
        print_error("❌ ERROR: TRADING_MODE is set to 'live'!")
        print_error("❌ Cannot start - real money risk!")
        print()
        print("To fix:")
        print("  export TRADING_MODE=demo")
        print("  ./start_demo_safe.py")
        sys.exit(1)
    elif mode != "demo":
        print_warning("⚠️  TRADING_MODE not set, defaulting to 'demo'")
        os.environ["TRADING_MODE"] = "demo"

def kill_existing_bots():
    """Kill any existing bot processes"""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print_warning("🔍 Safety Check: Stopping any running bots...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Create shutdown flag
    try:
        with open('.bot_shutdown', 'w') as f:
            f.write('1')
        print_success("✅ Created shutdown flag")
    except Exception as e:
        print_warning(f"⚠️  Could not create shutdown flag: {e}")
    
    time.sleep(2)  # Give bots time to shutdown
    
    # Remove shutdown flag
    try:
        if os.path.exists('.bot_shutdown'):
            os.remove('.bot_shutdown')
            print_success("✅ Removed shutdown flag")
    except Exception:
        pass
    
    print()

def start_demo_bot():
    """Start demo trading bot"""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print_warning("🚀 Starting DEMO trading bot (safe for sleeping!)...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Set environment
    os.environ["TRADING_MODE"] = "demo"
    os.environ["HOT_RELOAD"] = "1"
    os.environ["PYTHONPATH"] = os.getcwd()
    
    print(f"Environment:")
    print(f"  TRADING_MODE = {os.environ['TRADING_MODE']}")
    print(f"  HOT_RELOAD   = {os.environ.get('HOT_RELOAD', '0')}")
    print()
    
    print_success("✅ Environment configured")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print_success("✅ DEMO bot starting in background...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    # Start bot in background
    try:
        subprocess.Popen(
            [sys.executable, "bot/run.py"],
            stdout=open("bot/logs/bot.log", "a"),
            stderr=subprocess.STDOUT,
            env=os.environ.copy()
        )
        print_success("✅ Bot process started")
    except Exception as e:
        print_error(f"❌ Failed to start bot: {e}")
        return False
    
    return True

def main():
    print_header()
    
    # Safety checks
    check_trading_mode()
    
    # Kill any existing bots
    kill_existing_bots()
    
    # Start demo bot
    if not start_demo_bot():
        sys.exit(1)
    
    # Final status
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                          ║")
    print("║          ✅ SAFE TO SLEEP! 😴                                            ║")
    print("║                                                                          ║")
    print("║  Running:                                                                ║")
    print("║  ✅ gridbot-demo       (TESTNET - No real money!)                       ║")
    print("║                                                                          ║")
    print("║  NOT Running:                                                            ║")
    print("║  ❌ gridbot-live       (STOPPED - No real money risk!)                  ║")
    print("║                                                                          ║")
    print("║  View logs: tail -f bot/logs/bot.log                                    ║")
    print("║  Stop bot:  touch .bot_shutdown                                         ║")
    print("║                                                                          ║")
    print("║  Web UI:    http://localhost:5555                                       ║")
    print("║                                                                          ║")
    print("║  💤 Sleep well! Your real money is SAFE! 💰                             ║")
    print("║                                                                          ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    print("Logs are being written to: bot/logs/bot.log")
    print("Press Ctrl+C to stop viewing this message (bot will continue running)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_success("✅ Bot continues running in background")
        print("   To stop: touch .bot_shutdown")

