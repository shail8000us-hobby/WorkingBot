#!/usr/bin/env python3
"""
Log Consolidation Script
Consolidates scattered logs into unified format
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from pathlib import Path
import argparse

class LogConsolidator:
    """Consolidates logs from multiple sources into unified format"""
    
    def __init__(self, bot_dir: str = None):
        self.bot_dir = bot_dir or os.getcwd()
        self.logs_dir = os.path.join(self.bot_dir, 'logs')
        self.main_log_file = os.path.join(self.bot_dir, 'bot.log')
        
        # Log file patterns to search
        self.log_patterns = [
            'bot.log',
            'bot_*.log',
            'logs/*.log',
            'webui_backend*.log',
            'guardian*.log',
            '*.log'
        ]
        
        # Trade execution patterns
        self.trade_patterns = [
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(BUY|SELL) FILLED.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?FILLED.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(BUY|SELL).*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)'
        ]
        
        # Error patterns
        self.error_patterns = [
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?\[ERROR\].*?(.+)',
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?ERROR.*?(.+)'
        ]
    
    def find_log_files(self) -> List[str]:
        """Find all log files in the bot directory"""
        log_files = []
        
        # Search in bot directory
        for pattern in self.log_patterns:
            if '*' in pattern:
                # Use glob pattern
                import glob
                matches = glob.glob(os.path.join(self.bot_dir, pattern))
                log_files.extend(matches)
            else:
                # Direct file path
                file_path = os.path.join(self.bot_dir, pattern)
                if os.path.exists(file_path):
                    log_files.append(file_path)
        
        # Remove duplicates and sort by modification time
        log_files = list(set(log_files))
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        return log_files
    
    def parse_log_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse a single log file and extract structured data"""
        entries = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Try to extract timestamp
                timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not timestamp_match:
                    continue
                
                timestamp = timestamp_match.group(1)
                
                # Check for trade executions
                trade_match = self._extract_trade(line)
                if trade_match:
                    entries.append({
                        'timestamp': timestamp,
                        'type': 'trade',
                        'file': file_path,
                        'line': line_num,
                        'data': trade_match,
                        'raw_line': line
                    })
                    continue
                
                # Check for errors
                error_match = self._extract_error(line)
                if error_match:
                    entries.append({
                        'timestamp': timestamp,
                        'type': 'error',
                        'file': file_path,
                        'line': line_num,
                        'data': error_match,
                        'raw_line': line
                    })
                    continue
                
                # Check for position changes
                position_match = self._extract_position(line)
                if position_match:
                    entries.append({
                        'timestamp': timestamp,
                        'type': 'position',
                        'file': file_path,
                        'line': line_num,
                        'data': position_match,
                        'raw_line': line
                    })
                    continue
                
                # Other log entries
                entries.append({
                    'timestamp': timestamp,
                    'type': 'info',
                    'file': file_path,
                    'line': line_num,
                    'data': {'message': line},
                    'raw_line': line
                })
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        
        return entries
    
    def _extract_trade(self, line: str) -> Dict[str, Any]:
        """Extract trade information from log line"""
        for pattern in self.trade_patterns:
            match = re.search(pattern, line)
            if match:
                groups = match.groups()
                if len(groups) >= 4:
                    return {
                        'action': groups[1] if len(groups) > 1 else 'TRADE',
                        'size': float(groups[2]) if len(groups) > 2 else 0,
                        'price': float(groups[3]) if len(groups) > 3 else 0
                    }
                elif len(groups) >= 3:
                    return {
                        'action': 'TRADE',
                        'size': float(groups[1]) if len(groups) > 1 else 0,
                        'price': float(groups[2]) if len(groups) > 2 else 0
                    }
        return None
    
    def _extract_error(self, line: str) -> Dict[str, Any]:
        """Extract error information from log line"""
        for pattern in self.error_patterns:
            match = re.search(pattern, line)
            if match:
                return {
                    'message': match.group(2).strip(),
                    'severity': 'ERROR'
                }
        return None
    
    def _extract_position(self, line: str) -> Dict[str, Any]:
        """Extract position information from log line"""
        position_patterns = [
            r'POSITION\s+(\w+).*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'position.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'open.*?position.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)'
        ]
        
        for pattern in position_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    return {
                        'action': groups[0],
                        'size': float(groups[1]),
                        'price': float(groups[2])
                    }
                elif len(groups) >= 2:
                    return {
                        'action': 'UPDATE',
                        'size': float(groups[0]),
                        'price': float(groups[1])
                    }
        return None
    
    def consolidate_logs(self, output_file: str = None) -> Dict[str, Any]:
        """Consolidate all logs into a single structured file"""
        if output_file is None:
            output_file = os.path.join(self.bot_dir, 'consolidated_logs.json')
        
        print("🔍 Finding log files...")
        log_files = self.find_log_files()
        print(f"Found {len(log_files)} log files")
        
        all_entries = []
        file_stats = {}
        
        for file_path in log_files:
            print(f"📄 Processing {os.path.basename(file_path)}...")
            entries = self.parse_log_file(file_path)
            all_entries.extend(entries)
            
            file_stats[file_path] = {
                'entries': len(entries),
                'trades': len([e for e in entries if e['type'] == 'trade']),
                'errors': len([e for e in entries if e['type'] == 'error']),
                'positions': len([e for e in entries if e['type'] == 'position'])
            }
        
        # Sort entries by timestamp
        all_entries.sort(key=lambda x: x['timestamp'])
        
        # Create consolidated data
        consolidated_data = {
            'metadata': {
                'consolidated_at': datetime.now().isoformat(),
                'total_entries': len(all_entries),
                'total_files': len(log_files),
                'file_stats': file_stats
            },
            'entries': all_entries,
            'summary': self._create_summary(all_entries)
        }
        
        # Save consolidated logs
        with open(output_file, 'w') as f:
            json.dump(consolidated_data, f, indent=2)
        
        print(f"✅ Consolidated {len(all_entries)} entries into {output_file}")
        
        return consolidated_data
    
    def _create_summary(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary statistics from log entries"""
        summary = {
            'total_entries': len(entries),
            'by_type': {},
            'by_file': {},
            'trade_summary': {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_volume': 0,
                'total_value': 0
            },
            'error_summary': {
                'total_errors': 0,
                'error_types': {}
            },
            'time_range': {
                'earliest': None,
                'latest': None
            }
        }
        
        # Count by type
        for entry in entries:
            entry_type = entry['type']
            summary['by_type'][entry_type] = summary['by_type'].get(entry_type, 0) + 1
            
            # Count by file
            file_name = os.path.basename(entry['file'])
            summary['by_file'][file_name] = summary['by_file'].get(file_name, 0) + 1
            
            # Trade summary
            if entry_type == 'trade':
                data = entry['data']
                summary['trade_summary']['total_trades'] += 1
                
                if 'BUY' in data.get('action', '').upper():
                    summary['trade_summary']['buy_trades'] += 1
                elif 'SELL' in data.get('action', '').upper():
                    summary['trade_summary']['sell_trades'] += 1
                
                size = data.get('size', 0)
                price = data.get('price', 0)
                summary['trade_summary']['total_volume'] += size
                summary['trade_summary']['total_value'] += size * price
            
            # Error summary
            elif entry_type == 'error':
                summary['error_summary']['total_errors'] += 1
                error_msg = entry['data'].get('message', 'Unknown error')
                error_type = error_msg.split(':')[0] if ':' in error_msg else 'General'
                summary['error_summary']['error_types'][error_type] = summary['error_summary']['error_types'].get(error_type, 0) + 1
            
            # Time range
            timestamp = entry['timestamp']
            if summary['time_range']['earliest'] is None or timestamp < summary['time_range']['earliest']:
                summary['time_range']['earliest'] = timestamp
            if summary['time_range']['latest'] is None or timestamp > summary['time_range']['latest']:
                summary['time_range']['latest'] = timestamp
        
        return summary
    
    def create_unified_bot_log(self, output_file: str = None) -> str:
        """Create a unified bot.log file with all critical events"""
        if output_file is None:
            output_file = os.path.join(self.bot_dir, 'bot_unified.log')
        
        print("🔄 Creating unified bot.log...")
        
        # Find all log files
        log_files = self.find_log_files()
        
        # Collect all entries
        all_entries = []
        for file_path in log_files:
            entries = self.parse_log_file(file_path)
            all_entries.extend(entries)
        
        # Filter for critical events
        critical_events = [
            e for e in all_entries 
            if e['type'] in ['trade', 'error', 'position'] or 
               'FILLED' in e['raw_line'] or 
               'ERROR' in e['raw_line'] or
               'CRITICAL' in e['raw_line']
        ]
        
        # Sort by timestamp
        critical_events.sort(key=lambda x: x['timestamp'])
        
        # Write unified log
        with open(output_file, 'w') as f:
            for entry in critical_events:
                f.write(f"{entry['timestamp']} [{entry['type'].upper()}] {os.path.basename(entry['file'])}: {entry['raw_line']}\n")
        
        print(f"✅ Created unified bot.log with {len(critical_events)} critical events")
        return output_file

def main():
    """CLI interface for log consolidation"""
    parser = argparse.ArgumentParser(description='Log Consolidation Tool')
    parser.add_argument('--bot-dir', type=str, default=os.getcwd(),
                       help='Bot directory path')
    parser.add_argument('--output', type=str,
                       help='Output file for consolidated logs')
    parser.add_argument('--unified-log', action='store_true',
                       help='Create unified bot.log file')
    parser.add_argument('--stats', action='store_true',
                       help='Show consolidation statistics')
    
    args = parser.parse_args()
    
    consolidator = LogConsolidator(args.bot_dir)
    
    if args.unified_log:
        output_file = consolidator.create_unified_bot_log()
        print(f"Unified log created: {output_file}")
    
    else:
        consolidated_data = consolidator.consolidate_logs(args.output)
        
        if args.stats:
            print("\n📊 Consolidation Statistics:")
            print(f"Total entries: {consolidated_data['metadata']['total_entries']}")
            print(f"Total files: {consolidated_data['metadata']['total_files']}")
            print(f"Trade summary: {consolidated_data['summary']['trade_summary']}")
            print(f"Error summary: {consolidated_data['summary']['error_summary']}")

if __name__ == '__main__':
    main()

