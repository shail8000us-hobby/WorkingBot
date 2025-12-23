"""
Backtest Adapter for Production Bot

This module provides a safe way to run backtests without modifying
production code. It acts as a compatibility layer between SimExchange
and your production bot's expectations.

Usage in backtest:
    from backtest.adapter import BacktestAdapter
    
    adapter = BacktestAdapter(sim_exchange, config)
    # Use adapter as if it were the real bot
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional

# Suppress production imports that might fail in backtest
os.environ['BACKTEST_MODE'] = 'true'

log = logging.getLogger("backtest.adapter")


class BacktestAdapter:
    """
    Adapter that makes SimExchange compatible with production bot.
    
    This creates a minimal interface that your bot expects,
    routing all calls to SimExchange without touching production code.
    """
    
    def __init__(self, sim_exchange, config: Dict):
        """
        Initialize adapter.
        
        Args:
            sim_exchange: SimExchange instance
            config: Strategy configuration
        """
        self.sim_exchange = sim_exchange
        self.config = config
        self.backtest_mode = True
        
        # Grid parameters
        self.symbol = config.get('symbol', 'BTC/USD:USD')
        self.ref = float(config.get('ref', 112000))
        self.step = float(config.get('step', 100))
        self.lot = float(config.get('lot', 1))
        self.max_open = int(config.get('max_open', 10))
        self.lower = float(config.get('lower', 110000))
        self.upper = float(config.get('upper', 115000))
        self.tick_size = float(config.get('tick_size', 0.5))
        
        # Tracking
        self.last_price = self.ref
        self.filled_buys = []
        
        log.info(f"BacktestAdapter initialized: {self.symbol} REF={self.ref} STEP={self.step}")
    
    def on_tick(self, price: float, timestamp):
        """
        Process price update (main entry point for backtest).
        
        This implements simple grid logic that mirrors your production bot.
        """
        self.last_price = price
        
        # Maintain grid: place BUYs, check for TPs
        self._maintain_grid(price)
    
    def _maintain_grid(self, price: float):
        """Maintain grid orders (BUYs and TPs)."""
        # Get current state
        open_orders = self.sim_exchange.fetch_open_orders()
        position = self.sim_exchange.get_position()
        
        # Count active positions
        position_size = abs(position['contracts'])
        
        # Check capacity
        if position_size >= self.max_open:
            return
        
        # Calculate grid levels
        levels = self._calculate_grid_levels(price)
        
        # Get existing BUY order prices
        buy_prices = {o['price'] for o in open_orders if o['side'] == 'buy' and not o['reduceOnly']}
        
        # Place missing BUY orders
        orders_to_place = self.max_open - position_size - len(buy_prices)
        placed = 0
        
        for level in levels:
            if placed >= orders_to_place:
                break
            
            if level in buy_prices:
                continue
            
            if level >= price:
                # Don't BUY above market
                continue
            
            try:
                self.sim_exchange.create_order(
                    side='buy',
                    price=level,
                    amount=self.lot,
                    reduce_only=False,
                    client_id=f"GBOT_{level}"
                )
                placed += 1
            except Exception as e:
                log.debug(f"Could not place BUY at {level}: {e}")
        
        # Check for fills and place TPs
        self._check_fills_and_place_tps(open_orders, position)
    
    def _check_fills_and_place_tps(self, open_orders, position):
        """Check if any BUYs filled and place corresponding TPs."""
        # Get filled orders from sim exchange's trade log
        trades_df = self.sim_exchange.get_trades_df()
        
        if trades_df.empty:
            return
        
        # Find recent BUY fills that don't have TPs yet
        recent_buys = trades_df[
            (trades_df['side'] == 'buy') &
            (~trades_df['reduce_only'])
        ]
        
        # Get existing TP prices
        tp_prices = {o['price'] for o in open_orders if o['side'] == 'sell' and o['reduceOnly']}
        
        # For each filled BUY, ensure TP exists
        for _, trade in recent_buys.iterrows():
            buy_price = trade['price']
            tp_price = buy_price + self.step
            
            if tp_price in tp_prices:
                continue
            
            # Check if position exists to close
            if position['contracts'] == 0:
                continue
            
            # Place TP
            try:
                self.sim_exchange.create_order(
                    side='sell',
                    price=tp_price,
                    amount=self.lot,
                    reduce_only=True,
                    client_id=f"TP_{tp_price}"
                )
                log.debug(f"Placed TP: {self.lot}@{tp_price} (for BUY@{buy_price})")
            except Exception as e:
                log.debug(f"Could not place TP at {tp_price}: {e}")
    
    def _calculate_grid_levels(self, current_price: float) -> list:
        """Calculate grid levels below current price."""
        levels = []
        
        # Start from REF and go down
        price = self.ref
        while price > self.lower:
            if price < current_price:
                levels.append(price)
            price -= self.step
        
        # Quantize to tick size
        levels = [round(p / self.tick_size) * self.tick_size for p in levels]
        
        # Return closest levels first
        levels.sort(reverse=True)
        return levels[:20]  # Limit to 20 levels
    
    def update(self, price: float, timestamp):
        """Alias for on_tick (compatibility)."""
        self.on_tick(price, timestamp)


def create_backtest_strategy(sim_exchange, config: Dict):
    """
    Factory function to create backtest-compatible strategy.
    
    Returns an adapter that works with SimExchange.
    """
    return BacktestAdapter(sim_exchange, config)

