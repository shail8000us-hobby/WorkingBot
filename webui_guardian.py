#!/usr/bin/env python3
"""
WebUI Guardian - Production Stability System

Ensures WebUI stays running 24/7 with:
- Health monitoring
- Auto-recovery from crashes
- Resource leak detection
- Port conflict resolution
- Memory management
- Automatic restarts
- Error notifications
- Performance monitoring

Run: python3 webui_guardian.py
"""

import os
import sys
import time
import psutil
import subprocess
import requests
import signal
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Setup
PROJECT_ROOT = Path(__file__).parent
WEBUI_URL = "http://localhost:5555"
HEALTH_CHECK_INTERVAL = 30  # seconds
MAX_MEMORY_MB = 2048  # 2GB threshold
MAX_CPU_PERCENT = 80
MAX_RESTART_ATTEMPTS = 5
RESTART_COOLDOWN = 60  # seconds

# Create logs directory
(PROJECT_ROOT / 'logs').mkdir(exist_ok=True)

# Logging with proper rotation for ALL log levels
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(console_handler)

# Rotating file handler for all logs (with strict limits)
info_handler = logging.handlers.RotatingFileHandler(
    PROJECT_ROOT / 'logs' / 'webui_guardian.log',
    maxBytes=10*1024*1024,  # 10MB max per file
    backupCount=2  # Keep only 2 backups
)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(info_handler)

