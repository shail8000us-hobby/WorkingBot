# Maximum Loss Manager - Complete Documentation

## 🎯 Overview

Enterprise-grade automatic position protection system for Delta Exchange options trading. Monitors positions in real-time and automatically closes them when losses exceed configured limits.

## ✨ Features

### Core Features
- ✅ **Per-Strike Max Loss**: Set individual loss limits for each option position
- ✅ **Per-Expiry Max Loss**: Set combined loss limits for all positions of an expiry
- ✅ **Real-Time Monitoring**: Checks positions every 5 seconds (configurable)
- ✅ **Automatic Position Closing**: Market orders with `reduce_only=True`
- ✅ **Warning System**: Alerts at 80% of max loss threshold

### Production Features
- ✅ **Thread-Safe Caching**: Prevents race conditions with proper locking
- ✅ **API Rate Limiting**: Conservative 60 calls/minute (Delta Exchange: 10,000 units/5min)
- ✅ **Retry Logic**: 3 attempts with exponential backoff (2^n seconds)
- ✅ **Position Validation**: Checks existence and size before closing
- ✅ **Comprehensive Metrics**: 8 key performance indicators
- ✅ **Configuration File**: JSON-based settings management
- ✅ **WebSocket Support**: Real-time streaming (optional, requires `websockets`)
- ✅ **Delta Exchange Optimized**: Proper symbol validation, reduce_only, correct sides

