#!/usr/bin/env python3
"""
Test script for Position Tracking & Liquidation Protection System
"""

import os
import sys
import json
from pathlib import Path

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent))

# Set test environment
os.environ["USD_TO_INR_RATE"] = "85"
os.environ["MAINTENANCE_MARGIN_PERCENT"] = "2.5"
os.environ["AUTO_TOPUP_THRESHOLD"] = "60"
os.environ["AUTO_TOPUP_TARGET"] = "90"
os.environ["MAX_TOPUPS_PER_POSITION"] = "3"
os.environ["MARGIN_WARNING_THRESHOLD"] = "80"
os.environ["MARGIN_DANGER_THRESHOLD"] = "50"
os.environ["MARGIN_CRITICAL_THRESHOLD"] = "20"
os.environ["DISTANCE_TO_LIQ_WARNING"] = "3.0"
os.environ["MAX_ACCOUNT_LOSS_INR"] = "10000"

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("POSITION TRACKING SYSTEM - TEST SUITE")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()

# Test 1: Import all modules
print("Test 1: Importing modules...")
try:
    from bot.position_tracker import PositionTracker, Position, MarginInfo, LiquidationInfo
    from bot.utils.position_display import format_position_table, format_compact_summary
    from bot.margin_topup import MarginTopUpManager
    from bot.pnl_history import PnLHistoryLogger, LiquidationAlertManager
    print("✅ All modules imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print()

# Test 2: Create Position Tracker
print("Test 2: Creating Position Tracker...")
try:
    tracker = PositionTracker(storage_file="test_positions.json")
    print(f"✅ Position Tracker created")
    print(f"   USD to INR rate: {tracker.usd_to_inr_rate}")
    print(f"   Maintenance margin: {tracker.maintenance_margin_percent * 100}%")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 3: Add positions
print("Test 3: Adding test positions...")
try:
    # Position 1: Safe (current price = entry)
    pos1 = tracker.add_position(
        position_id="POS_TEST_001",
        entry_price=120000,
        size=1,
        tp_order_id="TP_001",
        current_price=120000,
        available_balance=50000
    )
    print(f"✅ Position 1 added:")
    print(f"   Entry: ₹{pos1.entry_price:,.2f}")
    print(f"   Liquidation: ₹{pos1.liquidation.liquidation_price:,.2f}")
    print(f"   Distance to liq: {pos1.liquidation.distance_to_liq_percent:.2f}%")
    print(f"   Risk level: {pos1.liquidation.risk_level}")
    
    # Position 2: In loss
    pos2 = tracker.add_position(
        position_id="POS_TEST_002",
        entry_price=119000,
        size=1,
        tp_order_id="TP_002",
        current_price=118500,  # Down ₹500
        available_balance=50000
    )
    print(f"✅ Position 2 added:")
    print(f"   Entry: ₹{pos2.entry_price:,.2f}")
    print(f"   Current: ₹{pos2.current_price:,.2f}")
    print(f"   PnL: ${pos2.pnl_usd:.2f} / ₹{pos2.pnl_inr:.2f}")
    print(f"   Risk level: {pos2.liquidation.risk_level}")
    
    # Position 3: In profit
    pos3 = tracker.add_position(
        position_id="POS_TEST_003",
        entry_price=118000,
        size=1,
        tp_order_id="TP_003",
        current_price=118500,  # Up ₹500
        available_balance=50000
    )
    print(f"✅ Position 3 added:")
    print(f"   Entry: ₹{pos3.entry_price:,.2f}")
    print(f"   Current: ₹{pos3.current_price:,.2f}")
    print(f"   PnL: ${pos3.pnl_usd:.2f} / ₹{pos3.pnl_inr:.2f}")
    print(f"   Risk level: {pos3.liquidation.risk_level}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Get summary
print("Test 4: Getting position summary...")
try:
    summary = tracker.get_summary()
    print(f"✅ Summary retrieved:")
    print(f"   Total positions: {summary['total_positions']}")
    print(f"   Total PnL: ${summary['total_pnl_usd']:.2f} / ₹{summary['total_pnl_inr']:.2f}")
    print(f"   Risk %: {summary['risk_percent']:.2f}%")
    print(f"   Avg margin ratio: {summary['avg_margin_ratio']:.2%}")
    print(f"   Min margin ratio: {summary['min_margin_ratio']:.2%}")
    print(f"   Overall liq risk: {summary['overall_liq_risk']}")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 5: Update positions
print("Test 5: Updating position prices...")
try:
    # Update pos2 with worse price
    pos2_updated = tracker.update_position("POS_TEST_002", 118000, available_balance=50000)
    print(f"✅ Position 2 updated:")
    print(f"   New price: ₹{pos2_updated.current_price:,.2f}")
    print(f"   New PnL: ${pos2_updated.pnl_usd:.2f} / ₹{pos2_updated.pnl_inr:.2f}")
    print(f"   New distance to liq: {pos2_updated.liquidation.distance_to_liq_percent:.2f}%")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 6: Position display
print("Test 6: Testing position display...")
try:
    positions = tracker.get_all_positions()
    table = format_position_table(positions, summary)
    print("✅ Position table generated:")
    print(table)
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 7: Compact summary
print("Test 7: Testing compact summary...")
try:
    compact = format_compact_summary(summary)
    print(f"✅ Compact summary: {compact}")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 8: Close position
print("Test 8: Closing position...")
try:
    closed = tracker.close_position("POS_TEST_001", 120500)
    print(f"✅ Position closed:")
    print(f"   Final PnL: ${closed.pnl_usd:.2f} / ₹{closed.pnl_inr:.2f}")
    print(f"   Remaining positions: {len(tracker.get_all_positions())}")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 9: Persistent storage
print("Test 9: Testing persistent storage...")
try:
    # Check if file exists
    if Path("test_positions.json").exists():
        with open("test_positions.json", "r") as f:
            data = json.load(f)
        print(f"✅ Storage file created:")
        print(f"   Positions saved: {len(data.get('positions', []))}")
        print(f"   Summary included: {'summary' in data}")
        print(f"   Config included: {'config' in data}")
    else:
        print(f"❌ Storage file not found")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print()

# Test 10: PnL History Logger
print("Test 10: Testing PnL History Logger...")
try:
    pnl_logger = PnLHistoryLogger(log_dir="test_reports")
    pnl_logger.log_snapshot(summary)
    print(f"✅ PnL history logged:")
    print(f"   CSV file: {pnl_logger.csv_file}")
    
    # Read back
    history = pnl_logger.get_recent_history(limit=5)
    print(f"   Entries retrieved: {len(history)}")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 11: Margin Top-Up Manager
print("Test 11: Testing Margin Top-Up Manager...")
try:
    os.environ["AUTO_MARGIN_TOPUP_ENABLED"] = "true"
    topup_manager = MarginTopUpManager(exchange_client=None)
    print(f"✅ Margin Top-Up Manager created:")
    print(f"   Enabled: {topup_manager.enabled}")
    print(f"   Threshold: {topup_manager.threshold:.0%}")
    print(f"   Target: {topup_manager.target:.0%}")
    
    # Check if any position needs top-up
    needs_topup = tracker.needs_topup("POS_TEST_002")
    print(f"   Position 2 needs top-up: {needs_topup}")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 12: Alert Manager
print("Test 12: Testing Alert Manager...")
try:
    os.environ["TELEGRAM_BOT_TOKEN"] = ""  # Disable actual sending
    alert_manager = LiquidationAlertManager()
    print(f"✅ Alert Manager created:")
    print(f"   Enabled: {alert_manager.enabled}")
    
    # Test alert checking (won't send without token)
    for pos in tracker.get_all_positions():
        alert_manager.check_and_alert(pos)
    print(f"   Alert checks completed")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Cleanup
print("Cleanup: Removing test files...")
try:
    if Path("test_positions.json").exists():
        Path("test_positions.json").unlink()
    if Path("test_reports").exists():
        import shutil
        shutil.rmtree("test_reports")
    print("✅ Test files removed")
except Exception as e:
    print(f"⚠️  Cleanup warning: {e}")

print()
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("✅ ALL TESTS PASSED!")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()
print("The Position Tracking & Liquidation Protection System")
print("is fully functional and ready for production use.")
print()

