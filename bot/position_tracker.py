# bot/position_tracker.py
"""
Position Tracker with Liquidation Protection
Tracks open positions, calculates PnL, monitors liquidation risk
"""
from __future__ import annotations

import sys
import os
import time
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.state.store import StateStore
from bot.utils.atomic_file import atomic_write_json

log = logging.getLogger("runner")


@dataclass
class MarginInfo:
    """Margin information for a position"""
    initial_margin: float
    maintenance_margin: float
    current_margin: float
    margin_ratio: float  # Current margin / Maintenance margin (1.0 = at limit)
    available_balance: float


@dataclass
class LiquidationInfo:
    """Liquidation risk information"""
    liquidation_price: float
    distance_to_liq_percent: float
    distance_to_liq_rupees: float
    risk_level: str  # safe, warning, danger, critical
    auto_topup_enabled: bool
    auto_topup_count: int


@dataclass
class Position:
    """A single trading position with full tracking"""
    id: str
    entry_price: float
    entry_time: str
    size: float
    current_price: float
    mark_price: float
    pnl_usd: float
    pnl_inr: float
    tp_order_id: Optional[str]
    status: str  # open, closed
    margin: MarginInfo
    liquidation: LiquidationInfo
    last_update: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "size": self.size,
            "current_price": self.current_price,
            "mark_price": self.mark_price,
            "pnl_usd": self.pnl_usd,
            "pnl_inr": self.pnl_inr,
            "tp_order_id": self.tp_order_id,
            "status": self.status,
            "margin": {
                "initial_margin": self.margin.initial_margin,
                "maintenance_margin": self.margin.maintenance_margin,
                "current_margin": self.margin.current_margin,
                "margin_ratio": self.margin.margin_ratio,
                "available_balance": self.margin.available_balance,
            },
            "liquidation": {
                "liquidation_price": self.liquidation.liquidation_price,
                "distance_to_liq_percent": self.liquidation.distance_to_liq_percent,
                "distance_to_liq_rupees": self.liquidation.distance_to_liq_rupees,
                "risk_level": self.liquidation.risk_level,
                "auto_topup_enabled": self.liquidation.auto_topup_enabled,
                "auto_topup_count": self.liquidation.auto_topup_count,
            },
            "last_update": self.last_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Position:
        """Create Position from dictionary"""
        margin = MarginInfo(**data["margin"])
        liquidation = LiquidationInfo(**data["liquidation"])
        
        return cls(
            id=data["id"],
            entry_price=data["entry_price"],
            entry_time=data["entry_time"],
            size=data["size"],
            current_price=data["current_price"],
            mark_price=data["mark_price"],
            pnl_usd=data["pnl_usd"],
            pnl_inr=data["pnl_inr"],
            tp_order_id=data.get("tp_order_id"),
            status=data["status"],
            margin=margin,
            liquidation=liquidation,
            last_update=data["last_update"],
        )


