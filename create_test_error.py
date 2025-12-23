#!/usr/bin/env python3
"""
Create a test error to verify Error Intelligence display
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import uuid

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "errors.db"

def create_test_error():
    """Create a realistic test error"""
    
    error_id = str(uuid.uuid4())
    
    error_data = {
        'id': error_id,
        'code': 'ORDER_PLACEMENT_FAILED',
        'source': 'trading',
        'severity': 'high',
        'status': 'open',  # IMPORTANT: Must be 'open' to show in UI
        'message_raw': 'Failed to place buy order at 64500.0 - Insufficient margin',
        'title': 'Order Placement Failed',
        'explanation': 'The bot attempted to place a buy order but was rejected due to insufficient margin. This prevents new grid orders from being created.',
        'likely_causes': json.dumps([
            'Account balance too low for required margin',
            'Leverage settings causing higher margin requirements',
            'Open positions consuming available margin',
            'Price movement requiring more margin than available'
        ]),
        'suggested_actions': json.dumps([
            'Check account balance and free margin',
            'Reduce grid size or number of active grids',
            'Close some existing positions to free margin',
            'Add funds to the account'
        ]),
        'can_auto_fix': False,
        'available_fixes': json.dumps([
            {
                'id': 'reduce_grid_size',
                'title': 'Reduce Grid Size',
                'description': 'Automatically reduce the number of grid levels to lower margin requirements',
                'requires_confirmation': True,
                'is_destructive': True,
                'is_dry_runnable': True,
                'estimated_duration_sec': 10,
                'preconditions': ['Bot must be running', 'Config file must be writable'],
                'side_effects': ['Fewer grid levels', 'Lower potential profit', 'Existing orders will be cancelled']
            },
            {
                'id': 'emergency_close_positions',
                'title': 'Close Oldest Positions',
                'description': 'Close the 2 oldest positions to free up margin',
                'requires_confirmation': True,
                'is_destructive': True,
                'is_dry_runnable': False,
                'estimated_duration_sec': 5,
                'preconditions': ['Open positions exist', 'Market is active'],
                'side_effects': ['Positions closed at market price', 'May realize loss', 'Margin freed immediately']
            }
        ]),
        'first_seen': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'occurrence_count': 1,
        'context': json.dumps({
            'trading_mode': 'demo',
            'price': 64500.0,
            'order_type': 'BUY',
            'required_margin': 250.0,
            'available_margin': 180.0,
            'classified_at': datetime.now().isoformat()
        }),
        'links': json.dumps([
            {'title': 'Margin Requirements Guide', 'url': '/docs/margin'},
            {'title': 'Grid Configuration', 'url': '/docs/grid-config'},
            {'title': 'Troubleshooting', 'url': '/docs/troubleshooting'}
        ]),
        'signature': f"trading:ORDER_PLACEMENT_FAILED:{hash('Insufficient margin')}"
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO errors (
            id, code, source, severity, status, message_raw,
            title, explanation, likely_causes, suggested_actions,
            can_auto_fix, available_fixes, first_seen, last_seen,
            occurrence_count, context, links, signature
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        error_data['id'],
        error_data['code'],
        error_data['source'],
        error_data['severity'],
        error_data['status'],
        error_data['message_raw'],
        error_data['title'],
        error_data['explanation'],
        error_data['likely_causes'],
        error_data['suggested_actions'],
        error_data['can_auto_fix'],
        error_data['available_fixes'],
        error_data['first_seen'],
        error_data['last_seen'],
        error_data['occurrence_count'],
        error_data['context'],
        error_data['links'],
        error_data['signature']
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created test error:")
    print(f"   ID: {error_id}")
    print(f"   Code: {error_data['code']}")
    print(f"   Severity: {error_data['severity']}")
    print(f"   Status: {error_data['status']}")
    print(f"   Message: {error_data['message_raw']}")
    print(f"\nRefresh WebUI to see it appear in Error Intelligence Panel!")

if __name__ == '__main__':
    create_test_error()
