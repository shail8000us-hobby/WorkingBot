"""
Price Alert System - Database Models and Migrations
"""
import sqlite3
import os
from datetime import datetime
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'alerts.db')

def init_alerts_db():
    """Initialize the alerts database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_alerts (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL DEFAULT 'BTCUSD',
            target_price REAL NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('above', 'below', 'cross')),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'triggered', 'expired', 'cancelled')),
            note TEXT,
            expected_pnl_expiry REAL,
            expected_pnl_target REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            triggered_at TIMESTAMP,
            last_triggered_at TIMESTAMP,
            expires_at TIMESTAMP,
            notification_channels TEXT DEFAULT 'telegram,in_app',
            is_repeating BOOLEAN DEFAULT FALSE,
            cooldown_minutes INTEGER DEFAULT 60,
            trigger_count INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            telegram_bot_token TEXT,
            telegram_chat_id TEXT,
            ntfy_topic TEXT,
            ntfy_server TEXT DEFAULT 'https://ntfy.sh',
            enabled_channels TEXT DEFAULT 'telegram',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            price_at_trigger REAL,
            notification_sent BOOLEAN DEFAULT FALSE,
            notification_error TEXT,
            FOREIGN KEY (alert_id) REFERENCES price_alerts(id)
        )
    ''')
    
    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_status ON price_alerts(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON price_alerts(symbol, status)')
    
    conn.commit()
    conn.close()
    
    print(f"[AlertDB] Initialized alerts database at {DB_PATH}")

def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class AlertsDB:
    """Database operations for price alerts."""
    
    @staticmethod
    def create_alert(target_price: float, direction: str, note: str = None, 
                     expected_pnl_expiry: float = None, expected_pnl_target: float = None,
                     symbol: str = 'BTCUSD', is_repeating: bool = False,
                     notification_channels: str = 'telegram,in_app') -> dict:
        """Create a new price alert."""
        alert_id = str(uuid.uuid4())[:8]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO price_alerts 
            (id, symbol, target_price, direction, note, expected_pnl_expiry, 
             expected_pnl_target, is_repeating, notification_channels)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (alert_id, symbol, target_price, direction, note, 
              expected_pnl_expiry, expected_pnl_target, is_repeating, notification_channels))
        
        conn.commit()
        
        # Fetch the created alert
        cursor.execute('SELECT * FROM price_alerts WHERE id = ?', (alert_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row)
    
    @staticmethod
    def get_all_alerts(status: str = None) -> list:
        """Get all alerts, optionally filtered by status."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM price_alerts WHERE status = ? ORDER BY created_at DESC', (status,))
        else:
            cursor.execute('SELECT * FROM price_alerts ORDER BY created_at DESC')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_active_alerts() -> list:
        """Get all active alerts for price monitoring."""
        return AlertsDB.get_all_alerts(status='active')
    
    @staticmethod
    def get_alert(alert_id: str) -> dict:
        """Get a specific alert by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM price_alerts WHERE id = ?', (alert_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    @staticmethod
    def update_alert(alert_id: str, **kwargs) -> dict:
        """Update an alert with the given fields."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic UPDATE query
        set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [alert_id]
        
        cursor.execute(f'UPDATE price_alerts SET {set_clause} WHERE id = ?', values)
        conn.commit()
        
        # Fetch updated alert
        cursor.execute('SELECT * FROM price_alerts WHERE id = ?', (alert_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def trigger_alert(alert_id: str, price_at_trigger: float) -> dict:
        """Mark an alert as triggered."""
        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current alert
        cursor.execute('SELECT * FROM price_alerts WHERE id = ?', (alert_id,))
        alert = cursor.fetchone()
        
        if alert:
            if alert['is_repeating']:
                # For repeating alerts, just update last_triggered_at and increment count
                cursor.execute('''
                    UPDATE price_alerts 
                    SET last_triggered_at = ?, trigger_count = trigger_count + 1
                    WHERE id = ?
                ''', (now, alert_id))
            else:
                # For one-time alerts, mark as triggered
                cursor.execute('''
                    UPDATE price_alerts 
                    SET status = 'triggered', triggered_at = ?, trigger_count = 1
                    WHERE id = ?
                ''', (now, alert_id))
            
            # Log to history
            history_id = str(uuid.uuid4())[:12]
            cursor.execute('''
                INSERT INTO alert_history (id, alert_id, price_at_trigger)
                VALUES (?, ?, ?)
            ''', (history_id, alert_id, price_at_trigger))
        
        conn.commit()
        
        cursor.execute('SELECT * FROM price_alerts WHERE id = ?', (alert_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def delete_alert(alert_id: str) -> bool:
        """Delete an alert."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM price_alerts WHERE id = ?', (alert_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    @staticmethod
    def cancel_alert(alert_id: str) -> dict:
        """Cancel an active alert."""
        return AlertsDB.update_alert(alert_id, status='cancelled')
    
    # Settings methods
    @staticmethod
    def get_settings() -> dict:
        """Get notification settings."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alert_settings WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        else:
            # Return defaults
            return {
                'telegram_bot_token': None,
                'telegram_chat_id': None,
                'ntfy_topic': None,
                'ntfy_server': 'https://ntfy.sh',
                'enabled_channels': 'telegram'
            }
    
    @staticmethod
    def update_settings(**kwargs) -> dict:
        """Update notification settings."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if settings exist
        cursor.execute('SELECT id FROM alert_settings WHERE id = 1')
        exists = cursor.fetchone()
        
        kwargs['updated_at'] = datetime.utcnow().isoformat()
        
        if exists:
            set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
            values = list(kwargs.values())
            cursor.execute(f'UPDATE alert_settings SET {set_clause} WHERE id = 1', values)
        else:
            columns = ', '.join(['id'] + list(kwargs.keys()))
            placeholders = ', '.join(['?'] * (len(kwargs) + 1))
            values = [1] + list(kwargs.values())
            cursor.execute(f'INSERT INTO alert_settings ({columns}) VALUES ({placeholders})', values)
        
        conn.commit()
        
        cursor.execute('SELECT * FROM alert_settings WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else {}


# Initialize database on import
init_alerts_db()
