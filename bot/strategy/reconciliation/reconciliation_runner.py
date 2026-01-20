#!/usr/bin/env python3
"""
Standalone Reconciliation Engine
Runs independently to detect and correct discrepancies between bot state and exchange state

Usage:
    python3 -m bot.strategy.reconciliation.reconciliation_runner

Created: November 20, 2025
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger as log

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config, get_api_credentials
from bot.api.unified_api_client import UnifiedAPIClient


class ReconciliationEngine:
    """
    Standalone reconciliation engine that detects and corrects discrepancies.
    
    Detects:
    - Missed fills (bot thinks pending, exchange says filled)
    - Unprotected positions (positions without TP orders)
    - Orphaned orders (orders on exchange not tracked by bot)
    - State corruption (invalid position data)
    """
    
    def __init__(self, config, api_client: UnifiedAPIClient):
        self.config = config
        self.api_client = api_client
        self.symbol = config.bot.symbol
        self.product_id = config.bot.product_id
        
        # State files
        self.state_file = Path("data/reconciliation/state.json")
        self.action_queue_file = Path("data/reconciliation/action_queue.json")
        self.bot_state_file = Path("data/bot_state.json")
        
        # Signal files for event-driven triggers
        self.shutdown_signal_file = Path("data/reconciliation/shutdown_signal.json")
        self.emergency_signal_file = Path("data/reconciliation/emergency_signal.json")
        
        # Ensure directories exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.checks_performed = 0
        self.discrepancies_found = 0
        self.actions_generated = 0
        
    async def run(self):
        """Main reconciliation loop - scheduled + event-driven"""
        log.info(" Reconciliation Engine started (EVENT-DRIVEN + SCHEDULED)")
        log.info(f"   Symbol: {self.symbol}")
        log.info(f"   Product ID: {self.product_id}")
        log.info(f"   Scheduled interval: 5 minutes")
        log.info(f"   Event-driven: Immediate on signals")
        
        check_interval = 300  # 5 minutes
        signal_check_interval = 1  # Check for signals every second
        
        while True:
            try:
                # Wait with signal checking
                signal_triggered = False
                for _ in range(check_interval):
                    # Check for immediate triggers
                    has_signal, signal_type = self._check_for_signals()
                    if has_signal:
                        log.info("="*80)
                        log.info(f" {signal_type.upper()} SIGNAL DETECTED - Running immediately!")
                        log.info("="*80)
                        await self._run_reconciliation_check()
                        signal_triggered = True
                        break
                    
                    await asyncio.sleep(signal_check_interval)
                
                # Scheduled check (if no signal interrupted)
                if not signal_triggered:
                    log.info("="*80)
                    log.info(" Scheduled reconciliation check (5 minutes)")
                    log.info("="*80)
                    await self._run_reconciliation_check()
                
            except Exception as e:
                log.error(f"Reconciliation error: {e}")
                import traceback
                log.error(traceback.format_exc())
                await asyncio.sleep(30)  # Retry in 30 seconds
    
    def load_bot_state(self) -> Optional[Dict]:
        """Load bot state from file"""
        try:
            if not self.bot_state_file.exists():
                return None
            
            with open(self.bot_state_file) as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading bot state: {e}")
            return None
    
    async def _run_reconciliation_check(self):
        """Run a single reconciliation check"""
        start_time = time.time()
        
        # Check for shutdown signal first (highest priority)
        shutdown_signal = self._load_shutdown_signal()
        if shutdown_signal:
            await self._handle_shutdown_cleanup(shutdown_signal)
            self._remove_signal_file(self.shutdown_signal_file)
        
        # Check for emergency signal
        emergency_signal = self._load_emergency_signal()
        if emergency_signal:
            await self._handle_emergency_cleanup(emergency_signal)
            self._remove_signal_file(self.emergency_signal_file)
        
        log.info("")
        log.info("🔍 Starting reconciliation check...")
        
        # Load bot state
        bot_state = self.load_bot_state()
        if not bot_state:
            log.warning("⚠️  Bot state file not found - bot may not be running")
            return
        
        # Query exchange for truth
        exchange_state = await self.query_exchange_state()
        
        # Detect discrepancies
        discrepancies = await self.detect_discrepancies(bot_state, exchange_state)
        
        # Generate correction actions
        actions = self.generate_correction_actions(discrepancies)
        
        # Write to action queue
        if actions:
            self.write_action_queue(actions)
            log.info(f" Generated {len(actions)} correction action(s)")
        else:
            log.info(" No discrepancies found - system is healthy")
        
        # Update state
        self.update_state(discrepancies, actions)
        
        # Statistics
        self.checks_performed += 1
        log.info(f" Total checks: {self.checks_performed}, Discrepancies: {self.discrepancies_found}, Actions: {self.actions_generated}")
    
    def _check_for_signals(self) -> Tuple[bool, str]:
        """Check for immediate trigger signals"""
        # Priority 1: Emergency (highest priority)
        if self.emergency_signal_file.exists():
            return True, "emergency"
        
        # Priority 2: Shutdown
        if self.shutdown_signal_file.exists():
            return True, "shutdown"
        
        return False, ""
    
    async def query_exchange_state(self) -> Dict:
        """Query exchange for current state"""
        try:
            # Get all open orders
            orders_response = await self.api_client.list_orders(symbol=self.symbol)
            open_orders = [o for o in orders_response if o.get("state") == "open"]
            
            # Get all positions
            positions_response = await self.api_client.get_positions()
            open_positions = [p for p in positions_response if p.get("product_id") == self.product_id]
            
            return {
                "open_orders": open_orders,
                "open_positions": open_positions,
                "timestamp": time.time()
            }
        except Exception as e:
            log.error(f"Error querying exchange: {e}")
            return {"open_orders": [], "open_positions": [], "timestamp": time.time()}
    
    async def detect_discrepancies(self, bot_state: Dict, exchange_state: Dict) -> List[Dict]:
        """Detect all types of discrepancies"""
        discrepancies = []
        
        log.info("🔍 Detecting discrepancies...")
        
        # 1. Missed fills
        missed_fills = await self.detect_missed_fills(bot_state, exchange_state)
        if missed_fills:
            log.warning(f"⚠️  Found {len(missed_fills)} missed fill(s)")
            discrepancies.extend(missed_fills)
        
        # 2. Unprotected positions
        unprotected = await self.detect_unprotected_positions(bot_state, exchange_state)
        if unprotected:
            log.warning(f"⚠️  Found {len(unprotected)} unprotected position(s)")
            discrepancies.extend(unprotected)
        
        # 3. Orphaned orders
        orphaned = await self.detect_orphaned_orders(bot_state, exchange_state)
        if orphaned:
            log.warning(f"⚠️  Found {len(orphaned)} orphaned order(s)")
            discrepancies.extend(orphaned)
        
        # 4. State corruption
        corrupted = self.detect_state_corruption(bot_state)
        if corrupted:
            log.warning(f"⚠️  Found {len(corrupted)} corrupted state(s)")
            discrepancies.extend(corrupted)
        
        self.discrepancies_found += len(discrepancies)
        return discrepancies
    
    async def detect_missed_fills(self, bot_state: Dict, exchange_state: Dict) -> List[Dict]:
        """Detect fills that bot missed"""
        missed_fills = []
        
        # Get bot's pending orders
        bot_pending_buy = bot_state.get("pending_buy")
        bot_pending_sell = bot_state.get("pending_sell")
        bot_pending_orders = []
        
        if bot_pending_buy:
            bot_pending_orders.append(bot_pending_buy.get("order_id"))
        if bot_pending_sell:
            bot_pending_orders.append(bot_pending_sell.get("order_id"))
        
        # Check each pending order on exchange
        for order_id in bot_pending_orders:
            if not order_id:
                continue
            
            # Query individual order status
            try:
                order = await self.api_client.get_order(order_id)
                
                if order.get("state") == "filled":
                    # Bot thinks pending, but exchange says filled
                    missed_fills.append({
                        "type": "missed_fill",
                        "order_id": str(order_id),
                        "side": order.get("side"),
                        "fill_price": float(order.get("average_fill_price", 0)),
                        "fill_size": int(order.get("size", 0)),
                        "detected_at": time.time()
                    })
                    log.warning(f"🚨 Missed fill detected: Order {order_id}")
            except Exception as e:
                log.debug(f"Could not query order {order_id}: {e}")
        
        return missed_fills
    
    async def detect_unprotected_positions(self, bot_state: Dict, exchange_state: Dict) -> List[Dict]:
        """Detect positions without TP orders"""
        unprotected = []
        
        # Get bot's open positions
        bot_positions = bot_state.get("open_tranches", [])
        exchange_orders = exchange_state.get("open_orders", [])
        
        for position in bot_positions:
            tp_order_id = position.get("tp_order_id")
            tp_price = position.get("tp_price")
            
            if not tp_order_id:
                # Position has no TP order ID
                unprotected.append({
                    "type": "unprotected_position",
                    "position_id": position.get("position_id"),
                    "entry_price": position.get("entry_price"),
                    "tp_price": tp_price,
                    "reason": "no_tp_order_id",
                    "detected_at": time.time()
                })
                log.warning(f"🚨 Unprotected position: {position.get('position_id')} (no TP order ID)")
                continue
            
            # Check if TP order exists on exchange (3-tier verification)
            tp_exists = False
            
            # Tier 1: Direct ID match
            for order in exchange_orders:
                if str(order.get("id")) == str(tp_order_id):
                    tp_exists = True
                    break
            
            # Tier 2: Price + reduce_only match
            if not tp_exists and tp_price:
                for order in exchange_orders:
                    is_reduce_only = order.get("reduce_only") == True
                    price_match = abs(float(order.get("limit_price", 0)) - float(tp_price)) < 0.01
                    if is_reduce_only and price_match:
                        tp_exists = True
                        break
            
            if not tp_exists:
                unprotected.append({
                    "type": "unprotected_position",
                    "position_id": position.get("position_id"),
                    "entry_price": position.get("entry_price"),
                    "tp_price": tp_price,
                    "tp_order_id": tp_order_id,
                    "reason": "tp_not_on_exchange",
                    "detected_at": time.time()
                })
                log.warning(f"🚨 Unprotected position: {position.get('position_id')} (TP order {tp_order_id} not found)")
        
        return unprotected
    
    async def detect_orphaned_orders(self, bot_state: Dict, exchange_state: Dict) -> List[Dict]:
        """Detect orders on exchange that bot doesn't track"""
        orphaned = []
        
        # Get bot's tracked orders
        bot_order_ids = set()
        
        # Add pending orders
        if bot_state.get("pending_buy"):
            bot_order_ids.add(str(bot_state["pending_buy"].get("order_id")))
        if bot_state.get("pending_sell"):
            bot_order_ids.add(str(bot_state["pending_sell"].get("order_id")))
        
        # Add TP orders from positions
        for position in bot_state.get("open_tranches", []):
            tp_order_id = position.get("tp_order_id")
            if tp_order_id:
                bot_order_ids.add(str(tp_order_id))
        
        # Check exchange orders
        for order in exchange_state.get("open_orders", []):
            order_id = str(order.get("id"))
            
            if order_id not in bot_order_ids:
                # Order on exchange but not tracked by bot
                orphaned.append({
                    "type": "orphaned_order",
                    "order_id": order_id,
                    "side": order.get("side"),
                    "price": float(order.get("limit_price", 0)),
                    "size": int(order.get("size", 0)),
                    "reduce_only": order.get("reduce_only", False),
                    "detected_at": time.time()
                })
                log.warning(f"🚨 Orphaned order: {order_id} ({order.get('side')})")
        
        return orphaned
    
    def detect_state_corruption(self, bot_state: Dict) -> List[Dict]:
        """Detect corrupted state data"""
        corrupted = []
        
        # Check positions for invalid data
        for position in bot_state.get("open_tranches", []):
            position_id = position.get("position_id")
            entry_price = position.get("entry_price")
            
            # Check for None or invalid entry price
            if entry_price is None or str(entry_price).lower() == "none":
                corrupted.append({
                    "type": "corrupted_state",
                    "position_id": position_id,
                    "field": "entry_price",
                    "value": entry_price,
                    "reason": "null_or_invalid",
                    "detected_at": time.time()
                })
                log.warning(f"🚨 Corrupted state: Position {position_id} has invalid entry_price")
        
        return corrupted
    
    def generate_correction_actions(self, discrepancies: List[Dict]) -> List[Dict]:
        """Generate correction actions for discrepancies"""
        actions = []
        action_id = int(time.time() * 1000)
        
        for disc in discrepancies:
            disc_type = disc.get("type")
            
            if disc_type == "missed_fill":
                actions.append({
                    "id": f"action_{action_id}",
                    "type": "process_missed_fill",
                    "order_id": disc["order_id"],
                    "side": disc["side"],
                    "fill_price": disc["fill_price"],
                    "fill_size": disc["fill_size"],
                    "priority": "high",
                    "created_at": time.time(),
                    "status": "pending"
                })
                action_id += 1
            
            elif disc_type == "unprotected_position":
                actions.append({
                    "id": f"action_{action_id}",
                    "type": "place_emergency_tp",
                    "position_id": disc["position_id"],
                    "entry_price": disc["entry_price"],
                    "tp_price": disc["tp_price"],
                    "priority": "critical",
                    "created_at": time.time(),
                    "status": "pending"
                })
                action_id += 1
            
            elif disc_type == "orphaned_order":
                # Only cancel non-TP orders (safety)
                if not disc.get("reduce_only"):
                    actions.append({
                        "id": f"action_{action_id}",
                        "type": "cancel_orphaned_order",
                        "order_id": disc["order_id"],
                        "side": disc["side"],
                        "price": disc["price"],
                        "priority": "medium",
                        "created_at": time.time(),
                        "status": "pending"
                    })
                    action_id += 1
            
            elif disc_type == "corrupted_state":
                actions.append({
                    "id": f"action_{action_id}",
                    "type": "flag_corrupted_state",
                    "position_id": disc["position_id"],
                    "field": disc["field"],
                    "value": disc["value"],
                    "priority": "low",
                    "created_at": time.time(),
                    "status": "pending"
                })
                action_id += 1
        
        self.actions_generated += len(actions)
        return actions
    
    def write_action_queue(self, actions: List[Dict]):
        """Write actions to queue file"""
        try:
            # Load existing queue
            existing_actions = []
            if self.action_queue_file.exists():
                with open(self.action_queue_file) as f:
                    data = json.load(f)
                    existing_actions = data.get("actions", [])
            
            # Add new actions
            all_actions = existing_actions + actions
            
            # Write atomically
            temp_file = self.action_queue_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump({
                    "actions": all_actions,
                    "updated_at": time.time()
                }, f, indent=2)
            
            temp_file.replace(self.action_queue_file)
            log.info(f"✅ Wrote {len(actions)} action(s) to queue")
            
        except Exception as e:
            log.error(f"Error writing action queue: {e}")
    
    def update_state(self, discrepancies: List[Dict], actions: List[Dict]):
        """Update reconciliation state"""
        try:
            state = {
                "last_check_time": time.time(),
                "checks_performed": self.checks_performed,
                "discrepancies_found": self.discrepancies_found,
                "actions_generated": self.actions_generated,
                "last_discrepancies": len(discrepancies),
                "last_actions": len(actions),
                "status": "healthy" if len(discrepancies) == 0 else "issues_detected"
            }
            
            # Write atomically
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            temp_file.replace(self.state_file)
            
        except Exception as e:
            log.error(f"Error updating state: {e}")
    
    def _load_shutdown_signal(self) -> Optional[Dict]:
        """Load shutdown signal from file"""
        try:
            if not self.shutdown_signal_file.exists():
                return None
            
            with open(self.shutdown_signal_file) as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading shutdown signal: {e}")
            return None
    
    def _load_emergency_signal(self) -> Optional[Dict]:
        """Load emergency signal from file"""
        try:
            if not self.emergency_signal_file.exists():
                return None
            
            with open(self.emergency_signal_file) as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading emergency signal: {e}")
            return None
    
    def _remove_signal_file(self, signal_file: Path):
        """Remove signal file after processing"""
        try:
            if signal_file.exists():
                signal_file.unlink()
                log.info(f"✅ Removed signal file: {signal_file.name}")
        except Exception as e:
            log.error(f"Error removing signal file: {e}")
    
    async def _handle_shutdown_cleanup(self, signal: Dict):
        """
        Handle bot shutdown cleanup with MODE-AWARE cancellation.
        
        CRITICAL FIX (Nov 20, 2025):
        - LONG mode: Cancel only pending BUY orders (entry orders)
        - SHORT mode: Cancel only pending SELL orders (entry orders)
        - Preserve TP orders (reduce_only) in both modes
        """
        log.info("🛑 Processing shutdown cleanup...")
        log.info(f"   Shutdown reason: {signal.get('reason', 'unknown')}")
        log.info(f"   Timestamp: {signal.get('timestamp')}")
        
        # Get bot mode for mode-aware cleanup
        mode = signal.get("mode", "LONG")  # Default to LONG if not specified
        log.info(f"   Bot mode: {mode}")
        
        actions = []
        
        # Get pending orders from signal
        pending_buy = signal.get("pending_buy")
        pending_sell = signal.get("pending_sell")
        
        # MODE-AWARE CLEANUP
        if mode == "LONG":
            # LONG mode: Cancel only pending BUY orders (entry orders)
            # Keep pending SELL orders (they are TP orders)
            if pending_buy and pending_buy.get("order_id"):
                actions.append({
                    "id": f"shutdown_cleanup_buy_{int(time.time())}",
                    "type": "cancel_pending_order",
                    "order_id": pending_buy["order_id"],
                    "side": "buy",
                    "price": pending_buy.get("price"),
                    "reason": "bot_shutdown_long_mode",
                    "priority": "high",
                    "status": "pending",
                    "created_at": time.time()
                })
                log.info(f"   📝 [LONG MODE] Cancel pending BUY order #{pending_buy['order_id']} @ ${pending_buy.get('price')}")
            
            if pending_sell:
                log.info(f"   ✅ [LONG MODE] Preserve pending SELL order (TP) @ ${pending_sell.get('price')}")
        
        elif mode == "SHORT":
            # SHORT mode: Cancel only pending SELL orders (entry orders)
            # Keep pending BUY orders (they are TP orders)
            if pending_sell and pending_sell.get("order_id"):
                actions.append({
                    "id": f"shutdown_cleanup_sell_{int(time.time())}",
                    "type": "cancel_pending_order",
                    "order_id": pending_sell["order_id"],
                    "side": "sell",
                    "price": pending_sell.get("price"),
                    "reason": "bot_shutdown_short_mode",
                    "priority": "high",
                    "status": "pending",
                    "created_at": time.time()
                })
                log.info(f"   📝 [SHORT MODE] Cancel pending SELL order #{pending_sell['order_id']} @ ${pending_sell.get('price')}")
            
            if pending_buy:
                log.info(f"   ✅ [SHORT MODE] Preserve pending BUY order (TP) @ ${pending_buy.get('price')}")
        
        # Write actions to queue
        if actions:
            self._append_to_action_queue(actions)
            log.info(f"✅ Generated {len(actions)} shutdown cleanup action(s)")
            self.actions_generated += len(actions)
        else:
            log.info("✅ No pending orders to clean up")
    
    async def _handle_emergency_cleanup(self, signal: Dict):
        """Handle emergency cleanup"""
        log.warning("🚨 Processing EMERGENCY cleanup...")
        log.warning(f"   Emergency reason: {signal.get('reason', 'unknown')}")
        
        # Emergency cleanup: Cancel ALL orders
        try:
            orders = await self.api_client.list_orders(symbol=self.symbol, state="open")
            
            actions = []
            for order in orders:
                # Cancel all non-TP orders
                if not order.get("reduce_only"):
                    actions.append({
                        "id": f"emergency_cleanup_{order['id']}",
                        "type": "cancel_pending_order",
                        "order_id": str(order["id"]),
                        "side": order.get("side"),
                        "price": order.get("limit_price"),
                        "reason": "emergency_cleanup",
                        "priority": "critical",
                        "status": "pending",
                        "created_at": time.time()
                    })
            
            if actions:
                self._append_to_action_queue(actions)
                log.warning(f"🚨 Generated {len(actions)} EMERGENCY cleanup action(s)")
                self.actions_generated += len(actions)
        
        except Exception as e:
            log.error(f"Error in emergency cleanup: {e}")
    
    def _append_to_action_queue(self, new_actions: List[Dict]):
        """Append new actions to existing action queue"""
        try:
            # Load existing queue
            existing_queue = {"actions": [], "updated_at": time.time()}
            if self.action_queue_file.exists():
                with open(self.action_queue_file) as f:
                    existing_queue = json.load(f)
            
            # Append new actions
            existing_queue["actions"].extend(new_actions)
            existing_queue["updated_at"] = time.time()
            
            # Write back
            temp_file = self.action_queue_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(existing_queue, f, indent=2)
            temp_file.replace(self.action_queue_file)
            
        except Exception as e:
            log.error(f"Error appending to action queue: {e}")


async def main():
    """Main entry point"""
    try:
        # Load configuration
        config = get_config()
        
        # Get API credentials
        credentials = get_api_credentials(config.trading_mode)
        api_key = credentials['api_key']
        api_secret = credentials['api_secret']
        
        # Create unified API client (REST only, no WebSocket needed)
        testnet = (config.trading_mode == 'demo')
        api_client = UnifiedAPIClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            enable_websocket=False  # Reconciliation doesn't need WebSocket
        )
        
        # Create and run reconciliation engine
        engine = ReconciliationEngine(config, api_client)
        await engine.run()
        
    except KeyboardInterrupt:
        log.info("Shutting down reconciliation engine...")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        import traceback
        log.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
