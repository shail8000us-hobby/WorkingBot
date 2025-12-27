"""
System Health Tracker for Guardian Layer 5
==========================================

Monitors API connectivity, WebSocket status, data freshness,
and exchange maintenance to detect system issues that should halt trading.

Author: Guardian Safety System
Version: 1.0.0
Date: 2025-12-26
"""

import time
import logging
from typing import Dict, Optional
from collections import deque
from datetime import datetime

log = logging.getLogger(__name__)


class SystemHealthTracker:
    """
    Tracks system health metrics for Guardian Layer 5 safety checks.
    
    Monitors:
    - API connectivity (success rate, response times, failures)
    - WebSocket status (connection state, data freshness)
    - Data collectors freshness (volatility, positions, liquidation)
    - Event store health (connection, write performance)
    """
    
    def __init__(self, config=None):
        """
        Initialize health tracker.
        
        Args:
            config: Configuration object with health_check settings
        """
        self.config = config
        
        # Load thresholds from config or use defaults
        if config and hasattr(config, 'guardian') and hasattr(config.guardian, 'health_check'):
            hc = config.guardian.health_check
            self.api_timeout = getattr(hc, 'api_timeout_seconds', 30)
            self.websocket_timeout = getattr(hc, 'websocket_timeout_seconds', 60)
            self.data_stale_threshold = getattr(hc, 'data_stale_threshold_seconds', 120)
            self.enabled = getattr(hc, 'enabled', True)
        else:
            # Defaults (conservative)
            self.api_timeout = 30
            self.websocket_timeout = 60
            self.data_stale_threshold = 120
            self.enabled = True
        
        # API health tracking
        self.api_calls = deque(maxlen=100)  # Last 100 API calls
        self.last_api_success = time.time()  # Assume healthy at start
        self.last_api_failure = 0
        self.consecutive_failures = 0
        
        # WebSocket health tracking (not critical for Guardian)
        self.websocket_connected = False
        self.last_websocket_data = time.time()  # Assume recent at start
        self.websocket_reconnect_count = 0
        
        # Data freshness tracking (not critical initially)
        self.data_updates = {
            'volatility': time.time(),  # Assume fresh at start
            'positions': time.time(),
            'liquidation': time.time(),
            'event_store': time.time()
        }
        
        # Event store health
        self.event_store_connected = True
        self.last_event_write = time.time()
        
        # Exchange maintenance monitoring
        self.maintenance_monitor = None
        self.exchange_in_maintenance = False
        
        log.info(f"✅ SystemHealthTracker initialized (enabled={self.enabled})")
        log.info(f"   API timeout: {self.api_timeout}s")
        log.info(f"   WebSocket timeout: {self.websocket_timeout}s")
        log.info(f"   Data stale threshold: {self.data_stale_threshold}s")
        
        # Start maintenance monitor if enabled
        if self.enabled:
            self._start_maintenance_monitor()
    
    def _start_maintenance_monitor(self):
        """Start the maintenance monitor."""
        try:
            from .maintenance_monitor import DeltaMaintenanceMonitor, WEBSOCKET_AVAILABLE
            
            if not WEBSOCKET_AVAILABLE:
                log.warning("⚠️ Maintenance monitoring disabled - websocket-client not installed")
                return
            
            self.maintenance_monitor = DeltaMaintenanceMonitor(health_tracker=self)
            
            # Set callbacks to update health status
            def on_maintenance_started(start_time, finish_time):
                self.exchange_in_maintenance = True
                log.critical("🔴 EXCHANGE MAINTENANCE - Trading halted by health tracker")
            
            def on_maintenance_finished(finish_time):
                self.exchange_in_maintenance = False
                log.info("🟢 Exchange maintenance finished - Trading can resume")
            
            self.maintenance_monitor.set_callbacks(
                on_started=on_maintenance_started,
                on_finished=on_maintenance_finished
            )
            
            self.maintenance_monitor.start()
            log.info("✅ Maintenance monitor started")
            
        except ImportError as e:
            log.warning(f"⚠️ Could not import maintenance monitor: {e}")
        except Exception as e:
            log.error(f"❌ Error starting maintenance monitor: {e}")
    
    def record_api_call(self, success: bool, response_time: float = 0, endpoint: str = ""):
        """
        Record an API call attempt.
        
        Args:
            success: Whether the API call succeeded
            response_time: Response time in seconds
            endpoint: API endpoint name (for debugging)
        """
        if not self.enabled:
            return
        
        timestamp = time.time()
        
        self.api_calls.append({
            'timestamp': timestamp,
            'success': success,
            'response_time': response_time,
            'endpoint': endpoint
        })
        
        if success:
            self.last_api_success = timestamp
            self.consecutive_failures = 0
            log.debug(f"✅ API call succeeded: {endpoint} ({response_time:.2f}s)")
        else:
            self.last_api_failure = timestamp
            self.consecutive_failures += 1
            log.warning(f"❌ API call failed: {endpoint} (consecutive failures: {self.consecutive_failures})")
    
    def record_websocket_update(self, data_type: str = "general"):
        """
        Record a WebSocket data update.
        
        Args:
            data_type: Type of data received (e.g., "ticker", "orderbook")
        """
        if not self.enabled:
            return
        
        timestamp = time.time()
        self.last_websocket_data = timestamp
        self.websocket_connected = True
        
        log.debug(f"✅ WebSocket data: {data_type}")
    
    def record_websocket_disconnect(self):
        """Record WebSocket disconnection event."""
        if not self.enabled:
            return
        
        self.websocket_connected = False
        self.websocket_reconnect_count += 1
        log.warning(f"⚠️ WebSocket disconnected (reconnect count: {self.websocket_reconnect_count})")
    
    def record_websocket_connect(self):
        """Record WebSocket connection event."""
        if not self.enabled:
            return
        
        self.websocket_connected = True
        self.last_websocket_data = time.time()
        log.info(f"✅ WebSocket connected")
    
    def record_data_update(self, data_type: str):
        """
        Record a data collector update.
        
        Args:
            data_type: Type of data ("volatility", "positions", "liquidation", "event_store")
        """
        if not self.enabled:
            return
        
        if data_type in self.data_updates:
            self.data_updates[data_type] = time.time()
            log.debug(f"✅ Data updated: {data_type}")
        else:
            log.warning(f"⚠️ Unknown data type: {data_type}")
    
    def record_event_store_write(self, success: bool = True):
        """
        Record an event store write.
        
        Args:
            success: Whether the write succeeded
        """
        if not self.enabled:
            return
        
        if success:
            self.last_event_write = time.time()
            self.event_store_connected = True
        else:
            self.event_store_connected = False
            log.warning("⚠️ Event store write failed")
    
    def get_api_health(self) -> Dict:
        """Get API health metrics."""
        if not self.enabled or not self.api_calls:
            return {
                'healthy': True,
                'success_rate': 100.0,
                'avg_response_time': 0,
                'consecutive_failures': 0,
                'last_success_ago': 0
            }
        
        # Calculate success rate
        recent_calls = list(self.api_calls)[-20:]  # Last 20 calls
        successes = sum(1 for call in recent_calls if call['success'])
        success_rate = (successes / len(recent_calls)) * 100 if recent_calls else 100.0
        
        # Calculate average response time
        successful_calls = [c for c in recent_calls if c['success']]
        avg_response_time = sum(c['response_time'] for c in successful_calls) / len(successful_calls) if successful_calls else 0
        
        # Time since last success
        last_success_ago = time.time() - self.last_api_success if self.last_api_success else 0
        
        # Determine if API is healthy
        healthy = (
            success_rate >= 50.0 and  # At least 50% success rate
            last_success_ago < self.api_timeout and  # Recent success within timeout
            self.consecutive_failures < 5  # Not too many consecutive failures
        )
        
        return {
            'healthy': healthy,
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'consecutive_failures': self.consecutive_failures,
            'last_success_ago': last_success_ago
        }
    
    def get_websocket_health(self) -> Dict:
        """Get WebSocket health metrics."""
        if not self.enabled:
            return {
                'healthy': True,
                'connected': True,
                'stale_seconds': 0,
                'reconnect_count': 0
            }
        
        stale_seconds = time.time() - self.last_websocket_data if self.last_websocket_data else 999
        
        healthy = (
            self.websocket_connected and
            stale_seconds < self.websocket_timeout
        )
        
        return {
            'healthy': healthy,
            'connected': self.websocket_connected,
            'stale_seconds': stale_seconds,
            'reconnect_count': self.websocket_reconnect_count
        }
    
    def get_data_freshness(self) -> Dict:
        """Get data freshness metrics."""
        if not self.enabled:
            return {
                'healthy': True,
                'volatility_stale_seconds': 0,
                'positions_stale_seconds': 0,
                'liquidation_stale_seconds': 0
            }
        
        current_time = time.time()
        
        volatility_stale = current_time - self.data_updates.get('volatility', 0) if self.data_updates.get('volatility', 0) else 0
        positions_stale = current_time - self.data_updates.get('positions', 0) if self.data_updates.get('positions', 0) else 0
        liquidation_stale = current_time - self.data_updates.get('liquidation', 0) if self.data_updates.get('liquidation', 0) else 0
        
        # Consider data healthy if at least one source is fresh
        # (More lenient - we don't want false positives)
        healthy = (
            volatility_stale < self.data_stale_threshold or
            positions_stale < self.data_stale_threshold or
            liquidation_stale < self.data_stale_threshold
        )
        
        return {
            'healthy': healthy,
            'volatility_stale_seconds': volatility_stale,
            'positions_stale_seconds': positions_stale,
            'liquidation_stale_seconds': liquidation_stale
        }
    
    def get_health_status(self) -> Dict:
        """
        Get comprehensive system health status.
        
        Returns:
            Dict with health metrics and overall system_healthy flag
        """
        if not self.enabled:
            return {
                'enabled': False,
                'system_healthy': True,
                'message': 'Health tracking disabled'
            }
        
        api_health = self.get_api_health()
        ws_health = self.get_websocket_health()
        data_health = self.get_data_freshness()
        
        # System is healthy if CRITICAL subsystems are healthy
        # WebSocket is NOT critical for Guardian (uses REST API)
        # Data freshness is NOT critical initially (no data yet is OK)
        system_healthy = (
            api_health['healthy'] and
            self.event_store_connected
        )
        
        # Identify issues
        issues = []
        if not api_health['healthy']:
            issues.append(f"API unhealthy (success rate: {api_health['success_rate']:.1f}%, failures: {api_health['consecutive_failures']})")
        
        # WebSocket is informational only (not critical for Guardian)
        if not ws_health['healthy']:
            if not ws_health['connected']:
                # Don't add to issues - WebSocket not required for Guardian
                pass
            else:
                issues.append(f"WebSocket data stale ({ws_health['stale_seconds']:.0f}s)")
        
        # Data freshness is informational initially (guardian just started)
        if not data_health['healthy']:
            # Only report if ALL data sources are very stale (>5 min)
            if (data_health['volatility_stale_seconds'] > 300 and
                data_health['positions_stale_seconds'] > 300 and
                data_health['liquidation_stale_seconds'] > 300):
                issues.append(f"All data very stale (>5 min)")
        
        if not self.event_store_connected:
            issues.append("Event store disconnected")
        
        # Exchange maintenance check (CRITICAL)
        if self.exchange_in_maintenance:
            issues.append("Exchange in maintenance mode")
            system_healthy = False  # Force unhealthy during maintenance
        
        return {
            'enabled': True,
            'system_healthy': system_healthy,
            'api': api_health,
            'websocket': ws_health,
            'data_freshness': data_health,
            'event_store_connected': self.event_store_connected,
            'exchange_in_maintenance': self.exchange_in_maintenance,
            'maintenance_status': self.maintenance_monitor.get_status() if self.maintenance_monitor else None,
            'issues': issues,
            'message': 'All systems operational' if system_healthy else f"Issues detected: {', '.join(issues)}"
        }
    
    def has_critical_issues(self) -> bool:
        """
        Check if there are critical system issues that should halt trading.
        
        This is the main method called by Guardian Layer 5.
        
        Returns:
            True if critical issues detected, False otherwise
        """
        if not self.enabled:
            return False  # Health tracking disabled = assume healthy (fail-safe)
        
        health = self.get_health_status()
        
        if not health['system_healthy']:
            log.warning(f"🚨 CRITICAL SYSTEM ISSUES DETECTED: {health['message']}")
            return True
        
        return False
    
    def get_summary(self) -> str:
        """Get human-readable health summary."""
        health = self.get_health_status()
        
        if not health['enabled']:
            return "Health tracking disabled"
        
        if health['system_healthy']:
            return f"✅ All systems healthy | API: {health['api']['success_rate']:.0f}% | WS: {'Connected' if health['websocket']['connected'] else 'Disconnected'}"
        else:
            return f"⚠️ System issues: {health['message']}"