# Rotating error handler (with even stricter limits)
error_handler = logging.handlers.RotatingFileHandler(
    PROJECT_ROOT / 'logs' / 'webui_guardian_error.log',
    maxBytes=10*1024*1024,  # 10MB max per file
    backupCount=2  # Keep only 2 backups
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(error_handler)

# Prevent propagation to root logger
log.propagate = False

class WebUIGuardian:
    def __init__(self):
        self.webui_process: Optional[psutil.Process] = None
        self.restart_count = 0
        self.last_restart_time = 0
        self.consecutive_failures = 0
        self.start_time = time.time()
        
        # Error throttling to prevent log spam
        self.last_error_log_time = {}
        self.error_throttle_seconds = 60  # Only log same error once per minute
        
        # Stats
        self.stats = {
            'uptime_seconds': 0,
            'total_restarts': 0,
            'total_health_checks': 0,
            'failed_health_checks': 0,
            'last_check_time': None,
            'status': 'initializing'
        }
        
        # Create logs dir
        (PROJECT_ROOT / 'logs').mkdir(exist_ok=True)
        
    def find_webui_process(self) -> Optional[psutil.Process]:
        """Find running WebUI process"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('webui/backend/app.py' in str(cmd) for cmd in cmdline):
                    return psutil.Process(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def is_process_hung_via_ps(self, pid: int) -> bool:
        """Check if process is hung using ps command (more reliable for state 'U')"""
        try:
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'state='],
                capture_output=True,
                text=True,
                timeout=2
            )
            state = result.stdout.strip()
            # 'U' = uninterruptible sleep (hung), 'D' = uninterruptible sleep (Linux)
            return state in ['U', 'D']
        except Exception:
            return False
    
    def is_port_in_use(self, port: int = 5555) -> bool:
        """Check if port is already in use"""
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False
    
    def kill_port_process(self, port: int = 5555):
        """Kill process using the port"""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        log.warning(f"Killing process {proc.pid} using port {port}")
                        proc.terminate()
                        proc.wait(timeout=10)
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
        return False
    
    def _throttled_log(self, level: str, message: str, throttle_key: str = None):
        """Log with throttling to prevent spam"""
        if throttle_key is None:
            throttle_key = message[:50]  # Use first 50 chars as key
        
        now = time.time()
        last_logged = self.last_error_log_time.get(throttle_key, 0)
        
        if now - last_logged >= self.error_throttle_seconds:
            self.last_error_log_time[throttle_key] = now
            getattr(log, level)(message)
            return True
        return False
    
    def check_health(self) -> bool:
        """Check if WebUI is responding"""
        try:
            response = requests.get(
                f"{WEBUI_URL}/api/health",
                timeout=10
            )
            self.stats['total_health_checks'] += 1
            self.stats['last_check_time'] = datetime.now().isoformat()
            
            if response.status_code == 200:
                self.consecutive_failures = 0
                self.stats['status'] = 'healthy'
                return True
            else:
                self._throttled_log('warning', f"Health check failed: HTTP {response.status_code}", 'health_http')
                self.stats['failed_health_checks'] += 1
                self.consecutive_failures += 1
                return False
        except Exception as e:
            self._throttled_log('warning', f"Health check failed: {e}", 'health_exception')
            self.stats['failed_health_checks'] += 1
            self.consecutive_failures += 1
            self.stats['status'] = 'unhealthy'
            return False
    
    def check_resources(self) -> Dict[str, Any]:
        """Monitor resource usage"""
        if not self.webui_process or not self.webui_process.is_running():
            return {}
        
        try:
            cpu_percent = self.webui_process.cpu_percent(interval=1)
            memory_info = self.webui_process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Check process state - detect hung processes
            status = self.webui_process.status()
            # Uninterruptible sleep states that indicate hung process
            hung_states = [
                psutil.STATUS_DISK_SLEEP,  # Uninterruptible sleep (I/O wait)
                psutil.STATUS_LOCKED,      # Locked in memory
            ]
            is_hung = status in hung_states
            
            return {
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb,
                'threads': self.webui_process.num_threads(),
                'open_files': len(self.webui_process.open_files()),
                'connections': len(self.webui_process.connections()),
                'status': status,
                'is_hung': is_hung
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}
    
    def start_webui(self) -> bool:
        """Start WebUI backend"""
        try:
            # Check for port conflicts
            if self.is_port_in_use(5555):
                log.warning("Port 5555 in use - attempting to clear...")
                self.kill_port_process(5555)
                time.sleep(2)
            
            # Start WebUI
            log.info("Starting WebUI backend...")
            
            webui_script = PROJECT_ROOT / "webui" / "backend" / "app.py"
            
            if not webui_script.exists():
                log.error(f"WebUI script not found: {webui_script}")
                return False
            
            # Start process
            process = subprocess.Popen(
                [sys.executable, str(webui_script)],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    **os.environ,
                    'PYTHONPATH': str(PROJECT_ROOT),
                    'FLASK_ENV': 'production',
                    'FLASK_DEBUG': '0',
                    'PYTHONUNBUFFERED': '1'
                }
            )
            
            # Wait for startup
            log.info(f"WebUI starting (PID: {process.pid})...")
            time.sleep(10)
            
            # Verify it's running
            self.webui_process = psutil.Process(process.pid)
            
            if self.check_health():
                log.info("✅ WebUI started successfully!")
                self.restart_count += 1
                self.stats['total_restarts'] += 1
                self.last_restart_time = time.time()
                return True
            else:
                log.error("WebUI started but health check failed")
                return False
                
        except Exception as e:
            log.error(f"Failed to start WebUI: {e}")
            return False
    
    def stop_webui(self):
        """Gracefully stop WebUI"""
        if not self.webui_process:
            return
        
        try:
            log.info("Stopping WebUI gracefully...")
            self.webui_process.terminate()
            self.webui_process.wait(timeout=30)
            log.info("WebUI stopped")
        except psutil.TimeoutExpired:
            log.warning("Graceful shutdown failed - forcing...")
            self.webui_process.kill()
        except Exception as e:
            log.error(f"Error stopping WebUI: {e}")
    
    def restart_webui(self, reason: str = "manual"):
        """Restart WebUI"""
        # Check restart limits
        time_since_last_restart = time.time() - self.last_restart_time
        
        if time_since_last_restart < RESTART_COOLDOWN:
            cooldown_remaining = int(RESTART_COOLDOWN - time_since_last_restart)
            log.warning(f"Restart cooldown active ({cooldown_remaining}s remaining) - sleeping...")
            time.sleep(min(cooldown_remaining, 10))  # Sleep at least 10s to prevent log spam
            return False
        
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            log.error(f"Max restart attempts ({MAX_RESTART_ATTEMPTS}) reached - manual intervention required")
            self.stats['status'] = 'failed_max_restarts'
            return False
        
        log.info(f"Restarting WebUI (Reason: {reason})")
        
        # Increment restart counter
        self.restart_count += 1
        self.last_restart_time = time.time()
        self.stats['total_restarts'] = self.restart_count
        
        # Stop existing process
        self.stop_webui()
        time.sleep(3)
        
        # Start new process
        success = self.start_webui()
        
        if success:
            self.consecutive_failures = 0
            log.info(f"Restart successful (Attempt {self.restart_count}/{MAX_RESTART_ATTEMPTS})")
        else:
            log.error(f"Restart failed (Attempt {self.restart_count}/{MAX_RESTART_ATTEMPTS})")
        
        return success
    
    def save_stats(self):
        """Save statistics to file"""
        stats_file = PROJECT_ROOT / 'data' / 'webui_guardian_stats.json'
        stats_file.parent.mkdir(exist_ok=True)
        
        self.stats['uptime_seconds'] = int(time.time() - self.start_time)
        
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def monitor_loop(self):
        """Main monitoring loop"""
        log.info("="*80)
        log.info("🛡️  WebUI Guardian - Production Stability System")
        log.info("="*80)
        log.info(f"Health check interval: {HEALTH_CHECK_INTERVAL}s")
        log.info(f"Memory threshold: {MAX_MEMORY_MB}MB")
        log.info(f"CPU threshold: {MAX_CPU_PERCENT}%")
        log.info("="*80)
        
        # Initial startup
        self.webui_process = self.find_webui_process()
        
        if not self.webui_process:
            log.info("WebUI not running - starting...")
            self.start_webui()
        else:
            log.info(f"Found existing WebUI process (PID: {self.webui_process.pid})")
        
        # Monitoring loop
        while True:
            try:
                # Check if process is still running
                if not self.webui_process or not self.webui_process.is_running():
                    log.error("WebUI process died!")
                    self.restart_webui(reason="process_died")
                    # Always sleep after failed restart to prevent log spam
                    time.sleep(10)
                    continue
                
                # Check for hung process using multiple methods
                is_hung = False
                hung_reason = None
                
                try:
                    # Method 1: Check psutil status
                    status = self.webui_process.status()
                    hung_states = [psutil.STATUS_DISK_SLEEP, psutil.STATUS_LOCKED]
                    if status in hung_states:
                        is_hung = True
                        hung_reason = f"psutil_status_{status}"
                    
                    # Method 2: Check using ps command (more reliable for 'U' state)
                    if not is_hung and self.is_process_hung_via_ps(self.webui_process.pid):
                        is_hung = True
                        hung_reason = "ps_command_state_U"
                    
                    if is_hung:
                        log.error(f"WebUI process is HUNG (PID: {self.webui_process.pid}, reason: {hung_reason})")
                        self.restart_webui(reason=f"process_hung_{hung_reason}")
                        continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
                # Health check
                is_healthy = self.check_health()
                
                if not is_healthy:
                    self._throttled_log('warning', 
                        f"Health check failed ({self.consecutive_failures} consecutive failures)",
                        'health_failed')
                    
                    # If process is "running" but not responding, it's likely hung
                    # Be more aggressive: 2 failures = likely hung, restart immediately
                    if self.consecutive_failures >= 2:
                        try:
                            # Double-check: process exists but not responding = hung
                            if self.webui_process and self.webui_process.is_running():
                                # Also check process state via ps command
                                if self.is_process_hung_via_ps(self.webui_process.pid):
                                    log.error(f"Process is HUNG (state U) - PID: {self.webui_process.pid}")
                                    self.restart_webui(reason="process_hung_state_U")
                                    continue
                                else:
                                    # Process exists but health check fails = hung
                                    log.error(f"Process running but not responding - likely HUNG (PID: {self.webui_process.pid})")
                                    self.restart_webui(reason="process_hung_no_response")
                                    continue
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # Fallback: 3 failures = definitely hung
                    if self.consecutive_failures >= 3:
                        log.error("Multiple health check failures - restarting...")
                        self.restart_webui(reason="health_check_failed_3x")
                    
                    time.sleep(HEALTH_CHECK_INTERVAL)
                    continue
                
                # Resource monitoring
                resources = self.check_resources()
                
                if resources:
                    log.info(
                        f"✅ Healthy | "
                        f"CPU: {resources['cpu_percent']:.1f}% | "
                        f"Memory: {resources['memory_mb']:.1f}MB | "
                        f"Threads: {resources['threads']} | "
                        f"Connections: {resources['connections']}"
                    )
                    
                    # Check for resource leaks
                    if resources['memory_mb'] > MAX_MEMORY_MB:
                        log.warning(f"Memory usage ({resources['memory_mb']:.1f}MB) exceeds threshold ({MAX_MEMORY_MB}MB)")
                        self.restart_webui(reason="high_memory")
                        continue
                    
                    if resources['cpu_percent'] > MAX_CPU_PERCENT:
                        log.warning(f"CPU usage ({resources['cpu_percent']:.1f}%) exceeds threshold ({MAX_CPU_PERCENT}%)")
                        # Don't auto-restart for high CPU, just log
                
                # Save stats
                self.save_stats()
                
                # Wait for next check
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                log.info("\n🛑 Shutdown requested...")
                self.stop_webui()
                break
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)
    
    def run(self):
        """Start guardian"""
        try:
            self.monitor_loop()
        except Exception as e:
            log.error(f"Guardian crashed: {e}")
            raise


def main():
    """Main entry point"""
    guardian = WebUIGuardian()
    guardian.run()


if __name__ == "__main__":
    main()

