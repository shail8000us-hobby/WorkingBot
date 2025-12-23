#!/usr/bin/env python3
"""
Parameter Sync Checker
Validates that GRIDBOT_* and legacy GRID_* parameters are in sync
"""

import os
import json
from pathlib import Path

from bot.state.store import load_state_file
from dotenv import dotenv_values
from typing import Dict, List, Tuple

# ANSI colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def load_config() -> Dict[str, str]:
    """Load configuration from config.yaml"""
    project_root = Path(__file__).parent.parent
    from config.loader import get_config
    cfg = get_config()
    
    # Convert YAML to flat dict for compatibility
    config = {
        'GRIDBOT_LOWER': str(cfg.grid.geometry.lower),
        'GRIDBOT_UPPER': str(cfg.grid.geometry.upper),
        'GRIDBOT_STEP': str(cfg.grid.geometry.step),
    }
    return config

def load_state() -> Dict:
    """Load state.json"""
    project_root = Path(__file__).parent.parent
    state_file = project_root / 'state.json'
    
    if not state_file.exists():
        return {}
    
    with open(state_file, 'r') as f:
        return json.load(f)

def check_param_match(config: Dict[str, str], modern: str, legacy: str, 
                     name: str) -> Tuple[bool, str]:
    """Check if a parameter matches between modern and legacy naming"""
    modern_val = config.get(modern, '').strip()
    legacy_val = config.get(legacy, '').strip()
    
    # Convert to float for numeric comparison
    try:
        modern_float = float(modern_val) if modern_val else None
        legacy_float = float(legacy_val) if legacy_val else None
        
        if modern_float is not None and legacy_float is not None:
            matches = modern_float == legacy_float
            if matches:
                return True, f"{GREEN}✅ {name:20s} {modern:20s} == {legacy:20s} ({modern_val}){RESET}"
            else:
                return False, f"{RED}❌ {name:20s} {modern:20s} ({modern_val}) != {legacy:20s} ({legacy_val}){RESET}"
        else:
            return False, f"{YELLOW}⚠️  {name:20s} Missing value (modern: {modern_val}, legacy: {legacy_val}){RESET}"
    except ValueError:
        # String comparison for non-numeric values
        matches = modern_val == legacy_val
        if matches:
            return True, f"{GREEN}✅ {name:20s} {modern:20s} == {legacy:20s} ({modern_val}){RESET}"
        else:
            return False, f"{RED}❌ {name:20s} {modern:20s} ({modern_val}) != {legacy:20s} ({legacy_val}){RESET}"

def check_state_sync(config: Dict[str, str], state: Dict) -> List[str]:
    """Check if state.json is in sync with config"""
    issues = []
    
    if not state:
        issues.append(f"{YELLOW}⚠️  state.json is missing or empty{RESET}")
        return issues
    
    # Check each parameter
    checks = [
        ('GRID_LOWER', float(config.get('GRIDBOT_LOWER', 0))),
        ('GRID_UPPER', float(config.get('GRIDBOT_UPPER', 0))),
        ('GRID_STEP', float(config.get('GRIDBOT_STEP', 0))),
        ('REFERENCE_LEVEL', float(config.get('GRIDBOT_REF', 0))),
        ('LOT', float(config.get('GRIDBOT_LOT', 0))),
    ]
    
    for state_key, expected_val in checks:
        state_val = state.get(state_key)
        
        if state_val is None:
            issues.append(f"{YELLOW}⚠️  state.json missing {state_key}{RESET}")
        elif float(state_val) != expected_val:
            issues.append(f"{RED}❌ state.json {state_key} = {state_val}, expected {expected_val}{RESET}")
        else:
            issues.append(f"{GREEN}✅ state.json {state_key} = {state_val} (correct){RESET}")
    
    return issues

def main():
    """Main function"""
    print("=" * 80)
    print(f"{BLUE}🔍 Bot Parameter Sync Checker{RESET}")
    print("=" * 80)
    print()
    
    try:
        # Load config
        config = load_config()
        print(f"{GREEN}✅ Loaded grid_config.env{RESET}")
        print()
        
        # Check each parameter pair
        print(f"{BLUE}📊 Config File Parameter Sync:{RESET}")
        print()
        
        checks = [
            ('GRIDBOT_LOWER', 'GRID_LOWER', 'LOWER'),
            ('GRIDBOT_UPPER', 'GRID_UPPER', 'UPPER'),
            ('GRIDBOT_STEP', 'GRID_STEP', 'STEP'),
            ('GRIDBOT_REF', 'REFERENCE_LEVEL', 'REF'),
            ('GRIDBOT_LOT', 'LOT', 'LOT'),
            ('GRIDBOT_MAX_OPEN', 'MAX_OPEN', 'MAX_OPEN'),
        ]
        
        all_match = True
        for modern, legacy, name in checks:
            matches, message = check_param_match(config, modern, legacy, name)
            print(f"  {message}")
            if not matches:
                all_match = False
        
        print()
        
        # Check state.json
        print(f"{BLUE}📊 state.json Sync:{RESET}")
        print()
        
        state = load_state()
        state_issues = check_state_sync(config, state)
        for issue in state_issues:
            print(f"  {issue}")
        
        print()
        
        # Summary
        print("=" * 80)
        if all_match and all(GREEN in issue for issue in state_issues):
            print(f"{GREEN}✅ ALL PARAMETERS IN SYNC!{RESET}")
            print()
            print("Your bot configuration is consistent across all files.")
            exit_code = 0
        else:
            print(f"{RED}❌ SYNC ISSUES DETECTED!{RESET}")
            print()
            print("Your bot has parameter mismatches that need to be fixed.")
            print()
            print(f"{YELLOW}To fix automatically, run:{RESET}")
            print(f"  bash scripts/fix_param_sync.sh")
            print()
            print(f"{YELLOW}Or see the full report:{RESET}")
            print(f"  cat BOT_PARAMETER_SYNC_INVESTIGATION_REPORT.md")
            exit_code = 1
        
        print("=" * 80)
        
        return exit_code
        
    except Exception as e:
        print(f"{RED}❌ Error: {e}{RESET}")
        return 1

if __name__ == "__main__":
    exit(main())



