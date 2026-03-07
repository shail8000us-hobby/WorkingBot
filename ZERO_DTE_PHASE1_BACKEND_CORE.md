# Phase 1: Backend Core Engine Implementation

**Duration:** 2-3 weeks  
**Deliverables:** Working 0DTE engine, premium balancer, strike rollover, state management

---

## 📋 Phase 1 Overview

This phase builds the foundational backend infrastructure for the 0DTE bot. The core engine orchestrates the entire trading lifecycle from entry to exit, with premium balancing and strike rollover logic operating independently.

**Key Principle:** Build modular, testable components that can run independently before integration.

---

## 🎯 Phase 1 Objectives

1. ✅ Core engine that manages session lifecycle
2. ✅ Premium balancer that maintains CE/PE parity
3. ✅ Strike rollover manager for <₹5 premium handling
4. ✅ State manager for persistence and recovery
5. ✅ Configuration system for strategy parameters
6. ✅ Database schema and migration scripts

---

## 📁 Module 1: Configuration System

### **File:** `config/zero_dte_config.yaml`

```yaml
zero_dte:
  # Trading parameters
  trading:
    underlying: "BTC"                    # 'BTC' or 'ETH'
    initial_lot_size: 5                  # Starting lot size per leg
    
  # Entry conditions
  entry:
    premium_range:
      min: 15                            # Minimum premium per leg (₹)
      max: 30                            # Maximum premium per leg (₹)
    
    strike_selection:
      offset_pct: 2.5                    # % away from ATM (2.5% = ±2.5%)
      premium_tolerance: 10              # % difference allowed between CE and PE
    
    liquidity:
      max_spread_pct: 5                  # Maximum bid-ask spread %
      min_volume: 10                     # Minimum volume threshold
    
    time_window:
      enabled: false                     # Manual start (no time window)
      start_time: "10:00"                # IST time (if enabled)
      end_time: "13:00"                  # IST time (if enabled)
  
  # Rebalancing logic
  rebalancing:
    enabled: true
    check_interval_seconds: 30           # How often to check imbalance
    threshold_pct: 20                    # Trigger rebalance at 20% imbalance
    
    # Lot adjustment strategy
    adjustment:
      method: "incremental"              # 'incremental' or 'full_hedge'
      min_lot_adjustment: 1              # Minimum lots to add
      max_lot_adjustment: 10             # Maximum lots in single rebalance
    
    # Order execution
    orders:
      preference: "maker_first"          # 'maker_first', 'maker_only', 'market_only'
      timeout_seconds: 2                 # Timeout before fallback to market
      retry_attempts: 3                  # Retry failed orders
  
  # Strike rollover
  rollover:
    enabled: true
    trigger_premium: 5                   # Roll when premium < ₹5
    target_premium: 22                   # Target premium after roll (₹20-25 range)
    
    # New strike selection
    new_strike:
      selection_method: "nearest_premium"  # 'nearest_premium' or 'fixed_offset'
      premium_tolerance: 20                # ±20% from target premium
      max_strike_distance_pct: 10          # Max 10% away from spot
    
    # Execution strategy
    execution:
      close_old_first: true                # Close old leg before opening new
      verify_fill: true                    # Verify new leg filled before confirming
      rollback_on_failure: true            # Reopen old leg if new leg fails
  
  # Exit conditions
  exit:
    # Profit target
    profit_target:
      enabled: true
      both_legs_below: 5                 # Exit when both CE and PE < ₹5
      time_based_adjustment: true        # Tighten target near expiry
    
    # Stop loss
    stop_loss:
      enabled: true
      max_loss_amount: 5000              # Maximum loss in ₹
      max_loss_multiple: 3               # Max loss = 3× collected premium
    
    # Time-based exit
    time_exit:
      enabled: true
      forced_exit_time: "17:15"          # Exit at 5:15 PM IST (15 min before settlement)
      settlement_time: "17:30"           # Delta Exchange settlement at 5:30 PM IST
      timezone: "Asia/Kolkata"           # IST
    
    # Liquidity-based exit
    liquidity_exit:
      enabled: true
      max_spread_pct: 10                 # Exit if spread > 10%
      check_start_time: "17:00"          # Start checking at 5:00 PM
  
  # Risk management
  risk:
    # Position limits
    position_limits:
      max_ce_lots: 20                    # Maximum CE lots
      max_pe_lots: 20                    # Maximum PE lots
      max_total_lots: 30                 # Maximum combined lots
    
    # Margin controls
    margin:
      max_utilization_pct: 75            # Halt if margin > 75%
      buffer_multiplier: 3               # Recommended capital = 3× margin
    
    # Greeks limits
    greeks:
      max_portfolio_delta: 0.5           # Max ±0.5 BTC delta exposure
      max_portfolio_gamma: 0.01          # Max gamma exposure
      monitor_interval_seconds: 30       # Greeks check frequency
    
    # Guardian integration
    guardian:
      enabled: true                      # Use Guardian risk signal
      halt_on_stop: true                 # Stop trading on STOP signal
      signal_file: "guardian_signal.txt" # Guardian signal file path
  
  # Monitoring & logging
  monitoring:
    snapshot_interval_seconds: 30        # Save monitoring snapshots
    log_level: "INFO"                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Alerts
    alerts:
      telegram_enabled: false            # Send Telegram alerts
      email_enabled: false               # Send email alerts
      
      # Alert triggers
      triggers:
        - "rebalance_executed"
        - "strike_rollover"
        - "stop_loss_approached"
        - "forced_exit"
        - "error_occurred"
  
  # Database settings
  database:
    sessions_db: "database/zero_dte_sessions.db"
    trades_db: "database/zero_dte_trades.db"
    rebalances_db: "database/zero_dte_rebalances.db"
    
    # Auto-save frequency
    autosave_interval_seconds: 10
    
    # Retention policy
    retention:
      monitoring_snapshots_days: 7       # Keep snapshots for 7 days
      trade_history_days: 30             # Keep trades for 30 days
      session_history_days: 90           # Keep sessions for 90 days
```

