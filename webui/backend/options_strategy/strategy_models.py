"""
Strategy Models
===============
Data models and schemas for options strategies.

Created: January 5, 2026
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


class StrategyType(str, Enum):
    """Supported strategy types"""
    # Long (debit) strategies
    STRADDLE = "straddle"
    LONG_STRADDLE = "long_straddle"
    STRANGLE = "strangle"
    LONG_STRANGLE = "long_strangle"
    
    # Short (credit) strategies
    SHORT_STRADDLE = "short_straddle"
    SHORT_STRANGLE = "short_strangle"
    
    # Multi-leg strategies
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    
    # Vertical spreads
    CALL_SPREAD = "call_spread"
    PUT_SPREAD = "put_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    
    # Custom
    CUSTOM = "custom"


class StrategyStatus(str, Enum):
    """Strategy lifecycle status"""
    PENDING = "pending"        # Created but not executed
    EXECUTING = "executing"    # Order being placed
    ACTIVE = "active"          # All legs filled, strategy running
    CLOSING = "closing"        # Exit in progress
    CLOSED = "closed"          # All positions closed
    FAILED = "failed"          # Execution failed
    PARTIAL = "partial"        # Some legs filled (needs attention)


class LegStatus(str, Enum):
    """Individual leg status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OrderSide(str, Enum):
    """Order direction"""
    BUY = "buy"
    SELL = "sell"


class OptionType(str, Enum):
    """Option type"""
    CALL = "call"
    PUT = "put"


@dataclass
class StrategyLeg:
    """
    Single leg of a multi-leg strategy
    
    Example: In a straddle, there are 2 legs:
    - Leg 1: Buy Call @ Strike
    - Leg 2: Buy Put @ Strike
    """
    leg_id: int
    option_type: str              # "call" or "put"
    strike: float
    expiry: str                   # DDMMYYYY format
    side: str                     # "buy" or "sell"
    quantity: int
    symbol: str = ""              # Delta Exchange symbol (e.g., C-BTC-93000-30012026)
    
    # Execution details (filled after order)
    status: str = LegStatus.PENDING.value
    order_id: str = ""
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    
    # Current market data
    current_price: float = 0.0
    current_bid: float = 0.0
    current_ask: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyLeg':
        return cls(**data)
    
    def generate_symbol(self, underlying: str) -> str:
        """Generate Delta Exchange option symbol"""
        prefix = "C" if self.option_type == "call" else "P"
        # Format: C-BTC-93000-30012026 or P-BTC-93000-30012026
        self.symbol = f"{prefix}-{underlying}-{int(self.strike)}-{self.expiry}"
        return self.symbol


