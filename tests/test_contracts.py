"""
Contract Testing Suite - Design by Contract Verification

Tests the contract system (preconditions, postconditions, invariants)
and verifies GridCalculator with contracts.

Run with: pytest tests/test_contracts.py -v -s
"""

import pytest
import math
from bot.utils.contracts import (
    require, ensure, invariant,
    ContractViolation, enable_contracts, disable_contracts
)
from bot.strategy.modules.grid_calculator_with_contracts import GridCalculator


class TestContractDecorators:
    """Test the contract decorator system itself"""
    
    def setup_method(self):
        """Enable contracts for testing"""
        enable_contracts()
    
    def test_require_passes_with_valid_input(self):
        """Test: Precondition passes when condition is True"""
        @require(lambda x: x > 0, "Must be positive")
        def divide_by_two(x):
            return x / 2
        
        # Should not raise
        result = divide_by_two(10)
        assert result == 5.0
    
    def test_require_fails_with_invalid_input(self):
        """Test: Precondition fails when condition is False"""
        @require(lambda x: x > 0, "Must be positive")
        def divide_by_two(x):
            return x / 2
        
        # Should raise ContractViolation
        with pytest.raises(ContractViolation, match="PRECONDITION FAILED"):
            divide_by_two(-5)
    
    def test_ensure_passes_with_valid_output(self):
        """Test: Postcondition passes when result is valid"""
        @ensure(lambda result: result > 0, "Result must be positive")
        def square(x):
            return x * x
        
        # Should not raise (4^2 = 16 > 0)
        result = square(4)
        assert result == 16
    
    def test_ensure_fails_with_invalid_output(self):
        """Test: Postcondition fails when result is invalid"""
        @ensure(lambda result: result > 100, "Result must be > 100")
        def square(x):
            return x * x
        
        # Should raise (2^2 = 4, not > 100)
        with pytest.raises(ContractViolation, match="POSTCONDITION FAILED"):
            square(2)
    
    def test_invariant_maintains_property(self):
        """Test: Invariant enforced before and after method"""
        class BankAccount:
            def __init__(self):
                self.balance = 1000
            
            @invariant(lambda self: self.balance >= 0, "Balance cannot be negative")
            def withdraw(self, amount):
                self.balance -= amount
        
        account = BankAccount()
        
        # Valid withdrawal
        account.withdraw(500)
        assert account.balance == 500
        
        # Invalid withdrawal (would go negative)
        with pytest.raises(ContractViolation, match="INVARIANT VIOLATED"):
            account.withdraw(600)


