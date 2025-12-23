#!/usr/bin/env python3
"""
GridBot Entry Point with Recovery Integration
PM2-compatible startup script with proper signal handling

Usage: pm2 start ecosystem.gridbot.config.js --only gridbot-live
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Global bot instance for signal handling
bot_instance = None

def signal_handler(sig, frame):
    """Handle shutdown signals from PM2"""
    print(f"Received signal {sig} - initiating graceful shutdown")
    if bot_instance:
        # Trigger bot's graceful shutdown
        bot_instance._running = False

async def run_recovery():
    """Run recovery engine if needed"""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'bot.strategy.recovery.recovery_runner',
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=PROJECT_ROOT
        )
        await process.communicate()
    except Exception:
        pass  # Continue if recovery fails

async def start_reconciliation_engine():
    """Start reconciliation engine in background"""
    try:
        # Start reconciliation engine as background process
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'bot.strategy.reconciliation.reconciliation_runner',
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=PROJECT_ROOT
        )
        print(f"Reconciliation engine started (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"Failed to start reconciliation engine: {e}")
        return None

async def main():
    """Main entry point"""
    global bot_instance
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    reconciliation_process = None
    
    try:
        # Step 1: Run recovery (silent)
        await run_recovery()
        
        # Step 2: Start reconciliation engine (background)
        reconciliation_process = await start_reconciliation_engine()
        
        # Step 3: Start main bot with integrated recovery and reconciliation
        from bot.strategy.async_gridbot import AsyncGridBot
        
        bot_instance = AsyncGridBot()
        await bot_instance.start()
        
    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        # Cleanup reconciliation process
        if reconciliation_process:
            try:
                reconciliation_process.terminate()
                await reconciliation_process.wait()
            except Exception as e:
                print(f"Error stopping reconciliation: {e}")
        
        if bot_instance:
            try:
                await bot_instance.stop()
            except Exception as e:
                print(f"Error during shutdown: {e}")

if __name__ == "__main__":
    asyncio.run(main())