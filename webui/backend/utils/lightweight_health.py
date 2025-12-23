#!/usr/bin/env python3
"""
Lightweight Health Check System

Ultra-fast health endpoint that doesn't do any heavy operations.
Uses cached state updated by background thread.
"""

import time
import threading
from typing import Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class HealthState:
    """Cached health state."""
    status: str = 'unknown'
    bot_running: bool = False
    monitor_running: bool = False
    guardian_running: bool = False
    telegram_connected: bool = False
    last_updated: float = 0.0
    update_count: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            'status': self.status,
            'bot_running': self.bot_running,
            'monitor_running': self.monitor_running,
            'guardian_running': self.guardian_running,
            'telegram_connected': self.telegram_connected,
            'last_updated': self.last_updated,
            'uptime': time.time() - self.last_updated if self.last_updated > 0 else 0
        }


class LightweightHealthCheck:
    """
    Ultra-lightweight health check system.
    
    - Updates health state in background thread (every 5 seconds)
    - Health endpoint just returns cached state (sub-millisecond response)
    - No file I/O, subprocess calls, or network requests in hot path
    """
    
    def __init__(self, update_interval: int = 5):
        self.update_interval = update_interval
        self.state = HealthState()
        self.state_lock = threading.Lock()
        self.running = False
        self.background_thread: Optional[threading.Thread] = None
        
        # Callbacks to check each service (set by app.py)
        self.check_bot_callback: Optional[Callable[[], bool]] = None
        self.check_monitor_callback: Optional[Callable[[], bool]] = None
        self.check_guardian_callback: Optional[Callable[[], bool]] = None
        self.check_telegram_callback: Optional[Callable[[], bool]] = None
    
    def set_check_callbacks(
        self,
        bot_check: Callable[[], bool] = None,
        monitor_check: Callable[[], bool] = None,
        guardian_check: Callable[[], bool] = None,
        telegram_check: Callable[[], bool] = None
    ):
        """Set callbacks for checking each service."""
        if bot_check:
            self.check_bot_callback = bot_check
        if monitor_check:
            self.check_monitor_callback = monitor_check
        if guardian_check:
            self.check_guardian_callback = guardian_check
        if telegram_check:
            self.check_telegram_callback = telegram_check
    
    def _update_state(self):
        """Update health state (runs in background thread)."""
        try:
            # Check each service if callback is set
            bot_running = self.check_bot_callback() if self.check_bot_callback else False
            monitor_running = self.check_monitor_callback() if self.check_monitor_callback else False
            guardian_running = self.check_guardian_callback() if self.check_guardian_callback else False
            telegram_connected = self.check_telegram_callback() if self.check_telegram_callback else False
            
            # Determine overall status
            if bot_running and monitor_running and guardian_running:
                status = 'healthy'
            elif bot_running or monitor_running or guardian_running:
                status = 'degraded'
            else:
                status = 'unhealthy'
            
            # Update state
            with self.state_lock:
                self.state.status = status
                self.state.bot_running = bot_running
                self.state.monitor_running = monitor_running
                self.state.guardian_running = guardian_running
                self.state.telegram_connected = telegram_connected
                self.state.last_updated = time.time()
                self.state.update_count += 1
        
        except Exception as e:
            print(f"⚠️  Health check update error: {e}")
            with self.state_lock:
                self.state.status = 'error'
                self.state.last_updated = time.time()
    
    def _background_updater(self):
        """Background thread that updates health state."""
        print(f"🏥 Health check background updater started (interval: {self.update_interval}s)")
        
        while self.running:
            self._update_state()
            
            # Sleep in small intervals to allow quick shutdown
            for _ in range(self.update_interval):
                if not self.running:
                    break
                time.sleep(1)
        
        print("🏥 Health check background updater stopped")
    
    def start(self):
        """Start background health check updates."""
        if self.running:
            return
        
        self.running = True
        self.background_thread = threading.Thread(
            target=self._background_updater,
            daemon=True,
            name="HealthCheckUpdater"
        )
        self.background_thread.start()
    
    def stop(self):
        """Stop background health check updates."""
        self.running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)
    
    def get_state(self) -> dict:
        """
        Get current health state (FAST - just returns cached data).
        
        This is what the /api/health endpoint calls.
        Response time: < 1ms (no I/O, no subprocess, no network)
        """
        with self.state_lock:
            result = self.state.to_dict()
            result['timestamp'] = time.time()
            result['cache_age_seconds'] = time.time() - self.state.last_updated
            return result
    
    def get_detailed_state(self) -> dict:
        """
        Get detailed health state with metrics.
        
        Still fast (< 5ms) but includes more data.
        """
        state = self.get_state()
        
        # Add metrics
        state['metrics'] = {
            'update_count': self.state.update_count,
            'update_interval': self.update_interval,
            'last_update_time': datetime.fromtimestamp(self.state.last_updated).isoformat()
        }
        
        return state
    
    def force_update(self):
        """Force immediate health state update (for testing)."""
        self._update_state()


# Global instance
_health_checker = None
_health_lock = threading.Lock()


def get_health_checker() -> LightweightHealthCheck:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        with _health_lock:
            if _health_checker is None:
                _health_checker = LightweightHealthCheck(update_interval=5)
    return _health_checker


def start_health_checker(
    bot_check: Callable[[], bool] = None,
    monitor_check: Callable[[], bool] = None,
    guardian_check: Callable[[], bool] = None,
    telegram_check: Callable[[], bool] = None
):
    """
    Initialize and start health checker.
    
    Example in app.py:
        from webui.backend.utils.lightweight_health import start_health_checker
        
        start_health_checker(
            bot_check=is_bot_running,
            monitor_check=is_monitor_running,
            guardian_check=is_guardian_running,
            telegram_check=lambda: get_telegram_health().get('connected', False)
        )
    """
    checker = get_health_checker()
    checker.set_check_callbacks(
        bot_check=bot_check,
        monitor_check=monitor_check,
        guardian_check=guardian_check,
        telegram_check=telegram_check
    )
    checker.start()
    return checker


def stop_health_checker():
    """Stop health checker background thread."""
    global _health_checker
    if _health_checker is not None:
        _health_checker.stop()
