"""
Portfolio Margin Data Models

Dataclasses for portfolio margin, positions, wallet, and risk metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class PortfolioMargin:
    """Real-time portfolio margin data from WebSocket or REST."""
    risk_margin: float = 0.0
    im_w_ucf: float = 0.0
    mm_w_ucf: float = 0.0
    positions_upl: float = 0.0
    risk_matrix: Dict[str, Any] = field(default_factory=dict)
    liquidation_risk: bool = False
    margin_floor: float = 0.0
    futures_margin_floor: float = 0.0
    long_options_margin_floor: float = 0.0
    short_options_margin_floor: float = 0.0
    margin_shortfall: float = 0.0
    commission: float = 0.0
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_ws_data(cls, data: dict) -> 'PortfolioMargin':
        """Parse WebSocket portfolio_margins channel data."""
        return cls(
            risk_margin=float(data.get('risk_margin', 0)),
            im_w_ucf=float(data.get('im_w_ucf', 0)),
            mm_w_ucf=float(data.get('mm_w_ucf', 0)),
            positions_upl=float(data.get('positions_upl', 0)),
            risk_matrix=data.get('risk_matrix', {}),
            liquidation_risk=bool(data.get('liquidation_risk', False)),
            margin_floor=float(data.get('margin_floor', 0)),
            futures_margin_floor=float(data.get('futures_margin_floor', 0)),
            long_options_margin_floor=float(data.get('long_options_margin_floor', 0)),
            short_options_margin_floor=float(data.get('short_options_margin_floor', 0)),
            margin_shortfall=float(data.get('margin_shortfall', 0)),
            commission=float(data.get('commission', 0)),
            timestamp=data.get('timestamp'),
        )

    @classmethod
    def from_api_data(cls, data: dict) -> 'PortfolioMargin':
        """Parse GET /v2/wallet/portfolio_margin REST response."""
        if not data:
            return cls()
        return cls(
            risk_margin=float(data.get('risk_margin', 0)),
            im_w_ucf=float(data.get('im_w_ucf', data.get('initial_margin', 0))),
            mm_w_ucf=float(data.get('mm_w_ucf', data.get('maintenance_margin', 0))),
            positions_upl=float(data.get('positions_upl', data.get('unrealized_cashflows', 0))),
            risk_matrix=data.get('risk_matrix', {}),
            liquidation_risk=bool(data.get('liquidation_risk', False)),
            margin_floor=float(data.get('margin_floor', 0)),
            futures_margin_floor=float(data.get('futures_margin_floor', 0)),
            long_options_margin_floor=float(data.get('long_options_margin_floor', 0)),
            short_options_margin_floor=float(data.get('short_options_margin_floor', 0)),
            margin_shortfall=float(data.get('margin_shortfall', 0)),
            commission=float(data.get('commission', 0)),
            timestamp=data.get('timestamp'),
        )


@dataclass
class WalletBalance:
    """Wallet balance with margin breakdown."""
    asset_id: int = 0
    asset_symbol: str = ''
    balance: float = 0.0
    available_balance: float = 0.0
    blocked_margin: float = 0.0
    portfolio_margin: float = 0.0
    position_margin: float = 0.0
    order_margin: float = 0.0
    commission: float = 0.0
    unrealized_pnl: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_api_data(cls, data: dict) -> 'WalletBalance':
        """Parse /v2/wallet/balances response item."""
        return cls(
            asset_id=data.get('asset_id', 0),
            asset_symbol=data.get('asset_symbol', ''),
            balance=float(data.get('balance', 0)),
            available_balance=float(data.get('available_balance', 0)),
            blocked_margin=float(data.get('blocked_margin', 0)),
            portfolio_margin=float(data.get('portfolio_margin', 0)),
            position_margin=float(data.get('position_margin', 0)),
            order_margin=float(data.get('order_margin', 0)),
            commission=float(data.get('commission', 0)),
            unrealized_pnl=float(data.get('unrealized_pnl', 0)),
        )

    @classmethod
    def from_ws_data(cls, data: dict) -> 'WalletBalance':
        """Parse WebSocket margins channel data."""
        return cls(
            balance=float(data.get('balance', 0)),
            available_balance=float(data.get('available_balance', 0)),
            blocked_margin=float(data.get('blocked_margin', 0)),
            portfolio_margin=float(data.get('portfolio_margin', 0)),
            position_margin=float(data.get('position_margin', 0)),
            order_margin=float(data.get('order_margin', 0)),
        )


@dataclass
class Position:
    """Open position with margin details and Greeks."""
    product_id: int = 0
    product_symbol: str = ''
    contract_type: str = ''  # perpetual_futures, call_options, put_options
    size: float = 0.0
    entry_price: float = 0.0
    mark_price: float = 0.0
    initial_margin: float = 0.0  # Per-position IM from API
    margin: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    liquidation_price: Optional[float] = None
    side: str = ''  # long, short
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    # Expiry
    expiry_date: Optional[str] = None
    strike_price: Optional[float] = None
    # Notional
    notional: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_api_data(cls, data: dict) -> 'Position':
        """Parse /v2/positions/margined response item."""
        liq = data.get('liquidation_price')
        strike = data.get('strike_price')
        size = float(data.get('size', 0))
        mark = float(data.get('mark_price', 0))
        # Map initial_margin from API — in portfolio mode 'margin' is 0 but
        # 'initial_margin' contains the real per-position margin.
        im = float(data.get('initial_margin', 0) or data.get('margin', 0) or 0)
        # Greeks from API (Delta Exchange provides per-position greeks)
        greeks = data.get('greeks', {}) or {}
        return cls(
            product_id=data.get('product_id', 0),
            product_symbol=data.get('product_symbol', ''),
            contract_type=data.get('contract_type', ''),
            size=size,
            entry_price=float(data.get('entry_price', 0)),
            mark_price=mark,
            initial_margin=im,
            margin=float(data.get('margin', 0)),
            realized_pnl=float(data.get('realized_pnl', 0)),
            unrealized_pnl=float(data.get('unrealized_pnl', 0)),
            liquidation_price=float(liq) if liq is not None else None,
            side=data.get('side', ''),
            delta=float(greeks.get('delta', 0) or 0),
            gamma=float(greeks.get('gamma', 0) or 0),
            theta=float(greeks.get('theta', 0) or 0),
            vega=float(greeks.get('vega', 0) or 0),
            expiry_date=data.get('expiry_date') or data.get('settlement_time'),
            strike_price=float(strike) if strike is not None else None,
            notional=abs(size) * mark,
        )


@dataclass
class RiskMetrics:
    """Calculated risk metrics from portfolio margin + wallet data."""
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    margin_utilization: float = 0.0
    margin_efficiency: float = 0.0  # notional / balance
    ucf_impact: float = 0.0
    liquidation_risk: bool = False
    margin_shortfall: float = 0.0
    total_position_margin: float = 0.0
    total_notional: float = 0.0
    margin_mode: str = 'isolated'
    # Portfolio Greeks
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarginHistoryEntry:
    """Single point in margin history for charting."""
    timestamp: str = ''
    margin_utilization: float = 0.0
    balance: float = 0.0
    blocked_margin: float = 0.0
    available_balance: float = 0.0
    risk_margin: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
