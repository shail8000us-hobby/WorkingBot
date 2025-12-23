"""
Predictive Decision Display - Show what bot will do next

Makes bot behavior transparent and predictable for users.
"""

import logging
import time
from typing import Optional, List, Dict, Any

log = logging.getLogger("runner")


class PredictiveDecisionDisplay:
    """
    Display predictive bot decisions
    
    Responsibilities:
    - Show next actions based on price movement
    - Display decision tree for current state
    - Predict order placement thresholds
    - Show expected profit/loss scenarios
    """
    
    def __init__(self):
        """Initialize predictive decision display"""
        self.last_display_time = 0
        self.display_interval = 600  # Show every 10 minutes (600 seconds)
        self.last_scenario_hash = None  # Track scenario changes
        self.completed_loops = []  # Track completed loops since bot start
        self.loop_counter = 0  # Total loop counter
        
        log.info("✅ Predictive Decision Display initialized")
    
    def add_completed_loop(self, entry_price: float, exit_price: float, profit: float, grid_mode: str):
        """Track a completed loop"""
        self.loop_counter += 1
        self.completed_loops.append({
            'loop_num': self.loop_counter,
            'entry': entry_price,
            'exit': exit_price,
            'profit': profit,
            'mode': grid_mode,
            'timestamp': time.time()
        })
        log.debug(f"Loop {self.loop_counter} completed: Entry ${entry_price:,.0f} → Exit ${exit_price:,.0f} → Profit ${profit:,.0f}")
    
    def display_decision_map(
        self,
        current_price: float,
        grid_mode: str,
        grid_step: float,
        lower_bound: float,
        upper_bound: float,
        current_positions: int,
        max_positions: int,
        open_tranches: List[Dict[str, Any]],
        pending_order: Optional[Dict[str, Any]] = None,
        volatility_halted: bool = False
    ) -> None:
        """
        Display comprehensive decision map
        
        Args:
            current_price: Current market price
            grid_mode: LONG or SHORT
            grid_step: Grid step size
            lower_bound: Grid lower boundary
            upper_bound: Grid upper boundary
            current_positions: Number of open positions
            max_positions: Maximum allowed positions
            open_tranches: List of open positions
            pending_order: Pending order if any
            volatility_halted: Whether volatility is halted
        """
        # Create a hash of the current scenario to detect changes
        # Include loop counter in hash to detect completed loops
        scenario_key = f"{grid_mode}|{current_positions}|{max_positions}|{bool(pending_order)}|{volatility_halted}|{self.loop_counter}"
        scenario_changed = (scenario_key != self.last_scenario_hash)
        
        # Throttle display unless scenario changed
        current_time = time.time()
        time_since_last = current_time - self.last_display_time
        
        # Display if:
        # 1. Scenario changed (loop completed, position added/closed, etc), OR
        # 2. 10 minutes passed since last display
        if not scenario_changed and time_since_last < self.display_interval:
            return  # Skip this display, too soon and no changes
        
        # Update tracking variables
        self.last_display_time = current_time
        self.last_scenario_hash = scenario_key
        
        log.info("")
        log.info("=" * 80)
        log.info("🔮 GRID STATUS & HISTORY")
        log.info("=" * 80)
        
        # Current state
        log.info(f"📊 CURRENT STATE:")
        log.info(f"  ├─ Mode: {grid_mode}")
        log.info(f"  ├─ Price: ${current_price:,.2f}")
        log.info(f"  ├─ Grid Step: ${grid_step:,.0f}")
        log.info(f"  ├─ Grid Range: ${lower_bound:,.0f} - ${upper_bound:,.0f}")
        log.info(f"  ├─ Positions: {current_positions}/{max_positions}")
        
        if pending_order:
            pending_type = "BUY" if grid_mode == "LONG" else "SELL"
            pending_price = pending_order.get('price', 0)
            log.info(f"  ├─ Pending Order: {pending_type} @ ${pending_price:,.0f}")
        else:
            log.info(f"  ├─ Pending Order: None")
        
        if volatility_halted:
            log.info(f"  └─ Volatility: HALTED 🛑")
        else:
            log.info(f"  └─ Volatility: SAFE ✅")
        
        # Capacity status
        capacity_used_pct = (current_positions / max_positions) * 100 if max_positions > 0 else 0
        capacity_available = max_positions - current_positions
        
        log.info(f"\n📦 CAPACITY:")
        log.info(f"  ├─ Used: {current_positions}/{max_positions} ({capacity_used_pct:.0f}%)")
        log.info(f"  └─ Available: {capacity_available} slot(s)")
        
        # Display completed loops history
        if self.completed_loops:
            total_profit = sum(loop['profit'] for loop in self.completed_loops)
            log.info(f"\n✅ COMPLETED LOOPS (Since bot start):")
            log.info(f"  Total: {len(self.completed_loops)} loops | Profit: ${total_profit:,.2f}")
            log.info(f"")
            
            # Show last 10 completed loops
            recent_loops = self.completed_loops[-10:] if len(self.completed_loops) > 10 else self.completed_loops
            for loop in recent_loops:
                log.info(f"  Loop {loop['loop_num']}:")
                log.info(f"    💰 Entry: ${loop['entry']:,.0f} → Exit: ${loop['exit']:,.0f} → Profit: ${loop['profit']:,.2f}")
            
            if len(self.completed_loops) > 10:
                older_count = len(self.completed_loops) - 10
                older_profit = sum(loop['profit'] for loop in self.completed_loops[:-10])
                log.info(f"  ... and {older_count} older loops (${older_profit:,.2f} profit)")
        
        # Predictive scenarios
        if grid_mode == "LONG":
            self._display_long_scenarios(
                current_price, grid_step, lower_bound, upper_bound,
                capacity_available, open_tranches, pending_order, volatility_halted
            )
        else:
            self._display_short_scenarios(
                current_price, grid_step, lower_bound, upper_bound,
                capacity_available, open_tranches, pending_order, volatility_halted
            )
        
        log.info("=" * 80)
        
        # Quick access information
        log.info("")
        log.info("📊 QUICK ACCESS (Double-click on Desktop):")
        log.info("  ⚡ GridBot Status  → Quick status check")
        log.info("  🔴 View Bot Logs  → Live streaming logs")
        log.info("  📊 PM2 Monitor    → Process & resource monitor")
        log.info("  📈 Grid Status    → Loops & profit history")
        log.info("")
    
    def _display_long_scenarios(
        self,
        current_price: float,
        grid_step: float,
        lower_bound: float,
        upper_bound: float,
        capacity_available: int,
        open_tranches: List[Dict[str, Any]],
        pending_order: Optional[Dict[str, Any]],
        volatility_halted: bool
    ) -> None:
        """Display LONG mode active loops and orders"""
        log.info(f"\n� ACTIVE GRID LOOPS:")
        
        if not open_tranches and not pending_order:
            log.info(f"  └─ No active loops - waiting for price to trigger first buy")
            return
        
        # Sort positions by entry price (highest to lowest for LONG)
        sorted_positions = sorted(open_tranches, key=lambda x: x.get('entry_price', 0), reverse=True)
        
        # Start numbering from completed loops count + 1
        loop_offset = len(self.completed_loops)
        
        # Display each active loop
        for i, pos in enumerate(sorted_positions, 1):
            entry_price = pos.get('entry_price', 0)
            tp_price = pos.get('tp_price', 0)
            size = pos.get('size', 0)
            loop_num = loop_offset + i
            
            log.info(f"\n  Loop {loop_num}:")
            log.info(f"    ✅ Buy order executed @ ${entry_price:,.0f} (Size: {size})")
            if tp_price > 0:
                log.info(f"    📤 TP order placed @ ${tp_price:,.0f}")
            else:
                log.info(f"    ⚠️  TP order missing")
            
            # Calculate next buy level for this loop
            next_buy = entry_price - grid_step
            if next_buy >= lower_bound:
                log.info(f"    ⏳ Next buy level @ ${next_buy:,.0f}")
        
        # Show pending order separately
        if pending_order:
            pending_price = pending_order.get('price', 0)
            pending_id = pending_order.get('order_id', 'unknown')
            loop_num = loop_offset + len(sorted_positions) + 1
            
            log.info(f"\n  Loop {loop_num}:")
            log.info(f"    ⏳ Buy order @ ${pending_price:,.0f} waiting to fill (ID: {pending_id})")
        
        # Show what happens if capacity available
        if capacity_available > 0 and not pending_order and not volatility_halted:
            next_trigger = current_price - grid_step
            if next_trigger >= lower_bound:
                log.info(f"\n  Next Loop:")
                log.info(f"    💡 Will trigger @ ${next_trigger:,.0f} (when price drops)")
        elif volatility_halted:
            log.info(f"\n  ⚠️  New orders halted due to volatility")
        elif capacity_available == 0:
            log.info(f"\n  ⚠️  Grid capacity full - no more loops until TP fills")
    
    def _display_short_scenarios(
        self,
        current_price: float,
        grid_step: float,
        lower_bound: float,
        upper_bound: float,
        capacity_available: int,
        open_tranches: List[Dict[str, Any]],
        pending_order: Optional[Dict[str, Any]],
        volatility_halted: bool
    ) -> None:
        """Display SHORT mode active loops and orders"""
        log.info(f"\n� ACTIVE GRID LOOPS:")
        
        if not open_tranches and not pending_order:
            log.info(f"  └─ No active loops - waiting for price to trigger first sell")
            return
        
        # Sort positions by entry price (lowest to highest for SHORT)
        sorted_positions = sorted(open_tranches, key=lambda x: x.get('entry_price', 0))
        
        # Start numbering from completed loops count + 1
        loop_offset = len(self.completed_loops)
        
        # Display each active loop
        for i, pos in enumerate(sorted_positions, 1):
            entry_price = pos.get('entry_price', 0)
            tp_price = pos.get('tp_price', 0)
            size = pos.get('size', 0)
            loop_num = loop_offset + i
            
            log.info(f"\n  Loop {loop_num}:")
            log.info(f"    ✅ Sell order executed @ ${entry_price:,.0f} (Size: {size})")
            if tp_price > 0:
                log.info(f"    📤 TP order placed @ ${tp_price:,.0f}")
            else:
                log.info(f"    ⚠️  TP order missing")
            
            # Calculate next sell level for this loop
            next_sell = entry_price + grid_step
            if next_sell <= upper_bound:
                log.info(f"    ⏳ Next sell level @ ${next_sell:,.0f}")
        
        # Show pending order separately
        if pending_order:
            pending_price = pending_order.get('price', 0)
            pending_id = pending_order.get('order_id', 'unknown')
            loop_num = loop_offset + len(sorted_positions) + 1
            
            log.info(f"\n  Loop {loop_num}:")
            log.info(f"    ⏳ Sell order @ ${pending_price:,.0f} waiting to fill (ID: {pending_id})")
        
        # Show what happens if capacity available
        if capacity_available > 0 and not pending_order and not volatility_halted:
            next_trigger = current_price + grid_step
            if next_trigger <= upper_bound:
                log.info(f"\n  Next Loop:")
                log.info(f"    💡 Will trigger @ ${next_trigger:,.0f} (when price rises)")
        elif volatility_halted:
            log.info(f"\n  ⚠️  New orders halted due to volatility")
        elif capacity_available == 0:
            log.info(f"\n  ⚠️  Grid capacity full - no more loops until TP fills")
    
    def display_next_action(
        self,
        grid_mode: str,
        current_price: float,
        next_order_price: Optional[float],
        pending_order: Optional[Dict[str, Any]],
        volatility_halted: bool,
        capacity_available: bool
    ) -> None:
        """
        Display next expected action
        
        Args:
            grid_mode: LONG or SHORT
            current_price: Current market price
            next_order_price: Next calculated order price
            pending_order: Pending order if any
            volatility_halted: Whether volatility is halted
            capacity_available: Whether capacity is available
        """
        order_type = "BUY" if grid_mode == "LONG" else "SELL"
        direction = "drops" if grid_mode == "LONG" else "rises"
        
        log.info("")
        log.info("─" * 60)
        log.info(f"⏭️  NEXT EXPECTED ACTION:")
        
        if pending_order:
            pending_price = pending_order.get('price', 0)
            pending_id = pending_order.get('order_id', 'unknown')
            
            if grid_mode == "LONG":
                gap = current_price - pending_price
                gap_pct = (gap / current_price) * 100
                log.info(f"  Waiting for pending {order_type} @ ${pending_price:,.0f}")
                log.info(f"  Price needs to drop ${gap:,.0f} ({gap_pct:.2f}%) to fill")
            else:
                gap = pending_price - current_price
                gap_pct = (gap / current_price) * 100
                log.info(f"  Waiting for pending {order_type} @ ${pending_price:,.0f}")
                log.info(f"  Price needs to rise ${gap:,.0f} (+{gap_pct:.2f}%) to fill")
            
            log.info(f"  Order ID: {pending_id}")
        
        elif volatility_halted:
            log.info(f"  ⏸️  Waiting for volatility to normalize")
            log.info(f"  No new orders until volatility is safe")
        
        elif not capacity_available:
            log.info(f"  ⏸️  Maximum positions reached")
            log.info(f"  Waiting for TP to fill before placing new orders")
        
        elif next_order_price:
            if grid_mode == "LONG":
                gap = current_price - next_order_price
                gap_pct = (gap / current_price) * 100
                log.info(f"  If price {direction} to ${next_order_price:,.0f}:")
                log.info(f"  → Place {order_type} order (gap: ${gap:,.0f}, {gap_pct:.2f}%)")
            else:
                gap = next_order_price - current_price
                gap_pct = (gap / current_price) * 100
                log.info(f"  If price {direction} to ${next_order_price:,.0f}:")
                log.info(f"  → Place {order_type} order (gap: ${gap:,.0f}, +{gap_pct:.2f}%)")
        
        else:
            log.info(f"  ⏸️  No action (price out of grid bounds)")
        
        log.info("─" * 60)
        log.info("")