## 📋 Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [API Reference](#api-reference)
5. [Usage Examples](#usage-examples)
6. [Monitoring & Metrics](#monitoring--metrics)
7. [WebSocket Mode](#websocket-mode)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

## 🚀 Installation

### Prerequisites
```bash
# Core dependencies (already included)
pip install flask sqlite3

# Optional: WebSocket support
pip install websockets
```

### Database Initialization
The SQLite database is automatically created at:
```
data/options_max_loss.db
```

## ⚡ Quick Start

### 1. Set Max Loss Limit

**Per-Strike (Individual Position):**
```bash
curl -X POST http://localhost:5555/api/options/max-loss/strike/set \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "C-BTC-95000-170126",
    "max_loss": 0.50
  }'
```

**Per-Expiry (All Positions of Expiry):**
```bash
curl -X POST http://localhost:5555/api/options/max-loss/expiry/set \
  -H "Content-Type: application/json" \
  -d '{
    "expiry_code": "170126",
    "max_loss": 2.0
  }'
```

### 2. Check Monitor Status

```bash
curl http://localhost:5555/api/options/max-loss/monitor/status
```

**Response:**
```json
{
  "success": true,
  "status": {
    "running": true,
    "check_count": 245,
    "check_interval": 5.0,
    "warning_threshold": 0.8,
    "mode": "real_time"
  }
}
```

### 3. View Metrics

```bash
curl http://localhost:5555/api/options/max-loss/monitor/metrics
```

**Response:**
```json
{
  "success": true,
  "metrics": {
    "total_checks": 245,
    "total_breaches": 2,
    "total_warnings": 5,
    "positions_closed": 2,
    "api_errors": 0,
    "failed_closes": 0,
    "retried_closes": 1,
    "last_breach_time": "2026-01-16T17:30:45.123456"
  },
  "status": { ... },
  "cache_info": {
    "cached": true,
    "cache_age": 2.3
  }
}
```

## ⚙️ Configuration

### Config File: `max_loss_config.json`

```json
{
  "max_loss_monitor": {
    "check_interval": 5.0,
    "warning_threshold": 0.8,
    "cache_ttl": 3.0,
    "max_calls_per_minute": 60,
    "test_mode": false,
    "max_retries": 3,
    "retry_backoff_base": 2,
    "websocket": {
      "enabled": false,
      "url": "wss://socket.india.delta.exchange",
      "reconnect_delay": 5,
      "ping_interval": 30
    },
    "notifications": {
      "enabled": false,
      "channels": ["log"],
      "webhook_url": null,
      "telegram_bot_token": null,
      "telegram_chat_id": null
    }
  }
}
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_interval` | float | 5.0 | Seconds between position checks |
| `warning_threshold` | float | 0.8 | Warn at 80% of max loss |
| `cache_ttl` | float | 3.0 | Position cache lifetime (seconds) |
| `max_calls_per_minute` | int | 60 | API rate limit |
| `test_mode` | bool | false | Log actions without executing |
| `max_retries` | int | 3 | Retry attempts for failed closes |
| `retry_backoff_base` | int | 2 | Exponential backoff base (2^n) |

## 📚 API Reference

### Per-Strike Endpoints

#### Set Max Loss
```
POST /api/options/max-loss/strike/set
Content-Type: application/json

{
  "symbol": "C-BTC-95000-170126",
  "max_loss": 0.50
}
```

#### Get Max Loss
```
GET /api/options/max-loss/strike/get?symbol=C-BTC-95000-170126
```

#### Remove Max Loss
```
POST /api/options/max-loss/strike/remove
Content-Type: application/json

{
  "symbol": "C-BTC-95000-170126"
}
```

#### List All
```
GET /api/options/max-loss/strike/list
```

### Per-Expiry Endpoints

#### Set Max Loss
```
POST /api/options/max-loss/expiry/set
Content-Type: application/json

{
  "expiry_code": "170126",
  "max_loss": 2.0
}
```

#### Get Max Loss
```
GET /api/options/max-loss/expiry/get?expiry_code=170126
```

#### Remove Max Loss
```
POST /api/options/max-loss/expiry/remove
Content-Type: application/json

{
  "expiry_code": "170126"
}
```

#### List All
```
GET /api/options/max-loss/expiry/list
```

### Monitor Control

#### Get Status
```
GET /api/options/max-loss/monitor/status
```

#### Get Metrics
```
GET /api/options/max-loss/monitor/metrics
```

#### Check Now (Manual Trigger)
```
POST /api/options/max-loss/check-now
```

#### Get History
```
GET /api/options/max-loss/history?limit=50
```

## 💡 Usage Examples

### Example 1: Protect Individual Trade

```python
import requests

# You bought C-BTC-95000-170126 for $0.30
# Set max loss to $0.20 (66% of entry)

response = requests.post(
    'http://localhost:5555/api/options/max-loss/strike/set',
    json={
        'symbol': 'C-BTC-95000-170126',
        'max_loss': 0.20
    }
)

print(response.json())
# {"success": true, "symbol": "C-BTC-95000-170126", "max_loss": 0.2}
```

**What happens:**
- Monitor checks every 5 seconds
- At -$0.16 loss (80%): Warning logged
- At -$0.20 loss (100%): Position automatically closed via market order

### Example 2: Protect Entire Expiry

```python
import requests

# Multiple positions for 17/01/26 expiry
# Total capital allocated: $5.00
# Set combined max loss to $2.00

response = requests.post(
    'http://localhost:5555/api/options/max-loss/expiry/set',
    json={
        'expiry_code': '170126',
        'max_loss': 2.0
    }
)

print(response.json())
# {"success": true, "expiry_code": "170126", "max_loss": 2.0}
```

**What happens:**
- Monitor sums PnL across ALL positions with 170126 expiry
- If combined loss >= $2.00: ALL positions of that expiry closed

### Example 3: Test Mode (Dry Run)

```json
{
  "max_loss_monitor": {
    "test_mode": true
  }
}
```

**Logs show:**
```
🧪 TEST MODE: Would close C-BTC-95000-170126 - loss $0.25
```

Position is NOT actually closed. Use this to:
- Test configuration
- Validate limits before production
- Debug monitoring logic

## 📊 Monitoring & Metrics

### Key Metrics

| Metric | Description |
|--------|-------------|
| `total_checks` | Number of position checks performed |
| `total_breaches` | Max loss limits exceeded |
| `total_warnings` | 80% threshold warnings |
| `positions_closed` | Successfully closed positions |
| `api_errors` | Delta Exchange API failures |
| `failed_closes` | Failed position closes (after retries) |
| `retried_closes` | Retry attempts made |
| `last_breach_time` | Timestamp of last breach |

### Monitoring Dashboard (Future)

```bash
# Watch logs in real-time
tail -f webui/backend/logs/backend.log | grep "MAX LOSS"
```

**Sample Output:**
```
[2026-01-16 17:30:42] ⚠️ WARNING: C-BTC-95000-170126 at 85.0% of max loss ($0.17 / $0.20)
[2026-01-16 17:30:47] 🛑 MAX LOSS BREACH: C-BTC-95000-170126 loss $0.21 >= limit $0.20 - AUTO CLOSING
[2026-01-16 17:30:48] 📊 Position details: sell 1 contracts (reduce_only=True)
[2026-01-16 17:30:49] ✅ Successfully closed C-BTC-95000-170126
```

## 🌐 WebSocket Mode

### Enable WebSocket Monitoring

1. **Install websockets:**
```bash
pip install websockets
```

2. **Update config:**
```json
{
  "max_loss_monitor": {
    "websocket": {
      "enabled": true,
      "url": "wss://socket.india.delta.exchange"
    }
  }
}
```

3. **Initialize WebSocket Monitor:**
```python
from options_strategy.max_loss_manager import MaxLossWebSocketMonitor, get_max_loss_manager

manager = get_max_loss_manager()
ws_monitor = MaxLossWebSocketMonitor(api_client, manager)

# In async context
await ws_monitor.connect()
await ws_monitor.start_monitoring()
```

### Benefits of WebSocket Mode

| Feature | REST Polling | WebSocket |
|---------|--------------|-----------|
| Latency | ~5 seconds | <100ms |
| API Calls | 12/minute | ~0/minute |
| Rate Limits | Risk of hitting | Near zero |
| Scalability | Limited | Excellent |

## 🔧 Troubleshooting

### Issue: Monitor Not Running

**Check Status:**
```bash
curl http://localhost:5555/api/options/max-loss/monitor/status
```

**Expected:**
```json
{"status": {"running": true}}
```

**If false:** Monitor not initialized. Check backend startup logs.

### Issue: High API Errors

**Check Metrics:**
```bash
curl http://localhost:5555/api/options/max-loss/monitor/metrics
```

**If `api_errors > 10`:**
1. Check Delta Exchange API status
2. Verify API credentials
3. Reduce `check_interval` (increase to 10s)
4. Check rate limiting: `max_calls_per_minute`

### Issue: Failed Closes

**Check Logs:**
```bash
tail -100 webui/backend/logs/backend.log | grep "Failed to close"
```

**Common Causes:**
- Position already closed
- Insufficient balance
- Market halted
- API rate limit

**Solution:**
- Increase `max_retries` to 5
- Increase `retry_backoff_base` to 3
- Enable test mode to debug

### Issue: Position Closed Unexpectedly

**Check History:**
```bash
curl http://localhost:5555/api/options/max-loss/history?limit=10
```

**Verify:**
1. Was max loss limit set for this symbol?
2. Did PnL actually exceed the limit?
3. Check `last_breach_time` in metrics

## 🎯 Best Practices

### 1. Setting Limits

**Conservative Approach:**
```
Max Loss = 50-70% of Premium Paid
```

**Example:**
- Entry: $0.40
- Max Loss: $0.28 (70% of $0.40)

**Aggressive Approach:**
```
Max Loss = 100-150% of Premium Paid
```

### 2. Per-Strike vs Per-Expiry

**Use Per-Strike When:**
- Trading individual positions
- Different risk tolerance per trade
- Want granular control

**Use Per-Expiry When:**
- Trading spreads/combinations
- Want portfolio-level protection
- Multiple positions same expiry

### 3. Warning Threshold

**Default: 80%** is optimal for most traders.

- Lower (60%): More warnings, more noise
- Higher (90%): Less warnings, may miss opportunities to exit earlier

### 4. Check Interval

**Default: 5 seconds** balances responsiveness and API usage.

- Lower (2s): More responsive, higher API usage
- Higher (10s): Less API usage, slower response

**Rule of Thumb:**
```
Check Interval = Expected Move Time / 5
```

If price moves 10% in 30 seconds → use 6s interval.

### 5. Test Before Production

```json
{
  "test_mode": true,
  "check_interval": 2.0
}
```

Run for 1 hour in test mode to validate:
- ✅ Limits trigger correctly
- ✅ No false positives
- ✅ API errors < 1%
- ✅ Monitoring is stable

Then switch to production:
```json
{
  "test_mode": false
}
```

## 📖 Advanced Usage

### Custom Implementation

```python
from options_strategy.max_loss_manager import (
    MaxLossManager,
    MaxLossMonitor,
    init_max_loss_monitoring
)

# Initialize with custom config
monitor = init_max_loss_monitoring(
    api_client=my_api_client,
    auto_start=True,
    config_path='custom_config.json'
)

# Custom check logic
def my_custom_check():
    positions = api_client.get_positions()
    for pos in positions:
        # Your custom logic
        pass

# Access metrics programmatically
metrics = monitor.get_metrics()
print(f"Breaches: {metrics['metrics']['total_breaches']}")
```

### Integration with Alerts

```python
import requests

def send_alert(message):
    # Telegram
    requests.post(
        f'https://api.telegram.org/bot{TOKEN}/sendMessage',
        json={'chat_id': CHAT_ID, 'text': message}
    )
    
    # Webhook
    requests.post(
        WEBHOOK_URL,
        json={'event': 'max_loss_breach', 'message': message}
    )

# Monitor logs and send alerts
# (This would be implemented in the notification system)
```

## 🔒 Security Considerations

1. **Database Encryption**: SQLite database is unencrypted. For production with sensitive data, consider encrypting `data/options_max_loss.db`.

2. **API Authentication**: All API endpoints should be behind authentication (implement in Flask blueprint).

3. **Rate Limiting**: Built-in rate limiting protects against API abuse.

4. **Audit Trail**: All max loss triggers logged to `max_loss_history` table.

## 📄 License & Support

- **Created:** January 16, 2026
- **Version:** 1.0.0
- **Status:** Production Ready ✅

## 🙏 Acknowledgments

- Delta Exchange API Documentation
- Your trading analysis that led to this implementation
- Production testing and validation

---

**🛡️ Trade with Confidence. Your positions are protected.**
