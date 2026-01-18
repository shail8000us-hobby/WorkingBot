# WebSocket Live Price Implementation - January 18, 2026

## Overview

Implemented real-time BTC and ETH price fetching using WebSocket connection to Delta Exchange India API. This replaces the previous REST API polling approach with a more efficient, lower-latency WebSocket solution.

## Architecture

### Backend Components

#### 1. Delta Price WebSocket Service
**File:** `webui/backend/services/delta_price_websocket.py`

A standalone WebSocket client that:
- Connects to `wss://socket.india.delta.exchange`
- Subscribes to real-time spot price feeds for `.DEXBTUSD` and `.DEETHUSD`
- Broadcasts price updates via Flask-SocketIO
- Implements automatic reconnection with exponential backoff
- Provides fallback REST API support

**Features:**
- Singleton pattern for global instance
- Thread-safe operation
- Automatic reconnection (max 10 attempts)
- Price caching for REST API fallback
- Status monitoring endpoint

**Key Methods:**
```python
class DeltaPriceWebSocket:
    def start()                    # Start WebSocket in background thread
    def stop()                     # Gracefully stop connection
    def get_price(symbol)          # Get latest price for BTC or ETH
    def get_all_prices()           # Get all prices as dict
    def is_connected()             # Check connection status
    def get_status()               # Get detailed service status
```

#### 2. Updated Market Routes
**File:** `webui/backend/routes/market.py`

Enhanced `/api/market/spot-price` endpoint with prioritized data sources:

1. **WebSocket** (real-time, lowest latency) - Primary source
2. **Cache** (10-second TTL) - Fast fallback
3. **Delta Exchange REST API** - Secondary fallback
4. **Guardian signal file** - Tertiary fallback
5. **Static fallback prices** - Last resort

Added new endpoint:
- `GET /api/market/ws-status` - Check WebSocket connection status and current prices

#### 3. Application Integration
**File:** `webui/backend/app.py`

Added WebSocket service initialization on startup:
```python
from webui.backend.services import start_price_service

price_ws = start_price_service(socketio)
```

The service automatically:
- Connects to Delta Exchange WebSocket
- Broadcasts prices via Socket.IO event `market_price_update`
- Runs in background daemon thread
- Provides fallback to REST API on disconnect

### Frontend Components

#### 1. useMarketPrices Hook
**File:** `webui/frontend/src/hooks/useMarketPrices.js`

Custom React hook that manages WebSocket subscription with automatic fallback:

**Features:**
- Automatic Socket.IO connection management
- Real-time price updates via `market_price_update` event
- Automatic fallback to REST API polling on disconnect
- Connection status tracking
- Price source identification (websocket/rest)

**Usage:**
```javascript
const { btcPrice, ethPrice, loading, source, wsConnected, refresh } = useMarketPrices();
```

**Returns:**
- `btcPrice`: Latest BTC price (number)
- `ethPrice`: Latest ETH price (number)
- `loading`: Initial loading state (boolean)
- `source`: Data source ('websocket' or 'rest')
- `wsConnected`: WebSocket connection status (boolean)
- `refresh`: Manual refresh function

#### 2. Updated TopBar Component
**File:** `webui/frontend/src/components/layout/TopBar.js`

**Changes:**
- Replaced REST polling with `useMarketPrices` hook
- Added WebSocket connection indicator (Wifi icon)
- Shows data source (websocket/rest) in small text
- Real-time updates with ~1 second latency

#### 3. Updated OptionsPanel Component
**File:** `webui/frontend/src/components/options/OptionsPanel.js`

**Changes:**
- Replaced position greeks-based price extraction with `useMarketPrices` hook
- Now shows real-time spot prices instead of stale position data
- Uses `useMemo` to convert hook prices to `indexPrices` format
- Maintains compatibility with existing automation and refs

#### 4. Updated FloatingPriceWidget
**File:** `webui/frontend/src/components/FloatingPriceWidget.js`

**Changes:**
- Replaced REST polling with `useMarketPrices` hook
- Added visual WebSocket status indicator (pulsing green dot)
- Shows data source in widget header
- Tracks price changes for delta display

## Data Flow

```
Delta Exchange WebSocket (wss://socket.india.delta.exchange)
    ↓
DeltaPriceWebSocket Service (Backend)
    ↓
Flask-SocketIO Broadcast (event: 'market_price_update')
    ↓
Frontend Socket.IO Client
    ↓
useMarketPrices Hook
    ↓
React Components (TopBar, OptionsPanel, FloatingPriceWidget)
```

## WebSocket Message Format

### From Delta Exchange:
```json
{
  "type": "v2/spot_price",
  "s": ".DEXBTUSD",
  "p": 95174.50
}
```

**Field Mapping:**
- `s` → symbol (e.g., ".DEXBTUSD" or ".DEETHUSD")
- `p` → price (as number, e.g., 95174.50)
- `type` → message type identifier

### Broadcast to Frontend:
```json
{
  "symbol": "BTC",
  "price": 95174.50,
  "timestamp": 1705612800.123
}
```

## Configuration

### Backend
No configuration needed - service starts automatically with the Flask app.

### Frontend
Socket.IO connection options in `useMarketPrices.js`:
```javascript
const socket = io({
  path: '/socket.io',
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 10
});
```

## Fallback Behavior

### WebSocket Disconnection:
1. Hook detects disconnect event
2. Automatically starts REST API polling (5-second interval)
3. Shows "rest" as data source
4. WebSocket icon changes to WifiOff
5. Continues to provide prices without interruption

### WebSocket Reconnection:
1. Automatic reconnection attempts (up to 10 times)
2. Exponential backoff (5-second base delay)
3. On successful reconnection:
   - Stops REST polling
   - Resumes WebSocket updates
   - Updates connection indicator

