"""
Integrity Checker
==================
Verifies that collected parquet files are complete and well-formed.

Checks:
  1. File exists and is readable
  2. Row count matches the SQLite index
  3. No gaps > 5 minutes in the 1-min candle timeline
  4. All required strikes have at least some data
  5. Close prices are within plausible range (non-zero, non-infinite)
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

from .store import DataStore
from .chain_index import ChainIndex

log = logging.getLogger("backtesting.integrity_check")


class IntegrityIssue:
    """Represents a single integrity problem found during a check."""

    def __init__(self, expiry_date: str, underlying: str, severity: str, issue: str):
        self.expiry_date = expiry_date
        self.underlying  = underlying
        self.severity    = severity  # "ERROR" | "WARNING" | "INFO"
        self.issue       = issue

    def __repr__(self):
        return f"[{self.severity}] {self.expiry_date} {self.underlying}: {self.issue}"


def check_expiry(
    expiry_date: str,
    underlying: str = "BTC",
    store: Optional[DataStore] = None,
    max_gap_minutes: int = 5,
) -> List[IntegrityIssue]:
    """
    Run integrity checks on one collected expiry.

    Args:
        expiry_date:     "DD-MM-YYYY"
        underlying:      "BTC" or "ETH"
        store:           DataStore instance
        max_gap_minutes: Maximum acceptable gap in candle timeline (minutes)

    Returns:
        List of IntegrityIssue objects. Empty list = clean.
    """
    if store is None:
        store = DataStore()

    issues = []

    # ── Check 1: File exists ──────────────────────────────────────────────────
    if not store.exists(expiry_date, underlying):
        issues.append(IntegrityIssue(
            expiry_date, underlying, "ERROR",
            "Parquet file does not exist"
        ))
        return issues  # Can't check further

    # ── Check 2: File is readable and has rows ────────────────────────────────
    try:
        df = store.read_options_data(expiry_date, underlying)
    except Exception as e:
        issues.append(IntegrityIssue(
            expiry_date, underlying, "ERROR",
            f"Failed to read parquet: {e}"
        ))
        return issues

    if df.empty:
        issues.append(IntegrityIssue(
            expiry_date, underlying, "ERROR",
            "Parquet file is empty"
        ))
        return issues

    row_count = len(df)
    log.debug(f"Loaded {row_count} rows for {expiry_date} {underlying}")

    # ── Check 3: Row count vs index ───────────────────────────────────────────
    idx = ChainIndex()
    indexed_count = idx.get_row_count(expiry_date, underlying)
    if indexed_count > 0 and abs(row_count - indexed_count) > 100:
        issues.append(IntegrityIssue(
            expiry_date, underlying, "WARNING",
            f"Row count mismatch: parquet={row_count}, index={indexed_count}"
        ))

    # ── Check 4: Timestamp gaps ───────────────────────────────────────────────
    timestamps = sorted(df["timestamp"].unique().tolist())
    if len(timestamps) > 1:
        # Timestamps are in Unix ms — convert to minutes
        ts_minutes = [t // 60000 for t in timestamps]  # ms → minutes
        gaps = [
            (ts_minutes[i+1] - ts_minutes[i])
            for i in range(len(ts_minutes) - 1)
            if ts_minutes[i+1] - ts_minutes[i] > max_gap_minutes
        ]
        if gaps:
            issues.append(IntegrityIssue(
                expiry_date, underlying, "WARNING",
                f"Found {len(gaps)} candle gaps > {max_gap_minutes}min "
                f"(max gap: {max(gaps)}min)"
            ))

    # ── Check 5: Price sanity ─────────────────────────────────────────────────
    null_close = df["close"].isna().sum()
    if null_close > 0:
        issues.append(IntegrityIssue(
            expiry_date, underlying, "WARNING",
            f"{null_close} rows have null close price"
        ))

    zero_close = (df["close"] == 0).sum()
    if zero_close > row_count * 0.05:  # More than 5% zeros is suspicious
        issues.append(IntegrityIssue(
            expiry_date, underlying, "WARNING",
            f"{zero_close} rows ({zero_close/row_count:.1%}) have zero close price"
        ))

    # ── Check 6: Strike coverage ──────────────────────────────────────────────
    strikes = df["strike"].unique()
    ce_strikes = df[df["option_type"] == "CE"]["strike"].unique()
    pe_strikes = df[df["option_type"] == "PE"]["strike"].unique()

    if len(ce_strikes) < 5 or len(pe_strikes) < 5:
        issues.append(IntegrityIssue(
            expiry_date, underlying, "WARNING",
            f"Very few strikes: CE={len(ce_strikes)}, PE={len(pe_strikes)}"
        ))

    # If clean, add info record
    if not any(i.severity == "ERROR" for i in issues):
        log.info(
            f"Integrity OK: {expiry_date} {underlying} — "
            f"{row_count} rows, {len(strikes)} strikes, {len(timestamps)} timestamps"
        )

    return issues


def check_date_range(
    start_date: str,
    end_date: str,
    underlying: str = "BTC",
    store: Optional[DataStore] = None,
) -> Dict:
    """
    Run integrity checks across an entire date range.

    Returns:
        {
          "checked": N,
          "clean": N,
          "with_warnings": N,
          "with_errors": N,
          "issues": [list of IntegrityIssue]
        }
    """
    from ..data_collector.expiry_resolver import get_expiry_range

    if store is None:
        store = DataStore()

    expiries = get_expiry_range(start_date, end_date)
    idx = ChainIndex()

    all_issues = []
    clean = 0
    with_warnings = 0
    with_errors = 0

    for expiry_date in expiries:
        if not idx.is_collected(expiry_date, underlying):
            all_issues.append(IntegrityIssue(
                expiry_date, underlying, "INFO",
                "Not yet collected"
            ))
            continue

        issues = check_expiry(expiry_date, underlying, store)
        all_issues.extend(issues)

        if any(i.severity == "ERROR" for i in issues):
            with_errors += 1
        elif any(i.severity == "WARNING" for i in issues):
            with_warnings += 1
        else:
            clean += 1

    return {
        "checked":       len(expiries),
        "clean":         clean,
        "with_warnings": with_warnings,
        "with_errors":   with_errors,
        "issues":        all_issues,
    }
