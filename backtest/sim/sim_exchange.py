"""
Simulated Exchange

Mock exchange for backtesting that simulates Delta Exchange behavior.
Tracks orders, fills, positions, and maintains a complete trade log.
"""

import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .fee_model import FeeModel
from .funding_model import FundingModel

log = logging.getLogger("backtest.sim")


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELED = "canceled"


@dataclass
class Order:
    """Simulated order."""
    id: str
    symbol: str
    side: OrderSide
    price: float
    amount: float
    reduce_only: bool = False
    client_id: Optional[str] = None
    status: OrderStatus = OrderStatus.OPEN
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None
    fee: float = 0.0
    is_maker: bool = True


@dataclass
class Position:
    """Simulated position."""
    symbol: str
    size: float = 0.0  # Positive = long, negative = short
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0


@dataclass
class Trade:
    """Trade record for logging."""
    timestamp: datetime
    order_id: str
    side: OrderSide
    price: float
    amount: float
    reduce_only: bool
    fee: float
    is_maker: bool
    client_id: Optional[str] = None
    position_size_after: float = 0.0
    realized_pnl: float = 0.0


class SimExchange:
    """
    Simulated exchange for backtesting.
    
    Features:
    - Realistic fill logic using OHLCV candles
    - Position tracking with average entry price
    - Fee calculation (maker/taker)
    - Funding payments
    - Complete trade log
    - Configurable fill priority (TP first vs BUY first)
    """
    
    def __init__(
        self,
        symbol: str = "BTC/USD:USD",
        initial_balance: float = 0.0,
        fee_model: Optional[FeeModel] = None,
        funding_model: Optional[FundingModel] = None,
        same_bar_priority: str = "tp_first",
        tick_size: float = 0.5
    ):
        """
        Initialize simulated exchange.
        
        Args:
            symbol: Trading symbol
            initial_balance: Starting balance (for equity calculation)
            fee_model: Fee calculator
            funding_model: Funding calculator
            same_bar_priority: 'tp_first' or 'buy_first' for same-bar fills
            tick_size: Minimum price increment
        """
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.fee_model = fee_model or FeeModel()
        self.funding_model = funding_model or FundingModel()
        self.same_bar_priority = same_bar_priority
        self.tick_size = tick_size
        
        # State
        self.orders: Dict[str, Order] = {}
        self.position = Position(symbol=symbol)
        self.trade_log: List[Trade] = []
        self.current_time: Optional[datetime] = None
        self.current_price: float = 0.0
        
        # Counters
        self._next_order_id = 1
        
        log.info(f"SimExchange initialized: {symbol}, priority={same_bar_priority}")
    
    def create_order(
        self,
        side: str,
        price: float,
        amount: float,
        reduce_only: bool = False,
        client_id: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create a limit order (compatible with ccxt interface).
        
        Args:
            side: 'buy' or 'sell'
            price: Limit price
            amount: Order size in contracts
            reduce_only: Only reduce position, don't increase
            client_id: Custom order ID
            
        Returns:
            Order dict (ccxt-compatible format)
        """
        # Quantize price to tick size
        price = round(price / self.tick_size) * self.tick_size
        
        # Generate order ID
        order_id = f"SIM{self._next_order_id}"
        self._next_order_id += 1
        
        # Create order
        order = Order(
            id=order_id,
            symbol=self.symbol,
            side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
            price=price,
            amount=amount,
            reduce_only=reduce_only,
            client_id=client_id,
            status=OrderStatus.OPEN
        )
        
        self.orders[order_id] = order
        
        log.debug(f"Created order: {order_id} {side.upper()} {amount}@{price} {'REDUCE_ONLY' if reduce_only else ''}")
        
        return self._order_to_dict(order)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        order = self.orders[order_id]
        
        if order.status != OrderStatus.OPEN:
            raise ValueError(f"Order {order_id} is not open (status: {order.status})")
        
        order.status = OrderStatus.CANCELED
        log.debug(f"Canceled order: {order_id}")
        
        return self._order_to_dict(order)
    
    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Fetch all open orders."""
        open_orders = [
            self._order_to_dict(order)
            for order in self.orders.values()
            if order.status == OrderStatus.OPEN
        ]
        return open_orders
    
    def fetch_balance(self) -> Dict:
        """Fetch account balance (equity)."""
        equity = self.initial_balance + self.position.realized_pnl + self.position.unrealized_pnl
        
        return {
            'free': equity,
            'used': 0.0,
            'total': equity
        }
    
    def process_candle(
        self,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float
    ):
        """
        Process a candle and check for order fills.
        
        This is the core simulation logic:
        - Check if any orders would have filled
        - Apply fee model
        - Update positions
        - Log trades
        - Apply funding
        
        Args:
            timestamp: Candle timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
        """
        self.current_time = timestamp
        self.current_price = close
        
        # Update unrealized PnL
        self._update_unrealized_pnl(close)
        
        # Apply funding
        if self.position.size != 0:
            funding = self.funding_model.calculate_funding(
                timestamp,
                self.position.size,
                close
            )
            if funding != 0:
                self.position.realized_pnl += funding
                self.position.total_fees += abs(funding)
        
        # Get fillable orders for this candle
        fillable_orders = self._get_fillable_orders(high, low)
        
        if not fillable_orders:
            return
        
        # Sort by priority
        fillable_orders = self._apply_fill_priority(fillable_orders, high, low)
        
        # Fill orders
        for order in fillable_orders:
            self._fill_order(order, timestamp)
    
    def _get_fillable_orders(
        self,
        high: float,
        low: float
    ) -> List[Order]:
        """Determine which orders would fill based on candle high/low."""
        fillable = []
        
        for order in self.orders.values():
            if order.status != OrderStatus.OPEN:
                continue
            
            # Check if price touched this order
            if order.side == OrderSide.BUY:
                # BUY limit fills if low <= price
                if low <= order.price:
                    fillable.append(order)
            else:  # SELL
                # SELL limit fills if high >= price
                if high >= order.price:
                    fillable.append(order)
        
        return fillable
    
    def _apply_fill_priority(
        self,
        orders: List[Order],
        high: float,
        low: float
    ) -> List[Order]:
        """
        Apply fill priority when multiple orders can fill in same bar.
        
        Priority modes:
        - tp_first: TPs (reduce_only SELLs) fill before new BUYs
        - buy_first: New BUYs fill before TPs
        """
        if len(orders) <= 1:
            return orders
        
        # Separate into reduce_only (TPs) and new entries (BUYs)
        tps = [o for o in orders if o.reduce_only]
        buys = [o for o in orders if not o.reduce_only]
        
        if self.same_bar_priority == "tp_first":
            return tps + buys
        else:  # buy_first
            return buys + tps
    
    def _fill_order(self, order: Order, timestamp: datetime):
        """Execute an order fill."""
        # Check reduce_only constraint
        if order.reduce_only:
            if self.position.size <= 0:
                log.warning(f"Skipping reduce_only order {order.id}: no position to reduce")
                return
            
            # Limit amount to position size
            fill_amount = min(order.amount, abs(self.position.size))
        else:
            fill_amount = order.amount
        
        # Calculate fee
        fee = self.fee_model.calculate_fee(
            order.price,
            fill_amount,
            is_maker=order.is_maker
        )
        
        # Update position
        realized_pnl = self._update_position(order.side, order.price, fill_amount)
        
        # Mark order as filled
        order.status = OrderStatus.FILLED
        order.filled_price = order.price
        order.filled_time = timestamp
        order.fee = fee
        
        # Add to position fees
        self.position.total_fees += fee
        
        # Log trade
        trade = Trade(
            timestamp=timestamp,
            order_id=order.id,
            side=order.side,
            price=order.price,
            amount=fill_amount,
            reduce_only=order.reduce_only,
            fee=fee,
            is_maker=order.is_maker,
            client_id=order.client_id,
            position_size_after=self.position.size,
            realized_pnl=realized_pnl
        )
        self.trade_log.append(trade)
        
        log.debug(
            f"Filled: {order.id} {order.side.value.upper()} {fill_amount}@{order.price} "
            f"fee=${fee:.2f} pos={self.position.size} realized_pnl=${realized_pnl:.2f}"
        )
    
    def _update_position(
        self,
        side: OrderSide,
        price: float,
        amount: float
    ) -> float:
        """
        Update position and calculate realized PnL.
        
        Returns:
            Realized PnL from this fill
        """
        realized_pnl = 0.0
        
        if side == OrderSide.BUY:
            # Buying (going long or covering short)
            if self.position.size < 0:
                # Covering short - realize PnL
                close_amount = min(amount, abs(self.position.size))
                realized_pnl = (self.position.entry_price - price) * close_amount
                self.position.realized_pnl += realized_pnl
                self.position.size += close_amount
                
                remaining = amount - close_amount
                if remaining > 0:
                    # Going long after covering
                    self.position.entry_price = price
                    self.position.size += remaining
            else:
                # Adding to long or opening long
                if self.position.size == 0:
                    self.position.entry_price = price
                else:
                    # Calculate new average entry
                    total_cost = (self.position.entry_price * self.position.size) + (price * amount)
                    self.position.size += amount
                    self.position.entry_price = total_cost / self.position.size
                self.position.size += amount
        
        else:  # SELL
            # Selling (closing long or going short)
            if self.position.size > 0:
                # Closing long - realize PnL
                close_amount = min(amount, self.position.size)
                realized_pnl = (price - self.position.entry_price) * close_amount
                self.position.realized_pnl += realized_pnl
                self.position.size -= close_amount
                
                remaining = amount - close_amount
                if remaining > 0:
                    # Going short after closing
                    self.position.entry_price = price
                    self.position.size = -remaining
            else:
                # Adding to short or opening short
                if self.position.size == 0:
                    self.position.entry_price = price
                else:
                    # Calculate new average entry
                    total_cost = (self.position.entry_price * abs(self.position.size)) + (price * amount)
                    self.position.size -= amount
                    self.position.entry_price = total_cost / abs(self.position.size)
                self.position.size -= amount
        
        return realized_pnl
    
    def _update_unrealized_pnl(self, current_price: float):
        """Update unrealized PnL based on current price."""
        if self.position.size == 0:
            self.position.unrealized_pnl = 0.0
        else:
            if self.position.size > 0:
                # Long position
                self.position.unrealized_pnl = (current_price - self.position.entry_price) * self.position.size
            else:
                # Short position
                self.position.unrealized_pnl = (self.position.entry_price - current_price) * abs(self.position.size)
    
    def _order_to_dict(self, order: Order) -> Dict:
        """Convert Order to ccxt-compatible dict."""
        return {
            'id': order.id,
            'clientOrderId': order.client_id,
            'symbol': order.symbol,
            'side': order.side.value,
            'price': order.price,
            'amount': order.amount,
            'status': order.status.value,
            'filled': order.amount if order.status == OrderStatus.FILLED else 0,
            'remaining': 0 if order.status == OrderStatus.FILLED else order.amount,
            'reduceOnly': order.reduce_only,
            'timestamp': order.filled_time.timestamp() * 1000 if order.filled_time else None,
            'fee': {'cost': order.fee, 'currency': 'USD'}
        }
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trade log as DataFrame."""
        if not self.trade_log:
            return pd.DataFrame(columns=[
                'timestamp', 'order_id', 'side', 'price', 'amount', 
                'reduce_only', 'fee', 'is_maker', 'client_id',
                'position_size_after', 'realized_pnl'
            ])
        
        trades_data = []
        for trade in self.trade_log:
            trades_data.append({
                'timestamp': trade.timestamp,
                'order_id': trade.order_id,
                'side': trade.side.value,
                'price': trade.price,
                'amount': trade.amount,
                'reduce_only': trade.reduce_only,
                'fee': trade.fee,
                'is_maker': trade.is_maker,
                'client_id': trade.client_id,
                'position_size_after': trade.position_size_after,
                'realized_pnl': trade.realized_pnl
            })
        
        return pd.DataFrame(trades_data)
    
    def get_position(self) -> Dict:
        """Get current position (ccxt-compatible)."""
        return {
            'symbol': self.symbol,
            'contracts': abs(self.position.size),
            'contractSize': 1,
            'side': 'long' if self.position.size > 0 else 'short' if self.position.size < 0 else 'none',
            'notional': abs(self.position.size) * self.current_price,
            'leverage': 0,
            'unrealizedPnl': self.position.unrealized_pnl,
            'realizedPnl': self.position.realized_pnl,
            'entryPrice': self.position.entry_price,
            'markPrice': self.current_price
        }
    
    def get_summary(self) -> Dict:
        """Get backtest summary statistics."""
        total_pnl = self.position.realized_pnl + self.position.unrealized_pnl
        net_pnl = total_pnl - self.position.total_fees - abs(self.funding_model.get_total_funding())
        
        return {
            'total_trades': len(self.trade_log),
            'realized_pnl': self.position.realized_pnl,
            'unrealized_pnl': self.position.unrealized_pnl,
            'total_pnl': total_pnl,
            'total_fees': self.position.total_fees,
            'total_funding': self.funding_model.get_total_funding(),
            'net_pnl': net_pnl,
            'final_equity': self.initial_balance + net_pnl,
            'position_size': self.position.size,
            'open_orders': len(self.fetch_open_orders())
        }

