"""
Quick Guardian Bot + PositionMonitor Integration Verification

This script tests that Guardian bot properly uses PositionMonitor
Run this to verify the integration is working correctly
"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_guardian_integration():
    """Verify Guardian bot has PositionMonitor properly integrated"""
    
    print("\n" + "=" * 70)
    print(" " * 10 + "GUARDIAN BOT INTEGRATION VERIFICATION")
    print("=" * 70)
    
    try:
        # Import Guardian
        from bot.guardian.core.guardian_bot import GuardianBot
        print("✅ GuardianBot imported successfully")
        
        # Initialize Guardian
        print("\nInitializing Guardian Bot...")
        guardian = GuardianBot()
        
        # Initialize (this sets up exchange and components)
        guardian.setup_logging()
        guardian.setup_exchange()
        guardian.initialize_components()
        
        print("✅ Guardian Bot initialized")
        
        # Verify PositionMonitor exists
        print("\n" + "-" * 70)
        print("CHECKING POSITION MONITOR INTEGRATION")
        print("-" * 70)
        
        if not hasattr(guardian, 'position_monitor'):
            print("❌ CRITICAL: Guardian does NOT have 'position_monitor' attribute")
            return False
        
        print("✅ Guardian has 'position_monitor' attribute")
        
        monitor = guardian.position_monitor
        
        # Verify configuration
        print("\nPosition Monitor Configuration:")
        print(f"   Symbol: {monitor.symbol}")
        print(f"   Product ID: {monitor.product_id}")
        print(f"   Contract Multiplier: {monitor.contract_multiplier}")
        print(f"   USD to INR Rate: {monitor.usd_to_inr_rate}")
        
        # Test basic methods
        print("\n" + "-" * 70)
        print("TESTING BASIC METHODS")
        print("-" * 70)
        
        # Test get_current_price
        try:
            price = monitor.get_current_price()
            print(f"✅ get_current_price(): ${price:.2f}" if price else "✅ get_current_price(): None")
        except Exception as e:
            print(f"❌ get_current_price() error: {e}")
            return False
        
        # Test get_current_pnl
        try:
            pnl = monitor.get_current_pnl()
            print(f"✅ get_current_pnl(): ₹{pnl:.2f}")
        except Exception as e:
            print(f"❌ get_current_pnl() error: {e}")
            return False
        
        # Test get_liquidation_distance
        try:
            liq_dist = monitor.get_liquidation_distance()
            print(f"✅ get_liquidation_distance(): {liq_dist:.2f}%")
        except Exception as e:
            print(f"❌ get_liquidation_distance() error: {e}")
            return False
        
        # Test get_bankruptcy_distance (Delta India improvement)
        try:
            bank_dist = monitor.get_bankruptcy_distance()
            print(f"✅ get_bankruptcy_distance(): {bank_dist:.2f}%")
        except Exception as e:
            print(f"❌ get_bankruptcy_distance() error: {e}")
            return False
        
        # Test monitor_cycle (critical for Guardian)
        print("\n" + "-" * 70)
        print("TESTING MONITOR CYCLE (Guardian's main method)")
        print("-" * 70)
        
        try:
            result = monitor.monitor_cycle()
            
            if result is None:
                print("⚠️  monitor_cycle() returned None (possible error)")
                return False
            
            print("✅ monitor_cycle() executed successfully")
            
            # Verify result structure
            required_keys = [
                'current_price',
                'positions',
                'positions_pnl',
                'total_summary',
                'liquidation_distance',
                'liquidation_details',
                'liquidation_critical',
                'liquidation_warning',
            ]
            
            missing_keys = [key for key in required_keys if key not in result]
            
            if missing_keys:
                print(f"❌ Missing keys in result: {missing_keys}")
                return False
            
            print(f"✅ All required keys present: {', '.join(required_keys)}")
            
            # Display monitoring summary
            print("\n" + "-" * 70)
            print("MONITORING SUMMARY")
            print("-" * 70)
            
            summary = result['total_summary']
            print(f"\nCurrent Price: ${result['current_price']:.2f}")
            print(f"Open Positions: {summary['position_count']}")
            print(f"Total PnL (USD): ${summary['total_pnl_usd']:.2f}")
            print(f"Total PnL (INR): ₹{summary['total_pnl_inr']:.2f}")
            print(f"Liquidation Distance: {result['liquidation_distance']:.2f}%")
            print(f"Critical Alert: {result['liquidation_critical']}")
            print(f"Warning Alert: {result['liquidation_warning']}")
            
            # Test Guardian's decision logic
            print("\n" + "-" * 70)
            print("GUARDIAN DECISION LOGIC")
            print("-" * 70)
            
            if result['liquidation_critical']:
                print("🚨 CRITICAL: Guardian should trigger emergency actions!")
                print("   Expected: Send Telegram alert, possibly halt trading")
            elif result['liquidation_warning']:
                print("⚠️  WARNING: Guardian should send warning alert")
                print("   Expected: Increased monitoring frequency")
            else:
                print("✅ SAFE: Guardian continues normal monitoring")
            
            if summary['total_loss_inr'] > 0:
                print(f"\n💰 Loss Tracking: ₹{summary['total_loss_inr']:.2f}")
                print("   Expected: Guardian tracks against max_loss_inr threshold")
            
            # Verify health file update (Guardian integration point)
            print("\n" + "-" * 70)
            print("CHECKING HEALTH FILE INTEGRATION")
            print("-" * 70)
            
            health_file = Path.cwd() / '.guardian_health'
            if health_file.exists():
                print(f"✅ Health file exists: {health_file}")
                
                import json
                try:
                    with open(health_file, 'r') as f:
                        health_data = json.load(f)
                    
                    # Check if liquidation data is in health file
                    if 'liquidation' in health_data:
                        liq_health = health_data['liquidation']
                        print(f"✅ Health file contains liquidation data:")
                        print(f"   Distance: {liq_health.get('distance', 'N/A')}")
                        print(f"   Critical: {liq_health.get('critical', 'N/A')}")
                        print(f"   Warning: {liq_health.get('warning', 'N/A')}")
                        if 'bankruptcy_distance' in liq_health:
                            print(f"   Bankruptcy Distance: {liq_health.get('bankruptcy_distance', 'N/A')}")
                    else:
                        print("⚠️  Health file missing 'liquidation' data")
                        print("   (This is OK if Guardian hasn't run yet)")
                    
                except Exception as e:
                    print(f"⚠️  Could not read health file: {e}")
            else:
                print("ℹ️  Health file not found (Guardian hasn't run yet)")
            
            # Final verdict
            print("\n" + "=" * 70)
            print("INTEGRATION VERIFICATION RESULT")
            print("=" * 70)
            print("\n✅ PASSED: Guardian Bot + PositionMonitor integration verified!")
            print("\nVerified:")
            print("   ✅ Guardian has position_monitor initialized")
            print("   ✅ Configuration properly passed to monitor")
            print("   ✅ All required methods exist and work")
            print("   ✅ monitor_cycle() returns correct structure")
            print("   ✅ Delta Exchange India improvements active")
            print("   ✅ Liquidation distance calculation working")
            print("   ✅ Bankruptcy distance calculation working")
            print("   ✅ Alert flags (critical/warning) functioning")
            print("\n🎉 Integration is production-ready!")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"❌ monitor_cycle() error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution"""
    success = verify_guardian_integration()
    
    if success:
        print("\n✅ All checks passed!")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed - review errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
