# WebUI Multi-Symbol LONG/SHORT Mode Configuration Guide

**Date**: January 3, 2026  
**Architecture**: v6.0 Instance-Based (Instance = Symbol + Mode)

## Problem Solved

### Issue 1: ETHUSD Bot Not Starting via API ✅ FIXED
**Root Cause**: Wrong LaunchAgent service (`com.gridbot.webui`) was running instead of `com.gridbot.production.webui`, causing stale config.

**Solution**:
```bash
# Stop wrong service
launchctl stop com.gridbot.webui

# Start correct service
launchctl start com.gridbot.production.webui

# Verify correct service is running
lsof -i :5555 | grep LISTEN
```

**Result**: ETHUSD now starts successfully via API!
```bash
curl -X POST http://localhost:5555/api/symbols/ETHUSD/process/start
# {"message":"Started trading for ETHUSD","success":true...}
```

---

## LONG vs SHORT Mode Configuration

### Current Architecture

Your config uses **v6.0 Instance-Based Structure**:
- **Instance** = Symbol + Mode (e.g., `BTCUSD_LONG`, `ETHUSD_SHORT`)
- Each instance has separate grid parameters, RSI thresholds, and capital allocation
- PM2 processes are symbol-specific (gridbot-btcusd-live, gridbot-ethusd-live)

### Config Structure

**instances section** (v6.0 - Full control with mode):
```yaml
instances:
  BTCUSD_LONG:
    symbol: BTCUSD
    mode: LONG                 # ← LONG mode
    enabled: true
    product_id: 139
    grid:
      geometry:
        lower: '85000'          # Buy zone lower bound
        upper: '95000'          # Buy zone upper bound
    safety:
      rsi:
        stop_threshold: 30.0    # Stop when RSI ≤ 30 (too weak)
        resume_threshold: 40.0
        
  BTCUSD_SHORT:
    symbol: BTCUSD
    mode: SHORT                # ← SHORT mode
    enabled: false             # Currently disabled
    product_id: 139
    grid:
      geometry:
        lower: '95000'          # Sell zone lower bound
        upper: '105000'         # Sell zone upper bound
    safety:
      rsi:
        stop_threshold: 70.0    # Stop when RSI ≥ 70 (too strong)
        resume_threshold: 60.0
        
  ETHUSD_LONG:
    symbol: ETHUSD
    mode: LONG                 # ← LONG mode
    enabled: true
    product_id: 3136
    grid:
      geometry:
        lower: '3200'
        upper: '3800'
    safety:
      rsi:
        stop_threshold: 30.0    # LONG-specific threshold
        resume_threshold: 40.0
```

**symbols section** (v5.0 compatibility - Limited, symbol-level only):
```yaml
symbols:
  BTCUSD:
    enabled: true
    mode: LONG                 # Default mode for this symbol
    product_id: 139
    grid:
      # Grid params...
    
  ETHUSD:
    enabled: true
    mode: LONG                 # Default mode for this symbol
    product_id: 3136
```

---

## How to Configure LONG/SHORT Modes

### Option 1: Using Instance Section (Recommended for v6.0)

Enable both LONG and SHORT for same symbol simultaneously:

```yaml
instances:
  ETHUSD_LONG:
    symbol: ETHUSD
    mode: LONG
    enabled: true              # ✅ Enable LONG trading
    grid:
      geometry:
        lower: '3200'           # LONG: Buy when price drops
        upper: '3800'
        
  ETHUSD_SHORT:
    symbol: ETHUSD
    mode: SHORT
    enabled: true              # ✅ Enable SHORT trading
    grid:
      geometry:
        lower: '3800'           # SHORT: Sell when price rises
        upper: '4400'
```

**PM2 Process Names** (would need to be added to ecosystem config):
- `gridbot-ethusd-long-live` - ETHUSD LONG bot
- `gridbot-ethusd-short-live` - ETHUSD SHORT bot
- `guardian-live` - Shared guardian

