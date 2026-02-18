"""
Test script to PROVE SQLite analytics persistence works.

This test:
1. Creates a test session with analytics
2. Saves analytics to SQLite
3. Deletes the session from mmm_sessions table
4. Proves analytics still exist in mmm_analytics table

Run: python3 test_analytics_persistence.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from routes.mmm.mmm_storage import get_storage
from routes.mmm.mmm_analytics_storage import get_analytics_storage
from routes.mmm.mmm_state import create_session

def test_persistence():
    print("=" * 70)
    print("TESTING: SQLite Analytics Persistence")
    print("=" * 70)
    
    # Step 1: Create a test session
    print("\n✓ Step 1: Creating test session...")
    test_params = {
        'expiry': '19022026',
        'initial_lots': 10,
    }
    session = create_session(mode='fresh', params=test_params)
    session_id = session['session_id']
    print(f"  Created session: {session_id}")
    
    # Step 2: Add some analytics data
    print("\n✓ Step 2: Adding analytics data...")
    session['analytics'] = {
        'session_start_time': '2026-02-18T07:00:00.000Z',
        'max_ce_lots': 50,
        'max_pe_lots': 60,
        'max_combined_lots': 110,
        'total_adjustments': 25,
        'total_reversals': 8,
        'total_shifts': 3,
        'final_realized_pnl': 125.50,
        'final_total_pnl': 130.25,
    }
    session['strategy_status'] = 'STOPPED'
    print(f"  Added analytics: {len(session['analytics'])} metrics")
    
    # Step 3: Save session to database
    print("\n✓ Step 3: Saving session to SQLite...")
    storage = get_storage()
    storage.save_session(session)
    print(f"  Session saved to mmm_sessions table")
    
    # Step 4: Save analytics to persistent storage
    print("\n✓ Step 4: Saving analytics to persistent storage...")
    analytics_storage = get_analytics_storage()
    analytics_storage.save_session_analytics(session)
    print(f"  Analytics saved to mmm_analytics table")
    
    # Step 5: Verify both exist
    print("\n✓ Step 5: Verifying both records exist...")
    session_check = storage.get_session(session_id)
    analytics_check = analytics_storage.get_session_analytics(session_id)
    print(f"  Session exists: {session_check is not None}")
    print(f"  Analytics exist: {analytics_check is not None}")
    
    # Step 6: DELETE THE SESSION (simulating expiry/deletion)
    print("\n✓ Step 6: DELETING SESSION (simulating expiry)...")
    storage.delete_session(session_id)
    print(f"  Session DELETED from mmm_sessions table")
    
    # Step 7: Verify session is gone
    print("\n✓ Step 7: Verifying session is deleted...")
    deleted_session = storage.get_session(session_id)
    print(f"  Session exists after deletion: {deleted_session is not None}")
    if deleted_session:
        print("  ❌ ERROR: Session still exists!")
        return False
    
    # Step 8: CRITICAL TEST - Analytics should still exist!
    print("\n✓ Step 8: CRITICAL TEST - Checking if analytics survived...")
    survived_analytics = analytics_storage.get_session_analytics(session_id)
    
    if survived_analytics:
        print(f"  ✅ SUCCESS! Analytics SURVIVED session deletion!")
        print(f"\n  Analytics data:")
        print(f"    - Max Combined Lots: {survived_analytics.get('max_combined_lots')}")
        print(f"    - Total Adjustments: {survived_analytics.get('total_adjustments')}")
        print(f"    - Final P&L: ${survived_analytics.get('final_total_pnl')}")
        print(f"    - Status: {survived_analytics.get('session_status')}")
        print(f"\n  📊 Analytics are stored in separate SQLite table!")
        print(f"  📊 Data PERSISTS even after session deletion!")
        
        # Cleanup
        print(f"\n✓ Step 9: Cleaning up test data...")
        analytics_storage.delete_analytics(session_id)
        print(f"  Test analytics deleted")
        
        return True
    else:
        print(f"  ❌ FAILURE: Analytics were LOST!")
        return False

if __name__ == '__main__':
    print(f"\nTest Location: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Database: data/mmm_sessions.db")
    print(f"Tables: mmm_sessions (sessions), mmm_analytics (analytics)\n")
    
    success = test_persistence()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST PASSED: Analytics persistence works correctly!")
    else:
        print("❌ TEST FAILED: Analytics were lost on session deletion!")
    print("=" * 70)
    
    sys.exit(0 if success else 1)
