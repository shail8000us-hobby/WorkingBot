# AsyncGridBot Issue Report - November 13, 2025

## Executive Summary

**Status:** Bot is **PARTIALLY FUNCTIONAL** - Orders are being placed successfully, but REST API authentication is failing for GET requests.

**Critical Finding:** 
- ✅ **Order placement works** (POST requests with signature auth) - Order ID 1034513295 successfully placed
- ❌ **Position/Order queries fail** (GET requests returning 401 Unauthorized)
- ✅ **WebSocket authentication works** perfectly

---

## 1. Issues by Category

### 🔴 **CRITICAL - REST API Authentication (GET requests)**

**Symptoms:**
```
HTTP/1.1 401 Unauthorized
{"error":"unauthorized","success":false}
```

**Affected Operations:**
- `GET /v2/orders` - List open orders
- `GET /v2/positions` - Get account positions  
- Orphaned order reconciliation
- Safety limit checks
- Position monitoring

**Frequency:** Every GET request fails (100% failure rate)

**Impact:**
- Cannot reconcile orders from exchange
- Safety checks degraded (relies on WebSocket only)
- Monitoring incomplete
- Circuit breaker triggers after 5 consecutive failures

**Evidence from logs:**
```
2025-11-13 14:59:37.181 [INFO] HTTP Request: GET https://api.india.delta.exchange/v2/orders?page_size=100&product_ids=27&states=open "HTTP/1.1 401 Unauthorized"
2025-11-13 14:59:40.529 [ERROR] ❌ Error during orphaned order reconciliation: Authentication failed - check API credentials
2025-11-13 14:59:46.791 [ERROR] ❌ Failed to check exchange orders: Authentication failed - check API credentials
2025-11-13 14:59:50.296 [ERROR] Safety check failed: Authentication failed - check API credentials
```

---

### ✅ **WORKING - Order Placement (POST requests)**

**Proof of Success:**
```
2025-11-13 14:59:51,514 [INFO] HTTP Request: POST https://api.india.delta.exchange/v2/orders "HTTP/1.1 200 OK"
2025-11-13 14:59:51.515 [INFO] Order placed: buy 1 @ 100500.0 (product_id=27) -> 1034513295
2025-11-13 14:59:51.523 [INFO] ✅ BUY order placed: 1034513295
2025-11-13 14:59:51.523 [INFO] ✅ Initial MAKER BUY placed @ $100,500.00 (Order: 1034513295)
```

**Order Details:**
- Order ID: `1034513295`
- Type: BUY (LIMIT, POST-ONLY)
- Size: 1 contract
- Price: $100,500.00
- Product: BTCUSD (ID: 27)
- Timestamp: 2025-11-13 14:59:51 IST
- Status: Successfully placed and tracked in bot state

---

### ✅ **WORKING - WebSocket Authentication**

**Success Evidence:**
```
2025-11-13 14:59:41.253 [INFO] ✅ WebSocket connected successfully
2025-11-13 14:59:41.253 [INFO] Sent authentication message (timestamp=1763026181)
2025-11-13 14:59:41.425 [INFO] ✅ Authentication successful
2025-11-13 14:59:41.425 [INFO] Subscribing to private channels after authentication
2025-11-13 14:59:41.595 [INFO] ✅ Subscription confirmed: orders
2025-11-13 14:59:41.624 [INFO] ✅ Subscription confirmed: positions
2025-11-13 14:59:41.724 [INFO] ✅ Subscription confirmed: v2/ticker
```

**WebSocket Functionality:**
- Price updates: ✅ Working
- Order updates: ✅ Working
- Position updates: ✅ Working
- Private channel subscriptions: ✅ Working
- Heartbeat: ✅ Working (every ~5 seconds)

---

### ⚠️ **MINOR - Monitoring System Error**

**Issue:**
```
2025-11-13 14:59:59.307 [ERROR] Monitoring error: 'PreOrderDecisionLogger' object has no attribute 'get_recent_decisions'
```

