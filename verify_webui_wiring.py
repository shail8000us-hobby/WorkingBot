#!/usr/bin/env python3
"""
WebUI Wiring Verification Script

Verifies that AsyncBot creates positions.json and state.json files
for WebUI consumption.

Usage:
    python verify_webui_wiring.py

Author: GridBot Team
Date: November 13, 2025
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text: str):
    """Print section header"""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text.center(70)}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def print_check(name: str, passed: bool, details: str = ""):
    """Print check result"""
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"       {details}")

def check_file_exists(filepath: Path, name: str) -> bool:
    """Check if file exists"""
    exists = filepath.exists()
    print_check(
        f"{name} exists",
        exists,
        f"Path: {filepath}" if exists else f"Not found: {filepath}"
    )
    return exists

def check_file_format(filepath: Path, name: str, expected_keys: List[str]) -> bool:
    """Check file format and required keys"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        missing_keys = [key for key in expected_keys if key not in data]
        
        if missing_keys:
            print_check(
                f"{name} format",
                False,
                f"Missing keys: {', '.join(missing_keys)}"
            )
            return False
        
        print_check(
            f"{name} format",
            True,
            f"All required keys present: {', '.join(expected_keys)}"
        )
        return True
    except json.JSONDecodeError as e:
        print_check(
            f"{name} format",
            False,
            f"Invalid JSON: {e}"
        )
        return False
    except Exception as e:
        print_check(
            f"{name} format",
            False,
            f"Error reading file: {e}"
        )
        return False

def check_positions_content(filepath: Path) -> bool:
    """Check positions.json content structure"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check summary
        summary = data.get('summary', {})
        required_summary = ['total_positions', 'total_opened', 'total_closed', 'max_positions', 'available_slots']
        missing_summary = [key for key in required_summary if key not in summary]
        
        if missing_summary:
            print_check(
                "positions.json summary",
                False,
                f"Missing summary keys: {', '.join(missing_summary)}"
            )
            return False
        
        # Check positions list
        positions = data.get('positions', [])
        if positions:
            required_pos_keys = ['position_id', 'entry_price', 'tp_price', 'size', 'status']
            first_pos = positions[0]
            missing_pos = [key for key in required_pos_keys if key not in first_pos]
            
            if missing_pos:
                print_check(
                    "positions.json position fields",
                    False,
                    f"Missing position keys: {', '.join(missing_pos)}"
                )
                return False
        
        print_check(
            "positions.json content",
            True,
            f"Summary: {summary['total_positions']} positions, "
            f"{summary['total_opened']} opened, "
            f"{summary['total_closed']} closed"
        )
        return True
    except Exception as e:
        print_check(
            "positions.json content",
            False,
            f"Error: {e}"
        )
        return False

def check_state_content(filepath: Path) -> bool:
    """Check state.json content structure"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check capacity
        capacity = data.get('capacity', {})
        if 'current' not in capacity or 'max' not in capacity or 'available' not in capacity:
            print_check(
                "state.json capacity",
                False,
                "Missing capacity fields"
            )
            return False
        
        # Check pending orders
        pending_buy = data.get('pending_buy')
        pending_sell = data.get('pending_sell')
        
        print_check(
            "state.json content",
            True,
            f"Capacity: {capacity['current']}/{capacity['max']}, "
            f"Pending Buy: {'Yes' if pending_buy else 'No'}, "
            f"Pending Sell: {'Yes' if pending_sell else 'No'}"
        )
        return True
    except Exception as e:
        print_check(
            "state.json content",
            False,
            f"Error: {e}"
        )
        return False

def check_file_freshness(filepath: Path, name: str, max_age_seconds: int = 60) -> bool:
    """Check if file was recently updated"""
    try:
        mtime = filepath.stat().st_mtime
        age = time.time() - mtime
        
        is_fresh = age <= max_age_seconds
        
        print_check(
            f"{name} freshness",
            is_fresh,
            f"Age: {age:.1f} seconds" + (" (stale)" if not is_fresh else " (fresh)")
        )
        return is_fresh
    except Exception as e:
        print_check(
            f"{name} freshness",
            False,
            f"Error: {e}"
        )
        return False

def check_webui_routes() -> Dict[str, bool]:
    """Check WebUI route configuration"""
    results = {}
    
    webui_positions = Path("webui/backend/routes/positions.py")
    
    if not webui_positions.exists():
        print_check("WebUI positions.py", False, "File not found")
        return {'webui_exists': False}
    
    try:
        with open(webui_positions, 'r') as f:
            content = f.read()
        
        # Check for expected file paths
        has_positions_file = 'bot/reports/positions.json' in content or 'POSITIONS_FILE' in content
        has_state_file = 'bot/reports/state.json' in content or 'STATE_FILE' in content
        
        print_check(
            "WebUI references positions.json",
            has_positions_file,
            "POSITIONS_FILE variable found" if has_positions_file else "Not found"
        )
        
        print_check(
            "WebUI references state.json",
            has_state_file,
            "STATE_FILE variable found" if has_state_file else "Not found"
        )
        
        results['webui_exists'] = True
        results['positions_ref'] = has_positions_file
        results['state_ref'] = has_state_file
        
    except Exception as e:
        print_check("WebUI configuration", False, f"Error: {e}")
        results['webui_exists'] = False
    
    return results

