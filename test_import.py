#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

try:
    from bot.strategy.actors.position_actor import PositionManagerActor
    print("✅ PositionActor imports successfully")
    
    # Check if validate method exists
    if hasattr(PositionManagerActor, 'validate_state_against_exchange'):
        print("✅ validate_state_against_exchange method exists")
    else:
        print("❌ validate_state_against_exchange method NOT found")
        
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
