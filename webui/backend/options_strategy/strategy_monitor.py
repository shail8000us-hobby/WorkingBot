"""
Strategy Monitor Service
========================
Background service to monitor active strategies and trigger auto-exits.

Features:
- Monitor strategy P&L in real-time
- Check exit conditions (profit target, stop loss, DTE)
- Auto-close strategies when conditions met
- WebSocket updates for live P&L
- Notification on strategy events

Created: January 5, 2026
Phase 3: Automation & Monitoring
"""

import sys
import asyncio
import logging
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .strategy_models import (
    Strategy, StrategyStatus, ExitConditions
)

log = logging.getLogger(__name__)


class ExitReason(str, Enum):
    """Reasons for strategy exit"""
    PROFIT_TARGET = "profit_target_reached"
    STOP_LOSS = "stop_loss_triggered"
    DTE_EXIT = "days_to_expiry_exit"
    TIME_DECAY = "theta_decay_threshold"
    MANUAL = "manual_close"
    EXPIRED = "options_expired"
    ERROR = "monitoring_error"


class StrategyEvent(str, Enum):
    """Strategy lifecycle events"""
    CREATED = "strategy_created"
    EXECUTED = "strategy_executed"
    UPDATED = "pnl_updated"
    EXIT_WARNING = "exit_condition_warning"
    CLOSED = "strategy_closed"
    ERROR = "strategy_error"


