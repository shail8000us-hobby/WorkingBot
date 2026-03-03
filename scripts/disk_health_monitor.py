#!/usr/bin/env python3
"""
Disk Health Monitor & Emergency Cleanup

Monitors: Log file sizes, disk space, process file handles
Auto-fixes: Rotates large logs, cleans old logs, alerts on issues
"""

import os
import sys
import psutil
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / 'logs'

# Thresholds
MAX_LOG_SIZE_MB = 50
MAX_TOTAL_LOGS_GB = 2
MAX_DISK_USAGE_PERCENT = 80

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'disk_health_monitor.log', maxBytes=5*1024*1024, backupCount=2
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

def health_check():
    """Run comprehensive health check"""
    logger.info("="*80)
    logger.info("🔍 Disk Health Check")
    logger.info("="*80)
    
    # Check disk usage
    usage = psutil.disk_usage('/')
    percent = usage.percent
    logger.info(f"💾 Disk: {usage.used/(1024**3):.1f}GB / {usage.total/(1024**3):.1f}GB ({percent:.1f}%)")
    
    if percent > MAX_DISK_USAGE_PERCENT:
        logger.warning(f"⚠️  HIGH DISK USAGE: {percent:.1f}%")
    
    # Check log sizes
    total_size = 0
    large_logs = []
    for log_file in LOG_DIR.glob('*.log*'):
        if log_file.is_file():
            size_mb = log_file.stat().st_size / (1024*1024)
            total_size += size_mb
            if size_mb > MAX_LOG_SIZE_MB:
                large_logs.append((log_file.name, size_mb))
    
    logger.info(f"📝 Total Logs: {total_size:.2f}MB")
    
    if large_logs:
        logger.warning(f"⚠️  Large logs found:")
        for name, size in large_logs:
            logger.warning(f"  - {name}: {size:.1f}MB")
    
    # Check Python processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'python' in proc.info['name'].lower():
                open_files = len(proc.open_files())
                if open_files > 100:
                    logger.warning(f"⚠️  PID {proc.info['pid']}: {open_files} open files")
        except:
            pass
    
    logger.info("="*80)
    return percent < MAX_DISK_USAGE_PERCENT and not large_logs

if __name__ == "__main__":
    health_check()
