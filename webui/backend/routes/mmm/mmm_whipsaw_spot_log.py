"""
mmm_whipsaw_spot_log — rolling price sample log for SmartWhipsawEngine.

Writes to _smart_ws_series (list, capped at MAX_SERIES_LEN).
Never reads or writes any _whipsaw_* key.
Migration-safe: missing key → empty list.
"""

from datetime import datetime, timedelta, timezone

MAX_SERIES_LEN = 240  # ~20 h at 5-min heartbeat


def append_sample(
    session: dict,
    spot: float,
    ce: float,
    pe: float,
    iv: float = 0.0,
) -> None:
    """Append one price sample to the rolling log. Evicts oldest if at cap."""
    series = session.setdefault('_smart_ws_series', [])
    series.append({
        'ts': datetime.now(timezone.utc).isoformat(),
        'spot': spot,
        'ce': ce,
        'pe': pe,
        'iv': iv,
    })
    if len(series) > MAX_SERIES_LEN:
        del series[0]


def get_series(session: dict, window_mins: float = 30.0) -> list:
    """Return samples within the last window_mins minutes (oldest first)."""
    series = session.get('_smart_ws_series', [])
    if not series:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_mins)
    result = []
    for s in series:
        try:
            ts = datetime.fromisoformat(s['ts'])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                result.append(s)
        except (ValueError, KeyError):
            continue
    return result


def extract_spots(series: list) -> list:
    return [s['spot'] for s in series if 'spot' in s]


def extract_premiums(series: list):
    """Returns (ces, pes) lists in the same order as series."""
    ces = [s['ce'] for s in series if 'ce' in s and 'pe' in s]
    pes = [s['pe'] for s in series if 'ce' in s and 'pe' in s]
    return ces, pes
