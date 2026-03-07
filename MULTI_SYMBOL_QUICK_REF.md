# Multi-Symbol Trading - Quick Reference

## System Status (January 3, 2026)

### ✅ All Systems Operational

| Process | Status | Symbol | Product ID | Database |
|---------|--------|--------|------------|----------|
| gridbot-btcusd-live | ✅ Online | BTCUSD | 27 | bot_events_BTCUSD_LONG.db |
| gridbot-ethusd-live | ✅ Online | ETHUSD | 3136 | bot_events_ETHUSD_LONG.db |
| guardian-live | ✅ Online | BTCUSD | - | Writes to BTCUSD db |
| guardian-sync | ✅ Online | All | - | Broadcasts signals |

## Critical Fixes Applied

### 1. Product ID Correction
- **BTCUSD**: 139 → **27** (correct live perpetual futures)
- **ETHUSD**: 3136 ✅ (already correct)

### 2. Multi-Symbol Startup Script
- Updated [start_bot_with_recovery.py](start_bot_with_recovery.py)
- Now reads `env.SYMBOL` and passes to AsyncGridBot
- Each bot loads symbol-specific configuration

### 3. Guardian Signal Broadcasting
- Added SYMBOL env var to Guardian (monitors BTCUSD)
- Created [sync_guardian_continuous.py](sync_guardian_continuous.py)
- Runs as `guardian-sync` PM2 process
- Syncs Guardian signals every 5 seconds to all symbol databases

## Common Commands

### Check Bot Status
```bash
pm2 list | grep gridbot
pm2 logs gridbot-btcusd-live --lines 50
pm2 logs gridbot-ethusd-live --lines 50
```

### Check Guardian Signals
```bash
pm2 logs guardian-live --lines 30
pm2 logs guardian-sync --lines 20

# Check signal counts in databases
sqlite3 data/bot_events_BTCUSD_LONG.db "SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_go';"
sqlite3 data/bot_events_ETHUSD_LONG.db "SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_go';"
```

### Restart Processes
```bash
# Restart individual bot
pm2 restart gridbot-btcusd-live
pm2 restart gridbot-ethusd-live

# Restart all trading processes
pm2 restart gridbot-btcusd-live gridbot-ethusd-live guardian-live guardian-sync
```

### Manual Guardian Signal Sync (if guardian-sync stops)
```bash
python3 sync_guardian_signals.py
```

## Configuration Files

### [config.yaml](config.yaml)
- `instances.BTCUSD_LONG.product_id: 27` - BTCUSD live
- `instances.ETHUSD_LONG.product_id: 3136` - ETHUSD live
- `symbols.BTCUSD.product_id: 27` - Legacy config
- `symbols.ETHUSD.product_id: 3136` - Legacy config

### [ecosystem.gridbot.config.js](ecosystem.gridbot.config.js)
- `gridbot-btcusd-live`: env.SYMBOL="BTCUSD"
- `gridbot-ethusd-live`: env.SYMBOL="ETHUSD"
- `guardian-live`: env.SYMBOL="BTCUSD"

## Current Trading Status

### BTCUSD
- ✅ **ACTIVE TRADING**
- Grid: $85,000 - $95,000, step $500
- Current Price: ~$89,900
- Pending BUY @ $88,000
- Guardian: 🟢 GO (signal age: <10s)

### ETHUSD
- ⏰ **WAITING FOR PRICE**
- Grid: $3,200 - $3,800, step $50
- Current Price: ~$3,102 (below grid)
- Will start trading when price >= $3,200
- Guardian: 🟢 GO (signals synced)

## Architecture Notes

### Why Guardian Sync is Needed
- Guardian monitors one symbol (BTCUSD) and writes to one database
- Each trading bot reads from its own symbol-specific database
- Guardian-sync broadcaster copies signals to all databases
- This shares Guardian protection across all symbols

### Alternative Approach (Future)
- Run separate Guardian instances per symbol
- Each Guardian monitors its own symbol
- Eliminates need for signal sync
- More resource intensive but more precise

## Troubleshooting

### ETHUSD Not Getting Guardian Signals
```bash
# Check guardian-sync is running
pm2 list | grep guardian-sync

# Restart guardian-sync
pm2 restart guardian-sync

# Manual sync
python3 sync_guardian_signals.py
```

### Invalid Contract Errors
```bash
# Verify product_ids in config
grep "product_id:" config.yaml

# Check if using correct product_id
pm2 logs gridbot-btcusd-live | grep "Product ID:"
pm2 logs gridbot-ethusd-live | grep "Product ID:"
```

### Bot Not Reading env.SYMBOL
```bash
# Check environment variables
pm2 env <process_id>

# Restart with --update-env
pm2 restart gridbot-btcusd-live --update-env
```

## See Also
- [MULTI_SYMBOL_FIX_JAN3_2026.md](MULTI_SYMBOL_FIX_JAN3_2026.md) - Full fix documentation
- [WEBUI_MULTI_SYMBOL_SETUP_JAN3_2026.md](WEBUI_MULTI_SYMBOL_SETUP_JAN3_2026.md) - WebUI integration guide
- [WEBUI_LONG_SHORT_MODE_GUIDE.md](WEBUI_LONG_SHORT_MODE_GUIDE.md) - Mode configuration guide
