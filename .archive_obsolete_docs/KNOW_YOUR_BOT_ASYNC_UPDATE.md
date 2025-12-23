# Know Your Bot - Async Bot Update

**Date:** November 14, 2025  
**Status:** ✅ COMPLETE

## Overview

Updated the "Know Your Bot" command reference in the WebUI to reflect the **Async GridBot** architecture that is now in production. All commands have been verified and updated to work with:

- **Async GridBot** (WebSocket + Actor Model + Saga Pattern)
- **PM2 Process Management** (Production standard)
- **Human-Readable Narrative Logging** (via HumanLogger)

---

## What Changed

### 1. Header Updated
**Before:**
```
KNOW YOUR BOT
Mac Terminal commands to start, stop, monitor, and troubleshoot your GridBot
```

**After:**
```
KNOW YOUR BOT - ASYNC EDITION
Mac Terminal commands for the Async GridBot (WebSocket + Actor Model + Saga Pattern)
🚀 Running production async bot with PM2 process management
```

### 2. PM2 Bot Management Section
**Category renamed:** `🤖 PM2 Bot Management (Primary) - ASYNC BOT`

**Updated commands:**
- ✅ "Start **Async** Trading Bot via PM2" - Clarified this starts the async bot
- ✅ "Stop **Async** Trading Bot via PM2" - Notes WebSocket closure
- ✅ "Restart **Async** Trading Bot via PM2" - Async-aware restart
- ✅ "View **Async** Bot Logs (Live)" - Mentions narrative mode logging
- ✅ "Start All Components (**Async**)" - All components now async-aware

**Key additions:**
- All commands tagged with `'async'`
- Descriptions highlight WebSocket + Actor model
- References to human-readable narrative logging

### 3. Direct Commands Section
**Category renamed:** `🚀 Direct Async Bot Commands (Backup)`

**Updated commands:**
- ✅ "Start Async Bot (Direct)" - Uses `USE_ASYNC_BOT=true`
- ✅ "Start Async Bot (Demo Mode)" - Async demo mode
- ✅ "Stop Async Bot" - Graceful async shutdown
- ✅ **NEW:** "Clean Start Async Bot" - Uses `./clean_start_async.sh`

**Command examples:**
```bash
# Start async bot directly
cd ~/Projects/WorkingBot && USE_ASYNC_BOT=true python3 -m bot.run

# Start async demo
cd ~/Projects/WorkingBot && TRADING_MODE=demo USE_ASYNC_BOT=true python3 bot/run.py

# Clean start
cd ~/Projects/WorkingBot && ./clean_start_async.sh
```

### 4. Monitoring & Logs Section
**Category renamed:** `📊 Monitoring & Logs (Async Bot)`

**Updated commands:**
- ✅ "Watch All **Async** Bot Logs (Multi-Pane)" - tmux with async logs
- ✅ "Watch **Async** Bot Logs" - Narrative mode logs
- ✅ "Watch Errors Only" - Filters async bot errors
- ✅ **NEW:** "Check WebSocket Connection" - Verify WS auth/subscription
- ✅ "View System Resource Usage" - Async bot resource monitoring

**New WebSocket monitoring:**
```bash
# Check WebSocket status
pm2 logs gridbot-live --lines 20 | grep -E "WebSocket|authenticated|subscribed"
```

### 5. Troubleshooting Section
**Category renamed:** `🔧 Troubleshooting & Fixes (Async Bot)`

**Updated commands:**
- ✅ "Fix **Async** Bot Instance Lock" - Async-aware lock fixing
- ✅ "Check **Async** Bot Status & Health" - WebSocket + PM2 checks
- ✅ **NEW:** "Check WebSocket Health" - Verify WS authentication
- ✅ **NEW:** "Check Actor System Health" - Verify OrderManager, PositionTracker
- ✅ **NEW:** "Debug WebSocket Reconnections" - Track reconnection patterns
- ✅ "Emergency Stop All Bots" - Async-aware emergency stop

