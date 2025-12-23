#!/usr/bin/env python3
"""
Unified Logging System
Centralized logging for all bot components with structured format
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import threading
import queue
import time

class UnifiedLogger:
    """Unified logging system for all bot components"""
    
    def __init__(self, bot_dir: str = None, log_level: str = 'INFO'):
        self.bot_dir = bot_dir or os.getcwd()
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Create logs directory
        self.logs_dir = os.path.join(self.bot_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Main log file
        self.main_log_file = os.path.join(self.bot_dir, 'bot.log')
        
        # Component-specific log files
        self.component_logs = {
            'trading': os.path.join(self.logs_dir, 'trading.log'),
            'health': os.path.join(self.logs_dir, 'health.log'),
            'guardian': os.path.join(self.logs_dir, 'guardian.log'),
            'reconciliation': os.path.join(self.logs_dir, 'reconciliation.log'),
            'webui': os.path.join(self.logs_dir, 'webui.log'),
            'system': os.path.join(self.logs_dir, 'system.log')
        }
        
        # Log rotation settings
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.backup_count = 5
        
        # Thread-safe logging queue
        self.log_queue = queue.Queue()
        self.log_thread = None
        self.running = False
        
        # Initialize loggers
        self.loggers = {}
        self._setup_loggers()
        
        # Start background logging thread
        self.start_background_logging()
    
    def _setup_loggers(self):
        """Setup loggers for each component"""
        for component, log_file in self.component_logs.items():
            logger = logging.getLogger(f'bot.{component}')
            logger.setLevel(self.log_level)
            
            # Clear existing handlers
            logger.handlers.clear()
            
            # File handler with rotation
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            file_handler.setLevel(self.log_level)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            
            # Prevent propagation to root logger
            logger.propagate = False
            
            self.loggers[component] = logger
    
    def start_background_logging(self):
        """Start background logging thread"""
        if self.log_thread is None or not self.log_thread.is_alive():
            self.running = True
            self.log_thread = threading.Thread(target=self._background_logger, daemon=True)
            self.log_thread.start()
    
    def stop_background_logging(self):
        """Stop background logging thread"""
        self.running = False
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=5)
    
    def _background_logger(self):
        """Background thread for processing log queue"""
        while self.running:
            try:
                # Get log entry from queue with timeout
                log_entry = self.log_queue.get(timeout=1)
                
                # Process log entry
                self._process_log_entry(log_entry)
                
                # Mark task as done
                self.log_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in background logger: {e}")
    
    def _process_log_entry(self, log_entry: Dict[str, Any]):
        """Process a single log entry"""
        try:
            component = log_entry.get('component', 'system')
            level = log_entry.get('level', 'INFO')
            message = log_entry.get('message', '')
            extra_data = log_entry.get('extra', {})
            
            # Get logger for component
            logger = self.loggers.get(component, self.loggers['system'])
            
            # Create structured log message
            if extra_data:
                structured_message = f"{message} | {json.dumps(extra_data)}"
            else:
                structured_message = message
            
            # Log the message
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, structured_message)
            
            # Also write to main bot.log for critical events
            if level in ['ERROR', 'CRITICAL'] or 'FILLED' in message:
                self._write_to_main_log(log_entry)
                
        except Exception as e:
            print(f"Error processing log entry: {e}")
    
    def _write_to_main_log(self, log_entry: Dict[str, Any]):
        """Write critical events to main bot.log"""
        try:
            timestamp = log_entry.get('timestamp', datetime.now().isoformat())
            component = log_entry.get('component', 'system')
            level = log_entry.get('level', 'INFO')
            message = log_entry.get('message', '')
            extra_data = log_entry.get('extra', {})
            
            # Format message for main log
            if extra_data:
                formatted_message = f"{timestamp} [{level}] {component}: {message} | {json.dumps(extra_data)}"
            else:
                formatted_message = f"{timestamp} [{level}] {component}: {message}"
            
            # Write to main log file
            with open(self.main_log_file, 'a') as f:
                f.write(formatted_message + '\n')
                
        except Exception as e:
            print(f"Error writing to main log: {e}")
    
    def log(self, component: str, level: str, message: str, **kwargs):
        """Log a message for a specific component"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'level': level,
            'message': message,
            'extra': kwargs
        }
        
        # Add to queue for background processing
        try:
            self.log_queue.put_nowait(log_entry)
        except queue.Full:
            # If queue is full, log directly
            self._process_log_entry(log_entry)
    
    def log_trade(self, component: str, trade_type: str, symbol: str, 
                  size: float, price: float, order_id: str = None, **kwargs):
        """Log a trade execution"""
        message = f"{trade_type} FILLED: {symbol} {size} @ {price}"
        if order_id:
            message += f" (Order: {order_id})"
        
        self.log(component, 'INFO', message, 
                trade_type=trade_type, symbol=symbol, size=size, 
                price=price, order_id=order_id, **kwargs)
    
    def log_position(self, component: str, action: str, symbol: str, 
                    size: float, entry_price: float, pnl: float = None, **kwargs):
        """Log a position change"""
        message = f"POSITION {action}: {symbol} {size} @ {entry_price}"
        if pnl is not None:
            message += f" (PnL: {pnl})"
        
        self.log(component, 'INFO', message,
                action=action, symbol=symbol, size=size, 
                entry_price=entry_price, pnl=pnl, **kwargs)
    
    def log_error(self, component: str, error: str, context: str = None, **kwargs):
        """Log an error"""
        message = f"ERROR: {error}"
        if context:
            message += f" (Context: {context})"
        
        self.log(component, 'ERROR', message, error=error, context=context, **kwargs)
    
    def log_system(self, component: str, event: str, **kwargs):
        """Log a system event"""
        self.log(component, 'INFO', f"SYSTEM: {event}", event=event, **kwargs)
    
    def get_logger(self, component: str) -> logging.Logger:
        """Get a logger for a specific component"""
        return self.loggers.get(component, self.loggers['system'])
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'queue_size': self.log_queue.qsize(),
            'background_thread_running': self.log_thread.is_alive() if self.log_thread else False,
            'log_files': {}
        }
        
        # Check log file sizes
        for component, log_file in self.component_logs.items():
            if os.path.exists(log_file):
                stats['log_files'][component] = {
                    'file': log_file,
                    'size_bytes': os.path.getsize(log_file),
                    'size_mb': round(os.path.getsize(log_file) / (1024 * 1024), 2)
                }
            else:
                stats['log_files'][component] = {
                    'file': log_file,
                    'size_bytes': 0,
                    'size_mb': 0
                }
        
        # Main log file
        if os.path.exists(self.main_log_file):
            stats['main_log'] = {
                'file': self.main_log_file,
                'size_bytes': os.path.getsize(self.main_log_file),
                'size_mb': round(os.path.getsize(self.main_log_file) / (1024 * 1024), 2)
            }
        else:
            stats['main_log'] = {
                'file': self.main_log_file,
                'size_bytes': 0,
                'size_mb': 0
            }
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 7):
        """Clean up old log files"""
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        cleaned_files = []
        
        for component, log_file in self.component_logs.items():
            if os.path.exists(log_file):
                file_time = os.path.getmtime(log_file)
                if file_time < cutoff_time:
                    try:
                        os.remove(log_file)
                        cleaned_files.append(log_file)
                    except Exception as e:
                        print(f"Error removing old log file {log_file}: {e}")
        
        return cleaned_files

