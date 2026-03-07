# Phase 2: Monitoring & Risk Management

**Duration:** 1-2 weeks  
**Deliverables:** Real-time monitoring, Greeks tracking, risk validators, Guardian integration, alert system

---

## 📋 Phase 2 Overview

This phase implements comprehensive monitoring and risk management for the 0DTE bot. Real-time tracking of positions, Greeks exposure, margin utilization, and automated risk controls ensure safe operation.

**Key Components:**
1. Real-time monitoring service
2. Greeks calculator and tracker
3. Risk validators and circuit breakers
4. Guardian integration
5. Alert and notification system

---

## Module 1: Real-Time Monitor Service

### **File:** `bot/strategy/zero_dte/monitor.py`

```python
"""
Real-time monitoring service for 0DTE sessions
Tracks positions, Greeks, P&L, and risk metrics
"""
import asyncio
import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
import pytz

from bot.api.unified_api_client import UnifiedAPIClient
from bot.strategy.zero_dte.state_manager import get_state_manager


class ZeroDTEMonitor:
    """Real-time monitoring for 0DTE sessions"""
    
    def __init__(self, api_client: UnifiedAPIClient, config):
        self.api_client = api_client
        self.config = config
        self.state_manager = get_state_manager()
        self.db_path = 'database/zero_dte_rebalances.db'
        self._init_monitoring_db()
    
    def _init_monitoring_db(self):
        """Initialize monitoring database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                spot_price REAL NOT NULL,
                ce_premium REAL,
                pe_premium REAL,
                ce_lots INTEGER,
                pe_lots INTEGER,
                portfolio_delta REAL,
                portfolio_gamma REAL,
                portfolio_theta REAL,
                portfolio_vega REAL,
                unrealized_pnl REAL,
                margin_used REAL,
                margin_utilization_pct REAL,
                time_to_expiry_minutes INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Monitoring database initialized")
    
    async def save_snapshot(
        self,
        session_id: str,
        session: Dict,
        positions: Dict,
        ce_premium: float,
        pe_premium: float,
        unrealized_pnl: float
    ):
        """Save monitoring snapshot to database"""
        try:
            # Get spot price
            underlying = session['underlying']
            spot_price = await self.api_client.get_current_price(f"{underlying}USD")
            
            # Calculate portfolio Greeks
            ce_pos = positions.get('CE', {})
            pe_pos = positions.get('PE', {})
            
            ce_lots = ce_pos.get('lots', 0)
            pe_lots = pe_pos.get('lots', 0)
            
            portfolio_delta = (
                (ce_pos.get('delta', 0) * ce_lots) + 
                (pe_pos.get('delta', 0) * pe_lots)
            )
            
            portfolio_gamma = (
                (ce_pos.get('gamma', 0) * ce_lots) + 
                (pe_pos.get('gamma', 0) * pe_lots)
            )
            
            portfolio_theta = (
                (ce_pos.get('theta', 0) * ce_lots) + 
                (pe_pos.get('theta', 0) * pe_lots)
            )
            
            portfolio_vega = (
                (ce_pos.get('vega', 0) * ce_lots) + 
                (pe_pos.get('vega', 0) * pe_lots)
            )
            
            # Get margin info
            margin_info = await self._get_margin_info()
            margin_used = margin_info.get('used_margin', 0)
            margin_utilization = margin_info.get('utilization_pct', 0)
            
            # Calculate time to expiry
            time_to_expiry = self._calculate_time_to_expiry()
            
            # Save to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO monitoring_snapshots (
                    session_id, spot_price, ce_premium, pe_premium,
                    ce_lots, pe_lots, portfolio_delta, portfolio_gamma,
                    portfolio_theta, portfolio_vega, unrealized_pnl,
                    margin_used, margin_utilization_pct, time_to_expiry_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, spot_price, ce_premium, pe_premium,
                ce_lots, pe_lots, portfolio_delta, portfolio_gamma,
                portfolio_theta, portfolio_vega, unrealized_pnl,
                margin_used, margin_utilization, time_to_expiry
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Snapshot saved: Δ={portfolio_delta:.3f}, Γ={portfolio_gamma:.4f}, θ={portfolio_theta:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to save monitoring snapshot: {e}")
    
    async def _get_margin_info(self) -> Dict[str, float]:
        """Get current margin information"""
        try:
            positions = await self.api_client.get_all_positions_with_options()
            
            # Get account info
            # Note: This would need to be implemented in UnifiedAPIClient
            # For now, return mock data
            return {
                'used_margin': 0,
                'available_margin': 0,
                'utilization_pct': 0
            }
        except Exception as e:
            logger.error(f"Failed to get margin info: {e}")
            return {'used_margin': 0, 'available_margin': 0, 'utilization_pct': 0}
    
    def _calculate_time_to_expiry(self) -> int:
        """Calculate minutes until expiry"""
        try:
            settlement_time_str = self.config.exit.time_exit.settlement_time
            timezone_str = self.config.exit.time_exit.timezone
            
            from datetime import time as dt_time
            settlement_time = dt_time.fromisoformat(settlement_time_str)
            tz = pytz.timezone(timezone_str)
            
            now = datetime.now(tz)
            settlement_datetime = datetime.combine(now.date(), settlement_time, tzinfo=tz)
            
            # If settlement time has passed, return 0
            if now > settlement_datetime:
                return 0
            
            time_diff = settlement_datetime - now
            minutes = int(time_diff.total_seconds() / 60)
            
            return max(0, minutes)
            
        except Exception as e:
            logger.error(f"Failed to calculate time to expiry: {e}")
            return 0
    
    async def get_current_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get current monitoring metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM monitoring_snapshots 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (session_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get current metrics: {e}")
            return {}
    
    async def get_snapshot_history(
        self,
        session_id: str,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Get historical snapshots for session"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM monitoring_snapshots 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get snapshot history: {e}")
            return []
```

