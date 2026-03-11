"""
Simulated Options Chain View
=============================
Provides a window into the options chain at any timestamp during a backtest.

At a given timestamp T:
  - Mark price (close) comes from the 1-min candle at T
  - Bid/ask, Greeks, OI come from the chain snapshot (static per session)
  - Missing strikes return None (not an error — they may not have existed at that time)
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd

log = logging.getLogger("backtesting.sim_chain")

# Keys in the chain dict
PREMIUM_KEY = "close"     # mark price / settlement price
BID_KEY     = "best_bid"
ASK_KEY     = "best_ask"


class SimChain:
    """
    Provides an options chain view at any point in time during a backtest.

    Backed by a pre-loaded parquet DataFrame. Fast column queries via pandas groupby.

    Usage:
        chain = SimChain(df)
        premium = chain.get_premium(95000, "CE", ts_ms)
        bid     = chain.get_bid(95000, "PE", ts_ms)
        strikes = chain.scan_chain("CE", target_premium=150, ts_ms=ts_ms)
    """

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: Options candle DataFrame from DataStore.read_options_data()
        """
        if df.empty:
            raise ValueError("SimChain received empty DataFrame")

        self._df = df.copy()

        # Build index: timestamp → sub-DataFrame for fast lookup
        # Group by timestamp for O(1) chain snapshots at any minute
        self._by_ts: Dict[int, pd.DataFrame] = {}
        for ts, group in df.groupby("timestamp"):
            self._by_ts[int(ts)] = group.set_index(["strike", "option_type"])

        # Build chain snapshot lookup: (strike, option_type) → static dict
        self._snapshot: Dict[Tuple[float, str], Dict] = {}
        for _, row in df.drop_duplicates(subset=["strike", "option_type"]).iterrows():
            key = (float(row["strike"]), str(row["option_type"]))
            self._snapshot[key] = {
                "symbol":    row.get("symbol", ""),
                "best_bid":  row.get("best_bid"),
                "best_ask":  row.get("best_ask"),
                "oi":        row.get("oi"),
                "delta":     row.get("delta"),
                "gamma":     row.get("gamma"),
                "theta":     row.get("theta"),
                "vega":      row.get("vega"),
                "iv":        row.get("iv"),
            }

        # Available timestamps (sorted)
        self._timestamps_ms: List[int] = sorted(self._by_ts.keys())
        self._all_strikes = sorted(df["strike"].unique().tolist())

        log.info(
            f"SimChain: {len(self._snapshot)//2} strikes × 2 sides, "
            f"{len(self._timestamps_ms)} timestamps"
        )

    # ── Core lookup ───────────────────────────────────────────────────────────

    def _get_row(self, strike: float, option_type: str, ts_ms: int) -> Optional[pd.Series]:
        """Get the candle row for a strike at a given timestamp (None if not found)."""
        nearest_ts = self._nearest_ts(ts_ms)
        if nearest_ts is None:
            return None
        bucket = self._by_ts.get(nearest_ts)
        if bucket is None:
            return None
        try:
            return bucket.loc[(strike, option_type.upper())]
        except KeyError:
            return None

    def _nearest_ts(self, ts_ms: int) -> Optional[int]:
        """Return the closest available timestamp <= ts_ms."""
        if not self._timestamps_ms:
            return None
        # Binary search for the nearest timestamp
        import bisect
        idx = bisect.bisect_right(self._timestamps_ms, ts_ms) - 1
        if idx < 0:
            return None
        return self._timestamps_ms[idx]

    # ── Public API ────────────────────────────────────────────────────────────

    def get_premium(self, strike: float, option_type: str, ts_ms: int) -> Optional[float]:
        """
        Get the mark price (close price from candle) for a strike at ts_ms.

        Returns None if the strike has no data at this timestamp.
        """
        row = self._get_row(strike, option_type, ts_ms)
        if row is None:
            return None
        val = row.get(PREMIUM_KEY) if hasattr(row, 'get') else row[PREMIUM_KEY]
        return float(val) if val is not None and not pd.isna(val) else None

    def get_bid(self, strike: float, option_type: str, ts_ms: int = None) -> Optional[float]:
        """
        Get the best bid for a strike.

        Bid comes from the chain snapshot (static). If ts_ms is provided,
        the mark price / bid ratio is used to approximate intraday bid.
        """
        key = (float(strike), option_type.upper())
        snap = self._snapshot.get(key, {})
        bid = snap.get("best_bid")
        if bid and ts_ms:
            # Approximate intraday bid using spread ratio
            mark = self.get_premium(strike, option_type, ts_ms)
            snap_mark = snap.get("mark_price")
            if mark and snap_mark and snap_mark > 0:
                ratio = mark / snap_mark
                bid = bid * ratio
        return float(bid) if bid is not None else None

    def get_ask(self, strike: float, option_type: str, ts_ms: int = None) -> Optional[float]:
        """
        Get the best ask for a strike.

        Ask comes from the chain snapshot (static), approximated intraday if ts_ms provided.
        """
        key = (float(strike), option_type.upper())
        snap = self._snapshot.get(key, {})
        ask = snap.get("best_ask")
        if ask and ts_ms:
            mark = self.get_premium(strike, option_type, ts_ms)
            snap_mark = snap.get("mark_price")
            if mark and snap_mark and snap_mark > 0:
                ratio = mark / snap_mark
                ask = ask * ratio
        return float(ask) if ask is not None else None

    def get_greeks(self, strike: float, option_type: str) -> Dict:
        """Return the Greeks for a strike (from chain snapshot — static)."""
        key = (float(strike), option_type.upper())
        snap = self._snapshot.get(key, {})
        return {
            "delta": snap.get("delta"),
            "gamma": snap.get("gamma"),
            "theta": snap.get("theta"),
            "vega":  snap.get("vega"),
            "iv":    snap.get("iv"),
        }

    def get_oi(self, strike: float, option_type: str) -> Optional[float]:
        """Return open interest for a strike (from chain snapshot)."""
        key = (float(strike), option_type.upper())
        return self._snapshot.get(key, {}).get("oi")

    def get_symbol(self, strike: float, option_type: str) -> Optional[str]:
        """Return the Delta Exchange symbol for a strike."""
        key = (float(strike), option_type.upper())
        return self._snapshot.get(key, {}).get("symbol")

    def get_all_strikes(self) -> List[float]:
        """Return sorted list of all available strikes."""
        return self._all_strikes

    def get_chain_at(self, ts_ms: int) -> Dict:
        """
        Return a full chain snapshot at ts_ms as a dict:
        { (strike, option_type): {close, bid, ask, greeks, oi, ...} }

        This is the format expected by mmm_initializer.find_entry_strikes().
        """
        result = {}
        nearest_ts = self._nearest_ts(ts_ms)
        if nearest_ts is None:
            return result

        bucket = self._by_ts.get(nearest_ts, pd.DataFrame())
        for (strike, opt_type), row in bucket.iterrows():
            key = (float(strike), str(opt_type))
            snap = self._snapshot.get(key, {})
            result[key] = {
                "strike":      float(strike),
                "option_type": str(opt_type),
                "close":       self._safe_float(row.get("close")),
                "open":        self._safe_float(row.get("open")),
                "high":        self._safe_float(row.get("high")),
                "low":         self._safe_float(row.get("low")),
                "volume":      self._safe_float(row.get("volume")),
                "best_bid":    snap.get("best_bid"),
                "best_ask":    snap.get("best_ask"),
                "oi":          snap.get("oi"),
                "delta":       snap.get("delta"),
                "gamma":       snap.get("gamma"),
                "theta":       snap.get("theta"),
                "vega":        snap.get("vega"),
                "iv":          snap.get("iv"),
                "symbol":      snap.get("symbol", ""),
            }
        return result

    def scan_chain(
        self,
        option_type: str,
        target_premium: float,
        ts_ms: int,
        min_oi: float = 0,
    ) -> List[Tuple[float, float]]:
        """
        Find strikes closest to a target premium at ts_ms.

        Args:
            option_type:    "CE" or "PE"
            target_premium: Desired option premium (mark price)
            ts_ms:          Timestamp in milliseconds
            min_oi:         Minimum open interest to consider (liquidity filter)

        Returns:
            List of (strike, premium) tuples sorted by closeness to target_premium.
        """
        nearest_ts  = self._nearest_ts(ts_ms)
        if nearest_ts is None:
            return []

        bucket = self._by_ts.get(nearest_ts, pd.DataFrame())
        results = []

        for (strike, opt_type), row in bucket.iterrows():
            if opt_type.upper() != option_type.upper():
                continue
            premium = self._safe_float(row.get("close"))
            if premium is None or premium <= 0:
                continue
            oi = self._snapshot.get((float(strike), opt_type.upper()), {}).get("oi", 0)
            if min_oi and (oi is None or oi < min_oi):
                continue
            results.append((float(strike), premium))

        results.sort(key=lambda x: abs(x[1] - target_premium))
        return results

    def get_spot_at(self, ts_ms: int) -> Optional[float]:
        """
        Estimate BTC spot price at ts_ms.

        Uses the average of ATM call and put mark prices (rough proxy)
        when no perp data is available.
        """
        # Better: use the perp DataFrame if loaded
        if hasattr(self, "_perp_df") and self._perp_df is not None:
            nearest_ts = self._nearest_ts_perp(ts_ms)
            if nearest_ts:
                row = self._perp_df[self._perp_df["timestamp"] == nearest_ts]
                if not row.empty:
                    return float(row.iloc[0]["close"])
        return None

    def load_perp_data(self, perp_df: pd.DataFrame):
        """Load perp candle data for spot price queries."""
        self._perp_df = perp_df
        self._perp_ts = sorted(perp_df["timestamp"].unique().tolist())

    def _nearest_ts_perp(self, ts_ms: int) -> Optional[int]:
        import bisect
        if not hasattr(self, "_perp_ts"):
            return None
        idx = bisect.bisect_right(self._perp_ts, ts_ms) - 1
        if idx < 0:
            return None
        return self._perp_ts[idx]

    @staticmethod
    def _safe_float(v) -> Optional[float]:
        if v is None:
            return None
        try:
            f = float(v)
            return f if not pd.isna(f) else None
        except (TypeError, ValueError):
            return None
