"""
GridCalculator - Pure Grid Logic Module

Single Responsibility: Calculate grid prices and validate grid bounds

This module contains ZERO state and ZERO side effects.
All functions are pure - same inputs always produce same outputs.

Extracted from GridBotWebSocket (Phase 1 - Safest extraction)
"""

import logging
import math
from typing import List, Dict, Optional, Any
from decimal import Decimal, ROUND_DOWN

from webui.backend.sealed import sealed

log = logging.getLogger("runner")


class GridCalculator:
    """
    Pure grid calculation logic (no state, no side effects)
    
    Responsibilities:
    - Calculate next BUY level based on positions
    - Calculate TP price from entry price
    - Quantize prices to exchange tick size
    - Validate prices within grid bounds
    
    NOT Responsible For:
    - Order placement
    - State management
    - Network I/O
    - Position tracking
    """
    
    def __init__(
        self,
        lower: float,
        upper: float,
        step: float,
        ref: float,
        tick_size: float = 0.5
    ):
        """
        Initialize grid calculator with grid parameters
        
        Args:
            lower: Grid lower bound (e.g., 105000)
            upper: Grid upper bound (e.g., 120000)
            step: Grid step size (e.g., 1000)
            ref: Reference level (e.g., 110000)
            tick_size: Exchange tick size for quantization (default: 0.5)
        
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate grid parameters
        if step <= 0:
            raise ValueError("Step must be positive")
        if math.isinf(step) or math.isnan(step):
            raise ValueError("Step must be a finite number")
        if tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if math.isinf(tick_size) or math.isnan(tick_size):
            raise ValueError("tick_size must be a finite number")
        if lower >= upper:
            raise ValueError("Lower bound must be less than upper bound")
        if not (lower <= ref <= upper):
            raise ValueError("Reference must be within grid bounds")
        
        self.lower = float(lower)
        self.upper = float(upper)
        self.step = float(step)
        self.ref = float(ref)
        self.tick_size = float(tick_size)
    
    @sealed
    def compute_next_buy_level(
        self,
        open_positions: List[Dict[str, Any]],
        current_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Compute the next BUY level for grid trading
        
        ✅ FIX NOV 6: Added defensive grid alignment validation
        ✅ FIX NOV 7: Added current_price to prevent placing BUY above market
        
        Logic:
        - If no positions: BUY at (ref - step), or nearest grid below market if ref is too high
        - If positions exist: BUY at (lowest_entry - step)
        - Quantize to tick size
        - Return None if outside grid bounds
        
        Args:
            open_positions: List of open position dicts with 'entry_price' key
            current_price: Optional current market price (for validation)
            
        Returns:
            Next BUY price (quantized), or None if no BUY needed
        """
        # Find lowest entry price
        if open_positions:
            lowest_entry = min(p['entry_price'] for p in open_positions)
            
            # ✅ FIX NOV 6: Validate lowest_entry is grid-aligned
            if not self.is_price_grid_aligned(lowest_entry):
                log.error(f"⚠️ Position entry ${lowest_entry:,.2f} is OFF-GRID!")
                log.error(f"   Snapping to nearest grid level...")
                lowest_entry = self.find_nearest_grid_level(lowest_entry)
                log.warning(f"   Corrected to: ${lowest_entry:,.2f}")
            
            # Calculate target one step below existing position
            target = lowest_entry - self.step
        else:
            # ✅ FIX NOV 20: If no positions, place at nearest grid BELOW current price
            if current_price and current_price < self.ref:
                # Market is below REF, find nearest grid level below market
                target = self.find_nearest_grid_below(current_price)
                if target:
                    log.info(f"📍 No positions + market below REF: placing at ${target:,.0f} (nearest grid below ${current_price:,.0f})")
                else:
                    # No valid level below market within grid
                    return None
            else:
                # Market at or above REF, use standard logic
                target = self.ref - self.step
        
        # ✅ FIX NOV 6: Double-check target is grid-aligned
        if not self.is_price_grid_aligned(target):
            log.critical(f"🚨 CRITICAL: Calculated target ${target:,.2f} is OFF-GRID!")
            log.critical(f"   This should NEVER happen if entry prices are valid!")
            # Force snap to grid
            target = self.find_nearest_grid_level(target)
            log.critical(f"   Emergency correction to: ${target:,.2f}")
        
        # Validate within bounds
        if not self.is_within_bounds(target):
            return None
        
        # Quantize to tick size
        return self.quantize_price(target)
    
    def compute_next_sell_level(
        self,
        open_positions: List[Dict[str, Any]],
        current_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Compute the next SELL level for SHORT grid trading
        
        ✅ FIX NOV 6: Added defensive grid alignment validation
        ✅ FIX NOV 7: Added current_price to prevent placing SELL below market
        
        Logic (mirror of compute_next_buy_level):
        - If no positions: SELL at (ref + step), or nearest grid above market if ref is too low
        - If positions exist: SELL at (highest_entry + step)
        - Quantize to tick size
        - Return None if outside grid bounds
        
        Args:
            open_positions: List of open position dicts with 'entry_price' key
            current_price: Optional current market price (for validation)
            
        Returns:
            Next SELL price (quantized), or None if no SELL needed
        """
        # Find highest entry price
        if open_positions:
            highest_entry = max(p['entry_price'] for p in open_positions)
            
            # ✅ FIX NOV 6: Validate highest_entry is grid-aligned
            if not self.is_price_grid_aligned(highest_entry):
                log.error(f"⚠️ Position entry ${highest_entry:,.2f} is OFF-GRID!")
                log.error(f"   Snapping to nearest grid level...")
                highest_entry = self.find_nearest_grid_level(highest_entry)
                log.warning(f"   Corrected to: ${highest_entry:,.2f}")
            
            # Calculate target one step above existing position
            target = highest_entry + self.step
        else:
            # ✅ FIX NOV 20: If no positions, place at nearest grid ABOVE current price
            if current_price and current_price > self.ref:
                # Market is above REF, find nearest grid level above market
                target = self.find_nearest_grid_above(current_price)
                if target:
                    log.info(f"📍 No positions + market above REF: placing at ${target:,.0f} (nearest grid above ${current_price:,.0f})")
                else:
                    # No valid level above market within grid
                    return None
            else:
                # Market at or below REF, use standard logic
                target = self.ref + self.step
        
        # ✅ FIX NOV 6: Double-check target is grid-aligned
        if not self.is_price_grid_aligned(target):
            log.critical(f"🚨 CRITICAL: Calculated target ${target:,.2f} is OFF-GRID!")
            log.critical(f"   This should NEVER happen if entry prices are valid!")
            # Force snap to grid
            target = self.find_nearest_grid_level(target)
            log.critical(f"   Emergency correction to: ${target:,.2f}")
        
        # Validate within bounds
        if not self.is_within_bounds(target):
            return None
        
        # Quantize to tick size
        return self.quantize_price(target)
    
    @sealed
    def compute_tp_price(self, entry_price: float) -> float:
        """
        Compute take-profit price from entry price (LONG mode)
        
        Args:
            entry_price: Position entry price
            
        Returns:
            TP price (entry + step)
        """
        return entry_price + self.step
    
    def compute_tp_price_short(self, entry_price: float) -> float:
        """
        Compute take-profit price from entry price (SHORT mode)
        
        For SHORT: TP is BELOW entry (BUY back at lower price)
        
        Args:
            entry_price: SELL entry price
            
        Returns:
            TP price (entry - step)
        """
        return entry_price - self.step
    
    def compute_next_level_down(self, current_price: float) -> float:
        """
        Compute next grid level below current price (LONG mode)
        
        Args:
            current_price: Current price level
            
        Returns:
            Next level down (current - step)
        """
        return current_price - self.step
    
    def compute_next_level_up(self, current_price: float) -> float:
        """
        Compute next grid level above current price (SHORT mode)
        
        Args:
            current_price: Current price level
            
        Returns:
            Next level up (current + step)
        """
        return current_price + self.step
    
    @sealed
    def quantize_price(self, price: float) -> float:
        """
        Quantize price to exchange tick size (snap down)
        
        Args:
            price: Raw price
            
        Returns:
            Price snapped to tick size (floor)
        
        Raises:
            ValueError: If price is NaN or Infinity
        
        Note:
            Uses Decimal for precise arithmetic to avoid floating point drift.
            This ensures idempotence: quantize(quantize(x)) == quantize(x)
            
            Bug Fix: Property-based testing revealed floating point errors
            with certain tick sizes (e.g., 0.74, 0.02) that caused drift.
            
            Fuzzing Fix: Added validation to reject NaN/Infinity inputs to
            prevent NaN propagation through calculations.
        """
        # Validate price is finite
        if not math.isfinite(price):
            raise ValueError(f"Price must be finite, got {price}")
        
        # Use Decimal for precise arithmetic to avoid floating point drift
        # CRITICAL FIX NOV 8: Ensure idempotence through consistent decimal operations
        
        # Convert to Decimal using repr() for full float precision
        # repr() gives the shortest string that round-trips through float()
        price_decimal = Decimal(repr(price))
        tick_decimal = Decimal(repr(self.tick_size))
        
        # Calculate number of ticks (floor using Decimal division + quantize)
        # ROUND_DOWN ensures we always floor, never ceil or round
        ticks_exact = (price_decimal / tick_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN)
        ticks = int(ticks_exact)
        
        # Multiply back using Decimal for exact result
        quantized_decimal = Decimal(ticks) * tick_decimal
        
        # Convert back to float
        # This is idempotent because quantized_decimal is always ticks * tick_size
        return float(quantized_decimal)
    
    @sealed
    def is_within_bounds(
        self,
        price: float,
        lower: Optional[float] = None,
        upper: Optional[float] = None
    ) -> bool:
        """
        Check if price is within grid bounds
        
        Args:
            price: Price to check
            lower: Lower bound (defaults to self.lower)
            upper: Upper bound (defaults to self.upper)
            
        Returns:
            True if price is within bounds
        """
        if lower is None:
            lower = self.lower
        if upper is None:
            upper = self.upper
        
        return lower <= price <= upper
    
    @sealed
    def get_grid_levels(self) -> List[float]:
        """
        Generate all grid levels from lower to upper
        
        ✅ FIX NOV 8: Ensure all levels are within bounds after quantization
        ✅ FIX NOV 8: Generate levels without quantization, then validate
        
        Returns:
            List of grid levels (quantized and within bounds)
        """
        levels = []
        current = self.lower
        
        # Generate levels up to upper bound
        while current <= self.upper:
            # Only include levels that remain within bounds after quantization
            quantized = self.quantize_price(current)
            
            # Verify quantized level is still within original bounds
            if self.is_within_bounds(quantized):
                levels.append(quantized)
            
            current += self.step
        
        # Edge case: Ensure upper bound itself is included if it's grid-aligned
        # This handles cases where step doesn't divide evenly into range
        upper_quantized = self.quantize_price(self.upper)
        if upper_quantized not in levels and self.is_within_bounds(upper_quantized):
            # Check if upper is approximately grid-aligned
            if self.is_price_grid_aligned(self.upper, tolerance=0.01):
                levels.append(upper_quantized)
        
        return levels
    
    @sealed
    def is_price_grid_aligned(self, price: float, tolerance: float = 0.01) -> bool:
        """
        Check if price is aligned to grid step
        
        ✅ FIX NOV 6: Helper method for grid validation
        
        Args:
            price: Price to check
            tolerance: Allowed deviation (default 0.01)
            
        Returns:
            True if price is on a grid level
        """
        # Calculate distance from lower boundary
        offset = price - self.lower
        
        # Check if offset is multiple of step
        remainder = offset % self.step
        
        # Allow small floating point tolerance
        return remainder < tolerance or (self.step - remainder) < tolerance
    
    @sealed
    def find_nearest_grid_level(self, price: float) -> float:
        """
        Find nearest grid level to given price (for alignment)
        
        Used in grid realignment after opportunistic recovery.
        
        Args:
            price: Target price
            
        Returns:
            Nearest grid level (rounded to step boundary and quantized)
        """
        # Calculate distance from lower boundary
        offset = price - self.lower
        
        # Round to nearest step and add back to lower
        nearest_steps = round(offset / self.step)
        grid_level = self.lower + (nearest_steps * self.step)
        
        # ✅ FIX NOV 10: Quantize to tick size to avoid floating-point precision issues
        # This ensures grid_level - step is also precisely on-grid
        return self.quantize_price(grid_level)
    
    @sealed
    def find_nearest_grid_below(self, price: float) -> Optional[float]:
        """
        Find nearest grid level strictly below given price.
        
        Used by Strict Grid to find MAKER order levels (LONG mode).
        
        Example:
            Grid: 800, 810, 820, 830...950, 960, 970...
            Price: 960
            Returns: 950 (nearest level below 960)
        
        Args:
            price: Reference price (usually current market price)
            
        Returns:
            Nearest grid level below price, or None if out of bounds
        """
        # Start from lower boundary and work up
        grid_level = self.lower
        last_valid = None
        
        # Find all levels below price
        while grid_level < price:
            if self.is_within_bounds(grid_level):
                last_valid = grid_level
            grid_level += self.step
            
            # Safety: prevent infinite loop
            if grid_level > self.upper:
                break
        
        return last_valid
    
    def find_nearest_grid_above(self, price: float) -> Optional[float]:
        """
        Find nearest grid level strictly above given price.
        
        Used by Strict Grid to find MAKER order levels (SHORT mode).
        
        Example:
            Grid: 800, 810, 820, 830...950, 960, 970...
            Price: 960
            Returns: 970 (nearest level above 960)
        
        Args:
            price: Reference price (usually current market price)
            
        Returns:
            Nearest grid level above price, or None if out of bounds
        """
        # Start from price and work up
        grid_level = self.lower
        
        # Find first level above price
        while grid_level <= price:
            grid_level += self.step
            
            # Safety: prevent infinite loop
            if grid_level > self.upper:
                return None
        
        # Validate the level is within bounds
        if self.is_within_bounds(grid_level):
            return grid_level
        
        return None
    
    @sealed
    def get_startup_maker_buy_level(
        self,
        current_price: float,
        open_positions: List[Dict],
        grid_mode: str = 'LONG'
    ) -> Optional[float]:
        """
        Get initial order level for bot startup that ensures MAKER order placement.
        
        ✅ SUPPORTS BOTH MODES - Automatically routes to correct logic:
        - LONG mode: Finds BUY level below market
        - SHORT mode: Routes to get_startup_maker_sell_level()
        
        This function is ONLY used at bot startup (no positions or first order).
        After the first fill, normal grid logic takes over.
        
        Logic (LONG mode):
        1. Check grid mode and route appropriately
        2. Calculate normal next buy level from grid logic
        3. If that level is ABOVE current market price (would be TAKER):
           - Skip to nearest grid level BELOW market
           - Ensures first order is a MAKER order
        4. If that level is already BELOW market:
           - Use it as-is (already a MAKER order)
        
        Example (LONG):
            Grid: 800-1500, Step: 10, Ref: 1000
            LTP: 960, No positions
            
            Normal calculation: 1000 - 10 = 990 (ABOVE market 960)
            Strict Grid: Find nearest below 960 = 950 ✅
        
        Args:
            current_price: Current market price (LTP)
            open_positions: Existing positions (usually empty at startup)
            grid_mode: Grid trading mode ('LONG' or 'SHORT')
            
        Returns:
            Price that ensures MAKER order, or None if out of bounds
        """
        # Import log here to avoid circular import
        import logging
        log = logging.getLogger(__name__)
        
        # Check grid mode - Route to appropriate function
        if grid_mode.upper() == 'SHORT':
            log.info(f"🔄 Routing to SHORT mode Strict Grid logic")
            return self.get_startup_maker_sell_level(current_price, open_positions)
        elif grid_mode.upper() != 'LONG':
            log.warning(f"⚠️  Unknown grid mode: {grid_mode}, defaulting to LONG")
        
        # LONG mode logic continues below
        # Step 1: Calculate what normal grid logic says
        calculated_target = self.compute_next_buy_level(open_positions)
        
        if calculated_target is None:
            log.warning("⚠️ Grid calculation returned None (out of bounds)")
            return None
        
        # Step 2: Check if calculated target would be MAKER or TAKER
        if calculated_target >= current_price:
            # Would be TAKER order (fills immediately)
            log.warning("=" * 80)
            log.warning(f"🔍 STRICT GRID STARTUP CHECK")
            log.warning(f"   Calculated BUY: ${calculated_target:,.2f}")
            log.warning(f"   Current Market: ${current_price:,.2f}")
            log.warning(f"   ⚠️  Calculated price is ABOVE market (would be TAKER order)")
            log.warning(f"   🎯 Finding nearest grid level BELOW market for MAKER order...")
            log.warning("=" * 80)
            
            # Find highest grid level BELOW current price
            maker_target = self.find_nearest_grid_below(current_price)
            
            if maker_target:
                log.info(f"✅ Strict Grid: Placing BUY @ ${maker_target:,.2f} (MAKER order)")
                log.info(f"   Skipped: ${calculated_target:,.2f} (would have been TAKER)")
                log.info(f"   Benefit: {calculated_target - maker_target:,.2f} points better entry + MAKER rebate")
            else:
                log.error(f"❌ No valid grid level below market ${current_price:,.2f}")
                log.error(f"   Grid lower bound: ${self.lower:,.2f}")
            
            return maker_target
        else:
            # Already below market - use as-is
            log.info(f"✅ Calculated BUY ${calculated_target:,.2f} is below market ${current_price:,.2f}")
            log.info(f"   Placing as MAKER order (no adjustment needed)")
            return calculated_target
    
    def get_startup_maker_sell_level(
        self,
        current_price: float,
        open_positions: List[Dict]
    ) -> Optional[float]:
        """
        Get initial SELL level for bot startup that ensures MAKER order placement (SHORT mode).
        
        ⚠️  SHORT MODE ONLY - This function is designed for SHORT grid trading.
        Mirror of get_startup_maker_buy_level() for SHORT mode.
        
        This function is ONLY used at bot startup (no positions or first order).
        After the first fill, normal grid logic (compute_next_sell_level) takes over.
        
        Logic:
        1. Calculate normal next sell level from grid logic
        2. If that level is BELOW current market price (would be TAKER):
           - Skip to nearest grid level ABOVE market
           - Ensures first order is a MAKER order
        3. If that level is already ABOVE market:
           - Use it as-is (already a MAKER order)
        
        Example:
            Grid: 800-1500, Step: 10, Ref: 1000
            LTP: 1040, No positions
            
            Normal calculation: 1000 + 10 = 1010 (BELOW market 1040)
            Strict Grid: Find nearest above 1040 = 1050 ✅
        
        Args:
            current_price: Current market price (LTP)
            open_positions: Existing positions (usually empty at startup)
            
        Returns:
            Price above current market (MAKER order), or None if out of bounds
        """
        # Import log here to avoid circular import
        import logging
        log = logging.getLogger(__name__)
        
        # Step 1: Calculate what normal grid logic says
        calculated_target = self.compute_next_sell_level(open_positions)
        
        if calculated_target is None:
            log.warning("⚠️ Grid calculation returned None (out of bounds)")
            return None
        
        # Step 2: Check if calculated target would be MAKER or TAKER
        if calculated_target <= current_price:
            # Would be TAKER order (fills immediately)
            log.warning("=" * 80)
            log.warning(f"🔍 STRICT GRID STARTUP CHECK (SHORT MODE)")
            log.warning(f"   Calculated SELL: ${calculated_target:,.2f}")
            log.warning(f"   Current Market: ${current_price:,.2f}")
            log.warning(f"   ⚠️  Calculated price is BELOW market (would be TAKER order)")
            log.warning(f"   🎯 Finding nearest grid level ABOVE market for MAKER order...")
            log.warning("=" * 80)
            
            # Find lowest grid level ABOVE current price
            maker_target = self.find_nearest_grid_above(current_price)
            
            if maker_target:
                log.info(f"✅ Strict Grid: Placing SELL @ ${maker_target:,.2f} (MAKER order)")
                log.info(f"   Skipped: ${calculated_target:,.2f} (would have been TAKER)")
                log.info(f"   Benefit: {maker_target - calculated_target:,.2f} points better entry + MAKER rebate")
            else:
                log.error(f"❌ No valid grid level above market ${current_price:,.2f}")
                log.error(f"   Grid upper bound: ${self.upper:,.2f}")
            
            return maker_target
        else:
            # Already above market - use as-is
            log.info(f"✅ Calculated SELL ${calculated_target:,.2f} is above market ${current_price:,.2f}")
            log.info(f"   Placing as MAKER order (no adjustment needed)")
            return calculated_target
