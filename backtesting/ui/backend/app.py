"""
Backtesting Web UI — Flask Backend
====================================
Serves the React frontend and REST/SocketIO API for the backtesting dashboard.

Port: 5557 (5555=live trading, 5556=grid backtest UI)

Routes:
  /api/data/*       — collection status, available dates
  /api/backtest/*   — run sessions, stream results via SocketIO
  /api/analytics/*  — metrics, reports, comparison
  /api/optimizer/*  — grid search, walk-forward, Bayesian
  /                 — serve React frontend (dist/)
"""

import os
import sys
import logging
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

log = logging.getLogger("backtesting.ui")

# ── App initialization ────────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=str(Path(__file__).parent.parent / "frontend" / "dist"),
    static_url_path="",
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "backtesting-dev-key-5557")

CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Register blueprints ───────────────────────────────────────────────────────
from .api_data      import data_bp
from .api_backtest  import backtest_bp, register_socketio as reg_bt_socket
from .api_analytics import analytics_bp
from .api_optimizer import optimizer_bp

app.register_blueprint(data_bp,      url_prefix="/api/data")
app.register_blueprint(backtest_bp,  url_prefix="/api/backtest")
app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
app.register_blueprint(optimizer_bp, url_prefix="/api/optimizer")

# Register SocketIO handlers (for live streaming backtest results)
reg_bt_socket(socketio)


# ── Serve React frontend ──────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve the React SPA for all non-API routes."""
    static_dir = Path(app.static_folder)
    if path and (static_dir / path).exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


# ── Health check ─────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    from flask import jsonify
    return jsonify({"status": "ok", "port": 5557, "service": "backtesting-ui"})


# ── Main entry ────────────────────────────────────────────────────────────────
def run_server(host: str = "0.0.0.0", port: int = 5557, debug: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.info(f"Starting Backtesting UI at http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",  type=int, default=5557)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    run_server(port=args.port, debug=args.debug)
