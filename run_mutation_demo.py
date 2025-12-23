#!/usr/bin/env python3
"""
Simple Mutation Testing Demo

Shows how mutation testing works by manually creating mutants
and verifying tests catch them.

This is a simplified demonstration since mutmut has configuration issues.
In production, you'd use: mutmut run
"""

import sys
import os
import tempfile
import subprocess
import shutil
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def create_mutant(original_code, mutation_desc, mutated_code):
    """Create a mutant and test if our tests catch it"""
    print(f"\n🧬 MUTANT: {mutation_desc}")
    print("=" * 70)
    
    # Create temporary file with mutant
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(mutated_code)
        mutant_file = f.name
    
    # Replace original file temporarily
    project_root = os.path.dirname(os.path.abspath(__file__))
    original_file = os.path.join(project_root, 'bot/strategy/modules/grid_calculator.py')
    backup_file = original_file + '.backup'
    
    try:
        # Backup original
        shutil.copy2(original_file, backup_file)
        
        # Install mutant
        shutil.copy2(mutant_file, original_file)
        
        # Run tests
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/test_grid_properties.py::test_property_lower_bound_is_inclusive',
            'tests/test_grid_properties.py::test_property_step_zero_is_invalid',
            'tests/test_grid_properties.py::test_property_lower_equals_upper_is_invalid',
            'tests/test_grid_properties.py::test_property_quantize_is_idempotent',
            '-x', '--tb=no', '-q'
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode != 0:
            print("✅ KILLED - Tests caught this bug!")
            return 'killed'
        else:
            print("❌ SURVIVED - Tests did NOT catch this bug!")
            print(f"   This means your tests are WEAK for this case")
            return 'survived'
            
    finally:
        # Restore original
        shutil.copy2(backup_file, original_file)
        os.unlink(backup_file)
        os.unlink(mutant_file)


def run_mutation_demo():
    """Run demonstration mutation tests"""
    
    print("\n" + "=" * 70)
    print("🧬 MUTATION TESTING DEMONSTRATION")
    print("=" * 70)
    print("\nTesting if your tests catch common bugs in grid_calculator.py\n")
    
    results = {
        'killed': 0,
        'survived': 0
    }
    
    # Read original code
    import os
    project_root = os.path.dirname(os.path.abspath(__file__))
    grid_calc_path = os.path.join(project_root, 'bot/strategy/modules/grid_calculator.py')
    
    with open(grid_calc_path) as f:
        original_code = f.read()
    
    # MUTANT 1: Change > to >= in bounds check
    print("\n📍 Testing: Bounds validation logic")
    mutant1 = original_code.replace(
        'return lower <= price <= upper',
        'return lower < price <= upper'  # Changed <= to <
    )
    result1 = create_mutant(original_code, "Change 'lower <= price' to 'lower < price'", mutant1)
    results[result1] += 1
    
    # MUTANT 2: Remove tick_size validation
    print("\n📍 Testing: Tick size validation")
    mutant2 = original_code.replace(
        'if tick_size <= 0:',
        'if tick_size < 0:'  # Changed <= to <
    )
    result2 = create_mutant(original_code, "Allow tick_size == 0 (should fail)", mutant2)
    results[result2] += 1
    
    # MUTANT 3: Change step validation
    print("\n📍 Testing: Step validation")
    mutant3 = original_code.replace(
        'if step <= 0:',
        'if step < 0:'  # Changed <= to <
    )
    result3 = create_mutant(original_code, "Allow step == 0 (should fail)", mutant3)
    results[result3] += 1
    
    # MUTANT 4: Change quantize logic
    print("\n📍 Testing: Quantization logic")
    mutant4 = original_code.replace(
        'ticks = int(price_decimal / tick_decimal)',
        'ticks = int(price_decimal / tick_decimal) + 1'  # Off by one
    )
    result4 = create_mutant(original_code, "Off-by-one error in quantization", mutant4)
    results[result4] += 1
    
    # MUTANT 5: Change lower bound check
    print("\n📍 Testing: Lower bound comparison")
    mutant5 = original_code.replace(
        'if lower >= upper:',
        'if lower > upper:'  # Changed >= to >
    )
    result5 = create_mutant(original_code, "Allow lower == upper (should fail)", mutant5)
    results[result5] += 1
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 MUTATION TESTING RESULTS")
    print("=" * 70)
    print(f"\n✅ Mutants KILLED:    {results['killed']}/5 ({results['killed']/5*100:.0f}%)")
    print(f"❌ Mutants SURVIVED:  {results['survived']}/5 ({results['survived']/5*100:.0f}%)")
    print()
    
    if results['survived'] == 0:
        print("🎉 EXCELLENT! All mutants killed - your tests are strong!")
        print("   Mutation Score: 100%")
    elif results['survived'] <= 1:
        print("✅ GOOD! Most mutants killed - tests are fairly strong")
        print(f"   Mutation Score: {results['killed']/5*100:.0f}%")
    else:
        print("⚠️  WARNING! Many mutants survived - tests need strengthening")
        print(f"   Mutation Score: {results['killed']/5*100:.0f}%")
        print("\n   Recommendation: Add more property-based tests for edge cases")
    
    print("\n" + "=" * 70)
    print()
    
    return results


if __name__ == '__main__':
    run_mutation_demo()
