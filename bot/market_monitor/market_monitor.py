"""
Market Monitor Service - Phase 3
Tracks market conditions for auto LONG/SHORT mode switching

Features:
- Real-time price tracking
- Reference price management
- Volatility monitoring
- Trend detection
- Market regime classification
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Current market state snapshot"""
    timestamp: str
    current_price: float
    reference_price: float
    volatility: float
    trend: str  # 'bullish', 'bearish', 'neutral'
    regime: str  # 'low_vol', 'medium_vol', 'high_vol'
    rsi: Optional[float] = None
    volume_24h: Optional[float] = None


@dataclass
class PriceLevel:
    """Price level with metadata"""
    price: float
    timestamp: str
    volume: float = 0.0
    source: str = "exchange"


class MarketMonitor:
    """
    Monitors market conditions and provides signals for mode switching
    
    Features:
    - Real-time price tracking from exchange
    - Reference price calculation (VWAP, SMA, manual)
    - Volatility regime detection
    - Trend analysis
    - Market state persistence
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.symbol = config.get('symbol', 'BTCUSD')
        self.update_interval = config.get('update_interval', 5)  # seconds
        
        # Price tracking
        self.current_price: Optional[float] = None
        self.reference_price: Optional[float] = None
        self.price_history: List[PriceLevel] = []
        self.max_history = 1000  # Keep last 1000 prices
        
        # Volatility tracking
        self.volatility_window = 20  # periods
        self.current_volatility: Optional[float] = None
        
        # Trend analysis
        self.trend_window = 50  # periods
        self.current_trend = "neutral"
        
        # State persistence
        self.state_file = Path("data/market_monitor_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Running flag
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info(f"MarketMonitor initialized for {self.symbol}")
    
    async def start(self):
        """Start monitoring market"""
        if self._running:
            logger.warning("MarketMonitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("MarketMonitor started")
    
    async def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Save state before stopping
        self._save_state()
        logger.info("MarketMonitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        # Load previous state
        self._load_state()
        
        while self._running:
            try:
                # Fetch current price
                await self._update_price()
                
                # Calculate reference price
                self._update_reference_price()
                
                # Calculate volatility
                self._calculate_volatility()
                
                # Detect trend
                self._detect_trend()
                
                # Classify regime
                self._classify_regime()
                
                # Save state periodically
                self._save_state()
                
                # Wait before next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in market monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)
    
    async def _update_price(self):
        """Fetch current price from exchange"""
        # TODO: Integrate with actual exchange API
        # For now, use dummy price or read from shared state
        
        # Attempt to read from bot's market data
        try:
            market_data_file = Path("data/monitoring_snapshot.json")
            if market_data_file.exists():
                with open(market_data_file) as f:
                    data = json.load(f)
                    price = data.get('current_price')
                    if price:
                        self.current_price = float(price)
                        
                        # Add to history
                        price_level = PriceLevel(
                            price=self.current_price,
                            timestamp=datetime.now().isoformat(),
                            source="bot_snapshot"
                        )
                        self.price_history.append(price_level)
                        
                        # Trim history
                        if len(self.price_history) > self.max_history:
                            self.price_history = self.price_history[-self.max_history:]
                        
                        logger.debug(f"Price updated: ${self.current_price:,.2f}")
        except Exception as e:
            logger.error(f"Failed to update price: {e}")
    
    def _update_reference_price(self):
        """Calculate reference price (VWAP, SMA, or manual)"""
        method = self.config.get('reference_price_method', 'sma')
        
        if method == 'manual':
            # Use manually set reference price
            self.reference_price = self.config.get('manual_reference_price')
        
        elif method == 'sma':
            # Simple Moving Average
            if len(self.price_history) >= 20:
                recent_prices = [p.price for p in self.price_history[-20:]]
                self.reference_price = sum(recent_prices) / len(recent_prices)
        
        elif method == 'vwap':
            # Volume Weighted Average Price
            if len(self.price_history) >= 20:
                recent = self.price_history[-20:]
                total_volume = sum(p.volume for p in recent)
                if total_volume > 0:
                    vwap = sum(p.price * p.volume for p in recent) / total_volume
                    self.reference_price = vwap
                else:
                    # Fallback to SMA if no volume data
                    self.reference_price = sum(p.price for p in recent) / len(recent)
        
        # If no reference price calculated, use current price
        if self.reference_price is None and self.current_price:
            self.reference_price = self.current_price
    
    def _calculate_volatility(self):
        """Calculate price volatility (standard deviation)"""
        if len(self.price_history) < self.volatility_window:
            return
        
        recent_prices = [p.price for p in self.price_history[-self.volatility_window:]]
        
        # Calculate standard deviation
        mean = sum(recent_prices) / len(recent_prices)
        variance = sum((p - mean) ** 2 for p in recent_prices) / len(recent_prices)
        std_dev = variance ** 0.5
        
        # Volatility as percentage of mean
        self.current_volatility = (std_dev / mean) * 100 if mean > 0 else 0
        
        logger.debug(f"Volatility: {self.current_volatility:.2f}%")
    
    def _detect_trend(self):
        """Detect market trend (bullish, bearish, neutral)"""
        if len(self.price_history) < self.trend_window:
            self.current_trend = "neutral"
            return
        
        recent = self.price_history[-self.trend_window:]
        first_half = [p.price for p in recent[:self.trend_window // 2]]
        second_half = [p.price for p in recent[self.trend_window // 2:]]
        
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        # Determine trend
        change_pct = ((avg_second - avg_first) / avg_first) * 100
        
        if change_pct > 1.0:  # More than 1% increase
            self.current_trend = "bullish"
        elif change_pct < -1.0:  # More than 1% decrease
            self.current_trend = "bearish"
        else:
            self.current_trend = "neutral"
        
        logger.debug(f"Trend: {self.current_trend} (change: {change_pct:.2f}%)")
    
    def _classify_regime(self):
        """Classify volatility regime"""
        if self.current_volatility is None:
            return "unknown"
        
        # Volatility thresholds (can be configured)
        low_threshold = self.config.get('low_vol_threshold', 1.0)
        high_threshold = self.config.get('high_vol_threshold', 3.0)
        
        if self.current_volatility < low_threshold:
            return "low_vol"
        elif self.current_volatility > high_threshold:
            return "high_vol"
        else:
            return "medium_vol"
    
    def get_snapshot(self) -> MarketSnapshot:
        """Get current market snapshot"""
        return MarketSnapshot(
            timestamp=datetime.now().isoformat(),
            current_price=self.current_price or 0.0,
            reference_price=self.reference_price or 0.0,
            volatility=self.current_volatility or 0.0,
            trend=self.current_trend,
            regime=self._classify_regime()
        )
    
    def get_state(self) -> Dict:
        """Get current state as dict"""
        snapshot = self.get_snapshot()
        return {
            **asdict(snapshot),
            'price_history_count': len(self.price_history),
            'last_update': datetime.now().isoformat(),
            'monitoring': self._running
        }
    
    def set_reference_price(self, price: float, method: str = 'manual'):
        """Manually set reference price"""
        self.reference_price = price
        self.config['reference_price_method'] = method
        self.config['manual_reference_price'] = price
        logger.info(f"Reference price manually set to ${price:,.2f}")
    
    def _save_state(self):
        """Save current state to file"""
        try:
            state = {
                'current_price': self.current_price,
                'reference_price': self.reference_price,
                'volatility': self.current_volatility,
                'trend': self.current_trend,
                'price_history': [
                    {
                        'price': p.price,
                        'timestamp': p.timestamp,
                        'volume': p.volume
                    }
                    for p in self.price_history[-100:]  # Save last 100 only
                ],
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save market monitor state: {e}")
    
    def _load_state(self):
        """Load previous state from file"""
        try:
            if not self.state_file.exists():
                logger.info("No previous market monitor state found")
                return
            
            with open(self.state_file) as f:
                state = json.load(f)
            
            self.current_price = state.get('current_price')
            self.reference_price = state.get('reference_price')
            self.current_volatility = state.get('volatility')
            self.current_trend = state.get('trend', 'neutral')
            
            # Restore price history
            history_data = state.get('price_history', [])
            self.price_history = [
                PriceLevel(
                    price=p['price'],
                    timestamp=p['timestamp'],
                    volume=p.get('volume', 0.0)
                )
                for p in history_data
            ]
            
            logger.info(f"Market monitor state loaded ({len(self.price_history)} prices)")
            
        except Exception as e:
            logger.error(f"Failed to load market monitor state: {e}")


# Global instance
_market_monitor: Optional[MarketMonitor] = None


def get_market_monitor(config: Optional[Dict] = None) -> MarketMonitor:
    """Get or create global market monitor instance"""
    global _market_monitor
    
    if _market_monitor is None:
        if config is None:
            config = {
                'symbol': 'BTCUSD',
                'update_interval': 5,
                'reference_price_method': 'sma'
            }
        _market_monitor = MarketMonitor(config)
    
    return _market_monitor


async def start_market_monitor(config: Optional[Dict] = None):
    """Start the global market monitor"""
    monitor = get_market_monitor(config)
    await monitor.start()
    return monitor


async def stop_market_monitor():
    """Stop the global market monitor"""
    global _market_monitor
    if _market_monitor:
        await _market_monitor.stop()
