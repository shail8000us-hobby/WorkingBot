#!/usr/bin/env python3
"""
GridBot Web UI - Backend Server (Refactored Architecture)

BEFORE: 8,850 lines, 133 routes, 233 functions in one file
AFTER:  ~180 lines + 16 blueprint modules

Refactored: October 31, 2025
Architecture: Flask Blueprints pattern
"""

import os
import sys
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load config from YAML (SINGLE SOURCE OF TRUTH)
from config.loader import get_config, get_api_credentials
cfg = get_config()

# Display config info (v5.0 multi-symbol or v4.0 single-symbol)
if hasattr(cfg, 'symbols') and cfg.symbols:
    symbols_list = ', '.join([s for s, c in cfg.symbols.items() if c.enabled])
    print(f"✅ Loaded config v{cfg.version} with symbols: {symbols_list}")
elif hasattr(cfg, 'bot') and hasattr(cfg.bot, 'symbol'):
    print(f"✅ Loaded config from config.yaml ({cfg.bot.symbol})")
else:
    print(f"✅ Loaded config v{cfg.version}")

# Load API credentials from .env (security best practice)
credentials = get_api_credentials(cfg.trading_mode)
if credentials['api_key']:
    os.environ['DELTA_API_KEY'] = credentials['api_key']
    os.environ['DELTA_API_SECRET'] = credentials['api_secret']
    print(f"✅ Trading mode: {cfg.trading_mode}")
    print(f"✅ API credentials loaded from secrets/api_keys.env (Key: {credentials['api_key'][:8]}...)")
else:
    print(f"⚠️  WARNING: API credentials not found in secrets/api_keys.env")

# Flask imports
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_compress import Compress
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Setup logging with rotation
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.WARNING,  # CHANGED: INFO -> WARNING to reduce log spam
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        # Console handler
        logging.StreamHandler(),
        # Rotating file handler: 10MB max, keep 3 backups
        RotatingFileHandler(
            LOG_DIR / 'backend_fixed.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )
    ]
)
log = logging.getLogger(__name__)

# Import all blueprints
# When run as module: use relative imports
# When run directly: use absolute imports
try:
    from .routes import (
        utility_bp, health_bp, logs_bp, docs_bp, metrics_bp,
        websocket_api_bp, system_bp, monitor_bp, guardian_bp,
        pm2_bp, orders_bp, pnl_bp, positions_bp,
        # config_bp,  # NOV 15: DISABLED - Migrated to yaml_config_bp
        bot_control_bp, todos_bp, risk_bp, capital_bp, recon_bp,
        robustness_bp, emergency_bp, ai_bp, liquidation_bp, strategy_bp,
        dynamic_brain_bp, grid_mode_bp, unified_safety_bp, resolved_state_bp
    )
    from .routes.prediction_api import prediction_bp
    from .routes.monitoring import monitoring_bp  # NOV 8: Bot monitoring systems
    from .routes.yaml_config_api import yaml_config_bp  # NOV 15: YAML config API
    from .routes.file_manager import file_manager_bp  # NOV 16: File Manager for Phase 2
    from .routes.mode_switcher import mode_switcher_bp  # NOV 16: Phase 3 - Mode Switcher
    from .routes.system_health import system_health_bp  # NOV 16: Phase 3 - System Health Monitor
    from .routes.instance_manager import instance_bp  # NOV 16: Phase 3 - Instance Manager
    from .routes.code_explainer import code_explainer_bp  # NOV 16: Phase 3 - Code Explainer AI
    from .routes.recovery import bp as recovery_bp  # NOV 20: Recovery systems
    from .routes.reconciliation import bp as reconciliation_bp  # NOV 20: Reconciliation engine
    from .routes.symbols import symbols_bp  # DEC 28: Multi-symbol API (v5.0)
    from .routes.settings import settings_bp  # JAN 2026: Settings API (risk limits)
    from .routes.market import market_bp  # JAN 2026: Market data (spot price)
    from .routes.ticker import ticker_bp  # JAN 2026: Ticker API (Greeks data)
    # JAN 2026: WebUI v3 API endpoints
    from .routes.trades import trades_bp
    from .routes.analytics import analytics_bp
    from .routes.performance import performance_bp
    from .routes.chart import chart_bp
    from .routes.backtest import backtest_bp
    from .routes.strategies import strategies_bp
