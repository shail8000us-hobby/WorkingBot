"""
Single Instance Lock System

Prevents multiple trading bot instances from running simultaneously.
Uses file-based locking with PID tracking for reliability.

Features:
- File-based lock with PID tracking
- Automatic cleanup on bot exit
- Process validation (check if PID is still alive)
- Graceful error handling
- Lock file rotation for stale locks
"""

import os
import sys
import time
import fcntl
import logging
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("single_instance")


class SingleInstanceLock:
    """
    Prevents multiple trading bot instances from running simultaneously.
    
    Uses file-based locking with PID tracking for cross-platform reliability.
    Supports separate locks for live and demo trading modes.
    """
    
    def __init__(self, lock_file: str = ".bot_instance.lock", trading_mode: str = None):
        """
        Initialize single instance lock.
        
        Args:
            lock_file: Path to lock file (relative to project root)
            trading_mode: 'live' or 'demo' - creates mode-specific lock files
        """
        self.project_root = Path(__file__).parent.parent.parent
        
        # Create mode-specific lock file if trading mode is specified
        if trading_mode:
            lock_file = f".bot_instance_{trading_mode}.lock"
        
        self.lock_file = self.project_root / lock_file
        self.lock_fd: Optional[int] = None
        self.pid = os.getpid()
        self.trading_mode = trading_mode
        
    def acquire(self) -> Tuple[bool, str]:
        """
        Acquire exclusive lock for this bot instance.
        
        Returns:
            (success: bool, message: str)
        """
        try:
            # Check if lock file exists and is valid
            if self.lock_file.exists():
                if not self._is_lock_valid():
                    log.warning("Stale lock file detected, removing...")
                    self.lock_file.unlink(missing_ok=True)
                else:
                    existing_pid = self._get_existing_pid()
                    mode_msg = f" ({self.trading_mode} mode)" if self.trading_mode else ""
                    return False, f"Another trading bot{mode_msg} is already running (PID: {existing_pid})"
            
            # Create lock file with exclusive access
            self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            
            # Try to acquire exclusive lock (non-blocking)
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(self.lock_fd)
                self.lock_fd = None
                return False, "Could not acquire lock (another instance may be starting)"
            
            # Write PID and timestamp to lock file
            lock_data = f"{self.pid}\n{time.time()}\n{time.strftime('%Y-%m-%d %H:%M:%S')}"
            os.write(self.lock_fd, lock_data.encode('utf-8'))
            os.fsync(self.lock_fd)  # Ensure data is written to disk
            
            log.info(f"Single instance lock acquired (PID: {self.pid})")
            return True, f"Lock acquired successfully (PID: {self.pid})"
            
        except Exception as e:
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
            return False, f"Failed to acquire lock: {e}"
    
    def release(self) -> bool:
        """
        Release the lock and clean up.
        
        Returns:
            success: bool
        """
        try:
            if self.lock_fd is not None:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
            
            if self.lock_file.exists():
                self.lock_file.unlink(missing_ok=True)
            
            log.info(f"Single instance lock released (PID: {self.pid})")
            return True
            
        except Exception as e:
            log.error(f"Failed to release lock: {e}")
            return False
    
    def _is_lock_valid(self) -> bool:
        """
        Check if existing lock file is valid (process still running).
        
        Returns:
            valid: bool
        """
        try:
            if not self.lock_file.exists():
                return False
            
            existing_pid = self._get_existing_pid()
            if existing_pid is None:
                return False
            
            # Check if process is still running
            try:
                os.kill(existing_pid, 0)  # Signal 0 just checks if process exists
                
                # Additional check: verify it's actually a bot process
                # This prevents false positives from recycled PIDs
                try:
                    import subprocess
                    cmd_result = subprocess.run(['ps', '-p', str(existing_pid), '-o', 'command='], 
                                              capture_output=True, text=True, timeout=2)
                    if cmd_result.returncode == 0:
                        cmd_line = cmd_result.stdout.strip()
                        # Check if it's actually a bot process
                        if 'bot.run' in cmd_line or 'bot_launcher' in cmd_line or 'python' in cmd_line.lower():
                            return True
                        else:
                            log.warning(f"PID {existing_pid} exists but is not a bot process: {cmd_line}")
                            return False
                except Exception as e:
                    log.warning(f"Could not verify process command for PID {existing_pid}: {e}")
                    # If we can't verify, assume it's valid to be safe
                    return True
                
                return True
            except (OSError, ProcessLookupError):
                return False
                
        except Exception:
            return False
    
    def _get_existing_pid(self) -> Optional[int]:
        """
        Get PID from existing lock file.
        
        Returns:
            pid: int or None
        """
        try:
            if not self.lock_file.exists():
                return None
            
            with open(self.lock_file, 'r') as f:
                first_line = f.readline().strip()
                return int(first_line) if first_line.isdigit() else None
                
        except Exception:
            return None
    
    def get_lock_info(self) -> Optional[dict]:
        """
        Get information about existing lock.
        
        Returns:
            lock_info: dict or None
        """
        try:
            if not self.lock_file.exists():
                return None
            
            with open(self.lock_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 3:
                    return {
                        'pid': int(lines[0].strip()),
                        'timestamp': float(lines[1].strip()),
                        'start_time': lines[2].strip(),
                        'is_valid': self._is_lock_valid()
                    }
            return None
            
        except Exception:
            return None


def check_single_instance(trading_mode: str = None) -> Tuple[bool, str]:
    """
    Check if only one trading bot instance should be allowed.
    
    Args:
        trading_mode: 'live' or 'demo' - checks mode-specific lock
    
    Returns:
        (can_start: bool, message: str)
    """
    lock = SingleInstanceLock(trading_mode=trading_mode)
    return lock.acquire()


def cleanup_single_instance(trading_mode: str = None):
    """
    Clean up single instance lock (call on bot exit).
    
    Args:
        trading_mode: 'live' or 'demo' - cleans mode-specific lock
    """
    lock = SingleInstanceLock(trading_mode=trading_mode)
    lock.release()


# Global lock instance for cleanup on exit
_instance_lock: Optional[SingleInstanceLock] = None


def setup_single_instance_lock(trading_mode: str = None) -> Tuple[bool, str]:
    """
    Setup single instance lock for the current bot process.
    Call this at bot startup.
    
    Args:
        trading_mode: 'live' or 'demo' - creates mode-specific lock
    
    Returns:
        (success: bool, message: str)
    """
    global _instance_lock
    
    success, message = check_single_instance(trading_mode)
    if success:
        _instance_lock = SingleInstanceLock(trading_mode=trading_mode)
        # Register cleanup handler
        import atexit
        atexit.register(lambda: cleanup_single_instance(trading_mode))
    
    return success, message


if __name__ == "__main__":
    # Test the lock system
    print("Testing single instance lock...")
    
    success, message = setup_single_instance_lock()
    print(f"Lock result: {success} - {message}")
    
    if success:
        print("Lock acquired, sleeping for 5 seconds...")
        time.sleep(5)
        print("Releasing lock...")
        cleanup_single_instance()
        print("Lock released")
    else:
        print("Could not acquire lock")

