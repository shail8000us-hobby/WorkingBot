#!/usr/bin/env python3
"""
WorkingBot Observability Module - Quick Start Script
Standalone launcher for the metrics server.

Usage:
    python3 observability/start.py
    
Or with PM2:
    pm2 start observability/ecosystem.config.js
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from observability.server.metrics_server import start_server
from observability.config.settings import ObservabilitySettings


def main():
    """Start the metrics server."""
    settings = ObservabilitySettings()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           WorkingBot Observability - Metrics Server           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Starting metrics server on port {settings.metrics_port}...                   ║
║                                                              ║
║  Endpoints:                                                  ║
║    • http://localhost:{settings.metrics_port}/metrics  - Prometheus metrics   ║
║    • http://localhost:{settings.metrics_port}/health   - Health check         ║
║    • http://localhost:{settings.metrics_port}/         - Info page            ║
║                                                              ║
║  Next Steps:                                                 ║
║    1. Configure Prometheus to scrape localhost:{settings.metrics_port}/metrics║
║    2. Import dashboards from observability/dashboards/       ║
║    3. Set up Grafana alerts as needed                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    start_server(port=settings.metrics_port)


if __name__ == '__main__':
    main()