### **File:** `config/schemas/zero_dte_schemas.py`

```python
"""
Pydantic schemas for 0DTE configuration validation
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import time

class PremiumRange(BaseModel):
    min: float = Field(..., ge=5, le=50, description="Minimum premium")
    max: float = Field(..., ge=10, le=100, description="Maximum premium")
    
    @validator('max')
    def max_must_exceed_min(cls, v, values):
        if 'min' in values and v <= values['min']:
            raise ValueError('max must be greater than min')
        return v


class StrikeSelection(BaseModel):
    offset_pct: float = Field(..., ge=0, le=10, description="Strike offset %")
    premium_tolerance: float = Field(..., ge=0, le=50, description="Premium tolerance %")


class LiquidityFilters(BaseModel):
    max_spread_pct: float = Field(..., ge=0, le=20, description="Max bid-ask spread %")
    min_volume: int = Field(..., ge=0, description="Minimum volume")


class TimeWindow(BaseModel):
    enabled: bool = False
    start_time: Optional[str] = Field(None, regex=r'^\d{2}:\d{2}$')
    end_time: Optional[str] = Field(None, regex=r'^\d{2}:\d{2}$')


class EntryConfig(BaseModel):
    premium_range: PremiumRange
    strike_selection: StrikeSelection
    liquidity: LiquidityFilters
    time_window: TimeWindow


class RebalancingAdjustment(BaseModel):
    method: Literal['incremental', 'full_hedge'] = 'incremental'
    min_lot_adjustment: int = Field(..., ge=1)
    max_lot_adjustment: int = Field(..., ge=1)


class OrderExecution(BaseModel):
    preference: Literal['maker_first', 'maker_only', 'market_only'] = 'maker_first'
    timeout_seconds: int = Field(..., ge=1, le=10)
    retry_attempts: int = Field(..., ge=0, le=5)


class RebalancingConfig(BaseModel):
    enabled: bool = True
    check_interval_seconds: int = Field(..., ge=10, le=300)
    threshold_pct: float = Field(..., ge=5, le=50)
    adjustment: RebalancingAdjustment
    orders: OrderExecution


class NewStrikeSelection(BaseModel):
    selection_method: Literal['nearest_premium', 'fixed_offset'] = 'nearest_premium'
    premium_tolerance: float = Field(..., ge=0, le=50)
    max_strike_distance_pct: float = Field(..., ge=0, le=20)


class RolloverExecution(BaseModel):
    close_old_first: bool = True
    verify_fill: bool = True
    rollback_on_failure: bool = True


class RolloverConfig(BaseModel):
    enabled: bool = True
    trigger_premium: float = Field(..., ge=1, le=10)
    target_premium: float = Field(..., ge=10, le=50)
    new_strike: NewStrikeSelection
    execution: RolloverExecution


class ProfitTarget(BaseModel):
    enabled: bool = True
    both_legs_below: float = Field(..., ge=1, le=10)
    time_based_adjustment: bool = True


class StopLoss(BaseModel):
    enabled: bool = True
    max_loss_amount: float = Field(..., ge=0)
    max_loss_multiple: float = Field(..., ge=1, le=10)


class TimeExit(BaseModel):
    enabled: bool = True
    forced_exit_time: str = Field(..., regex=r'^\d{2}:\d{2}$')
    settlement_time: str = Field(..., regex=r'^\d{2}:\d{2}$')
    timezone: str = 'Asia/Kolkata'


class LiquidityExit(BaseModel):
    enabled: bool = True
    max_spread_pct: float = Field(..., ge=0, le=50)
    check_start_time: str = Field(..., regex=r'^\d{2}:\d{2}$')


class ExitConfig(BaseModel):
    profit_target: ProfitTarget
    stop_loss: StopLoss
    time_exit: TimeExit
    liquidity_exit: LiquidityExit


class PositionLimits(BaseModel):
    max_ce_lots: int = Field(..., ge=1)
    max_pe_lots: int = Field(..., ge=1)
    max_total_lots: int = Field(..., ge=2)


class MarginControls(BaseModel):
    max_utilization_pct: float = Field(..., ge=0, le=100)
    buffer_multiplier: float = Field(..., ge=1, le=10)


class GreeksLimits(BaseModel):
    max_portfolio_delta: float = Field(..., ge=0)
    max_portfolio_gamma: float = Field(..., ge=0)
    monitor_interval_seconds: int = Field(..., ge=10)


class GuardianIntegration(BaseModel):
    enabled: bool = True
    halt_on_stop: bool = True
    signal_file: str = 'guardian_signal.txt'


class RiskConfig(BaseModel):
    position_limits: PositionLimits
    margin: MarginControls
    greeks: GreeksLimits
    guardian: GuardianIntegration


class TradingParams(BaseModel):
    underlying: Literal['BTC', 'ETH'] = 'BTC'
    initial_lot_size: int = Field(..., ge=1, le=20)


class ZeroDTEConfig(BaseModel):
    """Complete 0DTE configuration"""
    trading: TradingParams
    entry: EntryConfig
    rebalancing: RebalancingConfig
    rollover: RolloverConfig
    exit: ExitConfig
    risk: RiskConfig
    
    class Config:
        validate_assignment = True


def load_zero_dte_config(config_path: str = 'config/zero_dte_config.yaml') -> ZeroDTEConfig:
    """Load and validate 0DTE configuration from YAML"""
    import yaml
    
    with open(config_path, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    return ZeroDTEConfig(**raw_config['zero_dte'])
```

