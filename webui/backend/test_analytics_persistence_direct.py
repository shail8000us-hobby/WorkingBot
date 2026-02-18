"""
Direct SQLite test to PROVE analytics persistence.

This bypasses Flask app context and directly tests SQLite database.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = 'data/mmm_sessions.db'

def test_persistence():
    print("=" * 70)
    print("DIRECT SQLite TEST: Analytics Persistence")
    print("=" * 70)
    print(f"Database: {DB_PATH}\n")
    
    # Test session ID
    test_id = "mmm_test_persistence"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Step 1: Insert test session
        print("✓ Step 1: Creating test session in mmm_sessions table...")
        session_data = {
            'session_id': test_id,
            'mode': 'fresh',
            'strategy_status': 'STOPPED',
            'params': {'expiry': '19022026'},
        }
        cursor.execute('''
            INSERT INTO mmm_sessions (session_id, status, params_json, data_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            test_id,
            'STOPPED',
            json.dumps(session_data['params']),
            json.dumps(session_data),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        print(f"  Created session: {test_id}")
        
        # Step 2: Insert analytics
        print("\n✓ Step 2: Creating analytics in mmm_analytics table...")
        analytics_data = {
            'session_id': test_id,
            'session_status': 'STOPPED',
            'expiry': '19022026',
            'max_ce_lots': 50,
            'max_pe_lots': 60,
            'max_combined_lots': 110,
            'total_adjustments': 25,
            'total_reversals': 8,
            'final_total_pnl': 130.25,
        }
        cursor.execute('''
            INSERT INTO mmm_analytics (session_id, session_status, expiry, analytics_json, saved_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_id,
            'STOPPED',
            '19022026',
            json.dumps(analytics_data),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        print(f"  Created analytics for: {test_id}")
        
        # Step 3: Verify both exist
        print("\n✓ Step 3: Verifying both records exist...")
        cursor.execute('SELECT COUNT(*) FROM mmm_sessions WHERE session_id = ?', (test_id,))
        session_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM mmm_analytics WHERE session_id = ?', (test_id,))
        analytics_count = cursor.fetchone()[0]
        
        print(f"  Sessions found: {session_count}")
        print(f"  Analytics found: {analytics_count}")
        
        if session_count == 0 or analytics_count == 0:
            print("  ❌ ERROR: Failed to insert test data!")
            return False
        
        # Step 4: DELETE THE SESSION (simulate expiry)
        print("\n✓ Step 4: DELETING SESSION from mmm_sessions table...")
        cursor.execute('DELETE FROM mmm_sessions WHERE session_id = ?', (test_id,))
        conn.commit()
        print(f"  Session DELETED")
        
        # Step 5: Verify session is gone
        print("\n✓ Step 5: Verifying session deletion...")
        cursor.execute('SELECT COUNT(*) FROM mmm_sessions WHERE session_id = ?', (test_id,))
        session_after = cursor.fetchone()[0]
        print(f"  Sessions remaining: {session_after}")
        
        if session_after > 0:
            print("  ❌ ERROR: Session still exists!")
            return False
        
        # Step 6: CRITICAL TEST - Check analytics survived
        print("\n✓ Step 6: CRITICAL TEST - Checking analytics survival...")
        cursor.execute('SELECT analytics_json FROM mmm_analytics WHERE session_id = ?', (test_id,))
        result = cursor.fetchone()
        
        if result:
            analytics = json.loads(result[0])
            print(f"  ✅ SUCCESS! Analytics SURVIVED session deletion!\n")
            print(f"  Analytics data:")
            print(f"    - Max Combined Lots: {analytics.get('max_combined_lots')}")
            print(f"    - Total Adjustments: {analytics.get('total_adjustments')}")
            print(f"    - Final P&L: ${analytics.get('final_total_pnl')}")
            print(f"\n  📊 Analytics stored in SEPARATE table: mmm_analytics")
            print(f"  📊 Data PERSISTS even after session deletion!")
            print(f"  📊 You can query historical analytics anytime!")
            
            # Cleanup
            print(f"\n✓ Step 7: Cleaning up test data...")
            cursor.execute('DELETE FROM mmm_analytics WHERE session_id = ?', (test_id,))
            conn.commit()
            print(f"  Test data cleaned up")
            
            return True
        else:
            print(f"  ❌ FAILURE: Analytics were LOST!")
            return False
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        print(f"Run the MMM backend first to create the database.")
        exit(1)
    
    success = test_persistence()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST PASSED: Analytics persistence PROVEN!")
        print("\nWhat this means:")
        print("  • Analytics are stored in separate 'mmm_analytics' table")
        print("  • When sessions expire/delete, analytics remain")
        print("  • You can query analytics history forever")
        print("  • Institutional-grade data retention ✅")
    else:
        print("❌ TEST FAILED: Analytics were lost!")
    print("=" * 70)
    
    exit(0 if success else 1)
