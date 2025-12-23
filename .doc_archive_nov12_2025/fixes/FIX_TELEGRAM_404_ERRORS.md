# Fixing Telegram Bot 404 Errors

**Problem:** Guardian bot logs showing:
```
Warning: Failed to send Telegram alert: 404 Client Error: Not Found for url: https://api.telegram.org/bot***REDACTED***/sendMessage
```

**Cause:** The Telegram bot token is invalid or the bot was deleted from BotFather.

---

## 🔧 Quick Fix

### Option 1: Disable Telegram Notifications (Fastest)

If you don't need Telegram alerts right now:

```bash
# Edit grid_config.env
nano grid_config.env

# Find and set:
ENABLE_TELEGRAM=false

# Save and restart guardian
./pm2_gridbot.sh restart guardian-live
```

### Option 2: Get New Telegram Bot Token

1. **Create new bot with BotFather:**
   - Open Telegram app
   - Search for `@BotFather`
   - Send `/newbot`
   - Follow prompts to create bot
   - Copy the token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get your Chat ID:**
   - Send a message to your new bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}` in the response
   - Copy the chat ID number

3. **Update config:**
   ```bash
   nano grid_config.env
   
   # Update these lines:
   TELEGRAM_BOT_TOKEN=YOUR_NEW_TOKEN_HERE
   TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE
   
   # For live mode:
   LIVE_TELEGRAM_BOT_TOKEN=YOUR_NEW_TOKEN_HERE
   LIVE_TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE
   ```

4. **Restart guardian:**
   ```bash
   ./pm2_gridbot.sh restart guardian-live
   ```

---

## 🔍 Verify It's Working

```bash
# Watch guardian logs
pm2 logs guardian-live

# Should see successful messages, not 404 errors
# If still seeing 404, token is still invalid
```

---

## 📊 Current Status

**Guardian Errors:**
- Last error: 2025-11-09 17:30:24
- All errors are Telegram 404
- Bot is still running (just can't send notifications)

**Impact:**
- ✅ Bot continues trading normally
- ✅ All safety systems working
- ❌ No Telegram notifications
- ✅ Logs still working

**Priority:** Low (bot works fine, just no Telegram alerts)

---

## 🚨 Why This Happened

Common reasons:
1. Bot token was deleted in BotFather
2. Token was revoked/regenerated
3. Bot was banned by Telegram (unlikely)
4. Token expired (very rare)

---

## 💡 Recommendation

**For now:** Disable Telegram to stop the warning spam in logs

```bash
# Quick disable
sed -i '' 's/ENABLE_TELEGRAM=true/ENABLE_TELEGRAM=false/' grid_config.env
./pm2_gridbot.sh restart guardian-live

# Verify no more errors
pm2 logs guardian-live --lines 20
```

**Later:** When you have time, create a new bot and update tokens.

---

## 📝 Files to Update

1. `grid_config.env` - Main config (lines 435-449)
2. `webui/backend/grid_config.env` - WebUI config (same lines)

Make sure to update both if using WebUI!

---

**Last Updated:** November 9, 2025  
**Status:** Non-critical - Bot operational, Telegram alerts not working