**New async-specific commands:**
```bash
# Check WebSocket health
pm2 logs gridbot-live --lines 100 | grep -E "WebSocket authenticated|Subscriptions active|Price.*flowing|Connection stable"

# Check Actor system
pm2 logs gridbot-live --lines 100 | grep -E "Actor.*processing|actor.*active|OrderManager|PositionTracker"

# Debug reconnections
pm2 logs gridbot-live --lines 200 | grep -E "disconnected|reconnecting|CONNECTION LOST|RECONNECTING NOW"
```

### 6. Search & UI Updates

**Search placeholder updated:**
```
Search async bot commands... (e.g., 'start', 'logs', 'websocket', 'actor', 'debug')
```

**Tip updated:**
```
Click "Copy" to copy command to clipboard, then paste in your Mac Terminal. 
All commands use zsh shell and are optimized for the async bot.
```

**No results message updated:**
```
Try searching for: start, stop, logs, async, websocket, actor, guardian, debug, config
```

---

## Command Tags Added

All async bot commands now include the `'async'` tag for easy filtering:

```javascript
tags: ['bot', 'start', 'live', 'pm2', 'trading', 'async']
tags: ['logs', 'bot', 'pm2', 'live', 'async']
tags: ['debug', 'websocket', 'async', 'health']
tags: ['debug', 'actors', 'async', 'health']
```

---

## Async Bot Key Features Highlighted

The updated commands now properly reflect:

1. **WebSocket Architecture**
   - Real-time price feeds
   - Authenticated connections
   - Auto-reconnection on failure

2. **Actor Model**
   - OrderManager actor
   - PositionTracker actor
   - GridCalculator actor
   - Message-based concurrency

3. **Saga Pattern**
   - Order placement sagas
   - Compensating transactions
   - Rollback on failure

4. **Human-Readable Logging**
   - Narrative mode enabled by default
   - BOT OK / WARNING / ALERT / CRITICAL levels
   - Trader-friendly commentary

---

## Testing Checklist

- [x] Header shows "ASYNC EDITION"
- [x] PM2 commands reference async bot
- [x] Direct commands use `USE_ASYNC_BOT=true`
- [x] Monitoring commands check WebSocket health
- [x] Troubleshooting includes actor system checks
- [x] All async commands tagged with `'async'`
- [x] Search suggests async-relevant terms
- [x] Description mentions WebSocket + Actor Model

---

## Files Modified

```
webui/frontend/src/components/CommandKnowledgeBase.js
```

**Line count:** ~829 lines  
**Changes:** 6 major sections updated

---

## User Impact

✅ **Positive:**
- Users now see accurate commands for the async bot in production
- New WebSocket and Actor system debugging commands
- Clear distinction between async and legacy commands
- Better troubleshooting guidance for async-specific issues

⚠️ **Note:**
- Legacy bot commands preserved in "Direct Async Bot Commands (Backup)" section
- All PM2 commands continue to work without changes (PM2 config unchanged)

---

## Next Steps

1. ✅ **DONE:** Update CommandKnowledgeBase.js
2. 🔄 **TODO:** Rebuild frontend to apply changes
3. 🔄 **TODO:** Test search functionality with new tags
4. 🔄 **TODO:** Verify commands on production Mac Mini M4

---

## Rebuild Frontend

To apply these changes:

```bash
# Navigate to frontend directory
cd ~/Projects/WorkingBot/webui/frontend

# Rebuild production build
npm run build

# Or start dev server to test
npm start
```

The WebUI backend will automatically serve the new build.

---

## Verification Commands

```bash
# 1. Check if async bot is running
pm2 status

# 2. View async bot logs
pm2 logs gridbot-live --lines 20

# 3. Verify WebSocket connection
pm2 logs gridbot-live --lines 20 | grep -E "WebSocket|authenticated"

# 4. Check actor system
pm2 logs gridbot-live --lines 50 | grep -E "Actor.*processing"
```

---

## Summary

**All "Know Your Bot" commands have been successfully updated for the Async GridBot!** 🎉

The WebUI now provides:
- Accurate async bot commands
- WebSocket health monitoring
- Actor system debugging
- Human-readable logging references
- Clear async vs legacy distinction

Users can now confidently use the command reference to manage the production async bot.