class StrategyMonitor:
    """
    Background service to monitor active strategies
    
    Monitors:
    - P&L changes
    - Exit conditions
    - Days to expiry
    - Greeks thresholds
    
    Triggers:
    - Auto-close on conditions met
    - Notifications on events
    - WebSocket updates
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
        self._monitor_task: Optional[asyncio.Task] = None
        self._check_interval = 10  # seconds
        self._event_callbacks: List[Callable] = []
        self._last_pnl: Dict[str, float] = {}  # Track P&L changes
        self._warning_sent: Dict[str, Dict] = {}  # Track warnings
        
        # Import dependencies lazily
        self._strategy_manager = None
        self._notification_service = None
        
        self._initialized = True
        log.info("📡 StrategyMonitor initialized")
    
    @property
    def strategy_manager(self):
        """Lazy load strategy manager"""
        if self._strategy_manager is None:
            from .strategy_manager import StrategyManager
            self._strategy_manager = StrategyManager()
        return self._strategy_manager
    
    @property 
    def notification_service(self):
        """Lazy load notification service"""
        if self._notification_service is None:
            try:
                from ..utils.notifications import NotificationService
                self._notification_service = NotificationService()
            except ImportError:
                log.warning("NotificationService not available")
                self._notification_service = None
        return self._notification_service
    
    # ==================== Lifecycle ====================
    
    def start(self):
        """Start background monitoring"""
        if self._running:
            log.warning("Monitor already running")
            return
        
        self._running = True
        
        # Start in background thread with event loop
        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._monitor_loop())
            except Exception as e:
                log.error(f"Monitor loop error: {e}")
        
        thread = threading.Thread(target=run_monitor, daemon=True)
        thread.start()
        
        log.info("✅ Strategy monitor started")
    
    def stop(self):
        """Stop background monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        log.info("⏹️ Strategy monitor stopped")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._running
    
    # ==================== Event Callbacks ====================
    
    def register_callback(self, callback: Callable):
        """Register callback for strategy events"""
        if callback not in self._event_callbacks:
            self._event_callbacks.append(callback)
            log.debug(f"Registered event callback: {callback.__name__}")
    
    def unregister_callback(self, callback: Callable):
        """Unregister event callback"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    def _emit_event(self, event: StrategyEvent, strategy_id: str, data: Dict = None):
        """Emit event to all registered callbacks"""
        event_data = {
            'event': event.value,
            'strategy_id': strategy_id,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        
        for callback in self._event_callbacks:
            try:
                callback(event_data)
            except Exception as e:
                log.error(f"Event callback error: {e}")
    
    # ==================== Monitoring Loop ====================
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        log.info(f"🔄 Monitor loop started (interval: {self._check_interval}s)")
        
        while self._running:
            try:
                await self._check_all_strategies()
            except Exception as e:
                log.error(f"Monitor check error: {e}", exc_info=True)
            
            await asyncio.sleep(self._check_interval)
    
    async def _check_all_strategies(self):
        """Check all active strategies"""
        active_strategies = self.strategy_manager.get_active_strategies()
        
        if not active_strategies:
            return
        
        for strategy in active_strategies:
            try:
                await self._check_strategy(strategy)
            except Exception as e:
                log.error(f"Error checking strategy {strategy.id}: {e}")
                self._emit_event(
                    StrategyEvent.ERROR, 
                    strategy.id,
                    {'error': str(e)}
                )
    
    async def _check_strategy(self, strategy: Strategy):
        """
        Check single strategy for exit conditions
        
        Checks:
        1. Profit target
        2. Stop loss
        3. Days to expiry
        4. Theta decay (optional)
        """
        # Update P&L first
        try:
            pnl_result = await self.strategy_manager.calculate_strategy_pnl(strategy.id)
            current_pnl_pct = pnl_result.get('pnl_percent', 0)
            current_pnl = pnl_result.get('total_pnl', 0)
            
            # Emit update if P&L changed significantly
            last_pnl = self._last_pnl.get(strategy.id, 0)
            if abs(current_pnl - last_pnl) > 10:  # $10 threshold
                self._emit_event(
                    StrategyEvent.UPDATED,
                    strategy.id,
                    {
                        'pnl': current_pnl,
                        'pnl_pct': current_pnl_pct,
                        'previous_pnl': last_pnl
                    }
                )
                self._last_pnl[strategy.id] = current_pnl
                
        except Exception as e:
            log.warning(f"Could not calculate P&L for {strategy.id}: {e}")
            current_pnl_pct = 0
        
        # Check exit conditions
        exit_conditions = strategy.exit_conditions
        if not exit_conditions:
            return
        
        exit_reason = await self._check_exit_conditions(
            strategy, 
            exit_conditions, 
            current_pnl_pct
        )
        
        if exit_reason:
            log.info(f"🚨 Exit triggered for {strategy.name}: {exit_reason.value}")
            await self._auto_close_strategy(strategy, exit_reason)
    
    async def _check_exit_conditions(
        self, 
        strategy: Strategy, 
        conditions: ExitConditions,
        current_pnl_pct: float
    ) -> Optional[ExitReason]:
        """
        Check all exit conditions
        
        Returns ExitReason if any condition met, None otherwise
        """
        strategy_warnings = self._warning_sent.setdefault(strategy.id, {})
        
        # 1. Profit Target
        if conditions.profit_target_pct:
            if current_pnl_pct >= conditions.profit_target_pct:
                return ExitReason.PROFIT_TARGET
            
            # Warning at 80% of target
            warning_threshold = conditions.profit_target_pct * 0.8
            if current_pnl_pct >= warning_threshold and not strategy_warnings.get('profit_warning'):
                self._emit_event(
                    StrategyEvent.EXIT_WARNING,
                    strategy.id,
                    {
                        'type': 'profit_approaching',
                        'current': current_pnl_pct,
                        'target': conditions.profit_target_pct
                    }
                )
                strategy_warnings['profit_warning'] = True
        
        # 2. Stop Loss
        if conditions.stop_loss_pct:
            if current_pnl_pct <= conditions.stop_loss_pct:
                return ExitReason.STOP_LOSS
            
            # Warning at 80% of stop loss
            warning_threshold = conditions.stop_loss_pct * 0.8
            if current_pnl_pct <= warning_threshold and not strategy_warnings.get('loss_warning'):
                self._emit_event(
                    StrategyEvent.EXIT_WARNING,
                    strategy.id,
                    {
                        'type': 'stop_loss_approaching',
                        'current': current_pnl_pct,
                        'stop_loss': conditions.stop_loss_pct
                    }
                )
                strategy_warnings['loss_warning'] = True
        
        # 3. Days to Expiry
        if conditions.dte_exit:
            dte = self._calculate_dte(strategy.expiry)
            if dte is not None and dte <= conditions.dte_exit:
                return ExitReason.DTE_EXIT
            
            # Warning at 2x DTE threshold
            if dte is not None and dte <= conditions.dte_exit * 2 and not strategy_warnings.get('dte_warning'):
                self._emit_event(
                    StrategyEvent.EXIT_WARNING,
                    strategy.id,
                    {
                        'type': 'dte_approaching',
                        'current_dte': dte,
                        'exit_dte': conditions.dte_exit
                    }
                )
                strategy_warnings['dte_warning'] = True
        
        # 4. Max Holding Period (optional)
        if conditions.max_holding_days and strategy.executed_at:
            try:
                executed = datetime.fromisoformat(strategy.executed_at.replace('Z', '+00:00'))
                holding_days = (datetime.now(executed.tzinfo) - executed).days
                
                if holding_days >= conditions.max_holding_days:
                    return ExitReason.TIME_DECAY
            except Exception as e:
                log.warning(f"Could not check holding period: {e}")
        
        return None
    
    def _calculate_dte(self, expiry: str) -> Optional[int]:
        """Calculate days to expiry from expiry string (YYMMDD format)"""
        try:
            # Parse YYMMDD format
            if len(expiry) == 6:
                year = 2000 + int(expiry[:2])
                month = int(expiry[2:4])
                day = int(expiry[4:6])
                expiry_date = datetime(year, month, day)
            # Parse DDMMYYYY format  
            elif len(expiry) == 8:
                day = int(expiry[:2])
                month = int(expiry[2:4])
                year = int(expiry[4:])
                expiry_date = datetime(year, month, day)
            else:
                return None
            
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            dte = (expiry_date - today).days
            
            return max(0, dte)
            
        except Exception as e:
            log.warning(f"Could not parse expiry {expiry}: {e}")
            return None
    
    # ==================== Auto-Actions ====================
    
    async def _auto_close_strategy(self, strategy: Strategy, reason: ExitReason):
        """
        Automatically close strategy
        
        Steps:
        1. Close all positions
        2. Update strategy status
        3. Send notification
        4. Emit event
        """
        log.info(f"🔒 Auto-closing strategy {strategy.name}")
        log.info(f"   Reason: {reason.value}")
        
        try:
            # Close strategy via manager
            result = await self.strategy_manager.close_strategy(
                strategy.id,
                reason=reason.value
            )
            
            if result.get('success'):
                # Emit closed event
                self._emit_event(
                    StrategyEvent.CLOSED,
                    strategy.id,
                    {
                        'reason': reason.value,
                        'final_pnl': result.get('final_pnl'),
                        'final_pnl_pct': result.get('final_pnl_pct')
                    }
                )
                
                # Send notification
                await self._send_close_notification(strategy, reason, result)
                
                # Cleanup tracking
                self._last_pnl.pop(strategy.id, None)
                self._warning_sent.pop(strategy.id, None)
                
                log.info(f"✅ Strategy {strategy.name} closed successfully")
            else:
                log.error(f"❌ Failed to close strategy: {result.get('error')}")
                
        except Exception as e:
            log.error(f"❌ Auto-close failed: {e}", exc_info=True)
            self._emit_event(
                StrategyEvent.ERROR,
                strategy.id,
                {'error': f"Auto-close failed: {str(e)}"}
            )
    
    async def _send_close_notification(
        self, 
        strategy: Strategy, 
        reason: ExitReason, 
        result: Dict
    ):
        """Send notification about strategy closure"""
        if not self.notification_service:
            return
        
        # Build message based on reason
        emoji = "🎯" if reason == ExitReason.PROFIT_TARGET else "🛑" if reason == ExitReason.STOP_LOSS else "📅"
        
        pnl = result.get('final_pnl', 0)
        pnl_pct = result.get('final_pnl_pct', 0)
        pnl_sign = '+' if pnl >= 0 else ''
        
        message = f"""
{emoji} **Strategy Closed: {strategy.name}**

