#!/usr/bin/env python3
"""
Storage Guardian - Prevents disk space exhaustion

Monitors and manages bot storage usage automatically:
- Rotates large log files
- Cleans up old database records  
- Removes temporary debug files
- Compresses old archives
- Reports storage usage

Run manually: python3 storage_guardian.py
Or via cron: */15 * * * * cd /Users/ssr/Projects/WorkingBot && python3 storage_guardian.py

Created: January 15, 2026
"""

import os
import sys
import gzip
import shutil
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Configuration
PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / 'bot' / 'logs'
DATA_DIR = PROJECT_ROOT / 'data'
WEBUI_DIR = PROJECT_ROOT / 'webui'

# Size thresholds
MAX_LOG_SIZE_MB = 100
MAX_DB_SIZE_MB = 500
MAX_TEMP_FILE_SIZE_MB = 50

# Retention policies
LOG_RETENTION_DAYS = 3
DB_RETENTION_DAYS = 7
TEMP_FILE_RETENTION_HOURS = 24
BACKUP_RETENTION_DAYS = 14

# Setup logging
log_file = LOG_DIR / 'storage_guardian.log'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StorageGuardian:
    """Manages bot storage to prevent disk exhaustion"""
    
    def __init__(self):
        self.stats = {
            'logs_rotated': 0,
            'logs_compressed': 0,
            'temp_files_deleted': 0,
            'db_records_deleted': 0,
            'space_freed_mb': 0
        }
    
    def run(self):
        """Run all storage management tasks"""
        logger.info("=" * 80)
        logger.info("Storage Guardian - Starting cleanup")
        logger.info("=" * 80)
        
        try:
            self.cleanup_large_logs()
            self.cleanup_temp_files()
            self.cleanup_old_databases()
            self.compress_old_logs()
            self.cleanup_pm2_logs()
            self.report_storage_usage()
            
            logger.info(f"\n✅ Cleanup completed:")
            logger.info(f"   - Logs rotated: {self.stats['logs_rotated']}")
            logger.info(f"   - Logs compressed: {self.stats['logs_compressed']}")
            logger.info(f"   - Temp files deleted: {self.stats['temp_files_deleted']}")
            logger.info(f"   - DB records cleaned: {self.stats['db_records_deleted']}")
            logger.info(f"   - Space freed: ~{self.stats['space_freed_mb']:.1f} MB")
            
        except Exception as e:
            logger.error(f"Error in storage guardian: {e}", exc_info=True)
    
    def cleanup_large_logs(self):
        """Rotate large log files"""
        logger.info("\n🔍 Checking for large log files...")
        
        log_patterns = ['**/*.log', '**/*.jsonl', '**/*.txt']
        
        for pattern in log_patterns:
            for log_file in PROJECT_ROOT.glob(pattern):
                try:
                    if not log_file.is_file():
                        continue
                    
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    
                    if size_mb > MAX_LOG_SIZE_MB:
                        logger.warning(f"   Large file: {log_file.name} ({size_mb:.1f} MB)")
                        self._rotate_file(log_file)
                        self.stats['logs_rotated'] += 1
                        self.stats['space_freed_mb'] += size_mb * 0.7  # Estimate
                        
                except Exception as e:
                    logger.error(f"   Error checking {log_file}: {e}")
    
    def _rotate_file(self, filepath: Path, keep_last_lines: int = 1000):
        """Rotate a large file, keeping only recent entries"""
        try:
            backup_path = filepath.with_suffix(filepath.suffix + '.old')
            
            # If file is a log, keep last N lines
            if filepath.suffix in ['.log', '.txt']:
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                
                # Keep only last N lines
                if len(lines) > keep_last_lines:
                    # Move old content to backup
                    with open(backup_path, 'w') as f:
                        f.writelines(lines[:-keep_last_lines])
                    
                    # Keep recent content in original file
                    with open(filepath, 'w') as f:
                        f.writelines(lines[-keep_last_lines:])
                    
                    logger.info(f"   ✂️  Rotated {filepath.name}: kept last {keep_last_lines} lines")
            else:
                # For other files, just move to backup
                shutil.move(str(filepath), str(backup_path))
                logger.info(f"   📦 Moved {filepath.name} to {backup_path.name}")
                
        except Exception as e:
            logger.error(f"   Error rotating {filepath}: {e}")
    
    def cleanup_temp_files(self):
        """Remove old temporary files"""
        logger.info("\n🗑️  Cleaning temporary files...")
        
        temp_locations = [
            '/tmp/sl_tp_monitor_debug.txt',
            '/tmp/bot_*.log',
            '/tmp/guardian_*.log',
            PROJECT_ROOT / 'tmp',
            PROJECT_ROOT / '.tmp'
        ]
        
        cutoff_time = datetime.now() - timedelta(hours=TEMP_FILE_RETENTION_HOURS)
        
        for location in temp_locations:
            if isinstance(location, str):
                # Handle glob patterns
                if '*' in location:
                    import glob
                    for file in glob.glob(location):
                        self._delete_if_old(Path(file), cutoff_time)
                else:
                    self._delete_if_old(Path(location), cutoff_time)
            elif location.exists():
                if location.is_dir():
                    for file in location.rglob('*'):
                        if file.is_file():
                            self._delete_if_old(file, cutoff_time)
                else:
                    self._delete_if_old(location, cutoff_time)
    
    def _delete_if_old(self, filepath: Path, cutoff_time: datetime):
        """Delete file if older than cutoff time"""
        try:
            if not filepath.exists():
                return
            
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            
            if mtime < cutoff_time:
                size_mb = filepath.stat().st_size / (1024 * 1024)
                filepath.unlink()
                logger.info(f"   🗑️  Deleted: {filepath.name} ({size_mb:.2f} MB)")
                self.stats['temp_files_deleted'] += 1
                self.stats['space_freed_mb'] += size_mb
                
        except Exception as e:
            logger.debug(f"   Error deleting {filepath}: {e}")
    
    def cleanup_old_databases(self):
        """Clean old records from databases"""
        logger.info("\n🗄️  Cleaning database records...")
        
        db_files = [
            PROJECT_ROOT / 'bot_events_LONG.db',
            PROJECT_ROOT / 'metrics.db',
            PROJECT_ROOT / 'volatility.db',
            DATA_DIR / 'metrics.db',
            WEBUI_DIR / 'backend' / 'options_strategy' / 'sl_tp.db'
        ]
        
        cutoff_date = (datetime.now() - timedelta(days=DB_RETENTION_DAYS)).isoformat()
        
        for db_file in db_files:
            if not db_file.exists():
                continue
            
            try:
                size_before = db_file.stat().st_size / (1024 * 1024)
                
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # Find tables with timestamp columns
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                deleted_total = 0
                for table in tables:
                    # Try common timestamp column names
                    for ts_col in ['timestamp', 'created_at', 'updated_at', 'detected_at']:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {ts_col} < ?", (cutoff_date,))
                            count = cursor.fetchone()[0]
                            
                            if count > 0:
                                cursor.execute(f"DELETE FROM {table} WHERE {ts_col} < ?", (cutoff_date,))
                                deleted_total += count
                                logger.info(f"   🧹 {db_file.name}.{table}: deleted {count} old records")
                                break
                        except sqlite3.OperationalError:
                            continue
                
                conn.commit()
                conn.execute("VACUUM")  # Reclaim space
                conn.close()
                
                size_after = db_file.stat().st_size / (1024 * 1024)
                space_freed = size_before - size_after
                
                if deleted_total > 0:
                    logger.info(f"   💾 {db_file.name}: freed {space_freed:.1f} MB")
                    self.stats['db_records_deleted'] += deleted_total
                    self.stats['space_freed_mb'] += space_freed
                    
            except Exception as e:
                logger.error(f"   Error cleaning {db_file.name}: {e}")
    
    def compress_old_logs(self):
        """Compress old log files"""
        logger.info("\n🗜️  Compressing old logs...")
        
        cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        
        for log_file in PROJECT_ROOT.rglob('*.log'):
            try:
                if not log_file.is_file() or log_file.suffix == '.gz':
                    continue
                
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                if mtime < cutoff_date:
                    size_before = log_file.stat().st_size / (1024 * 1024)
                    
                    if size_before > 1:  # Only compress files > 1MB
                        gz_path = log_file.with_suffix(log_file.suffix + '.gz')
                        
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(gz_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        log_file.unlink()
                        
                        size_after = gz_path.stat().st_size / (1024 * 1024)
                        space_freed = size_before - size_after
                        
                        logger.info(f"   📦 Compressed: {log_file.name} ({size_before:.1f} MB → {size_after:.1f} MB)")
                        self.stats['logs_compressed'] += 1
                        self.stats['space_freed_mb'] += space_freed
                        
            except Exception as e:
                logger.debug(f"   Error compressing {log_file}: {e}")
    
    def cleanup_pm2_logs(self):
        """Clean up PM2 logs which can grow very large"""
        logger.info("\n🚀 Cleaning PM2 logs...")
        
        pm2_log_dirs = [
            Path.home() / '.pm2' / 'logs',
            PROJECT_ROOT / '.pm2' / 'logs'
        ]
        
        for log_dir in pm2_log_dirs:
            if not log_dir.exists():
                continue
            
            for log_file in log_dir.glob('*.log'):
                try:
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    
                    if size_mb > MAX_LOG_SIZE_MB:
                        logger.warning(f"   Large PM2 log: {log_file.name} ({size_mb:.1f} MB)")
                        # Truncate to last 1000 lines
                        self._rotate_file(log_file, keep_last_lines=1000)
                        self.stats['logs_rotated'] += 1
                        
                except Exception as e:
                    logger.error(f"   Error cleaning PM2 log {log_file}: {e}")
    
    def report_storage_usage(self):
        """Report current storage usage"""
        logger.info("\n📊 Storage usage report:")
        
        dirs_to_check = {
            'Logs': LOG_DIR,
            'Data': DATA_DIR,
            'WebUI': WEBUI_DIR,
            'Total': PROJECT_ROOT
        }
        
        for name, directory in dirs_to_check.items():
            if directory.exists():
                total_size = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                logger.info(f"   {name:12} {size_mb:8.1f} MB")


if __name__ == '__main__':
    guardian = StorageGuardian()
    guardian.run()
