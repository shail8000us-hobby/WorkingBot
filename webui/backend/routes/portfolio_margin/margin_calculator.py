"""
Portfolio Margin Calculator

Pure functions for margin calculations, risk analysis, stress testing,
and mode comparison.

Key formulas (from Delta Exchange docs):
  IM  = max(risk_margin, margin_floor) - UCF
  MM  = 0.80 × max(risk_margin, margin_floor) - UCF
  Utilization = (blocked_margin / balance) × 100
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import PortfolioMargin, WalletBalance, Position, RiskMetrics


def calculate_initial_margin(risk_margin: float, margin_floor: float, ucf: float) -> float:
    """Calculate Initial Margin (IM).

    IM = max(risk_margin, margin_floor) - UCF
    If UCF > max(risk_margin, margin_floor), IM becomes negative → increases available balance.
    """
    return max(risk_margin, margin_floor) - ucf


def calculate_maintenance_margin(risk_margin: float, margin_floor: float, ucf: float) -> float:
    """Calculate Maintenance Margin (MM).

    MM = 0.80 × max(risk_margin, margin_floor) - UCF
    """
    return 0.80 * max(risk_margin, margin_floor) - ucf


def calculate_utilization(blocked_margin: float, balance: float) -> float:
    """Calculate margin utilization percentage.

    Returns 0.0 if balance is zero to avoid division error.
    """
    if balance <= 0:
        return 0.0
    return (blocked_margin / balance) * 100.0


def calculate_efficiency(total_notional: float, balance: float) -> float:
    """Calculate capital efficiency = (total notional exposure / balance × 100).

    Measures how much notional you control per unit of capital.
    """
    if balance <= 0:
        return 0.0
    return (total_notional / balance) * 100.0


def analyze_portfolio_risk(
    wallet: Optional[WalletBalance],
    positions: List[Position],
    pm: Optional[PortfolioMargin],
) -> RiskMetrics:
    """Compute aggregated risk metrics from wallet, positions, and PM data."""

    if wallet is None:
        wallet = WalletBalance()
    if pm is None:
        pm = PortfolioMargin()

    ucf = pm.positions_upl  # Unrealized Cash Flows
    im = calculate_initial_margin(pm.risk_margin, pm.margin_floor, ucf)
    mm = calculate_maintenance_margin(pm.risk_margin, pm.margin_floor, ucf)
    utilization = calculate_utilization(wallet.blocked_margin, wallet.balance)

    # Total notional and per-position margin
    total_notional = sum(p.notional for p in positions)
    total_pos_margin = sum(p.initial_margin for p in positions)

    efficiency = calculate_efficiency(total_notional, wallet.balance)

    # Determine margin mode
    mode = 'portfolio' if wallet.portfolio_margin > 0 else 'isolated'

    # Aggregate portfolio Greeks
    p_delta = round(sum(p.size * p.delta for p in positions), 6)
    p_gamma = round(sum(p.size * p.gamma for p in positions), 6)
    p_theta = round(sum(p.size * p.theta for p in positions), 6)
    p_vega = round(sum(p.size * p.vega for p in positions), 6)

    # Use IM/MM from REST data if available (im_w_ucf fields), fall back to formula
    final_im = pm.im_w_ucf if pm.im_w_ucf != 0 else im
    final_mm = pm.mm_w_ucf if pm.mm_w_ucf != 0 else mm

    return RiskMetrics(
        initial_margin=round(final_im, 4),
        maintenance_margin=round(final_mm, 4),
        margin_utilization=round(utilization, 2),
        margin_efficiency=round(efficiency, 2),
        ucf_impact=round(ucf, 4),
        liquidation_risk=pm.liquidation_risk,
        margin_shortfall=round(pm.margin_shortfall, 4),
        total_position_margin=round(total_pos_margin, 4),
        total_notional=round(total_notional, 4),
        margin_mode=mode,
        portfolio_delta=p_delta,
        portfolio_gamma=p_gamma,
        portfolio_theta=p_theta,
        portfolio_vega=p_vega,
    )


def run_stress_test(
    positions: List[Position],
    wallet: WalletBalance,
    pct_moves: List[float],
) -> List[Dict]:
    """Simulate portfolio under different underlying price moves.

    Args:
        positions: list of current positions
        wallet: current wallet balance
        pct_moves: list of percentage moves (e.g., [-30, -20, -10, 10])

    Returns:
        list of stress test results per scenario
    """
    results = []
    for pct in pct_moves:
        multiplier = 1 + pct / 100.0
        total_stressed_pnl = 0.0
        for p in positions:
            stressed_mark = p.mark_price * multiplier
            # For options, delta-based approximation
            if p.contract_type in ('call_options', 'put_options'):
                price_change = p.mark_price * (pct / 100.0)
                estimated_pnl = p.size * p.delta * price_change
                # Add gamma effect for large moves
                estimated_pnl += 0.5 * p.size * p.gamma * (price_change ** 2)
            else:
                # Futures: linear P&L
                estimated_pnl = p.size * (stressed_mark - p.entry_price) - p.unrealized_pnl
            total_stressed_pnl += estimated_pnl

        stressed_balance = wallet.balance + total_stressed_pnl
        margin_call = stressed_balance < wallet.blocked_margin * 0.8

        results.append({
            'scenario': f'{pct:+.0f}%',
            'pct_move': pct,
            'stressed_pnl': round(total_stressed_pnl, 4),
            'stressed_balance': round(stressed_balance, 4),
            'current_balance': round(wallet.balance, 4),
            'margin_required': round(wallet.blocked_margin, 4),
            'margin_call_risk': margin_call,
            'status': 'MARGIN CALL' if margin_call else 'SAFE',
        })
    return results


def compare_margin_modes(
    isolated_margin: float,
    portfolio_margin: float,
) -> Dict:
    """Compare isolated vs portfolio margin requirements."""
    savings = isolated_margin - portfolio_margin
    pct = (savings / isolated_margin * 100) if isolated_margin > 0 else 0.0
    return {
        'isolated_margin': round(isolated_margin, 4),
        'portfolio_margin': round(portfolio_margin, 4),
        'margin_savings': round(savings, 4),
        'savings_percent': round(pct, 2),
        'recommendation': 'portfolio' if savings > 0 else 'isolated',
    }
