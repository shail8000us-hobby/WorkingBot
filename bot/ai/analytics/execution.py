"""
Institutional-Grade Execution Quality Analytics Module

This module provides professional-grade execution quality metrics:
- Fill Rate - percentage of orders successfully filled
- Slippage - difference between expected and actual execution price
- Latency - time from order placement to fill
- Rejection Rate - percentage of orders rejected

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Iterator
import json
from pathlib import Path


def _iter_orders_jsonl(file_path: Path) -> Iterator[Dict[str, Any]]:
    if not file_path.exists():
        return
    try:
        with file_path.open('r', encoding='utf-8', errors='replace') as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            yield item
                    continue
                if isinstance(payload, dict):
                    yield payload
    except Exception:
        return


class ExecutionAnalytics:
    """
    Professional-grade execution quality analytics engine
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the execution analytics engine"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.cache = {}
        self.cache_ttl = 60
        self.last_cache_time = None
    
    # =========================================================================
    # EXECUTION QUALITY METRICS
    # =========================================================================
    
    def calculate_fill_rate(self, orders: List[Dict[str, Any]]) -> float:
        """
        Calculate fill rate - percentage of orders successfully filled
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            Fill rate as percentage (0-100)
        """
        if not orders:
            return 0.0
        
        filled_orders = sum(1 for o in orders if o.get('status') == 'filled')
        fill_rate = (filled_orders / len(orders)) * 100
        
        return round(fill_rate, 2)
    
    def calculate_slippage(self, orders: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate slippage - difference between expected and actual execution price
        
        Args:
            orders: List of order dictionaries with 'expected_price' and 'fill_price'
        
        Returns:
            Dictionary with avg_slippage, max_slippage, slippage_pct
        """
        if not orders:
            return {
                'avg_slippage': 0.0,
                'max_slippage': 0.0,
                'avg_slippage_pct': 0.0,
                'max_slippage_pct': 0.0
            }
        
        slippages = []
        slippage_pcts = []
        
        for order in orders:
            if order.get('status') != 'filled':
                continue
            
            expected_price = order.get('expected_price') or order.get('price', 0)
            fill_price = order.get('fill_price') or order.get('price', 0)
            
            if expected_price == 0:
                continue
            
            slippage = abs(fill_price - expected_price)
            slippage_pct = (slippage / expected_price) * 100
            
            slippages.append(slippage)
            slippage_pcts.append(slippage_pct)
        
        if not slippages:
            return {
                'avg_slippage': 0.0,
                'max_slippage': 0.0,
                'avg_slippage_pct': 0.0,
                'max_slippage_pct': 0.0
            }
        
        return {
            'avg_slippage': round(np.mean(slippages), 2),
            'max_slippage': round(np.max(slippages), 2),
            'avg_slippage_pct': round(np.mean(slippage_pcts), 4),
            'max_slippage_pct': round(np.max(slippage_pcts), 4)
        }
    
    def calculate_latency(self, orders: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate latency - time from order placement to fill
        
        Args:
            orders: List of order dictionaries with timestamps
        
        Returns:
            Dictionary with avg_latency_ms, max_latency_ms, min_latency_ms
        """
        if not orders:
            return {
                'avg_latency_ms': 0.0,
                'max_latency_ms': 0.0,
                'min_latency_ms': 0.0
            }
        
        latencies = []
        
        for order in orders:
            if order.get('status') != 'filled':
                continue
            
            try:
                placed_time = datetime.fromisoformat(order.get('placed_at', ''))
                filled_time = datetime.fromisoformat(order.get('filled_at', ''))
                
                latency_ms = (filled_time - placed_time).total_seconds() * 1000
                latencies.append(latency_ms)
            
            except Exception:
                continue
        
        if not latencies:
            return {
                'avg_latency_ms': 0.0,
                'max_latency_ms': 0.0,
                'min_latency_ms': 0.0
            }
        
        return {
            'avg_latency_ms': round(np.mean(latencies), 2),
            'max_latency_ms': round(np.max(latencies), 2),
            'min_latency_ms': round(np.min(latencies), 2)
        }
    
    def calculate_rejection_rate(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate rejection rate - percentage of orders rejected
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            Dictionary with rejection_rate, rejection_reasons
        """
        if not orders:
            return {
                'rejection_rate': 0.0,
                'total_rejections': 0,
                'rejection_reasons': {}
            }
        
        rejected_orders = [o for o in orders if o.get('status') in ['rejected', 'failed', 'cancelled']]
        rejection_rate = (len(rejected_orders) / len(orders)) * 100
        
        # Count rejection reasons
        rejection_reasons = {}
        for order in rejected_orders:
            reason = order.get('rejection_reason', 'Unknown')
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        return {
            'rejection_rate': round(rejection_rate, 2),
            'total_rejections': len(rejected_orders),
            'rejection_reasons': rejection_reasons
        }
    
    def calculate_order_flow(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze order flow - buy/sell imbalance
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            Dictionary with buy_count, sell_count, imbalance
        """
        if not orders:
            return {
                'buy_count': 0,
                'sell_count': 0,
                'imbalance': 0.0,
                'buy_percentage': 0.0,
                'sell_percentage': 0.0
            }
        
        buy_orders = sum(1 for o in orders if o.get('side') == 'buy')
        sell_orders = sum(1 for o in orders if o.get('side') == 'sell')
        
        total = buy_orders + sell_orders
        
        if total == 0:
            return {
                'buy_count': 0,
                'sell_count': 0,
                'imbalance': 0.0,
                'buy_percentage': 0.0,
                'sell_percentage': 0.0
            }
        
        imbalance = (buy_orders - sell_orders) / total
        
        return {
            'buy_count': buy_orders,
            'sell_count': sell_orders,
            'imbalance': round(imbalance, 2),
            'buy_percentage': round((buy_orders / total) * 100, 2),
            'sell_percentage': round((sell_orders / total) * 100, 2)
        }
    
    def calculate_execution_efficiency(self, orders: List[Dict[str, Any]]) -> float:
        """
        Calculate overall execution efficiency score (0-100)
        
        Combines fill rate, slippage, latency, and rejection rate
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            Efficiency score (0-100, higher is better)
        """
        if not orders:
            return 0.0
        
        # Get individual metrics
        fill_rate = self.calculate_fill_rate(orders)
        slippage = self.calculate_slippage(orders)
        rejection_rate = self.calculate_rejection_rate(orders)['rejection_rate']
        
        # Calculate efficiency score
        # Fill rate: 40% weight
        # Slippage: 30% weight (lower is better)
        # Rejection rate: 30% weight (lower is better)
        
        fill_score = fill_rate * 0.4
        slippage_score = max(0, 100 - (slippage['avg_slippage_pct'] * 1000)) * 0.3
        rejection_score = max(0, 100 - rejection_rate) * 0.3
        
        efficiency = fill_score + slippage_score + rejection_score
        
        return round(efficiency, 2)
    
    # =========================================================================
    # DATA LOADING
    # =========================================================================
    
    def _load_orders(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Load order history from REAL event store database
        
        Args:
            lookback_days: Number of days to look back
        
        Returns:
            List of order dictionaries with real execution data
        """
        from .data_loader import get_data_loader
        
        # Get real order events from event store
        data_loader = get_data_loader()
        order_events = data_loader.get_order_events(lookback_days)
        
        # Convert event format to order format for analysis
        orders = []
        for event in order_events:
            orders.append({
                'order_id': event.get('order_id'),
                'timestamp': datetime.fromtimestamp(event['timestamp']).isoformat(),
                'status': event.get('status', event.get('event_type', '').replace('order_', '')),
                'side': event.get('side'),
                'size': event.get('size', 0),
                'price': event.get('price', 0),
                'filled_size': event.get('filled_size', 0),
                'rejection_reason': event.get('reason'),
                'event_type': event.get('event_type')
            })
        
        return orders
    
    # =========================================================================
    # COMPREHENSIVE ANALYSIS
    # =========================================================================
    
    def calculate_all_metrics(
        self,
        lookback_days: int = 30,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate all execution quality metrics
        
        Args:
            lookback_days: Number of days to analyze
            force_refresh: Force recalculation (ignore cache)
        
        Returns:
            Dictionary with all execution metrics
        """
        # Check cache
        if not force_refresh and self.last_cache_time:
            if (datetime.now() - self.last_cache_time).total_seconds() < self.cache_ttl:
                return self.cache
        
        # Load data
        orders = self._load_orders(lookback_days)
        
        # Calculate all metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'lookback_days': lookback_days,
            'total_orders': len(orders),
            
            # Core Metrics
            'fill_rate': self.calculate_fill_rate(orders),
            'slippage': self.calculate_slippage(orders),
            'latency': self.calculate_latency(orders),
            'rejection': self.calculate_rejection_rate(orders),
            
            # Order Flow
            'order_flow': self.calculate_order_flow(orders),
            
            # Overall Score
            'execution_efficiency': self.calculate_execution_efficiency(orders)
        }
        
        # Update cache
        self.cache = metrics
        self.last_cache_time = datetime.now()
        
        return metrics
    
    def get_execution_grade(self, metrics: Dict[str, Any]) -> Dict[str, str]:
        """
        Assign grades to execution metrics
        
        Args:
            metrics: Dictionary of execution metrics
        
        Returns:
            Dictionary with grades
        """
        grades = {}
        
        # Fill Rate
        fill_rate = metrics['fill_rate']
        if fill_rate >= 98:
            grades['fill_rate'] = '⭐'
        elif fill_rate >= 95:
            grades['fill_rate'] = '✓'
        elif fill_rate >= 90:
            grades['fill_rate'] = '⚠️'
        else:
            grades['fill_rate'] = '🔴'
        
        # Slippage
        slippage_pct = metrics['slippage']['avg_slippage_pct']
        if slippage_pct <= 0.05:
            grades['slippage'] = '⭐'
        elif slippage_pct <= 0.1:
            grades['slippage'] = '✓'
        elif slippage_pct <= 0.2:
            grades['slippage'] = '⚠️'
        else:
            grades['slippage'] = '🔴'
        
        # Latency
        latency_ms = metrics['latency']['avg_latency_ms']
        if latency_ms <= 100:
            grades['latency'] = '⭐'
        elif latency_ms <= 200:
            grades['latency'] = '✓'
        elif latency_ms <= 500:
            grades['latency'] = '⚠️'
        else:
            grades['latency'] = '🔴'
        
        # Rejection Rate
        rejection_rate = metrics['rejection']['rejection_rate']
        if rejection_rate <= 1:
            grades['rejection'] = '⭐'
        elif rejection_rate <= 3:
            grades['rejection'] = '✓'
        elif rejection_rate <= 5:
            grades['rejection'] = '⚠️'
        else:
            grades['rejection'] = '🔴'
        
        return grades


# Singleton accessor
_execution_analytics_instance = None

def get_execution_analytics() -> ExecutionAnalytics:
    """Get singleton instance of ExecutionAnalytics"""
    global _execution_analytics_instance
    if _execution_analytics_instance is None:
        _execution_analytics_instance = ExecutionAnalytics()
    return _execution_analytics_instance
