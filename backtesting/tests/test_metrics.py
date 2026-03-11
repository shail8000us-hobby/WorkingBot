"""
Unit Tests — Analytics Metrics
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from backtesting.analytics.metrics import (
    compute_session_metrics,
    compute_portfolio_metrics,
    compute_weakness_probes,
)


def _make_result(
    realized=500.0,
    unrealized=100.0,
    total_fees=30.0,
    max_drawdown=200.0,
    peak_pnl=700.0,
    adjustment_count=5,
    status="COMPLETE",
    expiry="10-03-2026",
    fills=None,
):
    return {
        "expiry_date":       expiry,
        "strategy_status":   status,
        "realized_pnl":      realized,
        "unrealized_pnl":    unrealized,
        "total_pnl":         realized + unrealized,
        "total_fees":        total_fees,
        "total_fees_usd":    total_fees,
        "max_drawdown":      max_drawdown,
        "peak_pnl":          peak_pnl,
        "adjustment_count":  adjustment_count,
        "both_sides_up":     0,
        "shift_count":       0,
        "close_at_5_count":  0,
        "harvest_count":     1,
        "recycle_count":     0,
        "total_beats":       480,
        "total_slippage_usd": 15.0,
        "start_ts_ms":       1_741_600_000_000,
        "end_ts_ms":         1_741_630_000_000,
        "fills":             fills or [],
        "final_margin":      {"utilization_pct": 40.0},
        "adjustment_history": [],
    }


def test_net_pnl_calculation():
    r = _make_result(realized=500, unrealized=100, total_fees=30)
    m = compute_session_metrics(r)
    assert m["net_pnl"] == pytest.approx(570.0)


def test_max_drawdown_pct():
    r = _make_result(peak_pnl=1000, max_drawdown=200)
    m = compute_session_metrics(r)
    assert m["max_drawdown_pct"] == pytest.approx(20.0)


def test_calmar_ratio():
    r = _make_result(realized=500, unrealized=100, total_fees=30, max_drawdown=200)
    m = compute_session_metrics(r)
    # net_pnl=570, max_drawdown=200 → calmar=2.85
    assert m["calmar_ratio"] == pytest.approx(570.0 / 200.0, rel=0.01)


def test_portfolio_win_rate():
    # Make one clearly losing session: realized=-500, unrealized=0, fees=30 → net=-530
    results = [
        _make_result(realized=100,  unrealized=0,   total_fees=30, expiry="01-03-2026"),
        _make_result(realized=-500, unrealized=0,   total_fees=30, expiry="02-03-2026"),
        _make_result(realized=200,  unrealized=0,   total_fees=30, expiry="03-03-2026"),
    ]
    p = compute_portfolio_metrics(results)
    assert p["win_rate"] == pytest.approx(66.67, abs=0.1)


def test_portfolio_sharpe_positive():
    results = [_make_result(realized=r, expiry=f"0{i+1}-03-2026") for i, r in enumerate([100, 200, 150])]
    p = compute_portfolio_metrics(results)
    assert p["sharpe_ratio"] > 0


def test_weakness_probe_survival():
    results = [
        _make_result(status="COMPLETE", expiry="01-03-2026"),
        _make_result(status="STOPPED",  expiry="02-03-2026"),
        _make_result(status="COMPLETE", expiry="03-03-2026"),
    ]
    probes = compute_weakness_probes(results)
    assert probes["survival"]["survival_pct"] == pytest.approx(66.7, abs=0.1)
    assert probes["survival"]["complete"] == 2
    assert probes["survival"]["stopped"] == 1


def test_weakness_probe_slippage():
    results = [_make_result(expiry=f"0{i+1}-03-2026") for i in range(3)]
    probes = compute_weakness_probes(results)
    assert probes["slippage_impact"]["total_slippage_usd"] == pytest.approx(45.0)
