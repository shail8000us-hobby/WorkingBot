"""
Trading Fee Model

Simulates Delta Exchange maker/taker fees for backtesting.
"""

import os
import logging
from typing import Optional

log = logging.getLogger("backtest.fees")


class FeeModel:
    """
    Trading fee calculator for backtesting.
    
    Default Delta Exchange fees:
    - Maker: 0.02% (0.0002)
    - Taker: 0.05% (0.0005)
    """
    
    def __init__(
        self,
        maker_fee: Optional[float] = None,
        taker_fee: Optional[float] = None,
        assume_maker: bool = True
    ):
        """
        Initialize fee model.
        
        Args:
            maker_fee: Maker fee rate (default: 0.0002 = 0.02%)
            taker_fee: Taker fee rate (default: 0.0005 = 0.05%)
            assume_maker: Assume all fills are maker (optimistic)
        """
        # Load from environment or use defaults
        self.maker_fee = maker_fee or float(os.getenv('BACKTEST_MAKER_FEE', '0.0002'))
        self.taker_fee = taker_fee or float(os.getenv('BACKTEST_TAKER_FEE', '0.0005'))
        self.assume_maker = assume_maker
        
        log.info(f"FeeModel: maker={self.maker_fee:.4f}%, taker={self.taker_fee:.4f}%, assume_maker={assume_maker}")
    
    def calculate_fee(
        self,
        price: float,
        amount: float,
        is_maker: Optional[bool] = None
    ) -> float:
        """
        Calculate trading fee for a fill.
        
        Args:
            price: Fill price
            amount: Fill quantity (contracts)
            is_maker: True if maker, False if taker, None to use assume_maker setting
            
        Returns:
            Fee amount in USD
        """
        notional = price * amount
        
        if is_maker is None:
            is_maker = self.assume_maker
        
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        fee = notional * fee_rate
        
        return fee
    
    def get_maker_fee(self) -> float:
        """Get maker fee rate."""
        return self.maker_fee
    
    def get_taker_fee(self) -> float:
        """Get taker fee rate."""
        return self.taker_fee