---

## 📁 Module 2: State Manager

### **File:** `bot/strategy/zero_dte/state_manager.py`

```python
"""
State management for 0DTE sessions with persistence and recovery
"""
import sqlite3
import json
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger

class StateManager:
    """Manages session state with SQLite persistence"""
    
    def __init__(self, db_path: str = 'database/zero_dte_sessions.db'):
        self.db_path = db_path
        self._current_session: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                underlying TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                entry_ce_strike REAL NOT NULL,
                entry_pe_strike REAL NOT NULL,
                entry_ce_premium REAL NOT NULL,
                entry_pe_premium REAL NOT NULL,
                entry_ce_lots INTEGER NOT NULL,
                entry_pe_lots INTEGER NOT NULL,
                current_ce_strike REAL,
                current_pe_strike REAL,
                current_ce_lots INTEGER,
                current_pe_lots INTEGER,
                total_premium_collected REAL,
                total_premium_paid REAL,
                realized_pnl REAL,
                unrealized_pnl REAL,
                total_rebalances INTEGER DEFAULT 0,
                total_rollovers INTEGER DEFAULT 0,
                stop_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                leg_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                strike REAL NOT NULL,
                lots INTEGER NOT NULL,
                entry_premium REAL NOT NULL,
                current_premium REAL,
                unrealized_pnl REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL,
                iv REAL,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"State database initialized: {self.db_path}")
    
    def create_session(self, session_data: Dict[str, Any]) -> str:
        """Create new trading session"""
        with self._lock:
            session_id = self._generate_session_id(
                session_data['underlying'],
                session_data['expiry_date']
            )
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sessions (
                    session_id, underlying, expiry_date, status, start_time,
                    entry_ce_strike, entry_pe_strike, entry_ce_premium, entry_pe_premium,
                    entry_ce_lots, entry_pe_lots, current_ce_strike, current_pe_strike,
                    current_ce_lots, current_pe_lots, total_premium_collected, total_premium_paid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                session_data['underlying'],
                session_data['expiry_date'],
                'active',
                datetime.now().isoformat(),
                session_data['entry_ce_strike'],
                session_data['entry_pe_strike'],
                session_data['entry_ce_premium'],
                session_data['entry_pe_premium'],
                session_data['entry_ce_lots'],
                session_data['entry_pe_lots'],
                session_data['entry_ce_strike'],
                session_data['entry_pe_strike'],
                session_data['entry_ce_lots'],
                session_data['entry_pe_lots'],
                session_data['total_premium_collected'],
                0.0
            ))
            
            conn.commit()
            conn.close()
            
            self._current_session = self.get_session(session_id)
            logger.info(f"Session created: {session_id}")
            return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Get currently active session"""
        if self._current_session and self._current_session['status'] == 'active':
            return self._current_session
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sessions WHERE status = ? ORDER BY start_time DESC LIMIT 1', ('active',))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self._current_session = dict(row)
            return self._current_session
        return None
    
    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Update session fields"""
        with self._lock:
            if not updates:
                return
            
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            set_clause += ', updated_at = ?'
            values = list(updates.values()) + [datetime.now().isoformat(), session_id]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f'UPDATE sessions SET {set_clause} WHERE session_id = ?', values)
            conn.commit()
            conn.close()
            
            # Update in-memory cache
            if self._current_session and self._current_session['session_id'] == session_id:
                self._current_session.update(updates)
            
            logger.debug(f"Session updated: {session_id} - {updates}")
    
    def close_session(self, session_id: str, stop_reason: str, final_pnl: float):
        """Close session"""
        updates = {
            'status': 'closed',
            'end_time': datetime.now().isoformat(),
            'stop_reason': stop_reason,
            'realized_pnl': final_pnl
        }
        self.update_session(session_id, updates)
        
        if self._current_session and self._current_session['session_id'] == session_id:
            self._current_session = None
        
        logger.info(f"Session closed: {session_id} | Reason: {stop_reason} | P&L: ₹{final_pnl}")
    
    def save_position(self, session_id: str, position_data: Dict[str, Any]):
        """Save or update position"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if position exists
            cursor.execute('''
                SELECT id FROM current_positions 
                WHERE session_id = ? AND leg_type = ?
            ''', (session_id, position_data['leg_type']))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute('''
                    UPDATE current_positions SET
                        symbol = ?, strike = ?, lots = ?, current_premium = ?,
                        unrealized_pnl = ?, delta = ?, gamma = ?, theta = ?, vega = ?, iv = ?,
                        last_updated = ?
                    WHERE session_id = ? AND leg_type = ?
                ''', (
                    position_data['symbol'],
                    position_data['strike'],
                    position_data['lots'],
                    position_data.get('current_premium'),
                    position_data.get('unrealized_pnl'),
                    position_data.get('delta'),
                    position_data.get('gamma'),
                    position_data.get('theta'),
                    position_data.get('vega'),
                    position_data.get('iv'),
                    datetime.now().isoformat(),
                    session_id,
                    position_data['leg_type']
                ))
            else:
                # Insert new
                cursor.execute('''
                    INSERT INTO current_positions (
                        session_id, leg_type, symbol, strike, lots, entry_premium,
                        current_premium, unrealized_pnl, delta, gamma, theta, vega, iv
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    position_data['leg_type'],
                    position_data['symbol'],
                    position_data['strike'],
                    position_data['lots'],
                    position_data['entry_premium'],
                    position_data.get('current_premium'),
                    position_data.get('unrealized_pnl'),
                    position_data.get('delta'),
                    position_data.get('gamma'),
                    position_data.get('theta'),
                    position_data.get('vega'),
                    position_data.get('iv')
                ))
            
            conn.commit()
            conn.close()
    
    def get_positions(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        """Get current CE and PE positions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM current_positions WHERE session_id = ?', (session_id,))
        rows = cursor.fetchall()
        conn.close()
        
        positions = {}
        for row in rows:
            leg_type = row['leg_type']
            positions[leg_type] = dict(row)
        
        return positions
    
    def increment_counter(self, session_id: str, counter_name: str):
        """Increment rebalance or rollover counter"""
        valid_counters = ['total_rebalances', 'total_rollovers']
        if counter_name not in valid_counters:
            raise ValueError(f"Invalid counter: {counter_name}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f'UPDATE sessions SET {counter_name} = {counter_name} + 1 WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
    
    def _generate_session_id(self, underlying: str, expiry_date: str) -> str:
        """Generate unique session ID"""
        from hashlib import md5
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        hash_input = f"{underlying}{expiry_date}{timestamp}"
        hash_suffix = md5(hash_input.encode()).hexdigest()[:6]
        return f"0dte_{underlying}_{expiry_date.replace('-', '')}_{hash_suffix}"


# Singleton instance
_state_manager_instance = None

def get_state_manager() -> StateManager:
    """Get singleton StateManager instance"""
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager()
    return _state_manager_instance
```

