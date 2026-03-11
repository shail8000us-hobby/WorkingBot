"""
Abstract Base Algo Adapter
===========================
All strategy adapters must implement this interface.

The session runner calls these methods in sequence. The adapter
translates the generic calls into algo-specific logic (e.g., MMM heartbeat).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAlgoAdapter(ABC):
    """
    Abstract base class for strategy adapters.

    Subclasses:
      - backtesting/strategies/mmm/mmm_adapter.py   ← MMM strategy
      - backtesting/strategies/future_algo/          ← future algos

    The session_runner calls:
      1. setup(params, chain, broker, margin)  — once at session start
      2. on_heartbeat(ts_ms, chain)            — every tick
      3. is_done()                             — check session end condition
      4. get_session_result()                  — final result dict
    """

    @abstractmethod
    def setup(
        self,
        params: Dict[str, Any],
        sim_chain,        # SimChain
        sim_broker,       # SimBroker
        sim_margin,       # MarginState
        entry_ts_ms: int,
    ) -> None:
        """
        Initialize the strategy session.

        Called once before any heartbeat. Should:
          - Create initial session state
          - Find entry strikes (or validate import strikes)
          - Place initial short positions via sim_broker

        Args:
            params:      Strategy parameters dict
            sim_chain:   SimChain instance (read-only market data)
            sim_broker:  SimBroker instance (for placing orders)
            sim_margin:  MarginState instance (for margin checks)
            entry_ts_ms: Timestamp (ms) at which the session starts
        """
        ...

    @abstractmethod
    def on_heartbeat(self, ts_ms: int, chain) -> None:
        """
        Execute one heartbeat cycle at timestamp ts_ms.

        Called by session_runner for each tick. Should:
          - Check close-at-5 / wind-down
          - Evaluate triggers
          - Calculate and execute adjustments if triggered
          - Run safety checks
          - Update session state

        Args:
            ts_ms: Current simulation timestamp (milliseconds)
            chain: SimChain instance at current timestamp
        """
        ...

    @abstractmethod
    def is_done(self) -> bool:
        """
        Return True when the session should terminate.

        Examples:
          - strategy_status == "STOPPED" (max loss, manual stop)
          - All positions closed (strategy_status == "COMPLETE")
          - Expiry reached
        """
        ...

    @abstractmethod
    def get_session_result(self) -> Dict[str, Any]:
        """
        Return the final session result dict after the session ends.

        Must include at minimum:
          - session_id
          - expiry_date
          - strategy_status (STOPPED / COMPLETE / ERROR)
          - total_pnl (realized + unrealized)
          - realized_pnl
          - unrealized_pnl
          - total_fees
          - adjustment_count
          - adjustment_history (list)
          - positions (list of position dicts)
          - trade_log (list of FillRecord-like dicts)
          - peak_pnl
          - max_drawdown
          - start_ts_ms, end_ts_ms
        """
        ...

    @abstractmethod
    def get_heartbeat_interval_sec(self) -> int:
        """
        Return the desired interval (seconds) between heartbeats.

        The session runner uses this to advance the clock after each tick.
        The MMM adapter returns the adaptive interval from mmm_trigger.compute_adaptive_interval().
        """
        ...

    # ── Optional hooks ────────────────────────────────────────────────────────

    def on_session_end(self) -> None:
        """
        Called by session_runner after the last heartbeat, before result collection.

        Use this for wind-down cleanup, final position closes, etc.
        Default: no-op.
        """
        pass

    def get_algo_name(self) -> str:
        """Return a human-readable algo name for logging and reporting."""
        return self.__class__.__name__
