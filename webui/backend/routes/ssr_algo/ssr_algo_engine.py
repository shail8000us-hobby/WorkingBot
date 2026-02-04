"""
SSR ALGO Engine - Strike Selection and Core Logic

Implements the algorithmic core of SSR Algo:
- ATM strike detection (minimum |CE - PE| premium)
- Percentage-based OTM strike selection
- Strike validation and fallback logic
- Date format normalization (DDMMYY ↔ DDMMYYYY)

Created: February 2, 2026
Updated: February 4, 2026 - Added date format normalization
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import sys
import os

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

log = logging.getLogger('ssr_algo_engine')


def normalize_expiry_format(expiry: str) -> str:
    """
    Normalize expiry date format to DDMMYYYY (8 digits).
    
    Accepts:
    - DDMMYY (6 digits) -> converts to DDMMYYYY
    - DDMMYYYY (8 digits) -> returns as-is
    - YYYY-MM-DD -> converts to DDMMYYYY
    
    Args:
        expiry: Expiry date string in various formats
    
    Returns:
        Normalized expiry in DDMMYYYY format
    
    Raises:
        ValueError: If format cannot be parsed
    """
    if not expiry:
        raise ValueError("Expiry date is required")
    
    expiry = str(expiry).strip()
    
    # Already 8 digits (DDMMYYYY)
    if len(expiry) == 8 and expiry.isdigit():
        try:
            # Validate it's a real date
            datetime.strptime(expiry, '%d%m%Y')
            return expiry
        except ValueError:
            pass
    
    # 6 digits (DDMMYY) - most common from frontend
    if len(expiry) == 6 and expiry.isdigit():
        try:
            dt = datetime.strptime(expiry, '%d%m%y')
            normalized = dt.strftime('%d%m%Y')
            log.info(f"Normalized expiry: {expiry} -> {normalized}")
            return normalized
        except ValueError as e:
            raise ValueError(f"Invalid DDMMYY format '{expiry}': {e}")
    
    # ISO format (YYYY-MM-DD)
    if len(expiry) == 10 and '-' in expiry:
        try:
            dt = datetime.strptime(expiry, '%Y-%m-%d')
            normalized = dt.strftime('%d%m%Y')
            log.info(f"Normalized expiry: {expiry} -> {normalized}")
            return normalized
        except ValueError:
            pass
    
    raise ValueError(f"Unsupported expiry format: '{expiry}'. Use DDMMYY, DDMMYYYY, or YYYY-MM-DD")


class StrikeSelector:
    """
    Strike selection engine for SSR Algo.
    
    Selects strikes based on premium percentages relative to ATM:
    - ATM: Strike where |CE_premium - PE_premium| is minimum
    - OTM Buy: Strikes at 45-49% of ATM premium
    - Far OTM Sell: Strikes at 20-30% of ATM premium
    """
    
    def __init__(self, chain_service=None):
        """
        Initialize strike selector.
        
        Args:
            chain_service: Optional injected chain service for testing
        """
        self._chain_service = chain_service
    
    @property
    def chain_service(self):
        """Lazy load chain service."""
        if self._chain_service is None:
            try:
                from webui.backend.options_chain.chain_service import OptionsChainService
                self._chain_service = OptionsChainService()
            except ImportError as e:
                log.error(f"Failed to import chain service: {e}")
                raise
        return self._chain_service
    
    def find_atm_strike(self, chain_data: List[Dict], spot_price: float) -> Dict:
        """
        Find the ATM strike where |CE_premium - PE_premium| is minimum.
        
        Args:
            chain_data: List of strike data with CE and PE premiums
            spot_price: Current spot price
        
        Returns:
            {
                'strike': int,
                'ce_premium': float,
                'pe_premium': float,
                'premium_diff': float
            }
        """
        if not chain_data:
            raise ValueError("Empty chain data")
        
        best_atm = None
        min_diff = float('inf')
        
        for strike_data in chain_data:
            if not strike_data or not isinstance(strike_data, dict):
                continue
                
            strike = strike_data.get('strike')
            ce = strike_data.get('call') or {}
            pe = strike_data.get('put') or {}
            
            if not isinstance(ce, dict):
                ce = {}
            if not isinstance(pe, dict):
                pe = {}
            
            ce_premium = ce.get('mark_price') or ce.get('close') or 0
            pe_premium = pe.get('mark_price') or pe.get('close') or 0
            
            if ce_premium <= 0 or pe_premium <= 0:
                continue
            
            diff = abs(ce_premium - pe_premium)
            
            # Also consider distance from spot as tiebreaker
            distance_from_spot = abs(strike - spot_price)
            
            if diff < min_diff or (diff == min_diff and best_atm and 
                                    distance_from_spot < abs(best_atm['strike'] - spot_price)):
                min_diff = diff
                best_atm = {
                    'strike': strike,
                    'ce_premium': ce_premium,
                    'pe_premium': pe_premium,
                    'premium_diff': diff
                }
        
        if best_atm is None:
            # Fallback: closest to spot
            closest = min(chain_data, 
                         key=lambda x: abs(x.get('strike', 0) - spot_price))
            ce = closest.get('call', {})
            pe = closest.get('put', {})
            best_atm = {
                'strike': closest.get('strike'),
                'ce_premium': ce.get('mark_price') or ce.get('close') or 0,
                'pe_premium': pe.get('mark_price') or pe.get('close') or 0,
                'premium_diff': 0
            }
        
        log.info(f"ATM found: strike={best_atm['strike']}, "
                f"CE={best_atm['ce_premium']}, PE={best_atm['pe_premium']}")
        
        return best_atm
    
    def calculate_premium_ranges(self, 
                                 atm_ce_premium: float, 
                                 atm_pe_premium: float, 
                                 config: Dict) -> Dict:
        """
        Calculate target premium ranges based on ATM premiums.
        
        Args:
            atm_ce_premium: ATM call premium
            atm_pe_premium: ATM put premium
            config: Strike config with percentage bounds
        
        Returns:
            {
                'otm_buy_ce': {'min': float, 'max': float},
                'otm_buy_pe': {'min': float, 'max': float},
                'far_otm_ce': {'min': float, 'max': float},
                'far_otm_pe': {'min': float, 'max': float}
            }
        """
        otm_buy_min_pct = config.get('otm_buy_percent_min', 45) / 100
        otm_buy_max_pct = config.get('otm_buy_percent_max', 49) / 100
        far_otm_min_pct = config.get('far_otm_percent_min', 20) / 100
        far_otm_max_pct = config.get('far_otm_percent_max', 30) / 100
        
        ranges = {
            'otm_buy_ce': {
                'min': atm_ce_premium * otm_buy_min_pct,
                'max': atm_ce_premium * otm_buy_max_pct
            },
            'otm_buy_pe': {
                'min': atm_pe_premium * otm_buy_min_pct,
                'max': atm_pe_premium * otm_buy_max_pct
            },
            'far_otm_ce': {
                'min': atm_ce_premium * far_otm_min_pct,
                'max': atm_ce_premium * far_otm_max_pct
            },
            'far_otm_pe': {
                'min': atm_pe_premium * far_otm_min_pct,
                'max': atm_pe_premium * far_otm_max_pct
            }
        }
        
        log.debug(f"Premium ranges calculated: {ranges}")
        return ranges
    
    def find_otm_strike(self,
                        chain_data: List[Dict],
                        atm_strike: int,
                        target_range: Dict,
                        direction: str,
                        fallback_expand: float = 0.1) -> Optional[Dict]:
        """
        Find OTM strike within target premium range.
        
        Args:
            chain_data: List of strike data
            atm_strike: ATM strike price
            target_range: {'min': float, 'max': float}
            direction: 'ce' or 'pe'
            fallback_expand: Range expansion factor if no match (10%)
        
        Returns:
            {
                'strike': int,
                'symbol': str,
                'premium': float,
                'target_range': str
            }
        """
        option_key = 'call' if direction == 'ce' else 'put'
        
        # Filter to OTM strikes only
        if direction == 'ce':
            # CE: OTM means strike > ATM
            candidates = [s for s in chain_data if s.get('strike', 0) > atm_strike]
            # Sort by strike ascending (closest to ATM first)
            candidates.sort(key=lambda x: x.get('strike', 0))
        else:
            # PE: OTM means strike < ATM
            candidates = [s for s in chain_data if s.get('strike', 0) < atm_strike]
            # Sort by strike descending (closest to ATM first)
            candidates.sort(key=lambda x: x.get('strike', 0), reverse=True)
        
        min_premium = target_range['min']
        max_premium = target_range['max']
        
        # First pass: exact match
        for strike_data in candidates:
            option = strike_data.get(option_key, {})
            premium = option.get('mark_price') or option.get('close') or 0
            
            if premium >= min_premium and premium <= max_premium:
                return {
                    'strike': strike_data.get('strike'),
                    'symbol': option.get('symbol'),
                    'premium': premium,
                    'target_range': f"{min_premium:.2f}-{max_premium:.2f}"
                }
        
        # Fallback: expand range by 10%
        expanded_min = min_premium * (1 - fallback_expand)
        expanded_max = max_premium * (1 + fallback_expand)
        
        log.warning(f"No exact match for {direction.upper()} OTM, "
                   f"expanding range to {expanded_min:.2f}-{expanded_max:.2f}")
        
        for strike_data in candidates:
            option = strike_data.get(option_key, {})
            premium = option.get('mark_price') or option.get('close') or 0
            
            if premium >= expanded_min and premium <= expanded_max:
                return {
                    'strike': strike_data.get('strike'),
                    'symbol': option.get('symbol'),
                    'premium': premium,
                    'target_range': f"{min_premium:.2f}-{max_premium:.2f} (expanded)"
                }
        
        log.error(f"No OTM {direction.upper()} found in premium range "
                 f"{min_premium:.2f}-{max_premium:.2f}")
        return None
    
    def find_far_otm_strike(self,
                            chain_data: List[Dict],
                            atm_strike: int,
                            otm_strike: int,
                            target_range: Dict,
                            direction: str,
                            fallback_expand: float = 0.15) -> Optional[Dict]:
        """
        Find far OTM strike beyond the OTM buy strike.
        
        Args:
            chain_data: List of strike data
            atm_strike: ATM strike price
            otm_strike: Already selected OTM buy strike
            target_range: {'min': float, 'max': float}
            direction: 'ce' or 'pe'
            fallback_expand: Range expansion factor if no match (15%)
        
        Returns:
            Same as find_otm_strike
        """
        option_key = 'call' if direction == 'ce' else 'put'
        
        # Filter to strikes beyond OTM buy
        if direction == 'ce':
            # Far OTM CE: strike > OTM CE buy strike
            candidates = [s for s in chain_data if s.get('strike', 0) > otm_strike]
            candidates.sort(key=lambda x: x.get('strike', 0))
        else:
            # Far OTM PE: strike < OTM PE buy strike
            candidates = [s for s in chain_data if s.get('strike', 0) < otm_strike]
            candidates.sort(key=lambda x: x.get('strike', 0), reverse=True)
        
        min_premium = target_range['min']
        max_premium = target_range['max']
        
        # First pass: exact match
        for strike_data in candidates:
            option = strike_data.get(option_key, {})
            premium = option.get('mark_price') or option.get('close') or 0
            
            if premium >= min_premium and premium <= max_premium:
                return {
                    'strike': strike_data.get('strike'),
                    'symbol': option.get('symbol'),
                    'premium': premium,
                    'target_range': f"{min_premium:.2f}-{max_premium:.2f}"
                }
        
        # Fallback with wider range
        expanded_min = min_premium * (1 - fallback_expand)
        expanded_max = max_premium * (1 + fallback_expand)
        
        log.warning(f"No exact match for far OTM {direction.upper()}, "
                   f"expanding range to {expanded_min:.2f}-{expanded_max:.2f}")
        
        for strike_data in candidates:
            option = strike_data.get(option_key, {})
            premium = option.get('mark_price') or option.get('close') or 0
            
            if premium >= expanded_min and premium <= expanded_max:
                return {
                    'strike': strike_data.get('strike'),
                    'symbol': option.get('symbol'),
                    'premium': premium,
                    'target_range': f"{min_premium:.2f}-{max_premium:.2f} (expanded)"
                }
        
        log.error(f"No far OTM {direction.upper()} found in premium range "
                 f"{min_premium:.2f}-{max_premium:.2f}")
        return None
    
    def select_all_strikes(self,
                           underlying: str,
                           expiry: str,
                           strike_config: Dict) -> Dict:
        """
        Select all 6 strikes for the butterfly strategy.
        
        Args:
            underlying: BTC or ETH
            expiry: Expiry in DDMMYY or DDMMYYYY format (auto-normalized)
            strike_config: Premium percentage configuration
        
        Returns:
            {
                'success': bool,
                'atm': {...},
                'otm_ce_buy': {...},
                'otm_pe_buy': {...},
                'far_otm_ce': {...},
                'far_otm_pe': {...},
                'spot_price': float,
                'original_expiry': str,
                'normalized_expiry': str,
                'error': str (if failed)
            }
        """
        try:
            # Normalize expiry format (DDMMYY -> DDMMYYYY)
            original_expiry = expiry
            try:
                expiry = normalize_expiry_format(expiry)
                log.info(f"Expiry normalized: {original_expiry} -> {expiry}")
            except ValueError as e:
                return {
                    'success': False,
                    'error': f"Invalid expiry format: {e}",
                    'original_expiry': original_expiry
                }
            
            # Fetch chain data
            log.info(f"Fetching chain for {underlying} expiry {expiry}")
            chain_result = self.chain_service.get_chain_data(underlying, expiry)
            
            log.info(f"Chain result type: {type(chain_result)}, keys: {chain_result.keys() if chain_result else 'None'}")
            
            if not chain_result or not chain_result.get('chain'):
                return {
                    'success': False,
                    'error': f"No chain data for {underlying} {expiry}"
                }
            
            spot_price = chain_result.get('spot_price', 0)
            chain_data = chain_result.get('chain', [])
            
            log.info(f"Chain loaded: {len(chain_data)} strikes, spot={spot_price}")
            
            # Validate chain_data is a list
            if not isinstance(chain_data, list):
                return {
                    'success': False,
                    'error': f"Invalid chain data type: {type(chain_data)}"
                }
            
            # Filter out None entries
            chain_data = [s for s in chain_data if s is not None and isinstance(s, dict)]
            
            if not chain_data:
                return {
                    'success': False,
                    'error': f"Chain data is empty after filtering"
                }
            
            # Step 1: Find ATM
            atm = self.find_atm_strike(chain_data, spot_price)
            
            if not atm or not atm.get('ce_premium') or not atm.get('pe_premium'):
                return {
                    'success': False,
                    'error': 'Could not find valid ATM strike'
                }
            
            # Step 2: Calculate premium ranges
            ranges = self.calculate_premium_ranges(
                atm['ce_premium'],
                atm['pe_premium'],
                strike_config
            )
            
            # Step 3: Find OTM buy strikes
            otm_ce_buy = self.find_otm_strike(
                chain_data, atm['strike'], 
                ranges['otm_buy_ce'], 'ce'
            )
            
            otm_pe_buy = self.find_otm_strike(
                chain_data, atm['strike'],
                ranges['otm_buy_pe'], 'pe'
            )
            
            if not otm_ce_buy:
                return {
                    'success': False,
                    'error': f"No OTM CE found in range {ranges['otm_buy_ce']}"
                }
            
            if not otm_pe_buy:
                return {
                    'success': False,
                    'error': f"No OTM PE found in range {ranges['otm_buy_pe']}"
                }
            
            # Step 4: Find far OTM sell strikes
            far_otm_ce = self.find_far_otm_strike(
                chain_data, atm['strike'], otm_ce_buy['strike'],
                ranges['far_otm_ce'], 'ce'
            )
            
            far_otm_pe = self.find_far_otm_strike(
                chain_data, atm['strike'], otm_pe_buy['strike'],
                ranges['far_otm_pe'], 'pe'
            )
            
            if not far_otm_ce:
                return {
                    'success': False,
                    'error': f"No far OTM CE found in range {ranges['far_otm_ce']}"
                }
            
            if not far_otm_pe:
                return {
                    'success': False,
                    'error': f"No far OTM PE found in range {ranges['far_otm_pe']}"
                }
            
            # Build ATM symbols
            atm_ce_symbol = f"C-{underlying}-{atm['strike']}-{expiry}"
            atm_pe_symbol = f"P-{underlying}-{atm['strike']}-{expiry}"
            
            # Try to find actual symbols from chain
            for strike_data in chain_data:
                if strike_data.get('strike') == atm['strike']:
                    if strike_data.get('call', {}).get('symbol'):
                        atm_ce_symbol = strike_data['call']['symbol']
                    if strike_data.get('put', {}).get('symbol'):
                        atm_pe_symbol = strike_data['put']['symbol']
                    break
            
            result = {
                'success': True,
                'spot_price': spot_price,
                'atm': {
                    'strike': atm['strike'],
                    'ce_symbol': atm_ce_symbol,
                    'pe_symbol': atm_pe_symbol,
                    'ce_premium': atm['ce_premium'],
                    'pe_premium': atm['pe_premium']
                },
                'otm_ce_buy': otm_ce_buy,
                'otm_pe_buy': otm_pe_buy,
                'far_otm_ce': far_otm_ce,
                'far_otm_pe': far_otm_pe,
                'premium_ranges': ranges
            }
            
            log.info(f"Strike selection complete: ATM={atm['strike']}, "
                    f"OTM_CE={otm_ce_buy['strike']}, OTM_PE={otm_pe_buy['strike']}, "
                    f"Far_CE={far_otm_ce['strike']}, Far_PE={far_otm_pe['strike']}")
            
            return result
            
        except Exception as e:
            log.exception(f"Strike selection failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def build_orders_from_strikes(self, strikes: Dict, underlying: str, expiry: str) -> List[Dict]:
        """
        Build order list from selected strikes.
        
        Args:
            strikes: Result from select_all_strikes
            underlying: BTC or ETH
            expiry: Expiry code
        
        Returns:
            List of 8 order dicts with symbol, size, side
        """
        orders = []
        
        atm = strikes.get('atm', {})
        
        # ATM CE Sell (1 lot)
        orders.append({
            'symbol': atm.get('ce_symbol'),
            'size': 1,
            'side': 'sell',
            'leg_type': 'atm_ce',
            'strike': atm.get('strike'),
            'premium': atm.get('ce_premium')
        })
        
        # ATM PE Sell (1 lot)
        orders.append({
            'symbol': atm.get('pe_symbol'),
            'size': 1,
            'side': 'sell',
            'leg_type': 'atm_pe',
            'strike': atm.get('strike'),
            'premium': atm.get('pe_premium')
        })
        
        # OTM CE Buy (2 lots)
        otm_ce = strikes.get('otm_ce_buy', {})
        orders.append({
            'symbol': otm_ce.get('symbol'),
            'size': 2,
            'side': 'buy',
            'leg_type': 'otm_ce_buy',
            'strike': otm_ce.get('strike'),
            'premium': otm_ce.get('premium')
        })
        
        # OTM PE Buy (2 lots)
        otm_pe = strikes.get('otm_pe_buy', {})
        orders.append({
            'symbol': otm_pe.get('symbol'),
            'size': 2,
            'side': 'buy',
            'leg_type': 'otm_pe_buy',
            'strike': otm_pe.get('strike'),
            'premium': otm_pe.get('premium')
        })
        
        # Far OTM CE Sell (1 lot)
        far_ce = strikes.get('far_otm_ce', {})
        orders.append({
            'symbol': far_ce.get('symbol'),
            'size': 1,
            'side': 'sell',
            'leg_type': 'far_otm_ce',
            'strike': far_ce.get('strike'),
            'premium': far_ce.get('premium')
        })
        
        # Far OTM PE Sell (1 lot)
        far_pe = strikes.get('far_otm_pe', {})
        orders.append({
            'symbol': far_pe.get('symbol'),
            'size': 1,
            'side': 'sell',
            'leg_type': 'far_otm_pe',
            'strike': far_pe.get('strike'),
            'premium': far_pe.get('premium')
        })
        
        return orders


# Singleton instance
_selector = None

def get_strike_selector() -> StrikeSelector:
    """Get the singleton strike selector instance."""
    global _selector
    if _selector is None:
        _selector = StrikeSelector()
    return _selector
