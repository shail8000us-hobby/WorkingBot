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
        Find max loss points (V-valley bottoms) from payoff curve.
        
        For a butterfly strategy, there are typically 2 max loss points:
        - Upper max loss (above ATM, at OTM CE buy strike)
        - Lower max loss (below ATM, at OTM PE buy strike)
        
        Algorithm:
        1. Find the global profit peak (typically at ATM)
        2. Split the curve at the peak into lower side and upper side
        3. On each side, find the global minimum (the V-valley bottom)
        
        This correctly identifies the OTM buy strikes as trigger zones
        and ignores the flat wing regions that previously caused false
        detections at price range edges.
        
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
        
        # Find global max (profit peak - typically at ATM)
        max_idx = max(range(len(payoff_data)), key=lambda i: payoff_data[i]['pnl'])
        max_point = payoff_data[max_idx]
        
        # Find global min for reference
        min_point = min(payoff_data, key=lambda x: x['pnl'])
        
        # Split curve at profit peak and find minimum on each side
        # Lower side: from start up to and including peak
        lower_side = payoff_data[:max_idx + 1]
        max_loss_lower = None
        if len(lower_side) > 1:
            min_lower = min(lower_side, key=lambda x: x['pnl'])
            # Only count as max loss zone if PnL is actually below the peak
            # (i.e., there IS a valley, not just a flat region)
            if min_lower['pnl'] < max_point['pnl'] * 0.5:
                max_loss_lower = min_lower['price']
        
        # Upper side: from peak to end
        upper_side = payoff_data[max_idx:]
        max_loss_upper = None
        if len(upper_side) > 1:
            min_upper = min(upper_side, key=lambda x: x['pnl'])
            if min_upper['pnl'] < max_point['pnl'] * 0.5:
                max_loss_upper = min_upper['price']
        
        # Edge case: if peak is at the very start or end, only one side exists
        # In that case, try to find two valleys on the available side
        if max_loss_lower is None and max_loss_upper is None:
            # Fallback: find first true valley (strict decrease then increase)
            for i in range(1, len(payoff_data) - 1):
                prev_pnl = payoff_data[i - 1]['pnl']
                curr_pnl = payoff_data[i]['pnl']
                next_pnl = payoff_data[i + 1]['pnl']
                if curr_pnl < prev_pnl and curr_pnl < next_pnl:
                    if max_loss_lower is None:
                        max_loss_lower = payoff_data[i]['price']
                    elif max_loss_upper is None and payoff_data[i]['price'] > max_loss_lower:
                        max_loss_upper = payoff_data[i]['price']
        
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
        
        Includes ALL positions from ALL position groups (initial + adjustments).
        Uses actual fill prices where available, falls back to entry prices.
        Max loss zones are DYNAMICALLY CALCULATED from the combined payoff curve.
        
        After each adjustment, the combined payoff shape changes, so max loss
        zones shift. This ensures the algo monitors the CORRECT trigger points.
        
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
                'pending_orders_count': int,
                'warning': str
            }
        """
        # Build a map of filled order symbols from filled_orders
        # These provide actual fill prices (more accurate than entry estimates)
        filled_symbols = set()
        fill_prices = {}
        for order in session.get('filled_orders', []):
            symbol = order.get('symbol', '')
            if symbol and order.get('fill_price'):
                filled_symbols.add(symbol)
                # Use latest fill price for the symbol
                fill_prices[symbol] = order['fill_price']
        
        # Build positions list from ALL position groups (initial + adjustments)
        # This is CRITICAL: payoff must reflect the COMBINED position
        positions = []
        
        # Track strikes from the LATEST position group for reference
        # (After adjustments, the latest group defines the "current" structure)
        latest_otm_ce_buy_strike = None
        latest_otm_pe_buy_strike = None
        latest_far_otm_ce_strike = None
        latest_far_otm_pe_strike = None
        latest_atm_strike = None
        
        # Get spot/ATM reference from latest active position group
        all_groups = session.get('positions', [])
        if all_groups:
            latest_group = all_groups[-1]  # Latest group (most recent adjustment)
            latest_atm_strike = latest_group.get('atm_strike', 0)
        
        first_group = all_groups[0] if all_groups else {}
        first_atm_strike = first_group.get('atm_strike', 0)
        spot_price = latest_atm_strike or first_atm_strike or 0
        
        leg_keys = {
            'atm_ce':      {'default_size': -1, 'key': None},
            'atm_pe':      {'default_size': -1, 'key': None},
            'otm_ce_buy':  {'default_size':  2, 'key': 'otm_ce_buy'},
            'otm_pe_buy':  {'default_size':  2, 'key': 'otm_pe_buy'},
            'far_otm_ce':  {'default_size': -1, 'key': 'far_otm_ce'},
            'far_otm_pe':  {'default_size': -1, 'key': 'far_otm_pe'},
        }
        
        for pos_group in all_groups:
            for leg_name, leg_info in leg_keys.items():
                leg_data = pos_group.get(leg_name)
                if not leg_data:
                    continue
                
                symbol = leg_data.get('symbol')
                if not symbol:
                    continue
                
                # Use actual fill price if available, otherwise use entry_price from position group
                entry_price = fill_prices.get(symbol, 0) or abs(leg_data.get('entry_price', 0) or 0)
                
                if entry_price > 0:
                    positions.append({
                        'symbol': symbol,
                        'size': leg_data.get('size', leg_info['default_size']),
                        'entry_price': entry_price
                    })
                
                # Track strikes from LATEST group for reference
                # Always update (not "is None" check) so latest group wins
                strike_key = leg_info.get('key')
                if strike_key and symbol:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        strike_val = float(parts[2])
                        if strike_key == 'otm_ce_buy':
                            latest_otm_ce_buy_strike = strike_val
                        elif strike_key == 'otm_pe_buy':
                            latest_otm_pe_buy_strike = strike_val
                        elif strike_key == 'far_otm_ce':
                            latest_far_otm_ce_strike = strike_val
                        elif strike_key == 'far_otm_pe':
                            latest_far_otm_pe_strike = strike_val
        
        price_tolerance = session.get('price_tolerance', 100)
        
        if not positions:
            pending_count = len(session.get('pending_orders', []))
            warning = f"⚠️ No positions yet ({pending_count} orders pending)" if pending_count > 0 else "⚠️ No positions"
            adjustment_triggers = {
                'upper_trigger': latest_otm_ce_buy_strike,
                'lower_trigger': latest_otm_pe_buy_strike,
                'tolerance': price_tolerance,
                'dwell_time_minutes': session.get('dwell_time_minutes', 10),
                'description': f'Triggers at max loss zones ±{price_tolerance}, dwell {session.get("dwell_time_minutes", 10)} min'
            }
            return {
                'payoff_curve': [],
                'max_loss_points': {},
                'breakevens': [],
                'net_premium': 0,
                'greeks': {},
                'spot_price': spot_price,
                'adjustment_triggers': adjustment_triggers,
                'otm_ce_buy_strike': latest_otm_ce_buy_strike,
                'otm_pe_buy_strike': latest_otm_pe_buy_strike,
                'far_otm_ce_strike': latest_far_otm_ce_strike,
                'far_otm_pe_strike': latest_far_otm_pe_strike,
                'atm_strike': latest_atm_strike or first_atm_strike,
                'pending_orders_count': pending_count,
                'warning': warning
            }
        
        # Get spot price fallback
        spot_price = spot_price or 75000
        
        # Generate price range centered around current spot/ATM
        price_range = self.generate_price_range(spot_price, range_percent=25, points=200)
        
        # Calculate COMBINED payoff curve from ALL positions (initial + adjustments)
        payoff_curve = self.calculate_payoff_curve(positions, price_range)
        
        # Add realized P&L from closed positions
        closed_pnl = sum(
            closed.get('realized_pnl', 0)
            for closed in session.get('closed_positions', [])
        )
        
        if closed_pnl != 0:
            for point in payoff_curve:
                point['pnl'] += closed_pnl
        
        # DYNAMIC MAX LOSS ZONES: Calculate from the ACTUAL combined payoff curve
        # After adjustments, the payoff shape changes and max loss zones shift
        # This is the CRITICAL fix: zones are recalculated, not hardcoded to initial strikes
        max_loss_points = self.find_max_loss_points(payoff_curve)
        
        # The adjustment triggers are the max loss zones from the combined payoff
        # NOT the initial OTM buy strikes (which were only correct before first adjustment)
        upper_trigger = max_loss_points.get('max_loss_upper')
        lower_trigger = max_loss_points.get('max_loss_lower')
        
        adjustment_triggers = {
            'upper_trigger': upper_trigger,
            'lower_trigger': lower_trigger,
            'tolerance': price_tolerance,
            'dwell_time_minutes': session.get('dwell_time_minutes', 10),
            'description': f'Triggers at max loss zones from combined payoff ±{price_tolerance}, dwell {session.get("dwell_time_minutes", 10)} min'
        }
        
        # Find breakevens
        breakevens = self.find_breakevens(payoff_curve)
        
        # Calculate net premium
        net_premium = self.calculate_net_premium(positions)
        
        # Calculate Greeks (if available)
        greeks = self.calculate_aggregated_greeks(positions)
        
        # Count pending orders
        pending_count = len(session.get('pending_orders', []))
        
        # Warning if payoff based on incomplete data
        warning = None
        if pending_count > 0:
            warning = f"⚠️ {pending_count} orders still pending - payoff includes estimated prices for some positions"
        
        return {
            'payoff_curve': payoff_curve,
            'max_loss_points': max_loss_points,
            'breakevens': breakevens,
            'net_premium': net_premium,
            'greeks': greeks,
            'spot_price': spot_price,
            'position_count': len(positions),
            'adjustment_triggers': adjustment_triggers,
            'otm_ce_buy_strike': latest_otm_ce_buy_strike,
            'otm_pe_buy_strike': latest_otm_pe_buy_strike,
            'far_otm_ce_strike': latest_far_otm_ce_strike,
            'far_otm_pe_strike': latest_far_otm_pe_strike,
            'atm_strike': latest_atm_strike or first_atm_strike,
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
