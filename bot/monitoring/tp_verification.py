"""
TP Verification System - Verify TP placement after every fill

Prevents "orphaned positions" (positions without TPs).
"""

import time
import logging
from typing import Optional, Dict, Any, List

log = logging.getLogger("runner")


class TPVerificationSystem:
    """
    Verify TP (Take Profit) placement for all positions
    
    Responsibilities:
    - Verify TP exists for every position
    - Detect orphaned positions (no TP)
    - Alert on missing TPs
    - Track TP placement success rate
    """
    
    def __init__(self, delta_client=None):
        """
        Initialize TP verification system
        
        Args:
            delta_client: Delta Exchange API client for verification
        """
        self.delta_client = delta_client
        
        # Statistics
        self.total_verifications = 0
        self.successful_verifications = 0
        self.failed_verifications = 0
        self.orphaned_positions = 0
        
        # Orphan tracking
        self.orphan_alerts_sent: List[str] = []
        
        log.info("✅ TP Verification System initialized")
    
    def verify_tp_placement(self, position: Dict[str, Any], check_exchange: bool = False) -> bool:
        """
        Verify TP was placed for a position
        
        Args:
            position: Position dictionary with entry_price, tp_id, etc.
            check_exchange: If True, verify TP exists on exchange (slower)
        
        Returns:
            True if TP exists, False if missing
        """
        self.total_verifications += 1
        
        entry_price = position.get('entry_price')
        tp_price = position.get('tp_price')
        tp_id = position.get('tp_id')
        buy_order_id = position.get('buy_order_id')
        
        log.info("=" * 80)
        log.info("[TP VERIFICATION]")
        log.info("=" * 80)
        log.info(f"📍 Position:")
        log.info(f"  ├─ Entry: ${entry_price:,.2f}" if entry_price else "  ├─ Entry: UNKNOWN")
        log.info(f"  ├─ TP Target: ${tp_price:,.2f}" if tp_price else "  ├─ TP Target: UNKNOWN")
        log.info(f"  ├─ Entry Order ID: {buy_order_id}" if buy_order_id else "  ├─ Entry Order ID: UNKNOWN")
        log.info(f"  └─ TP Order ID: {tp_id}" if tp_id else "  └─ TP Order ID: MISSING ❌")
        
        # Check if TP ID exists in position data
        if not tp_id:
            log.error("🚨 CRITICAL: Position has NO TP ORDER ID!")
            log.error(f"  ├─ Entry Price: ${entry_price:,.2f}")
            log.error(f"  ├─ Entry Order: {buy_order_id}")
            log.error(f"  └─ Expected TP: ${tp_price:,.2f}")
            log.error("")
            log.error("⚠️ ORPHANED POSITION DETECTED!")
            log.error("   Manual intervention required to place TP!")
            log.error("=" * 80)
            
            self.failed_verifications += 1
            self.orphaned_positions += 1
            
            # Track this orphan to avoid duplicate alerts
            orphan_key = f"{entry_price}_{buy_order_id}"
            if orphan_key not in self.orphan_alerts_sent:
                self.orphan_alerts_sent.append(orphan_key)
                self._send_orphan_alert(position)
            
            return False
        
        # If exchange verification requested
        if check_exchange and self.delta_client:
            log.info(f"🔍 Verifying TP on exchange...")
            
            try:
                tp_order = self.delta_client.get_order(tp_id)
                
                if not tp_order:
                    log.error(f"🚨 TP ORDER {tp_id} NOT FOUND ON EXCHANGE!")
                    log.error(f"   Position may be orphaned!")
                    log.error("=" * 80)
                    
                    self.failed_verifications += 1
                    self.orphaned_positions += 1
                    return False
                
                # Verify TP is still active
                tp_status = tp_order.get('state', 'unknown')
                
                if tp_status in ['open', 'pending']:
                    log.info(f"✅ TP VERIFIED ON EXCHANGE")
                    log.info(f"  ├─ TP Order ID: {tp_id}")
                    log.info(f"  ├─ TP Price: ${tp_order.get('limit_price', 'unknown')}")
                    log.info(f"  ├─ Status: {tp_status.upper()}")
                    log.info(f"  └─ Size: {tp_order.get('size', 'unknown')} lots")
                    log.info("=" * 80)
                    
                    self.successful_verifications += 1
                    return True
                
                elif tp_status == 'filled':
                    log.info(f"✅ TP WAS FILLED (Position closed)")
                    log.info(f"  └─ TP Order: {tp_id}")
                    log.info("=" * 80)
                    
                    self.successful_verifications += 1
                    return True
                
                else:
                    log.warning(f"⚠️ TP IN UNEXPECTED STATE: {tp_status}")
                    log.warning(f"  └─ TP Order: {tp_id}")
                    log.warning("=" * 80)
                    
                    self.failed_verifications += 1
                    return False
                    
            except Exception as e:
                log.error(f"❌ Failed to verify TP on exchange: {e}")
                log.error("=" * 80)
                
                self.failed_verifications += 1
                return False
        
        else:
            # Basic verification (just check if TP ID exists)
            log.info(f"✅ TP ORDER ID EXISTS")
            log.info(f"  └─ TP Order: {tp_id}")
            log.info(f"  Note: Not verified on exchange (set check_exchange=True for full verification)")
            log.info("=" * 80)
            
            self.successful_verifications += 1
            return True
    
    def verify_all_positions(self, positions: List[Dict[str, Any]], check_exchange: bool = False) -> tuple[int, int]:
        """
        Verify TPs for all positions
        
        Args:
            positions: List of position dictionaries
            check_exchange: If True, verify each TP on exchange
        
        Returns:
            (verified_count, orphaned_count) tuple
        """
        if not positions:
            log.info("[TP VERIFICATION] No positions to verify")
            return 0, 0
        
        log.info("=" * 80)
        log.info(f"[TP VERIFICATION] Checking {len(positions)} positions...")
        log.info("=" * 80)
        
        verified = 0
        orphaned = 0
        
        for i, position in enumerate(positions, 1):
            log.info(f"\nPosition {i}/{len(positions)}:")
            
            if self.verify_tp_placement(position, check_exchange=check_exchange):
                verified += 1
            else:
                orphaned += 1
        
        # Summary
        log.info("=" * 80)
        log.info("[TP VERIFICATION SUMMARY]")
        log.info("=" * 80)
        log.info(f"Total Positions: {len(positions)}")
        log.info(f"  ├─ Verified: {verified} ✅")
        log.info(f"  └─ Orphaned: {orphaned} ❌")
        
        if orphaned > 0:
            log.error(f"\n🚨 WARNING: {orphaned} ORPHANED POSITION(S) DETECTED!")
            log.error("   Manual intervention required to place missing TPs!")
        
        log.info("=" * 80)
        
        return verified, orphaned
    
    def _send_orphan_alert(self, position: Dict[str, Any]) -> None:
        """
        Send alert for orphaned position
        
        Args:
            position: Orphaned position
        """
        try:
            from bot.utils.notifier import TelegramNotifier
            
            entry_price = position.get('entry_price', 'unknown')
            tp_price = position.get('tp_price', 'unknown')
            buy_order_id = position.get('buy_order_id', 'unknown')
            
            message = (
                f"🚨 ORPHANED POSITION ALERT!\n\n"
                f"Position Details:\n"
                f"  • Entry: ${entry_price:,.2f}\n"
                f"  • Expected TP: ${tp_price:,.2f}\n"
                f"  • Entry Order: {buy_order_id}\n\n"
                f"❌ NO TP ORDER FOUND!\n\n"
                f"⚠️ ACTION REQUIRED:\n"
                f"Manually place TP order to protect position!\n\n"
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            notifier = TelegramNotifier()
            notifier.send(message)
            
            log.info("📱 Orphan alert sent via Telegram")
            
        except Exception as e:
            log.warning(f"⚠️ Failed to send orphan alert: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get TP verification statistics"""
        success_rate = (self.successful_verifications / self.total_verifications * 100) \
                      if self.total_verifications > 0 else 0
        
        return {
            'total_verifications': self.total_verifications,
            'successful': self.successful_verifications,
            'failed': self.failed_verifications,
            'orphaned_positions': self.orphaned_positions,
            'success_rate': success_rate
        }
    
    def log_statistics(self) -> None:
        """Log TP verification statistics"""
        stats = self.get_statistics()
        
        log.info("=" * 60)
        log.info("TP VERIFICATION STATISTICS")
        log.info("=" * 60)
        log.info(f"Total Verifications: {stats['total_verifications']}")
        log.info(f"  ├─ Successful: {stats['successful']} ✅")
        log.info(f"  ├─ Failed: {stats['failed']} ❌")
        log.info(f"  └─ Orphaned Positions: {stats['orphaned_positions']} 🚨")
        log.info(f"Success Rate: {stats['success_rate']:.1f}%")
        log.info("=" * 60)
