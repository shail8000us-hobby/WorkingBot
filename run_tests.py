#!/usr/bin/env python3
"""
GridBot Test Runner - Comprehensive Test Suite with Coverage

Runs all tests and generates coverage reports showing:
- Which code paths are tested
- Which functions lack tests
- Coverage percentage for critical modules
- HTML report for detailed analysis

Usage:
    python3 run_tests.py                    # Run all tests with coverage
    python3 run_tests.py --quick            # Run tests without coverage
    python3 run_tests.py --unit             # Only unit tests
    python3 run_tests.py --integration      # Only integration tests
    python3 run_tests.py --module grid      # Test specific module

Author: GridBot Team
Date: 2025-11-02
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

try:
    from termcolor import colored
except ImportError:
    def colored(text, color=None, attrs=None):
        return text

PROJECT_ROOT = Path(__file__).parent
TESTS_DIR = PROJECT_ROOT / 'tests'
COVERAGE_DIR = PROJECT_ROOT / 'htmlcov'

# Critical modules that should have high coverage
CRITICAL_MODULES = [
    'bot/strategy/modules/grid_calculator.py',
    'bot/strategy/modules/order_manager.py',
    'bot/strategy/modules/position_manager.py',
    'bot/strategy/gridbot.py',
]


class TestRunner:
    """Comprehensive test runner with coverage reporting"""
    
    def __init__(self, quick=False, html_report=True):
        self.quick = quick
        self.html_report = html_report
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'coverage_percentage': 0,
            'critical_modules_coverage': {}
        }
    
    def print_header(self):
        """Print test runner header"""
        print("=" * 80)
        print(colored("🧪 GridBot Test Suite - Comprehensive Testing & Coverage", 'cyan', attrs=['bold']))
        print("=" * 80)
        print(f"📁 Project Root: {PROJECT_ROOT}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Coverage: {'Disabled' if self.quick else 'Enabled'}")
        print("=" * 80)
        print()
    
    def run_tests(self, pattern='test_*.py', module_filter=None):
        """
        Run pytest with coverage
        
        Args:
            pattern: Test file pattern
            module_filter: Filter tests by module name
        """
        print(colored(f"🧪 Running Tests: {pattern}", 'yellow', attrs=['bold']))
        
        # Build pytest command
        cmd = ['python3', '-m', 'pytest', str(TESTS_DIR)]
        
        # Add pattern filter
        if module_filter:
            cmd.extend(['-k', module_filter])
        
        # Add coverage if not quick mode
        if not self.quick:
            cmd.extend([
                '--cov=bot/strategy',
                '--cov=bot/api',
                '--cov=bot/config',
                '--cov-report=term-missing',
                '--cov-report=html',
                '--cov-fail-under=0'  # Don't fail on low coverage yet
            ])
        
        # Add verbosity
        cmd.extend(['-v', '--tb=short'])
        
        # Colored output
        cmd.append('--color=yes')
        
        try:
            print(f"  Command: {' '.join(cmd[2:])}\n")
            
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=False,
                text=True
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(colored(f"❌ Error running tests: {e}", 'red'))
            return False
    
    def run_unit_tests(self):
        """Run unit tests only"""
        print(colored("\n🔬 Running Unit Tests...", 'cyan', attrs=['bold']))
        return self.run_tests(pattern='test_*.py', module_filter='not integration')
    
    def run_integration_tests(self):
        """Run integration tests only"""
        print(colored("\n🔗 Running Integration Tests...", 'cyan', attrs=['bold']))
        return self.run_tests(pattern='test_*.py', module_filter='integration')
    
    def run_module_tests(self, module_name):
        """Run tests for specific module"""
        print(colored(f"\n📦 Running Tests for: {module_name}", 'cyan', attrs=['bold']))
        return self.run_tests(module_filter=module_name)
    
    def generate_coverage_summary(self):
        """Generate coverage summary for critical modules"""
        if self.quick:
            print(colored("\n📊 Coverage report skipped (quick mode)", 'yellow'))
            return
        
        print(colored("\n📊 Coverage Summary for Critical Modules", 'cyan', attrs=['bold']))
        print("-" * 80)
        
        coverage_file = PROJECT_ROOT / '.coverage'
        if not coverage_file.exists():
            print(colored("  ⚠️  No coverage data found", 'yellow'))
            return
        
        # Parse coverage data
        try:
            import coverage
            cov = coverage.Coverage()
            cov.load()
            
            for module_path in CRITICAL_MODULES:
                full_path = PROJECT_ROOT / module_path
                if full_path.exists():
                    try:
                        analysis = cov.analysis2(str(full_path))
                        executed = len(analysis[1])
                        missing = len(analysis[2])
                        total = executed + missing
                        
                        if total > 0:
                            percentage = (executed / total) * 100
                            module_name = module_path.split('/')[-1]
                            
                            # Color based on coverage
                            if percentage >= 80:
                                color = 'green'
                            elif percentage >= 60:
                                color = 'yellow'
                            else:
                                color = 'red'
                            
                            status = colored(f"{percentage:.1f}%", color, attrs=['bold'])
                            print(f"  {module_name:40} {status} ({executed}/{total} lines)")
                            
                            self.results['critical_modules_coverage'][module_name] = {
                                'percentage': round(percentage, 1),
                                'executed': executed,
                                'total': total
                            }
                    except Exception:
                        pass
            
        except ImportError:
            print(colored("  ⚠️  coverage package not found", 'yellow'))
        except Exception as e:
            print(colored(f"  ⚠️  Error parsing coverage: {e}", 'yellow'))
    
    def show_html_report_info(self):
        """Show information about HTML coverage report"""
        if self.quick:
            return
        
        if COVERAGE_DIR.exists():
            index_file = COVERAGE_DIR / 'index.html'
            if index_file.exists():
                print(colored(f"\n📊 HTML Coverage Report Generated!", 'green', attrs=['bold']))
                print(f"  📄 Open: {index_file}")
                print(f"  💡 View in browser: open {index_file}")
    
    def print_summary(self, success):
        """Print test run summary"""
        print("\n" + "=" * 80)
        print(colored("📊 TEST RUN SUMMARY", 'cyan', attrs=['bold']))
        print("=" * 80)
        
        if success:
            print(colored("✅ All Tests Passed!", 'green', attrs=['bold']))
        else:
            print(colored("❌ Some Tests Failed", 'red', attrs=['bold']))
        
        if not self.quick and self.results['critical_modules_coverage']:
            avg_coverage = sum(
                m['percentage'] for m in self.results['critical_modules_coverage'].values()
            ) / len(self.results['critical_modules_coverage'])
            
            coverage_str = f"{avg_coverage:.1f}%"
            if avg_coverage >= 80:
                coverage_colored = colored(coverage_str, 'green', attrs=['bold'])
            elif avg_coverage >= 60:
                coverage_colored = colored(coverage_str, 'yellow', attrs=['bold'])
            else:
                coverage_colored = colored(coverage_str, 'red', attrs=['bold'])
            
            print(f"\n📈 Average Critical Module Coverage: {coverage_colored}")
        
        print("=" * 80)
        
        return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(
        description='GridBot Test Runner - Comprehensive Testing Suite'
    )
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode: skip coverage reporting')
    parser.add_argument('--unit', action='store_true',
                       help='Run unit tests only')
    parser.add_argument('--integration', action='store_true',
                       help='Run integration tests only')
    parser.add_argument('--module', type=str,
                       help='Run tests for specific module (e.g., grid, order, position)')
    parser.add_argument('--no-html', action='store_true',
                       help='Skip HTML coverage report generation')
    
    args = parser.parse_args()
    
    runner = TestRunner(quick=args.quick, html_report=not args.no_html)
    runner.print_header()
    
    # Determine which tests to run
    success = False
    
    if args.unit:
        success = runner.run_unit_tests()
    elif args.integration:
        success = runner.run_integration_tests()
    elif args.module:
        success = runner.run_module_tests(args.module)
    else:
        # Run all tests
        success = runner.run_tests()
    
    # Generate reports
    runner.generate_coverage_summary()
    runner.show_html_report_info()
    
    # Print summary
    exit_code = runner.print_summary(success)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
