import asyncio
import time
from typing import Dict, Any, Optional, Callable
from loguru import logger as log

from bot.strategy.monitors.base_monitor import BaseMonitor
from bot.api.async_delta_client import AsyncDeltaClient
from bot.strategy.actors.position_actor import PositionManagerActor


class EnhancedReconciliation(BaseMonitor):
    """
    Enhanced reconciliation with shorter interval.
    
    Runs more frequently than standard reconciliation (2 minutes vs 5 minutes)
    to catch issues faster. Complements the standard reconciliation loop.
    
    Features:
    - Faster reconciliation cycle (2 minutes)
    - Lightweight checks (no heavy operations)
    - Focuses on critical issues
    - Metrics and health tracking
    """
    
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        position_actor: PositionManagerActor,
        product_id: int,
        check_interval: int = 120,  # 2 minutes
        reconciliation_callback: Optional[Callable] = None
    ):
        super().__init__("EnhancedReconciliation")
        self.api_client = api_client
        self.position_actor = position_actor
        self.product_id = product_id
        self.check_interval = check_interval
        self.reconciliation_callback = reconciliation_callback
        
        # Metrics
        self._reconciliations_performed = 0
        self._issues_detected = 0
        self._issues_resolved = 0
    
    async def _execute(self) -> None:
        """Execute enhanced reconciliation loop."""
        await self._perform_reconciliation()
        await asyncio.sleep(self.check_interval)
    
    async def _perform_reconciliation(self) -> None:
        """Perform lightweight reconciliation checks."""
        try:
            log.info(f"[{self.name}] Starting enhanced reconciliation...")
            self._reconciliations_performed += 1
            
            # Get bot state
            bot_state = await self._get_bot_state()
            if not bot_state:
                return
            
            # Check 1: Verify pending orders still exist
            await self._verify_pending_orders(bot_state)
            
            # Check 2: Verify TP protection
            await self._verify_tp_protection(bot_state)
            
            log.info(f"[{self.name}] Enhanced reconciliation complete ✅")
        
        except Exception as e:
            log.error(f"[{self.name}] Error performing reconciliation: {e}")
    
    async def _get_bot_state(self) -> Optional[Dict[str, Any]]:
        """Get bot's internal state."""
        try:
            state_queue = asyncio.Queue()
            await self.position_actor.mailbox.put({
                "type": "GET_STATE",
                "payload": {},
                "reply_to": state_queue
            })
            
            state = await asyncio.wait_for(state_queue.get(), timeout=5.0)
            return state
        
        except asyncio.TimeoutError:
            log.error(f"[{self.name}] Timeout getting bot state")
            return None
        except Exception as e:
            log.error(f"[{self.name}] Error getting bot state: {e}")
            return None
    
    async def _verify_pending_orders(self, bot_state: Dict[str, Any]) -> None:
        """Verify pending orders still exist on exchange."""
        try:
            pending_buy = bot_state.get("pending_buy")
            pending_sell = bot_state.get("pending_sell")
            
            # Check pending buy
            if pending_buy:
                order_id = pending_buy.get("order_id")
                if order_id:
                    exists = await self._check_order_exists(order_id)
                    if not exists:
                        self._issues_detected += 1
                        log.warning(f"[{self.name}] Pending BUY order {order_id} not found on exchange!")
                        
                        if self.reconciliation_callback:
                            await self.reconciliation_callback("missing_pending_buy", order_id)
                            self._issues_resolved += 1
            
            # Check pending sell
            if pending_sell:
                order_id = pending_sell.get("order_id")
                if order_id:
                    exists = await self._check_order_exists(order_id)
                    if not exists:
                        self._issues_detected += 1
                        log.warning(f"[{self.name}] Pending SELL order {order_id} not found on exchange!")
                        
                        if self.reconciliation_callback:
                            await self.reconciliation_callback("missing_pending_sell", order_id)
                            self._issues_resolved += 1
        
        except Exception as e:
            log.error(f"[{self.name}] Error verifying pending orders: {e}")
    
    async def _verify_tp_protection(self, bot_state: Dict[str, Any]) -> None:
        """Verify all positions have TP protection."""
        try:
            positions = bot_state.get("open_tranches", [])
            
            for position in positions:
                tp_order_id = position.get("tp_order_id")
                position_id = position.get("position_id")
                
                if not tp_order_id:
                    self._issues_detected += 1
                    log.error(f"[{self.name}] Position {position_id} has no TP order!")
                    
                    if self.reconciliation_callback:
                        await self.reconciliation_callback("missing_tp", position)
                        self._issues_resolved += 1
                else:
                    # Verify TP order exists
                    exists = await self._check_order_exists(tp_order_id)
                    if not exists:
                        self._issues_detected += 1
                        log.error(f"[{self.name}] TP order {tp_order_id} for position {position_id} not found!")
                        
                        if self.reconciliation_callback:
                            await self.reconciliation_callback("missing_tp_order", position)
                            self._issues_resolved += 1
        
        except Exception as e:
            log.error(f"[{self.name}] Error verifying TP protection: {e}")
    
    async def _check_order_exists(self, order_id: str) -> bool:
        """Check if order exists on exchange."""
        try:
            order = await self.api_client.get_order(order_id)
            if not order:
                return False
            
            state = order.get("state", "unknown")
            # Order exists if it's open or recently closed
            return state in ["open", "partial_fill"]
        
        except Exception as e:
            log.error(f"[{self.name}] Error checking order {order_id}: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get reconciliation metrics."""
        success_rate = 0
        if self._issues_detected > 0:
            success_rate = (self._issues_resolved / self._issues_detected) * 100
        
        return {
            "reconciliations_performed": self._reconciliations_performed,
            "issues_detected": self._issues_detected,
            "issues_resolved": self._issues_resolved,
            "success_rate": success_rate
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with metrics."""
        base_health = super().get_health_status()
        base_health.update({
            "metrics": self.get_metrics()
        })
        return base_health
