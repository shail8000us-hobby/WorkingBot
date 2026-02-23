"""
MMM Initializer — Money Mind & Method

Handles strike selection and session initialization.
Two modes:
  Mode A: Auto-select — algo finds best strikes matching desired premium
  Mode B: Manual select — user picks specific strikes from the full option chain

Smart Execution integration:
  - Orders placed at mid-price (bid+ask)/2
  - Wait 60s for fill, reprice if unfilled
  - Handled by mmm_executor.py

References:
  MONEY_POWER_CALCULATION_LOGIC.md §3: Initialization
  §15: BTC-Specific Considerations

Created: February 15, 2026
Updated: February 15, 2026 — Robust strike selection + full chain scan
"""

import logging
import sys
import os
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

log = logging.getLogger('mmm_initializer')

# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# BTC options on Delta Exchange expire at 5:30 PM IST (12:00 PM UTC).
# L-1 fix: these are defaults; callers can override via session params
# expiry_hour_utc and expiry_minute_utc.
DEFAULT_EXPIRY_HOUR_UTC = 12
DEFAULT_EXPIRY_MINUTE_UTC = 0


def expiry_to_utc_datetime(expiry_ddmmyyyy: str, params: dict = None) -> str:
    """
    Convert DDMMYYYY expiry date to a full UTC datetime ISO string.

    BTC options expire at 5:30 PM IST (17:30 IST = 12:00 UTC) by default.
    L-1 fix: expiry time is now configurable via session params
    'expiry_hour_utc' and 'expiry_minute_utc' so the algo works with other
    exchanges or instruments that expire at different times.

    The algo uses this to calculate minutes_to_expiry for:
      - Near-expiry safety (stop adjustments at 15 min, auto-close at 5 min)
      - Theta acceleration near expiry

    Args:
        expiry_ddmmyyyy: Date string in DDMMYYYY format
        params: Session params dict (optional); reads expiry_hour_utc /
                expiry_minute_utc with fallback to DEFAULT values.

    Returns:
        ISO format UTC datetime string, e.g. '2026-02-16T12:00:00+00:00'
    """
    if params is None:
        params = {}
    expiry_hour_utc = params.get('expiry_hour_utc', DEFAULT_EXPIRY_HOUR_UTC)
    expiry_minute_utc = params.get('expiry_minute_utc', DEFAULT_EXPIRY_MINUTE_UTC)

    dt = datetime.strptime(expiry_ddmmyyyy, '%d%m%Y')
    expiry_utc = dt.replace(
        hour=expiry_hour_utc,
        minute=expiry_minute_utc,
        second=0,
        microsecond=0,
        tzinfo=timezone.utc,
    )
    # Fix #14: store as timezone-aware UTC ISO string (e.g. '2026-02-22T12:00:00+00:00').
    # _get_minutes_to_expiry() normalises naive legacy strings, so both formats work.
    return expiry_utc.isoformat()


def normalize_expiry(expiry: str) -> str:
    """
    Normalize expiry date format to DDMMYYYY (8 digits).

    Accepts DDMMYY (6-digit), DDMMYYYY (8-digit), or YYYY-MM-DD.

    Returns:
        Normalized DDMMYYYY string
    """
    if not expiry:
        raise ValueError("Expiry date is required")

    expiry = str(expiry).strip()

    if len(expiry) == 8 and expiry.isdigit():
        datetime.strptime(expiry, '%d%m%Y')  # validate
        return expiry

    if len(expiry) == 6 and expiry.isdigit():
        dt = datetime.strptime(expiry, '%d%m%y')
        return dt.strftime('%d%m%Y')

    if len(expiry) == 10 and '-' in expiry:
        dt = datetime.strptime(expiry, '%Y-%m-%d')
        return dt.strftime('%d%m%Y')

    raise ValueError(f"Unsupported expiry format: '{expiry}'. Use DDMMYY, DDMMYYYY, or YYYY-MM-DD")


