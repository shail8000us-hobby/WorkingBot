# Delta Exchange WebSocket Support Request - November 10, 2025

## Subject: Critical WebSocket Connection Issues - Seeking Official Recommendations

Dear Delta Exchange Engineering Team,

We are experiencing critical WebSocket connection stability issues with our production trading bot on Delta Exchange. After extensive debugging over multiple days, we've identified patterns that suggest we may be misunderstanding the correct implementation of your WebSocket protocol. We urgently need clarification on the official recommended practices.

---

## System Information

- **Environment**: Production (Live Trading)
- **WebSocket URL**: `wss://socket.india.delta.exchange`
- **Client Library**: `websocket-client` (Python)
- **Trading Symbol**: BTCUSD
- **Bot Runtime**: 24/7 automated trading system
- **Authentication**: HMAC-SHA256 with API keys (working correctly)

---

## Critical Issues Encountered

### Issue #1: 60-Second Connection Death Cycle ⚠️ CRITICAL

**Problem**: WebSocket connection dies exactly every 60 seconds and reconnects in an endless loop.

**Timeline Pattern** (from production logs):
```
07:44:15 Uptime: 60.6s → Connection dead → Force reconnect
07:46:24 Uptime: 128.4s → Connection dead → Force reconnect  
07:47:32 Uptime: 66.3s → Connection dead → Force reconnect
07:48:38 Uptime: 65.5s → Connection dead → Force reconnect
[Pattern continues for 7+ hours...]
```

**Our Initial Configuration**:
```python
ping_interval = 30  # Send WebSocket protocol ping every 30s
ping_timeout = 10   # Kill connection if no pong in 10s
```

**What We Believe Is Happening**:
1. At T+30s: Our client sends WebSocket protocol ping (0x9 frame)
2. At T+30-40s: Wait for WebSocket protocol pong (0xA frame)
3. At T+40s: No pong received → Library closes connection automatically
4. Connection dies, reconnects, cycle repeats

**Question 1**: Does Delta Exchange respond to WebSocket **protocol-level** ping frames (0x9), or only to **application-level** `{"type": "ping"}` JSON messages?

**Question 2**: If Delta doesn't respond to protocol pings, what is the recommended keepalive mechanism?

---

### Issue #2: No Data After Reconnection ⚠️ CRITICAL

**Problem**: After reconnection, subscriptions succeed but NO data flows on any channel.

**Evidence** (from logs at 08:16:51):
```
08:16:51 ✅ CONNECTION: New connection established successfully
08:16:52 ✅ Subscription confirmed: positions
08:16:52 📡 Subscribing to v2/ticker (BTCUSD)
08:16:54 ✅ Subscription confirmed: v2/ticker (BTCUSD)
08:16:54 ✅ Subscription confirmed: orders
08:16:54 ✅ Subscription confirmed: all_trades
08:16:55 ✅ Subscription confirmed: margins

[After 08:16:55: ZERO messages received for 11+ minutes]
- No ticker updates
- No heartbeats
- No pong responses
- No data on any channel
```

