#!/usr/bin/env python3
"""
Automatic Data Cleanup System

Automatically cleans up ALL bot data after configurable retention period.
Prevents disk bloat by removing:
- Old log files
- Old database records
- Old backup files
- Cache files
- Temporary files

Default retention: 48 hours (2 days)
Runs continuously in background or via cron.
"""

import os
import sys
import time
import sqlite3
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent  # scripts/ -> WorkingBot/
LOG_DIR = PROJECT_ROOT / 'logs'
BOT_LOG_DIR = PROJECT_ROOT / 'bot' / 'logs'
DATA_DIR = PROJECT_ROOT / 'data'

# Retention Policy (in days)
DEFAULT_RETENTION_DAYS = 2  # 48 hours
LOG_RETENTION_DAYS = 2
DATABASE_RETENTION_DAYS = 2
BACKUP_RETENTION_DAYS = 7
CACHE_RETENTION_DAYS = 1

# Size-based cap: truncate any single active log file that exceeds this (MB)
# Active logs can never be cleaned by mtime since they're always freshly written.
MAX_ACTIVE_LOG_MB = 500

# Cleanup interval (seconds)
CLEANUP_INTERVAL = 3600  # Run every hour

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'auto_cleanup.log',
    maxBytes=5*1024*1024,  # 5MB
    backupCount=2
)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


