"""
SSR ALGO Payoff - Payoff Calculation and Max Loss Detection

Calculates payoff curves and finds max loss points for SSR Algo positions.
Used by the monitoring daemon to determine when price hits max loss zones.

Features:
- Payoff curve calculation at expiry
- Max loss point detection (local minima)
- Greeks aggregation
- Closed position P&L inclusion

Created: February 2, 2026
"""

import logging
from typing import Dict, List, Optional, Tuple
import re
from datetime import datetime

log = logging.getLogger('ssr_algo_payoff')

# Contract multipliers (matches frontend constants)
CONTRACT_MULTIPLIERS = {
    'BTC': 0.001,  # 1 contract = 0.001 BTC
    'ETH': 0.01,   # 1 contract = 0.01 ETH
}


def get_contract_multiplier(symbol: str) -> float:
    """Get contract multiplier from symbol."""
    if not symbol:
        return 0.001
    if 'ETH' in symbol.upper():
        return CONTRACT_MULTIPLIERS['ETH']
    return CONTRACT_MULTIPLIERS['BTC']


def parse_symbol(symbol: str) -> Optional[Dict]:
    """
    Parse option symbol to extract details.
    
    Args:
        symbol: Option symbol (e.g., "C-BTC-82000-060226")
    
    Returns:
        {'type': 'call'|'put', 'underlying': str, 'strike': float, 'expiry': str}
    """
    if not symbol:
        return None
    
    parts = symbol.split('-')
    if len(parts) < 4:
        return None
    
    return {
        'type': 'call' if parts[0] == 'C' else 'put',
        'underlying': parts[1],
        'strike': float(parts[2]),
        'expiry': parts[3]
    }


