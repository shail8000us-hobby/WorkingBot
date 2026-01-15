# 0DTE Bot - Complete File Structure

**Purpose:** Independent module structure with minimal intrusion into existing GridBot and Options systems.

---

## 📁 Complete Directory Structure

```
WorkingBot/
│
├── bot/
│   ├── strategy/
│   │   ├── zero_dte/                          # NEW MODULE (Independent)
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                      # Main orchestrator (600+ lines)
│   │   │   ├── balancer.py                    # Premium balancing logic (400+ lines)
│   │   │   ├── rollover.py                    # Strike rollover manager (350+ lines)
│   │   │   ├── monitor.py                     # Real-time monitoring (500+ lines)
│   │   │   ├── risk_manager.py                # Risk validation (300+ lines)
│   │   │   ├── config.py                      # Configuration loader (200+ lines)
│   │   │   ├── state_manager.py               # Session state management (250+ lines)
│   │   │   └── utils.py                       # Helper utilities (150+ lines)
│   │   │
│   │   ├── gridbot/                           # EXISTING (No changes)
│   │   │   └── async_grid_bot.py
│   │   │
│   │   └── options/                           # EXISTING (No changes)
│   │       ├── strategy_manager.py
│   │       ├── leg_executor.py
│   │       └── options_helper.py
│   │
│   └── api/
│       ├── zero_dte_api.py                    # NEW - REST API routes (400+ lines)
│       ├── unified_api_client.py              # EXISTING (No changes)
│       └── delta_client.py                    # EXISTING (No changes)
│
├── webui/
│   ├── backend/
│   │   └── app.py                             # MODIFIED (1 line: blueprint registration)
│   │
│   └── frontend/
│       └── src/
│           └── components/
│               ├── zero_dte/                  # NEW DIRECTORY
│               │   ├── ZeroDTEDashboard.js    # Main container (400+ lines)
│               │   ├── PremiumGauge.js        # CE vs PE visual (250+ lines)
│               │   ├── CountdownTimer.js      # Settlement countdown (150+ lines)
│               │   ├── RebalanceHistory.js    # Activity log (300+ lines)
│               │   ├── ControlPanel.js        # Start/Stop/Close (200+ lines)
│               │   ├── PnLTracker.js          # Profit/Loss display (180+ lines)
│               │   ├── GreeksDisplay.js       # Delta/Gamma/Theta/Vega (220+ lines)
│               │   ├── RiskIndicators.js      # Margin/Risk metrics (180+ lines)
│               │   └── ZeroDTE.css            # Styling
│               │
│               ├── options/                   # EXISTING (No changes)
│               │   └── OptionsPanel.js
│               │
│               └── grid/                      # EXISTING (No changes)
│                   └── GridPanel.js
│
├── config/
│   ├── zero_dte_config.yaml                   # NEW - Strategy configuration
│   ├── config.yaml                            # EXISTING (No changes)
│   └── schemas/
│       └── zero_dte_schemas.py                # NEW - Pydantic models (300+ lines)
│
├── database/
│   ├── zero_dte_sessions.db                   # NEW - Active sessions
│   ├── zero_dte_trades.db                     # NEW - Trade history
│   └── zero_dte_rebalances.db                 # NEW - Rebalancing log
│
├── tests/
│   └── zero_dte/                              # NEW - Test suite
│       ├── test_engine.py                     # Engine tests (400+ lines)
│       ├── test_balancer.py                   # Balancer tests (300+ lines)
│       ├── test_rollover.py                   # Rollover tests (250+ lines)
│       ├── test_monitor.py                    # Monitor tests (200+ lines)
│       ├── test_api.py                        # API tests (300+ lines)
│       └── fixtures/                          # Test data
│           ├── mock_option_chains.json
│           └── mock_positions.json
│
└── docs/
    └── zero_dte/                              # NEW - Documentation
        ├── ZERO_DTE_MASTER_PLAN.md            # Master plan (this file)
        ├── ZERO_DTE_PHASE1_BACKEND_CORE.md    # Phase 1 details
        ├── ZERO_DTE_PHASE2_MONITORING.md      # Phase 2 details
        ├── ZERO_DTE_PHASE3_WEBUI.md           # Phase 3 details
        ├── ZERO_DTE_PHASE4_TESTING.md         # Phase 4 details
        ├── ZERO_DTE_FILE_STRUCTURE.md         # This file
        └── API_DOCUMENTATION.md               # API reference
```

---

## 🔗 Integration Points

### 1. Existing Files MODIFIED (Minimal Changes)

