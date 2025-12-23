#!/usr/bin/env python3
"""
Fill Audit Log Viewer

Quick tool to check the bot's permanent memory of fill processing
Shows what fills were processed, when, and what actions were taken
"""

import sys
from pathlib import Path
from bot.strategy.modules.fill_audit_log import FillAuditLog

def main():
    # Initialize audit log
    audit_log = FillAuditLog()
    
    print("\n" + "="*80)
    print("📝 FILL AUDIT LOG - BOT'S PERMANENT MEMORY")
    print("="*80 + "\n")
    
    # Get statistics
    stats = audit_log.get_stats()
    
    print("📊 STATISTICS:")
    print(f"   Total Fills Processed: {stats['total']}")
    print(f"   Successful: {stats['success']}")
    print(f"   Failed: {stats['failed']}")
    if stats['total'] > 0:
        print(f"   Success Rate: {stats['success_rate']}")
    print(f"   Detection Methods: {stats['detection_methods']}")
    if 'cached_records' in stats:
        print(f"   Cached in Memory: {stats['cached_records']}")
    print()
    
    # Get recent fills
    recent_fills = audit_log.get_recent_fills(limit=20)
    
    if not recent_fills:
        print("⚠️  No fills found in audit log")
        print("   The bot hasn't processed any fills yet, or the log file doesn't exist.")
        return
    
    print(f"📋 RECENT FILLS (last {len(recent_fills)}):\n")
    
    for i, record in enumerate(recent_fills, 1):
        status = "✅" if record.success else "❌"
        
        print(f"{i}. {status} Order {record.order_id}")
        print(f"   {record.side.upper()} {record.fill_size} @ ${record.fill_price:,.2f} as {record.role.upper()}")
        print(f"   Detected: {record.detection_method} | Processed: {time.ctime(record.processed_at)}")
        
        if record.tp_order_placed:
            print(f"   ✅ TP Order: {record.tp_order_id} @ ${record.tp_price:,.2f}")
        else:
            print(f"   ❌ TP Order: NOT PLACED")
        
        if record.next_grid_placed:
            print(f"   ✅ Next Grid: {record.next_grid_order_id} @ ${record.next_grid_price:,.2f}")
        else:
            print(f"   ❌ Next Grid: NOT PLACED")
        
        if record.error_message:
            print(f"   ⚠️  Error: {record.error_message}")
        
        print()
    
    # Check for unfinished fills
    unfinished = audit_log.get_unfinished_fills()
    if unfinished:
        print("\n" + "="*80)
        print(f"⚠️  UNFINISHED FILLS ({len(unfinished)}) - NEED MANUAL INTERVENTION:")
        print("="*80 + "\n")
        
        for record in unfinished:
            print(f"Order {record.order_id}: {record.side.upper()} @ ${record.fill_price:,.2f}")
            print(f"   Error: {record.error_message}")
            print(f"   Retry Count: {record.retry_count}")
            print()

if __name__ == '__main__':
    import time
    main()
