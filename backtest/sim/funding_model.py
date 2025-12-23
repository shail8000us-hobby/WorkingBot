"""
Funding Rate Model

Simulates perpetual funding payments for backtesting.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

log = logging.getLogger("backtest.funding")


class FundingModel:
    """
    Funding rate calculator for perpetual contracts.
    
    Modes:
    - off: No funding (default)
    - simple: Fixed periodic rate
    - historical: Use actual historical rates (future enhancement)
    """
    
    def __init__(
        self,
        mode: str = "off",
        simple_rate: float = 0.0001,  # 0.01% per 8h (~10% APR)
        interval_hours: int = 8
    ):
        """
        Initialize funding model.
        
        Args:
            mode: 'off', 'simple', or 'historical'
            simple_rate: Funding rate per interval (default: 0.01% per 8h)
            interval_hours: Hours between funding payments (default: 8)
        """
        self.mode = mode or os.getenv('BACKTEST_FUNDING_MODE', 'off')
        self.simple_rate = simple_rate or float(os.getenv('BACKTEST_FUNDING_SIMPLE_RATE', '0.0001'))
        self.interval_hours = interval_hours
        
        self.last_funding_time: Optional[datetime] = None
        self.total_funding_paid = 0.0
        
        log.info(f"FundingModel: mode={self.mode}, rate={self.simple_rate:.4f}% per {interval_hours}h")
    
    def calculate_funding(
        self,
        current_time: datetime,
        position_size: float,
        mark_price: float
    ) -> float:
        """
        Calculate funding payment for current timestamp.
        
        Args:
            current_time: Current simulation time
            position_size: Position size in contracts (positive = long)
            mark_price: Current mark price
            
        Returns:
            Funding payment (negative = you pay, positive = you receive)
        """
        if self.mode == 'off' or position_size == 0:
            return 0.0
        
        # Initialize last funding time
        if self.last_funding_time is None:
            self.last_funding_time = current_time
            return 0.0
        
        # Check if funding interval has passed
        time_since_last = (current_time - self.last_funding_time).total_seconds() / 3600
        
        if time_since_last < self.interval_hours:
            return 0.0
        
        # Calculate funding payment
        if self.mode == 'simple':
            funding = self._calculate_simple_funding(position_size, mark_price)
        elif self.mode == 'historical':
            # TODO: Implement historical funding lookup
            log.warning("Historical funding mode not yet implemented, using simple mode")
            funding = self._calculate_simple_funding(position_size, mark_price)
        else:
            funding = 0.0
        
        # Update last funding time
        self.last_funding_time = current_time
        self.total_funding_paid += funding
        
        if funding != 0:
            log.debug(f"Funding payment: ${funding:.2f} (total: ${self.total_funding_paid:.2f})")
        
        return funding
    
    def _calculate_simple_funding(
        self,
        position_size: float,
        mark_price: float
    ) -> float:
        """Calculate simple periodic funding."""
        notional = abs(position_size) * mark_price
        # Negative = you pay funding (long position in contango)
        # Positive = you receive funding (long position in backwardation)
        funding_payment = -notional * self.simple_rate
        return funding_payment
    
    def get_total_funding(self) -> float:
        """Get total funding paid/received."""
        return self.total_funding_paid
    
    def reset(self):
        """Reset funding tracking."""
        self.last_funding_time = None
        self.total_funding_paid = 0.0

