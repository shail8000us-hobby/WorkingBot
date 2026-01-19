# Telegram Bot Commands Guide

Complete guide for using Telegram bot commands to monitor your trading systems.

**Created:** January 19, 2026

---

## 🤖 Grid Bot Commands (@BTCSSR_bot)

### Available Commands

#### Status Commands
| Command | Description | Example Output |
|---------|-------------|----------------|
| `/start` | Welcome message and bot intro | Shows available commands |
| `/help` | Display all available commands | Command list with descriptions |
| `/status` | Get bot status and positions | Mode, symbol, price, open positions |
| `/positions` | List all open positions | Entry price, size, TP for each position |
| `/pnl` | Get current profit/loss | Realized + Unrealized P&L |
| `/guardian` | Get Guardian risk status | Current signal (GO/STOP) and reason |

#### Control Commands ⚠️
| Command | Description | Safety |
|---------|-------------|--------|
| `/startbot` | Start the grid bot | Safe - checks if already running |
| `/stopbot` | Stop bot gracefully (30s timeout) | Safe - graceful SIGTERM |
| `/killbot` | Emergency kill bot (immediate) | ⚠️ Forceful - use only if stuck |
| `/restart` | Restart the bot | Safe - graceful stop + start |

### Example Usage

**Check Bot Status:**
```
You: /status

Bot:
🤖 Grid Bot Status

Mode: LONG
Symbol: BTCUSD
Current Price: $95,234.50

Positions:
• Open: 5
• Total Size: 25 contracts

Pending BUY: $92,500

🕐 Updated: 22:57:45
```

**Start Bot:**
```
You: /startbot

Bot:
✅ Grid Bot Started Successfully

🔢 PID: 12345
📊 Check /status to verify

🕐 Started: 22:58:10
```

**Stop Bot:**
```
You: /stopbot

Bot:
✅ Bot Stopped Successfully

🔢 PID: 12345
⏱️ Shutdown time: 5s

🕐 Stopped: 23:01:45

Use /startbot to restart
```

**List Positions:**
```
You: /positions

Bot:
📊 Open Positions (3)

Position 1:
• Entry: $102,500
• Size: 40
• TP: $103,000

Position 2:
• Entry: $103,000
• Size: 40
• TP: $103,500

Position 3:
• Entry: $103,500
• Size: 40
• TP: $104,000

🕐 Updated: 14:23:50
```

**Check Guardian:**
```
You: /guardian

Bot:
🟢 Guardian Status

Signal: GO
Reason: Market conditions normal
Last Update: 14:20:15

✅ Trading is active
```

---

## 📈 Options Bot Commands

### Available Commands

| Command | Description | Example Output |
|---------|-------------|----------------|
| `/start` | Welcome message | Shows available commands |
| `/help` | Display all available commands | Command list with descriptions |
| `/status` | Get portfolio summary | Total positions, P&L, breakdown by underlying |
| `/positions` | List all options positions | Symbol, size, entry, mark, P&L for each |
| `/pnl` | Get detailed P&L breakdown | P&L by underlying, profitable vs losing |
| `/expiry` | Check expiry warnings | Positions expiring within 48 hours |

### Example Usage

**Portfolio Status:**
```
You: /status

Bot:
📈 Options Portfolio Status

Total Positions: 8
Unrealized P&L: +$1,245.50

By Underlying:
• BTC: 5 positions
• ETH: 3 positions

🕐 Updated: 14:25:30

Use /positions for detailed list
```

**List Positions:**
```
You: /positions

Bot:
📊 Options Positions (8)

1. 26 JAN C
• Size: +10
• Entry: $4.25
• Mark: $5.80
• P&L: +$155.00 (+36.5%)

2. 26 JAN P
• Size: -5
• Entry: $3.10
• Mark: $2.45
• P&L: +$32.50 (+21.0%)

3. 02 FEB C
• Size: +15
• Entry: $6.50
• Mark: $7.20
• P&L: +$105.00 (+10.8%)

🕐 Updated: 14:25:35
```

**P&L Summary:**
```
You: /pnl

Bot:
💰 Profit & Loss

Realized P&L: $+245.75
Unrealized P&L: $+68.50
Total P&L: $+314.25

Positions:
• Opened: 10
• Closed: 5

🕐 Updated: 22:59:30
```

