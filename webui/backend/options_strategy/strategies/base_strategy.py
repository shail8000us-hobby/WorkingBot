"""
Base Strategy Class
All strategy types inherit from this abstract base class
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for all option strategies"""
    
    def __init__(self, api_client, chain_service):
        self.api_client = api_client
        self.chain_service = chain_service
    
    @abstractmethod
    def calculate_legs(self, **kwargs) -> List[Dict]:
        """
        Calculate strategy legs based on parameters
        
        Returns:
            List of leg dictionaries with structure:
            {
                'option_type': 'call' or 'put',
                'symbol': 'C-BTC-100000-250126',
                'strike': 100000,
                'side': 'buy' or 'sell',
                'quantity': 1,
                'current_price': 1500.0,
                'iv': 65.5,
                'greeks': {...}
            }
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, **kwargs) -> Tuple[bool, str]:
        """
        Validate strategy-specific parameters
        
        Returns:
            Tuple of (is_valid, error_message)
            Example: (True, "") or (False, "Invalid strike price")
        """
        pass
    
    @abstractmethod
    def calculate_breakeven(self, legs: List[Dict]) -> Dict:
        """
        Calculate breakeven points for the strategy
        
        Args:
            legs: List of strategy legs
            
        Returns:
            Dict with breakeven analysis:
            {
                'breakeven_points': [lower_price, upper_price],
                'breakeven_lower': 97300,
                'breakeven_upper': 102700
            }
        """
        pass
    
    @abstractmethod
    def calculate_max_profit_loss(self, legs: List[Dict]) -> Dict:
        """
        Calculate maximum profit and loss for the strategy
        
        Args:
            legs: List of strategy legs
            
        Returns:
            Dict with max P&L:
            {
                'max_profit': 2700.0 or 'Unlimited',
                'max_loss': 2700.0 or 'Unlimited',
                'max_profit_price': 100000,
                'max_loss_price': 100000
            }
        """
        pass
    
    def get_strategy_info(self) -> Dict:
        """
        Return strategy metadata
        
        Returns:
            Dict with strategy information
        """
        return {
            "name": self.__class__.__name__,
            "description": self.__doc__ or "Options strategy",
            "risk_level": "medium",
            "complexity": "intermediate"
        }
    
    # Helper methods (concrete implementations)
    
    def _get_spot_price(self, underlying: str) -> float:
        """
        Get current spot price for underlying
        
        Args:
            underlying: BTC or ETH
            
        Returns:
            Spot price as float
        """
        try:
            # Try to get from market API first
            import requests
            response = requests.get('http://localhost:5555/api/market/spot-price', timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = data.get(underlying.lower())
                if price:
                    logger.info(f"Got spot price from API: {underlying} = {price}")
                    return float(price)
        except Exception as e:
            logger.warning(f"Failed to get spot price from API: {e}")
        
        # Fallback to guardian signal file
        try:
            with open('/tmp/guardian_signal.txt', 'r') as f:
                for line in f:
                    if 'BTC_price:' in line and underlying.upper() == 'BTC':
                        price = float(line.split(':')[1].strip())
                        logger.info(f"Got spot price from guardian: BTC = {price}")
                        return price
                    elif 'ETH_price:' in line and underlying.upper() == 'ETH':
                        price = float(line.split(':')[1].strip())
                        logger.info(f"Got spot price from guardian: ETH = {price}")
                        return price
        except Exception as e:
            logger.warning(f"Failed to get spot price from guardian: {e}")
        
        # Final fallback to default
        default_prices = {'BTC': 100000.0, 'ETH': 5000.0}
        price = default_prices.get(underlying.upper(), 100000.0)
        logger.warning(f"Using default spot price: {underlying} = {price}")
        return price
    
    def _convert_expiry_format(self, expiry: str) -> str:
        """
        Convert expiry from DDMMYYYY to DDMMYY format (Delta Exchange symbol format)
        
        Args:
            expiry: DDMMYYYY format (e.g., "25012026")
            
        Returns:
            DDMMYY format (e.g., "250126")
        """
        if len(expiry) == 8:
            # DDMMYYYY -> DDMMYY (remove century from year)
            expiry_6digit = expiry[0:4] + expiry[6:8]
            logger.info(f"Converted expiry format: {expiry} -> {expiry_6digit}")
            return expiry_6digit
        else:
            # Already in correct format or invalid
            return expiry
    
    def _calculate_days_to_expiry(self, expiry: str) -> int:
        """
        Calculate days until expiry
        
        Args:
            expiry: DDMMYYYY or DDMMYY format
            
        Returns:
            Days to expiry as integer
        """
        try:
            if len(expiry) == 8:
                # DDMMYYYY
                expiry_date = datetime.strptime(expiry, '%d%m%Y')
            elif len(expiry) == 6:
                # DDMMYY
                expiry_date = datetime.strptime(expiry, '%d%m%y')
            else:
                return 0
            
            now = datetime.now()
            delta = expiry_date - now
            return max(0, delta.days)
        except Exception as e:
            logger.error(f"Error calculating days to expiry: {e}")
            return 0
    
    def _validate_common_parameters(
        self,
        underlying: str,
        expiry: str,
        quantity: int
    ) -> Tuple[bool, str]:
        """
        Validate common parameters across all strategies
        
        Returns:
            (is_valid, error_message)
        """
        # Validate underlying
        if underlying.upper() not in ['BTC', 'ETH']:
            return False, f"Invalid underlying: {underlying}. Must be BTC or ETH"
        
        # Validate expiry format
        if len(expiry) not in [6, 8]:
            return False, f"Invalid expiry format: {expiry}. Must be DDMMYY or DDMMYYYY"
        
        # Validate quantity
        if not isinstance(quantity, int) or quantity <= 0:
            return False, f"Invalid quantity: {quantity}. Must be positive integer"
        
        # Check if expiry is in the future
        days_to_expiry = self._calculate_days_to_expiry(expiry)
        if days_to_expiry < 0:
            return False, f"Expiry date is in the past"
        
        return True, ""
