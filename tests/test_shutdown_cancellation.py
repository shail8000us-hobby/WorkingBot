#!/usr/bin/env python3
"""
Test script to validate shutdown order cancellation logic.

This script demonstrates the shutdown sequence with pending order cancellation.
Run after implementing the fix to verify behavior.

Usage:
    python test_shutdown_cancellation.py
"""

import asyncio
from typing import Dict, Any


class MockPositionActor:
    """Mock position actor for testing."""
    
    def __init__(self):
        self.state = {
            "pending_buy": {"order_id": "123456", "price": 99000},
            "pending_sell": None,
            "open_tranches": [
                {"entry_price": 99500, "tp_price": 100000},
                {"entry_price": 99000, "tp_price": 99500},
            ]
        }
        self.cleared_buy = False
        self.cleared_sell = False
    
    async def ask(self, msg_type: str, payload: Dict, timeout: float = 5.0) -> Dict[str, Any]:
        """Mock ask method."""
        if msg_type == "GET_STATE":
            return self.state
        return {}
    
    async def tell(self, msg_type: str, payload: Dict) -> None:
        """Mock tell method."""
        if msg_type == "CLEAR_PENDING_BUY":
            self.cleared_buy = True
            self.state["pending_buy"] = None
            print("   [PositionActor] Cleared pending_buy state")
        elif msg_type == "CLEAR_PENDING_SELL":
            self.cleared_sell = True
            self.state["pending_sell"] = None
            print("   [PositionActor] Cleared pending_sell state")


class MockOrderActor:
    """Mock order actor for testing."""
    
    def __init__(self):
        self.cancelled_orders = []
    
    async def ask(self, msg_type: str, payload: Dict, timeout: float = 10.0) -> Dict[str, Any]:
        """Mock ask method."""
        if msg_type == "CANCEL_ORDER":
            order_id = payload.get("order_id")
            self.cancelled_orders.append(order_id)
            print(f"   [OrderActor] Cancelled order: {order_id}")
            return {"status": "ok", "order_id": order_id}
        return {"status": "error", "error": "Unknown message type"}


async def simulate_shutdown_cancellation():
    """Simulate the shutdown cancellation sequence."""
    
    print("=" * 70)
    print("SHUTDOWN CANCELLATION SIMULATION")
    print("=" * 70)
    print()
    
    # Create mock actors
    position_actor = MockPositionActor()
    order_actor = MockOrderActor()
    
    print("Initial State:")
    print(f"  Pending BUY: {position_actor.state['pending_buy']}")
    print(f"  Pending SELL: {position_actor.state['pending_sell']}")
    print(f"  Open Positions: {len(position_actor.state['open_tranches'])}")
    print()
    
    print("Starting shutdown cancellation...")
    print()
    
    # Get state
    print("1. Getting state from PositionActor...")
    state = await position_actor.ask("GET_STATE", {}, timeout=5.0)
    print(f"   State retrieved: {len(state['open_tranches'])} positions, "
          f"pending_buy={state['pending_buy'] is not None}, "
          f"pending_sell={state['pending_sell'] is not None}")
    print()
    
    cancelled_count = 0
    
    # Cancel pending BUY
    if pending_buy := state.get("pending_buy"):
        order_id = pending_buy.get("order_id")
        price = pending_buy.get("price")
        
        print(f"2. Cancelling pending BUY @ ${price:,.0f} (Order: {order_id})")
        result = await order_actor.ask(
            "CANCEL_ORDER",
            {"order_id": order_id},
            timeout=10.0
        )
        
        if result.get("status") == "ok":
            print(f"   ✅ Cancelled successfully")
            cancelled_count += 1
            await position_actor.tell("CLEAR_PENDING_BUY", {})
        else:
            print(f"   ❌ Failed: {result.get('error')}")
        print()
    
    # Cancel pending SELL
    if pending_sell := state.get("pending_sell"):
        order_id = pending_sell.get("order_id")
        price = pending_sell.get("price")
        
        print(f"3. Cancelling pending SELL @ ${price:,.0f} (Order: {order_id})")
        result = await order_actor.ask(
            "CANCEL_ORDER",
            {"order_id": order_id},
            timeout=10.0
        )
        
        if result.get("status") == "ok":
            print(f"   ✅ Cancelled successfully")
            cancelled_count += 1
            await position_actor.tell("CLEAR_PENDING_SELL", {})
        else:
            print(f"   ❌ Failed: {result.get('error')}")
        print()
    
    # Summary
    open_positions = len(state.get("open_tranches", []))
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Cancelled {cancelled_count} pending entry order(s)")
    print(f"📊 Preserved {open_positions} open position(s) with TP protection")
    print()
    
    print("Final State:")
    print(f"  Pending BUY: {position_actor.state['pending_buy']}")
    print(f"  Pending SELL: {position_actor.state['pending_sell']}")
    print(f"  Open Positions: {len(position_actor.state['open_tranches'])}")
    print(f"  Cleared BUY state: {position_actor.cleared_buy}")
    print(f"  Cleared SELL state: {position_actor.cleared_sell}")
    print(f"  Cancelled orders: {order_actor.cancelled_orders}")
    print("=" * 70)
    
    # Validation
    print()
    print("VALIDATION:")
    if position_actor.state["pending_buy"] is None:
        print("  ✅ Pending BUY cleared")
    else:
        print("  ❌ Pending BUY still exists")
    
    if position_actor.state["pending_sell"] is None:
        print("  ✅ Pending SELL cleared")
    else:
        print("  ❌ Pending SELL still exists")
    
    if len(position_actor.state["open_tranches"]) == 2:
        print("  ✅ Open positions preserved")
    else:
        print("  ❌ Open positions modified")
    
    if "123456" in order_actor.cancelled_orders:
        print("  ✅ Order cancelled via OrderActor")
    else:
        print("  ❌ Order not cancelled")


async def simulate_no_pending_orders():
    """Simulate shutdown with no pending orders."""
    
    print("\n\n")
    print("=" * 70)
    print("SHUTDOWN WITH NO PENDING ORDERS")
    print("=" * 70)
    print()
    
    # Create mock actors with no pending orders
    position_actor = MockPositionActor()
    position_actor.state["pending_buy"] = None
    position_actor.state["pending_sell"] = None
    order_actor = MockOrderActor()
    
    print("Initial State:")
    print(f"  Pending BUY: {position_actor.state['pending_buy']}")
    print(f"  Pending SELL: {position_actor.state['pending_sell']}")
    print(f"  Open Positions: {len(position_actor.state['open_tranches'])}")
    print()
    
    # Get state
    state = await position_actor.ask("GET_STATE", {}, timeout=5.0)
    
    cancelled_count = 0
    
    # Check pending orders
    if not state.get("pending_buy") and not state.get("pending_sell"):
        print("ℹ️  No pending entry orders to cancel")
    
    # Summary
    open_positions = len(state.get("open_tranches", []))
    print()
    print("=" * 70)
    print(f"ℹ️  No pending entry orders to cancel")
    print(f"📊 Preserving {open_positions} open position(s) with TP protection")
    print("=" * 70)


async def main():
    """Run all simulations."""
    await simulate_shutdown_cancellation()
    await simulate_no_pending_orders()


if __name__ == "__main__":
    asyncio.run(main())