**Impact:** Low - Monitoring loop continues, only one feature affected

**Frequency:** Every 5 seconds (monitoring loop interval)

**Root Cause:** Code expects method that doesn't exist in PreOrderDecisionLogger class

---

### ⚠️ **MINOR - Notification System**

**Issue:**
```
2025-11-13 14:59:54,303 [WARNING] notifier: send failed: HTTP Error 404: Not Found
```

**Impact:** Low - Telegram/notification system not configured

**Status:** Non-critical, expected if notification service not set up

---

### ⚠️ **MINOR - Liquidation Monitor**

**Issue:**
```
2025-11-13 14:59:51,906 [WARNING] Liquidation monitor not available
```

**Impact:** Low - Optional feature, bot continues without it

---

## 2. Technical Implementation Details

### Our Authentication Implementation

**File:** `bot/api/async_delta_client.py`

**Signature Generation Method:**
```python
def _generate_signature(self, method: str, path: str, query_or_payload: str = "") -> Dict[str, str]:
    """
    Delta Exchange signature format:
    - For GET/DELETE with params: METHOD + TIMESTAMP + PATH + QUERY_STRING
    - For POST/PUT with body: METHOD + TIMESTAMP + PATH + JSON_BODY
    """
    timestamp = str(int(time.time()))  # SECONDS (not milliseconds)
    signature_data = method.upper() + timestamp + path + query_or_payload
    
    signature = hmac.new(
        self.api_secret.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "api-key": self.api_key,
        "signature": signature,
        "timestamp": timestamp,
        "User-Agent": "python-rest-client",
        "Content-Type": "application/json"
    }
```

**Request Implementation (GET with params):**
```python
if method in ["GET", "DELETE"] and params:
    # Build query string and include in signature
    query_string = urlencode(sorted(params.items()))  # ← Sorted for consistency
    full_path = f"{path}?{query_string}"
    headers = self._generate_signature(method, path, query_string)  # ← Sign with query string
    
    response = await self._client.request(
        method=method,
        url=full_path,
        headers=headers
    )
```

**Request Implementation (POST with body):**
```python
if method in ["POST", "PUT"] and data:
    # JSON body included in signature
    json_body = json.dumps(data, separators=(',', ':'))
    headers = self._generate_signature(method, path, json_body)  # ← Sign with JSON body
    
    response = await self._client.request(
        method=method,
        url=path,
        headers=headers,
        json=data
    )
```

---

### What's Different Between Working POST and Failing GET

| Aspect | POST (Working ✅) | GET (Failing ❌) |
|--------|------------------|------------------|
| HTTP Method | POST | GET |
| Signature includes | JSON body | Query string |
| URL format | `/v2/orders` | `/v2/orders?page_size=100&product_ids=27` |
| Response | 200 OK | 401 Unauthorized |
| Authentication | Succeeds | Fails |

**Key Questions:**
1. Is our query string format correct for Delta Exchange?
2. Should query params be included in signature for GET requests?
3. Is there a different authentication method for read-only operations?
4. Do API keys need specific permissions for GET operations?

---

## 3. API Configuration

**Credentials Used:**
```bash
DELTA_API_KEY=p1QrZ62WGTNW4NN9lsRP1iqzskqSMP
DELTA_API_SECRET=wbCMiey59MsNgsvqtoifrj4ZMp7SzwMnXEOKkBnWSTjk4GstXYXZzz5r6amy
```

**API Endpoints:**
- Base URL: `https://api.india.delta.exchange`
- WebSocket: `wss://socket.india.delta.exchange`
- Product: BTCUSD (ID: 27)

**API Key Permissions (Expected):**
- ✅ Place orders (POST /v2/orders) - CONFIRMED WORKING
- ❌ List orders (GET /v2/orders) - FAILING
- ❌ Get positions (GET /v2/positions) - FAILING
- ✅ WebSocket private channels - CONFIRMED WORKING

