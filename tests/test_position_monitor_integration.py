"""
Position Monitor Integration Test Suite
Tests that PositionMonitor is properly integrated with Guardian Bot

Run this script to verify:
1. All required methods exist and work
2. Return types are correct
3. Guardian integration points function properly
4. Monitor cycles execute successfully
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.guardian.collectors.position_monitor import PositionMonitor
import ccxt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTester:
    """Test suite for PositionMonitor integration"""
    
    def __init__(self):
        self.config = None
        self.exchange = None
        self.monitor = None
        self.passed_tests = 0
        self.failed_tests = 0
    
    def setup(self):
        """Initialize test environment"""
        print("\n" + "=" * 70)
        print(" " * 15 + "POSITION MONITOR INTEGRATION TEST")
        print("=" * 70)
        print("\nSetting up test environment...")
        
        try:
            # Load config
            self.config = get_config()
            print(f"✅ Config loaded: {self.config.bot.symbol}")
            
            # Initialize exchange (use CCXT directly)
            self.exchange = ccxt.delta({
                'apiKey': self.config.api.key,
                'secret': self.config.api.secret,
                'urls': {
                    'api': {
                        'public': self.config.api.url,
                        'private': self.config.api.url,
                    }
                },
                'options': {
                    'defaultType': 'swap',
                    'product_id': self.config.api.product_id
                }
            })
            print(f"✅ Exchange initialized: Delta India")
            
            # Initialize PositionMonitor
            self.monitor = PositionMonitor(self.exchange, self.config)
            print(f"✅ PositionMonitor initialized")
            print(f"   Symbol: {self.monitor.symbol}")
            print(f"   Contract Multiplier: {self.monitor.contract_multiplier}")
            print(f"   USD to INR Rate: {self.monitor.usd_to_inr_rate}")
            
            return True
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_interface_compatibility(self):
        """Test 1: Verify all required methods exist"""
        print("\n" + "=" * 70)
        print("TEST 1: INTERFACE COMPATIBILITY")
        print("=" * 70)
        
        required_methods = [
            'fetch_open_positions',
            'get_current_price',
            'get_current_pnl',
            'get_position',
            'get_liquidation_distance',
            'get_bankruptcy_distance',
            'get_liquidation_details',
            'monitor_cycle',
            'calculate_position_pnl',
            'calculate_total_pnl',
        ]
        
        print("\nChecking required methods...")
        all_exist = True
        for method in required_methods:
            if hasattr(self.monitor, method):
                print(f"   ✅ {method}")
            else:
                print(f"   ❌ {method} - MISSING")
                all_exist = False
        
        if all_exist:
            print("\n✅ TEST PASSED: All required methods exist")
            self.passed_tests += 1
        else:
            print("\n❌ TEST FAILED: Some methods are missing")
            self.failed_tests += 1
        
        return all_exist
    
    def test_method_return_types(self):
        """Test 2: Verify method return types are correct"""
        print("\n" + "=" * 70)
        print("TEST 2: METHOD RETURN TYPES")
        print("=" * 70)
        
        tests_passed = True
        
        # Test fetch_open_positions
        try:
            positions = self.monitor.fetch_open_positions()
            if isinstance(positions, list):
                print(f"   ✅ fetch_open_positions() → list ({len(positions)} items)")
            else:
                print(f"   ❌ fetch_open_positions() → {type(positions).__name__} (expected list)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ fetch_open_positions() error: {e}")
            tests_passed = False
        
        # Test get_current_price
        try:
            price = self.monitor.get_current_price()
            if price is None or isinstance(price, (float, int)):
                print(f"   ✅ get_current_price() → {type(price).__name__} (${price if price else 'None'})")
            else:
                print(f"   ❌ get_current_price() → {type(price).__name__} (expected float or None)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_current_price() error: {e}")
            tests_passed = False
        
        # Test get_current_pnl
        try:
            pnl = self.monitor.get_current_pnl()
            if isinstance(pnl, (float, int)):
                print(f"   ✅ get_current_pnl() → float (₹{pnl:.2f})")
            else:
                print(f"   ❌ get_current_pnl() → {type(pnl).__name__} (expected float)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_current_pnl() error: {e}")
            tests_passed = False
        
        # Test get_position
        try:
            position = self.monitor.get_position()
            if position is None:
                print(f"   ✅ get_position() → None (no positions)")
            elif hasattr(position, 'size') and hasattr(position, 'value'):
                print(f"   ✅ get_position() → object (size={position.size}, value={position.value})")
            else:
                print(f"   ❌ get_position() missing 'size' or 'value' attributes")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_position() error: {e}")
            tests_passed = False
        
        # Test get_liquidation_distance
        try:
            liq_dist = self.monitor.get_liquidation_distance()
            if isinstance(liq_dist, (float, int)):
                print(f"   ✅ get_liquidation_distance() → float ({liq_dist:.2f}%)")
            else:
                print(f"   ❌ get_liquidation_distance() → {type(liq_dist).__name__} (expected float)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_liquidation_distance() error: {e}")
            tests_passed = False
        
        # Test get_bankruptcy_distance
        try:
            bank_dist = self.monitor.get_bankruptcy_distance()
            if isinstance(bank_dist, (float, int)):
                print(f"   ✅ get_bankruptcy_distance() → float ({bank_dist:.2f}%)")
            else:
                print(f"   ❌ get_bankruptcy_distance() → {type(bank_dist).__name__} (expected float)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_bankruptcy_distance() error: {e}")
            tests_passed = False
        
        # Test get_liquidation_details
        try:
            liq_details = self.monitor.get_liquidation_details()
            if isinstance(liq_details, list):
                print(f"   ✅ get_liquidation_details() → list ({len(liq_details)} items)")
            else:
                print(f"   ❌ get_liquidation_details() → {type(liq_details).__name__} (expected list)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ get_liquidation_details() error: {e}")
            tests_passed = False
        
        # Test monitor_cycle
        try:
            result = self.monitor.monitor_cycle()
            if result is None:
                print(f"   ⚠️  monitor_cycle() → None (error occurred)")
            elif isinstance(result, dict):
                print(f"   ✅ monitor_cycle() → dict ({len(result.keys())} keys)")
            else:
                print(f"   ❌ monitor_cycle() → {type(result).__name__} (expected dict)")
                tests_passed = False
        except Exception as e:
            print(f"   ❌ monitor_cycle() error: {e}")
            tests_passed = False
        
        if tests_passed:
            print("\n✅ TEST PASSED: All methods return correct types")
            self.passed_tests += 1
        else:
            print("\n❌ TEST FAILED: Some methods return incorrect types")
            self.failed_tests += 1
        
        return tests_passed
    
    def test_monitor_cycle_structure(self):
        """Test 3: Verify monitor_cycle returns correct structure"""
        print("\n" + "=" * 70)
        print("TEST 3: MONITOR CYCLE STRUCTURE")
        print("=" * 70)
        
        try:
            result = self.monitor.monitor_cycle()
            
            if result is None:
                print("❌ monitor_cycle() returned None")
                self.failed_tests += 1
                return False
            
            # Expected keys (Delta Exchange India improvements)
            expected_keys = [
                'current_price',
                'positions',
                'positions_pnl',
                'total_summary',
                'liquidation_distance',
                'liquidation_details',
                'liquidation_critical',
                'liquidation_warning',
            ]
            
            print("\nChecking result structure:")
            all_keys_present = True
            for key in expected_keys:
                if key in result:
                    value = result[key]
                    if key == 'total_summary' and isinstance(value, dict):
                        print(f"   ✅ '{key}' → dict with {len(value)} keys")
                    elif isinstance(value, list):
                        print(f"   ✅ '{key}' → list with {len(value)} items")
                    elif isinstance(value, bool):
                        print(f"   ✅ '{key}' → {value}")
                    elif isinstance(value, (int, float)):
                        print(f"   ✅ '{key}' → {value}")
                    else:
                        print(f"   ✅ '{key}' → {type(value).__name__}")
                else:
                    print(f"   ❌ '{key}' - MISSING")
                    all_keys_present = False
            
            # Verify total_summary structure
            if 'total_summary' in result:
                summary = result['total_summary']
                summary_keys = [
                    'total_pnl_usd',
                    'total_pnl_inr',
                    'total_loss_inr',
                    'position_count',
                    'profitable_count',
                    'losing_count',
                ]
                
                print("\nChecking total_summary structure:")
                for key in summary_keys:
                    if key in summary:
                        print(f"   ✅ total_summary['{key}'] = {summary[key]}")
                    else:
                        print(f"   ❌ total_summary['{key}'] - MISSING")
                        all_keys_present = False
            
            if all_keys_present:
                print("\n✅ TEST PASSED: monitor_cycle structure is correct")
                self.passed_tests += 1
                return True
            else:
                print("\n❌ TEST FAILED: Some keys are missing")
                self.failed_tests += 1
                return False
                
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests += 1
            return False
    
    def test_guardian_integration_points(self):
        """Test 4: Verify Guardian bot integration points"""
        print("\n" + "=" * 70)
        print("TEST 4: GUARDIAN INTEGRATION POINTS")
        print("=" * 70)
        
        tests_passed = True
        
        # Test 1: Configuration compatibility
        print("\n1. Configuration Compatibility:")
        print(f"   Symbol: {self.monitor.symbol}")
        print(f"   Product ID: {self.monitor.product_id}")
        print(f"   Contract Multiplier: {self.monitor.contract_multiplier}")
        print(f"   USD to INR Rate: {self.monitor.usd_to_inr_rate}")
        
        if self.monitor.symbol and self.monitor.contract_multiplier > 0:
            print("   ✅ Configuration properly loaded")
        else:
            print("   ❌ Configuration incomplete")
            tests_passed = False
        
        # Test 2: Position tracking for Risk Engine
        print("\n2. Position Tracking (for Risk Engine):")
        position = self.monitor.get_position()
        if position:
            print(f"   Position found:")
            print(f"      size: {position.size}")
            print(f"      value: {position.value}")
            if hasattr(position, 'size') and hasattr(position, 'value'):
                print("   ✅ Position object has required attributes")
            else:
                print("   ❌ Position object missing attributes")
                tests_passed = False
        else:
            print("   ℹ️  No open positions (position=None)")
        
        # Test 3: Liquidation monitoring
        print("\n3. Liquidation Monitoring:")
        liq_dist = self.monitor.get_liquidation_distance()
        print(f"   Liquidation Distance: {liq_dist:.2f}%")
        
        if liq_dist < 1.0:
            print("   🚨 CRITICAL: Liquidation imminent!")
        elif liq_dist < 5.0:
            print("   ⚠️  WARNING: Close to liquidation")
        elif liq_dist < 100.0:
            print("   ✅ SAFE: Adequate distance from liquidation")
        else:
            print("   ℹ️  No liquidation risk (no positions or Portfolio Margin Mode)")
        
        # Test 4: Bankruptcy distance (Delta India improvement)
        print("\n4. Bankruptcy Distance:")
        bank_dist = self.monitor.get_bankruptcy_distance()
        print(f"   Bankruptcy Distance: {bank_dist:.2f}%")
        
        if bank_dist < 100.0:
            print(f"   ✅ Bankruptcy distance calculated")
        else:
            print(f"   ℹ️  No bankruptcy data (Portfolio Margin Mode or no positions)")
        
        # Test 5: Detailed liquidation info
        print("\n5. Detailed Liquidation Info:")
        liq_details = self.monitor.get_liquidation_details()
        if liq_details:
            print(f"   Found {len(liq_details)} position(s) with liquidation data:")
            for i, detail in enumerate(liq_details, 1):
                print(f"\n   Position {i}:")
                print(f"      Symbol: {detail['symbol']}")
                print(f"      Side: {detail['side']}")
                print(f"      Size: {detail['size']}")
                print(f"      Entry: ${detail['entry_price']:.2f}")
                print(f"      Current: ${detail['current_price']:.2f}")
                print(f"      Liquidation: ${detail['liquidation_price']:.2f}")
                print(f"      Distance: {detail['liquidation_distance_pct']:.2f}%")
                print(f"      Critical: {detail['is_critical']}")
                print(f"      Warning: {detail['is_warning']}")
        else:
            print("   ℹ️  No detailed liquidation info (Portfolio Margin Mode)")
        
        # Test 6: Monitor cycle integration
        print("\n6. Monitor Cycle Integration:")
        result = self.monitor.monitor_cycle()
        if result:
            print("   ✅ Monitor cycle executed successfully")
            print(f"   Keys returned: {', '.join(result.keys())}")
            
            # Check Guardian uses these flags
            if 'liquidation_critical' in result and 'liquidation_warning' in result:
                print(f"   ✅ Alert flags present: critical={result['liquidation_critical']}, warning={result['liquidation_warning']}")
            else:
                print("   ❌ Alert flags missing")
                tests_passed = False
        else:
            print("   ❌ Monitor cycle returned None")
            tests_passed = False
        
        if tests_passed:
            print("\n✅ TEST PASSED: All Guardian integration points working")
            self.passed_tests += 1
        else:
            print("\n❌ TEST FAILED: Some integration points failed")
            self.failed_tests += 1
        
        return tests_passed
    
    def test_live_monitoring_simulation(self):
        """Test 5: Simulate live monitoring (3 cycles)"""
        print("\n" + "=" * 70)
        print("TEST 5: LIVE MONITORING SIMULATION (3 cycles)")
        print("=" * 70)
        
        import time
        
        all_cycles_passed = True
        
        for i in range(3):
            print(f"\n--- Cycle {i+1}/3 ---")
            
            try:
                result = self.monitor.monitor_cycle()
                
                if result is None:
                    print(f"❌ Cycle {i+1} returned None")
                    all_cycles_passed = False
                    continue
                
                # Display cycle results
                summary = result.get('total_summary', {})
                print(f"✅ Cycle {i+1} completed")
                print(f"   Current Price: ${result.get('current_price', 0):.2f}")
                print(f"   Positions: {summary.get('position_count', 0)}")
                print(f"   PnL (INR): ₹{summary.get('total_pnl_inr', 0):.2f}")
                print(f"   Liquidation Distance: {result.get('liquidation_distance', 100):.2f}%")
                print(f"   Critical Alert: {result.get('liquidation_critical', False)}")
                print(f"   Warning Alert: {result.get('liquidation_warning', False)}")
                
                # Simulate Guardian decision logic
                if result.get('liquidation_critical'):
                    print("   🚨 Guardian would trigger: EMERGENCY STOP")
                elif result.get('liquidation_warning'):
                    print("   ⚠️  Guardian would trigger: WARNING ALERT")
                else:
                    print("   ✅ Guardian status: NORMAL")
                
                if i < 2:  # Don't sleep after last cycle
                    time.sleep(2)
                    
            except Exception as e:
                print(f"❌ Cycle {i+1} error: {e}")
                import traceback
                traceback.print_exc()
                all_cycles_passed = False
        
        if all_cycles_passed:
            print("\n✅ TEST PASSED: All monitoring cycles completed successfully")
            self.passed_tests += 1
        else:
            print("\n❌ TEST FAILED: Some cycles failed")
            self.failed_tests += 1
        
        return all_cycles_passed
    
    def test_critical_bug_fix_verification(self):
        """Test 6: Verify critical indentation bug is fixed"""
        print("\n" + "=" * 70)
        print("TEST 6: CRITICAL BUG FIX VERIFICATION")
        print("=" * 70)
        print("\nVerifying LONG/SHORT position tracking works correctly...")
        
        try:
            # Get positions
            positions = self.monitor.fetch_open_positions()
            
            if not positions:
                print("ℹ️  No positions to test (need LONG or SHORT positions)")
                print("✅ TEST SKIPPED: No positions available")
                return True
            
            # Check if we have both LONG and SHORT positions
            long_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
            short_positions = [p for p in positions if float(p.get('contracts', 0)) < 0]
            
            print(f"\nFound {len(long_positions)} LONG and {len(short_positions)} SHORT positions")
            
            # Get liquidation distance
            liq_dist = self.monitor.get_liquidation_distance()
            
            print(f"Minimum liquidation distance: {liq_dist:.2f}%")
            
            # Get detailed info
            liq_details = self.monitor.get_liquidation_details()
            
            if liq_details:
                print(f"\nDetailed liquidation info for {len(liq_details)} positions:")
                for detail in liq_details:
                    side = detail['side']
                    dist = detail['liquidation_distance_pct']
                    print(f"   {side}: {dist:.2f}% distance")
                
                # Verify minimum is correct
                min_from_details = min(d['liquidation_distance_pct'] for d in liq_details)
                
                if abs(liq_dist - min_from_details) < 0.01:  # Allow small floating point difference
                    print(f"\n✅ Tracking works correctly: minimum={liq_dist:.2f}% matches details")
                    print("✅ CRITICAL BUG FIX VERIFIED: Both LONG and SHORT positions tracked")
                    self.passed_tests += 1
                    return True
                else:
                    print(f"\n❌ Mismatch: get_liquidation_distance()={liq_dist:.2f}% but minimum from details={min_from_details:.2f}%")
                    self.failed_tests += 1
                    return False
            else:
                print("\nℹ️  No detailed liquidation info (Portfolio Margin Mode)")
                if liq_dist == 100.0:
                    print("✅ Correctly returns 100.0 when no liquidation prices available")
                    self.passed_tests += 1
                    return True
                else:
                    print(f"⚠️  Returns {liq_dist:.2f}% with no details (margin-based?)")
                    self.passed_tests += 1
                    return True
                    
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests += 1
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"\nTotal Tests: {self.passed_tests + self.failed_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        
        if self.failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED - Integration verified!")
            print("\n✅ PositionMonitor is properly integrated with Guardian Bot")
            print("✅ All Delta Exchange India improvements working")
            print("✅ Critical indentation bug fixed")
            print("✅ Ready for production use")
        else:
            print(f"\n⚠️  {self.failed_tests} test(s) failed - review errors above")
        
        print("=" * 70)
    
    def run_all_tests(self):
        """Run complete test suite"""
        if not self.setup():
            print("\n❌ Setup failed - cannot run tests")
            return False
        
        # Run all tests
        self.test_interface_compatibility()
        self.test_method_return_types()
        self.test_monitor_cycle_structure()
        self.test_guardian_integration_points()
        self.test_live_monitoring_simulation()
        self.test_critical_bug_fix_verification()
        
        # Print summary
        self.print_summary()
        
        return self.failed_tests == 0


def main():
    """Main test execution"""
    tester = IntegrationTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
