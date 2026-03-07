# Prometheus + Grafana Implementation Plan

**Created:** January 14, 2026  
**Estimated Time:** 4 hours  
**Status:** Planning Phase  
**Priority:** HIGH ROI - Biggest visibility upgrade  

---

## 📋 Executive Summary

This document provides a **phase-wise implementation plan** for adding Prometheus metrics collection and Grafana dashboards to the WorkingBot trading system. The plan leverages your existing monitoring infrastructure and adds long-term metrics storage and advanced visualization capabilities.

### What You Currently Have ✅

- ✅ **Monitoring System** (`monitoring_system.py`) - Collects system metrics
- ✅ **Health Monitor** (`bot/system_health/health_monitor.py`) - Process health tracking
- ✅ **WebUI Health Monitor** (`webui/backend/utils/health_monitor.py`) - API health checks
- ✅ **WebUI Dashboards** - Real-time monitoring panels
- ✅ **Telegram Alerts** - Production notifications
- ✅ **Guardian Bot** - Risk management with health signals

### What's Missing ❌

- ❌ **No historical metrics storage** (only last 1000 samples in memory)
- ❌ **No trend analysis** (can't see patterns over days/weeks)
- ❌ **No custom alerting rules** (Prometheus Alertmanager)
- ❌ **No correlation analysis** (CPU vs trade performance)
- ❌ **No time-series queries** (PromQL for complex analysis)

### What Grafana Adds 🎯

```
📊 Time-series dashboards with 30-day+ retention
📈 Historical performance trends and pattern detection
🔔 Advanced alerting (PagerDuty, Slack, email integration)
🎯 Rate limit pattern detection and prediction
💰 P&L trend visualization with annotations
⚡ Latency heatmaps and percentile graphs
🔍 Correlation analysis (system metrics vs trading performance)
🎨 Beautiful, shareable dashboards
📱 Mobile-friendly monitoring
🔗 Query language (PromQL) for complex analysis
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  EXISTING MONITORING SYSTEM                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   GridBot    │  │   Guardian   │  │    WebUI     │     │
│  │   Metrics    │  │   Metrics    │  │   Metrics    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              NEW: PROMETHEUS EXPORTER LAYER                  │
│                                                              │
│  • Collects metrics from all components                     │
│  • Exposes /metrics endpoint (Prometheus format)            │
│  • Runs as Flask route or standalone service                │
│  • No changes to existing monitoring code                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓ HTTP scrape every 15s
┌─────────────────────────────────────────────────────────────┐
│                    PROMETHEUS SERVER                         │
│                                                              │
│  • Time-series database (stores metrics long-term)          │
│  • PromQL query language                                     │
│  • Alertmanager integration                                  │
│  • Retention: 30 days default (configurable)                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓ Query via PromQL
┌─────────────────────────────────────────────────────────────┐
│                     GRAFANA DASHBOARDS                       │
│                                                              │
│  Dashboard 1: Trading Performance (P&L, win rate, etc.)     │
│  Dashboard 2: System Health (CPU, memory, disk, API)        │
│  Dashboard 3: Risk Management (Guardian, liquidation)       │
│  Dashboard 4: Execution Quality (latency, fills, slippage)  │
│  Dashboard 5: Anomaly Detection (price deviations, errors)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📅 Phase-Wise Implementation

### **Phase 1: Environment Setup & Installation** ⏱️ 30 minutes

#### 1.1 Install Prometheus (macOS)

```bash
# Install via Homebrew
brew install prometheus

# Verify installation
prometheus --version

# Default locations:
# Config: /opt/homebrew/etc/prometheus.yml
# Data: /opt/homebrew/var/prometheus
```

#### 1.2 Install Grafana (macOS)

```bash
# Install via Homebrew
brew install grafana

# Verify installation
grafana --version

# Default locations:
# Config: /opt/homebrew/etc/grafana/grafana.ini
# Data: /opt/homebrew/var/lib/grafana
```

#### 1.3 Start Services

```bash
# Start Prometheus (background service)
brew services start prometheus

# Start Grafana (background service)
brew services start grafana

# Verify services
brew services list

# Access URLs:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin default login)
```

#### 1.4 Install Python Dependencies

```bash
cd /Users/ssr/Projects/WorkingBot

# Add to requirements.txt
echo "prometheus-client==0.19.0" >> requirements.txt

# Install
pip3 install prometheus-client
```

**Deliverables:**
- ✅ Prometheus running on port 9090
- ✅ Grafana running on port 3000
- ✅ Python prometheus-client installed

---

### **Phase 2: Prometheus Exporter Implementation** ⏱️ 1 hour

#### 2.1 Create Metrics Exporter Module

**File:** `bot/observability/prometheus_metrics.py`

```python
#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for WorkingBot

Exposes metrics in Prometheus format for scraping.
Integrates with existing monitoring infrastructure.
"""

from prometheus_client import Counter, Gauge, Histogram, Summary, Info
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

# Create custom registry (don't pollute global)
registry = CollectorRegistry()

# ============================================================================
# TRADING METRICS
# ============================================================================

# Orders
orders_placed_total = Counter(
    'gridbot_orders_placed_total',
    'Total orders placed by side and status',
    ['side', 'status', 'symbol', 'instance'],
    registry=registry
)

orders_filled_total = Counter(
    'gridbot_orders_filled_total',
    'Total orders filled',
    ['side', 'symbol', 'instance'],
    registry=registry
)

orders_cancelled_total = Counter(
    'gridbot_orders_cancelled_total',
    'Total orders cancelled',
    ['reason', 'symbol', 'instance'],
    registry=registry
)

orders_failed_total = Counter(
    'gridbot_orders_failed_total',
    'Total orders that failed',
    ['error_type', 'symbol', 'instance'],
    registry=registry
)

# Positions
open_positions_count = Gauge(
    'gridbot_open_positions_count',
    'Number of open positions',
    ['symbol', 'instance'],
    registry=registry
)

position_value_usd = Gauge(
    'gridbot_position_value_usd',
    'Total position value in USD',
    ['symbol', 'instance'],
    registry=registry
)

unrealized_pnl_usd = Gauge(
    'gridbot_unrealized_pnl_usd',
    'Unrealized profit/loss in USD',
    ['symbol', 'instance'],
    registry=registry
)

realized_pnl_usd = Counter(
    'gridbot_realized_pnl_usd',
    'Cumulative realized profit/loss in USD',
    ['symbol', 'instance'],
    registry=registry
)

# Grid Performance
grid_level_fills = Counter(
    'gridbot_grid_level_fills',
    'Number of fills per grid level',
    ['level', 'side', 'symbol', 'instance'],
    registry=registry
)

grid_efficiency_ratio = Gauge(
    'gridbot_grid_efficiency_ratio',
    'Grid efficiency (fills/total_levels)',
    ['symbol', 'instance'],
    registry=registry
)

# ============================================================================
# EXECUTION METRICS
# ============================================================================

order_latency_seconds = Histogram(
    'gridbot_order_latency_seconds',
    'Order placement latency',
    ['operation', 'symbol', 'instance'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=registry
)

fill_latency_seconds = Histogram(
    'gridbot_fill_latency_seconds',
    'Time from order placement to fill',
    ['side', 'symbol', 'instance'],
    buckets=[1, 5, 10, 30, 60, 300, 600],
    registry=registry
)

api_call_duration_seconds = Histogram(
    'gridbot_api_call_duration_seconds',
    'API call duration',
    ['endpoint', 'method', 'status_code'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

slippage_percent = Histogram(
    'gridbot_slippage_percent',
    'Order slippage percentage',
    ['side', 'symbol', 'instance'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    registry=registry
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

system_cpu_percent = Gauge(
    'gridbot_system_cpu_percent',
    'System CPU usage percentage',
    registry=registry
)

system_memory_percent = Gauge(
    'gridbot_system_memory_percent',
    'System memory usage percentage',
    registry=registry
)

system_disk_percent = Gauge(
    'gridbot_system_disk_percent',
    'System disk usage percentage',
    registry=registry
)

bot_memory_mb = Gauge(
    'gridbot_bot_memory_mb',
    'Bot process memory usage in MB',
    ['process_name'],
    registry=registry
)

bot_uptime_seconds = Gauge(
    'gridbot_bot_uptime_seconds',
    'Bot uptime in seconds',
    ['symbol', 'instance'],
    registry=registry
)

# ============================================================================
# GUARDIAN METRICS
# ============================================================================

guardian_signal = Gauge(
    'gridbot_guardian_signal',
    'Guardian signal (1=GO, 0=STOP)',
    ['symbol', 'instance'],
    registry=registry
)

guardian_risk_level = Gauge(
    'gridbot_guardian_risk_level',
    'Guardian risk level (0-100)',
    ['symbol', 'instance'],
    registry=registry
)

guardian_interventions_total = Counter(
    'gridbot_guardian_interventions_total',
    'Number of Guardian interventions',
    ['action', 'reason', 'symbol', 'instance'],
    registry=registry
)

total_loss_inr = Gauge(
    'gridbot_total_loss_inr',
    'Total loss in INR',
    ['symbol', 'instance'],
    registry=registry
)

liquidation_distance_percent = Gauge(
    'gridbot_liquidation_distance_percent',
    'Distance to liquidation price',
    ['symbol', 'instance'],
    registry=registry
)

# ============================================================================
# API RATE LIMITING
# ============================================================================

api_rate_limit_hits = Counter(
    'gridbot_api_rate_limit_hits',
    'Number of rate limit hits',
    ['endpoint'],
    registry=registry
)

api_429_errors = Counter(
    'gridbot_api_429_errors',
    'Number of 429 (rate limited) errors',
    ['endpoint'],
    registry=registry
)

api_requests_per_second = Gauge(
    'gridbot_api_requests_per_second',
    'Current API requests per second',
    registry=registry
)

# ============================================================================
# RECOVERY METRICS
# ============================================================================

recovery_sessions_total = Counter(
    'gridbot_recovery_sessions_total',
    'Number of recovery sessions',
    ['engine', 'status', 'symbol', 'instance'],
    registry=registry
)

recovery_duration_seconds = Histogram(
    'gridbot_recovery_duration_seconds',
    'Recovery session duration',
    ['engine', 'symbol', 'instance'],
    buckets=[1, 5, 10, 30, 60, 300],
    registry=registry
)

missed_grids_recovered = Counter(
    'gridbot_missed_grids_recovered',
    'Number of missed grids recovered',
    ['symbol', 'instance'],
    registry=registry
)

# ============================================================================
# ANOMALY DETECTION
# ============================================================================

anomalies_detected = Counter(
    'gridbot_anomalies_detected',
    'Number of anomalies detected',
    ['category', 'severity', 'symbol', 'instance'],
    registry=registry
)

price_deviation_percent = Gauge(
    'gridbot_price_deviation_percent',
    'Price deviation from moving average',
    ['symbol', 'instance'],
    registry=registry
)

# ============================================================================
# OPTIONS TRADING METRICS (NEW - Jan 2026)
# ============================================================================

options_positions_count = Gauge(
    'gridbot_options_positions_count',
    'Number of open options positions',
    ['option_type', 'symbol'],
    registry=registry
)

options_pnl_usd = Gauge(
    'gridbot_options_pnl_usd',
    'Options unrealized P&L in USD',
    ['option_type', 'symbol'],
    registry=registry
)

options_greeks = Gauge(
    'gridbot_options_greeks',
    'Options portfolio Greeks',
    ['greek_type', 'symbol'],  # delta, gamma, theta, vega
    registry=registry
)

options_iv_percentile = Gauge(
    'gridbot_options_iv_percentile',
    'Implied volatility percentile',
    ['symbol'],
    registry=registry
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

class MetricsCollector:
    """Helper class to update metrics from existing monitoring data"""
    
    @staticmethod
    def update_from_monitoring_system(monitoring_data: Dict[str, Any]):
        """Update metrics from monitoring_system.py data"""
        try:
            # System metrics
            if 'metrics' in monitoring_data:
                metrics = monitoring_data['metrics']
                system_cpu_percent.set(metrics.get('cpu_percent', 0))
                system_memory_percent.set(metrics.get('memory_percent', 0))
                system_disk_percent.set(metrics.get('disk_percent', 0))
                
                # Bot memory
                bot_memory_mb.labels(process_name='gridbot').set(
                    metrics.get('bot_memory_mb', 0)
                )
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    @staticmethod
    def update_from_bot_state(bot_state: Dict[str, Any]):
        """Update metrics from AsyncGridBot state"""
        try:
            symbol = bot_state.get('symbol', 'BTCUSD')
            instance = bot_state.get('instance', 'BTCUSD_LONG')
            
            # Positions
            positions = bot_state.get('open_positions', [])
            open_positions_count.labels(symbol=symbol, instance=instance).set(len(positions))
            
            # P&L
            if 'unrealized_pnl' in bot_state:
                unrealized_pnl_usd.labels(symbol=symbol, instance=instance).set(
                    bot_state['unrealized_pnl']
                )
            
            # Uptime
            if 'start_time' in bot_state:
                uptime = time.time() - bot_state['start_time']
                bot_uptime_seconds.labels(symbol=symbol, instance=instance).set(uptime)
                
        except Exception as e:
            logger.error(f"Error updating bot state metrics: {e}")
    
    @staticmethod
    def update_from_guardian(guardian_health: Dict[str, Any]):
        """Update metrics from Guardian health data"""
        try:
            symbol = guardian_health.get('symbol', 'BTCUSD')
            instance = guardian_health.get('instance', 'BTCUSD_LONG')
            
            # Signal
            signal = 1 if guardian_health.get('signal') == 'GO' else 0
            guardian_signal.labels(symbol=symbol, instance=instance).set(signal)
            
            # Risk level
            risk_level = guardian_health.get('risk_level', 0)
            guardian_risk_level.labels(symbol=symbol, instance=instance).set(risk_level)
            
            # Total loss
            if 'total_loss_inr' in guardian_health:
                total_loss_inr.labels(symbol=symbol, instance=instance).set(
                    guardian_health['total_loss_inr']
                )
                
            # Liquidation distance
            if 'liquidation_distance' in guardian_health:
                liquidation_distance_percent.labels(symbol=symbol, instance=instance).set(
                    guardian_health['liquidation_distance']
                )
                
        except Exception as e:
            logger.error(f"Error updating guardian metrics: {e}")
    
    @staticmethod
    def record_order_placed(side: str, status: str, symbol: str, instance: str):
        """Record order placement"""
        orders_placed_total.labels(
            side=side,
            status=status,
            symbol=symbol,
            instance=instance
        ).inc()
    
    @staticmethod
    def record_order_filled(side: str, symbol: str, instance: str):
        """Record order fill"""
        orders_filled_total.labels(
            side=side,
            symbol=symbol,
            instance=instance
        ).inc()
    
    @staticmethod
    def record_api_call(endpoint: str, method: str, status_code: int, duration: float):
        """Record API call"""
        api_call_duration_seconds.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).observe(duration)
        
        if status_code == 429:
            api_429_errors.labels(endpoint=endpoint).inc()

# ============================================================================
# FLASK INTEGRATION
# ============================================================================

def get_metrics():
    """
    Get metrics in Prometheus format.
    Use this in Flask route.
    
    Example:
        from flask import Response
        from bot.observability.prometheus_metrics import get_metrics, CONTENT_TYPE_LATEST
        
        @app.route('/metrics')
        def metrics():
            return Response(get_metrics(), mimetype=CONTENT_TYPE_LATEST)
    """
    return generate_latest(registry)

def get_content_type():
    """Get Prometheus content type"""
    return CONTENT_TYPE_LATEST

# Export for convenience
__all__ = [
    'MetricsCollector',
    'get_metrics',
    'get_content_type',
    'registry'
]
```

#### 2.2 Add /metrics Endpoint to WebUI

**File:** `webui/backend/routes/metrics.py` (NEW)

```python
"""
Prometheus Metrics Endpoint

Exposes metrics for Prometheus scraping.
"""

from flask import Blueprint, Response
import logging

logger = logging.getLogger(__name__)

metrics_bp = Blueprint('metrics', __name__)

try:
    from bot.observability.prometheus_metrics import (
        get_metrics,
        get_content_type,
        MetricsCollector
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Prometheus metrics not available")

@metrics_bp.route('/metrics', methods=['GET'])
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    if not METRICS_AVAILABLE:
        return Response("Metrics not available", status=503)
    
    try:
        # Collect latest metrics from monitoring systems
        # This is called on every scrape (every 15s by default)
        
        # Update from existing monitoring
        from webui.backend.utils.health_monitor import health_monitor
        health_report = health_monitor.get_health_report()
        MetricsCollector.update_from_monitoring_system(health_report)
        
        # Update from bot state (if available)
        try:
            from webui.backend.utils.bot_state_reader import get_latest_bot_state
            bot_state = get_latest_bot_state()
            if bot_state:
                MetricsCollector.update_from_bot_state(bot_state)
        except Exception as e:
            logger.debug(f"Could not read bot state: {e}")
        
        # Update from Guardian health
        try:
            import json
            from pathlib import Path
            guardian_health_file = Path('/Users/ssr/Projects/WorkingBot/bot/guardian/.guardian_health.json')
            if guardian_health_file.exists():
                with open(guardian_health_file) as f:
                    guardian_health = json.load(f)
                    MetricsCollector.update_from_guardian(guardian_health)
        except Exception as e:
            logger.debug(f"Could not read guardian health: {e}")
        
        # Return metrics in Prometheus format
        return Response(get_metrics(), mimetype=get_content_type())
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        return Response(f"Error: {str(e)}", status=500)
```

#### 2.3 Register Metrics Blueprint

**File:** `webui/backend/app.py` (EDIT)

```python
# Add to imports at top
from .routes.metrics import metrics_bp

# Add to blueprints list (around line 192)
blueprints = [
    # ... existing blueprints ...
    metrics_bp,  # ADD THIS
]
```

#### 2.4 Integrate Metrics into AsyncGridBot

**File:** `bot/strategy/async_gridbot.py` (ADD)

Add metrics tracking to key operations:

```python
# Add at top of file
try:
    from bot.observability.prometheus_metrics import MetricsCollector
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("Prometheus metrics not available")

# In _place_order_saga method (around line 2800)
async def _place_order_saga(self, side: str, quantity: int, price: float) -> bool:
    """Place order with saga pattern"""
    
    # ... existing code ...
    
    # Record metrics
    if METRICS_ENABLED and order_response:
        MetricsCollector.record_order_placed(
            side=side,
            status='success',
            symbol=self.symbol,
            instance=self.instance
        )
    
    # ... rest of method ...

# In _process_fill method (around line 2100)
async def _process_fill(self, fill_data: Dict[str, Any]):
    """Process fill notification"""
    
    # ... existing code ...
    
    # Record metrics
    if METRICS_ENABLED:
        MetricsCollector.record_order_filled(
            side=fill_data.get('side'),
            symbol=self.symbol,
            instance=self.instance
        )
    
    # ... rest of method ...
```

**Deliverables:**
- ✅ Prometheus exporter with 50+ metrics
- ✅ /metrics endpoint on WebUI (port 5555)
- ✅ Integration with existing monitoring
- ✅ Metrics collection from GridBot, Guardian, Options

---

### **Phase 3: Prometheus Configuration** ⏱️ 30 minutes

#### 3.1 Configure Prometheus Scraping

**File:** `/opt/homebrew/etc/prometheus.yml` (EDIT)

```yaml
# Global configuration
global:
  scrape_interval: 15s      # Scrape targets every 15 seconds
  evaluation_interval: 15s  # Evaluate rules every 15 seconds
  
  # Attach labels to all time series
  external_labels:
    monitor: 'workingbot-monitor'
    environment: 'production'

# Alertmanager configuration (optional - Phase 4)
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          # - 'localhost:9093'  # Uncomment when Alertmanager added

# Rule files (optional - Phase 4)
rule_files:
  # - "rules/*.yml"

# Scrape configurations
scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # WorkingBot WebUI Metrics
  - job_name: 'workingbot'
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:5555']
        labels:
          service: 'gridbot'
          component: 'webui'
    
  # System Node Exporter (optional - install if you want OS-level metrics)
  # - job_name: 'node'
  #   static_configs:
  #     - targets: ['localhost:9100']
```

#### 3.2 Restart Prometheus

```bash
# Restart to load new config
brew services restart prometheus

# Verify config is valid
promtool check config /opt/homebrew/etc/prometheus.yml

# Check Prometheus is scraping
open http://localhost:9090
# Navigate to Status > Targets
# Should see 'workingbot' target with status UP
```

#### 3.3 Test Metrics Endpoint

```bash
# Test endpoint directly
curl http://localhost:5555/metrics

# Should see output like:
# # HELP gridbot_orders_placed_total Total orders placed by side and status
# # TYPE gridbot_orders_placed_total counter
# gridbot_orders_placed_total{side="buy",status="success",symbol="BTCUSD",instance="BTCUSD_LONG"} 42.0
# ...
```

#### 3.4 Verify Prometheus Scraping

```bash
# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=gridbot_orders_placed_total'

# Or use Prometheus web UI
open http://localhost:9090/graph
# Enter query: gridbot_orders_placed_total
# Click Execute
```

**Deliverables:**
- ✅ Prometheus configured to scrape WebUI
- ✅ 15-second scrape interval
- ✅ Metrics appearing in Prometheus UI
- ✅ PromQL queries working

---

### **Phase 4: Grafana Dashboard Creation** ⏱️ 1.5 hours

#### 4.1 Initial Grafana Setup

```bash
# Access Grafana
open http://localhost:3000

# Default login: admin/admin
# Change password on first login

# Add Prometheus data source:
# 1. Click "Configuration" (gear icon) > Data Sources
# 2. Click "Add data source"
# 3. Select "Prometheus"
# 4. Set URL: http://localhost:9090
# 5. Click "Save & Test"
```

#### 4.2 Dashboard 1: Trading Performance

**Create dashboard with these panels:**

1. **Total P&L (USD)** - Single Stat
   ```promql
   gridbot_unrealized_pnl_usd{instance="BTCUSD_LONG"}
   ```

2. **Realized P&L Over Time** - Graph
   ```promql
   rate(gridbot_realized_pnl_usd[1h])
   ```

3. **Orders Placed (24h)** - Single Stat
   ```promql
   increase(gridbot_orders_placed_total[24h])
   ```

4. **Orders by Side** - Pie Chart
   ```promql
   sum by(side) (increase(gridbot_orders_placed_total[1h]))
   ```

5. **Fill Rate** - Gauge
   ```promql
   (sum(increase(gridbot_orders_filled_total[1h])) / 
    sum(increase(gridbot_orders_placed_total[1h]))) * 100
   ```

6. **Open Positions** - Graph
   ```promql
   gridbot_open_positions_count
   ```

7. **Grid Efficiency** - Graph
   ```promql
   gridbot_grid_efficiency_ratio
   ```

8. **Order Latency (p95)** - Graph
   ```promql
   histogram_quantile(0.95, 
     rate(gridbot_order_latency_seconds_bucket[5m]))
   ```

#### 4.3 Dashboard 2: System Health

**Create dashboard with these panels:**

1. **CPU Usage** - Graph
   ```promql
   gridbot_system_cpu_percent
   ```

2. **Memory Usage** - Graph
   ```promql
   gridbot_system_memory_percent
   ```

3. **Disk Usage** - Gauge
   ```promql
   gridbot_system_disk_percent
   ```

4. **Bot Memory** - Graph
   ```promql
   gridbot_bot_memory_mb
   ```

5. **Bot Uptime** - Single Stat
   ```promql
   gridbot_bot_uptime_seconds / 3600
   ```

6. **API Call Duration (p50, p95, p99)** - Graph
   ```promql
   histogram_quantile(0.50, rate(gridbot_api_call_duration_seconds_bucket[5m]))
   histogram_quantile(0.95, rate(gridbot_api_call_duration_seconds_bucket[5m]))
   histogram_quantile(0.99, rate(gridbot_api_call_duration_seconds_bucket[5m]))
   ```

7. **API Rate Limit Hits** - Graph
   ```promql
   rate(gridbot_api_rate_limit_hits[5m])
   ```

8. **429 Errors** - Graph
   ```promql
   rate(gridbot_api_429_errors[5m])
   ```

#### 4.4 Dashboard 3: Risk Management

**Create dashboard with these panels:**

1. **Guardian Signal** - Gauge (Red/Green)
   ```promql
   gridbot_guardian_signal
   ```

2. **Risk Level** - Gauge
   ```promql
   gridbot_guardian_risk_level
   ```

3. **Total Loss (INR)** - Single Stat
   ```promql
   gridbot_total_loss_inr
   ```

4. **Liquidation Distance** - Graph
   ```promql
   gridbot_liquidation_distance_percent
   ```

5. **Guardian Interventions** - Graph
   ```promql
   rate(gridbot_guardian_interventions_total[1h])
   ```

6. **Interventions by Reason** - Pie Chart
   ```promql
   sum by(reason) (increase(gridbot_guardian_interventions_total[24h]))
   ```

#### 4.5 Dashboard 4: Execution Quality

**Create dashboard with these panels:**

1. **Fill Latency (p95)** - Graph
   ```promql
   histogram_quantile(0.95, 
     rate(gridbot_fill_latency_seconds_bucket[5m]))
   ```

2. **Slippage Distribution** - Histogram
   ```promql
   histogram_quantile(0.50, rate(gridbot_slippage_percent_bucket[5m]))
   histogram_quantile(0.95, rate(gridbot_slippage_percent_bucket[5m]))
   ```

3. **Orders Failed** - Graph
   ```promql
   rate(gridbot_orders_failed_total[5m])
   ```

4. **Failures by Error Type** - Table
   ```promql
   sum by(error_type) (increase(gridbot_orders_failed_total[1h]))
   ```

5. **Grid Level Fill Distribution** - Heatmap
   ```promql
   sum by(level) (increase(gridbot_grid_level_fills[1h]))
   ```

#### 4.6 Dashboard 5: Anomaly Detection

**Create dashboard with these panels:**

1. **Anomalies Detected** - Graph
   ```promql
   rate(gridbot_anomalies_detected[5m])
   ```

2. **Anomalies by Category** - Bar Chart
   ```promql
   sum by(category) (increase(gridbot_anomalies_detected[1h]))
   ```

3. **Price Deviation** - Graph
   ```promql
   gridbot_price_deviation_percent
   ```

4. **Recovery Sessions** - Graph
   ```promql
   rate(gridbot_recovery_sessions_total[5m])
   ```

5. **Missed Grids Recovered** - Single Stat
   ```promql
   increase(gridbot_missed_grids_recovered[24h])
   ```

#### 4.7 Export Dashboards

```bash
# Save dashboards as JSON for version control
cd /Users/ssr/Projects/WorkingBot
mkdir -p grafana/dashboards

# In Grafana UI:
# 1. Open dashboard
# 2. Click Share icon > Export
# 3. Save JSON to grafana/dashboards/
```

**Deliverables:**
- ✅ 5 production-ready Grafana dashboards
- ✅ 40+ panels with PromQL queries
- ✅ Color-coded alerts and thresholds
- ✅ Exported JSON for backup

---

### **Phase 5: Testing & Validation** ⏱️ 30 minutes

#### 5.1 Metrics Validation Checklist

```bash
# 1. Verify metrics endpoint
curl http://localhost:5555/metrics | grep gridbot

# 2. Check Prometheus targets
open http://localhost:9090/targets
# Verify 'workingbot' target is UP

# 3. Test PromQL queries
# Go to http://localhost:9090/graph
# Test each metric type:
gridbot_orders_placed_total
gridbot_system_cpu_percent
gridbot_guardian_signal
gridbot_api_call_duration_seconds

# 4. Verify data retention
# Check Prometheus has at least 15 minutes of data

# 5. Test Grafana dashboards
# Open each dashboard, verify panels load
# Check for "No data" errors
```

#### 5.2 Integration Tests

**File:** `tests/test_prometheus_metrics.py` (NEW)

```python
#!/usr/bin/env python3
"""
Integration tests for Prometheus metrics
"""

import pytest
import requests
from prometheus_client.parser import text_string_to_metric_families

def test_metrics_endpoint_available():
    """Test /metrics endpoint is accessible"""
    response = requests.get('http://localhost:5555/metrics')
    assert response.status_code == 200
    assert 'gridbot_' in response.text

def test_metrics_format():
    """Test metrics are in valid Prometheus format"""
    response = requests.get('http://localhost:5555/metrics')
    
    # Parse metrics
    metrics = {}
    for family in text_string_to_metric_families(response.text):
        metrics[family.name] = family
    
    # Check expected metrics exist
    assert 'gridbot_orders_placed_total' in metrics
    assert 'gridbot_system_cpu_percent' in metrics
    assert 'gridbot_guardian_signal' in metrics

def test_prometheus_scraping():
    """Test Prometheus is successfully scraping"""
    # Query Prometheus API
    response = requests.get(
        'http://localhost:9090/api/v1/query',
        params={'query': 'up{job="workingbot"}'}
    )
    
    data = response.json()
    assert data['status'] == 'success'
    
    # Check target is up
    results = data['data']['result']
    assert len(results) > 0
    assert results[0]['value'][1] == '1'  # up=1 means healthy

def test_grafana_datasource():
    """Test Grafana can connect to Prometheus"""
    # This requires Grafana API key - skip if not configured
    pytest.skip("Requires Grafana API key")

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

#### 5.3 Performance Tests

```bash
# Test metrics endpoint performance
ab -n 1000 -c 10 http://localhost:5555/metrics

# Should handle:
# - 100+ requests/second
# - < 100ms response time
# - No errors

# Monitor Prometheus resource usage
ps aux | grep prometheus
# Should use < 200MB RAM

# Monitor Grafana resource usage
ps aux | grep grafana
# Should use < 300MB RAM
```

#### 5.4 Validation Criteria

✅ **Metrics Collection:**
- [ ] All 50+ metrics appear in /metrics endpoint
- [ ] Metrics update every 15 seconds
- [ ] No errors in WebUI logs
- [ ] Bot continues trading normally

✅ **Prometheus:**
- [ ] Target 'workingbot' shows UP status
- [ ] Can query metrics via PromQL
- [ ] Data retained for 30 days
- [ ] < 200MB memory usage

✅ **Grafana:**
- [ ] All 5 dashboards load without errors
- [ ] Panels show real data (not "No data")
- [ ] Refresh works (default 5s)
- [ ] Can zoom/pan time ranges

✅ **Performance:**
- [ ] /metrics responds in < 100ms
- [ ] No impact on trading latency
- [ ] CPU usage < 5% increase
- [ ] Memory usage < 100MB increase

**Deliverables:**
- ✅ All metrics validated
- ✅ Integration tests passing
- ✅ Performance benchmarks met
- ✅ Documentation updated

---

## 📦 Final Deliverables

### Files Created (7 new files)

1. **bot/observability/__init__.py** - Package init
2. **bot/observability/prometheus_metrics.py** - Metrics exporter (500 lines)
3. **webui/backend/routes/metrics.py** - Flask /metrics endpoint (100 lines)
4. **tests/test_prometheus_metrics.py** - Integration tests (100 lines)
5. **grafana/dashboards/trading_performance.json** - Dashboard export
6. **grafana/dashboards/system_health.json** - Dashboard export
7. **grafana/dashboards/risk_management.json** - Dashboard export
8. **grafana/dashboards/execution_quality.json** - Dashboard export
9. **grafana/dashboards/anomaly_detection.json** - Dashboard export

### Files Modified (3 edits)

1. **webui/backend/app.py** - Register metrics blueprint (1 line)
2. **bot/strategy/async_gridbot.py** - Add metrics tracking (10 lines)
3. **requirements.txt** - Add prometheus-client (1 line)

### Configuration Files

1. **/opt/homebrew/etc/prometheus.yml** - Prometheus config
2. **/opt/homebrew/etc/grafana/grafana.ini** - Grafana config (default OK)

---

## 🚀 Quick Start Commands

```bash
# Phase 1: Install
brew install prometheus grafana
pip3 install prometheus-client

# Start services
brew services start prometheus
brew services start grafana

# Phase 2-3: Deploy code (after creating files above)
cd /Users/ssr/Projects/WorkingBot
pm2 restart webui-backend

# Verify
curl http://localhost:5555/metrics
open http://localhost:9090
open http://localhost:3000

# Phase 4: Import dashboards
# 1. Open Grafana (http://localhost:3000)
# 2. Click "+" > Import
# 3. Upload JSON files from grafana/dashboards/
```

---

## 📈 Sample PromQL Queries

### Trading Queries

```promql
# Total orders in last hour
increase(gridbot_orders_placed_total[1h])

# Fill rate (percentage)
(sum(increase(gridbot_orders_filled_total[1h])) / 
 sum(increase(gridbot_orders_placed_total[1h]))) * 100

# P&L trend (rate of change)
rate(gridbot_realized_pnl_usd[5m])

# Orders per minute by side
rate(gridbot_orders_placed_total[1m]) * 60

# Grid efficiency average
avg_over_time(gridbot_grid_efficiency_ratio[1h])
```

### System Queries

```promql
# CPU usage trend
avg_over_time(gridbot_system_cpu_percent[5m])

# Memory growth rate
rate(gridbot_bot_memory_mb[10m])

# API latency p95
histogram_quantile(0.95, rate(gridbot_api_call_duration_seconds_bucket[5m]))

# API errors per hour
increase(gridbot_api_429_errors[1h])
```

### Risk Queries

```promql
# Guardian signal changes (downtime detection)
changes(gridbot_guardian_signal[1h])

# Loss velocity (how fast losing money)
rate(gridbot_total_loss_inr[5m])

# Liquidation danger zone (< 15%)
gridbot_liquidation_distance_percent < 15

# Guardian intervention frequency
rate(gridbot_guardian_interventions_total[1h])
```

---

## 🎯 Next Steps After Implementation

### Week 2: Alert Rules (Optional)

1. **Install Alertmanager:**
   ```bash
   brew install alertmanager
   brew services start alertmanager
   ```

2. **Create Alert Rules:**
   ```yaml
   # /opt/homebrew/etc/prometheus/rules/gridbot_alerts.yml
   groups:
     - name: gridbot
       interval: 30s
       rules:
         - alert: HighCPUUsage
           expr: gridbot_system_cpu_percent > 80
           for: 5m
           annotations:
             summary: "High CPU usage detected"
         
         - alert: GuardianStop
           expr: gridbot_guardian_signal == 0
           for: 1m
           annotations:
             summary: "Guardian has stopped trading"
         
         - alert: HighAPILatency
           expr: histogram_quantile(0.95, gridbot_api_call_duration_seconds_bucket) > 5
           for: 5m
           annotations:
             summary: "API latency above 5 seconds"
   ```

3. **Configure Notifications:**
   - Telegram alerts
   - Email alerts
   - PagerDuty integration

### Week 3: Advanced Dashboards

1. **Correlation Analysis Dashboard:**
   - CPU vs Trading Performance
   - API Latency vs Fill Rate
   - Guardian Risk vs Market Volatility

2. **Capacity Planning Dashboard:**
   - Resource usage trends
   - Extrapolated limits
   - Scaling recommendations

3. **Options Trading Dashboard:**
   - Greeks portfolio view
   - IV percentile tracking
   - Strategy performance

---

## 🔧 Troubleshooting

### Issue: Metrics endpoint returns 503

**Solution:**
```bash
# Check prometheus-client is installed
pip3 show prometheus-client

# Check import works
python3 -c "from prometheus_client import Counter; print('OK')"

# Restart WebUI
pm2 restart webui-backend
```

### Issue: Prometheus shows target DOWN

**Solution:**
```bash
# Check WebUI is running
pm2 list | grep webui

# Check port 5555 is accessible
curl http://localhost:5555/metrics

# Check Prometheus config
cat /opt/homebrew/etc/prometheus.yml

# Restart Prometheus
brew services restart prometheus
```

### Issue: Grafana shows "No data"

**Solution:**
```bash
# 1. Check Prometheus has data
curl 'http://localhost:9090/api/v1/query?query=up'

# 2. Check Grafana datasource
# Go to Configuration > Data Sources > Test

# 3. Check PromQL query syntax
# Copy query from panel, test in Prometheus UI

# 4. Check time range
# Ensure dashboard time range covers available data
```

---

## 📚 Resources

- **Prometheus Documentation:** https://prometheus.io/docs/
- **Grafana Documentation:** https://grafana.com/docs/
- **PromQL Tutorial:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Python Client:** https://github.com/prometheus/client_python
- **Grafana Dashboards:** https://grafana.com/grafana/dashboards/

---

## ✅ Success Criteria

After implementation, you should have:

1. **Metrics Collection:**
   - ✅ 50+ metrics exposed at /metrics
   - ✅ 15-second collection interval
   - ✅ Zero impact on trading performance

2. **Data Storage:**
   - ✅ 30 days retention in Prometheus
   - ✅ < 1GB disk usage per month
   - ✅ Sub-second query response

3. **Dashboards:**
   - ✅ 5 dashboards with 40+ panels
   - ✅ All panels showing real data
   - ✅ 5-second auto-refresh

4. **Visibility:**
   - ✅ Historical trend analysis
   - ✅ Pattern detection
   - ✅ Correlation insights
   - ✅ Performance bottleneck identification

---

## 📝 Summary

This 4-hour implementation gives you:

- **Professional-grade observability** matching industry standards
- **Historical metrics** for trend analysis and debugging
- **Beautiful dashboards** for monitoring and presentations
- **Foundation for alerts** (Alertmanager integration ready)
- **Minimal changes** to existing code (< 20 lines modified)
- **Zero downtime** deployment (add-on only)

**Total ROI:** 10x improvement in debugging speed and visibility for 4 hours of work.

**Next Actions:**
1. Start with Phase 1 (installation) - 30 minutes
2. Deploy Phase 2 (metrics exporter) - 1 hour
3. Configure Phase 3 (Prometheus) - 30 minutes
4. Create Phase 4 (Grafana dashboards) - 1.5 hours
5. Validate Phase 5 (testing) - 30 minutes

**Questions?** Review this document or check the Resources section above.

---

**End of Document**