@dataclass
class EntryConditions:
    """
    Conditions that must be met before strategy execution
    All conditions are optional - empty = execute immediately
    """
    iv_min: Optional[float] = None          # Enter when IV >= this
    iv_max: Optional[float] = None          # Enter when IV <= this
    spot_min: Optional[float] = None        # Enter when spot >= this
    spot_max: Optional[float] = None        # Enter when spot <= this
    time_window_start: Optional[str] = None # HH:MM format
    time_window_end: Optional[str] = None   # HH:MM format
    max_cost: Optional[float] = None        # Max total premium to pay
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EntryConditions':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExitConditions:
    """
    Conditions that trigger automatic strategy exit
    """
    profit_target_pct: Optional[float] = 30.0    # Exit at +30% profit
    stop_loss_pct: Optional[float] = -50.0       # Exit at -50% loss
    dte_exit: Optional[int] = 3                  # Exit 3 days before expiry
    theta_decay_pct: Optional[float] = None      # Exit when theta decay > X%
    trailing_stop_pct: Optional[float] = None    # Trailing stop %
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExitConditions':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Strategy:
    """
    Complete strategy with all legs and conditions
    
    This is the main model stored in the database and used for tracking.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy_type: str = StrategyType.CUSTOM.value
    underlying: str = "BTC"
    expiry: str = ""                  # Expiry date (YYMMDD format)
    status: str = StrategyStatus.PENDING.value
    
    # Legs
    legs: List[StrategyLeg] = field(default_factory=list)
    
    # Conditions
    entry_conditions: EntryConditions = field(default_factory=EntryConditions)
    exit_conditions: ExitConditions = field(default_factory=ExitConditions)
    
    # Cost tracking
    estimated_cost: float = 0.0       # Pre-execution estimate
    total_cost: float = 0.0           # Actual cost after fills
    current_value: float = 0.0        # Current market value
    
    # P&L
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    current_pnl: float = 0.0          # Total current P&L
    pnl_pct: float = 0.0
    
    # Notes
    notes: Optional[str] = None
    
    # Greeks (aggregate)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    
    # Strategy-specific data
    breakeven_lower: Optional[float] = None
    breakeven_upper: Optional[float] = None
    max_profit: Optional[float] = None      # None = unlimited
    max_loss: Optional[float] = None        # None = unlimited
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    executed_at: Optional[str] = None
    closed_at: Optional[str] = None
    close_reason: Optional[str] = None
    
    # Tracking
    highest_pnl: float = 0.0          # For trailing stop
    lowest_pnl: float = 0.0           # Track worst drawdown
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'strategy_type': self.strategy_type,
            'underlying': self.underlying,
            'expiry': self.expiry,
            'status': self.status,
            'legs': [leg.to_dict() for leg in self.legs],
            'entry_conditions': self.entry_conditions.to_dict(),
            'exit_conditions': self.exit_conditions.to_dict(),
            'estimated_cost': self.estimated_cost,
            'total_cost': self.total_cost,
            'current_value': self.current_value,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'current_pnl': self.current_pnl,
            'pnl_pct': self.pnl_pct,
            'delta': self.delta,
            'gamma': self.gamma,
            'vega': self.vega,
            'theta': self.theta,
            'breakeven_lower': self.breakeven_lower,
            'breakeven_upper': self.breakeven_upper,
            'max_profit': self.max_profit,
            'max_loss': self.max_loss,
            'created_at': self.created_at,
            'executed_at': self.executed_at,
            'closed_at': self.closed_at,
            'close_reason': self.close_reason,
            'highest_pnl': self.highest_pnl,
            'lowest_pnl': self.lowest_pnl,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Strategy':
        """Create from dictionary"""
        legs = [StrategyLeg.from_dict(leg) for leg in data.get('legs', [])]
        entry_cond = EntryConditions.from_dict(data.get('entry_conditions', {}))
        exit_cond = ExitConditions.from_dict(data.get('exit_conditions', {}))
        
        strategy = cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            strategy_type=data.get('strategy_type', StrategyType.CUSTOM.value),
            underlying=data.get('underlying', 'BTC'),
            status=data.get('status', StrategyStatus.PENDING.value),
            legs=legs,
            entry_conditions=entry_cond,
            exit_conditions=exit_cond
        )
        
        # Copy other fields
        for field_name in ['estimated_cost', 'total_cost', 'current_value',
                          'realized_pnl', 'unrealized_pnl', 'pnl_pct',
                          'delta', 'gamma', 'vega', 'theta',
                          'breakeven_lower', 'breakeven_upper',
                          'max_profit', 'max_loss',
                          'created_at', 'executed_at', 'closed_at', 'close_reason',
                          'highest_pnl', 'lowest_pnl']:
            if field_name in data:
                setattr(strategy, field_name, data[field_name])
        
        return strategy
    
    def generate_name(self) -> str:
        """Auto-generate strategy name if not provided"""
        if self.name:
            return self.name
        
        # Get main strike (first leg)
        main_strike = self.legs[0].strike if self.legs else 0
        expiry = self.legs[0].expiry if self.legs else ""
        
        # Format expiry for display (DDMMYYYY -> DD/MM)
        expiry_display = f"{expiry[:2]}/{expiry[2:4]}" if len(expiry) >= 4 else expiry
        
        type_names = {
            StrategyType.STRADDLE.value: "Straddle",
            StrategyType.STRANGLE.value: "Strangle",
            StrategyType.IRON_CONDOR.value: "Iron Condor",
            StrategyType.IRON_BUTTERFLY.value: "Iron Butterfly",
            StrategyType.CALL_SPREAD.value: "Call Spread",
            StrategyType.PUT_SPREAD.value: "Put Spread",
            StrategyType.CUSTOM.value: "Custom"
        }
        
        type_name = type_names.get(self.strategy_type, "Strategy")
        self.name = f"{self.underlying} {type_name} {int(main_strike)} ({expiry_display})"
        return self.name
    
    def calculate_pnl(self):
        """Calculate P&L based on current values"""
        if self.total_cost == 0:
            return
        
        self.unrealized_pnl = self.current_value - self.total_cost
        self.pnl_pct = (self.unrealized_pnl / abs(self.total_cost)) * 100 if self.total_cost != 0 else 0
        
        # Track high/low for trailing stop
        if self.unrealized_pnl > self.highest_pnl:
            self.highest_pnl = self.unrealized_pnl
        if self.unrealized_pnl < self.lowest_pnl:
            self.lowest_pnl = self.unrealized_pnl


@dataclass
class StrategyExecutionResult:
    """Result of strategy execution attempt"""
    success: bool
    strategy_id: str
    status: str
    message: str
    legs_filled: int = 0
    legs_total: int = 0
    total_cost: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class PayoffPoint:
    """Single point on payoff diagram"""
    spot_price: float
    pnl: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PayoffDiagram:
    """Payoff diagram data for visualization"""
    points: List[PayoffPoint] = field(default_factory=list)
    breakeven_points: List[float] = field(default_factory=list)
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    current_spot: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        # Return both formats for compatibility
        # Legacy format: points array with objects
        # New format: separate price_points and payoff_values arrays for frontend charts
        return {
            'points': [p.to_dict() for p in self.points],
            'price_points': [p.spot_price for p in self.points],
            'payoff_values': [p.pnl for p in self.points],
            'breakeven_points': self.breakeven_points,
            'max_profit': self.max_profit,
            'max_loss': self.max_loss,
            'current_spot': self.current_spot
        }
