# Phase 3C: Documentation - COMPLETE DOCUMENTATION

## User Documentation

### Quick Start Guide: Multi-Symbol Trading

#### For New Users

**1. Check Available Symbols**
```bash
curl http://localhost:5556/api/symbols
```

**2. Select Symbol in WebUI**
- Open WebUI: `http://localhost:5556`
- Click symbol dropdown in header
- Select BTCUSD or ETHUSD
- All data updates automatically

**3. Start Trading a Symbol**
```bash
# Start BTCUSD bot
python3 bot/strategy/async_gridbot.py BTCUSD

# Or use PM2
pm2 start ecosystem.multi-symbol.config.js --only gridbot-btc-live
```

#### For Existing Users (v4.0 → v5.0 Migration)

**What Changed:**
- Config format: v4.0 (single-symbol) → v5.0 (multi-symbol)
- CLI: Now requires symbol argument: `python3 async_gridbot.py BTCUSD`
- WebUI: Symbol dropdown added to header
- Database: Symbol-specific files (no data mixing)

**Migration Steps:**
1. Backup your current setup
2. Switch to BTEH branch: `git checkout BTEH`
3. Run config migration: `python3 scripts/migrate_config_to_multi_symbol.py`
4. Restart services: `pm2 restart all`
5. Select symbol in WebUI dropdown

**Backward Compatibility:**
- V4.0 configs still work (single symbol only)
- No symbol argument = single-symbol mode
- Existing databases are NOT touched

---

## Developer Documentation

### Architecture Overview

```
Multi-Symbol Trading Bot v5.0
├── Configuration Layer (config.yaml)
│   ├── symbols: { BTCUSD, ETHUSD }
│   ├── capital_allocation
│   └── per-symbol: grid, safety, limits
│
├── Bot Layer (bot/strategy/async_gridbot.py)
│   ├── CLI: python async_gridbot.py <SYMBOL>
│   ├── Symbol validation & loading
│   └── Symbol-specific state files
│
├── WebUI Layer
│   ├── Backend (webui/backend/)
│   │   ├── /api/symbols - Symbol management
│   │   └── /api/monitoring/* - Per-symbol data
│   │
│   └── Frontend (webui/frontend/)
│       ├── SymbolSelector component
│       ├── SymbolContext (global state)
│       └── useSymbolAPI hook (auto params)
│
└── Guardian Layer (bot/guardian/)
    ├── Multi-symbol monitoring
    ├── Per-symbol risk calculations
    └── Unified STOP propagation
```

### Config Schema (v5.0)

```yaml
version: "5.0"
trading_mode: live

# Multi-symbol configuration
symbols:
  BTCUSD:
    enabled: true
    product_id: 139
    mode: LONG
    grid:
      geometry: { lower: 85000, upper: 95000, step: 500, reference: 88500 }
      limits: { max_open_positions: 50, lot_size: 5 }
    safety: { max_account_loss_inr: 100000, min_liquidation_distance_pct: 15 }
  
  ETHUSD:
    enabled: false  # Enable when ready
    product_id: 3136
    mode: LONG
    grid:
      geometry: { lower: 3000, upper: 4000, step: 50, reference: 3500 }
      limits: { max_open_positions: 30, lot_size: 10 }
    safety: { max_account_loss_inr: 50000, min_liquidation_distance_pct: 15 }

# Capital allocation
capital_allocation:
  total_capital_inr: 1000000
  btc_allocation_pct: 70
  eth_allocation_pct: 30
```

### API Documentation

#### Symbol Management API

**GET /api/symbols**
```bash
curl http://localhost:5556/api/symbols

Response:
{
  "symbols": [
    {
      "name": "BTCUSD",
      "enabled": true,
      "product_id": 139,
      "status": "active",
      "grid": { "lower": 85000, "upper": 95000, "step": 500 },
      "monitoring_file": "data/monitoring_snapshot_BTCUSD_LONG.json",
      "database_file": "data/bot_events_BTCUSD_LONG.db"
    },
    ...
  ],
  "config_version": "5.0",
  "total": 2,
  "enabled_count": 1
}
```

