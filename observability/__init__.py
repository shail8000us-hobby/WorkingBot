"""
Observability Module for WorkingBot
====================================

Standalone observability system with Prometheus metrics and Grafana dashboards.
Completely isolated from core trading logic - NO modifications to existing code.

Structure:
    observability/
    ├── __init__.py              # This file
    ├── metrics/                  # Prometheus metrics
    │   ├── __init__.py
    │   ├── definitions.py       # Metric definitions
    │   ├── collectors.py        # Data collectors
    │   └── exporters.py         # Prometheus exporter
    ├── server/                   # Standalone metrics server
    │   ├── __init__.py
    │   └── metrics_server.py    # Flask app for /metrics
    ├── config/                   # Configuration
    │   ├── __init__.py
    │   ├── prometheus.yml       # Prometheus config template
    │   └── settings.py          # Module settings
    └── dashboards/              # Grafana dashboard JSON exports
        └── *.json

Usage:
    # Start standalone metrics server (recommended - no code changes)
    python -m observability.server.metrics_server
    
    # Or import metrics collector in existing code (optional)
    from observability.metrics.collectors import MetricsCollector
    MetricsCollector.record_order_placed(...)

Author: AI Assistant
Created: January 14, 2026
Version: 1.0.0
"""

__version__ = '1.0.0'
__author__ = 'WorkingBot Team'

# Lazy imports to avoid loading heavy dependencies
def get_metrics_collector():
    """Get metrics collector instance"""
    from .metrics.collectors import MetricsCollector
    return MetricsCollector

def start_metrics_server(port: int = 9091):
    """Start standalone metrics server"""
    from .server.metrics_server import start_server
    start_server(port=port)