### Option 2: Using Symbols Section (Current Implementation)

Simpler but only one mode per symbol:

```yaml
symbols:
  ETHUSD:
    enabled: true
    mode: LONG                 # Switch between LONG/SHORT here
    product_id: 3136
```

**To switch ETHUSD from LONG to SHORT**:
1. Edit `config.yaml`:
   ```yaml
   symbols:
     ETHUSD:
       mode: SHORT             # Change from LONG to SHORT
       grid:
         geometry:
           lower: '3800'        # Adjust grid for SHORT
           upper: '4400'
   ```

2. Restart bot:
   ```bash
   pm2 restart gridbot-ethusd-live
   ```

**Current PM2 Processes**:
- `gridbot-btcusd-live` - BTCUSD (mode from symbols.BTCUSD.mode)
- `gridbot-ethusd-live` - ETHUSD (mode from symbols.ETHUSD.mode)

---

## Critical RSI Threshold Differences

**LONG Mode** (Buying at low prices):
- **stop_threshold: 30** - Stop when RSI ≤ 30 (oversold, market too weak)
- **resume_threshold: 40** - Resume when RSI > 40 (market recovering)
- **Grid**: Lower prices (buy zone)

**SHORT Mode** (Selling at high prices):
- **stop_threshold: 70** - Stop when RSI ≥ 70 (overbought, market too strong)
- **resume_threshold: 60** - Resume when RSI < 60 (market cooling)
- **Grid**: Higher prices (sell zone)

**Example for ETHUSD**:
```yaml
# LONG Mode (current)
ETHUSD_LONG:
  mode: LONG
  grid:
    lower: '3200'  # Start buying here
    upper: '3800'  # Stop buying here
  safety:
    rsi:
      stop_threshold: 30.0     # Stop if market drops too much
      resume_threshold: 40.0

# SHORT Mode (if enabled)
ETHUSD_SHORT:
  mode: SHORT
  grid:
    lower: '3800'  # Start selling here
    upper: '4400'  # Stop selling here
  safety:
    rsi:
      stop_threshold: 70.0     # Stop if market rises too much
      resume_threshold: 60.0
```

---

## WebUI Mode Selection

### Current Implementation (v5.0 Symbols API)

The webUI currently uses symbol-level control:
- Start/stop per symbol: `POST /api/symbols/ETHUSD/process/start`
- Each symbol has one PM2 process: `gridbot-ethusd-live`
- Mode is determined by `symbols.ETHUSD.mode` in config

**User Experience**:
1. User clicks "Start ETHUSD" button
2. Backend starts `gridbot-ethusd-live` PM2 process
3. Bot reads `symbols.ETHUSD.mode` from config (currently LONG)
4. Bot trades in that mode

**To add mode selection in webUI**:
- Frontend needs dropdown/toggle: "ETHUSD: [LONG|SHORT]"
- On selection, update config.yaml: `symbols.ETHUSD.mode`
- Restart bot to apply: `pm2 restart gridbot-ethusd-live`

### Future Implementation (v6.0 Instances API)

For simultaneous LONG+SHORT:
- Separate buttons: "Start ETHUSD LONG" and "Start ETHUSD SHORT"
- API endpoints:
  - `POST /api/instances/ETHUSD_LONG/start`
  - `POST /api/instances/ETHUSD_SHORT/start`
- Separate PM2 processes:
  - `gridbot-ethusd-long-live`
  - `gridbot-ethusd-short-live`
- Both can run simultaneously with different grids

---

## How to Enable SHORT Mode for ETHUSD

### Method 1: Single Mode (Current Architecture)

**Step 1**: Edit config.yaml
```yaml
symbols:
  ETHUSD:
    enabled: true
    mode: SHORT              # ← Change from LONG to SHORT
    product_id: 3136
    grid:
      geometry:
        lower: '3800'         # ← Adjust grid for SHORT (higher range)
        upper: '4400'
        step: '50'
        reference: '4100'
    # ... rest of config
```

