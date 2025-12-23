#!/usr/bin/env python3
"""
Combined Guardian + Trading Bot Log Viewer
Shows both bot logs simultaneously when trading bot starts
"""
import os
import sys
import time
import signal
import threading
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

class CombinedLogViewer:
    """Combines Guardian and Trading bot logs for simultaneous viewing"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.running = True
        
        # Log file paths
        self.guardian_log = self.base_dir / "bot" / "logs" / "guardian.log"
        self.trading_log = self.base_dir / "bot" / "logs" / "bot.log"
        
        # Track last positions
        self.guardian_pos = 0
        self.trading_pos = 0
        
        # Initial load
        self._load_initial_positions()
    
    def _load_initial_positions(self):
        """Load initial file positions"""
        if self.guardian_log.exists():
            self.guardian_pos = self.guardian_log.stat().st_size
        if self.trading_log.exists():
            self.trading_pos = self.trading_log.stat().st_size
    
    def _get_new_lines(self, file_path: Path, last_pos: int) -> tuple[list[str], int]:
        """Get new lines from file since last position"""
        if not file_path.exists():
            return [], last_pos
        
        try:
            with open(file_path, 'r') as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                return new_lines, f.tell()
        except Exception:
            return [], last_pos
    
    def _format_line(self, line: str, source: str) -> str:
        """Format log line with source prefix"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding
        if source == "GUARDIAN":
            color = "\033[95m"  # Purple
            prefix = f"[{color}GUARDIAN\033[0m]"
        else:
            color = "\033[94m"  # Blue  
            prefix = f"[{color}TRADING\033[0m]"
        
        return f"{timestamp} {prefix} {line.rstrip()}"
    
    def monitor_logs(self):
        """Main monitoring loop"""
        print("\033[96m" + "="*80 + "\033[0m")
        print("\033[96m🔍 COMBINED BOT LOG VIEWER - Guardian + Trading Bot\033[0m")
        print("\033[96mPress Ctrl+C to stop monitoring\033[0m")
        print("\033[96m" + "="*80 + "\033[0m")
        
        try:
            while self.running:
                # Get new lines from both logs
                guardian_lines, self.guardian_pos = self._get_new_lines(
                    self.guardian_log, self.guardian_pos
                )
                trading_lines, self.trading_pos = self._get_new_lines(
                    self.trading_log, self.trading_pos
                )
                
                # Display Guardian lines
                for line in guardian_lines:
                    print(self._format_line(line, "GUARDIAN"))
                
                # Display Trading lines
                for line in trading_lines:
                    print(self._format_line(line, "TRADING"))
                
                # Small delay to prevent high CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\033[96m📋 Log monitoring stopped\033[0m")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False

def signal_handler(signum, frame):
    """Handle Ctrl+C"""
    print("\n\033[93m⚠️  Shutdown signal received\033[0m")
    if 'viewer' in globals():
        viewer.stop()
    sys.exit(0)

def main():
    """Main entry point"""
    global viewer
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start viewer
    viewer = CombinedLogViewer()
    viewer.monitor_logs()

if __name__ == "__main__":
    main()
