# bot/margin_topup.py
"""
Auto Margin Top-Up System
Prevents liquidation by automatically adding margin to positions
"""
from __future__ import annotations

import sys
import os
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("runner")


class MarginTopUpManager:
    """
    Manages automatic margin top-up to prevent liquidation
    
    Features:
    - Threshold-based triggering
    - Balance safety checks
    - Maximum top-up limits
    - Integration with Delta Exchange API
    """
    
    def __init__(self, exchange_client=None):
        """
        Initialize margin top-up manager
        
        Args:
            exchange_client: CCXT exchange instance
        """
        self.ex = exchange_client
        
        # Load configuration from YAML
        cfg = get_config()
        self.enabled = False  # Disabled by default (no capital.auto_margin_topup_enabled in config)
        self.threshold = 80.0 / 100  # Convert percentage
        self.target = 90.0 / 100  # Convert percentage
        self.max_topups_per_position = 3
        self.min_balance_reserve_percent = 20.0 / 100
        
        self._topup_count = {}  # Track top-ups per position
        
        if self.enabled:
            log.info(f"✅ Auto Margin Top-Up enabled: threshold={self.threshold:.0%}, target={self.target:.0%}")
        else:
            log.info("Auto Margin Top-Up disabled")
    
    def check_and_topup(
        self,
        position_tracker,
        position_id: str,
        available_balance: float
    ) -> bool:
        """
        Check if position needs top-up and execute if necessary
        
        Args:
            position_tracker: PositionTracker instance
            position_id: Position to check
            available_balance: Available balance for top-up
        
        Returns:
            True if top-up was executed, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Check if position needs top-up
            if not position_tracker.needs_topup(position_id):
                return False
            
            position = position_tracker.get_position(position_id)
            if not position:
                log.warning(f"Position not found: {position_id}")
                return False
            
            # Check if we've already topped up too many times
            current_topups = position.liquidation.auto_topup_count
            if current_topups >= self.max_topups_per_position:
                log.warning(
                    f"Position {position_id} reached max top-ups ({self.max_topups_per_position}). "
                    f"Manual intervention required."
                )
                return False
            
            # Calculate required top-up amount
            required_margin = position.margin.maintenance_margin * self.target
            current_margin = position.margin.current_margin
            topup_amount = required_margin - current_margin
            
            if topup_amount <= 0:
                return False
            
            # Check if we have enough balance
            reserve_amount = available_balance * self.min_balance_reserve_percent
            available_for_topup = available_balance - reserve_amount
            
            if available_for_topup < topup_amount:
                log.warning(
                    f"Insufficient balance for top-up. Need: ₹{topup_amount:.2f}, "
                    f"Available: ₹{available_for_topup:.2f} (Reserve: ₹{reserve_amount:.2f})"
                )
                return False
            
            # Also check 50% of available balance limit
            max_topup = available_balance * 0.5
            if topup_amount > max_topup:
                topup_amount = max_topup
                log.info(f"Top-up amount capped at 50% of balance: ₹{topup_amount:.2f}")
            
            # Execute top-up
            success = self._execute_topup(position, topup_amount)
            
            if success:
                # Record in tracker
                position_tracker.record_topup(position_id, topup_amount)
                log.info(
                    f"✅ Auto top-up successful for {position_id}: +₹{topup_amount:.2f} "
                    f"(#{current_topups + 1}/{self.max_topups_per_position})"
                )
                
                # Send notification
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    if getattr(notifier, "enabled", False):
                        notifier.send(
                            f"🔧 Auto Margin Top-Up\n"
                            f"Position: {position_id}\n"
                            f"Amount: ₹{topup_amount:,.2f}\n"
                            f"Entry: ₹{position.entry_price:,.2f}\n"
                            f"Current: ₹{position.current_price:,.2f}\n"
                            f"Liquidation: ₹{position.liquidation.liquidation_price:,.2f}\n"
                            f"Count: {current_topups + 1}/{self.max_topups_per_position}"
                        )
                except Exception:
                    pass
                
                return True
            else:
                log.error(f"Failed to execute top-up for {position_id}")
                return False
                
        except Exception as e:
            log.error(f"Auto top-up error for {position_id}: {e}")
            return False
    
    def _execute_topup(self, position, amount: float) -> bool:
        """
        Execute margin top-up via exchange API
        
        NOTE: Delta Exchange doesn't have a direct "add margin" API.
        This is a placeholder for the actual implementation.
        
        For Delta Exchange, margin top-up can be achieved by:
        1. Transferring funds between wallet and margin account
        2. Using the position API to adjust margin
        
        Args:
            position: Position object
            amount: Amount to add (in INR)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.ex:
            log.warning("Exchange client not available for margin top-up")
            return False
        
        try:
            # For now, we'll just log the action
            # Real implementation would call Delta's API
            log.info(f"[SIMULATED] Adding ₹{amount:.2f} margin to position {position.id}")
            
            # TODO: Implement actual Delta Exchange margin transfer
            # Example (pseudo-code):
            # self.ex.add_margin(position.id, amount)
            # or
            # self.ex.transfer_to_margin(amount)
            
            # For simulation, we return True
            # In production, you would:
            # 1. Check if Delta has a margin management API
            # 2. If not, maintain higher initial margin to avoid this
            # 3. Or manually manage via exchange interface
            
            return True
            
        except Exception as e:
            log.error(f"Margin top-up execution failed: {e}")
            return False
    
    def check_all_positions(
        self,
        position_tracker,
        available_balance: float
    ) -> int:
        """
        Check all positions and top-up if needed
        
        Args:
            position_tracker: PositionTracker instance
            available_balance: Available balance
        
        Returns:
            Number of positions topped up
        """
        if not self.enabled:
            return 0
        
        topup_count = 0
        positions = position_tracker.get_all_positions()
        
        for position in positions:
            if self.check_and_topup(position_tracker, position.id, available_balance):
                topup_count += 1
        
        return topup_count
    
    def get_topup_recommendation(self, position) -> Optional[Dict[str, Any]]:
        """
        Get recommendation for manual top-up
        
        Args:
            position: Position object
        
        Returns:
            Dictionary with recommendation details or None
        """
        if position.margin.margin_ratio >= self.threshold:
            return None
        
        # Calculate recommended amount
        required_margin = position.margin.maintenance_margin * self.target
        recommended_amount = required_margin - position.margin.current_margin
        
        if recommended_amount <= 0:
            return None
        
        return {
            "position_id": position.id,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "liquidation_price": position.liquidation.liquidation_price,
            "current_margin_ratio": position.margin.margin_ratio,
            "distance_to_liq_percent": position.liquidation.distance_to_liq_percent,
            "recommended_topup": recommended_amount,
            "current_topup_count": position.liquidation.auto_topup_count,
            "max_topups": self.max_topups_per_position,
            "risk_level": position.liquidation.risk_level,
        }

