"""
Parquet Schema Definition
==========================
Defines and validates the column schema for options candle data stored as parquet.

Two schemas:
  - OPTIONS_SCHEMA:  Per-candle-per-strike rows (the main data)
  - PERP_SCHEMA:     BTC/ETH perpetual futures candles (for spot + delta hedge)
"""

import pyarrow as pa
import pandas as pd
import numpy as np
from typing import List, Dict

# ── Options candle schema ─────────────────────────────────────────────────────
OPTIONS_SCHEMA = pa.schema([
    # Temporal
    ("timestamp",    pa.int64()),      # Unix ms (candle open time)
    ("expiry_date",  pa.string()),     # "DD-MM-YYYY"
    # Identity
    ("underlying",   pa.string()),     # "BTC" | "ETH"
    ("symbol",       pa.string()),     # Full Delta symbol, e.g. "C-BTC-95000-260310"
    ("strike",       pa.float64()),    # Strike price in USD
    ("option_type",  pa.string()),     # "CE" | "PE"
    # Candle OHLCV (mark price, from /history/candles)
    ("open",         pa.float64()),
    ("high",         pa.float64()),
    ("low",          pa.float64()),
    ("close",        pa.float64()),    # This is the mark price used for P&L
    ("volume",       pa.float64()),
    # Chain snapshot (static for the expiry — from /tickers)
    ("best_bid",     pa.float64()),    # Best bid at chain snapshot time
    ("best_ask",     pa.float64()),    # Best ask at chain snapshot time
    ("oi",           pa.float64()),    # Open interest (lots)
    ("delta",        pa.float64()),    # Options delta (-1 to 1)
    ("gamma",        pa.float64()),    # Gamma
    ("theta",        pa.float64()),    # Theta (daily)
    ("vega",         pa.float64()),    # Vega
    ("iv",           pa.float64()),    # Implied volatility (annualized %)
])

# ── Perpetual futures candle schema ───────────────────────────────────────────
PERP_SCHEMA = pa.schema([
    ("timestamp",    pa.int64()),
    ("expiry_date",  pa.string()),
    ("underlying",   pa.string()),
    ("symbol",       pa.string()),     # "BTCUSD" | "ETHUSD"
    ("open",         pa.float64()),
    ("high",         pa.float64()),
    ("low",          pa.float64()),
    ("close",        pa.float64()),    # BTC spot price proxy
    ("volume",       pa.float64()),
])


# ── Columns present in the schema ─────────────────────────────────────────────
OPTIONS_COLUMNS = [f.name for f in OPTIONS_SCHEMA]
PERP_COLUMNS    = [f.name for f in PERP_SCHEMA]


def validate_options_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and coerce a DataFrame to the OPTIONS_SCHEMA.

    - Adds any missing columns with None/NaN
    - Casts types to match schema
    - Drops rows where timestamp or close is null

    Returns the validated DataFrame.
    """
    # Ensure all columns exist
    for field in OPTIONS_SCHEMA:
        if field.name not in df.columns:
            df[field.name] = None

    # Select only schema columns in order
    df = df[OPTIONS_COLUMNS].copy()

    # Type coercion
    df["timestamp"]   = pd.to_numeric(df["timestamp"],   errors="coerce").astype("Int64")
    df["strike"]      = pd.to_numeric(df["strike"],      errors="coerce")
    df["open"]        = pd.to_numeric(df["open"],        errors="coerce")
    df["high"]        = pd.to_numeric(df["high"],        errors="coerce")
    df["low"]         = pd.to_numeric(df["low"],         errors="coerce")
    df["close"]       = pd.to_numeric(df["close"],       errors="coerce")
    df["volume"]      = pd.to_numeric(df["volume"],      errors="coerce")
    df["best_bid"]    = pd.to_numeric(df["best_bid"],    errors="coerce")
    df["best_ask"]    = pd.to_numeric(df["best_ask"],    errors="coerce")
    df["oi"]          = pd.to_numeric(df["oi"],          errors="coerce")
    df["delta"]       = pd.to_numeric(df["delta"],       errors="coerce")
    df["gamma"]       = pd.to_numeric(df["gamma"],       errors="coerce")
    df["theta"]       = pd.to_numeric(df["theta"],       errors="coerce")
    df["vega"]        = pd.to_numeric(df["vega"],        errors="coerce")
    df["iv"]          = pd.to_numeric(df["iv"],          errors="coerce")

    # String columns
    for col in ("underlying", "symbol", "option_type", "expiry_date"):
        df[col] = df[col].astype(str)

    # Drop rows without a timestamp or close price
    initial_len = len(df)
    df = df.dropna(subset=["timestamp", "close"])
    dropped = initial_len - len(df)
    if dropped > 0:
        import logging
        logging.getLogger("backtesting.schema").warning(
            f"Dropped {dropped} rows with null timestamp/close"
        )

    # Sort by (strike, option_type, timestamp)
    df = df.sort_values(["strike", "option_type", "timestamp"]).reset_index(drop=True)
    return df


def validate_perp_df(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and coerce a DataFrame to the PERP_SCHEMA."""
    for field in PERP_SCHEMA:
        if field.name not in df.columns:
            df[field.name] = None

    df = df[PERP_COLUMNS].copy()

    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce").astype("Int64")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("underlying", "symbol", "expiry_date"):
        df[col] = df[col].astype(str)

    df = df.dropna(subset=["timestamp", "close"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def rows_to_df(rows: List[Dict]) -> pd.DataFrame:
    """Convert a list of row dicts to a validated options DataFrame."""
    df = pd.DataFrame(rows)
    return validate_options_df(df)


def perp_rows_to_df(rows: List[Dict], expiry_date: str, underlying: str) -> pd.DataFrame:
    """Convert a list of perp candle dicts to a validated perp DataFrame."""
    df = pd.DataFrame(rows)
    if "expiry_date" not in df.columns:
        df["expiry_date"] = expiry_date
    if "underlying" not in df.columns:
        df["underlying"] = underlying
    # The candle dicts from candle_collector have 'time' not 'timestamp'
    if "time" in df.columns and "timestamp" not in df.columns:
        df["timestamp"] = df["time"]
    return validate_perp_df(df)
