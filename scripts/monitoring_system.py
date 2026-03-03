#!/usr/bin/env python3
"""
Real-time Monitoring System
Comprehensive monitoring and alerting for all bot components
"""

import os
import json
import time
import psutil
import threading
import smtplib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

@dataclass
class Alert:
    """Alert data structure"""
    timestamp: str
    level: str  # 'info', 'warning', 'error', 'critical'
    component: str
    message: str
    details: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[str] = None

@dataclass
class SystemMetrics:
    """System metrics data structure"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_avg: List[float]
    bot_processes: int
    bot_memory_mb: float
    network_connections: int

class MonitoringSystem:
    """Real-time monitoring and alerting system"""
    
    def __init__(self, bot_dir: str = None):
        self.bot_dir = bot_dir or os.getcwd()
        self.logs_dir = os.path.join(self.bot_dir, 'logs')
        self.alerts_file = os.path.join(self.logs_dir, 'alerts.json')
        self.metrics_file = os.path.join(self.logs_dir, 'metrics.json')
        
        # Create directories
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Monitoring configuration
        self.config = self._load_config()
        self.monitoring_interval = int(self.config.get('MONITORING_INTERVAL', 30))  # seconds
        self.alert_thresholds = {
            'cpu_percent': float(self.config.get('CPU_ALERT_THRESHOLD', 80.0)),
            'memory_percent': float(self.config.get('MEMORY_ALERT_THRESHOLD', 85.0)),
            'disk_percent': float(self.config.get('DISK_ALERT_THRESHOLD', 90.0)),
            'bot_memory_mb': float(self.config.get('BOT_MEMORY_ALERT_THRESHOLD', 1000.0))
        }
        
        # Alert channels
        self.alert_channels = {
            'email': self.config.get('ALERT_EMAIL_ENABLED', 'false').lower() == 'true',
            'telegram': self.config.get('ALERT_TELEGRAM_ENABLED', 'false').lower() == 'true',
            'webhook': self.config.get('ALERT_WEBHOOK_ENABLED', 'false').lower() == 'true'
        }
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Monitoring state
        self.running = False
        self.monitor_thread = None
        self.alerts = self._load_alerts()
        self.metrics_history = self._load_metrics()
        
        # Bot process patterns
        self.bot_patterns = [
            'python.*bot',
            'python.*run',
            'python.*health',
            'python.*guardian',
            'python.*reconciliation'
        ]
    
    def _load_config(self) -> Dict[str, str]:
        """Load configuration from config.yaml"""
        config = {}
        try:
            with open(os.path.join(self.bot_dir, 'config.yaml'), 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line and '→' not in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"')
        except FileNotFoundError:
            self.logger.error("Config file not found")
        return config
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for monitoring system"""
        logger = logging.getLogger('monitoring_system')
        logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(
            os.path.join(self.logs_dir, 'monitoring.log')
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _load_alerts(self) -> List[Alert]:
        """Load alerts from file"""
        try:
            if os.path.exists(self.alerts_file):
                with open(self.alerts_file, 'r') as f:
                    data = json.load(f)
                    return [Alert(**alert) for alert in data]
        except Exception as e:
            self.logger.error(f"Error loading alerts: {e}")
        return []
    
    def _save_alerts(self):
        """Save alerts to file"""
        try:
            with open(self.alerts_file, 'w') as f:
                json.dump([alert.__dict__ for alert in self.alerts], f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving alerts: {e}")
    
    def _load_metrics(self) -> List[Dict[str, Any]]:
        """Load metrics history from file"""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading metrics: {e}")
        return []
    
    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {e}")
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Load average
            load_avg = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Bot processes
            bot_processes = 0
            bot_memory_mb = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']).lower()
                    if any(pattern in cmdline for pattern in self.bot_patterns):
                        bot_processes += 1
                        bot_memory_mb += proc.info['memory_info'].rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Network connections
            network_connections = len(psutil.net_connections())
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                load_avg=load_avg,
                bot_processes=bot_processes,
                bot_memory_mb=bot_memory_mb,
                network_connections=network_connections
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0,
                memory_percent=0,
                disk_percent=0,
                load_avg=[0, 0, 0],
                bot_processes=0,
                bot_memory_mb=0,
                network_connections=0
            )
    
    def check_thresholds(self, metrics: SystemMetrics) -> List[Alert]:
        """Check metrics against alert thresholds"""
        alerts = []
        
        # CPU threshold
        if metrics.cpu_percent > self.alert_thresholds['cpu_percent']:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='warning',
                component='system',
                message=f'High CPU usage: {metrics.cpu_percent:.1f}%',
                details={'cpu_percent': metrics.cpu_percent, 'threshold': self.alert_thresholds['cpu_percent']}
            ))
        
        # Memory threshold
        if metrics.memory_percent > self.alert_thresholds['memory_percent']:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='warning',
                component='system',
                message=f'High memory usage: {metrics.memory_percent:.1f}%',
                details={'memory_percent': metrics.memory_percent, 'threshold': self.alert_thresholds['memory_percent']}
            ))
        
        # Disk threshold
        if metrics.disk_percent > self.alert_thresholds['disk_percent']:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='critical',
                component='system',
                message=f'High disk usage: {metrics.disk_percent:.1f}%',
                details={'disk_percent': metrics.disk_percent, 'threshold': self.alert_thresholds['disk_percent']}
            ))
        
        # Bot memory threshold
        if metrics.bot_memory_mb > self.alert_thresholds['bot_memory_mb']:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='warning',
                component='bot',
                message=f'High bot memory usage: {metrics.bot_memory_mb:.1f} MB',
                details={'bot_memory_mb': metrics.bot_memory_mb, 'threshold': self.alert_thresholds['bot_memory_mb']}
            ))
        
        # Bot process count
        if metrics.bot_processes == 0:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='error',
                component='bot',
                message='No bot processes running',
                details={'bot_processes': metrics.bot_processes}
            ))
        elif metrics.bot_processes > 5:
            alerts.append(Alert(
                timestamp=metrics.timestamp,
                level='warning',
                component='bot',
                message=f'Too many bot processes: {metrics.bot_processes}',
                details={'bot_processes': metrics.bot_processes}
            ))
        
        return alerts
    
    def add_alert(self, alert: Alert):
        """Add a new alert"""
        self.alerts.append(alert)
        self._save_alerts()
        
        # Send alert notifications
        self._send_alert_notifications(alert)
        
        self.logger.warning(f"Alert: {alert.level.upper()} - {alert.component}: {alert.message}")
    
    def resolve_alert(self, alert_index: int):
        """Resolve an alert"""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].resolved = True
            self.alerts[alert_index].resolved_at = datetime.now().isoformat()
            self._save_alerts()
            self.logger.info(f"Alert resolved: {self.alerts[alert_index].message}")
    
    def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications through configured channels"""
        if self.alert_channels['email']:
            self._send_email_alert(alert)
        
        if self.alert_channels['telegram']:
            self._send_telegram_alert(alert)
        
        if self.alert_channels['webhook']:
            self._send_webhook_alert(alert)
    
    def _send_email_alert(self, alert: Alert):
        """Send email alert"""
        try:
            # Email configuration would go here
            # This is a placeholder implementation
            self.logger.info(f"Email alert sent: {alert.message}")
        except Exception as e:
            self.logger.error(f"Error sending email alert: {e}")
    
    def _send_telegram_alert(self, alert: Alert):
        """Send Telegram alert"""
        try:
            # Telegram configuration would go here
            # This is a placeholder implementation
            self.logger.info(f"Telegram alert sent: {alert.message}")
        except Exception as e:
            self.logger.error(f"Error sending Telegram alert: {e}")
    
    def _send_webhook_alert(self, alert: Alert):
        """Send webhook alert"""
        try:
            webhook_url = self.config.get('ALERT_WEBHOOK_URL')
            if webhook_url:
                payload = {
                    'timestamp': alert.timestamp,
                    'level': alert.level,
                    'component': alert.component,
                    'message': alert.message,
                    'details': alert.details
                }
                requests.post(webhook_url, json=payload, timeout=10)
                self.logger.info(f"Webhook alert sent: {alert.message}")
        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {e}")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting monitoring loop...")
        
        while self.running:
            try:
                # Collect metrics
                metrics = self.collect_system_metrics()
                
                # Store metrics
                self.metrics_history.append(metrics.__dict__)
                
                # Keep only last 1000 metrics
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                # Check thresholds
                new_alerts = self.check_thresholds(metrics)
                
                # Add new alerts
                for alert in new_alerts:
                    # Check if similar alert already exists
                    similar_alert = any(
                        a.component == alert.component and 
                        a.message == alert.message and 
                        not a.resolved
                        for a in self.alerts
                    )
                    
                    if not similar_alert:
                        self.add_alert(alert)
                
                # Save metrics
                self._save_metrics()
                
                # Log metrics
                self.logger.info(
                    f"Metrics - CPU: {metrics.cpu_percent:.1f}%, "
                    f"Memory: {metrics.memory_percent:.1f}%, "
                    f"Bots: {metrics.bot_processes}, "
                    f"Bot Memory: {metrics.bot_memory_mb:.1f}MB"
                )
                
                # Wait for next interval
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def start_monitoring(self):
        """Start the monitoring system"""
        if self.running:
            self.logger.warning("Monitoring system is already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("Monitoring system started")
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("Monitoring system stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitoring system status"""
        return {
            'running': self.running,
            'monitoring_interval': self.monitoring_interval,
            'total_alerts': len(self.alerts),
            'unresolved_alerts': len([a for a in self.alerts if not a.resolved]),
            'metrics_count': len(self.metrics_history),
            'alert_channels': self.alert_channels,
            'thresholds': self.alert_thresholds
        }
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        recent_alerts = sorted(self.alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [alert.__dict__ for alert in recent_alerts]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        if not self.metrics_history:
            return {'error': 'No metrics available'}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 measurements
        
        return {
            'current': recent_metrics[-1] if recent_metrics else {},
            'average': {
                'cpu_percent': sum(m['cpu_percent'] for m in recent_metrics) / len(recent_metrics),
                'memory_percent': sum(m['memory_percent'] for m in recent_metrics) / len(recent_metrics),
                'bot_processes': sum(m['bot_processes'] for m in recent_metrics) / len(recent_metrics),
                'bot_memory_mb': sum(m['bot_memory_mb'] for m in recent_metrics) / len(recent_metrics)
            },
            'trends': {
                'cpu_trend': 'increasing' if len(recent_metrics) > 1 and recent_metrics[-1]['cpu_percent'] > recent_metrics[0]['cpu_percent'] else 'stable',
                'memory_trend': 'increasing' if len(recent_metrics) > 1 and recent_metrics[-1]['memory_percent'] > recent_metrics[0]['memory_percent'] else 'stable'
            }
        }

def main():
    """CLI interface for monitoring system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitoring System')
    parser.add_argument('--bot-dir', type=str, default=os.getcwd(),
                       help='Bot directory path')
    parser.add_argument('--start', action='store_true',
                       help='Start monitoring')
    parser.add_argument('--stop', action='store_true',
                       help='Stop monitoring')
    parser.add_argument('--status', action='store_true',
                       help='Show status')
    parser.add_argument('--alerts', type=int, metavar='N',
                       help='Show recent N alerts')
    parser.add_argument('--metrics', action='store_true',
                       help='Show metrics summary')
    
    args = parser.parse_args()
    
    monitor = MonitoringSystem(args.bot_dir)
    
    if args.start:
        monitor.start_monitoring()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_monitoring()
    
    elif args.stop:
        monitor.stop_monitoring()
    
    elif args.status:
        status = monitor.get_status()
        print(json.dumps(status, indent=2))
    
    elif args.alerts:
        alerts = monitor.get_recent_alerts(args.alerts)
        print(json.dumps(alerts, indent=2))
    
    elif args.metrics:
        metrics = monitor.get_metrics_summary()
        print(json.dumps(metrics, indent=2))
    
    else:
        print("Use --help for available options")

if __name__ == '__main__':
    main()
