# Delta Exchange API Support Request

**Date:** November 13, 2025  
**Priority:** High  
**Category:** API Authentication Issue  
**Product:** BTCUSD (ID: 27)  
**Environment:** Production (api.india.delta.exchange)

---

## Summary

We have implemented an async trading bot using Delta Exchange REST API and WebSocket. **Order placement (POST requests) works perfectly**, but **all GET requests return 401 Unauthorized**. We need guidance on the correct authentication implementation for GET requests.

---

## What's Working ✅

1. **Order Placement (POST /v2/orders)**
   - Successfully placed Order ID: 1034513295
   - Authentication signature accepted
   - Order confirmed on exchange

2. **WebSocket Authentication**
   - Connection successful
   - Private channel subscriptions working
   - Real-time order/position updates working
   - Heartbeat functioning

3. **Public REST Endpoints**
   - Ticker data retrieval working
   - Product information working

---

## What's Failing ❌

**All authenticated GET requests return 401 Unauthorized:**

```
GET /v2/orders?page_size=100&product_ids=27&states=open
Response: 401 Unauthorized
{"error":"unauthorized","success":false}

GET /v2/positions?product_id=27
Response: 401 Unauthorized
{"error":"unauthorized","success":false}
```

---

## Our Implementation

### Signature Generation

```python
def _generate_signature(self, method: str, path: str, query_or_payload: str = "") -> Dict[str, str]:
    timestamp = str(int(time.time()))  # Unix timestamp in seconds
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

### GET Request Implementation

```python
# For GET with query parameters
query_string = urlencode(sorted(params.items()))  # e.g., "page_size=100&product_ids=27"
full_path = f"{path}?{query_string}"              # e.g., "/v2/orders?page_size=100&product_ids=27"
headers = self._generate_signature("GET", path, query_string)

response = await httpx_client.request(
    method="GET",
    url=full_path,
    headers=headers
)
```

### POST Request Implementation (Working)

```python
# For POST with JSON body
json_body = json.dumps(data, separators=(',', ':'))
headers = self._generate_signature("POST", path, json_body)

response = await httpx_client.request(
    method="POST",
    url=path,
    headers=headers,
    json=data
)
```

---

## Specific Questions

### 1. Signature Format for GET Requests
When constructing the signature for GET requests with query parameters, should we:

**Option A (Current):**
```
signature_data = "GET" + timestamp + "/v2/orders" + "page_size=100&product_ids=27"
```

**Option B:**
```
signature_data = "GET" + timestamp + "/v2/orders"  # Exclude query string
```

**Option C:**
Something else entirely?

### 2. Query String Ordering
Should query parameters be:
- Sorted alphabetically (current implementation)?
- In original order?
- Does order matter for signature?

### 3. URL Format
When making the actual HTTP request, should the URL be:
- `/v2/orders?page_size=100&product_ids=27` (current)
- `/v2/orders` with params passed separately to HTTP client
- Something else?

### 4. API Key Permissions
Our API key can:
- ✅ Place orders (POST)
- ✅ Authenticate WebSocket
- ❌ List orders (GET)
- ❌ Get positions (GET)

**Question:** Are there separate read/write permissions? Do we need to regenerate the API key?

### 5. HTTP Client
We're using Python's `httpx` (async) library instead of `requests` (sync). Are there any known compatibility issues?

### 6. Timestamp Format
Confirming we're using the correct timestamp format:
```python
timestamp = str(int(time.time()))  # Unix seconds, not milliseconds
```
Is this correct?

---

## Evidence

### Successful POST Request
```
2025-11-13 14:59:51,514 [INFO] HTTP Request: POST https://api.india.delta.exchange/v2/orders "HTTP/1.1 200 OK"
Response: {"success": true, "result": {"id": 1034513295, ...}}
```

### Failed GET Request
```
2025-11-13 14:59:37,181 [INFO] HTTP Request: GET https://api.india.delta.exchange/v2/orders?page_size=100&product_ids=27&states=open "HTTP/1.1 401 Unauthorized"
Response: {"error":"unauthorized","success":false}
```

### Request Headers (Both requests use same format)
```
api-key: p1QrZ62WGTNW4NN9lsRP1iqzskqSMP
signature: <hmac-sha256-hex>
timestamp: <unix-seconds>
User-Agent: python-rest-client
Content-Type: application/json
```

---

## What We Need

1. **Confirmation** our POST signature method is correct (since it works)
2. **Explanation** of why GET requests fail with same credentials
3. **Working example** of GET request authentication (Python preferred)
4. **Documentation link** for signature generation if available
5. **Guidance** on API key permissions/settings
6. **Alternative approach** if we're missing something fundamental

---

## Our Context

- **Language:** Python 3.9
- **HTTP Library:** httpx (async)
- **Bot Architecture:** Async/await with asyncio
- **Previous Bot:** Used same credentials with `requests` library - worked fine
- **Current Status:** Live trading with degraded monitoring (relying only on WebSocket)

---

## Urgency

We have a live trading bot that:
- ✅ Can place orders
- ✅ Receives WebSocket updates
- ❌ Cannot reconcile orders on startup
- ❌ Cannot verify positions for safety checks
- ❌ Lacks REST API fallback

We need GET requests working for complete safety and monitoring features.

---

## Additional Information

**Full technical report available:** ASYNC_BOT_ISSUE_REPORT_NOV13_2025.md

**API Credentials:**
- Key: p1QrZ62WGTNW4NN9lsRP1iqzskqSMP
- (Secret available privately)

**Contact:**
- Repository: Working-gridBOT (production-v2.0 branch)
- Available for testing/debugging with Delta Exchange team

---

**Thank you for your assistance!**

We appreciate any guidance on resolving this authentication issue. Our POST implementation works perfectly, so we're confident we're close to the solution - just need clarification on GET request signature format.
