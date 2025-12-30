# Phase 3A: Integration Testing - TEST PLAN

## Test Scenarios

### 1. Single Symbol Test (BTCUSD Only)
**Goal:** Verify v5.0 works with one symbol (backward compatibility)

```bash
# Config: BTCUSD enabled, ETHUSD disabled
python3 bot/strategy/async_gridbot.py BTCUSD

# Expected:
✅ Bot starts successfully
✅ Database: data/bot_events_BTCUSD_LONG.db created
✅ Monitoring: data/monitoring_snapshot_BTCUSD_LONG.json updated
✅ WebUI shows BTCUSD only in dropdown
✅ Orders placed with BTCUSD product_id (139)
```

### 2. Multi-Symbol Test (BTCUSD + ETHUSD)
**Goal:** Verify both symbols can run simultaneously

```bash
# Enable both symbols in config.yaml
# symbols:
#   BTCUSD:
#     enabled: true
#   ETHUSD:
#     enabled: true

# Start both bots
pm2 start ecosystem.multi-symbol.config.js

# Expected:
✅ gridbot-btc-live starts (port 5555 logic)
✅ gridbot-eth-live starts
✅ Both databases created (BTCUSD, ETHUSD)
✅ Both monitoring snapshots updated
✅ WebUI dropdown shows both symbols
✅ Symbol selector switches between BTCUSD/ETHUSD data
```

### 3. WebUI Multi-Symbol Test
**Goal:** Verify frontend correctly displays per-symbol data

```bash
# Open WebUI
open http://localhost:5556

# Test Steps:
1. Check symbol dropdown shows BTCUSD, ETHUSD
2. Select BTCUSD → Verify status=active, positions load
3. Select ETHUSD → Verify status=active, positions load
4. Check monitoring panel updates per symbol
5. Verify grid parameters match config for each symbol
6. Check PnL displays correctly per symbol
```

### 4. Database Isolation Test
**Goal:** Verify no data mixing between symbols

```bash
# Check databases are separate
ls -lh data/bot_events_*.db
# Expected:
# bot_events_BTCUSD_LONG.db
# bot_events_ETHUSD_LONG.db

# Query BTCUSD database
sqlite3 data/bot_events_BTCUSD_LONG.db "SELECT symbol FROM positions;"
# Expected: Only BTCUSD

# Query ETHUSD database
sqlite3 data/bot_events_ETHUSD_LONG.db "SELECT symbol FROM positions;"
# Expected: Only ETHUSD
```

### 5. Guardian Multi-Symbol Test
**Goal:** Verify Guardian monitors both symbols

```bash
# Check Guardian logs
tail -f bot/logs/guardian.log

# Expected:
✅ Guardian monitoring BTCUSD
✅ Guardian monitoring ETHUSD
✅ Risk calculations per symbol
✅ Unified STOP propagates to both bots
```

### 6. Symbol Enable/Disable Test
**Goal:** Verify config changes work

```bash
# Disable ETHUSD in config.yaml
symbols:
  ETHUSD:
    enabled: false

# Restart WebUI backend
pm2 restart webui-backend-dev

# Test:
curl http://localhost:5556/api/symbols/ETHUSD
# Expected: status="disabled"

# Try to start ETHUSD bot
python3 bot/strategy/async_gridbot.py ETHUSD
# Expected: Error - "Symbol 'ETHUSD' is disabled"
```

### 7. API Symbol Parameter Test
**Goal:** Verify all API routes accept symbol param

```bash
# Test all monitoring routes
curl http://localhost:5556/api/monitoring/status?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/price-health?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/pre-order-stats?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/tp-verification?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/anomalies?symbol=BTCUSD
curl http://localhost:5556/api/monitoring/predictive-map?symbol=BTCUSD

# Test with ETHUSD
curl http://localhost:5556/api/monitoring/status?symbol=ETHUSD

# All should return symbol-specific data
```

### 8. PM2 Process Management Test
**Goal:** Verify PM2 multi-instance management

```bash
# Start all processes
pm2 start ecosystem.multi-symbol.config.js

# Check status
pm2 status
# Expected:
# gridbot-btc-live    │ online
# gridbot-eth-live    │ online
# guardian-live       │ online
# webui-backend-dev   │ online

# Restart specific symbol
pm2 restart gridbot-btc-live
# Expected: Only BTCUSD bot restarts

# Stop ETHUSD only
pm2 stop gridbot-eth-live
# Expected: BTCUSD continues running
```

### 9. Crash Recovery Test
**Goal:** Verify auto-restart works per symbol

```bash
# Kill BTCUSD bot process
pm2 stop gridbot-btc-live

# Check PM2 auto-restart
pm2 status gridbot-btc-live
# Expected: auto-restarts (if autorestart:true)

# Verify ETHUSD unaffected
pm2 status gridbot-eth-live
# Expected: Still running
```

### 10. Production Safety Test
**Goal:** Verify production branch is untouched

```bash
# Check production branch
git checkout production-4.0-clean
git status
# Expected: No changes, v4.0 intact

# Check production bot not affected
pm2 status
# Expected: gridbot-live (v4.0) still running on port 5555
```

## Success Criteria

✅ All 10 test scenarios pass
✅ No data corruption or mixing
✅ Both symbols trade independently
✅ WebUI correctly displays per-symbol data
✅ Guardian monitors both symbols
✅ Production v4.0 unaffected

## Test Execution Checklist

```bash
# 1. Pre-test setup
git checkout BTEH
pm2 stop all
pm2 delete all

# 2. Run tests 1-10
# [Execute each test scenario]

# 3. Document results
# Create: TEST_RESULTS_PHASE_3A.md

# 4. Fix any issues
# [Address failures]

# 5. Re-test until all pass

# 6. Mark Phase 3A complete
```

## Estimated Time: 2-3 hours

**Status:** Test plan complete, ready to execute ✅