**Our Modified Configuration** (attempting to fix Issue #1):
```python
ping_interval = 0     # Disabled protocol pings
ping_timeout = None   # Disabled timeout
```

**Result**: Connection stays "alive" at TCP level, but Delta stops sending data completely.

**Question 3**: When `ping_interval=0` (no protocol pings), does Delta Exchange:
- Still send data normally?
- Require periodic protocol pings to keep sending data?
- Have a timeout that closes data flow if no pings received?

**Question 4**: After reconnection, is there a special message or sequence required to "activate" data flow?

---

### Issue #3: Multiple Heartbeat Monitor Threads

**Problem**: Heartbeat warnings spamming logs (26 identical warnings in 1 second).

**Evidence** (at 08:27:21):
```
08:27:21,194 WARNING: ⚠️  [HEARTBEAT] No messages for 35s, sending ping...
08:27:21,203 WARNING: ⚠️  [HEARTBEAT] No messages for 35s, sending ping...
08:27:21,272 WARNING: ⚠️  [HEARTBEAT] No messages for 35s, sending ping...
[... 23 more identical warnings in same second ...]
```

This suggests either:
- Multiple heartbeat threads running (our bug)
- OR connection is in a broken state causing rapid ping attempts

**Question 5**: Could this be related to Delta's connection state machine? Is there a state where connection appears alive but data flow is paused?

---

### Issue #4: Server Heartbeat Not Received

**Problem**: After enabling `{"type": "enable_heartbeat"}`, we never receive `{"type": "heartbeat"}` messages.

**Our Implementation**:
```python
# After authentication success
auth_response = {"type": "auth", "success": true}
# We send:
{"type": "enable_heartbeat"}
```

**Expected**: `{"type": "heartbeat"}` every 30 seconds
**Actual**: No heartbeat messages ever received

**Question 6**: 
- Is `{"type": "enable_heartbeat"}` the correct message format?
- Should we receive confirmation that heartbeat is enabled?
- What is the exact format of heartbeat messages we should receive?

---

### Issue #5: Stale Price Data Despite Active Connection

**Problem**: Price data becomes stale (600+ seconds old) while WebSocket connection appears connected.

**Evidence**:
```
08:27:12 ERROR: 🚨 PRICE CRITICAL: $105,661.50 | Age: 634.9s
08:27:30 ERROR: 🚨 PRICE CRITICAL: $105,661.50 | Age: 652.6s
[Price stuck at same value for 11+ minutes]
[Connection shows as "connected" and "authenticated"]
```

**Question 7**: Is there a server-side throttling or rate limiting that could pause data flow without closing connection?

---

## What We Need from Delta Exchange

### 1. Official WebSocket Configuration Recommendations

**Please provide the officially recommended settings for**:
```python
# WebSocket protocol keepalive
ping_interval = ???      # Seconds between protocol pings (or 0 to disable?)
ping_timeout = ???       # Seconds to wait for protocol pong (or None?)

# Application-level keepalive  
enable_heartbeat = ???   # Should we enable server heartbeat?
client_ping_interval = ??? # Should we send {"type": "ping"}? How often?

# Connection health
max_silence_before_reconnect = ??? # How long is acceptable silence?
```

### 2. Data Flow State Machine

**Please clarify**:
- What states can a WebSocket connection be in? (connected, authenticated, active, paused, etc.)
- What triggers data flow to stop while connection stays alive?
- How to detect if connection is in a "zombie" state?
- How to properly recover from stalled data flow without full reconnection?

### 3. Channel-Specific Behavior

**For `v2/ticker` channel**:
- Guaranteed update frequency? (we see in docs: "every 5 seconds")
- Does this guarantee hold during:
  - Low market activity?
  - High load on server?
  - After reconnections?
  
**For private channels** (`orders`, `positions`, `v2/user_trades`):
- Are these event-driven only? (silence is normal with no activity?)
- Or should we expect periodic keepalive messages?

### 4. Debugging Support

**Can you help us understand**:
- Server-side connection logs for our API key (if available)?
- Are we being rate-limited or throttled?
- Any red flags in our connection pattern that would cause data flow to stop?
- Known issues with the India WebSocket endpoint (`wss://socket.india.delta.exchange`)?

---

## Our Current Workaround (Unstable)

```python
# Configuration that allows connection but no data flows
ping_interval = 0
ping_timeout = None

# OR

# Configuration that causes 60-second death cycle  
ping_interval = 30
ping_timeout = 10
```

**Neither configuration works reliably for production 24/7 trading.**

---

## Production Impact

This is affecting live trading operations:

1. ❌ **No order execution** when price data is stale (safety mechanism)
2. ❌ **Missed trading opportunities** during reconnection cycles
3. ❌ **Positions at risk** due to inability to place stop-loss orders
4. ⚠️ **Manual intervention required** every 60 seconds to restart bot
5. ⚠️ **REST API fallback** is slow (5s polling vs 0.05s WebSocket latency)

**We need stable WebSocket connectivity to safely trade on Delta Exchange.**

---

## Request for Official Documentation

We've reviewed:
- WebSocket documentation at Delta Exchange developer portal
- API documentation for authentication
- Various GitHub examples and community solutions

**But we still need clarity on**:
1. Official Python example with `websocket-client` library
2. Recommended keepalive strategy and configuration
3. Reconnection best practices
4. How to detect and recover from "zombie" connections
5. Expected behavior for each message type (ping, pong, heartbeat, ticker, etc.)

---

## Testing Assistance

We are willing to:
- Provide detailed logs from our production system
- Test any recommended configuration changes
- Share our complete WebSocket implementation for review
- Enable debug logging on your recommendation
- Work with your engineering team to identify root cause

---

## API Key Information

**For reference** (if you need to check server-side logs):
- API Key: `[REDACTED - Will provide in private communication]`
- Trading Account: Live Production Account
- Last Successful Connection: November 10, 2025, 08:05:02 IST
- Last Failed State: November 10, 2025, 08:16:51 IST (connected but no data)

---

## Summary of Questions

1. Does Delta respond to WebSocket protocol ping frames (0x9)?
2. What is the recommended keepalive mechanism?
3. Why does data stop flowing after reconnection despite successful subscriptions?
4. Is there a required sequence or message to activate data flow post-reconnect?
5. Can connection be in a state where it's "alive" but data is paused?
6. What is the correct format for enabling and receiving server heartbeats?
7. Is there server-side throttling that pauses data without closing connection?
8. What are the official recommended WebSocket configuration values?

---

## Urgency: HIGH

Our production trading system is currently unstable and requires manual intervention.

We appreciate your prompt assistance in resolving these critical WebSocket stability issues.

Best regards,
GridBot Development Team

---

**Attachments**:
- Full WebSocket implementation code (delta_ws.py)
- Production log excerpt showing connection death cycle
- Production log excerpt showing data starvation after reconnect
- Network packet capture (if needed)

**Contact**: [Your preferred contact method]

**Expected Response Time**: 24-48 hours for critical production issue