except ImportError:
    from routes import (
        utility_bp, health_bp, logs_bp, docs_bp, metrics_bp,
        websocket_api_bp, system_bp, monitor_bp, guardian_bp,
        pm2_bp, orders_bp, pnl_bp, positions_bp,
        # config_bp,  # NOV 15: DISABLED - Migrated to yaml_config_bp
        bot_control_bp, todos_bp, risk_bp, capital_bp, recon_bp,
        robustness_bp, emergency_bp, ai_bp, liquidation_bp, strategy_bp,
        dynamic_brain_bp, grid_mode_bp, unified_safety_bp, resolved_state_bp
    )
    from routes.prediction_api import prediction_bp
    from routes.monitoring import monitoring_bp  # NOV 8: Bot monitoring systems
    from routes.yaml_config_api import yaml_config_bp  # NOV 15: YAML config API
    from routes.file_manager import file_manager_bp  # NOV 16: File Manager for Phase 2
    from routes.mode_switcher import mode_switcher_bp  # NOV 16: Phase 3 - Mode Switcher
    from routes.system_health import system_health_bp  # NOV 16: Phase 3 - System Health Monitor
    from routes.instance_manager import instance_bp  # NOV 16: Phase 3 - Instance Manager
    from routes.code_explainer import code_explainer_bp  # NOV 16: Phase 3 - Code Explainer AI
    from routes.recovery import bp as recovery_bp  # NOV 20: Recovery system
    from routes.reconciliation import bp as reconciliation_bp  # NOV 20: Reconciliation engine
    from routes.symbols import symbols_bp  # DEC 28: Multi-symbol API (v5.0)
    from routes.settings import settings_bp  # JAN 2026: Settings API (risk limits)
    from routes.market import market_bp  # JAN 2026: Market data (spot price)
    from routes.ticker import ticker_bp  # JAN 2026: Ticker API (Greeks data)
    # JAN 2026: WebUI v3 API endpoints
    from routes.trades import trades_bp
    from routes.analytics import analytics_bp
    from routes.performance import performance_bp
    from routes.chart import chart_bp
    from routes.backtest import backtest_bp
    from routes.strategies import strategies_bp

# Load YAML config
from config.loader import get_config
cfg = get_config()

# Create Flask app
app = Flask(__name__, static_folder='../frontend/build')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['_start_time'] = time.time()

# Enable compression
compress = Compress()
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/xml', 'application/json',
    'application/javascript', 'text/javascript'
]
compress.init_app(app)

# CORS configuration
ALLOWED_ORIGINS = cfg.webui.allowed_origins
CORS(app, origins=ALLOWED_ORIGINS.split(','), supports_credentials=True)

# SocketIO (configured for socket.io-client v4.x compatibility)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    engineio_logger=False,  # DISABLED: Reduce log spam
    logger=False,  # DISABLED: Reduce log spam
    ping_timeout=60,  # REDUCED: 120 -> 60 to cleanup stale connections faster
    ping_interval=25,  # REDUCED: 60 -> 25 to detect disconnects faster
    allow_upgrades=True,
    # max_http_buffer_size increased for larger payloads
    max_http_buffer_size=1000000
)

# ============================================================================
# Register All Blueprints
# ============================================================================

# Brain Analyzer (Independent Observer - doesn't touch bot code)
try:
    from webui.backend.brain_analyzer import brain_analyzer_bp
    BRAIN_ANALYZER_AVAILABLE = True
except:
    try:
        from brain_analyzer import brain_analyzer_bp
        BRAIN_ANALYZER_AVAILABLE = True
    except:
        BRAIN_ANALYZER_AVAILABLE = False

blueprints = [
    yaml_config_bp,  # NOV 15: Register FIRST to intercept /api/config/all
    resolved_state_bp,  # JAN 2026: Single authoritative state resolver
    utility_bp, health_bp, logs_bp, docs_bp, metrics_bp,
    websocket_api_bp, system_bp, monitor_bp, guardian_bp,
    pm2_bp, orders_bp, pnl_bp, positions_bp,
    # config_bp,  # NOV 15: DISABLED - Migrated to yaml_config_bp
    bot_control_bp, todos_bp, risk_bp, capital_bp, recon_bp,
    robustness_bp, emergency_bp, ai_bp, liquidation_bp, strategy_bp,
    dynamic_brain_bp, prediction_bp, grid_mode_bp, monitoring_bp,
    unified_safety_bp,  # DEC 27: Unified Risk & Safety Dashboard
    market_bp,  # JAN 2026: Market data API (spot price)
    ticker_bp,  # JAN 2026: Ticker API (Greeks data)
    # JAN 2026: WebUI v3 endpoints
    trades_bp, analytics_bp, performance_bp, chart_bp, backtest_bp, strategies_bp
]

# Register Frontend Error Logger
try:
    from webui.backend.routes.frontend_error_logger import frontend_error_bp
    app.register_blueprint(frontend_error_bp)
    log.info("✅ Frontend Error Logger registered")
except Exception as e:
    log.error(f"❌ Failed to register frontend error logger: {e}")

# Add brain analyzer if available (same port, separate codebase)
if BRAIN_ANALYZER_AVAILABLE:
    blueprints.append(brain_analyzer_bp)
    log.info("✅ Brain Analyzer (Observer) registered")

# Register health blueprint with /api prefix (its routes don't have /api)
app.register_blueprint(health_bp, url_prefix='/api')

# Register other blueprints without prefix (they already have /api in routes)
for i, bp in enumerate(blueprints):
    if bp != health_bp:
        try:
            app.register_blueprint(bp)
            print(f"✅ Registered blueprint {i+1}/{len(blueprints)}: {bp.name}")
        except Exception as e:
            print(f"❌ Failed to register blueprint {i+1}/{len(blueprints)}: {bp.name} - {e}")
            log.error(f"Blueprint registration failed: {bp.name} - {e}")

# Register File Manager blueprint (Phase 2)
app.register_blueprint(file_manager_bp)
print(f"✅ Registered file_manager blueprint")

# Register Phase 3 blueprints (NOV 16)
app.register_blueprint(mode_switcher_bp)
print(f"✅ Registered mode_switcher blueprint")

app.register_blueprint(system_health_bp)
print(f"✅ Registered system_health blueprint")