**GET /api/symbols/<symbol>**
```bash
curl http://localhost:5556/api/symbols/BTCUSD

Response:
{
  "name": "BTCUSD",
  "enabled": true,
  "product_id": 139,
  "mode": "LONG",
  "status": "active",  # active | stale | disabled | not_running
  "grid": {...},
  "limits": {...},
  "safety": {...}
}
```

#### Monitoring API (Multi-Symbol)

All monitoring endpoints now accept `?symbol=X&mode=Y` query parameters:

```bash
# BTCUSD monitoring
curl http://localhost:5556/api/monitoring/status?symbol=BTCUSD

# ETHUSD monitoring
curl http://localhost:5556/api/monitoring/status?symbol=ETHUSD

# All monitoring routes support symbol param:
/api/monitoring/status
/api/monitoring/price-health
/api/monitoring/pre-order-stats
/api/monitoring/tp-verification
/api/monitoring/anomalies
/api/monitoring/predictive-map
/api/monitoring/advanced-predictions
/api/monitoring/trading-condition
```

### Frontend Integration Guide

**1. Import Symbol Context**
```javascript
import { useSymbol } from '../context/SymbolContext';

function MyComponent() {
  const { selectedSymbol, symbols, changeSymbol } = useSymbol();
  
  // selectedSymbol: "BTCUSD" or "ETHUSD"
  // symbols: Array of all symbols
  // changeSymbol(name): Switch symbol
}
```

**2. Use Symbol API Hook**
```javascript
import { useSymbolAPI } from '../hooks/useSymbolAPI';

function MyComponent() {
  const api = useSymbolAPI();
  
  // Automatic symbol parameter injection
  const data = await api.fetchJSON('/api/monitoring/status');
  // Becomes: /api/monitoring/status?symbol=BTCUSD
}
```

**3. Manual Symbol Parameter**
```javascript
import { useSymbol } from '../context/SymbolContext';

function MyComponent() {
  const { withSymbol } = useSymbol();
  
  const url = withSymbol('/api/orders');
  // url = "/api/orders?symbol=BTCUSD"
}
```

### Database Schema

**Symbol-Specific Databases:**
```
data/bot_events_BTCUSD_LONG.db
data/bot_events_ETHUSD_LONG.db
```

**Tables (per symbol):**
```sql
-- Positions table
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    entry_price REAL,
    quantity INTEGER,
    side TEXT,
    ...
);

-- Orders table
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    price REAL,
    quantity INTEGER,
    ...
);

-- Events table
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    event_type TEXT,
    symbol TEXT,
    data TEXT  -- JSON
);
```

### CLI Reference

**Start Bot for Specific Symbol:**
```bash
python3 bot/strategy/async_gridbot.py <SYMBOL>

# Examples:
python3 bot/strategy/async_gridbot.py BTCUSD
python3 bot/strategy/async_gridbot.py ETHUSD

# Error if symbol not configured:
python3 bot/strategy/async_gridbot.py INVALID
# ❌ Error: Symbol 'INVALID' not found in config.yaml
```

**PM2 Multi-Instance:**
```bash
# Start all symbols
pm2 start ecosystem.multi-symbol.config.js

# Start specific symbol
pm2 start ecosystem.multi-symbol.config.js --only gridbot-btc-live
pm2 start ecosystem.multi-symbol.config.js --only gridbot-eth-live

# Restart specific symbol
pm2 restart gridbot-btc-live

# Stop specific symbol
pm2 stop gridbot-eth-live

# Logs for specific symbol
pm2 logs gridbot-btc-live
```

### Troubleshooting Guide

**Problem:** Symbol dropdown not appearing in WebUI
```bash
# Check symbols API
curl http://localhost:5556/api/symbols

# If error, check backend logs
pm2 logs webui-backend-dev

# Verify SymbolProvider loaded
# Check browser console for errors
```

**Problem:** Bot fails to start with symbol argument
```bash
# Check config version
python3 -c "from config.loader import get_config; print(get_config().version)"

# Expected: "5.0"
# If "4.0", run migration:
python3 scripts/migrate_config_to_multi_symbol.py
```

**Problem:** Data not updating for selected symbol
```bash
# Check monitoring snapshot exists
ls -lh data/monitoring_snapshot_*.json

# Check bot is running
pm2 status | grep gridbot

# Check API returns symbol parameter
curl http://localhost:5556/api/monitoring/status?symbol=BTCUSD -v
# Should see "symbol": "BTCUSD" in response
```

