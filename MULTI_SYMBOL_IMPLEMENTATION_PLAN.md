# 🎯 Multi-Symbol Trading Bot Implementation Plan

**Project:** Adding ETH Support to GridBot (Multi-Symbol Architecture)  
**Version:** 5.0.0 (Proposed)  
**Date:** December 30, 2025  
**Status:** Planning Phase  
**Development Branch:** `BTEH` ✅ **Created**  
**Production Branch:** `production-4.0-clean` (Protected - Live Trading BTC)  
**Backup Production Branch:** `BTC` ✅ **Created**  
**Current Production:** BTCUSD only on port 5555 (Locked)

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Branch Strategy](#branch-strategy)
3. [WebUI Dual-Port Strategy](#webui-dual-port-strategy)
4. [Implementation Phases](#implementation-phases)
5. [Detailed Phase Breakdown](#detailed-phase-breakdown)
6. [Testing & Validation](#testing--validation)
7. [Production Deployment](#production-deployment)
8. [Rollback Plan](#rollback-plan)

---

## 📊 Executive Summary

### Current State (Production v4.0)
```
Production System (Port 5555)
├── AsyncGridBot (BTCUSD only)
│   ├── product_id: 27
│   ├── grid: 85000-95000, step 500
│   └── EventStore: bot_events_LONG.db
├── Guardian Bot (single symbol)
├── WebUI Backend (port 5555, LaunchAgent)
└── PM2: gridbot-live, guardian-live
```

### Target State (v5.0 - Multi-Symbol)
```
Multi-Symbol System
├── Development WebUI (Port 5556) ← Test here first
├── BTC Bot Instance
│   ├── Symbol: BTCUSD, product_id: 27
│   ├── EventStore: bot_events_BTCUSD_LONG.db
│   └── State: data/runtime_state_BTCUSD_LONG.json
├── ETH Bot Instance
│   ├── Symbol: ETHUSD, product_id: 139
│   ├── EventStore: bot_events_ETHUSD_LONG.db
│   └── State: data/runtime_state_ETHUSD_LONG.json
├── Guardian (multi-symbol aware)
└── Production WebUI (Port 5555) ← Migrate when stable
```

### Key Changes Required

| Component | Current | New |
|-----------|---------|-----|
| **Config** | Single symbol in `bot.symbol` | Multi-symbol in `symbols{}` section |
| **Bot Launch** | No CLI args | `python async_gridbot.py <SYMBOL>` |
| **State Files** | `runtime_state_LONG.json` | `runtime_state_BTCUSD_LONG.json` |
| **Databases** | `bot_events_LONG.db` | `bot_events_BTCUSD_LONG.db` |
| **PM2 Processes** | `gridbot-live` | `gridbot-btc-live`, `gridbot-eth-live` |
| **WebUI** | Single symbol view | Tabbed multi-symbol dashboard |
| **Guardian** | Single symbol monitor | Multi-symbol collector |

---

## 🔀 Branch Strategy

### Branch Protection & Workflow

```bash
# Production Branch (LOCKED - DO NOT TOUCH)
production-4.0-clean (PROTECTED) ✅ Active
├── Live trading BTCUSD
├── WebUI on port 5555 (LaunchAgent - LOCKED)
├── Current database: data/
├── Stable, battle-tested
└── Emergency fixes only

# Backup Production Branch
BTC (PROTECTED) ✅ Created
├── Exact copy of production-4.0-clean
├── Safety backup
└── Can be used if production-4.0-clean has issues

# Development Branch (All multi-symbol work here)
BTEH (DEVELOPMENT) ✅ Created - Currently Active
├── Branched from: BTC (which is from production-4.0-clean)
├── WebUI on port 5556 (testing)
├── Database: data_bteh/ (separate)
├── Multi-symbol implementation
└── Can break things safely - production unaffected
```

### Branch Structure (Already Created)

```bash
# Current branch setup - already done! ✅
cd /Users/ssr/Projects/WorkingBot

# View all branches
git branch -a
# Output:
#   production-4.0-clean  (LOCKED production)
#   BTC                   (backup production)
# * BTEH                  (active development branch)

# You're currently on Bis LOCKED on `production-4.0-clean`
- Mac Mini runs production bot (port 5555)
- Live trading BTCUSD continues uninterrupted
- **NEVER** switch away from this branch during trading hours
- Database: `data/` directory
- LaunchAgent: LOCKED to this branch

**Rule 2:** All development on `BTEH` branch (current)
- WebUI runs on port 5556 for testing
- Separate database: `data_bteh/` directory
- Can test with demo mode or paper trading
- Breaking changes OK - production unaffected
- Can experiment freely without risk

**Rule 3:** Use `BTC` as backup/staging
- Exact copy of production for testing production-like scenarios
- Use if production-4.0-clean needs emergency restore
- Test production deployments here first

**Rule 4:** Sync production fixes to development branch
```bash
# If production-4.0-clean gets emergency fix, pull it to BTEH
git checkout BTEH
git merge production-4.0-clean

# Or from BTC backup
git checkout BTEH
git merge BTC
**Rule 3:** Sync production fixes to feature branch
```bash
# If production gets emergency fix, pull it to feature branch
git checkout feature/multi-symbol-v5.0
git merge production-v4.0
```

---(LOCKED) | production-4.0-clean | Yes (running) | **DO NOT TOUCH** |
| **5556** | Development | BTEH | No (manual start) | To be configured
## 🌐 WebUI Dual-Port Strategy

### Why Two Ports?

**Problem:** Can't upgrade production WebUI while testing multi-symbol  
**Solution:** Run development WebUI on port 5556 simultaneously

### Port Assignment

| Port | Purpose | Branch | LaunchAgent | Status |
|------|---------|--------|-------------|--------|
| **5555** | Production | production-v4.0 | Yes (running) | Keep untouched |
| **5556** | Development | feature/multi-symbol-v5.0 | No (manual) | Create new |

### Development WebUI Setup

**Manual Start for BTEH Development WebUI (Port 5556):**

```bash
# Switch to BTEH branch
git checkout BTEH

# Start development WebUI manually (DO NOT use LaunchAgent)
cd /Users/ssr/Projects/WorkingBot
export PYTHONPATH=/Users/ssr/Projects/WorkingBot
export FLASK_PORT=5556
python3 webui/backend/app.py 5556

# Access development WebUI
open http://localhost:5556

# Note: Production WebUI on port 5555 keeps running via LaunchAgent
# This allows you to compare both UIs side-by-side
```

**Why Manual Start?**
- Production LaunchAgent is LOCKED to production-4.0-clean branch
- Manual start ensures BTEH WebUI doesn't interfere with production
- Gives you full control over dev environment
- Can easily stop/restart without affecting production

### Testing Both WebUIs

```bash
# Production WebUI (unchanged)
curl http://localhost:5555/api/health
# {"status": "ok", "symbol": "BTCUSD", "version": "4.0"}

# Development WebUI (multi-symbol)
curl http://localhost:5556/api/health
# {"status": "ok", "symbols": ["BTCUSD", "ETHUSD"], "version": "5.0-dev"}
```

---

## 🚀 Implementation Phases

### Phase Breakdown (3 Major Parts)

```
PART 1: FOUNDATION (Week 1)
├── Phase 1A: Configuration Architecture (2 days)
├── Phase 1B: Core Bot Changes (3 days)
└── Phase 1C: State & Database Isolation (2 days)

PART 2: INTEGRATION (We Simultaneously

```bash
# Production WebUI (LOCKED on port 5555 - production-4.0-clean branch)
curl http://localhost:5555/api/health
# {"status": "ok", "symbol": "BTCUSD", "version": "4.0"}

# Development WebUI (BTEH branch on port 5556)
curl http://localhost:5556/api/health
# {"status": "ok", "symbols": ["BTCUSD", "ETHUSD"], "version": "5.0-dev"}

# You can view both in browser:
# Production: http://localhost:5555  (current trading system)
# Development: http://localhost:5556 (multi-symbol testing)

---

## 📝 Detailed Phase Breakdown

## PART 1: FOUNDATION (Week 1)

### 🚨 Pre-Implementation Checklist (MUST DO FIRST)

**Complete these before starting Phase 1A:**

```bash
# 1. Verify you're on BTEH branch
cd /Users/ssr/Projects/WorkingBot
git branch --show-current  # Should show: BTEH

# 2. Verify ETH product ID from Delta Exchange
python3 scripts/verify_eth_product_id.py

# 3. Create PM2 ecosystem config
# (Script will be created in this phase)

# 4. Document capital allocation strategy
# (Will be added to config.yaml)
```

**Checklist:**
- [ ] On BTEH development branch
- [ ] ETH product_id verified (not assumed)
- [ ] Capital allocation documented
- [ ] Delta Exchange rate limits checked
- [ ] Production WebUI on port 5555 confirmed running
- [ ] Development environment isolated (port 5556, data_bteh/)

---

### Phase 1A: Configuration Architecture (2-3 days)

**Objective:** Transform config.yaml to support multiple symbols

**Current config.yaml structure:**
```yaml
version: '2.0'
trading_mode: live
bot:
  symbol: BTCUSD
  mode: LONG
grid:
  geometry:
    lower: 85000
    upper: 95000
    step: 500
```

**New multi-symbol config.yaml:**
```yaml
version: '5.0'
trading_mode: live

# Capital allocation across symbols
capital_allocation:
  total_capital_usd: 10000  # Adjust based on actual capital
  allocations:
    BTCUSD:
      capital_usd: 7000
      percentage: 70
      max_position_value_usd: 5000  # Don't use all allocated capital
    ETHUSD:
      capital_usd: 3000
      percentage: 30
      max_position_value_usd: 2000

# Multi-symbol configuration
symbols:
  BTCUSD:
    enabled: true
    product_id: 27
    mode: LONG
    grid:
      geometry:
        lower: 85000
        upper: 95000
        step: 500
        reference: 88500
      limits:
        max_open_positions: 50
        lot_size: 5
        max_open_orders: 20
        max_qty_per_order: 2
      behavior:
        strict_grid: true
        tick_size: 0.5
    safety:
      max_account_loss_inr: 10000
      min_liquidation_distance_pct: 10.0
      
  ETHUSD:
    enabled: false  # Start disabled, enable after testing
    product_id: 139  # ⚠️ VERIFY THIS - run scripts/verify_eth_product_id.py
    mode: LONG
    capital:
      allocated_usd: 3000
      max_position_value_usd: 2000
    grid:
      geometry:
        lower: 3200
        upper: 3800
        step: 50
        reference: 3500
      limits:
        max_open_positions: 30
        lot_size: 10
        max_open_orders: 15
        max_qty_per_order: 3
      behavior:
        strict_grid: true
        tick_size: 0.05
    safety:
      max_account_loss_inr: 5000
      min_liquidation_distance_pct: 10.0

# Shared settings (apply to all symbols)
capital_protection:
  equity_floor:
    floor_inr: 70000
    enabled: true
    
guardian:
  enabled: true
  check_interval: 5
  
order_execution:
  max_retries: 3
  retry_delay: 2.0
  
# ... rest of shared config
```

**Files to modify:**
1. `config.yaml` - Add symbols section
2. `config/models.py` - Add SymbolConfig model
3. `config/loader.py` - Update get_config() for symbols
4. `config/validator.py` - Validate symbols section

**Implementation Steps:**

**Step 1: Backup current config**
```bash
cd /Users/ssr/Projects/WorkingBot
cp config.yaml config.yaml.backup.v4.0
git add config.yaml.backup.v4.0
git commit -m "backup: Save v4.0 config before multi-symbol"
```

**Step 2: Update config/models.py**

Add new models:
```python
# config/models.py

class SymbolGridGeometry(BaseModel):
    """Symbol-specific grid geometry"""
    lower: int = Field(gt=0, description="Grid lower boundary")
    upper: int = Field(gt=0, description="Grid upper boundary")
    step: int = Field(gt=0, le=10000, description="Grid step size")
    reference: int = Field(gt=0, description="Reference price")
Verify you're on BTEH branch and backup config**
```bash
# Ensure you're on BTEH branch
cd /Users/ssr/Projects/WorkingBot
git branch --show-current
# Should show: BTEH

# If not on BTEH, switch to it
git checkout BTEH

# Backup current config
cp config.yaml config.yaml.backup.v4.0
git add config.yaml.backup.v4.0
git commit -m "backup: Save v4.0 config before multi-symbol (BTEH branch)"
git push origin BTEH
    max_qty_per_order: int = Field(gt=0)

class SymbolGridBehavior(BaseModel):
    """Symbol-specific grid behavior"""
    strict_grid: bool = Field(True)
    tick_size: float = Field(gt=0)
    rung_snap_mode: str = Field("below")

class SymbolGridConfig(BaseModel):
    """Symbol-specific grid configuration"""
    geometry: SymbolGridGeometry
    limits: SymbolGridLimits
    behavior: SymbolGridBehavior

class SymbolSafety(BaseModel):
    """Symbol-specific safety limits"""
    max_account_loss_inr: float = Field(gt=0)
    min_liquidation_distance_pct: float = Field(gt=0)

class SymbolConfig(BaseModel):
    """Complete configuration for a single trading symbol"""
    enabled: bool = Field(True, description="Enable/disable this symbol")
    product_id: int = Field(gt=0, description="Delta Exchange product ID")
    mode: GridMode = Field(description="LONG or SHORT")
    grid: SymbolGridConfig
    safety: SymbolSafety

class RootConfig(BaseModel):
    """Complete bot configuration with multi-symbol support"""
    version: str = Field("5.0")
    trading_mode: TradingMode
    
    # Multi-symbol configuration
    symbols: Dict[str, SymbolConfig] = Field(
        default_factory=dict,
        description="Symbol configurations keyed by symbol name"
    )
    
    # Shared components (same as before)
    capital_protection: CapitalProtection
    guardian: GuardianConfig
    safety: SafetyConfig  # Global safety, symbols have their own too
    # ... rest
```

**Step 3: Create config migration script**

```python
# scripts/migrate_config_to_multi_symbol.py

import yaml
from pathlib import Path

def migrate_config():
    """Migrate v4.0 single-symbol config to v5.0 multi-symbol"""
    
    config_file = Path("config.yaml")
    backup_file = Path("config.yaml.backup.v4.0")
    
    # Load current config
    with open(config_file) as f:
        old_config = yaml.safe_load(f)
    
    # Extract symbol info
    symbol = old_config['bot']['symbol']  # 'BTCUSD'
    product_id = old_config['api']['live']['product_id']  # 27
    mode = old_config['bot']['mode']  # 'LONG'
    
    # Create new multi-symbol structure
    new_config = {
        'version': '5.0',
        'trading_mode': old_config['trading_mode'],
        
        'symbols': {
            symbol: {
                'enabled': True,
                'product_id': product_id,
                'mode': mode,
                'grid': old_config['grid'],
                'safety': {
                    'max_account_loss_inr': old_config['guardian']['max_account_loss_inr'],
                    'min_liquidation_distance_pct': old_config['safety']['min_liquidation_distance_pct']
                }
            }
        }
    }
    
    # Copy all shared sections
    shared_sections = [
        'capital_protection', 'guardian', 'safety', 'startup',
        'shutdown', 'order_execution', 'heartbeat', 'api',
        'telegram', 'logging', 'webui'
    ]
    
    for section in shared_sections:
        if section in old_config:
            new_config[section] = old_config[section]
    
    # Write new config
    with open(config_file, 'w') as f:
        yaml.dump(new_config, f, default_flow_style=False, indent=2)
    
    print("✅ Config migrated to v5.0 multi-symbol format")
    print(f"   Backup saved to: {backup_file}")
    print(f"   Symbol: {symbol} (product_id={product_id})")

if __name__ == "__main__":
    migrate_config()
```

**Step 4: Add ETH symbol to config**

Manually add ETH after migration:
```yaml
symbols:
  BTCUSD:
    # ... existing from migration
    
  ETHUSD:
    enabled: false  # Disabled initially
    product_id: 139
    mode: LONG
    grid:
      geometry:
        lower: 3200
        upper: 3800
        step: 50
        reference: 3500
      limits:
        max_open_positions: 30
        lot_size: 10
        max_open_orders: 15
        max_qty_per_order: 3
      behavior:
        strict_grid: true
        tick_size: 0.05
    safety:
      max_account_loss_inr: 5000
      min_liquidation_distance_pct: 10.0
```

**Deliverables:**
- ✅ `config.yaml` with `symbols{}` section
- ✅ `config/models.py` with `SymbolConfig` class
- ✅ Migration script tested
- ✅ Validation: `python -c "from config.loader import get_config; cfg = get_config(); print(cfg.symbols.keys())"`

---

### Phase 1B: Core Bot Changes (3 days)

**Objective:** Modify AsyncGridBot to accept symbol as CLI argument

**File:** `bot/strategy/async_gridbot.py` (4,281 lines)

**Key Changes:**

**Change 1: Constructor - Accept symbol_name parameter**

Current (Line ~144):
```python
def __init__(self, api_key, api_secret, config, mode='LONG', testnet=False, ...):
    self.config = config
    self.symbol = config.bot.symbol  # Hardcoded from config
    self.product_id = 27  # Hardcoded
    self.mode = mode
```

New:
```python
def __init__(self, api_key, api_secret, config, symbol_name, testnet=False, ...):
    """
    Initialize GridBot for specific symbol
    
    Args:
        symbol_name: Symbol key from config.symbols (e.g., 'BTCUSD', 'ETHUSD')
    """
    self.config = config
    
    # Validate symbol exists
    if symbol_name not in config.symbols:
        raise ValueError(
            f"Symbol '{symbol_name}' not found in config.yaml\n"
            f"Available symbols: {list(config.symbols.keys())}"
        )
    
    symbol_config = config.symbols[symbol_name]
    
    # Check if symbol is enabled
    if not symbol_config.enabled:
        raise ValueError(f"Symbol '{symbol_name}' is disabled in config.yaml")
    
    # Set symbol-specific attributes
    self.symbol_name = symbol_name
    self.symbol = symbol_name  # For backwards compatibility
    self.product_id = symbol_config.product_id
    self.mode = symbol_config.mode
    
    # Load symbol-specific grid parameters
    self.lower_price = symbol_config.grid.geometry.lower
    self.upper_price = symbol_config.grid.geometry.upper
    self.grid_step = symbol_config.grid.geometry.step
    self.ref_price = symbol_config.grid.geometry.reference
    self.max_positions = symbol_config.grid.limits.max_open_positions
    self.lot_size = symbol_config.grid.limits.lot_size
    self.max_qty_per_order = symbol_config.grid.limits.max_qty_per_order
    self.tick_size = symbol_config.grid.behavior.tick_size
    
    # Symbol-specific safety limits
    self.max_account_loss_inr = symbol_config.safety.max_account_loss_inr
    self.min_liq_distance_pct = symbol_config.safety.min_liquidation_distance_pct
    
    # Symbol-specific database
    db_name = f"data/bot_events_{symbol_name}_{self.mode}.db"
    self.event_store = EventStore(db_name)
    
    # Symbol-specific state file
    self.state_file = Path(f"data/runtime_state_{symbol_name}_{self.mode}.json")
    
    log.info(f"🎯 Initialized bot for {symbol_name}")
    log.info(f"   Product ID: {self.product_id}")
    log.info(f"   Mode: {self.mode}")
    log.info(f"   Grid: {self.lower_price}-{self.upper_price}, step {self.grid_step}")
    log.info(f"   Database: {db_name}")
```

**Change 2: Update all file paths to be symbol-specific**

Find all references to state files and update:

```python
# OLD (Line ~961):
state_file = Path(f"data/runtime_state_{self.mode}.json")

# NEW:
state_file = Path(f"data/runtime_state_{self.symbol_name}_{self.mode}.json")

# OLD (Line ~1234):
db_file = f"data/bot_events_{self.mode}.db"

# NEW:
db_file = f"data/bot_events_{self.symbol_name}_{self.mode}.db"
```

**Change 3: Update main() function**

Current (Line ~4930):
```python
async def main():
    config = get_config()
    credentials = get_api_credentials(config.trading_mode)
    
    bot = AsyncGridBot(
        api_key=credentials['api_key'],
        api_secret=credentials['api_secret'],
        mode=config.bot.mode,
        testnet=(config.trading_mode == 'demo')
    )
    
    await bot.start()
```

New:
```python
async def main():
    import sys
    
    # Get symbol from command line
    if len(sys.argv) < 2:
        print("❌ Error: Missing symbol argument")
        print("")
        print("Usage: python bot/strategy/async_gridbot.py <SYMBOL>")
        print("")
        print("Examples:")
        print("  python bot/strategy/async_gridbot.py BTCUSD")
        print("  python bot/strategy/async_gridbot.py ETHUSD")
        print("")
        
        # Show available symbols from config
        try:
            config = get_config()
            enabled_symbols = [s for s, cfg in config.symbols.items() if cfg.enabled]
            if enabled_symbols:
                print(f"Available enabled symbols: {', '.join(enabled_symbols)}")
            else:
                print("No enabled symbols found in config.yaml")
        except Exception as e:
            print(f"Error loading config: {e}")
        
        sys.exit(1)
    
    symbol_name = sys.argv[1].upper()
    
    # Load config
    config = get_config()
    
    # Validate symbol
    if symbol_name not in config.symbols:
        print(f"❌ Error: Symbol '{symbol_name}' not found in config.yaml")
        print(f"   Available symbols: {list(config.symbols.keys())}")
        sys.exit(1)
    
    if not config.symbols[symbol_name].enabled:
        print(f"❌ Error: Symbol '{symbol_name}' is disabled in config.yaml")
        print(f"   Set symbols.{symbol_name}.enabled=true to enable it")
        sys.exit(1)
    
    # Get credentials
    credentials = get_api_credentials(config.trading_mode)
    
    # Display startup banner
    print("=" * 80)
    print(f"🚀 Starting AsyncGridBot for {symbol_name}")
    print(f"   Mode: {config.symbols[symbol_name].mode}")
    print(f"   Trading Mode: {config.trading_mode}")
    print(f"   Product ID: {config.symbols[symbol_name].product_id}")
    print("=" * 80)
    
    # Create bot instance
    bot = AsyncGridBot(
        api_key=credentials['api_key'],
        api_secret=credentials['api_secret'],
        config=config,
        symbol_name=symbol_name,
        testnet=(config.trading_mode == 'demo')
    )
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

**Testing Phase 1B:**

```bash
# Test BTC (should work with existing config)
python3 bot/strategy/async_gridbot.py BTCUSD

# Test ETH (should fail if disabled)
python3 bot/strategy/async_gridbot.py ETHUSD
# Expected: "Symbol 'ETHUSD' is disabled"

# Test invalid symbol
python3 bot/strategy/async_gridbot.py INVALID
# Expected: "Symbol 'INVALID' not found"

# Test missing argument
python3 bot/strategy/async_gridbot.py
# Expected: Usage help
```

**Step 4: Create PM2 Ecosystem Config**

Create multi-symbol PM2 configuration:

```javascript
// ecosystem.multi-symbol.config.js

module.exports = {
  apps: [
    // BTC Bot
    {
      name: 'gridbot-btc-live',
      script: 'bot/strategy/async_gridbot.py',
      args: 'BTCUSD',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-btc-error.log',
      out_file: 'logs/gridbot-btc-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000
    },
    
    // ETH Bot (disabled initially)
    {
      name: 'gridbot-eth-live',
      script: 'bot/strategy/async_gridbot.py',
      args: 'ETHUSD',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: false,  // Don't auto-start until tested
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/gridbot-eth-error.log',
      out_file: 'logs/gridbot-eth-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      kill_timeout: 15000
    },
    
    // Guardian (multi-symbol aware)
    {
      name: 'guardian-live',
      script: 'bot/guardian/core/guardian_bot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        TRADING_MODE: 'live'
      },
      error_file: 'logs/guardian-error.log',
      out_file: 'logs/guardian-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss'
    },
    
    // WebUI Backend (port 5556 for development)
    {
      name: 'webui-backend-dev',
      script: 'webui/backend/app.py',
      args: '5556',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
        FLASK_PORT: '5556'
      },
      error_file: 'logs/webui-dev-error.log',
      out_file: 'logs/webui-dev-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss'
    }
  ]
};
```

**Test PM2 Config:**
```bash
# Validate config
pm2 start ecosystem.multi-symbol.config.js --dry-run

# Start in demo mode first
pm2 start ecosystem.multi-symbol.config.js
pm2 list

# Expected:
# gridbot-btc-live   online
# gridbot-eth-live   stopped (autorestart: false)
# guardian-live      online
# webui-backend-dev  online
```

**Deliverables:**
- ✅ AsyncGridBot accepts `symbol_name` parameter
- ✅ Symbol-specific state files
- ✅ Symbol-specific databases
- ✅ CLI argument validation
- ✅ Proper error messages
- ✅ PM2 ecosystem config created
- ✅ PM2 config tested (dry-run)

---

### Phase 1C: State & Database Isolation (2 days)

**Objective:** Ensure complete state isolation between symbols

**Files to Check:**

1. **EventStore** (`bot/strategy/actors/event_store.py`)
2. **PositionActor** (`bot/strategy/actors/position_actor.py`)
3. **OrderActor** (`bot/strategy/actors/order_actor.py`)
4. **State persistence** (all JSON file writes)

**Changes:**

**File: bot/strategy/actors/event_store.py**

Current:
```python
class EventStore:
    def __init__(self, db_name='data/bot_events.db'):
        self.db_name = db_name
```

Updated (already parameterized, verify symbol is passed):
```python
# In async_gridbot.py __init__:
db_name = f"data/bot_events_{symbol_name}_{self.mode}.db"
self.event_store = EventStore(db_name)
```

**File: bot/strategy/actors/position_actor.py**

Check for hardcoded paths, make symbol-specific:
```python
# OLD:
positions_file = "data/positions.json"

# NEW (pass from bot):
positions_file = f"data/positions_{self.symbol_name}.json"
```

**State File Inventory:**

Create checklist of all state files:
```bash
# Current state files (single symbol):
data/runtime_state_LONG.json
data/bot_events_LONG.db
data/positions.json
data/pending_orders.json
.volatility_status.json

# New state files (per symbol):
data/runtime_state_BTCUSD_LONG.json
data/runtime_state_ETHUSD_LONG.json
data/bot_events_BTCUSD_LONG.db
data/bot_events_ETHUSD_LONG.db
data/positions_BTCUSD.json
data/positions_ETHUSD.json
data/pending_orders_BTCUSD.json
data/pending_orders_ETHUSD.json
.volatility_status_BTCUSD.json
.volatility_status_ETHUSD.json
```

**Create State File Cleanup Script:**

```bash
# scripts/cleanup_old_state_files.sh

#!/bin/bash
# Backup old single-symbol state files before multi-symbol migration

BACKUP_DIR="data/backup_v4.0_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Backing up v4.0 state files to $BACKUP_DIR"

# Move old files
mv data/runtime_state_LONG.json "$BACKUP_DIR/" 2>/dev/null
mv data/bot_events_LONG.db "$BACKUP_DIR/" 2>/dev/null
mv data/positions.json "$BACKUP_DIR/" 2>/dev/null
mv data/pending_orders.json "$BACKUP_DIR/" 2>/dev/null
mv .volatility_status.json "$BACKUP_DIR/" 2>/dev/null

echo "✅ Backup complete"
echo "   Old files in: $BACKUP_DIR"
echo "   New symbol-specific files will be created on first run"
```

**Deliverables:**
- ✅ All state files are symbol-specific
- ✅ No cross-symbol contamination
- ✅ Cleanup script for old files
- ✅ Documentation of state file naming

---

## PART 2: INTEGRATION (Week 2)

### Phase 2A: Multi-Symbol WebUI Backend (3 days)

**Objective:** Create API endpoints for multi-symbol control

**File:** `webui/backend/routes/bot_control.py`

**New Endpoints:**

```python
# webui/backend/routes/multi_symbol.py

from flask import Blueprint, jsonify, request
from pathlib import Path
import json
import subprocess

bp = Blueprint('multi_symbol', __name__)

@bp.route('/api/symbols', methods=['GET'])
def get_symbols():
    """Get all configured symbols and their status"""
    from config.loader import get_config
    
    config = get_config()
    symbols_info = {}
    
    for symbol_name, symbol_config in config.symbols.items():
        # Check if bot is running
        pm2_name = f"gridbot-{symbol_name.lower()}-live"
        pm2_status = subprocess.run(
            ['pm2', 'describe', pm2_name],
            capture_output=True,
            text=True
        )
        is_running = pm2_status.returncode == 0
        
        # Read state file
        state_file = Path(f"data/runtime_state_{symbol_name}_LONG.json")
        state_data = {}
        if state_file.exists():
            with open(state_file) as f:
                state_data = json.load(f)
        
        symbols_info[symbol_name] = {
            'enabled': symbol_config.enabled,
            'product_id': symbol_config.product_id,
            'mode': symbol_config.mode,
            'is_running': is_running,
            'pm2_process': pm2_name,
            'state': state_data,
            'grid': {
                'lower': symbol_config.grid.geometry.lower,
                'upper': symbol_config.grid.geometry.upper,
                'step': symbol_config.grid.geometry.step
            }
        }
    
    return jsonify({
        'success': True,
        'symbols': symbols_info,
        'total_symbols': len(symbols_info),
        'enabled_count': sum(1 for s in symbols_info.values() if s['enabled']),
        'running_count': sum(1 for s in symbols_info.values() if s['is_running'])
    })

@bp.route('/api/symbol/<symbol>/start', methods=['POST'])
def start_symbol_bot(symbol):
    """Start bot for specific symbol"""
    from config.loader import get_config
    
    symbol = symbol.upper()
    config = get_config()
    
    if symbol not in config.symbols:
        return jsonify({'success': False, 'error': f'Symbol {symbol} not found'}), 404
    
    if not config.symbols[symbol].enabled:
        return jsonify({'success': False, 'error': f'Symbol {symbol} is disabled'}), 400
    
    pm2_name = f"gridbot-{symbol.lower()}-live"
    result = subprocess.run(['pm2', 'start', pm2_name], capture_output=True)
    
    return jsonify({
        'success': result.returncode == 0,
        'symbol': symbol,
        'pm2_process': pm2_name,
        'message': f'Started {symbol} bot'
    })

@bp.route('/api/symbol/<symbol>/stop', methods=['POST'])
def stop_symbol_bot(symbol):
    """Stop bot for specific symbol"""
    symbol = symbol.upper()
    pm2_name = f"gridbot-{symbol.lower()}-live"
    
    result = subprocess.run(['pm2', 'stop', pm2_name], capture_output=True)
    
    return jsonify({
        'success': result.returncode == 0,
        'symbol': symbol,
        'pm2_process': pm2_name,
        'message': f'Stopped {symbol} bot'
    })

@bp.route('/api/symbol/<symbol>/positions', methods=['GET'])
def get_symbol_positions(symbol):
    """Get positions for specific symbol"""
    symbol = symbol.upper()
    
    positions_file = Path(f"data/positions_{symbol}.json")
    if not positions_file.exists():
        return jsonify({'success': True, 'positions': [], 'total': 0})
    
    with open(positions_file) as f:
        data = json.load(f)
    
    return jsonify({
        'success': True,
        'symbol': symbol,
        'positions': data.get('positions', []),
        'total': len(data.get('positions', []))
    })
```

**Register Blueprint:**

```python
# webui/backend/app.py

from webui.backend.routes import multi_symbol

app.register_blueprint(multi_symbol.bp)
```

**Update WebUI Config:**

```python
# webui/backend/app.py

def create_app(port=5555):
    app = Flask(__name__)
    
    # Get port from environment or parameter
    app_port = int(os.getenv('FLASK_PORT', port))
    
    # Register blueprints
    # ... existing blueprints
    from webui.backend.routes import multi_symbol
    app.register_blueprint(multi_symbol.bp)
    
    return app

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5555
    app = create_app(port)
    app.run(host='127.0.0.1', port=port)
```

**Deliverables:**
- ✅ `/api/symbols` endpoint
- ✅ `/api/symbol/<symbol>/start` endpoint
- ✅ `/api/symbol/<symbol>/stop` endpoint
- ✅ `/api/symbol/<symbol>/positions` endpoint
- ✅ Port configuration support

---

### Phase 2B: Frontend Tabbed Dashboard (2 days)

**Objective:** Multi-symbol UI with symbol selector

**File:** `webui/frontend/src/App.js`

**New Component: SymbolSelector**

```javascript
// webui/frontend/src/components/SymbolSelector.js

import React, { useState, useEffect } from 'react';
import { Tabs, Tab, Badge } from '@mui/material';

export function SymbolSelector({ onSymbolChange }) {
  const [symbols, setSymbols] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSD');

  useEffect(() => {
    // Fetch symbols from backend
    fetch('/api/symbols')
      .then(res => res.json())
      .then(data => {
        setSymbols(data.symbols);
        // Auto-select first enabled symbol
        const enabled = Object.keys(data.symbols).find(
          s => data.symbols[s].enabled
        );
        if (enabled) {
          setSelectedSymbol(enabled);
          onSymbolChange(enabled);
        }
      });
  }, []);

  const handleChange = (event, newSymbol) => {
    setSelectedSymbol(newSymbol);
    onSymbolChange(newSymbol);
  };

  return (
    <Tabs value={selectedSymbol} onChange={handleChange}>
      {Object.entries(symbols).map(([symbol, info]) => (
        <Tab
          key={symbol}
          label={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {symbol}
              {info.is_running && (
                <Badge color="success" variant="dot" />
              )}
              {!info.enabled && (
                <Badge color="error" badgeContent="OFF" />
              )}
            </div>
          }
          value={symbol}
          disabled={!info.enabled}
        />
      ))}
    </Tabs>
  );
}
```

**Update Main App:**

```javascript
// webui/frontend/src/App.js

import { SymbolSelector } from './components/SymbolSelector';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSD');
  const [symbolData, setSymbolData] = useState(null);

  const handleSymbolChange = (symbol) => {
    setSelectedSymbol(symbol);
    // Fetch symbol-specific data
    fetch(`/api/symbol/${symbol}/positions`)
      .then(res => res.json())
      .then(data => setSymbolData(data));
  };

  return (
    <div className="App">
      <header>
        <h1>GridBot Dashboard</h1>
        <SymbolSelector onSymbolChange={handleSymbolChange} />
      </header>
      
      <main>
        {symbolData && (
          <Dashboard 
            symbol={selectedSymbol}
            data={symbolData}
          />
        )}
      </main>
    </div>
  );
}
```

**Frontend Build Process:**

```bash
# After frontend changes, build production bundle
cd webui/frontend

# Install dependencies (if not already done)
npm install

# Test in development mode first
npm start
# Opens http://localhost:3000
# Test multi-symbol functionality

# Build production bundle
npm run build
# Creates optimized build/ directory

# Copy build to backend static folder
rm -rf ../backend/static/*
cp -r build/* ../backend/static/

# Return to project root
cd /Users/ssr/Projects/WorkingBot

# Restart development WebUI to serve new build
pm2 restart webui-backend-dev

# Test production build
open http://localhost:5556
```

**Deliverables:**
- ✅ Symbol selector tabs
- ✅ Running indicator per symbol
- ✅ Symbol-specific dashboard views
- ✅ Auto-reload on symbol switch
- ✅ Frontend tested in dev mode (npm start)
- ✅ Production build created (npm run build)
- ✅ Build deployed to backend static folder
- ✅ Production build tested on port 5556

---

### Phase 2C: Guardian Multi-Symbol Support (2 days)

**Objective:** Guardian monitors all enabled symbols

**File:** `bot/guardian/core/guardian_bot.py`

**Current:** Monitors single BTCUSD position

**New:** Monitor all enabled symbols

```python
# bot/guardian/core/guardian_bot.py

class GuardianBot:
    def __init__(self, config):
        self.config = config
        
        # Create collectors for each enabled symbol
        self.symbol_collectors = {}
        
        for symbol_name, symbol_config in config.symbols.items():
            if not symbol_config.enabled:
                log.info(f"⏭️  Skipping disabled symbol: {symbol_name}")
                continue
            
            log.info(f"📊 Setting up monitoring for {symbol_name}")
            self.symbol_collectors[symbol_name] = {
                'product_id': symbol_config.product_id,
                'mode': symbol_config.mode,
                'max_loss': symbol_config.safety.max_account_loss_inr,
                'min_liq_distance': symbol_config.safety.min_liquidation_distance_pct,
                'event_store': EventStore(
                    f"data/bot_events_{symbol_name}_{symbol_config.mode}.db"
                )
            }
        
        log.info(f"✅ Guardian monitoring {len(self.symbol_collectors)} symbols")
    
    async def check_all_symbols(self):
        """Check safety limits for all symbols in parallel"""
        # Create tasks for parallel execution
        tasks = [
            self._check_symbol_safety(symbol_name, collector)
            for symbol_name, collector in self.symbol_collectors.items()
        ]
        
        # Run all checks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        for symbol_name, result in zip(self.symbol_collectors.keys(), results):
            if isinstance(result, Exception):
                log.error(f"❌ Guardian check failed for {symbol_name}: {result}")
            else:
                signal, reason = result
                if signal == 'HALT':
                    log.warning(f"🚨 {reason}")
                else:
                    log.debug(f"✅ {reason}")
    
    async def _check_symbol_safety(self, symbol_name, collector):
        """Check safety for specific symbol"""
        # Get positions for this symbol
        positions = await self.api_client.get_positions(
            product_id=collector['product_id']
        )
        
        # Calculate PnL
        total_pnl_inr = sum(p['unrealized_pnl'] * self.usd_to_inr for p in positions)
        
        # Check loss limit
        if abs(total_pnl_inr) > collector['max_loss']:
            signal = 'HALT'
            reason = f"{symbol_name}: Loss {total_pnl_inr:.0f} INR exceeds limit {collector['max_loss']}"
            log.warning(f"🚨 {reason}")
        else:
            signal = 'OK'
            reason = f"{symbol_name}: Within limits"
        
        # Write signal to symbol-specific database
        collector['event_store'].write_guardian_signal(signal, reason)
        
        return signal, reason
    
    async def run(self):
        """Main monitoring loop"""
        while not self.shutdown_event.is_set():
            await self.check_all_symbols()
            await asyncio.sleep(self.config.guardian.check_interval)
```

**Deliverables:**
- ✅ Multi-symbol position monitoring
- ✅ Symbol-specific safety signals
- ✅ Per-symbol event logging
- ✅ Aggregate safety reporting

---

## PART 3: DEPLOYMENT (Week 3)

### Phase 3A: Testing & Validation (3 days)

**Day 1: Configuration Testing**

```bash
# Test config loading
python3 -c "
from config.loader import get_config
cfg = get_config()
print('Symbols:', list(cfg.symbols.keys()))
for s, c in cfg.symbols.items():
    print(f'  {s}: enabled={c.enabled}, product_id={c.product_id}')
"

# Expected output:
# Symbols: ['BTCUSD', 'ETHUSD']
#   BTCUSD: enabled=True, product_id=27
#   ETHUSD: enabled=False, product_id=139
```

**Day 2: Bot Instance Testing**

```bash
# Terminal 1: Start BTC bot (demo mode)
cd /Users/ssr/Projects/WorkingBot
export PYTHONPATH=/Users/ssr/Projects/WorkingBot
python3 bot/strategy/async_gridbot.py BTCUSD

# Terminal 2: Start development WebUI
python3 webui/backend/app.py 5556

# Terminal 3: Test API
curl http://localhost:5556/api/symbols | jq
```

**Day 3: Integration Testing**

```bash
# Start all components
pm2 start ecosystem.multi-symbol.config.js

# Monitor
pm2 monit

# Check databases
ls -la data/*.db
# Should show:
# bot_events_BTCUSD_LONG.db
# bot_events_ETHUSD_LONG.db (if enabled)
```

**Testing Checklist:**

**Basic Functionality:**
- [ ] Config loads successfully
- [ ] BTC bot starts with BTCUSD argument
- [ ] ETH bot fails if disabled (expected)
- [ ] ETH bot starts when enabled
- [ ] State files are symbol-specific
- [ ] Databases are symbol-specific
- [ ] WebUI shows both symbols
- [ ] Symbol tabs work
- [ ] Start/stop per symbol works
- [ ] Guardian monitors both symbols
- [ ] No cross-symbol contamination

**Edge Case Testing:**

```bash
# Test 1: Start ETH before BTC (order independence)
pm2 start gridbot-eth-live
pm2 start gridbot-btc-live
# Both should work regardless of order

# Test 2: Stop one symbol while other runs
pm2 stop gridbot-eth-live
pm2 logs gridbot-btc-live --lines 20
# BTC should continue trading normally

# Test 3: Guardian halt for one symbol
# Manually trigger loss limit for ETH (reduce max_account_loss_inr)
# Verify:
# - Guardian halts ETH bot
# - BTC continues trading
# - Separate HALT signals in databases

# Test 4: Concurrent order placement
# Both bots place orders simultaneously
pm2 logs gridbot-btc-live | grep "Order placed"
pm2 logs gridbot-eth-live | grep "Order placed"
# Check for API rate limit errors

# Test 5: Database isolation
sqlite3 data_bteh/bot_events_BTCUSD_LONG.db "SELECT COUNT(*) FROM events;"
sqlite3 data_bteh/bot_events_ETHUSD_LONG.db "SELECT COUNT(*) FROM events;"
# Counts should be independent, no shared events

# Test 6: State file corruption
cp data_bteh/runtime_state_ETHUSD_LONG.json data_bteh/runtime_state_ETHUSD_LONG.json.bak
rm data_bteh/runtime_state_ETHUSD_LONG.json
pm2 restart gridbot-eth-live
# ETH bot should recover, BTC unaffected

# Test 7: WebUI symbol switching
# Open http://localhost:5556
# Rapidly switch between BTCUSD and ETHUSD tabs (10+ times)
# Check browser console for errors
# Monitor backend memory: pm2 monit

# Test 8: API rate limit stress test
# Start both bots + guardian + webui
watch -n 1 "pm2 logs --lines 50 | grep 'rate limit'"
# Should see no rate limit errors

# Test 9: PM2 restart resilience
pm2 restart all
pm2 list
# All processes should recover with correct symbols
```

**Edge Case Checklist:**
- [ ] Order independence verified
- [ ] Single symbol halt doesn't affect others
- [ ] Guardian parallel checks work
- [ ] No API rate limit errors
- [ ] Database isolation confirmed
- [ ] State file recovery works
- [ ] WebUI memory stable during symbol switching
- [ ] PM2 restart resilience verified

---

### Phase 3B: Production Migration (2 days)

**Day 1: Parallel Testing**

```bash
# Keep production running on port 5555
# Run development on port 5556
# Compare both for 24 hours
```

**Day 2: Migration**

```bash
# Step 1: Stop production bot
pm2 stop gridbot-live

# Step 2: Backup production data
./scripts/backup_production_state.sh

# Step 3: Switch to multi-symbol branch
git checkout feature/multi-symbol-v5.0

# Step 4: Migrate config
python3 scripts/migrate_config_to_multi_symbol.py

# Step 5: Start new multi-symbol system
pm2 start ecosystem.multi-symbol.config.js

# Step 6: Verify
pm2 list
# Should show: gridbot-btc-live, gridbot-eth-live, guardian-live

# Step 7: Update production WebUI to port 5555
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
```

---

### Phase 3C: Documentation & Handoff (2 days)

**Update Documentation:**

1. Update `AI_CONTEXT.md`
2. Create `MULTI_SYMBOL_QUICK_START.md`
3. Update `PM2_QUICK_START.md`
4. Update `README.md`

**Create Quick Start Guide:**

```markdown
# Multi-Symbol Quick Start

## Starting Bots

# Start BTC bot
pm2 start gridbot-btc-live

# Start ETH bot
pm2 start gridbot-eth-live

# Start all
pm2 start all

## Monitoring

# View all symbols
curl http://localhost:5555/api/symbols

# View BTC positions
curl http://localhost:5555/api/symbol/BTCUSD/positions

## Adding New Symbol

1. Add to config.yaml symbols section
2. Add PM2 process to ecosystem.config.js
3. Restart WebUI
4. Start symbol bot: pm2 start gridbot-<symbol>-live
```

---

## 🔄 Rollback Plan

### Emergency Rollback to v4.0

```bash
# If multi-symbol has critical issues, revert to v4.0

# Step 1: Stop all multi-symbol bots
pm2 stop all

# Step 2: Switch back to production branch
git checkout production-v4.0

# Step 3: Restore v4.0 config
cp config.yaml.backup.v4.0 config.yaml

# Step 4: Restore v4.0 state files
cp data/backup_v4.0_*/runtime_state_LONG.json data/
cp data/backup_v4.0_*/bot_events_LONG.db data/

# Step 5: Start v4.0 bot
pm2 start gridbot-live

# Step 6: Verify
pm2 logs gridbot-live

# System back to single-symbol BTC trading
```

---

## 📊 Timeline Summary

| Week | Phase | Original | Additions | Total | Status |
|------|-------|----------|-----------|-------|--------|
| Week 1 | PART 1: Foundation | 40-50h | +10h (rate limiter, PM2, ETH verify) | 50-60h | Not Started |
| Week 2 | PART 2: Integration | 40-50h | +8h (parallel Guardian, frontend build) | 48-58h | Not Started |
| Week 3 | PART 3: Deployment | 30-40h | +12h (edge testing, capital docs) | 42-52h | Not Started |
| **Total** | **All Phases** | **110-140h** | **+30h** | **140-170h** | **Planning** |

**Revised Timeline:** 3.5-4 weeks (instead of 3 weeks)

**Key Additions:**
- ETH product_id verification script
- Capital allocation documentation
- PM2 ecosystem config creation
- Global API rate limiter
- Parallel Guardian checks (asyncio.gather)
- Frontend build process
- Comprehensive edge case testing (9 tests)

---

## ✅ Success Criteria

**Phase 1 Complete When:**
- [ ] Config has `symbols{}` section
- [ ] Bot accepts `<SYMBOL>` CLI argument
- [ ] State files are symbol-specific
- [ ] No hardcoded symbol references

**Phase 2 Complete When:**
- [ ] WebUI shows multiple symbols
- [ ] Can start/stop individual symbols
- [ ] Guardian monitors all symbols
- [ ]✅ Branches created** - production-4.0-clean (LOCKED), BTC (backup), BTEH (dev)
2. **✅ Currently on BTEH branch** - Ready for development
3. **Start Phase 1A** - Config architecture changes (in BTEH branch)
4. **Setup separate environment** - Port 5556, data_bteh/ directory
5. **Daily progress tracking** - Implement and test
6 [ ] BTC trading continues uninterrupted
- [ ] ETH trading can be enabled
- [ ] Documentation complete
## 🔄 Git Branch Commands Quick Reference

```bash
# View all branches
git branch -a

# Check current branch
git branch --show-current

# Switch to production (LOCKED - use only for viewing)
git checkout production-4.0-clean

# Switch to BTC (backup/staging)
git checkout BTC

# Switch to BTEH (development - where you work)
git checkout BTEH

# Commit changes in BTEH
git add -A
git commit -m "description of changes"
git push origin BTEH

# Merge production fixes into BTEH (if needed)
git checkout BTEH
git merge production-4.0-clean
git push origin BTEH
```

---

**Document Version:** 1.1  
**Last Updated:** December 30, 2025  
**Branch Structure:** ✅ Created (production-4.0-clean, BTC, BTEH)  
**Current Branch:** BTEH (development)
---

## 🎯 Next Steps

1. **Review this plan** - Approve or adjust timeline
2. **Create feature branch** - `feature/multi-symbol-v5.0`
3. **Start Phase 1A** - Config architecture changes
4. **Daily standups** - 15min progress check
5. **End of week 1** - Demo PART 1 Foundation

---

**Document Version:** 1.0  
**Last Updated:** December 30, 2025  
**Next Review:** End of Week 1 (Phase 1 completion)
