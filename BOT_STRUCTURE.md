# 🏗️ WorkingBot Technical Architecture

**Complete technical documentation for developers**

**Last Updated:** October 31, 2025  
**Version:** 4.0.0 (Modular Architecture)  
**Language:** Python 3.10+

---

## 🚨 ARCHITECTURE UPDATE (October 31, 2025)

**GridBot Refactored: Single God Class → 7 Domain Modules**

The trading strategy has been completely refactored from `gbot_ws.py` (3,492-line God Class) into a clean modular architecture:

```
OLD: bot/strategy/gbot_ws.py (3,492 lines) ❌ BACKUP ONLY
NEW: bot/strategy/gridbot.py + 7 modules ✅ ACTIVE
```

**Key Changes:**
- Entry point: `from bot.strategy.gridbot import run_grid_strategy`
- Modular design: 7 focused domain modules
- Test coverage: 96.7% (30/31 tests passing)
- All critical fixes preserved (#6, #8, #12, #13)

**See `ARCHITECTURE_UPDATE_REFACTORED_GRIDBOT.md` for complete details.**

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Trading Strategy](#trading-strategy)
5. [API Documentation](#api-documentation)
6. [Database Schema](#database-schema)
7. [Configuration System](#configuration-system)
8. [Development Guide](#development-guide)

---

## 1. Architecture Overview

### System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User Interface Layer                   │
│  ┌────────────────────┐        ┌────────────────────────┐   │
│  │  React Frontend    │◄──────►│  Flask Backend API     │   │
│  │  (Port: Frontend)  │  HTTP  │  (Port: 5555)          │   │
│  │  - Material-UI     │WebSocket│  - REST Endpoints      │   │
│  │  - Charts          │        │  - SocketIO Server     │   │
│  └────────────────────┘        └────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Trading Bot  │  │Guardian Bot  │  │Heartbeat Mon.│       │
│  │ gridbot.py   │  │guardian_bot  │  │  monitor.py  │       │
│  │ + 7 modules  │  │    .py       │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     Service Layer                             │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Delta Client     │  │ Config Manager   │                 │
│  │ delta_client.py  │  │ config_manager   │                 │
│  │ - REST API       │  │    _core.py      │                 │
│  │ - WebSocket      │  │ - Hot reload     │                 │
│  └──────────────────┘  └──────────────────┘                 │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Volatility Coll. │  │ Emergency Kill   │                 │
│  │ delta_volatility │  │ emergency_kill   │                 │
│  │  _collector.py   │  │     .py          │                 │
│  └──────────────────┘  └──────────────────┘                 │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ SQLite DB    │  │ Config Files │  │ Log Files    │       │
│  │ volatility.db│  │ grid_config  │  │ bot_live.log │       │
│  │              │  │    .env      │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     External Services                         │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Delta Exchange   │  │  Telegram API    │                 │
│  │ (India)          │  │  (Alerts)        │                 │
│  └──────────────────┘  └──────────────────┘                 │
└──────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.10+
- Flask 2.3.x (Web framework)
- Flask-SocketIO (Real-time communication)
- SQLite (Database)
- WebSocket (Delta Exchange streaming)

**Frontend:**
- React 18.2.0
- Material-UI 5.x
- Recharts (Data visualization)
- Tailwind CSS (Styling)
- Framer Motion (Animations)

**Infrastructure:**
- macOS LaunchAgents (Auto-start)
- tmux (Process management)
- Git (Version control)

---

## 2. Project Structure

```
WorkingBot/
├── bot/                              # Trading bot core
│   ├── run.py                        # Main entry point (247 lines)
│   │   └── Initializes trading bot with mode (demo/live) and duration
│   │
│   ├── strategy/                     # Trading strategies
│   │   ├── gbot_ws.py                # WebSocket GridBot (ACTIVE, 1970 lines)
│   │   │   ├── __init__              # Initialize with config
│   │   │   ├── _on_fill_detected     # Handle fills (WebSocket event)
│   │   │   ├── _place_next_buy       # Calculate and place next BUY
│   │   │   ├── _place_tp_sell        # Place TP after fill
│   │   │   ├── _hot_reload_config    # Check for config changes every 5s
│   │   │   └── run                   # Main event loop
│   │   │
│   │   └── grid_sync.py              # REST GridBot (LEGACY, 358 lines)
│   │
│   ├── api/                          # Exchange API clients
│   │   └── delta_client.py           # Delta Exchange client (587 lines)
│   │       ├── DeltaClient           # REST API wrapper
│   │       ├── fetch_ticker          # Get current price
│   │       ├── create_order          # Place order
│   │       ├── cancel_order          # Cancel order
│   │       ├── fetch_order           # Get order status
│   │       └── fetch_positions       # Get open positions
│   │
│   ├── config/                       # Configuration management
│   │   ├── config_manager_core.py    # Config loader/validator (943 lines)
│   │   │   ├── load_config           # Load from grid_config.env
│   │   │   ├── validate_config       # Validate all parameters
│   │   │   ├── save_config           # Save changes
│   │   │   └── watch_config          # Monitor for changes (hot reload)
│   │   │
│   │   └── aliases.py                # Legacy parameter mapping (254 lines)
│   │
│   ├── guardian/                     # Safety monitoring
│   │   └── guardian_bot.py           # 24/7 position monitor (682 lines)
│   │       ├── check_account_health  # Monitor total loss
│   │       ├── check_positions       # Monitor position risk
│   │       ├── emergency_close       # Force close all positions
│   │       └── main_loop             # 5-second monitoring loop
│   │
│   ├── heartbeat/                    # Dead man's switch
│   │   └── monitor.py                # Heartbeat monitor (321 lines)
│   │       ├── update_heartbeat      # Write .heartbeat file every 5s
│   │       ├── check_heartbeat       # Verify heartbeat alive
│   │       └── emergency_action      # Cancel orders if heartbeat dead
│   │
│   ├── volatility/                   # Volatility monitoring
│   │   ├── delta_volatility_collector.py  # IV/RV collector (893 lines)
│   │   │   ├── _fetch_and_store_iv   # Fetch implied volatility
│   │   │   ├── _fetch_and_store_rv   # Calculate realized volatility
│   │   │   ├── get_latest_values     # Get current IV/RV
│   │   │   └── collector_loop        # 30-second collection loop
│   │   │
│   │   └── iv_rv_tracker.py          # Volatility tracker (188 lines)
│   │       └── HOT RELOAD implemented here
│   │
│   ├── emergency_kill.py             # Emergency shutdown system (156 lines)
│   │   └── emergency_kill_all        # Kill all bots, cancel orders
│   │
│   └── audit/                        # Audit logs
│       ├── order_audit.py            # Parse logs to JSONL (234 lines)
│       ├── orders.jsonl              # Structured order history
│       └── orders.csv                # CSV export
│
├── webui/                            # Web interface
│   ├── backend/                      # Flask API
│   │   ├── app.py                    # Main Flask app (7973 lines)
│   │   │   ├── /api/health           # Health check
│   │   │   ├── /api/bot/status       # Bot status
│   │   │   ├── /api/trading_status   # Trading status
│   │   │   ├── /api/positions        # Open positions
│   │   │   ├── /api/config/flat      # Configuration
│   │   │   ├── /api/logs             # Log viewer
│   │   │   └── /api/volatility/*     # Volatility endpoints
│   │   │
│   │   ├── connection_pool.py        # HTTP connection pooling
│   │   ├── lightweight_health.py     # Cached health checks
│   │   └── circuit_breaker.py        # Circuit breaker pattern
│   │
│   └── frontend/                     # React app
│       ├── src/
│       │   ├── App.js                # Main app (1385 lines)
│       │   ├── components/           # React components
│       │   │   ├── BotControl.js     # Bot start/stop controls
│       │   │   ├── VolatilityChart.js # IV/RV chart
│       │   │   ├── PnLChart.js       # P&L chart
│       │   │   ├── ConfigEditor.js   # Config editor with help
│       │   │   └── ...               # Other components
│       │   │
│       │   └── utils/
│       │       ├── apiClient.js      # API client with retry
│       │       └── websocket.js      # WebSocket manager
│       │
│       └── public/
│           └── build/                # Production build
│
├── data/                             # Data storage
│   ├── volatility.db                 # SQLite database (IV/RV data)
│   └── state.json                    # Bot state persistence
│
├── reports/                          # Generated reports
│   ├── bot.pid                       # Bot process ID
│   ├── pnl_history_YYYYMMDD.csv      # Daily P&L history
│   └── trades_last_24h.csv           # Recent trades
│
├── scripts/                          # Utility scripts
│   └── start_tmux_daemon.sh          # LaunchAgent startup script
│
├── grid_config.env                   # Main configuration (1535 lines)
├── secrets/api_keys.env              # API credentials
├── .heartbeat                        # Heartbeat file (updated every 5s)
├── .guardian_health                  # Guardian status
└── .volatility_halt.json             # Volatility halt state
```

---

## 3. Core Components

### 3.1 Trading Bot (gbot_ws.py)

**Primary Trading Engine**

**File:** `bot/strategy/gbot_ws.py` (1970 lines)

**Architecture:** Event-driven WebSocket strategy

**Key Classes:**

```python
class GbotWS:
    """WebSocket-based grid trading bot"""
    
    def __init__(self, config):
        """Initialize bot with configuration"""
        self.config = config
        self.client = DeltaClient(config)
        self.grid_params = self._calculate_grid()
        self.open_tranches = []  # Open positions
        self.pending_entry = {"price": None, "order_id": None}
        self._processed_fills = set()  # Deduplication
        
    def _on_fill_detected(self, fill_data):
        """
        WebSocket event handler for fills
        Detection time: 0.05 seconds (vs 20s REST)
        
        Args:
            fill_data: Fill event from WebSocket
            
        Actions:
            1. Validate fill (not duplicate)
            2. Add to open_tranches
            3. Place TP order immediately
            4. Update state
        """
        
    def _place_next_buy(self):
        """
        Calculate and place next BUY order
        
        Logic:
            - If no positions: BUY @ (REF - STEP)
            - If positions exist: BUY @ (lowest_entry - STEP)
            - Only if: len(open_tranches) < MAX_OPEN
            
        Side Effects:
            - Cancels old pending BUY (single enforcement)
            - Places new BUY order
            - Updates pending_entry state
        """
        
    def _place_tp_sell(self, entry_price, quantity):
        """
        Place take-profit SELL order
        
        Args:
            entry_price: Entry price of position
            quantity: Position size
            
        Logic:
            tp_price = entry_price + GRID_STEP
            
        Retry:
            - Up to 3 attempts
            - Exponential backoff (1s, 2s, 4s)
            - Logs all failures
        """
        
    def _hot_reload_config(self):
        """
        Check for configuration changes every 5 seconds
        
        Monitored:
            - GRID_STEP
            - GRID_LOWER
            - GRID_UPPER
            - REFERENCE_LEVEL
            
        Actions if changed:
            1. Validate new config
            2. Cancel pending BUY
            3. Recalculate grid
            4. Place new BUY
            5. Log reload event
        """
        
    def run(self):
        """
        Main event loop
        
        Flow:
            1. Connect WebSocket
            2. Subscribe to fills channel
            3. Start heartbeat thread
            4. Start hot reload thread
            5. Listen for events
            6. Handle fills immediately
            7. Update grid continuously
        """
```

**Critical Methods:**

| Method | Purpose | Lines | Timing |
|--------|---------|-------|--------|
| `_on_fill_detected` | Handle fill events | 340-404 | 0.05s |
| `_place_next_buy` | Place next BUY order | 720-821 | Immediate |
| `_place_tp_sell` | Place TP after fill | 823-920 | <1s |
| `_hot_reload_config` | Check config changes | 1000-1174 | Every 5s |
| `_format_heartbeat_status` | Generate heartbeat | 1920-1970 | Every 5s |

**State Management:**

```python
# In-memory state
self.open_tranches = [
    {
        'entry_price': 109000.0,
        'actual_entry': 109000.0,  # Actual fill price
        'quantity': 1,
        'tp_id': 'order_123456',
        'tp_price': 110000.0,
        'timestamp': 1730304000,
        'is_opportunistic': False
    },
    # ... more positions
]

# Persistent state (state.json)
{
    "open_tranches": [...],
    "pending_entry": {"price": 108000.0, "order_id": "order_789"},
    "last_update": 1730304000,
    "config_hash": "abc123def456"
}
```

### 3.2 Guardian Bot (guardian_bot.py)

**24/7 Safety Monitor**

**File:** `bot/guardian/guardian_bot.py` (682 lines)

**Purpose:** Monitor account health and enforce loss limits

**Key Functions:**

```python
def check_account_health():
    """
    Monitor total account loss every 5 seconds
    
    Returns:
        dict: {
            'current_loss': -15000.50,
            'loss_limit': 20000.00,
            'loss_pct': 75.0,
            'alert_level': 'warning'  # 'ok', 'warning', 'critical', 'emergency'
        }
    """
    
def emergency_close_positions():
    """
    Force close all open positions
    
    Trigger:
        - Loss >= 100% of GUARDIAN_MAX_ACCOUNT_LOSS_INR
        
    Actions:
        1. Send critical alert
        2. Place market SELL for each position
        3. Cancel all pending orders
        4. Stop trading bot
        5. Log all actions
    """
    
def main_loop():
    """
    Guardian monitoring loop (every 5 seconds)
    
    Checks:
        1. Total account loss
        2. Position risk (margin, liquidation distance)
        3. Pending order exposure
        4. Config changes
        
    Alerts:
        - 80% loss → Warning
        - 90% loss → Critical
        - 100% loss → Emergency stop!
    """
```

**Alert Thresholds:**

```
0-79%:   ✅ OK (no alerts)
80-89%:  ⚠️  WARNING (Telegram alert)
90-99%:  🚨 CRITICAL (Telegram + position review)
100%+:   🛑 EMERGENCY (Auto-stop + close all)
```

### 3.3 Delta Client (delta_client.py)

**Exchange API Interface**

**File:** `bot/api/delta_client.py` (587 lines)

**Purpose:** Wrapper for Delta Exchange India API

**Key Methods:**

```python
class DeltaClient:
    """Delta Exchange REST API client"""
    
    def __init__(self, api_key, api_secret, base_url):
        """Initialize with credentials"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()
        
    def _sign_request(self, method, path, data=None):
        """
        Sign API request with HMAC-SHA256
        
        Args:
            method: HTTP method (GET/POST/DELETE)
            path: API endpoint path
            data: Request payload
            
        Returns:
            headers: Signed headers with timestamp and signature
        """
        
    def fetch_ticker(self, symbol):
        """
        Get current ticker data
        
        Endpoint: GET /v2/tickers/{symbol}
        
        Returns:
            {
                'symbol': 'BTCUSD',
                'mark_price': 111246.50,
                'last_price': 111250.00,
                'bid': 111241.00,
                'ask': 111252.00,
                'volume_24h': 1234567.89
            }
        """
        
    def create_order(self, symbol, side, quantity, price=None, order_type='limit'):
        """
        Place order on exchange
        
        Args:
            symbol: Trading pair (BTCUSD)
            side: 'buy' or 'sell'
            quantity: Order size (contracts)
            price: Limit price (None for market)
            order_type: 'limit', 'market', 'post_only'
            
        Returns:
            {
                'id': 'order_123456',
                'symbol': 'BTCUSD',
                'side': 'buy',
                'price': 109000.00,
                'quantity': 1,
                'status': 'pending',
                'created_at': 1730304000
            }
        """
        
    def cancel_order(self, order_id):
        """Cancel specific order"""
        
    def fetch_positions(self):
        """Get all open positions"""
        
    def fetch_balance(self):
        """Get account balance"""
```

**Error Handling:**

```python
# Retry logic with exponential backoff
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, Timeout))
)
def _request(self, method, path, data=None):
    """Execute API request with retry logic"""
```

### 3.4 Config Manager (config_manager_core.py)

**Configuration Loading & Validation**

**File:** `bot/config/config_manager_core.py` (943 lines)

**Purpose:** Load, validate, and hot-reload configuration

**Key Functions:**

```python
def load_config(file_path='grid_config.env'):
    """
    Load configuration from file
    
    Returns:
        dict: Parsed configuration with defaults
        
    Validation:
        - Type checking (int, float, bool, str)
        - Range validation (min/max)
        - Dependency checking
        - Security validation
    """
    
def validate_grid_params(config):
    """
    Validate grid parameters
    
    Checks:
        1. GRID_LOWER < GRID_UPPER
        2. GRID_STEP > 0
        3. REFERENCE_LEVEL within range
        4. Step size reasonable (0.5-2% of price)
        5. Sufficient levels (>= 5)
        
    Raises:
        ValueError: If validation fails
    """
    
def watch_config(callback):
    """
    Monitor config file for changes
    
    Args:
        callback: Function to call when config changes
        
    Interval:
        Every 5 seconds
        
    Implementation:
        Check file modification time (mtime)
        If changed: reload, validate, callback
    """
```

**Hot Reload Implementation:**

```python
# In iv_rv_tracker.py (lines 67-188)
class IVRVTracker:
    def __init__(self, config_path='grid_config.env'):
        self._config_file_path = Path(config_path)
        self._last_config_mtime = 0
        
    def _check_config_file_changed(self):
        """Check if config file modified"""
        current_mtime = self._config_file_path.stat().st_mtime
        if current_mtime > self._last_config_mtime:
            self._last_config_mtime = current_mtime
            return True
        return False
        
    def _reload_config(self):
        """Reload config if changed"""
        if self._check_config_file_changed():
            self.config = load_config(self._config_file_path)
            log.info("Config reloaded - hot reload successful")
```

### 3.5 Volatility Collector (delta_volatility_collector.py)

**IV/RV Data Collection**

**File:** `bot/volatility/delta_volatility_collector.py` (893 lines)

**Purpose:** Collect and store implied & realized volatility

**Database Schema:**

```sql
-- volatility.db

CREATE TABLE iv_snapshots (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    iv REAL NOT NULL,
    source TEXT DEFAULT 'delta',
    num_options INTEGER,
    atm_strike REAL
);

CREATE TABLE rv_snapshots (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    rv_1h REAL,
    rv_1d REAL,
    rv_7d REAL,
    rv_30d REAL,
    num_candles INTEGER
);

CREATE INDEX idx_iv_time ON iv_snapshots(timestamp);
CREATE INDEX idx_rv_time ON rv_snapshots(timestamp);
```

**Key Methods:**

```python
class DeltaVolatilityCollector:
    def _fetch_and_store_iv(self):
        """
        Fetch implied volatility from Delta Exchange
        
        Method:
            1. Get options chain for nearest expiry
            2. Filter ATM options (±5% of current price)
            3. Calculate weighted average IV
            4. Store in database
            
        Returns:
            float: Current IV percentage (e.g., 45.2)
        """
        
    def _fetch_and_store_rv(self, timeframe='1d'):
        """
        Calculate realized volatility from price history
        
        Args:
            timeframe: '1h', '1d', '7d', or '30d'
            
        Method:
            1. Fetch OHLCV candles
            2. Calculate log returns
            3. Compute standard deviation
            4. Annualize to percentage
            5. Store in database
            
        Returns:
            float: Realized volatility (e.g., 38.5)
        """
        
    def get_latest_values(self):
        """
        Get most recent IV and RV values
        
        Returns:
            {
                'iv': 45.2,
                'rv_1h': 37.9,
                'rv_1d': 36.9,
                'rv_7d': 28.6,
                'rv_30d': 44.3,
                'spread': 8.3,  # iv - rv_1d
                'timestamp': 1730304000
            }
        """
        
    def collector_loop(self):
        """
        Main collection loop (every 30 seconds)
        
        Actions:
            1. Fetch IV
            2. Fetch RV (all timeframes)
            3. Store in database
            4. Broadcast via WebSocket (if callback)
            5. Cleanup old data (>90 days)
        """
```

---

## 4. Trading Strategy

### Grid Trading Logic

**Concept:**
Place BUY orders below current price, SELL (TP) orders above entry.

**Implementation:**

```python
# Initial state
price = 110000  # Current BTC price
ref = 110000    # Reference level
step = 1000     # Grid step
max_open = 3    # Max positions

# Bot starts
first_buy = ref - step  # 109000
bot.place_order('buy', quantity=1, price=first_buy)

# Price drops to 109000 → BUY fills
bot.on_fill_detected({
    'price': 109000,
    'quantity': 1,
    'side': 'buy'
})

# Bot places TP
tp_price = 109000 + step  # 110000
bot.place_order('sell', quantity=1, price=tp_price, reduce_only=True)

# Bot places next BUY
next_buy = 109000 - step  # 108000
bot.place_order('buy', quantity=1, price=next_buy)

# Price rises to 110000 → TP fills → Profit: $1000!
# Bot places new BUY @ 109000

# Repeat infinitely...
```

### State Machine

```
┌──────────────────────────────────────────┐
│           GRID BOT STATE MACHINE         │
└──────────────────────────────────────────┘

States:
  1. IDLE       - No positions, no pending orders
  2. WAITING    - Pending BUY placed, waiting for fill
  3. FILLED     - BUY filled, placing TP
  4. HOLDING    - Position open, TP active, next BUY placed
  5. HALTED     - Volatility halt, no new orders

Transitions:

IDLE → WAITING
  Trigger: Bot start
  Action: Place first BUY @ (REF - STEP)

WAITING → FILLED
  Trigger: BUY order fills
  Action: Detect fill via WebSocket

FILLED → HOLDING
  Trigger: TP placement successful
  Action: Place next BUY (if max_open not reached)

HOLDING → HOLDING
  Trigger: TP fills (profit!)
  Action: Remove from open_tranches, place new BUY

HOLDING → WAITING
  Trigger: TP fills, last position closed
  Action: Only pending BUY remains

ANY → HALTED
  Trigger: Volatility exceeds limits
  Action: Cancel pending BUY, keep TPs active

HALTED → WAITING/HOLDING
  Trigger: Volatility normalizes
  Action: Opportunistic recovery or normal resume
```

### Fill Detection

**Dual System:**

```python
# Primary: WebSocket (0.05s detection)
def _on_websocket_message(self, message):
    if message['type'] == 'trade':
        if message['side'] == 'buy' and message['order_id'] in self.our_orders:
            self._on_fill_detected(message)

# Backup: REST Polling (every 20s)
def _poll_for_fills(self):
    while True:
        orders = self.client.fetch_orders(status='filled')
        for order in orders:
            if order['id'] not in self._processed_fills:
                self._on_fill_detected(order)
        time.sleep(20)
```

**Deduplication:**

```python
self._processed_fills = set()  # Track processed fill IDs

def _on_fill_detected(self, fill):
    fill_id = fill['id']
    if fill_id in self._processed_fills:
        return  # Already processed, skip
    
    self._processed_fills.add(fill_id)
    # ... process fill
```

### Grid Calculation

```python
def _calculate_grid(self):
    """Calculate all grid levels"""
    lower = self.config.GRID_LOWER  # 105000
    upper = self.config.GRID_UPPER  # 120000
    step = self.config.GRID_STEP    # 1000
    
    levels = []
    price = lower
    while price <= upper:
        levels.append(price)
        price += step
    
    # levels = [105000, 106000, ..., 120000]
    # Total: 16 levels
    
    return {
        'lower': lower,
        'upper': upper,
        'step': step,
        'levels': levels,
        'count': len(levels)
    }
```

---

## 5. API Documentation

### WebUI Backend API

**Base URL:** `http://localhost:5555/api`

#### Health & Status

**GET /api/health**
```json
Response:
{
  "status": "healthy",
  "timestamp": "2025-10-30T13:15:30Z",
  "uptime": 7200,
  "bot_running": true
}
```

**GET /api/bot/status**
```json
Response:
{
  "running": true,
  "mode": "live",
  "pid": 7926,
  "uptime": "2h 15m",
  "last_heartbeat": "2025-10-30T13:15:28Z"
}
```

**GET /api/trading_status**
```json
Response:
{
  "btc_price": 111246.50,
  "change_24h_pct": 2.3,
  "bid": 111241.00,
  "ask": 111252.00,
  "pending_orders": 5,
  "open_positions": 2,
  "upnl_inr": 125.50
}
```

#### Configuration

**GET /api/config/flat**
```json
Response:
{
  "GRID_LOWER": 105000.0,
  "GRID_UPPER": 120000.0,
  "GRID_STEP": 1000.0,
  "REFERENCE_LEVEL": 110000.0,
  "GRIDBOT_LOT": 1,
  "MAX_OPEN_POSITIONS": 3,
  // ... all 171 parameters
}
```

**POST /api/config**
```json
Request:
{
  "GRID_STEP": 500.0,
  "MAX_OPEN_POSITIONS": 5
}

Response:
{
  "success": true,
  "applied": true,
  "changes": ["GRID_STEP", "MAX_OPEN_POSITIONS"],
  "reload_time": 5.2
}
```

#### Trading Operations

**POST /api/bot/start**
```json
Request:
{
  "mode": "live",  // or "demo"
  "duration": "infinite"  // or seconds (e.g., 3600)
}

Response:
{
  "success": true,
  "pid": 7926,
  "message": "Bot started successfully"
}
```

**POST /api/bot/stop**
```json
Response:
{
  "success": true,
  "message": "Bot stopped gracefully"
}
```

**GET /api/positions**
```json
Response:
{
  "positions": [
    {
      "symbol": "BTCUSD",
      "side": "long",
      "quantity": 1,
      "entry_price": 109000.0,
      "current_price": 111246.5,
      "upnl": 2246.5,
      "upnl_pct": 2.06,
      "tp_id": "order_123456",
      "tp_price": 110000.0
    }
  ],
  "total_upnl": 2246.5
}
```

#### Volatility

**GET /api/risk/volatility/latest**
```json
Response:
{
  "iv": 45.2,
  "rv_1h": 37.9,
  "rv_1d": 36.9,
  "rv_7d": 28.6,
  "rv_30d": 44.3,
  "spread": 8.3,
  "timestamp": 1730304000,
  "safe": true,
  "halted": false
}
```

**GET /api/risk/volatility/historical?timeframe=daily**
```json
Query Params:
  - timeframe: hourly|daily|weekly|monthly

Response:
{
  "timeframe": "daily",
  "data": [
    {
      "timestamp": 1730217600,
      "iv": 44.5,
      "rv": 36.2
    },
    // ... more points
  ],
  "count": 30
}
```

#### Logs

**GET /api/logs?level=ERROR&limit=50**
```json
Query Params:
  - level: INFO|WARNING|ERROR|CRITICAL
  - limit: Max number of logs (default: 100)
  - since: Unix timestamp (optional)

Response:
{
  "logs": [
    {
      "timestamp": "2025-10-30T13:15:30",
      "level": "ERROR",
      "component": "GridBot",
      "message": "API rate limit exceeded",
      "details": {...}
    }
  ],
  "count": 12
}
```

### WebSocket Events

**Connect:** `ws://localhost:5555/socket.io`

**Events (Server → Client):**

```javascript
// State snapshot (every 2 seconds)
socket.on('state_snapshot', (data) => {
  /*
  {
    btc_price: 111246.50,
    pending_orders: 5,
    open_positions: 2,
    upnl: 125.50,
    timestamp: 1730304000
  }
  */
});

// Configuration updated
socket.on('config_updated', (data) => {
  /*
  {
    parameter: 'GRID_STEP',
    old_value: 1000.0,
    new_value: 500.0
  }
  */
});

// Bot status changed
socket.on('bot_status', (data) => {
  /*
  {
    running: true,
    mode: 'live',
    pid: 7926
  }
  */
});

// New log entry
socket.on('log_entry', (data) => {
  /*
  {
    level: 'INFO',
    message: 'Fill detected @ $109,000',
    timestamp: 1730304000
  }
  */
});

// Volatility update
socket.on('volatility_update', (data) => {
  /*
  {
    iv: 45.2,
    rv: 36.9,
    safe: true
  }
  */
});
```

**Events (Client → Server):**

```javascript
// Subscribe to volatility updates
socket.emit('subscribe_volatility');

// Unsubscribe
socket.emit('unsubscribe_volatility');
```

---

## 6. Database Schema

### volatility.db (SQLite)

**Table: iv_snapshots**
```sql
CREATE TABLE iv_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,           -- Unix timestamp
    iv REAL NOT NULL,                     -- Implied volatility (%)
    source TEXT DEFAULT 'delta',          -- Data source
    num_options INTEGER,                  -- Number of options used
    atm_strike REAL,                      -- ATM strike price
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_iv_timestamp ON iv_snapshots(timestamp DESC);
```

**Table: rv_snapshots**
```sql
CREATE TABLE rv_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    rv_1h REAL,                           -- Realized volatility 1h (%)
    rv_1d REAL,                           -- Realized volatility 1d (%)
    rv_7d REAL,                           -- Realized volatility 7d (%)
    rv_30d REAL,                          -- Realized volatility 30d (%)
    num_candles INTEGER,                  -- Number of candles used
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_rv_timestamp ON rv_snapshots(timestamp DESC);
```

**Queries:**

```sql
-- Get latest IV
SELECT iv, timestamp 
FROM iv_snapshots 
ORDER BY timestamp DESC 
LIMIT 1;

-- Get hourly IV for last 24 hours
SELECT timestamp, iv
FROM iv_snapshots
WHERE timestamp > (strftime('%s', 'now') - 86400)
  AND timestamp % 3600 < 60  -- Sample every hour
ORDER BY timestamp;

-- Get all RV timeframes
SELECT rv_1h, rv_1d, rv_7d, rv_30d
FROM rv_snapshots
ORDER BY timestamp DESC
LIMIT 1;

-- Cleanup old data (>90 days)
DELETE FROM iv_snapshots
WHERE timestamp < (strftime('%s', 'now') - 7776000);

DELETE FROM rv_snapshots
WHERE timestamp < (strftime('%s', 'now') - 7776000);
```

---

## 7. Configuration System

### Environment Variables

**File:** `grid_config.env` (1535 lines)

**Categories:**

1. **Trading Mode** (Lines 31-45)
2. **Grid Parameters** (Lines 66-78)
3. **Position Limits** (Lines 90-110)
4. **Safety Limits** (Lines 130-200)
5. **Volatility** (Lines 546-564)
6. **API Settings** (Lines 800-850)
7. **Features** (Lines 1400-1535)

**Example:**

```bash
# Trading Mode
TRADING_MODE=live
EXECUTE_ORDERS=true
I_UNDERSTAND_LIVE=YES

# Grid Parameters
GRID_LOWER=105000.0
GRID_UPPER=120000.0
GRID_STEP=1000.0
REFERENCE_LEVEL=110000.0
GRIDBOT_LOT=1
MAX_OPEN_POSITIONS=3

# Safety Limits
MAX_ACCOUNT_LOSS_INR=25000
GUARDIAN_MAX_ACCOUNT_LOSS_INR=20000
MAX_MARGIN_UTILIZATION=40

# Volatility
VOLATILITY_MAX_IV=45
VOLATILITY_MAX_RV=55
VOLATILITY_MAX_SPREAD=10

# Features
ENABLE_OPPORTUNISTIC_RECOVERY=true
HOT_RELOAD=1
ENABLE_TELEGRAM_ALERTS=true
```

### Loading Process

```python
# 1. Load from file
config = load_config('grid_config.env')

# 2. Apply defaults
config = apply_defaults(config)

# 3. Validate
validate_config(config)

# 4. Type coercion
config = coerce_types(config)

# 5. Return as object
return Config(**config)
```

### Hot Reload

**Monitored Files:**
- `grid_config.env`
- `state.json`

**Check Interval:** 5 seconds

**Reloadable Parameters:**
- ✅ Grid params (LOWER, UPPER, STEP, REF)
- ✅ Position limits
- ✅ Safety thresholds
- ✅ Volatility limits
- ✅ Feature toggles

**Non-Reloadable:**
- ❌ API keys
- ❌ Trading mode
- ❌ Database settings

---

## 8. Development Guide

### Setting Up Development Environment

```bash
# Clone repository
git clone <repo_url>
cd WorkingBot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd webui/frontend
npm install
npm run build

# Create config
cp grid_config.env.example grid_config.env
cp secrets/api_keys.env.example secrets/api_keys.env

# Edit configs
nano grid_config.env
nano secrets/api_keys.env

# Run tests
pytest tests/

# Start bot (demo mode)
python3 bot/run.py demo infinite
```

### Running Tests

```bash
# Unit tests
pytest tests/test_refactored_code.py -v

# Virtual test environment
python3 tests/virtual_test_environment.py

# Integration tests
pytest tests/test_integration.py -v

# Coverage report
pytest --cov=bot --cov-report=html
open htmlcov/index.html
```

### Code Style

**PEP 8 Compliance:**
```bash
# Check style
flake8 bot/ --max-line-length=100

# Auto-format
black bot/

# Type checking
mypy bot/
```

**Naming Conventions:**
- Variables: `snake_case`
- Functions: `snake_case()`
- Classes: `PascalCase`
- Constants: `UPPER_CASE`
- Private methods: `_leading_underscore()`

### Adding New Features

**1. Create feature branch:**
```bash
git checkout -b feature/new-feature
```

**2. Implement feature:**
```python
# bot/features/my_feature.py

class MyFeature:
    """Feature description"""
    
    def __init__(self, config):
        self.config = config
        
    def execute(self):
        """Main logic"""
        pass
```

**3. Add tests:**
```python
# tests/test_my_feature.py

def test_my_feature():
    feature = MyFeature(config)
    result = feature.execute()
    assert result == expected
```

**4. Update configuration:**
```bash
# grid_config.env
ENABLE_MY_FEATURE=true
MY_FEATURE_PARAM=value
```

**5. Document:**
- Update USER_MANUAL.md
- Add inline help to WebUI
- Update API documentation

**6. Submit PR:**
```bash
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

### Debugging

**Logging:**
```python
import logging
log = logging.getLogger(__name__)

log.debug("Debug message")
log.info("Info message")
log.warning("Warning message")
log.error("Error message")
log.critical("Critical message")
```

**Breakpoints:**
```python
import pdb; pdb.set_trace()  # Python debugger
```

**Log Analysis:**
```bash
# All errors
grep ERROR bot_live.log

# All fills
grep "FILL\|Fill detected" bot_live.log

# Specific time range
sed -n '/2025-10-30 13:00/,/2025-10-30 14:00/p' bot_live.log
```

### Performance Optimization

**Profiling:**
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... code to profile

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

**Memory Profiling:**
```bash
pip install memory_profiler

python -m memory_profiler bot/run.py demo 60
```

---

## 📚 Additional Resources

### Code References

- **Main Bot:** `bot/strategy/gbot_ws.py` (Lines 340-404: Fill detection)
- **Guardian:** `bot/guardian/guardian_bot.py` (Lines 234-289: Loss monitoring)
- **Config:** `bot/config/config_manager_core.py` (Lines 67-188: Hot reload)
- **WebUI:** `webui/backend/app.py` (Lines 7466-7640: API endpoints)

### External Documentation

- **Delta Exchange API:** https://docs.delta.exchange/
- **Flask:** https://flask.palletsprojects.com/
- **React:** https://react.dev/
- **WebSocket:** https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

---

**Last Updated:** October 30, 2025  
**Version:** 3.9.0  
**Status:** Production Ready ✅

**For Questions:** See USER_MANUAL.md or START_HERE.md