---

## Module 2: Greeks Calculator

### **File:** `bot/strategy/zero_dte/greeks_calculator.py`

```python
"""
Greeks calculator for portfolio-level risk metrics
"""
from typing import Dict, Any, Tuple
from loguru import logger


class GreeksCalculator:
    """Calculate and track portfolio Greeks"""
    
    def __init__(self, config):
        self.config = config
    
    def calculate_portfolio_greeks(
        self,
        ce_position: Dict[str, Any],
        pe_position: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate portfolio-level Greeks
        
        Returns:
            {
                'delta': float,
                'gamma': float,
                'theta': float,
                'vega': float,
                'delta_pct': float,  # Delta as % of 1 BTC
            }
        """
        ce_delta = ce_position.get('delta', 0) * ce_position.get('lots', 0)
        pe_delta = pe_position.get('delta', 0) * pe_position.get('lots', 0)
        portfolio_delta = ce_delta + pe_delta
        
        ce_gamma = ce_position.get('gamma', 0) * ce_position.get('lots', 0)
        pe_gamma = pe_position.get('gamma', 0) * pe_position.get('lots', 0)
        portfolio_gamma = ce_gamma + pe_gamma
        
        ce_theta = ce_position.get('theta', 0) * ce_position.get('lots', 0)
        pe_theta = pe_position.get('theta', 0) * pe_position.get('lots', 0)
        portfolio_theta = ce_theta + pe_theta
        
        ce_vega = ce_position.get('vega', 0) * ce_position.get('lots', 0)
        pe_vega = pe_position.get('vega', 0) * pe_position.get('lots', 0)
        portfolio_vega = ce_vega + pe_vega
        
        # Delta as percentage (for BTC, contract size = 0.001 BTC)
        delta_pct = abs(portfolio_delta) * 100
        
        return {
            'delta': portfolio_delta,
            'gamma': portfolio_gamma,
            'theta': portfolio_theta,
            'vega': portfolio_vega,
            'delta_pct': delta_pct,
            'ce_delta': ce_delta,
            'pe_delta': pe_delta
        }
    
    def check_greeks_limits(self, greeks: Dict[str, float]) -> Tuple[bool, str]:
        """
        Check if portfolio Greeks are within limits
        
        Returns:
            (is_within_limits, violation_message)
        """
        max_delta = self.config.risk.greeks.max_portfolio_delta
        max_gamma = self.config.risk.greeks.max_portfolio_gamma
        
        # Check delta
        if abs(greeks['delta']) > max_delta:
            msg = f"Delta limit exceeded: {greeks['delta']:.3f} > ±{max_delta}"
            logger.warning(msg)
            return False, msg
        
        # Check gamma
        if abs(greeks['gamma']) > max_gamma:
            msg = f"Gamma limit exceeded: {greeks['gamma']:.4f} > {max_gamma}"
            logger.warning(msg)
            return False, msg
        
        return True, ""
    
    def calculate_delta_dollars(
        self,
        delta: float,
        spot_price: float,
        contract_size: float = 0.001
    ) -> float:
        """
        Calculate delta in dollar terms
        
        Args:
            delta: Portfolio delta
            spot_price: Current spot price
            contract_size: BTC per contract (0.001 for Delta Exchange)
        
        Returns:
            Dollar delta exposure
        """
        btc_exposure = delta * contract_size
        dollar_exposure = btc_exposure * spot_price
        
        return dollar_exposure
    
    def estimate_pnl_on_move(
        self,
        greeks: Dict[str, float],
        spot_move: float,
        contract_size: float = 0.001
    ) -> Dict[str, float]:
        """
        Estimate P&L impact of spot price move
        
        Args:
            greeks: Portfolio Greeks
            spot_move: Expected spot price move ($)
            contract_size: BTC per contract
        
        Returns:
            {
                'delta_pnl': P&L from delta,
                'gamma_pnl': P&L from gamma (second order),
                'total_pnl': Combined estimate
            }
        """
        # First order: Delta P&L
        delta_pnl = greeks['delta'] * spot_move * contract_size
        
        # Second order: Gamma P&L
        # Gamma P&L = 0.5 × Gamma × (ΔS)²
        gamma_pnl = 0.5 * greeks['gamma'] * (spot_move ** 2) * contract_size
        
        total_pnl = delta_pnl + gamma_pnl
        
        return {
            'delta_pnl': delta_pnl,
            'gamma_pnl': gamma_pnl,
            'total_pnl': total_pnl
        }
```

