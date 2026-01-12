"""
System Health Monitor for WorkingBot
====================================
Comprehensive system health monitoring with auto-recovery capabilities.
Monitors CPU, memory, disk, API connectivity, and database status.

Imported from OptionBot project with adaptations.
Original: monitoring/system_health_monitor.py

Usage:
    from webui.backend.utils.health_monitor import SystemHealthMonitor
    
    monitor = SystemHealthMonitor()
    monitor.start_monitoring()
    
    # Get health report
    report = monitor.get_health_report()
"""

from __future__ import annotations

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed. System metrics will be limited.")

# Try to import requests for API checks
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class SystemMetrics:
    """System metrics snapshot"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_latency: float  # API latency in ms
    database_status: bool
    api_connectivity: bool
    active_threads: int
    open_file_descriptors: int
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            'cpu_usage': round(self.cpu_usage, 1),
            'memory_usage': round(self.memory_usage, 1),
            'disk_usage': round(self.disk_usage, 1),
            'network_latency_ms': round(self.network_latency, 1),
            'database_status': self.database_status,
            'api_connectivity': self.api_connectivity,
            'active_threads': self.active_threads,
            'open_file_descriptors': self.open_file_descriptors,
            'timestamp': self.timestamp.isoformat()
        }


class SystemHealthMonitor:
    """
    Comprehensive system health monitoring.
    
    Features:
    - CPU/memory/disk monitoring
    - API connectivity checks
    - Database connectivity checks
    - Configurable thresholds
    - Background monitoring thread
    - Health reports for dashboards
    
    Example:
        monitor = SystemHealthMonitor()
        monitor.start_monitoring()
        
        # Check health anytime
        report = monitor.get_health_report()
        
        # Stop when done
        monitor.stop_monitoring()
    """

    def __init__(
        self,
        cpu_warning: float = 70.0,
        cpu_critical: float = 90.0,
        memory_warning: float = 80.0,
        memory_critical: float = 95.0,
        disk_warning: float = 85.0,
        disk_critical: float = 95.0,
        latency_warning: float = 1000.0,  # ms
        latency_critical: float = 5000.0,  # ms
        check_interval: int = 60,  # seconds
        api_url: str = "https://api.india.delta.exchange"
    ):
        """
        Initialize health monitor.
        
        Args:
            cpu_warning: CPU usage % for warning
            cpu_critical: CPU usage % for critical
            memory_warning: Memory usage % for warning
            memory_critical: Memory usage % for critical
            disk_warning: Disk usage % for warning
            disk_critical: Disk usage % for critical
            latency_warning: API latency ms for warning
            latency_critical: API latency ms for critical
            check_interval: Seconds between checks
            api_url: Delta Exchange API URL for connectivity check
        """
        self.thresholds = {
            'cpu_warning': cpu_warning,
            'cpu_critical': cpu_critical,
            'memory_warning': memory_warning,
            'memory_critical': memory_critical,
            'disk_warning': disk_warning,
            'disk_critical': disk_critical,
            'latency_warning': latency_warning,
            'latency_critical': latency_critical,
        }
        self.check_interval = check_interval
        self.api_url = api_url
        
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = 1440  # 24 hours at 1-minute intervals
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.last_health_check: Optional[datetime] = None
        
        logger.info("SystemHealthMonitor initialized")

    def start_monitoring(self):
        """Start background health monitoring"""
        if self.is_monitoring:
            logger.warning("Health monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="HealthMonitor"
        )
        self.monitoring_thread.start()
        logger.info("System health monitoring started")

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("System health monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.is_monitoring:
            try:
                metrics = self._collect_system_metrics()
                status = self._analyze_health_status(metrics)
                
                self.metrics_history.append(metrics)
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                if status not in [HealthStatus.HEALTHY, HealthStatus.UNKNOWN]:
                    logger.warning(f"System health degraded: {status.value}")
                
                self.last_health_check = datetime.now()
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
            
            time.sleep(self.check_interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        cpu_usage = 0.0
        memory_usage = 0.0
        disk_usage = 0.0
        active_threads = 0
        open_fds = 0
        
        if PSUTIL_AVAILABLE:
            try:
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent
                
                process = psutil.Process()
                active_threads = process.num_threads()
                
                if hasattr(process, 'num_fds'):
                    open_fds = process.num_fds()
                    
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
        
        # Measure API latency
        network_latency = self._measure_network_latency()
        
        # Check database
        database_status = self._check_database_connectivity()
        
        # Check API
        api_connectivity = network_latency < 9999
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_latency=network_latency,
            database_status=database_status,
            api_connectivity=api_connectivity,
            active_threads=active_threads,
            open_file_descriptors=open_fds,
            timestamp=datetime.now()
        )

    def _measure_network_latency(self) -> float:
        """Measure API latency in milliseconds"""
        if not REQUESTS_AVAILABLE:
            return 0.0
        
        try:
            start = time.time()
            response = requests.get(
                f"{self.api_url}/v2/products",
                timeout=10
            )
            end = time.time()
            
            if response.status_code == 200:
                return (end - start) * 1000
            else:
                logger.warning(f"API check returned status {response.status_code}")
                return 9999.0
                
        except requests.exceptions.Timeout:
            logger.warning("API check timed out")
            return 9999.0
        except Exception as e:
            logger.error(f"API check failed: {e}")
            return 9999.0

    def _check_database_connectivity(self) -> bool:
        """Check SQLite database connectivity"""
        try:
            import sqlite3
            import os
            
            # Check for options strategy database
            db_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'options_strategy',
                'strategies.db'
            )
            
            if not os.path.exists(db_path):
                # Try default trading bot database
                db_path = 'trading_bot.db'
            
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                return True
            
            return True  # No database file is OK for some setups
            
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return False

    def _analyze_health_status(self, metrics: SystemMetrics) -> HealthStatus:
        """Analyze metrics and determine health status"""
        critical_count = 0
        warning_count = 0
        
        # CPU check
        if metrics.cpu_usage >= self.thresholds['cpu_critical']:
            critical_count += 1
        elif metrics.cpu_usage >= self.thresholds['cpu_warning']:
            warning_count += 1
        
        # Memory check
        if metrics.memory_usage >= self.thresholds['memory_critical']:
            critical_count += 1
        elif metrics.memory_usage >= self.thresholds['memory_warning']:
            warning_count += 1
        
        # Disk check
        if metrics.disk_usage >= self.thresholds['disk_critical']:
            critical_count += 1
        elif metrics.disk_usage >= self.thresholds['disk_warning']:
            warning_count += 1
        
        # Network latency check
        if metrics.network_latency >= self.thresholds['latency_critical']:
            critical_count += 1
        elif metrics.network_latency >= self.thresholds['latency_warning']:
            warning_count += 1
        
        # API and database connectivity
        if not metrics.api_connectivity or not metrics.database_status:
            critical_count += 1
        
        # Determine overall status
        if critical_count > 0:
            return HealthStatus.CRITICAL
        if warning_count > 0:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY

    def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive health report.
        
        Returns fresh metrics if no history available.
        """
        # Collect fresh metrics if no history
        if not self.metrics_history:
            try:
                latest = self._collect_system_metrics()
                status = self._analyze_health_status(latest)
            except Exception as e:
                logger.error(f"Error collecting fresh metrics: {e}")
                return {
                    'overall_status': HealthStatus.UNKNOWN.value,
                    'last_check': datetime.now().isoformat(),
                    'error': str(e),
                    'monitoring_active': self.is_monitoring,
                    'psutil_available': PSUTIL_AVAILABLE
                }
            
            return {
                'overall_status': status.value,
                'last_check': datetime.now().isoformat(),
                'current_metrics': latest.to_dict(),
                'hourly_averages': {
                    'cpu_usage': latest.cpu_usage,
                    'memory_usage': latest.memory_usage,
                    'network_latency': latest.network_latency,
                },
                'thresholds': self.thresholds,
                'monitoring_active': self.is_monitoring,
                'psutil_available': PSUTIL_AVAILABLE,
                'note': 'Initial health check'
            }
        
        # Use historical data
        latest = self.metrics_history[-1]
        status = self._analyze_health_status(latest)
        
        # Calculate hourly averages
        hour_ago = datetime.now() - timedelta(hours=1)
        recent = [m for m in self.metrics_history if m.timestamp >= hour_ago]
        
        if recent:
            avg_cpu = sum(m.cpu_usage for m in recent) / len(recent)
            avg_memory = sum(m.memory_usage for m in recent) / len(recent)
            avg_latency = sum(m.network_latency for m in recent) / len(recent)
        else:
            avg_cpu = latest.cpu_usage
            avg_memory = latest.memory_usage
            avg_latency = latest.network_latency
        
        return {
            'overall_status': status.value,
            'last_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'current_metrics': latest.to_dict(),
            'hourly_averages': {
                'cpu_usage': round(avg_cpu, 1),
                'memory_usage': round(avg_memory, 1),
                'network_latency': round(avg_latency, 1),
            },
            'thresholds': self.thresholds,
            'monitoring_active': self.is_monitoring,
            'psutil_available': PSUTIL_AVAILABLE,
            'history_size': len(self.metrics_history)
        }

    def check_health_now(self) -> Dict[str, Any]:
        """
        Perform immediate health check (synchronous).
        
        Returns:
            Health report dictionary
        """
        metrics = self._collect_system_metrics()
        status = self._analyze_health_status(metrics)
        
        return {
            'status': status.value,
            'metrics': metrics.to_dict(),
            'issues': self._get_current_issues(metrics),
            'timestamp': datetime.now().isoformat()
        }

    def _get_current_issues(self, metrics: SystemMetrics) -> List[str]:
        """Get list of current issues"""
        issues = []
        
        if metrics.cpu_usage >= self.thresholds['cpu_critical']:
            issues.append(f"Critical CPU usage: {metrics.cpu_usage:.1f}%")
        elif metrics.cpu_usage >= self.thresholds['cpu_warning']:
            issues.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
        
        if metrics.memory_usage >= self.thresholds['memory_critical']:
            issues.append(f"Critical memory usage: {metrics.memory_usage:.1f}%")
        elif metrics.memory_usage >= self.thresholds['memory_warning']:
            issues.append(f"High memory usage: {metrics.memory_usage:.1f}%")
        
        if metrics.disk_usage >= self.thresholds['disk_critical']:
            issues.append(f"Critical disk usage: {metrics.disk_usage:.1f}%")
        elif metrics.disk_usage >= self.thresholds['disk_warning']:
            issues.append(f"High disk usage: {metrics.disk_usage:.1f}%")
        
        if metrics.network_latency >= self.thresholds['latency_critical']:
            issues.append(f"API unreachable or very slow: {metrics.network_latency:.0f}ms")
        elif metrics.network_latency >= self.thresholds['latency_warning']:
            issues.append(f"High API latency: {metrics.network_latency:.0f}ms")
        
        if not metrics.api_connectivity:
            issues.append("Delta Exchange API not reachable")
        
        if not metrics.database_status:
            issues.append("Database connectivity issue")
        
        return issues


# Global health monitor instance (start with start_monitoring())
health_monitor = SystemHealthMonitor()
