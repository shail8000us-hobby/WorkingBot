"""
Strategy Auto-Entry Logic
=========================
Monitor pending strategies and auto-execute when entry conditions are met.

Entry Conditions:
- IV threshold
- Spot price range
- Time window
- Max cost validation

Created: January 5, 2026
Phase 3: Automation & Monitoring
"""

import sys
import asyncio
import logging
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, time as dt_time
from enum import Enum

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .strategy_models import (
    Strategy, StrategyStatus, EntryConditions
)

log = logging.getLogger(__name__)


class EntryConditionStatus(str, Enum):
    """Status of entry condition check"""
    MET = "met"
    NOT_MET = "not_met"
    SKIPPED = "skipped"
    ERROR = "error"


class ConditionCheckResult:
    """Result of checking entry conditions"""
    
    def __init__(self, condition_name: str):
        self.name = condition_name
        self.status = EntryConditionStatus.SKIPPED
        self.message = ""
        self.current_value = None
        self.threshold = None
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'current_value': self.current_value,
            'threshold': self.threshold
        }


class StrategyAutoEntry:
    """
    Monitor pending strategies and auto-execute when conditions met
    
    Features:
    - Check IV thresholds
    - Validate spot price range
    - Enforce time windows
    - Verify capital availability
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        self._running = False
        self._check_interval = 30  # seconds (entry checks less frequent)
        self._strategy_manager = None
        self._market_data = None
        
        # Track failed entry attempts
        self._entry_attempts: Dict[str, int] = {}
        self._max_attempts = 3
        
        self._initialized = True
        log.info("🎯 StrategyAutoEntry initialized")
    
    @property
    def strategy_manager(self):
        """Lazy load strategy manager"""
        if self._strategy_manager is None:
            from .strategy_manager import StrategyManager
            self._strategy_manager = StrategyManager()
        return self._strategy_manager
    
    # ==================== Lifecycle ====================
    
    def start(self):
        """Start auto-entry monitoring"""
        if self._running:
            log.warning("Auto-entry already running")
            return
        
        self._running = True
        
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._entry_loop())
            except Exception as e:
                log.error(f"Auto-entry loop error: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        
        log.info("✅ Strategy auto-entry started")
    
    def stop(self):
        """Stop auto-entry monitoring"""
        self._running = False
        log.info("⏹️ Strategy auto-entry stopped")
    
    def is_running(self) -> bool:
        return self._running
    
    # ==================== Entry Loop ====================
    
    async def _entry_loop(self):
        """Main auto-entry loop"""
        log.info(f"🔄 Auto-entry loop started (interval: {self._check_interval}s)")
        
        while self._running:
            try:
                await self._check_pending_strategies()
            except Exception as e:
                log.error(f"Auto-entry check error: {e}", exc_info=True)
            
            await asyncio.sleep(self._check_interval)
    
    async def _check_pending_strategies(self):
        """Check all pending strategies for entry"""
        pending = self.strategy_manager.get_pending_strategies()
        
        if not pending:
            return
        
        log.debug(f"Checking {len(pending)} pending strategies for entry")
        
        for strategy in pending:
            try:
                await self._check_strategy_entry(strategy)
            except Exception as e:
                log.error(f"Error checking entry for {strategy.id}: {e}")
    
    async def _check_strategy_entry(self, strategy: Strategy):
        """
        Check if strategy entry conditions are met
        
        If all conditions met, execute the strategy
        """
        # Skip if too many failed attempts
        attempts = self._entry_attempts.get(strategy.id, 0)
        if attempts >= self._max_attempts:
            log.warning(f"Skipping {strategy.id}: max attempts ({self._max_attempts}) reached")
            return
        
        # Check entry conditions
        conditions = strategy.entry_conditions
        if not conditions:
            # No conditions = immediate entry
            log.info(f"No entry conditions for {strategy.name}, executing immediately")
            await self._execute_strategy(strategy)
            return
        
        # Check all conditions
        check_results = await self._check_all_conditions(strategy, conditions)
        
        # Determine if all required conditions are met
        all_met = all(
            r.status in (EntryConditionStatus.MET, EntryConditionStatus.SKIPPED)
            for r in check_results
        )
        
        if all_met:
            log.info(f"✅ Entry conditions met for {strategy.name}")
            await self._execute_strategy(strategy)
        else:
            not_met = [r for r in check_results if r.status == EntryConditionStatus.NOT_MET]
            log.debug(f"Entry conditions not met: {[r.name for r in not_met]}")
    
    async def _check_all_conditions(
        self, 
        strategy: Strategy, 
        conditions: EntryConditions
    ) -> List[ConditionCheckResult]:
        """Check all entry conditions"""
        results = []
        
        # 1. Time Window
        if conditions.time_window_start or conditions.time_window_end:
            results.append(self._check_time_window(conditions))
        
        # 2. IV Threshold
        if conditions.iv_threshold:
            results.append(await self._check_iv_threshold(strategy, conditions))
        
        # 3. Spot Price Range
        if conditions.spot_min is not None or conditions.spot_max is not None:
            results.append(await self._check_spot_range(strategy, conditions))
        
        # 4. Max Cost
        if conditions.max_cost:
            results.append(await self._check_max_cost(strategy, conditions))
        
        # 5. Min Days to Expiry
        if conditions.min_dte:
            results.append(self._check_min_dte(strategy, conditions))
        
        return results
    
    def _check_time_window(self, conditions: EntryConditions) -> ConditionCheckResult:
        """Check if current time is within allowed window"""
        result = ConditionCheckResult("time_window")
        
        now = datetime.now().time()
        
        # Parse time strings (HH:MM format)
        try:
            start_time = None
            end_time = None
            
            if conditions.time_window_start:
                h, m = map(int, conditions.time_window_start.split(':'))
                start_time = dt_time(h, m)
            
            if conditions.time_window_end:
                h, m = map(int, conditions.time_window_end.split(':'))
                end_time = dt_time(h, m)
            
            # Check window
            in_window = True
            
            if start_time and now < start_time:
                in_window = False
            
            if end_time and now > end_time:
                in_window = False
            
            result.status = EntryConditionStatus.MET if in_window else EntryConditionStatus.NOT_MET
            result.current_value = now.strftime('%H:%M')
            result.threshold = f"{conditions.time_window_start or '00:00'} - {conditions.time_window_end or '23:59'}"
            result.message = "Within time window" if in_window else "Outside time window"
            
        except Exception as e:
            result.status = EntryConditionStatus.ERROR
            result.message = f"Error parsing time: {e}"
        
        return result
    
    async def _check_iv_threshold(
        self, 
        strategy: Strategy, 
        conditions: EntryConditions
    ) -> ConditionCheckResult:
        """Check if IV is above threshold"""
        result = ConditionCheckResult("iv_threshold")
        
        try:
            # Get current IV from market data
            current_iv = await self._get_current_iv(strategy.underlying)
            
            if current_iv is None:
                result.status = EntryConditionStatus.SKIPPED
                result.message = "IV data not available"
                return result
            
            threshold = conditions.iv_threshold
            
            if current_iv >= threshold:
                result.status = EntryConditionStatus.MET
                result.message = f"IV {current_iv:.1f}% >= {threshold}%"
            else:
                result.status = EntryConditionStatus.NOT_MET
                result.message = f"IV {current_iv:.1f}% < {threshold}%"
            
            result.current_value = current_iv
            result.threshold = threshold
            
        except Exception as e:
            result.status = EntryConditionStatus.ERROR
            result.message = f"Error checking IV: {e}"
        
        return result
    
    async def _check_spot_range(
        self, 
        strategy: Strategy, 
        conditions: EntryConditions
    ) -> ConditionCheckResult:
        """Check if spot price is in range"""
        result = ConditionCheckResult("spot_range")
        
        try:
            # Get current spot price
            spot = await self._get_current_spot(strategy.underlying)
            
            if spot is None:
                result.status = EntryConditionStatus.SKIPPED
                result.message = "Spot price not available"
                return result
            
            in_range = True
            
            if conditions.spot_min is not None and spot < conditions.spot_min:
                in_range = False
            
            if conditions.spot_max is not None and spot > conditions.spot_max:
                in_range = False
            
            result.status = EntryConditionStatus.MET if in_range else EntryConditionStatus.NOT_MET
            result.current_value = spot
            result.threshold = f"${conditions.spot_min or 0:,.0f} - ${conditions.spot_max or 999999:,.0f}"
            result.message = f"Spot ${spot:,.0f} {'in' if in_range else 'out of'} range"
            
        except Exception as e:
            result.status = EntryConditionStatus.ERROR
            result.message = f"Error checking spot: {e}"
        
        return result
    
    async def _check_max_cost(
        self, 
        strategy: Strategy, 
        conditions: EntryConditions
    ) -> ConditionCheckResult:
        """Check if estimated cost is within budget"""
        result = ConditionCheckResult("max_cost")
        
        try:
            # Calculate estimated cost
            estimated_cost = strategy.estimated_cost or 0
            
            if estimated_cost == 0:
                # Try to recalculate
                estimated_cost = await self._estimate_strategy_cost(strategy)
            
            max_cost = conditions.max_cost
            
            if estimated_cost <= max_cost:
                result.status = EntryConditionStatus.MET
                result.message = f"Cost ${estimated_cost:,.0f} <= ${max_cost:,.0f}"
            else:
                result.status = EntryConditionStatus.NOT_MET
                result.message = f"Cost ${estimated_cost:,.0f} > ${max_cost:,.0f}"
            
            result.current_value = estimated_cost
            result.threshold = max_cost
            
        except Exception as e:
            result.status = EntryConditionStatus.ERROR
            result.message = f"Error checking cost: {e}"
        
        return result
    
    def _check_min_dte(
        self, 
        strategy: Strategy, 
        conditions: EntryConditions
    ) -> ConditionCheckResult:
        """Check minimum days to expiry"""
        result = ConditionCheckResult("min_dte")
        
        try:
            dte = self._calculate_dte(strategy.expiry)
            
            if dte is None:
                result.status = EntryConditionStatus.SKIPPED
                result.message = "Could not calculate DTE"
                return result
            
            min_dte = conditions.min_dte
            
            if dte >= min_dte:
                result.status = EntryConditionStatus.MET
                result.message = f"DTE {dte} >= {min_dte}"
            else:
                result.status = EntryConditionStatus.NOT_MET
                result.message = f"DTE {dte} < {min_dte} (too close to expiry)"
            
            result.current_value = dte
            result.threshold = min_dte
            
        except Exception as e:
            result.status = EntryConditionStatus.ERROR
            result.message = f"Error checking DTE: {e}"
        
        return result
    
    def _calculate_dte(self, expiry: str) -> Optional[int]:
        """Calculate days to expiry"""
        try:
            if len(expiry) == 6:  # YYMMDD
                year = 2000 + int(expiry[:2])
                month = int(expiry[2:4])
                day = int(expiry[4:6])
                expiry_date = datetime(year, month, day)
            elif len(expiry) == 8:  # DDMMYYYY
                day = int(expiry[:2])
                month = int(expiry[2:4])
                year = int(expiry[4:])
                expiry_date = datetime(year, month, day)
            else:
                return None
            
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return max(0, (expiry_date - today).days)
            
        except Exception:
            return None
    
    # ==================== Market Data ====================
    
    async def _get_current_iv(self, underlying: str) -> Optional[float]:
        """Get current implied volatility"""
        try:
            # Try to get from options chain
            from ..options_chain.chain_service import get_options_chain_service
            chain_service = get_options_chain_service()
            
            # Get ATM IV as representative
            chain_data = await chain_service.get_chain_data_async(underlying)
            
            if chain_data and 'atm_iv' in chain_data:
                return chain_data['atm_iv']
            
            # Fallback: calculate from mark prices
            return None
            
        except Exception as e:
            log.warning(f"Could not get IV: {e}")
            return None
    
    async def _get_current_spot(self, underlying: str) -> Optional[float]:
        """Get current spot price"""
        try:
            from bot.api.unified_api_client import UnifiedAPIClient
            from config.loader import get_api_credentials
            
            creds = get_api_credentials()
            client = UnifiedAPIClient(
                api_key=creds['api_key'],
                api_secret=creds['api_secret'],
                symbol=f'{underlying}USD',
                enable_websocket=False
            )
            
            ticker = await client.get_ticker_async()
            if ticker and 'mark_price' in ticker:
                return float(ticker['mark_price'])
            
            return None
            
        except Exception as e:
            log.warning(f"Could not get spot price: {e}")
            return None
    
    async def _estimate_strategy_cost(self, strategy: Strategy) -> float:
        """Estimate total cost of strategy"""
        total_cost = 0.0
        
        try:
            for leg in strategy.legs:
                # Get current price for each leg
                # This is simplified - real implementation would use mid price
                price = leg.current_price or 0
                qty = leg.quantity or 1
                
                if leg.side == 'buy':
                    total_cost += price * qty
                else:
                    total_cost -= price * qty
                    
        except Exception as e:
            log.warning(f"Error estimating cost: {e}")
        
        return abs(total_cost)
    
    # ==================== Execution ====================
    
    async def _execute_strategy(self, strategy: Strategy):
        """Execute strategy after conditions met"""
        log.info(f"🚀 Auto-executing strategy: {strategy.name}")
        
        try:
            result = await self.strategy_manager.execute_strategy(
                strategy_id=strategy.id,
                execution_mode='sequential',
                order_type='limit'
            )
            
            if result.get('success'):
                log.info(f"✅ Strategy {strategy.name} executed successfully")
                # Clear attempt counter
                self._entry_attempts.pop(strategy.id, None)
            else:
                log.error(f"❌ Strategy execution failed: {result.get('error')}")
                # Increment attempt counter
                self._entry_attempts[strategy.id] = self._entry_attempts.get(strategy.id, 0) + 1
                
        except Exception as e:
            log.error(f"❌ Auto-execute error: {e}", exc_info=True)
            self._entry_attempts[strategy.id] = self._entry_attempts.get(strategy.id, 0) + 1
    
    # ==================== Manual Operations ====================
    
    async def check_entry_conditions(self, strategy_id: str) -> Dict:
        """Manually check entry conditions for a strategy"""
        strategy = self.strategy_manager.get_strategy(strategy_id)
        
        if not strategy:
            return {'error': 'Strategy not found'}
        
        conditions = strategy.entry_conditions
        if not conditions:
            return {
                'strategy_id': strategy_id,
                'has_conditions': False,
                'can_enter': True,
                'results': []
            }
        
        results = await self._check_all_conditions(strategy, conditions)
        
        all_met = all(
            r.status in (EntryConditionStatus.MET, EntryConditionStatus.SKIPPED)
            for r in results
        )
        
        return {
            'strategy_id': strategy_id,
            'has_conditions': True,
            'can_enter': all_met,
            'results': [r.to_dict() for r in results]
        }
    
    def get_status(self) -> Dict:
        """Get auto-entry status"""
        return {
            'running': self._running,
            'check_interval': self._check_interval,
            'pending_attempts': dict(self._entry_attempts)
        }


# Global instance
_auto_entry_instance: Optional[StrategyAutoEntry] = None


def get_auto_entry_service() -> StrategyAutoEntry:
    """Get singleton auto-entry instance"""
    global _auto_entry_instance
    if _auto_entry_instance is None:
        _auto_entry_instance = StrategyAutoEntry()
    return _auto_entry_instance


def start_auto_entry():
    """Start auto-entry service"""
    service = get_auto_entry_service()
    service.start()
    return service


def stop_auto_entry():
    """Stop auto-entry service"""
    if _auto_entry_instance:
        _auto_entry_instance.stop()
