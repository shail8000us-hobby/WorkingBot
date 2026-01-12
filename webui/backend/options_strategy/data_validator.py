"""
Market Data Validation Module for WorkingBot
=============================================
Validates market data quality before strategy execution.
Catches stale data, invalid prices, wide spreads, and arbitrage violations.

Imported from OptionBot project with adaptations.
Original: data/data_validator.py

Usage:
    from webui.backend.options_strategy.data_validator import MarketDataValidator
    
    validator = MarketDataValidator()
    
    # Before strategy execution
    alerts = await validator.validate_option_data(option_data)
    if any(a.severity == 'critical' for a in alerts):
        raise DataError("Critical data quality issue detected")
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)


class DataQualityIssue(Enum):
    """Types of data quality issues"""
    STALE_DATA = "stale_data"
    MISSING_GREEKS = "missing_greeks"
    INVALID_PRICES = "invalid_prices"
    WIDE_SPREADS = "wide_spreads"
    ZERO_VOLUME = "zero_volume"
    INCONSISTENT_IV = "inconsistent_iv"
    ARBITRAGE_VIOLATION = "arbitrage_violation"
    CROSSED_MARKET = "crossed_market"


@dataclass
class DataQualityAlert:
    """
    Represents a data quality issue.
    
    Attributes:
        issue_type: Type of issue detected
        severity: 'low', 'medium', 'high', 'critical'
        message: Human-readable description
        affected_symbols: List of affected option symbols
        timestamp: When the issue was detected
        metadata: Additional context (thresholds, values, etc.)
    """
    issue_type: DataQualityIssue
    severity: str
    message: str
    affected_symbols: List[str]
    timestamp: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'issue_type': self.issue_type.value,
            'severity': self.severity,
            'message': self.message,
            'affected_symbols': self.affected_symbols,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


class MarketDataValidator:
    """
    Comprehensive market data validation and quality control.
    
    Validates:
    - Data freshness (staleness)
    - Price validity (negative, crossed markets)
    - Bid-ask spreads (liquidity)
    - IV consistency (outliers)
    - Put-call parity (arbitrage)
    
    Example:
        validator = MarketDataValidator()
        
        # Validate single option
        alerts = validator.validate_option_quote(option_data)
        
        # Get quality score
        score = validator.calculate_quality_score()
    """

    def __init__(
        self,
        max_data_age: int = 300,
        max_bid_ask_spread: float = 0.50,
        min_volume_threshold: int = 0,
        max_iv_deviation: float = 2.5
    ):
        """
        Initialize validator with quality thresholds.
        
        Args:
            max_data_age: Maximum acceptable data age in seconds (default: 5 min)
            max_bid_ask_spread: Maximum spread as fraction of mid price (default: 50%)
            min_volume_threshold: Minimum volume for warnings (default: 0)
            max_iv_deviation: Max IV z-score for outlier detection (default: 2.5)
        """
        self.max_data_age = max_data_age
        self.max_bid_ask_spread = max_bid_ask_spread
        self.min_volume_threshold = min_volume_threshold
        self.max_iv_deviation = max_iv_deviation
        
        # Alert history
        self.quality_alerts: deque = deque(maxlen=1000)
        
        # IV history for consistency checking
        self.iv_history: List[float] = []
        
        logger.info(f"MarketDataValidator initialized: max_age={max_data_age}s, max_spread={max_bid_ask_spread*100}%")

    def validate_option_quote(
        self,
        symbol: str,
        bid: float = None,
        ask: float = None,
        mark_price: float = None,
        volume: int = None,
        iv: float = None,
        delta: float = None,
        last_updated: datetime = None
    ) -> List[DataQualityAlert]:
        """
        Validate a single option quote.
        
        Args:
            symbol: Option symbol
            bid: Bid price
            ask: Ask price
            mark_price: Mark/mid price
            volume: Trading volume
            iv: Implied volatility
            delta: Option delta
            last_updated: When data was last updated
            
        Returns:
            List of DataQualityAlert objects
        """
        alerts: List[DataQualityAlert] = []
        current_time = datetime.now()
        
        # Check data freshness
        if last_updated:
            data_age = (current_time - last_updated).total_seconds()
            if data_age > self.max_data_age:
                alerts.append(DataQualityAlert(
                    issue_type=DataQualityIssue.STALE_DATA,
                    severity='high' if data_age > self.max_data_age * 2 else 'medium',
                    message=f"Data is {data_age:.0f} seconds old (threshold: {self.max_data_age}s)",
                    affected_symbols=[symbol],
                    timestamp=current_time,
                    metadata={'data_age': data_age, 'threshold': self.max_data_age}
                ))
        
        # Check for invalid prices
        if bid is not None and bid < 0:
            alerts.append(DataQualityAlert(
                issue_type=DataQualityIssue.INVALID_PRICES,
                severity='critical',
                message=f"Negative bid price: {bid}",
                affected_symbols=[symbol],
                timestamp=current_time,
                metadata={'bid': bid}
            ))
        
        if ask is not None and ask < 0:
            alerts.append(DataQualityAlert(
                issue_type=DataQualityIssue.INVALID_PRICES,
                severity='critical',
                message=f"Negative ask price: {ask}",
                affected_symbols=[symbol],
                timestamp=current_time,
                metadata={'ask': ask}
            ))
        
        # Check for crossed market
        if bid is not None and ask is not None and bid > ask:
            alerts.append(DataQualityAlert(
                issue_type=DataQualityIssue.CROSSED_MARKET,
                severity='critical',
                message=f"Crossed market: bid ({bid}) > ask ({ask})",
                affected_symbols=[symbol],
                timestamp=current_time,
                metadata={'bid': bid, 'ask': ask}
            ))
        
        # Check bid-ask spread
        if bid is not None and ask is not None and bid > 0 and ask > 0 and bid <= ask:
            mid_price = (bid + ask) / 2
            if mid_price > 0:
                spread = (ask - bid) / mid_price
                if spread > self.max_bid_ask_spread:
                    alerts.append(DataQualityAlert(
                        issue_type=DataQualityIssue.WIDE_SPREADS,
                        severity='medium' if spread < self.max_bid_ask_spread * 1.5 else 'high',
                        message=f"Wide bid-ask spread: {spread:.1%} (threshold: {self.max_bid_ask_spread:.1%})",
                        affected_symbols=[symbol],
                        timestamp=current_time,
                        metadata={'spread': spread, 'threshold': self.max_bid_ask_spread, 'bid': bid, 'ask': ask}
                    ))
        
        # Check volume
        if volume is not None and volume < self.min_volume_threshold:
            alerts.append(DataQualityAlert(
                issue_type=DataQualityIssue.ZERO_VOLUME,
                severity='low',
                message=f"Low/zero volume: {volume}",
                affected_symbols=[symbol],
                timestamp=current_time,
                metadata={'volume': volume, 'threshold': self.min_volume_threshold}
            ))
        
        # Check IV for outliers
        if iv is not None and iv > 0:
            self.iv_history.append(iv)
            if len(self.iv_history) > 100:
                self.iv_history.pop(0)
            
            if len(self.iv_history) > 10:
                iv_mean = statistics.mean(self.iv_history)
                iv_std = statistics.stdev(self.iv_history)
                if iv_std > 0:
                    z_score = abs(iv - iv_mean) / iv_std
                    if z_score > self.max_iv_deviation:
                        alerts.append(DataQualityAlert(
                            issue_type=DataQualityIssue.INCONSISTENT_IV,
                            severity='medium',
                            message=f"IV outlier: {iv:.1%} (z-score: {z_score:.1f})",
                            affected_symbols=[symbol],
                            timestamp=current_time,
                            metadata={'iv': iv, 'z_score': z_score, 'iv_mean': iv_mean}
                        ))
        
        # Check for missing Greeks
        if delta is None and self.min_volume_threshold > 0:
            alerts.append(DataQualityAlert(
                issue_type=DataQualityIssue.MISSING_GREEKS,
                severity='low',
                message="Missing delta value",
                affected_symbols=[symbol],
                timestamp=current_time,
                metadata={'symbol': symbol}
            ))
        
        # Store alerts
        for alert in alerts:
            self.quality_alerts.append(alert)
        
        return alerts

    def validate_option_chain(
        self,
        chain_data: Dict[str, Any],
        spot_price: float = None
    ) -> List[DataQualityAlert]:
        """
        Validate an entire option chain.
        
        Args:
            chain_data: Dictionary with 'calls' and 'puts' lists
            spot_price: Current spot price for arbitrage checks
            
        Returns:
            List of DataQualityAlert objects
        """
        alerts: List[DataQualityAlert] = []
        current_time = datetime.now()
        
        calls = chain_data.get('calls', [])
        puts = chain_data.get('puts', [])
        
        # Validate individual options
        for option in calls + puts:
            option_alerts = self.validate_option_quote(
                symbol=option.get('symbol', 'unknown'),
                bid=option.get('bid_price') or option.get('bid'),
                ask=option.get('ask_price') or option.get('ask'),
                mark_price=option.get('mark_price') or option.get('mark'),
                volume=option.get('volume'),
                iv=option.get('mark_iv') or option.get('iv'),
                delta=option.get('delta')
            )
            alerts.extend(option_alerts)
        
        # Check put-call parity if spot price available
        if spot_price and spot_price > 0:
            parity_alerts = self._check_put_call_parity(calls, puts, spot_price)
            alerts.extend(parity_alerts)
        
        # Check IV smile consistency
        iv_alerts = self._check_iv_consistency(calls + puts)
        alerts.extend(iv_alerts)
        
        return alerts

    def _check_put_call_parity(
        self,
        calls: List[Dict],
        puts: List[Dict],
        spot_price: float
    ) -> List[DataQualityAlert]:
        """
        Check for put-call parity violations (potential arbitrage).
        
        Put-Call Parity: C - P = S - K (simplified, ignoring interest/time)
        """
        alerts: List[DataQualityAlert] = []
        current_time = datetime.now()
        
        # Group by strike
        call_by_strike = {self._get_strike(c): c for c in calls}
        put_by_strike = {self._get_strike(p): p for p in puts}
        
        common_strikes = set(call_by_strike.keys()) & set(put_by_strike.keys())
        
        for strike in common_strikes:
            if strike is None:
                continue
            
            call = call_by_strike[strike]
            put = put_by_strike[strike]
            
            call_price = call.get('mark_price') or call.get('mark') or 0
            put_price = put.get('mark_price') or put.get('mark') or 0
            
            if call_price > 0 and put_price > 0:
                # Theoretical: C - P ≈ S - K
                theoretical_diff = spot_price - strike
                actual_diff = call_price - put_price
                deviation = abs(actual_diff - theoretical_diff)
                
                # Allow 5% deviation for illiquid markets
                max_deviation = max(strike * 0.05, 100)  # At least $100 tolerance
                
                if deviation > max_deviation:
                    alerts.append(DataQualityAlert(
                        issue_type=DataQualityIssue.ARBITRAGE_VIOLATION,
                        severity='high',
                        message=f"Put-call parity violation at strike {strike}: deviation ${deviation:.2f}",
                        affected_symbols=[call.get('symbol', ''), put.get('symbol', '')],
                        timestamp=current_time,
                        metadata={
                            'strike': strike,
                            'theoretical_diff': theoretical_diff,
                            'actual_diff': actual_diff,
                            'deviation': deviation,
                            'call_price': call_price,
                            'put_price': put_price
                        }
                    ))
        
        return alerts

    def _check_iv_consistency(self, options: List[Dict]) -> List[DataQualityAlert]:
        """Check for IV outliers across the chain"""
        alerts: List[DataQualityAlert] = []
        current_time = datetime.now()
        
        ivs = [(o.get('mark_iv') or o.get('iv', 0), o.get('symbol', '')) for o in options]
        ivs = [(iv, sym) for iv, sym in ivs if iv and iv > 0]
        
        if len(ivs) < 5:
            return alerts
        
        iv_values = [iv for iv, _ in ivs]
        iv_mean = statistics.mean(iv_values)
        iv_std = statistics.stdev(iv_values)
        
        if iv_std > 0:
            outliers = [(iv, sym) for iv, sym in ivs if abs(iv - iv_mean) / iv_std > self.max_iv_deviation]
            
            if outliers:
                alerts.append(DataQualityAlert(
                    issue_type=DataQualityIssue.INCONSISTENT_IV,
                    severity='medium',
                    message=f"Found {len(outliers)} IV outliers in chain",
                    affected_symbols=[sym for _, sym in outliers],
                    timestamp=current_time,
                    metadata={
                        'iv_mean': iv_mean,
                        'iv_std': iv_std,
                        'outlier_count': len(outliers)
                    }
                ))
        
        return alerts

    def _get_strike(self, option: Dict) -> Optional[float]:
        """Extract strike from option dict or symbol"""
        if 'strike' in option:
            return option['strike']
        
        symbol = option.get('symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 3:
            try:
                return float(parts[2])
            except ValueError:
                pass
        return None

    def calculate_quality_score(self) -> float:
        """
        Calculate overall data quality score (0.0 to 1.0).
        
        Returns:
            Quality score where 1.0 is perfect quality
        """
        if not self.quality_alerts:
            return 1.0
        
        # Get recent alerts (last hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_alerts = [a for a in self.quality_alerts if a.timestamp > cutoff_time]
        
        if not recent_alerts:
            return 1.0
        
        # Calculate penalty based on severity
        penalty = 0.0
        for alert in recent_alerts:
            if alert.severity == 'low':
                penalty += 0.01
            elif alert.severity == 'medium':
                penalty += 0.05
            elif alert.severity == 'high':
                penalty += 0.10
            elif alert.severity == 'critical':
                penalty += 0.25
        
        return max(0.0, 1.0 - penalty)

    def get_quality_summary(self) -> Dict[str, Any]:
        """
        Get summary of data quality status.
        
        Returns:
            Dictionary with quality metrics and alert counts
        """
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_alerts = [a for a in self.quality_alerts if a.timestamp > cutoff_time]
        
        # Count by type
        type_counts: Dict[str, int] = {}
        for issue in DataQualityIssue:
            type_counts[issue.value] = len([a for a in recent_alerts if a.issue_type == issue])
        
        # Count by severity
        severity_counts: Dict[str, int] = {
            'low': len([a for a in recent_alerts if a.severity == 'low']),
            'medium': len([a for a in recent_alerts if a.severity == 'medium']),
            'high': len([a for a in recent_alerts if a.severity == 'high']),
            'critical': len([a for a in recent_alerts if a.severity == 'critical'])
        }
        
        return {
            'quality_score': self.calculate_quality_score(),
            'total_alerts': len(recent_alerts),
            'alerts_by_type': type_counts,
            'alerts_by_severity': severity_counts,
            'thresholds': {
                'max_data_age': self.max_data_age,
                'max_bid_ask_spread': self.max_bid_ask_spread,
                'min_volume_threshold': self.min_volume_threshold,
                'max_iv_deviation': self.max_iv_deviation
            },
            'recent_critical_alerts': [
                a.to_dict() for a in recent_alerts 
                if a.severity == 'critical'
            ][-5:]  # Last 5 critical alerts
        }

    def clear_alerts(self):
        """Clear alert history"""
        self.quality_alerts.clear()
        self.iv_history.clear()
        logger.info("Data validator alerts cleared")


# Global validator instance
data_validator = MarketDataValidator()
