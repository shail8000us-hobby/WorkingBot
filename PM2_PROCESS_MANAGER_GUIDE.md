# PM2 Process Manager Setup - Multi-Instrument Trading

**Updated:** January 13, 2026  
**Status:** ✅ Production Ready

## 🎯 Overview

The PM2 Process Manager provides **clear separation** for different trading instruments with:

- ✅ **BTC LONG** - `gridbot-btc-long`
- ✅ **BTC SHORT** - `gridbot-btc-short`
- ✅ **ETH LONG** - `gridbot-eth-long`
- ✅ **ETH SHORT** - `gridbot-eth-short`
- ✅ **Guardian Bot** - `guardian-live` (auto-restart enabled)
- ✅ **WebUI Backend** - `webui-backend` (auto-restart enabled)

## 📁 Key Files

| File | Purpose |
|------|---------|
| `ecosystem.production.config.js` | PM2 configuration for all processes |
| `pm2_manager.sh` | Easy management script |
| `com.gridbot.guardian.plist` | LaunchAgent for guardian auto-start |

## 🚀 Quick Start

### 1. Start Individual Bots

```bash
# Start BTC LONG
./pm2_manager.sh start btc-long

# Start ETH LONG
./pm2_manager.sh start eth-long

# Start Guardian (monitors all bots)
./pm2_manager.sh start guardian

# Start WebUI
./pm2_manager.sh start webui
```

### 2. Start All Bots

```bash
# Start all 4 trading bots
./pm2_manager.sh start all-bots

# Start everything (bots + guardian + webui)
./pm2_manager.sh start all
```

### 3. Check Status

```bash
./pm2_manager.sh status
```

Expected output:
```
┌────┬──────────────────┬─────────────┬─────────┬─────────┬──────────┬────────┬──────┬───────────┬──────────┬──────────┐
│ id │ name             │ namespace   │ version │ mode    │ pid      │ uptime │ ↺    │ status    │ cpu      │ mem      │
├────┼──────────────────┼─────────────┼─────────┼─────────┼──────────┼────────┼──────┼───────────┼──────────┼──────────┤
│ 0  │ gridbot-btc-long │ default     │ N/A     │ fork    │ 12345    │ 10m    │ 0    │ online    │ 0%       │ 45.2mb   │
│ 1  │ guardian-live    │ default     │ N/A     │ fork    │ 12346    │ 10m    │ 0    │ online    │ 0%       │ 32.1mb   │
│ 2  │ webui-backend    │ default     │ N/A     │ fork    │ 12347    │ 10m    │ 0    │ online    │ 0%       │ 55.8mb   │
└────┴──────────────────┴─────────────┴─────────┴─────────┴──────────┴────────┴──────┴───────────┴──────────┴──────────┘
```

## 🔍 Monitoring

### View Logs

```bash
# Tail logs for specific bot
./pm2_manager.sh logs btc-long

# View all logs
./pm2_manager.sh logs

# Real-time monitoring dashboard
./pm2_manager.sh monit
```

### Check Individual Bot

```bash
pm2 describe gridbot-btc-long
```

## 🛑 Stopping Bots

```bash
# Stop specific bot
./pm2_manager.sh stop btc-long

# Stop all trading bots (but keep guardian & webui running)
./pm2_manager.sh stop all-bots

# Stop everything
./pm2_manager.sh stop all
```

## 🔄 Restarting

```bash
# Restart specific bot
./pm2_manager.sh restart btc-long

# Restart all trading bots
./pm2_manager.sh restart all-bots

# Restart everything
./pm2_manager.sh restart all
```

## 🤖 Guardian Auto-Start with LaunchAgent

The guardian bot can be configured to start automatically on system boot.

### Install LaunchAgent

```bash
# Copy plist to LaunchAgents directory
cp com.gridbot.guardian.plist ~/Library/LaunchAgents/

# Load the agent
launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist

# Check if it's running
launchctl list | grep gridbot.guardian
```

### Uninstall LaunchAgent

```bash
# Unload the agent
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist

# Remove the file
rm ~/Library/LaunchAgents/com.gridbot.guardian.plist
```

### Check LaunchAgent Logs

```bash
tail -f logs/launchagent-guardian.log
tail -f logs/launchagent-guardian-error.log
```

## 📊 WebUI Integration

The PM2 Process Manager tab in the WebUI displays:

- ✅ **By Symbol** - Shows processes grouped by trading instrument
  - 0 Live Trading (BTC LONG, BTC SHORT, ETH LONG, ETH SHORT shown separately)
  - 0 Demo Trading
  - 0 All Processes (total count)
  
- ✅ **Start/Stop Buttons** - Individual control per instrument

## 🏗️ Architecture

### Process Separation

Each trading instrument runs as a **separate PM2 process**:

```
gridbot-btc-long   → BTCUSD symbol, LONG mode, separate config
gridbot-btc-short  → BTCUSD symbol, SHORT mode, separate config  
gridbot-eth-long   → ETHUSD symbol, LONG mode, separate config
gridbot-eth-short  → ETHUSD symbol, SHORT mode, separate config
```

### Process Configuration

