"""
Pre-Order Decision Logger - Log complete context before order placement

Shows exactly what the bot is "thinking" before placing each order.
"""

import time
import logging
from typing import Optional, Dict, Any, List

log = logging.getLogger("runner")


class PreOrderDecisionLogger:
    """
    Log comprehensive decision context before order placement
    
    Responsibilities:
    - Log all decision factors before order placement
    - Validate price freshness
    - Check grid alignment
    - Verify capacity
    - Check volatility status
    - Provide clear pass/fail reasoning
    """
    
    def __init__(self):
        """Initialize pre-order decision logger"""
        self.decisions_logged = 0
        self.orders_approved = 0
        self.orders_rejected = 0
        
        # Ring buffer to store recent decisions for monitoring
        from collections import deque
        self.recent_decisions: deque = deque(maxlen=50)  # Last 50 decisions
        
        log.info("✅ Pre-Order Decision Logger initialized")
    
    def log_decision(
        self,
        side: str,
        price: float,
        current_price: Optional[float],
        price_age: Optional[float] = None,
        grid_aligned: bool = True,
        current_positions: int = 0,
        max_positions: int = 10,
        volatility_safe: bool = True,
        grid_step: float = 500,
        reasons: Optional[List[str]] = None
    ) -> bool:
        if side.upper() == 'BUY':
            return self.log_buy_decision(
                target_price=price,
                current_price=current_price,
                price_age=price_age,
                grid_aligned=grid_aligned,
                current_positions=current_positions,
                max_positions=max_positions,
                volatility_safe=volatility_safe,
                grid_step=grid_step,
                reasons=reasons
            )
        elif side.upper() == 'SELL':
            return self.log_sell_decision(
                target_price=price,
                current_price=current_price,
                price_age=price_age,
                grid_aligned=grid_aligned,
                current_positions=current_positions,
                max_positions=max_positions,
                volatility_safe=volatility_safe,
                grid_step=grid_step,
                reasons=reasons
            )
        else:
            log.error(f"Invalid side: {side}. Must be 'BUY' or 'SELL'")
            return False
    
    def log_buy_decision(
        self,
        target_price: float,
        current_price: Optional[float],
        price_age: Optional[float],
        grid_aligned: bool,
        current_positions: int,
        max_positions: int,
        volatility_safe: bool,
        grid_step: float,
        reasons: Optional[List[str]] = None
    ) -> bool:
        """
        Log BUY order decision with full context
        
        Args:
            target_price: Proposed BUY price
            current_price: Current market price
            price_age: Age of price data in seconds
            grid_aligned: Whether price is grid-aligned
            current_positions: Current number of positions
            max_positions: Maximum allowed positions
            volatility_safe: Whether volatility is safe
            grid_step: Grid step size
            reasons: Optional list of rejection reasons
        
        Returns:
            True if all checks pass, False if any fail
        """
        self.decisions_logged += 1
        
        log.info("=" * 80)
        log.info("[PRE-ORDER ANALYSIS] BUY ORDER")
        log.info("=" * 80)
        
        # Price information
        if current_price:
            price_gap = current_price - target_price
            price_gap_pct = (price_gap / current_price) * 100
            
            age_str = f"{price_age:.1f}s" if price_age is not None else "unknown"
            log.info(f"📊 PRICE ANALYSIS:")
            log.info(f"  ├─ Current Price: ${current_price:,.2f} (age: {age_str})")
            log.info(f"  ├─ Target BUY: ${target_price:,.2f}")
            log.info(f"  ├─ Price Gap: ${price_gap:,.2f} ({price_gap_pct:+.2f}%)")
            
            # Price should be BELOW market for BUY
            if target_price >= current_price:
                log.info(f"  └─ Position: AT/ABOVE market ❌ (MAKER order required)")
            else:
                log.info(f"  └─ Position: BELOW market ✅ (safe for MAKER)")
        else:
            log.info(f"📊 PRICE ANALYSIS:")
            log.info(f"  ├─ Current Price: UNKNOWN ❌")
            log.info(f"  └─ Target BUY: ${target_price:,.2f}")
        
        # Grid alignment
        log.info(f"📐 GRID ALIGNMENT:")
        log.info(f"  ├─ Grid Step: ${grid_step:,.0f}")
        log.info(f"  ├─ Target Price: ${target_price:,.2f}")
        if grid_aligned:
            log.info(f"  └─ Status: ALIGNED ✅")
        else:
            log.info(f"  └─ Status: OFF-GRID ❌")
        
        # Capacity check
        capacity_available = max_positions - current_positions
        capacity_pct = (current_positions / max_positions) * 100
        
        log.info(f"📦 CAPACITY CHECK:")
        log.info(f"  ├─ Current Positions: {current_positions}/{max_positions}")
        log.info(f"  ├─ Utilization: {capacity_pct:.0f}%")
        log.info(f"  ├─ Available Slots: {capacity_available}")
        
        if capacity_available > 0:
            log.info(f"  └─ Status: AVAILABLE ✅")
        else:
            log.info(f"  └─ Status: FULL ❌")
        
        # Volatility check
        log.info(f"🌊 VOLATILITY CHECK:")
        if volatility_safe:
            log.info(f"  └─ Status: SAFE ✅")
        else:
            log.info(f"  └─ Status: HALTED ❌")
        
        # Price freshness
        log.info(f"⏰ PRICE FRESHNESS:")
        if price_age is not None:
            if price_age <= 10:
                log.info(f"  └─ Age: {price_age:.1f}s ✅")
            elif price_age <= 30:
                log.info(f"  └─ Age: {price_age:.1f}s ⚠️ (stale but acceptable)")
            else:
                log.info(f"  └─ Age: {price_age:.1f}s ❌ (critically stale)")
        else:
            log.info(f"  └─ Age: UNKNOWN ❌")
        
        # Final decision
        all_checks_pass = (
            current_price is not None and
            target_price < current_price and
            grid_aligned and
            capacity_available > 0 and
            volatility_safe and
            (price_age is not None and price_age <= 30)
        )
        
        log.info("=" * 80)
        if all_checks_pass:
            log.info("✅ DECISION: APPROVE ORDER PLACEMENT")
            self.orders_approved += 1
        else:
            log.info("❌ DECISION: REJECT ORDER PLACEMENT")
            self.orders_rejected += 1
            
            if reasons:
                log.info("📋 REJECTION REASONS:")
                for reason in reasons:
                    log.info(f"  └─ {reason}")
        
        log.info("=" * 80)
        
        # Store decision in ring buffer for monitoring
        self.recent_decisions.append({
            'type': 'BUY',
            'target_price': target_price,
            'current_price': current_price,
            'price_age': price_age,
            'grid_aligned': grid_aligned,
            'capacity_available': capacity_available > 0,
            'volatility_safe': volatility_safe,
            'approved': all_checks_pass,
            'reasons': reasons if not all_checks_pass else None,
            'timestamp': time.time()
        })
        
        return all_checks_pass
    
    def log_sell_decision(
        self,
        target_price: float,
        current_price: Optional[float],
        price_age: Optional[float],
        grid_aligned: bool,
        current_positions: int,
        max_positions: int,
        volatility_safe: bool,
        grid_step: float,
        reasons: Optional[List[str]] = None
    ) -> bool:
        """
        Log SELL order decision with full context
        
        Args:
            target_price: Proposed SELL price
            current_price: Current market price
            price_age: Age of price data in seconds
            grid_aligned: Whether price is grid-aligned
            current_positions: Current number of positions
            max_positions: Maximum allowed positions
            volatility_safe: Whether volatility is safe
            grid_step: Grid step size
            reasons: Optional list of rejection reasons
        
        Returns:
            True if all checks pass, False if any fail
        """
        self.decisions_logged += 1
        
        log.info("=" * 80)
        log.info("[PRE-ORDER ANALYSIS] SELL ORDER (SHORT MODE)")
        log.info("=" * 80)
        
        # Price information
        if current_price:
            price_gap = target_price - current_price
            price_gap_pct = (price_gap / current_price) * 100
            
            log.info(f"📊 PRICE ANALYSIS:")
            age_str = f"{price_age:.1f}s" if price_age is not None else "unknown"
            log.info(f"  ├─ Current Price: ${current_price:,.2f} (age: {age_str})")
            log.info(f"  ├─ Target SELL: ${target_price:,.2f}")
            log.info(f"  ├─ Price Gap: ${price_gap:,.2f} ({price_gap_pct:+.2f}%)")
            
            # Price should be ABOVE market for SELL
            if target_price <= current_price:
                log.info(f"  └─ Position: AT/BELOW market ❌ (MAKER order required)")
            else:
                log.info(f"  └─ Position: ABOVE market ✅ (safe for MAKER)")
        else:
            log.info(f"📊 PRICE ANALYSIS:")
            log.info(f"  ├─ Current Price: UNKNOWN ❌")
            log.info(f"  └─ Target SELL: ${target_price:,.2f}")
        
        # Grid alignment
        log.info(f"📐 GRID ALIGNMENT:")
        log.info(f"  ├─ Grid Step: ${grid_step:,.0f}")
        log.info(f"  ├─ Target Price: ${target_price:,.2f}")
        if grid_aligned:
            log.info(f"  └─ Status: ALIGNED ✅")
        else:
            log.info(f"  └─ Status: OFF-GRID ❌")
        
        # Capacity check
        capacity_available = max_positions - current_positions
        capacity_pct = (current_positions / max_positions) * 100
        
        log.info(f"📦 CAPACITY CHECK:")
        log.info(f"  ├─ Current Positions: {current_positions}/{max_positions}")
        log.info(f"  ├─ Utilization: {capacity_pct:.0f}%")
        log.info(f"  ├─ Available Slots: {capacity_available}")
        
        if capacity_available > 0:
            log.info(f"  └─ Status: AVAILABLE ✅")
        else:
            log.info(f"  └─ Status: FULL ❌")
        
        # Volatility check
        log.info(f"🌊 VOLATILITY CHECK:")
        if volatility_safe:
            log.info(f"  └─ Status: SAFE ✅")
        else:
            log.info(f"  └─ Status: HALTED ❌")
        
        # Price freshness
        log.info(f"⏰ PRICE FRESHNESS:")
        if price_age is not None:
            if price_age <= 10:
                log.info(f"  └─ Age: {price_age:.1f}s ✅")
            elif price_age <= 30:
                log.info(f"  └─ Age: {price_age:.1f}s ⚠️ (stale but acceptable)")
            else:
                log.info(f"  └─ Age: {price_age:.1f}s ❌ (critically stale)")
        else:
            log.info(f"  └─ Age: UNKNOWN ❌")
        
        # Final decision
        all_checks_pass = (
            current_price is not None and
            target_price > current_price and
            grid_aligned and
            capacity_available > 0 and
            volatility_safe and
            (price_age is not None and price_age <= 30)
        )
        
        log.info("=" * 80)
        if all_checks_pass:
            log.info("✅ DECISION: APPROVE ORDER PLACEMENT")
            self.orders_approved += 1
        else:
            log.info("❌ DECISION: REJECT ORDER PLACEMENT")
            self.orders_rejected += 1
            
            if reasons:
                log.info("📋 REJECTION REASONS:")
                for reason in reasons:
                    log.info(f"  └─ {reason}")
        
        log.info("=" * 80)
        
        # Store decision in ring buffer for monitoring
        self.recent_decisions.append({
            'type': 'SELL',
            'target_price': target_price,
            'current_price': current_price,
            'price_age': price_age,
            'grid_aligned': grid_aligned,
            'capacity_available': capacity_available > 0,
            'volatility_safe': volatility_safe,
            'approved': all_checks_pass,
            'reasons': reasons if not all_checks_pass else None,
            'timestamp': time.time()
        })
        
        return all_checks_pass
    
    def get_recent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent order decisions for monitoring
        
        Args:
            limit: Maximum number of decisions to return (default: 50)
        
        Returns:
            List of recent decision dictionaries
        """
        # Convert deque to list and return last N items
        decisions = list(self.recent_decisions)
        return decisions[-limit:] if len(decisions) > limit else decisions
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get decision logging statistics"""
        return {
            'total_decisions': self.decisions_logged,
            'approved': self.orders_approved,
            'rejected': self.orders_rejected,
            'approval_rate': (self.orders_approved / self.decisions_logged * 100) 
                            if self.decisions_logged > 0 else 0
        }
    
    def log_statistics(self) -> None:
        """Log decision statistics"""
        stats = self.get_statistics()
        
        log.info("=" * 60)
        log.info("PRE-ORDER DECISION STATISTICS")
        log.info("=" * 60)
        log.info(f"Total Decisions: {stats['total_decisions']}")
        log.info(f"  ├─ Approved: {stats['approved']}")
        log.info(f"  ├─ Rejected: {stats['rejected']}")
        log.info(f"  └─ Approval Rate: {stats['approval_rate']:.1f}%")
        log.info("=" * 60)
