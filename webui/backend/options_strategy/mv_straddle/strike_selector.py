"""
Intelligent Strike Selector for MV Straddle
Selects optimal ATM strike based on spot price and available strikes
"""
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class StrikeSelector:
    """Select optimal strike for straddle strategies"""
    
    def __init__(self, chain_service):
        self.chain_service = chain_service
    
    def select_atm_strike(
        self,
        underlying: str,
        expiry: str,
        spot_price: float,
        offset: int = 0
    ) -> int:
        """
        Select ATM (At The Money) strike
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYYYY format
            spot_price: Current spot price
            offset: Offset from ATM (e.g., +1000 for OTM call bias)
        
        Returns:
            Strike price (integer)
        """
        try:
            # Get available strikes from chain service
            strikes = self.chain_service.get_available_strikes(underlying, expiry)
            
            if not strikes or len(strikes) == 0:
                logger.warning(f"No strikes available from API, using rounded spot price")
                return self._round_to_nearest_strike(spot_price, underlying)
            
            # Find closest strike to spot price
            atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
            
            # Apply offset
            target_strike = atm_strike + offset
            
            # Find closest available strike to target
            final_strike = min(strikes, key=lambda x: abs(x - target_strike))
            
            logger.info(f"Selected strike: {final_strike} (spot: {spot_price}, ATM: {atm_strike}, offset: {offset})")
            return final_strike
            
        except Exception as e:
            logger.error(f"Error selecting ATM strike: {e}")
            return self._round_to_nearest_strike(spot_price, underlying)
    
    def get_strike_range(
        self,
        underlying: str,
        expiry: str,
        spot_price: float,
        range_pct: float = 10.0
    ) -> List[int]:
        """
        Get strikes within X% of spot price
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYYYY format
            spot_price: Current spot price
            range_pct: Percentage range (e.g., 10 = ±10%)
        
        Returns:
            List of strikes within range
        """
        try:
            strikes = self.chain_service.get_available_strikes(underlying, expiry)
            
            if not strikes:
                return []
            
            # Calculate range bounds
            lower_bound = spot_price * (1 - range_pct / 100)
            upper_bound = spot_price * (1 + range_pct / 100)
            
            # Filter strikes within range
            strikes_in_range = [
                strike for strike in strikes
                if lower_bound <= strike <= upper_bound
            ]
            
            logger.info(f"Found {len(strikes_in_range)} strikes within {range_pct}% of spot")
            return sorted(strikes_in_range)
            
        except Exception as e:
            logger.error(f"Error getting strike range: {e}")
            return []
    
    def _round_to_nearest_strike(self, spot_price: float, underlying: str) -> int:
        """
        Round spot price to nearest typical strike interval
        
        Args:
            spot_price: Current spot price
            underlying: BTC or ETH
            
        Returns:
            Rounded strike price
        """
        # Typical strike intervals
        # BTC: Usually 500 or 1000 intervals
        # ETH: Usually 50 or 100 intervals
        
        if underlying.upper() == 'BTC':
            if spot_price > 50000:
                interval = 1000
            else:
                interval = 500
        else:  # ETH
            if spot_price > 5000:
                interval = 100
            else:
                interval = 50
        
        # Round to nearest interval
        rounded_strike = round(spot_price / interval) * interval
        
        logger.info(f"Rounded {spot_price} to {rounded_strike} (interval: {interval})")
        return int(rounded_strike)
    
    def get_otm_strikes(
        self,
        underlying: str,
        expiry: str,
        spot_price: float,
        num_strikes: int = 5
    ) -> Dict[str, List[int]]:
        """
        Get OTM (Out of The Money) strikes on both sides
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYYYY format
            spot_price: Current spot price
            num_strikes: Number of strikes to return on each side
        
        Returns:
            {
                'otm_calls': [101000, 102000, ...],  # Strikes above spot
                'otm_puts': [99000, 98000, ...]      # Strikes below spot
            }
        """
        try:
            strikes = self.chain_service.get_available_strikes(underlying, expiry)
            
            if not strikes:
                return {'otm_calls': [], 'otm_puts': []}
            
            # Separate strikes above and below spot
            otm_calls = sorted([s for s in strikes if s > spot_price])[:num_strikes]
            otm_puts = sorted([s for s in strikes if s < spot_price], reverse=True)[:num_strikes]
            
            return {
                'otm_calls': otm_calls,
                'otm_puts': otm_puts
            }
            
        except Exception as e:
            logger.error(f"Error getting OTM strikes: {e}")
            return {'otm_calls': [], 'otm_puts': []}
