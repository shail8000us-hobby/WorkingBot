#!/usr/bin/env python3
"""
Emergency Log Cleanup Script
Runs on macOS to prevent disk space exhaustion from trading bot logs

Automatically deletes:
- Log files > 500MB
- Error logs > 100MB
- PM2 logs > 100MB
- Old database backups > 30 days
- Old event databases

Run manually: python3 emergency_log_cleanup.py
Or schedule with cron: */30 * * * * cd /Users/ssr/Projects/WorkingBot && python3 emergency_log_cleanup.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Setup
PROJECT_ROOT = Path(__file__).parent
LOG_SIZE_THRESHOLD_MB = 500
ERROR_LOG_THRESHOLD_MB = 100
PM2_LOG_THRESHOLD_MB = 100
OLD_FILE_DAYS = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / 'logs' / 'emergency_cleanup.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in MB"""
    try:
        return filepath.stat().st_size / (1024 * 1024)
    except:
        return 0


def get_file_age_days(filepath: Path) -> int:
    """Get file age in days"""
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        return (datetime.now() - mtime).days
    except:
        return 0


def cleanup_large_logs():
    """Clean up oversized log files"""
    log.info("=" * 80)
    log.info("Emergency Log Cleanup Started")
    log.info("=" * 80)
    
    total_freed_mb = 0
    files_deleted = 0
    
    # Find all log files
    log_patterns = [
        'logs/**/*.log',
        'reports/**/*.log',
        'bot/logs/**/*.log',
        'webui/backend/logs/**/*.log',
    ]
    
    for pattern in log_patterns:
        for log_file in PROJECT_ROOT.glob(pattern):
            if not log_file.is_file():
                continue
            
            size_mb = get_file_size_mb(log_file)
            
            # Check if file should be deleted
            should_delete = False
            reason = ""
            
            if 'error' in log_file.name.lower() and size_mb > ERROR_LOG_THRESHOLD_MB:
                should_delete = True
                reason = f"error log > {ERROR_LOG_THRESHOLD_MB}MB"
            elif 'pm2' in log_file.name.lower() and size_mb > PM2_LOG_THRESHOLD_MB:
                should_delete = True
                reason = f"PM2 log > {PM2_LOG_THRESHOLD_MB}MB"
            elif size_mb > LOG_SIZE_THRESHOLD_MB:
                should_delete = True
                reason = f"log > {LOG_SIZE_THRESHOLD_MB}MB"
            
            if should_delete:
                try:
                    log.warning(f"Deleting {log_file.name} ({size_mb:.1f}MB) - {reason}")
                    log_file.unlink()
                    total_freed_mb += size_mb
                    files_deleted += 1
                except Exception as e:
                    log.error(f"Failed to delete {log_file}: {e}")
    
    # Clean up old database backups
    for db_file in PROJECT_ROOT.glob('**/*_backup_*.db'):
        age_days = get_file_age_days(db_file)
        size_mb = get_file_size_mb(db_file)
        
        if age_days > OLD_FILE_DAYS:
            try:
                log.warning(f"Deleting old backup {db_file.name} ({size_mb:.1f}MB, {age_days} days old)")
                db_file.unlink()
                total_freed_mb += size_mb
                files_deleted += 1
            except Exception as e:
                log.error(f"Failed to delete {db_file}: {e}")
    
    # Clean up old event databases (except main ones)
    exclude_dbs = {'bot_events.db', 'volatility.db', 'metrics.db', 'gridbot_events.db'}
    for db_file in PROJECT_ROOT.glob('**/*.db'):
        if db_file.name in exclude_dbs:
            continue
        
        if 'LONG' in db_file.name or 'OLD' in db_file.name or 'backup' in db_file.name:
            size_mb = get_file_size_mb(db_file)
            age_days = get_file_age_days(db_file)
            
            if size_mb > 50 or age_days > OLD_FILE_DAYS:
                try:
                    log.warning(f"Deleting old database {db_file.name} ({size_mb:.1f}MB, {age_days} days old)")
                    db_file.unlink()
                    total_freed_mb += size_mb
                    files_deleted += 1
                except Exception as e:
                    log.error(f"Failed to delete {db_file}: {e}")
    
    log.info("=" * 80)
    log.info(f"Cleanup Complete:")
    log.info(f"  - Files deleted: {files_deleted}")
    log.info(f"  - Space freed: {total_freed_mb:.1f} MB ({total_freed_mb/1024:.2f} GB)")
    log.info("=" * 80)
    
    return total_freed_mb, files_deleted


def check_disk_space():
    """Check current disk usage"""
    try:
        import shutil
        total, used, free = shutil.disk_usage(PROJECT_ROOT)
        
        log.info(f"Disk Space:")
        log.info(f"  - Total: {total // (2**30)} GB")
        log.info(f"  - Used: {used // (2**30)} GB ({used/total*100:.1f}%)")
        log.info(f"  - Free: {free // (2**30)} GB ({free/total*100:.1f}%)")
        
        return free / total * 100
    except Exception as e:
        log.error(f"Failed to check disk space: {e}")
        return 100


if __name__ == "__main__":
    try:
        # Check disk space
        free_percent = check_disk_space()
        
        # Run cleanup
        freed_mb, files_deleted = cleanup_large_logs()
        
        if files_deleted == 0:
            log.info("✅ No cleanup needed - all logs are within size limits")
        else:
            log.info(f"✅ Cleanup successful - freed {freed_mb/1024:.2f} GB")
        
        # Check disk space again
        free_percent_after = check_disk_space()
        
        if free_percent_after > free_percent:
            log.info(f"📈 Disk space improved: {free_percent:.1f}% → {free_percent_after:.1f}% free")
        
    except Exception as e:
        log.error(f"Emergency cleanup failed: {e}")
        sys.exit(1)