app.register_blueprint(instance_bp)
print(f"✅ Registered instance_manager blueprint")

# Register Code Explainer blueprint (NOV 16: Phase 3)
app.register_blueprint(code_explainer_bp, url_prefix='/api/code-explainer')
print(f"✅ Registered code_explainer blueprint")

# Register Recovery System blueprint (NOV 20: Recovery system)
app.register_blueprint(recovery_bp)
print(f"✅ Registered recovery blueprint")

app.register_blueprint(reconciliation_bp)
print(f"✅ Registered reconciliation blueprint")

# Register Settings API blueprint (JAN 2026: Risk limits)
app.register_blueprint(settings_bp)
print(f"✅ Registered settings blueprint")

# Register Multi-Symbol API blueprint (DEC 28: v5.0 multi-symbol support)
app.register_blueprint(symbols_bp)
print(f"✅ Registered symbols blueprint (v5.0 multi-symbol)")

# Unified safety blueprint is now part of blueprints list (registered above)

# Register Options Control blueprint (JAN 2026: Options trading module)
try:
    from webui.backend.routes.options.options_control import options_bp
    app.register_blueprint(options_bp)
    print(f"✅ Registered options blueprint (options trading module)")
except Exception as e:
    print(f"⚠️ Could not register options blueprint: {e}")
    log.warning(f"Options routes not available: {e}")

# Register Kelly Criterion Position Sizer (JAN 2026: Institutional position sizing)
try:
    from webui.backend.routes.kelly import kelly_bp
    app.register_blueprint(kelly_bp)
    print(f"✅ Registered Kelly Criterion blueprint (institutional position sizing)")
except Exception as e:
    print(f"⚠️ Could not register Kelly blueprint: {e}")
    log.warning(f"Kelly routes not available: {e}")

# Register Experimental Features (JAN 2026: Auto-Delta Hedging, experimental algos)
try:
    from webui.backend.routes.experimental import experimental_bp
    app.register_blueprint(experimental_bp)
    print(f"✅ Registered Experimental blueprint (auto-delta hedging, Greeks)")
except Exception as e:
    print(f"⚠️ Could not register Experimental blueprint: {e}")
    log.warning(f"Experimental routes not available: {e}")

# Register Delta Data blueprint (JAN 2026: Advanced data collection - INDEPENDENT MODULE)
try:
    from webui.backend.routes.delta_data import delta_data_bp
    app.register_blueprint(delta_data_bp)
    print(f"✅ Registered delta_data blueprint (advanced data collection, OHLCV, streaming)")
except Exception as e:
    print(f"⚠️ Could not register delta_data blueprint: {e}")
    log.warning(f"Delta data routes not available: {e}")

# Register Options Chain blueprint (JAN 2026: Options chain market data - ISOLATED MODULE)
try:
    from webui.backend.options_chain import options_chain_bp
    app.register_blueprint(options_chain_bp)
    print(f"✅ Registered options_chain blueprint (options chain market data)")
except Exception as e:
    print(f"⚠️ Could not register options_chain blueprint: {e}")
    log.warning(f"Options chain routes not available: {e}")

# Register Options Strategy blueprint (JAN 2026: Multi-leg strategy builder - ISOLATED MODULE)
try:
    from webui.backend.options_strategy import options_strategy_bp
    app.register_blueprint(options_strategy_bp)
    print(f"✅ Registered options_strategy blueprint (multi-leg strategy builder)")
except Exception as e:
    print(f"⚠️ Could not register options_strategy blueprint: {e}")
    log.warning(f"Options strategy routes not available: {e}")

# Register MV Straddle Native blueprint (JAN 25, 2026: Native Delta Exchange MV Straddle - ISOLATED MODULE)
try:
    from webui.backend.routes.mv_straddle_routes import mv_straddle_bp
    app.register_blueprint(mv_straddle_bp)
    print(f"✅ Registered mv_straddle_native blueprint (Delta Exchange MV Straddle product)")
except Exception as e:
    print(f"⚠️ Could not register mv_straddle_native blueprint: {e}")
    log.warning(f"MV Straddle native routes not available: {e}")

# Register Futures Panel blueprint (JAN 17, 2026: Futures positions display - ISOLATED MODULE)
try:
    from webui.backend.routes.futures import futures_bp
    app.register_blueprint(futures_bp)
    print(f"✅ Registered futures blueprint (futures positions panel)")
except Exception as e:
    print(f"⚠️ Could not register futures blueprint: {e}")
    log.warning(f"Futures routes not available: {e}")

# Register Futures Trading blueprint (JAN 18, 2026: Buy/Sell/Close operations - ISOLATED MODULE)
try:
    from webui.backend.routes.futures.futures_trading_api import futures_trading_bp
    app.register_blueprint(futures_trading_bp)
    print(f"✅ Registered futures_trading blueprint (buy/sell/close operations)")
except Exception as e:
    print(f"⚠️ Could not register futures_trading blueprint: {e}")
    log.warning(f"Futures trading routes not available: {e}")

# Register Futures Max Loss Monitor (JAN 18, 2026: Per-position max loss safety - ISOLATED MODULE)
try:
    from webui.backend.routes.futures.futures_max_loss_monitor import futures_max_loss_bp
    app.register_blueprint(futures_max_loss_bp)
    print(f"✅ Registered futures_max_loss blueprint (overnight protection)")
