import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from loguru import logger as log

from bot.strategy.monitors.base_monitor import BaseMonitor
from bot.api.async_delta_client import AsyncDeltaClient
from bot.strategy.actors.position_actor import PositionManagerActor


class DiscrepancyType(Enum):
    """Types of state discrepancies between bot and exchange."""
    MISSING_ORDER = "bot_has_order_exchange_doesnt"
    EXTRA_ORDER = "exchange_has_order_bot_doesnt"
    MISSING_POSITION = "exchange_has_position_bot_doesnt"
    STATE_MISMATCH = "bot_and_exchange_disagree_on_state"
    ORPHANED_TP = "tp_order_without_position"
    UNPROTECTED_POSITION = "position_without_tp_order"


class Discrepancy:
    """Represents a state discrepancy."""
    
    def __init__(
        self,
        discrepancy_type: DiscrepancyType,
        order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.type = discrepancy_type
        self.order_id = order_id
        self.position_id = position_id
        self.details = details or {}
        self.detected_at = time.time()
    
    def __repr__(self):
        return f"Discrepancy({self.type.value}, order={self.order_id}, position={self.position_id})"


class StateComparator(BaseMonitor):
    """
    Exchange state comparator.
    
    Periodically compares bot's internal state with exchange state:
    - Snapshots bot state (from PositionActor)
    - Snapshots exchange state (via API)
    - Detects discrepancies
    - Auto-reconciles common issues
    - Alerts on critical discrepancies
    
    Features:
    - Continuous validation (every 60 seconds)
    - Multiple discrepancy types
    - Auto-reconciliation
    - Metrics and alerting
    """
    
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        position_actor: PositionManagerActor,
        product_id: int,
        check_interval: int = 60,
        auto_reconcile: bool = True,
        alert_threshold: int = 3,
        reconciliation_callback: Optional[Callable] = None
    ):
        super().__init__("StateComparator")
        self.api_client = api_client
        self.position_actor = position_actor
        self.product_id = product_id
        self.check_interval = check_interval
        self.auto_reconcile = auto_reconcile
        self.alert_threshold = alert_threshold
        self.reconciliation_callback = reconciliation_callback
        
        # Metrics
        self._comparisons_performed = 0
        self._discrepancies_detected = 0
        self._auto_reconciled = 0
        self._alerts_sent = 0
        
        # Discrepancy tracking
        self._recent_discrepancies: List[Discrepancy] = []
        self._max_discrepancy_history = 100
    
    async def _execute(self) -> None:
        """Execute state comparison loop."""
        await self._perform_comparison()
        await asyncio.sleep(self.check_interval)
    
    async def _perform_comparison(self) -> None:
        """Perform state comparison between bot and exchange."""
        try:
            log.info(f"[{self.name}] Starting state comparison...")
            self._comparisons_performed += 1
            
            # Get bot state
            bot_state = await self._get_bot_state()
            if not bot_state:
                log.warning(f"[{self.name}] Could not get bot state")
                return
            
            # Get exchange state
            exchange_state = await self._get_exchange_state()
            if not exchange_state:
                log.warning(f"[{self.name}] Could not get exchange state")
                return
            
            # Compare states
            discrepancies = self._compare_states(bot_state, exchange_state)
            
            if discrepancies:
                self._discrepancies_detected += len(discrepancies)
                log.warning(f"[{self.name}] Found {len(discrepancies)} discrepancies")
                
                # Store discrepancies
                self._recent_discrepancies.extend(discrepancies)
                self._cleanup_discrepancy_history()
                
                # Handle discrepancies
                if self.auto_reconcile:
                    await self._handle_discrepancies(discrepancies)
                
                # Alert if threshold exceeded
                if len(discrepancies) >= self.alert_threshold:
                    await self._send_alert(discrepancies)
            else:
                log.info(f"[{self.name}] No discrepancies found - states match ✅")
        
        except Exception as e:
            log.error(f"[{self.name}] Error performing comparison: {e}")
    
    async def _get_bot_state(self) -> Optional[Dict[str, Any]]:
        """Get bot's internal state from PositionActor."""
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
    
    async def _get_exchange_state(self) -> Optional[Dict[str, Any]]:
        """Get exchange state via API."""
        try:
            # Get open orders
            open_orders = await self.api_client.list_orders(
                product_id=self.product_id,
                state="open"
            )
            
            # Get positions
            positions = await self.api_client.get_positions(
                product_id=self.product_id
            )
            
            return {
                "open_orders": open_orders or [],
                "positions": positions or []
            }
        
        except Exception as e:
            log.error(f"[{self.name}] Error getting exchange state: {e}")
            return None
    
    def _compare_states(
        self,
        bot_state: Dict[str, Any],
        exchange_state: Dict[str, Any]
    ) -> List[Discrepancy]:
        """
        Compare bot state with exchange state.
        
        Returns list of discrepancies found.
        """
        discrepancies = []
        
        # Extract data
        bot_pending_buy = bot_state.get("pending_buy")
        bot_pending_sell = bot_state.get("pending_sell")
        bot_positions = bot_state.get("open_tranches", [])
        
        exchange_orders = exchange_state.get("open_orders", [])
        exchange_positions = exchange_state.get("positions", [])
        
        # Check 1: Bot has pending order, exchange doesn't
        if bot_pending_buy:
            order_id = str(bot_pending_buy.get("order_id"))
            if not self._order_exists_on_exchange(order_id, exchange_orders):
                discrepancies.append(Discrepancy(
                    DiscrepancyType.MISSING_ORDER,
                    order_id=order_id,
                    details={"side": "buy", "bot_state": bot_pending_buy}
                ))
        
        if bot_pending_sell:
            order_id = str(bot_pending_sell.get("order_id"))
            if not self._order_exists_on_exchange(order_id, exchange_orders):
                discrepancies.append(Discrepancy(
                    DiscrepancyType.MISSING_ORDER,
                    order_id=order_id,
                    details={"side": "sell", "bot_state": bot_pending_sell}
                ))
        
        # Check 2: Exchange has entry orders bot doesn't know about
        for order in exchange_orders:
            if order.get("reduce_only"):
                continue  # Skip TP orders
            
            order_id = str(order.get("id") or order.get("order_id"))
            side = order.get("side")
            
            # Check if bot knows about this order
            if side == "buy" and bot_pending_buy:
                if str(bot_pending_buy.get("order_id")) != order_id:
                    discrepancies.append(Discrepancy(
                        DiscrepancyType.EXTRA_ORDER,
                        order_id=order_id,
                        details={"side": "buy", "exchange_order": order}
                    ))
            elif side == "sell" and bot_pending_sell:
                if str(bot_pending_sell.get("order_id")) != order_id:
                    discrepancies.append(Discrepancy(
                        DiscrepancyType.EXTRA_ORDER,
                        order_id=order_id,
                        details={"side": "sell", "exchange_order": order}
                    ))
            elif (side == "buy" and not bot_pending_buy) or (side == "sell" and not bot_pending_sell):
                discrepancies.append(Discrepancy(
                    DiscrepancyType.EXTRA_ORDER,
                    order_id=order_id,
                    details={"side": side, "exchange_order": order}
                ))
        
        # Check 3: Unprotected positions (no TP order)
        for position in bot_positions:
            tp_order_id = position.get("tp_order_id")
            if not tp_order_id:
                discrepancies.append(Discrepancy(
                    DiscrepancyType.UNPROTECTED_POSITION,
                    position_id=position.get("position_id"),
                    details={"position": position}
                ))
            elif not self._order_exists_on_exchange(str(tp_order_id), exchange_orders):
                discrepancies.append(Discrepancy(
                    DiscrepancyType.UNPROTECTED_POSITION,
                    position_id=position.get("position_id"),
                    order_id=str(tp_order_id),
                    details={"position": position, "missing_tp": tp_order_id}
                ))
        
        return discrepancies
    
    def _order_exists_on_exchange(self, order_id: str, exchange_orders: List[Dict]) -> bool:
        """Check if order exists on exchange."""
        for order in exchange_orders:
            exchange_order_id = str(order.get("id") or order.get("order_id", ""))
            if exchange_order_id == order_id:
                return True
        return False
    
    async def _handle_discrepancies(self, discrepancies: List[Discrepancy]) -> None:
        """Handle discrepancies with auto-reconciliation."""
        for disc in discrepancies:
            try:
                log.info(f"[{self.name}] Handling discrepancy: {disc.type.value}")
                
                if disc.type == DiscrepancyType.MISSING_ORDER:
                    # Bot thinks order exists, but exchange doesn't have it
                    # Trigger reconciliation callback to investigate
                    if self.reconciliation_callback:
                        await self.reconciliation_callback(disc)
                        self._auto_reconciled += 1
                
                elif disc.type == DiscrepancyType.UNPROTECTED_POSITION:
                    # Position without TP - critical!
                    log.error(f"[{self.name}] CRITICAL: Unprotected position detected!")
                    if self.reconciliation_callback:
                        await self.reconciliation_callback(disc)
                        self._auto_reconciled += 1
                
                elif disc.type == DiscrepancyType.EXTRA_ORDER:
                    # Exchange has order bot doesn't know about
                    log.warning(f"[{self.name}] Extra order on exchange: {disc.order_id}")
                    # This might be a manual order - don't auto-reconcile
            
            except Exception as e:
                log.error(f"[{self.name}] Error handling discrepancy {disc}: {e}")
    
    async def _send_alert(self, discrepancies: List[Discrepancy]) -> None:
        """Send alert for critical discrepancies."""
        self._alerts_sent += 1
        
        log.critical("=" * 80)
        log.critical(f"🚨 [{self.name}] ALERT: {len(discrepancies)} discrepancies detected!")
        
        for disc in discrepancies:
            log.critical(f"   - {disc.type.value}")
            if disc.order_id:
                log.critical(f"     Order: {disc.order_id}")
            if disc.position_id:
                log.critical(f"     Position: {disc.position_id}")
        
        log.critical("=" * 80)
    
    def _cleanup_discrepancy_history(self) -> None:
        """Cleanup old discrepancies."""
        if len(self._recent_discrepancies) > self._max_discrepancy_history:
            self._recent_discrepancies = self._recent_discrepancies[-self._max_discrepancy_history:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comparator metrics."""
        # Count discrepancies by type
        type_counts = {}
        for disc_type in DiscrepancyType:
            count = sum(1 for d in self._recent_discrepancies if d.type == disc_type)
            type_counts[disc_type.value] = count
        
        return {
            "comparisons_performed": self._comparisons_performed,
            "discrepancies_detected": self._discrepancies_detected,
            "auto_reconciled": self._auto_reconciled,
            "alerts_sent": self._alerts_sent,
            "recent_discrepancies": len(self._recent_discrepancies),
            "discrepancy_types": type_counts
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with metrics."""
        base_health = super().get_health_status()
        base_health.update({
            "metrics": self.get_metrics()
        })
        return base_health