**Expiry Warnings:**
```
You: /expiry

Bot:
⚠️ Expiry Warnings (2)

🔴 BTCUSD-26JAN25-110000-C
• Expires in: 4h
• Size: +10
• P&L: +$125.50

⚠️ BTCUSD-26JAN25-105000-P
• Expires in: 18h
• Size: -5
• P&L: -$45.00

🕐 Updated: 14:26:10
```

---

## 🚀 Setup Instructions

### 1. Start Command Handlers

**For Grid Bot:**
```bash
cd /Users/ssr/Projects/WorkingBot
python3 bot/telegram_bot_commands.py --bot grid
```

**For Options Bot:**
```bash
cd /Users/ssr/Projects/WorkingBot
python3 bot/telegram_bot_commands.py --bot options
```

### 2. Run in Background (Optional)

**Using nohup:**
```bash
# Grid bot
nohup python3 bot/telegram_bot_commands.py --bot grid > logs/grid_commands.log 2>&1 &

# Options bot
nohup python3 bot/telegram_bot_commands.py --bot options > logs/options_commands.log 2>&1 &
```

**Using screen:**
```bash
# Grid bot
screen -dmS grid_commands python3 bot/telegram_bot_commands.py --bot grid

# Options bot
screen -dmS options_commands python3 bot/telegram_bot_commands.py --bot options
```

### 3. Test Commands

1. Open Telegram
2. Send `/start` to your bot
3. Send `/help` to see available commands
4. Try `/status` to test

---

## 📊 Data Sources

### Grid Bot Data
- **Status:** `data/system_state.json` (created by gridbot)
- **Guardian:** `data/guardian_signal.json` (created by Guardian)
- **P&L:** Calculated from system_state.json

### Options Bot Data
- **All Data:** WebUI API at `http://localhost:5555/api/options/positions`
- **Requires:** WebUI backend running on port 5555

---

## ⚙️ Configuration

Commands use your existing configuration from `config.yaml`:

```yaml
telegram:
  live_bot_token: "8577856008:AAH4C52AeHRvcWjrRt3ztWt6RZS5MAkinxU"
  options_bot_token: "8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0"
  options_chat_id: "8170794676"
  chat_id: "8170794676"
```

No additional configuration needed.

---

## 🔧 Troubleshooting

### Commands

**"Bot state file not found"**  
**Problem:** Grid bot not running  
**Solution:** Start your grid bot:
```bash
# Via Telegram
/startbot

# Or manually
python3 bot_launcher.py --daemon
```

**"WebUI is offline"**  
**Problem:** Options commands need WebUI backend  
**Solution:** Start WebUI backend:
```bash
cd webui/backend
python3 app.py
```

**"Bot did not stop gracefully"**  
**Problem:** Bot stuck during shutdown  
**Solution:** Use emergency kill:
```
/killbot
```

---

## 🎯 Best Practices

1. **Keep Handlers Running:** Use systemd, supervisor, or screen to keep command handlers running
2. **Monitor Logs:** Check logs regularly for errors
3. **Test Regularly:** Send `/status` periodically to ensure everything works
4. **Response Time:** Commands usually respond in 1-2 seconds
5. **Rate Limits:** Don't spam commands (Telegram has rate limits)

---

## 🔐 Security Notes

- Bot tokens are sensitive - don't share them
- Commands only work from your configured chat_id
- All data is fetched from local system (no external APIs)
- Commands are read-only (can't execute trades)

---

## 📝 Adding New Commands

To add a new command:

1. **Add handler method:**
```python
def _cmd_new_feature(self) -> str:
    """Your new command"""
    # Fetch data
    # Format response
    return "Your response"
```

2. **Register in command router:**
```python
elif command == "/newfeature":
    return self._cmd_new_feature()
```

3. **Update help message:**
```python
"/newfeature - Description of new feature\n"
```

4. **Test it:**
```bash
# Restart handler
# Send /newfeature in Telegram
```

---

## 📞 Support

If commands aren't working:

1. Check handler logs
2. Verify WebUI is running (for options bot)
3. Verify bot is running (for grid bot)
4. Check config.yaml has correct tokens
5. Send `/help` to see if bot responds

---

## 🎉 Quick Start Checklist

- [ ] Grid bot is running
- [ ] WebUI backend is running (for options commands)
- [ ] Start grid command handler: `python3 bot/telegram_bot_commands.py --bot grid`
- [ ] Start options command handler: `python3 bot/telegram_bot_commands.py --bot options`
- [ ] Send `/start` to both bots in Telegram
- [ ] Test with `/status` command
- [ ] Set up background processes with nohup or screen

**You're all set! Use commands anytime to monitor your trading.**
