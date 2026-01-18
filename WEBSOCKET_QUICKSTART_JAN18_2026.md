# WebSocket Live Prices - Quick Start Guide

## What Changed

We've implemented real-time BTC and ETH price updates using WebSocket instead of REST API polling.

## Key Benefits

- **Real-time updates**: ~1 second latency (vs 5-10 seconds before)
- **Lower network usage**: Single persistent connection
- **Automatic fallback**: Falls back to REST API if WebSocket disconnects
- **Visual indicators**: See connection status in UI

## Installation

### Backend Dependencies
```bash
cd webui/backend
pip install -r requirements.txt
```

This installs:
- `websocket-client==1.7.0` (NEW)
- `flask-compress==1.14` (NEW)

### Frontend
No new dependencies needed (socket.io-client already installed)

## How to Start

### Backend
Just start the backend as usual:
```bash
cd webui/backend
python app.py
```

You should see:
```
💹 Starting Delta Price WebSocket...
✅ Delta Price WebSocket started (BTC & ETH real-time feeds)
   📡 Connected to wss://socket.india.delta.exchange
   📊 Broadcasting prices via Socket.IO on 'market_price_update' event
```

### Frontend
Start the frontend as usual:
```bash
cd webui/frontend
npm start
```

## Visual Indicators

### TopBar (Header)
- **Green Wifi icon** = WebSocket connected
- **Gray WifiOff icon** = Using REST API fallback
- Small text shows "websocket" or "rest"

### FloatingPriceWidget (Bottom Right)
- **Pulsing green dot** = WebSocket connected
- **Gray dot** = Using REST API fallback
- Header shows "websocket" or "rest"

### OptionsPanel (Main Section)
- Prices update in real-time automatically
- No visual indicator (uses same hook as TopBar)

## How It Works

```
Delta Exchange WebSocket
    ↓
Backend Python Service
    ↓
Flask-SocketIO Broadcast
    ↓
Frontend React Hook (useMarketPrices)
    ↓
All Components (TopBar, OptionsPanel, FloatingPriceWidget)
```

## API Endpoints

### Get Current Price
```bash
curl "http://localhost:5555/api/market/spot-price?symbol=BTC"
```

Response sources (in priority order):
1. `"source": "websocket"` - Real-time from WebSocket
2. `"source": "cache"` - From 10-second cache
3. `"source": "delta_api"` - From REST API
4. `"source": "guardian"` - From guardian signal file
5. `"source": "fallback"` - Static fallback price

### Check WebSocket Status
```bash
curl "http://localhost:5555/api/market/ws-status"
```

Response:
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

## Troubleshooting

### Backend Not Connecting to WebSocket
Check logs:
```bash
tail -f webui/backend/logs/backend_fixed.log | grep DeltaWS
```

Should see:
```
[DeltaWS] Connection established
[DeltaWS] Subscribed to .DEXBTUSD and .DEETHUSD spot price feeds
[DeltaWS] BTC price update: $95,174.50
```

### Frontend Not Receiving Updates
Check browser console:
```
[useMarketPrices] WebSocket connected
[useMarketPrices] BTC: $95,174
```

If you see `WebSocket disconnected`, it will automatically fall back to REST API polling.

### Prices Still Wrong
1. Check WebSocket status: `curl http://localhost:5555/api/market/ws-status`
2. If `connected: false`, restart backend
3. Frontend will automatically reconnect

## Fallback Behavior

### If WebSocket Disconnects:
1. Frontend automatically switches to REST API polling (5-second interval)
2. Visual indicator changes to "rest" mode
3. No interruption in price updates
4. Automatic reconnection attempts in background

### If Backend is Down:
1. Frontend continues with last known prices
2. Will attempt to reconnect when backend is back
3. No errors shown to user (graceful degradation)

## Testing

### Test WebSocket Connection
1. Open browser DevTools → Console
2. Watch for `[useMarketPrices] WebSocket connected`
3. Check TopBar for green Wifi icon
4. Prices should update every ~1 second

### Test Fallback
1. Stop backend: `Ctrl+C` in backend terminal
2. Frontend switches to REST mode automatically
3. Restart backend
4. Frontend reconnects automatically

## Files Changed

### Backend (5 files):
- `webui/backend/services/delta_price_websocket.py` (NEW)
- `webui/backend/services/__init__.py` (NEW)
- `webui/backend/routes/market.py` (UPDATED)
- `webui/backend/app.py` (UPDATED)
- `webui/backend/requirements.txt` (UPDATED)

### Frontend (4 files):
- `webui/frontend/src/hooks/useMarketPrices.js` (NEW)
- `webui/frontend/src/components/layout/TopBar.js` (UPDATED)
- `webui/frontend/src/components/options/OptionsPanel.js` (UPDATED)
- `webui/frontend/src/components/FloatingPriceWidget.js` (UPDATED)

## Rollback

If you need to rollback, just comment out in `app.py`:
```python
# try:
#     from webui.backend.services import start_price_service
#     price_ws = start_price_service(socketio)
# except:
#     pass
```

Frontend will automatically fall back to REST API polling.

## Documentation

For complete technical details, see:
- `WEBSOCKET_PRICE_IMPLEMENTATION_JAN18_2026.md`
- `PRICE_SYNC_FIX_JAN18_2026.md`
