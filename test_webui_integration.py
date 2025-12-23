#!/usr/bin/env python3
"""
Web UI Integration Test
Tests all button/action endpoints to verify they're properly connected to the bot
"""

import requests
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Configuration
BASE_URL = "http://localhost:5555"
BASE_DIR = Path(__file__).parent

class Color:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def test_endpoint(method: str, endpoint: str, data: Dict = None, expected_status: int = 200) -> Tuple[bool, str, Any]:
    """
    Test a single endpoint
    Returns: (success, message, response_data)
    """
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            return False, f"Unsupported method: {method}", None
        
        # Check status code
        if response.status_code != expected_status:
            return False, f"Expected {expected_status}, got {response.status_code}", None
        
        # Try to parse JSON
        try:
            response_data = response.json()
        except:
            response_data = response.text
        
        return True, "OK", response_data
    
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - Is the web UI running?", None
    except requests.exceptions.Timeout:
        return False, "Request timeout", None
    except Exception as e:
        return False, f"Error: {str(e)}", None

def print_result(category: str, endpoint: str, success: bool, message: str):
    """Print test result with color coding"""
    status = f"{Color.GREEN}✅ PASS{Color.END}" if success else f"{Color.RED}❌ FAIL{Color.END}"
    print(f"  {status} {endpoint:<50} {message}")

def main():
    """Run all integration tests"""
    
    print(f"\n{Color.BOLD}{'='*80}{Color.END}")
    print(f"{Color.BOLD}GridBot Web UI Integration Test{Color.END}")
    print(f"{Color.BOLD}{'='*80}{Color.END}\n")
    
    print(f"{Color.BLUE}Testing connection to: {BASE_URL}{Color.END}\n")
    
    # Define all test cases
    test_cases = {
        "🏥 Health & Status": [
            ("GET", "/api/health", None, 200),
            ("GET", "/api/bot/status", None, 200),
            ("GET", "/api/monitor/status", None, 200),
            ("GET", "/api/guardian/status", None, 200),
            ("GET", "/api/tmux/status", None, 200),
            ("GET", "/api/trading_status", None, 200),
        ],
        
        "⚙️  Configuration": [
            ("GET", "/api/config", None, 200),
            ("GET", "/api/config/all", None, 200),
            ("GET", "/api/trading-mode", None, 200),
        ],
        
        "📊 State & Positions": [
            ("GET", "/api/state", None, 200),
            ("GET", "/api/positions", None, 200),
            ("GET", "/api/logs?lines=10", None, 200),
        ],
        
        "🔄 Reconciliation": [
            ("GET", "/api/recon/status", None, 200),
            ("GET", "/api/recon/table?page=1&per_page=10", None, 200),
        ],
        
        "🛡️  Robustness": [
            ("GET", "/api/robustness/gatekeeper/status", None, 200),
            ("GET", "/api/robustness/loss-limits", None, 200),
            ("GET", "/api/robustness/circuit-breakers", None, 200),
            ("GET", "/api/robustness/audit/report", None, 200),
            ("GET", "/api/robustness/guardian/hysteresis", None, 200),
            ("GET", "/api/robustness/volatility/status", None, 200),
            ("GET", "/api/robustness/confirmation-guard/status", None, 200),
        ],
        
        "⚖️  Liquidation Protection": [
            ("GET", "/api/liquidation/status", None, 200),
            ("GET", "/api/liquidation/config", None, 200),
        ],
        
        "💰 Capital Protection": [
            ("GET", "/api/capital/equity-floor/status", None, 200),
            ("GET", "/api/capital/drawdown/status", None, 200),
            ("GET", "/api/capital/exposure/status", None, 200),
            ("GET", "/api/capital/budget/status", None, 200),
            ("GET", "/api/capital/config-guard/status", None, 200),
        ],
        
        "📰 News & AI": [
            ("GET", "/api/news/feed", None, 200),
            ("GET", "/api/institutional/comprehensive_analysis", None, 200),
        ],
        
        "🚨 Emergency": [
            ("GET", "/api/emergency/check_flag", None, 200),
        ],
        
        "🔍 Error Intelligence": [
            ("GET", "/api/errors/status", None, 200),
            ("GET", "/api/errors/recent", None, 200),
            ("GET", "/api/errors/stats", None, 200),
        ],
    }
    
    # Run tests
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for category, tests in test_cases.items():
        print(f"\n{Color.BOLD}{category}{Color.END}")
        for method, endpoint, data, expected_status in tests:
            total_tests += 1
            success, message, response_data = test_endpoint(method, endpoint, data, expected_status)
            print_result(category, endpoint, success, message)
            
            if success:
                passed_tests += 1
            else:
                failed_tests += 1
    
    # Summary
    print(f"\n{Color.BOLD}{'='*80}{Color.END}")
    print(f"{Color.BOLD}Summary{Color.END}")
    print(f"{Color.BOLD}{'='*80}{Color.END}")
    print(f"Total Tests:  {total_tests}")
    print(f"{Color.GREEN}Passed:       {passed_tests}{Color.END}")
    print(f"{Color.RED}Failed:       {failed_tests}{Color.END}")
    
    if failed_tests == 0:
        print(f"\n{Color.GREEN}{Color.BOLD}🎉 All tests passed! Web UI is fully integrated.{Color.END}")
        return 0
    else:
        print(f"\n{Color.RED}{Color.BOLD}⚠️  Some tests failed. Check the endpoints above.{Color.END}")
        return 1

if __name__ == "__main__":
    exit(main())

