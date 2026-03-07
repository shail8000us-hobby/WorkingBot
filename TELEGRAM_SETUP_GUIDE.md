# Telegram Notifications Setup Guide

This guide explains how to configure and test Telegram notifications for your trading system.

---

## 📱 Two Separate Bots

Your system uses **two different Telegram bots**:

### Bot 1: Grid Bot & Guardian (Futures Trading)
- **Token:** `8577856008:AAH4C52AeHRvcWjrRt3ztWt6RZS5MAkinxU`
- **Username:** `@BTCSSR_bot`
- **Sends:** Grid trading alerts, Guardian risk signals, P&L updates

### Bot 2: Options Trading
- **Token:** `8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0`
- **Sends:** Options position alerts, expiry warnings, P&L updates

---

## 🔧 Configuration

### Step 1: Update config.yaml

The tokens are already configured in [config.yaml](config.yaml):

```yaml
telegram:
  # Grid Bot & Guardian (Futures)
  live_bot_token: '8577856008:AAH4C52AeHRvcWjrRt3ztWt6RZS5MAkinxU'
  live_chat_id: '8170794676'
  
  # Options Trading Bot
  options_bot_token: '8509485131:AAFyCFj9mZZWcHO_qEzSq8aqWy9jGkMWHK0'
  options_chat_id: '8170794676'
  
  enabled: true
```

### Step 2: Start the Bots

Start both bots in Telegram by sending `/start` to:
1. `@BTCSSR_bot` (for futures/grid trading)
2. Your options bot (find username from @BotFather)

---

## 🧪 Testing

### Test Grid Bot Notifications

```bash
# Test grid bot/guardian notifications
python test_telegram_alerts.py
```

This will test:
- ✅ Connection
- ✅ WebSocket disconnect alerts
- ✅ Loss limit warnings
- ✅ Startup/shutdown notifications

### Test Options Bot Notifications

```bash
# Test options trading notifications
python test_options_telegram.py
```

This will send:
- ✅ Position opened
- ✅ Position closed
- ✅ Take profit hit
- ✅ Expiry warnings
- ✅ Liquidity warnings

---

## 📋 What Messages to Expect

See [TELEGRAM_BOT_NOTIFICATIONS_SPEC.md](TELEGRAM_BOT_NOTIFICATIONS_SPEC.md) for complete list of all notification types.

### Grid Bot Messages (Bot 1)

**Lifecycle:**
- 🚀 Bot Started
- 🛑 Bot Stopped

**Trading:**
- 📥 BUY Order Filled
- 💰 Take Profit Hit
- 📤 SELL Order Filled

**Risk Management:**
- 🔴 Guardian STOP Signal
- 🟢 Guardian GO Signal
- 📊 Loss Limit Warnings (80%, 90%, 100%)
- ⚠️ WebSocket Disconnect

**Daily:**
- 📊 Daily Trading Report

### Options Bot Messages (Bot 2)

**Position Management:**
- 📥 Position Opened
- ➕ Position Added
- 💰 Position Closed

**Profit & Loss:**
- 🎯 Take Profit Hit
- 🛑 Stop Loss Triggered
- 🚨 Max Loss Breach

**Expiry:**
- ⚠️ 24h Warning
- 🔴 1h Critical Alert
- 🕐 Auto-Close Protection

**Risk:**
- ⚠️ Liquidity Warning
- 🔴 Guardian Block

---

## 🔐 Security Notes

### Keep Tokens Private
- ✅ Tokens are already in `config.yaml` (gitignored)
- ❌ Never commit tokens to public repos
- ❌ Never share tokens in screenshots

### Chat ID Security
- Your chat ID: `8170794676`
- Only you will receive these messages
- To add team members, get their chat IDs from @userinfobot

---

## 🐛 Troubleshooting

### No messages arriving?

1. **Check bot is started in Telegram**
   ```bash
   # Send /start to both bots
   @BTCSSR_bot
   @YourOptionsBot
   ```

2. **Verify configuration**
   ```bash
   python test_options_telegram.py
   ```

3. **Check logs**
   ```bash
   tail -f logs/pm2-gridbot-live.log | grep telegram
   tail -f webui/backend/logs/app.log | grep options
   ```

### Messages duplicated?

This is normal if you have multiple bot instances running. Check:
```bash
ps aux | grep python | grep bot
pm2 list
```

### Wrong bot receiving messages?

Verify in `config.yaml`:
- Grid bot uses `live_bot_token`
- Options bot uses `options_bot_token`

---

## 📁 Implementation Files

### Core Files Created/Modified:

1. **[bot/options/notifications/options_notifier.py](bot/options/notifications/options_notifier.py)**
   - Options Telegram notifier class
   - All notification methods

2. **[config.yaml](config.yaml)**
   - Added `options_bot_token` and `options_chat_id`

3. **[webui/backend/routes/options/options_control.py](webui/backend/routes/options/options_control.py)**
   - Integrated notifications on position open/close/add

4. **[webui/backend/options_strategy/max_loss_manager.py](webui/backend/options_strategy/max_loss_manager.py)**
   - Added max loss breach notifications

5. **[test_options_telegram.py](test_options_telegram.py)**
   - Test script for options notifications

6. **[TELEGRAM_BOT_NOTIFICATIONS_SPEC.md](TELEGRAM_BOT_NOTIFICATIONS_SPEC.md)**
   - Complete specification of all message types

### Existing Grid Bot Notifications:

Already implemented in:
- `bot/utils/notifier.py` - Grid bot notifier
- `bot/strategy/async_gridbot.py` - Startup/shutdown
- `bot/guardian/core/guardian_bot.py` - Risk alerts
- `bot/strategy/modules/fill_detector.py` - Fill alerts

---

## 🚀 Next Steps

1. **Test both bots:**
   ```bash
   python test_telegram_alerts.py     # Grid bot
   python test_options_telegram.py    # Options bot
   ```

2. **Start trading:**
   ```bash
   # Grid bot will automatically send notifications
   pm2 start gridbot-live
   
   # Options notifications will trigger when you trade via WebUI
   ```

3. **Monitor notifications:**
   - Check Telegram for real-time alerts
   - Review [TELEGRAM_BOT_NOTIFICATIONS_SPEC.md](TELEGRAM_BOT_NOTIFICATIONS_SPEC.md) for message types

---

## 💡 Tips

- **Mute non-critical notifications** at night by configuring Telegram notification settings
- **Pin important alerts** (like max loss breaches) in Telegram
- **Set up chat folders** to separate grid bot vs options bot messages
- **Use Telegram Desktop** for better message management

---

## 📞 Support

If notifications aren't working:
1. Check bot tokens are correct
2. Verify you've sent /start to both bots  
3. Check `enabled: true` in config.yaml
4. Review logs for error messages
5. Run test scripts to diagnose issues

---

**Last Updated:** January 19, 2026  
**Status:** ✅ Fully Implemented & Tested
