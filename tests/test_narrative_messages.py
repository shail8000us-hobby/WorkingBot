#!/usr/bin/env python3
"""
Test script to verify narrative mode is working for recently fixed methods.
Run this to see trader-style commentary in action!
"""

from bot.utils.human_logger import HumanLogger

# Create logger with narrative mode enabled
logger = HumanLogger(narrative_mode=True)

print("\n" + "="*70)
print("TESTING NARRATIVE MODE - Recently Fixed Methods")
print("="*70 + "\n")

# Test 1: Message routing
print("Test 1: Message Routing")
logger.message_routed("v2/orderbook", 1)
logger.message_routed("v2/trades", 1)
print()

# Test 2: Actor processing
print("Test 2: Actor Processing")
logger.actor_processing("OrderActor")
logger.actor_processing("PositionActor")
print()

# Test 3: Checking operations
print("Test 3: Checking Operations")
logger.checking_positions()
logger.checking_orders()
logger.checking_for_entry()
print()

# Test 4: System status
print("Test 4: System Status")
logger.position_tracker_active()
logger.order_manager_active()
logger.startup_notification_sent()
print()

# Test 5: Existing orders
print("Test 5: Existing Orders")
logger.existing_orders_found(2)
logger.existing_orders_found(8)
print()

# Test 6: Orders and fills (already working, but included for completeness)
print("Test 6: Orders and Fills")
logger.order_placed("order-123", "BUY", 42000)
logger.order_filled("order-123", "BUY", 42000)
logger.position_updated(5, 150.50)
print()

print("="*70)
print("✅ All narrative tests complete!")
print("If you see trader-style commentary above, narrative mode is working!")
print("="*70 + "\n")
