"""
State Manager for Zero DTE Bot
Handles session persistence, positions, and database operations
"""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from loguru import logger

from config.schemas.zero_dte_schemas import ZeroDTEConfig


class StateManager:
    """
    Manages persistent state for 0DTE trading sessions
    - Session lifecycle (create, update, close)
    - Position tracking (CE/PE legs)
    - Trade logging
    - Rebalancing history
    """
    
    def __init__(self, config: ZeroDTEConfig):
        self.config = config
        self.db_dir = Path(config.database.directory)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Database paths
        self.sessions_db = self.db_dir / config.database.sessions_db
        self.trades_db = self.db_dir / config.database.trades_db
        self.rebalances_db = self.db_dir / config.database.rebalances_db
        
        # Initialize databases
        self._init_databases()
        
        # In-memory cache for active session
        self._active_session: Optional[Dict] = None
        self._current_positions: Dict[str, Dict] = {}
        
        logger.info(f"StateManager initialized with DB dir: {self.db_dir}")
    
    def _init_databases(self):
        """Initialize all database tables"""
        self._init_sessions_db()
        self._init_trades_db()
        self._init_rebalances_db()
    
    @contextmanager
    def _get_connection(self, db_path: Path):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_sessions_db(self):
        """Initialize sessions database"""
        with self._get_connection(self.sessions_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    underlying TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
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
                    total_premium_paid REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    total_rebalances INTEGER DEFAULT 0,
                    total_rollovers INTEGER DEFAULT 0,
                    stop_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
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
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_positions_session ON current_positions(session_id)
            ''')
    
    def _init_trades_db(self):
        """Initialize trades database"""
        with self._get_connection(self.trades_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    leg_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    strike REAL NOT NULL,
                    lots INTEGER NOT NULL,
                    premium REAL NOT NULL,
                    order_id TEXT,
                    execution_price REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reason TEXT,
                    executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id)
            ''')
    
    def _init_rebalances_db(self):
        """Initialize rebalances database"""
        with self._get_connection(self.rebalances_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS rebalances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    rebalance_type TEXT NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    ce_premium_before REAL,
                    pe_premium_before REAL,
                    ce_lots_before INTEGER,
                    pe_lots_before INTEGER,
                    ce_premium_after REAL,
                    pe_premium_after REAL,
                    ce_lots_after INTEGER,
                    pe_lots_after INTEGER,
                    imbalance_pct_before REAL,
                    imbalance_pct_after REAL,
                    action_taken TEXT,
                    execution_status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            ''')
            
            conn.execute('''
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
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_rebalances_session ON rebalances(session_id)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshots_session ON monitoring_snapshots(session_id)
            ''')
    
    # ==========================================================================
    # SESSION MANAGEMENT
    # ==========================================================================
    
    def generate_session_id(self, underlying: str, expiry_date: str) -> str:
        """Generate unique session ID"""
        short_uuid = uuid.uuid4().hex[:8]
        expiry_formatted = expiry_date.replace('-', '')
        return f"0dte_{underlying}_{expiry_formatted}_{short_uuid}"
    
    def create_session(self, session_data: Dict) -> str:
        """
        Create new trading session
        
        Args:
            session_data: Dictionary containing:
                - underlying: BTC or ETH
                - expiry_date: YYYY-MM-DD
                - entry_ce_strike, entry_pe_strike
                - entry_ce_premium, entry_pe_premium
                - entry_ce_lots, entry_pe_lots
                - total_premium_collected
        
        Returns:
            session_id: Unique session identifier
        """
        session_id = self.generate_session_id(
            session_data['underlying'],
            session_data['expiry_date']
        )
        
        now = datetime.now().isoformat()
        
        with self._get_connection(self.sessions_db) as conn:
            conn.execute('''
                INSERT INTO sessions (
                    session_id, underlying, expiry_date, status, start_time,
                    entry_ce_strike, entry_pe_strike,
                    entry_ce_premium, entry_pe_premium,
                    entry_ce_lots, entry_pe_lots,
                    current_ce_strike, current_pe_strike,
                    current_ce_lots, current_pe_lots,
                    total_premium_collected
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                session_data['underlying'],
                session_data['expiry_date'],
                now,
                session_data['entry_ce_strike'],
                session_data['entry_pe_strike'],
                session_data['entry_ce_premium'],
                session_data['entry_pe_premium'],
                session_data['entry_ce_lots'],
                session_data['entry_pe_lots'],
                session_data['entry_ce_strike'],  # current = entry initially
                session_data['entry_pe_strike'],
                session_data['entry_ce_lots'],
                session_data['entry_pe_lots'],
                session_data['total_premium_collected']
            ))
        
        # Cache active session
        self._active_session = {
            'session_id': session_id,
            'status': 'active',
            **session_data
        }
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        with self._get_connection(self.sessions_db) as conn:
            cursor = conn.execute(
                'SELECT * FROM sessions WHERE session_id = ?',
                (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_active_session(self) -> Optional[Dict]:
        """Get currently active session (if any)"""
        # Check cache first
        if self._active_session and self._active_session.get('status') == 'active':
            return self._active_session
        
        # Query database
        with self._get_connection(self.sessions_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE status = 'active' ORDER BY start_time DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                self._active_session = dict(row)
                return self._active_session
        
        return None
    
    def update_session(self, session_id: str, updates: Dict):
        """Update session with new values"""
        if not updates:
            return
        
        updates['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [session_id]
        
        with self._get_connection(self.sessions_db) as conn:
            conn.execute(
                f'UPDATE sessions SET {set_clause} WHERE session_id = ?',
                values
            )
        
        # Update cache
        if self._active_session and self._active_session['session_id'] == session_id:
            self._active_session.update(updates)
    
    def close_session(self, session_id: str, stop_reason: str, realized_pnl: float):
        """Close trading session"""
        now = datetime.now().isoformat()
        
        with self._get_connection(self.sessions_db) as conn:
            conn.execute('''
                UPDATE sessions SET
                    status = 'closed',
                    end_time = ?,
                    stop_reason = ?,
                    realized_pnl = ?,
                    updated_at = ?
                WHERE session_id = ?
            ''', (now, stop_reason, realized_pnl, now, session_id))
        
        # Clear cache
        self._active_session = None
        self._current_positions = {}
        
        logger.info(f"Closed session {session_id}: reason={stop_reason}, pnl={realized_pnl}")
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    def save_position(self, session_id: str, position: Dict):
        """Save or update a position"""
        leg_type = position['leg_type']
        
        with self._get_connection(self.sessions_db) as conn:
            # Check if position exists
            cursor = conn.execute(
                'SELECT id FROM current_positions WHERE session_id = ? AND leg_type = ?',
                (session_id, leg_type)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                conn.execute('''
                    UPDATE current_positions SET
                        symbol = ?, strike = ?, lots = ?, entry_premium = ?,
                        current_premium = ?, unrealized_pnl = ?,
                        delta = ?, gamma = ?, theta = ?, vega = ?, iv = ?,
                        last_updated = ?
                    WHERE session_id = ? AND leg_type = ?
                ''', (
                    position['symbol'], position['strike'], position['lots'],
                    position['entry_premium'], position.get('current_premium'),
                    position.get('unrealized_pnl'),
                    position.get('delta'), position.get('gamma'),
                    position.get('theta'), position.get('vega'), position.get('iv'),
                    datetime.now().isoformat(),
                    session_id, leg_type
                ))
            else:
                # Insert new
                conn.execute('''
                    INSERT INTO current_positions (
                        session_id, leg_type, symbol, strike, lots, entry_premium,
                        current_premium, unrealized_pnl,
                        delta, gamma, theta, vega, iv
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id, leg_type, position['symbol'], position['strike'],
                    position['lots'], position['entry_premium'],
                    position.get('current_premium'), position.get('unrealized_pnl'),
                    position.get('delta'), position.get('gamma'),
                    position.get('theta'), position.get('vega'), position.get('iv')
                ))
        
        # Update cache
        self._current_positions[leg_type] = position
    
    def get_positions(self, session_id: str) -> Dict[str, Dict]:
        """Get all positions for a session"""
        with self._get_connection(self.sessions_db) as conn:
            cursor = conn.execute(
                'SELECT * FROM current_positions WHERE session_id = ?',
                (session_id,)
            )
            positions = {}
            for row in cursor.fetchall():
                pos = dict(row)
                positions[pos['leg_type']] = pos
            return positions
    
    def update_position_premium(self, session_id: str, leg_type: str, 
                                 current_premium: float, greeks: Dict = None):
        """Update current premium and Greeks for a position"""
        updates = {
            'current_premium': current_premium,
            'last_updated': datetime.now().isoformat()
        }
        
        if greeks:
            updates.update({
                'delta': greeks.get('delta'),
                'gamma': greeks.get('gamma'),
                'theta': greeks.get('theta'),
                'vega': greeks.get('vega'),
                'iv': greeks.get('iv')
            })
        
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [session_id, leg_type]
        
        with self._get_connection(self.sessions_db) as conn:
            conn.execute(
                f'UPDATE current_positions SET {set_clause} WHERE session_id = ? AND leg_type = ?',
                values
            )
    
    # ==========================================================================
    # TRADE LOGGING
    # ==========================================================================
    
    def log_trade(self, trade_data: Dict) -> int:
        """Log a trade execution"""
        with self._get_connection(self.trades_db) as conn:
            cursor = conn.execute('''
                INSERT INTO trades (
                    session_id, trade_type, leg_type, symbol, side,
                    strike, lots, premium, order_id, execution_price,
                    status, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data['session_id'],
                trade_data['trade_type'],
                trade_data['leg_type'],
                trade_data['symbol'],
                trade_data['side'],
                trade_data['strike'],
                trade_data['lots'],
                trade_data['premium'],
                trade_data.get('order_id'),
                trade_data.get('execution_price'),
                trade_data.get('status', 'filled'),
                trade_data.get('reason')
            ))
            return cursor.lastrowid
    
    def get_trades(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get trades for a session"""
        with self._get_connection(self.trades_db) as conn:
            cursor = conn.execute(
                'SELECT * FROM trades WHERE session_id = ? ORDER BY executed_at DESC LIMIT ?',
                (session_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ==========================================================================
    # REBALANCING HISTORY
    # ==========================================================================
    
    def log_rebalance(self, rebalance_data: Dict) -> int:
        """Log a rebalancing event"""
        with self._get_connection(self.rebalances_db) as conn:
            cursor = conn.execute('''
                INSERT INTO rebalances (
                    session_id, rebalance_type, trigger_reason,
                    ce_premium_before, pe_premium_before,
                    ce_lots_before, pe_lots_before,
                    ce_premium_after, pe_premium_after,
                    ce_lots_after, pe_lots_after,
                    imbalance_pct_before, imbalance_pct_after,
                    action_taken, execution_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rebalance_data['session_id'],
                rebalance_data['rebalance_type'],
                rebalance_data['trigger_reason'],
                rebalance_data.get('ce_premium_before'),
                rebalance_data.get('pe_premium_before'),
                rebalance_data.get('ce_lots_before'),
                rebalance_data.get('pe_lots_before'),
                rebalance_data.get('ce_premium_after'),
                rebalance_data.get('pe_premium_after'),
                rebalance_data.get('ce_lots_after'),
                rebalance_data.get('pe_lots_after'),
                rebalance_data.get('imbalance_pct_before'),
                rebalance_data.get('imbalance_pct_after'),
                json.dumps(rebalance_data.get('action_taken', [])),
                rebalance_data.get('execution_status', 'success'),
                rebalance_data.get('error_message')
            ))
            return cursor.lastrowid
    
    def get_rebalances(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get rebalancing history for a session"""
        with self._get_connection(self.rebalances_db) as conn:
            cursor = conn.execute(
                'SELECT * FROM rebalances WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?',
                (session_id, limit)
            )
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                if r.get('action_taken'):
                    r['action_taken'] = json.loads(r['action_taken'])
                results.append(r)
            return results
    
    def increment_rebalance_count(self, session_id: str):
        """Increment rebalance counter for session"""
        with self._get_connection(self.sessions_db) as conn:
            conn.execute(
                'UPDATE sessions SET total_rebalances = total_rebalances + 1 WHERE session_id = ?',
                (session_id,)
            )
    
    def increment_rollover_count(self, session_id: str):
        """Increment rollover counter for session"""
        with self._get_connection(self.sessions_db) as conn:
            conn.execute(
                'UPDATE sessions SET total_rollovers = total_rollovers + 1 WHERE session_id = ?',
                (session_id,)
            )
    
    # ==========================================================================
    # MONITORING SNAPSHOTS
    # ==========================================================================
    
    def save_snapshot(self, snapshot_data: Dict):
        """Save monitoring snapshot"""
        with self._get_connection(self.rebalances_db) as conn:
            conn.execute('''
                INSERT INTO monitoring_snapshots (
                    session_id, spot_price, ce_premium, pe_premium,
                    ce_lots, pe_lots, portfolio_delta, portfolio_gamma,
                    portfolio_theta, portfolio_vega, unrealized_pnl,
                    margin_used, margin_utilization_pct, time_to_expiry_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_data['session_id'],
                snapshot_data['spot_price'],
                snapshot_data.get('ce_premium'),
                snapshot_data.get('pe_premium'),
                snapshot_data.get('ce_lots'),
                snapshot_data.get('pe_lots'),
                snapshot_data.get('portfolio_delta'),
                snapshot_data.get('portfolio_gamma'),
                snapshot_data.get('portfolio_theta'),
                snapshot_data.get('portfolio_vega'),
                snapshot_data.get('unrealized_pnl'),
                snapshot_data.get('margin_used'),
                snapshot_data.get('margin_utilization_pct'),
                snapshot_data.get('time_to_expiry_minutes')
            ))
    
    def get_snapshots(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get monitoring snapshots for a session"""
        with self._get_connection(self.rebalances_db) as conn:
            cursor = conn.execute(
                'SELECT * FROM monitoring_snapshots WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?',
                (session_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    
    def cleanup_old_records(self, days: int = None):
        """Remove records older than retention period"""
        if days is None:
            days = self.config.database.retention_days
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection(self.sessions_db) as conn:
            conn.execute('DELETE FROM sessions WHERE created_at < ? AND status = "closed"', (cutoff,))
            conn.execute('DELETE FROM current_positions WHERE last_updated < ?', (cutoff,))
        
        with self._get_connection(self.trades_db) as conn:
            conn.execute('DELETE FROM trades WHERE executed_at < ?', (cutoff,))
        
        with self._get_connection(self.rebalances_db) as conn:
            conn.execute('DELETE FROM rebalances WHERE timestamp < ?', (cutoff,))
            conn.execute('DELETE FROM monitoring_snapshots WHERE timestamp < ?', (cutoff,))
        
        logger.info(f"Cleaned up records older than {days} days")


# Import timedelta for cleanup
from datetime import timedelta
