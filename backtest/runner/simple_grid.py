"""
Simple Grid Strategy

Simplified grid trading logic for backtesting.
Used when production strategy cannot be imported.
"""

import logging
from typing import Dict, Optional, List

log = logging.getLogger("backtest.simple_grid")


class SimpleGridStrategy:
    """
    Simplified grid strategy for backtesting.
    
    Logic:
    - Calculate grid levels based on REF and STEP
    - Place BUY orders at grid rungs
    - Place TP orders at BUY_PRICE + STEP
    - Respect MAX_OPEN limit
    """
    
    def __init__(self, exchange, config: Dict):
        """
        Initialize simple grid strategy.
        
        Args:
            exchange: SimExchange instance
            config: Strategy configuration
        """
        self.exchange = exchange
        self.config = config
        
        # Grid parameters
        self.symbol = config.get('symbol', 'BTC/USD:USD')
        self.ref = float(config.get('ref', 112000))
        self.step = float(config.get('step', 100))
        self.lot = float(config.get('lot', 1))
        self.max_open = int(config.get('max_open', 10))
        self.lower = float(config.get('lower', 110000))
        self.upper = float(config.get('upper', 115000))
        
        # State
        self.current_price = self.ref
        self.open_buys: Dict[str, float] = {}  # order_id -> price
        self.filled_entries: List[float] = []  # Track filled entry prices
        
        log.info(f"SimpleGrid: REF={self.ref} STEP={self.step} LOT={self.lot} MAX_OPEN={self.max_open}")
    
    def on_tick(self, price: float, timestamp):
        """
        Process new price tick.
        
        Args:
            price: Current market price
            timestamp: Current timestamp
        """
        self.current_price = price
        
        # Check if we have capacity for new orders
        position = self.exchange.get_position()
        current_position_size = abs(position['contracts'])
        
        if current_position_size >= self.max_open:
            # At max capacity
            return
        
        # Place new BUY orders at grid levels
        self._maintain_grid_orders()
    
    def _maintain_grid_orders(self):
        """Ensure we have BUY orders at appropriate grid levels."""
        # Get current open orders
        open_orders = self.exchange.fetch_open_orders()
        
        # Count non-TP orders (BUY orders)
        buy_orders = [o for o in open_orders if o['side'] == 'buy' and not o['reduceOnly']]
        
        # Get position
        position = self.exchange.get_position()
        current_position_size = abs(position['contracts'])
        
        # Calculate how many more positions we can open
        remaining_capacity = self.max_open - current_position_size - len(buy_orders)
        
        if remaining_capacity <= 0:
            return
        
        # Calculate grid levels below current price
        grid_levels = self._calculate_grid_levels()
        
        # Check which levels don't have orders
        existing_buy_prices = {o['price'] for o in buy_orders}
        
        # Place new orders
        placed = 0
        for level in grid_levels:
            if level in existing_buy_prices:
                continue
            
            if level >= self.current_price:
                # Don't place BUY above current price
                continue
            
            # Place BUY order
            try:
                order = self.exchange.create_order(
                    side='buy',
                    price=level,
                    amount=self.lot,
                    reduce_only=False,
                    client_id=f"GRID_{level}"
                )
                
                log.debug(f"Placed BUY: {self.lot}@{level}")
                placed += 1
                
                if placed >= remaining_capacity:
                    break
                    
            except Exception as e:
                log.error(f"Failed to place BUY at {level}: {e}")
    
    def _calculate_grid_levels(self) -> List[float]:
        """Calculate grid levels based on REF and STEP."""
        levels = []
        
        # Calculate levels below REF
        price = self.ref - self.step
        while price >= self.lower:
            levels.append(price)
            price -= self.step
        
        # Sort ascending (lowest first)
        levels.sort()
        
        # Limit to reasonable number
        return levels[-20:]  # Only keep 20 closest levels
    
    def update(self, price: float, timestamp):
        """Alias for on_tick (for compatibility)."""
        self.on_tick(price, timestamp)