class PositionTracker:
    """
    Tracks open positions with liquidation monitoring
    
    Features:
    - Real-time PnL calculation
    - Liquidation price monitoring
    - Margin ratio tracking
    - Risk level assessment
    - Persistent storage
    """
    
    def __init__(self, storage_file: str = "positions.json"):
        # Make storage file mode-specific
        cfg = get_config()
        trading_mode = cfg.safety.trading_mode.lower()
        if storage_file == "positions.json":
            storage_file = f"positions_{trading_mode}.json"

        self.storage_path = Path(storage_file)
        self.storage_file = storage_file
        self.positions: Dict[str, Position] = {}
        self._store = StateStore(
            self.storage_path,
            default={"positions": [], "metadata": {}},
            logger_name="position_store",
        )
        
        # Load configuration from YAML
        self.usd_to_inr_rate = cfg.guardian.usd_to_inr_rate
        self.maintenance_margin_percent = cfg.risk_limits.maintenance_margin_percent / 100
        self.auto_topup_threshold = 80.0 / 100  # Default 80%
        self.auto_topup_target = 90.0 / 100  # Default 90%
        self.max_topups_per_position = 3  # Default
        
        # Risk thresholds
        self.margin_warning_threshold = cfg.risk_limits.margin_warning_threshold / 100
        self.margin_danger_threshold = cfg.risk_limits.margin_danger_threshold / 100
        self.margin_critical_threshold = cfg.risk_limits.margin_critical_threshold / 100
        
        # Load existing positions
        self.load()
        
        log.info(f"PositionTracker initialized ({trading_mode} mode): {len(self.positions)} positions loaded from {self.storage_file}")
    
    def add_position(
        self,
        position_id: str,
        entry_price: float,
        size: float,
        tp_order_id: Optional[str] = None,
        current_price: Optional[float] = None,
        available_balance: float = 0.0
    ) -> Position:
        """
        Add a new position to track
        
        Args:
            position_id: Unique identifier for position
            entry_price: Entry price in INR
            size: Position size (contracts)
            tp_order_id: Take profit order ID
            current_price: Current market price (defaults to entry)
            available_balance: Available balance for margin
        """
        if current_price is None:
            current_price = entry_price
        
        # Calculate initial margin (simplified: entry_price * size * maintenance%)
        initial_margin = entry_price * size * self.maintenance_margin_percent
        maintenance_margin = initial_margin
        
        # Calculate liquidation price - FIXED for Delta Portfolio Mode
        # In portfolio/cross margin mode, liquidation is based on account equity, not per-position
        # For demo: use a conservative estimate (much larger distance than isolated margin)
        # Real liquidation distance depends on total account balance and all positions
        # Using a safe approximation: 60% of entry price for long positions in cross margin
        liquidation_price = entry_price * 0.40  # Liquidation at 60% drop (conservative for cross margin)
        
        # Calculate PnL
        pnl_inr = (current_price - entry_price) * size
        pnl_usd = pnl_inr / self.usd_to_inr_rate
        
        # Calculate distance to liquidation
        distance_to_liq_rupees = current_price - liquidation_price
        distance_to_liq_percent = (distance_to_liq_rupees / current_price) * 100
        
        # Determine risk level
        margin_ratio = 1.0 if maintenance_margin == 0 else (initial_margin / maintenance_margin)
        risk_level = self._calculate_risk_level(margin_ratio, distance_to_liq_percent)
        
        # Create position
        position = Position(
            id=position_id,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            size=size,
            current_price=current_price,
            mark_price=current_price,
            pnl_usd=pnl_usd,
            pnl_inr=pnl_inr,
            tp_order_id=tp_order_id,
            status="open",
            margin=MarginInfo(
                initial_margin=initial_margin,
                maintenance_margin=maintenance_margin,
                current_margin=initial_margin,
                margin_ratio=margin_ratio,
                available_balance=available_balance,
            ),
            liquidation=LiquidationInfo(
                liquidation_price=liquidation_price,
                distance_to_liq_percent=distance_to_liq_percent,
                distance_to_liq_rupees=distance_to_liq_rupees,
                risk_level=risk_level,
                auto_topup_enabled=True,
                auto_topup_count=0,
            ),
            last_update=datetime.now().isoformat(),
        )
        
        self.positions[position_id] = position
        self.save()
        
        log.info(f"Position added: {position_id} @ ₹{entry_price:,.2f}, Liq: ₹{liquidation_price:,.2f}")
        
        return position
    
    def update_position(
        self,
        position_id: str,
        current_price: float,
        available_balance: Optional[float] = None
    ) -> Optional[Position]:
        """
        Update position with new market price
        
        Args:
            position_id: Position to update
            current_price: New market price
            available_balance: Updated available balance
        """
        position = self.positions.get(position_id)
        if not position:
            log.warning(f"Position not found: {position_id}")
            return None
        
        # Update prices
        position.current_price = current_price
        position.mark_price = current_price
        
        # Recalculate PnL
        position.pnl_inr = (current_price - position.entry_price) * position.size
        position.pnl_usd = position.pnl_inr / self.usd_to_inr_rate
        
        # Update distance to liquidation
        liq_price = position.liquidation.liquidation_price
        position.liquidation.distance_to_liq_rupees = current_price - liq_price
        position.liquidation.distance_to_liq_percent = (
            (current_price - liq_price) / current_price * 100
        )
        
        # Update margin info if balance provided
        if available_balance is not None:
            position.margin.available_balance = available_balance
            # Recalculate current margin based on PnL
            position.margin.current_margin = position.margin.initial_margin + position.pnl_inr
            position.margin.margin_ratio = (
                position.margin.current_margin / position.margin.maintenance_margin
                if position.margin.maintenance_margin > 0 else 1.0
            )
        
        # Update risk level
        position.liquidation.risk_level = self._calculate_risk_level(
            position.margin.margin_ratio,
            position.liquidation.distance_to_liq_percent
        )
        
        position.last_update = datetime.now().isoformat()
        
        self.save()
        
        return position
    
    def close_position(self, position_id: str, close_price: float) -> Optional[Position]:
        """
        Close a position
        
        Args:
            position_id: Position to close
            close_price: Closing price
        """
        position = self.positions.get(position_id)
        if not position:
            log.warning(f"Position not found: {position_id}")
            return None
        
        # Final PnL calculation
        position.current_price = close_price
        position.pnl_inr = (close_price - position.entry_price) * position.size
        position.pnl_usd = position.pnl_inr / self.usd_to_inr_rate
        position.status = "closed"
        position.last_update = datetime.now().isoformat()
        
        log.info(
            f"Position closed: {position_id} @ ₹{close_price:,.2f}, "
            f"PnL: ${position.pnl_usd:.2f} / ₹{position.pnl_inr:.2f}"
        )
        
        # Remove from active tracking
        del self.positions[position_id]
        self.save()
        
        return position
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all positions"""
        if not self.positions:
            return {
                "total_positions": 0,
                "total_pnl_usd": 0.0,
                "total_pnl_inr": 0.0,
                "risk_percent": 0.0,
                "avg_margin_ratio": 0.0,
                "min_margin_ratio": 0.0,
                "positions_at_risk": 0,
                "overall_liq_risk": "none",
            }
        
        total_pnl_usd = sum(p.pnl_usd for p in self.positions.values())
        total_pnl_inr = sum(p.pnl_inr for p in self.positions.values())
        margin_ratios = [p.margin.margin_ratio for p in self.positions.values()]
        
        avg_margin_ratio = sum(margin_ratios) / len(margin_ratios)
        min_margin_ratio = min(margin_ratios)
        
        # Count positions at risk (warning or worse)
        positions_at_risk = sum(
            1 for p in self.positions.values()
            if p.liquidation.risk_level in ("warning", "danger", "critical")
        )
        
        # Determine overall liquidation risk
        if min_margin_ratio < self.margin_critical_threshold:
            overall_liq_risk = "critical"
        elif min_margin_ratio < self.margin_danger_threshold:
            overall_liq_risk = "high"
        elif min_margin_ratio < self.margin_warning_threshold:
            overall_liq_risk = "medium"
        else:
            overall_liq_risk = "low"
        
        # Calculate risk percentage (vs MAX_ACCOUNT_LOSS_INR)
        cfg = get_config()
        max_loss_inr = cfg.capital_protection.max_loss_inr
        risk_percent = 0.0
        if total_pnl_inr < 0:
            risk_percent = abs(total_pnl_inr) / max_loss_inr * 100
        
        return {
            "total_positions": len(self.positions),
            "total_pnl_usd": total_pnl_usd,
            "total_pnl_inr": total_pnl_inr,
            "risk_percent": risk_percent,
            "avg_margin_ratio": avg_margin_ratio,
            "min_margin_ratio": min_margin_ratio,
            "positions_at_risk": positions_at_risk,
            "overall_liq_risk": overall_liq_risk,
        }
    
    def _calculate_risk_level(self, margin_ratio: float, distance_to_liq_percent: float) -> str:
        """
        Calculate risk level based on margin ratio and distance to liquidation
        
        Returns: safe, warning, danger, critical
        
        FIXED: Distance thresholds now properly calibrated for leveraged trading.
        For 10x leverage positions:
        - 10% distance = liquidation imminent
        - 20% distance = danger zone
        - 40% distance = warning level
        - 60%+ distance = safe
        """
        # Check distance to liquidation first (using realistic thresholds)
        # CRITICAL: Less than 10% to liquidation
        if distance_to_liq_percent < 10.0:
            return "critical"
        # DANGER: Less than 20% to liquidation
        elif distance_to_liq_percent < 20.0:
            return "danger"
        # WARNING: Less than 40% to liquidation
        elif distance_to_liq_percent < 40.0:
            return "warning"
        
        # If distance is safe (40%+), check margin ratio for additional risk assessment
        if margin_ratio >= self.margin_warning_threshold:
            return "safe"
        elif margin_ratio >= self.margin_danger_threshold:
            return "warning"
        elif margin_ratio >= self.margin_critical_threshold:
            return "danger"
        else:
            return "critical"
    
    def save(self) -> None:
        """Save positions to disk"""
        try:
            data = {
                "positions": [p.to_dict() for p in self.positions.values()],
                "summary": self.get_summary(),
                "config": {
                    "maintenance_margin_percent": self.maintenance_margin_percent * 100,
                    "auto_topup_threshold": self.auto_topup_threshold * 100,
                    "auto_topup_target": self.auto_topup_target * 100,
                    "max_topups_per_position": self.max_topups_per_position,
                    "usd_to_inr_rate": self.usd_to_inr_rate,
                },
                "last_save": datetime.now().isoformat(),
            }
            
            atomic_write_json(self.storage_path, data, indent=2)

            log.debug(f"Positions saved: {len(self.positions)} positions")
            
        except Exception as e:
            log.error(f"Failed to save positions: {e}")
    
    def load(self) -> None:
        """Load positions from disk"""
        try:
            if not self.storage_path.exists():
                log.info("No existing positions file found")
                return

            data = self._store.locked_read()
            self.positions = {}
            for pos_data in data.get("positions", []):
                position = Position.from_dict(pos_data)
                self.positions[position.id] = position
            
            log.info(f"Positions loaded: {len(self.positions)} positions")
            
        except Exception as e:
            log.error(f"Failed to load positions: {e}")
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position"""
        return self.positions.get(position_id)
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())
    
    def needs_topup(self, position_id: str) -> bool:
        """Check if position needs margin top-up"""
        position = self.positions.get(position_id)
        if not position:
            return False
        
        # Check if already topped up too many times
        if position.liquidation.auto_topup_count >= self.max_topups_per_position:
            return False
        
        # Check margin ratio
        if position.margin.margin_ratio < self.auto_topup_threshold:
            return True
        
        # Check distance to liquidation
        cfg = get_config()
        distance_warning = cfg.risk_limits.distance_to_liq_warning
        if position.liquidation.distance_to_liq_percent < distance_warning:
            return True
        
        return False
    
    def record_topup(self, position_id: str, amount: float) -> None:
        """Record a margin top-up event"""
        position = self.positions.get(position_id)
        if not position:
            return
        
        position.margin.current_margin += amount
        position.margin.margin_ratio = (
            position.margin.current_margin / position.margin.maintenance_margin
            if position.margin.maintenance_margin > 0 else 1.0
        )
        position.liquidation.auto_topup_count += 1
        position.last_update = datetime.now().isoformat()
        
        log.info(f"Top-up recorded for {position_id}: +₹{amount:.2f}, ratio now {position.margin.margin_ratio:.2%}")
        
        self.save()
