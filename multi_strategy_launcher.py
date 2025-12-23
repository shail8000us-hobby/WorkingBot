#!/usr/bin/env python3
"""
Multi-Strategy Bot Launcher
Launches multiple GridBot instances with different strategy configurations.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from config.loader import get_config
from config.strategy_manager import StrategyManager, CapitalAllocator
from config.models import RootConfig


class MultiStrategyLauncher:
    """Manages multiple bot instances with different strategies"""
    
    def __init__(self, total_capital: float):
        self.total_capital = total_capital
        self.base_config = get_config()
        self.strategy_manager = StrategyManager(self.base_config)
        self.allocator = CapitalAllocator(total_capital)
        self.bot_processes: Dict[str, asyncio.Task] = {}
        self.running = False
        
    def configure_strategies(self, allocation_method: str = 'equal', weights: Optional[Dict[str, float]] = None):
        """Configure capital allocation for strategies"""
        active_strategies = list(self.strategy_manager.active_strategies)
        
        if not active_strategies:
            raise ValueError("No active strategies found. Activate strategies first.")
        
        if allocation_method == 'equal':
            self.allocator.allocate_equal(active_strategies)
        elif allocation_method == 'weighted':
            if not weights:
                raise ValueError("Weights required for weighted allocation")
            self.allocator.allocate_weighted(weights)
        else:
            raise ValueError(f"Unknown allocation method: {allocation_method}")
        
        print(f"✅ Capital allocated to {len(active_strategies)} strategies:")
        for strategy_name in active_strategies:
            capital = self.allocator.get_allocation(strategy_name)
            print(f"   - {strategy_name}: ${capital:,.2f}")
    
    async def launch_strategy(self, strategy_name: str) -> None:
        """Launch a single strategy instance"""
        try:
            # Get strategy config
            strategy_config = self.strategy_manager.get_strategy(strategy_name)
            capital = self.allocator.get_allocation(strategy_name)
            
            print(f"\n🚀 Launching strategy: {strategy_name}")
            print(f"   Capital: ${capital:,.2f}")
            print(f"   Symbol: {strategy_config.bot.symbol}")
            print(f"   Mode: {strategy_config.bot.mode}")
            print(f"   Grid: {strategy_config.grid.geometry.lower}-{strategy_config.grid.geometry.upper} (step: {strategy_config.grid.geometry.step})")
            
            # In production, this would actually launch the bot
            # For now, simulate with a long-running task
            while self.running:
                await asyncio.sleep(10)
                # Placeholder for actual bot execution
                # In real implementation:
                # from gridbot_async import GridBot
                # bot = GridBot(strategy_config, capital)
                # await bot.run()
            
        except Exception as e:
            print(f"❌ Error in strategy {strategy_name}: {e}")
            raise
    
    async def launch_all(self):
        """Launch all active strategies"""
        active_strategies = list(self.strategy_manager.active_strategies)
        
        if not active_strategies:
            raise ValueError("No active strategies to launch")
        
        print(f"\n{'='*60}")
        print(f"Multi-Strategy Bot Launcher")
        print(f"{'='*60}")
        print(f"Total Capital: ${self.total_capital:,.2f}")
        print(f"Active Strategies: {len(active_strategies)}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        self.running = True
        
        # Launch each strategy as a separate task
        for strategy_name in active_strategies:
            task = asyncio.create_task(self.launch_strategy(strategy_name))
            self.bot_processes[strategy_name] = task
        
        # Wait for all strategies
        try:
            await asyncio.gather(*self.bot_processes.values())
        except asyncio.CancelledError:
            print("\n⚠️  Shutdown signal received")
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown all strategies"""
        print("\n🛑 Shutting down all strategies...")
        self.running = False
        
        # Cancel all running tasks
        for strategy_name, task in self.bot_processes.items():
            if not task.done():
                print(f"   Stopping {strategy_name}...")
                task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self.bot_processes.values(), return_exceptions=True)
        
        print("✅ All strategies stopped")
    
    def print_status(self):
        """Print current status of all strategies"""
        print(f"\n{'='*60}")
        print(f"Multi-Strategy Status")
        print(f"{'='*60}")
        print(f"Total Capital: ${self.total_capital:,.2f}")
        print(f"Allocated: ${self.allocator.total_capital - self.allocator.get_unallocated_capital():,.2f}")
        print(f"Unallocated: ${self.allocator.get_unallocated_capital():,.2f}")
        print(f"\nActive Strategies: {len(self.bot_processes)}")
        
        for strategy_name, task in self.bot_processes.items():
            status = "Running" if not task.done() else "Stopped"
            capital = self.allocator.get_allocation(strategy_name)
            print(f"   [{status}] {strategy_name}: ${capital:,.2f}")
        
        print(f"{'='*60}\n")


async def main():
    """Main entry point"""
    # Example usage
    try:
        # Initialize launcher with total capital
        launcher = MultiStrategyLauncher(total_capital=100000)
        
        # Activate desired strategies
        # (In production, these would be defined in config.yaml)
        launcher.strategy_manager.activate_strategy('default')  # Base strategy always available
        
        # Allocate capital equally
        launcher.configure_strategies(allocation_method='equal')
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            print("\n⚠️  Interrupt received, shutting down...")
            asyncio.create_task(launcher.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Launch all strategies
        await launcher.launch_all()
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    """
    Example usage with multiple strategies:
    
    # In config.yaml, define strategies:
    strategies:
      - name: conservative
        description: Conservative grid trading
        overrides:
          grid.geometry.step: 1000
          grid.limits.lot_size: 1
      
      - name: aggressive
        description: Aggressive grid trading
        overrides:
          grid.geometry.step: 200
          grid.limits.lot_size: 5
    
    # Then run:
    python3 multi_strategy_launcher.py
    
    # Or with custom allocation:
    launcher = MultiStrategyLauncher(total_capital=100000)
    launcher.strategy_manager.activate_strategy('conservative')
    launcher.strategy_manager.activate_strategy('aggressive')
    launcher.configure_strategies(
        allocation_method='weighted',
        weights={'conservative': 0.7, 'aggressive': 0.3}
    )
    await launcher.launch_all()
    """
    
    asyncio.run(main())
