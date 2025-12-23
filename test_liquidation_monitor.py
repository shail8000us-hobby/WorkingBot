#!/usr/bin/env python3
"""
Test script for liquidation_monitor.py
=====================================

This script tests the basic functionality of the liquidation monitor
without requiring actual API credentials.
"""

import sys
import os
from unittest.mock import Mock, patch

# Add current directory to path to import liquidation_monitor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """Test that the module can be imported successfully"""
    try:
        import liquidation_monitor
        print("✅ Module imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_classes():
    """Test that all required classes are available"""
    try:
        from liquidation_monitor import DeltaExchangeClient, LiquidationMonitor, Position, AccountBalance
        print("✅ All classes imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Class import failed: {e}")
        return False

def test_position_dataclass():
    """Test Position dataclass creation"""
    try:
        from liquidation_monitor import Position
        
        pos = Position(
            product_id=27,
            symbol="BTCUSD",
            size=0.1,
            entry_price=400000,
            mark_price=410000,
            liquidation_price=380000,
            unrealized_pnl=1000,
            margin_used=20000,
            side="long"
        )
        
        assert pos.product_id == 27
        assert pos.symbol == "BTCUSD"
        assert pos.unrealized_pnl == 1000
        print("✅ Position dataclass works correctly")
        return True
    except Exception as e:
        print(f"❌ Position dataclass test failed: {e}")
        return False

def test_account_balance_dataclass():
    """Test AccountBalance dataclass creation"""
    try:
        from liquidation_monitor import AccountBalance
        
        balance = AccountBalance(
            total_balance=100000,
            available_balance=80000,
            blocked_balance=20000,
            maintenance_margin=15000
        )
        
        assert balance.total_balance == 100000
        assert balance.available_balance == 80000
        print("✅ AccountBalance dataclass works correctly")
        return True
    except Exception as e:
        print(f"❌ AccountBalance dataclass test failed: {e}")
        return False

def test_client_initialization():
    """Test DeltaExchangeClient initialization"""
    try:
        from liquidation_monitor import DeltaExchangeClient
        
        client = DeltaExchangeClient("test_key", "test_secret")
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api.india.delta.exchange"
        print("✅ DeltaExchangeClient initializes correctly")
        return True
    except Exception as e:
        print(f"❌ DeltaExchangeClient test failed: {e}")
        return False

def test_monitor_initialization():
    """Test LiquidationMonitor initialization"""
    try:
        from liquidation_monitor import LiquidationMonitor
        
        monitor = LiquidationMonitor("test_key", "test_secret", refresh_interval=5)
        assert monitor.refresh_interval == 5
        assert monitor.liquidation_threshold == 5.0
        assert monitor.client is not None
        print("✅ LiquidationMonitor initializes correctly")
        return True
    except Exception as e:
        print(f"❌ LiquidationMonitor test failed: {e}")
        return False

def test_signature_generation():
    """Test HMAC signature generation"""
    try:
        from liquidation_monitor import DeltaExchangeClient
        
        client = DeltaExchangeClient("test_key", "test_secret")
        signature = client._generate_signature("GET", "/v2/positions", "", "")
        
        # Signature should be a 64-character hex string
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)
        print("✅ HMAC signature generation works correctly")
        return True
    except Exception as e:
        print(f"❌ Signature generation test failed: {e}")
        return False

def test_risk_analysis():
    """Test liquidation risk analysis with mock data"""
    try:
        from liquidation_monitor import LiquidationMonitor, Position, AccountBalance
        
        monitor = LiquidationMonitor("test_key", "test_secret")
        
        # Create test positions
        positions = [
            Position(
                product_id=27, symbol="BTCUSD", size=0.1,
                entry_price=400000, mark_price=410000,
                liquidation_price=380000, unrealized_pnl=1000,
                margin_used=20000, side="long"
            )
        ]
        
        # Create test balance
        balance = AccountBalance(
            total_balance=100000,
            available_balance=80000,
            blocked_balance=20000,
            maintenance_margin=15000
        )
        
        # Test risk analysis
        analysis = monitor.analyze_liquidation_risk(positions, balance)
        
        assert analysis['total_positions'] == 1
        assert analysis['total_margin_used'] == 20000
        assert analysis['total_unrealized_pnl'] == 1000
        assert analysis['available_balance'] == 80000
        print("✅ Risk analysis works correctly")
        return True
    except Exception as e:
        print(f"❌ Risk analysis test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Liquidation Monitor Module")
    print("=" * 50)
    
    tests = [
        test_import,
        test_classes,
        test_position_dataclass,
        test_account_balance_dataclass,
        test_client_initialization,
        test_monitor_initialization,
        test_signature_generation,
        test_risk_analysis
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The module is ready to use.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
