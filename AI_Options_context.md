# Options Trading Module - Complete Context

**Created:** January 5, 2026  
**Last Updated:** January 12, 2026  
**Purpose:** Comprehensive documentation of all options-related code and documentation in the WorkingBot project  
**Status:** Production Ready (MVP + Enhancements + Strategy Builder + Build Your Own Strategy)

---

## Table of Contents

1. [Overview](#overview)
2. [⚠️ CRITICAL FIX LOG - January 2026](#critical-fix-log)
3. [Documentation Files](#documentation-files)
4. [Code Architecture](#code-architecture)
5. [Backend Implementation](#backend-implementation)
6. [Frontend Implementation](#frontend-implementation)
7. [API Endpoints](#api-endpoints)
8. [Key Features](#key-features)
9. [File Structure](#file-structure)
10. [Integration Points](#integration-points)

---

## Overview

The Options Trading Module is a **completely isolated** system for managing options positions on Delta Exchange. It provides:

- ✅ **Position Tracking**: Real-time monitoring of options positions
- ✅ **Order Execution**: One-click close/add to positions
- ✅ **Options Chain**: Market data viewer for all strikes/expiries
- ✅ **Strategy Builder**: Multi-leg strategy execution (Straddle, Strangle, Iron Condor, etc.)
- ✅ **Build Your Own Strategy**: Custom multi-leg, multi-expiry strategies with one-click execution
- ✅ **Automation**: Rule-based entry/exit conditions
- ✅ **Payoff Diagrams**: Visual P&L projections

**Design Principle:** Zero conflict with existing GridBot - complete separation of concerns.

### Production-Ready Utilities (Imported from OptionBot - Jan 12, 2026)

| Utility | Location | Purpose |
|---------|----------|---------|
| Rate Limiter | `webui/backend/utils/rate_limiter.py` | API rate limiting |
| Custom Exceptions | `webui/backend/utils/exceptions.py` | Error hierarchy |
| Option Validator | `webui/backend/options_strategy/option_validator.py` | Pre-execution validation |
| Data Validator | `webui/backend/options_strategy/data_validator.py` | Market data quality |
| Advanced Risk Manager | `webui/backend/options_strategy/advanced_risk_manager.py` | VaR, Sharpe metrics |
| Health Monitor | `webui/backend/utils/health_monitor.py` | System health |

---

## ⚠️ CRITICAL FIX LOG - January 2026

### January 12, 2026 - Build Your Own Strategy Feature

**NEW FEATURE: Custom Multi-Leg Strategy Builder**

Added "Build Your Own Strategy" tab to Strategy Builder that allows:
- Any number of legs (unlimited)
- Different expiries per leg (multi-expiry strategies)
- Real-time premium calculation
- Net Greeks calculation (Delta, Gamma, Theta, Vega)
- Credit/Debit classification
- One-click execution

**File:** `webui/frontend/src/components/optionsStrategy/CustomStrategyBuilder.js`

**Features:**
- Add/remove legs dynamically
- Auto-fetch available expiries from Delta Exchange
- Strike selection with ATM highlighting
- Per-leg quantity adjustment
- Validation before execution
- Strategy summary with net premium

**API Endpoint:** `POST /api/options-strategy/create-custom`

---

### January 12, 2026 - Strategy Builder Critical Fixes

**Issues Fixed:**
1. **Pink Card Styling** - Strategy type selector cards unreadable in dark mode
2. **404 /api/market/spot-price** - Endpoint missing entirely  
3. **Expiry Dropdown Bug** - Showing only Fridays instead of real Delta Exchange expiries
4. **Strategy Execution "0 legs placed"** - Orders not reaching exchange

---

### Fix 1: Pink Card Styling (StrategyTypeSelector.js)

**File:** `webui/frontend/src/components/optionsStrategy/StrategyTypeSelector.js`

**Problem:** STRATEGY_CONFIG used light-mode hex colors (#f3e5f5) as bgColor, invisible in dark mode

**Solution:** Changed to rgba with 0.15 alpha transparency:
```javascript
// BEFORE (broken in dark mode)
bgColor: '#f3e5f5'

// AFTER (works in both light/dark mode)
bgColor: 'rgba(156, 39, 176, 0.15)'
```

**All Strategy Colors:**
- Straddle (purple): `rgba(156, 39, 176, 0.15)`
- Strangle (blue): `rgba(33, 150, 243, 0.15)`
- Iron Condor (orange): `rgba(255, 152, 0, 0.15)`
- Bull Call Spread (green): `rgba(76, 175, 80, 0.15)`
- Bear Put Spread (red): `rgba(244, 67, 54, 0.15)`
- Custom (grey): `rgba(158, 158, 158, 0.15)`

---

### Fix 2: Missing /api/market/spot-price Endpoint

**File Created:** `webui/backend/routes/market.py`

**Problem:** Frontend called `/api/market/spot-price` but endpoint didn't exist

**Solution:** Created new market blueprint:
```python
from flask import Blueprint, jsonify
import requests

market_bp = Blueprint('market', __name__, url_prefix='/api/market')

@market_bp.route('/spot-price', methods=['GET'])
def get_spot_price():
    # Fetches from Delta Exchange API with fallback
    # Falls back to guardian signal file or defaults
```

**Registration in app.py:**
```python
from .routes.market import market_bp
blueprints = [options_bp, options_chain_bp, options_strategy_bp, market_bp]
```

---

### Fix 3: Expiry Dropdown Bug (StrategyForm.js)

**File:** `webui/frontend/src/components/optionsStrategy/StrategyForm.js`

**Problem:** `getDefaultExpiries()` generated fake Friday-only dates instead of real expiries

**Old Code (BROKEN):**
```javascript
const getDefaultExpiries = () => {
  const expiries = [];
  const now = new Date();
  for (let i = 0; i < 8; i++) {
    const friday = getNextFriday(now, i);  // WRONG - only Fridays!
    expiries.push(formatExpiry(friday));
  }
  return expiries;
};
```

**New Code (FIXED):**
```javascript
// Fetch real expiries from API
useEffect(() => {
  const fetchExpiries = async () => {
    try {
      setExpiryLoading(true);
      const response = await fetch('/api/options-chain/expirations?underlying=BTC');
      const data = await response.json();
      if (data.expirations && data.expirations.length > 0) {
        // API returns DDMMYYYY format, convert to display format
        const formattedExpiries = data.expirations.map(exp => formatExpiryDate(exp));
        setAvailableExpiries(formattedExpiries);
        setSelectedExpiry(formattedExpiries[0]);
      }
    } catch (error) {
      console.error('Failed to fetch expiries:', error);
    } finally {
      setExpiryLoading(false);
    }
  };
  fetchExpiries();
}, []);
```

---

### Fix 4: Strategy Execution "0 legs placed"

**Root Cause:** Expiry format mismatch between API and Delta Exchange symbols

**Delta Exchange Symbol Format:**
- Symbol: `C-BTC-95000-DDMMYY` (6-digit date)
- API returns expiry: `DDMMYYYY` (8-digit date)
- Example: API gives `13012026`, but symbol needs `130126`

**File 1:** `webui/backend/options_strategy/strategy_manager.py`

**Fix in create_strategy():**
```python
def create_strategy(self, name: str, strategy_type: str, expiry: str, ...):
    # Convert DDMMYYYY to DDMMYY for Delta Exchange symbols
    expiry_formatted = expiry
    if len(expiry) == 8:
        # DDMMYYYY -> DDMMYY (remove century from year)
        expiry_formatted = expiry[0:4] + expiry[6:8]
        logger.info(f"Converted expiry format: {expiry} -> {expiry_formatted}")
```

**Same fix in create_custom_strategy():**
```python
def create_custom_strategy(self, name: str, legs: List[Dict], expiry: str, ...):
    expiry_formatted = expiry
    if len(expiry) == 8:
        expiry_formatted = expiry[0:4] + expiry[6:8]
        logger.info(f"Converted expiry format: {expiry} -> {expiry_formatted}")
```

**File 2:** `webui/backend/options_strategy/leg_executor.py`

**Improved _validate_legs():**
```python
def _validate_legs(self, legs: List[Dict]) -> Tuple[bool, str]:
    # Don't fail on missing ticker - just warn
    for leg in legs:
        ticker = self.api_client.get_option_ticker(symbol)
        if not ticker:
            logger.warning(f"Could not fetch ticker for {symbol} - will attempt anyway")
            # Continue instead of returning False
```

**Improved _execute_leg() with market order fallback:**
```python
def _execute_leg(self, leg: Dict, strategy_id: str) -> Dict:
    current_price = leg.get('current_price', 0)
    if current_price == 0 or current_price is None:
        logger.warning(f"No current price for {symbol}, using market order")
        order_type = 'market_order'
        limit_price = None
    else:
        order_type = 'limit_order'
        limit_price = str(current_price)
```

---

### Key Technical Details for Future Reference

**Symbol Format:** `{C|P}-BTC-{STRIKE}-{DDMMYY}`
- C = Call, P = Put
- DDMMYY = 6-digit date (day, month, 2-digit year)
- Example: `C-BTC-95000-130126` = BTC Call at 95000 strike, expiring Jan 13, 2026

**API Expiry Format:** `DDMMYYYY` (8-digit)
- Example: `13012026` = January 13, 2026

**Conversion Formula:**
```python
# DDMMYYYY -> DDMMYY
expiry_6digit = expiry_8digit[0:4] + expiry_8digit[6:8]
# "13012026" -> "1301" + "26" -> "130126"
```

---

## Documentation Files

### 1. **Option_chain.md**
**Location:** `/Users/ssr/Projects/WorkingBot/Option_chain.md`  
**Purpose:** Development plan for options chain market data scanner  
**Key Points:**
- Standalone options chain viewer with real-time market data
- Displays strikes, IVs, volumes, and OI for BTC/ETH options
- 3-phase implementation (Backend → Frontend → Advanced Features)
- Estimated time: 10-14 hours (Basic), 14-20 hours (Advanced)
- Risk Level: LOW (fully isolated from trading system)

### 2. **Option_strategy.md**
**Location:** `/Users/ssr/Projects/WorkingBot/Option_strategy.md`  
**Purpose:** Strategy builder development plan  
**Key Points:**
- Automated strategy execution (Straddle, Strangle, Iron Condor, etc.)
- Multi-leg order execution with position management
- Entry/exit conditions with auto-execution
- Feasibility: ✅ HIGHLY DOABLE
- Risk Level: MEDIUM (affects trading execution)

### 3. **Options_automation.md**
**Location:** `/Users/ssr/Projects/WorkingBot/Options_automation.md`  
**Purpose:** Automated options trading rules engine  
**Key Points:**
- 5-phase implementation (MVP → Advanced Features)
- Alert-only system → Dry Run → Real Execution
- Entry/exit conditions, risk controls, templates
- Estimated time: ~10 days for full system
- Safety-first approach with multiple confirmation layers

### 4. **OPTIONS_MODULE_FILE_STRUCTURE.md**
**Location:** `/Users/ssr/Projects/WorkingBot/OPTIONS_MODULE_FILE_STRUCTURE.md`  
**Purpose:** Complete file structure and separation strategy  
**Key Points:**
- 24 new files, 0 grid bot files modified
- Complete namespace isolation
- Independent deployment capability
- Clear boundaries between options and grid bot

### 5. **OPTIONS_STRATEGY_PHASE1_COMPLETE.md**
**Location:** `/Users/ssr/Projects/WorkingBot/OPTIONS_STRATEGY_PHASE1_COMPLETE.md`  
**Purpose:** Status update for strategy builder Phase 1  
**Key Points:**
- Backend foundation complete
- 6 built-in strategies (Straddle, Strangle, Iron Condor, etc.)
- SQLite persistence
- Multi-leg execution engine
- API endpoints documented

### 6. **OPTIONS_TRADING_FINAL_DECISION.md**
**Location:** `/Users/ssr/Projects/WorkingBot/OPTIONS_TRADING_FINAL_DECISION.md`  
**Purpose:** Decision document for phased approach  
**Key Points:**
- MVP (Phase 1): Position management only
- Full Automation (Phase 2): Options chain selector
- Recommendation: Execute MVP first, evaluate after 1-2 weeks
- Time investment: MVP 10-12 hrs, Full 16-21 hrs

### 7. **OPTIONS_TRADING_IMPLEMENTATION_PLAN.md**
**Location:** `/Users/ssr/Projects/WorkingBot/OPTIONS_TRADING_IMPLEMENTATION_PLAN.md`  
**Purpose:** Phase-wise implementation plan  
**Key Points:**
- 6 phases: Backend Tracking → Order Execution → Frontend → Safety → Testing → Documentation
- Timeline: 10-12 hours total
- Status: ✅ COMPLETE (All tests passed)
- Scope: Position Management (Track & Manage Existing Positions)

### 8. **OPTIONS_TRADING_PLAN_REVIEW.md**
**Location:** `/Users/ssr/Projects/WorkingBot/OPTIONS_TRADING_PLAN_REVIEW.md`  
**Purpose:** Expert review and analysis  
**Key Points:**
- Overall Assessment: ⭐⭐⭐⭐⭐ EXCELLENT
- Detailed analysis by phase
- Implementation recommendations
- Risk assessment
- Success metrics

### 9. **OPTIONS_TRADING_USER_GUIDE.md**
**Location:** `/Users/ssr/Projects/WorkingBot/Documentation/OPTIONS_TRADING_USER_GUIDE.md`  
**Purpose:** User documentation  
**Key Points:**
- Quick start guide
- Feature explanations
- Safety features
- Troubleshooting
- API reference
- Version history (v1.0 → v1.4)

---

## Code Architecture

### Backend Structure

```
bot/options/
├── __init__.py                    # Package initialization
├── utils/
│   └── options_helper.py         # Helper functions (PnL, expiry, liquidity)
└── config/
    └── __init__.py               # Config package

webui/backend/routes/options/
├── __init__.py                   # Blueprint package
└── options_control.py            # Main API routes
```

### Frontend Structure

```
webui/frontend/src/components/
├── options/
│   ├── OptionsPanel.js          # Main position management panel
│   ├── OptionsPayoffDiagram.js  # Payoff visualization
│   ├── index.js                 # Component exports
│   └── automation/              # Automation system
│       ├── components/          # UI components
│       ├── core/               # Business logic
│       ├── monitoring/         # Background services
│       ├── storage/            # Persistence
│       └── hooks/              # React hooks
└── optionsChain/
    └── OptionsChainPanel.js    # Options chain viewer
```

---

## Backend Implementation

### 1. **options_helper.py**
**Location:** `bot/options/utils/options_helper.py`  
**Purpose:** Utility functions for options trading

**Key Functions:**
- `calculate_unrealized_pnl(position, mid_price)` - Calculate P&L using mid price
- `calculate_pnl_percentage(position, mid_price)` - Calculate P&L percentage
- `check_expiry_warning(settlement_time)` - Check if option expiring soon
- `check_liquidity(ticker)` - Check bid-ask spread
- `determine_close_side(position_size)` - Determine buy/sell to close
- `enrich_position_data(position, ticker)` - Add real-time data to position

**Key Features:**
- Uses mid price (bid+ask)/2 for P&L calculation
- Expiry warnings: critical (<1h), warning (<24h), normal
- Liquidity check: spread < 10% considered liquid
- Cashflow calculation in USD

### 2. **options_control.py**
**Location:** `webui/backend/routes/options/options_control.py`  
**Purpose:** Flask blueprint for options API endpoints

**Key Features:**
- Rate limiting (2-second cooldown)
- Duplicate order prevention (5-second window)
- Guardian signal caching (5-second TTL)
- Smart order execution (Maker First → Market fallback)
- Position caching (3-second TTL)

**Order Types:**
- `maker_first`: Limit at mid-price, wait 2s, fallback to market
- `maker_only`: Only limit orders
- `market_only`: Immediate market order

**API Endpoints:**
- `GET /api/options/positions` - Get all positions
- `GET /api/options/ticker/<symbol>` - Get ticker data
- `POST /api/options/close` - Close position
- `POST /api/options/add` - Add to position
- `GET /api/options/status` - Module status

### 3. **unified_api_client.py (Options Methods)**
**Location:** `bot/api/unified_api_client.py`  
**Purpose:** Extended with options-specific methods

**Methods Added:**
- `get_all_positions_with_options()` - Fetch futures + options, separate by type
- `get_option_ticker(symbol)` - Get ticker with Greeks, quotes, mark price

**Implementation Details:**
- Filters options by symbol pattern (contains expiry date)
- Caches product details to avoid rate limiting
- Handles errors gracefully (skip failed positions)

---

## Frontend Implementation

### 1. **OptionsPanel.js**
**Location:** `webui/frontend/src/components/options/OptionsPanel.js`  
**Purpose:** Main options position management UI

**Key Features:**
- Real-time position tracking (5-second polling, configurable)
- Sortable table (drag-and-drop reordering)
- Expiry filtering (all / <24h / <7d / <30d)
- Position hiding (focus mode)
- Quick Mode (skip confirmation per strike)
- Keyboard shortcuts (B=Buy, S=Sell, C=Close, R=Refresh)
- Bulk operations (close multiple positions)
- Payoff diagram integration
- Automation button integration

**State Management:**
- Positions fetched from `/api/options/positions`
- Auto-refresh with configurable interval
- localStorage persistence for preferences
- Guardian signal display (GO/STOP)

**Order Execution:**
- Close: Market order with confirmation
- Add: Size input with quick presets (1, 2, 5, 10, 20, 50)
- Order types: Smart (maker_first), Market Only, Maker Only
- Default: 5 lots, Sell side, Smart order type

### 2. **OptionsPayoffDiagram.js**
**Location:** `webui/frontend/src/components/options/OptionsPayoffDiagram.js`  
**Purpose:** Visual payoff diagram (Sensibull-style)

**Key Features:**
- Dual lines: "On Expiry" (green/red) + "On Target Date" (blue)
- Interactive date slider (hourly precision for 0 DTE)
- BTC target price slider (-30% to +30%)
- Color-coded expiry area (green profit, red loss)
- Black-Scholes model for theoretical pricing
- Real IV calculation from market prices
- Zoom functionality (drag to select area)
- Projected profit display at target price

**Calculations:**
- Uses Black-Scholes for theoretical prices
- Calculates implied volatility from market prices
- Projects P&L at any price point and time
- Shows breakeven points

### 3. **OptionsChainPanel.js**
**Location:** `webui/frontend/src/components/optionsChain/OptionsChainPanel.js`  
**Purpose:** Options chain market data viewer

**Key Features:**
- Underlying selector (BTC/ETH)
- Expiry selector (dropdown)
- Real-time chain data (bid/ask, IV, volume, OI)
- Spot price and ATM strike display
- Days to expiry counter
- Put/Call ratio
- Auto-refresh toggle (10-second interval)
- Trading integration (click to open order dialog)
- Strategy leg selection mode

**Strategy Mode:**
- Multi-leg strategy building
- Leg selector sidebar
- Review dialog before execution
- Sequential/parallel execution

### 4. **Automation System**
**Location:** `webui/frontend/src/components/options/automation/`  
**Purpose:** Rule-based automation for options trading

**Components:**
- `AutomationButton.js` - ⚡ button in table
- `AutomationDialog.js` - Main modal with tabs
- `EntryConditionsTab.js` - Entry rules (IV, moneyness, premium, time)
- `ExecutionTab.js` - Order type, timing, scaling
- `ExitConditionsTab.js` - Profit target, stop loss, trailing stop
- `RiskControlsTab.js` - Position limits, daily loss limit

**Core Logic:**
- `ConditionEvaluator.js` - Rule evaluation engine
- `OrderExecutor.js` - API integration
- `RiskManager.js` - Risk checks
- `AutomationMonitor.js` - Background polling service
- `AutomationStorage.js` - localStorage persistence

**Phases:**
1. Phase 1: Alert-only (MVP)
2. Phase 2: Execution + Exit + Dry Run
3. Phase 3: Risk Controls + Real Orders
4. Phase 4: UI Polish + Templates
5. Phase 5: Advanced Features

---

## API Endpoints

### Options Positions: `http://localhost:5555/api/options`

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| GET | `/positions` | Get all options positions | - |
| GET | `/ticker/<symbol>` | Get ticker for option | - |
| POST | `/close` | Close position | `{symbol, confirm, order_preference}` |
| POST | `/add` | Add to position | `{symbol, size, side, confirm, order_preference}` |
| GET | `/status` | Module status | - |

### Options Chain: `http://localhost:5555/api/options-chain`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/expirations` | Get available expiry dates (DDMMYYYY format) |
| GET | `/chain` | Get full options chain for strike/expiry |
| GET | `/strikes` | Get available strikes for expiry |

### Strategy Builder: `http://localhost:5555/api/options-strategy`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/strategies` | List all strategies |
| GET | `/strategies/<id>` | Get strategy details |
| POST | `/strategies` | Create new strategy |
| POST | `/strategies/execute` | Execute strategy legs |
| DELETE | `/strategies/<id>` | Delete strategy |

### Market Data: `http://localhost:5555/api/market`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/spot-price` | Get BTC/ETH spot price |

### Request Examples

**Get Positions:**
```bash
curl http://localhost:5555/api/options/positions
```

**Close Position:**
```bash
curl -X POST http://localhost:5555/api/options/close \
  -H "Content-Type: application/json" \
  -d '{"symbol": "C-BTC-113000-300126", "confirm": true, "order_preference": "market_only"}'
```

**Add to Position:**
```bash
curl -X POST http://localhost:5555/api/options/add \
  -H "Content-Type: application/json" \
  -d '{"symbol": "C-BTC-113000-300126", "size": 5, "side": "sell", "confirm": true, "order_preference": "maker_first"}'
```

### Response Format

**Positions Response:**
```json
{
  "success": true,
  "positions": [
    {
      "product_symbol": "C-BTC-113000-300126",
      "size": -40,
      "entry_price": 190.0,
      "mark_price": 206.51,
      "mid_price": 206.0,
      "unrealized_pnl": -0.6604,
      "pnl_percentage": -8.69,
      "spread_pct": 0.25,
      "is_liquid": true,
      "greeks": {
        "delta": 0.65,
        "gamma": 0.001,
        "vega": 12.5,
        "theta": -0.5
      },
      "expiry_warning": {
        "is_expiring_soon": false,
        "hours_until_expiry": 120,
        "warning_level": "normal"
      }
    }
  ],
  "count": 9,
  "timestamp": "2026-01-04 13:30:00",
  "cached": false
}
```

---

## Key Features

### 1. **Position Management**
- ✅ Real-time tracking (5-second polling)
- ✅ One-click close
- ✅ Add to existing positions
- ✅ Bulk operations
- ✅ Sortable table
- ✅ Expiry filtering
- ✅ Position hiding (focus mode)

### 2. **Order Execution**
- ✅ Smart orders (maker first → market fallback)
- ✅ Rate limiting (2-second cooldown)
- ✅ Duplicate prevention (5-second window)
- ✅ Guardian integration (GO/STOP)
- ✅ Liquidity warnings
- ✅ Confirmation dialogs

### 3. **Options Chain**
- ✅ Market data viewer
- ✅ All strikes/expiries
- ✅ Real-time bid/ask, IV, volume, OI
- ✅ Trading integration
- ✅ Strategy leg selection

### 4. **Strategy Builder**
- ✅ Pre-built strategies (Straddle, Strangle, Iron Condor, etc.)
- ✅ Multi-leg execution
- ✅ Entry/exit conditions
- ✅ P&L tracking
- ✅ Payoff diagrams

### 5. **Automation**
- ✅ Rule-based entry/exit
- ✅ IV filters
- ✅ Moneyness filters
- ✅ Time windows
- ✅ Profit targets / Stop losses
- ✅ Risk controls

### 6. **Visualization**
- ✅ Payoff diagrams (Sensibull-style)
- ✅ Interactive date slider
- ✅ Target price projection
- ✅ Black-Scholes calculations
- ✅ Real IV from market

---

## File Structure

### Complete File List

**Backend:**
- `bot/options/__init__.py`
- `bot/options/utils/options_helper.py`
- `bot/options/config/__init__.py`
- `webui/backend/routes/options/__init__.py`
- `webui/backend/routes/options/options_control.py`
- `webui/backend/routes/market.py` - **NEW** (spot price endpoint)
- `webui/backend/options_chain/` - Options chain backend
- `webui/backend/options_strategy/` - Strategy builder backend:
  - `strategy_manager.py` - CRUD operations, expiry format conversion
  - `strategy_routes.py` - API endpoints for strategies
  - `leg_executor.py` - Multi-leg order execution
  - `chain_service.py` - Options chain data fetching

**Frontend:**
- `webui/frontend/src/components/options/OptionsPanel.js`
- `webui/frontend/src/components/options/OptionsPayoffDiagram.js`
- `webui/frontend/src/components/options/index.js`
- `webui/frontend/src/components/optionsChain/OptionsChainPanel.js`
- `webui/frontend/src/components/options/automation/` (multiple files)
- `webui/frontend/src/components/optionsStrategy/` - Strategy Builder:
  - `StrategyBuilder.js` - Main container component
  - `StrategyTypeSelector.js` - Strategy cards (dark mode fixed)
  - `StrategyForm.js` - Form with real expiry dates
  - `StrategyReviewDialog.js` - Execution confirmation
  - `ChainTable.js` - Strike selection table

**Documentation:**
- `Option_chain.md`
- `Option_strategy.md`
- `Options_automation.md`
- `OPTIONS_MODULE_FILE_STRUCTURE.md`
- `OPTIONS_STRATEGY_PHASE1_COMPLETE.md`
- `OPTIONS_TRADING_FINAL_DECISION.md`
- `OPTIONS_TRADING_IMPLEMENTATION_PLAN.md`
- `OPTIONS_TRADING_PLAN_REVIEW.md`
- `Documentation/OPTIONS_TRADING_USER_GUIDE.md`

**Modified Files (Minimal):**
- `bot/api/unified_api_client.py` - Added options methods
- `webui/backend/app.py` - Registered options blueprint
- `webui/frontend/src/App.js` - Added OptionsPanel component
- `config.yaml` - Added options section

---

## Integration Points

### 1. **UnifiedAPIClient**
- Options module extends `UnifiedAPIClient` with options methods
- Reuses existing rate limiting, circuit breaker, error handling
- No conflicts - both modules read from same client

### 2. **Guardian Integration**
- Options trading respects Guardian GO/STOP signals
- Cached signal check (5-second TTL)
- Trading disabled when Guardian is STOP

### 3. **Configuration**
- Options config in `config.yaml` under `options:` section
- Separate from grid bot config
- Can be enabled/disabled independently

### 4. **State Machine**
- Options trading checks bot state machine
- Respects NORMAL_TRADING / WAITING_FOR_GUARDIAN states
- Halts during RECOVERY_CHECK / HALTED

### 5. **WebUI Integration**
- Options panel added as new tab in WebUI
- Uses existing Material-UI theme
- Shares authentication/session management

---

## Safety Features

### 1. **Guardian Integration**
- ✅ Respects GO/STOP signals
- ✅ Cached checks (5-second TTL)
- ✅ Fail-safe defaults (STOP on error)

### 2. **Rate Limiting**
- ✅ 2-second cooldown between orders
- ✅ Prevents accidental double-clicks
- ✅ Shows countdown if too fast

### 3. **Duplicate Prevention**
- ✅ 5-second window blocks duplicate orders
- ✅ Hash-based request deduplication
- ✅ Prevents rapid-fire mistakes

### 4. **Confirmation Dialogs**
- ✅ Every order requires confirmation
- ✅ Shows position details and P&L
- ✅ Quick Mode can skip (per strike)

### 5. **Liquidity Checks**
- ✅ Warns on spread > 10%
- ✅ Still allows order (user decision)
- ✅ Protects against poor fills

### 6. **Expiry Warnings**
- ✅ Critical: < 1 hour (red badge)
- ✅ Warning: < 24 hours (yellow badge)
- ✅ Normal: > 24 hours (no badge)

---

## Configuration

### config.yaml Options Section

```yaml
options:
  enabled: true
  polling_interval_seconds: 5    # Position refresh interval
  rate_limit_seconds: 2          # Cooldown between orders
  max_spread_pct: 10.0           # Liquidity warning threshold
  guardian_integration: true     # Respect Guardian signals
  expiry_warning_hours: 24       # When to show expiry warnings
  liquidity_check: true          # Check spread before orders
```

---

## Version History

### v1.5 (Current - January 12, 2026)
- ✅ Fixed pink strategy cards (dark mode rgba colors)
- ✅ Created /api/market/spot-price endpoint
- ✅ Fixed expiry dropdown (real Delta Exchange expiries)
- ✅ Fixed strategy execution (DDMMYYYY→DDMMYY conversion)
- ✅ Improved leg executor with market order fallback
- ✅ Added extensive logging for debugging

### v1.4
- Sorted by expiry (nearest first)
- Quick Mode for instant orders
- Visual indicators (⚡ icon)
- Expiry highlighting
- Persistent settings

### v1.3
- Fixed order placement API
- Fixed quotes parsing
- New defaults (5 lots, Sell, Smart)
- All order types verified

### v1.2
- Concurrent ticker fetching (3x faster)
- Position caching (3s cache)
- Graceful error handling
- Port standardization

### v1.1
- Maker orders
- Quick presets
- Keyboard shortcuts

### v1.0
- Initial MVP release

---

## Testing

### Unit Tests
- `tests/options/test_api_methods.py` - API method tests
- `tests/options/test_integration.py` - Integration tests

### Manual Testing Checklist
- Position tracking
- Real-time updates
- Close position
- Add to position
- Rate limiting
- Guardian integration
- Error handling

---

## Future Enhancements

### Phase 2: Options Chain Selector
- Open NEW positions from bot (any strike/expiry)
- Full options chain UI
- Strike/expiry picker
- Zero Delta Exchange usage needed

### Phase 3: Advanced Features
- WebSocket real-time updates
- Greeks-based triggers
- Conditional chains
- Rolling strategies
- Backtesting
- Multi-position automation

---

## Summary

The Options Trading Module is a **production-ready, isolated system** for managing options positions. It provides:

- ✅ Complete separation from GridBot
- ✅ Real-time position tracking
- ✅ One-click order execution
- ✅ Options chain viewer
- ✅ Strategy builder (Straddle, Strangle, Iron Condor, Spreads, Custom)
- ✅ Multi-leg execution with proper expiry format handling
- ✅ Automation system
- ✅ Payoff diagrams
- ✅ Comprehensive safety features
- ✅ Dark mode compatible UI

**Status:** ✅ Production Ready (v1.5 - Strategy Builder Fixed)  
**Risk Level:** LOW (isolated module)  
**Integration:** Minimal (only 4 files modified from original codebase)  
**Deployment:** Independent (can enable/disable without affecting GridBot)

---

## Quick Troubleshooting Guide

### "0 legs placed" when executing strategy
1. Check backend logs for expiry format issues
2. Ensure expiry is DDMMYY (6-digit), not DDMMYYYY (8-digit)
3. Verify symbol format: `C-BTC-95000-130126`

### Strategy cards unreadable (pink/light colors)
1. Colors should use rgba with 0.15 alpha
2. Check StrategyTypeSelector.js bgColor values

### Expiry dropdown showing wrong dates
1. Should fetch from `/api/options-chain/expirations`
2. Check StrategyForm.js useEffect for API call

### 404 errors on API calls
1. Check if blueprint is registered in app.py
2. Verify route prefix matches frontend calls

---

**End of Document**