---

## Module 3: Risk Validator

### **File:** `bot/strategy/zero_dte/risk_validator.py`

```python
"""
Risk validation for 0DTE trading
Pre-trade and runtime risk checks
"""
from typing import Dict, Any, Tuple, Optional
from loguru import logger

from bot.strategy.zero_dte.greeks_calculator import GreeksCalculator


class ZeroDTERiskValidator:
    """Validates risk limits for 0DTE trading"""
    
    def __init__(self, config):
        self.config = config
        self.greeks_calc = GreeksCalculator(config)
    
    def validate_entry(
        self,
        ce_lots: int,
        pe_lots: int,
        ce_premium: float,
        pe_premium: float
    ) -> Tuple[bool, str]:
        """
        Validate entry order
        
        Returns:
            (is_valid, error_message)
        """
        # Check lot limits
        if ce_lots > self.config.risk.position_limits.max_ce_lots:
            return False, f"CE lots {ce_lots} exceeds limit {self.config.risk.position_limits.max_ce_lots}"
        
        if pe_lots > self.config.risk.position_limits.max_pe_lots:
            return False, f"PE lots {pe_lots} exceeds limit {self.config.risk.position_limits.max_pe_lots}"
        
        total_lots = ce_lots + pe_lots
        if total_lots > self.config.risk.position_limits.max_total_lots:
            return False, f"Total lots {total_lots} exceeds limit {self.config.risk.position_limits.max_total_lots}"
        
        # Check premiums
        min_premium = self.config.entry.premium_range.min
        max_premium = self.config.entry.premium_range.max
        
        if not (min_premium <= ce_premium <= max_premium):
            return False, f"CE premium ₹{ce_premium} outside range ₹{min_premium}-₹{max_premium}"
        
        if not (min_premium <= pe_premium <= max_premium):
            return False, f"PE premium ₹{pe_premium} outside range ₹{min_premium}-₹{max_premium}"
        
        # Check premium balance
        tolerance_pct = self.config.entry.strike_selection.premium_tolerance / 100
        premium_diff = abs(ce_premium - pe_premium) / max(ce_premium, pe_premium)
        
        if premium_diff > tolerance_pct:
            return False, f"Premium imbalance {premium_diff*100:.1f}% exceeds tolerance {tolerance_pct*100}%"
        
        return True, ""
    
    def validate_rebalance(
        self,
        positions: Dict[str, Dict],
        additional_ce_lots: int = 0,
        additional_pe_lots: int = 0
    ) -> Tuple[bool, str]:
        """
        Validate rebalancing operation
        
        Returns:
            (is_valid, error_message)
        """
        ce_lots = positions.get('CE', {}).get('lots', 0) + additional_ce_lots
        pe_lots = positions.get('PE', {}).get('lots', 0) + additional_pe_lots
        
        # Check new lot counts against limits
        if ce_lots > self.config.risk.position_limits.max_ce_lots:
            return False, f"CE lots after rebalance {ce_lots} exceeds limit"
        
        if pe_lots > self.config.risk.position_limits.max_pe_lots:
            return False, f"PE lots after rebalance {pe_lots} exceeds limit"
        
        total_lots = ce_lots + pe_lots
        if total_lots > self.config.risk.position_limits.max_total_lots:
            return False, f"Total lots after rebalance {total_lots} exceeds limit"
        
        return True, ""
    
    def validate_greeks(
        self,
        ce_position: Dict,
        pe_position: Dict
    ) -> Tuple[bool, str]:
        """
        Validate portfolio Greeks
        
        Returns:
            (is_valid, error_message)
        """
        greeks = self.greeks_calc.calculate_portfolio_greeks(ce_position, pe_position)
        
        is_valid, msg = self.greeks_calc.check_greeks_limits(greeks)
        
        if not is_valid:
            logger.warning(f"Greeks limit violation: {msg}")
        
        return is_valid, msg
    
    def check_guardian_signal(self) -> Tuple[bool, str]:
        """
        Check Guardian risk signal
        
        Returns:
            (is_go, message)
        """
        if not self.config.risk.guardian.enabled:
            return True, "Guardian disabled"
        
        signal_file = self.config.risk.guardian.signal_file
        
        try:
            with open(signal_file, 'r') as f:
                signal = f.read().strip().upper()
            
            if signal == 'GO':
                return True, "Guardian: GO"
            else:
                return False, f"Guardian: {signal}"
                
        except FileNotFoundError:
            logger.warning(f"Guardian signal file not found: {signal_file}")
            return True, "Guardian file not found (allowing trade)"
        except Exception as e:
            logger.error(f"Error reading Guardian signal: {e}")
            return False, f"Guardian error: {str(e)}"
    
    async def validate_margin(
        self,
        margin_used: float,
        available_margin: float
    ) -> Tuple[bool, str]:
        """
        Validate margin utilization
        
        Returns:
            (is_safe, message)
        """
        total_margin = margin_used + available_margin
        if total_margin == 0:
            return True, "No margin data"
        
        utilization_pct = (margin_used / total_margin) * 100
        max_utilization = self.config.risk.margin.max_utilization_pct
        
        if utilization_pct > max_utilization:
            msg = f"Margin utilization {utilization_pct:.1f}% exceeds limit {max_utilization}%"
            logger.error(msg)
            return False, msg
        
        # Warning at 80% of limit
        warning_threshold = max_utilization * 0.8
        if utilization_pct > warning_threshold:
            logger.warning(f"Margin utilization {utilization_pct:.1f}% approaching limit")
        
        return True, f"Margin OK: {utilization_pct:.1f}%"
```