## Error Handling

### Backend:
- Graceful handling of WebSocket errors
- Automatic reconnection with retry limits
- Detailed logging for debugging
- Multiple fallback data sources

### Frontend:
- Connection error handling
- Graceful degradation to REST API
- Loading states for initial fetch
- Error recovery without user intervention

## Benefits Over Previous Implementation

### Performance:
- **Latency**: ~1 second (vs 5-10 seconds with polling)
- **Network**: Single persistent connection (vs repeated HTTP requests)
- **CPU**: Event-driven (vs timer-based polling)
- **Accuracy**: Real-time Delta Exchange data (vs cached/stale prices)

### User Experience:
- **Real-time updates**: Prices update as they change on the exchange
- **Visual feedback**: Connection status indicators
- **Data source transparency**: Users see "websocket" vs "rest"
- **Seamless fallback**: No interruption during connection issues

### Reliability:
- **Multiple fallbacks**: 5 data sources in priority order
- **Auto-reconnection**: Handles temporary network issues
- **Singleton pattern**: Prevents duplicate connections
- **Thread-safe**: Safe concurrent access

## Testing

### Backend Testing:

1. **Check WebSocket Status:**
```bash
curl http://localhost:5555/api/market/ws-status
```

Expected response:
```json
{
  "connected": true,
  "running": true,
  "prices": {
    "BTC": 95174.50,
    "ETH": 3312.44
  },
  "last_update": {
    "BTC": 1705612800.123,
    "ETH": 1705612800.456
  },
  "reconnect_attempts": 0
}
```

2. **Check Price Endpoint:**
```bash
curl "http://localhost:5555/api/market/spot-price?symbol=BTC"
```

Expected response:
```json
{
  "symbol": "BTC",
  "price": 95174.50,
  "source": "websocket"
}
```

3. **Check Backend Logs:**
```bash
tail -f webui/backend/logs/backend_fixed.log | grep DeltaWS
```

Look for:
- `[DeltaWS] Connection established`
- `[DeltaWS] Subscribed to .DEXBTUSD and .DEETHUSD spot price feeds`
- `[DeltaWS] BTC price update: $95,174.50`
- `[DeltaWS] ETH price update: $3,312.44`

### Frontend Testing:

1. **Check Browser Console:**
```
[useMarketPrices] WebSocket connected
[useMarketPrices] BTC: $95,174
[useMarketPrices] ETH: $3,312.44
```

2. **Visual Indicators:**
- TopBar: Green Wifi icon when connected, gray WifiOff when disconnected
- TopBar: Shows "websocket" or "rest" as source
- FloatingPriceWidget: Pulsing green dot when connected
- FloatingPriceWidget: Shows "websocket" or "rest" in header

3. **Test Fallback:**
- Stop the backend server
- Observe automatic fallback to "rest" mode
- Restart server
- Observe automatic reconnection

## Monitoring

### Backend Logs:
```bash
# WebSocket connection logs
grep "DeltaWS" webui/backend/logs/backend_fixed.log

# Price update logs
grep "price update" webui/backend/logs/backend_fixed.log
```

### Frontend Console:
```javascript
// Open browser console and run:
window.socketDebug = true; // Enable verbose logging
```

## Files Modified

### Backend:
1. `webui/backend/services/__init__.py` (NEW)
2. `webui/backend/services/delta_price_websocket.py` (NEW)
3. `webui/backend/routes/market.py` (UPDATED)
4. `webui/backend/app.py` (UPDATED)
5. `webui/backend/requirements.txt` (UPDATED)

### Frontend:
1. `webui/frontend/src/hooks/useMarketPrices.js` (NEW)
2. `webui/frontend/src/components/layout/TopBar.js` (UPDATED)
3. `webui/frontend/src/components/options/OptionsPanel.js` (UPDATED)
4. `webui/frontend/src/components/FloatingPriceWidget.js` (UPDATED)

## Dependencies Added

### Backend:
- `websocket-client==1.7.0` - WebSocket client library

### Frontend:
- No new dependencies (socket.io-client already installed)

## Future Enhancements

1. **Additional Symbols**: Extend to support more cryptocurrencies
2. **Price History**: Store recent price updates for charts
3. **Alert System**: Notify on significant price movements
4. **Compression**: Enable WebSocket message compression
5. **Metrics**: Track WebSocket uptime and latency
6. **Batching**: Batch multiple price updates for efficiency

## Rollback Instructions

If issues arise, rollback is simple:

1. **Backend**: Comment out WebSocket service initialization in `app.py`
```python
# try:
#     from webui.backend.services import start_price_service
#     price_ws = start_price_service(socketio)
# except:
#     pass
```

2. **Frontend**: The components will automatically fall back to REST API polling

3. **Remove files** (optional):
```bash
rm webui/backend/services/delta_price_websocket.py
rm webui/backend/services/__init__.py
rm webui/frontend/src/hooks/useMarketPrices.js
```

The system is designed to work seamlessly with or without WebSocket, ensuring zero downtime.

## Conclusion

This implementation provides:
- ✅ Real-time price updates from Delta Exchange
- ✅ Lower latency (~1s vs 5-10s)
- ✅ Reduced network overhead
- ✅ Automatic fallback to REST API
- ✅ Visual connection status indicators
- ✅ Multiple data source fallbacks
- ✅ Comprehensive error handling
- ✅ Zero breaking changes to existing functionality

All three price displays (TopBar, OptionsPanel, FloatingPriceWidget) now show identical, real-time prices from Delta Exchange via WebSocket with automatic REST API fallback.