class AutoDataCleanup:
    """Automatic cleanup system for all bot data"""
    
    def __init__(self, retention_days: int = DEFAULT_RETENTION_DAYS):
        self.retention_days = retention_days
        self.stats = {
            'logs_cleaned': 0,
            'logs_size_freed_mb': 0,
            'db_records_deleted': 0,
            'db_size_freed_mb': 0,
            'backups_deleted': 0,
            'cache_cleaned': 0,
            'last_run': None
        }
        
    def cleanup_old_logs(self) -> Dict:
        """Remove old log files and truncate oversized active logs."""
        cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        stats = {'removed': 0, 'truncated': 0, 'size_freed_mb': 0}

        log_dirs = [d for d in [LOG_DIR, BOT_LOG_DIR] if d.exists()]

        logger.info(f"🧹 Cleaning logs older than {LOG_RETENTION_DAYS} days "
                    f"(size cap {MAX_ACTIVE_LOG_MB}MB for active logs)...")

        for log_dir in log_dirs:
            for log_file in log_dir.glob('**/*'):
                if not log_file.is_file():
                    continue
                # Only process log and zip files
                if not any(log_file.name.endswith(ext) for ext in
                           ('.log', '.log.gz', '.log.zip', '.zip')):
                    continue

                size_mb = log_file.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                try:
                    if mtime < cutoff:
                        # File not touched in retention window — delete
                        log_file.unlink()
                        stats['removed'] += 1
                        stats['size_freed_mb'] += size_mb
                        logger.info(f"  ✅ Deleted (old): {log_file.name} ({size_mb:.2f}MB)")
                    elif size_mb > MAX_ACTIVE_LOG_MB:
                        # Active but oversized — truncate in-place so running
                        # processes keep their file descriptor intact
                        with open(log_file, 'w'):
                            pass
                        stats['truncated'] += 1
                        stats['size_freed_mb'] += size_mb
                        logger.info(f"  ✅ Truncated (oversized): {log_file.name} "
                                    f"({size_mb:.2f}MB → 0MB)")
                except Exception as e:
                    logger.error(f"  ❌ Failed on {log_file.name}: {e}")

        logger.info(f"   Deleted: {stats['removed']} files, "
                    f"Truncated: {stats['truncated']} files, "
                    f"Freed: {stats['size_freed_mb']:.2f}MB")
        return stats
    
    def cleanup_database_records(self) -> Dict:
        """Clean old records from all databases"""
        cutoff_timestamp = (datetime.now() - timedelta(days=DATABASE_RETENTION_DAYS)).timestamp()
        stats = {'databases_cleaned': 0, 'records_deleted': 0, 'size_freed_mb': 0}
        
        logger.info(f"🧹 Cleaning database records older than {DATABASE_RETENTION_DAYS} days...")
        
        # Database cleanup configurations
        # NOTE: volatility.db is managed by size limit (500MB), not time-based
        databases = [
            {
                'path': PROJECT_ROOT / 'bot_events_LONG.db',
                'table': 'events',
                'timestamp_col': 'timestamp',
                'description': 'Bot Events (LONG)'
            },
            {
                'path': PROJECT_ROOT / 'gridbot_events.db',
                'table': 'events',
                'timestamp_col': 'timestamp',
                'description': 'Gridbot Events'
            },
            {
                'path': PROJECT_ROOT / 'webui' / 'backend' / 'metrics.db',
                'table': 'api_metrics',
                'timestamp_col': 'timestamp',
                'description': 'API Metrics'
            },
            {
                'path': PROJECT_ROOT / 'bot' / 'state' / 'events.db',
                'table': 'pnl_history',
                'timestamp_col': 'timestamp',
                'description': 'PnL History'
            },
            {
                'path': DATA_DIR / 'errors.db',
                'table': 'errors',
                'timestamp_col': 'timestamp',
                'description': 'Error Logs'
            }
        ]
        
        for db_config in databases:
            db_path = db_config['path']
            if not db_path.exists():
                continue
            
            try:
                size_before = db_path.stat().st_size / (1024 * 1024)
                
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute(f"""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (db_config['table'],))
                
                if not cursor.fetchone():
                    conn.close()
                    continue
                
                # Count records before
                cursor.execute(f"SELECT COUNT(*) FROM {db_config['table']}")
                before_count = cursor.fetchone()[0]
                
                # Delete old records
                cursor.execute(f"""
                    DELETE FROM {db_config['table']} 
                    WHERE {db_config['timestamp_col']} < ?
                """, (cutoff_timestamp,))
                
                deleted = cursor.rowcount
                conn.commit()
                
                # VACUUM if significant deletion
                if deleted > 100:
                    cursor.execute("VACUUM")
                
                # Count records after
                cursor.execute(f"SELECT COUNT(*) FROM {db_config['table']}")
                after_count = cursor.fetchone()[0]
                
                conn.close()
                
                size_after = db_path.stat().st_size / (1024 * 1024)
                size_freed = size_before - size_after
                
                if deleted > 0:
                    stats['databases_cleaned'] += 1
                    stats['records_deleted'] += deleted
                    stats['size_freed_mb'] += size_freed
                    
                    logger.info(f"  ✅ {db_config['description']}: "
                              f"Deleted {deleted:,} records, "
                              f"freed {size_freed:.2f}MB "
                              f"({before_count:,} → {after_count:,} records)")
                
            except Exception as e:
                logger.error(f"  ❌ Failed to clean {db_config['description']}: {e}")
        
        return stats
    
    def manage_volatility_database(self) -> Dict:
        """Manage volatility database by size (500MB limit), not time"""
        MAX_VOLATILITY_SIZE_MB = 500
        stats = {'records_deleted': 0, 'size_freed_mb': 0}
        
        volatility_db = DATA_DIR / 'volatility.db'
        
        if not volatility_db.exists():
            logger.info("🧹 Volatility database not found, skipping...")
            return stats
        
        try:
            size_mb = volatility_db.stat().st_size / (1024 * 1024)
            
            if size_mb <= MAX_VOLATILITY_SIZE_MB:
                logger.info(f"🧹 Volatility database: {size_mb:.2f}MB (under {MAX_VOLATILITY_SIZE_MB}MB limit) ✅")
                return stats
            
            logger.info(f"🧹 Volatility database exceeds limit: {size_mb:.2f}MB > {MAX_VOLATILITY_SIZE_MB}MB")
            logger.info("   Cleaning oldest 30% of records...")
            
            conn = sqlite3.connect(str(volatility_db))
            cursor = conn.cursor()
            
            # Get all tables in volatility database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                conn.close()
                logger.info("   No tables found in volatility database")
                return stats
            
            logger.info(f"   Found tables: {', '.join(tables)}")
            
            total_deleted = 0
            total_before = 0
            total_after = 0
            
            # Clean oldest 30% from each table
            for table in tables:
                # Count total records
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                total_before += count
                
                if count == 0:
                    continue
                
                # Delete oldest 30% of records
                records_to_delete = int(count * 0.3)
                
                # Get timestamp column name (could be 'timestamp' or 'created_at')
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                timestamp_col = 'timestamp' if 'timestamp' in columns else 'created_at'
                
                if timestamp_col not in columns:
                    logger.info(f"   Skipping {table}: no timestamp column found")
                    continue
                
                cursor.execute(f"""
                    DELETE FROM {table} 
                    WHERE {timestamp_col} IN (
                        SELECT {timestamp_col} FROM {table} 
                        ORDER BY {timestamp_col} ASC 
                        LIMIT ?
                    )
                """, (records_to_delete,))
                
                deleted = cursor.rowcount
                total_deleted += deleted
                
                logger.info(f"   • {table}: Deleted {deleted:,} oldest records")
            
            conn.commit()
            
            # VACUUM to reclaim space
            logger.info("   Running VACUUM to reclaim space...")
            cursor.execute("VACUUM")
            
            # Get final total count
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total_after += cursor.fetchone()[0]
            
            conn.close()
            
            final_size_mb = volatility_db.stat().st_size / (1024 * 1024)
            size_freed = size_mb - final_size_mb
            
            stats['records_deleted'] = total_deleted
            stats['size_freed_mb'] = size_freed
            
            logger.info(f"   ✅ Volatility Database: Deleted {total_deleted:,} oldest records")
            logger.info(f"      {total_before:,} → {total_after:,} total records")
            logger.info(f"      {size_mb:.2f}MB → {final_size_mb:.2f}MB (freed {size_freed:.2f}MB)")
            
        except Exception as e:
            logger.error(f"   ❌ Failed to manage volatility database: {e}")
        
        return stats
    
    def cleanup_old_backups(self) -> Dict:
        """Remove old database backups"""
        cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
        stats = {'removed': 0, 'size_freed_mb': 0}
        
        logger.info(f"🧹 Cleaning backups older than {BACKUP_RETENTION_DAYS} days...")
        
        # Clean database backups
        for backup_file in PROJECT_ROOT.glob('**/*_backup_*.db'):
            if backup_file.is_file():
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if mtime < cutoff:
                    size_mb = backup_file.stat().st_size / (1024 * 1024)
                    try:
                        backup_file.unlink()
                        stats['removed'] += 1
                        stats['size_freed_mb'] += size_mb
                        logger.info(f"  ✅ Removed: {backup_file.name} ({size_mb:.2f}MB)")
                    except Exception as e:
                        logger.error(f"  ❌ Failed to remove {backup_file.name}: {e}")
        
        # Clean log backups
        for backup_file in LOG_DIR.glob('*.log.*'):
            if backup_file.is_file():
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if mtime < cutoff:
                    size_mb = backup_file.stat().st_size / (1024 * 1024)
                    try:
                        backup_file.unlink()
                        stats['removed'] += 1
                        stats['size_freed_mb'] += size_mb
                        logger.info(f"  ✅ Removed: {backup_file.name} ({size_mb:.2f}MB)")
                    except Exception as e:
                        logger.error(f"  ❌ Failed to remove {backup_file.name}: {e}")
        
        return stats
    
    def cleanup_cache_files(self) -> Dict:
        """Remove old cache files"""
        cutoff = datetime.now() - timedelta(days=CACHE_RETENTION_DAYS)
        stats = {'removed': 0, 'size_freed_mb': 0}
        
        logger.info(f"🧹 Cleaning cache files older than {CACHE_RETENTION_DAYS} days...")
        
        cache_patterns = [
            '__pycache__',
            '*.pyc',
            '*.pyo',
            '.pytest_cache',
            '.coverage',
            '*.log~',
            '*.tmp',
            'bot_*.json'  # Temporary JSON files
        ]
        
        for pattern in cache_patterns:
            for cache_file in PROJECT_ROOT.glob(f'**/{pattern}'):
                try:
                    if cache_file.is_file():
                        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if mtime < cutoff:
                            size_mb = cache_file.stat().st_size / (1024 * 1024)
                            cache_file.unlink()
                            stats['removed'] += 1
                            stats['size_freed_mb'] += size_mb
                    elif cache_file.is_dir() and pattern == '__pycache__':
                        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if mtime < cutoff:
                            import shutil
                            shutil.rmtree(cache_file)
                            stats['removed'] += 1
                except Exception as e:
                    logger.debug(f"  Skipped {cache_file}: {e}")
        
        return stats
    
    def run_cleanup(self) -> Dict:
        """Run complete cleanup cycle"""
        logger.info("="*80)
        logger.info("🧹 AUTOMATIC DATA CLEANUP STARTED")
        logger.info(f"   Retention Policy: {self.retention_days} days")
        logger.info("="*80)
        
        start_time = time.time()
        
        # Clean logs
        log_stats = self.cleanup_old_logs()
        self.stats['logs_cleaned'] += log_stats['removed']
        self.stats['logs_size_freed_mb'] += log_stats['size_freed_mb']
        
        # Clean database records
        db_stats = self.cleanup_database_records()
        self.stats['db_records_deleted'] += db_stats['records_deleted']
        self.stats['db_size_freed_mb'] += db_stats['size_freed_mb']
        
        # Manage volatility database by size (500MB limit)
        volatility_stats = self.manage_volatility_database()
        self.stats['db_records_deleted'] += volatility_stats['records_deleted']
        self.stats['db_size_freed_mb'] += volatility_stats['size_freed_mb']
        
        # Clean backups
        backup_stats = self.cleanup_old_backups()
        self.stats['backups_deleted'] += backup_stats['removed']
        
        # Clean cache
        cache_stats = self.cleanup_cache_files()
        self.stats['cache_cleaned'] += cache_stats['removed']
        
        elapsed = time.time() - start_time
        self.stats['last_run'] = datetime.now().isoformat()
        
        # Summary
        logger.info("="*80)
        logger.info("✅ CLEANUP COMPLETED")
        logger.info(f"   Duration: {elapsed:.2f}s")
        logger.info(f"   Logs removed: {log_stats['removed']} ({log_stats['size_freed_mb']:.2f}MB)")
        logger.info(f"   DB records deleted: {db_stats['records_deleted']:,}")
        logger.info(f"   DB space freed: {db_stats['size_freed_mb']:.2f}MB")
        logger.info(f"   Backups removed: {backup_stats['removed']} ({backup_stats['size_freed_mb']:.2f}MB)")
        logger.info(f"   Cache files removed: {cache_stats['removed']}")
        logger.info(f"   Total space freed: {(log_stats['size_freed_mb'] + db_stats['size_freed_mb'] + backup_stats['size_freed_mb']):.2f}MB")
        logger.info("="*80)
        
        return self.stats
    
    def run_continuous(self, interval: int = CLEANUP_INTERVAL):
        """Run cleanup continuously"""
        logger.info(f"🔄 Starting continuous cleanup (every {interval//3600} hours)")
        
        try:
            while True:
                self.run_cleanup()
                logger.info(f"💤 Sleeping for {interval//3600} hours until next cleanup...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("\n🛑 Cleanup service stopped")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatic Data Cleanup System')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--retention-days', type=int, default=DEFAULT_RETENTION_DAYS,
                       help='Retention period in days (default: 2)')
    parser.add_argument('--interval', type=int, default=CLEANUP_INTERVAL,
                       help='Cleanup interval in seconds (default: 3600)')
    
    args = parser.parse_args()
    
    cleaner = AutoDataCleanup(retention_days=args.retention_days)
    
    if args.once:
        cleaner.run_cleanup()
    else:
        cleaner.run_continuous(interval=args.interval)


if __name__ == "__main__":
    main()
