#!/usr/bin/env python3
"""
Test & Demonstration of HumanLogger Narrative Engine
Shows the new narrative-driven logging in action with simulated scenarios.
"""

import time
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.utils.human_logger import HumanLogger, Mood, MarketTempo

def print_section(title: str):
    """Print a section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def scenario_1_startup_to_tp():
    """
    Scenario 1: Startup → First Order → Fill → TP
    
    Expected narrative flow:
    - Bot starts up
    - Places first BUY order
    - Gets filled
    - Hits take profit
    """
    print_section("SCENARIO 1: Startup → First Order → Fill → TP")
    
    logger = HumanLogger(rate_limit_seconds=0.5, narrative_mode=True)
    
    # Startup
    logger.bot_started_successfully()
    time.sleep(0.6)
    
    # Place first order
    logger.order_placed("ORD-001", "BUY", 50000.0)
    time.sleep(0.6)
    
    # Order filled
    logger.order_filled("ORD-001", "BUY", 50000.0)
    time.sleep(0.6)
    
    # Position updated
    logger.position_updated(size=1, pnl=50.0)
    time.sleep(0.6)
    
    # TP hit (simulated as sell fill)
    logger.order_placed("ORD-002", "SELL", 50250.0)
    time.sleep(0.6)
    logger.order_filled("ORD-002", "SELL", 50250.0)
    time.sleep(0.6)
    
    # Final position
    logger.position_updated(size=0, pnl=250.0)
    
    print(f"\n📊 Final State: Mood={logger._mood.value}, Fills={logger._orders_filled}")


def scenario_2_connection_lost_reconnect():
    """
    Scenario 2: Connection Lost → Reconnect → Authentication → Subscription → Resume
    
    Expected narrative flow:
    - Connection drops
    - Reconnection starts
    - Authentication successful
    - Subscriptions restored
    - Connection confirmed stable
    """
    print_section("SCENARIO 2: Connection Lost → Reconnect → Resume")
    
    logger = HumanLogger(rate_limit_seconds=0.5, narrative_mode=True)
    
    # Connection lost
    logger.disconnected()
    time.sleep(0.6)
    
    # Reconnecting
    logger.reconnecting()
    time.sleep(0.6)
    
    # Authenticated
    logger.websocket_authenticated()
    time.sleep(0.6)
    
    # Subscriptions active
    logger.subscriptions_active(["trades", "positions", "orders"])
    time.sleep(0.6)
    
    # Connection stable - completes the arc
    logger.connection_stable()
    
    print(f"\n📊 Final State: Mood={logger._mood.value}, In Arc={logger._in_reconnect_arc}")


def scenario_3_rapid_fills():
    """
    Scenario 3: Rapid BUY/SELL Fills
    
    Expected narrative flow:
    - Multiple orders placed quickly
    - Fills coming in fast
    - Bot enters EXCITED/AGGRESSIVE mood
    - Market tempo becomes CHOPPY
    - Special "rapid fills" narrative triggered
    """
    print_section("SCENARIO 3: Rapid BUY/SELL Fills")
    
    logger = HumanLogger(rate_limit_seconds=0.5, narrative_mode=True)
    
    prices = [49000, 49500, 50000, 50500, 51000]
    
    for i, price in enumerate(prices):
        # Place order
        logger.order_placed(f"ORD-{i:03d}", "BUY", price)
        time.sleep(0.3)
        
        # Quick fill
        logger.order_filled(f"ORD-{i:03d}", "BUY", price)
        time.sleep(0.3)
        
        # Update position
        logger.position_updated(size=i+1, pnl=(i+1)*50.0)
        time.sleep(0.3)
    
    # Price update in excited mood
    logger.price_data_flowing(price=51000.0)
    
    print(f"\n📊 Final State: Mood={logger._mood.value}, Tempo={logger._market_tempo.value}, "
          f"Fills={logger._orders_filled}, Streak={logger._fill_streak}")


def scenario_4_warnings_to_recovery():
    """
    Scenario 4: Multiple Warnings → Recovery
    
    Expected narrative flow:
    - Price update delayed
    - API slow response
    - Handler failure
    - Bot enters ALERT/STRESSED mood
    - Eventually recovers with fill
    - Error streak resets
    """
    print_section("SCENARIO 4: Multiple Warnings → Recovery")
    
    logger = HumanLogger(rate_limit_seconds=0.5, narrative_mode=True)
    
    # Warning 1: Price delayed
    logger.price_delayed(seconds=8.0)
    time.sleep(0.6)
    
    # Warning 2: Slow API
    logger.slow_response("place_order", duration=3.5)
    time.sleep(0.6)
    
    # Warning 3: Queue growing
    logger.queue_growing("order_queue", size=15)
    time.sleep(0.6)
    
    print(f"Current mood: {logger._mood.value}, Error streak: {logger._error_streak}")
    
    # Error: Handler failed
    logger.handler_failed("price_handler", "Timeout after 10s")
    time.sleep(0.6)
    
    # Another error
    logger.api_error("get_positions", "503 Service Unavailable")
    time.sleep(0.6)
    
    print(f"Stressed mood: {logger._mood.value}, Error streak: {logger._error_streak}")
    
    # Recovery: Price updates start flowing
    logger.price_data_flowing(price=50000.0)
    time.sleep(0.6)
    
    # Successful fill - resets error streak
    logger.order_placed("ORD-RECOVERY", "BUY", 50000.0)
    time.sleep(0.6)
    logger.order_filled("ORD-RECOVERY", "BUY", 50000.0)
    
    print(f"\n📊 Final State: Mood={logger._mood.value}, Error streak={logger._error_streak}, "
          f"Recovered={logger._error_streak == 0}")


def scenario_5_extended_session():
    """
    Scenario 5: Extended Trading Session with Mixed Events
    
    Shows how narratives evolve over a longer session with:
    - Multiple orders (milestone commentary)
    - Mix of fills and warnings
    - Mood transitions
    - Template rotation
    """
    print_section("SCENARIO 5: Extended Trading Session (10 Orders)")
    
    logger = HumanLogger(rate_limit_seconds=0.3, narrative_mode=True)
    
    base_price = 50000
    
    for i in range(10):
        order_id = f"ORD-{i:03d}"
        side = "BUY" if i % 3 != 2 else "SELL"
        price = base_price + (i * 100) if side == "BUY" else base_price + (i * 100) + 250
        
        # Place order
        logger.order_placed(order_id, side, price)
        time.sleep(0.4)
        
        # Occasional warnings
        if i % 4 == 2:
            logger.price_delayed(seconds=5.0)
            time.sleep(0.4)
        
        # Fill order
        logger.order_filled(order_id, side, price)
        time.sleep(0.4)
        
        # Show milestone commentary on 5th and 10th fills
        if i == 4 or i == 9:
            print(f"\n  >>> Milestone reached: {i+1} fills! <<<")
        
        time.sleep(0.2)
    
    print(f"\n📊 Final State:")
    print(f"   Orders placed: {logger._orders_placed}")
    print(f"   Orders filled: {logger._orders_filled}")
    print(f"   Current mood: {logger._mood.value}")
    print(f"   Market tempo: {logger._market_tempo.value}")
    print(f"   Consecutive BUYs: {logger._consecutive_buys}")
    print(f"   Memory size: {len(logger._event_memory)} events")


def main():
    """Run all test scenarios"""
    print("\n" + "🎭 "*25)
    print("   HUMAN LOGGER NARRATIVE ENGINE - TEST SUITE")
    print("🎭 "*25)
    
    try:
        # Run all scenarios
        scenario_1_startup_to_tp()
        time.sleep(1)
        
        scenario_2_connection_lost_reconnect()
        time.sleep(1)
        
        scenario_3_rapid_fills()
        time.sleep(1)
        
        scenario_4_warnings_to_recovery()
        time.sleep(1)
        
        scenario_5_extended_session()
        
        print("\n" + "="*70)
        print("  ✅ ALL SCENARIOS COMPLETED SUCCESSFULLY")
        print("="*70 + "\n")
        
        print("🎬 The narrative engine transforms raw events into trader-style commentary!")
        print("💬 Logs now tell a story instead of just listing facts.")
        print("🧠 Context, mood, and memory make logs feel human.")
        print("\n✨ Upgrade complete! The bot can now narrate its journey. ✨\n")
        
    except Exception as e:
        print(f"\n❌ Error running scenarios: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
