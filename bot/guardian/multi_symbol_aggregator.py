"""
Multi-Symbol Risk Aggregator

Purpose: Aggregates risk data from multiple symbols and makes global STOP decisions

Architecture:
- Single Guardian instance monitors all enabled symbols
- Separate monitors per symbol (PositionMonitor, VolatilityCollector per symbol)
- Unified risk aggregation
- Global STOP if ANY symbol violates limits

Version: 1.0 (Phase 2C)
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger("guardian.multi_symbol")


@dataclass
class SymbolRiskSnapshot:
    """Risk snapshot for a single symbol"""
    symbol: str
    pnl: float
    unrealized_pnl: float
    position_count: int
    max_drawdown: float
    volatility: Optional[float]
    rsi: Optional[float]
    liquidation_distance_pct: Optional[float]
    timestamp: float
    status: str  # "SAFE" | "WARNING" | "DANGER" | "CRITICAL"


@dataclass
class AggregatedRisk:
    """Aggregated risk across all symbols"""
    total_pnl: float
    total_unrealized_pnl: float
    total_positions: int
    max_loss_across_symbols: float
    critical_symbols: List[str]
    warning_symbols: List[str]
    safe_symbols: List[str]
    global_risk_level: str  # "SAFE" | "WARNING" | "DANGER" | "CRITICAL"
    decision: str  # "GO" | "STOP"
    reason: str
    timestamp: float
    symbol_snapshots: Dict[str, SymbolRiskSnapshot]


class MultiSymbolRiskAggregator:
    """
    Aggregates risk from multiple symbols and makes global trading decisions
    
    Rules:
    1. CRITICAL on ANY symbol → Global STOP
    2. DANGER on ANY symbol → Global WARNING
    3. Total loss exceeds global limit → Global STOP
    4. All symbols SAFE → Global GO
    """
    
    def __init__(self, config):
        """
        Initialize aggregator
        
        Args:
            config: Global config with capital_allocation section
        """
        self.config = config
        
        # Extract capital allocation
        allocation = config.capital_allocation
        self.total_capital = allocation.total_capital_inr
        
        # Symbol allocations
        self.symbol_allocations = {}
        if hasattr(config, 'symbols') and config.symbols:
            for symbol_name, symbol_config in config.symbols.items():
                if symbol_config.enabled:
                    # Calculate allocation based on percentage
                    if symbol_name == "BTCUSD":
                        pct = allocation.btc_allocation_pct / 100.0
                    elif symbol_name == "ETHUSD":
                        pct = allocation.eth_allocation_pct / 100.0
                    else:
                        pct = 0.1  # Default 10% for unknown symbols
                    
                    allocated_capital = self.total_capital * pct
                    max_loss = symbol_config.safety.max_account_loss_inr
                    
                    self.symbol_allocations[symbol_name] = {
                        'capital': allocated_capital,
                        'max_loss': max_loss,
                        'percentage': pct * 100
                    }
        
        log.info(f"✅ Multi-Symbol Risk Aggregator initialized")
        log.info(f"Total Capital: ₹{self.total_capital:,.2f}")
        for symbol, alloc in self.symbol_allocations.items():
            log.info(f"  {symbol}: ₹{alloc['capital']:,.2f} ({alloc['percentage']:.1f}%) - Max Loss: ₹{alloc['max_loss']:,.2f}")
    
    def aggregate_risk(self, symbol_snapshots: Dict[str, SymbolRiskSnapshot]) -> AggregatedRisk:
        """
        Aggregate risk from all symbols and make global decision
        
        Args:
            symbol_snapshots: Dict mapping symbol name to its risk snapshot
            
        Returns:
            AggregatedRisk with global decision
        """
        # Initialize aggregates
        total_pnl = 0.0
        total_unrealized = 0.0
        total_positions = 0
        max_loss = 0.0
        
        critical_symbols = []
        warning_symbols = []
        danger_symbols = []
        safe_symbols = []
        
        # Aggregate across symbols
        for symbol, snapshot in symbol_snapshots.items():
            total_pnl += snapshot.pnl
            total_unrealized += snapshot.unrealized_pnl
            total_positions += snapshot.position_count
            
            # Track max loss
            if snapshot.max_drawdown < max_loss:
                max_loss = snapshot.max_drawdown
            
            # Categorize by status
            if snapshot.status == "CRITICAL":
                critical_symbols.append(symbol)
            elif snapshot.status == "DANGER":
                danger_symbols.append(symbol)
            elif snapshot.status == "WARNING":
                warning_symbols.append(symbol)
            else:
                safe_symbols.append(symbol)
        
        # Decision logic
        global_risk_level = "SAFE"
        decision = "GO"
        reason = "All symbols operating within safe limits"
        
        # Rule 1: CRITICAL on any symbol → Global STOP
        if critical_symbols:
            global_risk_level = "CRITICAL"
            decision = "STOP"
            reason = f"CRITICAL risk on symbols: {', '.join(critical_symbols)}"
        
        # Rule 2: DANGER on any symbol → Global WARNING (but not STOP)
        elif danger_symbols:
            global_risk_level = "DANGER"
            decision = "GO"  # Still allow trading, but elevated risk
            reason = f"DANGER level on symbols: {', '.join(danger_symbols)}"
        
        # Rule 3: Check total loss against global limit
        elif total_pnl < -self.total_capital * 0.1:  # 10% of total capital
            global_risk_level = "CRITICAL"
            decision = "STOP"
            reason = f"Total loss (₹{abs(total_pnl):,.2f}) exceeds 10% of capital"
        
        # Rule 4: WARNING on any symbol
        elif warning_symbols:
            global_risk_level = "WARNING"
            decision = "GO"
            reason = f"WARNING on symbols: {', '.join(warning_symbols)}"
        
        return AggregatedRisk(
            total_pnl=total_pnl,
            total_unrealized_pnl=total_unrealized,
            total_positions=total_positions,
            max_loss_across_symbols=max_loss,
            critical_symbols=critical_symbols,
            warning_symbols=warning_symbols + danger_symbols,
            safe_symbols=safe_symbols,
            global_risk_level=global_risk_level,
            decision=decision,
            reason=reason,
            timestamp=time.time(),
            symbol_snapshots=symbol_snapshots
        )
    
    def format_report(self, aggregated: AggregatedRisk) -> str:
        """
        Format aggregated risk report for logging/alerts
        
        Args:
            aggregated: AggregatedRisk instance
            
        Returns:
            Formatted string report
        """
        lines = [
            "═" * 80,
            "MULTI-SYMBOL RISK REPORT",
            "═" * 80,
            f"Global Decision: {aggregated.decision} ({aggregated.global_risk_level})",
            f"Reason: {aggregated.reason}",
            "",
            "Portfolio Summary:",
            f"  Total PnL: ₹{aggregated.total_pnl:,.2f}",
            f"  Unrealized PnL: ₹{aggregated.total_unrealized_pnl:,.2f}",
            f"  Total Positions: {aggregated.total_positions}",
            f"  Max Drawdown: ₹{abs(aggregated.max_loss_across_symbols):,.2f}",
            "",
            "Symbol Status:"
        ]
        
        # Add per-symbol details
        for symbol, snapshot in aggregated.symbol_snapshots.items():
            allocation = self.symbol_allocations.get(symbol, {})
            capital = allocation.get('capital', 0)
            max_loss = allocation.get('max_loss', 0)
            
            lines.append(f"\n  {symbol}:")
            lines.append(f"    Status: {snapshot.status}")
            lines.append(f"    PnL: ₹{snapshot.pnl:,.2f}")
            lines.append(f"    Unrealized: ₹{snapshot.unrealized_pnl:,.2f}")
            lines.append(f"    Positions: {snapshot.position_count}")
            lines.append(f"    Allocated Capital: ₹{capital:,.2f}")
            lines.append(f"    Max Loss Limit: ₹{max_loss:,.2f}")
            
            if snapshot.volatility is not None:
                lines.append(f"    Volatility: {snapshot.volatility:.2%}")
            if snapshot.rsi is not None:
                lines.append(f"    RSI: {snapshot.rsi:.2f}")
            if snapshot.liquidation_distance_pct is not None:
                lines.append(f"    Liq Distance: {snapshot.liquidation_distance_pct:.2%}")
        
        lines.append("═" * 80)
        return "\n".join(lines)


import time

