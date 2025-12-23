"""
WebSocketHandler - WebSocket Event Routing Module

Single Responsibility: Route WebSocket events to appropriate handlers

This module handles all WebSocket callback setup and event routing.
It acts as an adapter between the WebSocket manager and the GridBot logic.

Extracted from GridBotWebSocket (Phase 2 - Event routing)
"""

import logging
import threading
import time
from typing import Dict, Callable, Optional, Any

log = logging.getLogger("runner")


class WebSocketHandler:
    """
    WebSocket event routing and callback management
    
    Responsibilities:
    - Setup WebSocket callbacks
    - Route price updates to price handler
    - Route order updates to order handler
    - Route position updates to position handler
    - Route fill events to fill detector
    - Handle liquidation/emergency alerts
    
    NOT Responsible For:
    - WebSocket connection management (WS Manager handles this)
    - Business logic (delegates to other modules)
    - State management (delegates to PositionManager)
    """
    
    def __init__(
        self,
        ws_manager: Any,
        liquidation_monitor: Optional[Any] = None
    ):
        """
        Initialize WebSocket event handler
        
        Args:
            ws_manager: WebSocket manager instance
            liquidation_monitor: Optional liquidation monitoring system
        """
        # Validate WebSocket manager has required methods
        required_methods = ['on_price_update', 'on_fill']
        optional_methods = ['on_order_update', 'on_position_update']
        
        for method in required_methods:
            if not hasattr(ws_manager, method):
                raise ValueError(f"❌ WebSocket manager missing required method: {method}")
        
        # Store which optional methods are available
        self._available_methods = {}
        for method in optional_methods:
            self._available_methods[method] = hasattr(ws_manager, method)
            if self._available_methods[method]:
                log.debug(f"✅ Optional method available: {method}")
            else:
                log.debug(f"⚠️ Optional method not available: {method}")
        
        self.ws_manager = ws_manager
        self.liquidation_monitor = liquidation_monitor
        
        # Callback storage
        self._price_update_callback: Optional[Callable] = None
        self._fill_callback: Optional[Callable] = None
        self._order_update_callback: Optional[Callable] = None
        self._position_update_callback: Optional[Callable] = None
        self._liquidation_callback: Optional[Callable] = None
        self._emergency_callback: Optional[Callable] = None
        
        # Callback execution tracking
        self._callback_stats = {
            'price_updates': 0,
            'price_update_errors': 0,
            'fills': 0,
            'fill_errors': 0,
            'order_updates': 0,
            'order_update_errors': 0,
            'position_updates': 0,
            'position_update_errors': 0,
            'total_errors': 0
        }
        
        # Circuit breaker for failing callbacks
        self._callback_failures = {}
        self._max_failures = 5
        self._failure_reset_time = 300  # 5 minutes
        self._circuit_breaker_lock = threading.Lock()  # Thread safety for circuit breaker
    
    def _validate_callback(self, callback: Optional[Callable], name: str) -> bool:
        """
        Validate callback is callable
        
        Args:
            callback: Callback function to validate
            name: Callback name for error messages
            
        Returns:
            True if callback is valid (None or callable), False otherwise
        """
        if callback is None:
            return True  # Optional callbacks allowed
        
        if not callable(callback):
            log.error(f"❌ Invalid callback for {name}: not callable")
            return False
        return True
    
    def _is_callback_circuit_broken(self, callback_name: str) -> bool:
        """
        Check if callback is circuit broken due to too many failures (thread-safe with lazy cleanup)
        
        Args:
            callback_name: Name of callback to check
            
        Returns:
            True if circuit is broken (too many recent failures)
        """
        now = time.time()
        
        with self._circuit_breaker_lock:
            if callback_name not in self._callback_failures:
                return False
            
            failures = self._callback_failures[callback_name]
            
            # Only cleanup if we have old failures (lazy cleanup for efficiency)
            if failures and (now - failures[0]) > self._failure_reset_time:
                recent_failures = [f for f in failures if now - f < self._failure_reset_time]
                self._callback_failures[callback_name] = recent_failures
            else:
                recent_failures = failures
            
            is_broken = len(recent_failures) >= self._max_failures
            
            if is_broken:
                log.warning(f"⚠️ Circuit breaker OPEN for {callback_name}: "
                           f"{len(recent_failures)} failures in {self._failure_reset_time}s")
            
            return is_broken
    
    def _record_callback_failure(self, callback_name: str):
        """
        Record callback failure for circuit breaker (thread-safe)
        
        Args:
            callback_name: Name of callback that failed
        """
        with self._circuit_breaker_lock:
            if callback_name not in self._callback_failures:
                self._callback_failures[callback_name] = []
            
            self._callback_failures[callback_name].append(time.time())
    
    def setup_callbacks(
        self,
        on_price_update: Callable[[Dict], None],
        on_fill: Callable[[Dict], None],
        on_order_update: Optional[Callable[[Dict], None]] = None,
        on_position_update: Optional[Callable[[Dict], None]] = None,
        on_liquidation: Optional[Callable[[str, str, Dict], None]] = None,
        on_emergency: Optional[Callable[[str, Dict], None]] = None
    ):
        """
        Register callbacks for WebSocket events with validation
        
        Args:
            on_price_update: Callback for price updates (ticker data)
            on_fill: Callback for fill detection (critical for capital protection)
            on_order_update: Optional callback for order state changes
            on_position_update: Optional callback for position updates
            on_liquidation: Optional callback for liquidation alerts (level, message, status)
            on_emergency: Optional callback for emergency alerts (message, status)
        """
        # Validate required callbacks
        if not self._validate_callback(on_price_update, "price_update"):
            raise ValueError("Invalid price_update callback - must be callable")
        if not self._validate_callback(on_fill, "fill"):
            raise ValueError("Invalid fill callback - must be callable")
        
        # Validate optional callbacks
        if not self._validate_callback(on_order_update, "order_update"):
            raise ValueError("Invalid order_update callback - must be callable or None")
        if not self._validate_callback(on_position_update, "position_update"):
            raise ValueError("Invalid position_update callback - must be callable or None")
        if not self._validate_callback(on_liquidation, "liquidation"):
            raise ValueError("Invalid liquidation callback - must be callable or None")
        if not self._validate_callback(on_emergency, "emergency"):
            raise ValueError("Invalid emergency callback - must be callable or None")
        
        # Store callbacks
        self._price_update_callback = on_price_update
        self._fill_callback = on_fill
        self._order_update_callback = on_order_update
        self._position_update_callback = on_position_update
        self._liquidation_callback = on_liquidation
        self._emergency_callback = on_emergency
        
        # Register with WebSocket manager with error handling
        try:
            self.ws_manager.on_price_update(self._handle_price_update)
            log.info("   ✅ Price update callback registered")
            
            self.ws_manager.on_fill(self._handle_fill)
            log.info("   ✅ Fill callback registered")
            
            if on_order_update and self._available_methods.get('on_order_update', False):
                self.ws_manager.on_order_update(self._handle_order_update)
                log.info("   ✅ Order update callback registered")
            elif on_order_update:
                log.warning("   ⚠️ Order update callback provided but WebSocket manager doesn't support it")
            
            if on_position_update and self._available_methods.get('on_position_update', False):
                self.ws_manager.on_position_update(self._handle_position_update)
                log.info("   ✅ Position update callback registered")
            elif on_position_update:
                log.warning("   ⚠️ Position update callback provided but WebSocket manager doesn't support it")
            
        except Exception as e:
            log.error(f"❌ Failed to register callbacks with WebSocket manager: {e}")
            raise
        
        log.info("📡 WebSocket callbacks registered successfully")
        log.info(f"   Statistics tracking enabled - current: {self._callback_stats}")
    
    def cleanup(self):
        """Cleanup callbacks and unregister from WebSocket manager"""
        log.info("🧹 Cleaning up WebSocket handler...")
        
        # Unregister from WebSocket manager if it has cleanup methods
        try:
            if hasattr(self.ws_manager, 'remove_price_callback'):
                self.ws_manager.remove_price_callback(self._handle_price_update)
                log.info("   ✅ Price callback unregistered")
            
            if hasattr(self.ws_manager, 'remove_fill_callback'):
                self.ws_manager.remove_fill_callback(self._handle_fill)
                log.info("   ✅ Fill callback unregistered")
            
            if hasattr(self.ws_manager, 'remove_order_callback'):
                self.ws_manager.remove_order_callback(self._handle_order_update)
                log.info("   ✅ Order callback unregistered")
            
            if hasattr(self.ws_manager, 'remove_position_callback'):
                self.ws_manager.remove_position_callback(self._handle_position_update)
                log.info("   ✅ Position callback unregistered")
                
        except Exception as e:
            log.warning(f"⚠️ Error during WebSocket manager cleanup: {e}")
        
        # Clear all callbacks
        self._price_update_callback = None
        self._fill_callback = None
        self._order_update_callback = None
        self._position_update_callback = None
        self._liquidation_callback = None
        self._emergency_callback = None
        
        log.info(f"✅ WebSocket handler cleanup completed - Final stats: {self._callback_stats}")
    
    def get_stats(self) -> Dict:
        """Get callback execution statistics"""
        return self._callback_stats.copy()
    
    def reset_circuit_breaker(self, callback_name: str):
        """
        Manually reset circuit breaker for a specific callback (thread-safe)
        
        Args:
            callback_name: Name of callback to reset
        """
        with self._circuit_breaker_lock:
            if callback_name in self._callback_failures:
                del self._callback_failures[callback_name]
                log.info(f"✅ Circuit breaker reset for {callback_name}")
            else:
                log.info(f"ℹ️ No failures to reset for {callback_name}")
    
    def get_circuit_breaker_status(self) -> Dict:
        """
        Get current circuit breaker status for all callbacks (thread-safe)
        
        Returns:
            Dict with status of each callback's circuit breaker
        """
        with self._circuit_breaker_lock:
            status = {}
            now = time.time()
            
            for callback_name in ['price_update', 'fill', 'order_update', 'position_update']:
                failures = self._callback_failures.get(callback_name, [])
                
                # Calculate if broken without calling _is_callback_circuit_broken (avoid double lock)
                recent_failures = [f for f in failures if now - f < self._failure_reset_time]
                is_broken = len(recent_failures) >= self._max_failures
                
                status[callback_name] = {
                    'is_broken': is_broken,
                    'failure_count': len(failures),
                    'recent_failure_count': len(recent_failures)
                }
            
            return status
    
    def validate_callbacks(self) -> Dict:
        """
        Validate that all registered callbacks are still callable
        
        Returns:
            Dict with validation results for each callback
        """
        results = {}
        
        callbacks_to_check = {
            'price_update': self._price_update_callback,
            'fill': self._fill_callback,
            'order_update': self._order_update_callback,
            'position_update': self._position_update_callback,
            'liquidation': self._liquidation_callback,
            'emergency': self._emergency_callback
        }
        
        for name, callback in callbacks_to_check.items():
            if callback is None:
                results[name] = {'valid': True, 'reason': 'Not registered (optional)'}
            elif callable(callback):
                results[name] = {'valid': True, 'reason': 'Callable'}
            else:
                results[name] = {'valid': False, 'reason': 'Not callable'}
                log.error(f"❌ Callback {name} is no longer callable!")
        
        return results
    
    def get_health_status(self) -> Dict:
        """
        Get comprehensive health status of WebSocket handler
        
        Returns:
            Dict with complete health information
        """
        circuit_status = self.get_circuit_breaker_status()
        callback_validation = self.validate_callbacks()
        
        # Check if any critical callbacks are broken
        critical_broken = (
            circuit_status.get('fill', {}).get('is_broken', False) or
            circuit_status.get('price_update', {}).get('is_broken', False)
        )
        
        # Check if any critical callbacks are invalid
        critical_invalid = (
            not callback_validation.get('fill', {}).get('valid', True) or
            not callback_validation.get('price_update', {}).get('valid', True)
        )
        
        # Calculate overall health
        is_healthy = not (critical_broken or critical_invalid)
        
        # Collect issues
        issues = []
        if critical_broken:
            issues.append("Critical callbacks have circuit breaker open")
        if critical_invalid:
            issues.append("Critical callbacks are not callable")
        
        # Check WebSocket manager connection
        ws_connected = 'unknown'
        if hasattr(self.ws_manager, 'is_connected'):
            try:
                ws_connected = self.ws_manager.is_connected()
                if not ws_connected:
                    is_healthy = False
                    issues.append("WebSocket manager not connected")
            except Exception as e:
                log.warning(f"⚠️ Could not check WebSocket connection status: {e}")
        
        return {
            'is_healthy': is_healthy,
            'issues': issues,
            'callbacks_registered': {
                'price_update': self._price_update_callback is not None,
                'fill': self._fill_callback is not None,
                'order_update': self._order_update_callback is not None,
                'position_update': self._position_update_callback is not None,
                'liquidation': self._liquidation_callback is not None,
                'emergency': self._emergency_callback is not None,
            },
            'callback_validation': callback_validation,
            'circuit_breakers': circuit_status,
            'stats': self.get_stats(),
            'ws_manager_connected': ws_connected,
            'available_methods': self._available_methods.copy()
        }
    
    def test_callbacks(self, test_data: Optional[Dict] = None) -> Dict:
        """
        Test all registered callbacks with sample data (for debugging)
        
        Args:
            test_data: Optional test data to use, otherwise uses default test data
            
        Returns:
            Dict with test results for each callback
        """
        if test_data is None:
            test_data = {
                'price_update': {'last': 50000, 'bid': 49999, 'ask': 50001},
                'fill': {'order_id': 'test_123', 'fill_price': 50000, 'fill_size': 1, 'side': 'buy'},
                'order_update': {'id': 'test_123', 'state': 'filled', 'side': 'buy'},
                'position_update': {'symbol': 'BTCUSD', 'size': 1, 'entry_price': 50000, 'pnl': 100}
            }
        
        results = {}
        
        # Test price update callback
        if self._price_update_callback:
            try:
                self._price_update_callback(test_data['price_update'])
                results['price_update'] = {'success': True, 'error': None}
            except Exception as e:
                results['price_update'] = {'success': False, 'error': str(e)}
        else:
            results['price_update'] = {'success': None, 'error': 'Not registered'}
        
        # Test fill callback
        if self._fill_callback:
            try:
                self._fill_callback(test_data['fill'])
                results['fill'] = {'success': True, 'error': None}
            except Exception as e:
                results['fill'] = {'success': False, 'error': str(e)}
        else:
            results['fill'] = {'success': None, 'error': 'Not registered'}
        
        # Test order update callback
        if self._order_update_callback:
            try:
                self._order_update_callback(test_data['order_update'])
                results['order_update'] = {'success': True, 'error': None}
            except Exception as e:
                results['order_update'] = {'success': False, 'error': str(e)}
        else:
            results['order_update'] = {'success': None, 'error': 'Not registered'}
        
        # Test position update callback
        if self._position_update_callback:
            try:
                self._position_update_callback(test_data['position_update'])
                results['position_update'] = {'success': True, 'error': None}
            except Exception as e:
                results['position_update'] = {'success': False, 'error': str(e)}
        else:
            results['position_update'] = {'success': None, 'error': 'Not registered'}
        
        return results
    
    def _register_all_callbacks(self):
        """Helper method to register all active callbacks"""
        if self._price_update_callback:
            self.ws_manager.on_price_update(self._handle_price_update)
            log.info("   ✅ Price update callback re-registered")
        
        if self._fill_callback:
            self.ws_manager.on_fill(self._handle_fill)
            log.info("   ✅ Fill callback re-registered")
        
        if self._order_update_callback and self._available_methods.get('on_order_update', False):
            self.ws_manager.on_order_update(self._handle_order_update)
            log.info("   ✅ Order update callback re-registered")
        
        if self._position_update_callback and self._available_methods.get('on_position_update', False):
            self.ws_manager.on_position_update(self._handle_position_update)
            log.info("   ✅ Position update callback re-registered")
    
    def _reset_connection_related_failures(self):
        """Reset only connection-related circuit breaker failures"""
        with self._circuit_breaker_lock:
            # Only reset if we have recent failures (might be connection-related)
            now = time.time()
            reset_threshold = 60  # Reset failures from last minute (likely connection issues)
            
            for callback_name in list(self._callback_failures.keys()):
                failures = self._callback_failures[callback_name]
                # Keep failures older than reset_threshold (likely not connection-related)
                old_failures = [f for f in failures if now - f > reset_threshold]
                if old_failures != failures:
                    self._callback_failures[callback_name] = old_failures
                    log.info(f"   ✅ Recent failures reset for {callback_name}")
    
    def on_websocket_reconnect(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Re-register callbacks after WebSocket reconnection with retry logic
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful, False otherwise
        """
        log.info("🔄 Re-registering callbacks after WebSocket reconnection...")
        
        for attempt in range(max_retries):
            try:
                # Check if WebSocket manager is ready
                if hasattr(self.ws_manager, 'is_connected'):
                    if not self.ws_manager.is_connected():
                        if attempt < max_retries - 1:
                            log.warning(f"⚠️ WebSocket manager not ready - retry {attempt + 1}/{max_retries} in {retry_delay}s")
                            time.sleep(retry_delay)
                            continue
                        else:
                            log.error("❌ WebSocket manager not ready after all retries")
                            return False
                
                # Re-register callbacks
                self._register_all_callbacks()
                
                # Only reset connection-related circuit breaker failures
                self._reset_connection_related_failures()
                
                log.info("✅ All callbacks re-registered successfully after reconnection")
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    log.warning(f"⚠️ Retry {attempt + 1}/{max_retries} failed: {e}")
                    time.sleep(retry_delay)
                else:
                    log.error(f"❌ All retries failed: {e}")
                    import traceback
                    log.error(traceback.format_exc())
                    raise
        
        return False
    
    def _handle_price_update(self, ticker_data: Dict):
        """
        Handle real-time price update from WebSocket
        
        Internal handler that routes to registered callback.
        
        Args:
            ticker_data: Ticker data with 'last', 'bid', 'ask' prices
        """
        try:
            # Check circuit breaker
            if self._is_callback_circuit_broken('price_update'):
                log.debug("⚠️ Price update callback circuit broken - skipping")
                return
            
            self._callback_stats['price_updates'] += 1
            
            if self._price_update_callback:
                self._price_update_callback(ticker_data)
        except Exception as e:
            self._callback_stats['price_update_errors'] += 1
            self._callback_stats['total_errors'] += 1
            self._record_callback_failure('price_update')
            log.error(f"❌ Error in price update handler: {e}")
    
    def _handle_fill(self, fill_data: Dict):
        """
        Handle fill detection from WebSocket (CRITICAL)
        
        This is the PRIMARY fill detection system (0.05s latency).
        Routes to registered fill callback for immediate TP placement.
        
        Args:
            fill_data: Fill data with order_id, fill_price, fill_size, side
        """
        try:
            # Validate required fields first
            if not isinstance(fill_data, dict):
                raise ValueError(f"Fill data must be dict, got {type(fill_data)}")
            
            order_id = fill_data.get('order_id')
            if not order_id:
                raise ValueError("Fill data missing required 'order_id' field")
            
            fill_price = fill_data.get('fill_price', 0)
            if fill_price <= 0:
                raise ValueError(f"Invalid fill_price: {fill_price}")
            
            # Check circuit breaker
            if self._is_callback_circuit_broken('fill'):
                log.warning(f"⚠️ Fill callback circuit broken - CRITICAL fill may be skipped: {order_id}")
                return
            
            # Use debug for routine detection, info for important stages
            log.debug(f"🔔 _handle_fill() called: order_id={order_id}, price=${fill_price:,.0f}")
            self._callback_stats['fills'] += 1
            
            if self._fill_callback:
                log.debug(f"   ✅ Callback registered, calling fill_callback...")
                
                try:
                    # Execute callback
                    self._fill_callback(fill_data)
                    log.debug(f"   ✅ Callback execution completed for {order_id}")
                except Exception as callback_error:
                    self._callback_stats['fill_errors'] += 1
                    self._callback_stats['total_errors'] += 1
                    self._record_callback_failure('fill')
                    # Use warning level since fill failures are important
                    log.warning(f"   ❌ Fill callback failed for {order_id}: {callback_error}")
                    import traceback
                    log.error(traceback.format_exc())
                    # DON'T re-raise - log and continue to prevent WebSocket thread death
                    
            else:
                log.critical(f"   ❌ NO FILL CALLBACK REGISTERED! Fill will be lost!")
                log.critical(f"   Order: {order_id}, Stats: {self._callback_stats}")
                
        except ValueError as e:
            self._callback_stats['total_errors'] += 1
            log.error(f"❌ Invalid fill data: {e}")
            log.error(f"   Fill data: {fill_data}")
        except Exception as e:
            self._callback_stats['total_errors'] += 1
            log.error(f"❌ Unexpected error in fill handler: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    def _handle_order_update(self, order_data: Dict):
        """
        Handle order update from WebSocket
        
        Args:
            order_data: Order data with id, state, side, etc.
        """
        try:
            # Check circuit breaker
            if self._is_callback_circuit_broken('order_update'):
                log.debug("⚠️ Order update callback circuit broken - skipping")
                return
            
            self._callback_stats['order_updates'] += 1
            
            if self._order_update_callback:
                self._order_update_callback(order_data)
        except Exception as e:
            self._callback_stats['order_update_errors'] += 1
            self._callback_stats['total_errors'] += 1
            self._record_callback_failure('order_update')
            log.error(f"❌ Error in order update handler: {e}")
    
    def _handle_position_update(self, position_data: Dict):
        """
        Handle position update from WebSocket
        
        Args:
            position_data: Position data with symbol, size, entry_price, pnl
        """
        try:
            # Check circuit breaker
            if self._is_callback_circuit_broken('position_update'):
                log.debug("⚠️ Position update callback circuit broken - skipping")
                return
            
            self._callback_stats['position_updates'] += 1
            
            if self._position_update_callback:
                self._position_update_callback(position_data)
        except Exception as e:
            self._callback_stats['position_update_errors'] += 1
            self._callback_stats['total_errors'] += 1
            self._record_callback_failure('position_update')
            log.error(f"❌ Error in position update handler: {e}")
    
    def handle_liquidation_alert(self, level: str, message: str, status: dict):
        """
        Handle liquidation monitoring alerts
        
        Args:
            level: Alert level (CRITICAL, WARNING, INFO)
            message: Alert message
            status: Current monitoring status
        """
        try:
            if self._liquidation_callback:
                self._liquidation_callback(level, message, status)
            else:
                # Default handling if no callback registered
                if level == 'CRITICAL':
                    log.critical(f"🚨 LIQUIDATION ALERT: {message}")
                elif level == 'WARNING':
                    log.warning(f"⚠️ LIQUIDATION WARNING: {message}")
                else:
                    log.info(f"ℹ️ LIQUIDATION INFO: {message}")
        except Exception as e:
            log.critical(f"❌ CRITICAL: Liquidation alert handler failed: {e}")
            raise
    
    def handle_emergency_alert(self, message: str, status: dict):
        """
        Handle emergency liquidation alerts
        
        Args:
            message: Emergency message
            status: Current monitoring status
        """
        try:
            if self._emergency_callback:
                self._emergency_callback(message, status)
            else:
                # Default handling if no callback registered
                log.critical(f"🚨🚨 EMERGENCY LIQUIDATION ALERT: {message}")
        except Exception as e:
            log.error(f"❌ Error handling emergency alert: {e}")
