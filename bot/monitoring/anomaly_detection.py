"""
Anomaly Detection System - Detect abnormal bot behavior

Prevents catastrophic failures by detecting unusual patterns.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from collections import deque

log = logging.getLogger("runner")


class AnomalyDetectionSystem:
    """
    Detect anomalous bot behavior
    
    Responsibilities:
    - Detect multiple orders without TPs
    - Detect abnormal price jumps
    - Detect WebSocket disconnections
    - Detect excessive order placement rate
    - Alert on critical anomalies
    """
    
    def __init__(self):
        """Initialize anomaly detection system"""
        # Order tracking
        self.recent_orders: deque = deque(maxlen=50)  # Last 50 orders
        self.recent_tps: deque = deque(maxlen=50)  # Last 50 TPs
        
        # Price jump detection
        self.price_history: deque = deque(maxlen=100)  # Last 100 price updates
        
        # Rate limiting
        self.order_timestamps: deque = deque(maxlen=20)  # Last 20 order times
        
        # Ring buffer to store detected anomalies for monitoring
        self.detected_anomalies: deque = deque(maxlen=100)  # Last 100 anomalies
        
        # Thresholds
        self.max_orders_without_tp = 3  # Max orders without TP before alert
        self.max_price_jump_pct = 5.0  # Max price change % in 30s
        self.max_orders_per_minute = 10  # Max order placement rate
        
        # Statistics
        self.anomalies_detected = 0
        self.critical_alerts = 0
        
        log.info("✅ Anomaly Detection System initialized")
        log.info(f"   Max orders without TP: {self.max_orders_without_tp}")
        log.info(f"   Max price jump: {self.max_price_jump_pct}%")
        log.info(f"   Max order rate: {self.max_orders_per_minute}/min")
    
    def track_order_placement(self, order_id: str, price: float, order_type: str = "BUY") -> None:
        """
        Track order placement
        
        Args:
            order_id: Order ID
            price: Order price
            order_type: BUY or SELL
        """
        self.recent_orders.append({
            'order_id': order_id,
            'price': price,
            'type': order_type,
            'timestamp': time.time(),
            'has_tp': False,  # Will be set to True when TP is placed
            'filled': False   # Will be set to True when order fills
        })
        
        self.order_timestamps.append(time.time())
    
    def track_tp_placement(self, position_order_id: str, tp_order_id: str) -> None:
        """
        Track TP placement for a position
        
        Args:
            position_order_id: Entry order ID
            tp_order_id: TP order ID
        """
        # Mark the entry order as having a TP
        for order in self.recent_orders:
            if order['order_id'] == position_order_id:
                order['has_tp'] = True
                break
        
        self.recent_tps.append({
            'tp_id': tp_order_id,
            'position_order_id': position_order_id,
            'timestamp': time.time()
        })
    
    def track_order_fill(self, order_id: str) -> None:
        """
        Track when an order is filled
        
        Args:
            order_id: Order ID that was filled
        """
        # Mark the order as filled
        for order in self.recent_orders:
            if order['order_id'] == order_id:
                order['filled'] = True
                break
    
    def check_orders_without_tp(self) -> Optional[Dict[str, Any]]:
        """
        Check for multiple FILLED orders without TPs
        
        Returns:
            Anomaly dict if detected, None otherwise
        """
        # Count recent FILLED orders without TPs (only filled orders need TPs)
        orders_without_tp = [
            order for order in self.recent_orders
            if order.get('filled', False)  # Only check filled orders
            and not order['has_tp'] 
            and (time.time() - order['timestamp']) > 10  # Give 10s grace period
        ]
        
        if len(orders_without_tp) >= self.max_orders_without_tp:
            self.anomalies_detected += 1
            self.critical_alerts += 1
            
            anomaly = {
                'type': 'MULTIPLE_ORDERS_WITHOUT_TP',
                'severity': 'CRITICAL',
                'count': len(orders_without_tp),
                'orders': orders_without_tp,
                'timestamp': time.time()
            }
            
            log.error("=" * 80)
            log.error("🚨 CRITICAL ANOMALY DETECTED!")
            log.error("=" * 80)
            log.error(f"Type: MULTIPLE FILLED ORDERS WITHOUT TP")
            log.error(f"Count: {len(orders_without_tp)} filled positions without TPs")
            log.error("")
            log.error("Filled orders without TPs:")
            
            for i, order in enumerate(orders_without_tp, 1):
                age = time.time() - order['timestamp']
                log.error(f"  {i}. {order['type']} @ ${order['price']:,.2f}")
                log.error(f"     └─ Order ID: {order['order_id']}")
                log.error(f"     └─ Age: {age:.1f}s")
                log.error(f"     └─ TP Status: MISSING ❌")
            
            log.error("")
            log.error("⚠️ RECOMMENDED ACTION:")
            log.error("  1. STOP BOT IMMEDIATELY")
            log.error("  2. Manually place TPs for orphaned positions")
            log.error("  3. Investigate why TPs are not being placed")
            log.error("  4. Check order_manager.py and handlers")
            log.error("=" * 80)
            
            self._send_critical_alert(anomaly)
            
            # Store in ring buffer for monitoring
            self.detected_anomalies.append(anomaly)
            
            return anomaly
        
        return None
    
    def check_price_jump(self, current_price: float, previous_price: Optional[float]) -> Optional[Dict[str, Any]]:
        """
        Check for abnormal price jumps
        
        Args:
            current_price: Current price
            previous_price: Previous price
        
        Returns:
            Anomaly dict if detected, None otherwise
        """
        self.price_history.append({
            'price': current_price,
            'timestamp': time.time()
        })
        
        if previous_price and previous_price > 0:
            price_change_pct = abs((current_price - previous_price) / previous_price) * 100
            
            if price_change_pct > self.max_price_jump_pct:
                self.anomalies_detected += 1
                
                # Check if this happened in <30 seconds
                if len(self.price_history) >= 2:
                    time_delta = self.price_history[-1]['timestamp'] - self.price_history[-2]['timestamp']
                    
                    if time_delta < 30:
                        self.critical_alerts += 1
                        
                        anomaly = {
                            'type': 'ABNORMAL_PRICE_JUMP',
                            'severity': 'HIGH',
                            'price_change_pct': price_change_pct,
                            'previous_price': previous_price,
                            'current_price': current_price,
                            'time_delta': time_delta,
                            'timestamp': time.time()
                        }
                        
                        log.warning("=" * 80)
                        log.warning("⚠️ ANOMALY DETECTED: ABNORMAL PRICE JUMP")
                        log.warning("=" * 80)
                        log.warning(f"Price Change: {price_change_pct:.2f}% in {time_delta:.1f}s")
                        log.warning(f"  ├─ Previous: ${previous_price:,.2f}")
                        log.warning(f"  └─ Current: ${current_price:,.2f}")
                        log.warning("")
                        log.warning("Possible causes:")
                        log.warning("  • Flash crash/spike")
                        log.warning("  • Data feed error")
                        log.warning("  • WebSocket reconnection")
                        log.warning("")
                        log.warning("⚠️ Bot will halt orders until price stabilizes")
                        log.warning("=" * 80)
                        
                        # Store in ring buffer for monitoring
                        self.detected_anomalies.append(anomaly)
                        
                        return anomaly
        
        return None
    
    def check_order_placement_rate(self) -> Optional[Dict[str, Any]]:
        """
        Check if orders are being placed too quickly
        
        Returns:
            Anomaly dict if detected, None otherwise
        """
        if len(self.order_timestamps) >= self.max_orders_per_minute:
            # Check if all orders were in last 60 seconds
            now = time.time()
            recent = [ts for ts in self.order_timestamps if now - ts <= 60]
            
            if len(recent) >= self.max_orders_per_minute:
                self.anomalies_detected += 1
                
                anomaly = {
                    'type': 'EXCESSIVE_ORDER_RATE',
                    'severity': 'MEDIUM',
                    'orders_per_minute': len(recent),
                    'threshold': self.max_orders_per_minute,
                    'timestamp': time.time()
                }
                
                log.warning("=" * 80)
                log.warning("⚠️ ANOMALY DETECTED: EXCESSIVE ORDER RATE")
                log.warning("=" * 80)
                log.warning(f"Orders in last 60s: {len(recent)}")
                log.warning(f"Threshold: {self.max_orders_per_minute} orders/minute")
                log.warning("")
                log.warning("Possible causes:")
                log.warning("  • Logic error (placing duplicate orders)")
                log.warning("  • Fill detection issue (re-placing filled orders)")
                log.warning("  • Rapid price movements")
                log.warning("")
                log.warning("⚠️ Consider rate limiting order placement")
                log.warning("=" * 80)
                
                # Store in ring buffer for monitoring
                self.detected_anomalies.append(anomaly)
                
                return anomaly
        
        return None
    
    def check_websocket_staleness(self, last_ws_update: Optional[float]) -> Optional[Dict[str, Any]]:
        """
        Check if WebSocket connection is stale
        
        Args:
            last_ws_update: Timestamp of last WebSocket update
        
        Returns:
            Anomaly dict if detected, None otherwise
        """
        if last_ws_update is None:
            # Skip check during startup - WebSocket needs time to connect
            log.debug("Anomaly detector: Waiting for first WebSocket update...")
            return None
        
        age = time.time() - last_ws_update
        
        if age > 60:  # No updates for 1 minute
            self.anomalies_detected += 1
            self.critical_alerts += 1
            
            anomaly = {
                'type': 'WEBSOCKET_STALE',
                'severity': 'CRITICAL',
                'age': age,
                'timestamp': time.time()
            }
            
            log.error("=" * 80)
            log.error("🚨 CRITICAL: WEBSOCKET CONNECTION STALE")
            log.error("=" * 80)
            log.error(f"Last update: {age:.1f}s ago")
            log.error("")
            log.error("⚠️ WebSocket may be disconnected!")
            log.error("  • No price updates received")
            log.error("  • No fill notifications")
            log.error("  • Bot is operating blind!")
            log.error("")
            log.error("ACTION: Check WebSocket connection status")
            log.error("=" * 80)
            
            # Store in ring buffer for monitoring
            self.detected_anomalies.append(anomaly)
            
            return anomaly
        
        return None
    
    def run_all_checks(self, current_price: Optional[float] = None, 
                       previous_price: Optional[float] = None,
                       last_ws_update: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Run all anomaly checks
        
        Args:
            current_price: Current market price
            previous_price: Previous market price
            last_ws_update: Timestamp of last WebSocket update
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check orders without TPs
        anomaly = self.check_orders_without_tp()
        if anomaly:
            anomalies.append(anomaly)
        
        # Check price jumps
        if current_price and previous_price:
            anomaly = self.check_price_jump(current_price, previous_price)
            if anomaly:
                anomalies.append(anomaly)
        
        # Check order placement rate
        anomaly = self.check_order_placement_rate()
        if anomaly:
            anomalies.append(anomaly)
        
        # Check WebSocket staleness
        anomaly = self.check_websocket_staleness(last_ws_update)
        if anomaly:
            anomalies.append(anomaly)
        
        return anomalies
    
    def _send_critical_alert(self, anomaly: Dict[str, Any]) -> None:
        """
        Send critical alert
        
        Args:
            anomaly: Anomaly details
        """
        try:
            from bot.utils.notifier import TelegramNotifier
            
            message = (
                f"🚨 CRITICAL ANOMALY DETECTED!\n\n"
                f"Type: {anomaly['type']}\n"
                f"Severity: {anomaly['severity']}\n\n"
            )
            
            if anomaly['type'] == 'MULTIPLE_ORDERS_WITHOUT_TP':
                message += (
                    f"⚠️ {anomaly['count']} orders without TPs!\n\n"
                    f"IMMEDIATE ACTION REQUIRED:\n"
                    f"1. Stop bot\n"
                    f"2. Place missing TPs manually\n"
                    f"3. Investigate TP placement failure\n\n"
                )
            
            message += f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            notifier = TelegramNotifier()
            notifier.send(message)
            
            log.info("📱 Critical anomaly alert sent via Telegram")
            
        except Exception as e:
            log.warning(f"⚠️ Failed to send critical alert: {e}")
    
    def get_recent_anomalies(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent detected anomalies for monitoring
        
        Args:
            limit: Maximum number of anomalies to return (default: 50)
        
        Returns:
            List of recent anomaly dictionaries
        """
        # Convert deque to list and return last N items
        anomalies = list(self.detected_anomalies)
        return anomalies[-limit:] if len(anomalies) > limit else anomalies
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get anomaly detection summary for dashboard display
        
        Returns:
            Summary dictionary with anomaly metrics
        """
        # Get current anomalies (if any)
        current_anomalies = self.run_all_checks()
        
        # Count orders without TPs
        orders_without_tp = [
            order for order in self.recent_orders
            if not order['has_tp'] and (time.time() - order['timestamp']) > 10
        ]
        
        return {
            'active': True,
            'anomalies_detected': self.anomalies_detected,
            'critical_alerts': self.critical_alerts,
            'current_anomalies': len(current_anomalies),
            'anomaly_list': current_anomalies,
            'statistics': {
                'recent_orders_tracked': len(self.recent_orders),
                'recent_tps_tracked': len(self.recent_tps),
                'orders_without_tp': len(orders_without_tp),
                'order_placement_rate': len([ts for ts in self.order_timestamps if time.time() - ts <= 60])
            },
            'thresholds': {
                'max_orders_without_tp': self.max_orders_without_tp,
                'max_price_jump_pct': self.max_price_jump_pct,
                'max_orders_per_minute': self.max_orders_per_minute
            },
            'health_status': 'HEALTHY' if len(current_anomalies) == 0 else 'ANOMALY_DETECTED'
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get anomaly detection statistics"""
        return {
            'anomalies_detected': self.anomalies_detected,
            'critical_alerts': self.critical_alerts,
            'recent_orders_tracked': len(self.recent_orders),
            'recent_tps_tracked': len(self.recent_tps),
            'orders_without_tp': sum(1 for o in self.recent_orders if not o['has_tp'])
        }
    
    def log_statistics(self) -> None:
        """Log anomaly detection statistics"""
        stats = self.get_statistics()
        
        log.info("=" * 60)
        log.info("ANOMALY DETECTION STATISTICS")
        log.info("=" * 60)
        log.info(f"Total Anomalies: {stats['anomalies_detected']}")
        log.info(f"  └─ Critical Alerts: {stats['critical_alerts']}")
        log.info(f"Recent Orders Tracked: {stats['recent_orders_tracked']}")
        log.info(f"Recent TPs Tracked: {stats['recent_tps_tracked']}")
        log.info(f"Current Orders Without TP: {stats['orders_without_tp']}")
        log.info("=" * 60)