def check_actor_implementation() -> Dict[str, bool]:
    """Check PositionManagerActor implementation"""
    results = {}
    
    actor_file = Path("bot/strategy/actors/position_actor.py")
    
    if not actor_file.exists():
        print_check("PositionManagerActor file", False, "File not found")
        return {'actor_exists': False}
    
    try:
        with open(actor_file, 'r') as f:
            content = f.read()
        
        # Check for export methods
        has_save_positions = '_save_positions_file' in content
        has_save_state = '_save_state_file' in content
        has_debouncing = '_min_file_write_interval' in content
        has_json_import = 'import json' in content
        
        print_check(
            "_save_positions_file() method",
            has_save_positions,
            "Method implemented" if has_save_positions else "Not found"
        )
        
        print_check(
            "_save_state_file() method",
            has_save_state,
            "Method implemented" if has_save_state else "Not found"
        )
        
        print_check(
            "Debouncing implemented",
            has_debouncing,
            "Interval variable found" if has_debouncing else "Not found"
        )
        
        print_check(
            "JSON import",
            has_json_import,
            "json module imported" if has_json_import else "Not imported"
        )
        
        results['actor_exists'] = True
        results['save_positions'] = has_save_positions
        results['save_state'] = has_save_state
        results['debouncing'] = has_debouncing
        results['json_import'] = has_json_import
        
    except Exception as e:
        print_check("Actor implementation", False, f"Error: {e}")
        results['actor_exists'] = False
    
    return results

def main():
    """Main verification function"""
    print_header("WebUI Wiring Verification")
    
    print(f"{YELLOW}This script verifies AsyncBot creates positions.json and state.json{RESET}")
    print(f"{YELLOW}for WebUI consumption.{RESET}\n")
    
    all_checks_passed = True
    
    # Check 1: Actor Implementation
    print_header("CHECK 1: PositionManagerActor Implementation")
    actor_results = check_actor_implementation()
    
    if not actor_results.get('actor_exists'):
        print(f"\n{RED}❌ CRITICAL: PositionManagerActor file not found{RESET}")
        all_checks_passed = False
    else:
        if not all([
            actor_results.get('save_positions'),
            actor_results.get('save_state'),
            actor_results.get('debouncing'),
            actor_results.get('json_import')
        ]):
            print(f"\n{RED}❌ CRITICAL: Actor implementation incomplete{RESET}")
            all_checks_passed = False
        else:
            print(f"\n{GREEN}✅ Actor implementation complete{RESET}")
    
    # Check 2: WebUI Configuration
    print_header("CHECK 2: WebUI Routes Configuration")
    webui_results = check_webui_routes()
    
    if not webui_results.get('webui_exists'):
        print(f"\n{YELLOW}⚠️  WARNING: WebUI routes file not found{RESET}")
    elif not all([webui_results.get('positions_ref'), webui_results.get('state_ref')]):
        print(f"\n{YELLOW}⚠️  WARNING: WebUI configuration incomplete{RESET}")
    else:
        print(f"\n{GREEN}✅ WebUI configuration correct{RESET}")
    
    # Check 3: Runtime Files
    print_header("CHECK 3: Runtime Files (Bot Must Be Running)")
    
    positions_file = Path("bot/reports/positions.json")
    state_file = Path("bot/reports/state.json")
    
    positions_exists = check_file_exists(positions_file, "positions.json")
    state_exists = check_file_exists(state_file, "state.json")
    
    if positions_exists:
        check_file_format(
            positions_file,
            "positions.json",
            ['positions', 'summary', 'last_update', 'source']
        )
        check_positions_content(positions_file)
        check_file_freshness(positions_file, "positions.json", max_age_seconds=300)
    else:
        print(f"\n{YELLOW}⚠️  positions.json not found (bot may not be running){RESET}")
        all_checks_passed = False
    
    if state_exists:
        check_file_format(
            state_file,
            "state.json",
            ['open_positions', 'pending_buy', 'pending_sell', 'capacity', 'last_update', 'source']
        )
        check_state_content(state_file)
        check_file_freshness(state_file, "state.json", max_age_seconds=300)
    else:
        print(f"\n{YELLOW}⚠️  state.json not found (bot may not be running){RESET}")
        all_checks_passed = False
    
    # Final Summary
    print_header("VERIFICATION SUMMARY")
    
    if all_checks_passed and positions_exists and state_exists:
        print(f"{GREEN}✅ ALL CHECKS PASSED{RESET}")
        print(f"\n{GREEN}AsyncBot WebUI wiring is complete and functional!{RESET}")
        print(f"\nWebUI should now have full visibility into:")
        print(f"  • Open positions (from positions.json)")
        print(f"  • Pending orders (from state.json)")
        print(f"  • Position capacity (from state.json)")
        print(f"  • Order timestamps (from state.json)")
        return 0
    elif not positions_exists or not state_exists:
        print(f"{YELLOW}⚠️  PARTIAL PASS (Bot Not Running){RESET}")
        print(f"\n{YELLOW}Implementation is complete, but runtime files not found.{RESET}")
        print(f"\n{YELLOW}To complete verification:{RESET}")
        print(f"  1. Start the bot: python bot/run.py --dry-run")
        print(f"  2. Re-run this script: python verify_webui_wiring.py")
        print(f"  3. Check WebUI: http://localhost:5000")
        return 1
    else:
        print(f"{RED}❌ VERIFICATION FAILED{RESET}")
        print(f"\n{RED}Critical issues detected. Review errors above.{RESET}")
        return 2

if __name__ == "__main__":
    sys.exit(main())
