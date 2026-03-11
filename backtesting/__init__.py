"""
Backtesting Engine for Delta Exchange India Options Algos
=========================================================

Fully independent module. Does NOT modify any production files.
Port 5557 for the web UI.

Structure:
  data_collector/   — Fetch historical data from Delta Exchange India
  data_store/       — Parquet storage and SQLite index
  engine/           — Generic simulation engine
  strategies/       — Algo adapters (MMM, future algos)
  analytics/        — Metrics, reports, export
  optimizer/        — Grid search, walk-forward, Bayesian optimization
  ui/               — Web dashboard (Flask + React)
  scripts/          — CLI runners
  tests/            — Unit and integration tests
"""

__version__ = "1.0.0"
