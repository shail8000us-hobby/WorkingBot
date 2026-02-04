# TradingView Integration Guide 📊

Complete guide to integrate TradingView buy/sell signals with your WebUI.

## 🎯 Overview

This integration allows you to:
- Receive real-time buy/sell signals from TradingView Pine Script charts
- Store and display all signals in your WebUI
- Filter and analyze signal performance
- Optionally execute trades automatically based on signals

## 📋 Setup Steps

### 1. Backend Setup (Already Done ✅)

The following components have been added to your backend:

- **Webhook Endpoint**: `/api/tradingview/webhook`
- **Database**: `webui/data/tradingview_signals.db`
- **API Routes**: 
  - `GET /api/tradingview/signals` - List all signals
  - `GET /api/tradingview/signals/stats` - Get statistics
  - `GET /api/tradingview/config` - Get setup instructions
  - `DELETE /api/tradingview/signals/:id` - Delete a signal

### 2. Restart Backend

```bash
cd /Users/ssr/Projects/WorkingBot/webui/backend
pkill -f backend_api.py
python backend_api.py &
```

### 3. TradingView Alert Configuration

#### Step 1: Create Your Pine Script Strategy

Here's a simple example with RSI:

```pinescript
//@version=5
indicator("Trading Signals", overlay=true)

// Your strategy logic
rsiValue = ta.rsi(close, 14)
buySignal = ta.crossover(rsiValue, 30)
sellSignal = ta.crossunder(rsiValue, 70)

// Plot signals on chart
plotshape(buySignal, title="Buy", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small)
plotshape(sellSignal, title="Sell", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small)

// Buy Alert
if (buySignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "buy", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(time) + '", "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed above 30", "metadata": {"rsi": ' + str.tostring(rsiValue) + '}}', alert.freq_once_per_bar)

// Sell Alert  
if (sellSignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "sell", "price": ' + str.tostring(close) + ', "timestamp": "' + str.tostring(time) + '", "strategy": "RSI_Strategy", "timeframe": "' + timeframe.period + '", "message": "RSI crossed below 70", "metadata": {"rsi": ' + str.tostring(rsiValue) + '}}', alert.freq_once_per_bar)
```

#### Step 2: Set Up TradingView Alert

1. **Open TradingView** and apply your Pine Script indicator/strategy
2. **Click the Alert button** (clock icon) in the toolbar
3. **Configure the alert**:
   - **Condition**: Select your script and condition
   - **Alert name**: "Buy Signal" or "Sell Signal"
   - **Message**: Leave as is (the alert() function in Pine Script sets this)
   - **Webhook URL**: `http://your-server-url:5555/api/tradingview/webhook`
   
   **Important**: Replace `your-server-url` with:
   - **Local testing**: `localhost` or `127.0.0.1`
   - **Public server**: Your server's public IP or domain
   - **If using ngrok**: `https://your-ngrok-url.ngrok.io` (see below)

4. **Click Create**

### 4. Exposing Your Local Server (For Testing)

If you're testing locally and want TradingView to reach your server:

#### Option A: Using ngrok (Recommended for Testing)

```bash
# Install ngrok (if not installed)
brew install ngrok

# Start ngrok
ngrok http 5555
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and use it in TradingView:
```
https://abc123.ngrok.io/api/tradingview/webhook
```

#### Option B: Public Server

If you have a VPS or cloud server:
```
http://your-domain.com:5555/api/tradingview/webhook
```

**Security Note**: In production, use HTTPS and consider adding webhook signature verification.

### 5. Test the Integration

#### Method 1: Manual Test with curl

```bash
curl -X POST http://localhost:5555/api/tradingview/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "action": "buy",
    "price": 50000.00,
    "strategy": "RSI_Strategy",
    "timeframe": "15m",
    "message": "Test buy signal",
    "metadata": {
      "rsi": 25.5
    }
  }'
```

#### Method 2: From TradingView

Trigger your strategy condition on a chart and check if the signal appears in your WebUI.

### 6. View Signals in WebUI

Access the TradingView Signals panel:
```
http://localhost:3000/tradingview-signals
```

Or integrate the component into your existing UI:

```jsx
import TradingViewSignals from './components/TradingViewSignals';

// In your main component or routing
<Route path="/tradingview-signals" element={<TradingViewSignals />} />
```

## 📊 JSON Payload Format

Your TradingView alerts should send JSON in this format:

```json
{
  "symbol": "BTCUSD",           // Required: Trading symbol
  "action": "buy",               // Required: buy, sell, long, short, close
  "price": 50000.00,             // Required: Current price
  "timestamp": "2026-02-03T10:30:00Z",  // Optional: Alert timestamp
  "strategy": "RSI_Strategy",    // Optional: Strategy name
  "timeframe": "15m",            // Optional: Chart timeframe
  "message": "Strong buy signal", // Optional: Signal description
  "metadata": {                  // Optional: Additional data
    "rsi": 25.5,
    "volume": 1234.56,
    "macd": -10.5
  }
}
```

## 🔧 Advanced: Auto-Trading

To automatically execute trades based on TradingView signals, you can extend the webhook handler:

```python
# In webui/backend/routes/tradingview_webhook.py

@tradingview_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    # ... existing code ...
    
    # Store signal in database
    signal = TradingViewSignalsDB.create_signal(...)
    
    # Optional: Auto-execute trades
    if should_auto_execute(signal):
        execute_trade(signal)
    
    return jsonify({...})

