"""
Grid Search Optimizer
======================
Exhaustively sweeps combinations of MMM parameters across a date range.

Usage:
    from backtesting.optimizer.grid_search import GridSearch

    gs = GridSearch(
        param_grid={
            "desired_ce_premium":  [100, 150, 200],
            "desired_pe_premium":  [100, 150, 200],
            "initial_lots":        [5, 10],
            "min_trigger_move_pct": [2.5, 3.0, 3.5],
        },
        expiry_dates=["01-03-2026", "05-03-2026", "10-03-2026"],
        underlying="BTC",
        n_workers=4,  # parallel workers
    )
    results = gs.run()
    best = gs.best_params(metric="sharpe_ratio")
"""

import itertools
import logging
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from backtesting.data_store import DataStore
from backtesting.engine import run_session
from backtesting.strategies.mmm import MMMAdapter
from backtesting.analytics import compute_portfolio_metrics, result_to_summary_dict

log = logging.getLogger("backtesting.grid_search")


class GridSearch:
    """
    Parameter grid search over a set of expiry dates.

    For each param combination × each expiry date, runs one backtest session.
    Results are aggregated into portfolio-level metrics per param set.
    """

    def __init__(
        self,
        param_grid: Dict[str, List[Any]],
        expiry_dates: List[str],
        underlying: str = "BTC",
        entry_ist_time: str = "09:15",
        slippage_bps: float = 2.0,
        initial_margin_usd: float = 500_000.0,
        n_workers: int = 1,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Args:
            param_grid:       Dict mapping param_name → list of values to try
            expiry_dates:     List of "DD-MM-YYYY" dates to backtest over
            underlying:       "BTC" or "ETH"
            entry_ist_time:   Entry time in IST "HH:MM"
            slippage_bps:     Slippage in bps for all sessions
            initial_margin_usd: Starting margin balance
            n_workers:        Number of parallel workers (use 1 for debugging)
            progress_callback: Optional callable(done, total) for progress reporting
        """
        self.param_grid         = param_grid
        self.expiry_dates       = expiry_dates
        self.underlying         = underlying
        self.entry_ist_time     = entry_ist_time
        self.slippage_bps       = slippage_bps
        self.initial_margin_usd = initial_margin_usd
        self.n_workers          = n_workers
        self.progress_callback  = progress_callback

        self._results: List[Dict] = []  # Flat list of (params, expiry) session results
        self._portfolio_results: List[Dict] = []  # Aggregated per param set

    def _get_param_combinations(self) -> List[Dict]:
        """Return all param combinations as a list of dicts."""
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        combos = []
        for combo in itertools.product(*values):
            combos.append(dict(zip(keys, combo)))
        return combos

    def run(self, output_dir: Optional[str] = None) -> List[Dict]:
        """
        Run the full grid search.

        Args:
            output_dir: If provided, save interim JSON results to this directory

        Returns:
            List of portfolio result dicts, one per param combination, sorted by Sharpe.
        """
        param_combos = self._get_param_combinations()
        total_runs = len(param_combos) * len(self.expiry_dates)
        done_count = [0]

        log.info(
            f"Grid search: {len(param_combos)} param combos × "
            f"{len(self.expiry_dates)} expiries = {total_runs} total sessions"
        )

        store = DataStore()
        portfolio_results = []

        for combo_idx, params in enumerate(param_combos):
            log.info(f"[{combo_idx+1}/{len(param_combos)}] Params: {params}")
            combo_session_results = []

            for expiry_date in self.expiry_dates:
                result = _run_single_session(
                    params=params,
                    expiry_date=expiry_date,
                    underlying=self.underlying,
                    entry_ist_time=self.entry_ist_time,
                    slippage_bps=self.slippage_bps,
                    initial_margin_usd=self.initial_margin_usd,
                    store=store,
                )
                combo_session_results.append(result)
                self._results.append({**result, "_params": params})

                done_count[0] += 1
                if self.progress_callback:
                    self.progress_callback(done_count[0], total_runs)

            portfolio = compute_portfolio_metrics(combo_session_results)
            portfolio["params"] = params
            portfolio["param_id"] = combo_idx
            portfolio["sessions"] = [result_to_summary_dict(r) for r in combo_session_results]
            portfolio_results.append(portfolio)

            if output_dir:
                _save_interim(portfolio, combo_idx, output_dir)

        # Sort by Sharpe ratio descending
        portfolio_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
        self._portfolio_results = portfolio_results

        log.info(
            f"Grid search complete: {len(portfolio_results)} param sets, "
            f"best Sharpe={portfolio_results[0].get('sharpe_ratio', 0):.4f} at params={portfolio_results[0].get('params')}"
        )
        return portfolio_results

    def best_params(self, metric: str = "sharpe_ratio") -> Dict:
        """
        Return the best param set by a given portfolio metric.

        Args:
            metric: Key in portfolio result dict (default: "sharpe_ratio")

        Returns:
            Params dict of the best-performing combination.
        """
        if not self._portfolio_results:
            raise RuntimeError("Run grid_search.run() first")

        best = max(self._portfolio_results, key=lambda x: x.get(metric, 0))
        return best.get("params", {})

    def top_n(self, n: int = 5, metric: str = "sharpe_ratio") -> List[Dict]:
        """Return top N param sets sorted by metric."""
        if not self._portfolio_results:
            raise RuntimeError("Run grid_search.run() first")
        sorted_results = sorted(
            self._portfolio_results,
            key=lambda x: x.get(metric, 0),
            reverse=True,
        )
        return sorted_results[:n]

    def to_dataframe(self):
        """Return all portfolio results as a pandas DataFrame for analysis."""
        import pandas as pd
        if not self._portfolio_results:
            return pd.DataFrame()

        rows = []
        for pr in self._portfolio_results:
            row = {**pr.get("params", {})}
            for key in ("win_rate", "avg_net_pnl", "sharpe_ratio", "sortino_ratio",
                        "max_drawdown", "calmar_ratio", "total_net_pnl", "avg_adjustments"):
                row[key] = pr.get(key)
            rows.append(row)
        return pd.DataFrame(rows)

    def save_results(self, path: str):
        """Save full grid search results to JSON."""
        with open(path, "w") as f:
            json.dump(self._portfolio_results, f, indent=2, default=str)
        log.info(f"Grid search results saved to {path}")


# ── Session runner (module-level for pickling in ProcessPoolExecutor) ─────────

def _run_single_session(
    params: Dict,
    expiry_date: str,
    underlying: str,
    entry_ist_time: str,
    slippage_bps: float,
    initial_margin_usd: float,
    store: DataStore = None,
) -> Dict:
    """Run one backtest session. Returns result dict or error dict."""
    if store is None:
        store = DataStore()

    try:
        df = store.read_options_data(expiry_date, underlying)
    except FileNotFoundError:
        return {
            "expiry_date":     expiry_date,
            "strategy_status": "ERROR",
            "error":           "No data",
            "total_pnl":       0.0,
            "net_pnl":         0.0,
            "max_drawdown":    0.0,
            "total_fees":      0.0,
        }

    perp_df = store.read_perp_data(expiry_date, underlying)
    run_params = {**params, "expiry_date": expiry_date}

    result = run_session(
        df=df,
        algo_adapter=MMMAdapter(mode="fresh"),
        params=run_params,
        entry_ist_time=entry_ist_time,
        expiry_date=expiry_date,
        underlying=underlying,
        slippage_bps=slippage_bps,
        initial_margin_usd=initial_margin_usd,
        perp_df=perp_df,
    )
    return result


def _save_interim(portfolio: Dict, idx: int, output_dir: str):
    path = Path(output_dir) / f"combo_{idx:04d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(portfolio, f, indent=2, default=str)