#### **webui/backend/app.py**
```python
# BEFORE (line ~50)
from bot.api.options_control import options_bp
app.register_blueprint(options_bp, url_prefix='/api/options')

# AFTER (add 2 lines)
from bot.api.options_control import options_bp
from bot.api.zero_dte_api import zero_dte_bp  # NEW IMPORT
app.register_blueprint(options_bp, url_prefix='/api/options')
app.register_blueprint(zero_dte_bp, url_prefix='/api/zero-dte')  # NEW BLUEPRINT
```

**Lines Changed:** 2 lines added  
**Risk:** None (new blueprint, no conflicts)

---

#### **webui/frontend/src/App.js** (Optional - if adding menu item)
```javascript
// Add route for 0DTE dashboard (if needed)
import ZeroDTEDashboard from './components/zero_dte/ZeroDTEDashboard';

// In routes section:
<Route path="/zero-dte" element={<ZeroDTEDashboard />} />
```

**Lines Changed:** 3 lines added  
**Risk:** None (new route, no conflicts)

---

### 2. Existing Files USED (Read-Only, No Modifications)

These files are imported/used by 0DTE module but NOT modified:

- `bot/api/unified_api_client.py` - Delta Exchange API client
- `bot/strategy/options/options_helper.py` - Helper functions
- `bot/strategy/options/leg_executor.py` - Order execution (optional reuse)
- `config/loader.py` - Configuration loader
- `config/credentials.json` - API keys (read-only)
- `guardian_signal.txt` - Risk signal (read-only)

---

## 📊 Database Schema

### **zero_dte_sessions.db**

#### **Table: sessions**
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    underlying TEXT NOT NULL,              -- 'BTC' or 'ETH'
    expiry_date TEXT NOT NULL,             -- '2026-01-30'
    status TEXT NOT NULL,                  -- 'active', 'closed', 'stopped'
    start_time TEXT NOT NULL,              -- ISO timestamp
    end_time TEXT,                         -- ISO timestamp
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
    stop_reason TEXT,                      -- 'profit_target', 'time_exit', 'stop_loss', 'manual'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### **Table: current_positions**
```sql
CREATE TABLE current_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    leg_type TEXT NOT NULL,                -- 'CE' or 'PE'
    symbol TEXT NOT NULL,                  -- 'C-BTC-95000-30012026'
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
);
```

---

### **zero_dte_trades.db**

#### **Table: trades**
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trade_type TEXT NOT NULL,              -- 'entry', 'rebalance', 'rollover', 'exit'
    leg_type TEXT NOT NULL,                -- 'CE', 'PE', 'BOTH'
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                    -- 'sell', 'buy'
    strike REAL NOT NULL,
    lots INTEGER NOT NULL,
    premium REAL NOT NULL,
    order_id TEXT,
    execution_price REAL,
    status TEXT NOT NULL,                  -- 'pending', 'filled', 'partial', 'cancelled', 'failed'
    reason TEXT,                           -- 'initial_entry', 'premium_imbalance', 'strike_roll', 'profit_target'
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

---

### **zero_dte_rebalances.db**

#### **Table: rebalances**
```sql
CREATE TABLE rebalances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    rebalance_type TEXT NOT NULL,          -- 'lot_adjustment', 'strike_rollover'
    trigger_reason TEXT NOT NULL,          -- 'premium_imbalance_20pct', 'premium_below_5'
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
    action_taken TEXT,                     -- JSON: [{"action": "add_ce_lots", "lots": 2}]
    execution_status TEXT NOT NULL,        -- 'success', 'partial', 'failed'
    error_message TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

#### **Table: monitoring_snapshots**
```sql
CREATE TABLE monitoring_snapshots (
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
);
```

---

## 🔌 API Endpoints

### **Base URL:** `/api/zero-dte`

#### **Session Management**

**1. Start New Session**
```http
POST /api/zero-dte/session/start
Content-Type: application/json

{
    "underlying": "BTC",
    "expiry_date": "2026-01-30",
    "initial_lots": 5,
    "target_premium_min": 15,
    "target_premium_max": 30,
    "strike_offset_pct": 2.5
}

Response 200:
{
    "success": true,
    "session_id": "0dte_BTC_20260130_abc123",
    "entry_summary": {
        "ce_strike": 95000,
        "pe_strike": 91000,
        "ce_premium": 20.5,
        "pe_premium": 19.8,
        "ce_lots": 5,
        "pe_lots": 5,
        "total_premium_collected": 201.5
    }
}
```

**2. Get Active Session**
```http
GET /api/zero-dte/session/active

