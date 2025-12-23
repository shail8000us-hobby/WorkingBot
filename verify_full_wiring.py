#!/usr/bin/env python3
"""
Comprehensive Grid Config Wiring Verification Script
Checks all parameters from grid_config.env are properly wired to AsyncGridBot
"""

import os
import sys
from dotenv import load_dotenv

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_param(name, param_type="any"):
    """Check if parameter exists in environment."""
    value = os.getenv(name)
    if value is None:
        return f"{RED}❌ {name}: NOT SET{RESET}"
    else:
        return f"{GREEN}✅ {name}: {value}{RESET}"

def print_section(title):
    """Print section header."""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def main():
    # Load grid_config.env
    load_dotenv("grid_config.env", override=True)
    
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}GRID CONFIG WIRING VERIFICATION{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    
    total_checks = 0
    passed_checks = 0
    
    # Check core grid parameters
    print_section("🎯 CORE GRID PARAMETERS")
    core_params = [
        "GRIDBOT_LOWER",
        "GRIDBOT_UPPER",
        "GRIDBOT_STEP",
        "GRIDBOT_REF",
        "GRIDBOT_LOT",
        "GRIDBOT_MAX_OPEN",
        "GRIDBOT_SYMBOL",
        "GRIDBOT_GRID_MODE"
    ]
    for param in core_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check safety parameters
    print_section("🛡️  SAFETY FEATURES")
    safety_params = [
        "MAX_ACCOUNT_LOSS_INR",
        "VOLATILITY_SAFETY_ENABLED",
        "VOLATILITY_MAX_IV",
        "VOLATILITY_MAX_RV",
        "VOLATILITY_MAX_SPREAD",
        "CONFIRMATION_GUARD_ENABLED",
        "CIRCUIT_BREAKER_ENABLED",
        "LIQUIDATION_PROTECTION_ENABLED"
    ]
    for param in safety_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check order management parameters
    print_section("🏷️  ORDER MANAGEMENT")
    order_params = [
        "GRIDBOT_TAG_PREFIX",
        "GRIDBOT_POST_ONLY_MODE",
        "GRIDBOT_CANCEL_ALL_ON_START",
        "GRIDBOT_CANCEL_SCOPE",
        "GRIDBOT_ADOPT_UNTAGGED"
    ]
    for param in order_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check grid behavior parameters
    print_section("📊 GRID BEHAVIOR")
    grid_params = [
        "GRIDBOT_STRICT_GRID",
        "GRIDBOT_STRICT_START",
        "GRIDBOT_SEED_INITIAL_COUNT",
        "SMART_GAP_FILL",
        "GRIDBOT_RUNG_SNAP_MODE"
    ]
    for param in grid_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check timing parameters
    print_section("⏱️  TIMING & RETRIES")
    timing_params = [
        "GRIDBOT_MAX_RETRIES",
        "GRIDBOT_RETRY_DELAY",
        "GRIDBOT_COOLDOWN_SECONDS"
    ]
    for param in timing_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check conversion rate
    print_section("💱 CONVERSION RATE")
    conversion_params = ["USD_TO_INR_RATE"]
    for param in conversion_params:
        result = check_param(param)
        print(result)
        total_checks += 1
        if "✅" in result:
            passed_checks += 1
    
    # Check code implementation
    print_section("📝 CODE IMPLEMENTATION CHECKS")
    
    # Check AsyncGridBot has parameters
    print(f"Checking AsyncGridBot implementation...")
    try:
        with open("bot/strategy/async_gridbot.py", "r") as f:
            content = f.read()
            
        impl_checks = [
            ("max_account_loss_inr", "Safety: loss limit"),
            ("volatility_safety_enabled", "Safety: volatility check"),
            ("tag_prefix", "Order: tag prefix"),
            ("post_only_mode", "Order: post-only mode"),
            ("strict_grid", "Grid: strict grid"),
            ("seed_initial_count", "Grid: initial seeding"),
            ("max_retries", "Timing: max retries"),
            ("cooldown_seconds", "Timing: cooldown"),
            ("_check_safety_limits", "Method: safety check"),
            ("_check_cooldown", "Method: cooldown check"),
            ("_update_last_order_time", "Method: cooldown update")
        ]
        
        for check, desc in impl_checks:
            if check in content:
                print(f"{GREEN}✅ {desc}: IMPLEMENTED{RESET}")
                passed_checks += 1
            else:
                print(f"{RED}❌ {desc}: MISSING{RESET}")
            total_checks += 1
            
    except Exception as e:
        print(f"{RED}❌ Error checking AsyncGridBot: {e}{RESET}")
    
    # Check OrderManagerActor has tag generation
    print(f"\nChecking OrderManagerActor implementation...")
    try:
        with open("bot/strategy/actors/order_actor.py", "r") as f:
            content = f.read()
            
        actor_checks = [
            ("tag_prefix", "Parameter: tag_prefix"),
            ("post_only_mode", "Parameter: post_only_mode"),
            ("_generate_order_tag", "Method: tag generation"),
            ("_should_use_post_only", "Method: post-only logic"),
            ("client_order_id", "API call: includes tag")
        ]
        
        for check, desc in actor_checks:
            if check in content:
                print(f"{GREEN}✅ {desc}: IMPLEMENTED{RESET}")
                passed_checks += 1
            else:
                print(f"{RED}❌ {desc}: MISSING{RESET}")
            total_checks += 1
            
    except Exception as e:
        print(f"{RED}❌ Error checking OrderManagerActor: {e}{RESET}")
    
    # Check bot/run.py extracts parameters
    print(f"\nChecking bot/run.py parameter extraction...")
    try:
        with open("bot/run.py", "r") as f:
            content = f.read()
            
        extract_checks = [
            ("max_loss = envf", "Extract: MAX_ACCOUNT_LOSS_INR"),
            ("vol_safety = os.getenv", "Extract: VOLATILITY_SAFETY_ENABLED"),
            ("tag_prefix = os.getenv", "Extract: GRIDBOT_TAG_PREFIX"),
            ("post_only_mode = os.getenv", "Extract: GRIDBOT_POST_ONLY_MODE"),
            ("strict_grid = os.getenv", "Extract: GRIDBOT_STRICT_GRID"),
            ("max_account_loss_inr=max_loss", "Pass to bot: max_loss"),
            ("tag_prefix=tag_prefix", "Pass to bot: tag_prefix"),
            ("post_only_mode=post_only_mode", "Pass to bot: post_only_mode")
        ]
        
        for check, desc in extract_checks:
            if check in content:
                print(f"{GREEN}✅ {desc}: IMPLEMENTED{RESET}")
                passed_checks += 1
            else:
                print(f"{RED}❌ {desc}: MISSING{RESET}")
            total_checks += 1
            
    except Exception as e:
        print(f"{RED}❌ Error checking bot/run.py: {e}{RESET}")
    
    # Check AsyncDeltaClient has client_order_id support
    print(f"\nChecking AsyncDeltaClient API support...")
    try:
        with open("bot/api/async_delta_client.py", "r") as f:
            content = f.read()
            
        if "client_order_id: str = None" in content and 'data["client_order_id"]' in content:
            print(f"{GREEN}✅ API: client_order_id support ADDED{RESET}")
            passed_checks += 1
        else:
            print(f"{RED}❌ API: client_order_id support MISSING{RESET}")
        total_checks += 1
        
    except Exception as e:
        print(f"{RED}❌ Error checking AsyncDeltaClient: {e}{RESET}")
    
    # Summary
    print_section("📊 SUMMARY")
    
    percentage = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    
    print(f"Total Checks: {total_checks}")
    print(f"Passed: {GREEN}{passed_checks}{RESET}")
    print(f"Failed: {RED}{total_checks - passed_checks}{RESET}")
    print(f"Success Rate: {GREEN if percentage == 100 else YELLOW}{percentage:.1f}%{RESET}\n")
    
    if percentage == 100:
        print(f"{GREEN}{BOLD}✅ ALL CHECKS PASSED - FULL WIRING COMPLETE!{RESET}\n")
        print(f"{BOLD}Next Steps:{RESET}")
        print(f"1. Test bot startup: python3 -m bot.run")
        print(f"2. Verify configuration logs show all parameters")
        print(f"3. Check order tags on Delta Exchange")
        print(f"4. Test safety limit with small amount")
        print(f"5. Monitor first 5 minutes of trading\n")
        return 0
    else:
        print(f"{YELLOW}⚠️  PARTIAL WIRING - Some components missing{RESET}\n")
        print(f"{RED}Not production ready until all checks pass!{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
