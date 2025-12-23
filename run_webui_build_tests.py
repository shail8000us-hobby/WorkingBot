#!/usr/bin/env python3
"""
Complete WebUI Build Testing Runner

Runs all WebUI frontend build and advanced tests.

Usage:
    python3 run_webui_build_tests.py [--build|--advanced|--all]
    
Options:
    --build      Run only build tests
    --advanced   Run only advanced tests
    --all        Run all tests (default)
"""

import sys
import subprocess
from pathlib import Path

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def run_test(test_file: str, name: str) -> bool:
    """Run a test file and return success status"""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}Running {name}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=Path(__file__).parent.parent,
            timeout=600
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{RED}❌ {name} timed out after 10 minutes{RESET}")
        return False
    except Exception as e:
        print(f"{RED}❌ Failed to run {name}: {e}{RESET}")
        return False

def main():
    """Main entry point"""
    project_root = Path(__file__).parent
    
    build_test = project_root / "tests" / "test_webui_build.py"
    advanced_test = project_root / "tests" / "test_webui_advanced.py"
    
    if not build_test.exists():
        print(f"{RED}❌ Build test not found: {build_test}{RESET}")
        sys.exit(1)
    
    if not advanced_test.exists():
        print(f"{RED}❌ Advanced test not found: {advanced_test}{RESET}")
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ["--all"]
    
    run_build = "--build" in args or "--all" in args
    run_advanced = "--advanced" in args or "--all" in args
    
    print(f"\n{BOLD}{GREEN}{'='*80}{RESET}")
    print(f"{BOLD}{GREEN}WebUI Frontend Complete Testing Suite{RESET}")
    print(f"{GREEN}{'='*80}{RESET}\n")
    
    results = {}
    
    if run_build:
        results["build"] = run_test(str(build_test), "Build Tests")
    
    if run_advanced:
        results["advanced"] = run_test(str(advanced_test), "Advanced Tests")
    
    # Summary
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}FINAL SUMMARY{RESET}")
    print(f"{'='*80}{RESET}\n")
    
    all_passed = True
    
    if "build" in results:
        status = f"{GREEN}✅ PASSED{RESET}" if results["build"] else f"{RED}❌ FAILED{RESET}"
        print(f"Build Tests:     {status}")
        if not results["build"]:
            all_passed = False
    
    if "advanced" in results:
        status = f"{GREEN}✅ PASSED{RESET}" if results["advanced"] else f"{RED}❌ FAILED{RESET}"
        print(f"Advanced Tests:  {status}")
        if not results["advanced"]:
            all_passed = False
    
    print()
    
    if all_passed:
        print(f"{BOLD}{GREEN}🎉 ALL WEBUI TESTS PASSED! 🎉{RESET}")
        print(f"{GREEN}Frontend is production-ready! 🚀{RESET}\n")
    else:
        print(f"{BOLD}{RED}❌ SOME TESTS FAILED{RESET}")
        print(f"{RED}Please fix the issues before deploying.{RESET}\n")
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()

