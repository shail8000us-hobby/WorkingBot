"""
Institutional-Grade Log Analysis Module

This module provides professional-grade log analysis:
- Real-time log parsing
- Pattern detection (order flow, errors, performance trends)
- Anomaly detection
- Trade quality analysis

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import defaultdict, Counter


class LogAnalyzer:
    """
    Professional-grade log analysis engine
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the log analyzer"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.log_file = self.base_dir / 'bot' / 'logs' / 'bot.log'
        self.cache = {}
        self.cache_ttl = 60
        self.last_cache_time = None
    
    # =========================================================================
    # LOG PARSING
    # =========================================================================
    
    def parse_logs(self, lookback_hours: int = 24) -> Dict[str, Any]:
        """
        Parse bot logs for patterns and metrics
        
        Args:
            lookback_hours: Number of hours to look back
        
        Returns:
            Dictionary with parsed log data
        """
        if not self.log_file.exists():
            return self._empty_log_data()
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        log_data = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_rejected': 0,
            'orders_cancelled': 0,
            'errors': [],
            'warnings': [],
            'info_messages': [],
            'api_calls': 0,
            'api_errors': 0,
            'slippage_events': [],
            'latency_events': [],
            'timestamps': []
        }
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        # Extract timestamp
                        timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                        if not timestamp_match:
                            continue
                        
                        timestamp = datetime.strptime(timestamp_match.group(), '%Y-%m-%d %H:%M:%S')
                        
                        if timestamp < cutoff_time:
                            continue
                        
                        log_data['timestamps'].append(timestamp)
                        
                        # Parse different log types
                        if 'ERROR' in line:
                            log_data['errors'].append({
                                'timestamp': timestamp.isoformat(),
                                'message': line.strip()
                            })
                        
                        elif 'WARNING' in line:
                            log_data['warnings'].append({
                                'timestamp': timestamp.isoformat(),
                                'message': line.strip()
                            })
                        
                        # Order events
                        if 'order placed' in line.lower() or 'placing order' in line.lower():
                            log_data['orders_placed'] += 1
                        
                        elif 'order filled' in line.lower() or 'fill confirmation' in line.lower():
                            log_data['orders_filled'] += 1
                        
                        elif 'order rejected' in line.lower() or 'order failed' in line.lower():
                            log_data['orders_rejected'] += 1
                        
                        elif 'order cancelled' in line.lower():
                            log_data['orders_cancelled'] += 1
                        
                        # API events
                        if 'api call' in line.lower() or 'fetching' in line.lower():
                            log_data['api_calls'] += 1
                        
                        if 'api error' in line.lower() or '500' in line or '403' in line:
                            log_data['api_errors'] += 1
                        
                        # Slippage events
                        slippage_match = re.search(r'slippage[:\s]+(\d+\.?\d*)', line.lower())
                        if slippage_match:
                            log_data['slippage_events'].append({
                                'timestamp': timestamp.isoformat(),
                                'slippage': float(slippage_match.group(1))
                            })
                        
                        # Latency events
                        latency_match = re.search(r'latency[:\s]+(\d+)ms', line.lower())
                        if latency_match:
                            log_data['latency_events'].append({
                                'timestamp': timestamp.isoformat(),
                                'latency_ms': int(latency_match.group(1))
                            })
                    
                    except Exception:
                        continue
        
        except Exception as e:
            return self._empty_log_data()
        
        return log_data
    
    def _empty_log_data(self) -> Dict[str, Any]:
        """Return empty log data structure"""
        return {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_rejected': 0,
            'orders_cancelled': 0,
            'errors': [],
            'warnings': [],
            'info_messages': [],
            'api_calls': 0,
            'api_errors': 0,
            'slippage_events': [],
            'latency_events': [],
            'timestamps': []
        }
    
    # =========================================================================
    # PATTERN DETECTION
    # =========================================================================
    
    def detect_patterns(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect patterns in log data
        
        Args:
            log_data: Parsed log data
        
        Returns:
            Dictionary with detected patterns
        """
        patterns = {
            'order_flow_pattern': self._detect_order_flow_pattern(log_data),
            'error_pattern': self._detect_error_pattern(log_data),
            'performance_trend': self._detect_performance_trend(log_data),
            'time_of_day_pattern': self._detect_time_of_day_pattern(log_data)
        }
        
        return patterns
    
    def _detect_order_flow_pattern(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect order flow patterns"""
        total_orders = log_data['orders_placed']
        filled_orders = log_data['orders_filled']
        rejected_orders = log_data['orders_rejected']
        
        if total_orders == 0:
            return {
                'pattern': 'NO_ACTIVITY',
                'description': 'No orders placed',
                'severity': 'info'
            }
        
        fill_rate = (filled_orders / total_orders) * 100 if total_orders > 0 else 0
        rejection_rate = (rejected_orders / total_orders) * 100 if total_orders > 0 else 0
        
        if rejection_rate > 10:
            return {
                'pattern': 'HIGH_REJECTION',
                'description': f'High order rejection rate: {rejection_rate:.1f}%',
                'severity': 'critical',
                'fill_rate': fill_rate,
                'rejection_rate': rejection_rate
            }
        
        elif fill_rate < 90:
            return {
                'pattern': 'LOW_FILL_RATE',
                'description': f'Low fill rate: {fill_rate:.1f}%',
                'severity': 'warning',
                'fill_rate': fill_rate,
                'rejection_rate': rejection_rate
            }
        
        else:
            return {
                'pattern': 'HEALTHY',
                'description': f'Healthy order flow (Fill: {fill_rate:.1f}%)',
                'severity': 'info',
                'fill_rate': fill_rate,
                'rejection_rate': rejection_rate
            }
    
    def _detect_error_pattern(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect error patterns"""
        errors = log_data['errors']
        warnings = log_data['warnings']
        
        if len(errors) == 0:
            return {
                'pattern': 'NO_ERRORS',
                'description': 'No errors detected',
                'severity': 'info'
            }
        
        # Count error types
        error_types = Counter()
        for error in errors:
            msg = error['message'].lower()
            
            if 'api' in msg or 'connection' in msg or 'timeout' in msg:
                error_types['API_ERROR'] += 1
            elif 'insufficient' in msg or 'balance' in msg:
                error_types['BALANCE_ERROR'] += 1
            elif 'liquidation' in msg:
                error_types['LIQUIDATION_ERROR'] += 1
            else:
                error_types['OTHER_ERROR'] += 1
        
        most_common_error = error_types.most_common(1)[0] if error_types else ('UNKNOWN', 0)
        
        if len(errors) > 10:
            return {
                'pattern': 'FREQUENT_ERRORS',
                'description': f'Frequent errors detected ({len(errors)} errors)',
                'severity': 'critical',
                'total_errors': len(errors),
                'most_common_error': most_common_error[0],
                'error_types': dict(error_types)
            }
        
        elif len(errors) > 5:
            return {
                'pattern': 'MODERATE_ERRORS',
                'description': f'Moderate error rate ({len(errors)} errors)',
                'severity': 'warning',
                'total_errors': len(errors),
                'most_common_error': most_common_error[0],
                'error_types': dict(error_types)
            }
        
        else:
            return {
                'pattern': 'LOW_ERRORS',
                'description': f'Low error rate ({len(errors)} errors)',
                'severity': 'info',
                'total_errors': len(errors),
                'most_common_error': most_common_error[0],
                'error_types': dict(error_types)
            }
    
    def _detect_performance_trend(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect performance trends"""
        api_calls = log_data['api_calls']
        api_errors = log_data['api_errors']
        
        if api_calls == 0:
            return {
                'trend': 'NO_DATA',
                'description': 'No API activity',
                'severity': 'info'
            }
        
        error_rate = (api_errors / api_calls) * 100 if api_calls > 0 else 0
        
        if error_rate > 5:
            return {
                'trend': 'DEGRADING',
                'description': f'Performance degrading (API error rate: {error_rate:.1f}%)',
                'severity': 'warning',
                'api_error_rate': error_rate
            }
        
        else:
            return {
                'trend': 'STABLE',
                'description': f'Performance stable (API error rate: {error_rate:.1f}%)',
                'severity': 'info',
                'api_error_rate': error_rate
            }
    
    def _detect_time_of_day_pattern(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect time-of-day patterns"""
        timestamps = log_data['timestamps']
        
        if not timestamps:
            return {
                'pattern': 'NO_DATA',
                'description': 'No timestamp data',
                'severity': 'info'
            }
        
        # Count activity by hour
        hour_counts = defaultdict(int)
        for ts in timestamps:
            hour_counts[ts.hour] += 1
        
        if not hour_counts:
            return {
                'pattern': 'NO_DATA',
                'description': 'No timestamp data',
                'severity': 'info'
            }
        
        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_count = hour_counts[peak_hour]
        
        return {
            'pattern': 'TIME_BASED',
            'description': f'Peak activity at {peak_hour}:00 ({peak_count} events)',
            'severity': 'info',
            'peak_hour': peak_hour,
            'peak_count': peak_count,
            'hourly_distribution': dict(hour_counts)
        }
    
    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================
    
    def detect_anomalies(self, log_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in log data
        
        Args:
            log_data: Parsed log data
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # High rejection rate
        total_orders = log_data['orders_placed']
        rejected_orders = log_data['orders_rejected']
        
        if total_orders > 0:
            rejection_rate = (rejected_orders / total_orders) * 100
            
            if rejection_rate > 10:
                anomalies.append({
                    'type': 'HIGH_REJECTION_RATE',
                    'severity': 'critical',
                    'message': f'Order rejection rate is abnormally high: {rejection_rate:.1f}%',
                    'value': rejection_rate,
                    'threshold': 10
                })
        
        # High API error rate
        api_calls = log_data['api_calls']
        api_errors = log_data['api_errors']
        
        if api_calls > 0:
            api_error_rate = (api_errors / api_calls) * 100
            
            if api_error_rate > 5:
                anomalies.append({
                    'type': 'HIGH_API_ERROR_RATE',
                    'severity': 'warning',
                    'message': f'API error rate is high: {api_error_rate:.1f}%',
                    'value': api_error_rate,
                    'threshold': 5
                })
        
        # Excessive slippage
        slippage_events = log_data['slippage_events']
        if slippage_events:
            avg_slippage = sum(e['slippage'] for e in slippage_events) / len(slippage_events)
            
            if avg_slippage > 0.5:  # 0.5% slippage
                anomalies.append({
                    'type': 'HIGH_SLIPPAGE',
                    'severity': 'warning',
                    'message': f'Average slippage is high: {avg_slippage:.2f}%',
                    'value': avg_slippage,
                    'threshold': 0.5
                })
        
        # High latency
        latency_events = log_data['latency_events']
        if latency_events:
            avg_latency = sum(e['latency_ms'] for e in latency_events) / len(latency_events)
            
            if avg_latency > 500:  # 500ms
                anomalies.append({
                    'type': 'HIGH_LATENCY',
                    'severity': 'warning',
                    'message': f'Average latency is high: {avg_latency:.0f}ms',
                    'value': avg_latency,
                    'threshold': 500
                })
        
        # Frequent errors
        if len(log_data['errors']) > 10:
            anomalies.append({
                'type': 'FREQUENT_ERRORS',
                'severity': 'critical',
                'message': f'Frequent errors detected: {len(log_data["errors"])} errors',
                'value': len(log_data['errors']),
                'threshold': 10
            })
        
        return anomalies
    
    # =========================================================================
    # COMPREHENSIVE ANALYSIS
    # =========================================================================
    
    def analyze_logs(
        self,
        lookback_hours: int = 24,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Perform comprehensive log analysis
        
        Args:
            lookback_hours: Number of hours to analyze
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with complete log analysis
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Parse logs
        log_data = self.parse_logs(lookback_hours)
        
        # Detect patterns
        patterns = self.detect_patterns(log_data)
        
        # Detect anomalies
        anomalies = self.detect_anomalies(log_data)
        
        # Compile analysis
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'lookback_hours': lookback_hours,
            
            # Raw metrics
            'metrics': {
                'orders_placed': log_data['orders_placed'],
                'orders_filled': log_data['orders_filled'],
                'orders_rejected': log_data['orders_rejected'],
                'orders_cancelled': log_data['orders_cancelled'],
                'total_errors': len(log_data['errors']),
                'total_warnings': len(log_data['warnings']),
                'api_calls': log_data['api_calls'],
                'api_errors': log_data['api_errors']
            },
            
            # Patterns
            'patterns': patterns,
            
            # Anomalies
            'anomalies': anomalies,
            
            # Recent errors (last 5)
            'recent_errors': log_data['errors'][-5:] if log_data['errors'] else [],
            
            # Recent warnings (last 5)
            'recent_warnings': log_data['warnings'][-5:] if log_data['warnings'] else []
        }
        
        # Update cache
        self.cache = analysis
        self.last_cache_time = datetime.now()
        
        return analysis
    
    def get_health_status(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get overall health status from log analysis
        
        Args:
            analysis: Log analysis dictionary
        
        Returns:
            Dictionary with health status
        """
        critical_anomalies = [a for a in analysis['anomalies'] if a['severity'] == 'critical']
        warning_anomalies = [a for a in analysis['anomalies'] if a['severity'] == 'warning']
        
        if critical_anomalies:
            status = 'CRITICAL'
            message = f'{len(critical_anomalies)} critical issues detected'
            color = '🔴'
        elif warning_anomalies:
            status = 'WARNING'
            message = f'{len(warning_anomalies)} warnings detected'
            color = '⚠️'
        else:
            status = 'HEALTHY'
            message = 'All systems operating normally'
            color = '✓'
        
        return {
            'status': status,
            'message': message,
            'color': color,
            'critical_count': len(critical_anomalies),
            'warning_count': len(warning_anomalies)
        }


# Singleton accessor
_log_analyzer_instance = None

def get_log_analyzer() -> LogAnalyzer:
    """Get singleton instance of LogAnalyzer"""
    global _log_analyzer_instance
    if _log_analyzer_instance is None:
        _log_analyzer_instance = LogAnalyzer()
    return _log_analyzer_instance

