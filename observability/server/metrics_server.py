#!/usr/bin/env python3
"""
Standalone Prometheus Metrics Server

A completely separate Flask application that serves Prometheus metrics.
Runs on port 9091 (default) - completely independent from WebUI on port 5555.

NO MODIFICATIONS to existing code required!

Features:
- Reads metrics from health files, state files, and PM2
- Exposes /metrics endpoint in Prometheus format
- Includes /health endpoint for monitoring the metrics server itself
- Configurable via environment variables

Usage:
    # Start metrics server
    python -m observability.server.metrics_server
    
    # Or via PM2
    pm2 start observability/server/metrics_server.py --name metrics-server
    
    # Or import and run
    from observability.server.metrics_server import start_server
    start_server(port=9091)

Environment Variables:
    METRICS_PORT: Port to run on (default: 9091)
    METRICS_HOST: Host to bind to (default: 0.0.0.0)
    METRICS_DEBUG: Enable debug mode (default: false)

Prometheus Configuration:
    Add to prometheus.yml:
    
    scrape_configs:
      - job_name: 'workingbot'
        static_configs:
          - targets: ['localhost:9091']
"""

import os
import sys
import logging
import time
from datetime import datetime
from flask import Flask, Response, jsonify

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from observability.metrics.exporters import generate_metrics, get_content_type

# Try to use enhanced collector if available
try:
    from observability.metrics.enhanced_collector import collect_enhanced_metrics
    USE_ENHANCED = True
except ImportError:
    USE_ENHANCED = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('metrics_server')

# Create Flask app
app = Flask(__name__)

# Server start time for uptime tracking
SERVER_START_TIME = time.time()

# Request counter for basic stats
REQUEST_COUNT = 0
LAST_SCRAPE_TIME = None


@app.route('/metrics', methods=['GET'])
def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    Called by Prometheus scraper (typically every 15 seconds).
    """
    global REQUEST_COUNT, LAST_SCRAPE_TIME
    
    try:
        REQUEST_COUNT += 1
        LAST_SCRAPE_TIME = datetime.now()
        
        # Use enhanced collector if available
        if USE_ENHANCED:
            try:
                collect_enhanced_metrics()
            except Exception as e:
                logger.warning(f"Enhanced collector error: {e}")
        
        # Generate all metrics
        metrics_output = generate_metrics()
        
        return Response(
            metrics_output,
            mimetype=get_content_type(),
            status=200
        )
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        return Response(
            f"# Error generating metrics: {str(e)}\n",
            mimetype='text/plain',
            status=500
        )


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for the metrics server itself.
    
    Returns server status and basic statistics.
    """
    uptime = time.time() - SERVER_START_TIME
    
    return jsonify({
        'status': 'healthy',
        'server': 'workingbot-metrics',
        'version': '1.0.0',
        'uptime_seconds': int(uptime),
        'uptime_human': f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m",
        'request_count': REQUEST_COUNT,
        'last_scrape': LAST_SCRAPE_TIME.isoformat() if LAST_SCRAPE_TIME else None,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
def index():
    """
    Index page with links to other endpoints.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WorkingBot Metrics Server</title>
        <style>
            body { font-family: sans-serif; margin: 40px; background: #1a1a2e; color: #eee; }
            h1 { color: #00ff88; }
            a { color: #00aaff; }
            .endpoint { margin: 10px 0; padding: 10px; background: #16213e; border-radius: 5px; }
            code { background: #0f3460; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🔍 WorkingBot Metrics Server</h1>
        <p>Prometheus metrics exporter for WorkingBot trading system.</p>
        
        <h2>Endpoints</h2>
        
        <div class="endpoint">
            <strong><a href="/metrics">/metrics</a></strong>
            <p>Prometheus metrics endpoint. Add this to your <code>prometheus.yml</code>:</p>
            <pre>scrape_configs:
  - job_name: 'workingbot'
    static_configs:
      - targets: ['localhost:9091']</pre>
        </div>
        
        <div class="endpoint">
            <strong><a href="/health">/health</a></strong>
            <p>Health check endpoint for monitoring the metrics server itself.</p>
        </div>
        
        <h2>Quick Start</h2>
        <ol>
            <li>Install Prometheus: <code>brew install prometheus</code></li>
            <li>Add the scrape config above to <code>/opt/homebrew/etc/prometheus.yml</code></li>
            <li>Restart Prometheus: <code>brew services restart prometheus</code></li>
            <li>Open Prometheus: <a href="http://localhost:9090" target="_blank">http://localhost:9090</a></li>
            <li>Query: <code>gridbot_guardian_signal</code></li>
        </ol>
        
        <h2>Grafana Setup</h2>
        <ol>
            <li>Install Grafana: <code>brew install grafana</code></li>
            <li>Start Grafana: <code>brew services start grafana</code></li>
            <li>Open Grafana: <a href="http://localhost:3000" target="_blank">http://localhost:3000</a> (admin/admin)</li>
            <li>Add Prometheus data source: http://localhost:9090</li>
            <li>Import dashboards from <code>observability/dashboards/</code></li>
        </ol>
        
        <p style="margin-top: 30px; color: #666;">
            Server started: """ + datetime.fromtimestamp(SERVER_START_TIME).isoformat() + """
        </p>
    </body>
    </html>
    """


def start_server(host: str = None, port: int = None, debug: bool = None):
    """
    Start the metrics server.
    
    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to run on (default: 9091)
        debug: Enable debug mode (default: False)
    """
    # Get configuration from environment or arguments
    host = host or os.environ.get('METRICS_HOST', '0.0.0.0')
    port = port or int(os.environ.get('METRICS_PORT', '9091'))
    debug = debug if debug is not None else os.environ.get('METRICS_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting WorkingBot Metrics Server on {host}:{port}")
    logger.info(f"Prometheus endpoint: http://{host}:{port}/metrics")
    logger.info(f"Health endpoint: http://{host}:{port}/health")
    
    # Run Flask app
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=False  # Disable reloader for production
    )


if __name__ == '__main__':
    start_server()
