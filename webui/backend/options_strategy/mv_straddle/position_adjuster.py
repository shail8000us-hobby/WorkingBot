"""
Position Adjuster for MV Straddle
Handles rolling, closing one leg, adjusting ratios
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PositionAdjuster:
    """Adjust existing straddle positions"""
    
    def __init__(self, api_client, strategy_manager):
        self.api_client = api_client
        self.strategy_manager = strategy_manager
    
    def close_one_leg(
        self,
        strategy_id: str,
        leg_type: str  # "call" or "put"
    ) -> Dict:
        """
        Close one leg of straddle (convert to long/short call or put)
        
        Use case: Price moved significantly, want to lock in profit on one side
        
        Args:
            strategy_id: Strategy ID
            leg_type: "call" or "put" - which leg to close
        
        Returns:
            {
                'success': bool,
                'closed_leg': str,
                'order': {...},
                'remaining_position': str
            }
        """
        try:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if not strategy:
                return {"success": False, "error": "Strategy not found"}
            
            # Find the leg to close
            leg_to_close = None
            for leg in strategy["legs"]:
                if leg["option_type"] == leg_type.lower():
                    leg_to_close = leg
                    break
            
            if not leg_to_close:
                return {"success": False, "error": f"No {leg_type} leg found in strategy"}
            
            # Close the leg (reverse the position)
            symbol = leg_to_close["symbol"]
            size = abs(leg_to_close["quantity"])
            side = "buy" if leg_to_close["side"] == "sell" else "sell"
            
            logger.info(f"Closing {leg_type} leg: {symbol}, size: {size}, side: {side}")
            
            # Place closing order
            order_result = self.api_client.place_order(
                symbol=symbol,
                size=size,
                side=side,
                order_type="market_order"
            )
            
            # Determine remaining position
            remaining_leg = "put" if leg_type.lower() == "call" else "call"
            remaining_direction = "long" if leg_to_close["side"] == "buy" else "short"
            remaining_position = f"{remaining_direction}_{remaining_leg}"
            
            logger.info(f"Closed {leg_type} leg of strategy {strategy_id}. Remaining: {remaining_position}")
            
            return {
                "success": True,
                "closed_leg": leg_type,
                "order": order_result,
                "remaining_position": remaining_position,
                "message": f"Closed {leg_type} leg. Now holding {remaining_position}"
            }
            
        except Exception as e:
            logger.error(f"Error closing leg: {e}")
            return {"success": False, "error": str(e)}
    
    def roll_straddle(
        self,
        strategy_id: str,
        new_expiry: str,
        new_strike: Optional[int] = None,
        keep_same_strike: bool = True
    ) -> Dict:
        """
        Roll straddle to new expiry (and optionally new strike)
        
        Process:
        1. Close existing straddle
        2. Open new straddle at new expiry/strike
        
        Args:
            strategy_id: Current strategy ID
            new_expiry: New expiry date (DDMMYYYY)
            new_strike: New strike price (optional)
            keep_same_strike: Use same strike as current (if new_strike not provided)
        
        Returns:
            {
                'success': bool,
                'closed_strategy_id': str,
                'new_strategy_id': str,
                'execution': {...}
            }
        """
        try:
            # Get current strategy
            old_strategy = self.strategy_manager.get_strategy(strategy_id)
            if not old_strategy:
                return {"success": False, "error": "Strategy not found"}
            
            # Extract current parameters
            current_strike = old_strategy["legs"][0]["strike"]
            current_quantity = abs(old_strategy["legs"][0]["quantity"])
            current_direction = old_strategy["legs"][0]["side"]
            underlying = old_strategy.get("underlying", "BTC")
            
            # Determine new strike
            if new_strike is None and keep_same_strike:
                new_strike = current_strike
            elif new_strike is None:
                return {"success": False, "error": "Must provide new_strike if keep_same_strike=False"}
            
            logger.info(f"Rolling strategy {strategy_id}: {current_strike} -> {new_strike}, expiry -> {new_expiry}")
            
            # Step 1: Close existing position
            close_results = []
            for leg in old_strategy["legs"]:
                symbol = leg["symbol"]
                size = abs(leg["quantity"])
                side = "buy" if leg["side"] == "sell" else "sell"
                
                order_result = self.api_client.place_order(
                    symbol=symbol,
                    size=size,
                    side=side,
                    order_type="market_order"
                )
                close_results.append(order_result)
            
            # Step 2: Create new strategy
            new_strategy_result = self.strategy_manager.create_mv_straddle(
                name=f"Rolled {old_strategy['name']}",
                underlying=underlying,
                expiry=new_expiry,
                strike=new_strike,
                direction=current_direction,
                quantity=current_quantity,
                auto_strike=False
            )
            
            if not new_strategy_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to create new strategy: {new_strategy_result.get('error')}",
                    "closed_orders": close_results
                }
            
            return {
                "success": True,
                "closed_strategy_id": strategy_id,
                "new_strategy_id": new_strategy_result["strategy"]["id"],
                "close_orders": close_results,
                "new_strategy": new_strategy_result["strategy"],
                "message": f"Rolled from strike {current_strike} to {new_strike}, expiry {new_expiry}"
            }
            
        except Exception as e:
            logger.error(f"Error rolling straddle: {e}")
            return {"success": False, "error": str(e)}
    
    def adjust_ratio(
        self,
        strategy_id: str,
        call_quantity: int,
        put_quantity: int
    ) -> Dict:
        """
        Adjust call:put ratio (e.g., 2:1 for bullish bias)
        
        Process:
        1. Calculate difference from current quantities
        2. Place orders to adjust to target quantities
        
        Args:
            strategy_id: Strategy ID
            call_quantity: Target call contracts
            put_quantity: Target put contracts
        
        Returns:
            {
                'success': bool,
                'adjustment_orders': [...],
                'new_ratio': str
            }
        """
        try:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if not strategy:
                return {"success": False, "error": "Strategy not found"}
            
            # Find current quantities
            current_call_qty = 0
            current_put_qty = 0
            call_symbol = None
            put_symbol = None
            
            for leg in strategy["legs"]:
                if leg["option_type"] == "call":
                    current_call_qty = abs(leg["quantity"])
                    call_symbol = leg["symbol"]
                elif leg["option_type"] == "put":
                    current_put_qty = abs(leg["quantity"])
                    put_symbol = leg["symbol"]
            
            # Calculate adjustments needed
            call_adjustment = call_quantity - current_call_qty
            put_adjustment = put_quantity - current_put_qty
            
            adjustment_orders = []
            
            # Adjust call position
            if call_adjustment != 0:
                call_side = "buy" if call_adjustment > 0 else "sell"
                call_size = abs(call_adjustment)
                
                call_order = self.api_client.place_order(
                    symbol=call_symbol,
                    size=call_size,
                    side=call_side,
                    order_type="market_order"
                )
                adjustment_orders.append({
                    "leg": "call",
                    "action": call_side,
                    "quantity": call_size,
                    "order": call_order
                })
            
            # Adjust put position
            if put_adjustment != 0:
                put_side = "buy" if put_adjustment > 0 else "sell"
                put_size = abs(put_adjustment)
                
                put_order = self.api_client.place_order(
                    symbol=put_symbol,
                    size=put_size,
                    side=put_side,
                    order_type="market_order"
                )
                adjustment_orders.append({
                    "leg": "put",
                    "action": put_side,
                    "quantity": put_size,
                    "order": put_order
                })
            
            # Calculate new ratio
            new_ratio = f"{call_quantity}:{put_quantity}"
            
            logger.info(f"Adjusted ratio for strategy {strategy_id}: {current_call_qty}:{current_put_qty} -> {call_quantity}:{put_quantity}")
            
            return {
                "success": True,
                "adjustment_orders": adjustment_orders,
                "old_ratio": f"{current_call_qty}:{current_put_qty}",
                "new_ratio": new_ratio,
                "message": f"Adjusted ratio to {new_ratio}"
            }
            
        except Exception as e:
            logger.error(f"Error adjusting ratio: {e}")
            return {"success": False, "error": str(e)}
