"""
Real-time Monitor for Zero DTE Bot
==================================

Provides monitoring utilities and snapshot saving.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
import pytz

from config.schemas.zero_dte_schemas import ZeroDTEConfig


IST = pytz.timezone('Asia/Kolkata')


class ZeroDTEMonitor:
    """
    Real-time monitoring for 0DTE sessions
    
    Features:
    - Premium tracking
    - Greeks monitoring
    - Snapshot persistence
    - Alert generation
    """
    
    def __init__(self, api_client, config: ZeroDTEConfig, state_manager):
        self.api_client = api_client
        self.config = config
        self.state_manager = state_manager
    
    async def get_current_data(self, session_id: str) -> Dict:
        """Get comprehensive current data for session"""
        session = self.state_manager.get_session(session_id)
        if not session:
            return {}
        
        positions = self.state_manager.get_positions(session_id)
        underlying = session['underlying']
        
        # Get spot price
        spot_price = await self._get_spot_price(underlying)
        
        # Get position data
        ce_data = {}
        pe_data = {}
        
        if 'CE' in positions:
            ce_data = await self._get_position_data(positions['CE']['symbol'])
        if 'PE' in positions:
            pe_data = await self._get_position_data(positions['PE']['symbol'])
        
        # Calculate metrics
        ce_premium = ce_data.get('mark_price', 0)
        pe_premium = pe_data.get('mark_price', 0)
        ce_lots = positions.get('CE', {}).get('lots', 0)
        pe_lots = positions.get('PE', {}).get('lots', 0)
        
        ce_total = ce_premium * ce_lots
        pe_total = pe_premium * pe_lots
        avg_total = (ce_total + pe_total) / 2 if (ce_total + pe_total) > 0 else 1
        imbalance_pct = abs(ce_total - pe_total) / avg_total * 100
        
        # Calculate P&L
        total_collected = session.get('total_premium_collected', 0)
        total_paid = session.get('total_premium_paid', 0)
        current_value = ce_total + pe_total
        unrealized_pnl = total_collected - current_value - total_paid
        
        # Greeks
        ce_greeks = ce_data.get('greeks', {})
        pe_greeks = pe_data.get('greeks', {})
        
        portfolio_delta = (ce_greeks.get('delta', 0) * ce_lots + 
                         pe_greeks.get('delta', 0) * pe_lots)
        portfolio_gamma = (ce_greeks.get('gamma', 0) * ce_lots + 
                         pe_greeks.get('gamma', 0) * pe_lots)
        portfolio_theta = (ce_greeks.get('theta', 0) * ce_lots + 
                         pe_greeks.get('theta', 0) * pe_lots)
        portfolio_vega = (ce_greeks.get('vega', 0) * ce_lots + 
                        pe_greeks.get('vega', 0) * pe_lots)
        
        # Time to expiry
        now_ist = datetime.now(IST)
        settlement_time = self._parse_time(self.config.exit.settlement_time)
        settlement_dt = datetime.combine(now_ist.date(), settlement_time)
        settlement_dt = IST.localize(settlement_dt)
        time_to_expiry = max(0, int((settlement_dt - now_ist).total_seconds() / 60))
        
        return {
            'session_id': session_id,
            'underlying': underlying,
            'spot_price': spot_price,
            'positions': {
                'CE': {
                    'symbol': positions.get('CE', {}).get('symbol'),
                    'strike': positions.get('CE', {}).get('strike'),
                    'lots': ce_lots,
                    'entry_premium': positions.get('CE', {}).get('entry_premium'),
                    'current_premium': ce_premium,
                    'total_value': ce_total,
                    'greeks': ce_greeks
                },
                'PE': {
                    'symbol': positions.get('PE', {}).get('symbol'),
                    'strike': positions.get('PE', {}).get('strike'),
                    'lots': pe_lots,
                    'entry_premium': positions.get('PE', {}).get('entry_premium'),
                    'current_premium': pe_premium,
                    'total_value': pe_total,
                    'greeks': pe_greeks
                }
            },
            'premium_balance': {
                'ce_total': ce_total,
                'pe_total': pe_total,
                'imbalance_pct': imbalance_pct,
                'is_balanced': imbalance_pct < self.config.rebalancing.imbalance_threshold_pct
            },
            'pnl': {
                'total_collected': total_collected,
                'total_paid': total_paid,
                'unrealized': unrealized_pnl,
                'realized': session.get('realized_pnl', 0)
            },
            'greeks': {
                'portfolio_delta': portfolio_delta,
                'portfolio_gamma': portfolio_gamma,
                'portfolio_theta': portfolio_theta,
                'portfolio_vega': portfolio_vega
            },
            'time': {
                'current_ist': now_ist.isoformat(),
                'time_to_expiry_minutes': time_to_expiry,
                'settlement_time': self.config.exit.settlement_time
            },
            'stats': {
                'total_rebalances': session.get('total_rebalances', 0),
                'total_rollovers': session.get('total_rollovers', 0)
            }
        }
    
    async def check_greeks_limits(self, greeks: Dict) -> Dict:
        """Check if Greeks are within limits"""
        limits = self.config.monitoring.greeks_limits
        
        violations = []
        
        if abs(greeks.get('portfolio_delta', 0)) > limits.max_delta:
            violations.append(f"Delta {greeks['portfolio_delta']:.3f} exceeds limit ±{limits.max_delta}")
        
        if abs(greeks.get('portfolio_gamma', 0)) > limits.max_gamma:
            violations.append(f"Gamma {greeks['portfolio_gamma']:.4f} exceeds limit {limits.max_gamma}")
        
        if abs(greeks.get('portfolio_vega', 0)) > limits.max_vega:
            violations.append(f"Vega {greeks['portfolio_vega']:.2f} exceeds limit {limits.max_vega}")
        
        return {
            'within_limits': len(violations) == 0,
            'violations': violations
        }
    
    async def _get_spot_price(self, underlying: str) -> float:
        """Get current spot price"""
        try:
            return await self.api_client.get_current_price(underlying)
        except Exception as e:
            logger.warning(f"Failed to get spot price: {e}")
            return 0
    
    async def _get_position_data(self, symbol: str) -> Dict:
        """Get current data for a position"""
        try:
            return await self.api_client.get_option_ticker(symbol)
        except Exception as e:
            logger.warning(f"Failed to get ticker for {symbol}: {e}")
            return {}
    
    def _parse_time(self, time_str: str):
        """Parse time string"""
        from datetime import time
        parts = time_str.split(':')
        return time(int(parts[0]), int(parts[1]))
