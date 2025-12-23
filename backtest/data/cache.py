"""
Cache Management Utilities

Helper functions for managing backtest data cache.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

log = logging.getLogger("backtest.cache")


def get_cache_stats(cache_dir: str = "backtest/data/cache") -> Dict:
    """
    Get statistics about cached data.
    
    Returns:
        dict: {
            'total_files': int,
            'total_size_mb': float,
            'symbols': list of str,
            'oldest_date': datetime,
            'newest_date': datetime
        }
    """
    cache_path = Path(cache_dir)
    
    if not cache_path.exists():
        return {
            'total_files': 0,
            'total_size_mb': 0.0,
            'symbols': [],
            'oldest_date': None,
            'newest_date': None
        }
    
    parquet_files = list(cache_path.glob("*.parquet"))
    
    total_size = sum(f.stat().st_size for f in parquet_files)
    
    # Extract symbols and dates from filenames
    symbols = set()
    dates = []
    
    for f in parquet_files:
        parts = f.stem.split('_')
        if len(parts) >= 4:
            # Format: SYMBOL_TIMEFRAME_STARTDATE_ENDDATE
            symbol = '_'.join(parts[:-3])
            symbols.add(symbol)
            
            try:
                start_date = datetime.strptime(parts[-2], '%Y%m%d')
                end_date = datetime.strptime(parts[-1], '%Y%m%d')
                dates.extend([start_date, end_date])
            except ValueError:
                pass
    
    return {
        'total_files': len(parquet_files),
        'total_size_mb': total_size / (1024 * 1024),
        'symbols': sorted(list(symbols)),
        'oldest_date': min(dates) if dates else None,
        'newest_date': max(dates) if dates else None
    }


def clear_old_cache(
    cache_dir: str = "backtest/data/cache",
    days_old: int = 30
) -> int:
    """
    Remove cache files older than specified days.
    
    Args:
        cache_dir: Cache directory path
        days_old: Remove files older than this many days
        
    Returns:
        Number of files removed
    """
    cache_path = Path(cache_dir)
    
    if not cache_path.exists():
        return 0
    
    now = datetime.now()
    removed = 0
    
    for cache_file in cache_path.glob("*.parquet"):
        # Check file modification time
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age_days = (now - mtime).days
        
        if age_days > days_old:
            cache_file.unlink()
            removed += 1
            log.debug(f"Removed old cache file: {cache_file.name} ({age_days} days old)")
    
    if removed > 0:
        log.info(f"Removed {removed} cache files older than {days_old} days")
    
    return removed


def list_cached_ranges(
    symbol: str,
    timeframe: str = "1m",
    cache_dir: str = "backtest/data/cache"
) -> List[Dict]:
    """
    List all cached date ranges for a symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTC/USD:USD")
        timeframe: Timeframe
        cache_dir: Cache directory
        
    Returns:
        List of dicts with 'start', 'end', 'filename' keys
    """
    cache_path = Path(cache_dir)
    
    if not cache_path.exists():
        return []
    
    symbol_safe = symbol.replace('/', '_').replace(':', '_')
    pattern = f"{symbol_safe}_{timeframe}_*.parquet"
    
    ranges = []
    for cache_file in cache_path.glob(pattern):
        parts = cache_file.stem.split('_')
        if len(parts) >= 2:
            try:
                start_str = parts[-2]
                end_str = parts[-1]
                start_date = datetime.strptime(start_str, '%Y%m%d')
                end_date = datetime.strptime(end_str, '%Y%m%d')
                
                ranges.append({
                    'start': start_date,
                    'end': end_date,
                    'filename': cache_file.name,
                    'size_mb': cache_file.stat().st_size / (1024 * 1024)
                })
            except ValueError:
                pass
    
    return sorted(ranges, key=lambda x: x['start'])

