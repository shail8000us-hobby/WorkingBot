# Delta Exchange WebSocket Support Query
**Date:** November 9, 2025  
**Trading Bot:** GridBot v2.0 (Production)  
**Exchange:** Delta Exchange (Testnet & Live)  
**API Version:** v2

**Status:** ✅ **RESOLVED** - Implemented fixes per Delta documentation

---

## Summary

~~We're experiencing periodic WebSocket data starvation on Delta Exchange WebSocket connections. Our automated fallback system works correctly, but we'd like to optimize our implementation to align with Delta's recommended practices.~~

**UPDATE NOV 9:** Issues resolved by implementing Delta's recommended WebSocket practices:
- Enabled server heartbeat (30s interval)
- Adjusted starvation threshold (30s → 35s)
- Handle 'pong' messages silently
- Updated ping interval (20s → 30s)

See `WEBSOCKET_FIX_COMPLETE_NOV9_2025.md` for implementation details.

---

## Current Implementation

### WebSocket Configuration
```python
# Connection Details
Endpoint: wss://socket.delta.exchange
Protocol: WebSocket v13
Authentication: API Key + Secret (HMAC-SHA256)
Subscriptions: 
  - v2/ticker (for price updates)
  - user (for order fills, position updates)
  
# Our Settings
Heartbeat/Ping Interval: 40 seconds
Starvation Detection Threshold: 30 seconds
Reconnect Strategy: Exponential backoff (1s, 2s, 4s, 8s, max 60s)
Connection Timeout: 10 seconds
```

### Message Handling
```python
# Messages We Handle
✅ ticker - Price updates
✅ user - Order fills, position updates
✅ subscriptions - Subscription confirmations
✅ auth - Authentication success
⚠️ pong - Currently logs as "unknown" (see Issue #2)

# Our Flow
1. Connect → Authenticate → Subscribe
2. Receive data continuously
3. Send ping every 40s if no messages received
4. Activate REST fallback if no data for 30s
5. Deactivate fallback when WebSocket recovers
```

---

## Issues Observed

### Issue #1: Periodic WebSocket Data Starvation (Primary Issue)

**Pattern:**
- WebSocket stops receiving data for exactly 30+ seconds
- Happens every ~30-31 seconds consistently
- Occurs during low volatility periods (no active trades)
- Always recovers within 1-2 seconds after REST fallback queries

**Timeline Example (Nov 9, 2025):**
```
13:51:32 - Starvation detected (30.2s since last message)
13:52:04 - Starvation detected (30.0s) 
13:52:35 - Starvation detected (30.2s)
13:53:07 - Starvation detected (30.5s)
13:53:38 - Starvation detected (30.6s)
13:54:10 - Starvation detected (30.9s)
... continues every ~30 seconds
```

**Observed During:**
- ✅ Low market volatility
- ✅ No active positions
- ✅ No pending orders
- ✅ Weekend/off-hours trading
- ✅ Both testnet and live environments

**What Happens:**
1. Last WebSocket message received (ticker or user data)
2. Exactly 30-31 seconds pass with no new messages
3. Our system detects starvation, activates REST fallback
4. REST API query executes successfully
5. WebSocket suddenly receives data again (0.7-2.0s later)
6. REST fallback deactivates

**Current Workaround:**
- ✅ REST API fallback prevents data loss
- ⚠️ Creates noisy logs (16 events in 31 minutes)
- ⚠️ Unnecessary API calls (already rate-limited properly)

---

### Issue #2: Unknown 'pong' Message Type

**What We See:**
```json
{
  "type": "pong"
}
```

**Frequency:** 7 times in 31 minutes (every ~4-5 minutes)

**Context:**
- We send `{"type": "ping"}` when no messages for 40 seconds
- Exchange responds with `{"type": "pong"}`
- Our handler logs it as "Unknown WebSocket message type 'pong'"

**Question:** 
- Should we handle 'pong' messages explicitly?
- Or is this a diagnostic message we should ignore?
- Is there a standard WebSocket protocol message we should use instead?

---

### Issue #3: No Clear Documentation on Message Frequency

**Questions:**
1. **During low volatility**, what is the expected minimum message frequency from Delta WebSocket?
   - Should we expect ticker updates even if price doesn't change?
   - What about user channel when no positions/orders active?