---

## 📁 Module 3: Core Engine (Part 1 - Initialization & Entry)

### **File:** `bot/strategy/zero_dte/engine.py` (Part 1/3)

```python
"""
Zero DTE Trading Engine - Main Orchestrator
Manages session lifecycle from entry to exit
"""
import asyncio
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, time as dt_time
from loguru import logger
import pytz

from bot.api.unified_api_client import UnifiedAPIClient
from bot.strategy.options.options_helper import check_liquidity, calculate_unrealized_pnl
from bot.strategy.zero_dte.state_manager import get_state_manager
from bot.strategy.zero_dte.config import load_zero_dte_config
from bot.strategy.zero_dte.balancer import PremiumBalancer
from bot.strategy.zero_dte.rollover import StrikeRolloverManager


class ZeroDTEEngine:
    """Main 0DTE trading engine"""
    
    def __init__(self, api_client: UnifiedAPIClient):
        self.api_client = api_client
        self.config = load_zero_dte_config()
        self.state_manager = get_state_manager()
        self.balancer = PremiumBalancer(api_client, self.config)
        self.rollover_manager = StrikeRolloverManager(api_client, self.config)
        
        self.session_id: Optional[str] = None
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("ZeroDTEEngine initialized")
    
    async def start_session(
        self,
        underlying: str = 'BTC',
        expiry_date: Optional[str] = None,
        initial_lots: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Start new 0DTE trading session
        
        Args:
            underlying: 'BTC' or 'ETH'
            expiry_date: 'YYYY-MM-DD' (auto-detect if None)
            initial_lots: Lot size (use config default if None)
        
        Returns:
            Session creation summary
        """
        if self.is_running:
            raise RuntimeError("Session already active")
        
        logger.info(f"Starting 0DTE session for {underlying}")
        
        # Get configuration
        initial_lots = initial_lots or self.config.trading.initial_lot_size
        
        # Auto-detect today's 0DTE expiry
        if not expiry_date:
            expiry_date = self._get_today_expiry_date()
        
        # Validate entry time window (if enabled)
        if self.config.entry.time_window.enabled:
            if not self._is_within_entry_window():
                raise RuntimeError("Outside entry time window")
        
        # Fetch option chain
        logger.info(f"Fetching option chain for {underlying} expiry {expiry_date}")
        option_chain = await self._fetch_option_chain(underlying, expiry_date)
        
        # Select strikes
        ce_strike, pe_strike = await self._select_strikes(underlying, option_chain)
        logger.info(f"Selected strikes: CE={ce_strike}, PE={pe_strike}")
        
        # Get premiums and validate
        ce_premium, ce_symbol = await self._get_premium_and_symbol(underlying, ce_strike, expiry_date, 'call')
        pe_premium, pe_symbol = await self._get_premium_and_symbol(underlying, pe_strike, expiry_date, 'put')
        
        logger.info(f"CE premium: ₹{ce_premium} | PE premium: ₹{pe_premium}")
        
        # Validate premiums in range
        if not self._validate_premiums(ce_premium, pe_premium):
            raise ValueError(f"Premiums outside target range (₹{self.config.entry.premium_range.min}-₹{self.config.entry.premium_range.max})")
        
        # Validate liquidity
        await self._validate_liquidity(ce_symbol, pe_symbol)
        
        # Check Guardian signal
        if self.config.risk.guardian.enabled:
            if not self._check_guardian_signal():
                raise RuntimeError("Guardian signal is STOP - cannot start session")
        
        # Execute entry orders
        logger.info(f"Placing entry orders: {initial_lots} lots each")
        ce_fill_premium = await self._place_sell_order(ce_symbol, initial_lots)
        pe_fill_premium = await self._place_sell_order(pe_symbol, initial_lots)
        
        logger.info(f"Orders filled: CE @ ₹{ce_fill_premium}, PE @ ₹{pe_fill_premium}")
        
        # Calculate total premium collected
        total_premium = (ce_fill_premium * initial_lots) + (pe_fill_premium * initial_lots)
        
        # Create session state
        session_data = {
            'underlying': underlying,
            'expiry_date': expiry_date,
            'entry_ce_strike': ce_strike,
            'entry_pe_strike': pe_strike,
            'entry_ce_premium': ce_fill_premium,
            'entry_pe_premium': pe_fill_premium,
            'entry_ce_lots': initial_lots,
            'entry_pe_lots': initial_lots,
            'total_premium_collected': total_premium
        }
        
        self.session_id = self.state_manager.create_session(session_data)
        
        # Save positions
        self.state_manager.save_position(self.session_id, {
            'leg_type': 'CE',
            'symbol': ce_symbol,
            'strike': ce_strike,
            'lots': initial_lots,
            'entry_premium': ce_fill_premium,
            'current_premium': ce_fill_premium
        })
        
        self.state_manager.save_position(self.session_id, {
            'leg_type': 'PE',
            'symbol': pe_symbol,
            'strike': pe_strike,
            'lots': initial_lots,
            'entry_premium': pe_fill_premium,
            'current_premium': pe_fill_premium
        })
        
        # Start monitoring loop
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        
        logger.success(f"✅ Session started: {self.session_id} | Premium collected: ₹{total_premium}")
        
        return {
            'session_id': self.session_id,
            'underlying': underlying,
            'expiry_date': expiry_date,
            'entry_summary': {
                'ce_strike': ce_strike,
                'pe_strike': pe_strike,
                'ce_premium': ce_fill_premium,
                'pe_premium': pe_fill_premium,
                'ce_lots': initial_lots,
                'pe_lots': initial_lots,
                'total_premium_collected': total_premium
            }
        }
    
    def _get_today_expiry_date(self) -> str:
        """Get today's date in YYYY-MM-DD format for 0DTE"""
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist).date()
        return today.strftime('%Y-%m-%d')
    
    def _is_within_entry_window(self) -> bool:
        """Check if current time is within entry window"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist).time()
        
        start_time = dt_time.fromisoformat(self.config.entry.time_window.start_time)
        end_time = dt_time.fromisoformat(self.config.entry.time_window.end_time)
        
        return start_time <= now <= end_time
    
    async def _fetch_option_chain(self, underlying: str, expiry_date: str) -> Dict[str, Any]:
        """Fetch full option chain from Delta Exchange"""
        try:
            # Use UnifiedAPIClient method
            chain_data = await self.api_client.get_option_chain(
                underlying_asset=underlying,
                expiry_date=expiry_date
            )
            
            if not chain_data:
                raise ValueError(f"No option chain data for {underlying} expiry {expiry_date}")
            
            return chain_data
            
        except Exception as e:
            logger.error(f"Failed to fetch option chain: {e}")
            raise
    
    async def _select_strikes(self, underlying: str, option_chain: Dict[str, Any]) -> Tuple[float, float]:
        """
        Select CE and PE strikes with approximately equal premiums
        
        Returns:
            (ce_strike, pe_strike)
        """
        # Get current spot price
        spot_price = await self.api_client.get_current_price(f"{underlying}USD")
        logger.info(f"Current {underlying} spot: ${spot_price}")
        
        offset_pct = self.config.entry.strike_selection.offset_pct / 100
        tolerance_pct = self.config.entry.strike_selection.premium_tolerance / 100
        
        # Calculate target strikes
        ce_target_strike = spot_price * (1 + offset_pct)
        pe_target_strike = spot_price * (1 - offset_pct)
        
        # Find nearest strikes in chain
        ce_strike = self._find_nearest_strike(option_chain['calls'], ce_target_strike)
        pe_strike = self._find_nearest_strike(option_chain['puts'], pe_target_strike)
        
        # Get premiums and verify balance
        ce_premium = option_chain['calls'][ce_strike]['mark_price']
        pe_premium = option_chain['puts'][pe_strike]['mark_price']
        
        premium_diff_pct = abs(ce_premium - pe_premium) / max(ce_premium, pe_premium)
        
        if premium_diff_pct > tolerance_pct:
            logger.warning(f"Premium imbalance: CE=₹{ce_premium}, PE=₹{pe_premium} ({premium_diff_pct*100:.1f}%)")
            # Try to find better strikes
            ce_strike, pe_strike = self._adjust_strikes_for_balance(
                option_chain, spot_price, ce_premium, pe_premium
            )
        
        return ce_strike, pe_strike
    
    def _find_nearest_strike(self, strikes_data: Dict, target_strike: float) -> float:
        """Find nearest strike to target"""
        available_strikes = [float(s) for s in strikes_data.keys()]
        nearest = min(available_strikes, key=lambda x: abs(x - target_strike))
        return nearest
    
    def _adjust_strikes_for_balance(
        self,
        option_chain: Dict,
        spot_price: float,
        current_ce_premium: float,
        current_pe_premium: float
    ) -> Tuple[float, float]:
        """
        Adjust strikes to better balance CE and PE premiums
        (Implementation details in actual code)
        """
        # Find strikes where premiums are closest
        # This is a placeholder - full implementation would iterate through strikes
        logger.info("Adjusting strikes for premium balance...")
        
        # For now, return ATM strikes
        calls = option_chain['calls']
        puts = option_chain['puts']
        
        ce_strike = self._find_nearest_strike(calls, spot_price)
        pe_strike = self._find_nearest_strike(puts, spot_price)
        
        return ce_strike, pe_strike
    
    async def _get_premium_and_symbol(
        self,
        underlying: str,
        strike: float,
        expiry_date: str,
        option_type: str
    ) -> Tuple[float, str]:
        """
        Get premium and symbol for option
        
        Returns:
            (premium, symbol)
        """
        # Format symbol: C-BTC-95000-30012026
        type_prefix = 'C' if option_type == 'call' else 'P'
        expiry_formatted = datetime.strptime(expiry_date, '%Y-%m-%d').strftime('%d%m%Y')
        symbol = f"{type_prefix}-{underlying}-{int(strike)}-{expiry_formatted}"
        
        # Get ticker data
        ticker = await self.api_client.get_option_ticker(symbol)
        premium = ticker['mark_price']
        
        return premium, symbol
    
    def _validate_premiums(self, ce_premium: float, pe_premium: float) -> bool:
        """Validate premiums are in acceptable range"""
        min_prem = self.config.entry.premium_range.min
        max_prem = self.config.entry.premium_range.max
        
        if not (min_prem <= ce_premium <= max_prem):
            logger.warning(f"CE premium ₹{ce_premium} outside range ₹{min_prem}-₹{max_prem}")
            return False
        
        if not (min_prem <= pe_premium <= max_prem):
            logger.warning(f"PE premium ₹{pe_premium} outside range ₹{min_prem}-₹{max_prem}")
            return False
        
        return True
    
    async def _validate_liquidity(self, ce_symbol: str, pe_symbol: str):
        """Validate liquidity of both legs"""
        for symbol in [ce_symbol, pe_symbol]:
            ticker = await self.api_client.get_option_ticker(symbol)
            liquidity_check = check_liquidity(ticker)
            
            if not liquidity_check['is_liquid']:
                raise ValueError(f"{symbol} has poor liquidity: {liquidity_check['spread_pct']:.1f}% spread")
    
    def _check_guardian_signal(self) -> bool:
        """Check Guardian signal file"""
        signal_file = self.config.risk.guardian.signal_file
        try:
            with open(signal_file, 'r') as f:
                signal = f.read().strip().upper()
                return signal == 'GO'
        except FileNotFoundError:
            logger.warning(f"Guardian signal file not found: {signal_file}")
            return True  # Allow trading if file doesn't exist
    
    async def _place_sell_order(self, symbol: str, lots: int) -> float:
        """
        Place sell order (short option)
        
        Returns:
            Fill premium
        """
        order_pref = self.config.rebalancing.orders.preference
        timeout = self.config.rebalancing.orders.timeout_seconds
        
        logger.info(f"Placing SELL order: {symbol} × {lots} lots ({order_pref})")
        
        if order_pref == 'maker_first':
            # Try limit order first
            ticker = await self.api_client.get_option_ticker(symbol)
            limit_price = ticker['mark_price']
            
            order = await self.api_client.place_order(
                symbol=symbol,
                side='sell',
                size=lots,
                order_type='limit_order',
                limit_price=limit_price,
                reduce_only=False
            )
            
            # Wait for fill
            await asyncio.sleep(timeout)
            
            order_status = await self.api_client.get_order(order['id'])
            
            if order_status['state'] == 'filled':
                fill_price = order_status['average_fill_price']
                logger.info(f"✅ Limit order filled @ ₹{fill_price}")
                return fill_price
            
            # Cancel and fallback to market
            logger.info("Limit order not filled, cancelling and using market order")
            await self.api_client.cancel_order(order['id'])
        
        # Market order
        order = await self.api_client.place_order(
            symbol=symbol,
            side='sell',
            size=lots,
            order_type='market_order',
            reduce_only=False
        )
        
        # Get fill price
        await asyncio.sleep(1)  # Wait for fill
        order_status = await self.api_client.get_order(order['id'])
        fill_price = order_status['average_fill_price']
        
        logger.info(f"✅ Market order filled @ ₹{fill_price}")
        return fill_price
```

**Continue to next comment for Part 2 & 3 of engine.py...**

---

## Module 3 continues in ZERO_DTE_PHASE1_BACKEND_CORE_PART2.md

**Next:** See [ZERO_DTE_PHASE1_BACKEND_CORE_PART2.md](ZERO_DTE_PHASE1_BACKEND_CORE_PART2.md) for:
- Monitoring loop
- Exit logic
- Premium balancer
- Strike rollover manager
