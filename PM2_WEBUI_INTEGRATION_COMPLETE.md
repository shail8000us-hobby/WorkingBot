# PM2 Process Manager - WebUI Integration Complete

## ✅ Setup Status

**All trading bot processes are now running and visible in the WebUI PM2 Process Manager!**

### Current Running Processes

```bash
pm2 list
```

You should see:
- ✅ **gridbot-BTCUSD-LONG** - BTC Long position trading
- ✅ **gridbot-BTCUSD-SHORT** - BTC Short position trading
- ✅ **gridbot-ETHUSD-LONG** - ETH Long position trading
- ✅ **gridbot-ETHUSD-SHORT** - ETH Short position trading
- ✅ **webui-backend** - WebUI backend server
- ⚠️ **guardian-live** - Guardian monitor (may need separate configuration)

## WebUI PM2 Process Manager

### Viewing Processes in WebUI

1. **Open WebUI**: Navigate to the PM2 Process Manager tab
2. **By Symbol Tab**: Shows processes grouped by trading pair:
   - **BTCUSD**: gridbot-BTCUSD-LONG, gridbot-BTCUSD-SHORT
   - **ETHUSD**: gridbot-ETHUSD-LONG, gridbot-ETHUSD-SHORT
3. **All Processes Tab**: Shows all 6 processes

### Process Naming Convention

The WebUI expects this format:
```
gridbot-{SYMBOL}-{MODE}
```

Examples:
- `gridbot-BTCUSD-LONG` → Extracts: Symbol=BTCUSD, Mode=LONG
- `gridbot-ETHUSD-SHORT` → Extracts: Symbol=ETHUSD, Mode=SHORT

The frontend JavaScript automatically:
1. Parses process names
2. Groups by symbol (BTCUSD, ETHUSD)
3. Shows separate LONG/SHORT instances

## Quick Management Commands

### Using pm2_manager.sh

```bash
# Start specific bots
./pm2_manager.sh start btc-long
./pm2_manager.sh start btc-short
./pm2_manager.sh start eth-long
./pm2_manager.sh start eth-short

# Stop specific bots
./pm2_manager.sh stop btc-long
./pm2_manager.sh stop all-bots

# View logs
./pm2_manager.sh logs btc-long

# Show status
./pm2_manager.sh status
```

### Direct PM2 Commands

```bash
# Start all processes
pm2 start ecosystem.production.config.js

# Start specific process
pm2 start ecosystem.production.config.js --only gridbot-BTCUSD-LONG

# Stop specific process
pm2 stop gridbot-BTCUSD-LONG

# Restart specific process
pm2 restart gridbot-BTCUSD-LONG

# View logs
pm2 logs gridbot-BTCUSD-LONG

# Real-time monitoring dashboard
pm2 monit

# Show detailed info
pm2 show gridbot-BTCUSD-LONG

# Delete process
pm2 delete gridbot-BTCUSD-LONG

# Save process list for auto-start
pm2 save
```

## Configuration Files

### Ecosystem Config
**File**: `ecosystem.production.config.js`
- Defines all 6 PM2 processes
- Uses WebUI-compatible naming convention
- Maps INSTANCE_NAME to config.yaml instances
- Correct script paths (bot/strategy/async_gridbot.py)

### PM2 Manager Script
**File**: `pm2_manager.sh`
- Wrapper for easy process management
- Friendly names: btc-long, btc-short, eth-long, eth-short
- Maps to full PM2 process names

### Config YAML
**File**: `config.yaml`
- Instance definitions: BTCUSD_LONG, BTCUSD_SHORT, ETHUSD_LONG
- Each instance has symbol and mode
- GridBot reads INSTANCE_NAME from environment

## Architecture

### Multi-Instance Flow

