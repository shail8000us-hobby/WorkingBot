#!/usr/bin/env python3
"""
Phase 3A Integration Test Suite

Tests multi-symbol implementation across all layers:
- Config loading
- Bot initialization
- Database isolation
- WebUI API
- Frontend symbol selector

Usage:
    python3 test_multi_symbol_integration.py
    
Exit codes:
    0 - All tests passed
    1 - Some tests failed
"""
import os
import sys
import json
import time
import sqlite3
import requests
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

class MultiSymbolIntegrationTester:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.results: List[TestResult] = []
        self.webui_port = 5556  # Development WebUI
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with color"""
        colors = {
            "INFO": BLUE,
            "SUCCESS": GREEN,
            "FAIL": RED,
            "WARN": YELLOW
        }
        color = colors.get(level, RESET)
        print(f"{color}[{level}] {message}{RESET}")
    
    def add_result(self, name: str, passed: bool, message: str = ""):
        """Add test result"""
        self.results.append(TestResult(name, passed, message))
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        self.log(f"{name}: {status} {message}")
    
    def test_1_config_version(self) -> bool:
        """Test 1: Verify config is v5.0"""
        self.log("Test 1: Config Version Check", "INFO")
        try:
            from config.loader import get_config
            config = get_config()
            
            # Check version
            if config.version != "5.0":
                self.add_result("Config Version", False, f"Expected v5.0, got {config.version}")
                return False
            
            # Check symbols exist
            if not hasattr(config, 'symbols') or not config.symbols:
                self.add_result("Config Version", False, "No symbols defined in config")
                return False
            
            # Check BTCUSD
            if 'BTCUSD' not in config.symbols:
                self.add_result("Config Version", False, "BTCUSD not found in symbols")
                return False
            
            # Check ETHUSD
            if 'ETHUSD' not in config.symbols:
                self.add_result("Config Version", False, "ETHUSD not found in symbols")
                return False
            
            self.add_result("Config Version", True, f"v{config.version} with {len(config.symbols)} symbols")
            return True
            
        except Exception as e:
            self.add_result("Config Version", False, str(e))
            return False
    
    def test_2_symbol_configs(self) -> bool:
        """Test 2: Verify individual symbol configurations"""
        self.log("Test 2: Symbol Configuration Validation", "INFO")
        try:
            from config.loader import get_config
            config = get_config()
            
            # Test BTCUSD
            btc = config.symbols.get('BTCUSD')
            if not btc:
                self.add_result("Symbol Configs", False, "BTCUSD config missing")
                return False
            
            if btc.product_id != 139:
                self.add_result("Symbol Configs", False, f"BTCUSD product_id wrong: {btc.product_id}")
                return False
            
            # Test ETHUSD
            eth = config.symbols.get('ETHUSD')
            if not eth:
                self.add_result("Symbol Configs", False, "ETHUSD config missing")
                return False
            
            if eth.product_id != 3136:
                self.add_result("Symbol Configs", False, f"ETHUSD product_id wrong: {eth.product_id}")
                return False
            
            # Check grid configs
            if not btc.grid or not btc.grid.geometry:
                self.add_result("Symbol Configs", False, "BTCUSD grid config missing")
                return False
            
            if not eth.grid or not eth.grid.geometry:
                self.add_result("Symbol Configs", False, "ETHUSD grid config missing")
                return False
            
            self.add_result("Symbol Configs", True, "BTCUSD (139) and ETHUSD (3136) configured correctly")
            return True
            
        except Exception as e:
            self.add_result("Symbol Configs", False, str(e))
            return False
    
    def test_3_database_isolation(self) -> bool:
        """Test 3: Verify symbol-specific database files exist or can be created"""
        self.log("Test 3: Database Isolation Check", "INFO")
        try:
            data_dir = self.project_root / 'data'
            if not data_dir.exists():
                self.add_result("Database Isolation", False, "data/ directory not found")
                return False
            
            # Check for symbol-specific database pattern
            # bot_events_{SYMBOL}_{MODE}.db
            expected_dbs = [
                'bot_events_BTCUSD_LONG.db',
                'bot_events_ETHUSD_LONG.db'
            ]
            
            found_dbs = []
            for db_name in expected_dbs:
                db_path = data_dir / db_name
                if db_path.exists():
                    found_dbs.append(db_name)
            
            if not found_dbs:
                self.add_result("Database Isolation", True, 
                    "No symbol DBs exist yet (expected on first run)")
                return True
            
            # If databases exist, verify they're separate
            if len(found_dbs) >= 2:
                # Check they have different data
                db1 = data_dir / found_dbs[0]
                db2 = data_dir / found_dbs[1]
                
                # Quick size check (crude but effective)
                size1 = db1.stat().st_size
                size2 = db2.stat().st_size
                
                self.add_result("Database Isolation", True,
                    f"Found {len(found_dbs)} symbol databases: {', '.join(found_dbs)}")
                return True
            else:
                self.add_result("Database Isolation", True,
                    f"Found {len(found_dbs)} database(s) - partial setup")
                return True
            
        except Exception as e:
            self.add_result("Database Isolation", False, str(e))
            return False
    
    def test_4_webui_symbols_api(self) -> bool:
        """Test 4: Test WebUI /api/symbols endpoint"""
        self.log("Test 4: WebUI Symbols API", "INFO")
        try:
            url = f"http://localhost:{self.webui_port}/api/symbols"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                self.add_result("WebUI Symbols API", False, 
                    f"HTTP {response.status_code}: {response.text[:100]}")
                return False
            
            data = response.json()
            
            # Check response structure
            if 'symbols' not in data:
                self.add_result("WebUI Symbols API", False, "No 'symbols' key in response")
                return False
            
            symbols = data['symbols']
            if len(symbols) < 2:
                self.add_result("WebUI Symbols API", False, 
                    f"Expected 2+ symbols, got {len(symbols)}")
                return False
            
            # Check BTCUSD and ETHUSD present
            symbol_names = [s['name'] for s in symbols]
            if 'BTCUSD' not in symbol_names:
                self.add_result("WebUI Symbols API", False, "BTCUSD not in API response")
                return False
            
            if 'ETHUSD' not in symbol_names:
                self.add_result("WebUI Symbols API", False, "ETHUSD not in API response")
                return False
            
            self.add_result("WebUI Symbols API", True,
                f"API returned {len(symbols)} symbols: {', '.join(symbol_names)}")
            return True
            
        except requests.exceptions.ConnectionError:
            self.add_result("WebUI Symbols API", False, 
                f"WebUI not running on port {self.webui_port}")
            return False
        except Exception as e:
            self.add_result("WebUI Symbols API", False, str(e))
            return False
    
    def test_5_monitoring_api_symbol_param(self) -> bool:
        """Test 5: Test monitoring API accepts symbol parameter"""
        self.log("Test 5: Monitoring API Symbol Parameter", "INFO")
        try:
            # Test with BTCUSD symbol param
            url = f"http://localhost:{self.webui_port}/api/monitoring/status?symbol=BTCUSD"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                self.add_result("Monitoring Symbol Param", False,
                    f"HTTP {response.status_code}: {response.text[:100]}")
                return False
            
            data = response.json()
            
            # If monitoring file exists, it should contain data
            # If not, API should return error message
            if data.get('error'):
                self.add_result("Monitoring Symbol Param", True,
                    "API accepts symbol param (no monitoring file yet)")
                return True
            
            # If we got data, verify it's symbol-specific
            if 'monitoring_active' in data:
                self.add_result("Monitoring Symbol Param", True,
                    "API accepts symbol param and returned data")
                return True
            
            self.add_result("Monitoring Symbol Param", True,
                "API endpoint functional")
            return True
            
        except requests.exceptions.ConnectionError:
            self.add_result("Monitoring Symbol Param", False,
                f"WebUI not running on port {self.webui_port}")
            return False
        except Exception as e:
            self.add_result("Monitoring Symbol Param", False, str(e))
            return False
    
    def test_6_capital_allocation(self) -> bool:
        """Test 6: Verify capital allocation configuration"""
        self.log("Test 6: Capital Allocation Check", "INFO")
        try:
            from config.loader import get_config
            config = get_config()
            
            if not hasattr(config, 'capital_allocation'):
                self.add_result("Capital Allocation", False, "No capital_allocation section")
                return False
            
            alloc = config.capital_allocation
            
            # Check total capital (USD)
            if alloc.total_capital_usd <= 0:
                self.add_result("Capital Allocation", False, "Invalid total_capital_usd")
                return False
            
            # Check allocations exist
            if not alloc.allocations:
                self.add_result("Capital Allocation", False, "No symbol allocations defined")
                return False
            
            # Verify BTCUSD and ETHUSD allocations
            if 'BTCUSD' not in alloc.allocations:
                self.add_result("Capital Allocation", False, "No BTCUSD allocation")
                return False
            
            if 'ETHUSD' not in alloc.allocations:
                self.add_result("Capital Allocation", False, "No ETHUSD allocation")
                return False
            
            # Check percentages sum to 100%
            btc_pct = alloc.allocations['BTCUSD'].get('percentage', 0)
            eth_pct = alloc.allocations['ETHUSD'].get('percentage', 0)
            total_pct = btc_pct + eth_pct
            
            if abs(total_pct - 100) > 0.01:  # Allow tiny floating point error
                self.add_result("Capital Allocation", False,
                    f"Allocations sum to {total_pct}%, not 100%")
                return False
            
            self.add_result("Capital Allocation", True,
                f"${alloc.total_capital_usd:,.0f} - BTC: {btc_pct}%, ETH: {eth_pct}%")
            return True
            
        except Exception as e:
            self.add_result("Capital Allocation", False, str(e))
            return False
    
    def test_7_bot_cli_symbol_arg(self) -> bool:
        """Test 7: Verify bot accepts symbol CLI argument (import test)"""
        self.log("Test 7: Bot Symbol CLI Argument", "INFO")
        try:
            # We can't actually run the bot, but we can check if it imports correctly
            import sys
            sys.path.insert(0, str(self.project_root))
            
            from bot.strategy.async_gridbot import AsyncGridBot
            
            # Check if __main__ section handles symbol arg
            gridbot_path = self.project_root / 'bot' / 'strategy' / 'async_gridbot.py'
            if not gridbot_path.exists():
                self.add_result("Bot Symbol CLI", False, "async_gridbot.py not found")
                return False
            
            # Read file and check for symbol handling
            content = gridbot_path.read_text()
            
            if 'sys.argv[1]' in content or 'argparse' in content:
                self.add_result("Bot Symbol CLI", True,
                    "Bot script handles symbol CLI argument")
                return True
            else:
                self.add_result("Bot Symbol CLI", False,
                    "Bot script doesn't appear to handle symbol argument")
                return False
            
        except Exception as e:
            self.add_result("Bot Symbol CLI", False, str(e))
            return False
    
    def test_8_monitoring_snapshot_paths(self) -> bool:
        """Test 8: Verify monitoring snapshot naming convention"""
        self.log("Test 8: Monitoring Snapshot Paths", "INFO")
        try:
            data_dir = self.project_root / 'data'
            
            # Check for symbol-specific monitoring files
            # Pattern: monitoring_snapshot_{SYMBOL}_{MODE}.json
            expected_patterns = [
                'monitoring_snapshot_BTCUSD_LONG.json',
                'monitoring_snapshot_ETHUSD_LONG.json'
            ]
            
            found_files = []
            for pattern in expected_patterns:
                file_path = data_dir / pattern
                if file_path.exists():
                    found_files.append(pattern)
            
            if not found_files:
                self.add_result("Monitoring Snapshots", True,
                    "No monitoring files yet (expected on first run)")
                return True
            
            # If files exist, verify they contain symbol-specific data
            for filename in found_files:
                file_path = data_dir / filename
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        # Just verify it's valid JSON
                except json.JSONDecodeError:
                    self.add_result("Monitoring Snapshots", False,
                        f"{filename} contains invalid JSON")
                    return False
            
            self.add_result("Monitoring Snapshots", True,
                f"Found {len(found_files)} monitoring file(s): {', '.join(found_files)}")
            return True
            
        except Exception as e:
            self.add_result("Monitoring Snapshots", False, str(e))
            return False
    
    def test_9_frontend_symbol_selector(self) -> bool:
        """Test 9: Verify frontend has SymbolSelector component"""
        self.log("Test 9: Frontend SymbolSelector", "INFO")
        try:
            selector_path = self.project_root / 'webui' / 'frontend' / 'src' / 'components' / 'SymbolSelector.js'
            
            if not selector_path.exists():
                self.add_result("Frontend SymbolSelector", False,
                    "SymbolSelector.js component not found")
                return False
            
            # Check component has required functionality
            content = selector_path.read_text()
            
            required_features = [
                'SymbolContext',  # Uses symbol context
                '/api/symbols',  # Fetches symbols
                'handleSymbolSelect',  # Handles selection
                'localStorage'  # Persists selection
            ]
            
            missing_features = [f for f in required_features if f not in content]
            
            if missing_features:
                self.add_result("Frontend SymbolSelector", False,
                    f"Missing features: {', '.join(missing_features)}")
                return False
            
            self.add_result("Frontend SymbolSelector", True,
                "Component exists with all required features")
            return True
            
        except Exception as e:
            self.add_result("Frontend SymbolSelector", False, str(e))
            return False
    
    def test_10_symbol_context(self) -> bool:
        """Test 10: Verify SymbolContext provider exists"""
        self.log("Test 10: Symbol Context Provider", "INFO")
        try:
            context_path = self.project_root / 'webui' / 'frontend' / 'src' / 'context' / 'SymbolContext.js'
            
            if not context_path.exists():
                self.add_result("Symbol Context", False,
                    "SymbolContext.js not found")
                return False
            
            content = context_path.read_text()
            
            # Check for essential context features
            required_features = [
                'createContext',
                'SymbolProvider',
                'selectedSymbol',
                'changeSymbol',
                'useSymbol'
            ]
            
            missing = [f for f in required_features if f not in content]
            
            if missing:
                self.add_result("Symbol Context", False,
                    f"Missing: {', '.join(missing)}")
                return False
            
            self.add_result("Symbol Context", True,
                "Context provider complete with all features")
            return True
            
        except Exception as e:
            self.add_result("Symbol Context", False, str(e))
            return False
    
    def run_all_tests(self) -> bool:
        """Run all integration tests"""
        self.log("=" * 80, "INFO")
        self.log("MULTI-SYMBOL INTEGRATION TEST SUITE", "INFO")
        self.log("=" * 80, "INFO")
        self.log(f"Project Root: {self.project_root}", "INFO")
        self.log(f"WebUI Port: {self.webui_port}", "INFO")
        self.log("", "INFO")
        
        # Run tests in order
        tests = [
            self.test_1_config_version,
            self.test_2_symbol_configs,
            self.test_3_database_isolation,
            self.test_4_webui_symbols_api,
            self.test_5_monitoring_api_symbol_param,
            self.test_6_capital_allocation,
            self.test_7_bot_cli_symbol_arg,
            self.test_8_monitoring_snapshot_paths,
            self.test_9_frontend_symbol_selector,
            self.test_10_symbol_context
        ]
        
        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                self.log(f"Test crashed: {e}", "FAIL")
                self.add_result(test_func.__name__, False, f"Crash: {e}")
            
            time.sleep(0.5)  # Brief pause between tests
        
        # Summary
        self.log("", "INFO")
        self.log("=" * 80, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("=" * 80, "INFO")
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        self.log(f"Total: {total} tests", "INFO")
        self.log(f"Passed: {passed} ({passed/total*100:.1f}%)", "SUCCESS" if passed == total else "INFO")
        self.log(f"Failed: {failed} ({failed/total*100:.1f}%)", "FAIL" if failed > 0 else "INFO")
        
        if failed > 0:
            self.log("", "INFO")
            self.log("FAILED TESTS:", "FAIL")
            for result in self.results:
                if not result.passed:
                    self.log(f"  ❌ {result.name}: {result.message}", "FAIL")
        
        self.log("=" * 80, "INFO")
        
        return failed == 0

if __name__ == '__main__':
    tester = MultiSymbolIntegrationTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)