def expiry_to_symbol_suffix(expiry_ddmmyyyy: str) -> str:
    """
    Convert DDMMYYYY to DDMMYY for Delta Exchange symbol construction.

    e.g. '15022026' → '150226'
    """
    return expiry_ddmmyyyy[:4] + expiry_ddmmyyyy[6:]


class MMMInitializer:
    """
    Strike selection and initialization engine for MMM.

    Two initialization paths:
      1. Auto-select (Mode A): Specify desired premium → algo finds best OTM strikes
      2. Manual select (Mode B): Browse full chain → pick exact CE and PE strikes

    Both paths feed into smart execution for order placement.
    """

    def __init__(self, chain_service=None):
        self._chain_service = chain_service

    @property
    def chain_service(self):
        """Lazy load OptionsChainService."""
        if self._chain_service is None:
            try:
                from webui.backend.options_chain.chain_service import OptionsChainService
                self._chain_service = OptionsChainService()
            except ImportError as e:
                log.error(f"Failed to import chain service: {e}")
                raise
        return self._chain_service

    # =========================================================================
    # Public API: Chain Data
    # =========================================================================

    def get_spot_price(self, underlying: str = 'BTC') -> float:
        """Get current spot price."""
        return self.chain_service._get_spot_price(underlying)

    def get_available_expiries(self, underlying: str = 'BTC') -> List[str]:
        """
        Get available expiry dates.

        Returns:
            List of expiry strings in DDMMYYYY format, sorted chronologically.
        """
        return self.chain_service.get_expirations(underlying)

    def get_full_chain(
        self,
        expiry: str,
        underlying: str = 'BTC',
    ) -> Dict[str, Any]:
        """
        Get the FULL option chain for user to browse and manually select strikes.

        This powers the MMMStrikeSelector component — same data as the existing
        Options Chain Panel but formatted for MMM's needs.

        Returns:
            {
                success: bool,
                spot_price: float,
                atm_strike: float,
                chain: [
                    {
                        strike: float,
                        call: {
                            symbol, bid, ask, mark_price, bid_size, ask_size,
                            mid_price, delta, gamma, theta, vega, iv, oi
                        },
                        put: { ... same fields ... },
                        moneyness_call: 'ITM'|'ATM'|'OTM',
                        moneyness_put: 'ITM'|'ATM'|'OTM',
                    },
                    ...
                ],
                error: str (if not success)
            }
        """
        try:
            expiry_normalized = normalize_expiry(expiry)
            chain_data = self.chain_service.get_chain_data(underlying, expiry_normalized)

            if not chain_data or not chain_data.get('chain'):
                return {
                    'success': False,
                    'error': f'No chain data for {underlying} expiry {expiry_normalized}',
                }

            spot_price = chain_data.get('spot_price', 0)
            atm_strike = chain_data.get('atm_strike', 0)
            raw_chain = chain_data['chain']

            # Enrich each row with mid_price and moneyness
            enriched = []
            for entry in raw_chain:
                strike = entry.get('strike', 0)
                row = {
                    'strike': strike,
                    'call': self._enrich_option(entry.get('call'), 'call', underlying, strike, expiry_normalized),
                    'put': self._enrich_option(entry.get('put'), 'put', underlying, strike, expiry_normalized),
                    'moneyness_call': self._get_moneyness(strike, spot_price, 'call'),
                    'moneyness_put': self._get_moneyness(strike, spot_price, 'put'),
                }
                enriched.append(row)

            return {
                'success': True,
                'spot_price': spot_price,
                'atm_strike': atm_strike,
                'chain': enriched,
                'expiry': expiry_normalized,
                'strike_count': len(enriched),
            }

        except Exception as e:
            log.exception("Failed to get full chain")
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # Public API: Auto-Select (Mode A)
    # =========================================================================

    def preview_strikes(
        self,
        desired_ce_premium: float,
        desired_pe_premium: float,
        expiry: str,
        underlying: str = 'BTC',
    ) -> Dict[str, Any]:
        """
        Auto-find strikes closest to desired premiums.

        Section 3, Mode A: fetch chain → scan OTM calls/puts → find closest
        to desired premium → further OTM wins ties.

        Scoring system (lower = better):
          1. Primary: |mark_price - desired_premium|  (premium accuracy)
          2. Tiebreaker: further OTM preferred (safer)
          3. Penalty: low liquidity (bid_size < 5) gets penalty
          4. Penalty: zero bid gets large penalty (unsellable)

        Returns:
            {
                success, spot_price,
                ce: { strike, premium, symbol, bid, ask, delta, ... },
                pe: { strike, premium, symbol, bid, ask, delta, ... },
                alternatives: { ce: [...top 5...], pe: [...top 5...] }
            }
        """
        try:
            expiry_normalized = normalize_expiry(expiry)

            chain_data = self.chain_service.get_chain_data(underlying, expiry_normalized)
            if not chain_data or not chain_data.get('chain'):
                return {
                    'success': False,
                    'error': f'No options chain data for {underlying} expiry {expiry_normalized}',
                }

            spot_price = chain_data.get('spot_price', 0)
            if spot_price <= 0:
                return {'success': False, 'error': 'Could not fetch spot price'}

            chain = chain_data['chain']

            # Find CE strike (CALL above spot)
            ce_result, ce_all = self._rank_strikes(
                chain, 'call', desired_ce_premium, spot_price,
                above_spot=True, expiry=expiry_normalized, underlying=underlying,
            )

            # Find PE strike (PUT below spot)
            pe_result, pe_all = self._rank_strikes(
                chain, 'put', desired_pe_premium, spot_price,
                above_spot=False, expiry=expiry_normalized, underlying=underlying,
            )

            if not ce_result:
                return {
                    'success': False,
                    'error': f'No suitable CE strike found near premium ${desired_ce_premium}',
                    'spot_price': spot_price,
                }

            if not pe_result:
                return {
                    'success': False,
                    'error': f'No suitable PE strike found near premium ${desired_pe_premium}',
                    'spot_price': spot_price,
                }

            # Alternatives: top 5, excluding the best
            ce_alts = [s for s in ce_all if s['strike'] != ce_result['strike']][:5]
            pe_alts = [s for s in pe_all if s['strike'] != pe_result['strike']][:5]

            return {
                'success': True,
                'spot_price': spot_price,
                'ce': ce_result,
                'pe': pe_result,
                'alternatives': {'ce': ce_alts, 'pe': pe_alts},
            }

        except Exception as e:
            log.exception("Failed to preview strikes")
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # Public API: Validate Manual Selection
    # =========================================================================

    def validate_manual_selection(
        self,
        ce_symbol: str,
        pe_symbol: str,
        lots: int,
        expiry: str,
        underlying: str = 'BTC',
    ) -> Dict[str, Any]:
        """
        Validate a manually selected CE+PE pair before execution.

        Checks:
        1. Both symbols exist and have valid tickers
        2. CE is above spot, PE is below spot
        3. Sufficient bid liquidity for both
        4. Reasonable premium (not zero, not absurdly high)

        Returns:
            {
                valid: bool,
                ce: { strike, bid, ask, mid_price, delta, ... },
                pe: { strike, bid, ask, mid_price, delta, ... },
                warnings: [str],
                errors: [str],
                estimated_total_premium: float,
            }
        """
        try:
            expiry_normalized = normalize_expiry(expiry)
            spot_price = self.get_spot_price(underlying)
            warnings = []
            errors = []

            # Fetch tickers for both options
            ce_ticker = self.chain_service.get_option_ticker(ce_symbol)
            pe_ticker = self.chain_service.get_option_ticker(pe_symbol)

            if not ce_ticker:
                errors.append(f'Cannot fetch ticker for CE: {ce_symbol}')
            if not pe_ticker:
                errors.append(f'Cannot fetch ticker for PE: {pe_symbol}')

            if errors:
                return {'valid': False, 'errors': errors, 'warnings': warnings}

            # Extract data
            ce_data = self._extract_ticker_data(ce_ticker, 'CE', ce_symbol)
            pe_data = self._extract_ticker_data(pe_ticker, 'PE', pe_symbol)

            # Validate CE is above spot
            if ce_data['strike'] and ce_data['strike'] <= spot_price:
                warnings.append(
                    f"CE strike {ce_data['strike']} is not OTM (spot: {spot_price:.0f}). "
                    f"ITM calls have higher risk."
                )

            # Validate PE is below spot
            if pe_data['strike'] and pe_data['strike'] >= spot_price:
                warnings.append(
                    f"PE strike {pe_data['strike']} is not OTM (spot: {spot_price:.0f}). "
                    f"ITM puts have higher risk."
                )

            # Check bid liquidity
            if ce_data['bid_size'] < lots:
                warnings.append(
                    f"CE bid liquidity ({ce_data['bid_size']}) < lots ({lots}). "
                    f"Order may take longer or get partial fill."
                )
            if pe_data['bid_size'] < lots:
                warnings.append(
                    f"PE bid liquidity ({pe_data['bid_size']}) < lots ({lots}). "
                    f"Order may take longer or get partial fill."
                )

            # Check zero bid
            if ce_data['bid'] <= 0:
                errors.append(f"CE has zero bid — cannot sell at {ce_symbol}")
            if pe_data['bid'] <= 0:
                errors.append(f"PE has zero bid — cannot sell at {pe_symbol}")

            # Check spread
            for label, d in [('CE', ce_data), ('PE', pe_data)]:
                if d['bid'] > 0 and d['ask'] > 0:
                    spread_pct = (d['ask'] - d['bid']) / d['mid_price'] * 100 if d['mid_price'] > 0 else 0
                    if spread_pct > 30:
                        warnings.append(
                            f"{label} spread is very wide ({spread_pct:.0f}%). "
                            f"Consider a more liquid strike."
                        )

            is_valid = len(errors) == 0
            total_prem = (ce_data['mid_price'] + pe_data['mid_price']) * lots

            return {
                'valid': is_valid,
                'spot_price': spot_price,
                'ce': ce_data,
                'pe': pe_data,
                'warnings': warnings,
                'errors': errors,
                'estimated_total_premium': round(total_prem, 2),
            }

        except Exception as e:
            log.exception("Validation failed")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': [],
            }

    # =========================================================================
    # Build Symbol
    # =========================================================================

    def build_symbol(self, option_type: str, underlying: str, strike: float,
                     expiry_ddmmyyyy: str) -> str:
        """
        Build Delta Exchange symbol string.

        Format: C-BTC-99000-150226  /  P-BTC-96000-150226
        """
        prefix = 'C' if option_type == 'call' else 'P'
        strike_str = str(int(strike))
        suffix = expiry_to_symbol_suffix(expiry_ddmmyyyy)
        return f"{prefix}-{underlying}-{strike_str}-{suffix}"

    # =========================================================================
    # Internal: Robust Strike Ranking (Mode A)
    # =========================================================================

    def _rank_strikes(
        self,
        chain: List[Dict],
        option_type: str,
        desired_premium: float,
        spot_price: float,
        above_spot: bool,
        expiry: str,
        underlying: str,
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Rank all OTM strikes by quality score for auto-selection.

        Scoring (lower = better):
          score = premium_diff_weight * |premium - desired|
                + (penalty if zero bid)
                + (penalty if low liquidity)
                - (small bonus for further OTM on tie)

        Args:
            chain: List of {strike, call, put} dicts
            option_type: 'call' or 'put'
            desired_premium: Target premium per lot
            spot_price: Current BTC spot
            above_spot: True for CE, False for PE
            expiry: DDMMYYYY
            underlying: 'BTC'

        Returns:
            (best_strike_dict, all_ranked_list)
        """
        candidates = []

        for entry in chain:
            strike = entry.get('strike', 0)

            # Filter by OTM direction
            if above_spot and strike <= spot_price:
                continue
            if not above_spot and strike >= spot_price:
                continue

            option_data = entry.get(option_type)
            if not option_data:
                continue

            mark = option_data.get('mark_price', 0)
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            bid_size = option_data.get('bid_size', 0)

            # Use mark price as reference; fallback to mid
            if mark > 0:
                premium = mark
            elif bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            elif bid > 0:
                premium = bid
            else:
                continue  # Skip strikes with no price data

            mid_price = (bid + ask) / 2 if (bid > 0 and ask > 0) else premium

            # --- Scoring ---
            diff = abs(premium - desired_premium)

            # Base score: premium accuracy (normalized by desired)
            score = diff

            # Penalty: zero bid = can't sell
            if bid <= 0:
                score += 10000

            # Penalty: low liquidity
            if bid_size < 5 and bid_size > 0:
                score += 50
            elif bid_size == 0 and bid > 0:
                score += 100

            # Tiebreaker: further OTM is safer (small negative bonus)
            distance = abs(strike - spot_price)
            score -= distance * 0.0001  # tiny bonus for further OTM

            symbol = option_data.get('symbol', self.build_symbol(
                option_type, underlying, strike, expiry
            ))

            candidates.append({
                'strike': strike,
                'premium': round(premium, 2),
                'mid_price': round(mid_price, 2),
                'symbol': symbol,
                'bid': round(bid, 2),
                'ask': round(ask, 2),
                'mark_price': round(mark, 2),
                'bid_size': bid_size,
                'ask_size': option_data.get('ask_size', 0),
                'delta': round(option_data.get('delta', 0), 4),
                'gamma': round(option_data.get('gamma', 0), 6),
                'theta': round(option_data.get('theta', 0), 4),
                'iv': round(option_data.get('iv', 0), 4),
                'oi': option_data.get('oi', 0),
                'diff_from_desired': round(diff, 2),
                'score': round(score, 4),
                'distance_from_spot': round(distance, 0),
            })

        if not candidates:
            return None, []

        # Sort by score (lower = better)
        candidates.sort(key=lambda c: c['score'])

        return candidates[0], candidates

    # =========================================================================
    # Internal: Enrichment Helpers
    # =========================================================================

    def _enrich_option(
        self, option_data: Optional[Dict],
        option_type: str, underlying: str,
        strike: float, expiry: str,
    ) -> Optional[Dict]:
        """Enrich raw option data with mid_price and symbol."""
        if not option_data:
            return None

        bid = option_data.get('bid', 0)
        ask = option_data.get('ask', 0)
        mark = option_data.get('mark_price', 0)
        mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else mark

        return {
            'symbol': option_data.get('symbol', self.build_symbol(
                option_type, underlying, strike, expiry
            )),
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'mark_price': round(mark, 2),
            'mid_price': round(mid, 2),
            'bid_size': option_data.get('bid_size', 0),
            'ask_size': option_data.get('ask_size', 0),
            'delta': round(option_data.get('delta', 0), 4),
            'gamma': round(option_data.get('gamma', 0), 6),
            'theta': round(option_data.get('theta', 0), 4),
            'vega': round(option_data.get('vega', 0), 4),
            'iv': round(option_data.get('iv', 0), 4),
            'oi': option_data.get('oi', 0),
        }

    def _get_moneyness(self, strike: float, spot: float, option_type: str) -> str:
        """Determine ITM/ATM/OTM."""
        pct = abs(strike - spot) / spot if spot > 0 else 0
        if pct < 0.005:
            return 'ATM'
        if option_type == 'call':
            return 'ITM' if strike < spot else 'OTM'
        else:
            return 'ITM' if strike > spot else 'OTM'

    def _extract_ticker_data(
        self, ticker: Dict, label: str, symbol: str,
    ) -> Dict:
        """Extract normalized data from a raw option ticker."""
        # Handle different ticker formats
        quotes = ticker.get('quotes', {})
        if not quotes and 'raw' in ticker:
            quotes = ticker.get('raw', {}).get('quotes', {})

        bid = float(quotes.get('best_bid') or ticker.get('best_bid') or 0)
        ask = float(quotes.get('best_ask') or ticker.get('best_ask') or 0)
        bid_size = float(quotes.get('best_bid_size') or ticker.get('bid_size') or 0)
        ask_size = float(quotes.get('best_ask_size') or ticker.get('ask_size') or 0)
        mark = float(ticker.get('mark_price') or 0)
        mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else mark

        # Parse strike from symbol
        strike = 0
        try:
            parts = symbol.split('-')
            if len(parts) >= 3:
                strike = float(parts[2])
        except (ValueError, IndexError):
            pass

        greeks = ticker.get('greeks', {})
        if not greeks and 'raw' in ticker:
            greeks = ticker.get('raw', {}).get('greeks', {})

        return {
            'symbol': symbol,
            'strike': strike,
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'mid_price': round(mid, 2),
            'mark_price': round(mark, 2),
            'bid_size': bid_size,
            'ask_size': ask_size,
            'delta': round(float(greeks.get('delta', 0)), 4),
            'iv': round(float(greeks.get('iv', 0) or ticker.get('iv', 0)), 4),
            'oi': ticker.get('oi', 0),
        }

    # =========================================================================
    # Utility
    # =========================================================================

    def check_liquidity(
        self,
        symbol: str,
        lots_needed: int,
        underlying: str = 'BTC',
    ) -> Dict[str, Any]:
        """
        Section 15.6: Before selling at a strike, check bid liquidity.
        """
        try:
            ticker = self.chain_service.get_option_ticker(symbol)
            if not ticker:
                return {
                    'sufficient': False,
                    'bid_size': 0,
                    'lots_needed': lots_needed,
                    'warning': f'Cannot fetch ticker for {symbol}',
                }

            bid_size = ticker.get('bid_size', 0)
            sufficient = bid_size >= lots_needed

            return {
                'sufficient': sufficient,
                'bid_size': bid_size,
                'lots_needed': lots_needed,
                'warning': (
                    f'Low liquidity: bid_size={bid_size} < lots_needed={lots_needed}. '
                    f'Consider splitting order or choosing a different strike.'
                ) if not sufficient else None,
            }

        except Exception as e:
            log.error(f"Liquidity check failed for {symbol}: {e}")
            return {
                'sufficient': False,
                'bid_size': 0,
                'lots_needed': lots_needed,
                'warning': f'Liquidity check error: {e}',
            }

    def calculate_total_premium(
        self,
        ce_premium: float,
        ce_lots: int,
        pe_premium: float,
        pe_lots: int,
    ) -> Dict[str, float]:
        """Calculate total premium collected at entry (in USD).
        Premiums are per-BTC, 1 lot = 0.001 BTC."""
        from .mmm_constants import LOT_SIZE_BTC
        ce_total = ce_premium * ce_lots * LOT_SIZE_BTC
        pe_total = pe_premium * pe_lots * LOT_SIZE_BTC
        return {
            'ce_premium_total': ce_total,
            'pe_premium_total': pe_total,
            'total': ce_total + pe_total,
        }

    def calculate_lots_with_buffer(
        self,
        base_lots: int,
        buffer_pct: float = 0.05,
    ) -> int:
        """Section 14.1: Premium buffer — add extra lots for slippage protection."""
        return math.ceil(base_lots * (1 + buffer_pct))


# =============================================================================
# Singleton
# =============================================================================

_initializer_instance = None


def get_initializer(chain_service=None) -> MMMInitializer:
    """Get singleton initializer instance."""
    global _initializer_instance
    if _initializer_instance is None:
        _initializer_instance = MMMInitializer(chain_service)
    return _initializer_instance