---

## 4. Timeline of Events

**14:59:36** - Bot starts, credentials loaded
**14:59:37** - First 401 error on GET /v2/orders (orphaned order reconciliation)
**14:59:40** - WebSocket connects successfully
**14:59:41** - WebSocket authentication succeeds
**14:59:43** - Price fetched via REST: $102,974.50 (public endpoint, works)
**14:59:46** - GET /v2/orders fails (checking existing orders before placing)
**14:59:51** - **POST /v2/orders SUCCEEDS** - Order 1034513295 placed ✅
**14:59:54** - Bot starts all monitoring loops
**15:00:15** - Circuit breaker opens after 5 consecutive GET failures

---

## 5. Code References

**Signature generation:**
- File: `bot/api/async_delta_client.py`
- Lines: 127-161

**GET request handler:**
- File: `bot/api/async_delta_client.py`
- Lines: 244-254

**POST request handler:**
- File: `bot/api/async_delta_client.py`
- Lines: 224-242

**Order placement (working):**
- File: `bot/api/async_delta_client.py`
- Method: `place_order()` - Lines 370-430

**Get positions (failing):**
- File: `bot/api/async_delta_client.py`
- Method: `get_positions()` - Lines 540-570

---

## 6. Comparison with Old Bot

**Old Bot (GridBot):**
- Also uses same API credentials
- Also uses signature-based authentication
- GET requests work without issues
- No 401 errors reported

**Key Differences:**
- Old bot uses synchronous `requests` library
- Async bot uses `httpx` async library
- Both should generate identical signatures
- Both hit same endpoints

**Hypothesis:** The authentication method is identical, but there may be:
1. Timing difference in timestamp generation
2. URL encoding difference in query strings
3. Header format differences between `requests` and `httpx`

---

## 7. What We Need from Delta Exchange Support

### **Question 1: Signature Format for GET Requests**

Is our signature generation correct for GET requests with query parameters?

**Our current implementation:**
```
Signature data = "GET" + timestamp + "/v2/orders" + "page_size=100&product_ids=27"
```

**Should it be:**
- Option A: Include query string (current implementation)
- Option B: Exclude query string (only sign path)
- Option C: Different format entirely

### **Question 2: URL Format for Signed Requests**

When building the signature with query params, should we use:
- Option A: `full_path = f"{path}?{query_string}"` (current)
- Option B: Sign path only, append query after
- Option C: URL-encode the query string before signing

### **Question 3: Header Requirements**

Are these headers sufficient and in the correct format?
```python
{
    "api-key": self.api_key,
    "signature": signature,
    "timestamp": timestamp,
    "User-Agent": "python-rest-client",
    "Content-Type": "application/json"
}
```

Do GET requests need any additional headers?

### **Question 4: API Key Permissions**

The API key successfully:
- ✅ Places orders (POST /v2/orders)
- ✅ Authenticates WebSocket
- ✅ Subscribes to private channels

But fails to:
- ❌ List orders (GET /v2/orders)
- ❌ Get positions (GET /v2/positions)

**Question:** Are there separate permissions for read vs write operations? Do we need to regenerate the API key with specific permissions?

### **Question 5: Async HTTP Client Compatibility**

We're using `httpx` (async) instead of `requests` (sync). Are there any known compatibility issues with Delta Exchange API and async HTTP clients?

### **Question 6: Timestamp Format**

We're using:
```python
timestamp = str(int(time.time()))  # Unix timestamp in seconds
```

Is this the correct format? Should we use milliseconds instead?

### **Question 7: Query String Encoding**

For GET requests with multiple parameters, should we:
- Sort parameters alphabetically? (we currently do)
- Use specific URL encoding?
- Escape special characters in a particular way?

---

## 8. Temporary Workarounds in Place

