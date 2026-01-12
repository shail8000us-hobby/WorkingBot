"""
Shared File Operation Utilities

Used by: logs, config, docs, positions blueprints

Extracted from app.py to avoid duplication across blueprints.
"""

import os
from pathlib import Path
from typing import List, Optional


def get_recent_logs(lines: int = 100, log_file: str = "bot/logs/bot.log") -> List[str]:
    """
    Get recent log lines from file
    
    ✅ FIXED: Changed default path from logs/gridbot.log to bot/logs/bot.log
    
    Args:
        lines: Number of lines to return (default: 100)
        log_file: Path to log file (default: bot/logs/bot.log)
        
    Returns:
        List of log lines (last N lines)
    """
    log_path = Path(log_file)
    
    # If log_file is not an absolute path, make it relative to project root
    if not log_path.is_absolute():
        # Get project root (4 levels up from this file)
        base_dir = Path(__file__).parent.parent.parent
        log_path = base_dir / log_file
    
    if not log_path.exists():
        # Try alternate log paths if primary doesn't exist
        base_dir = Path(__file__).parent.parent.parent
        alternate_paths = [
            base_dir / "logs" / "gridbot.log",
            base_dir / "bot" / "logs" / "gridbot_live.log",
            base_dir / "logs" / "trading_bot.log",
            base_dir / "logs" / "webui_guardian.log",
            base_dir / "logs" / "guardian_monitor.log",
        ]
        
        for alt_path in alternate_paths:
            if alt_path.exists():
                log_path = alt_path
                break
        
        if not log_path.exists():
            return [f"Log file not found: {log_file}"]
    
    try:
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if lines > 0 else all_lines
    except Exception as e:
        return [f"Error reading logs: {e}"]


def read_file_safely(filepath: Path, default: Optional[str] = None) -> Optional[str]:
    """
    Read file with error handling
    
    Args:
        filepath: Path to file to read
        default: Default value to return on error
        
    Returns:
        File contents as string, or default value on error
    """
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return f.read()
    except Exception:
        pass
    return default


def file_exists_and_readable(filepath: Path) -> bool:
    """
    Check if file exists and is readable
    
    Args:
        filepath: Path to file to check
        
    Returns:
        True if file exists and is readable, False otherwise
    """
    try:
        return filepath.exists() and filepath.is_file() and os.access(filepath, os.R_OK)
    except Exception:
        return False
