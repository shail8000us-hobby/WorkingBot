"""
Strategy Manager
================
CRUD operations and persistence for options strategies.

Storage: SQLite database for persistence
State: In-memory tracking for active strategies

Created: January 5, 2026
"""

import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from threading import Lock

from .strategy_models import (
    Strategy, StrategyLeg, StrategyStatus, LegStatus,
    StrategyType
)
from .strategy_definitions import StrategyDefinitions
from .leg_executor import LegExecutor

# MV Straddle imports
from .strategies.mv_straddle_strategy import MVStraddleStrategy
from .mv_straddle.volatility_analyzer import VolatilityAnalyzer
from .mv_straddle.strike_selector import StrikeSelector
from .mv_straddle.breakeven_calculator import BreakevenCalculator
from .mv_straddle.position_adjuster import PositionAdjuster

log = logging.getLogger(__name__)


class StrategyManager:
    """
    Manage strategy lifecycle
    
    Features:
    - Create strategies from templates
    - Persist to SQLite
    - Track active strategies
    - Calculate P&L
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._db_path = Path(__file__).parent / "strategies.db"
        self._active_strategies: Dict[str, Strategy] = {}
        self._executor = LegExecutor()
        
        # Initialize MV Straddle components
        try:
            # Get API client and chain service from existing imports
            from ...bot.api.unified_api_client import UnifiedAPIClient
            from ..options_chain.chain_service import ChainService
            
            self._api_client = UnifiedAPIClient()
            self._chain_service = ChainService()
            
            # Initialize MV Straddle utilities
            self._volatility_analyzer = VolatilityAnalyzer(self._api_client)
            self._strike_selector = StrikeSelector(self._chain_service)
            self._breakeven_calculator = BreakevenCalculator()
            self._position_adjuster = PositionAdjuster(self._api_client, self)
            
            # Initialize MV Straddle strategy
            self._mv_straddle = MVStraddleStrategy(
                api_client=self._api_client,
                chain_service=self._chain_service,
                volatility_analyzer=self._volatility_analyzer,
                strike_selector=self._strike_selector
            )
            
            log.info("✅ MV Straddle components initialized")
        except Exception as e:
            log.warning(f"⚠️ MV Straddle initialization skipped: {e}")
            self._mv_straddle = None
        
        self._init_db()
        self._load_active_strategies()
        self._initialized = True
        
        log.info(f"📊 StrategyManager initialized, DB: {self._db_path}")
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # Strategies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                strategy_type TEXT NOT NULL,
                underlying TEXT NOT NULL,
                expiry TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                legs_json TEXT NOT NULL,
                entry_conditions_json TEXT,
                exit_conditions_json TEXT,
                total_cost REAL,
                current_pnl REAL,
                created_at TEXT NOT NULL,
                executed_at TEXT,
                closed_at TEXT,
                notes TEXT
            )
        ''')
        
        # Execution history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details_json TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _load_active_strategies(self):
        """Load non-closed strategies into memory"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM strategies 
            WHERE status NOT IN ('closed', 'expired', 'failed')
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            try:
                strategy = self._row_to_strategy(dict(row))
                self._active_strategies[strategy.id] = strategy
                log.info(f"  Loaded: {strategy.name} ({strategy.status})")
            except Exception as e:
                log.error(f"  Failed to load strategy {row['id']}: {e}")
        
        log.info(f"  Loaded {len(self._active_strategies)} active strategies")
    
    def _row_to_strategy(self, row: Dict) -> Strategy:
        """Convert DB row to Strategy object"""
        legs_data = json.loads(row['legs_json'])
        legs = [StrategyLeg(**leg) for leg in legs_data]
        
        strategy = Strategy(
            id=row['id'],
            name=row['name'],
            strategy_type=row['strategy_type'],
            underlying=row['underlying'],
            expiry=row['expiry'],
            legs=legs,
            status=row['status'],
            total_cost=row.get('total_cost'),
            current_pnl=row.get('current_pnl'),
            created_at=row['created_at'],
            executed_at=row.get('executed_at'),
            closed_at=row.get('closed_at'),
            notes=row.get('notes')
        )
        
        # Load conditions if present
        if row.get('entry_conditions_json'):
            from .strategy_models import EntryConditions
            strategy.entry_conditions = EntryConditions(**json.loads(row['entry_conditions_json']))
        
        if row.get('exit_conditions_json'):
            from .strategy_models import ExitConditions
            strategy.exit_conditions = ExitConditions(**json.loads(row['exit_conditions_json']))
        
        return strategy
    
    def _strategy_to_row(self, strategy: Strategy) -> Dict:
        """Convert Strategy to DB row dict"""
        legs_data = [leg.to_dict() for leg in strategy.legs]
        
        row = {
            'id': strategy.id,
            'name': strategy.name,
            'strategy_type': strategy.strategy_type,
            'underlying': strategy.underlying,
            'expiry': strategy.expiry,
            'status': strategy.status,
            'legs_json': json.dumps(legs_data),
            'total_cost': strategy.total_cost,
            'current_pnl': strategy.current_pnl,
            'created_at': strategy.created_at,
            'executed_at': strategy.executed_at,
            'closed_at': strategy.closed_at,
            'notes': strategy.notes
        }
        
        if strategy.entry_conditions:
            row['entry_conditions_json'] = json.dumps(strategy.entry_conditions.to_dict())
        
        if strategy.exit_conditions:
            row['exit_conditions_json'] = json.dumps(strategy.exit_conditions.to_dict())
        
        return row
    
    # ==================== CREATE Operations ====================
    
    def create_strategy(
        self,
        strategy_type: str,
        underlying: str = "BTC",
        expiry: str = None,
        params: Dict = None
    ) -> Strategy:
        """
        Create a new strategy from template
        
        Args:
            strategy_type: straddle, strangle, iron_condor, etc.
            underlying: BTC, ETH
            expiry: DDMMYYYY format (from options-chain API) or DDMMYY
            params: Type-specific parameters (strikes, deltas, etc.)
            
        Returns:
            Configured Strategy (not executed)
        """
        params = params or {}
        
        # Convert expiry to Delta Exchange format (DDMMYY) if needed
        if expiry and len(expiry) == 8:
            # DDMMYYYY -> DDMMYY (take DD, MM, and last 2 digits of year)
            expiry_formatted = expiry[0:4] + expiry[6:8]
        else:
            expiry_formatted = expiry
        
        log.info(f"Creating strategy: type={strategy_type}, expiry input={expiry}, formatted={expiry_formatted}")
        
        # Use factory to create strategy - pass params with underlying/expiry
        strategy = StrategyDefinitions.create_strategy(
            strategy_type=strategy_type,
            underlying=underlying,
            expiry=expiry_formatted,
            **params
        )
        
        if not strategy:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        # Generate option symbols for each leg
        for leg in strategy.legs:
            leg.generate_symbol(underlying)
            log.info(f"  Generated symbol: {leg.symbol}")
        
        # Save to DB
        self._save_strategy(strategy)
        
        log.info(f"✨ Created strategy: {strategy.name} ({strategy.id})")
        return strategy
    
    def create_custom_strategy(
        self,
        name: str,
        underlying: str,
        expiry: str,
        legs: List[Dict],
        strategy_type: str = None
    ) -> Strategy:
        """
        Create a custom strategy with manually specified legs
        
        Args:
            name: Strategy name
            underlying: BTC, ETH
            expiry: DDMMYYYY format (from options-chain/expirations)
            legs: List of leg definitions
            strategy_type: Optional strategy type (defaults to CUSTOM)
            
        Returns:
            Configured Strategy
        """
        # Convert expiry to Delta Exchange symbol format (DDMMYY)
        # Input: 13012026 (DDMMYYYY) -> Output: 130126 (DDMMYY)
        if len(expiry) == 8:
            # DDMMYYYY -> DDMMYY (take DD, MM, and last 2 digits of year)
            expiry_formatted = expiry[0:4] + expiry[6:8]  # 1301 + 26 = 130126
        elif len(expiry) == 6:
            # Already in DDMMYY format
            expiry_formatted = expiry
        else:
            # Fallback - use as-is
            expiry_formatted = expiry
        
        log.info(f"Creating custom strategy: expiry input={expiry}, formatted={expiry_formatted}, legs={len(legs)}")
            
        strategy_legs = []
        for i, leg_data in enumerate(legs, 1):
            # Build complete leg dict with all required fields
            # Use 'size' from Delta Exchange API format, fallback to 'quantity'
            quantity = leg_data.get('size', leg_data.get('quantity', 1))
            
            # Use provided limit_price from frontend (mid-price calculation)
            limit_price = float(leg_data.get('limit_price', 0))
            
            log.info(f"  Leg {i} input: size={leg_data.get('size')}, quantity={leg_data.get('quantity')}, final={quantity}, limit_price={limit_price}")
            
            leg_dict = {
                'leg_id': i,
                'option_type': leg_data['option_type'],
                'strike': float(leg_data['strike']),
                'expiry': expiry_formatted,
                'side': leg_data['side'],
                'quantity': quantity,
                'symbol': '',
                'status': 'pending',
                'order_id': '',
                'filled_qty': 0,
                'avg_fill_price': 0.0,
                'current_price': limit_price,
                'current_bid': 0.0,
                'current_ask': 0.0
            }
            
            # Create StrategyLeg from complete dict
            leg = StrategyLeg(**leg_dict)
            
            # Generate symbol
            leg.generate_symbol(underlying)
            
            log.info(f"  Leg {i}: {leg.symbol} ({leg.side} {leg.option_type} @ {leg.strike})")
            strategy_legs.append(leg)
        
        # Determine strategy type
        if strategy_type and strategy_type != 'custom':
            try:
                st_type = StrategyType(strategy_type).value
            except ValueError:
                st_type = StrategyType.CUSTOM.value
        else:
            st_type = StrategyType.CUSTOM.value
        
        strategy = Strategy(
            name=name,
            strategy_type=st_type,
            underlying=underlying,
            expiry=expiry_formatted,
            legs=strategy_legs
        )
        
        self._save_strategy(strategy)
        
        log.info(f"✨ Created custom strategy: {name} ({strategy.id})")
        return strategy
    
    def _save_strategy(self, strategy: Strategy):
        """Save strategy to database"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        row = self._strategy_to_row(strategy)
        
        cursor.execute('''
            INSERT OR REPLACE INTO strategies 
            (id, name, strategy_type, underlying, expiry, status, legs_json,
             entry_conditions_json, exit_conditions_json, total_cost, current_pnl,
             created_at, executed_at, closed_at, notes)
            VALUES 
            (:id, :name, :strategy_type, :underlying, :expiry, :status, :legs_json,
             :entry_conditions_json, :exit_conditions_json, :total_cost, :current_pnl,
             :created_at, :executed_at, :closed_at, :notes)
        ''', row)
        
        conn.commit()
        conn.close()
        
        # Keep in memory if active
        if strategy.status not in ['closed', 'expired', 'failed']:
            self._active_strategies[strategy.id] = strategy
    
    # ==================== READ Operations ====================
    
    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get strategy by ID"""
        # Check memory first
        if strategy_id in self._active_strategies:
            return self._active_strategies[strategy_id]
        
        # Query DB
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM strategies WHERE id = ?', (strategy_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_strategy(dict(row))
        return None
    
    def get_active_strategies(self) -> List[Strategy]:
        """Get all active (non-closed) strategies"""
        return list(self._active_strategies.values())
    
    def get_all_strategies(
        self, 
        status: str = None,
        underlying: str = None,
        limit: int = 50
    ) -> List[Strategy]:
        """
        Query strategies with filters
        
        Args:
            status: Filter by status
            underlying: Filter by underlying
            limit: Max results
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM strategies WHERE 1=1'
        params = []
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        if underlying:
            query += ' AND underlying = ?'
            params.append(underlying)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_strategy(dict(row)) for row in rows]
    
    def get_strategies_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                status,
                COUNT(*) as count,
                SUM(total_cost) as total_cost,
                SUM(current_pnl) as total_pnl
            FROM strategies
            GROUP BY status
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        summary = {
            'by_status': {row['status']: {
                'count': row['count'],
                'total_cost': row['total_cost'] or 0,
                'total_pnl': row['total_pnl'] or 0
            } for row in rows},
            'active_count': len(self._active_strategies),
            'total_count': sum(row['count'] for row in rows)
        }
        
        return summary
    
    # ==================== UPDATE Operations ====================
    
    async def execute_strategy(
        self,
        strategy_id: str,
        execution_mode: str = "sequential",
        order_type: str = "limit"
    ) -> Dict[str, Any]:
        """
        Execute a configured strategy
        
        Args:
            strategy_id: Strategy to execute
            execution_mode: sequential or parallel
            order_type: market or limit
            
        Returns:
            Execution result
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return {'success': False, 'error': f'Strategy not found: {strategy_id}'}
        
        if strategy.status != StrategyStatus.PENDING.value:
            return {
                'success': False, 
                'error': f'Strategy not in pending state: {strategy.status}'
            }
        
        # Execute via leg executor
        result = await self._executor.execute_strategy(
            strategy=strategy,
            execution_mode=execution_mode,
            order_type=order_type
        )
        
        # Log execution
        self._log_execution(strategy_id, 'execute', result.to_dict())
        
        # Update DB
        self._save_strategy(strategy)
        
        return result.to_dict()
    
    async def close_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Close an active strategy
        
        Args:
            strategy_id: Strategy to close
            
        Returns:
            Close result
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return {'success': False, 'error': f'Strategy not found: {strategy_id}'}
        
        if strategy.status not in [StrategyStatus.ACTIVE.value, StrategyStatus.PARTIAL.value]:
            return {
                'success': False,
                'error': f'Strategy not active: {strategy.status}'
            }
        
        # Close via executor
        result = await self._executor.close_strategy(strategy)
        
        # Log
        self._log_execution(strategy_id, 'close', result.to_dict())
        
        # Update DB and remove from active
        self._save_strategy(strategy)
        
        if result.success:
            del self._active_strategies[strategy_id]
        
        return result.to_dict()
    
    def update_strategy_pnl(self, strategy_id: str, current_pnl: float):
        """Update strategy P&L"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            strategy.current_pnl = current_pnl
            self._save_strategy(strategy)
    
    def update_strategy_notes(self, strategy_id: str, notes: str):
        """Update strategy notes"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            strategy.notes = notes
            self._save_strategy(strategy)
    
    # ==================== DELETE Operations ====================
    
    def delete_strategy(self, strategy_id: str) -> bool:
        """
        Delete a strategy (only if not executed)
        
        Args:
            strategy_id: Strategy to delete
            
        Returns:
            Success status
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.PENDING.value:
            log.warning(f"Cannot delete executed strategy: {strategy_id}")
            return False
        
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM strategies WHERE id = ?', (strategy_id,))
        cursor.execute('DELETE FROM execution_history WHERE strategy_id = ?', (strategy_id,))
        
        conn.commit()
        conn.close()
        
        if strategy_id in self._active_strategies:
            del self._active_strategies[strategy_id]
        
        log.info(f"🗑️ Deleted strategy: {strategy_id}")
        return True
    
    # ==================== P&L Calculation ====================
    
    async def calculate_strategy_pnl(self, strategy_id: str) -> Dict[str, Any]:
        """
        Calculate current P&L for a strategy
        
        Compares current option prices to entry prices
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return {'error': 'Strategy not found'}
        
        if strategy.status not in [StrategyStatus.ACTIVE.value, StrategyStatus.PARTIAL.value]:
            return {'error': 'Strategy not active'}
        
        total_entry_value = 0.0
        total_current_value = 0.0
        leg_pnls = []
        
        for leg in strategy.legs:
            if leg.status != LegStatus.FILLED.value:
                continue
            
            entry_value = leg.avg_fill_price * leg.filled_qty
            
            # Get current price
            ticker = await self._executor._get_ticker(leg.symbol)
            current_price = ticker.get('mark_price', leg.avg_fill_price) if ticker else leg.avg_fill_price
            current_value = current_price * leg.filled_qty
            
            # Calculate P&L based on side
            if leg.side == "buy":
                # Long position: profit if current > entry
                pnl = current_value - entry_value
                total_entry_value += entry_value
                total_current_value += current_value
            else:
                # Short position: profit if current < entry
                pnl = entry_value - current_value
                total_entry_value -= entry_value  # Credit received
                total_current_value -= current_value  # Liability
            
            leg_pnls.append({
                'leg_id': leg.leg_id,
                'symbol': leg.symbol,
                'side': leg.side,
                'entry_price': leg.avg_fill_price,
                'current_price': current_price,
                'pnl': round(pnl, 2)
            })
        
        total_pnl = sum(l['pnl'] for l in leg_pnls)
        
        # Update strategy
        strategy.current_pnl = total_pnl
        self._save_strategy(strategy)
        
        return {
            'strategy_id': strategy_id,
            'total_pnl': round(total_pnl, 2),
            'entry_cost': round(total_entry_value, 2),
            'current_value': round(total_current_value, 2),
            'pnl_percent': round((total_pnl / abs(total_entry_value)) * 100, 2) if total_entry_value else 0,
            'legs': leg_pnls
        }
    
    # ==================== Execution History ====================
    
    def _log_execution(self, strategy_id: str, action: str, details: Dict):
        """Log execution event"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO execution_history (strategy_id, action, timestamp, details_json)
            VALUES (?, ?, ?, ?)
        ''', (
            strategy_id,
            action,
            datetime.utcnow().isoformat() + "Z",
            json.dumps(details)
        ))
        
        conn.commit()
        conn.close()
    
    def get_execution_history(self, strategy_id: str) -> List[Dict]:
        """Get execution history for a strategy"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM execution_history 
            WHERE strategy_id = ?
            ORDER BY timestamp DESC
        ''', (strategy_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'action': row['action'],
            'timestamp': row['timestamp'],
            'details': json.loads(row['details_json']) if row['details_json'] else None
        } for row in rows]
    
    # ==================== Payoff Diagram ====================
    
    def get_payoff_diagram(
        self,
        strategy_id: str,
        price_range_pct: float = 20.0,
        num_points: int = 100
    ) -> Dict[str, Any]:
        """
        Generate payoff diagram data
        
        Args:
            strategy_id: Strategy ID
            price_range_pct: % above/below current price
            num_points: Number of price points
            
        Returns:
            Payoff diagram data
        """
        from .strategy_definitions import PayoffCalculator
        
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return {'error': 'Strategy not found'}
        
        return PayoffCalculator.calculate_payoff(
            strategy=strategy,
            price_range_pct=price_range_pct,
            num_points=num_points
        ).to_dict()
    
    # ==================== MV Straddle Methods ====================
    
    def create_mv_straddle(
        self,
        name: str,
        underlying: str,
        expiry: str,
        strike: Optional[int] = None,
        direction: str = "long",
        quantity: int = 1,
        auto_strike: bool = True,
        strike_offset: int = 0,
        preview_only: bool = False
    ) -> Dict:
        """
        Create MV Straddle strategy
        
        Args:
            name: Strategy name
            underlying: BTC or ETH
            expiry: DDMMYYYY format
            strike: Strike price (optional if auto_strike=True)
            direction: "long" or "short"
            quantity: Contracts per leg
            auto_strike: Auto-select ATM strike
            strike_offset: Offset from ATM
            preview_only: If True, don't save to DB
        
        Returns:
            Strategy dict with ID or error
        """
        try:
            if not self._mv_straddle:
                return {
                    "success": False,
                    "error": "MV Straddle not initialized"
                }
            
            # Validate parameters
            is_valid, error_msg = self._mv_straddle.validate_parameters(
                underlying=underlying,
                expiry=expiry,
                direction=direction,
                quantity=quantity
            )
            
            if not is_valid:
                return {"success": False, "error": error_msg}
            
            # Calculate legs
            legs = self._mv_straddle.calculate_legs(
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                direction=direction,
                quantity=quantity,
                auto_strike=auto_strike,
                strike_offset=strike_offset
            )
            
            # Calculate analytics
            breakeven = self._mv_straddle.calculate_breakeven(legs)
            max_pnl = self._mv_straddle.calculate_max_profit_loss(legs)
            vol_analysis = self._mv_straddle.get_volatility_analysis(legs, expiry, underlying)
            
            # Calculate P&L curve
            pnl_curve = self._breakeven_calculator.calculate_pnl_curve(legs)
            
            # Build strategy dict
            strategy = {
                "id": f"mv_straddle_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "name": name,
                "strategy_type": "mv_straddle",
                "underlying": underlying,
                "expiry": expiry,
                "direction": direction,
                "legs": legs,
                "total_premium": sum(leg["current_price"] * leg["quantity"] for leg in legs),
                "breakeven": breakeven,
                "max_profit_loss": max_pnl,
                "volatility_analysis": vol_analysis,
                "pnl_curve": pnl_curve,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
            
            # Save to DB if not preview
            if not preview_only:
                self._save_mv_straddle_to_db(strategy)
                log.info(f"Created MV Straddle strategy: {strategy['id']}")
            
            return {
                "success": True,
                "strategy": strategy
            }
            
        except Exception as e:
            log.error(f"Error creating MV Straddle: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _save_mv_straddle_to_db(self, strategy: Dict):
        """Save MV Straddle to database"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO strategies (
                    id, name, strategy_type, underlying, expiry, status,
                    legs_json, total_cost, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                strategy['id'],
                strategy['name'],
                strategy['strategy_type'],
                strategy['underlying'],
                strategy['expiry'],
                strategy['status'],
                json.dumps(strategy['legs']),
                strategy['total_premium'],
                strategy['created_at']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            log.error(f"Error saving MV Straddle to DB: {e}")
            raise
    
    def get_mv_straddle_preview(
        self,
        underlying: str,
        expiry: str,
        strike: Optional[int] = None,
        direction: str = "long",
        quantity: int = 1,
        auto_strike: bool = True,
        strike_offset: int = 0
    ) -> Dict:
        """
        Get MV Straddle preview without saving
        
        Returns:
            Preview dict with all analytics
        """
        return self.create_mv_straddle(
            name="Preview",
            underlying=underlying,
            expiry=expiry,
            strike=strike,
            direction=direction,
            quantity=quantity,
            auto_strike=auto_strike,
            strike_offset=strike_offset,
            preview_only=True
        )
    
    def close_mv_straddle_leg(
        self,
        strategy_id: str,
        leg_type: str
    ) -> Dict:
        """Close one leg of MV Straddle"""
        if not self._position_adjuster:
            return {"success": False, "error": "Position adjuster not initialized"}
        
        return self._position_adjuster.close_one_leg(strategy_id, leg_type)
    
    def roll_mv_straddle(
        self,
        strategy_id: str,
        new_expiry: str,
        new_strike: Optional[int] = None,
        keep_same_strike: bool = True
    ) -> Dict:
        """Roll MV Straddle to new expiry"""
        if not self._position_adjuster:
            return {"success": False, "error": "Position adjuster not initialized"}
        
        return self._position_adjuster.roll_straddle(
            strategy_id, new_expiry, new_strike, keep_same_strike
        )
    
    def adjust_mv_straddle_ratio(
        self,
        strategy_id: str,
        call_quantity: int,
        put_quantity: int
    ) -> Dict:
        """Adjust MV Straddle call:put ratio"""
        if not self._position_adjuster:
            return {"success": False, "error": "Position adjuster not initialized"}
        
        return self._position_adjuster.adjust_ratio(
            strategy_id, call_quantity, put_quantity
        )
