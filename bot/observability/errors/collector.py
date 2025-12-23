"""
Error Collector - Monitors bot logs and streams for error detection
Supports both file tailing and process pipe subscription.
"""

import os
import re
import time
import threading
from queue import Queue, Empty
from typing import Optional, Callable, Dict, Set
from pathlib import Path
from datetime import datetime, timedelta
from .schema import ErrorSource


class ErrorCollector:
    """Collects errors from bot logs and processes"""
    
    def __init__(
        self,
        on_error_detected: Callable[[str, ErrorSource], None],
        rate_limit_window: int = 60,  # seconds
        rate_limit_max: int = 100,    # max events per window
        burst_threshold: int = 10      # events in 5 seconds = burst
    ):
        self.on_error_detected = on_error_detected
        self.rate_limit_window = rate_limit_window
        self.rate_limit_max = rate_limit_max
        self.burst_threshold = burst_threshold
        
        self.running = False
        self.threads: list[threading.Thread] = []
        self.event_timestamps: Dict[ErrorSource, list[datetime]] = {
            source: [] for source in ErrorSource
        }
        self.suppressed_until: Dict[ErrorSource, Optional[datetime]] = {
            source: None for source in ErrorSource
        }
        
        # Deduplication cache (signature -> last_seen)
        self.seen_signatures: Dict[str, datetime] = {}
        self.dedup_window = timedelta(seconds=30)  # Suppress duplicates within 30s
    
    def start(self, log_configs: Dict[str, Dict]):
        """
        Start monitoring configured log sources.
        
        log_configs format:
        {
            'trading': {'type': 'file', 'path': '/path/to/bot.log'},
            'guardian': {'type': 'file', 'path': '/path/to/guardian.log'},
            'health': {'type': 'file', 'path': '/path/to/health.log'}
        }
        """
        if self.running:
            print("⚠️  Error collector already running")
            return
        
        self.running = True
        print("🔍 Starting error collector...")
        
        for source_name, config in log_configs.items():
            try:
                source = ErrorSource(source_name.lower())
                
                if config['type'] == 'file':
                    thread = threading.Thread(
                        target=self._tail_file,
                        args=(config['path'], source),
                        daemon=True,
                        name=f"ErrorCollector-{source_name}"
                    )
                    thread.start()
                    self.threads.append(thread)
                    print(f"  ✓ Monitoring {source_name}: {config['path']}")
                
            except Exception as e:
                print(f"  ✗ Failed to start collector for {source_name}: {e}")
        
        print(f"✅ Error collector started ({len(self.threads)} sources)")
    
    def stop(self):
        """Stop all collectors"""
        print("🛑 Stopping error collector...")
        self.running = False
        
        for thread in self.threads:
            thread.join(timeout=2)
        
        self.threads.clear()
        print("✅ Error collector stopped")
    
    def _tail_file(self, filepath: str, source: ErrorSource):
        """Tail a log file and detect errors"""
        try:
            path = Path(filepath)
            if not path.exists():
                print(f"  ⚠️  Log file not found: {filepath}")
                return
            
            # Seek to end of file
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                # Go to end
                f.seek(0, 2)
                
                while self.running:
                    line = f.readline()
                    
                    if not line:
                        time.sleep(0.1)  # Wait for new data
                        continue
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this line indicates an error
                    if self._is_error_line(line):
                        # Rate limiting check
                        if not self._should_process(source):
                            continue
                        
                        # Deduplication check
                        signature = self._get_line_signature(line, source)
                        if self._is_duplicate(signature):
                            continue
                        
                        # Process the error
                        self.on_error_detected(line, source)
                        
        except Exception as e:
            print(f"  ✗ Error tailing {filepath}: {e}")
    
    def _is_error_line(self, line: str) -> bool:
        """Check if a log line indicates an error or warning"""
        # Look for common error/warning indicators
        patterns = [
            r'\[ERROR\]',
            r'\[CRITICAL\]',
            r'\[WARNING\]',
            r'ERROR:',
            r'CRITICAL:',
            r'WARNING:',
            r'Exception:',
            r'Traceback',
            r'Failed',
            r'Error:',
            r'failed',
            r'error',
            r'rejected',
            r'insufficient',
            r'unauthorized',
            r'rate limit',
            r'connection refused',
            r'timed out',
            r'unreachable'
        ]
        
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    def _should_process(self, source: ErrorSource) -> bool:
        """Check rate limiting and burst detection"""
        now = datetime.utcnow()
        
        # Check if source is suppressed
        if self.suppressed_until.get(source):
            if now < self.suppressed_until[source]:
                return False
            else:
                self.suppressed_until[source] = None
        
        # Clean old timestamps
        cutoff = now - timedelta(seconds=self.rate_limit_window)
        self.event_timestamps[source] = [
            ts for ts in self.event_timestamps[source]
            if ts > cutoff
        ]
        
        # Check rate limit
        if len(self.event_timestamps[source]) >= self.rate_limit_max:
            print(f"⚠️  Rate limit exceeded for {source.value}, suppressing for 60s")
            self.suppressed_until[source] = now + timedelta(seconds=60)
            return False
        
        # Check for burst (10 events in 5 seconds)
        recent = [
            ts for ts in self.event_timestamps[source]
            if ts > (now - timedelta(seconds=5))
        ]
        
        if len(recent) >= self.burst_threshold:
            print(f"⚠️  Burst detected for {source.value}, suppressing for 30s")
            self.suppressed_until[source] = now + timedelta(seconds=30)
            return False
        
        # Record this event
        self.event_timestamps[source].append(now)
        return True
    
    def _get_line_signature(self, line: str, source: ErrorSource) -> str:
        """Get signature for deduplication"""
        # Normalize the line: remove timestamps, numbers, IDs
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '', line)  # Remove dates
        normalized = re.sub(r'\d{2}:\d{2}:\d{2}', '', normalized)  # Remove times
        normalized = re.sub(r'\d+', '', normalized)  # Remove all numbers
        normalized = re.sub(r'[a-f0-9]{8,}', '', normalized, flags=re.IGNORECASE)  # Remove hashes/IDs
        normalized = normalized.lower().strip()[:100]  # Normalize and truncate
        
        return f"{source.value}:{hash(normalized)}"
    
    def _is_duplicate(self, signature: str) -> bool:
        """Check if we've seen this error recently"""
        now = datetime.utcnow()
        
        # Clean old signatures
        cutoff = now - self.dedup_window
        self.seen_signatures = {
            sig: ts for sig, ts in self.seen_signatures.items()
            if ts > cutoff
        }
        
        if signature in self.seen_signatures:
            return True
        
        self.seen_signatures[signature] = now
        return False
    
    def get_stats(self) -> Dict[str, any]:
        """Get collector statistics"""
        return {
            'running': self.running,
            'sources_monitored': len(self.threads),
            'total_seen_signatures': len(self.seen_signatures),
            'rate_limits_active': sum(
                1 for ts in self.suppressed_until.values()
                if ts and ts > datetime.utcnow()
            ),
            'events_last_minute': {
                source.value: len([
                    ts for ts in timestamps
                    if ts > datetime.utcnow() - timedelta(seconds=60)
                ])
                for source, timestamps in self.event_timestamps.items()
            }
        }
