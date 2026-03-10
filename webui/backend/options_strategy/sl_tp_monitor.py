"""
Background monitoring service for Stop-Loss and Take-Profit
Runs continuously and checks positions every 5 seconds

Created: January 14, 2026
"""

import time
import threading
import logging
from typing import Dict, List, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SLTPMonitor:
    """Background service to monitor SL/TP triggers"""
    
    def __init__(self, check_interval: int = 5):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.last_check = None
        self.trigger_callbacks: List[Callable] = []
        self.api_client = None
        self.sl_tp_manager = None
        self._triggers_fired = set()  # Track fired triggers to avoid duplicates
        # Dedicated event loop for this monitor's async calls.
        # Using a per-instance loop (instead of asyncio.get_event_loop()) avoids
        # the "This event loop is already running" error under eventlet, and ensures
        # the httpx.AsyncClient stays bound to a single consistent loop.
        self._loop = asyncio.new_event_loop()
    
    def set_dependencies(self, api_client, sl_tp_manager):
        """Set dependencies (called after initialization)"""
        self.api_client = api_client
        self.sl_tp_manager = sl_tp_manager
        logger.info("SL/TP monitor dependencies set")
    
    def start(self):
        """Start the monitoring service"""
        if self.running:
            logger.warning("SL/TP monitor already running")
            return False
        
        if not self.api_client or not self.sl_tp_manager:
            logger.error("Cannot start SL/TP monitor: dependencies not set")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info(f"SL/TP monitor started (check interval: {self.check_interval}s)")
        return True
    
    def stop(self):
        """Stop the monitoring service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("SL/TP monitor stopped")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.running
    
    def add_trigger_callback(self, callback: Callable):
        """Add callback function to be called when SL/TP triggers"""
        self.trigger_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """Get monitor status"""
        return {
            "running": self.running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_interval": self.check_interval,
            "triggers_fired_count": len(self._triggers_fired)
        }
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("SL/TP monitor loop started")
        
        while self.running:
            try:
                self._check_all_positions()
                self.last_check = datetime.now()
            except Exception as e:
                logger.error(f"Error in SL/TP monitor loop: {e}", exc_info=True)
            
            time.sleep(self.check_interval)
        
        logger.info("SL/TP monitor loop ended")
    
    def _check_all_positions(self):
        """Check all positions for SL/TP triggers"""
        try:
            # Get all active SL/TP settings
            all_settings = self.sl_tp_manager.get_all_active_sl_tp()
            
            if not all_settings:
                return
            
            # Get current positions
            positions = self._get_positions()
            if not positions:
                return
            
            # Create position lookup
            position_map = {p.get('product_symbol'): p for p in positions}
            
            # Check each SL/TP setting
            for settings in all_settings:
                symbol = settings.get('symbol')
                position = position_map.get(symbol)
                
                if not position:
                    # Position might be closed, skip
                    continue
                
                # Skip if already triggered (avoid duplicate triggers)
                trigger_key = f"{symbol}_{settings.get('updated_at')}"
                if trigger_key in self._triggers_fired:
                    continue
                
                # Get position data
                current_price = position.get('mid_price') or position.get('mark_price', 0)
                entry_price = position.get('entry_price', 0)
                pnl_pct = position.get('pnl_percentage', 0)
                
                if current_price <= 0 or entry_price <= 0:
                    continue
                
                # Check for triggers
                trigger = self.sl_tp_manager.check_triggers(
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct
                )
                
                if trigger:
                    self._handle_trigger(trigger, position)
                    self._triggers_fired.add(trigger_key)
                    
        except Exception as e:
            logger.error(f"Error checking positions: {e}", exc_info=True)
    
    def _get_positions(self) -> List[Dict]:
        """Get current options positions via internal HTTP endpoint (avoids asyncio+eventlet conflicts)."""
        try:
            import requests
            response = requests.get(
                "http://localhost:5555/api/options/positions",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('positions', [])
            logger.error(f"HTTP fetch failed: {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}", exc_info=True)
            return []
    
    def _handle_trigger(self, trigger: Dict, position: Dict):
        """Handle SL/TP trigger"""
        symbol = trigger.get('symbol')
        trigger_type = trigger.get('type')
        reason = trigger.get('reason')
        auto_execute = trigger.get('auto_execute', True)
        alert_only = trigger.get('alert_only', False)
        
        logger.warning(f"🚨 SL/TP TRIGGERED: {symbol} - {trigger_type}: {reason}")
        
        # Add to history
        self.sl_tp_manager.add_history(
            symbol=symbol,
            trigger_type=trigger_type,
            trigger_price=trigger.get('current_price', 0),
            position_size=position.get('size', 0),
            pnl=position.get('unrealized_pnl', 0),
            pnl_pct=position.get('pnl_percentage', 0),
            executed=False
        )
        
        # Call registered callbacks
        for callback in self.trigger_callbacks:
            try:
                callback(trigger, position)
            except Exception as e:
                logger.error(f"Error in trigger callback: {e}")
        
        # Execute if auto_execute and not alert_only
        if auto_execute and not alert_only:
            self._execute_close(symbol, position, trigger)
    
    def _execute_close(self, symbol: str, position: Dict, trigger: Dict):
        """Execute position close"""
        try:
            logger.info(f"Auto-executing close for {symbol} due to {trigger.get('type')}")
            
            # Import here to avoid circular imports
            from webui.backend.routes.options.options_control import execute_close_order
            
            result = execute_close_order(symbol, order_preference='market_only')
            
            if result.get('success'):
                logger.info(f"✅ Successfully closed {symbol} - Order ID: {result.get('order_id')}")
                
                # Update history with execution info
                self.sl_tp_manager.mark_triggered(symbol, trigger.get('type'))
                
                # Update the last history entry with execution info
                conn = self.sl_tp_manager._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sl_tp_history 
                    SET executed = 1, execution_order_id = ?
                    WHERE symbol = ? 
                    ORDER BY id DESC LIMIT 1
                """, (result.get('order_id'), symbol))
                conn.commit()
                conn.close()
            else:
                logger.error(f"❌ Failed to close {symbol}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error executing close for {symbol}: {e}", exc_info=True)


# Singleton instance
_sl_tp_monitor = None

def get_sl_tp_monitor() -> SLTPMonitor:
    """Get singleton SL/TP monitor instance"""
    global _sl_tp_monitor
    if _sl_tp_monitor is None:
        _sl_tp_monitor = SLTPMonitor()
    return _sl_tp_monitor


def init_sl_tp_monitoring(api_client, sl_tp_manager, auto_start: bool = True) -> SLTPMonitor:
    """Initialize and optionally start the SL/TP monitor"""
    monitor = get_sl_tp_monitor()
    monitor.set_dependencies(api_client, sl_tp_manager)
    
    if auto_start:
        monitor.start()
    
    return monitor
