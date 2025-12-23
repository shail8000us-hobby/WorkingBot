# bot/heartbeat/manager.py
"""
HeartbeatManager - Bot-side heartbeat system
Updates heartbeat file periodically to signal bot is alive.
"""

import os
import json
import time
import logging
from typing import Optional

log = logging.getLogger("runner")


class HeartbeatManager:
    """
    Manages bot heartbeat by updating a file periodically.
    
    The monitor process watches this file and takes action if it becomes stale.
    """
    
    def __init__(
        self, 
        heartbeat_file: str = ".heartbeat",
        update_interval: int = 5,
        enabled: bool = True
    ):
        """
        Initialize HeartbeatManager.
        
        Args:
            heartbeat_file: Path to heartbeat file
            update_interval: How often to update heartbeat (seconds)
            enabled: Whether heartbeat is enabled
        """
        self.heartbeat_file = heartbeat_file
        self.update_interval = update_interval
        self.enabled = enabled
        self.last_update = 0
        self.bot_pid = os.getpid()
        
        if self.enabled:
            log.info(f"✅ Heartbeat enabled: {heartbeat_file} (update every {update_interval}s)")
        else:
            log.info("Heartbeat disabled")
    
    def start(self):
        """Initialize heartbeat file on startup."""
        if not self.enabled:
            return
        
        try:
            self._write_heartbeat("starting")
            log.info(f"💓 Heartbeat started: PID={self.bot_pid}")
        except Exception as e:
            log.error(f"Failed to start heartbeat: {e}")
    
    def update(self):
        """
        Update heartbeat file if enough time has passed.
        Call this in your main bot loop.
        """
        if not self.enabled:
            return
        
        now = time.time()
        
        # Only update if interval has passed
        if now - self.last_update < self.update_interval:
            return
        
        try:
            self._write_heartbeat("ok")
            self.last_update = now
            log.debug(f"💓 Heartbeat updated: {int(now)}")
        except Exception as e:
            log.warning(f"Failed to update heartbeat: {e}")
    
    def stop(self):
        """Mark heartbeat as stopped on graceful shutdown."""
        if not self.enabled:
            return
        
        try:
            self._write_heartbeat("stopped")
            log.info("💓 Heartbeat stopped (graceful shutdown)")
        except Exception as e:
            log.warning(f"Failed to stop heartbeat: {e}")
    
    def _write_heartbeat(self, status: str):
        """Write heartbeat data to file with memory monitoring."""
        # Get memory usage (MB)
        memory_mb = None
        try:
            import psutil
            process = psutil.Process(self.bot_pid)
            memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
            
            # Alert on high memory usage
            if memory_mb > 150:
                log.warning(f"⚠️ High memory usage: {memory_mb}MB")
            
        except Exception as e:
            log.debug(f"Could not get memory stats: {e}")
        
        data = {
            "timestamp": time.time(),
            "status": status,
            "pid": self.bot_pid,
            "memory_mb": memory_mb,
            "update_interval": self.update_interval
        }
        
        try:
            with open(self.heartbeat_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to write heartbeat file: {e}")
            raise
    
    def get_status(self) -> Optional[dict]:
        """Read current heartbeat status (for debugging)."""
        if not os.path.exists(self.heartbeat_file):
            return None
        
        try:
            with open(self.heartbeat_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Failed to read heartbeat: {e}")
            return None

