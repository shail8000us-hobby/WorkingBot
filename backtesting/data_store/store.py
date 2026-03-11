"""
Data Store
===========
Reads and writes parquet files for historical options data.

Layout:
  backtesting/historical_data/
    btc/
      10-03-2026.parquet     ← options candle data
      10-03-2026_perp.parquet ← BTC perp candles
    eth/
      ...
    index.db                 ← SQLite collection index
"""

import logging
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional, List

from .schema import (
    OPTIONS_SCHEMA, PERP_SCHEMA,
    validate_options_df, validate_perp_df,
    rows_to_df, perp_rows_to_df,
)

log = logging.getLogger("backtesting.data_store")

# Default data directory: backtesting/historical_data/
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "historical_data"


class DataStore:
    """
    Parquet-based storage for historical options and perp data.

    Usage:
        store = DataStore()
        store.write_options_data(rows, "10-03-2026", "BTC")
        df = store.read_options_data("10-03-2026", "BTC")
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        log.debug(f"DataStore initialized at: {self.data_dir}")

    # ── Internal path helpers ─────────────────────────────────────────────────

    def _options_path(self, expiry_date: str, underlying: str) -> Path:
        """Return path for options candle parquet file."""
        subdir = self.data_dir / underlying.lower()
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{expiry_date}.parquet"
        return subdir / filename

    def _perp_path(self, expiry_date: str, underlying: str) -> Path:
        """Return path for perp candle parquet file."""
        subdir = self.data_dir / underlying.lower()
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{expiry_date}_perp.parquet"
        return subdir / filename

    # ── Write methods ─────────────────────────────────────────────────────────

    def write_options_data(
        self,
        rows: list,
        expiry_date: str,
        underlying: str = "BTC",
    ) -> Path:
        """
        Validate and write options candle data to parquet.

        Args:
            rows:        List of dicts (from candle_collector.fetch_all_candles_for_chain)
            expiry_date: "DD-MM-YYYY"
            underlying:  "BTC" or "ETH"

        Returns:
            Path to the written parquet file.
        """
        df = rows_to_df(rows)
        path = self._options_path(expiry_date, underlying)
        table = pa.Table.from_pandas(df, schema=OPTIONS_SCHEMA, safe=False)
        pq.write_table(table, path, compression="snappy")
        log.info(f"Wrote {len(df)} rows → {path}")
        return path

    def write_perp_data(
        self,
        rows: list,
        expiry_date: str,
        underlying: str = "BTC",
    ) -> Optional[Path]:
        """Write perp candle data to parquet."""
        if not rows:
            log.warning(f"No perp data to write for {expiry_date} {underlying}")
            return None

        df = perp_rows_to_df(rows, expiry_date, underlying)
        path = self._perp_path(expiry_date, underlying)
        table = pa.Table.from_pandas(df, schema=PERP_SCHEMA, safe=False)
        pq.write_table(table, path, compression="snappy")
        log.info(f"Wrote {len(df)} perp rows → {path}")
        return path

    # ── Read methods ──────────────────────────────────────────────────────────

    def read_options_data(
        self,
        expiry_date: str,
        underlying: str = "BTC",
        strikes: Optional[List[float]] = None,
        option_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Read options candle data from parquet.

        Args:
            expiry_date:  "DD-MM-YYYY"
            underlying:   "BTC" or "ETH"
            strikes:      Optional filter — only return these strikes
            option_types: Optional filter — ["CE"], ["PE"], or ["CE", "PE"]

        Returns:
            DataFrame with OPTIONS_SCHEMA columns, sorted by (strike, option_type, timestamp).

        Raises:
            FileNotFoundError if the parquet file does not exist.
        """
        path = self._options_path(expiry_date, underlying)
        if not path.exists():
            raise FileNotFoundError(
                f"No options data for {expiry_date} {underlying}. "
                f"Run: python backtesting/scripts/collect_data.py --date {expiry_date}"
            )

        df = pq.read_table(path).to_pandas()

        # Apply filters
        if strikes is not None:
            df = df[df["strike"].isin(strikes)]
        if option_types is not None:
            df = df[df["option_type"].isin(option_types)]

        log.debug(f"Read {len(df)} rows from {path}")
        return df

    def read_perp_data(
        self,
        expiry_date: str,
        underlying: str = "BTC",
    ) -> pd.DataFrame:
        """
        Read perp futures candle data.

        Returns empty DataFrame if no perp data exists (perp hedge is optional).
        """
        path = self._perp_path(expiry_date, underlying)
        if not path.exists():
            log.warning(f"No perp data for {expiry_date} {underlying}")
            return pd.DataFrame(columns=[f.name for f in PERP_SCHEMA])

        df = pq.read_table(path).to_pandas()
        log.debug(f"Read {len(df)} perp rows from {path}")
        return df

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_all_strikes(self, expiry_date: str, underlying: str = "BTC") -> List[float]:
        """Return sorted list of all strike prices available for an expiry."""
        df = self.read_options_data(expiry_date, underlying)
        return sorted(df["strike"].unique().tolist())

    def get_timestamps(self, expiry_date: str, underlying: str = "BTC") -> List[int]:
        """Return sorted list of unique Unix timestamps (ms) for an expiry."""
        df = self.read_options_data(expiry_date, underlying)
        return sorted(df["timestamp"].unique().tolist())

    def exists(self, expiry_date: str, underlying: str = "BTC") -> bool:
        """Return True if options data exists for the given expiry."""
        return self._options_path(expiry_date, underlying).exists()

    def file_size_mb(self, expiry_date: str, underlying: str = "BTC") -> float:
        """Return size of the parquet file in MB."""
        path = self._options_path(expiry_date, underlying)
        if not path.exists():
            return 0.0
        return path.stat().st_size / (1024 * 1024)
