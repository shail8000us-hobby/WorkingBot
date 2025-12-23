# Safe Tmux Shutdown - How to Stop Bot Properly

## ❌ PROBLEM: Order Not Cancelled

When you stop tmux incorrectly, the bot gets **SIGKILL (signal 9)** which **cannot be caught**, so cleanup never runs and orders stay on the exchange.

---

## ✅ SAFE METHODS (Orders Get Cancelled)

### Method 1: Use tmux_stop_bot.sh (BEST FOR TMUX)
```bash
# Graceful shutdown with proper timeout handling
./tmux_stop_bot.sh gridbot

# This automatically:
# 1. Sends Ctrl+C (SIGINT) to bot
# 2. Waits up to 30 seconds for cleanup
# 3. Verifies cleanup in log
# 4. Only force-kills if bot hangs
# 5. Cleans up tmux session
```

### Method 2: Stop Bot from Inside Tmux
```bash
# 1. Attach to tmux session
tmux attach -t gridbot

# 2. Press Ctrl+C in the window running the bot
# This sends SIGINT → cleanup runs → orders cancelled

# 3. Wait for "GRACEFUL SHUTDOWN" message in log

# 4. Detach from tmux (optional)
# Press: Ctrl+B then D
```

### Method 3: Use bot_stopper.py (RECOMMENDED)
```bash
# Graceful shutdown (default, waits 30s)
python3 bot_stopper.py

# This automatically:
# 1. Finds bot PID
# 2. Sends SIGINT
# 3. Waits up to 30 seconds
# 4. Only force-kills if bot hangs
```

### Method 4: Send Signal to Bot Process
```bash
# Get bot PID
cat reports/bot.pid

# Send graceful shutdown signal
kill -SIGTERM <PID>
# OR
kill -SIGINT <PID>

# Both trigger cleanup and cancel orders
```

---

## ❌ UNSAFE METHODS (Orders NOT Cancelled)

### Don't Use: tmux kill-server
```bash
❌ tmux kill-server
```
**Why it fails:**
- Sends SIGKILL to ALL processes in ALL sessions
- Cannot be caught by signal handlers
- Cleanup never runs
- Orders stay on exchange

### Don't Use: kill -9
```bash
❌ kill -9 <PID>
❌ pkill -9 -f bot
```
**Why it fails:**
- SIGKILL (signal 9) cannot be caught
- Process dies immediately
- No cleanup, no order cancellation

### Don't Use: Closing Terminal Window
```bash
❌ Close terminal/iTerm window with tmux session inside
```
**Why it fails:**
- Terminal sends SIGHUP to tmux
- Tmux may send SIGKILL to processes
- Unreliable cleanup

---

## 🔍 How to Verify Cleanup Ran

### Check Bot Log
```bash
tail -50 reports/bot.log | grep -E "GRACEFUL SHUTDOWN|cleanup|Cancelling"
```

**Should see:**
```
2025-11-02 17:30:15 [INFO] ========================================
2025-11-02 17:30:15 [INFO] 🧹 GRACEFUL SHUTDOWN
2025-11-02 17:30:15 [INFO] ========================================
2025-11-02 17:30:15 [INFO] 🎯 Found pending BUY @ $115,500 (ID: abc123)
2025-11-02 17:30:15 [INFO] 🔄 Using bulk cancel API (Delta recommendation)...
2025-11-02 17:30:17 [INFO] ✅ Bulk cancellation successful
2025-11-02 17:30:17 [INFO] ✅ Final verification passed - zero bot orders remain
2025-11-02 17:30:17 [INFO] 📱 Telegram: Bot stopped notification sent
```

**Bad (SIGKILL):**
```
2025-11-02 17:28:18 [INFO] [HB] BTC/USD:USD: 115599.5 | pending: 115500.0
<log ends abruptly - NO cleanup messages>
```