# Global logger instance
_unified_logger = None

def get_unified_logger(bot_dir: str = None) -> UnifiedLogger:
    """Get the global unified logger instance"""
    global _unified_logger
    if _unified_logger is None:
        _unified_logger = UnifiedLogger(bot_dir)
    return _unified_logger

def log_trade(component: str, trade_type: str, symbol: str, 
              size: float, price: float, order_id: str = None, **kwargs):
    """Convenience function for logging trades"""
    logger = get_unified_logger()
    logger.log_trade(component, trade_type, symbol, size, price, order_id, **kwargs)

def log_position(component: str, action: str, symbol: str, 
                size: float, entry_price: float, pnl: float = None, **kwargs):
    """Convenience function for logging positions"""
    logger = get_unified_logger()
    logger.log_position(component, action, symbol, size, entry_price, pnl, **kwargs)

def log_error(component: str, error: str, context: str = None, **kwargs):
    """Convenience function for logging errors"""
    logger = get_unified_logger()
    logger.log_error(component, error, context, **kwargs)

def log_system(component: str, event: str, **kwargs):
    """Convenience function for logging system events"""
    logger = get_unified_logger()
    logger.log_system(component, event, **kwargs)

def main():
    """CLI interface for unified logger"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Logging System')
    parser.add_argument('--bot-dir', type=str, default=os.getcwd(),
                       help='Bot directory path')
    parser.add_argument('--stats', action='store_true',
                       help='Show logging statistics')
    parser.add_argument('--cleanup', type=int, metavar='DAYS',
                       help='Clean up logs older than specified days')
    
    args = parser.parse_args()
    
    logger = UnifiedLogger(args.bot_dir)
    
    if args.stats:
        stats = logger.get_log_stats()
        print(json.dumps(stats, indent=2))
    
    if args.cleanup:
        cleaned = logger.cleanup_old_logs(args.cleanup)
        print(f"Cleaned up {len(cleaned)} old log files")
        for file in cleaned:
            print(f"  - {file}")
    
    if not args.stats and not args.cleanup:
        print("Unified logging system ready")
        print("Use --stats to see statistics or --cleanup DAYS to clean old logs")

if __name__ == '__main__':
    main()