**Reason:** {reason.value.replace('_', ' ').title()}
**Final P&L:** {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.1f}%)
**Underlying:** {strategy.underlying}
**Type:** {strategy.strategy_type}
        """.strip()
        
        try:
            await self.notification_service.send_async(
                title=f"Strategy Closed: {strategy.name}",
                message=message,
                priority='high' if abs(pnl) > 500 else 'normal'
            )
        except Exception as e:
            log.warning(f"Failed to send notification: {e}")
    
    # ==================== Manual Operations ====================
    
    async def force_check(self, strategy_id: str) -> Dict:
        """Force check a specific strategy now"""
        strategy = self.strategy_manager.get_strategy(strategy_id)
        
        if not strategy:
            return {'error': 'Strategy not found'}
        
        if strategy.status != StrategyStatus.ACTIVE.value:
            return {'error': f'Strategy not active (status: {strategy.status})'}
        
        await self._check_strategy(strategy)
        
        return {
            'checked': True,
            'strategy_id': strategy_id,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        return {
            'running': self._running,
            'check_interval': self._check_interval,
            'strategies_tracked': len(self._last_pnl),
            'callbacks_registered': len(self._event_callbacks)
        }
    
    def set_check_interval(self, seconds: int):
        """Update check interval (10-300 seconds)"""
        self._check_interval = max(10, min(300, seconds))
        log.info(f"Monitor interval updated to {self._check_interval}s")


# Global instance
_monitor_instance: Optional[StrategyMonitor] = None


def get_strategy_monitor() -> StrategyMonitor:
    """Get singleton monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = StrategyMonitor()
    return _monitor_instance


def start_strategy_monitor():
    """Start the strategy monitor service"""
    monitor = get_strategy_monitor()
    monitor.start()
    return monitor


def stop_strategy_monitor():
    """Stop the strategy monitor service"""
    if _monitor_instance:
        _monitor_instance.stop()
