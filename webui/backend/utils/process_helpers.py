"""
Shared Process Management Utilities

Used by: bot_control, monitor, guardian, tmux, health blueprints

Extracted from app.py to avoid duplication across blueprints.
"""

import os
import signal
import time
from pathlib import Path
from typing import Optional

# PID file paths (used by multiple blueprints)
# ✅ FIXED: Use same paths as Guardian bot writes (root directory, not reports/)
BOT_PID_FILE = Path("reports/bot.pid")
GUARDIAN_PID_FILE = Path(".guardian.pid")  # Guardian writes to root directory
MONITOR_PID_FILE = Path("reports/monitor.pid")


def is_process_running(pid: int) -> bool:
    """
    Check if process with given PID is running
    
    Args:
        pid: Process ID to check
        
    Returns:
        True if process is running, False otherwise
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def read_pid_file(filepath: Path) -> Optional[int]:
    """
    Read PID from file, return None if doesn't exist or invalid
    
    Args:
        filepath: Path to PID file
        
    Returns:
        PID as integer, or None if file doesn't exist/invalid
    """
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        return None
    return None


def stop_process_by_pid(pid: int, timeout: int = 5) -> bool:
    """
    Stop process gracefully (SIGTERM), then forcefully (SIGKILL) if needed
    
    Args:
        pid: Process ID to stop
        timeout: Seconds to wait before force kill
        
    Returns:
        True if process stopped, False otherwise
    """
    try:
        # Try graceful shutdown first
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to exit
        for _ in range(timeout * 10):
            if not is_process_running(pid):
                return True
            time.sleep(0.1)
        
        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        return True
        
    except ProcessLookupError:
        # Already stopped
        return True
    except Exception:
        return False


def is_bot_running() -> bool:
    """
    Check if trading bot is running
    
    Returns:
        True if bot is running, False otherwise
    """
    pid = read_pid_file(BOT_PID_FILE)
    return pid is not None and is_process_running(pid)


def is_guardian_running() -> bool:
    """
    Check if guardian bot is running
    
    Returns:
        True if guardian is running, False otherwise
    """
    pid = read_pid_file(GUARDIAN_PID_FILE)
    return pid is not None and is_process_running(pid)


def is_monitor_running() -> bool:
    """
    Check if heartbeat monitor is running
    
    Returns:
        True if monitor is running, False otherwise
    """
    pid = read_pid_file(MONITOR_PID_FILE)
    return pid is not None and is_process_running(pid)