except Exception as e:
    print(f"⚠️ Could not register futures_max_loss blueprint: {e}")
    log.warning(f"Futures max loss routes not available: {e}")

# Register Production Monitoring blueprint (JAN 12, 2026: Enhanced monitoring from OptionBot)
try:
    from webui.backend.routes.production_monitoring import production_monitoring_bp
    app.register_blueprint(production_monitoring_bp)
    print(f"✅ Registered production_monitoring blueprint (health, risk, rate limits)")
except Exception as e:
    print(f"⚠️ Could not register production_monitoring blueprint: {e}")
    log.warning(f"Production monitoring routes not available: {e}")

# Register 0DTE Strategy blueprint (JAN 13, 2026: Autonomous 0DTE strangle with premium balancing)
try:
    from bot.api.zero_dte_api import zero_dte_bp, init_engine
    from bot.api.unified_api_client import UnifiedAPIClient
    
    # Initialize 0DTE engine with API client (needs credentials from config)
    zero_dte_credentials = get_api_credentials(cfg.trading_mode)
    _zero_dte_client = UnifiedAPIClient(
        zero_dte_credentials['api_key'], 
        zero_dte_credentials['api_secret'], 
        enable_websocket=False
    )
    init_engine(_zero_dte_client)
    
    app.register_blueprint(zero_dte_bp, url_prefix='/api/zero-dte')
    print(f"✅ Registered zero_dte blueprint (0DTE autonomous strangle strategy)")
except Exception as e:
    print(f"⚠️ Could not register zero_dte blueprint: {e}")
    log.warning(f"0DTE routes not available: {e}")

# Register Position & Liquidation Metrics blueprint (DEC 28: Delta Exchange India improvements)
try:
    from webui.backend.routes.position_liquidation import position_liquidation_bp
    app.register_blueprint(position_liquidation_bp)
    print(f"✅ Registered position_liquidation blueprint (Delta Exchange India improvements)")
except Exception as e:
    print(f"⚠️ Could not register position_liquidation blueprint: {e}")
    log.warning(f"Position liquidation routes not available: {e}")

# Register ML Trading blueprint (JAN 14: Trade learning and automation)
try:
    # First ensure the backend path is available for imports
    import sys
    from pathlib import Path
    backend_path = str(Path(__file__).parent)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    
    try:
        from .routes.ml_trading import ml_trading_bp
    except ImportError:
        from routes.ml_trading import ml_trading_bp
    app.register_blueprint(ml_trading_bp)
    print(f"✅ Registered ml_trading blueprint (ML trade learning and automation)")
except Exception as e:
    print(f"⚠️ Could not register ml_trading blueprint: {e}")
    log.warning(f"ML trading routes not available: {e}")

# Register Price Alerts blueprint (JAN 28, 2026: Price alerts with Telegram/ntfy notifications)
try:
    try:
        from .routes.alerts.alert_routes import alerts_bp, init_price_monitor
    except ImportError:
        from routes.alerts.alert_routes import alerts_bp, init_price_monitor
    app.register_blueprint(alerts_bp)
    # Start the price alert monitor automatically and wire to ticker
    price_monitor = init_price_monitor()
    try:
        try:
            from .routes.ticker import set_price_alert_monitor
        except ImportError:
            from routes.ticker import set_price_alert_monitor
        set_price_alert_monitor(price_monitor)
        log.info("✅ Price alert monitor wired to ticker feed")
    except ImportError:
        log.warning("Could not wire price monitor to ticker")
    print(f"✅ Registered alerts blueprint (price alerts with Telegram/ntfy notifications)")
except Exception as e:
    print(f"⚠️ Could not register alerts blueprint: {e}")
    log.warning(f"Price alerts routes not available: {e}")

# Initialize monitoring system wiring
from webui.backend.routes.monitoring import set_bot_instance

def wire_bot_monitoring(bot_instance):
    """Wire bot instance to monitoring system"""
    try:
        set_bot_instance(bot_instance)
        log.info("✅ Bot monitoring systems wired to WebUI")
    except Exception as e:
        log.error(f"Failed to wire bot monitoring: {e}")

def wire_guardian_bot(guardian_bot):
    """
    Wire Guardian bot instance to WebUI routes
    
    This exposes PositionMonitor data (with Delta Exchange India improvements)
    to the WebUI via position_liquidation routes.
    
    Args:
        guardian_bot: GuardianBot instance with position_monitor
    """
    try:
        from webui.backend.routes.position_liquidation import set_guardian_bot
        set_guardian_bot(guardian_bot)
        log.info("✅ Guardian bot (position monitor) wired to WebUI")
    except Exception as e:
        log.warning(f"Could not wire Guardian bot: {e}")

# Make wire functions available globally
app.wire_bot_monitoring = wire_bot_monitoring
app.wire_guardian_bot = wire_guardian_bot

print(f"✅ Registered {len(app.blueprints)} total blueprints")

# ============================================================================
# Route Overrides (YAML Config Migration)
# ============================================================================

# Override /api/config/all to use YAML (config.yaml is the source)
from routes.yaml_config_api import get_all_config_compat, get_flat_config_compat

# Remove old routes and add YAML-based ones
app.add_url_rule('/api/config/all', 'yaml_config_all', get_all_config_compat, methods=['GET'])
app.add_url_rule('/api/config/flat', 'yaml_config_flat', get_flat_config_compat, methods=['GET'])
print("✅ Overrode /api/config/all with YAML-based endpoint")

