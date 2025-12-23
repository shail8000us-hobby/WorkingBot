# Bot Investigation Report - November 9, 2025

## Summary
User reported: "Bot failed to place TP orders and next BUY orders. WebSocket giving trouble."

## Investigation Findings

### ✅ ISSUE 1: TP Order Placement - **NO BOT ISSUE FOUND**
**Status**: False alarm - User confused manual positions with bot positions

**Facts**:
- Bot started fresh: Nov 8, 2025 @ 19:24 IST
- Bot placed 10 BUY orders since startup:
  - 1027796346 @ 20:05
  - 1027832680 @ 20:33
  - 1027837137 @ 20:37
  - 1027838680 @ 20:38
  - 1027843836 @ 20:43
  - 1027881220 @ 21:07
  - 1027970581 @ 22:15 (cancelled during shutdown @ 23:15)
  - 1028041685 @ 23:18
  - 1028042811 @ 23:19
  - 1028045548 @ 23:22 (CURRENT PENDING)

**None of these orders filled**, therefore NO TP orders needed to be placed.

**The 14 existing positions** @ $101,128 average are from manual trades (Nov 3-7), NOT bot trades.
- Last bot fill: Nov 7 @ 16:45 (BUY @ $100,000) → TP was placed correctly (ID: 1025709821 @ $101,000)

**Conclusion**: Bot TP placement logic is working. No bug.

---

### 🚨 ISSUE 2: WebSocket Frequent Disconnections - **CONFIRMED BUG**
**Status**: Real issue - WebSocket dies every 30-60 minutes

**Evidence**:
Connection deaths overnight (Nov 9):
```
01:52:32 - No data for 42s → Force reconnect
01:59:48 - No data for 57s → Force reconnect  
03:46:37 - No data for 51s → Force reconnect
04:17:59 - No data for 56s → Force reconnect
05:37:53 - No data for 57s → Force reconnect
06:01:33 - No data for 54s → Force reconnect
06:22:10 - No data for 51s → Force reconnect
```

**Pattern**: Every ~20-60 minutes, WebSocket stops receiving data for 50-57 seconds.

**Current Behavior**:
1. Heartbeat monitor detects starvation @ 50s threshold
2. Forces reconnection
3. REST fallback activates (30s threshold)
4. WebSocket recovers in 0.5-2 seconds
5. REST fallback deactivates
6. Cycle repeats 30-60 min later

**Impact**:
- REST fallback working as designed (activates/deactivates quickly)
- No missed fills (REST fallback catches them)
- BUT: Unnecessary reconnections causing log spam
- Potential risk: If WebSocket dies during fill, 0.5-2s delay for fill detection

**Root Cause Analysis**:
Current settings (delta_ws.py:45-50):
```python
'ping_interval': 20,                # Application ping every 20s
'dead_connection_threshold': 50,    # Declare dead after 50s no data
'quiet_ping_at': 35,                # Warn at 35s
```

**Hypothesis**: Delta Exchange WebSocket server may have:
- Server-side timeout at ~60s
- Idle connection cleanup
- Network path issue causing drops

**Why it happens**:
- Bot sends pings every 20s (application level)
- But pings don't count as "data" for last_message_time
- If no market activity (no price updates), counter keeps climbing
- Hits 50s threshold → forced reconnect
- Server probably would have sent data soon after, but too late

---

### 📊 NEXT BUY Orders - **WORKING CORRECTLY**
**Status**: No issue

**Current State**:
- 1 pending BUY: 1028045548 @ $101,500
- Runtime state shows: `pending_buy` correctly tracked
- Bot logic: Won't place another BUY until current one fills/cancels
- This is correct behavior (strict grid mode)

---

## Recommended Fixes

### For WebSocket Stability:
1. **Update ping to also update last_message_time** (treat pings as activity)
2. **Increase dead_connection_threshold to 90s** (give more grace time)
3. **Add WebSocket frame-level ping/pong** (not just application ping)
4. **Log WebSocket pong responses** to verify server is responding

### For Monitoring:
1. Add metric: "Forced reconnections in last 24h"
2. Alert if >5 reconnections/hour (indicates real problem)
3. Track actual vs expected uptime %

---

## Files Checked:
- bot/strategy/gridbot.py (TP placement logic)
- bot/delta_websocket/delta_ws.py (WebSocket client)
- bot/delta_websocket/ws_manager.py (WebSocket manager)
- runtime_state.json (bot state)
- reports/pm2-gridbot-live-error.log (bot logs)

## Investigation Tools Created:
- check_current_status.py - Exchange status checker
- test_delta_rest_api.py - REST API verification (existing)
- test_ws_connection.py - WebSocket connection test (existing)
