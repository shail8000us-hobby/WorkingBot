# WorkingBot Observability Module

A completely standalone, zero-invasion observability system for WorkingBot.

## Architecture

```
observability/
├── __init__.py              # Main package entry
├── start.py                 # Quick start launcher
├── ecosystem.config.js      # PM2 configuration
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuration dataclass
│   └── prometheus.yml       # Prometheus scrape config
├── metrics/
│   ├── __init__.py
│   ├── definitions.py       # 80+ Prometheus metric definitions
│   ├── collectors.py        # Data collectors (file-based, no code invasion)
│   └── exporters.py         # Prometheus format exporter
├── server/
│   ├── __init__.py
│   └── metrics_server.py    # Standalone Flask server (port 9091)
└── dashboards/
    ├── trading_performance.json
    ├── system_health.json
    ├── risk_management.json
    └── options_analytics.json
```

## Key Design Principles

1. **Zero Code Invasion** - Does NOT modify any existing bot code
2. **File-Based Collection** - Reads from Guardian health files, bot state files
3. **Standalone Server** - Runs on port 9091 (separate from WebUI on 5555)
4. **PM2 Compatible** - Can be managed alongside other bot processes

## Quick Start

### 1. Install Dependencies

```bash
pip install prometheus-client flask psutil
```

### 2. Start Metrics Server

**Option A: Direct Python**
```bash
cd /Users/ssr/Projects/WorkingBot
python3 observability/start.py
```

**Option B: PM2**
```bash
pm2 start observability/ecosystem.config.js
```

### 3. Verify Metrics

```bash
curl http://localhost:9091/metrics
curl http://localhost:9091/health
```

## Setting Up Prometheus

### 1. Install Prometheus

```bash
# macOS
brew install prometheus

# Or download from https://prometheus.io/download/
```

### 2. Configure Prometheus

Copy the provided config:
```bash
cp observability/config/prometheus.yml /usr/local/etc/prometheus.yml
```

Or add to existing prometheus.yml:
```yaml
scrape_configs:
  - job_name: 'workingbot'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9091']
```

### 3. Start Prometheus

```bash
prometheus --config.file=/usr/local/etc/prometheus.yml
```

Access at: http://localhost:9090

## Setting Up Grafana

### 1. Install Grafana

```bash
# macOS
brew install grafana

# Start service
brew services start grafana
```

### 2. Access Grafana

Open http://localhost:3000 (default login: admin/admin)

### 3. Add Prometheus Data Source

1. Go to Configuration → Data Sources
2. Add data source → Prometheus
3. URL: `http://localhost:9090`
4. Click "Save & Test"

### 4. Import Dashboards

1. Go to Dashboards → Import
2. Upload JSON files from `observability/dashboards/`:
   - `trading_performance.json` - P&L, positions, orders
   - `system_health.json` - CPU, memory, API latency
   - `risk_management.json` - Guardian signal, risk levels
   - `options_analytics.json` - Greeks, IV, premium

## Available Metrics

### Trading Metrics
- `gridbot_unrealized_pnl_usd` - Current unrealized P&L
- `gridbot_daily_pnl_usd` - Daily realized P&L
- `gridbot_open_positions_count` - Number of open positions
- `gridbot_orders_placed_total` - Total orders placed (counter)
- `gridbot_orders_filled_total` - Total orders filled (counter)
- `gridbot_current_price_usd` - Current BTC price

### Guardian/Risk Metrics
- `gridbot_guardian_signal` - Guardian GO/STOP signal (1/0)
- `gridbot_guardian_risk_level` - Current risk level (0-100)
- `gridbot_total_loss_inr` - Total cumulative loss
- `gridbot_daily_loss_inr` - Daily loss amount
- `gridbot_liquidation_distance_percent` - Distance to liquidation

### System Metrics
- `gridbot_system_cpu_percent` - CPU usage
- `gridbot_system_memory_percent` - Memory usage
- `gridbot_system_disk_percent` - Disk usage
- `gridbot_bot_uptime_seconds` - Bot uptime
- `gridbot_bot_memory_mb` - Bot process memory

### API Metrics
- `gridbot_api_call_duration_seconds` - API latency histogram
- `gridbot_api_rate_limit_hits_total` - Rate limit hits
- `gridbot_api_429_errors_total` - 429 errors count

### Options Metrics (if enabled)
- `gridbot_options_delta` - Portfolio delta
- `gridbot_options_gamma` - Portfolio gamma
- `gridbot_options_theta` - Portfolio theta
- `gridbot_options_vega` - Portfolio vega
- `gridbot_options_implied_volatility_percent` - IV

## Data Sources

The collector reads from these files (no code modification needed):

| Data | Source File |
|------|-------------|
| Guardian Signal | `data/guardian_health.json` |
| Risk Levels | `data/guardian_health.json` |
| Bot State | `data/runtime_state.json` |
| Trading Data | `data/runtime_state.json` |
| System Metrics | `psutil` library |
| Process Info | `pm2 jlist` command |

## Troubleshooting

### Metrics server won't start
```bash
# Check if port is in use
lsof -i :9091

# Kill existing process
kill $(lsof -t -i :9091)
```

### No data in Grafana
1. Verify metrics server: `curl localhost:9091/metrics`
2. Check Prometheus targets: http://localhost:9090/targets
3. Ensure Grafana data source is configured correctly

### Missing Guardian metrics
- Ensure Guardian is running and writing to `data/guardian_health.json`
- Check file permissions

## Integration with Existing Bot

This module requires **ZERO** changes to existing code. It:

1. Reads from existing health/state files
2. Runs as a separate process
3. Uses a different port (9091 vs 5555)
4. Can be started/stopped independently

To start everything together with PM2, add to your main ecosystem:
```javascript
// In ecosystem.config.js
{
  name: 'metrics-server',
  script: 'observability/server/metrics_server.py',
  interpreter: 'python3'
}
```

## Alerting

### Prometheus Alerts (alertmanager)

Create `alerts.yml`:
```yaml
groups:
- name: workingbot
  rules:
  - alert: GuardianStop
    expr: gridbot_guardian_signal == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: Guardian signal is STOP

  - alert: HighRiskLevel
    expr: gridbot_guardian_risk_level > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: Risk level above 80%
```

### Grafana Alerts

1. Open any dashboard panel
2. Click "Alert" tab
3. Configure threshold and notification channel