**Problem:** Wrong data displayed after switching symbols
```bash
# Clear browser cache
# localStorage.clear() in browser console

# Verify symbol context
# console.log(localStorage.getItem('selectedSymbol'))

# Refresh page
```

---

## README Updates

### Updated README.md

```markdown
# GridBot - Multi-Symbol Trading Bot v5.0

## Features

- ✅ Multi-symbol support (BTCUSD, ETHUSD, and more)
- ✅ Independent grid strategies per symbol
- ✅ WebUI with symbol selector
- ✅ Symbol-specific risk monitoring
- ✅ Isolated state per symbol
- ✅ PM2 multi-instance management
- ✅ Backward compatible with v4.0

## Quick Start

### 1. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
cd webui/backend && pip install -r requirements.txt
cd webui/frontend && npm install
\`\`\`

### 2. Configure Symbols
Edit \`config.yaml\`:
\`\`\`yaml
symbols:
  BTCUSD:
    enabled: true
    product_id: 139
    grid: { lower: 85000, upper: 95000, step: 500 }
  
  ETHUSD:
    enabled: true  # Enable when ready
    product_id: 3136
    grid: { lower: 3000, upper: 4000, step: 50 }
\`\`\`

### 3. Start Trading
\`\`\`bash
# Start all services
pm2 start ecosystem.multi-symbol.config.js

# Or start individual symbol
python3 bot/strategy/async_gridbot.py BTCUSD
\`\`\`

### 4. Access WebUI
\`\`\`bash
open http://localhost:5556
# Use symbol dropdown to switch between symbols
\`\`\`

## Configuration

### Symbol Configuration
Each symbol has independent:
- Grid parameters (lower, upper, step, reference)
- Position limits (max_open_positions, lot_size)
- Safety limits (max_loss, liquidation distance)

### Capital Allocation
\`\`\`yaml
capital_allocation:
  total_capital_inr: 1000000
  btc_allocation_pct: 70
  eth_allocation_pct: 30
\`\`\`

## Architecture

\`\`\`
v5.0 Multi-Symbol Architecture
├── Config: Symbol-specific grids
├── Bot: python async_gridbot.py <SYMBOL>
├── WebUI: Symbol dropdown selector
├── Guardian: Multi-symbol monitoring
└── State: Symbol-specific databases
\`\`\`

## Migration from v4.0

\`\`\`bash
# Backup current config
cp config.yaml config.yaml.backup

# Run migration script
python3 scripts/migrate_config_to_multi_symbol.py

# Restart services
pm2 restart all
\`\`\`

## Monitoring

\`\`\`bash
# Check all symbols
pm2 status

# Monitor logs
pm2 logs

# Check databases
ls -lh data/bot_events_*.db

# API health
curl http://localhost:5556/api/symbols
\`\`\`

## Support

- Documentation: See docs/ folder
- Issues: GitHub Issues
- Contact: [Your contact]
\`\`\`

---

## CHANGELOG.md

```markdown
# Changelog

## [5.0.0] - 2025-12-30

### Added
- 🎯 Multi-symbol support (BTCUSD, ETHUSD, extensible)
- 🎨 Symbol selector dropdown in WebUI
- 📊 Symbol-specific databases and state files
- 🔒 Isolated risk calculations per symbol
- 🚀 PM2 multi-instance configuration
- 📡 Symbol-aware API endpoints
- 🧪 Comprehensive integration test suite

### Changed
- Config format: v4.0 → v5.0 (multi-symbol schema)
- CLI: Now requires symbol argument
- Bot initialization: Symbol-specific loading
- WebUI: Symbol context and hooks
- Guardian: Multi-symbol monitoring (planned)

### Fixed
- Database path isolation
- Config validation for multi-symbol
- Monitoring snapshot per symbol
- API backward compatibility

### Backward Compatibility
- v4.0 configs still supported (single symbol)
- No breaking changes for existing single-symbol setups
- Gradual migration path provided

## [4.0.0] - 2025-11-20
- Previous version (single symbol)
\`\`\`

---

**Status:** Documentation complete ✅

All phases documented and ready for implementation/testing.
