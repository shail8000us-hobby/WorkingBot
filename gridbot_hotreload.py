"""
GridBot Hot-Reload Integration Module
Integrates ConfigWatcher with GridBot for safe, zero-downtime config updates.
"""

import asyncio
from typing import Optional, Callable, Awaitable
from pathlib import Path

from config.watcher import ConfigWatcher
from config.loader import get_config, reload_config
from config.models import RootConfig


class GridBotHotReload:
    """Manages safe hot-reload of configuration for GridBot"""
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        on_reload_callback: Optional[Callable[[RootConfig, RootConfig], Awaitable[None]]] = None
    ):
        """
        Initialize hot-reload manager
        
        Args:
            config_path: Path to config file (auto-detected if None)
            on_reload_callback: Async callback function(old_config, new_config)
        """
        self.config_path = config_path
        self.watcher: Optional[ConfigWatcher] = None
        self.user_callback = on_reload_callback
        self.current_config = get_config()
        self.reload_in_progress = False
        
    async def safe_reload_callback(self, old_config: RootConfig, new_config: RootConfig) -> None:
        """
        Safe reload callback with trading pause
        
        This is the internal callback that handles:
        1. Pause trading
        2. Reload configuration
        3. Call user callback
        4. Resume trading
        """
        if self.reload_in_progress:
            print("⚠️  Config reload already in progress, skipping...")
            return
        
        try:
            self.reload_in_progress = True
            print("\n🔄 Config change detected - initiating safe reload...")
            
            # Step 1: Pause trading
            print("   1. Pausing trading...")
            # In actual GridBot, this would call: bot.pause_trading()
            await asyncio.sleep(0.5)  # Simulate pause
            
            # Step 2: Validate new config
            print("   2. Validating new configuration...")
            try:
                new_config.validate_cross_field_constraints()
                print("   ✓ Validation passed")
            except Exception as e:
                print(f"   ✗ Validation failed: {e}")
                print("   ⚠️  Keeping old configuration")
                return
            
            # Step 3: Apply new config
            print("   3. Applying new configuration...")
            self.current_config = new_config
            
            # Step 4: Call user callback (if provided)
            if self.user_callback:
                print("   4. Executing user callback...")
                await self.user_callback(old_config, new_config)
            
            # Step 5: Resume trading
            print("   5. Resuming trading...")
            # In actual GridBot, this would call: bot.resume_trading()
            await asyncio.sleep(0.5)  # Simulate resume
            
            print("✅ Config reload completed successfully\n")
            
            # Log what changed
            self._log_changes(old_config, new_config)
            
        except Exception as e:
            print(f"❌ Error during config reload: {e}")
            print("   Reverting to old configuration...")
            self.current_config = old_config
            
        finally:
            self.reload_in_progress = False
    
    def _log_changes(self, old_config: RootConfig, new_config: RootConfig) -> None:
        """Log configuration changes"""
        changes = []
        
        # Check grid changes
        if old_config.grid.geometry != new_config.grid.geometry:
            changes.append(f"Grid geometry: {old_config.grid.geometry.dict()} → {new_config.grid.geometry.dict()}")
        
        if old_config.grid.limits != new_config.grid.limits:
            changes.append(f"Grid limits: {old_config.grid.limits.dict()} → {new_config.grid.limits.dict()}")
        
        # Check bot changes
        if old_config.bot.symbol != new_config.bot.symbol:
            changes.append(f"Symbol: {old_config.bot.symbol} → {new_config.bot.symbol}")
        
        if old_config.bot.mode != new_config.bot.mode:
            changes.append(f"Mode: {old_config.bot.mode} → {new_config.bot.mode}")
        
        if changes:
            print("📋 Configuration changes:")
            for change in changes:
                print(f"   - {change}")
    
    def start(self) -> None:
        """Start watching for config changes"""
        print("🔍 Starting config file watcher...")
        self.watcher = ConfigWatcher(self.config_path)
        self.watcher.start()
        print(f"✓ Watching: {self.watcher.config_path}")
    
    def stop(self) -> None:
        """Stop watching for config changes"""
        if self.watcher:
            print("🛑 Stopping config file watcher...")
            self.watcher.stop()
            print("✓ Watcher stopped")
    
    def get_current_config(self) -> RootConfig:
        """Get current active configuration"""
        return self.current_config


# Example integration with GridBot
class GridBotWithHotReload:
    """Example GridBot class with hot-reload support"""
    
    def __init__(self):
        self.config = get_config()
        self.running = False
        self.trading_paused = False
        
        # Setup hot-reload
        self.hot_reload = GridBotHotReload(
            on_reload_callback=self.on_config_reloaded
        )
    
    async def on_config_reloaded(self, old_config: RootConfig, new_config: RootConfig) -> None:
        """Custom callback when config is reloaded"""
        print("🔧 GridBot: Applying new configuration...")
        
        # Update internal config reference
        self.config = new_config
        
        # Reinitialize components if needed
        if old_config.grid.geometry != new_config.grid.geometry:
            print("   Rebuilding grid structure...")
            # await self.rebuild_grid()
        
        if old_config.bot.symbol != new_config.bot.symbol:
            print("   Switching to new symbol...")
            # await self.switch_symbol(new_config.bot.symbol)
        
        print("   ✓ GridBot configuration updated")
    
    async def run(self):
        """Main bot loop"""
        print("🚀 Starting GridBot with hot-reload enabled...")
        
        # Start config watcher
        self.hot_reload.start()
        
        self.running = True
        try:
            while self.running:
                # Bot logic here
                if not self.trading_paused:
                    # Execute trading logic
                    pass
                
                await asyncio.sleep(1)
        
        finally:
            # Stop config watcher
            self.hot_reload.stop()
    
    def pause_trading(self):
        """Pause trading (called during config reload)"""
        self.trading_paused = True
        print("⏸️  Trading paused")
    
    def resume_trading(self):
        """Resume trading (called after config reload)"""
        self.trading_paused = False
        print("▶️  Trading resumed")
    
    def stop(self):
        """Stop bot"""
        self.running = False
        print("🛑 GridBot stopping...")


# Usage example
async def main():
    """Example usage of GridBot with hot-reload"""
    bot = GridBotWithHotReload()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        bot.stop()


if __name__ == '__main__':
    """
    Integration instructions for existing GridBot:
    
    1. Add to gridbot_async.py imports:
       from gridbot_hotreload import GridBotHotReload
    
    2. In GridBot.__init__():
       self.hot_reload = GridBotHotReload(
           on_reload_callback=self.on_config_reloaded
       )
    
    3. In GridBot.run():
       self.hot_reload.start()
       try:
           # ... existing run logic ...
       finally:
           self.hot_reload.stop()
    
    4. Implement GridBot.on_config_reloaded():
       async def on_config_reloaded(self, old_config, new_config):
           # Update internal state
           self.config = new_config
           # Reinitialize components as needed
    
    5. Test with:
       # Edit config.yaml while bot is running
       echo "# test change" >> config.yaml
       # Bot should reload automatically
    """
    
    asyncio.run(main())
