#!/usr/bin/env python3
"""
WebUI Instance Lock Manager

Ensures only ONE WebUI instance runs per project using file-based locking.
Used by app.py on startup to prevent duplicate instances.
"""

import os
import sys
import time
import fcntl
from pathlib import Path


class WebUIInstanceLock:
    """Manages single-instance enforcement for WebUI"""
    
    def __init__(self, project_root: Path, port: int):
        self.project_root = Path(project_root)
        self.port = port
        self.lock_file = self.project_root / f".webui_instance_{port}.lock"
        self.lock_fd = None
        
    def acquire(self) -> bool:
        """
        Try to acquire instance lock.
        Returns True if acquired, False if another instance is running.
        """
        try:
            # Create lock file if it doesn't exist
            self.lock_file.touch(exist_ok=True)
            
            # Try to acquire exclusive lock (non-blocking)
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write our PID to the lock file
            self.lock_fd.write(f"{os.getpid()}\n")
            self.lock_fd.write(f"Port: {self.port}\n")
            self.lock_fd.write(f"Started: {time.ctime()}\n")
            self.lock_fd.flush()
            
            return True
            
        except BlockingIOError:
            # Another instance is already running
            return False
        except Exception as e:
            print(f"❌ Error acquiring lock: {e}", file=sys.stderr)
            return False
    
    def release(self):
        """Release the lock (called on exit)"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_file.unlink(missing_ok=True)
            except Exception:
                pass
    
    def get_running_instance_info(self) -> dict:
        """Get info about the currently running instance"""
        if not self.lock_file.exists():
            return None
        
        try:
            with open(self.lock_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    return {
                        'pid': int(lines[0].strip()) if lines[0].strip().isdigit() else None,
                        'port': int(lines[1].split(':')[1].strip()) if len(lines) > 1 else self.port,
                        'started': lines[2].split('Started:')[1].strip() if len(lines) > 2 else 'unknown'
                    }
        except Exception:
            pass
        
        return None


def check_webui_instance(project_root: Path, port: int = 5555) -> bool:
    """
    Check if WebUI instance is already running.
    Returns True if running, False if not.
    """
    lock = WebUIInstanceLock(project_root, port)
    
    # Try to acquire lock
    if lock.acquire():
        # We got the lock, so no instance was running
        lock.release()
        return False
    else:
        # Couldn't get lock, instance is running
        return True


if __name__ == '__main__':
    # Test the lock
    import argparse
    parser = argparse.ArgumentParser(description='Check WebUI instance lock')
    parser.add_argument('--port', type=int, default=5555, help='Port to check')
    parser.add_argument('--project', type=str, required=True, help='Project root path')
    args = parser.parse_args()
    
    lock = WebUIInstanceLock(Path(args.project), args.port)
    
    if check_webui_instance(Path(args.project), args.port):
        info = lock.get_running_instance_info()
        print(f"✅ WebUI instance IS running on port {args.port}")
        if info:
            print(f"   PID: {info.get('pid')}")
            print(f"   Started: {info.get('started')}")
    else:
        print(f"❌ No WebUI instance running on port {args.port}")
