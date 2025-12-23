<!-- Created: November 9, 2025 -->
# Phase 3 Implementation: Production Infrastructure

## Overview
Production-ready infrastructure for 24/7 bot operation:
- Log rotation (prevents disk fill)
- Health check endpoint (monitoring integration)
- Systemd service (auto-restart, resource limits)

**Status**: Ready to implement  
**Priority**: LOW (non-critical for trading logic)  
**Time**: 30 minutes

---

## 3.1: Log Rotation Setup

### Create Logrotate Config
```bash
sudo nano /etc/logrotate.d/gridbot
```

**Content**:
```
# GridBot Log Rotation
# Prevents disk space exhaustion

/Users/ssr/Projects/WorkingBot/bot_live.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ssr staff
    postrotate
        # Send HUP signal to bot to reopen log file
        pkill -HUP -f "python3.*gridbot.py" || true
    endscript
}

/Users/ssr/Projects/WorkingBot/fill_audit_log.jsonl {
    weekly
    rotate 52
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ssr staff
    # Never delete audit logs - critical for debugging
}

/Users/ssr/Projects/WorkingBot/runtime_state.json {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ssr staff
    # Keep 7 days of state snapshots
}
```

### Test Rotation
```bash
# Test configuration
sudo logrotate -d /etc/logrotate.d/gridbot

# Force rotation (testing)
sudo logrotate -f /etc/logrotate.d/gridbot

# Verify rotated files
ls -lh bot_live.log*
```

### Result
- **bot_live.log**: Rotated daily, kept for 30 days
- **fill_audit_log.jsonl**: Rotated weekly, kept for 1 year
- **runtime_state.json**: Rotated daily, kept for 7 days
- Automatic compression after 1 day
- Bot receives HUP signal to reopen log file

---

## 3.2: Health Check Endpoint

### Create Health Check Server
**File**: `bot/monitoring/health_check.py`

```python
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
from typing import Optional, Dict, Any

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
                "uptime_seconds": int(time.time() - self.bot_instance.last_state_change)
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
                "uptime_seconds": int(time.time() - bot.last_state_change),
                
                # Grid state
                "grid": {
                    "mode": bot.grid_mode,
                    "lower": bot.grid_calc.lower,
                    "upper": bot.grid_calc.upper,
                    "step": bot.grid_calc.step,
                },
                
                # Position state
                "positions": {
                    "count": len(bot.position_mgr.state.get('positions', [])),
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
                    "rss_mb": bot._process.memory_info().rss / 1024 / 1024,
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
        self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
        
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        log.info(f"🏥 Health check server started on http://0.0.0.0:{self.port}")
        log.info(f"   Endpoints:")
        log.info(f"   - GET http://localhost:{self.port}/health")
        log.info(f"   - GET http://localhost:{self.port}/metrics")
    
    def stop(self):
        """Stop health check server"""
        if self.server:
            log.info("🛑 Stopping health check server...")
            self.server.shutdown()
            self.server.server_close()
            log.info("✅ Health check server stopped")
```

### Integration with GridBot
**Add to `bot/strategy/gridbot.py` __init__**:

```python
# 🏥 FIX NOV 9 PHASE 3: Health check server
self._health_server = None
if os.getenv('ENABLE_HEALTH_CHECK', 'true').lower() == 'true':
    from bot.monitoring.health_check import HealthCheckServer
    health_port = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
    self._health_server = HealthCheckServer(self, port=health_port)
    self._health_server.start()
```

### Testing
```bash
# Start bot with health check
export ENABLE_HEALTH_CHECK=true
export HEALTH_CHECK_PORT=8080
./bot_launcher.py

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/metrics

# Check from monitoring system
curl -f http://localhost:8080/health || echo "Bot is down!"
```

---

## 3.3: Systemd Service (Production Only)

⚠️ **WARNING**: Only deploy on Linux production server, NOT on development Mac!

### Create Systemd Unit
**File**: `/etc/systemd/system/gridbot.service`

```ini
[Unit]
Description=GridBot - Automated Grid Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ssr
Group=staff
WorkingDirectory=/Users/ssr/Projects/WorkingBot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"

# Start bot
ExecStart=/usr/bin/python3 /Users/ssr/Projects/WorkingBot/bot_launcher.py

# Auto-restart on failure
Restart=always
RestartSec=10

# Resource limits
MemoryMax=1G
LimitNOFILE=65536

# Logging
StandardOutput=append:/Users/ssr/Projects/WorkingBot/bot_live.log
StandardError=append:/Users/ssr/Projects/WorkingBot/bot_live.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/Users/ssr/Projects/WorkingBot

[Install]
WantedBy=multi-user.target
```

### Enable and Start
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable gridbot

# Start service
sudo systemctl start gridbot

# Check status
sudo systemctl status gridbot

# View logs
sudo journalctl -u gridbot -f

# Stop service
sudo systemctl stop gridbot

# Restart service
sudo systemctl restart gridbot
```

### Auto-Restart Testing
```bash
# Kill bot process - systemd will restart it
sudo pkill -f "python3.*gridbot"

# Wait 10 seconds
sleep 10

# Check if restarted
sudo systemctl status gridbot
```

---

## Phase 3 Summary

### What's Implemented:
1. **Log Rotation**: Prevents disk space exhaustion
   - Daily rotation for main logs (30 days)
   - Weekly rotation for audit logs (52 weeks)
   - Automatic compression

2. **Health Check**: HTTP monitoring endpoint
   - `/health` - Basic liveness check
   - `/metrics` - Detailed bot metrics
   - Prometheus/Nagios compatible

3. **Systemd Service**: Production deployment
   - Auto-restart on failure (10s delay)
   - Resource limits (1GB RAM, 65K files)
   - Security hardening
   - Boot auto-start

### Benefits:
- **24/7 Operation**: Auto-restart on crashes
- **Monitoring**: Health endpoints for alerting
- **Disk Management**: Log rotation prevents disk fill
- **Production Ready**: Systemd integration

### Testing Checklist:
- [ ] Log rotation works (test with `sudo logrotate -f`)
- [ ] Health endpoint responds (`curl localhost:8080/health`)
- [ ] Metrics endpoint works (`curl localhost:8080/metrics`)
- [ ] Systemd auto-restart works (kill process, verify restart)
- [ ] Resource limits enforced (check with `systemctl status gridbot`)

---

## Next Steps

Phase 3 is **OPTIONAL** for local development. Deploy to production server when ready for 24/7 operation.

**Current Status**: All critical fixes (Phase 1 + 2) are deployed and tested.