class SSRPayoffCalculator:
    """
    Calculates payoff curves and max loss points for SSR Algo positions.
    """
    
    def __init__(self):
        """Initialize calculator."""
        pass
    
    def generate_price_range(self, 
                             spot_price: float, 
                             range_percent: float = 20,
                             points: int = 200) -> List[float]:
        """
        Generate array of price points for payoff calculation.
        
        Args:
            spot_price: Current spot price
            range_percent: Range as percentage (e.g., 20 for ±20%)
            points: Number of data points
        
        Returns:
            List of price points
        """
        min_price = spot_price * (1 - range_percent / 100)
        max_price = spot_price * (1 + range_percent / 100)
        step = (max_price - min_price) / (points - 1)
        
        return [round(min_price + i * step) for i in range(points)]
    
    def calculate_single_position_payoff(self, 
                                         position: Dict, 
                                         price_at_expiry: float) -> float:
        """
        Calculate single position P&L at a given price (at expiry).
        
        Args:
            position: Position dict with symbol, size, entry_price
            price_at_expiry: Underlying price at expiry
        
        Returns:
            P&L in USD
        """
        symbol = position.get('symbol') or position.get('product_symbol')
        parsed = parse_symbol(symbol)
        
        if not parsed:
            return 0.0
        
        option_type = parsed['type']
        strike = parsed['strike']
        size = position.get('size', 0)
        entry_price = abs(position.get('entry_price', 0) or position.get('premium', 0) or 0)
        multiplier = get_contract_multiplier(symbol)
        
        # Intrinsic value at expiry
        if option_type == 'call':
            intrinsic = max(0, price_at_expiry - strike)
        else:
            intrinsic = max(0, strike - price_at_expiry)
        
        # P&L calculation
        # Long (size > 0): Paid premium, profit from intrinsic
        # Short (size < 0): Received premium, loss from intrinsic
        is_long = size > 0
        direction = 1 if is_long else -1
        
        pnl = (intrinsic - entry_price) * direction * abs(size) * multiplier
        
        return pnl
    
    def calculate_positions_payoff(self, 
                                   positions: List[Dict], 
                                   price_at_expiry: float) -> float:
        """
        Calculate total payoff for multiple positions at a given price.
        
        Args:
            positions: List of position dicts
            price_at_expiry: Underlying price at expiry
        
        Returns:
            Total P&L in USD
        """
        if not positions:
            return 0.0
        
        return sum(
            self.calculate_single_position_payoff(pos, price_at_expiry)
            for pos in positions
        )
    
    def calculate_payoff_curve(self, 
                               positions: List[Dict], 
                               price_range: List[float]) -> List[Dict]:
        """
        Calculate payoff data points for chart.
        
        Args:
            positions: Position objects
            price_range: Array of price points
        
        Returns:
            List of {'price': float, 'pnl': float}
        """
        return [
            {
                'price': price,
                'pnl': self.calculate_positions_payoff(positions, price)
            }
            for price in price_range
        ]
    
    def find_max_loss_points(self, payoff_data: List[Dict]) -> Dict:
        """
        Find max loss points (local minima) from payoff curve.
        
        For a butterfly strategy, there are typically 2 max loss points:
        - Upper max loss (above ATM)
        - Lower max loss (below ATM)
        
        Args:
            payoff_data: List of {'price': float, 'pnl': float}
        
        Returns:
            {
                'max_loss_upper': float,  # Price point of upper max loss
                'max_loss_lower': float,  # Price point of lower max loss
                'max_loss_value': float,  # The max loss amount (negative)
                'max_profit_price': float,  # Price at max profit (typically ATM)
                'max_profit_value': float,  # Max profit value
            }
        """
        if not payoff_data or len(payoff_data) < 3:
            return {
                'max_loss_upper': None,
                'max_loss_lower': None,
                'max_loss_value': None,
                'max_profit_price': None,
                'max_profit_value': None
            }
        
        # Find global min and max
        min_point = min(payoff_data, key=lambda x: x['pnl'])
        max_point = max(payoff_data, key=lambda x: x['pnl'])
        
        # Find local minima (max loss points)
        local_minima = []
        
        for i in range(1, len(payoff_data) - 1):
            prev_pnl = payoff_data[i - 1]['pnl']
            curr_pnl = payoff_data[i]['pnl']
            next_pnl = payoff_data[i + 1]['pnl']
            
            # Local minimum: current point is lower than neighbors
            if curr_pnl <= prev_pnl and curr_pnl <= next_pnl:
                local_minima.append(payoff_data[i])
        
        # If no local minima found, use global minimum
        if not local_minima:
            local_minima = [min_point]
        
        # Sort by price to identify upper and lower
        local_minima.sort(key=lambda x: x['price'])
        
        # For butterfly: first is lower, last is upper
        max_loss_lower = local_minima[0]['price'] if local_minima else None
        max_loss_upper = local_minima[-1]['price'] if len(local_minima) > 1 else local_minima[0]['price'] if local_minima else None
        
        # If only one minimum found, it's probably at edge - treat as both
        if len(local_minima) == 1:
            # Check if it's more towards upper or lower end
            mid_price = (payoff_data[0]['price'] + payoff_data[-1]['price']) / 2
            if local_minima[0]['price'] > mid_price:
                max_loss_upper = local_minima[0]['price']
                max_loss_lower = None
            else:
                max_loss_lower = local_minima[0]['price']
                max_loss_upper = None
        
        return {
            'max_loss_upper': max_loss_upper,
            'max_loss_lower': max_loss_lower,
            'max_loss_value': min_point['pnl'],
            'max_profit_price': max_point['price'],
            'max_profit_value': max_point['pnl']
        }
    
    def find_breakevens(self, payoff_data: List[Dict]) -> List[float]:
        """
        Find breakeven points from payoff data.
        
        Args:
            payoff_data: List of {'price': float, 'pnl': float}
        
        Returns:
            List of breakeven prices
        """
        if not payoff_data or len(payoff_data) < 2:
            return []
        
        breakevens = []
        
        for i in range(1, len(payoff_data)):
            prev = payoff_data[i - 1]
            curr = payoff_data[i]
            
            # Check for zero crossing
            if (prev['pnl'] <= 0 and curr['pnl'] >= 0) or \
               (prev['pnl'] >= 0 and curr['pnl'] <= 0):
                # Linear interpolation
                pnl_diff = abs(curr['pnl'] - prev['pnl'])
                if pnl_diff > 0:
                    ratio = abs(prev['pnl']) / pnl_diff
                    breakeven = prev['price'] + ratio * (curr['price'] - prev['price'])
                    breakevens.append(round(breakeven, 2))
        
        return breakevens
    
    def calculate_net_premium(self, positions: List[Dict]) -> float:
        """
        Calculate net premium (positive = credit, negative = debit).
        
        Args:
            positions: Position objects
        
        Returns:
            Net premium in USD
        """
        if not positions:
            return 0.0
        
        total = 0.0
        for pos in positions:
            symbol = pos.get('symbol') or pos.get('product_symbol')
            premium = abs(pos.get('entry_price', 0) or pos.get('premium', 0) or 0)
            size = abs(pos.get('size', 0))
            multiplier = get_contract_multiplier(symbol)
            is_long = (pos.get('size', 0) > 0)
            
            # Long = paid premium (debit, negative)
            # Short = received premium (credit, positive)
            direction = -1 if is_long else 1
            
            total += premium * size * multiplier * direction
        
        return total
    
    def calculate_aggregated_greeks(self, positions: List[Dict]) -> Dict:
        """
        Calculate aggregated Greeks for all positions.
        
        Args:
            positions: Position objects with greeks
        
        Returns:
            {'delta': float, 'gamma': float, 'theta': float, 'vega': float}
        """
        result = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}
        
        for pos in positions:
            size = pos.get('size', 0)
            greeks = pos.get('greeks', {})
            
            result['delta'] += greeks.get('delta', 0) * size
            result['gamma'] += greeks.get('gamma', 0) * abs(size)
            result['theta'] += (greeks.get('theta', 0) / 1000) * size  # Convert from per-lot
            result['vega'] += (greeks.get('vega', 0) / 1000) * size
        
        return result
    
    def calculate_session_payoff(self, session: Dict) -> Dict:
        """
        Calculate complete payoff data for an SSR Algo session.
        
        ONLY USES FILLED POSITIONS! Pending orders are excluded to prevent
        fake payoff graphs and incorrect max loss trigger zones.
        
        Args:
            session: SSR Algo session data
        
        Returns:
            {
                'payoff_curve': List[Dict],
                'max_loss_points': Dict,
                'breakevens': List[float],
                'net_premium': float,
                'greeks': Dict,
                'spot_price': float,
                'adjustment_triggers': Dict,
                'pending_orders_count': int,  # Number of orders not yet filled
                'warning': str  # Warning if payoff is based on incomplete data
            }
        """
        # Build a map of filled order symbols from filled_orders
        # CRITICAL: Only these symbols will be included in payoff!
        filled_symbols = set()
        fill_prices = {}
        for order in session.get('filled_orders', []):
            symbol = order.get('symbol', '')
            if symbol and order.get('fill_price'):
                filled_symbols.add(symbol)
                fill_prices[symbol] = order['fill_price']
        
        # Build positions list from session - ONLY FILLED POSITIONS
        positions = []
        
        # Track OTM buy strikes for adjustment triggers (protective wings)
        # These are where max loss occurs in iron butterfly structure
        otm_ce_buy_strike = None
        otm_pe_buy_strike = None
        far_otm_ce_strike = None
        far_otm_pe_strike = None
        
        # Get spot/ATM reference from first position group (even if not filled yet)
        first_group = session.get('positions', [{}])[0]
        atm_strike = first_group.get('atm_strike', 0)
        spot_price = atm_strike or 0
        
        for pos_group in session.get('positions', []):
            # ATM CE Sell - ONLY IF FILLED
            if pos_group.get('atm_ce'):
                atm_ce = pos_group['atm_ce']
                symbol = atm_ce.get('symbol')
                # Skip if not filled
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:  # Only include if we have actual fill price
                    positions.append({
                        'symbol': symbol,
                        'size': atm_ce.get('size', -1),
                        'entry_price': entry_price
                    })
            
            # ATM PE Sell - ONLY IF FILLED
            if pos_group.get('atm_pe'):
                atm_pe = pos_group['atm_pe']
                symbol = atm_pe.get('symbol')
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': atm_pe.get('size', -1),
                        'entry_price': entry_price
                    })
            
            # OTM CE Buy - TRACK STRIKE FOR TRIGGERS (even if not filled)
            if pos_group.get('otm_ce_buy'):
                otm_ce = pos_group['otm_ce_buy']
                symbol = otm_ce.get('symbol')
                if symbol and otm_ce_buy_strike is None:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        otm_ce_buy_strike = float(parts[2])
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': otm_ce.get('size', 2),
                        'entry_price': entry_price
                    })
            
            # OTM PE Buy - TRACK STRIKE FOR TRIGGERS (even if not filled)
            if pos_group.get('otm_pe_buy'):
                otm_pe = pos_group['otm_pe_buy']
                symbol = otm_pe.get('symbol')
                if symbol and otm_pe_buy_strike is None:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        otm_pe_buy_strike = float(parts[2])
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': otm_pe.get('size', 2),
                        'entry_price': entry_price
                    })
            
            # Far OTM CE Sell - TRACK STRIKE FOR REFERENCE (even if not filled)
            if pos_group.get('far_otm_ce'):
                far_ce = pos_group['far_otm_ce']
                symbol = far_ce.get('symbol', '')
                if symbol and far_otm_ce_strike is None:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        far_otm_ce_strike = float(parts[2])
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': far_ce.get('size', -1),
                        'entry_price': entry_price
                    })
            
            # Far OTM PE Sell - TRACK STRIKE FOR REFERENCE (even if not filled)
            if pos_group.get('far_otm_pe'):
                far_pe = pos_group['far_otm_pe']
                symbol = far_pe.get('symbol', '')
                if symbol and far_otm_pe_strike is None:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        far_otm_pe_strike = float(parts[2])
                if symbol not in filled_symbols:
                    continue
                entry_price = fill_prices.get(symbol, 0)
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': far_pe.get('size', -1),
                        'entry_price': entry_price
                    })
        
        # Include closed positions as phantom positions
        for closed in session.get('closed_positions', []):
            # Closed positions contribute fixed P&L
            # We handle them separately
            pass
        
        if not positions:
            pending_count = len(session.get('pending_orders', []))
            warning = f"⚠️ No filled positions yet ({pending_count} orders pending)" if pending_count > 0 else "⚠️ No positions"
            price_tolerance = session.get('price_tolerance', 100)
            adjustment_triggers = {
                'upper_trigger': otm_ce_buy_strike,
                'lower_trigger': otm_pe_buy_strike,
                'tolerance': price_tolerance,
                'dwell_time_minutes': session.get('dwell_time_minutes', 10),
                'description': f'Triggers at OTM buy strikes (protective wings) ±{price_tolerance}, dwell {session.get("dwell_time_minutes", 10)} min'
            }
            return {
                'payoff_curve': [],
                'max_loss_points': {},
                'breakevens': [],
                'net_premium': 0,
                'greeks': {},
                'spot_price': spot_price,
                'adjustment_triggers': adjustment_triggers,
                'otm_ce_buy_strike': otm_ce_buy_strike,
                'otm_pe_buy_strike': otm_pe_buy_strike,
                'far_otm_ce_strike': far_otm_ce_strike,
                'far_otm_pe_strike': far_otm_pe_strike,
                'atm_strike': atm_strike,
                'pending_orders_count': pending_count,
                'warning': warning
            }
        
        # Get spot price from first position group
        spot_price = spot_price or 75000  # Default fallback
        
        # Generate price range
        price_range = self.generate_price_range(spot_price, range_percent=25, points=200)
        
        # Calculate payoff curve
        payoff_curve = self.calculate_payoff_curve(positions, price_range)
        
        # Add realized P&L from closed positions
        closed_pnl = sum(
            closed.get('realized_pnl', 0)
            for closed in session.get('closed_positions', [])
        )
        
        if closed_pnl != 0:
            for point in payoff_curve:
                point['pnl'] += closed_pnl
        
        # Find max loss points from payoff curve
        max_loss_points = self.find_max_loss_points(payoff_curve)
        
        # CRITICAL FIX PER ARCHITECTURE:
        # Use OTM BUY strikes as adjustment triggers (protective wings)
        # These are where max loss occurs in iron butterfly structure
        # NOT the far OTM sell strikes which are further out
        price_tolerance = session.get('price_tolerance', 100)
        
        adjustment_triggers = {
            'upper_trigger': otm_ce_buy_strike,  # When price reaches upper protective wing
            'lower_trigger': otm_pe_buy_strike,  # When price reaches lower protective wing
            'tolerance': price_tolerance,
            'dwell_time_minutes': session.get('dwell_time_minutes', 10),
            'description': f'Triggers at OTM buy strikes (protective wings) ±{price_tolerance}, dwell {session.get("dwell_time_minutes", 10)} min'
        }
        
        # Override max_loss_points with OTM buy strikes for monitoring
        # These are the actual trigger points per architecture
        if otm_ce_buy_strike:
            max_loss_points['max_loss_upper'] = otm_ce_buy_strike
        if otm_pe_buy_strike:
            max_loss_points['max_loss_lower'] = otm_pe_buy_strike
        
        # Find breakevens
        breakevens = self.find_breakevens(payoff_curve)
        
        # Calculate net premium
        net_premium = self.calculate_net_premium(positions)
        
        # Calculate Greeks (if available)
        greeks = self.calculate_aggregated_greeks(positions)
        
        # Count pending orders
        pending_count = len(session.get('pending_orders', []))
        total_expected_positions = len(session.get('positions', [])) * 6  # 6 legs per position group
        
        # Warning if payoff based on incomplete data
        warning = None
        if pending_count > 0:
            warning = f"⚠️ {pending_count} orders still pending - payoff based only on {len(positions)} filled positions"
        elif len(positions) == 0:
            warning = "⚠️ No filled positions yet - payoff calculation unavailable"
        
        return {
            'payoff_curve': payoff_curve,
            'max_loss_points': max_loss_points,
            'breakevens': breakevens,
            'net_premium': net_premium,
            'greeks': greeks,
            'spot_price': spot_price,
            'position_count': len(positions),
            'adjustment_triggers': adjustment_triggers,
            'otm_ce_buy_strike': otm_ce_buy_strike,  # Upper protective wing
            'otm_pe_buy_strike': otm_pe_buy_strike,  # Lower protective wing
            'far_otm_ce_strike': far_otm_ce_strike,  # Far OTM sell (for reference)
            'far_otm_pe_strike': far_otm_pe_strike,  # Far OTM sell (for reference)
            'atm_strike': atm_strike,
            'pending_orders_count': pending_count,
            'warning': warning
        }
    
    def is_price_in_max_loss_zone(self, 
                                   current_price: float, 
                                   max_loss_upper: float, 
                                   max_loss_lower: float,
                                   tolerance: float = 100) -> Tuple[bool, str]:
        """
        Check if current price is within a max loss zone.
        
        Args:
            current_price: Current underlying price
            max_loss_upper: Upper max loss price point
            max_loss_lower: Lower max loss price point
            tolerance: Price tolerance (±100)
        
        Returns:
            (is_in_zone: bool, zone: 'upper'|'lower'|None)
        """
        if max_loss_upper and abs(current_price - max_loss_upper) <= tolerance:
            return True, 'upper'
        
        if max_loss_lower and abs(current_price - max_loss_lower) <= tolerance:
            return True, 'lower'
        
        return False, None


# Singleton instance
_calculator = None

def get_payoff_calculator() -> SSRPayoffCalculator:
    """Get the singleton payoff calculator instance."""
    global _calculator
    if _calculator is None:
        _calculator = SSRPayoffCalculator()
    return _calculator
