#!/usr/bin/env python3
"""
Apply mutex lock fix to Windows testnet gridbot.py
Prevents race condition between fill handler and reconciliation
"""

import sys

# Path to Windows gridbot.py
WINDOWS_GRIDBOT = "/Volumes/D_Drive/Projects/WorkingBot/bot/strategy/gridbot.py"

# Read the file
try:
    with open(WINDOWS_GRIDBOT, 'r') as f:
        content = f.read()
    print(f"✅ Read {len(content)} bytes from {WINDOWS_GRIDBOT}")
except Exception as e:
    print(f"❌ Failed to read file: {e}")
    sys.exit(1)

# Old code without mutex lock
old_code = '''    def _on_fill_processed(self, fill_data: Dict):
        """
        Handle processed fill
        
        This is called by FillDetector after deduplication.
        Delegates to business logic for TP placement and next order.
        Supports both LONG and SHORT modes.
        """
        try:
            order_id = fill_data.get('order_id')'''

# New code with mutex lock
new_code = '''    def _on_fill_processed(self, fill_data: Dict):
        """
        Handle processed fill
        
        This is called by FillDetector after deduplication.
        Delegates to business logic for TP placement and next order.
        Supports both LONG and SHORT modes.
        
        🔒 CRITICAL FIX NOV 7: Uses position manager's state lock to prevent
        race condition between fill processing and heartbeat reconciliation.
        """
        # 🔒 CRITICAL: Acquire lock to prevent concurrent reconciliation during fill processing
        with self.position_mgr.state_lock:
            try:
                order_id = fill_data.get('order_id')'''

# Apply the fix
if old_code in content:
    new_content = content.replace(old_code, new_code)
    
    # Also need to update the closing of try block to match new indentation
    # Find the exception handler and fix indentation
    old_except = '''        except Exception as e:
            log.error(f"Error processing fill: {e}")
            import traceback
            log.error(traceback.format_exc())'''
    
    new_except = '''            except Exception as e:
                log.error(f"Error processing fill: {e}")
                import traceback
                log.error(traceback.format_exc())'''
    
    new_content = new_content.replace(old_except, new_except)
    
    # Write back
    try:
        with open(WINDOWS_GRIDBOT, 'w') as f:
            f.write(new_content)
        print(f"✅ Applied mutex lock fix to Windows gridbot.py")
        print(f"   Added 'with self.position_mgr.state_lock:' to _on_fill_processed()")
        print(f"   Fixed indentation for exception handler")
    except Exception as e:
        print(f"❌ Failed to write file: {e}")
        sys.exit(1)
else:
    print(f"⚠️ Could not find expected code pattern - file may already be fixed or different version")
    print(f"   Searching for '_on_fill_processed' method...")
    if '_on_fill_processed' in content:
        print(f"   Found method - may already have fix applied")
    else:
        print(f"   ❌ Method not found!")