2. **Is there a "keepalive" message** we're missing?
   - Does Delta send periodic heartbeat/keepalive on idle channels?
   - Should we be receiving something even during complete market silence?

3. **What's the recommended starvation threshold?**
   - We use 30 seconds (triggers false alarms)
   - Should it be 45s? 60s? Dynamic based on subscription type?

---

## Questions for Delta Engineering Team

### 1. WebSocket Message Frequency (Critical)

**Q1.1:** During periods of no market activity (low volatility, no trades), how often should clients expect messages on the `v2/ticker` subscription?
- Every second regardless of price change?
- Only on price change?
- Periodic heartbeat every N seconds?

**Q1.2:** On the `user` channel, when a user has:
- ✅ No active positions
- ✅ No pending orders
- ✅ No recent fills

Should clients still expect periodic messages, or is complete silence normal?

**Q1.3:** Does Delta Exchange send any form of "keepalive" or "heartbeat" messages automatically, or is client ping/pong the only mechanism?

---

### 2. Ping/Pong Protocol (Medium Priority)

**Q2.1:** When client sends `{"type": "ping"}`, should we:
- ✅ Expect `{"type": "pong"}` response (and handle it silently)?
- ❌ Expect no response (WebSocket-level ping/pong instead)?
- ❓ Use WebSocket protocol-level ping frames instead of JSON messages?

**Q2.2:** What is the recommended ping interval for Delta WebSocket?
- We currently use 40 seconds
- Should it be higher/lower?
- Does Delta have a connection timeout if no pings received?

**Q2.3:** If we don't send pings, will Delta close the connection after N seconds of client inactivity?

---

### 3. Starvation Detection Threshold (High Priority)

**Q3.1:** What is the recommended "no data received" timeout before considering WebSocket connection stale?
- We use 30 seconds → triggers false alarms
- Should it be 45s, 60s, or dynamic?

**Q3.2:** In production, have you observed any scenarios where WebSocket can be silent for 30+ seconds but still healthy?
- Low volatility markets?
- Weekend/off-hours?
- Specific subscription types?

**Q3.3:** Does Delta recommend a specific reconnection strategy for stale connections?

---

### 4. Best Practices for Hybrid Architecture (Medium Priority)

**Q4.1:** We use WebSocket (primary) + REST API fallback (backup). Is this recommended?
- Current: If no WebSocket data for 30s → poll REST every 5s until WebSocket recovers
- Alternative: Just reconnect WebSocket immediately?

**Q4.2:** Does Delta have rate limits that distinguish between:
- REST calls made during WebSocket downtime (fallback)?
- REST calls made alongside active WebSocket (redundant)?

**Q4.3:** What's the recommended way to verify WebSocket is "truly alive"?
- Send ping and expect pong?
- Check message timestamps?
- Periodic subscription re-confirmation?

---

### 5. Connection Stability (Low Priority)

**Q5.1:** Are there known periods of WebSocket maintenance or degraded performance?
- Specific UTC hours?
- Weekends?
- Testnet vs Production differences?

**Q5.2:** What's the expected WebSocket uptime SLA?
- Should clients expect 99.9% uptime?
- Are periodic disconnections normal?

---

## Our Current Metrics (Last Session)

```
Session Duration: 31 minutes (13:24 - 13:56 UTC)
Total WebSocket Messages Received: ~1,850
Starvation Events: 16
Starvation Frequency: Every ~30 seconds
Avg Starvation Duration: 30.4 seconds
Recovery Time After Fallback: 0.7-2.0 seconds
Unknown 'pong' Messages: 7
WebSocket Disconnections: 0
Authentication Failures: 0
Subscription Failures: 0
```

**Observations:**
- ✅ Connection stable (no disconnects)
- ✅ Authentication working perfectly
- ✅ Data accurate when received
- ⚠️ Periodic 30s gaps in data flow
- ⚠️ 'pong' messages not handled

---

## What We Need

### Immediate Needs:
1. **Clarification on expected message frequency** during low activity
2. **Recommended starvation threshold** (30s, 45s, 60s, dynamic?)
3. **Confirmation on 'pong' message handling** (handle explicitly or ignore?)

### Nice to Have:
4. **Best practices guide** for WebSocket + REST hybrid architecture
5. **Debug/diagnostic endpoint** to check WebSocket health from server side
6. **WebSocket statistics** (server-side view of our connection quality)

