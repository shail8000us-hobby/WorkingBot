"""
Bayesian Optimizer
==================
Uses Gaussian Process-based Bayesian Optimization (via scikit-optimize)
to find optimal MMM parameters with fewer evaluations than grid search.

Excellent for expensive evaluations or large parameter spaces where
exhaustive grid search is impractical.

Requires:
    pip install scikit-optimize
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Tuple

log = logging.getLogger("backtesting.bayesian_optimizer")

try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    _SKOPT_AVAILABLE = True
except ImportError:
    _SKOPT_AVAILABLE = False
    log.warning("scikit-optimize not installed. BayesianOptimizer unavailable. Install: pip install scikit-optimize")


class BayesianOptimizer:
    """
    Bayesian optimization over MMM parameters.

    Uses a Gaussian Process surrogate model to intelligently explore
    the parameter space, balancing exploration vs exploitation.

    Works best when:
     - Grid search would be impractical (>3 parameters or many values)
     - n_calls is limited (e.g., 50–100 calls vs 1000+ grid points)

    Usage:
        opt = BayesianOptimizer(
            param_space={
                "desired_ce_premium":   (50.0, 300.0, "real"),
                "desired_pe_premium":   (50.0, 300.0, "real"),
                "initial_lots":         (3, 25, "int"),
                "min_trigger_move_pct": (1.5, 5.0, "real"),
            },
            expiry_dates=["01-03-2026", ..., "10-03-2026"],
            n_calls=50,
            optimize_on="sharpe_ratio",
        )
        result = opt.run()
        best = result["best_params"]
    """

    def __init__(
        self,
        param_space: Dict[str, Tuple],
        expiry_dates: List[str],
        underlying: str = "BTC",
        entry_ist_time: str = "09:15",
        slippage_bps: float = 2.0,
        initial_margin_usd: float = 500_000.0,
        n_calls: int = 50,
        n_initial_points: int = 10,
        optimize_on: str = "sharpe_ratio",
        random_state: int = 42,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Args:
            param_space:       Dict of {param_name: (min, max, type)} where type is "real", "int", or list for categorical
            expiry_dates:      Dates to backtest over for each evaluation
            n_calls:           Total number of evaluations (includes initial random points)
            n_initial_points:  How many random evaluations before GP starts (default: 10)
            optimize_on:       Portfolio metric to maximize (default: "sharpe_ratio")
            random_state:      Random seed for reproducibility
        """
        if not _SKOPT_AVAILABLE:
            raise RuntimeError("scikit-optimize is required. Run: pip install scikit-optimize")

        self.param_space         = param_space
        self.expiry_dates        = expiry_dates
        self.underlying          = underlying
        self.entry_ist_time      = entry_ist_time
        self.slippage_bps        = slippage_bps
        self.initial_margin_usd  = initial_margin_usd
        self.n_calls             = n_calls
        self.n_initial_points    = n_initial_points
        self.optimize_on         = optimize_on
        self.random_state        = random_state
        self.progress_callback   = progress_callback

        self._call_count = 0
        self._evaluations: List[Dict] = []

    def _build_space(self) -> Tuple[List, List[str]]:
        """Convert param_space dict to skopt dimensions."""
        dimensions = []
        names = []
        for name, spec in self.param_space.items():
            if isinstance(spec, (list, tuple)) and len(spec) == 3:
                lo, hi, dtype = spec
                if dtype == "real":
                    dimensions.append(Real(lo, hi, name=name))
                elif dtype == "int":
                    dimensions.append(Integer(int(lo), int(hi), name=name))
                else:
                    dimensions.append(Categorical(spec, name=name))
            elif isinstance(spec, list):
                dimensions.append(Categorical(spec, name=name))
            names.append(name)
        return dimensions, names

    def run(self) -> Dict[str, Any]:
        """
        Run Bayesian optimization.

        Returns:
            Dict with best_params, best_score, all_evaluations, convergence_trace
        """
        from backtesting.data_store import DataStore
        from backtesting.optimizer.grid_search import _run_single_session
        from backtesting.analytics import compute_portfolio_metrics

        store = DataStore()
        dimensions, names = self._build_space()

        def objective(**params) -> float:
            """Evaluate a parameter set; returns NEGATIVE metric (skopt minimizes)."""
            self._call_count += 1
            log.info(f"Bayesian eval {self._call_count}/{self.n_calls}: {params}")

            sessions = []
            for date in self.expiry_dates:
                result = _run_single_session(
                    params={**params, "expiry_date": date},
                    expiry_date=date,
                    underlying=self.underlying,
                    entry_ist_time=self.entry_ist_time,
                    slippage_bps=self.slippage_bps,
                    initial_margin_usd=self.initial_margin_usd,
                    store=store,
                )
                sessions.append(result)

            portfolio  = compute_portfolio_metrics(sessions)
            metric_val = portfolio.get(self.optimize_on, 0.0)

            self._evaluations.append({
                "call":       self._call_count,
                "params":     dict(params),
                "metric":     metric_val,
                "win_rate":   portfolio.get("win_rate", 0),
                "avg_net_pnl": portfolio.get("avg_net_pnl", 0),
            })

            if self.progress_callback:
                self.progress_callback(self._call_count, self.n_calls)

            return -metric_val   # Negate because skopt minimizes

        # Wrap objective for use_named_args decorator
        @use_named_args(dimensions)
        def _objective_wrapped(**kwargs):
            return objective(**kwargs)

        result = gp_minimize(
            func=_objective_wrapped,
            dimensions=dimensions,
            n_calls=self.n_calls,
            n_initial_points=self.n_initial_points,
            random_state=self.random_state,
            verbose=False,
        )

        # Extract best params
        best_params = dict(zip(names, result.x))
        best_score  = -result.fun   # Un-negate

        log.info(f"Bayesian opt complete: best {self.optimize_on}={best_score:.4f} at {best_params}")

        # Sort evaluations by metric
        self._evaluations.sort(key=lambda x: x["metric"], reverse=True)

        return {
            "best_params":        best_params,
            "best_score":         best_score,
            "optimize_on":        self.optimize_on,
            "n_calls":            self.n_calls,
            "all_evaluations":    self._evaluations,
            "convergence_trace":  [-v for v in result.func_vals],
        }

    def plot_convergence(self) -> None:
        """Print a simple ASCII convergence trace."""
        if not self._evaluations:
            print("No evaluations yet. Run opt.run() first.")
            return
        print("\n📈 Bayesian Optimization Convergence:")
        best = float("-inf")
        for ev in self._evaluations:
            if ev["metric"] > best:
                best = ev["metric"]
            bar_len = max(0, int(best * 10))
            print(f"  Call {ev['call']:3d}: {ev['metric']:+.4f}  (best={best:+.4f})  {'█'*min(bar_len,40)}")