# ============================================================================
# Request Metrics Logging Middleware
# ============================================================================

from webui.backend.utils.metrics_logger import metrics_logger

@app.before_request
def start_request_timer():
    """Record request start time for latency tracking"""
    request._start_time = time.time()

@app.after_request
def log_request_metrics(response):
    """
    Log API request metrics to SQLite for trending
    
    Tracks:
    - API latency (response time)
    - Error counts (4xx, 5xx responses)
    - Endpoint usage patterns
    """
    try:
        # Calculate latency
        if hasattr(request, '_start_time'):
            latency_ms = (time.time() - request._start_time) * 1000
        else:
            latency_ms = 0
        
        # Only log API routes (not static files)
        if request.path.startswith('/api/'):
            # Determine status
            if response.status_code < 400:
                status = 'ok'
            elif response.status_code < 500:
                status = 'client_error'
            else:
                status = 'server_error'
            
            # Log latency metric
            metrics_logger.log_metric(
                'api_latency',
                request.path,
                latency_ms,
                status
            )
            
            # Log error count if error
            if status != 'ok':
                metrics_logger.log_metric(
                    'error_count',
                    request.path,
                    1,
                    status
                )
    
    except Exception as e:
        # Don't fail the request if metrics logging fails
        log.debug(f"Metrics logging failed: {e}")
    
    return response

# ============================================================================
# Global Error Handlers
# ============================================================================

