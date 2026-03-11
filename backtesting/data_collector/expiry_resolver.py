"""
Expiry Resolver
================
Generates the list of historical 0DTE BTC/ETH expiry dates for Delta Exchange India.

Delta India 0DTE options expire daily at 08:00 UTC (13:30 IST).
"""

from datetime import datetime, timedelta, timezone
from typing import List


def get_past_expiries(
    days_back: int = 30,
    underlying: str = "BTC",
    reference_date: datetime = None,
) -> List[str]:
    """
    Generate list of past 0DTE expiry dates in "DD-MM-YYYY" format.

    Args:
        days_back:       How many calendar days to look back from reference_date
        underlying:      "BTC" or "ETH" — both have daily 0DTE on Delta India
        reference_date:  Date to count back from (default: today UTC)

    Returns:
        List of date strings in "DD-MM-YYYY" format, newest first.

    Example:
        get_past_expiries(5) →  ["10-03-2026", "09-03-2026", "08-03-2026", ...]
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    expiries = []
    # Start from yesterday (today's session is still live)
    for i in range(1, days_back + 1):
        date = reference_date - timedelta(days=i)
        expiries.append(date.strftime("%d-%m-%Y"))

    return expiries


def get_expiry_range(
    start_date: str,
    end_date: str,
) -> List[str]:
    """
    Generate expiry dates between start_date and end_date (inclusive).

    Args:
        start_date: "DD-MM-YYYY"
        end_date:   "DD-MM-YYYY"

    Returns:
        List of date strings in "DD-MM-YYYY" format, oldest first.
    """
    start = datetime.strptime(start_date, "%d-%m-%Y")
    end   = datetime.strptime(end_date,   "%d-%m-%Y")

    if start > end:
        raise ValueError(f"start_date {start_date} is after end_date {end_date}")

    expiries = []
    current = start
    while current <= end:
        expiries.append(current.strftime("%d-%m-%Y"))
        current += timedelta(days=1)

    return expiries


def expiry_to_session_window(expiry_date: str) -> tuple:
    """
    Return Unix timestamps (seconds) for the start and end of a 0DTE session.

    Delta India BTC 0DTE:
      - Session starts: 08:00 UTC on expiry day (previous day's evening IST)
      - Session ends:   08:00 UTC on expiry day (i.e., 13:30 IST on expiry day)

    Args:
        expiry_date: "DD-MM-YYYY"

    Returns:
        (start_ts, end_ts) as Unix timestamps (seconds, UTC)
    """
    expiry_dt = datetime.strptime(expiry_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)

    # The 0DTE session covers the 24 hours BEFORE the 08:00 UTC expiry
    end_ts   = int(expiry_dt.replace(hour=8, minute=0, second=0, microsecond=0).timestamp())
    start_ts = end_ts - (24 * 3600)  # Go back 24 hours

    return start_ts, end_ts


def expiry_date_to_datetime(expiry_date: str) -> datetime:
    """Parse "DD-MM-YYYY" to a UTC-aware datetime at 08:00 UTC."""
    dt = datetime.strptime(expiry_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)
    return dt.replace(hour=8, minute=0, second=0, microsecond=0)
