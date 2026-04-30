"""
MMM Constants

Shared constants for the MMM algorithm.
"""

from decimal import Decimal

# Delta Exchange BTC Options: 1 BTC = 1000 lots, so 1 lot = 0.001 BTC
# Premiums are quoted in USD per BTC. To get USD value for N lots:
#   usd_value = premium_per_btc * N * LOT_SIZE_BTC
LOT_SIZE_BTC = 0.001


def _D(x) -> Decimal:
    """Canonical Decimal precision helper — single source of truth for all MMM modules."""
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal('0')


_LOT = _D(LOT_SIZE_BTC)


def strike_key(strike: float) -> str:
    """
    Robust v2 Fix #13: Canonical strike key for trigger_snapshot lookups.

    Converts any strike representation to a consistent string key.
    Handles integers, floats, string inputs. Always returns str(int(round(strike))).

    This prevents key mismatches where one code path uses str(int(23100.5)) = '23100'
    and another uses str(23100.5) = '23100.5'.

    Usage:
        from .mmm_constants import strike_key
        snapshot[strike_key(active_strike)] = premium
    """
    try:
        return str(int(round(float(strike))))
    except (ValueError, TypeError, OverflowError):
        return str(strike)
