"""
🏥 FIX NOV 9 PHASE 3: Health Check HTTP Endpoint

Provides HTTP endpoint for monitoring systems (Prometheus, Nagios, etc.)

Endpoints:
- GET /health - Basic liveness check
- GET /metrics - Detailed bot metrics

Author: GridBot Team
Date: November 9, 2025
"""

import json
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional, Any

log = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks"""
    
    # Class variable to store bot reference
    bot_instance: Optional[Any] = None
    
    def log_message(self, format, *args):
        """Suppress HTTP access logs"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self._handle_health()
        elif self.path == '/metrics':
            self._handle_metrics()
        else:
            self.send_error(404, "Not Found")
    
    def _handle_health(self):
        """Basic health check - is bot alive?"""
        if not self.bot_instance:
            self.send_error(503, "Bot not initialized")
            return
        
        # Check if bot is running
        is_alive = not self.bot_instance._shutdown_requested
        
        if is_alive:
            response = {
                "status": "ok",
                "timestamp": int(time.time()),
                "uptime_seconds": int(time.time() - self.bot_instance.last_state_change) if hasattr(self.bot_instance, 'last_state_change') else 0
            }
            self.send_response(200)
        else:
            response = {
                "status": "shutdown",
                "timestamp": int(time.time())
            }
            self.send_response(503)
        
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def _handle_metrics(self):
        """Detailed metrics"""
        if not self.bot_instance:
            self.send_error(503, "Bot not initialized")
            return
        
        bot = self.bot_instance
        
        try:
            # Gather metrics
            metrics = {
                "status": "ok" if not bot._shutdown_requested else "shutdown",
                "timestamp": int(time.time()),
                
                # Grid state
                "grid": {
                    "mode": bot.grid_mode,
                    "lower": bot.grid_calc.lower,
                    "upper": bot.grid_calc.upper,
                    "step": bot.grid_calc.step,
                },
                
                # Position state
                "positions": {
                    "count": len(bot.position_mgr.get_positions()),
                    "pending_buy": bool(bot.position_mgr.get_pending_buy()),
                    "pending_sell": bool(bot.position_mgr.get_pending_sell()),
                },
                
                # Price data
                "price": {
                    "current": bot.current_price,
                    "last_update": bot.last_price_update,
                    "staleness_seconds": time.time() - bot.last_price_update if bot.last_price_update else None,
                },
                
                # Watchdog
                "watchdog": {
                    "last_heartbeat": bot._last_heartbeat_time,
                    "heartbeat_age_seconds": time.time() - bot._last_heartbeat_time,
                    "timeout_threshold": bot._watchdog_timeout,
                },
                
                # Memory (if available)
                "memory": {
                    "rss_mb": round(bot._process.memory_info().rss / 1024 / 1024, 2),
                    "threshold_mb": bot._memory_threshold_mb,
                    "critical_mb": bot._memory_critical_mb,
                },
                
                # Circuit breaker stats
                "circuit_breaker": bot.order_mgr.delta_client.circuit_breaker.get_stats(),
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(metrics, indent=2).encode())
        
        except Exception as e:
            log.error(f"Error generating metrics: {e}")
            import traceback
            log.error(traceback.format_exc())
            self.send_error(500, f"Error: {e}")


class HealthCheckServer:
    """
    Health check HTTP server
    
    Usage:
        server = HealthCheckServer(bot_instance, port=8080)
        server.start()
        
        # Later...
        server.stop()
    """
    
    def __init__(self, bot_instance, port: int = 8080):
        """
        Initialize health check server
        
        Args:
            bot_instance: GridBot instance to monitor
            port: HTTP port (default: 8080)
        """
        self.bot_instance = bot_instance
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        
        # Set bot instance in handler
        HealthCheckHandler.bot_instance = bot_instance
        
        log.info(f"🏥 Health check server initialized on port {port}")
    
    def start(self):
        """Start health check server in background thread"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
            
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            log.info(f"🏥 Health check server started on http://0.0.0.0:{self.port}")
            log.info(f"   Endpoints:")
            log.info(f"   - GET http://localhost:{self.port}/health")
            log.info(f"   - GET http://localhost:{self.port}/metrics")
        except Exception as e:
            log.error(f"Failed to start health check server: {e}")
    
    def stop(self):
        """Stop health check server"""
        if self.server:
            log.info("🛑 Stopping health check server...")
            self.server.shutdown()
            self.server.server_close()
            log.info("✅ Health check server stopped")