@app.route('/api/debug/routes')
def debug_routes():
    """Debug endpoint to list all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
            'path': str(rule.rule)
        })
    return jsonify({'routes': sorted(routes, key=lambda x: x['path']), 'count': len(routes)})

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'path': request.path
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'details': str(e) if app.debug else None
    }), 500


@app.errorhandler(Exception)
def handle_global_exception(e):
    """Global exception handler with traceback logging"""
    import traceback
    print(f"❌ Unhandled exception in {request.method} {request.path}: {e}")
    print(traceback.format_exc())
    
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'details': str(e) if app.debug else None,
        'path': request.path
    }), 500


# ============================================================================
# SocketIO Event Handlers
# ============================================================================

# Log streaming state
import threading
_log_tailer_thread = None
_log_tailer_running = False

def tail_logs_and_emit():
    """
    Background thread that tails bot log file and emits new lines via WebSocket
    
    ✅ RESTORED: This was lost during refactoring but is critical for live logs
    """
    global _log_tailer_running
    log_file = Path("bot/logs/bot.log")
    
    print(f"📜 Starting log tailer for {log_file}")
    
    # Start from end of file
    if not log_file.exists():
        print(f"⚠️  Log file {log_file} doesn't exist yet, waiting...")
        while not log_file.exists() and _log_tailer_running:
            time.sleep(1)
    
    try:
        with open(log_file, 'r') as f:
            # Seek to end
            f.seek(0, 2)
            
            while _log_tailer_running:
                line = f.readline()
                if line:
                    # Strip and emit to all connected clients
                    socketio.emit('log_entry', {'message': line.strip()})
                else:
                    # No new line, wait a bit
                    time.sleep(0.1)
                    
    except Exception as e:
        print(f"❌ Error in log tailer: {e}")
    
    print("📜 Log tailer stopped")


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    global _log_tailer_thread, _log_tailer_running
    
    try:
        print(f"🔌 Client connected: {request.sid}")
        emit('connected', {'status': 'Connected to GridBot WebUI'})
        
        # Start log tailer if not already running
        if not _log_tailer_running:
            _log_tailer_running = True
            _log_tailer_thread = threading.Thread(target=tail_logs_and_emit, daemon=True, name="LogTailer")
            _log_tailer_thread.start()
            print("✅ Log tailer thread started")
        
        # Send recent logs on connect (last 30 lines)
        try:
            from webui.backend.utils.file_helpers import get_recent_logs
            recent_logs = get_recent_logs(30)
            if recent_logs:
                for log_line in recent_logs:
                    emit('log_entry', {'message': log_line.strip()})
                print(f"📤 Sent {len(recent_logs)} recent log lines to new client")
        except Exception as e:
            print(f"⚠️  Error sending recent logs: {e}")
            log.error(f"Error sending recent logs on WebSocket connect: {e}", exc_info=True)
            
    except Exception as e:
        log.error(f"❌ WebSocket connection error: {e}", exc_info=True)
        # Return False to reject the connection gracefully
        return False


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"🔌 Client disconnected: {request.sid}")


@socketio.on('ping')
def handle_ping(data):
    """Handle ping for latency monitoring"""
    try:
        emit('pong', {
            'timestamp': time.time(),
            'latency': int((time.time() - data.get('timestamp', time.time())) * 1000) if data else 0
        })
    except Exception as e:
        print(f"Error handling ping: {e}")


@socketio.on('get_halt_status')
def handle_get_halt_status():
    """Get volatility halt status from monitoring snapshot"""
    try:
        from pathlib import Path
        import json
        
        # Read from monitoring snapshot (written by bot's MonitoringDataWriter)
        snapshot_path = Path(BASE_DIR) / 'monitoring_snapshot.json'
        
        if snapshot_path.exists():
            with open(snapshot_path, 'r') as f:
                snapshot = json.load(f)
            
            # Get trading condition which includes volatility data
            trading_condition = snapshot.get('trading_condition', {})
            
            # Check if there's an active halt
            active = trading_condition.get('volatility_halted', False)
            
            emit('volatility_halt_status', {
                'active': active,
                'iv': trading_condition.get('iv', 0),
                'rv': trading_condition.get('rv', 0),
                'spread': trading_condition.get('spread', 0),
                'haltDuration': trading_condition.get('halt_duration', 0),
                'cancelledPrice': trading_condition.get('cancelled_order_price'),
                'currentPrice': trading_condition.get('current_price'),
                'gridStep': trading_condition.get('grid_step'),
                'message': 'Active halt' if active else 'Normal trading'
            })
        else:
            # No bot running - return safe defaults
            emit('volatility_halt_status', {
                'active': False,
                'iv': 0,
                'rv': 0,
                'spread': 0,
                'message': 'Bot not running'
            })
            
    except Exception as e:
        print(f"Error getting halt status: {e}")
        emit('volatility_halt_status', {'active': False, 'error': str(e)})


@socketio.on('get_recovery_history')
def handle_get_recovery_history():
    """Get opportunistic recovery history from monitoring snapshot"""
    try:
        from pathlib import Path
        import json
        
        # Read from monitoring snapshot (written by bot's MonitoringDataWriter)
        snapshot_path = Path(BASE_DIR) / 'monitoring_snapshot.json'
        
        if snapshot_path.exists():
            with open(snapshot_path, 'r') as f:
                snapshot = json.load(f)
            
            recovery_data = snapshot.get('opportunistic_recovery', {})
            recent_recoveries = recovery_data.get('recent_recoveries', [])
            
            emit('recovery_history', {
                'success': True,
                'history': recent_recoveries
            })
        else:
            emit('recovery_history', {
                'success': False,
                'history': [],
                'message': 'No monitoring data available - bot may not be running'
            })
            
    except Exception as e:
        print(f"Error getting recovery history: {e}")
        emit('recovery_history', {'success': False, 'history': [], 'error': str(e)})


@socketio.on('get_recovery_stats')
def handle_get_recovery_stats():
    """Get opportunistic recovery statistics from monitoring snapshot"""
    try:
        from pathlib import Path
        import json
        
        # Read from monitoring snapshot (written by bot's MonitoringDataWriter)
        snapshot_path = Path(BASE_DIR) / 'monitoring_snapshot.json'
        
        if snapshot_path.exists():
            with open(snapshot_path, 'r') as f:
                snapshot = json.load(f)
            
            recovery_data = snapshot.get('opportunistic_recovery', {})
            
            emit('recovery_stats', {
                'totalHalts': recovery_data.get('volatility_recoveries', 0) + recovery_data.get('startup_recoveries', 0),
                'successfulRecoveries': recovery_data.get('total_recoveries', 0),
                'totalExtraProfit': recovery_data.get('total_capital_saved', 0),
                'avgExtraProfit': recovery_data.get('total_capital_saved', 0) / max(recovery_data.get('total_recoveries', 1), 1),
                'levelsFilled': recovery_data.get('total_positions_recovered', 0)
            })
        else:
            emit('recovery_stats', {
                'totalHalts': 0,
                'successfulRecoveries': 0,
                'totalExtraProfit': 0,
                'avgExtraProfit': 0,
                'levelsFilled': 0
            })
            
    except Exception as e:
        print(f"Error getting recovery stats: {e}")
        emit('recovery_stats', {
            'totalHalts': 0,
            'successfulRecoveries': 0,
            'totalExtraProfit': 0,
            'avgExtraProfit': 0,
            'levelsFilled': 0,
            'error': str(e)
        })


@socketio.on('get_recovery_config')
def handle_get_recovery_config():
    """Get opportunistic recovery configuration from YAML"""
    try:
        import yaml
        from pathlib import Path
        
        config_path = Path(BASE_DIR) / 'config.yaml'
        
        if not config_path.exists():
            emit('recovery_config', {
                'success': False,
                'error': 'Config file not found',
                'config': {
                    'enabled': False,
                    'maxOrders': 5,
                    'delayMs': 300,
                    'minProfitInr': 500
                }
            })
            return
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        opp_config = config.get('safety', {}).get('volatility', {}).get('opportunistic_recovery', {})
        
        emit('recovery_config', {
            'success': True,
            'config': {
                'enabled': opp_config.get('enabled', False),
                'maxOrders': opp_config.get('max_orders_startup', 5),
                'delayMs': opp_config.get('execution_delay_ms', 300),
                'minProfitInr': opp_config.get('min_profit_margin', 500)
            }
        })
        
    except Exception as e:
        print(f"Error getting recovery config: {e}")
        emit('recovery_config', {
            'success': False,
            'error': str(e),
            'config': {
                'enabled': False,
                'maxOrders': 5,
                'delayMs': 300,
                'minProfitInr': 500
            }
        })


@socketio.on('update_recovery_config')
def handle_update_recovery_config(data):
    """Update opportunistic recovery configuration in YAML"""
    try:
        import yaml
        from pathlib import Path
        
        config_path = Path(BASE_DIR) / 'config.yaml'
        
        if not config_path.exists():
            emit('recovery_config_updated', {
                'success': False,
                'error': 'Config file not found'
            })
            return
        
        # Load config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update opportunistic recovery settings
        if 'safety' not in config:
            config['safety'] = {}
        if 'volatility' not in config['safety']:
            config['safety']['volatility'] = {}
        if 'opportunistic_recovery' not in config['safety']['volatility']:
            config['safety']['volatility']['opportunistic_recovery'] = {}
        
        opp_config = config['safety']['volatility']['opportunistic_recovery']
        
        # Update fields from frontend
        if 'enabled' in data:
            opp_config['enabled'] = bool(data['enabled'])
        if 'maxOrders' in data:
            opp_config['max_orders_startup'] = int(data['maxOrders'])
            opp_config['max_orders_volatility'] = int(data['maxOrders'])
        if 'delayMs' in data:
            opp_config['execution_delay_ms'] = int(data['delayMs'])
        if 'minProfitInr' in data:
            opp_config['min_profit_margin'] = int(data['minProfitInr'])
        
        # Write back to file
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"✅ Opportunistic recovery config updated: enabled={opp_config.get('enabled')}")
        
        emit('recovery_config_updated', {
            'success': True,
            'config': {
                'enabled': opp_config.get('enabled', False),
                'maxOrders': opp_config.get('max_orders_startup', 2),
                'delayMs': opp_config.get('execution_delay_ms', 300),
                'minProfitInr': opp_config.get('min_profit_margin', 500)
            }
        })
        
    except Exception as e:
        print(f"Error updating recovery config: {e}")
        emit('recovery_config_updated', {
            'success': False,
            'error': str(e)
        })


# ============================================================================
# Static File Serving (for React frontend)
# ============================================================================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """
    Serve React frontend (catch-all route)
    
    ⚠️  This route must be registered LAST to avoid intercepting API routes
    """
    # Don't intercept API routes - let them pass through to blueprints
    if path.startswith('api/'):
        # Let 404 handler or blueprint handle it
        from flask import abort
        abort(404)
    
    from flask import make_response
    
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        response = make_response(send_from_directory(app.static_folder, path))
    else:
        response = make_response(send_from_directory(app.static_folder, 'index.html'))
    
    # Add aggressive no-cache headers for ALL files during development
    # This ensures hard refresh always gets the latest files
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # ============================================================================
    # SINGLE INSTANCE ENFORCEMENT
    # ============================================================================
    from webui.backend.utils.instance_lock import WebUIInstanceLock
    
    # Allow port configuration via CLI argument or YAML config
    import sys
    if len(sys.argv) > 1:
        try:
            WEBUI_PORT = int(sys.argv[1])
            print(f"🔧 Using CLI port argument: {WEBUI_PORT}")
        except ValueError:
            print(f"❌ Invalid port argument: {sys.argv[1]}")
            sys.exit(1)
    else:
        WEBUI_PORT = cfg.webui.port
        print(f"🔧 Using config port: {WEBUI_PORT}")
    
    instance_lock = WebUIInstanceLock(BASE_DIR, WEBUI_PORT)
    
    if not instance_lock.acquire():
        # Another instance is already running
        existing_info = instance_lock.get_running_instance_info()
        print("=" * 80)
        print("❌ ERROR: WebUI instance is already running!")
        print("=" * 80)
        if existing_info:
            print(f"   PID: {existing_info.get('pid')}")
            print(f"   Port: {existing_info.get('port')}")
            print(f"   Started: {existing_info.get('started')}")
        print("\nTo stop the existing instance:")
        print("  • Check LaunchAgent: launchctl list | grep gridbot.webui")
        print("  • Stop it: launchctl stop com.gridbot.webui")
        print("  • Or kill process: kill <PID>")
        print("=" * 80)
        sys.exit(1)
    
    # Register cleanup on exit
    import atexit
    atexit.register(instance_lock.release)
    
    # Count routes
    route_count = len([r for r in app.url_map.iter_rules()])
    
    # Check if running in production mode (via YAML config)
    flask_env = cfg.webui.flask.env
    debug_mode = (flask_env != 'production')
    
    print("=" * 80)
    print("🚀 GridBot WebUI Backend (Refactored Architecture)")
    print("=" * 80)
    print(f"   Blueprints: {len(app.blueprints)}")
    print(f"   Routes: {route_count}")
    print(f"   Port: {WEBUI_PORT}")
    print(f"   Mode: {flask_env.upper()}")
    print(f"   Debug: {debug_mode}")
    print(f"   Instance Lock: ✅ Acquired (PID {os.getpid()})")
    print("=" * 80)
    
    # ============================================================================
    # Initialize Health Checker with Process Callbacks
    # ============================================================================
    try:
        print("\n💊 Starting Health Checker...")
        from webui.backend.utils.lightweight_health import start_health_checker
        from webui.backend.utils.process_helpers import (
            check_bot_running,
            check_guardian_running
        )
        
        # Helper functions for safe health checks
        def safe_check_bot():
            try:
                return check_bot_running()
            except Exception:
                return False
        
        def safe_check_guardian():
            try:
                return check_guardian_running()
            except Exception:
                return False
        
        def safe_check_telegram():
            try:
                # Check if telegram is configured using YAML config
                from config.loader import get_config
                cfg = get_config()
                
                # Determine which token to check based on trading mode
                if cfg.trading_mode == 'live':
                    bot_token = cfg.telegram.live_bot_token
                else:
                    bot_token = cfg.telegram.demo_bot_token
                
                # Fallback to generic token if mode-specific not set
                if not bot_token:
                    bot_token = cfg.telegram.bot_token
                
                return bool(bot_token and bot_token != '***REDACTED***')
            except Exception:
                return False
        
        # Start health checker with callbacks
        start_health_checker(
            bot_check=safe_check_bot,
            monitor_check=lambda: False,  # Monitor deprecated, always False
            guardian_check=safe_check_guardian,
            telegram_check=safe_check_telegram
        )
        print("✅ Health checker started (background updates every 5s)\n")
    except Exception as e:
        print(f"⚠️  Failed to start health checker: {e}")
        print("   Health dashboard will show 'unknown' status\n")
    
    # ============================================================================
    # Initialize and Start Delta Volatility Collector
    # ============================================================================
    try:
        print("\n📊 Starting Delta Volatility Collector...")
        from bot.volatility.delta_volatility_collector import get_collector
        
        collector = get_collector()
        
        # Check if we need to backfill historical data (SIMPLE SEEDING)
        import sqlite3
        conn = sqlite3.connect(collector.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rv_calculations WHERE timeframe = '1d'")
        daily_rv_count = cursor.fetchone()[0]
        conn.close()
        
        # If we have less than 30 days of data, run backfill
        if daily_rv_count < 30:
            print(f"📊 Detected only {daily_rv_count} days of RV data - running backfill...")
            try:
                from bot.volatility.backfill_historical_data import backfill_rv_data
                backfill_rv_data(days_back=90)
                print("✅ Historical data backfill complete\n")
            except Exception as backfill_error:
                print(f"⚠️  Backfill warning: {backfill_error}")
                print("   Collector will still work, but charts may have limited history\n")
        
        # Start background collection
        collector.start()
        print("✅ Delta Volatility Collector started (polling every 30s)\n")
    except Exception as e:
        print(f"❌ Failed to start Volatility Collector: {e}")
        import traceback
        traceback.print_exc()
        print("⚠️  Continuing without volatility collector...\n")
    
    # ============================================================================
    # Initialize and Start SL/TP Monitor (Options Trading)
    # ============================================================================
    try:
        print("\n🎯 Starting SL/TP Monitor...")
        from webui.backend.options_strategy.sl_tp_monitor import init_sl_tp_monitoring
        from webui.backend.options_strategy.sl_tp_manager import get_sl_tp_manager
        from bot.api.unified_api_client import UnifiedAPIClient
        
        # Create API client for options monitoring
        creds = get_api_credentials()
        api_client = UnifiedAPIClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            symbol='BTCUSD',
            enable_websocket=False
        )
        
        # Get manager and initialize monitor
        sl_tp_manager = get_sl_tp_manager()
        monitor = init_sl_tp_monitoring(api_client, sl_tp_manager, auto_start=True)
        
        if monitor.is_running():
            print("✅ SL/TP Monitor started (checking positions every 5s)\n")
        else:
            print("⚠️  SL/TP Monitor failed to start\n")
    except Exception as e:
        print(f"⚠️  Failed to start SL/TP Monitor: {e}")
        import traceback
        traceback.print_exc()
        print("   Options SL/TP will not auto-trigger (manual mode only)\n")

    # ============================================================================
    # Initialize and Start Max Loss Monitor (Options Trading)
    # ============================================================================
    try:
        print("\n🛑 Starting Max Loss Monitor...")
        from webui.backend.options_strategy.max_loss_manager import init_max_loss_monitoring, get_max_loss_manager
        # Use the same api_client as above
        max_loss_manager = get_max_loss_manager()
        max_loss_monitor = init_max_loss_monitoring(api_client, max_loss_manager, auto_start=True)
        if max_loss_monitor and getattr(max_loss_monitor, 'start', None):
            print("✅ Max Loss Monitor started (per-strike/expiry loss limits enforced)\n")
        else:
            print("⚠️  Max Loss Monitor failed to start\n")
    except Exception as e:
        print(f"⚠️  Failed to start Max Loss Monitor: {e}")
        import traceback
        traceback.print_exc()
        print("   Per-strike/expiry max loss will NOT be enforced!\n")
    
    # ============================================================================
    # Initialize Delta Exchange Price WebSocket
    # ============================================================================
    try:
        print("\n💹 Starting Delta Price WebSocket...")
        from webui.backend.services import start_price_service
        
        price_ws = start_price_service(socketio)
        print("✅ Delta Price WebSocket started (BTC & ETH real-time feeds)\n")
        print("   📡 Connected to wss://socket.india.delta.exchange")
        print("   📊 Broadcasting prices via Socket.IO on 'market_price_update' event\n")
    except Exception as e:
        print(f"⚠️  Failed to start Price WebSocket: {e}")
        import traceback
        traceback.print_exc()
        print("   Will fall back to REST API for price fetching\n")
    
    # IMPORTANT: Disable reloader to work with instance lock
    # Reloader spawns child process which conflicts with lock
    socketio.run(
        app,
        host='0.0.0.0',
        port=WEBUI_PORT,
        debug=False,  # Disable debug to prevent reloader
        use_reloader=False,  # Critical: reloader conflicts with instance lock
        allow_unsafe_werkzeug=True
    )
