"""
SSR ALGO Greeks - Live Greeks Fetcher & MTM P&L Engine

Fetches live Greeks for all positions in an SSR Algo session from exchange chain data,
calculates portfolio-level aggregated Greeks and mark-to-market P&L.

Uses OptionsChainService (10s cache) as primary source, with Black-Scholes-Merton
fallback for missing/zero Greeks (deep OTM near expiry).

Created: February 20, 2026
Phase 1 of SSR Algo Development Plan
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from .ssr_algo_payoff import parse_symbol, get_contract_multiplier, CONTRACT_MULTIPLIERS
from .ssr_algo_engine import normalize_expiry_format

log = logging.getLogger('ssr_algo_greeks')

# IST timezone for expiry calculations
IST = ZoneInfo('Asia/Kolkata')

# Leg keys in a position group
POSITION_LEG_KEYS = ['atm_ce', 'atm_pe', 'otm_ce_buy', 'otm_pe_buy', 'far_otm_ce', 'far_otm_pe']


class SSRGreeksFetcher:
    """
    Fetches live Greeks and calculates MTM P&L for SSR Algo positions.

    Uses exchange-provided Greeks from chain data (delta, gamma, theta, vega, iv, mark_price).
    Falls back to Black-Scholes-Merton when exchange returns 0 for Greeks.
    """

    def __init__(self):
        self._chain_service = None
        self._pricing_engine = None

    @property
    def chain_service(self):
        if self._chain_service is None:
            from webui.backend.options_chain.chain_service import OptionsChainService
            self._chain_service = OptionsChainService()
        return self._chain_service

    @property
    def pricing_engine(self):
        if self._pricing_engine is None:
            from webui.backend.options_strategy.pricing_engine import OptionPricingEngine
            self._pricing_engine = OptionPricingEngine
        return self._pricing_engine

    def _calculate_time_to_expiry(self, expiry: str) -> float:
        """
        Calculate time to expiry in years.

        Args:
            expiry: Expiry date in DDMMYYYY or DDMMYY format

        Returns:
            Time to expiry in years (fractional)
        """
        try:
            normalized = normalize_expiry_format(expiry)
            expiry_dt = datetime.strptime(normalized, '%d%m%Y')
            # Expiry at 5:30 PM IST = 12:00 UTC
            expiry_dt = expiry_dt.replace(hour=17, minute=30, tzinfo=IST)
            now = datetime.now(IST)
            diff = expiry_dt - now
            years = diff.total_seconds() / (365.25 * 24 * 3600)
            return max(years, 0.0)
        except Exception as e:
            log.warning(f"Could not calculate time_to_expiry for {expiry}: {e}")
            return 0.0

    def _find_strike_in_chain(self, chain_data: Dict, symbol: str) -> Optional[Dict]:
        """
        Find a specific option in chain data by symbol.

        Args:
            chain_data: Chain data from chain_service.get_chain_data()
            symbol: Option symbol (e.g., "C-BTC-82000-060226")

        Returns:
            Option data dict with Greeks, or None
        """
        parsed = parse_symbol(symbol)
        if not parsed:
            return None

        target_strike = parsed['strike']
        option_type = 'call' if parsed['type'] == 'call' else 'put'

        for strike_row in chain_data.get('chain', []):
            if strike_row.get('strike') == target_strike:
                option_data = strike_row.get(option_type)
                if option_data and option_data.get('symbol') == symbol:
                    return option_data
                # Symbol might differ in expiry format, match by strike
                if option_data:
                    return option_data

        return None

    def _get_bsm_greeks(self, symbol: str, spot_price: float, iv: float,
                         time_to_expiry: float) -> Dict:
        """
        Calculate Greeks using Black-Scholes-Merton as fallback.

        Args:
            symbol: Option symbol
            spot_price: Current spot price
            iv: Implied volatility (as decimal, e.g., 0.60 for 60%)
            time_to_expiry: Time to expiry in years

        Returns:
            Dict with delta, gamma, theta, vega
        """
        parsed = parse_symbol(symbol)
        if not parsed or time_to_expiry <= 0:
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}

        option_type = parsed['type']
        strike = parsed['strike']

        # Use default IV if none provided
        if iv <= 0:
            iv = 0.60

        try:
            result = self.pricing_engine.black_scholes_merton(
                spot=spot_price,
                strike=strike,
                time_to_expiry=time_to_expiry,
                risk_free_rate=0.0,
                volatility=iv,
                dividend_yield=0.0,
                option_type=option_type
            )
            return {
                'delta': result.get('delta', 0.0),
                'gamma': result.get('gamma', 0.0),
                'theta': result.get('theta', 0.0),
                'vega': result.get('vega', 0.0)
            }
        except Exception as e:
            log.warning(f"BSM fallback failed for {symbol}: {e}")
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}

    def fetch_position_greeks(self, session: Dict) -> List[Dict]:
        """
        Fetch live Greeks for all positions in an SSR Algo session.

        Args:
            session: SSR Algo session data (from storage)

        Returns:
            List of per-leg Greeks dicts:
            [
                {
                    'symbol': str,
                    'leg_key': str,
                    'trigger_id': int,
                    'size': int,
                    'delta': float,
                    'gamma': float,
                    'theta': float,
                    'vega': float,
                    'iv': float,
                    'mark_price': float,
                    'entry_price': float,
                    'source': 'exchange' | 'bsm_fallback'
                },
                ...
            ]
        """
        positions = session.get('positions', [])
        if not positions:
            return []

        underlying = session.get('underlying', 'BTC')
        expiry = session.get('expiry', '')

        # Normalize expiry for chain_service
        try:
            normalized_expiry = normalize_expiry_format(expiry)
        except ValueError:
            log.warning(f"Invalid expiry format: {expiry}")
            return []

        # Fetch chain data (cached for 10s)
        try:
            chain_data = self.chain_service.get_chain_data(underlying, normalized_expiry)
        except Exception as e:
            log.warning(f"Failed to fetch chain data: {e}")
            return []

        spot_price = chain_data.get('spot_price', 0)
        time_to_expiry = self._calculate_time_to_expiry(expiry)

        result = []

        for position_group in positions:
            trigger_id = position_group.get('trigger_id', 0)

            for leg_key in POSITION_LEG_KEYS:
                leg = position_group.get(leg_key)
                if not leg or not isinstance(leg, dict):
                    continue

                symbol = leg.get('symbol')
                if not symbol:
                    continue

                # Skip closed legs
                if leg.get('closed', False):
                    continue

                size = leg.get('size', 0)
                entry_price = leg.get('fill_price') or leg.get('entry_price', 0)

                # Find in chain data
                option_data = self._find_strike_in_chain(chain_data, symbol)

                if option_data:
                    delta = option_data.get('delta', 0)
                    gamma = option_data.get('gamma', 0)
                    theta = option_data.get('theta', 0)
                    vega = option_data.get('vega', 0)
                    iv = option_data.get('iv', 0)
                    mark_price = option_data.get('mark_price', 0)
                    source = 'exchange'

                    # If exchange returns 0 for all Greeks (deep OTM near expiry), use BSM
                    if delta == 0 and gamma == 0 and theta == 0 and time_to_expiry > 0:
                        bsm = self._get_bsm_greeks(symbol, spot_price, iv / 100 if iv > 1 else iv, time_to_expiry)
                        delta = bsm['delta']
                        gamma = bsm['gamma']
                        theta = bsm['theta']
                        vega = bsm['vega']
                        source = 'bsm_fallback'
                else:
                    # No chain data at all — full BSM fallback
                    mark_price = entry_price  # Best guess
                    iv = 0.60
                    bsm = self._get_bsm_greeks(symbol, spot_price, iv, time_to_expiry)
                    delta = bsm['delta']
                    gamma = bsm['gamma']
                    theta = bsm['theta']
                    vega = bsm['vega']
                    source = 'bsm_fallback'

                result.append({
                    'symbol': symbol,
                    'leg_key': leg_key,
                    'trigger_id': trigger_id,
                    'size': size,
                    'delta': delta,
                    'gamma': gamma,
                    'theta': theta,
                    'vega': vega,
                    'iv': iv,
                    'mark_price': mark_price,
                    'entry_price': entry_price,
                    'source': source
                })

        return result

    def calculate_portfolio_greeks(self, position_greeks: List[Dict],
                                    underlying: str = 'BTC') -> Dict:
        """
        Calculate portfolio-level aggregated Greeks.

        Sums up Greeks across all legs, weighted by size and contract multiplier.
        For sells (negative size), delta contribution is negative.

        Args:
            position_greeks: Per-leg Greeks from fetch_position_greeks()
            underlying: BTC or ETH (for contract multiplier)

        Returns:
            {
                'net_delta': float,
                'net_gamma': float,
                'net_theta': float,
                'net_vega': float,
                'leg_count': int
            }
        """
        multiplier = CONTRACT_MULTIPLIERS.get(underlying, 0.001)

        net_delta = 0.0
        net_gamma = 0.0
        net_theta = 0.0
        net_vega = 0.0

        for leg in position_greeks:
            size = leg.get('size', 0)
            if size == 0:
                continue

            # Delta: directional, sign matters (short = negative size)
            net_delta += leg['delta'] * size * multiplier
            # Gamma: always positive contribution (use abs size)
            net_gamma += leg['gamma'] * abs(size) * multiplier
            # Theta: directional (short options = positive theta = earning decay)
            net_theta += leg['theta'] * size * multiplier
            # Vega: directional (short options = negative vega)
            net_vega += leg['vega'] * size * multiplier

        return {
            'net_delta': round(net_delta, 6),
            'net_gamma': round(net_gamma, 6),
            'net_theta': round(net_theta, 4),
            'net_vega': round(net_vega, 4),
            'leg_count': len(position_greeks)
        }

    def calculate_mtm_pnl(self, session: Dict, position_greeks: List[Dict]) -> Dict:
        """
        Calculate mark-to-market P&L for the session.

        For each leg:
            leg_pnl = (current_price - entry_price) * size * contract_multiplier
            (for sells, size is negative, so loss on price increase is automatic)

        Args:
            session: SSR Algo session data
            position_greeks: Per-leg Greeks with mark_price from fetch_position_greeks()

        Returns:
            {
                'unrealized_pnl': float,     # Sum of all open leg P&Ls
                'realized_pnl': float,       # From closed positions
                'total_pnl': float,          # unrealized + realized
                'per_leg_pnl': [             # Breakdown per leg
                    {
                        'symbol': str,
                        'leg_key': str,
                        'size': int,
                        'entry_price': float,
                        'current_price': float,
                        'pnl': float
                    },
                    ...
                ]
            }
        """
        underlying = session.get('underlying', 'BTC')
        multiplier = CONTRACT_MULTIPLIERS.get(underlying, 0.001)

        unrealized_pnl = 0.0
        per_leg_pnl = []

        for leg in position_greeks:
            entry_price = leg.get('entry_price', 0)
            current_price = leg.get('mark_price', 0)
            size = leg.get('size', 0)

            if size == 0 or entry_price == 0:
                continue

            # P&L = (current - entry) * size * multiplier
            # For short (size < 0): if price went up, (current - entry) > 0, * negative size = loss
            leg_pnl = (current_price - entry_price) * size * multiplier
            unrealized_pnl += leg_pnl

            per_leg_pnl.append({
                'symbol': leg['symbol'],
                'leg_key': leg['leg_key'],
                'trigger_id': leg.get('trigger_id', 0),
                'size': size,
                'entry_price': round(entry_price, 2),
                'current_price': round(current_price, 2),
                'pnl': round(leg_pnl, 4)
            })

        # Realized P&L from closed positions
        realized_pnl = 0.0
        for closed in session.get('closed_positions', []):
            realized_pnl += closed.get('pnl', 0)

        return {
            'unrealized_pnl': round(unrealized_pnl, 4),
            'realized_pnl': round(realized_pnl, 4),
            'total_pnl': round(unrealized_pnl + realized_pnl, 4),
            'per_leg_pnl': per_leg_pnl
        }


# Singleton instance
_greeks_fetcher = None

def get_greeks_fetcher() -> SSRGreeksFetcher:
    """Get singleton SSRGreeksFetcher instance."""
    global _greeks_fetcher
    if _greeks_fetcher is None:
        _greeks_fetcher = SSRGreeksFetcher()
    return _greeks_fetcher