| Process | Auto-Restart | Memory Limit | Kill Timeout |
|---------|-------------|--------------|--------------|
| Trading Bots | ❌ No (manual only) | 500MB | 15s |
| Guardian | ✅ Yes | 300MB | 5s |
| WebUI | ✅ Yes | 400MB | 5s |

**Why no auto-restart for trading bots?**
- Requires manual intervention to diagnose issues
- Prevents runaway processes during errors
- Guardian monitors and alerts on crashes

### Environment Variables

Each process receives:

```javascript
env: {
  PYTHONPATH: '/Users/ssr/Projects/WorkingBot',
  TRADING_MODE: 'live',
  SYMBOL: 'BTCUSD',  // or 'ETHUSD'
  MODE: 'LONG'       // or 'SHORT'
}
```

### Log Files

Each process has separate log files:

```
logs/pm2-gridbot-btc-long-out.log
logs/pm2-gridbot-btc-long-error.log
logs/pm2-gridbot-btc-short-out.log
logs/pm2-gridbot-btc-short-error.log
logs/pm2-gridbot-eth-long-out.log
logs/pm2-gridbot-eth-long-error.log
logs/pm2-gridbot-eth-short-out.log
logs/pm2-gridbot-eth-short-error.log
logs/pm2-guardian-live-out.log
logs/pm2-guardian-live-error.log
logs/pm2-webui-backend-out.log
logs/pm2-webui-backend-error.log
```

## 🔧 Advanced Usage

### Save PM2 State

```bash
./pm2_manager.sh save
```

This saves the current process list, so they restart after system reboot if using `pm2 startup`.

### Setup PM2 Startup

```bash
# Generate startup script
pm2 startup

# Follow the instructions to run the command with sudo
# Example: sudo env PATH=$PATH:/usr/local/bin pm2 startup launchd -u ssr --hp /Users/ssr

# Save current processes
./pm2_manager.sh save
```

### Delete Processes

```bash
# Delete specific process
./pm2_manager.sh delete btc-long

# Delete all processes
./pm2_manager.sh delete all
```

## 📝 Configuration Files

### config.yaml

The bot reads configuration from `config.yaml`:

```yaml
instances:
  BTCUSD_LONG:
    symbol: BTCUSD
    mode: LONG
    enabled: true
    capital:
      allocated_usd: 7000
    grid:
      geometry:
        lower: '85000'
        upper: '95000'
        step: '500'
  
  BTCUSD_SHORT:
    symbol: BTCUSD
    mode: SHORT
    enabled: false
    # ... config ...
```

### Bot Startup Logic

The bot (`bot/strategy/async_gridbot.py`) accepts a symbol argument:

```python
# Start with symbol argument
python3 bot/strategy/async_gridbot.py BTCUSD

# Bot determines mode from config.yaml instances
# Looks for BTCUSD_LONG or BTCUSD_SHORT based on enabled flag
```

PM2 passes the symbol via `args`:

```javascript
{
  name: 'gridbot-btc-long',
  script: 'bot/strategy/async_gridbot.py',
  args: 'BTCUSD',  // Symbol argument
  env: {
    MODE: 'LONG'   // Additional context
  }
}
```

## ⚠️ Important Notes

### Manual Restart Policy

Trading bots do **NOT** auto-restart by design:

- Prevents cascading failures
- Forces manual diagnosis
- Guardian alerts on crashes
- Operator decides when to restart

### Guardian Auto-Restart

Guardian **DOES** auto-restart:

- Critical monitoring function
- No order execution risk
- Must stay running 24/7
- Monitors all trading bots

### WebUI Shows All Processes

The WebUI PM2 Process Manager tab displays:

- Current status of each instrument
- Memory usage
- Uptime
- Start/Stop controls

**Note:** The screenshot shows "0" for all counts because PM2 is currently empty. After starting bots, you'll see them appear under "By Symbol" section.

## 🐛 Troubleshooting

### Bot Won't Start

```bash
# Check PM2 logs
./pm2_manager.sh logs btc-long

# Check if port is in use
lsof -ti:5555 | xargs kill -9

# Verify config exists
cat config.yaml | grep BTCUSD_LONG
```

### Guardian Not Auto-Starting

```bash
# Check LaunchAgent status
launchctl list | grep gridbot.guardian

# Check logs
tail -f logs/launchagent-guardian.log

# Reload agent
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
```

### PM2 Not Found

```bash
# Install PM2
npm install -g pm2

# Verify installation
which pm2
pm2 --version
```

### Process Shows "errored" Status

```bash
# Check error logs
./pm2_manager.sh logs btc-long

# Delete and restart
pm2 delete gridbot-btc-long
./pm2_manager.sh start btc-long
```

## 📚 Further Reading

- **AI_CONTEXT.md** - Complete system overview
- **BOT_STRUCTURE.md** - Technical architecture
- **config.yaml** - Configuration reference
- **PM2 Documentation** - https://pm2.keymetrics.io/docs/usage/quick-start/

## 🎉 Summary

The new PM2 setup provides:

✅ **Clear Separation** - Each instrument has its own process  
✅ **Guardian Auto-Start** - Via LaunchAgent for 24/7 monitoring  
✅ **Easy Management** - Single script for all operations  
✅ **WebUI Integration** - Visual process management  
✅ **Production Ready** - Tested and documented  

Start trading with confidence! 🚀
