#!/usr/bin/env python3
"""
Real-time Log Parser for Error Intelligence
Parses bot logs for error patterns and returns structured error data
"""

import re
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import deque


class LogParser:
    """Parse bot logs and extract structured error information"""
    
    # Error pattern definitions
    PATTERNS = {
        'error': re.compile(r'\[ERROR\]', re.IGNORECASE),
        'reconnect': re.compile(r'\[RECONNECT\]', re.IGNORECASE),
        'heartbeat': re.compile(r'\[HEARTBEAT\]|\[HB\]', re.IGNORECASE),
        'lifecycle': re.compile(r'\[LIFECYCLE\]', re.IGNORECASE),
        'auth': re.compile(r'authentication|auth.*fail|unauthorized|invalid.*key', re.IGNORECASE),
        'websocket': re.compile(r'websocket|ws_|connection.*close|disconnect', re.IGNORECASE),
        'api': re.compile(r'api.*error|rate.*limit|timeout|http.*error', re.IGNORECASE),
        'execution': re.compile(r'order.*fail|execution.*error|trade.*error', re.IGNORECASE),
        'network': re.compile(r'network.*error|connection.*error|socket.*error', re.IGNORECASE),
    }
    
    # Timestamp patterns (ISO format, custom formats)
    TIMESTAMP_PATTERNS = [
        re.compile(r'^(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'),
        re.compile(r'^\[?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]?'),
        re.compile(r'^\[?(\d{2}:\d{2}:\d{2})\]?'),
    ]
    
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize parser with base directory"""
        # ✅ FIX NOV 10: Ensure base_dir is always a Path object
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent.parent
        else:
            self.base_dir = Path(base_dir) if not isinstance(base_dir, Path) else base_dir
        self.log_file = self.base_dir / "bot_live.log"
        
        # Cache for error deduplication
        self._error_cache = deque(maxlen=1000)
        
    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line"""
        for pattern in self.TIMESTAMP_PATTERNS:
            match = pattern.match(line.strip())
            if match:
                try:
                    ts_str = match.group(1)
                    # Try different parsing formats
                    for fmt in [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%S.%fZ',
                        '%Y-%m-%d %H:%M:%S.%f',
                        '%H:%M:%S',
                    ]:
                        try:
                            dt = datetime.strptime(ts_str.split('+')[0].split('Z')[0], fmt)
                            # If time-only, use today's date
                            if fmt == '%H:%M:%S':
                                now = datetime.now()
                                dt = dt.replace(year=now.year, month=now.month, day=now.day)
                            return dt
                        except ValueError:
                            continue
                except Exception:
                    pass
        # Default to now if no timestamp found
        return datetime.now()
    
    def _categorize_error(self, line: str) -> str:
        """Determine error category based on content"""
        line_lower = line.lower()
        
        if self.PATTERNS['auth'].search(line_lower):
            return 'Auth'
        elif self.PATTERNS['websocket'].search(line_lower):
            return 'WebSocket'
        elif self.PATTERNS['api'].search(line_lower):
            return 'API'
        elif self.PATTERNS['execution'].search(line_lower):
            return 'Execution'
        elif self.PATTERNS['network'].search(line_lower):
            return 'Network'
        else:
            return 'Other'
    
    def _determine_severity(self, line: str, prefix: str) -> str:
        """Determine severity based on prefix and content"""
        line_lower = line.lower()
        
        # Critical keywords
        critical_keywords = ['fatal', 'critical', 'authentication failed', 'unauthorized', 
                           'crash', 'panic', 'abort', 'killed']
        if any(kw in line_lower for kw in critical_keywords):
            return 'Critical'
        
        # Error prefix or error keywords
        if prefix == '[ERROR]' or 'error' in line_lower:
            # Check if it's just a warning disguised as error
            if 'warning' in line_lower or 'retry' in line_lower:
                return 'Warning'
            return 'Critical'
        
        # Reconnect events are warnings
        if prefix == '[RECONNECT]':
            return 'Warning'
        
        # Stale heartbeat
        if 'stale' in line_lower or 'timeout' in line_lower:
            return 'Warning'
        
        # Default to info
        return 'Info'
    
    def _extract_message(self, line: str) -> str:
        """Extract clean message from log line"""
        # Remove timestamp
        for pattern in self.TIMESTAMP_PATTERNS:
            line = pattern.sub('', line).strip()
        
        # Remove common prefixes
        prefixes = ['[ERROR]', '[RECONNECT]', '[HEARTBEAT]', '[HB]', '[LIFECYCLE]', 
                   '[CONNECTION]', '[WARN]', '[INFO]', '[DEBUG]']
        for prefix in prefixes:
            if prefix in line:
                line = line.split(prefix, 1)[1].strip()
                break
        
        # Limit length
        if len(line) > 500:
            line = line[:497] + '...'
        
        return line
    
    def _get_suggested_action(self, category: str, severity: str, message: str) -> str:
        """Generate suggested action based on error details"""
        message_lower = message.lower()
        
        # Auth issues
        if category == 'Auth':
            return 'Check API keys in secrets/api_keys.env and verify they are valid'
        
        # WebSocket issues
        if category == 'WebSocket':
            if 'reconnect' in message_lower:
                return 'WebSocket will auto-reconnect. Monitor for successful reconnection'
            elif 'close' in message_lower or 'disconnect' in message_lower:
                return 'Check network connectivity. WebSocket has built-in reconnection'
            else:
                return 'Review WebSocket configuration and network stability'
        
        # API issues
        if category == 'API':
            if 'rate limit' in message_lower:
                return 'Reduce API call frequency or wait for rate limit reset'
            elif 'timeout' in message_lower:
                return 'Check network latency and API endpoint availability'
            else:
                return 'Review API response and ensure proper error handling'
        
        # Execution issues
        if category == 'Execution':
            return 'Check order parameters and account balance. Review execution logs'
        
        # Network issues
        if category == 'Network':
            return 'Check internet connectivity and firewall settings'
        
        # Critical severity
        if severity == 'Critical':
            return 'Immediate attention required. Review logs and restart bot if needed'
        
        # Default
        return 'Monitor the situation. Check logs for more details'
    
    def _is_duplicate(self, error: Dict[str, Any]) -> bool:
        """Check if error is a recent duplicate"""
        key = f"{error['category']}:{error['message'][:100]}"
        if key in self._error_cache:
            return True
        self._error_cache.append(key)
        return False
    
    def tail_log(self, lines: int = 500, include_duplicates: bool = False) -> List[Dict[str, Any]]:
        """
        Tail the log file and parse errors
        
        Args:
            lines: Number of lines to read from end
            include_duplicates: Whether to include duplicate errors
            
        Returns:
            List of parsed error dictionaries
        """
        if not self.log_file.exists():
            return []
        
        try:
            # Read last N lines efficiently
            with open(self.log_file, 'r', encoding='utf-8', errors='replace') as f:
                # Seek to end
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                # Read in chunks from end
                chunk_size = 8192
                lines_found = []
                position = file_size
                
                while len(lines_found) < lines and position > 0:
                    # Move back one chunk
                    chunk_size = min(chunk_size, position)
                    position -= chunk_size
                    f.seek(position)
                    
                    # Read chunk and split into lines
                    chunk = f.read(chunk_size)
                    chunk_lines = chunk.split('\n')
                    
                    # Add to found lines
                    lines_found = chunk_lines + lines_found
                
                # Take last N lines
                log_lines = lines_found[-lines:] if len(lines_found) > lines else lines_found
            
            # Parse errors
            errors = []
            for line in log_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line contains error patterns
                prefix = None
                if self.PATTERNS['error'].search(line):
                    prefix = '[ERROR]'
                elif self.PATTERNS['reconnect'].search(line):
                    prefix = '[RECONNECT]'
                elif self.PATTERNS['heartbeat'].search(line):
                    # Check for stale heartbeat
                    if 'stale' not in line.lower() and 'timeout' not in line.lower():
                        continue
                    prefix = '[HEARTBEAT]'
                else:
                    # Check for implicit errors
                    if not any(kw in line.lower() for kw in ['error', 'fail', 'exception', 'critical']):
                        continue
                    prefix = '[ERROR]'
                
                # Extract details
                timestamp = self._extract_timestamp(line)
                category = self._categorize_error(line)
                severity = self._determine_severity(line, prefix)
                message = self._extract_message(line)
                
                if not message:
                    continue
                
                # Build error dict
                error = {
                    'timestamp': timestamp.isoformat(),
                    'severity': severity,
                    'category': category,
                    'message': message,
                    'suggested_action': self._get_suggested_action(category, severity, message),
                    'raw_line': line,
                }
                
                # Check for duplicates
                if not include_duplicates and self._is_duplicate(error):
                    continue
                
                errors.append(error)
            
            # Sort by timestamp (newest first)
            errors.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return errors
            
        except Exception as e:
            print(f"Error parsing log file: {e}")
            return []
    
    def get_latest_errors(self, max_errors: int = 50, 
                         severity_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get latest errors with optional filtering
        
        Args:
            max_errors: Maximum number of errors to return
            severity_filter: Filter by severity ('Critical', 'Warning', 'Info', 'All')
            
        Returns:
            Dictionary with errors and metadata
        """
        errors = self.tail_log(lines=500)
        
        # Apply severity filter
        if severity_filter and severity_filter != 'All':
            errors = [e for e in errors if e['severity'] == severity_filter]
        
        # Limit results
        errors = errors[:max_errors]
        
        # Calculate stats
        severity_counts = {
            'Critical': sum(1 for e in errors if e['severity'] == 'Critical'),
            'Warning': sum(1 for e in errors if e['severity'] == 'Warning'),
            'Info': sum(1 for e in errors if e['severity'] == 'Info'),
        }
        
        category_counts = {}
        for error in errors:
            cat = error['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return {
            'success': True,
            'errors': errors,
            'total_count': len(errors),
            'severity_counts': severity_counts,
            'category_counts': category_counts,
            'log_file': str(self.log_file),
            'log_exists': self.log_file.exists(),
            'timestamp': datetime.now().isoformat(),
        }


def get_parser(base_dir: Optional[Path] = None) -> LogParser:
    """Factory function to get log parser instance"""
    return LogParser(base_dir)


# Convenience function for quick access
def parse_latest_errors(lines: int = 500, max_errors: int = 50, 
                       severity_filter: Optional[str] = None) -> Dict[str, Any]:
    """Quick function to parse latest errors"""
    parser = get_parser()
    return parser.get_latest_errors(max_errors, severity_filter)
