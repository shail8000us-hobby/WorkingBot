"""
Configuration file watcher for hot reload.
Monitors config.yaml for changes and triggers safe reload.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Callable, Awaitable, List, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from config.models import RootConfig
from config.loader import reload_config


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes"""
    
    def __init__(self, callback: Callable[[Path], Awaitable[None]]):
        """Initialize handler
        
        Args:
            callback: Async callback function to call on file change
        """
        super().__init__()
        self.callback = callback
        self.last_modified = 0
        self.debounce_seconds = 1  # Debounce rapid file changes
        self._callback_in_progress = False  # Re-entrancy guard
        self._pending_task = None  # Track active task
        
    def on_modified(self, event):
        """Handle file modification event"""
        if event.is_directory:
            return
        
        # Only watch YAML files
        if not event.src_path.endswith(('.yaml', '.yml')):
            return
        
        # Debounce (avoid duplicate events)
        now = time.time()
        if now - self.last_modified < self.debounce_seconds:
            return
        self.last_modified = now
        
        # RE-ENTRANCY GUARD: Prevent recursive callback amplification
        if self._callback_in_progress:
            return
        
        # Cancel pending task if still running
        if self._pending_task and not self._pending_task.done():
            return
        
        # Trigger callback with guard
        self._callback_in_progress = True
        self._pending_task = asyncio.create_task(self._safe_callback(Path(event.src_path)))
    
    async def _safe_callback(self, path: Path):
        """Execute callback with re-entrancy protection"""
        try:
            await self.callback(path)
        finally:
            self._callback_in_progress = False


class ConfigWatcher:
    """Watch configuration file for changes and trigger hot reload"""
    
    def __init__(
        self,
        config_path: Path,
        on_change: Optional[Callable[[RootConfig], Awaitable[None]]] = None
    ):
        """Initialize config watcher
        
        Args:
            config_path: Path to config file to watch
            on_change: Callback when config changes (receives new config)
        """
        self.config_path = Path(config_path)
        self.on_change = on_change
        self.observer: Optional[Observer] = None
        self.running = False
        
    async def start(self):
        """Start watching config file"""
        if self.running:
            return
        
        # Create file handler
        handler = ConfigFileHandler(self._on_config_changed)
        
        # Create and start observer
        self.observer = Observer()
        watch_dir = self.config_path.parent if self.config_path.is_file() else self.config_path
        self.observer.schedule(handler, str(watch_dir), recursive=False)
        self.observer.start()
        
        self.running = True
        print(f"👁️  Watching {self.config_path} for changes...")
        
    async def stop(self):
        """Stop watching config file"""
        if not self.running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.running = False
        print("🛑 Config watcher stopped")
        
    async def _on_config_changed(self, file_path: Path):
        """Handle config file change
        
        Args:
            file_path: Path to changed file
        """
        print(f"\n🔄 Config file changed: {file_path}")
        
        try:
            # Reload and validate new config
            new_config = reload_config()
            print("  ✅ New config validated successfully")
            
            # Trigger callback if provided
            if self.on_change:
                await self.on_change(new_config)
            else:
                print("  ℹ️  No change callback configured")
                
        except Exception as e:
            print(f"  ❌ Invalid config: {e}")
            print("  ⚠️  Keeping current configuration")


class ConfigHistory:
    """Track configuration change history for rollback"""
    
    def __init__(self, max_history: int = 10):
        """Initialize config history
        
        Args:
            max_history: Maximum number of configs to keep
        """
        self.history: List[RootConfig] = []
        self.max_history = max_history
        self.current_index = -1
        
    def save_version(self, config: RootConfig):
        """Save configuration version
        
        Args:
            config: Configuration to save
        """
        # If we're not at the latest version, remove future versions
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # Add new version
        self.history.append(config)
        
        # Trim old versions
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.current_index += 1
        
    def rollback(self, steps: int = 1) -> RootConfig:
        """Rollback to previous configuration
        
        Args:
            steps: Number of versions to go back
            
        Returns:
            Previous configuration
            
        Raises:
            ValueError: If cannot rollback that many steps
        """
        target_index = self.current_index - steps
        
        if target_index < 0:
            raise ValueError(f"Cannot rollback {steps} steps (only {self.current_index + 1} versions in history)")
        
        self.current_index = target_index
        return self.history[self.current_index]
        
    def rollforward(self, steps: int = 1) -> RootConfig:
        """Roll forward to newer configuration
        
        Args:
            steps: Number of versions to go forward
            
        Returns:
            Newer configuration
            
        Raises:
            ValueError: If cannot roll forward that many steps
        """
        target_index = self.current_index + steps
        
        if target_index >= len(self.history):
            available = len(self.history) - self.current_index - 1
            raise ValueError(f"Cannot roll forward {steps} steps (only {available} versions ahead)")
        
        self.current_index = target_index
        return self.history[self.current_index]
        
    def get_current(self) -> Optional[RootConfig]:
        """Get current configuration
        
        Returns:
            Current config or None if empty
        """
        if self.current_index >= 0 and self.current_index < len(self.history):
            return self.history[self.current_index]
        return None
        
    def get_version(self, index: int) -> RootConfig:
        """Get specific version
        
        Args:
            index: Version index (0 = oldest, -1 = newest)
            
        Returns:
            Configuration at that index
            
        Raises:
            IndexError: If index out of range
        """
        return self.history[index]
        
    def list_versions(self) -> List[Dict]:
        """List all versions with metadata
        
        Returns:
            List of version info dicts
        """
        return [
            {
                'index': i,
                'is_current': i == self.current_index,
                'symbol': config.bot.symbol,
                'grid_lower': config.grid.geometry.lower,
                'grid_upper': config.grid.geometry.upper,
            }
            for i, config in enumerate(self.history)
        ]