Response 200:
{
    "success": true,
    "session": {
        "session_id": "0dte_BTC_20260130_abc123",
        "status": "active",
        "start_time": "2026-01-30T10:00:00+05:30",
        "underlying": "BTC",
        "positions": {
            "ce": { "strike": 95000, "lots": 7, "premium": 15.2 },
            "pe": { "strike": 91000, "lots": 5, "premium": 21.3 }
        },
        "pnl": {
            "realized": 0,
            "unrealized": 45.5,
            "total": 45.5
        }
    }
}
```

**3. Stop Session (Manual Close)**
```http
POST /api/zero-dte/session/stop
Content-Type: application/json

{
    "session_id": "0dte_BTC_20260130_abc123",
    "reason": "manual"
}

Response 200:
{
    "success": true,
    "final_pnl": 167.8,
    "exit_summary": {
        "ce_exit_premium": 3.2,
        "pe_exit_premium": 2.8,
        "total_profit": 167.8
    }
}
```

---

#### **Real-Time Data**

**4. Get Current Status**
```http
GET /api/zero-dte/status

Response 200:
{
    "success": true,
    "is_active": true,
    "session_id": "0dte_BTC_20260130_abc123",
    "current_time": "2026-01-30T14:30:00+05:30",
    "time_to_expiry_minutes": 60,
    "positions": {
        "ce": {
            "symbol": "C-BTC-95000-30012026",
            "lots": 7,
            "current_premium": 12.3,
            "total_value": 86.1,
            "delta": 0.35,
            "gamma": 0.002
        },
        "pe": {
            "symbol": "P-BTC-91000-30012026",
            "lots": 5,
            "current_premium": 17.2,
            "total_value": 86.0,
            "delta": -0.42,
            "gamma": 0.003
        }
    },
    "premium_differential": {
        "ce_total": 86.1,
        "pe_total": 86.0,
        "imbalance_pct": 0.1,
        "is_balanced": true
    },
    "pnl": {
        "unrealized": 54.2,
        "realized": 0,
        "total": 54.2
    },
    "greeks": {
        "portfolio_delta": -0.07,
        "portfolio_gamma": 0.005,
        "portfolio_theta": -45.2,
        "portfolio_vega": 12.3
    }
}
```

**5. Get Rebalancing History**
```http
GET /api/zero-dte/rebalances?session_id=0dte_BTC_20260130_abc123&limit=20

Response 200:
{
    "success": true,
    "rebalances": [
        {
            "id": 3,
            "timestamp": "2026-01-30T13:45:00+05:30",
            "type": "lot_adjustment",
            "reason": "premium_imbalance_22pct",
            "before": { "ce_lots": 5, "pe_lots": 5, "imbalance": 22 },
            "after": { "ce_lots": 7, "pe_lots": 5, "imbalance": 2 },
            "action": "Added 2 CE lots",
            "status": "success"
        }
    ]
}
```

---

#### **Configuration**

**6. Get Configuration**
```http
GET /api/zero-dte/config

Response 200:
{
    "success": true,
    "config": {
        "rebalance_threshold_pct": 20,
        "min_premium_for_roll": 5,
        "exit_both_legs_below": 5,
        "forced_exit_time": "17:15",
        "stop_loss_amount": 5000,
        "maker_order_timeout_seconds": 2
    }
}
```

**7. Update Configuration**
```http
PUT /api/zero-dte/config
Content-Type: application/json

{
    "rebalance_threshold_pct": 15,
    "stop_loss_amount": 3000
}

Response 200:
{
    "success": true,
    "message": "Configuration updated"
}
```

---

## 🎨 WebUI Component Tree

```
ZeroDTEDashboard (Main Container)
│
├── ControlPanel
│   ├── StartSessionButton
│   ├── StopSessionButton
│   └── EmergencyCloseButton
│
├── StatusOverview
│   ├── SessionInfo (ID, start time, underlying)
│   ├── CountdownTimer (Time to 5:30 PM settlement)
│   └── StatusBadge (Active/Stopped/Closed)
│
├── PremiumGauge
│   ├── CEBar (Visual bar showing CE total premium)
│   ├── PEBar (Visual bar showing PE total premium)
│   ├── ImbalanceIndicator (Percentage difference)
│   └── BalanceStatus (Green/Yellow/Red)
│
├── PositionsTable
│   ├── CEPositionRow (Strike, Lots, Premium, Greeks)
│   └── PEPositionRow (Strike, Lots, Premium, Greeks)
│
├── PnLTracker
│   ├── PnLChart (Real-time P&L line chart)
│   ├── UnrealizedPnL (Current unrealized profit)
│   ├── RealizedPnL (Locked-in profit)
│   └── ROIMetrics (% return on margin)
│
├── GreeksDisplay
│   ├── DeltaGauge (Portfolio delta)
│   ├── GammaIndicator (Gamma exposure)
│   ├── ThetaDecay (Theta per hour)
│   └── VegaExposure (Vega sensitivity)
│
├── RebalanceHistory
│   ├── RebalanceTable (Timestamp, Action, Result)
│   └── RebalanceFilter (Filter by type/date)
│
└── RiskIndicators
    ├── MarginUtilization (% of margin used)
    ├── LiquidationDistance (Safety margin)
    ├── StopLossProgress (Distance to stop loss)
    └── GuardianStatus (GO/STOP signal)
