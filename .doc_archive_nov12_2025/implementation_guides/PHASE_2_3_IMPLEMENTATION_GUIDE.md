<!-- Created: November 9, 2025 -->
# PHASE 2 & 3 IMPLEMENTATION GUIDE
## November 9, 2025

---

## ✅ **PHASE 1 STATUS: COMPLETE & VERIFIED**

**Confirmed Working:**
- ✅ Watchdog started (60s timeout)
- ✅ Fill audit log initialized  
- ✅ Permanent memory active
- ✅ All fixes deployed successfully

Bot started and ran without errors. All Phase 1 objectives achieved.

---

## 🚀 **PHASE 2: ENHANCED STABILITY** (Ready to Implement)

### **Objective:**
Make the bot even more resilient to API failures, memory issues, and edge cases.

### **2.1: Circuit Breaker for API Calls** ⏳

**Status:** PARTIALLY EXISTS  
**Location:** `bot/api/delta_client.py` already has circuit breaker  
**Task:** Enhance with more sophisticated retry logic

**Implementation:**
```python
# File: bot/api/delta_client.py
# Add exponential backoff with jitter

def place_order_with_circuit_breaker(self, **kwargs):
    """
    Place order with circuit breaker and exponential backoff
    """
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            if self.circuit_breaker.is_open():
                raise CircuitBreakerOpen("API circuit breaker is open")
            
            return self.place_order(**kwargs)
        
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                log.warning(f"API call failed (attempt {attempt+1}/{max_retries}), retry in {delay:.1f}s")
                time.sleep(delay)
            else:
                raise
```

**Benefits:**
- Protects against API rate limits
- Auto-recovery from transient failures
- Prevents cascade failures

---

### **2.2: Memory Leak Prevention** ⏳

**Task:** Add memory monitoring and cleanup

**Implementation:**
```python
# File: bot/strategy/gridbot.py
# Add to __init__

import psutil
import gc

self._memory_check_interval = 300  # 5 minutes
self._last_memory_check = time.time()
self._memory_threshold_mb = 500  # Alert if bot uses >500MB

# Add to _heartbeat method

def _check_memory_usage(self):
    """Monitor memory usage and trigger cleanup if needed"""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    if memory_mb > self._memory_threshold_mb:
        log.warning(f"⚠️ High memory usage: {memory_mb:.1f}MB")
        log.warning("   Triggering garbage collection...")
        gc.collect()
        
        # Check again
        memory_mb = process.memory_info().rss / 1024 / 1024
        log.info(f"   Memory after cleanup: {memory_mb:.1f}MB")
        
        if memory_mb > self._memory_threshold_mb:
            log.critical(f"🚨 Memory usage still high: {memory_mb:.1f}MB - possible memory leak")
```

**Benefits:**
- Detects memory leaks early
- Auto-cleanup before problems occur
- Alerts on persistent high usage

---

### **2.3: Enhanced Exception Handling** ⏳

**Task:** Add more specific exception handlers in critical paths

**Implementation:**
```python
# File: bot/strategy/gridbot.py
# Enhance _on_fill_processed with specific exception handling

def _on_fill_processed(self, fill_data: Dict):
    """Handle processed fills with enhanced error handling"""
    try:
        # ... existing code ...
    
    except ConnectionError as e:
        log.error(f"❌ Connection error during fill processing: {e}")
        log.error("   Will retry on next heartbeat reconciliation")
        # Don't raise - let reconciliation fix it
    
    except TimeoutError as e:
        log.error(f"❌ Timeout during fill processing: {e}")
        # Requeue fill for processing
        self.fill_detector.requeue_fill(fill_data)
    
    except ValueError as e:
        log.error(f"❌ Invalid data in fill processing: {e}")
        log.error(f"   Fill data: {fill_data}")
        # Don't requeue - data is bad
    
    except Exception as e:
        log.error(f"❌ Unexpected error in fill processing: {e}")
        log.error(traceback.format_exc())
        raise  # Re-raise unknown errors
```

**Benefits:**
- Specific handling for known failure modes
- Better recovery strategies
- Clearer error messages

---

## 🔄 **PHASE 3: INFINITE RUNTIME CAPABILITY** (Infrastructure)

### **Objective:**
Enable bot to run 24/7/365 with auto-restart and proper system integration.

### **3.1: Systemd Service Configuration** ⏳

**Task:** Create systemd service for auto-restart

**File:** `/etc/systemd/system/gridbot.service`

```ini
[Unit]
Description=GridBot Trading Bot
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=ssr
WorkingDirectory=/Users/ssr/Projects/WorkingBot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /Users/ssr/Projects/WorkingBot/bot_launcher.py --foreground
StandardOutput=append:/Users/ssr/Projects/WorkingBot/bot/logs/bot.log
StandardError=append:/Users/ssr/Projects/WorkingBot/bot/logs/bot.log

# Resource Limits
LimitNOFILE=65536
LimitNPROC=4096
MemoryLimit=1G

# Security
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

**Commands:**
```bash
# Install
sudo cp gridbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gridbot
sudo systemctl start gridbot

