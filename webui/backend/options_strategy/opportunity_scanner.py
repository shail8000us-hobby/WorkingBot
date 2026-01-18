"""
Opportunity Scanner - Phase 3 of ML Autonomous Trading Engine

Continuously scans markets for opportunities that match the trader's style.
Scores each option based on how well it matches historical preferences.

Created: January 18, 2026
"""

import asyncio
import aiohttp
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import math

# Import style profiler
try:
    from .style_profiler import style_profiler, TradingStyleDNA
except ImportError:
    from style_profiler import style_profiler, TradingStyleDNA


@dataclass
class TradingOpportunity:
    """Represents a trading opportunity found by the scanner"""
    
    # Option details
    symbol: str = ""
    option_type: str = ""  # "call" or "put"
    strike: float = 0.0
    expiry: str = ""
    
    # Pricing
    bid: float = 0.0
    ask: float = 0.0
    mid_price: float = 0.0
    iv: float = 0.0
    
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # Scoring
    score: float = 0.0  # 0-1, how well it matches style
    confidence: float = 0.0
    
    # Analysis
    reasoning: List[str] = field(default_factory=list)
    risk_reward: float = 0.0
    expected_win_rate: float = 0.0
    max_loss: float = 0.0
    max_gain: float = 0.0
    
    # Similar trades
    similar_past_trades: List[Dict] = field(default_factory=list)
    
    # Metadata
    scanned_at: str = ""
    spot_price: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class TradingSignal:
    """A trading signal generated from an opportunity"""
    
    # Action
    signal_id: str = ""
    symbol: str = ""
    action: str = ""  # "BUY" or "SELL"
    option_type: str = ""
    strike: float = 0.0
    expiry: str = ""
    
    # Sizing
    quantity: int = 1
    entry_price: float = 0.0
    
    # Risk management
    stop_loss: float = 0.0
    take_profit: float = 0.0
    max_loss: float = 0.0
    
    # Confidence
    confidence: float = 0.0
    reasoning: List[str] = field(default_factory=list)
    
    # Expected outcome
    expected_win_rate: float = 0.0
    expected_return: float = 0.0
    risk_reward: float = 0.0
    time_horizon_hours: float = 0.0
    
    # Status
    status: str = "pending"  # pending, executed, expired, rejected
    created_at: str = ""
    expires_at: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class OpportunityScanner:
    """
    Scans options chain for opportunities matching trader's style.
    
    Features:
    - Multi-factor scoring based on style profile
    - IV percentile analysis
    - Risk/reward calculation
    - Similar trade matching
    - Real-time opportunity ranking
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.signals_file = self.data_dir / 'active_signals.json'
        self.opportunities_file = self.data_dir / 'recent_opportunities.json'
        
        # Scoring weights (can be adjusted based on style)
        self.default_weights = {
            'iv_match': 0.20,
            'timing_match': 0.15,
            'type_match': 0.15,
            'risk_reward': 0.25,
            'momentum': 0.15,
            'liquidity': 0.10
        }
        
        # Cache
        self._cached_opportunities: List[TradingOpportunity] = []
        self._last_scan_time: Optional[datetime] = None
    
    async def scan_options_chain(self, symbol: str = "BTC") -> List[TradingOpportunity]:
        """
        Scan options chain and score each option.
        
        Args:
            symbol: Base symbol to scan (BTC, ETH)
            
        Returns:
            List of opportunities sorted by score
        """
        # Get trader's style profile
        style = style_profiler.get_cached_profile()
        if not style:
            style = style_profiler.analyze_trading_style()
        
        # Fetch options chain data
        chain_data = await self._fetch_options_chain(symbol)
        if not chain_data:
            return []
        
        opportunities = []
        spot_price = chain_data.get('spot_price', 0)
        
        for option in chain_data.get('options', []):
            # Score this option
            score, reasoning = self._score_opportunity(option, style, spot_price)
            
            if score >= 0.3:  # Minimum threshold
                opp = TradingOpportunity(
                    symbol=option.get('symbol', ''),
                    option_type=option.get('contract_type', '').lower(),
                    strike=float(option.get('strike_price', 0)),
                    expiry=option.get('expiry', ''),
                    bid=float(option.get('best_bid', 0)),
                    ask=float(option.get('best_ask', 0)),
                    mid_price=(float(option.get('best_bid', 0)) + float(option.get('best_ask', 0))) / 2,
                    iv=float(option.get('iv', 0)) if option.get('iv') else 0,
                    delta=float(option.get('delta', 0)) if option.get('delta') else 0,
                    gamma=float(option.get('gamma', 0)) if option.get('gamma') else 0,
                    theta=float(option.get('theta', 0)) if option.get('theta') else 0,
                    vega=float(option.get('vega', 0)) if option.get('vega') else 0,
                    score=score,
                    confidence=min(score, style.confidence) if style else score,
                    reasoning=reasoning,
                    risk_reward=self._calculate_risk_reward(option, spot_price),
                    expected_win_rate=self._estimate_win_rate(option, style),
                    max_loss=float(option.get('best_ask', 0)),
                    max_gain=self._estimate_max_gain(option, spot_price),
                    scanned_at=datetime.now().isoformat(),
                    spot_price=spot_price
                )
                opportunities.append(opp)
        
        # Sort by score
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        # Cache results
        self._cached_opportunities = opportunities[:20]  # Keep top 20
        self._last_scan_time = datetime.now()
        self._save_opportunities(opportunities[:20])
        
        return opportunities
    
    def _score_opportunity(
        self, 
        option: Dict, 
        style: Optional[TradingStyleDNA],
        spot_price: float
    ) -> Tuple[float, List[str]]:
        """
        Score an option based on style match.
        
        Returns:
            Tuple of (score 0-1, list of reasoning strings)
        """
        scores = {}
        reasoning = []
        
        # 1. IV Match (20%)
        iv = float(option.get('iv', 30)) if option.get('iv') else 30
        if style:
            if style.volatility_preference == "high" and iv > 50:
                scores['iv_match'] = 1.0
                reasoning.append(f"High IV ({iv:.0f}%) matches your preference")
            elif style.volatility_preference == "low" and iv < 30:
                scores['iv_match'] = 1.0
                reasoning.append(f"Low IV ({iv:.0f}%) matches your preference")
            elif style.volatility_preference == "medium" and 30 <= iv <= 50:
                scores['iv_match'] = 1.0
                reasoning.append(f"Medium IV ({iv:.0f}%) matches your preference")
            else:
                scores['iv_match'] = 0.4
        else:
            scores['iv_match'] = 0.5
        
        # 2. Timing Match (15%)
        current_hour = datetime.now().hour
        if style and style.preferred_entry_hours:
            if current_hour in style.preferred_entry_hours:
                scores['timing_match'] = 1.0
                reasoning.append(f"Current hour ({current_hour}:00) is your preferred trading time")
            else:
                scores['timing_match'] = 0.3
        else:
            scores['timing_match'] = 0.5
        
        # 3. Option Type Match (15%)
        option_type = option.get('contract_type', '').lower()
        if style:
            if option_type == 'call' and style.call_preference > 0.6:
                scores['type_match'] = 1.0
                reasoning.append("Call option matches your bullish preference")
            elif option_type == 'put' and style.call_preference < 0.4:
                scores['type_match'] = 1.0
                reasoning.append("Put option matches your bearish preference")
            elif 0.4 <= style.call_preference <= 0.6:
                scores['type_match'] = 0.8
                reasoning.append("Balanced style - both calls and puts work")
            else:
                scores['type_match'] = 0.4
        else:
            scores['type_match'] = 0.5
        
        # 4. Risk/Reward (25%)
        strike = float(option.get('strike_price', 0))
        ask = float(option.get('best_ask', 0))
        if spot_price > 0 and ask > 0:
            if option_type == 'call':
                potential_gain = max(0, spot_price * 1.05 - strike) - ask
            else:
                potential_gain = max(0, strike - spot_price * 0.95) - ask
            
            risk_reward = potential_gain / ask if ask > 0 else 0
            
            if risk_reward >= 2:
                scores['risk_reward'] = 1.0
                reasoning.append(f"Excellent risk/reward ratio: {risk_reward:.1f}:1")
            elif risk_reward >= 1:
                scores['risk_reward'] = 0.7
                reasoning.append(f"Good risk/reward ratio: {risk_reward:.1f}:1")
            else:
                scores['risk_reward'] = 0.3
        else:
            scores['risk_reward'] = 0.5
        
        # 5. Momentum alignment (15%)
        # Simple heuristic based on option type and market direction
        delta = float(option.get('delta', 0)) if option.get('delta') else 0
        if abs(delta) >= 0.3 and abs(delta) <= 0.7:
            scores['momentum'] = 0.8
            reasoning.append(f"Delta ({delta:.2f}) in optimal range for directional trades")
        else:
            scores['momentum'] = 0.5
        
        # 6. Liquidity (10%)
        bid = float(option.get('best_bid', 0))
        ask = float(option.get('best_ask', 0))
        if bid > 0 and ask > 0:
            spread_pct = (ask - bid) / ask * 100
            if spread_pct < 5:
                scores['liquidity'] = 1.0
                reasoning.append("Tight spread indicates good liquidity")
            elif spread_pct < 15:
                scores['liquidity'] = 0.6
            else:
                scores['liquidity'] = 0.2
                reasoning.append("Wide spread - consider limit orders")
        else:
            scores['liquidity'] = 0.3
        
        # Calculate weighted score
        total_score = sum(
            scores.get(k, 0.5) * self.default_weights.get(k, 0.1)
            for k in self.default_weights
        )
        
        return total_score, reasoning
    
    def _calculate_risk_reward(self, option: Dict, spot_price: float) -> float:
        """Calculate risk/reward ratio for an option"""
        ask = float(option.get('best_ask', 0))
        strike = float(option.get('strike_price', 0))
        option_type = option.get('contract_type', '').lower()
        
        if ask <= 0:
            return 0
        
        # Assume 5% move in favorable direction
        if option_type == 'call':
            potential_gain = max(0, spot_price * 1.05 - strike) - ask
        else:
            potential_gain = max(0, strike - spot_price * 0.95) - ask
        
        return potential_gain / ask if ask > 0 else 0
    
    def _estimate_win_rate(self, option: Dict, style: Optional[TradingStyleDNA]) -> float:
        """Estimate win probability based on option characteristics"""
        # Base win rate from style
        if style and style.win_rate > 0:
            base_rate = style.win_rate
        else:
            base_rate = 0.45
        
        # Adjust based on delta (closer to 0.5 delta = more balanced probability)
        delta = abs(float(option.get('delta', 0.5)) if option.get('delta') else 0.5)
        delta_adjustment = 1 - abs(delta - 0.5)  # Peaks at 0.5 delta
        
        return min(0.8, base_rate * (0.8 + 0.4 * delta_adjustment))
    
    def _estimate_max_gain(self, option: Dict, spot_price: float) -> float:
        """Estimate maximum gain potential"""
        strike = float(option.get('strike_price', 0))
        ask = float(option.get('best_ask', 0))
        option_type = option.get('contract_type', '').lower()
        
        # Assume 10% favorable move for max gain estimate
        if option_type == 'call':
            return max(0, spot_price * 1.10 - strike - ask)
        else:
            return max(0, strike - spot_price * 0.90 - ask)
    
    async def _fetch_options_chain(self, symbol: str) -> Dict:
        """Fetch options chain from Delta Exchange API"""
        try:
            # Use the existing options chain endpoint
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:5555/api/options-chain?symbol={symbol}"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            return {
                                'spot_price': data.get('spotPrice', 0),
                                'options': data.get('options', [])
                            }
        except Exception as e:
            print(f"Error fetching options chain: {e}")
        
        return {}
    
    def _save_opportunities(self, opportunities: List[TradingOpportunity]):
        """Save opportunities to file"""
        try:
            with open(self.opportunities_file, 'w') as f:
                json.dump([o.to_dict() for o in opportunities], f, indent=2)
        except Exception as e:
            print(f"Error saving opportunities: {e}")
    
    def get_cached_opportunities(self) -> List[TradingOpportunity]:
        """Get cached opportunities"""
        if self._cached_opportunities:
            return self._cached_opportunities
        
        # Try loading from file
        if self.opportunities_file.exists():
            try:
                with open(self.opportunities_file) as f:
                    data = json.load(f)
                return [TradingOpportunity(**o) for o in data]
            except Exception:
                pass
        
        return []
    
    def generate_signals(
        self, 
        opportunities: List[TradingOpportunity],
        max_signals: int = 5,
        min_score: float = 0.6
    ) -> List[TradingSignal]:
        """
        Generate trading signals from opportunities.
        
        Args:
            opportunities: List of scanned opportunities
            max_signals: Maximum signals to generate
            min_score: Minimum score threshold
            
        Returns:
            List of trading signals
        """
        style = style_profiler.get_cached_profile()
        signals = []
        
        for opp in opportunities[:max_signals]:
            if opp.score < min_score:
                continue
            
            # Determine action
            action = "BUY"  # For now, only buy signals
            if style and style.buy_preference < 0.3:
                action = "SELL"
            
            # Calculate position size
            quantity = 1
            if style and style.avg_position_size > 0:
                quantity = max(1, int(style.avg_position_size))
            
            # Calculate stop loss and take profit
            stop_loss = opp.ask * 0.5  # 50% stop loss
            take_profit = opp.ask * 2.0  # 2x take profit
            
            signal = TradingSignal(
                signal_id=f"SIG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(signals)}",
                symbol=opp.symbol,
                action=action,
                option_type=opp.option_type,
                strike=opp.strike,
                expiry=opp.expiry,
                quantity=quantity,
                entry_price=opp.ask,
                stop_loss=stop_loss,
                take_profit=take_profit,
                max_loss=opp.ask * quantity,
                confidence=opp.confidence,
                reasoning=opp.reasoning,
                expected_win_rate=opp.expected_win_rate,
                expected_return=opp.risk_reward * opp.expected_win_rate,
                risk_reward=opp.risk_reward,
                time_horizon_hours=style.avg_hold_duration_hours if style else 24,
                status="pending",
                created_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
            )
            signals.append(signal)
        
        # Save signals
        self._save_signals(signals)
        
        return signals
    
    def _save_signals(self, signals: List[TradingSignal]):
        """Save signals to file"""
        try:
            existing = []
            if self.signals_file.exists():
                with open(self.signals_file) as f:
                    existing = json.load(f)
            
            # Add new signals
            for sig in signals:
                existing.append(sig.to_dict())
            
            # Keep only last 50
            existing = existing[-50:]
            
            with open(self.signals_file, 'w') as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            print(f"Error saving signals: {e}")
    
    def get_active_signals(self) -> List[TradingSignal]:
        """Get active (pending) signals"""
        if not self.signals_file.exists():
            return []
        
        try:
            with open(self.signals_file) as f:
                data = json.load(f)
            
            signals = []
            now = datetime.now()
            
            for s in data:
                sig = TradingSignal(**s)
                # Check if still valid
                if sig.status == "pending":
                    expires = datetime.fromisoformat(sig.expires_at) if sig.expires_at else now + timedelta(hours=1)
                    if expires > now:
                        signals.append(sig)
            
            return signals
        except Exception:
            return []
    
    def get_scanner_status(self) -> Dict:
        """Get current scanner status"""
        return {
            'last_scan': self._last_scan_time.isoformat() if self._last_scan_time else None,
            'opportunities_count': len(self._cached_opportunities),
            'top_score': self._cached_opportunities[0].score if self._cached_opportunities else 0,
            'active_signals': len(self.get_active_signals()),
            'is_scanning': False
        }


# Singleton instance
opportunity_scanner = OpportunityScanner()
