#!/usr/bin/env python3
"""
Advanced WebUI Frontend Build Testing Suite

Tests build quality, bundle sizes, TypeScript compilation, code quality,
performance metrics, and build artifact validation.

Run: python3 tests/test_webui_build.py
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import time

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class BuildTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.frontend_dir = self.project_root / "webui" / "frontend"
        self.build_dir = self.frontend_dir / "build"
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
        """Run a shell command and return exit code, stdout, stderr"""
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
            return -1, "", "Command timed out after 300 seconds"
        except Exception as e:
            return -1, "", str(e)
    
    def test_node_modules_exists(self) -> bool:
        """Test 1: Verify node_modules exists"""
        self.log("Test 1: Checking node_modules installation...")
        node_modules = self.frontend_dir / "node_modules"
        if node_modules.exists():
            self.log("✅ node_modules found", "PASS")
            self.results["passed"].append("node_modules exists")
            return True
        else:
            self.log("❌ node_modules not found. Run 'npm install' first", "FAIL")
            self.results["failed"].append("node_modules missing")
            return False
    
    def test_package_json_valid(self) -> bool:
        """Test 2: Validate package.json structure"""
        self.log("Test 2: Validating package.json...")
        package_json = self.frontend_dir / "package.json"
        if not package_json.exists():
            self.log("❌ package.json not found", "FAIL")
            self.results["failed"].append("package.json missing")
            return False
        
        try:
            with open(package_json) as f:
                data = json.load(f)
            
            required_keys = ["name", "version", "scripts", "dependencies"]
            missing = [k for k in required_keys if k not in data]
            
            if missing:
                self.log(f"❌ package.json missing keys: {missing}", "FAIL")
                self.results["failed"].append(f"package.json missing keys: {missing}")
                return False
            
            # Check build script exists
            if "build" not in data.get("scripts", {}):
                self.log("❌ No 'build' script in package.json", "FAIL")
                self.results["failed"].append("build script missing")
                return False
            
            self.log(f"✅ package.json valid (version: {data.get('version')})", "PASS")
            self.results["passed"].append("package.json valid")
            return True
        except json.JSONDecodeError:
            self.log("❌ package.json is invalid JSON", "FAIL")
            self.results["failed"].append("package.json invalid JSON")
            return False
    
    def test_typescript_compilation(self) -> bool:
        """Test 3: TypeScript type checking"""
        self.log("Test 3: Running TypeScript type check...")
        exit_code, stdout, stderr = self.run_command(["npm", "run", "typecheck"])
        
        if exit_code == 0:
            self.log("✅ TypeScript compilation passed", "PASS")
            self.results["passed"].append("TypeScript type check")
            return True
        else:
            self.log("❌ TypeScript compilation failed", "FAIL")
            self.log(f"Errors:\n{stderr}", "FAIL")
            self.results["failed"].append("TypeScript type check")
            return False
    
    def test_build_success(self) -> bool:
        """Test 4: Verify production build succeeds"""
        self.log("Test 4: Running production build...")
        start_time = time.time()
        
        exit_code, stdout, stderr = self.run_command(["npm", "run", "build"])
        build_time = time.time() - start_time
        
        if exit_code == 0:
            self.log(f"✅ Build succeeded in {build_time:.2f}s", "PASS")
            self.results["passed"].append(f"Build successful ({build_time:.1f}s)")
            return True
        else:
            self.log("❌ Build failed", "FAIL")
            self.log(f"Errors:\n{stderr}", "FAIL")
            self.results["failed"].append("Build failed")
            return False
    
    def test_build_artifacts(self) -> bool:
        """Test 5: Verify build artifacts exist"""
        self.log("Test 5: Checking build artifacts...")
        required_files = [
            "index.html",
            "asset-manifest.json",
            "static/js/main.*.js",
            "static/css/main.*.css"
        ]
        
        missing = []
        if not self.build_dir.exists():
            self.log("❌ Build directory does not exist", "FAIL")
            self.results["failed"].append("Build directory missing")
            return False
        
        # Check index.html
        index_html = self.build_dir / "index.html"
        if not index_html.exists():
            missing.append("index.html")
        
        # Check asset manifest
        manifest = self.build_dir / "asset-manifest.json"
        if not manifest.exists():
            missing.append("asset-manifest.json")
        
        # Check JS bundle
        js_dir = self.build_dir / "static" / "js"
        js_files = list(js_dir.glob("main.*.js")) if js_dir.exists() else []
        if not js_files:
            missing.append("static/js/main.*.js")
        
        # Check CSS bundle
        css_dir = self.build_dir / "static" / "css"
        css_files = list(css_dir.glob("main.*.css")) if css_dir.exists() else []
        if not css_files:
            missing.append("static/css/main.*.css")
        
        if missing:
            self.log(f"❌ Missing build artifacts: {missing}", "FAIL")
            self.results["failed"].append(f"Missing artifacts: {missing}")
            return False
        
        self.log("✅ All build artifacts present", "PASS")
        self.results["passed"].append("Build artifacts present")
        return True
    
    def test_bundle_size(self) -> bool:
        """Test 6: Check bundle sizes are reasonable"""
        self.log("Test 6: Analyzing bundle sizes...")
        
        js_dir = self.build_dir / "static" / "js"
        css_dir = self.build_dir / "static" / "css"
        
        warnings = []
        
        # Check JS bundle size
        js_files = list(js_dir.glob("main.*.js")) if js_dir.exists() else []
        if js_files:
            js_size = js_files[0].stat().st_size / (1024 * 1024)  # MB
            if js_size > 2.0:  # 2MB threshold
                warnings.append(f"JS bundle is large: {js_size:.2f}MB (threshold: 2MB)")
            else:
                self.log(f"✅ JS bundle size: {js_size:.2f}MB", "PASS")
                self.results["passed"].append(f"JS bundle size OK ({js_size:.2f}MB)")
        
        # Check CSS bundle size
        css_files = list(css_dir.glob("main.*.css")) if css_dir.exists() else []
        if css_files:
            css_size = css_files[0].stat().st_size / 1024  # KB
            if css_size > 500:  # 500KB threshold
                warnings.append(f"CSS bundle is large: {css_size:.2f}KB (threshold: 500KB)")
            else:
                self.log(f"✅ CSS bundle size: {css_size:.2f}KB", "PASS")
                self.results["passed"].append(f"CSS bundle size OK ({css_size:.2f}KB)")
        
        if warnings:
            for warn in warnings:
                self.log(f"⚠️  {warn}", "WARN")
                self.results["warnings"].append(warn)
        
        return True
    
    def test_asset_manifest_valid(self) -> bool:
        """Test 7: Validate asset-manifest.json structure"""
        self.log("Test 7: Validating asset manifest...")
        manifest = self.build_dir / "asset-manifest.json"
        
        if not manifest.exists():
            self.log("❌ asset-manifest.json not found", "FAIL")
            self.results["failed"].append("asset-manifest.json missing")
            return False
        
        try:
            with open(manifest) as f:
                data = json.load(f)
            
            # Check required structure
            if "files" not in data:
                self.log("❌ asset-manifest.json missing 'files' key", "FAIL")
                self.results["failed"].append("asset-manifest.json invalid")
                return False
            
            file_count = len(data.get("files", {}))
            self.log(f"✅ Asset manifest valid ({file_count} files)", "PASS")
            self.results["passed"].append(f"Asset manifest valid ({file_count} files)")
            return True
        except json.JSONDecodeError:
            self.log("❌ asset-manifest.json is invalid JSON", "FAIL")
            self.results["failed"].append("asset-manifest.json invalid JSON")
            return False
    
    def test_html_integrity(self) -> bool:
        """Test 8: Check HTML file includes necessary scripts"""
        self.log("Test 8: Checking HTML integrity...")
        index_html = self.build_dir / "index.html"
        
        if not index_html.exists():
            self.log("❌ index.html not found", "FAIL")
            self.results["failed"].append("index.html missing")
            return False
        
        try:
            with open(index_html) as f:
                content = f.read()
            
            checks = {
                "root div": '<div id="root">' in content or '<div id="root"></div>' in content,
                "meta viewport": 'viewport' in content.lower(),
                "title": '<title>' in content,
                "script tags": 'script' in content.lower(),
                "css link": 'link' in content.lower() or 'stylesheet' in content.lower()
            }
            
            missing = [k for k, v in checks.items() if not v]
            
            if missing:
                self.log(f"⚠️  HTML missing elements: {missing}", "WARN")
                self.results["warnings"].append(f"HTML missing: {missing}")
            else:
                self.log("✅ HTML integrity check passed", "PASS")
                self.results["passed"].append("HTML integrity")
            
            return True
        except Exception as e:
            self.log(f"❌ Error reading index.html: {e}", "FAIL")
            self.results["failed"].append("HTML read error")
            return False
    
    def test_no_build_errors(self) -> bool:
        """Test 9: Check for common build errors/warnings"""
        self.log("Test 9: Scanning for build errors...")
        
        # Check for common error patterns in build output
        index_html = self.build_dir / "index.html"
        
        if not index_html.exists():
            return False
        
        try:
            with open(index_html) as f:
                content = f.read()
            
            error_patterns = [
                "error",
                "failed",
                "undefined",
                "null reference"
            ]
            
            errors_found = [p for p in error_patterns if p in content.lower()]
            
            if errors_found:
                self.log(f"⚠️  Potential issues found: {errors_found}", "WARN")
                self.results["warnings"].append(f"Potential errors: {errors_found}")
                return True
            
            self.log("✅ No obvious build errors detected", "PASS")
            self.results["passed"].append("No build errors")
            return True
        except Exception:
            return False
    
    def test_dependencies_compatible(self) -> bool:
        """Test 10: Check for dependency conflicts"""
        self.log("Test 10: Checking dependency compatibility...")
        
        # Run npm audit (dry run)
        exit_code, stdout, stderr = self.run_command(["npm", "audit", "--json"])
        
        if exit_code == 0:
            try:
                audit_data = json.loads(stdout)
                vulnerabilities = audit_data.get("vulnerabilities", {})
                
                if vulnerabilities:
                    count = len(vulnerabilities)
                    self.log(f"⚠️  Found {count} dependency vulnerabilities", "WARN")
                    self.results["warnings"].append(f"{count} vulnerabilities found")
                else:
                    self.log("✅ No critical vulnerabilities found", "PASS")
                    self.results["passed"].append("No vulnerabilities")
            except json.JSONDecodeError:
                self.log("⚠️  Could not parse npm audit output", "WARN")
                self.results["warnings"].append("Audit parse error")
        
        return True
    
    def test_build_performance(self) -> bool:
        """Test 11: Measure build performance metrics"""
        self.log("Test 11: Measuring build performance...")
        
        if not self.build_dir.exists():
            self.log("⚠️  Build directory not found, skipping performance test", "WARN")
            return True
        
        # Calculate total build size
        total_size = 0
        file_count = 0
        
        for file_path in self.build_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        total_size_mb = total_size / (1024 * 1024)
        
        self.log(f"✅ Build size: {total_size_mb:.2f}MB ({file_count} files)", "PASS")
        self.results["passed"].append(f"Build size: {total_size_mb:.2f}MB")
        
        if total_size_mb > 10:
            self.log(f"⚠️  Build size exceeds 10MB threshold", "WARN")
            self.results["warnings"].append("Large build size")
        
        return True
    
    def run_all_tests(self) -> bool:
        """Run all build tests"""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}WebUI Frontend Build Testing Suite{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")
        
        tests = [
            self.test_node_modules_exists,
            self.test_package_json_valid,
            self.test_typescript_compilation,
            self.test_build_success,
            self.test_build_artifacts,
            self.test_bundle_size,
            self.test_asset_manifest_valid,
            self.test_html_integrity,
            self.test_no_build_errors,
            self.test_dependencies_compatible,
            self.test_build_performance
        ]
        
        passed_count = 0
        failed_count = 0
        
        for test in tests:
            try:
                if test():
                    passed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                self.log(f"❌ Test {test.__name__} crashed: {e}", "FAIL")
                failed_count += 1
                self.results["failed"].append(f"{test.__name__} crashed: {e}")
            print()
        
        return self.print_summary(passed_count, failed_count)
    
    def print_summary(self, passed: int, failed: int) -> bool:
        """Print test summary"""
        total = len(self.results["passed"]) + len(self.results["failed"])
        warnings = len(self.results["warnings"])
        
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}BUILD TEST SUMMARY{RESET}")
        print(f"{'='*80}{RESET}\n")
        
        print(f"{GREEN}✅ Passed: {len(self.results['passed'])}{RESET}")
        print(f"{RED}❌ Failed: {len(self.results['failed'])}{RESET}")
        print(f"{YELLOW}⚠️  Warnings: {warnings}{RESET}")
        print(f"📊 Total Tests: {total}\n")
        
        if self.results["failed"]:
            print(f"{BOLD}{RED}FAILED TESTS:{RESET}")
            for failure in self.results["failed"]:
                print(f"  ❌ {failure}")
            print()
        
        if self.results["warnings"]:
            print(f"{BOLD}{YELLOW}WARNINGS:{RESET}")
            for warning in self.results["warnings"]:
                print(f"  ⚠️  {warning}")
            print()
        
        success = len(self.results["failed"]) == 0
        
        if success:
            print(f"{BOLD}{GREEN}✅ ALL BUILD TESTS PASSED!{RESET}")
            print(f"{GREEN}Frontend build is production-ready! 🚀{RESET}\n")
        else:
            print(f"{BOLD}{RED}❌ SOME BUILD TESTS FAILED{RESET}")
            print(f"{RED}Please fix the issues before deploying.{RESET}\n")
        
        return success


def main():
    """Main entry point"""
    tester = BuildTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