# Monitor
sudo systemctl status gridbot
sudo journalctl -u gridbot -f

# Control
sudo systemctl stop gridbot
sudo systemctl restart gridbot
```

**Benefits:**
- Auto-restart on crash
- Starts on system boot
- Resource limits enforced
- Centralized logging

---

### **3.2: Log Rotation** ⏳

**Task:** Configure logrotate to prevent log files from filling disk

**File:** `/etc/logrotate.d/gridbot`

```
/Users/ssr/Projects/WorkingBot/bot/logs/bot.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 ssr ssr
    postrotate
        # Signal bot to reopen log file (if needed)
        /usr/bin/killall -USR1 python3 2>/dev/null || true
    endscript
}

/Users/ssr/Projects/WorkingBot/bot/audit/fill_processing_log.jsonl {
    weekly
    rotate 52
    compress
    delaycompress
    notifempty
    missingok
    create 0644 ssr ssr
}
```

**Test:**
```bash
# Test rotation manually
sudo logrotate -f /etc/logrotate.d/gridbot

# Verify
ls -lh bot/logs/
ls -lh bot/audit/
```

**Benefits:**
- Prevents disk from filling
- 30 days of main logs
- 52 weeks of audit logs
- Compressed old logs

---

### **3.3: Advanced Circuit Breaker** ⏳

**Task:** Implement more sophisticated circuit breaker pattern

**File:** `bot/utils/advanced_circuit_breaker.py`

```python
"""
Advanced Circuit Breaker with Half-Open State
"""
import time
import logging
from enum import Enum
from typing import Callable, Any