```

---

## 📦 External Dependencies (New Packages)

### Python Dependencies
```txt
# Already in requirements.txt:
asyncio
aiohttp
pandas
numpy
sqlalchemy
pydantic
loguru

# May need to add:
pytz                # Timezone handling (IST)
python-dateutil     # Date parsing
```

### Frontend Dependencies
```json
// package.json additions:
{
  "dependencies": {
    "recharts": "^2.10.0",      // For P&L charts
    "date-fns": "^3.0.0",       // Date manipulation
    "date-fns-tz": "^2.0.0",    // Timezone handling
    "react-circular-progressbar": "^2.1.0"  // For gauges
  }
}
```

---

## 🔐 Security Considerations

### 1. API Authentication
- Reuse existing WebUI authentication
- No new authentication system needed
- Same session tokens as GridBot

### 2. Database Access
- SQLite databases in `database/` folder (same as GridBot)
- File permissions: 644 (read/write for bot user)
- No network exposure (local only)

### 3. API Key Usage
- Reuse existing `config/credentials.json`
- No new API keys needed
- Same Delta Exchange API client

---

## 🧪 Development Environment Setup

### 1. Create 0DTE Directory Structure
```bash
cd /Users/ssr/Projects/WorkingBot
mkdir -p bot/strategy/zero_dte
mkdir -p webui/frontend/src/components/zero_dte
mkdir -p tests/zero_dte/fixtures
mkdir -p docs/zero_dte
```

### 2. Initialize Python Module
```bash
touch bot/strategy/zero_dte/__init__.py
touch bot/api/zero_dte_api.py
```

### 3. Create Configuration File
```bash
touch config/zero_dte_config.yaml
```

### 4. Initialize Databases
```bash
# Databases will be created automatically by engine on first run
# Or manually:
sqlite3 database/zero_dte_sessions.db < schema.sql
```

---

## 📝 Naming Conventions

### Python Files
- **Module names:** `snake_case` (e.g., `premium_balancer.py`)
- **Class names:** `PascalCase` (e.g., `ZeroDTEEngine`)
- **Function names:** `snake_case` (e.g., `calculate_lot_adjustment()`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MIN_PREMIUM_THRESHOLD`)

### React Components
- **Component files:** `PascalCase.js` (e.g., `PremiumGauge.js`)
- **Component names:** `PascalCase` (e.g., `<PremiumGauge />`)
- **Props:** `camelCase` (e.g., `cePremium={20}`)

### Database Tables
- **Table names:** `snake_case` (e.g., `rebalances`)
- **Column names:** `snake_case` (e.g., `session_id`)

### API Endpoints
- **Routes:** `kebab-case` (e.g., `/api/zero-dte/session/start`)
- **Query params:** `snake_case` (e.g., `?session_id=abc123`)

---

## 🔄 State Management

### Backend State
- **Active session:** Stored in `zero_dte_sessions.db`
- **In-memory cache:** `state_manager.py` caches current session for fast access
- **Persistence:** Auto-save to database every 10s
- **Recovery:** On restart, reload last active session from database

### Frontend State
- **Global state:** React Context API (`ZeroDTEContext`)
- **Real-time updates:** WebSocket connection to backend
- **Polling fallback:** HTTP polling every 5s if WebSocket disconnects
- **Local storage:** Save user preferences (chart settings, filters)

---

## 📊 Logging Strategy

### Log Levels
- **DEBUG:** Detailed function calls, parameter values (development only)
- **INFO:** Session start/stop, rebalances, rollovers, exits
- **WARNING:** Premium imbalance detected, approaching stop loss
- **ERROR:** Failed orders, API errors, database errors
- **CRITICAL:** Emergency stop, liquidation risk, system crash

### Log Files
```
logs/
├── zero_dte_engine.log         # Main engine logs
├── zero_dte_balancer.log       # Rebalancing decisions
├── zero_dte_rollover.log       # Strike rollover logs
├── zero_dte_monitor.log        # Monitoring alerts
└── zero_dte_api.log            # API request/response logs
```

### Log Rotation
- **Max size:** 50 MB per file
- **Retention:** 7 days
- **Compression:** gzip after rotation
- **Format:** `{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {module}:{function}:{line} | {message}`

---

**Ready to start implementation?** Proceed to [Phase 1: Backend Core](ZERO_DTE_PHASE1_BACKEND_CORE.md)
