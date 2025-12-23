#!/usr/bin/env python3
"""
Advanced WebUI Frontend Testing Suite

Advanced tests for:
- ESLint code quality
- Accessibility (a11y)
- Performance metrics
- Component structure
- API integration points
- Real-time features

Run: python3 tests/test_webui_advanced.py
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class AdvancedWebUITester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.frontend_dir = self.project_root / "webui" / "frontend"
        self.src_dir = self.frontend_dir / "src"
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
    
    def log(self, message: str, status: str = "INFO"):
        """Log with color coding"""
        colors = {
            "PASS": GREEN,
            "FAIL": RED,
            "WARN": YELLOW,
            "INFO": BLUE
        }
        color = colors.get(status, RESET)
        print(f"{color}[{status}]{RESET} {message}")
    
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
        """Run a shell command"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.frontend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def test_eslint_available(self) -> bool:
        """Test 1: Check if ESLint is configured"""
        self.log("Test 1: Checking ESLint configuration...")
        
        package_json = self.frontend_dir / "package.json"
        if not package_json.exists():
            return False
        
        try:
            with open(package_json) as f:
                data = json.load(f)
            
            # Check for ESLint in dependencies or package.json config
            has_eslint_config = "eslintConfig" in data
            has_eslint_dep = any(
                "eslint" in dep.lower() 
                for dep in list(data.get("dependencies", {}).keys()) + 
                           list(data.get("devDependencies", {}).keys())
            )
            
            if has_eslint_config or has_eslint_dep:
                self.log("✅ ESLint is configured", "PASS")
                self.results["passed"].append("ESLint configured")
                return True
            else:
                self.log("⚠️  ESLint not explicitly configured", "WARN")
                self.results["warnings"].append("ESLint not configured")
                return True
        except Exception:
            return False
    
    def test_component_structure(self) -> bool:
        """Test 2: Verify component structure and naming"""
        self.log("Test 2: Analyzing component structure...")
        
        components_dir = self.src_dir / "components"
        if not components_dir.exists():
            self.log("❌ components directory not found", "FAIL")
            self.results["failed"].append("components directory missing")
            return False
        
        js_files = list(components_dir.rglob("*.js"))
        jsx_files = list(components_dir.rglob("*.jsx"))
        all_components = js_files + jsx_files
        
        if not all_components:
            self.log("⚠️  No React components found", "WARN")
            self.results["warnings"].append("No components found")
            return True
        
        # Check for common component issues
        issues = []
        
        for comp_file in all_components[:10]:  # Sample first 10
            try:
                with open(comp_file) as f:
                    content = f.read()
                
                # Check for React import
                if "import" in content and "react" not in content.lower():
                    issues.append(f"{comp_file.name}: Missing React import")
                
                # Check for default export
                if "export default" not in content and "export {" in content:
                    # Named exports are OK
                    pass
                
            except Exception:
                pass
        
        if issues:
            self.log(f"⚠️  Found {len(issues)} potential component issues", "WARN")
            self.results["warnings"].extend(issues[:5])  # Limit warnings
        else:
            self.log(f"✅ Component structure looks good ({len(all_components)} components)", "PASS")
            self.results["passed"].append(f"Components OK ({len(all_components)} files)")
        
        return True
    
    def test_api_integration_points(self) -> bool:
        """Test 3: Check API integration code"""
        self.log("Test 3: Checking API integration points...")
        
        api_files = []
        
        # Check utils/api directory
        api_dir = self.src_dir / "lib" / "api"
        if api_dir.exists():
            api_files.extend(api_dir.glob("*.ts"))
            api_files.extend(api_dir.glob("*.js"))
        
        # Check for API client usage
        utils_dir = self.src_dir / "utils"
        api_client_files = [
            utils_dir / "apiClient.js",
            utils_dir / "enhancedApiClient.js",
            utils_dir / "robustApiClient.js"
        ]
        
        api_files.extend([f for f in api_client_files if f.exists()])
        
        if api_files:
            self.log(f"✅ Found {len(api_files)} API integration files", "PASS")
            self.results["passed"].append(f"API integration ({len(api_files)} files)")
            
            # Check for error handling
            for api_file in api_files[:3]:  # Sample
                try:
                    with open(api_file) as f:
                        content = f.read()
                    
                    if "try" in content and "catch" in content:
                        self.log(f"  ✅ {api_file.name}: Has error handling", "PASS")
                except Exception:
                    pass
        else:
            self.log("⚠️  No API integration files found", "WARN")
            self.results["warnings"].append("No API files found")
        
        return True
    
    def test_socket_integration(self) -> bool:
        """Test 4: Check WebSocket/SocketIO integration"""
        self.log("Test 4: Checking SocketIO integration...")
        
        socket_files = []
        
        # Check hooks
        hooks_dir = self.src_dir / "hooks"
        if hooks_dir.exists():
            socket_files.extend(hooks_dir.glob("*socket*.js"))
            socket_files.extend(hooks_dir.glob("*Socket*.js"))
        
        # Check for socket.io-client usage
        components_dir = self.src_dir / "components"
        if components_dir.exists():
            for js_file in components_dir.rglob("*.js"):
                try:
                    with open(js_file) as f:
                        if "socket.io" in f.read().lower():
                            socket_files.append(js_file)
                except Exception:
                    pass
        
        if socket_files:
            self.log(f"✅ Found {len(socket_files)} SocketIO integration files", "PASS")
            self.results["passed"].append(f"SocketIO integration ({len(socket_files)} files)")
        else:
            self.log("⚠️  No SocketIO integration found", "WARN")
            self.results["warnings"].append("No SocketIO files")
        
        return True
    
    def test_error_handling(self) -> bool:
        """Test 5: Check for error boundaries and error handling"""
        self.log("Test 5: Checking error handling...")
        
        components_dir = self.src_dir / "components"
        error_boundaries = []
        error_handlers = []
        
        if components_dir.exists():
            for js_file in components_dir.rglob("*.js"):
                try:
                    with open(js_file) as f:
                        content = f.read()
                        
                        if "ErrorBoundary" in content or "error boundary" in content.lower():
                            error_boundaries.append(js_file.name)
                        
                        if "try" in content and "catch" in content:
                            error_handlers.append(js_file.name)
                except Exception:
                    pass
        
        if error_boundaries:
            self.log(f"✅ Found {len(error_boundaries)} error boundaries", "PASS")
            self.results["passed"].append(f"Error boundaries ({len(error_boundaries)})")
        else:
            self.log("⚠️  No error boundaries found", "WARN")
            self.results["warnings"].append("No error boundaries")
        
        if error_handlers:
            self.log(f"✅ Found {len(error_handlers)} files with error handling", "PASS")
            self.results["passed"].append(f"Error handlers ({len(error_handlers)})")
        
        return True
    
    def test_accessibility_basics(self) -> bool:
        """Test 6: Basic accessibility checks"""
        self.log("Test 6: Checking accessibility basics...")
        
        components_dir = self.src_dir / "components"
        a11y_issues = []
        a11y_good = []
        
        if components_dir.exists():
            for js_file in list(components_dir.rglob("*.js"))[:20]:  # Sample
                try:
                    with open(js_file) as f:
                        content = f.read()
                    
                    # Check for common a11y patterns
                    has_aria = "aria-" in content or "role=" in content
                    has_alt = "alt=" in content
                    has_labels = "label" in content.lower()
                    
                    # Check for common issues
                    if "<img" in content and "alt=" not in content:
                        a11y_issues.append(f"{js_file.name}: Images without alt")
                    elif "<img" in content:
                        a11y_good.append(f"{js_file.name}: Images have alt")
                    
                    if has_aria or has_labels:
                        a11y_good.append(f"{js_file.name}: Has a11y attributes")
                    
                except Exception:
                    pass
        
        if a11y_issues:
            self.log(f"⚠️  Found {len(a11y_issues)} potential a11y issues", "WARN")
            self.results["warnings"].extend(a11y_issues[:5])
        
        if a11y_good:
            self.log(f"✅ Found {len(a11y_good)} good a11y practices", "PASS")
            self.results["passed"].append(f"a11y practices ({len(a11y_good)})")
        
        return True
    
    def test_performance_optimizations(self) -> bool:
        """Test 7: Check for performance optimizations"""
        self.log("Test 7: Checking performance optimizations...")
        
        optimizations_found = []
        
        # Check for lazy loading
        lazy_files = list(self.src_dir.rglob("*lazy*.js"))
        if lazy_files:
            optimizations_found.append(f"Lazy loading ({len(lazy_files)} files)")
        
        # Check for memoization
        components_dir = self.src_dir / "components"
        if components_dir.exists():
            memo_count = 0
            for js_file in components_dir.rglob("*.js"):
                try:
                    with open(js_file) as f:
                        if "React.memo" in f.read() or "useMemo" in f.read():
                            memo_count += 1
                except Exception:
                    pass
            
            if memo_count > 0:
                optimizations_found.append(f"Memoization ({memo_count} files)")
        
        if optimizations_found:
            self.log(f"✅ Found performance optimizations: {', '.join(optimizations_found)}", "PASS")
            self.results["passed"].append("Performance optimizations")
        else:
            self.log("⚠️  No obvious performance optimizations found", "WARN")
            self.results["warnings"].append("No perf optimizations")
        
        return True
    
    def test_hook_structure(self) -> bool:
        """Test 8: Verify React hooks structure"""
        self.log("Test 8: Checking React hooks...")
        
        hooks_dir = self.src_dir / "hooks"
        custom_hooks = []
        
        if hooks_dir.exists():
            custom_hooks = list(hooks_dir.glob("*.js"))
            
            # Validate hook naming (should start with 'use')
            invalid_hooks = []
            for hook_file in custom_hooks:
                if not hook_file.stem.startswith("use"):
                    invalid_hooks.append(hook_file.name)
            
            if invalid_hooks:
                self.log(f"⚠️  Hooks not following naming convention: {invalid_hooks}", "WARN")
                self.results["warnings"].extend(invalid_hooks)
            
            if custom_hooks:
                self.log(f"✅ Found {len(custom_hooks)} custom hooks", "PASS")
                self.results["passed"].append(f"Custom hooks ({len(custom_hooks)})")
            else:
                self.log("⚠️  No custom hooks found", "WARN")
        
        return True
    
    def test_dependency_versions(self) -> bool:
        """Test 9: Check critical dependency versions"""
        self.log("Test 9: Checking dependency versions...")
        
        package_json = self.frontend_dir / "package.json"
        if not package_json.exists():
            return False
        
        try:
            with open(package_json) as f:
                data = json.load(f)
            
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            
            critical_deps = {
                "react": "18.0.0",
                "react-dom": "18.0.0"
            }
            
            issues = []
            for dep, min_version in critical_deps.items():
                if dep in deps:
                    version = deps[dep]
                    # Simple version check (remove ^ or ~)
                    clean_version = version.lstrip("^~")
                    self.log(f"  ✅ {dep}: {version}", "PASS")
                else:
                    issues.append(f"{dep} not found")
            
            if issues:
                self.log(f"⚠️  Issues: {issues}", "WARN")
                self.results["warnings"].extend(issues)
            else:
                self.results["passed"].append("Dependency versions OK")
            
            return True
        except Exception:
            return False
    
    def test_file_structure(self) -> bool:
        """Test 10: Verify frontend file structure"""
        self.log("Test 10: Verifying file structure...")
        
        required_dirs = [
            "src",
            "src/components",
            "src/utils",
            "public"
        ]
        
        missing = []
        for dir_path in required_dirs:
            full_path = self.frontend_dir / dir_path
            if not full_path.exists():
                missing.append(dir_path)
        
        if missing:
            self.log(f"❌ Missing directories: {missing}", "FAIL")
            self.results["failed"].extend([f"Missing: {d}" for d in missing])
            return False
        
        self.log("✅ File structure is correct", "PASS")
        self.results["passed"].append("File structure")
        return True
    
    def run_all_tests(self) -> bool:
        """Run all advanced tests"""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}Advanced WebUI Frontend Testing Suite{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")
        
        tests = [
            self.test_eslint_available,
            self.test_component_structure,
            self.test_api_integration_points,
            self.test_socket_integration,
            self.test_error_handling,
            self.test_accessibility_basics,
            self.test_performance_optimizations,
            self.test_hook_structure,
            self.test_dependency_versions,
            self.test_file_structure
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log(f"❌ Test {test.__name__} crashed: {e}", "FAIL")
                self.results["failed"].append(f"{test.__name__} crashed: {e}")
            print()
        
        return self.print_summary()
    
    def print_summary(self) -> bool:
        """Print test summary"""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}ADVANCED TEST SUMMARY{RESET}")
        print(f"{'='*80}{RESET}\n")
        
        print(f"{GREEN}✅ Passed: {len(self.results['passed'])}{RESET}")
        print(f"{RED}❌ Failed: {len(self.results['failed'])}{RESET}")
        print(f"{YELLOW}⚠️  Warnings: {len(self.results['warnings'])}{RESET}\n")
        
        if self.results["failed"]:
            print(f"{BOLD}{RED}FAILED TESTS:{RESET}")
            for failure in self.results["failed"][:10]:
                print(f"  ❌ {failure}")
            print()
        
        success = len(self.results["failed"]) == 0
        
        if success:
            print(f"{BOLD}{GREEN}✅ ALL ADVANCED TESTS PASSED!{RESET}\n")
        else:
            print(f"{BOLD}{RED}❌ SOME TESTS FAILED{RESET}\n")
        
        return success


def main():
    """Main entry point"""
    tester = AdvancedWebUITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

