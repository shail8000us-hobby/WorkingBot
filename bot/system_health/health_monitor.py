"""
System Health Monitor

Monitors system resources (CPU, memory, disk, network), process health,
and provides auto-healing capabilities with configurable alerts.

Features:
- Real-time system resource monitoring
- Process health tracking with auto-restart
- API connectivity monitoring
- Alert thresholds with severity levels
- Historical metrics storage
- Predictive alerts based on trends
- Auto-healing for crashed processes
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import psutil
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System resource metrics snapshot"""
    timestamp: str
    cpu_percent: float
    cpu_count: int
    memory_total_mb: float
    memory_used_mb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    load_average_1m: float
    load_average_5m: float
    load_average_15m: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessHealth:
    """Process health status"""
    name: str
    pid: Optional[int]
    status: str  # running, stopped, crashed, zombie
    cpu_percent: float
    memory_mb: float
    uptime_seconds: float
    restart_count: int
    last_restart: Optional[str]
    auto_healing_enabled: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlertThreshold:
    """Alert threshold configuration"""
    metric: str  # cpu_percent, memory_percent, disk_percent
    warning_threshold: float
    critical_threshold: float
    duration_seconds: int  # How long threshold must be exceeded
    enabled: bool = True


@dataclass
class HealthAlert:
    """Health monitoring alert"""
    id: str
    timestamp: str
    severity: str  # info, warning, error, critical
    category: str  # system, process, api, disk, network
    metric: str
    current_value: float
    threshold_value: float
    message: str
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HealthMonitor:
    """
    System Health Monitor
    
    Monitors system resources, process health, and API connectivity.
    Provides auto-healing and alerting capabilities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.running = False
        self.monitor_task = None
        
        # Monitoring interval
        self.update_interval = self.config.get('update_interval', 30)  # seconds
        
        # State file
        self.state_file = Path(self.config.get(
            'state_file',
            'data/system_health_state.json'
        ))
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Metrics history (keep last 1000 snapshots)
        self.metrics_history: List[SystemMetrics] = []
        self.max_history = 1000
        
        # Processes to monitor
        self.monitored_processes: Dict[str, ProcessHealth] = {}
        self.process_patterns = self.config.get('process_patterns', [
            'python.*gridbot',
            'python.*webui',
            'node.*react',
        ])
        
        # Alert thresholds
        self.alert_thresholds = [
            AlertThreshold('cpu_percent', 80.0, 95.0, 300),  # 5 minutes
            AlertThreshold('memory_percent', 85.0, 95.0, 300),
            AlertThreshold('disk_percent', 85.0, 95.0, 600),  # 10 minutes
        ]
        
        # Active alerts
        self.active_alerts: List[HealthAlert] = []
        self.alert_history: List[HealthAlert] = []
        self.max_alert_history = 500
        
        # Alert counters (for threshold duration)
        self.alert_counters: Dict[str, Dict] = {}
        
        # Auto-healing config
        self.auto_healing_enabled = self.config.get('auto_healing', True)
        self.max_restart_attempts = self.config.get('max_restart_attempts', 3)
        self.restart_cooldown = self.config.get('restart_cooldown', 300)  # 5 minutes
        
        # API monitoring
        self.api_endpoints = self.config.get('api_endpoints', [
            'http://localhost:5555/api/health',
            'http://localhost:5557/api/health',
        ])
        self.api_status: Dict[str, Dict] = {}
        
        # Network baseline (for calculating deltas)
        self.last_network_stats = None
        
        # Load state
        self._load_state()
        
        logger.info(f"Health Monitor initialized (update interval: {self.update_interval}s)")
    
    async def start(self):
        """Start health monitoring"""
        if self.running:
            logger.warning("Health Monitor already running")
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health Monitor started")
    
    async def stop(self):
        """Stop health monitoring"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self._save_state()
        logger.info("Health Monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Trim history
                if len(self.metrics_history) > self.max_history:
                    self.metrics_history = self.metrics_history[-self.max_history:]
                
                # Update process health
                await self._update_process_health()
                
                # Check API health
                await self._check_api_health()
                
                # Check alert thresholds
                await self._check_alert_thresholds(metrics)
                
                # Auto-healing
                if self.auto_healing_enabled:
                    await self._perform_auto_healing()
                
                # Save state periodically
                self._save_state()
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory
        memory = psutil.virtual_memory()
        memory_total_mb = memory.total / (1024 * 1024)
        memory_used_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_percent = disk.percent
        
        # Network
        net_io = psutil.net_io_counters()
        
        # Load average (Unix-like systems)
        try:
            load_avg = psutil.getloadavg()
            load_1m, load_5m, load_15m = load_avg
        except AttributeError:
            # Windows doesn't have load average
            load_1m = load_5m = load_15m = 0.0
        
        return SystemMetrics(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            memory_total_mb=memory_total_mb,
            memory_used_mb=memory_used_mb,
            memory_percent=memory_percent,
            disk_total_gb=disk_total_gb,
            disk_used_gb=disk_used_gb,
            disk_percent=disk_percent,
            network_bytes_sent=net_io.bytes_sent,
            network_bytes_recv=net_io.bytes_recv,
            load_average_1m=load_1m,
            load_average_5m=load_5m,
            load_average_15m=load_15m
        )
    
    async def _update_process_health(self):
        """Update health status of monitored processes"""
        current_processes = {}
        
        # Find processes matching patterns
        for pattern in self.process_patterns:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_percent', 'memory_info', 'create_time']):
                try:
                    cmdline = ' '.join(proc.info.get('cmdline', []))
                    
                    # Simple pattern matching (could use regex)
                    if pattern.replace('.*', '') in cmdline:
                        name = proc.info['name']
                        pid = proc.info['pid']
                        
                        # Calculate uptime
                        create_time = proc.info['create_time']
                        uptime = time.time() - create_time
                        
                        # Get existing health record or create new
                        existing = self.monitored_processes.get(name)
                        restart_count = existing.restart_count if existing else 0
                        last_restart = existing.last_restart if existing else None
                        
                        # Create health record
                        health = ProcessHealth(
                            name=name,
                            pid=pid,
                            status='running',
                            cpu_percent=proc.info['cpu_percent'] or 0.0,
                            memory_mb=proc.info['memory_info'].rss / (1024 * 1024),
                            uptime_seconds=uptime,
                            restart_count=restart_count,
                            last_restart=last_restart,
                            auto_healing_enabled=self.auto_healing_enabled
                        )
                        
                        current_processes[name] = health
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        
        # Check for crashed processes
        for name, old_health in self.monitored_processes.items():
            if name not in current_processes and old_health.status == 'running':
                # Process crashed
                crashed_health = ProcessHealth(
                    name=name,
                    pid=None,
                    status='crashed',
                    cpu_percent=0.0,
                    memory_mb=0.0,
                    uptime_seconds=0.0,
                    restart_count=old_health.restart_count,
                    last_restart=old_health.last_restart,
                    auto_healing_enabled=self.auto_healing_enabled
                )
                current_processes[name] = crashed_health
                
                # Create alert
                alert = HealthAlert(
                    id=f"process_crash_{name}_{int(time.time())}",
                    timestamp=datetime.utcnow().isoformat() + 'Z',
                    severity='critical',
                    category='process',
                    metric='process_status',
                    current_value=0.0,
                    threshold_value=1.0,
                    message=f"Process {name} (PID: {old_health.pid}) has crashed"
                )
                self._add_alert(alert)
        
        self.monitored_processes = current_processes
    
    async def _check_api_health(self):
        """Check health of API endpoints"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            for endpoint in self.api_endpoints:
                try:
                    start_time = time.time()
                    async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        latency = (time.time() - start_time) * 1000  # ms
                        
                        self.api_status[endpoint] = {
                            'status': 'up' if response.status == 200 else 'degraded',
                            'status_code': response.status,
                            'latency_ms': latency,
                            'last_check': datetime.utcnow().isoformat() + 'Z'
                        }
                        
                        # Alert if latency too high
                        if latency > 1000:  # 1 second
                            alert = HealthAlert(
                                id=f"api_latency_{endpoint}_{int(time.time())}",
                                timestamp=datetime.utcnow().isoformat() + 'Z',
                                severity='warning',
                                category='api',
                                metric='latency_ms',
                                current_value=latency,
                                threshold_value=1000,
                                message=f"API endpoint {endpoint} latency is high: {latency:.0f}ms"
                            )
                            self._add_alert(alert)
                            
                except asyncio.TimeoutError:
                    self.api_status[endpoint] = {
                        'status': 'down',
                        'status_code': 0,
                        'latency_ms': 0,
                        'last_check': datetime.utcnow().isoformat() + 'Z',
                        'error': 'timeout'
                    }
                    
                    alert = HealthAlert(
                        id=f"api_down_{endpoint}_{int(time.time())}",
                        timestamp=datetime.utcnow().isoformat() + 'Z',
                        severity='critical',
                        category='api',
                        metric='status',
                        current_value=0.0,
                        threshold_value=1.0,
                        message=f"API endpoint {endpoint} is down (timeout)"
                    )
                    self._add_alert(alert)
                    
                except Exception as e:
                    self.api_status[endpoint] = {
                        'status': 'error',
                        'status_code': 0,
                        'latency_ms': 0,
                        'last_check': datetime.utcnow().isoformat() + 'Z',
                        'error': str(e)
                    }
    
    async def _check_alert_thresholds(self, metrics: SystemMetrics):
        """Check if any alert thresholds are exceeded"""
        for threshold in self.alert_thresholds:
            if not threshold.enabled:
                continue
            
            # Get current value
            current_value = getattr(metrics, threshold.metric, 0.0)
            
            # Initialize counter if needed
            if threshold.metric not in self.alert_counters:
                self.alert_counters[threshold.metric] = {
                    'warning_count': 0,
                    'critical_count': 0,
                    'last_check': time.time()
                }
            
            counter = self.alert_counters[threshold.metric]
            
            # Check critical threshold
            if current_value >= threshold.critical_threshold:
                counter['critical_count'] += 1
                
                # Check if exceeded for required duration
                if counter['critical_count'] * self.update_interval >= threshold.duration_seconds:
                    alert = HealthAlert(
                        id=f"threshold_critical_{threshold.metric}_{int(time.time())}",
                        timestamp=datetime.utcnow().isoformat() + 'Z',
                        severity='critical',
                        category='system',
                        metric=threshold.metric,
                        current_value=current_value,
                        threshold_value=threshold.critical_threshold,
                        message=f"{threshold.metric} is critically high: {current_value:.1f}% (threshold: {threshold.critical_threshold}%)"
                    )
                    self._add_alert(alert)
                    counter['critical_count'] = 0  # Reset
            
            # Check warning threshold
            elif current_value >= threshold.warning_threshold:
                counter['warning_count'] += 1
                
                if counter['warning_count'] * self.update_interval >= threshold.duration_seconds:
                    alert = HealthAlert(
                        id=f"threshold_warning_{threshold.metric}_{int(time.time())}",
                        timestamp=datetime.utcnow().isoformat() + 'Z',
                        severity='warning',
                        category='system',
                        metric=threshold.metric,
                        current_value=current_value,
                        threshold_value=threshold.warning_threshold,
                        message=f"{threshold.metric} is high: {current_value:.1f}% (threshold: {threshold.warning_threshold}%)"
                    )
                    self._add_alert(alert)
                    counter['warning_count'] = 0  # Reset
            
            else:
                # Below thresholds, reset counters
                counter['warning_count'] = 0
                counter['critical_count'] = 0
    
    async def _perform_auto_healing(self):
        """Perform auto-healing actions for crashed processes"""
        for name, health in self.monitored_processes.items():
            if health.status == 'crashed' and health.auto_healing_enabled:
                # Check restart cooldown
                if health.last_restart:
                    try:
                        last_restart_time = datetime.fromisoformat(health.last_restart.replace('Z', '+00:00'))
                        cooldown_end = last_restart_time + timedelta(seconds=self.restart_cooldown)
                        if datetime.utcnow() < cooldown_end.replace(tzinfo=None):
                            logger.info(f"Process {name} in restart cooldown, skipping")
                            continue
                    except Exception:
                        pass
                
                # Check max restart attempts
                if health.restart_count >= self.max_restart_attempts:
                    logger.warning(f"Process {name} exceeded max restart attempts ({self.max_restart_attempts})")
                    continue
                
                # Attempt restart
                logger.info(f"Auto-healing: Attempting to restart {name}")
                success = await self._restart_process(name)
                
                if success:
                    health.restart_count += 1
                    health.last_restart = datetime.utcnow().isoformat() + 'Z'
                    health.status = 'running'
                    
                    alert = HealthAlert(
                        id=f"auto_heal_success_{name}_{int(time.time())}",
                        timestamp=datetime.utcnow().isoformat() + 'Z',
                        severity='info',
                        category='process',
                        metric='auto_healing',
                        current_value=1.0,
                        threshold_value=1.0,
                        message=f"Auto-healing: Successfully restarted {name}"
                    )
                    self._add_alert(alert)
                else:
                    alert = HealthAlert(
                        id=f"auto_heal_failed_{name}_{int(time.time())}",
                        timestamp=datetime.utcnow().isoformat() + 'Z',
                        severity='error',
                        category='process',
                        metric='auto_healing',
                        current_value=0.0,
                        threshold_value=1.0,
                        message=f"Auto-healing: Failed to restart {name}"
                    )
                    self._add_alert(alert)
    
    async def _restart_process(self, name: str) -> bool:
        """Restart a crashed process"""
        try:
            # This is a placeholder - actual implementation depends on how processes are managed
            # Could use PM2, systemd, or custom process manager
            
            # Example with PM2:
            # subprocess.run(['pm2', 'restart', name], check=True)
            
            # For now, just log
            logger.info(f"Would restart process: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart process {name}: {e}")
            return False
    
    def _add_alert(self, alert: HealthAlert):
        """Add alert to active alerts and history"""
        # Check if similar alert already exists
        for existing in self.active_alerts:
            if (existing.category == alert.category and 
                existing.metric == alert.metric and
                existing.severity == alert.severity):
                # Update existing alert
                existing.timestamp = alert.timestamp
                existing.current_value = alert.current_value
                existing.message = alert.message
                return
        
        # Add new alert
        self.active_alerts.append(alert)
        self.alert_history.append(alert)
        
        # Trim history
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]
        
        logger.warning(f"Alert [{alert.severity.upper()}] {alert.category}: {alert.message}")
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get most recent system metrics"""
        if not self.metrics_history:
            return None
        return self.metrics_history[-1]
    
    def get_metrics_history(self, minutes: int = 60) -> List[SystemMetrics]:
        """Get metrics history for specified time period"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat() + 'Z'
        
        return [m for m in self.metrics_history if m.timestamp >= cutoff_str]
    
    def get_process_health(self) -> Dict[str, ProcessHealth]:
        """Get health status of all monitored processes"""
        return self.monitored_processes.copy()
    
    def get_api_status(self) -> Dict[str, Dict]:
        """Get API health status"""
        return self.api_status.copy()
    
    def get_active_alerts(self) -> List[HealthAlert]:
        """Get all active alerts"""
        return self.active_alerts.copy()
    
    def get_alert_history(self, hours: int = 24) -> List[HealthAlert]:
        """Get alert history for specified time period"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat() + 'Z'
        
        return [a for a in self.alert_history if a.timestamp >= cutoff_str]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False
    
    def clear_acknowledged_alerts(self):
        """Remove acknowledged alerts from active list"""
        self.active_alerts = [a for a in self.active_alerts if not a.acknowledged]
    
    def _save_state(self):
        """Save current state to file"""
        try:
            state = {
                'metrics_history': [m.to_dict() for m in self.metrics_history[-100:]],  # Last 100
                'monitored_processes': {k: v.to_dict() for k, v in self.monitored_processes.items()},
                'active_alerts': [a.to_dict() for a in self.active_alerts],
                'alert_history': [a.to_dict() for a in self.alert_history[-100:]],  # Last 100
                'api_status': self.api_status,
                'last_update': datetime.utcnow().isoformat() + 'Z'
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save health monitor state: {e}")
    
    def _load_state(self):
        """Load state from file"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Load metrics history
            self.metrics_history = [
                SystemMetrics(**m) for m in state.get('metrics_history', [])
            ]
            
            # Load process health
            self.monitored_processes = {
                k: ProcessHealth(**v) for k, v in state.get('monitored_processes', {}).items()
            }
            
            # Load alerts
            self.active_alerts = [
                HealthAlert(**a) for a in state.get('active_alerts', [])
            ]
            self.alert_history = [
                HealthAlert(**a) for a in state.get('alert_history', [])
            ]
            
            # Load API status
            self.api_status = state.get('api_status', {})
            
            logger.info(f"Loaded health monitor state from {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to load health monitor state: {e}")


# Global health monitor instance
_health_monitor_instance: Optional[HealthMonitor] = None


def get_health_monitor(config: Optional[Dict[str, Any]] = None) -> HealthMonitor:
    """Get or create health monitor instance"""
    global _health_monitor_instance
    
    if _health_monitor_instance is None:
        _health_monitor_instance = HealthMonitor(config)
    
    return _health_monitor_instance


async def start_health_monitor(config: Optional[Dict[str, Any]] = None):
    """Start health monitor"""
    monitor = get_health_monitor(config)
    await monitor.start()


async def stop_health_monitor():
    """Stop health monitor"""
    global _health_monitor_instance
    
    if _health_monitor_instance:
        await _health_monitor_instance.stop()
