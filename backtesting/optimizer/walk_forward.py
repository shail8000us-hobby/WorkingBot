"""
Walk-Forward Optimizer
========================
Prevents overfitting by using rolling train/test splits.

Method:
  1. Split the date range into N windows, each window = train_days + test_days
  2. For each window:
     a. Grid search the param_grid on train dates → find best params
     b. Run ONE backtest on the test dates with the best params (out-of-sample)
  3. Report both in-sample and out-of-sample metrics

This is the gold standard for avoiding curve-fitting in parameter optimization.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

from .grid_search import GridSearch, _run_single_session
from backtesting.analytics import compute_portfolio_metrics, result_to_summary_dict

log = logging.getLogger("backtesting.walk_forward")


class WalkForwardOptimizer:
    """
    Walk-forward optimization across a historical date range.

    Usage:
        wfo = WalkForwardOptimizer(
            param_grid={"desired_ce_premium": [100, 150, 200], "initial_lots": [5, 10]},
            start_date="01-01-2026",
            end_date="10-03-2026",
            train_days=20,
            test_days=5,
            underlying="BTC",
        )
        report = wfo.run()
        print(report["oos_sharpe"])   # Out-of-sample Sharpe
    """

    def __init__(
        self,
        param_grid: Dict[str, List],
        start_date: str,
        end_date: str,
        train_days: int = 20,
        test_days: int = 5,
        underlying: str = "BTC",
        entry_ist_time: str = "09:15",
        slippage_bps: float = 2.0,
        initial_margin_usd: float = 500_000.0,
        optimize_on: str = "sharpe_ratio",
        progress_callback: Optional[Callable] = None,
    ):
        self.param_grid          = param_grid
        self.start_date          = start_date
        self.end_date            = end_date
        self.train_days          = train_days
        self.test_days           = test_days
        self.underlying          = underlying
        self.entry_ist_time      = entry_ist_time
        self.slippage_bps        = slippage_bps
        self.initial_margin_usd  = initial_margin_usd
        self.optimize_on         = optimize_on
        self.progress_callback   = progress_callback
        self._windows: List[Dict] = []

    def _build_windows(self) -> List[Dict]:
        """Split the date range into train/test sliding windows."""
        start_dt = datetime.strptime(self.start_date, "%d-%m-%Y")
        end_dt   = datetime.strptime(self.end_date,   "%d-%m-%Y")

        windows = []
        train_start = start_dt

        while True:
            train_end  = train_start + timedelta(days=self.train_days - 1)
            test_start = train_end   + timedelta(days=1)
            test_end   = test_start  + timedelta(days=self.test_days - 1)

            if test_end > end_dt:
                break

            windows.append({
                "train_start": train_start.strftime("%d-%m-%Y"),
                "train_end":   train_end.strftime("%d-%m-%Y"),
                "test_start":  test_start.strftime("%d-%m-%Y"),
                "test_end":    test_end.strftime("%d-%m-%Y"),
            })

            train_start = test_start   # Slide forward by test_days (anchored walk-forward)

        log.info(f"Walk-forward: {len(windows)} windows ({self.train_days}d train / {self.test_days}d test)")
        return windows

    def _get_dates_in_range(self, start: str, end: str) -> List[str]:
        from backtesting.data_collector.expiry_resolver import get_expiry_range
        return get_expiry_range(start, end)

    def run(self) -> Dict[str, Any]:
        """
        Run the full walk-forward optimization.

        Returns:
            Dict with:
              windows:       List of per-window results
              oos_sessions:  All out-of-sample sessions
              oos_portfolio: Aggregate OOS portfolio metrics
              oos_sharpe:    OOS Sharpe ratio
              efficiency:    OOS/IS Sharpe (1.0 = perfect, <0.7 = overfit)
        """
        windows = self._build_windows()
        self._windows = windows

        all_oos_sessions = []
        window_reports   = []
        total_steps = len(windows)

        for i, w in enumerate(windows):
            log.info(f"Window {i+1}/{len(windows)}: train={w['train_start']}→{w['train_end']}, test={w['test_start']}→{w['test_end']}")

            # ── Step 1: Grid search on training data ──────────────────────────
            train_dates = self._get_dates_in_range(w["train_start"], w["train_end"])
            gs = GridSearch(
                param_grid=self.param_grid,
                expiry_dates=train_dates,
                underlying=self.underlying,
                entry_ist_time=self.entry_ist_time,
                slippage_bps=self.slippage_bps,
                initial_margin_usd=self.initial_margin_usd,
                n_workers=1,
            )
            is_results = gs.run()
            best_params = is_results[0]["params"] if is_results else {}
            is_metric = is_results[0].get(self.optimize_on, 0) if is_results else 0

            # ── Step 2: Test on out-of-sample data ────────────────────────────
            test_dates = self._get_dates_in_range(w["test_start"], w["test_end"])
            oos_sessions = []
            for date in test_dates:
                result = _run_single_session(
                    params={**best_params, "expiry_date": date},
                    expiry_date=date,
                    underlying=self.underlying,
                    entry_ist_time=self.entry_ist_time,
                    slippage_bps=self.slippage_bps,
                    initial_margin_usd=self.initial_margin_usd,
                )
                oos_sessions.append(result)

            oos_portfolio = compute_portfolio_metrics(oos_sessions) if oos_sessions else {}
            oos_metric    = oos_portfolio.get(self.optimize_on, 0)
            all_oos_sessions.extend(oos_sessions)

            window_reports.append({
                "window_idx":   i + 1,
                "train_start":  w["train_start"],
                "train_end":    w["train_end"],
                "test_start":   w["test_start"],
                "test_end":     w["test_end"],
                "best_params":  best_params,
                f"is_{self.optimize_on}":  is_metric,
                f"oos_{self.optimize_on}": oos_metric,
                "oos_win_rate": oos_portfolio.get("win_rate", 0),
                "oos_avg_pnl":  oos_portfolio.get("avg_net_pnl", 0),
            })

            if self.progress_callback:
                self.progress_callback(i + 1, total_steps)

            log.info(
                f"Window {i+1}: IS={self.optimize_on}={is_metric:.4f}, "
                f"OOS={self.optimize_on}={oos_metric:.4f}, "
                f"best_params={best_params}"
            )

        # ── Aggregate OOS ─────────────────────────────────────────────────────
        oos_portfolio = compute_portfolio_metrics(all_oos_sessions) if all_oos_sessions else {}
        avg_is_metric = sum(w.get(f"is_{self.optimize_on}", 0) for w in window_reports) / max(len(window_reports), 1)
        oos_metric    = oos_portfolio.get(self.optimize_on, 0)
        efficiency    = oos_metric / avg_is_metric if avg_is_metric else 0.0

        return {
            "windows":        window_reports,
            "oos_portfolio":  oos_portfolio,
            "oos_sessions":   [result_to_summary_dict(r) for r in all_oos_sessions],
            "oos_sharpe":     oos_portfolio.get("sharpe_ratio", 0),
            "oos_win_rate":   oos_portfolio.get("win_rate", 0),
            "oos_avg_pnl":    oos_portfolio.get("avg_net_pnl", 0),
            "avg_is_metric":  avg_is_metric,
            "efficiency":     round(efficiency, 4),   # OOS/IS ratio
            "n_windows":      len(windows),
            "optimize_on":    self.optimize_on,
        }
