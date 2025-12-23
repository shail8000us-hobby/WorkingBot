"""
Price Health Monitor - Track price data freshness and reliability

Prevents orders from being placed with stale or unreliable price data.
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

log = logging.getLogger("runner")


class PriceHealthMonitor:
    """
    Monitor price data health and freshness
    
    Responsibilities:
    - Track price update frequency
    - Detect stale price data
    - Monitor price source (WebSocket vs REST API)
    - Detect abnormal price gaps
    - Alert on price data issues
    """
    
    def __init__(self, stale_threshold: float = 35.0, critical_threshold: float = 60.0):
        """
        Initialize price health monitor
        
        Args:
            stale_threshold: Seconds before price is considered stale (default: 35s, matches Delta heartbeat)
            critical_threshold: Seconds before price is considered critical (default: 60s)
        """
        # Thresholds
        self.stale_threshold = stale_threshold
        self.critical_threshold = critical_threshold
        
        # Price tracking
        self.last_price: Optional[float] = None
        self.last_update_time: Optional[float] = None
        self.price_source: str = "NONE"  # WebSocket, REST_API, NONE
        
        # Statistics
        self.total_updates = 0
        self.stale_warnings = 0
        self.critical_warnings = 0
        self.websocket_updates = 0
        self.rest_api_updates = 0
        
        # Anomaly detection
        self.last_gap_check: Optional[float] = None
        self.max_normal_gap_pct = 0.5  # 0.5% is normal, >5% is suspicious
        
        log.info("✅ Price Health Monitor initialized")
        log.info(f"   Stale threshold: {stale_threshold}s")
        log.info(f"   Critical threshold: {critical_threshold}s")
    
    def update_price(self, price: float, source: str = "WebSocket") -> None:
        """
        Record price update
        
        Args:
            price: Current market price
            source: Data source (WebSocket or REST_API)
        """
        now = time.time()
        
        # Check for abnormal gap before updating
        if self.last_price is not None:
            gap_pct = abs(price - self.last_price) / self.last_price * 100
            
            if gap_pct > self.max_normal_gap_pct:
                log.warning(f"⚠️ PRICE GAP: {gap_pct:.2f}% change "
                           f"(${self.last_price:,.2f} → ${price:,.2f})")
                
                if gap_pct > 5.0:
                    log.error(f"🚨 ABNORMAL PRICE JUMP: {gap_pct:.2f}% in "
                             f"{now - self.last_update_time:.1f}s!")
        
        # Update tracking
        self.last_price = price
        self.last_update_time = now
        self.price_source = source
        self.total_updates += 1
        
        if source == "WebSocket":
            self.websocket_updates += 1
        elif source == "REST_API":
            self.rest_api_updates += 1
    
    def get_price_age(self) -> Optional[float]:
        """
        Get age of current price in seconds
        
        Returns:
            Age in seconds or None if no price data
        """
        if self.last_update_time is None:
            return None
        
        return time.time() - self.last_update_time
    
    def is_price_fresh(self) -> bool:
        """
        Check if price is fresh (not stale)
        
        Returns:
            True if price is fresh, False if stale or missing
        """
        age = self.get_price_age()
        
        if age is None:
            log.warning("⚠️ NO PRICE DATA - cannot verify freshness")
            return False
        
        return age <= self.stale_threshold
    
    def is_price_critical(self) -> bool:
        """
        Check if price is critically stale
        
        Returns:
            True if price is critically old
        """
        age = self.get_price_age()
        
        if age is None:
            return True  # No data is critical
        
        return age > self.critical_threshold
    
    def check_and_log_health(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Check price health and log status
        
        Args:
            verbose: If True, always log. If False, only log warnings/errors
        
        Returns:
            Health status dictionary
        """
        age = self.get_price_age()
        
        health = {
            'price': self.last_price,
            'age': age,
            'source': self.price_source,
            'is_fresh': False,
            'is_critical': False,
            'status': 'UNKNOWN'
        }
        
        if age is None:
            health['status'] = 'NO_DATA'
            health['is_critical'] = True
            log.error("🚨 PRICE HEALTH: NO DATA")
            return health
        
        # Determine status
        if age <= self.stale_threshold:
            health['status'] = 'FRESH'
            health['is_fresh'] = True
            
            if verbose:
                log.info(f"[PRICE] ${self.last_price:,.2f} | Age: {age:.1f}s | "
                        f"Source: {self.price_source} ✅")
        
        elif age <= self.critical_threshold:
            health['status'] = 'STALE'
            self.stale_warnings += 1
            
            log.warning(f"⚠️ PRICE STALE: ${self.last_price:,.2f} | Age: {age:.1f}s | "
                       f"Source: {self.price_source}")
        
        else:
            health['status'] = 'CRITICAL'
            health['is_critical'] = True
            self.critical_warnings += 1
            
            log.error(f"🚨 PRICE CRITICAL: ${self.last_price:,.2f} | Age: {age:.1f}s | "
                     f"Source: {self.price_source}")
            log.error("   ⛔ UNSAFE TO PLACE ORDERS - Price data too old!")
        
        return health
    
    def can_place_orders(self) -> tuple[bool, str]:
        """
        Check if it's safe to place orders based on price health
        
        Returns:
            (can_place, reason) tuple
        """
        age = self.get_price_age()
        
        if age is None:
            return False, "No price data available"
        
        if age > self.critical_threshold:
            return False, f"Price critically stale ({age:.1f}s old, limit: {self.critical_threshold}s)"
        
        if age > self.stale_threshold:
            return True, f"Price stale ({age:.1f}s old) but within limits"
        
        return True, f"Price fresh ({age:.1f}s old)"
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get price health statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            'total_updates': self.total_updates,
            'websocket_updates': self.websocket_updates,
            'rest_api_updates': self.rest_api_updates,
            'stale_warnings': self.stale_warnings,
            'critical_warnings': self.critical_warnings,
            'current_price': self.last_price,
            'current_age': self.get_price_age(),
            'current_source': self.price_source
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current price health status for dashboard display
        
        Returns:
            Status dictionary with health metrics
        """
        age = self.get_price_age()
        health = self.check_and_log_health(verbose=False)
        
        return {
            'active': True,
            'price': self.last_price,
            'price_age_seconds': age,
            'source': self.price_source,
            'status': health['status'],
            'is_fresh': health['is_fresh'],
            'is_critical': health['is_critical'],
            'thresholds': {
                'stale': self.stale_threshold,
                'critical': self.critical_threshold
            },
            'statistics': {
                'total_updates': self.total_updates,
                'websocket_updates': self.websocket_updates,
                'rest_api_updates': self.rest_api_updates,
                'stale_warnings': self.stale_warnings,
                'critical_warnings': self.critical_warnings
            }
        }
    
    def log_statistics(self) -> None:
        """Log price health statistics"""
        stats = self.get_statistics()
        
        log.info("=" * 60)
        log.info("PRICE HEALTH STATISTICS")
        log.info("=" * 60)
        log.info(f"Total Updates: {stats['total_updates']}")
        log.info(f"  └─ WebSocket: {stats['websocket_updates']}")
        log.info(f"  └─ REST API: {stats['rest_api_updates']}")
        log.info(f"Warnings:")
        log.info(f"  └─ Stale: {stats['stale_warnings']}")
        log.info(f"  └─ Critical: {stats['critical_warnings']}")
        log.info(f"Current Status:")
        log.info(f"  └─ Price: ${stats['current_price']:,.2f}" if stats['current_price'] else "  └─ Price: None")
        log.info(f"  └─ Age: {stats['current_age']:.1f}s" if stats['current_age'] else "  └─ Age: N/A")
        log.info(f"  └─ Source: {stats['current_source']}")
        log.info("=" * 60)
