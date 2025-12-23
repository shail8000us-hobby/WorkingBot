#!/usr/bin/env python3
"""
Auto-Heal Engine for Reconciliation Issues
Automatically fixes safe issues detected by enhanced detection system.

IMPORTANT: This module ONLY modifies bot/audit/orders.jsonl (bot memory).
It does NOT touch any bot strategy files, trading logic, or live exchange orders.

Safe Operations:
- Remove ghost orders from bot memory (orders gone from exchange)
- Deduplicate orders in bot memory
- Update stale status information

NEVER Does:
- Place/cancel exchange orders
- Modify bot strategy files
- Change trading logic
- Touch bot's decision-making process
"""

import logging
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

log = logging.getLogger("auto_heal")


@dataclass
class HealResult:
    """Result of a healing operation"""
    success: bool
    issue_type: str
    order_id: str
    action_taken: str
    details: Dict[str, Any]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutoHealEngine:
    """
    Auto-heal engine for safe reconciliation issue fixes.
    
    Features:
    - Ghost order removal (safe - order already gone from exchange)
    - Duplicate order cleanup (safe - keeps latest entry)
    - Stuck order status updates (safe - informational only)
    
    Safety:
    - All operations only modify bot/audit/orders.jsonl
    - Creates backup before any modification
    - Never touches exchange or bot strategy
    - Detailed audit logging
    """
    
    def __init__(self, base_dir: str = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).parent.parent.parent
        
        self.orders_file = self.base_dir / "bot" / "audit" / "orders.jsonl"
        self.heal_history: List[HealResult] = []
        
        log.info(f"🔧 Auto-Heal Engine initialized (orders file: {self.orders_file})")
    
    def heal_all_safe_issues(
        self,
        issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Auto-heal all safe issues (auto_healable=True).
        
        Args:
            issues: List of issues from enhanced detection
            
        Returns:
            Dictionary with:
            - healed_count: Number of issues healed
            - skipped_count: Number of issues requiring manual review
            - results: List of HealResult objects
            - backup_path: Path to backup file
        """
        log.info(f"🔧 Starting auto-heal for {len(issues)} issues")
        
        # Filter safe issues
        safe_issues = [i for i in issues if i.get('auto_healable', False)]
        unsafe_issues = [i for i in issues if not i.get('auto_healable', False)]
        
        log.info(f"🔧 {len(safe_issues)} safe issues, {len(unsafe_issues)} require manual review")
        
        if len(safe_issues) == 0:
            return {
                'status': 'success',
                'healed_count': 0,
                'skipped_count': len(unsafe_issues),
                'results': [],
                'message': 'No safe issues to heal'
            }
        
        # Create backup
        backup_path = self._create_backup()
        log.info(f"📦 Created backup: {backup_path}")
        
        # Heal each safe issue
        results = []
        for issue in safe_issues:
            try:
                result = self._heal_single_issue(issue)
                results.append(result)
                self.heal_history.append(result)
            except Exception as e:
                log.error(f"❌ Failed to heal issue {issue.get('order_id')}: {e}")
                results.append(HealResult(
                    success=False,
                    issue_type=issue.get('issue_type', 'unknown'),
                    order_id=issue.get('order_id', 'unknown'),
                    action_taken='error',
                    details={'error': str(e)}
                ))
        
        healed_count = len([r for r in results if r.success])
        
        log.info(f"✅ Auto-heal complete: {healed_count}/{len(safe_issues)} healed")
        
        return {
            'status': 'success',
            'healed_count': healed_count,
            'skipped_count': len(unsafe_issues),
            'results': [r.to_dict() for r in results],
            'backup_path': str(backup_path),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _heal_single_issue(self, issue: Dict[str, Any]) -> HealResult:
        """Heal a single issue based on its type"""
        issue_type = issue.get('issue_type')
        order_id = issue.get('order_id')
        
        log.info(f"🔧 Healing {issue_type} for order {order_id}")
        
        if issue_type == 'ghost_order':
            return self._heal_ghost_order(issue)
        elif issue_type == 'duplicate_order':
            return self._heal_duplicate_order(issue)
        elif issue_type == 'stuck_order':
            return self._heal_stuck_order(issue)
        else:
            raise ValueError(f"Unknown issue type: {issue_type}")
    
    def _heal_ghost_order(self, issue: Dict[str, Any]) -> HealResult:
        """
        Remove ghost order from bot memory.
        Safe because order is already gone from exchange.
        """
        order_id = issue.get('order_id')
        client_order_id = issue.get('client_order_id')
        
        # Read orders
        orders = self._read_orders()
        initial_count = len(orders)
        
        # Remove ghost order
        filtered_orders = [
            o for o in orders
            if (str(o.get('order_id')) != str(order_id) and
                str(o.get('client_order_id')) != str(client_order_id))
        ]
        
        removed_count = initial_count - len(filtered_orders)
        
        # Write back
        self._write_orders(filtered_orders, f"Removed {removed_count} ghost order(s)")
        
        log.info(f"✅ Removed ghost order {order_id} from bot memory")
        
        return HealResult(
            success=True,
            issue_type='ghost_order',
            order_id=order_id,
            action_taken='removed_from_memory',
            details={
                'removed_count': removed_count,
                'capital_freed': issue.get('impact_value', 0),
                'reason': 'Order not found on exchange'
            }
        )
    
    def _heal_duplicate_order(self, issue: Dict[str, Any]) -> HealResult:
        """
        Remove duplicate orders from bot memory, keep only the latest.
        Safe because it's just cleaning up memory corruption.
        """
        order_id = issue.get('order_id')
        
        # Read orders
        orders = self._read_orders()
        initial_count = len(orders)
        
        # Find all occurrences of this order
        duplicates = [o for o in orders if str(o.get('order_id')) == str(order_id)]
        
        if len(duplicates) <= 1:
            return HealResult(
                success=True,
                issue_type='duplicate_order',
                order_id=order_id,
                action_taken='no_duplicates_found',
                details={'message': 'No duplicates to remove'}
            )
        
        # Keep the latest one (highest timestamp)
        def get_timestamp(order):
            ts = order.get('timestamp') or order.get('created_at') or ''
            return ts
        
        duplicates.sort(key=get_timestamp, reverse=True)
        latest = duplicates[0]
        
        # Remove duplicates, keep latest
        filtered_orders = [
            o for o in orders
            if str(o.get('order_id')) != str(order_id)
        ]
        filtered_orders.append(latest)
        
        removed_count = len(duplicates) - 1
        
        # Write back
        self._write_orders(filtered_orders, f"Deduplicated order {order_id}, kept latest")
        
        log.info(f"✅ Deduplicated order {order_id}: removed {removed_count} duplicates")
        
        return HealResult(
            success=True,
            issue_type='duplicate_order',
            order_id=order_id,
            action_taken='deduplicated',
            details={
                'removed_count': removed_count,
                'kept_timestamp': get_timestamp(latest)
            }
        )
    
    def _heal_stuck_order(self, issue: Dict[str, Any]) -> HealResult:
        """
        Update status of stuck order in bot memory.
        Safe because it's informational only - doesn't affect trading.
        """
        order_id = issue.get('order_id')
        
        # For now, just log it - actual status update would require more context
        log.info(f"ℹ️  Stuck order {order_id} requires manual review")
        
        return HealResult(
            success=True,
            issue_type='stuck_order',
            order_id=order_id,
            action_taken='logged_for_manual_review',
            details={
                'message': 'Stuck orders require manual intervention',
                'recommendation': 'Check exchange directly or wait for automatic resolution'
            }
        )
    
    def _read_orders(self) -> List[Dict[str, Any]]:
        """Read all orders from orders.jsonl"""
        orders = []
        
        if not self.orders_file.exists():
            log.warning(f"Orders file not found: {self.orders_file}")
            return orders
        
        with open(self.orders_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    order = json.loads(line)
                    orders.append(order)
                except json.JSONDecodeError as e:
                    log.error(f"Failed to parse order line: {e}")
                    continue
        
        return orders
    
    def _write_orders(self, orders: List[Dict[str, Any]], reason: str):
        """Write orders back to orders.jsonl"""
        with open(self.orders_file, 'w') as f:
            f.write(f"# Auto-heal operation: {reason}\n")
            f.write(f"# Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"# Orders count: {len(orders)}\n")
            for order in orders:
                f.write(json.dumps(order) + '\n')
        
        log.info(f"✅ Wrote {len(orders)} orders to {self.orders_file}")
    
    def _create_backup(self) -> Path:
        """Create backup of orders.jsonl before modification"""
        if not self.orders_file.exists():
            raise FileNotFoundError(f"Orders file not found: {self.orders_file}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.orders_file.parent / f"orders.jsonl.autoheal_backup_{timestamp}"
        
        shutil.copy2(self.orders_file, backup_path)
        
        return backup_path
    
    def get_heal_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent heal history"""
        return [h.to_dict() for h in self.heal_history[-limit:]]
    
    def undo_last_heal(self) -> Dict[str, Any]:
        """
        Undo the last heal operation by restoring from backup.
        
        Returns:
            Status dictionary
        """
        # Find most recent backup
        backup_dir = self.orders_file.parent
        backups = sorted(backup_dir.glob("orders.jsonl.autoheal_backup_*"), reverse=True)
        
        if not backups:
            return {
                'success': False,
                'error': 'No backup found to restore'
            }
        
        latest_backup = backups[0]
        
        # Create backup of current state
        current_backup = self.orders_file.parent / f"orders.jsonl.before_undo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(self.orders_file, current_backup)
        
        # Restore from backup
        shutil.copy2(latest_backup, self.orders_file)
        
        log.info(f"↩️  Restored from backup: {latest_backup}")
        
        return {
            'success': True,
            'restored_from': str(latest_backup),
            'current_backed_up_to': str(current_backup),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


# Global singleton
_auto_heal_engine: Optional[AutoHealEngine] = None


def get_auto_heal_engine() -> AutoHealEngine:
    """Get global auto-heal engine instance"""
    global _auto_heal_engine
    if _auto_heal_engine is None:
        _auto_heal_engine = AutoHealEngine()
    return _auto_heal_engine


def heal_all_safe_issues(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function to heal all safe issues"""
    engine = get_auto_heal_engine()
    return engine.heal_all_safe_issues(issues)
