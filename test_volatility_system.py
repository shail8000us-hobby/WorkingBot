#!/usr/bin/env python3
"""
Volatility Chart System Test Suite

Comprehensive tests to verify all components are working correctly.

Usage:
    python3 test_volatility_system.py
"""

import sys
import time
import json
import sqlite3
import requests
from pathlib import Path
from typing import Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print a section header"""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_test(name: str):
    """Print test name"""
    print(f"{BOLD}Testing: {name}{RESET}...", end=' ', flush=True)


def print_result(success: bool, message: str = ""):
    """Print test result"""
    if success:
        print(f"{GREEN}✅ PASS{RESET}")
        if message:
            print(f"  {message}")
    else:
        print(f"{RED}❌ FAIL{RESET}")
        if message:
            print(f"  {RED}{message}{RESET}")


def test_files_exist() -> Tuple[bool, str]:
    """Test that all required files exist"""
    print_header("1. File Existence Tests")
    
    required_files = [
        "bot/volatility/delta_volatility_collector.py",
        "webui/backend/volatility_chart_api.py",
        "webui/frontend/src/components/charts/VolatilityChart.js",
        "integrate_volatility_chart.py",
        "VOLATILITY_CHART_SYSTEM.md"
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        print_test(f"File exists: {file_path}")
        exists = full_path.exists()
        print_result(exists)
        if not exists:
            all_exist = False
    
    return all_exist, "All files exist" if all_exist else "Some files are missing"


def test_collector_import() -> Tuple[bool, str]:
    """Test that collector can be imported"""
    print_header("2. Import Tests")
    
    print_test("Import delta_volatility_collector")
    try:
        from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector, get_collector
        print_result(True, "Successfully imported collector")
        return True, "Collector import successful"
    except Exception as e:
        print_result(False, f"Import error: {e}")
        return False, str(e)


def test_collector_initialization() -> Tuple[bool, str]:
    """Test that collector initializes correctly"""
    print_test("Initialize collector with in-memory DB")
    try:
        from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector
        
        # Use in-memory database for testing
        collector = DeltaVolatilityCollector(db_path=":memory:")
        
        # Check attributes
        assert collector.api_base == "https://api.india.delta.exchange"
        assert collector.symbol == "BTCUSD"
        assert collector.collection_interval == 30
        
        print_result(True, "Collector initialized with correct defaults")
        return True, "Collector initialization successful"
    except Exception as e:
        print_result(False, f"Initialization error: {e}")
        return False, str(e)


def test_database_schema() -> Tuple[bool, str]:
    """Test that database schema is created correctly"""
    print_test("Database schema creation")
    try:
        from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector
        
        # Create collector with in-memory DB
        collector = DeltaVolatilityCollector(db_path=":memory:")
        
        # Check tables exist
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Re-initialize schema for in-memory DB
        collector._init_database()
        
        # Query tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert "iv_snapshots" in tables
        assert "rv_calculations" in tables
        
        conn.close()
        
        print_result(True, "Tables created: iv_snapshots, rv_calculations")
        return True, "Database schema correct"
    except Exception as e:
        print_result(False, f"Schema error: {e}")
        return False, str(e)


def test_api_module_import() -> Tuple[bool, str]:
    """Test that API module can be imported"""
    print_test("Import volatility_chart_api")
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "webui" / "backend"))
        from volatility_chart_api import register_volatility_chart_api
        print_result(True, "Successfully imported API module")
        return True, "API module import successful"
    except Exception as e:
        print_result(False, f"Import error: {e}")
        return False, str(e)


def test_delta_api_connectivity() -> Tuple[bool, str]:
    """Test connectivity to Delta Exchange API"""
    print_header("3. API Connectivity Tests")
    
    print_test("Delta Exchange ticker API")
    try:
        response = requests.get(
            "https://api.india.delta.exchange/v2/tickers/BTCUSD",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'mark_price' in data['result']:
                price = data['result']['mark_price']
                print_result(True, f"BTC price: ${price}")
                return True, f"Delta API accessible (BTC: ${price})"
            else:
                print_result(False, "Unexpected response format")
                return False, "Unexpected response format"
        else:
            print_result(False, f"HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        print_result(False, f"Connection error: {e}")
        return False, str(e)


def test_delta_options_api() -> Tuple[bool, str]:
    """Test Delta Exchange options API"""
    print_test("Delta Exchange options API")
    try:
        response = requests.get(
            "https://api.india.delta.exchange/v2/tickers",
            params={
                'underlying_asset_symbols': 'BTC',
                'contract_types': 'call_options,put_options'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and len(data['result']) > 0:
                num_options = len(data['result'])
                print_result(True, f"Found {num_options} BTC options")
                return True, f"Options API accessible ({num_options} options)"
            else:
                print_result(False, "No options data")
                return False, "No options data"
        else:
            print_result(False, f"HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        print_result(False, f"Connection error: {e}")
        return False, str(e)


def test_delta_candles_api() -> Tuple[bool, str]:
    """Test Delta Exchange candles API"""
    print_test("Delta Exchange candles API")
    try:
        import time
        end_time = int(time.time())
        start_time = end_time - (24 * 3600)  # Last 24 hours
        
        response = requests.get(
            "https://api.india.delta.exchange/v2/history/candles",
            params={
                'symbol': 'BTCUSD',
                'resolution': '1h',
                'start': start_time,
                'end': end_time
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and len(data['result']) > 0:
                num_candles = len(data['result'])
                print_result(True, f"Found {num_candles} candles")
                return True, f"Candles API accessible ({num_candles} candles)"
            else:
                print_result(False, "No candle data")
                return False, "No candle data"
        else:
            print_result(False, f"HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        print_result(False, f"Connection error: {e}")
        return False, str(e)


def test_webui_running() -> Tuple[bool, str]:
    """Test if WebUI is running"""
    print_header("4. WebUI Tests")
    
    print_test("WebUI health endpoint")
    try:
        response = requests.get("http://localhost:5555/api/health", timeout=5)
        
        if response.status_code == 200:
            print_result(True, "WebUI is running")
            return True, "WebUI accessible"
        else:
            print_result(False, f"HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        print_result(False, f"WebUI not running: {e}")
        return False, "WebUI not running"


def test_volatility_endpoints() -> Tuple[bool, str]:
    """Test volatility API endpoints"""
    print_test("Volatility API endpoints")
    try:
        # Test latest endpoint
        response = requests.get("http://localhost:5555/api/risk/volatility/latest", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_result(True, "Volatility endpoints accessible")
                return True, "Endpoints working"
            else:
                print_result(False, f"API error: {data.get('error')}")
                return False, data.get('error', 'Unknown error')
        else:
            print_result(False, f"HTTP {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        print_result(False, f"Endpoint error: {e}")
        return False, str(e)


def test_data_collection() -> Tuple[bool, str]:
    """Test actual data collection"""
    print_header("5. Data Collection Tests")
    
    print_test("Collect IV data")
    try:
        from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector
        
        # Create collector with temporary database
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        collector = DeltaVolatilityCollector(db_path=temp_db.name)
        
        # Fetch IV
        iv_data = collector._fetch_and_store_iv()
        
        if iv_data and iv_data.get('value'):
            iv_value = iv_data['value']
            num_options = iv_data['num_options']
            print_result(True, f"IV: {iv_value:.2f}% from {num_options} options")
            success = True
        else:
            print_result(False, "Failed to fetch IV")
            success = False
        
        # Cleanup
        import os
        os.unlink(temp_db.name)
        
        return success, f"IV collection {'successful' if success else 'failed'}"
    except Exception as e:
        print_result(False, f"Collection error: {e}")
        return False, str(e)


def test_rv_calculation() -> Tuple[bool, str]:
    """Test RV calculation"""
    print_test("Calculate RV (daily)")
    try:
        from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector
        
        # Create collector with temporary database
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        collector = DeltaVolatilityCollector(db_path=temp_db.name)
        
        # Fetch RV
        rv_data = collector._fetch_and_store_rv('1d')
        
        if rv_data and rv_data.get('value'):
            rv_value = rv_data['value']
            num_candles = rv_data['num_candles']
            print_result(True, f"RV: {rv_value:.2f}% from {num_candles} candles")
            success = True
        else:
            print_result(False, "Failed to calculate RV")
            success = False
        
        # Cleanup
        import os
        os.unlink(temp_db.name)
        
        return success, f"RV calculation {'successful' if success else 'failed'}"
    except Exception as e:
        print_result(False, f"Calculation error: {e}")
        return False, str(e)


def print_summary(results: dict):
    """Print test summary"""
    print_header("Test Summary")
    
    total = len(results)
    passed = sum(1 for success, _ in results.values() if success)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print()
    
    if failed > 0:
        print(f"{RED}Failed Tests:{RESET}")
        for name, (success, message) in results.items():
            if not success:
                print(f"  ❌ {name}: {message}")
        print()
    
    if failed == 0:
        print(f"{GREEN}{BOLD}🎉 ALL TESTS PASSED!{RESET}")
        print()
        print("The volatility chart system is ready to use.")
        print()
        print("Next steps:")
        print("  1. Run: ./start_volatility_collector.sh")
        print("  2. Open: http://localhost:5555")
        print("  3. Navigate to Dashboard tab")
        print()
    else:
        print(f"{YELLOW}⚠️  Some tests failed. Please review the errors above.{RESET}")
        print()


def main():
    """Run all tests"""
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}VOLATILITY CHART SYSTEM - TEST SUITE{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    
    results = {}
    
    # Run tests
    results["File Existence"] = test_files_exist()
    results["Collector Import"] = test_collector_import()
    results["Collector Init"] = test_collector_initialization()
    results["Database Schema"] = test_database_schema()
    results["API Module Import"] = test_api_module_import()
    results["Delta Ticker API"] = test_delta_api_connectivity()
    results["Delta Options API"] = test_delta_options_api()
    results["Delta Candles API"] = test_delta_candles_api()
    results["WebUI Running"] = test_webui_running()
    results["Volatility Endpoints"] = test_volatility_endpoints()
    results["IV Collection"] = test_data_collection()
    results["RV Calculation"] = test_rv_calculation()
    
    # Print summary
    print_summary(results)
    
    # Exit code
    failed = sum(1 for success, _ in results.values() if not success)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