**Step 2**: Restart bot
```bash
pm2 restart gridbot-ethusd-live
```

**Step 3**: Verify mode
```bash
# Check bot logs
pm2 logs gridbot-ethusd-live --lines 20 | grep -i mode
```

### Method 2: Dual Mode (Requires Changes)

**Step 1**: Enable SHORT instance in config.yaml
```yaml
instances:
  ETHUSD_SHORT:
    symbol: ETHUSD
    mode: SHORT
    enabled: true            # ← Enable this
    # ... configure grid for SHORT range
```

**Step 2**: Add PM2 process to ecosystem.gridbot.config.js
```javascript
{
  name: "gridbot-ethusd-short-live",
  script: "start_bot_with_recovery.py",
  cwd: "/Users/ssr/Projects/WorkingBot",
  env: {
    SYMBOL: "ETHUSD",
    INSTANCE: "ETHUSD_SHORT",  // New: specify instance
    TRADING_MODE: "live",
    BOT_MODE: "SHORT"
  }
}
```

**Step 3**: Start SHORT bot
```bash
pm2 start ecosystem.gridbot.config.js --only gridbot-ethusd-short-live
pm2 save
```

---

## Current Status

### Running Processes
```
✅ gridbot-btcusd-live  - BTCUSD LONG mode
✅ gridbot-ethusd-live  - ETHUSD LONG mode
✅ guardian-live        - Risk management
```

### Configuration
```yaml
# Active Modes
BTCUSD: LONG (enabled)
ETHUSD: LONG (enabled)

# Available but Disabled
BTCUSD: SHORT (disabled)
```

### WebUI Control
- **Start ETHUSD**: `POST /api/symbols/ETHUSD/process/start` ✅ Working
- **Stop ETHUSD**: `POST /api/symbols/ETHUSD/process/stop` ✅ Working
- **Status**: `GET /api/symbols/ETHUSD/process/status` ✅ Working

---

## Next Steps for Mode Selection in WebUI

### Option A: Simple Mode Switcher (Quick)
1. Add dropdown in webUI: "ETHUSD Mode: [LONG|SHORT]"
2. On change:
   - Call new API: `POST /api/symbols/ETHUSD/config/mode` with `{"mode": "SHORT"}`
   - Update config.yaml: `symbols.ETHUSD.mode = SHORT`
   - Restart bot: `pm2 restart gridbot-ethusd-live`
3. User must stop bot before changing mode (safety measure)

### Option B: Dual Mode Support (Advanced)
1. Update PM2 config to support both LONG and SHORT processes
2. Add instance-based API routes: `/api/instances/{INSTANCE_NAME}/start`
3. WebUI shows separate buttons: "ETHUSD LONG [Start]" and "ETHUSD SHORT [Start]"
4. Both modes can run simultaneously with separate grids
5. Separate capital allocation for each mode

---

## Troubleshooting

### ETHUSD Won't Start via API
✅ **Fixed**: Ensure correct LaunchAgent is running
```bash
# Check which service is on port 5555
lsof -i :5555 | grep LISTEN

# Should show: com.gridbot.production.webui
# If shows com.gridbot.webui, stop it:
launchctl stop com.gridbot.webui
launchctl start com.gridbot.production.webui
```

### Mode Not Changing
1. Check config syntax:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```
2. Verify bot restarted:
   ```bash
   pm2 logs gridbot-ethusd-live --lines 5 | grep "Grid Mode\|BOT_MODE"
   ```
3. Check instance vs symbols confusion:
   - Instance-based: `instances.ETHUSD_LONG.mode`
   - Symbol-based: `symbols.ETHUSD.mode`

---

**Last Updated**: 2026-01-03 17:40 UTC  
**Tested**: ETHUSD LONG mode working, API start/stop operational  
**Ready for**: Mode switcher UI implementation