**Current Bot Behavior:**
1. ✅ Places orders successfully via POST
2. ⚠️ Relies on WebSocket for position updates (instead of REST)
3. ⚠️ Skips orphaned order reconciliation (can't GET orders)
4. ⚠️ Safety checks degraded (can't GET positions)
5. ✅ All order tracking works via WebSocket push updates

**Risk Level:** MEDIUM
- Bot can trade but lacks full reconciliation
- WebSocket updates are reliable but REST fallback would be safer
- If WebSocket disconnects, bot cannot query current state

---

## 9. Request for Official Guidance

**What We Need:**
1. **Working example** of GET request authentication (Python preferred)
2. **Documentation link** for signature generation (if available)
3. **Verification** that our POST implementation is correct (since it works)
4. **Explanation** of why POST works but GET fails with same credentials
5. **API key permission settings** guidance
6. **Alternative authentication method** if signature-based auth has different requirements for GET vs POST

**Our Goal:**
Make REST API GET requests work reliably so we can:
- Reconcile orders on startup
- Verify positions for safety checks
- Provide REST fallback if WebSocket fails
- Complete full monitoring and safety features

---

## 10. Contact Information

**Bot Details:**
- Bot Name: AsyncGridBot v2.0
- Architecture: Async/await with Actor pattern
- Language: Python 3.9
- HTTP Client: httpx (async)
- Exchange: Delta Exchange India

**API Configuration:**
- Base URL: https://api.india.delta.exchange
- WebSocket: wss://socket.india.delta.exchange
- Product: BTCUSD (ID: 27)
- Mode: LIVE trading (production)

**Timeline:** Need resolution ASAP - Bot is live trading with degraded monitoring

---

## Appendix A: Full Error Stack Trace

```
2025-11-13 14:59:40.534 | ERROR | bot.strategy.async_gridbot:_reconcile_orphaned_orders:631 - 
Traceback (most recent call last):
  File "/Users/ssr/Projects/WorkingBot/bot/strategy/async_gridbot.py", line 538, in _reconcile_orphaned_orders
    all_orders = await self.api_client.list_orders(
  File "/Users/ssr/Projects/WorkingBot/bot/api/async_delta_client.py", line 650, in list_orders
    response = await self._request_with_retry(
  File "/Users/ssr/Projects/WorkingBot/bot/api/async_delta_client.py", line 278, in _request_with_retry
    raise DeltaAuthenticationError("Authentication failed - check API credentials")
bot.api.async_delta_client.DeltaAuthenticationError: Authentication failed - check API credentials
```

---

## Appendix B: Successful Order Placement Log

```
2025-11-13 14:59:50.296 | INFO | bot.strategy.async_gridbot:_place_initial_order:1209 - 
  📍 Placing initial MAKER BUY order @ $100,500.00
  Current market: $102,961.00

2025-11-13 14:59:50.296 | DEBUG | [OrderManager] Processing PLACE_BUY

2025-11-13 14:59:50.296 | INFO | bot.strategy.actors.order_actor:_handle_place_buy:143 - 
  Placing BUY order: 1 @ 100500.0 (tag: GBOT_BUY_100500_1763026190, post_only: True, attempt 1)

2025-11-13 14:59:51,514 [INFO] HTTP Request: POST https://api.india.delta.exchange/v2/orders "HTTP/1.1 200 OK"

2025-11-13 14:59:51.515 | INFO | bot.api.async_delta_client:place_order:394 - 
  Order placed: buy 1 @ 100500.0 (product_id=27) -> 1034513295

2025-11-13 14:59:51.523 | INFO | bot.strategy.actors.order_actor:_handle_place_buy:186 - 
  ✅ BUY order placed: 1034513295

2025-11-13 14:59:51.523 | INFO | bot.strategy.async_gridbot:_place_initial_order:1232 - 
  ✅ Initial MAKER BUY placed @ $100,500.00 (Order: 1034513295)
```

---

**End of Report**

Generated: November 13, 2025
Bot Version: AsyncGridBot v2.0 (Actor + Saga + EventStore)
Repository: Working-gridBOT (production-v2.0 branch)
