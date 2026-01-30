"""
Database Manager - Production Ready
Handles all database operations for the prototype
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database for historical data, signals, and backtest results.
    Thread-safe and production-ready.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize database manager"""
        if db_path is None:
            # Load from config
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
                db_path = config['database']['path']
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        logger.info(f"Database initialized at {self.db_path}")
    
    def _init_database(self):
        """Create tables from schema.sql if they don't exist"""
        schema_path = Path(__file__).parent / 'schema.sql'
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
        
        logger.info("Database schema created/verified")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    
    # ===== OHLCV Operations =====
    
    def insert_ohlcv(self, symbol: str, timestamp: int, open_: float, high: float,
                     low: float, close: float, volume: float, timeframe: str):
        """Insert OHLCV candle (or ignore if exists)"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO ohlcv 
                (symbol, timestamp, open, high, low, close, volume, timeframe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, timestamp, open_, high, low, close, volume, timeframe))
            conn.commit()
    
    def insert_ohlcv_bulk(self, candles: List[Dict[str, Any]]):
        """Insert multiple OHLCV candles efficiently"""
        with self.get_connection() as conn:
            conn.executemany('''
                INSERT OR IGNORE INTO ohlcv 
                (symbol, timestamp, open, high, low, close, volume, timeframe)
                VALUES (:symbol, :timestamp, :open, :high, :low, :close, :volume, :timeframe)
            ''', candles)
            conn.commit()
        
        logger.info(f"Inserted {len(candles)} OHLCV candles")
    
    def get_ohlcv(self, symbol: str, timeframe: str, 
                   start_time: Optional[int] = None,
                   end_time: Optional[int] = None,
                   limit: Optional[int] = None) -> List[Dict]:
        """
        Get OHLCV data for symbol/timeframe
        
        Returns list of dicts with keys: timestamp, open, high, low, close, volume
        """
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
        '''
        params = [symbol, timeframe]
        
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time)
        
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time)
        
        query += ' ORDER BY timestamp ASC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_ohlcv_timestamp(self, symbol: str, timeframe: str) -> Optional[int]:
        """Get the most recent timestamp for symbol/timeframe"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT MAX(timestamp) as latest
                FROM ohlcv
                WHERE symbol = ? AND timeframe = ?
            ''', (symbol, timeframe))
            
            result = cursor.fetchone()
            return result['latest'] if result else None
    
    # ===== Options Chain Operations =====
    
    def insert_options_chain(self, chain_data: List[Dict[str, Any]]):
        """Insert options chain snapshot"""
        with self.get_connection() as conn:
            conn.executemany('''
                INSERT OR IGNORE INTO options_chains
                (underlying_symbol, snapshot_timestamp, contract_symbol, strike, expiry,
                 option_type, bid, ask, last_price, mark_price, iv, delta, gamma, theta, vega,
                 rho, volume, open_interest, underlying_price)
                VALUES (
                    :underlying_symbol, :snapshot_timestamp, :contract_symbol, :strike, :expiry,
                    :option_type, :bid, :ask, :last_price, :mark_price, :iv, :delta, :gamma,
                    :theta, :vega, :rho, :volume, :open_interest, :underlying_price
                )
            ''', chain_data)
            conn.commit()
        
        logger.info(f"Inserted options chain with {len(chain_data)} contracts")
    
    # ===== IV History Operations =====
    
    def insert_iv_history(self, symbol: str, timestamp: int, current_iv: float,
                          iv_rank: Optional[float] = None,
                          iv_percentile: Optional[float] = None,
                          hv_10d: Optional[float] = None,
                          hv_30d: Optional[float] = None,
                          hv_60d: Optional[float] = None):
        """Insert IV history record"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO iv_history
                (symbol, timestamp, current_iv, iv_rank, iv_percentile, hv_10d, hv_30d, hv_60d)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, timestamp, current_iv, iv_rank, iv_percentile, hv_10d, hv_30d, hv_60d))
            conn.commit()
    
    def get_iv_history(self, symbol: str, days: int = 365) -> List[Dict]:
        """Get IV history for symbol"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT *
                FROM iv_history
                WHERE symbol = ?
                AND timestamp >= strftime('%s', 'now', '-' || ? || ' days')
                ORDER BY timestamp ASC
            ''', (symbol, days))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== Signal Operations =====
    
    def insert_signal(self, strategy_name: str, symbol: str, signal_time: int,
                     signal_type: str, action: str, confidence: float = None,
                     reasoning: str = None, metadata: str = None):
        """Insert trading signal"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO signals
                (strategy_name, symbol, signal_time, signal_type, action, 
                 confidence, reasoning, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, signal_time, signal_type, action,
                  confidence, reasoning, metadata))
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_signals(self, strategy_name: Optional[str] = None, 
                          limit: int = 100) -> List[Dict]:
        """Get recent signals"""
        query = 'SELECT * FROM signals'
        params = []
        
        if strategy_name:
            query += ' WHERE strategy_name = ?'
            params.append(strategy_name)
        
        query += ' ORDER BY signal_time DESC LIMIT ?'
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== Backtest Operations =====
    
    def insert_backtest_result(self, strategy_name: str, symbol: str, timeframe: str,
                               start_time: int, end_time: int, initial_capital: float,
                               final_capital: float, total_trades: int, winning_trades: int,
                               losing_trades: int, total_pnl: float, total_return_pct: float,
                               sharpe_ratio: float, max_drawdown_pct: float, win_rate: float,
                               profit_factor: float, avg_trade_pnl: float,
                               extra_metrics: Optional[Dict] = None) -> int:
        """Insert backtest result and return ID"""
        import uuid
        import json
        
        backtest_id = str(uuid.uuid4())[:8]
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO backtest_results
                (strategy_name, backtest_id, start_date, end_date, initial_capital,
                 final_capital, total_return, total_trades, winning_trades, losing_trades,
                 win_rate, avg_win, avg_loss, largest_win, largest_loss, sharpe_ratio,
                 sortino_ratio, max_drawdown, profit_factor, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, backtest_id, start_time, end_time, initial_capital,
                  final_capital, total_return_pct, total_trades, winning_trades, losing_trades,
                  win_rate, avg_trade_pnl, avg_trade_pnl, 0, 0, sharpe_ratio,
                  0, max_drawdown_pct, profit_factor, 
                  json.dumps(extra_metrics) if extra_metrics else '{}'))
            conn.commit()
            return cursor.lastrowid
    
    def insert_backtest_trade(self, backtest_id: int, trade_id: str, symbol: str,
                              action: str, direction: str, entry_time: int,
                              entry_price: float, exit_time: int, exit_price: float,
                              pnl: float, pnl_percent: float):
        """Insert a single backtest trade"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO backtest_trades
                (backtest_id, trade_number, entry_time, exit_time, symbol, trade_type,
                 entry_price, exit_price, quantity, pnl, pnl_percent, exit_reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (backtest_id, trade_id, entry_time, exit_time, symbol, action,
                  entry_price, exit_price, 1.0, pnl, pnl_percent, direction, '{}'))
            conn.commit()
    
    def insert_backtest_trades(self, trades: List[Dict[str, Any]]):
        """Insert backtest trades"""
        with self.get_connection() as conn:
            conn.executemany('''
                INSERT INTO backtest_trades
                (backtest_id, trade_number, entry_time, exit_time, symbol, trade_type,
                 entry_price, exit_price, quantity, pnl, pnl_percent, exit_reason, metadata)
                VALUES (
                    :backtest_id, :trade_number, :entry_time, :exit_time, :symbol, :trade_type,
                    :entry_price, :exit_price, :quantity, :pnl, :pnl_percent, :exit_reason, :metadata
                )
            ''', trades)
            conn.commit()
    
    def get_backtest_results(self, strategy_name: Optional[str] = None,
                             limit: int = 20) -> List[Dict]:
        """Get all backtest results"""
        query = 'SELECT * FROM backtest_results'
        params = []
        
        if strategy_name:
            query += ' WHERE strategy_name = ?'
            params.append(strategy_name)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_backtest_trades(self, backtest_id: int) -> List[Dict]:
        """Get trades for a specific backtest"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM backtest_trades
                WHERE backtest_id = ?
                ORDER BY entry_time ASC
            ''', (backtest_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== Optimization Operations =====
    
    def insert_optimization_result(self, strategy_name: str, symbol: str, timeframe: str,
                                   optimization_target: str, best_params: Dict,
                                   best_value: float, n_trials: int, completed_trials: int,
                                   execution_time: float) -> int:
        """Insert optimization result"""
        import json
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO optimization_results
                (strategy_name, symbol, timeframe, optimization_target,
                 best_params, best_value, n_trials, completed_trials, execution_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (strategy_name, symbol, timeframe, optimization_target,
                  json.dumps(best_params), best_value, n_trials, completed_trials, execution_time))
            conn.commit()
            return cursor.lastrowid
    
    def get_optimization_results(self, strategy_name: Optional[str] = None,
                                 limit: int = 20) -> List[Dict]:
        """Get optimization results"""
        query = 'SELECT * FROM optimization_results'
        params = []
        
        if strategy_name:
            query += ' WHERE strategy_name = ?'
            params.append(strategy_name)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                # Parse JSON fields
                if r.get('best_params'):
                    try:
                        r['best_params'] = json.loads(r['best_params'])
                    except:
                        pass
                results.append(r)
            return results
    
    # ===== Utility Methods =====
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get statistics about database contents"""
        with self.get_connection() as conn:
            stats = {}
            
            # Count records in each table
            tables = ['ohlcv', 'options_chains', 'iv_history', 'signals', 
                     'backtest_results', 'backtest_trades', 'optimization_results']
            
            for table in tables:
                cursor = conn.execute(f'SELECT COUNT(*) as count FROM {table}')
                stats[table] = cursor.fetchone()['count']
            
            return stats
    
    def clear_table(self, table_name: str):
        """Clear all data from a table (use with caution!)"""
        with self.get_connection() as conn:
            conn.execute(f'DELETE FROM {table_name}')
            conn.commit()
        
        logger.warning(f"Cleared table: {table_name}")


if __name__ == '__main__':
    # Test the database manager
    logging.basicConfig(level=logging.INFO)
    
    db = DatabaseManager()
    
    # Show stats
    stats = db.get_database_stats()
    print("\n=== Database Statistics ===")
    for table, count in stats.items():
        print(f"{table}: {count} records")
