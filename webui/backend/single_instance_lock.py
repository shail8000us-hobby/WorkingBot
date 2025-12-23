"""
WebUI Single Instance Lock System

Prevents multiple WebUI backend instances from running simultaneously.
Uses file-based locking with PID tracking for reliability.

Features:
- File-based lock with PID tracking
- Automatic cleanup on WebUI exit
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

log = logging.getLogger("webui_single_instance")


class WebUISingleInstanceLock:
    """
    Prevents multiple WebUI backend instances from running simultaneously.
    
    Uses file-based locking with PID tracking for cross-platform reliability.
    """
    
    def __init__(self, lock_file: str = ".webui_instance.lock"):
        """
        Initialize WebUI single instance lock.
        
        Args:
            lock_file: Path to lock file (relative to project root)
        """
        self.project_root = Path(__file__).parent.parent.parent
        self.lock_file = self.project_root / lock_file
        self.lock_fd: Optional[int] = None
        self.pid = os.getpid()
        
    def acquire(self) -> Tuple[bool, str]:
        """
        Acquire exclusive lock for this WebUI instance.
        
        Returns:
            (success: bool, message: str)
        """
        try:
            # Check if lock file exists and is valid
            if self.lock_file.exists():
                if not self._is_lock_valid():
                    log.warning("Stale WebUI lock file detected, removing...")
                    self.lock_file.unlink(missing_ok=True)
                else:
                    existing_pid = self._get_existing_pid()
                    return False, f"Another WebUI backend is already running (PID: {existing_pid})"
            
            # Create lock file with exclusive access
            self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            
            # Try to acquire exclusive lock (non-blocking)
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(self.lock_fd)
                self.lock_fd = None
                return False, "Could not acquire WebUI lock (another instance may be starting)"
            
            # Write PID and timestamp to lock file
            lock_data = f"{self.pid}\n{time.time()}\n{time.strftime('%Y-%m-%d %H:%M:%S')}\nWebUI Backend"
            os.write(self.lock_fd, lock_data.encode('utf-8'))
            os.fsync(self.lock_fd)  # Ensure data is written to disk
            
            log.info(f"WebUI single instance lock acquired (PID: {self.pid})")
            return True, f"WebUI lock acquired successfully (PID: {self.pid})"
            
        except Exception as e:
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
            return False, f"Failed to acquire WebUI lock: {e}"
    
    def release(self) -> bool:
        """
        Release the WebUI lock and clean up.
        
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
            
            log.info(f"WebUI single instance lock released (PID: {self.pid})")
            return True
            
        except Exception as e:
            log.error(f"Failed to release WebUI lock: {e}")
            return False
    
    def _is_lock_valid(self) -> bool:
        """
        Check if existing WebUI lock file is valid (process still running).
        
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
                return True
            except (OSError, ProcessLookupError):
                return False
                
        except Exception:
            return False
    
    def _get_existing_pid(self) -> Optional[int]:
        """
        Get PID from existing WebUI lock file.
        
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
        Get information about existing WebUI lock.
        
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
                        'process_type': lines[3].strip() if len(lines) > 3 else 'WebUI Backend',
                        'is_valid': self._is_lock_valid()
                    }
            return None
            
        except Exception:
            return None


def check_webui_single_instance() -> Tuple[bool, str]:
    """
    Check if only one WebUI backend instance should be allowed.
    
    Returns:
        (can_start: bool, message: str)
    """
    lock = WebUISingleInstanceLock()
    return lock.acquire()


def cleanup_webui_single_instance():
    """
    Clean up WebUI single instance lock (call on WebUI exit).
    """
    lock = WebUISingleInstanceLock()
    lock.release()


# Global lock instance for cleanup on exit
_webui_instance_lock: Optional[WebUISingleInstanceLock] = None


def setup_webui_single_instance_lock() -> Tuple[bool, str]:
    """
    Setup WebUI single instance lock for the current WebUI process.
    Call this at WebUI startup.
    
    Returns:
        (success: bool, message: str)
    """
    global _webui_instance_lock
    
    success, message = check_webui_single_instance()
    if success:
        _webui_instance_lock = WebUISingleInstanceLock()
        # Register cleanup handler
        import atexit
        atexit.register(cleanup_webui_single_instance)
    
    return success, message


if __name__ == "__main__":
    # Test the WebUI lock system
    print("Testing WebUI single instance lock...")
    
    success, message = setup_webui_single_instance_lock()
    print(f"WebUI Lock result: {success} - {message}")
    
    if success:
        print("WebUI Lock acquired, sleeping for 5 seconds...")
        time.sleep(5)
        print("Releasing WebUI lock...")
        cleanup_webui_single_instance()
        print("WebUI Lock released")
    else:
        print("Could not acquire WebUI lock")

