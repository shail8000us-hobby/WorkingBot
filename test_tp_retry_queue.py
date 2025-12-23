#!/usr/bin/env python3
"""
Test TP Retry Queue Feature

Verifies that the TP retry queue functionality works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger as log
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.modules.event_store import EventStore


async def test_tp_retry_queue():
    """Test TP retry queue functionality"""
    
    log.info("=" * 80)
    log.info("🧪 Testing TP Retry Queue Feature")
    log.info("=" * 80)
    
    # Initialize event store
    event_store = EventStore("test_tp_retry.db")
    
    # Initialize position actor
    position_actor = PositionManagerActor(event_store, max_positions=5)
    
    # Start actor
    log.info("\n1️⃣ Starting position actor...")
    await position_actor.start()
    log.info("✅ Position actor started")
    
    # Test 1: Schedule TP retry
    log.info("\n2️⃣ Scheduling TP retry...")
    test_position = {
        "position_id": "test_pos_1",
        "entry_price": 100000,
        "tp_price": 100500,
        "size": 1
    }
    
    result = await position_actor.ask("SCHEDULE_TP_RETRY", {
        "position": test_position,
        "retry_count": 0,
        "max_retries": 5
    }, timeout=5.0)
    
    log.info(f"✅ TP retry scheduled: {result}")
    
    # Test 2: Get retry queue size
    log.info("\n3️⃣ Checking retry queue size...")
    queue_result = await position_actor.ask("GET_RETRY_QUEUE_SIZE", {}, timeout=5.0)
    log.info(f"✅ Queue size: {queue_result.get('queue_size')}")
    
    assert queue_result.get("queue_size") == 1, "Queue size should be 1"
    
    # Test 3: Get due retries (should not be due yet, scheduled for +10s)
    log.info("\n4️⃣ Checking due retries (should be empty - not due yet)...")
    due_result = await position_actor.ask("GET_DUE_RETRIES", {}, timeout=5.0)
    log.info(f"✅ Due retries: {due_result.get('due_count')} / {due_result.get('total_queue_size')}")
    
    assert due_result.get("due_count") == 0, "No retries should be due yet"
    assert due_result.get("total_queue_size") == 1, "Total queue should have 1 entry"
    
    # Test 4: Wait for retry to become due
    log.info("\n5️⃣ Waiting 11 seconds for retry to become due...")
    await asyncio.sleep(11)
    
    due_result = await position_actor.ask("GET_DUE_RETRIES", {}, timeout=5.0)
    log.info(f"✅ Due retries after wait: {due_result.get('due_count')} / {due_result.get('total_queue_size')}")
    
    assert due_result.get("due_count") == 1, "1 retry should now be due"
    
    # Test 5: Remove from retry queue
    log.info("\n6️⃣ Removing from retry queue...")
    retry_entry = due_result.get("retries", [])[0]
    remove_result = await position_actor.ask("REMOVE_FROM_RETRY_QUEUE", {
        "retry_entry": retry_entry
    }, timeout=5.0)
    
    log.info(f"✅ Removed from queue: {remove_result}")
    
    assert remove_result.get("removed") == True, "Entry should be removed"
    
    # Test 6: Verify queue is empty
    log.info("\n7️⃣ Verifying queue is empty...")
    queue_result = await position_actor.ask("GET_RETRY_QUEUE_SIZE", {}, timeout=5.0)
    log.info(f"✅ Final queue size: {queue_result.get('queue_size')}")
    
    assert queue_result.get("queue_size") == 0, "Queue should be empty"
    
    # Stop actor
    log.info("\n8️⃣ Stopping position actor...")
    await position_actor.stop()
    log.info("✅ Position actor stopped")
    
    log.info("\n" + "=" * 80)
    log.info("✅ ALL TESTS PASSED! TP Retry Queue is working correctly!")
    log.info("=" * 80)


async def test_multiple_retries():
    """Test multiple retry entries"""
    
    log.info("\n" + "=" * 80)
    log.info("🧪 Testing Multiple TP Retries")
    log.info("=" * 80)
    
    # Initialize event store
    event_store = EventStore("test_tp_retry_multi.db")
    
    # Initialize position actor
    position_actor = PositionManagerActor(event_store, max_positions=5)
    
    # Start actor
    log.info("\n1️⃣ Starting position actor...")
    await position_actor.start()
    
    # Schedule multiple retries
    log.info("\n2️⃣ Scheduling 3 TP retries...")
    for i in range(3):
        test_position = {
            "position_id": f"test_pos_{i+1}",
            "entry_price": 100000 + (i * 500),
            "tp_price": 100500 + (i * 500),
            "size": 1
        }
        
        await position_actor.tell("SCHEDULE_TP_RETRY", {
            "position": test_position,
            "retry_count": 0,
            "max_retries": 5
        })
        log.info(f"   ✅ Scheduled retry {i+1}/3")
    
    # Check queue size
    log.info("\n3️⃣ Checking queue size...")
    queue_result = await position_actor.ask("GET_RETRY_QUEUE_SIZE", {}, timeout=5.0)
    log.info(f"✅ Queue size: {queue_result.get('queue_size')}")
    
    assert queue_result.get("queue_size") == 3, "Queue should have 3 entries"
    
    # Wait for all to become due
    log.info("\n4️⃣ Waiting for all retries to become due...")
    await asyncio.sleep(11)
    
    due_result = await position_actor.ask("GET_DUE_RETRIES", {}, timeout=5.0)
    log.info(f"✅ Due retries: {due_result.get('due_count')} / {due_result.get('total_queue_size')}")
    
    assert due_result.get("due_count") == 3, "All 3 retries should be due"
    
    # Process all
    log.info("\n5️⃣ Processing all due retries...")
    for retry_entry in due_result.get("retries", []):
        position = retry_entry.get("position", {})
        log.info(f"   Processing: {position.get('position_id')}")
        
        await position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
            "retry_entry": retry_entry
        })
    
    # Verify empty
    log.info("\n6️⃣ Verifying queue is empty...")
    await asyncio.sleep(1)  # Give time for tells to process
    queue_result = await position_actor.ask("GET_RETRY_QUEUE_SIZE", {}, timeout=5.0)
    log.info(f"✅ Final queue size: {queue_result.get('queue_size')}")
    
    assert queue_result.get("queue_size") == 0, "Queue should be empty"
    
    # Stop actor
    await position_actor.stop()
    
    log.info("\n" + "=" * 80)
    log.info("✅ ALL MULTI-RETRY TESTS PASSED!")
    log.info("=" * 80)


async def main():
    """Run all tests"""
    try:
        # Test 1: Basic functionality
        await test_tp_retry_queue()
        
        # Test 2: Multiple retries
        await test_multiple_retries()
        
        log.info("\n" + "🎉" * 40)
        log.info("🎉 ALL TP RETRY QUEUE TESTS PASSED!")
        log.info("🎉" * 40)
        
        return 0
    
    except Exception as e:
        log.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
