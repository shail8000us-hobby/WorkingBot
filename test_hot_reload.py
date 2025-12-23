#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.loader import get_config, reload_config
from bot.guardian.engine.risk_decision_engine import GuardianRiskDecisionEngine
from bot.strategy.modules.event_store import EventStore

def test_config_hash_calculation():
    print("=" * 80)
    print("Testing Hot Reload Configuration Hash Calculation")
    print("=" * 80)
    
    config = get_config()
    
    print("\n1. Loading configuration...")
    print(f"   Trading Mode: {config.trading_mode}")
    print(f"   Bot Mode: {config.bot.mode}")
    
    print("\n2. Checking volatility parameters...")
    print(f"   Max IV: {config.safety.volatility.max_iv}%")
    print(f"   Max RV: {config.safety.volatility.max_rv}%")
    print(f"   Max Spread: {config.safety.volatility.max_spread}%")
    
    print("\n3. Checking guardian parameters...")
    print(f"   Max Loss: ₹{config.guardian.max_account_loss_inr}")
    print(f"   Check Interval: {config.guardian.check_interval}s")
    
    print("\n4. Checking grid parameters...")
    print(f"   Max Open Positions: {config.grid.limits.max_open_positions}")
    print(f"   Grid Lower: ${config.grid.geometry.lower}")
    print(f"   Grid Upper: ${config.grid.geometry.upper}")
    print(f"   Grid Step: ${config.grid.geometry.step}")
    
    print("\n5. Checking liquidation protection...")
    print(f"   Min Liquidation Distance: {config.liquidation_protection.liquidation_distance_min}%")
    
    print("\n6. Checking opportunistic recovery...")
    print(f"   Enabled: {config.safety.volatility.opportunistic_recovery.enabled}")
    print(f"   IV Threshold: {config.safety.volatility.opportunistic_recovery.iv_threshold}%")
    print(f"   RV Threshold: {config.safety.volatility.opportunistic_recovery.rv_threshold}%")
    
    print("\n7. Initializing EventStore...")
    mode = config.bot.mode
    db_path = f"data/bot_events_{mode}.db"
    event_store = EventStore(db_path=db_path)
    print(f"   EventStore initialized for mode: {mode}")
    print(f"   Database: {db_path}")
    
    print("\n8. Creating Risk Decision Engine...")
    try:
        engine = GuardianRiskDecisionEngine(event_store)
        print(f"   ✅ Risk Decision Engine created successfully")
        print(f"   Config Hash: {engine.config_hash}")
        
        if engine.config_hash == "error":
            print("   ❌ ERROR: Config hash calculation failed!")
            print("   This means hot reload will NOT work.")
            return False
        else:
            print("   ✅ Config hash calculated successfully")
            print("   Hot reload should work correctly")
            
    except Exception as e:
        print(f"   ❌ ERROR: Failed to create Risk Decision Engine: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n9. Testing config reload...")
    try:
        new_config = reload_config()
        print("   ✅ Config reloaded successfully")
        
        engine2 = GuardianRiskDecisionEngine(event_store)
        new_hash = engine2.config_hash
        print(f"   New Config Hash: {new_hash}")
        
        if new_hash == engine.config_hash:
            print("   ✅ Hash matches (config unchanged)")
        else:
            print("   ⚠️  Hash changed (config was modified)")
            
    except Exception as e:
        print(f"   ❌ ERROR: Failed to reload config: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Hot Reload Should Work!")
    print("=" * 80)
    print("\nTo test hot reload manually:")
    print("1. Start Guardian: pm2 start guardian-live")
    print("2. Watch logs: pm2 logs guardian-live --lines 50")
    print("3. Change config in WebUI (e.g., max_iv from 55 to 60)")
    print("4. Save configuration")
    print("5. Check logs for: '📝 Config file changed - reloading risk parameters...'")
    print()
    
    return True

if __name__ == "__main__":
    success = test_config_hash_calculation()
    sys.exit(0 if success else 1)
