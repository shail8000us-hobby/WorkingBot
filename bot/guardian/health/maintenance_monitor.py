"""
Delta Exchange Maintenance Monitor
===================================

Monitors exchange maintenance announcements via WebSocket and
automatically halts trading during maintenance periods.

Author: Guardian Safety System
Version: 1.0.0
Date: 2025-12-26
"""

import json
import time
import logging
import threading
from typing import Optional, Callable
from datetime import datetime

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

log = logging.getLogger(__name__)


class DeltaMaintenanceMonitor:
    """
    Monitors Delta Exchange maintenance announcements and updates system health.
    
    Subscribes to Delta Exchange announcements WebSocket channel to receive:
    - maintenance_scheduled (6-24 hours before)
    - maintenance_started (when maintenance begins)
    - maintenance_finished (when maintenance ends)
    """
    
    def __init__(self, health_tracker=None, websocket_url: str = "wss://socket.india.delta.exchange"):
        """
        Initialize maintenance monitor.
        
        Args:
            health_tracker: SystemHealthTracker instance to update
            websocket_url: Delta Exchange WebSocket URL
        """
        self.websocket_url = websocket_url
        self.health_tracker = health_tracker
        
        # Maintenance state
        self.is_maintenance_mode = False
        self.maintenance_scheduled = False
        self.scheduled_start_time = None
        self.scheduled_finish_time = None
        self.maintenance_start_time = None
        self.estimated_finish_time = None
        
        # WebSocket connection
        self.ws = None
        self.is_connected = False
        self.heartbeat_timer = None
        self.heartbeat_interval = 30  # Send heartbeat every 30s
        self.heartbeat_timeout = 35   # Timeout if no pong in 35s
        self.last_pong_time = time.time()
        
        # Reconnection
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Callbacks
        self.on_scheduled_callback: Optional[Callable] = None
        self.on_started_callback: Optional[Callable] = None
        self.on_finished_callback: Optional[Callable] = None
        
        # Thread control
        self.ws_thread = None
        self.running = False
        
        if not WEBSOCKET_AVAILABLE:
            log.warning("⚠️ websocket-client not installed - maintenance monitoring disabled")
            log.warning("   Install: pip install websocket-client")
    
    def set_callbacks(self, on_scheduled=None, on_started=None, on_finished=None):
        """Set callbacks for maintenance events."""
        self.on_scheduled_callback = on_scheduled
        self.on_started_callback = on_started
        self.on_finished_callback = on_finished
    
    def on_open(self, ws):
        """Handle WebSocket connection open."""
        log.info("✅ Connected to Delta Exchange announcements channel")
        self.is_connected = True
        self.reconnect_attempts = 0
        
        # Subscribe to announcements channel (public, no auth required)
        subscribe_msg = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "announcements"
                    }
                ]
            }
        }
        
        ws.send(json.dumps(subscribe_msg))
        log.info("📡 Subscribed to maintenance announcements")
        
        # Start heartbeat
        self.start_heartbeat()
        
        # Update health tracker
        if self.health_tracker:
            self.health_tracker.record_websocket_connect()
    
    def on_message(self, ws, message):
        """Handle WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # Handle heartbeat responses
            if msg_type == "pong":
                self.last_pong_time = time.time()
                return
            
            # Handle subscription confirmation
            if msg_type == "subscriptions":
                log.info(f"✅ Subscription confirmed: {data}")
                return
            
            # Handle announcements
            if msg_type == "announcements":
                event = data.get("event")
                
                if event == "maintenance_scheduled":
                    self._handle_maintenance_scheduled(data)
                elif event == "maintenance_started":
                    self._handle_maintenance_started(data)
                elif event == "maintenance_finished":
                    self._handle_maintenance_finished(data)
                else:
                    log.info(f"📢 Announcement: {data}")
            
            # Update health tracker with any message
            if self.health_tracker:
                self.health_tracker.record_websocket_update("maintenance_announcements")
                
        except json.JSONDecodeError:
            log.error(f"Failed to parse message: {message}")
        except Exception as e:
            log.error(f"Error handling message: {e}", exc_info=True)
    
    def _handle_maintenance_scheduled(self, data):
        """Handle maintenance_scheduled event (6-24 hours before)."""
        start_time_us = data.get("maintenance_start_time")
        finish_time_us = data.get("maintenance_finish_time")
        
        # Convert microseconds to datetime
        start_dt = datetime.fromtimestamp(start_time_us / 1_000_000) if start_time_us else None
        finish_dt = datetime.fromtimestamp(finish_time_us / 1_000_000) if finish_time_us else None
        
        self.maintenance_scheduled = True
        self.scheduled_start_time = start_dt
        self.scheduled_finish_time = finish_dt
        
        log.warning("="*80)
        log.warning("🚨 MAINTENANCE SCHEDULED")
        log.warning(f"   Start Time:  {start_dt}")
        log.warning(f"   Finish Time: {finish_dt}")
        log.warning("="*80)
        
        # Call callback if set
        if self.on_scheduled_callback:
            try:
                self.on_scheduled_callback(start_dt, finish_dt)
            except Exception as e:
                log.error(f"Error in scheduled callback: {e}")
    
    def _handle_maintenance_started(self, data):
        """Handle maintenance_started event (when maintenance begins)."""
        finish_time_us = data.get("maintenance_finish_time")
        timestamp_us = data.get("timestamp")
        
        # Convert microseconds to datetime
        finish_dt = datetime.fromtimestamp(finish_time_us / 1_000_000) if finish_time_us else None
        start_dt = datetime.fromtimestamp(timestamp_us / 1_000_000) if timestamp_us else datetime.now()
        
        self.is_maintenance_mode = True
        self.maintenance_start_time = start_dt
        self.estimated_finish_time = finish_dt
        
        log.critical("="*80)
        log.critical("🔴 EXCHANGE MAINTENANCE STARTED - TRADING HALTED")
        log.critical(f"   Started:  {start_dt}")
        log.critical(f"   Expected Finish: {finish_dt}")
        log.critical("="*80)
        
        # Call callback if set
        if self.on_started_callback:
            try:
                self.on_started_callback(start_dt, finish_dt)
            except Exception as e:
                log.error(f"Error in started callback: {e}")
    
    def _handle_maintenance_finished(self, data):
        """Handle maintenance_finished event (when maintenance ends)."""
        timestamp_us = data.get("timestamp")
        finish_dt = datetime.fromtimestamp(timestamp_us / 1_000_000) if timestamp_us else datetime.now()
        
        self.is_maintenance_mode = False
        self.maintenance_scheduled = False
        self.maintenance_start_time = None
        self.estimated_finish_time = None
        
        log.warning("="*80)
        log.warning("🟢 EXCHANGE MAINTENANCE FINISHED")
        log.warning(f"   Finished: {finish_dt}")
        log.warning("   Trading can resume (after market stabilization)")
        log.warning("="*80)
        
        # Call callback if set
        if self.on_finished_callback:
            try:
                self.on_finished_callback(finish_dt)
            except Exception as e:
                log.error(f"Error in finished callback: {e}")
    
    def start_heartbeat(self):
        """Start sending heartbeat pings."""
        def send_heartbeat():
            if self.ws and self.is_connected:
                try:
                    # Check if we got pong recently
                    if time.time() - self.last_pong_time > self.heartbeat_timeout:
                        log.warning("⚠️ Heartbeat timeout - connection may be dead")
                        self.ws.close()
                        return
                    
                    # Send ping
                    ping_msg = {"type": "ping"}
                    self.ws.send(json.dumps(ping_msg))
                    
                    # Schedule next heartbeat
                    self.heartbeat_timer = threading.Timer(self.heartbeat_interval, send_heartbeat)
                    self.heartbeat_timer.daemon = True
                    self.heartbeat_timer.start()
                except Exception as e:
                    log.error(f"Error sending heartbeat: {e}")
        
        # Start first heartbeat
        send_heartbeat()
    
    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        log.error(f"❌ WebSocket error: {error}")
        
        # Update health tracker
        if self.health_tracker:
            self.health_tracker.record_websocket_disconnect()
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        log.warning(f"🔌 WebSocket closed - Status: {close_status_code}, Message: {close_msg}")
        
        self.is_connected = False
        
        # Cancel heartbeat timer
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
        
        # Update health tracker
        if self.health_tracker:
            self.health_tracker.record_websocket_disconnect()
        
        # Attempt to reconnect if still running
        if self.running:
            self.reconnect()
    
    def reconnect(self):
        """Attempt to reconnect to WebSocket."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            log.critical(f"🚨 Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return
        
        self.reconnect_attempts += 1
        wait_time = min(2 ** self.reconnect_attempts, 60)  # Exponential backoff, max 60s
        
        log.info(f"🔄 Reconnecting in {wait_time}s... (Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        time.sleep(wait_time)
        
        if self.running:
            self._start_websocket()
    
    def _start_websocket(self):
        """Internal method to start WebSocket connection."""
        if not WEBSOCKET_AVAILABLE:
            log.error("Cannot start - websocket-client not installed")
            return
        
        try:
            self.ws = websocket.WebSocketApp(
                self.websocket_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Run in blocking mode (should be in a thread)
            self.ws.run_forever()
        except Exception as e:
            log.error(f"Error starting WebSocket: {e}")
    
    def start(self):
        """Start the maintenance monitor in a background thread."""
        if not WEBSOCKET_AVAILABLE:
            log.warning("⚠️ Maintenance monitor disabled - websocket-client not installed")
            return
        
        if self.running:
            log.warning("Maintenance monitor already running")
            return
        
        log.info("🚀 Starting Delta Exchange Maintenance Monitor...")
        self.running = True
        
        # Start WebSocket in a daemon thread
        self.ws_thread = threading.Thread(target=self._start_websocket, daemon=True)
        self.ws_thread.start()
        
        log.info("✅ Maintenance monitor started (background thread)")
    
    def stop(self):
        """Stop the maintenance monitor."""
        log.info("🛑 Stopping maintenance monitor...")
        self.running = False
        
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
        
        if self.ws:
            self.ws.close()
        
        log.info("✅ Maintenance monitor stopped")
    
    def get_status(self) -> dict:
        """Get current maintenance status."""
        return {
            'is_connected': self.is_connected,
            'is_maintenance_mode': self.is_maintenance_mode,
            'maintenance_scheduled': self.maintenance_scheduled,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'scheduled_finish_time': self.scheduled_finish_time.isoformat() if self.scheduled_finish_time else None,
            'maintenance_start_time': self.maintenance_start_time.isoformat() if self.maintenance_start_time else None,
            'estimated_finish_time': self.estimated_finish_time.isoformat() if self.estimated_finish_time else None,
            'websocket_available': WEBSOCKET_AVAILABLE
        }


# Example standalone usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = DeltaMaintenanceMonitor()
    
    # Set callbacks (optional)
    def on_scheduled(start_time, finish_time):
        print(f"🔔 Prepare for maintenance: {start_time} - {finish_time}")
    
    def on_started(start_time, finish_time):
        print(f"🚨 HALT ALL TRADING - Maintenance started!")
    
    def on_finished(finish_time):
        print(f"✅ Maintenance finished - Can resume trading")
    
    monitor.set_callbacks(
        on_scheduled=on_scheduled,
        on_started=on_started,
        on_finished=on_finished
    )
    
    try:
        monitor.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        monitor.stop()
