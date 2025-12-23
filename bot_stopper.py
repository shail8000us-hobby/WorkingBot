#!/usr/bin/env python3
"""
Unified Bot Stopper - THE ONLY WAY TO STOP THE BOT

This is the single, authoritative way to stop the GridBot.
All other methods (WebUI, dashboard scripts) should call this.

Usage:
    python3 bot_stopper.py [options]
    
Options:
    --graceful      Graceful stop with 30s cleanup (default)
    --force         Force kill (immediate)
    --check-only    Just check if bot is running

Returns:
    Exit code 0 on success, 1 if bot not running, 2 on error
"""

import sys
import os
import signal
import time
from pathlib import Path

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).parent.absolute()
os.chdir(PROJECT_ROOT)

def get_bot_pid():
    """Get bot PID from PID file"""
    pid_file = PROJECT_ROOT / "reports" / "bot.pid"
    
    if not pid_file.exists():
        return None
    
    try:
        pid = int(pid_file.read_text().strip())
        # Verify process is still running
        os.kill(pid, 0)
        return pid
    except (ProcessLookupError, OSError, ValueError):
        # Stale PID file
        pid_file.unlink(missing_ok=True)
        return None

def stop_bot_graceful(pid):
    """Graceful stop - sends SIGINT, waits 30 seconds"""
    print(f"🛑 Stopping bot gracefully (PID: {pid})...")
    print("   Sending SIGINT (Ctrl+C)...")
    
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        print("   Bot already stopped")
        return True
    
    # Wait up to 30 seconds for graceful shutdown
    print("   Waiting for graceful shutdown (max 30 seconds)...")
    for i in range(30):
        try:
            os.kill(pid, 0)  # Check if still alive
            time.sleep(1)
            if (i + 1) % 5 == 0:
                print(f"   Still waiting... ({i + 1}/30 seconds)")
        except ProcessLookupError:
            print(f"✅ Bot stopped gracefully ({i + 1} seconds)")
            return True
    
    # Still running after 30 seconds
    print("⚠️  Bot did not stop within 30 seconds")
    return False

def stop_bot_force(pid):
    """Force kill - sends SIGKILL immediately"""
    print(f"⚡ Force killing bot (PID: {pid})...")
    
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        
        # Verify it's dead
        try:
            os.kill(pid, 0)
            print("❌ Force kill failed - process still alive")
            return False
        except ProcessLookupError:
            print("✅ Bot force killed successfully")
            return True
            
    except ProcessLookupError:
        print("   Bot already stopped")
        return True
    except Exception as e:
        print(f"❌ Error during force kill: {e}")
        return False

def cleanup_pid_file():
    """Clean up PID file"""
    pid_file = PROJECT_ROOT / "reports" / "bot.pid"
    try:
        if pid_file.exists():
            pid_file.unlink()
            print("🗑️  Removed PID file")
    except Exception as e:
        print(f"⚠️  Could not remove PID file: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Bot Stopper')
    parser.add_argument('--graceful', action='store_true', help='Graceful stop (default)')
    parser.add_argument('--force', action='store_true', help='Force kill')
    parser.add_argument('--check-only', action='store_true', help='Check if bot is running')
    
    args = parser.parse_args()
    
    # Get bot PID
    pid = get_bot_pid()
    
    if args.check_only:
        if pid:
            print(f"✅ Bot is running (PID: {pid})")
            sys.exit(0)
        else:
            print("ℹ️  Bot is not running")
            sys.exit(1)
    
    if not pid:
        print("ℹ️  Bot is not running (no PID file or process not found)")
        cleanup_pid_file()
        sys.exit(1)
    
    # Stop bot
    success = False
    
    if args.force:
        success = stop_bot_force(pid)
    else:
        # Graceful is default
        success = stop_bot_graceful(pid)
        
        if not success:
            # Graceful failed, try force kill
            print("")
            print("⚠️  Graceful shutdown failed, trying force kill...")
            success = stop_bot_force(pid)
    
    # Clean up
    cleanup_pid_file()
    
    if success:
        print("")
        print("✅ Bot stopped successfully")
        sys.exit(0)
    else:
        print("")
        print("❌ Failed to stop bot")
        sys.exit(2)

if __name__ == '__main__':
    main()


