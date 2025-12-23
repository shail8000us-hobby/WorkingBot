# Standalone Liquidation Monitor for Delta Exchange

A production-ready Python module that monitors liquidation risk by fetching data directly from Delta Exchange APIs.

## 🎯 Key Features

- **Direct API Integration**: Fetches all data directly from Delta Exchange REST APIs
- **No Bot Dependencies**: Completely independent of local bot memory or state files
- **Real-time Monitoring**: Configurable refresh interval (default: 3 seconds)
- **Comprehensive Risk Analysis**: Calculates margin utilization, liquidation distance, and position risks
- **Alert System**: Warns when positions approach liquidation threshold
- **Production Ready**: Proper error handling, logging, and authentication

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements_liquidation_monitor.txt
```

### 2. Configure API Credentials
Create a `.env` file with your Delta Exchange API credentials:
```bash
cp liquidation_monitor.env.example .env
# Edit .env with your actual API credentials
```

### 3. Run the Monitor
```bash
python liquidation_monitor.py
```

## 📊 What It Monitors

### Account Level
- Total Balance
- Available Balance  
- Blocked Balance
- Maintenance Margin

### Position Level
- Product ID & Symbol
- Position Size & Side (Long/Short)
- Entry Price & Mark Price
- Liquidation Price
- Unrealized PnL
- Margin Used

### Risk Metrics
- **Margin Utilization**: Percentage of total balance used as margin
- **Liquidation Distance**: How far from liquidation (formula: ((Available / MM) - 1) × 100)
- **High Risk Positions**: Positions within 5% of liquidation price

## 🔧 Configuration

### Environment Variables
- `DELTA_API_KEY`: Your Delta Exchange API key
- `DELTA_API_SECRET`: Your Delta Exchange API secret
- Alternative: `LIVE_DELTA_API_KEY` and `LIVE_DELTA_API_SECRET`

### Monitor Settings
Edit the `LiquidationMonitor` initialization in `main()`:
```python
monitor = LiquidationMonitor(
    api_key=api_key,
    api_secret=api_secret,
    refresh_interval=3  # Seconds between updates
)
```

### Risk Thresholds
Modify the `liquidation_threshold` in the `LiquidationMonitor` class:
```python
self.liquidation_threshold = 5.0  # Alert when within 5% of liquidation
```

## 📈 Sample Output

```
================================================================================
📊 LIQUIDATION MONITOR REPORT - 2024-01-15 14:30:25
================================================================================

💰 ACCOUNT SUMMARY:
   Total Balance:     ₹1,25,000.00
   Available:         ₹85,000.00
   Blocked:           ₹40,000.00
   Maintenance Margin: ₹15,000.00

⚠️  RISK ANALYSIS:
   Margin Utilization: 32.0%
   Liquidation Distance: 466.7%
   Total Margin Used:   ₹40,000.00
   Total Unrealized PnL: ₹2,500.00
   Overall Risk:       🟢 SAFE

📈 POSITIONS SUMMARY (2 positions):
   📈 BTCUSD LONG: Size=0.1500, Mark=₹4,25,000.00, PnL=₹1,500.00, Margin=₹25,000.00
      💀 Liquidation: ₹3,80,000.00
   📉 ETHUSD SHORT: Size=-2.5000, Mark=₹2,15,000.00, PnL=₹1,000.00, Margin=₹15,000.00
      💀 Liquidation: ₹2,25,000.00

✅ No high-risk positions detected
================================================================================
```

## 🚨 Alert Conditions

The monitor will generate alerts for:

1. **High Risk Positions**: Any position within 5% of liquidation price
2. **Low Liquidation Distance**: Overall account liquidation distance < 30%
3. **API Failures**: Connection or authentication issues

## 🔒 Security

- API credentials loaded from environment variables or `.env` file
- No hardcoded secrets
- HMAC-SHA256 authentication for all API requests
- Secure request signing following Delta Exchange specifications

## 🛠️ API Endpoints Used

- `GET /v2/positions` - Fetch all open positions
- `GET /v2/wallet/balances` - Fetch account balance information

## 📝 Logging

The monitor creates detailed logs in:
- **Console**: Real-time status updates
- **File**: `liquidation_monitor.log` for persistent logging

Log levels:
- `INFO`: Normal operations and status updates
- `WARNING`: High-risk positions detected
- `ERROR`: API failures or data parsing issues
- `CRITICAL`: Critical liquidation risks or system failures

## 🔧 Troubleshooting

### Common Issues

1. **"API credentials not found"**
   - Ensure `.env` file exists with correct credentials
   - Check environment variable names match exactly

2. **"API request failed"**
   - Verify API key and secret are correct
   - Check internet connection
   - Ensure API key has required permissions

3. **"No balance data received"**
   - Account might have zero balance
   - API endpoint might be temporarily unavailable

### Debug Mode
Enable debug logging by modifying the logging level:
```python
logging.basicConfig(level=logging.DEBUG, ...)
```

## 📋 Requirements

- Python 3.7+
- `requests` library for HTTP requests
- `python-dotenv` for environment variable loading (optional)

## 🎯 Use Cases

- **Live Trading Monitoring**: Real-time liquidation risk assessment
- **Portfolio Management**: Track margin utilization across positions
- **Risk Management**: Early warning system for liquidation events
- **Compliance**: Audit trail of position and margin data
- **Integration**: Use as a standalone service for other trading systems

## 🔄 Integration

This monitor is designed to be completely independent but can be integrated with other systems by:

1. **Importing the classes**: Use `LiquidationMonitor` in other Python applications
2. **API responses**: Parse the structured data returned by fetch methods
3. **Log parsing**: Process the log files for external monitoring systems
4. **Custom alerts**: Modify the alerting logic for specific requirements

---

**⚠️ Important**: This monitor treats Delta Exchange as the single source of truth. It does not read from any local bot memory, cache files, or state JSON files. All data is fetched fresh from Delta Exchange APIs on every cycle.
