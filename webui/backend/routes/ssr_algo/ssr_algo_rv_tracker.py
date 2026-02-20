"""
SSR ALGO Realized vs Implied Volatility Tracker

Tracks realized volatility (actual price movement) vs implied volatility:
- rv_iv_ratio < 0.7: IV is expensive → GREAT for selling premium
- rv_iv_ratio > 1.2: Realized exceeds implied → DANGER for short gamma

Created: February 20, 2026
Phase 10 of SSR Algo Development Plan
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

log = logging.getLogger('ssr_algo_rv_tracker')


class SSRRVTracker:
    """
    Tracks realized volatility vs implied volatility for SSR Algo sessions.

    Stores rolling price history and calculates RV using log returns.
    Compares to ATM IV from options chain data.
    """

    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        # Per-underlying price history: {'BTC': deque([(timestamp, price), ...])}
        self._price_history: Dict[str, deque] = {}
        # Per-underlying RV/IV snapshots: {'BTC': deque([{timestamp, rv_5d, rv_20d, atm_iv, ratio}, ...])}
        self._rv_iv_history: Dict[str, deque] = {}

    def record_price(self, underlying: str, price: float, timestamp: datetime = None):
        """Record a price observation for RV calculation."""
        if underlying not in self._price_history:
            self._price_history[underlying] = deque(maxlen=self.max_history)
        ts = timestamp or datetime.utcnow()
        self._price_history[underlying].append((ts, price))

    def calculate_realized_vol(self, underlying: str, window_days: int = 5) -> Optional[float]:
        """
        Calculate annualized realized volatility from price history.

        Uses standard deviation of log returns over the specified window.
        Prices are sampled at ~5-minute intervals in the monitor loop,
        so we use the number of data points rather than strict daily windows.

        Args:
            underlying: BTC or ETH
            window_days: Lookback window in days (5 or 20)

        Returns:
            Annualized realized volatility as a decimal (e.g., 0.65 = 65%)
            or None if insufficient data
        """
        history = self._price_history.get(underlying)
        if not history or len(history) < 10:
            return None

        # Estimate points per day: monitor runs every 5s, RV recorded every ~5 min
        # ~288 data points per day at 5-min intervals
        # But we record on every monitor cycle, so estimate from actual timestamps
        prices = [p for _, p in history]

        # Use last N points proportional to window
        # If we have 5-min data, 5 days ≈ 1440 points, 20 days ≈ 5760 points
        # With 5s monitor cycle recording every ~60 cycles = every 5 min
        points_needed = min(len(prices), window_days * 288)
        if points_needed < 5:
            return None

        recent_prices = prices[-points_needed:]

        # Calculate log returns
        log_returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i - 1] > 0 and recent_prices[i] > 0:
                log_returns.append(math.log(recent_prices[i] / recent_prices[i - 1]))

        if len(log_returns) < 5:
            return None

        # Standard deviation of log returns
        mean_return = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
        std_dev = math.sqrt(variance)

        # Annualize: multiply by sqrt(periods per year)
        # For 5-min intervals: 365 * 288 = 105,120 periods/year
        periods_per_year = 365 * 288
        annualized_rv = std_dev * math.sqrt(periods_per_year)

        return round(annualized_rv, 4)

    def get_atm_iv(self, underlying: str, expiry: str) -> Optional[float]:
        """
        Get ATM implied volatility from options chain data.

        Returns:
            ATM IV as a decimal (e.g., 0.75 = 75%) or None
        """
        try:
            from webui.backend.options_chain.chain_service import OptionsChainService
            from .ssr_algo_engine import normalize_expiry_format

            chain_service = OptionsChainService()
            normalized = normalize_expiry_format(expiry)
            chain_data = chain_service.get_chain_data(underlying, normalized)
            chain = chain_data.get('chain', [])

            if not chain:
                return None

            # Find ATM strike (closest to spot)
            spot = chain_data.get('spot_price', 0)
            if not spot:
                return None

            atm = min(chain, key=lambda s: abs(s.get('strike', 0) - spot))
            call_iv = atm.get('call', {}).get('implied_volatility', 0) or 0
            put_iv = atm.get('put', {}).get('implied_volatility', 0) or 0

            # Average call and put IV
            if call_iv and put_iv:
                return round((call_iv + put_iv) / 2, 4)
            return round(call_iv or put_iv, 4) or None

        except Exception as e:
            log.debug(f"Could not get ATM IV for {underlying}: {e}")
            return None

    def get_rv_iv_snapshot(self, underlying: str, expiry: str) -> Dict:
        """
        Get a complete RV/IV analysis snapshot.

        Returns:
            {
                'rv_5d': float,     # 5-day realized vol (annualized)
                'rv_20d': float,    # 20-day realized vol (annualized)
                'atm_iv': float,    # Current ATM implied vol
                'rv_iv_ratio': float,  # rv_20d / atm_iv
                'signal': str,      # 'SELL_PREMIUM' | 'NEUTRAL' | 'DANGER'
                'signal_strength': float,  # 0-1 confidence
                'message': str,
                'data_points': int,
                'timestamp': str
            }
        """
        rv_5d = self.calculate_realized_vol(underlying, window_days=5)
        rv_20d = self.calculate_realized_vol(underlying, window_days=20)
        atm_iv = self.get_atm_iv(underlying, expiry)

        data_points = len(self._price_history.get(underlying, []))

        result = {
            'rv_5d': rv_5d,
            'rv_20d': rv_20d,
            'atm_iv': atm_iv,
            'rv_iv_ratio': None,
            'signal': 'INSUFFICIENT_DATA',
            'signal_strength': 0.0,
            'message': 'Insufficient data for RV/IV analysis',
            'data_points': data_points,
            'timestamp': datetime.utcnow().isoformat()
        }

        if rv_20d is not None and atm_iv and atm_iv > 0:
            ratio = rv_20d / atm_iv
            result['rv_iv_ratio'] = round(ratio, 3)

            if ratio < 0.7:
                result['signal'] = 'SELL_PREMIUM'
                result['signal_strength'] = min(1.0, (0.7 - ratio) / 0.3)
                result['message'] = f'RV/IV ratio {ratio:.2f} — IV is expensive, great for selling premium'
            elif ratio > 1.2:
                result['signal'] = 'DANGER'
                result['signal_strength'] = min(1.0, (ratio - 1.2) / 0.5)
                result['message'] = f'RV/IV ratio {ratio:.2f} — Realized exceeds implied, danger for short gamma'
            else:
                result['signal'] = 'NEUTRAL'
                result['signal_strength'] = 0.5
                result['message'] = f'RV/IV ratio {ratio:.2f} — RV and IV are balanced'

        # Store snapshot
        if underlying not in self._rv_iv_history:
            self._rv_iv_history[underlying] = deque(maxlen=30)
        self._rv_iv_history[underlying].append(result)

        return result

    def get_rv_iv_history(self, underlying: str) -> List[Dict]:
        """Get last 30 RV/IV snapshots for dashboard chart."""
        return list(self._rv_iv_history.get(underlying, []))


# Singleton
_rv_tracker = None

def get_rv_tracker() -> SSRRVTracker:
    """Get singleton SSRRVTracker instance."""
    global _rv_tracker
    if _rv_tracker is None:
        _rv_tracker = SSRRVTracker()
    return _rv_tracker