```
PM2 Process                Environment Var        Config YAML Instance
----------------          ------------------      --------------------
gridbot-BTCUSD-LONG   →   INSTANCE_NAME:        →   BTCUSD_LONG:
                          BTCUSD_LONG                   symbol: BTCUSD
                                                        mode: LONG

gridbot-BTCUSD-SHORT  →   INSTANCE_NAME:        →   BTCUSD_SHORT:
                          BTCUSD_SHORT                  symbol: BTCUSD
                                                        mode: SHORT

gridbot-ETHUSD-LONG   →   INSTANCE_NAME:        →   ETHUSD_LONG:
                          ETHUSD_LONG                   symbol: ETHUSD
                                                        mode: LONG
```

### WebUI Integration

```
1. PM2 → List processes via PM2 API
2. Backend (pm2.py) → Call pm2.list_all_processes()
3. Frontend (PM2Panel.js) → Extract symbol from process name
4. Display → Group by symbol in "By Symbol" tab
```

## Logs

All PM2 logs are stored in:
```
logs/pm2/
  ├── gridbot-BTCUSD-LONG-out.log
  ├── gridbot-BTCUSD-LONG-error.log
  ├── gridbot-BTCUSD-SHORT-out.log
  ├── gridbot-BTCUSD-SHORT-error.log
  ├── gridbot-ETHUSD-LONG-out.log
  ├── gridbot-ETHUSD-LONG-error.log
  ├── gridbot-ETHUSD-SHORT-out.log
  ├── gridbot-ETHUSD-SHORT-error.log
  ├── guardian-live-out.log
  ├── guardian-live-error.log
  ├── webui-backend-out.log
  └── webui-backend-error.log
```

View logs:
```bash
# PM2 command
pm2 logs gridbot-BTCUSD-LONG

# Direct file access
tail -f logs/pm2/gridbot-BTCUSD-LONG-out.log
tail -f logs/pm2/gridbot-BTCUSD-LONG-error.log
```

## Guardian Bot Note

The guardian bot currently shows as "errored" (15 restarts). This is likely due to:
1. Missing configuration
2. Dependency issues
3. API connection problems

To troubleshoot:
```bash
pm2 logs guardian-live --lines 50
```

You can disable it for now:
```bash
pm2 delete guardian-live
pm2 save
```

## Auto-Start on System Boot

To enable auto-start using macOS LaunchAgent:

1. Copy LaunchAgent plist:
   ```bash
   cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
   ```

2. Load LaunchAgent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
   ```

3. Verify:
   ```bash
   launchctl list | grep gridbot
   ```

**Note**: The current LaunchAgent is configured for guardian only. For full auto-start, you may want to create a startup script that runs `pm2 resurrect`.

## Troubleshooting

### Processes not showing in WebUI?

1. Check PM2 is running:
   ```bash
   pm2 list
   ```

2. Check WebUI backend is running:
   ```bash
   pm2 list | grep webui-backend
   ```

3. Refresh WebUI PM2 Process Manager tab

4. Check browser console for errors (F12)

### Bot crashes immediately?

Check logs:
```bash
pm2 logs gridbot-BTCUSD-LONG --lines 50
```

Common issues:
- API credentials missing/invalid
- Database connection issues
- Config.yaml syntax errors

### Guardian keeps restarting?

The guardian may be trying to connect to bot instances. Check:
```bash
pm2 logs guardian-live --lines 50
```

If not needed, disable:
```bash
pm2 delete guardian-live
pm2 save
```

## Next Steps

1. ✅ **Verify WebUI**: Open PM2 Process Manager tab and confirm all processes appear grouped by symbol
2. ✅ **Check Bot Logs**: Monitor logs to ensure bots are trading properly
3. ⚠️ **Fix Guardian**: Investigate guardian-live errors if monitoring is needed
4. 📝 **Configure Alerts**: Set up email/Telegram alerts for process crashes
5. 🔄 **Auto-Start**: Set up proper system auto-start for all processes

## References

- **PM2 Documentation**: https://pm2.keymetrics.io/docs/usage/quick-start/
- **Ecosystem File**: https://pm2.keymetrics.io/docs/usage/application-declaration/
- **Process Management**: https://pm2.keymetrics.io/docs/usage/process-management/
