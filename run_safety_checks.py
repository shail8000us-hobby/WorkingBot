#!/usr/bin/env python3
"""
GridBot Safety Checker - Comprehensive Safety Analysis Suite

Performs multiple safety checks:
1. Dependency vulnerability scanning (CVEs, security issues)
2. Dead code detection (unused functions, classes)
3. Order validation checks
4. State consistency verification

Usage:
    python3 run_safety_checks.py                    # Full scan
    python3 run_safety_checks.py --quick            # Skip dead code analysis
    python3 run_safety_checks.py --dependencies     # Only check dependencies
    python3 run_safety_checks.py --dead-code        # Only find dead code

Author: GridBot Team
Date: 2025-11-02
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

try:
    from termcolor import colored
except ImportError:
    def colored(text, color=None, attrs=None):
        return text

# Project directories
PROJECT_ROOT = Path(__file__).parent
SCAN_DIRS = ['bot', 'webui/backend', 'scripts', 'dashboard']


class SafetyChecker:
    """Comprehensive safety analysis for GridBot"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {},
            'vulnerabilities': [],
            'dead_code': [],
            'order_validation': {},
            'state_consistency': {}
        }
        
    def print_header(self):
        """Print tool header"""
        print("=" * 80)
        print(colored("🛡️  GridBot Safety Checker - Comprehensive Security Analysis", 'cyan', attrs=['bold']))
        print("=" * 80)
        print(f"📁 Project Root: {PROJECT_ROOT}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
    
    def check_dependencies(self) -> Tuple[int, List[Dict]]:
        """
        Check dependencies for known vulnerabilities using Safety
        Returns: (vulnerability_count, vulnerabilities_list)
        """
        print(colored("🔍 Checking Dependencies for Security Vulnerabilities...", 'yellow', attrs=['bold']))
        
        vulnerabilities = []
        
        # Find all requirements files
        req_files = [
            PROJECT_ROOT / 'requirements.txt',
            PROJECT_ROOT / 'bug_finder_requirements.txt',
            PROJECT_ROOT / 'webui' / 'backend' / 'requirements.txt'
        ]
        
        for req_file in req_files:
            if not req_file.exists():
                continue
                
            print(f"  Scanning: {req_file.name}")
            
            try:
                # Run safety check
                result = subprocess.run(
                    ['python3', '-m', 'safety', 'check', '--json', '--file', str(req_file)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    print(colored(f"    ✓ No vulnerabilities found", 'green'))
                else:
                    # Parse JSON output
                    try:
                        vulns = json.loads(result.stdout)
                        for vuln in vulns:
                            vulnerabilities.append({
                                'file': req_file.name,
                                'package': vuln.get('package', 'Unknown'),
                                'installed_version': vuln.get('installed_version', 'Unknown'),
                                'vulnerability_id': vuln.get('vulnerability_id', 'Unknown'),
                                'advisory': vuln.get('advisory', 'No details'),
                                'severity': self._classify_severity(vuln.get('advisory', ''))
                            })
                        print(colored(f"    ⚠️  Found {len(vulns)} vulnerabilities", 'red'))
                    except json.JSONDecodeError:
                        # Non-JSON output, parse text
                        if 'vulnerabilities found' in result.stdout.lower():
                            print(colored(f"    ⚠️  Vulnerabilities detected (see output)", 'yellow'))
                
            except subprocess.TimeoutExpired:
                print(colored(f"    ⏱  Timeout checking {req_file.name}", 'yellow'))
            except FileNotFoundError:
                print(colored("    ⚠️  Safety not installed. Run: pip3 install safety", 'yellow'))
                return 0, []
            except Exception as e:
                print(colored(f"    ❌ Error: {e}", 'red'))
        
        self.results['vulnerabilities'] = vulnerabilities
        return len(vulnerabilities), vulnerabilities
    
    def _classify_severity(self, advisory: str) -> str:
        """Classify vulnerability severity from advisory text"""
        advisory_lower = advisory.lower()
        if any(word in advisory_lower for word in ['critical', 'remote code execution', 'rce']):
            return 'CRITICAL'
        elif any(word in advisory_lower for word in ['high', 'sql injection', 'xss']):
            return 'HIGH'
        elif any(word in advisory_lower for word in ['medium', 'moderate']):
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def find_dead_code(self, min_confidence: int = 80) -> Tuple[int, List[Dict]]:
        """
        Find unused code using Vulture
        Returns: (dead_code_count, dead_code_list)
        """
        print(colored("\n🔍 Finding Dead Code (Unused Functions/Classes/Variables)...", 'yellow', attrs=['bold']))
        
        dead_code = []
        
        for scan_dir in SCAN_DIRS:
            dir_path = PROJECT_ROOT / scan_dir
            if not dir_path.exists():
                continue
            
            print(f"  Scanning: {scan_dir}/")
            
            try:
                result = subprocess.run(
                    ['python3', '-m', 'vulture', str(dir_path), 
                     f'--min-confidence={min_confidence}',
                     '--sort-by-size'],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line and not line.startswith('vulture'):
                            # Parse vulture output: file:line: message
                            parts = line.split(':', 3)
                            if len(parts) >= 3:
                                dead_code.append({
                                    'file': parts[0],
                                    'line': parts[1],
                                    'message': parts[2].strip() if len(parts) > 2 else '',
                                    'directory': scan_dir
                                })
                    
                    count = len([l for l in lines if l and not l.startswith('vulture')])
                    print(colored(f"    Found {count} unused code items", 'yellow' if count > 0 else 'green'))
                else:
                    print(colored(f"    ✓ No dead code found", 'green'))
                
            except subprocess.TimeoutExpired:
                print(colored(f"    ⏱  Timeout scanning {scan_dir}", 'yellow'))
            except FileNotFoundError:
                print(colored("    ⚠️  Vulture not installed. Run: pip3 install vulture", 'yellow'))
                return 0, []
            except Exception as e:
                print(colored(f"    ❌ Error: {e}", 'red'))
        
        self.results['dead_code'] = dead_code
        return len(dead_code), dead_code
    
    def validate_order_logic(self) -> Dict[str, Any]:
        """
        Validate order placement logic for safety issues
        """
        print(colored("\n🔍 Validating Order Placement Safety...", 'yellow', attrs=['bold']))
        
        validation_results = {
            'checks_performed': 0,
            'issues_found': [],
            'recommendations': []
        }
        
        # Check if order_manager.py has validation
        order_manager_file = PROJECT_ROOT / 'bot' / 'strategy' / 'modules' / 'order_manager.py'
        
        if order_manager_file.exists():
            content = order_manager_file.read_text()
            
            checks = [
                {
                    'name': 'Price validation',
                    'pattern': ['price > 0', 'price <= 0', 'if not price'],
                    'required': True
                },
                {
                    'name': 'Quantity validation',
                    'pattern': ['quantity > 0', 'lot > 0', 'size > 0', 'lot_size > 0', 'quantity <= 0', 'lot_size <= 0'],
                    'required': True
                },
                {
                    'name': 'Emergency stop check',
                    'pattern': ['emergency_stop', 'EMERGENCY_STOP'],
                    'required': True
                },
                {
                    'name': 'Volatility check',
                    'pattern': ['volatility_check', 'VOLATILITY'],
                    'required': False
                },
                {
                    'name': 'Liquidation check',
                    'pattern': ['liquidation_check', 'LIQUIDATION'],
                    'required': True
                },
                {
                    'name': 'Max price deviation',
                    'pattern': ['max.*price', 'price.*limit', 'price.*threshold'],
                    'required': False
                }
            ]
            
            for check in checks:
                validation_results['checks_performed'] += 1
                found = any(pattern.lower() in content.lower() for pattern in check['pattern'])
                
                if found:
                    print(colored(f"  ✓ {check['name']}: Present", 'green'))
                else:
                    severity = 'required' if check['required'] else 'recommended'
                    print(colored(f"  ⚠️  {check['name']}: Missing ({severity})", 'red' if check['required'] else 'yellow'))
                    validation_results['issues_found'].append({
                        'check': check['name'],
                        'severity': severity,
                        'status': 'missing'
                    })
            
            # Add recommendations
            if any(issue['severity'] == 'required' for issue in validation_results['issues_found']):
                validation_results['recommendations'].append(
                    "Add missing required validations to order_manager.py"
                )
            
            validation_results['recommendations'].extend([
                "Consider adding max price deviation check (e.g., price < current_price * 1.5)",
                "Add order size limits to prevent fat-finger errors",
                "Implement daily/hourly order count limits"
            ])
        else:
            print(colored("  ⚠️  order_manager.py not found", 'yellow'))
        
        self.results['order_validation'] = validation_results
        return validation_results
    
    def check_state_consistency(self) -> Dict[str, Any]:
        """
        Check for state consistency issues
        """
        print(colored("\n🔍 Checking State File Consistency...", 'yellow', attrs=['bold']))
        
        consistency_results = {
            'files_checked': 0,
            'issues_found': [],
            'status': 'unknown'
        }
        
        # Check critical state files
        state_files = [
            ('positions.json', 'Position tracking'),
            ('equity_snapshots_live.json', 'Live equity data'),
            ('equity_snapshots_demo.json', 'Demo equity data'),
            ('.state.json', 'Bot state'),
            ('.guardian_health.json', 'Guardian health')
        ]
        
        for filename, description in state_files:
            file_path = PROJECT_ROOT / filename
            consistency_results['files_checked'] += 1
            
            if file_path.exists():
                try:
                    # Try to load as JSON
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    # Basic validation
                    if isinstance(data, dict):
                        if 'last_update' in data or 'timestamp' in data:
                            print(colored(f"  ✓ {filename}: Valid ({description})", 'green'))
                        else:
                            print(colored(f"  ⚠️  {filename}: Missing timestamp", 'yellow'))
                            consistency_results['issues_found'].append({
                                'file': filename,
                                'issue': 'Missing timestamp field',
                                'severity': 'low'
                            })
                    else:
                        print(colored(f"  ✓ {filename}: Valid JSON", 'green'))
                        
                except json.JSONDecodeError as e:
                    print(colored(f"  ❌ {filename}: Invalid JSON - {e}", 'red'))
                    consistency_results['issues_found'].append({
                        'file': filename,
                        'issue': f'Invalid JSON: {e}',
                        'severity': 'critical'
                    })
                except Exception as e:
                    print(colored(f"  ⚠️  {filename}: Error reading - {e}", 'yellow'))
            else:
                print(colored(f"  ℹ️  {filename}: Not found (may be normal)", 'cyan'))
        
        # Determine overall status
        critical_issues = [i for i in consistency_results['issues_found'] if i['severity'] == 'critical']
        if critical_issues:
            consistency_results['status'] = 'critical'
        elif consistency_results['issues_found']:
            consistency_results['status'] = 'warning'
        else:
            consistency_results['status'] = 'healthy'
        
        self.results['state_consistency'] = consistency_results
        return consistency_results
    
    def print_summary(self, vuln_count: int, dead_code_count: int, 
                     order_validation: Dict, state_consistency: Dict):
        """Print comprehensive summary"""
        print("\n" + "=" * 80)
        print(colored("📊 SAFETY CHECK SUMMARY", 'cyan', attrs=['bold']))
        print("=" * 80)
        
        # Vulnerabilities
        if vuln_count == 0:
            print(colored("✅ Dependencies: No known vulnerabilities", 'green'))
        else:
            critical = len([v for v in self.results['vulnerabilities'] if v['severity'] == 'CRITICAL'])
            high = len([v for v in self.results['vulnerabilities'] if v['severity'] == 'HIGH'])
            print(colored(f"⚠️  Dependencies: {vuln_count} vulnerabilities found", 'red'))
            if critical > 0:
                print(colored(f"   🔴 {critical} CRITICAL", 'red', attrs=['bold']))
            if high > 0:
                print(colored(f"   🟠 {high} HIGH", 'yellow'))
        
        # Dead code
        if dead_code_count == 0:
            print(colored("✅ Dead Code: None found", 'green'))
        else:
            print(colored(f"ℹ️  Dead Code: {dead_code_count} unused items found (cleanup opportunity)", 'cyan'))
        
        # Order validation
        order_issues = len(order_validation.get('issues_found', []))
        if order_issues == 0:
            print(colored("✅ Order Validation: All checks passed", 'green'))
        else:
            required_missing = len([i for i in order_validation['issues_found'] if i['severity'] == 'required'])
            if required_missing > 0:
                print(colored(f"❌ Order Validation: {required_missing} required checks missing", 'red'))
            else:
                print(colored(f"⚠️  Order Validation: {order_issues} recommended checks missing", 'yellow'))
        
        # State consistency
        state_status = state_consistency.get('status', 'unknown')
        if state_status == 'healthy':
            print(colored("✅ State Consistency: All files valid", 'green'))
        elif state_status == 'warning':
            print(colored(f"⚠️  State Consistency: {len(state_consistency['issues_found'])} minor issues", 'yellow'))
        elif state_status == 'critical':
            print(colored(f"❌ State Consistency: Critical issues detected", 'red'))
        
        print()
        print("=" * 80)
        
        # Overall status
        has_critical = vuln_count > 0 or \
                      any(i['severity'] == 'required' for i in order_validation.get('issues_found', [])) or \
                      state_status == 'critical'
        
        if has_critical:
            print(colored("🚨 CRITICAL ISSUES FOUND - Action Required!", 'red', attrs=['bold']))
            return 1
        elif dead_code_count > 50 or order_issues > 0:
            print(colored("⚠️  Warnings Found - Review Recommended", 'yellow', attrs=['bold']))
            return 0
        else:
            print(colored("✅ All Safety Checks Passed!", 'green', attrs=['bold']))
            return 0
    
    def write_report(self, filename: str = 'safety_report.txt'):
        """Write detailed report to file"""
        report_path = PROJECT_ROOT / filename
        
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("GridBot Safety Check Report\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {self.results['timestamp']}\n")
            f.write(f"Project: {PROJECT_ROOT}\n\n")
            
            # Vulnerabilities
            f.write("-" * 80 + "\n")
            f.write("DEPENDENCY VULNERABILITIES\n")
            f.write("-" * 80 + "\n")
            if self.results['vulnerabilities']:
                for vuln in self.results['vulnerabilities']:
                    f.write(f"\n[{vuln['severity']}] {vuln['package']} v{vuln['installed_version']}\n")
                    f.write(f"  File: {vuln['file']}\n")
                    f.write(f"  CVE: {vuln['vulnerability_id']}\n")
                    f.write(f"  Advisory: {vuln['advisory']}\n")
            else:
                f.write("\nNo vulnerabilities found.\n")
            
            # Dead code
            f.write("\n" + "-" * 80 + "\n")
            f.write("DEAD CODE ANALYSIS\n")
            f.write("-" * 80 + "\n")
            if self.results['dead_code']:
                f.write(f"\nFound {len(self.results['dead_code'])} unused items:\n\n")
                for item in self.results['dead_code'][:50]:  # Limit to first 50
                    f.write(f"{item['file']}:{item['line']} - {item['message']}\n")
                if len(self.results['dead_code']) > 50:
                    f.write(f"\n... and {len(self.results['dead_code']) - 50} more\n")
            else:
                f.write("\nNo dead code found.\n")
            
            # Order validation
            f.write("\n" + "-" * 80 + "\n")
            f.write("ORDER VALIDATION SAFETY\n")
            f.write("-" * 80 + "\n")
            order_val = self.results.get('order_validation', {})
            if order_val.get('issues_found'):
                for issue in order_val['issues_found']:
                    f.write(f"\n[{issue['severity'].upper()}] {issue['check']}: {issue['status']}\n")
            
            if order_val.get('recommendations'):
                f.write("\nRecommendations:\n")
                for rec in order_val['recommendations']:
                    f.write(f"  - {rec}\n")
            
            # State consistency
            f.write("\n" + "-" * 80 + "\n")
            f.write("STATE CONSISTENCY\n")
            f.write("-" * 80 + "\n")
            state_check = self.results.get('state_consistency', {})
            f.write(f"\nFiles checked: {state_check.get('files_checked', 0)}\n")
            f.write(f"Status: {state_check.get('status', 'unknown').upper()}\n")
            
            if state_check.get('issues_found'):
                f.write("\nIssues:\n")
                for issue in state_check['issues_found']:
                    f.write(f"  [{issue['severity'].upper()}] {issue['file']}: {issue['issue']}\n")
        
        print(f"\n📄 Detailed report written to: {report_path}")
    
    def export_json(self, filename: str = 'safety_report.json'):
        """Export results as JSON"""
        report_path = PROJECT_ROOT / filename
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"📄 JSON report exported to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description='GridBot Safety Checker - Comprehensive Security Analysis'
    )
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode: skip dead code analysis')
    parser.add_argument('--dependencies', action='store_true',
                       help='Only check dependencies')
    parser.add_argument('--dead-code', action='store_true',
                       help='Only find dead code')
    parser.add_argument('--export-json', action='store_true',
                       help='Export results as JSON')
    
    args = parser.parse_args()
    
    checker = SafetyChecker()
    checker.print_header()
    
    vuln_count = 0
    dead_code_count = 0
    order_validation = {}
    state_consistency = {}
    
    # Run checks based on flags
    if args.dependencies:
        vuln_count, _ = checker.check_dependencies()
    elif args.dead_code:
        dead_code_count, _ = checker.find_dead_code()
    else:
        # Full scan
        vuln_count, _ = checker.check_dependencies()
        
        if not args.quick:
            dead_code_count, _ = checker.find_dead_code()
        
        order_validation = checker.validate_order_logic()
        state_consistency = checker.check_state_consistency()
    
    # Print summary
    exit_code = checker.print_summary(vuln_count, dead_code_count, 
                                      order_validation, state_consistency)
    
    # Write reports
    checker.write_report()
    
    if args.export_json:
        checker.export_json()
    
    print("=" * 80)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