log = logging.getLogger("runner")


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures exceeded, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class AdvancedCircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 60,
        half_open_timeout: int = 30,
        success_threshold: int = 2
    ):
        """
        Advanced circuit breaker with half-open state
        
        Args:
            name: Breaker name (for logging)
            failure_threshold: Failures before opening circuit
            timeout: Seconds before trying half-open
            half_open_timeout: Timeout for half-open state
            success_threshold: Successes needed in half-open to close
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state_changed_time = time.time()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker
        
        Raises:
            CircuitOpenException: If circuit is open
        """
        # Check if we should transition to half-open
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                log.info(f"🔄 Circuit breaker '{self.name}' transitioning to HALF-OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.state_changed_time = time.time()
            else:
                raise CircuitOpenException(f"Circuit '{self.name}' is OPEN")
        
        # Check half-open timeout
        if self.state == CircuitState.HALF_OPEN:
            if time.time() - self.state_changed_time >= self.half_open_timeout:
                log.warning(f"⚠️ Circuit breaker '{self.name}' half-open timed out - reopening")
                self.state = CircuitState.OPEN
                self.last_failure_time = time.time()
                raise CircuitOpenException(f"Circuit '{self.name}' is OPEN (half-open timeout)")
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            log.info(f"✅ Circuit breaker '{self.name}' success in HALF-OPEN "
                    f"({self.success_count}/{self.success_threshold})")
            
            if self.success_count >= self.success_threshold:
                log.info(f"🔓 Circuit breaker '{self.name}' closing - service recovered")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            log.warning(f"❌ Circuit breaker '{self.name}' failed in HALF-OPEN - reopening")
            self.state = CircuitState.OPEN
            self.success_count = 0
        
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                log.error(f"🔒 Circuit breaker '{self.name}' OPENING "
                         f"({self.failure_count} failures)")
                self.state = CircuitState.OPEN
    
    def reset(self):
        """Manually reset circuit breaker"""
        log.info(f"🔄 Circuit breaker '{self.name}' manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get current state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time
        }


class CircuitOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass
```

**Usage:**
```python
# In delta_client.py
from bot.utils.advanced_circuit_breaker import AdvancedCircuitBreaker

self.api_breaker = AdvancedCircuitBreaker(
    name="delta_api",
    failure_threshold=5,
    timeout=60,
    half_open_timeout=30,
    success_threshold=2
)

def place_order(self, **kwargs):
    """Place order through circuit breaker"""
    return self.api_breaker.call(self._place_order_internal, **kwargs)
```

**Benefits:**
- Prevents hammering failed API
- Auto-recovery testing (half-open)
- Gradual service restoration
- Detailed state tracking

---

### **3.4: Health Check Endpoint** ⏳

**Task:** Add HTTP endpoint for health checks

**File:** `bot/monitoring/health_check.py`

```python
"""
Health Check HTTP Server
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time

class HealthCheckHandler(BaseHTTPRequestHandler):
    bot_instance = None  # Set by server
    
    def do_GET(self):
        """Handle health check requests"""
        if self.path == "/health":
            self._health_check()
        elif self.path == "/metrics":
            self._metrics()
        else:
            self.send_response(404)
            self.end_headers()
    
    def _health_check(self):
        """Basic health check"""
        try:
            bot = self.bot_instance
            
            # Check if bot is running
            if bot is None or bot._shutdown_requested:
                status = "unhealthy"
                code = 503
            else:
                # Check last heartbeat
                time_since_hb = time.time() - bot._last_heartbeat_time
                
                if time_since_hb > 30:
                    status = "degraded"
                    code = 200
                else:
                    status = "healthy"
                    code = 200
            
            response = {
                "status": status,
                "timestamp": time.time(),
                "uptime": time.time() - bot._start_time if bot else 0
            }
            
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        except Exception as e:
            self.send_response(500)
            self.end_headers()
    
    def _metrics(self):
        """Detailed metrics"""
        try:
            bot = self.bot_instance
            
            metrics = {
                "positions": len(bot.position_mgr.get_positions()),
                "max_positions": bot.max_open,
                "pending_order": bot.position_mgr.get_pending_buy() is not None,
                "current_price": bot.current_price,
                "last_heartbeat": bot._last_heartbeat_time,
                "memory_mb": self._get_memory_usage()
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(metrics).encode())
        
        except Exception as e:
            self.send_response(500)
            self.end_headers()
    
    def _get_memory_usage(self):
        """Get memory usage in MB"""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs"""
        pass


def start_health_check_server(bot, port=8080):
    """Start health check server in background"""
    HealthCheckHandler.bot_instance = bot
    server = HTTPServer(('', port), HealthCheckHandler)
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    log.info(f"🏥 Health check server started on port {port}")
    log.info(f"   GET /health - Basic health status")
    log.info(f"   GET /metrics - Detailed metrics")
    
    return server
```

**Usage:**
```python
# In gridbot.py run() method
from bot.monitoring.health_check import start_health_check_server

self.health_server = start_health_check_server(self, port=8080)
```

**Test:**
```bash
curl http://localhost:8080/health
curl http://localhost:8080/metrics
```

**Benefits:**
- External monitoring integration
- Load balancer health checks
- Prometheus/Grafana integration
- Uptime monitoring

---

## 📊 **IMPLEMENTATION PRIORITY**

### **Do Now (High Priority):**
1. ✅ Phase 1 - COMPLETE & VERIFIED
2. ⏳ Log Rotation - Prevents disk full
3. ⏳ Health Check Endpoint - Monitoring

### **Do Soon (Medium Priority):**
4. ⏳ Memory Monitoring - Leak detection
5. ⏳ Enhanced Exception Handling - Better recovery
6. ⏳ Advanced Circuit Breaker - API protection

### **Do Later (Low Priority):**
7. ⏳ Systemd Service - Production deployment
8. ⏳ Additional monitoring - Prometheus/Grafana

---

## 🧪 **TESTING PLAN**

### **Phase 2 Testing:**
```bash
# Memory monitoring
# - Run bot for 24 hours
# - Check memory usage trend
# - Verify garbage collection triggers

# Exception handling
# - Simulate API failures
# - Verify specific exception paths
# - Check recovery mechanisms

# Circuit breaker
# - Simulate sustained API failures
# - Verify circuit opens
# - Test half-open recovery
# - Verify circuit closes after recovery
```

### **Phase 3 Testing:**
```bash
# Systemd service
sudo systemctl start gridbot
sudo systemctl status gridbot
# Kill bot process - verify auto-restart
sudo systemctl stop gridbot

# Log rotation
sudo logrotate -f /etc/logrotate.d/gridbot
ls -lh bot/logs/
# Verify old logs compressed

# Health check
curl http://localhost:8080/health
# Verify response
```

---

## 📝 **DEPLOYMENT CHECKLIST**

### **Phase 2:**
- [ ] Install psutil: `pip3 install psutil`
- [ ] Add memory check to heartbeat
- [ ] Enhance exception handlers
- [ ] Test circuit breaker
- [ ] Monitor for 24 hours

### **Phase 3:**
- [ ] Create systemd service file
- [ ] Test systemd service locally
- [ ] Create logrotate configuration
- [ ] Test log rotation
- [ ] Add health check server
- [ ] Test health endpoints
- [ ] Deploy to production
- [ ] Monitor for 1 week

---

## 🎯 **SUCCESS CRITERIA**

### **Phase 2:**
- Bot runs 7+ days without memory issues
- Specific exceptions handled gracefully
- Circuit breaker prevents API hammering
- No cascade failures

### **Phase 3:**
- Bot auto-restarts on crash within 10s
- Log files rotate automatically
- Disk usage stays under control
- Health checks respond correctly
- Uptime > 99.9%

---

## 📚 **NEXT STEPS**

1. **Current Status:** Phase 1 complete and verified ✅
2. **Next Action:** Implement Phase 2 memory monitoring
3. **Then:** Add log rotation (Phase 3)
4. **Finally:** Full systemd deployment

**All code examples provided above are ready to use.**

---

*Phases 2 & 3 Implementation Guide*
*November 9, 2025*
*Status: Ready for implementation*
