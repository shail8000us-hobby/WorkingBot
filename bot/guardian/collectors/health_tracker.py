"""
Health Tracker - Manages guardian health status and heartbeat
"""
import logging
import json
import time
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


class HealthTracker:
    """Tracks and reports guardian health status"""
    
    def __init__(self, config, base_dir: Path):
        """
        Initialize health tracker
        
        Args:
            config: Guardian configuration (RootConfig or dict)
            base_dir: Base directory for health files
        """
        self.config = config
        self.base_dir = base_dir
        
        # Handle both RootConfig and dict
        if hasattr(config, 'guardian'):
            # RootConfig object
            health_file_name = getattr(config.guardian, 'HEALTH_FILE', '.guardian_health')
            pid_file_name = getattr(config.guardian, 'PID_FILE', '.guardian.pid')
        else:
            # Dict fallback
            health_file_name = config.get('GUARDIAN_HEALTH_FILE', '.guardian_health')
            pid_file_name = config.get('GUARDIAN_PID_FILE', '.guardian.pid')
        
        self.health_file = self.base_dir / health_file_name
        self.pid_file = self.base_dir / pid_file_name
        
        self.pid = os.getpid()
        self.start_time = time.time()
        self.cycle_count = 0
        self.last_check_time = None
        
        logger.info(f"HealthTracker initialized: PID={self.pid}")
    
    def update_health(self, monitoring_result: Optional[Dict] = None):
        """
        Update health status file
        
        Args:
            monitoring_result: Latest monitoring cycle results
        """
        self.update_health_data(monitoring_result)
    
    def update_health_data(self, monitoring_result: Optional[Dict] = None):
        """
        Update health status file (legacy method name for compatibility)
        
        Args:
            monitoring_result: Latest monitoring cycle results OR custom health dict
        """
        try:
            # Check if this is a pre-formatted health dict from guardian_bot
            if monitoring_result and 'guardian_version' in monitoring_result:
                # Use the provided data directly, just add metadata
                health_data = monitoring_result.copy()
                health_data['timestamp'] = time.time()
                health_data['uptime_seconds'] = int(time.time() - self.start_time)
                health_data['cycle_count'] = self.cycle_count
            else:
                # Legacy path: build from monitoring_result
                health_data = {
                    'timestamp': time.time(),
                    'status': 'ok',
                    'pid': self.pid,
                    'uptime_seconds': int(time.time() - self.start_time),
                    'cycle_count': self.cycle_count,
                    'last_check': self.last_check_time,
                }
                
                # Add monitoring summary if available
                if monitoring_result and 'total_summary' in monitoring_result:
                    summary = monitoring_result['total_summary']
                    health_data['monitoring'] = {
                        'position_count': summary.get('position_count', 0),
                        'total_pnl_inr': summary.get('total_pnl_inr', 0),
                        'total_loss_inr': summary.get('total_loss_inr', 0),
                    }
                
                # Add liquidation data if available
                if monitoring_result and 'liquidation' in monitoring_result:
                    health_data['liquidation'] = monitoring_result['liquidation']
            
            # Write health file
            with open(self.health_file, 'w') as f:
                json.dump(health_data, f, indent=2)
            
            self.last_check_time = time.time()
            self.cycle_count += 1
            
        except Exception as e:
            logger.error(f"Error updating health file: {e}")
    
    def write_pid_file(self):
        """Write PID file for process management"""
        try:
            self.pid_file.write_text(str(self.pid))
            logger.info(f"PID file created: {self.pid_file}")
        except Exception as e:
            logger.error(f"Error writing PID file: {e}")
    
    def remove_pid_file(self):
        """Remove PID file on shutdown"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info("PID file removed")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
    
    def remove_health_file(self):
        """Remove health file on shutdown"""
        try:
            if self.health_file.exists():
                self.health_file.unlink()
                logger.info("Health file removed")
        except Exception as e:
            logger.error(f"Error removing health file: {e}")
    
    def get_uptime(self) -> str:
        """
        Get formatted uptime string
        
        Returns:
            Human-readable uptime
        """
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        return f"{hours}h {minutes}m {seconds}s"
    
    def get_status_summary(self) -> str:
        """
        Get formatted status summary
        
        Returns:
            Status summary string
        """
        uptime = self.get_uptime()
        return (
            f"Guardian Status: PID={self.pid} | "
            f"Uptime={uptime} | "
            f"Cycles={self.cycle_count}"
        )
    
    @staticmethod
    def is_guardian_running(health_file_path: Path, timeout: int = 30) -> bool:
        """
        Check if guardian is running based on health file
        
        Args:
            health_file_path: Path to health file
            timeout: Max age of health file in seconds
            
        Returns:
            True if guardian appears to be running
        """
        try:
            if not health_file_path.exists():
                return False
            
            with open(health_file_path, 'r') as f:
                health_data = json.load(f)
            
            timestamp = health_data.get('timestamp', 0)
            age = time.time() - timestamp
            
            return age < timeout
            
        except Exception:
            return False

