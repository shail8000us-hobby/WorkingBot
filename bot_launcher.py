#!/usr/bin/env python3
"""
Unified Bot Launcher - THE ONLY WAY TO START THE BOT

This is the single, authoritative way to start the GridBot.
All other methods (WebUI, dashboard scripts, tmux) should call this.

Usage:
    python3 bot_launcher.py [options]
    
Options:
    --daemon        Run in background (returns immediately)
    --foreground    Run in foreground (blocks, shows logs)
    --check-only    Just check if bot can start (don't actually start)

Returns:
    Exit code 0 on success, non-zero on failure
    Writes PID to reports/bot.pid
"""

import sys
import os
import subprocess
from pathlib import Path

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).parent.absolute()
os.chdir(PROJECT_ROOT)

def check_existing_bot():
    """Check if a bot is already running"""
    pid_file = PROJECT_ROOT / "reports" / "bot.pid"
    
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process is still alive
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, OSError, ValueError):
            # Stale PID file
            pid_file.unlink(missing_ok=True)
            return None
    
    return None

def start_bot_daemon():
    """Start bot in background (daemon mode)"""
    # Start bot process
    process = subprocess.Popen(
        [sys.executable, '-m', 'bot.run'],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Detach from parent
    )
    
    # Write PID file
    pid_file = PROJECT_ROOT / "reports" / "bot.pid"
    pid_file.parent.mkdir(exist_ok=True)
    pid_file.write_text(str(process.pid))
    
    print(f"✅ Bot started in background (PID: {process.pid})")
    print(f"📝 PID written to: {pid_file}")
    return process.pid

def start_bot_foreground():
    """Start bot in foreground (blocking, shows output in terminal)"""
    print("🚀 Starting bot in FOREGROUND mode...")
    print("   Logs will appear in this terminal")
    print("   Press Ctrl+C to stop gracefully")
    print("")
    
    # Write PID file first (bot.run will overwrite with correct PID)
    pid_file = PROJECT_ROOT / "reports" / "bot.pid"
    pid_file.parent.mkdir(exist_ok=True)
    pid_file.write_text(str(os.getpid()))  # Temporary, will be overwritten
    
    # Run bot (this blocks and shows output)
    # FIX NOV 14: Handle SIGTERM/SIGINT gracefully to avoid ugly traceback
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'bot.run'],
            cwd=str(PROJECT_ROOT)
        )
        exit_code = result.returncode
    except KeyboardInterrupt:
        # User pressed Ctrl+C or received SIGTERM - this is expected
        print("\n✅ Bot shutdown signal received")
        exit_code = 0
    finally:
        # Clean up PID file on exit
        pid_file.unlink(missing_ok=True)
    
    print(f"\n✅ Bot exited with code {exit_code}")
    return exit_code

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Bot Launcher')
    parser.add_argument('--daemon', action='store_true', help='Run in background')
    parser.add_argument('--foreground', action='store_true', help='Run in foreground (default)')
    parser.add_argument('--check-only', action='store_true', help='Check if bot can start')
    
    args = parser.parse_args()
    
    # Check for existing bot
    existing_pid = check_existing_bot()
    if existing_pid:
        print(f"❌ Bot is already running (PID: {existing_pid})")
        print(f"   Stop it first: ./dashboard/stop.sh")
        print(f"   Or kill it: kill {existing_pid}")
        sys.exit(1)
    
    if args.check_only:
        print("✅ No bot running, can start")
        sys.exit(0)
    
    # Start bot
    if args.daemon:
        start_bot_daemon()
    else:
        # Foreground is default
        exit_code = start_bot_foreground()
        sys.exit(exit_code)

if __name__ == '__main__':
    main()

