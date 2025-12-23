"""
Virtual Testing Suite for Bulk Seeding Feature

Tests bulk seeding without making real API calls using MockDeltaClient.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from bot.tests.mock_delta_client import MockDeltaClient
from bot.strategy.modules.bulk_seeding.seeding_calculator import SeedingCalculator, SeedLevel
from bot.strategy.modules.bulk_seeding.seeding_validator import SeedingValidator
from bot.strategy.modules.bulk_seeding.seeding_executor import SeedingExecutor


class VirtualTester:
    """Virtual testing framework for bulk seeding"""
    
    def __init__(self):
        self.mock_client = None
        self.engine = None
        self.test_results = []
        
    def setup(self, **kwargs):
        """Setup mock environment"""
        print("\n" + "="*80)
        print("🧪 VIRTUAL TESTING - BULK SEEDING")
        print("="*80)
        
        # Create mock client
        self.mock_client = MockDeltaClient(**kwargs)
        
        print(f"\n✅ Mock Exchange initialized:")
        print(f"   Symbol: {self.mock_client.symbol}")
        print(f"   Balance: ${self.mock_client.balance:,.0f}")
        print(f"   Current Price: ${self.mock_client.current_price:,.0f}")
        
        # Grid parameters
        self.ref_price = 115000.0
        self.step_size = 1000.0
        self.lower = 105000.0
        self.upper = 120000.0
        self.lot_size = 150  # 150 contracts per order (e.g., 1.5 BTC at $100k)
        
        # Create calculator
        self.calculator = SeedingCalculator(
            ref=self.ref_price,
            step=self.step_size,
            lower=self.lower,
            upper=self.upper
        )
        
        # Create validator
        validator_config = {
            'GRIDBOT_SEED_MAX_COUNT': '10',
            'GRIDBOT_SEED_IV_THRESHOLD': '50.0',
            'GRIDBOT_SEED_RV_THRESHOLD': '45.0',
            'GRIDBOT_SEED_MARGIN_BUFFER': '1.5'
        }
        self.validator = SeedingValidator(config=validator_config)
        
        # Create simple mock order manager
        class MockOrderManager:
            def __init__(self, client):
                self.api = client
                self.symbol = client.symbol
            
            def place_buy_order(self, price, post_only=True):
                # Use mock client
                mode = "limit_order" if post_only else "market_order"
                result = self.api.place_order(
                    symbol=self.symbol,
                    side="buy",
                    order_type=mode,
                    size=Decimal("150"),
                    price=Decimal(str(price)) if price else None,
                    post_only=post_only
                )
                return result
        
        self.order_mgr = MockOrderManager(self.mock_client)
        
        # Create executor
        self.executor = SeedingExecutor(
            order_manager=self.order_mgr,
            api_client=self.mock_client
        )
        
        print(f"\n✅ Bulk Seeding Modules initialized:")
        print(f"   REF Price: ${self.ref_price:,.0f}")
        print(f"   STEP Size: ${self.step_size:,.0f}")
        print(f"   Lot Size: {self.lot_size} contracts")
        print(f"   Max Seeds: 10")
        
    def test_calculation(self):
        """Test 1: Seed level calculation"""
        print("\n" + "="*80)
        print("TEST 1: Seed Level Calculation")
        print("="*80)
        
        seed_count = 5
        
        # Calculate seeds
        current_price = float(self.mock_client.current_price)
        
        print(f"\n📊 Inputs:")
        print(f"   REF: ${self.ref_price:,.0f}")
        print(f"   STEP: ${self.step_size:,.0f}")
        print(f"   Current: ${current_price:,.0f}")
        print(f"   Seeds: {seed_count}")
        
        # Calculate seed levels
        print("\n🧮 Calculating seed levels...")
        seeds = self.calculator.calculate_seed_levels(
            seed_count=seed_count,
            current_price=current_price
        )
        
        print(f"\n📝 Calculated {len(seeds)} levels:")
        for i, seed in enumerate(seeds, 1):
            print(f"   #{i}: Order ${seed.order_price:,.0f} → TP ${seed.target_price:,.0f}")
            print(f"       Estimated fill: ${seed.estimated_entry:,.0f}")
            profit = seed.target_price - seed.estimated_entry
            print(f"       Expected profit: ${profit:,.0f}")
        
        # Calculate margins
        base_margin, buffered_margin = self.calculator.calculate_margin_requirement(
            seed_levels=seeds,
            lot_size=self.lot_size,
            margin_buffer=1.5
        )
        
        available = float(self.mock_client.balance)
        
        print(f"\n💰 Margin Requirements:")
        print(f"   Base: ${base_margin:,.0f}")
        print(f"   Buffered (1.5x): ${buffered_margin:,.0f}")
        print(f"   Available: ${available:,.0f}")
        
        # Verdict
        test_passed = len(seeds) == seed_count and buffered_margin < available
        self.test_results.append({
            'name': 'Calculation',
            'passed': test_passed,
            'seeds': len(seeds)
        })
        
        if test_passed:
            print("\n✅ TEST PASSED")
        else:
            print("\n❌ TEST FAILED")
        
        return test_passed
    
    def test_validation(self):
        """Test 2: Validation checks"""
        print("\n" + "="*80)
        print("TEST 2: Validation Checks")
        print("="*80)
        
        # Calculate seeds
        seeds = self.calculator.calculate_seed_levels(
            seed_count=5,
            current_price=float(self.mock_client.current_price)
        )
        
        # Get margin requirement
        _, buffered_margin = self.calculator.calculate_margin_requirement(
            seed_levels=seeds,
            lot_size=self.lot_size,
            margin_buffer=1.5
        )
        
        # Mock volatility data
        iv = 32.0
        rv = 28.0
        current_positions = 0
        max_positions = 20
        
        print(f"\n📊 Validation Inputs:")
        print(f"   Seeds: {len(seeds)}")
        print(f"   Margin needed: ${buffered_margin:,.0f}")
        print(f"   Margin available: ${self.mock_client.balance:,.0f}")
        print(f"   IV: {iv}%, RV: {rv}%")
        print(f"   Positions: {current_positions}/{max_positions}")
        
        # Run validations
        print(f"\n� Running validation checks...")
        
        valid, results = self.validator.validate_all(
            seed_count=len(seeds),
            seeds=seeds,
            available_margin=self.mock_client.balance,
            margin_required=buffered_margin,
            iv=iv,
            rv=rv,
            current_positions=current_positions,
            max_positions=max_positions
        )
        
        print(f"\n📊 Validation Results:")
        for result in results:
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.check}: {result.message}")
        
        # Verdict
        test_passed = valid
        self.test_results.append({
            'name': 'Validation (Normal)',
            'passed': test_passed,
            'all_passed': valid
        })
        
        if test_passed:
            print("\n✅ TEST PASSED")
        else:
            print("\n❌ TEST FAILED")
        
        return test_passed
    
    def test_insufficient_margin(self):
        """Test 3: Insufficient margin rejection"""
        print("\n" + "="*80)
        print("TEST 3: Insufficient Margin Rejection")
        print("="*80)
        
        # Calculate seeds
        seeds = self.calculator.calculate_seed_levels(5, float(self.mock_client.current_price))
        _, buffered_margin = self.calculator.calculate_margin_requirement(
            seed_levels=seeds,
            lot_size=self.lot_size,
            margin_buffer=1.5
        )
        
        # Set low balance
        low_balance = Decimal("50000")
        
        print(f"\n📊 Validation Inputs:")
        print(f"   Margin needed: ${buffered_margin:,.0f}")
        print(f"   Margin available: ${low_balance:,.0f} (TOO LOW)")
        
        # Run validation
        valid, results = self.validator.validate_all(
            seed_count=5,
            seeds=seeds,
            available_margin=low_balance,
            margin_required=buffered_margin,
            iv=32.0,
            rv=28.0,
            current_positions=0,
            max_positions=20
        )
        
        print(f"\n📊 Validation Results:")
        for result in results:
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.check}: {result.message}")
        
        # Verdict - should FAIL
        test_passed = not valid  # Expecting rejection
        self.test_results.append({
            'name': 'Insufficient Margin',
            'passed': test_passed,
            'correctly_rejected': not valid
        })
        
        if test_passed:
            print("\n✅ TEST PASSED (Correctly rejected)")
        else:
            print("\n❌ TEST FAILED (Should have rejected)")
        
        return test_passed
    
    def test_high_volatility(self):
        """Test 4: High volatility rejection"""
        print("\n" + "="*80)
        print("TEST 4: High Volatility Rejection")
        print("="*80)
        
        # Calculate seeds
        seeds = self.calculator.calculate_seed_levels(5, float(self.mock_client.current_price))
        _, buffered_margin = self.calculator.calculate_margin_requirement(
            seed_levels=seeds,
            lot_size=self.lot_size,
            margin_buffer=1.5
        )
        
        # High volatility
        high_iv = 65.0
        high_rv = 58.0
        
        print(f"\n📊 Validation Inputs:")
        print(f"   IV: {high_iv}% (TOO HIGH)")
        print(f"   RV: {high_rv}% (TOO HIGH)")
        print(f"   Thresholds: IV<50%, RV<45%")
        
        # Run validation
        valid, results = self.validator.validate_all(
            seed_count=5,
            seeds=seeds,
            available_margin=self.mock_client.balance,
            margin_required=buffered_margin,
            iv=high_iv,
            rv=high_rv,
            current_positions=0,
            max_positions=20
        )
        
        print(f"\n📊 Validation Results:")
        for result in results:
            status = "✅" if result.passed else "❌"
            print(f"   {status} {result.check}: {result.message}")
        
        # Verdict - should FAIL
        test_passed = not valid
        self.test_results.append({
            'name': 'High Volatility',
            'passed': test_passed,
            'correctly_rejected': not valid
        })
        
        if test_passed:
            print("\n✅ TEST PASSED (Correctly rejected)")
        else:
            print("\n❌ TEST FAILED (Should have rejected)")
        
        return test_passed
    
    def test_execution(self):
        """Test 5: Order execution with mock exchange"""
        print("\n" + "="*80)
        print("TEST 5: Order Execution")
        print("="*80)
        
        # Calculate seeds
        seeds = self.calculator.calculate_seed_levels(3, float(self.mock_client.current_price))
        
        print(f"\n📊 Executing {len(seeds)} seed orders:")
        for i, seed in enumerate(seeds, 1):
            print(f"   #{i}: Order ${seed.order_price:,.0f} → TP ${seed.target_price:,.0f}")
        
        # Execute seeds
        print(f"\n🚀 Placing orders...")
        results = self.executor.execute_parallel(
            seed_levels=seeds,
            lot_size=self.lot_size,
            mode='market'
        )
        
        filled = sum(1 for r in results if r['success'])
        
        print(f"\n📊 Execution Results:")
        print(f"   Filled: {filled}/{len(seeds)}")
        
        for i, result in enumerate(results, 1):
            if result['success']:
                print(f"   ✅ Seed #{i}: Filled @ ${result['fill_price']:,.2f}")
            else:
                print(f"   ❌ Seed #{i}: Failed - {result.get('error', 'Unknown')}")
        
        # Check mock stats
        stats = self.mock_client.get_statistics()
        print(f"\n💰 Mock Exchange Stats:")
        print(f"   Orders placed: {stats['total_orders_placed']}")
        print(f"   Orders filled: {stats['total_orders_filled']}")
        print(f"   Positions: {stats['open_positions']}")
        print(f"   Balance: ${Decimal(stats['balance']):,.2f}")
        
        # Verdict
        test_passed = filled == len(seeds)
        self.test_results.append({
            'name': 'Execution',
            'passed': test_passed,
            'filled': filled,
            'total': len(seeds)
        })
        
        if test_passed:
            print("\n✅ TEST PASSED")
        else:
            print("\n❌ TEST FAILED")
        
        return test_passed
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("\n" + "="*80)
        print("🧪 VIRTUAL TESTING SUITE - BULK SEEDING")
        print("="*80)
        print("\nRunning 5 test scenarios...\n")
        
        # Run tests
        self.setup()
        self.test_calculation()
        self.test_validation()
        self.test_insufficient_margin()
        self.test_high_volatility()
        self.test_execution()
        
        # Summary
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for t in self.test_results if t['passed'])
        total = len(self.test_results)
        
        for i, test in enumerate(self.test_results, 1):
            status = "✅ PASS" if test['passed'] else "❌ FAIL"
            print(f"{i}. {test['name']}: {status}")
        
        print(f"\n{'='*80}")
        print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
        print(f"{'='*80}")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED - BULK SEEDING MODULES WORKING")
        else:
            print(f"\n⚠️ {total - passed} TESTS FAILED - REVIEW NEEDED")
        
        return passed == total


if __name__ == "__main__":
    """Run virtual tests"""
    tester = VirtualTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)