### Check Exchange Manually
```bash
# Run this after stopping bot
python3 -c "
from bot.exchange.delta_client import DeltaClient
client = DeltaClient()
orders = client.list_orders(product_id=139, state='open')
print('Open orders:', len(orders.get('result', [])))
for o in orders.get('result', []):
    print(f\"  - {o.get('side')} @ {o.get('limit_price')} (ID: {o.get('id')})\")
"
```

Should return: `Open orders: 0`

---

## 📊 Signal Comparison

| Method | Signal | Catchable? | Cleanup Runs? | Orders Cancelled? |
|--------|--------|-----------|---------------|-------------------|
| Ctrl+C in tmux | SIGINT (2) | ✅ YES | ✅ YES | ✅ YES |
| kill -SIGTERM | SIGTERM (15) | ✅ YES | ✅ YES | ✅ YES |
| kill -SIGINT | SIGINT (2) | ✅ YES | ✅ YES | ✅ YES |
| tmux kill-session | SIGTERM (15) | ✅ YES | ✅ YES | ✅ YES |
| bot_stopper.py | SIGINT (2) | ✅ YES | ✅ YES | ✅ YES |
| **kill -9** | **SIGKILL (9)** | **❌ NO** | **❌ NO** | **❌ NO** |
| **tmux kill-server** | **SIGKILL (9)** | **❌ NO** | **❌ NO** | **❌ NO** |

---

## 🛠️ What to Do If Orders Are Orphaned

If you already stopped with SIGKILL and orders are still on exchange:

### Quick Fix
```bash
# Run the manual order canceller
python3 cancel_pending_orders.py
```

### Or Use WebUI
1. Open WebUI: http://localhost:5555
2. Go to Emergency Controls
3. Click "Cancel All Orders"

### Or Use Delta Web App
1. Go to https://www.delta.exchange
2. Login
3. Navigate to Orders
4. Manually cancel the order

---

## 🎯 Best Practice Recommendation

**Always use one of these 3 methods:**

1. **From outside tmux: `./tmux_stop_bot.sh`** ← Best for tmux sessions
2. **Inside tmux: Ctrl+C** ← Simplest
3. **Command line: `python3 bot_stopper.py`** ← Most reliable
4. **WebUI: Stop Bot button** ← User-friendly

**Never use:**
- `kill -9`
- `tmux kill-server`
- `pkill -9`

---

## 🔧 Troubleshooting

### Q: I stopped bot but order is still there
**A:** You probably used `kill -9` or `tmux kill-server`. Check bot log:
```bash
tail -50 reports/bot.log
```
If no "GRACEFUL SHUTDOWN" message, cleanup didn't run.

**Solution:**
```bash
# Cancel manually
python3 cancel_pending_orders.py
```

### Q: How do I know which tmux session has the bot?
```bash
# List all sessions
tmux list-sessions

# Typical output:
# gridbot: 1 windows (created Sat Nov  2 17:15:00 2025)
# demo: 1 windows (created Sat Nov  2 16:00:00 2025)

# Attach to correct session
tmux attach -t gridbot
```

### Q: Can I make tmux safer?
**A:** Yes! We've created `~/.tmux.conf` with graceful shutdown settings:
```bash
# Config is already created, just reload any existing sessions:
tmux source-file ~/.tmux.conf

# Or if in a tmux session, press: Ctrl+B then type:
# :source-file ~/.tmux.conf
```

The config ensures:
- Mouse support enabled (scroll in tmux)
- Graceful shutdown on kill-pane
- Better visual feedback
- Larger scrollback buffer (50k lines)

---

## 📝 Summary

- ✅ **SAFE**: Ctrl+C, bot_stopper.py, WebUI, kill -SIGTERM
- ❌ **UNSAFE**: kill -9, tmux kill-server, pkill -9
- 🔍 **Always verify**: Check bot.log for "GRACEFUL SHUTDOWN"
- 🆘 **If failed**: Run `cancel_pending_orders.py`

**The golden rule:** If you see "GRACEFUL SHUTDOWN" in bot.log, your orders were cancelled. If not, they're still on exchange.
