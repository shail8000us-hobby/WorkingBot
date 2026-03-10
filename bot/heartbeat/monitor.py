#!/usr/bin/env python3
# bot/heartbeat/monitor.py
"""
Heartbeat Monitor - External process that watches bot health
Cancels pending BUY orders if bot becomes unresponsive.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config

# Set up logging
log_dir = project_root / "bot" / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "heartbeat_monitor.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("heartbeat_monitor")


class HeartbeatMonitor:
    """
    Monitors bot heartbeat and takes action if bot crashes.
    
    Actions:
    - cancel_buy_orders: Cancel only pending BUY orders (default)
    - cancel_all_orders: Cancel all open orders
    - notify_only: Just send notification, don't cancel
    """
    
    def __init__(
        self,
        heartbeat_file: str = ".heartbeat",
        timeout: int = 15,
        check_interval: int = 10,
        action: str = "cancel_buy_orders"
    ):
        """
        Initialize monitor.
        
        Args:
            heartbeat_file: Path to heartbeat file to monitor
            timeout: How long to wait before considering bot crashed (seconds)
            check_interval: How often to check heartbeat (seconds)
            action: What to do on timeout (cancel_buy_orders, cancel_all_orders, notify_only)
        """
        self.heartbeat_file = Path(heartbeat_file)
        self.timeout = timeout
        self.check_interval = check_interval
        self.action = action
        self.running = True
        self.crash_detected = False
        self._missing_heartbeat_count = 0
        
        # Will be initialized later
        self.exchange = None
        self.symbol_ccxt = None
        self.notifier = None
        
        log.info("=" * 60)
        log.info("🔍 Heartbeat Monitor Starting")
        log.info("=" * 60)
        log.info(f"Heartbeat file: {self.heartbeat_file}")
        log.info(f"Timeout: {timeout}s")
        log.info(f"Check interval: {check_interval}s")
        log.info(f"Action on timeout: {action}")
        log.info("=" * 60)
    
    def _init_exchange(self):
        """Initialize exchange connection (lazy loading) - uses native DeltaClient."""
        if self.exchange is not None:
            return
        
        try:
            from dotenv import load_dotenv
            from bot.utils.env_loader import load_trading_mode_config, get_mode_display_info
            from bot.api.delta_client import DeltaClient
            
            # Load API credentials from secrets
            load_dotenv(project_root / "secrets" / "api_keys.env", verbose=False)
            
            # Load and configure trading mode
            try:
                trading_mode = load_trading_mode_config()
                mode_info = get_mode_display_info()
                
                log.info("")
                log.info("=" * 60)
                log.info(f"{mode_info['emoji']} MONITOR - TRADING MODE: {mode_info['description']}")
                log.info(f"API URL: {mode_info['api_url']}")
                log.info("=" * 60)
                log.info("")
            except Exception as e:
                log.error(f"❌ Failed to load trading mode: {e}")
                raise
            
            cfg = get_config()
            symbol = cfg.bot.symbol
            
            # Get product_id from API config based on trading mode
            if cfg.trading_mode.value == 'demo':
                product_id = cfg.api.demo.product_id
            else:
                product_id = cfg.api.live.product_id
            
            # Initialize native Delta client
            self.exchange = DeltaClient()
            self.symbol_ccxt = symbol
            self.product_id = product_id
            
            log.info(f"✅ Exchange initialized: {symbol} (Product ID: {product_id}) using DeltaClient (config: YAML)")
            
        except Exception as e:
            log.error(f"Failed to initialize exchange: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise
    
    def _init_notifier(self):
        """Initialize Telegram notifier (lazy loading)."""
        if self.notifier is not None:
            return
        
        try:
            from bot.utils.notifier import TelegramNotifier
            self.notifier = TelegramNotifier()
            if self.notifier.enabled:
                log.info("✅ Telegram notifier initialized")
        except Exception as e:
            log.warning(f"Telegram notifier not available: {e}")
            # Create dummy notifier
            class DummyNotifier:
                enabled = False
                def send(self, *args, **kwargs): pass
            self.notifier = DummyNotifier()
    
    def _read_heartbeat(self) -> dict:
        """Read heartbeat file."""
        if not self.heartbeat_file.exists():
            raise FileNotFoundError(f"Heartbeat file not found: {self.heartbeat_file}")
        
        with open(self.heartbeat_file, 'r') as f:
            return json.load(f)
    
    def _check_heartbeat(self) -> bool:
        """
        Check if heartbeat is fresh.
        
        Returns:
            True if bot is healthy, False if timed out
        """
        try:
            data = self._read_heartbeat()
            timestamp = data.get('timestamp', 0)
            status = data.get('status', 'unknown')
            pid = data.get('pid', 'unknown')
            
            age = time.time() - timestamp
            
            log.debug(f"Heartbeat age: {age:.1f}s (status={status}, pid={pid})")
            
            if age > self.timeout:
                log.warning(f"⚠️  Heartbeat timeout! Age: {age:.1f}s > {self.timeout}s")
                return False

            self._missing_heartbeat_count = 0
            return True
            
        except FileNotFoundError:
            self._missing_heartbeat_count += 1
            if self._missing_heartbeat_count >= 3:
                log.warning(f"⚠️  Heartbeat file missing for {self._missing_heartbeat_count} consecutive checks — treating as unhealthy")
                return False
            log.warning("⚠️  Heartbeat file not found - bot may not be running yet")
            return True
        except Exception as e:
            log.error(f"Error reading heartbeat: {e}")
            return True  # Don't take action on read errors
    
    def _cancel_buy_orders(self):
        """Cancel only pending BUY orders (not TP orders)."""
        try:
            self._init_exchange()
            
            log.info("🔍 Fetching open orders...")
            orders = self.exchange.fetch_open_orders(self.symbol_ccxt)
            
            if not orders:
                log.info("No open orders found")
                return
            
            # Filter for BUY orders (not reduce_only)
            buy_orders = []
            tp_orders = []
            
            for order in orders:
                side = order.get('side', '').lower()
                reduce_only = order.get('reduceOnly', False) or order.get('reduce_only', False)
                
                if side == 'buy' and not reduce_only:
                    buy_orders.append(order)
                elif side == 'sell' and reduce_only:
                    tp_orders.append(order)
            
            log.info(f"📊 Found: {len(buy_orders)} BUY orders, {len(tp_orders)} TP orders")
            
            # Cancel BUY orders
            cancelled = 0
            for order in buy_orders:
                try:
                    order_id = order['id']
                    price = order.get('price', 'market')
                    self.exchange.cancel_order(order_id, self.symbol_ccxt)
                    log.info(f"✅ Cancelled BUY order: {order_id} @ {price}")
                    cancelled += 1
                except Exception as e:
                    log.error(f"Failed to cancel order {order.get('id')}: {e}")
            
            # Summary
            log.info("=" * 60)
            log.info(f"🎯 Action Summary:")
            log.info(f"   Cancelled BUY orders: {cancelled}")
            log.info(f"   Kept TP orders: {len(tp_orders)} (positions protected)")
            log.info("=" * 60)
            
            # Send notification
            self._init_notifier()
            message = (
                f"🚨 BOT CRASH DETECTED!\n\n"
                f"Heartbeat Monitor took action:\n"
                f"✅ Cancelled {cancelled} pending BUY order(s)\n"
                f"✅ Kept {len(tp_orders)} TP order(s) active\n\n"
                f"Existing positions remain protected.\n"
                f"Please investigate and restart bot."
            )
            self.notifier.send(message)
            
        except Exception as e:
            log.error(f"Error cancelling orders: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    def _cancel_all_orders(self):
        """Cancel ALL open orders."""
        try:
            self._init_exchange()
            
            log.info("🔍 Fetching all open orders...")
            orders = self.exchange.fetch_open_orders(self.symbol_ccxt)
            
            if not orders:
                log.info("No open orders found")
                return
            
            log.info(f"📊 Found {len(orders)} open order(s)")
            
            # Cancel all
            cancelled = 0
            for order in orders:
                try:
                    order_id = order['id']
                    self.exchange.cancel_order(order_id, self.symbol_ccxt)
                    log.info(f"✅ Cancelled order: {order_id}")
                    cancelled += 1
                except Exception as e:
                    log.error(f"Failed to cancel order {order.get('id')}: {e}")
            
            log.info(f"✅ Cancelled {cancelled} order(s)")
            
            # Send notification
            self._init_notifier()
            message = (
                f"🚨 BOT CRASH DETECTED!\n\n"
                f"Heartbeat Monitor cancelled ALL {cancelled} open order(s).\n\n"
                f"Please investigate and restart bot."
            )
            self.notifier.send(message)
            
        except Exception as e:
            log.error(f"Error cancelling orders: {e}")
    
    def _notify_only(self):
        """Just send notification, don't cancel orders."""
        log.warning("⚠️  Notify-only mode - not cancelling orders")
        
        self._init_notifier()
        message = (
            f"⚠️ BOT HEARTBEAT TIMEOUT\n\n"
            f"Bot appears to be unresponsive.\n"
            f"Monitor is in notify-only mode - no orders cancelled.\n\n"
            f"Please check bot status."
        )
        self.notifier.send(message)
    
    def _take_action(self):
        """Take configured action on heartbeat timeout."""
        log.warning("=" * 60)
        log.warning("🚨 BOT CRASH DETECTED - TAKING ACTION")
        log.warning("=" * 60)
        
        if self.action == "cancel_buy_orders":
            self._cancel_buy_orders()
        elif self.action == "cancel_all_orders":
            self._cancel_all_orders()
        elif self.action == "notify_only":
            self._notify_only()
        else:
            log.error(f"Unknown action: {self.action}")
        
        log.warning("=" * 60)
    
    def run(self):
        """Main monitor loop."""
        log.info("✅ Monitor started - watching bot health...")
        log.info("")
        
        try:
            while self.running:
                # Check heartbeat
                is_healthy = self._check_heartbeat()
                
                if not is_healthy and not self.crash_detected:
                    # First detection of crash
                    self.crash_detected = True
                    self._take_action()
                    log.info("Action complete - continuing to monitor for further crashes")
                
                elif is_healthy and self.crash_detected:
                    # Bot recovered
                    log.info("✅ Bot heartbeat resumed - cancelling crash state")
                    self.crash_detected = False
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            log.info("\n🛑 Monitor stopped by user")
        except Exception as e:
            log.error(f"Monitor error: {e}")
            import traceback
            log.error(traceback.format_exc())
        finally:
            log.info("Monitor shutdown complete")


def main():
    """Main entry point."""
    # Get config from YAML
    cfg = get_config()
    enabled = cfg.monitoring.heartbeat.enabled
    
    if not enabled:
        log.info("Heartbeat monitoring is disabled in config")
        return
    
    heartbeat_file = cfg.monitoring.heartbeat.file
    timeout = cfg.monitoring.heartbeat.timeout
    check_interval = cfg.monitoring.heartbeat.check_interval
    action = cfg.monitoring.heartbeat.action
    
    # Create and run monitor
    monitor = HeartbeatMonitor(
        heartbeat_file=heartbeat_file,
        timeout=timeout,
        check_interval=check_interval,
        action=action
    )
    
    monitor.run()


if __name__ == "__main__":
    main()