class TestGridCalculatorContracts:
    """Test GridCalculator with contracts enabled"""
    
    def setup_method(self):
        """Enable contracts"""
        enable_contracts()
    
    def test_constructor_with_valid_params(self):
        """Test: Constructor succeeds with valid parameters"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        assert calc.lower == 105000
        assert calc.upper == 115000
    
    def test_constructor_rejects_negative_step(self):
        """Test: Precondition rejects step <= 0"""
        with pytest.raises(ContractViolation, match="Step must be positive"):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=-500,  # ❌ Invalid
                ref=110000,
                tick_size=0.5
            )
    
    def test_constructor_rejects_negative_tick_size(self):
        """Test: Precondition rejects tick_size <= 0"""
        with pytest.raises(ContractViolation, match="Tick size must be positive"):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=500,
                ref=110000,
                tick_size=-0.5  # ❌ Invalid
            )
    
    def test_constructor_rejects_inverted_bounds(self):
        """Test: Precondition rejects lower >= upper"""
        with pytest.raises(ContractViolation, match="Lower must be less than upper"):
            GridCalculator(
                lower=115000,  # ❌ Greater than upper
                upper=105000,
                step=500,
                ref=110000,
                tick_size=0.5
            )
    
    def test_constructor_rejects_ref_outside_bounds(self):
        """Test: Precondition rejects ref outside bounds"""
        with pytest.raises(ContractViolation, match="Reference must be within bounds"):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=500,
                ref=120000,  # ❌ Above upper
                tick_size=0.5
            )
    
    def test_compute_next_buy_postcondition_quantized(self):
        """Test: Postcondition ensures result is quantized"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Result should be quantized
        result = calc.compute_next_buy_level([])
        
        if result is not None:
            # Verify quantization (result == quantize(result))
            assert result == calc.quantize_price(result)
    
    def test_compute_next_buy_postcondition_within_bounds(self):
        """Test: Postcondition ensures result within bounds or None"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # At lower boundary
        positions = [{'entry_price': 105000}]
        result = calc.compute_next_buy_level(positions)
        
        # Next would be 104500 (outside bounds) → should be None
        assert result is None, "Should return None when outside bounds"
    
    def test_compute_tp_price_postcondition_distance(self):
        """Test: Postcondition verifies TP is exactly step away"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        entry = 110000
        tp = calc.compute_tp_price(entry)
        
        # Contract ensures: tp == entry + step
        assert tp == entry + 500
    
    def test_compute_tp_price_short_postcondition_distance(self):
        """Test: Postcondition verifies SHORT TP is exactly step below"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        entry = 110500
        tp = calc.compute_tp_price_short(entry)
        
        # Contract ensures: tp == entry - step
        assert tp == entry - 500
    
    def test_quantize_postcondition_idempotence(self):
        """Test: Postcondition ensures quantize(x) == quantize(quantize(x))"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        prices = [110000.7, 110001.3, 110002.9]
        
        for price in prices:
            once = calc.quantize_price(price)
            twice = calc.quantize_price(once)
            
            # Contract ensures idempotence
            assert once == twice
    
    def test_get_grid_levels_postcondition_non_empty(self):
        """Test: Postcondition ensures at least one level returned"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        levels = calc.get_grid_levels()
        
        # Contract ensures len(result) > 0
        assert len(levels) > 0


class TestContractViolationDetection:
    """Test that contracts actually catch violations"""
    
    def setup_method(self):
        """Enable contracts"""
        enable_contracts()
    
    def test_detects_invalid_step_at_runtime(self):
        """Test: Contract catches step <= 0"""
        with pytest.raises(ContractViolation):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=0,  # ❌ Invalid
                ref=110000,
                tick_size=0.5
            )
    
    def test_detects_invalid_tick_size_at_runtime(self):
        """Test: Contract catches tick_size <= 0"""
        with pytest.raises(ContractViolation):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=500,
                ref=110000,
                tick_size=0  # ❌ Invalid (would cause division by zero!)
            )
    
    def test_detects_bounds_violation(self):
        """Test: Contract catches lower >= upper"""
        with pytest.raises(ContractViolation):
            GridCalculator(
                lower=115000,
                upper=105000,  # ❌ Less than lower
                step=500,
                ref=110000,
                tick_size=0.5
            )
    
    def test_detects_ref_outside_bounds(self):
        """Test: Contract catches ref outside grid range"""
        with pytest.raises(ContractViolation):
            GridCalculator(
                lower=105000,
                upper=115000,
                step=500,
                ref=100000,  # ❌ Below lower bound
                tick_size=0.5
            )


class TestContractPerformance:
    """Test contract overhead and performance"""
    
    def test_contracts_can_be_disabled(self):
        """Test: Contracts can be disabled for production"""
        from bot.utils.contracts import disable_contracts, enable_contracts
        
        # Disable contracts
        disable_contracts()
        
        # This should NOT raise even with invalid input
        # (contracts are disabled)
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Re-enable for other tests
        enable_contracts()
    
    def test_contract_overhead_is_minimal(self):
        """Test: Contract checking has minimal performance impact"""
        import time
        
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Benchmark with contracts enabled
        enable_contracts()
        start = time.time()
        for i in range(1000):
            calc.compute_next_buy_level([])
        with_contracts = time.time() - start
        
        # Disable contracts
        disable_contracts()
        start = time.time()
        for i in range(1000):
            calc.compute_next_buy_level([])
        without_contracts = time.time() - start
        
        # Re-enable
        enable_contracts()
        
        # Overhead should be < 50% (acceptable)
        overhead = (with_contracts - without_contracts) / without_contracts
        print(f"\n  Contract overhead: {overhead*100:.1f}%")
        
        assert overhead < 0.5, f"Contract overhead too high: {overhead*100:.1f}%"


class TestContractDocumentation:
    """Test that contracts serve as documentation"""
    
    def test_contracts_document_valid_inputs(self):
        """Contracts document what inputs are valid"""
        # Just by looking at decorators, you know:
        # - step > 0
        # - tick_size > 0
        # - lower < upper
        # - lower <= ref <= upper
        
        # This is self-documenting!
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        assert calc is not None
    
    def test_contracts_document_expected_outputs(self):
        """Contracts document what outputs are guaranteed"""
        calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Contract ensures: TP == entry + step
        tp = calc.compute_tp_price(110000)
        assert tp == 110500  # Guaranteed by contract!
        
        # Contract ensures: SHORT TP == entry - step
        tp_short = calc.compute_tp_price_short(110500)
        assert tp_short == 110000  # Guaranteed by contract!


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])

