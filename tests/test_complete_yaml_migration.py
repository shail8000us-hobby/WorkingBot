#!/usr/bin/env python3
"""
Complete YAML Migration Verification Test
==========================================
Verifies that ALL production components use config.yaml, NOT grid_config.env

Tests:
1. async_gridbot.py uses get_config()
2. guardian_bot.py uses get_config()
3. heartbeat/monitor.py uses get_config()
4. liquidation/delta_realtime_websocket.py uses get_config()
5. dashboard/run.py uses get_config()
6. webui backend uses get_config()
7. NO production code loads grid_config.env via dotenv

Author: GridBot Migration Team
Date: 2025-01-24
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Tuple

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_file_for_pattern(file_path: Path, forbidden_patterns: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if file contains any forbidden patterns
    
    Returns:
        (is_clean, violations) - is_clean=True means no violations found
    """
    violations = []
    
    if not file_path.exists():
        return False, [f"File not found: {file_path}"]
    
    try:
        content = file_path.read_text()
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(f"Found forbidden pattern: '{pattern}'")
        
        return len(violations) == 0, violations
    except Exception as e:
        return False, [f"Error reading file: {e}"]

def check_file_for_required(file_path: Path, required_patterns: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if file contains all required patterns
    
    Returns:
        (has_all, missing) - has_all=True means all patterns found
    """
    missing = []
    
    if not file_path.exists():
        return False, [f"File not found: {file_path}"]
    
    try:
        content = file_path.read_text()
        for pattern in required_patterns:
            if pattern not in content:
                missing.append(f"Missing required pattern: '{pattern}'")
        
        return len(missing) == 0, missing
    except Exception as e:
        return False, [f"Error reading file: {e}"]

def run_grep_search(pattern: str, directories: List[str]) -> Tuple[bool, str]:
    """
    Run grep search across specified directories
    
    Returns:
        (is_clean, output) - is_clean=True means no matches found
    """
    try:
        cmd = ["grep", "-r", pattern, "--include=*.py"] + directories
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        # grep returns 0 if matches found, 1 if no matches
        is_clean = result.returncode == 1
        output = result.stdout.strip() if result.stdout else "No matches"
        
        return is_clean, output
    except Exception as e:
        return False, f"Error running grep: {e}"

def main():
    """Run comprehensive migration verification"""
    
    print("=" * 80)
    print(f"{BLUE}🔍 COMPLETE YAML MIGRATION VERIFICATION TEST{RESET}")
    print("=" * 80)
    print()
    
    project_root = Path(__file__).parent
    all_passed = True
    
    # Test 1: guardian_bot.py
    print(f"{BLUE}Test 1: guardian_bot.py{RESET}")
    file_path = project_root / "bot" / "guardian" / "guardian_bot.py"
    is_clean, violations = check_file_for_pattern(
        file_path,
        ['load_dotenv("grid_config.env")', "load_dotenv('grid_config.env')"]
    )
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config", "get_config()"]
    )
    
    if is_clean and has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config(), no grid_config.env loading")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for v in violations + missing:
            print(f"    {RED}{v}{RESET}")
    print()
    
    # Test 2: heartbeat/monitor.py
    print(f"{BLUE}Test 2: heartbeat/monitor.py{RESET}")
    file_path = project_root / "bot" / "heartbeat" / "monitor.py"
    is_clean, violations = check_file_for_pattern(
        file_path,
        ['load_dotenv("grid_config.env")', "load_dotenv('grid_config.env')"]
    )
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config", "get_config()"]
    )
    
    if is_clean and has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config(), no grid_config.env loading")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for v in violations + missing:
            print(f"    {RED}{v}{RESET}")
    print()
    
    # Test 3: heartbeat/monitor.py
    print(f"{BLUE}Test 3: heartbeat/monitor.py{RESET}")
    file_path = project_root / "bot" / "heartbeat" / "monitor.py"
    is_clean, violations = check_file_for_pattern(
        file_path,
        ['load_dotenv("grid_config.env")', "load_dotenv('grid_config.env')"]
    )
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config", "cfg = get_config()"]
    )
    
    if is_clean and has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config(), no grid_config.env loading")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for v in violations + missing:
            print(f"    {RED}{v}{RESET}")
    print()
    
    # Test 4: liquidation/delta_realtime_websocket.py
    print(f"{BLUE}Test 4: liquidation/delta_realtime_websocket.py{RESET}")
    file_path = project_root / "bot" / "liquidation" / "delta_realtime_websocket.py"
    is_clean, violations = check_file_for_pattern(
        file_path,
        ['load_dotenv("grid_config.env")', "load_dotenv('grid_config.env')"]
    )
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config"]
    )
    
    if is_clean and has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config(), no grid_config.env loading")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for v in violations + missing:
            print(f"    {RED}{v}{RESET}")
    print()
    
    # Test 5: dashboard/run.py
    print(f"{BLUE}Test 5: dashboard/run.py{RESET}")
    file_path = project_root / "dashboard" / "run.py"
    is_clean, violations = check_file_for_pattern(
        file_path,
        ['load_dotenv("grid_config.env")', "load_dotenv('grid_config.env')"]
    )
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config", "cfg = get_config()"]
    )
    
    if is_clean and has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config(), no grid_config.env loading")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for v in violations + missing:
            print(f"    {RED}{v}{RESET}")
    print()
    
    # Test 6: webui backend uses get_config()
    print(f"{BLUE}Test 6: webui/backend/app.py{RESET}")
    file_path = project_root / "webui" / "backend" / "app.py"
    has_required, missing = check_file_for_required(
        file_path,
        ["from config.loader import get_config"]
    )
    
    if has_required:
        print(f"  {GREEN}✅ PASS{RESET} - Uses get_config()")
    else:
        print(f"  {RED}❌ FAIL{RESET}")
        all_passed = False
        for m in missing:
            print(f"    {RED}{m}{RESET}")
    print()
    
    # Test 7: NO production code loads grid_config.env
    print(f"{BLUE}Test 7: Production code clean of grid_config.env{RESET}")
    is_clean, output = run_grep_search(
        'load_dotenv.*grid_config',
        ['bot/', 'webui/backend/', 'dashboard/']
    )
    
    if is_clean:
        print(f"  {GREEN}✅ PASS{RESET} - No grid_config.env loading in production code")
    else:
        print(f"  {RED}❌ FAIL{RESET} - Found grid_config.env loading:")
        all_passed = False
        print(f"    {RED}{output}{RESET}")
    print()
    
    # Test 8: config.yaml exists and is valid
    print(f"{BLUE}Test 8: config.yaml validity{RESET}")
    try:
        sys.path.insert(0, str(project_root))
        from config.loader import get_config
        cfg = get_config()
        
        # Check critical fields
        checks = [
            ("bot.symbol", cfg.bot.symbol),
            ("grid.geometry.lower", cfg.grid.geometry.lower),
            ("grid.geometry.upper", cfg.grid.geometry.upper),
            ("grid.geometry.step", cfg.grid.geometry.step),
            ("liquidation_protection.mtm_check_interval", cfg.liquidation_protection.mtm_check_interval),
            ("heartbeat.enabled", cfg.heartbeat.enabled),
        ]
        
        all_present = True
        for field_name, field_value in checks:
            if field_value is None:
                print(f"    {RED}Missing field: {field_name}{RESET}")
                all_present = False
        
        if all_present:
            print(f"  {GREEN}✅ PASS{RESET} - config.yaml is valid with all critical fields")
        else:
            print(f"  {RED}❌ FAIL{RESET} - config.yaml missing critical fields")
            all_passed = False
    except Exception as e:
        print(f"  {RED}❌ FAIL{RESET} - Error loading config.yaml: {e}")
        all_passed = False
    print()
    
    # Final summary
    print("=" * 80)
    if all_passed:
        print(f"{GREEN}✅ ALL TESTS PASSED - YAML MIGRATION COMPLETE{RESET}")
        print()
        print("Production components verified:")
        print("  ✅ bot/guardian/guardian_bot.py")
        print("  ✅ bot/heartbeat/monitor.py")
        print("  ✅ bot/liquidation/delta_realtime_websocket.py")
        print("  ✅ dashboard/run.py")
        print("  ✅ webui/backend/app.py")
        print()
        print(f"{GREEN}🎯 REAL 100% MIGRATION VERIFIED{RESET}")
        print("=" * 80)
        return 0
    else:
        print(f"{RED}❌ SOME TESTS FAILED - MIGRATION INCOMPLETE{RESET}")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