---

## Module 4: Alert System

### **File:** `bot/strategy/zero_dte/alerts.py`

```python
"""
Alert and notification system for 0DTE bot
"""
from typing import Dict, Any, List
from loguru import logger
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, config):
        self.config = config
        self.alert_history: List[Dict[str, Any]] = []
    
    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        session_id: str = None
    ):
        """
        Send alert via configured channels
        
        Args:
            level: Alert severity
            title: Alert title
            message: Alert message
            session_id: Associated session ID
        """
        alert = {
            'timestamp': logger._core.now(),
            'level': level.value,
            'title': title,
            'message': message,
            'session_id': session_id
        }
        
        self.alert_history.append(alert)
        
        # Log alert
        if level == AlertLevel.CRITICAL:
            logger.critical(f"🚨 {title}: {message}")
        elif level == AlertLevel.ERROR:
            logger.error(f"❌ {title}: {message}")
        elif level == AlertLevel.WARNING:
            logger.warning(f"⚠️ {title}: {message}")
        else:
            logger.info(f"ℹ️ {title}: {message}")
        
        # Send via configured channels
        if self.config.monitoring.alerts.telegram_enabled:
            self._send_telegram(alert)
        
        if self.config.monitoring.alerts.email_enabled:
            self._send_email(alert)
    
    def _send_telegram(self, alert: Dict):
        """Send Telegram notification"""
        # Implementation would use existing Telegram bot
        pass
    
    def _send_email(self, alert: Dict):
        """Send email notification"""
        # Implementation would use email service
        pass
    
    def get_recent_alerts(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        return self.alert_history[-count:]
```

---

**Continue to:** [ZERO_DTE_PHASE3_WEBUI.md](ZERO_DTE_PHASE3_WEBUI.md) for frontend implementation details.
