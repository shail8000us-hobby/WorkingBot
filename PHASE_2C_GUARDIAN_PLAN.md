# Phase 2C: Guardian Multi-Symbol Support - IMPLEMENTATION PLAN

## Current Architecture (v4.0 - Single Symbol)

Guardian monitors one symbol (BTCUSD) with:
- Position monitoring
- Liquidation distance tracking
- Health checks
- SQL-based GO/STOP signals

## Target Architecture (v5.0 - Multi-Symbol)

Guardian monitors ALL enabled symbols simultaneously with:
- **Per-Symbol Risk Tracking**: Separate risk calculations for each symbol
- **Unified Stop Logic**: STOP if ANY symbol triggers critical risk
- **Aggregated Alerts**: Combined Telegram notifications
- **Symbol-Specific SQL Tables**: Separate guardian_signals per symbol

## Implementation Strategy

### Option A: Single Guardian, Multiple Monitors (RECOMMENDED)
```
Guardian Bot (ONE instance)
├─ BTCUSD Monitor (PositionMonitor, LiquidationMonitor)
├─ ETHUSD Monitor (PositionMonitor, LiquidationMonitor)
└─ Risk Aggregator → Publish unified GO/STOP signal
```

**Pros:**
- Simple deployment (one PM2 process)
- Centralized risk aggregation
- Lower resource usage

**Cons:**
- Slightly more complex code

### Option B: Multiple Guardian Instances (SIMPLER CODE)
```
Guardian Bot - BTCUSD (instance 1)
Guardian Bot - ETHUSD (instance 2)
```

**Pros:**
- Simpler code (no changes needed)
- Independent monitoring
- Easier debugging

**Cons:**
- Multiple PM2 processes
- No unified stop logic
- Higher resource usage

## DECISION: Use Option A (Single Guardian, Multiple Monitors)

Rationale:
- Better resource efficiency
- Unified risk view
- One Telegram notification stream
- Better for production

## Code Changes Required

### 1. Guardian Initialization (guardian_bot.py)

**Before:**
```python
self.position_monitor = PositionMonitor(config, exchange)
```

**After:**
```python
self.symbol_monitors = {}
for symbol_name, symbol_config in config.symbols.items():
    if symbol_config.enabled:
        self.symbol_monitors[symbol_name] = {
            'position': PositionMonitor(symbol_config, exchange, symbol_name),
            'liquidation': LiquidationMonitor(symbol_config, exchange, symbol_name),
            'health': HealthTracker(symbol_config, symbol_name)
        }
```

### 2. Risk Decision Engine (risk_decision_engine.py)

**Before:**
```python
def analyze_risk(self, position_data, liquidation_data):
    # Single symbol analysis
    signal = 'GO' if safe else 'STOP'
    self.publish_signal(signal)
```

**After:**
```python
def analyze_risk_multi_symbol(self, symbol_data_map):
    # Analyze each symbol
    symbol_signals = {}
    for symbol, data in symbol_data_map.items():
        symbol_signals[symbol] = self.analyze_symbol(symbol, data)
    
    # Aggregate: STOP if ANY symbol is STOP
    unified_signal = 'STOP' if 'STOP' in symbol_signals.values() else 'GO'
    
    # Publish per-symbol signals
    for symbol, signal in symbol_signals.items():
        self.publish_signal(symbol, signal)
    
    # Publish unified signal
    self.publish_unified_signal(unified_signal)
```

### 3. SQL Schema Updates

**Before:**
```sql
CREATE TABLE guardian_signals (
    timestamp REAL,
    signal TEXT,  -- GO or STOP
    reason TEXT
)
```

**After:**
```sql
-- Per-symbol signals
CREATE TABLE guardian_signals_BTCUSD (
    timestamp REAL,
    signal TEXT,
    reason TEXT,
    symbol TEXT DEFAULT 'BTCUSD'
)

CREATE TABLE guardian_signals_ETHUSD (
    timestamp REAL,
    signal TEXT,
    reason TEXT,
    symbol TEXT DEFAULT 'ETHUSD'
)

-- Unified signal (for backward compatibility)
CREATE TABLE guardian_signals (
    timestamp REAL,
    signal TEXT,
    reason TEXT,
    symbols_data TEXT  -- JSON: {BTCUSD: GO, ETHUSD: STOP}
)
```

### 4. Monitoring Loop

**Before:**
```python
async def monitoring_loop(self):
    while True:
        position_data = await self.position_monitor.get_data()
        liquidation_data = await self.liquidation_monitor.get_data()
        
        await self.risk_engine.analyze_risk(position_data, liquidation_data)
        await asyncio.sleep(self.check_interval)
```

**After:**
```python
async def monitoring_loop(self):
    while True:
        symbol_data = {}
        
        # Collect data from all symbols
        for symbol, monitors in self.symbol_monitors.items():
            symbol_data[symbol] = {
                'position': await monitors['position'].get_data(),
                'liquidation': await monitors['liquidation'].get_data(),
                'health': await monitors['health'].get_status()
            }
        
        # Analyze all symbols
        await self.risk_engine.analyze_risk_multi_symbol(symbol_data)
        
        await asyncio.sleep(self.check_interval)
```

### 5. Telegram Alerts

**Before:**
```python
send_telegram_alert(f"🛑 STOP Signal: {reason}")
```

**After:**
```python
# Per-symbol alerts
for symbol, signal_data in symbol_signals.items():
    if signal_data['signal'] == 'STOP':
        send_telegram_alert(f"⚠️ {symbol} STOP: {signal_data['reason']}")

# Unified alert
if unified_signal == 'STOP':
    send_telegram_alert(
        f"🛑 TRADING HALTED - Critical Risk Detected\n"
        f"Affected Symbols: {', '.join(stopped_symbols)}\n"
        f"Action: All trading bots STOPPED"
    )
```

## File Changes Summary

```
✅ TO MODIFY:
- bot/guardian/core/guardian_bot.py (multi-symbol monitors)
- bot/guardian/engine/risk_decision_engine.py (per-symbol analysis)
- bot/guardian/collectors/position_monitor.py (add symbol_name param)
- bot/guardian/collectors/liquidation_monitor.py (add symbol_name param)
- bot/strategy/modules/event_store.py (symbol-specific tables)

✅ TO CREATE:
- bot/guardian/core/multi_symbol_aggregator.py (risk aggregation logic)

⏸️ NO CHANGES:
- bot/guardian/collectors/health_tracker.py (already symbol-agnostic)
```

## Testing Strategy

1. **Single Symbol Test**: Verify BTCUSD still works
2. **Dual Symbol Test**: Enable ETHUSD, verify both monitored
3. **Stop Propagation**: Trigger STOP on one symbol, verify all stop
4. **Alert Test**: Verify Telegram alerts for both symbols

## Backward Compatibility

- V4.0 configs (single symbol) → Guardian monitors ONE symbol
- V5.0 configs (multi-symbol) → Guardian monitors ALL enabled symbols
- SQL table names: `guardian_signals_{SYMBOL}_{MODE}` for isolation

## Deployment

```bash
# Guardian now monitors ALL enabled symbols in one process
pm2 start ecosystem.multi-symbol.config.js --only guardian-live

# Guardian logs
tail -f bot/logs/guardian.log
```

## Timeline

- Implementation: 2-3 hours
- Testing: 1 hour
- Total: 3-4 hours

**Current Status:** Plan complete, ready to implement ✅