def should_auto_execute(signal):
    """Determine if signal should trigger auto-trade"""
    # Add your logic here:
    # - Check if auto-trading is enabled
    # - Verify signal meets criteria
    # - Check risk limits
    return False  # Disabled by default for safety

def execute_trade(signal):
    """Execute trade based on signal"""
    # Your trading logic here
    # - Calculate position size
    # - Place order via exchange API
    # - Record execution in signal_executions table
    pass
```

## 📱 Webhook Security (Optional)

For production, add webhook signature verification:

1. **Set a webhook secret** in your environment:
```bash
export TRADINGVIEW_WEBHOOK_SECRET="your-secret-key"
```

2. **Update the webhook handler** to verify signatures:
```python
# In tradingview_webhook.py
WEBHOOK_SECRET = os.getenv('TRADINGVIEW_WEBHOOK_SECRET')
```

3. **In TradingView**, add the secret to your webhook URL:
```
https://your-server.com/api/tradingview/webhook?secret=your-secret-key
```

## 🔍 Monitoring & Analytics

### View Signal Statistics

```bash
curl http://localhost:5555/api/tradingview/signals/stats
```

Response:
```json
{
  "success": true,
  "stats": {
    "total_signals": 150,
    "by_action": {"buy": 75, "sell": 75},
    "by_symbol": {"BTCUSD": 100, "ETHUSD": 50},
    "last_24h": 25,
    "processed": 100,
    "unprocessed": 50
  }
}
```

### Filter Signals

```bash
# Get only buy signals for BTCUSD
curl "http://localhost:5555/api/tradingview/signals?action=buy&symbol=BTCUSD&limit=10"

# Get signals from specific strategy
curl "http://localhost:5555/api/tradingview/signals?strategy=RSI_Strategy"
```

## 📝 Pine Script Templates

### Template 1: Moving Average Crossover

```pinescript
//@version=5
indicator("MA Crossover Signals", overlay=true)

// Moving averages
fastMA = ta.sma(close, 9)
slowMA = ta.sma(close, 21)

// Signals
buySignal = ta.crossover(fastMA, slowMA)
sellSignal = ta.crossunder(fastMA, slowMA)

// Plot
plot(fastMA, color=color.blue, title="Fast MA")
plot(slowMA, color=color.red, title="Slow MA")
plotshape(buySignal, title="Buy", style=shape.triangleup, location=location.belowbar, color=color.green)
plotshape(sellSignal, title="Sell", style=shape.triangledown, location=location.abovebar, color=color.red)

// Alerts
if (buySignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "buy", "price": ' + str.tostring(close) + ', "strategy": "MA_Crossover", "timeframe": "' + timeframe.period + '", "message": "Fast MA crossed above Slow MA"}', alert.freq_once_per_bar)

if (sellSignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "sell", "price": ' + str.tostring(close) + ', "strategy": "MA_Crossover", "timeframe": "' + timeframe.period + '", "message": "Fast MA crossed below Slow MA"}', alert.freq_once_per_bar)
```

### Template 2: Support/Resistance Breakout

```pinescript
//@version=5
indicator("Breakout Signals", overlay=true)

// Calculate support/resistance
length = 20
resistance = ta.highest(high, length)
support = ta.lowest(low, length)

// Signals
buySignal = ta.crossover(close, resistance)
sellSignal = ta.crossunder(close, support)

// Plot
plot(resistance, color=color.red, title="Resistance")
plot(support, color=color.green, title="Support")
plotshape(buySignal, title="Breakout", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.large)
plotshape(sellSignal, title="Breakdown", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.large)

// Alerts
if (buySignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "buy", "price": ' + str.tostring(close) + ', "strategy": "Breakout", "timeframe": "' + timeframe.period + '", "message": "Price broke above resistance", "metadata": {"resistance": ' + str.tostring(resistance) + '}}', alert.freq_once_per_bar)

if (sellSignal)
    alert('{"symbol": "' + syminfo.ticker + '", "action": "sell", "price": ' + str.tostring(close) + ', "strategy": "Breakdown", "timeframe": "' + timeframe.period + '", "message": "Price broke below support", "metadata": {"support": ' + str.tostring(support) + '}}', alert.freq_once_per_bar)
```

## 🐛 Troubleshooting

### Signals Not Appearing?

1. **Check webhook URL** is correct and accessible
2. **Verify backend is running**: `curl http://localhost:5555/api/tradingview/config`
3. **Check logs**: `tail -f ~/Projects/WorkingBot/logs/launchagent_webui_error.log`
4. **Test manually** with curl command above
5. **Check ngrok** (if using): Make sure it's still running

### Invalid JSON Error?

Make sure your Pine Script alert message is valid JSON. Common issues:
- Missing quotes around strings
- Unescaped quotes in message text
- Invalid number formats

### Webhook Timeout?

- Ensure your server is accessible from the internet
- Check firewall rules
- Verify port 5555 is open

## 🚀 Next Steps

1. ✅ **Test the integration** with manual curl requests
2. ✅ **Configure TradingView alerts** with your Pine Script
3. ✅ **Monitor signals** in the WebUI
4. ⚠️ **Implement auto-trading** (optional, be cautious!)
5. 📊 **Analyze signal performance** over time

## 📚 Resources

- [TradingView Webhooks Documentation](https://www.tradingview.com/support/solutions/43000529348-webhook-alerts/)
- [Pine Script Documentation](https://www.tradingview.com/pine-script-docs/)
- [Ngrok Documentation](https://ngrok.com/docs)

---

**Need Help?** Check the logs or test with curl commands to debug connection issues.
