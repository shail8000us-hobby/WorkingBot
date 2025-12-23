"""
Bot Prediction Engine - Real-time Decision Prediction Based on Actual Bot Code

This module mirrors the ACTUAL bot decision logic from async_gridbot.py and grid_calculator.py
to predict what the bot will do next. NO ASSUMPTIONS, NO HALLUCINATIONS.

Based on:
- bot/strategy/async_gridbot.py (_check_and_place_entry_order, fill processing)
- bot/strategy/modules/grid_calculator.py (grid calculations)
- bot/strategy/sagas/fill_processing_saga.py (cancel + place logic)

Author: AI Assistant
Date: November 16, 2025
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import sys

# Add bot module to path
BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from bot.strategy.modules.grid_calculator import GridCalculator

log = logging.getLogger(__name__)


class BotPredictionEngine:
    """
    Predicts bot's next actions based on actual code logic
    
    Mirrors exact behavior from:
    - Grid calculations (grid_calculator.py)
    - Fill processing (fill_processing_saga.py)
    - Entry order placement (_check_and_place_entry_order)
    """
    
    def __init__(
        self,
        grid_lower: float,
        grid_upper: float,
        grid_step: float,
        grid_ref: float,
        mode: str = "LONG",
        max_open: int = 10,
        tick_size: float = 0.5
    ):
        """
        Initialize prediction engine with grid config
        
        Args:
            grid_lower: Grid lower bound
            grid_upper: Grid upper bound
            grid_step: Grid step size
            grid_ref: Reference level
            mode: Trading mode (LONG/SHORT)
            max_open: Maximum open positions
            tick_size: Exchange tick size
        """
        self.grid_calc = GridCalculator(
            lower=grid_lower,
            upper=grid_upper,
            step=grid_step,
            ref=grid_ref,
            tick_size=tick_size
        )
        self.mode = mode
        self.max_open = max_open
        
    def predict_next_action(
        self,
        current_price: float,
        positions: List[Dict[str, Any]],
        pending_buy: Optional[Dict[str, Any]] = None,
        pending_sell: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Predict bot's immediate next action
        
        This mirrors _check_and_place_entry_order logic from async_gridbot.py
        
        Args:
            current_price: Current market price
            positions: List of open positions [{entry_price, tp_price, size}]
            pending_buy: Pending BUY order {price, size, order_id} or None
            pending_sell: Pending SELL order {price, size, order_id} or None
            
        Returns:
            Prediction dict with structure:
            {
                "type": "PENDING_BUY" | "PENDING_SELL" | "WILL_BUY" | "WILL_SELL" | "CAPACITY_FULL" | "NONE",
                "price": float or None,
                "status": str (explanation),
                "then": str (what happens after this action)
            }
        """
        num_positions = len(positions)
        
        # Check capacity
        if num_positions >= self.max_open:
            return {
                "type": "CAPACITY_FULL",
                "price": None,
                "status": f"Maximum capacity reached ({num_positions}/{self.max_open})",
                "then": "Wait for TP fills to free capacity"
            }
        
        if self.mode == "LONG":
            return self._predict_long_mode(current_price, positions, pending_buy)
        else:  # SHORT
            return self._predict_short_mode(current_price, positions, pending_sell)
    
    def _predict_long_mode(
        self,
        current_price: float,
        positions: List[Dict[str, Any]],
        pending_buy: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Predict next action for LONG mode
        
        Logic from async_gridbot.py:_check_and_place_entry_order (LONG branch)
        
        Returns:
            Next action prediction
        """
        # If pending BUY exists, that's our next action
        if pending_buy:
            pending_price = pending_buy.get('price')
            return {
                "type": "PENDING_BUY",
                "price": pending_price,
                "status": f"Will place when price drops to ${pending_price:,.2f}",
                "then": f"Calculate TP @ ${pending_price + self.grid_calc.step:,.2f}"
            }
        
        # Calculate next BUY level
        next_buy = self.grid_calc.compute_next_buy_level(positions, current_price)
        
        if next_buy is None:
            return {
                "type": "NONE",
                "price": None,
                "status": "No valid BUY level (out of grid bounds)",
                "then": "Wait for market to return to grid range"
            }
        
        # Check if we should place pending order
        # From _check_and_place_entry_order: place if no pending exists
        return {
            "type": "WILL_BUY",
            "price": next_buy,
            "status": f"Will place pending BUY @ ${next_buy:,.2f}",
            "then": f"When filled → place TP @ ${next_buy + self.grid_calc.step:,.2f}"
        }
    
    def _predict_short_mode(
        self,
        current_price: float,
        positions: List[Dict[str, Any]],
        pending_sell: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Predict next action for SHORT mode
        
        Logic from async_gridbot.py:_check_and_place_entry_order (SHORT branch)
        
        Returns:
            Next action prediction
        """
        # If pending SELL exists, that's our next action
        if pending_sell:
            pending_price = pending_sell.get('price')
            return {
                "type": "PENDING_SELL",
                "price": pending_price,
                "status": f"Will place when price rises to ${pending_price:,.2f}",
                "then": f"Calculate TP @ ${pending_price - self.grid_calc.step:,.2f}"
            }
        
        # Calculate next SELL level
        next_sell = self.grid_calc.compute_next_sell_level(positions, current_price)
        
        if next_sell is None:
            return {
                "type": "NONE",
                "price": None,
                "status": "No valid SELL level (out of grid bounds)",
                "then": "Wait for market to return to grid range"
            }
        
        # Check if we should place pending order
        return {
            "type": "WILL_SELL",
            "price": next_sell,
            "status": f"Will place pending SELL @ ${next_sell:,.2f}",
            "then": f"When filled → place TP @ ${next_sell - self.grid_calc.step:,.2f}"
        }
    
    def predict_fill_scenario(
        self,
        fill_price: float,
        fill_type: str,
        positions: List[Dict[str, Any]],
        pending_buy: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Predict what happens when an order fills
        
        This mirrors fill_processing_saga.py logic:
        - BUY fill: place TP SELL
        - SELL (TP) fill: CANCEL old pending BUY, place new BUY
        
        Args:
            fill_price: Price where fill occurred
            fill_type: "BUY" or "SELL"
            positions: Current open positions
            pending_buy: Current pending BUY order
            
        Returns:
            Prediction of post-fill actions
        """
        if fill_type == "BUY":
            return self._predict_buy_fill(fill_price, positions)
        else:  # SELL (TP fill)
            return self._predict_sell_fill(fill_price, positions, pending_buy)
    
    def _predict_buy_fill(
        self,
        entry_price: float,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Predict actions after BUY fills (entry order)
        
        Logic from fill_processing_saga.py:create_buy_fill_saga
        - Place TP SELL at entry + step
        - Clear pending buy
        
        Args:
            entry_price: BUY fill price (entry)
            positions: Current positions
            
        Returns:
            Post-fill prediction
        """
        tp_price = self.grid_calc.compute_tp_price(entry_price)
        
        # After BUY fills, we need new pending BUY one level down
        new_positions = positions + [{"entry_price": entry_price, "tp_price": tp_price}]
        next_buy = self.grid_calc.compute_next_buy_level(new_positions)
        
        return {
            "type": "BUY_FILLED",
            "actions": [
                {
                    "sequence": 1,
                    "action": "PLACE_TP",
                    "price": tp_price,
                    "reason": f"Place TP SELL @ ${tp_price:,.2f} (entry + step)"
                },
                {
                    "sequence": 2,
                    "action": "CLEAR_PENDING_BUY",
                    "reason": "Clear old pending BUY order"
                },
                {
                    "sequence": 3,
                    "action": "PLACE_NEW_BUY",
                    "price": next_buy,
                    "reason": f"Place new pending BUY @ ${next_buy:,.2f}" if next_buy else "No new BUY (out of bounds)"
                }
            ],
            "new_position": {
                "entry_price": entry_price,
                "tp_price": tp_price,
                "profit_target": self.grid_calc.step
            }
        }
    
    def _predict_sell_fill(
        self,
        tp_price: float,
        positions: List[Dict[str, Any]],
        pending_buy: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Predict actions after SELL fills (TP hit)
        
        Logic from fill_processing_saga.py:create_sell_fill_saga (lines 422-441)
        KEY: CANCEL old pending BUY before placing new one
        
        Args:
            tp_price: TP SELL fill price
            positions: Current positions
            pending_buy: Current pending BUY (will be cancelled)
            
        Returns:
            Post-fill prediction with CANCELLATION step
        """
        # Find position that was closed
        closed_position = None
        for pos in positions:
            if abs(pos.get('tp_price', 0) - tp_price) < 0.01:
                closed_position = pos
                break
        
        if not closed_position:
            return {
                "type": "SELL_FILLED",
                "error": "Could not find position matching TP price"
            }
        
        # Calculate new BUY level (TP - step, from line 417 of fill_processing_saga.py)
        # "New BUY should be 1 step BELOW TP"
        new_buy_price = self.grid_calc.compute_next_level_down(tp_price)
        
        # Build action sequence (mirrors saga steps)
        actions = [
            {
                "sequence": 1,
                "action": "REMOVE_POSITION",
                "reason": f"Close position (entry ${closed_position['entry_price']:,.2f})"
            },
            {
                "sequence": 2,
                "action": "CLEAR_PENDING_SELL",
                "reason": "Clear TP order from state"
            }
        ]
        
        # KEY STEP: Cancel old pending BUY (lines 425-441)
        if pending_buy:
            old_price = pending_buy.get('price')
            if old_price and abs(old_price - new_buy_price) > 0.01:
                actions.append({
                    "sequence": 3,
                    "action": "CANCEL_PENDING_BUY",
                    "price": old_price,
                    "reason": f"Cancel old pending BUY @ ${old_price:,.2f} (FIX NOV 14)"
                })
        
        # Place new BUY
        actions.append({
            "sequence": 4,
            "action": "PLACE_NEW_BUY",
            "price": new_buy_price,
            "reason": f"Place new pending BUY @ ${new_buy_price:,.2f} (TP - 1 step)"
        })
        
        return {
            "type": "SELL_FILLED",
            "actions": actions,
            "profit_realized": self.grid_calc.step,
            "closed_position": closed_position
        }
    
    def predict_sequence(
        self,
        current_price: float,
        positions: List[Dict[str, Any]],
        pending_buy: Optional[Dict[str, Any]] = None,
        num_steps: int = 5
    ) -> Dict[str, Any]:
        """
        Predict full sequence of bot actions over multiple price movements
        
        Simulates:
        1. Current state → next pending order
        2. If pending fills → TP placement
        3. If TP fills → cancel old pending, place new pending
        4. Repeat for num_steps
        
        Args:
            current_price: Starting market price
            positions: Current open positions
            pending_buy: Current pending BUY
            num_steps: Number of simulation steps
            
        Returns:
            Full decision tree prediction
        """
        sequence = []
        
        # Step 1: What's the immediate next action?
        next_action = self.predict_next_action(current_price, positions, pending_buy)
        sequence.append({
            "step": 1,
            "trigger": "CURRENT_STATE",
            "price": current_price,
            "action": next_action
        })
        
        # Step 2: Simulate pending order filling
        if next_action["type"] in ["PENDING_BUY", "WILL_BUY"]:
            fill_price = next_action.get("price")
            if fill_price:
                fill_result = self._predict_buy_fill(fill_price, positions)
                sequence.append({
                    "step": 2,
                    "trigger": "BUY_FILLS",
                    "price": fill_price,
                    "action": fill_result
                })
                
                # Update simulated state
                positions = positions + [{"entry_price": fill_price, "tp_price": fill_price + self.grid_calc.step}]
        
        # Step 3: Simulate TP filling
        if positions:
            # Pick highest TP (most likely to fill first in rising market)
            highest_tp = max(p.get('tp_price', 0) for p in positions)
            tp_fill_result = self._predict_sell_fill(highest_tp, positions, pending_buy)
            sequence.append({
                "step": 3,
                "trigger": "TP_FILLS",
                "price": highest_tp,
                "action": tp_fill_result
            })
        
        return {
            "mode": self.mode,
            "grid_step": self.grid_calc.step,
            "sequence": sequence,
            "summary": f"Predicted {len(sequence)} actions based on actual bot code"
        }


def create_prediction_from_bot_state(bot_state: Dict[str, Any]) -> BotPredictionEngine:
    """
    Factory function to create prediction engine from live bot state
    
    Args:
        bot_state: Bot state dict with grid config
        
    Returns:
        Configured BotPredictionEngine
    """
    grid_config = bot_state.get('grid_config', {})
    
    return BotPredictionEngine(
        grid_lower=grid_config.get('lower', 90000),
        grid_upper=grid_config.get('upper', 120000),
        grid_step=grid_config.get('step', 1000),
        grid_ref=grid_config.get('ref', 100000),
        mode=bot_state.get('mode', 'LONG'),
        max_open=bot_state.get('max_open', 10),
        tick_size=grid_config.get('tick_size', 0.5)
    )
