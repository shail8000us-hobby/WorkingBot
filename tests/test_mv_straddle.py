#!/usr/bin/env python3
"""
Test MV Straddle Implementation
Quick verification script to test MV Straddle without full backend
"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "webui/backend"))

def test_imports():
    """Test all MV Straddle imports"""
    print("Testing imports...")
    
    try:
        from webui.backend.options_strategy.strategies.base_strategy import BaseStrategy
        print("✅ BaseStrategy imported")
    except Exception as e:
        print(f"❌ BaseStrategy failed: {e}")
        return False
    
    try:
        from webui.backend.options_strategy.strategies.mv_straddle_strategy import MVStraddleStrategy
        print("✅ MVStraddleStrategy imported")
    except Exception as e:
        print(f"❌ MVStraddleStrategy failed: {e}")
        return False
    
    try:
        from webui.backend.options_strategy.mv_straddle.volatility_analyzer import VolatilityAnalyzer
        print("✅ VolatilityAnalyzer imported")
    except Exception as e:
        print(f"❌ VolatilityAnalyzer failed: {e}")
        return False
    
    try:
        from webui.backend.options_strategy.mv_straddle.strike_selector import StrikeSelector
        print("✅ StrikeSelector imported")
    except Exception as e:
        print(f"❌ StrikeSelector failed: {e}")
        return False
    
    try:
        from webui.backend.options_strategy.mv_straddle.breakeven_calculator import BreakevenCalculator
        print("✅ BreakevenCalculator imported")
    except Exception as e:
        print(f"❌ BreakevenCalculator failed: {e}")
        return False
    
    try:
        from webui.backend.options_strategy.mv_straddle.position_adjuster import PositionAdjuster
        print("✅ PositionAdjuster imported")
    except Exception as e:
        print(f"❌ PositionAdjuster failed: {e}")
        return False
    
    return True

def test_chain_service():
    """Test chain service method exists"""
    print("\nTesting chain service...")
    
    try:
        from webui.backend.options_chain.chain_service import OptionsChainService
        chain = OptionsChainService()
        
        # Check if get_option_ticker method exists
        if hasattr(chain, 'get_option_ticker'):
            print("✅ get_option_ticker method exists")
        else:
            print("❌ get_option_ticker method NOT FOUND")
            return False
            
    except Exception as e:
        print(f"❌ Chain service test failed: {e}")
        return False
    
    return True

def main():
    print("=" * 60)
    print("MV STRADDLE IMPLEMENTATION TEST")
    print("=" * 60)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests FAILED")
        return 1
    
    # Test chain service
    if not test_chain_service():
        print("\n❌ Chain service test FAILED")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