---

## Technical Environment

```
Language: Python 3.11
WebSocket Library: websockets 12.0
Framework: asyncio
Connection Pooling: aiohttp 3.9.1
REST Client: requests 2.31.0
Server Location: [Your Server Location]
Network: [Fiber/Cloud/Residential]
Latency to Delta: ~50-100ms avg
```

---

## Expected Outcome

We'd like to optimize our WebSocket implementation to:
1. ✅ Eliminate false starvation alarms
2. ✅ Reduce unnecessary REST fallback activations  
3. ✅ Clean up log noise from 'pong' messages
4. ✅ Align with Delta's recommended architecture
5. ✅ Maintain 100% data accuracy (already achieved)

---

## Proposed Solutions (For Delta Review)

Based on the pattern, we're considering:

### Option A: Increase Starvation Threshold
```python
STARVATION_THRESHOLD = 45.0  # Was 30.0
# Rationale: Exchange naturally has 30s gaps during low volatility
```

### Option B: Dynamic Threshold Based on Market Activity
```python
# Active market: 30s threshold
# Quiet market: 60s threshold  
# Determine "active" by message frequency in last 5 minutes
```

### Option C: Implement Proper Ping/Pong with Shorter Interval
```python
PING_INTERVAL = 20.0  # Was 40.0
STARVATION_THRESHOLD = 45.0  # Give extra buffer
# More frequent pings = more regular 'pong' responses = less starvation
```

### Option D: Trust WebSocket Connection State Only
```python
# Don't use message age as health indicator
# Only check WebSocket.state == OPEN
# Reconnect only on actual connection failures
```

**Which approach does Delta recommend?**

---

## Contact Information

**Bot Owner:** [Your Name/Company]  
**API Key ID:** [Your API Key - last 4 chars]  
**Environment:** Testnet (wss://testnet-socket.delta.exchange) + Live  
**User ID:** [Your Delta User ID]  
**Support Ticket:** [If you have one]  

---

## Appendix: Sample Logs

### Starvation Event Log
```
2025-11-09 13:55:12,996 [WARNING] 🚨 [REST FALLBACK] WebSocket starved for 30.3s > 30.0s threshold
2025-11-09 13:55:12,997 [WARNING] ================================================================================
2025-11-09 13:55:12,997 [WARNING] 🔄 ACTIVATING REST API FALLBACK - WebSocket Starvation Detected
2025-11-09 13:55:12,997 [WARNING]    Last WebSocket update: 30.3s ago
2025-11-09 13:55:12,997 [WARNING]    Polling interval: 5.0s
2025-11-09 13:55:12,997 [WARNING] ================================================================================
2025-11-09 13:55:12,998 [INFO] 🔄 [REST FALLBACK] Polling loop started
2025-11-09 13:55:12,998 [INFO] ✅ [REST FALLBACK] Polling thread started
2025-11-09 13:55:15,111 [INFO] ✅ [REST FALLBACK] WebSocket recovered (age: 0.9s)
2025-11-09 13:55:15,111 [INFO] ================================================================================
2025-11-09 13:55:15,111 [INFO] ✅ DEACTIVATING REST API FALLBACK - WebSocket Recovered
2025-11-09 13:55:15,112 [INFO] ================================================================================
```

### 'pong' Message Log
```
2025-11-09 13:55:43,864 [WARNING] ⚠️  [HEARTBEAT] No messages for 42s, sending ping...
2025-11-09 13:55:44,032 [WARNING] ⚠️ Unknown WebSocket message type 'pong': {
  "type": "pong"
}
```

---

## Summary Question

**TLDR:** Our WebSocket implementation works correctly but experiences periodic 30-second data gaps during low market activity. Should we:
1. Increase our starvation threshold from 30s to 45s+?
2. Handle 'pong' messages explicitly instead of logging as unknown?
3. Change our ping interval from 40s to something else?
4. Trust that 30s gaps are normal during low volatility and suppress warnings?

**Please advise on Delta Exchange's recommended WebSocket architecture for grid trading bots with minimal market activity periods.**

---

**Thank you for your support!** 🙏

---

**Document Version:** 1.0  
**Created:** November 9, 2025  
**For:** Delta Exchange Engineering/Support Team  
**Bot:** GridBot v2.0 Production System
