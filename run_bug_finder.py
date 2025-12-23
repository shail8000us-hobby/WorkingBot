#!/usr/bin/env python3
"""
GridBot Bug Finder - Automated Static Analysis Tool

Scans Python files for syntax errors, logic issues, security problems,
and type mismatches across the trading bot project.

Usage:
    python3 run_bug_finder.py           # Full scan
    python3 run_bug_finder.py --quick   # Fast scan (flake8 + pylint only)
    python3 run_bug_finder.py --export-json  # Export JSON report
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict

try:
    from termcolor import colored
except ImportError:
    # Fallback if termcolor not installed
    def colored(text, color=None, attrs=None):
        return text


class BugFinder:
    """Automated bug detection system for GridBot project"""
    
    # Directories to scan
    SCAN_DIRS = [
        'bot',
        'webui/backend',
        'scripts',
        'dashboard'
    ]
    
    # Tools configuration
    TOOLS = {
        'flake8': {
            'name': 'Flake8',
            'description': 'Syntax & Style Checker',
            'critical': True
        },
        'pylint': {
            'name': 'Pylint',
            'description': 'Logic & Code Quality Analyzer',
            'critical': True
        },
        'mypy': {
            'name': 'Mypy',
            'description': 'Type Checker',
            'critical': False
        },
        'bandit': {
            'name': 'Bandit',
            'description': 'Security Analyzer',
            'critical': True
        }
    }
    
    def __init__(self, quick_mode=False, export_json=False):
        self.project_root = Path.cwd()
        self.quick_mode = quick_mode
        self.export_json = export_json
        self.results = defaultdict(list)
        self.summary = {
            'total_files': 0,
            'errors': 0,
            'warnings': 0,
            'critical': 0,
            'info': 0,
            'timestamp': datetime.now().isoformat()
        }
        
    def print_header(self):
        """Print scan header"""
        print("=" * 80)
        print(colored("🔍 GridBot Bug Finder - Automated Static Analysis", 'cyan', attrs=['bold']))
        print("=" * 80)
        print(f"📁 Project Root: {self.project_root}")
        print(f"🔧 Mode: {'Quick Scan' if self.quick_mode else 'Full Scan'}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
    def find_python_files(self) -> List[Path]:
        """Find all Python files in target directories"""
        python_files = []
        
        for dir_name in self.SCAN_DIRS:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                files = list(dir_path.rglob('*.py'))
                python_files.extend(files)
                print(f"📂 {dir_name}: {len(files)} Python files")
        
        self.summary['total_files'] = len(python_files)
        print()
        return python_files
    
    def check_tool_installed(self, tool: str) -> bool:
        """Check if analysis tool is installed"""
        try:
            subprocess.run(
                [tool, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
    
    def run_flake8(self, files: List[Path]) -> Dict:
        """Run flake8 syntax and style checks"""
        print(colored("🔎 Running Flake8 (Syntax & Style)...", 'yellow'))
        
        if not self.check_tool_installed('flake8'):
            return {'error': 'flake8 not installed'}
        
        issues = []
        cmd = [
            'flake8',
            '--max-line-length=120',
            '--ignore=E501,W503,E203',  # Ignore line length, line break before operator
            '--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s'
        ] + [str(f) for f in files]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        for line in result.stdout.strip().split('\n'):
            if line:
                issues.append(self.parse_flake8_line(line))
        
        self.results['flake8'] = issues
        print(f"  ✓ Found {len(issues)} issues")
        return {'count': len(issues), 'issues': issues}
    
    def parse_flake8_line(self, line: str) -> Dict:
        """Parse flake8 output line"""
        try:
            parts = line.split(':', 3)
            if len(parts) >= 4:
                file_path = parts[0]
                line_num = parts[1]
                col = parts[2]
                message = parts[3].strip()
                
                # Determine severity
                severity = 'warning'
                if any(code in message for code in ['F821', 'F401', 'E999']):
                    severity = 'error'
                    self.summary['errors'] += 1
                else:
                    self.summary['warnings'] += 1
                
                return {
                    'tool': 'flake8',
                    'file': file_path,
                    'line': line_num,
                    'column': col,
                    'severity': severity,
                    'message': message
                }
        except Exception:
            pass
        
        return {'raw': line}
    
    def run_pylint(self, files: List[Path]) -> Dict:
        """Run pylint logic and quality checks"""
        print(colored("🔎 Running Pylint (Logic & Quality)...", 'yellow'))
        
        if not self.check_tool_installed('pylint'):
            return {'error': 'pylint not installed'}
        
        issues = []
        
        # Run pylint on each directory to avoid overwhelming output
        for dir_name in self.SCAN_DIRS:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            cmd = [
                'pylint',
                '--output-format=json',
                '--disable=C0114,C0115,C0116',  # Disable missing docstrings
                '--max-line-length=120',
                str(dir_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                pylint_results = json.loads(result.stdout)
                for issue in pylint_results:
                    parsed = self.parse_pylint_issue(issue)
                    issues.append(parsed)
            except json.JSONDecodeError:
                pass
        
        self.results['pylint'] = issues
        print(f"  ✓ Found {len(issues)} issues")
        return {'count': len(issues), 'issues': issues}
    
    def parse_pylint_issue(self, issue: Dict) -> Dict:
        """Parse pylint JSON issue"""
        severity_map = {
            'error': 'error',
            'warning': 'warning',
            'convention': 'info',
            'refactor': 'info'
        }
        
        severity = severity_map.get(issue.get('type', 'info'), 'info')
        
        if severity == 'error':
            self.summary['errors'] += 1
        elif severity == 'warning':
            self.summary['warnings'] += 1
        else:
            self.summary['info'] += 1
        
        return {
            'tool': 'pylint',
            'file': issue.get('path', ''),
            'line': issue.get('line', 0),
            'column': issue.get('column', 0),
            'severity': severity,
            'message': f"{issue.get('message-id', '')} {issue.get('message', '')}",
            'symbol': issue.get('symbol', '')
        }
    
    def run_mypy(self, files: List[Path]) -> Dict:
        """Run mypy type checks"""
        print(colored("🔎 Running Mypy (Type Checker)...", 'yellow'))
        
        if not self.check_tool_installed('mypy'):
            return {'error': 'mypy not installed'}
        
        issues = []
        
        # Run mypy on each directory
        for dir_name in self.SCAN_DIRS:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            cmd = [
                'mypy',
                '--ignore-missing-imports',
                '--no-error-summary',
                str(dir_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line:
                    parsed = self.parse_mypy_line(line)
                    if parsed:
                        issues.append(parsed)
        
        self.results['mypy'] = issues
        print(f"  ✓ Found {len(issues)} issues")
        return {'count': len(issues), 'issues': issues}
    
    def parse_mypy_line(self, line: str) -> Dict:
        """Parse mypy output line"""
        try:
            parts = line.split(':', 3)
            if len(parts) >= 3:
                file_path = parts[0]
                line_num = parts[1]
                message = parts[2].strip()
                
                severity = 'warning'
                if 'error' in message.lower():
                    severity = 'error'
                    self.summary['errors'] += 1
                else:
                    self.summary['warnings'] += 1
                
                return {
                    'tool': 'mypy',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': severity,
                    'message': message
                }
        except Exception:
            pass
        
        return None
    
    def run_bandit(self, files: List[Path]) -> Dict:
        """Run bandit security checks"""
        print(colored("🔎 Running Bandit (Security Analyzer)...", 'yellow'))
        
        if not self.check_tool_installed('bandit'):
            return {'error': 'bandit not installed'}
        
        issues = []
        cmd = [
            'bandit',
            '-r',
            '-f', 'json',
            '--skip', 'B404,B603',  # Skip some common false positives
        ] + [str(self.project_root / d) for d in self.SCAN_DIRS if (self.project_root / d).exists()]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            bandit_results = json.loads(result.stdout)
            for issue in bandit_results.get('results', []):
                parsed = self.parse_bandit_issue(issue)
                issues.append(parsed)
        except json.JSONDecodeError:
            pass
        
        self.results['bandit'] = issues
        print(f"  ✓ Found {len(issues)} security issues")
        return {'count': len(issues), 'issues': issues}
    
    def parse_bandit_issue(self, issue: Dict) -> Dict:
        """Parse bandit JSON issue"""
        severity_map = {
            'HIGH': 'critical',
            'MEDIUM': 'warning',
            'LOW': 'info'
        }
        
        severity = severity_map.get(issue.get('issue_severity', 'LOW'), 'info')
        
        if severity == 'critical':
            self.summary['critical'] += 1
        elif severity == 'warning':
            self.summary['warnings'] += 1
        else:
            self.summary['info'] += 1
        
        return {
            'tool': 'bandit',
            'file': issue.get('filename', ''),
            'line': issue.get('line_number', 0),
            'column': 0,
            'severity': severity,
            'message': f"{issue.get('test_id', '')} {issue.get('issue_text', '')}",
            'confidence': issue.get('issue_confidence', 'UNKNOWN')
        }
    
    def print_results(self):
        """Print formatted results to terminal"""
        print()
        print("=" * 80)
        print(colored("📊 ANALYSIS RESULTS", 'cyan', attrs=['bold']))
        print("=" * 80)
        print()
        
        # Group issues by severity
        critical_issues = []
        error_issues = []
        warning_issues = []
        info_issues = []
        
        for tool, issues in self.results.items():
            for issue in issues:
                if isinstance(issue, dict) and 'severity' in issue:
                    if issue['severity'] == 'critical':
                        critical_issues.append(issue)
                    elif issue['severity'] == 'error':
                        error_issues.append(issue)
                    elif issue['severity'] == 'warning':
                        warning_issues.append(issue)
                    else:
                        info_issues.append(issue)
        
        # Print critical issues
        if critical_issues:
            print(colored("🔴 CRITICAL ISSUES (Security/Safety)", 'red', attrs=['bold']))
            print("-" * 80)
            for issue in critical_issues[:20]:  # Limit to 20
                self.print_issue(issue, 'red')
            if len(critical_issues) > 20:
                print(colored(f"  ... and {len(critical_issues) - 20} more", 'red'))
            print()
        
        # Print errors
        if error_issues:
            print(colored("❌ ERRORS (Runtime/Logic)", 'red', attrs=['bold']))
            print("-" * 80)
            for issue in error_issues[:20]:
                self.print_issue(issue, 'red')
            if len(error_issues) > 20:
                print(colored(f"  ... and {len(error_issues) - 20} more", 'red'))
            print()
        
        # Print warnings
        if warning_issues:
            print(colored("🟡 WARNINGS", 'yellow', attrs=['bold']))
            print("-" * 80)
            for issue in warning_issues[:15]:
                self.print_issue(issue, 'yellow')
            if len(warning_issues) > 15:
                print(colored(f"  ... and {len(warning_issues) - 15} more", 'yellow'))
            print()
        
        # Print summary
        print("=" * 80)
        print(colored("📈 SUMMARY", 'cyan', attrs=['bold']))
        print("=" * 80)
        print(f"📁 Total Files Scanned: {self.summary['total_files']}")
        print(f"🔴 Critical Issues: {colored(str(self.summary['critical']), 'red', attrs=['bold'])}")
        print(f"❌ Errors: {colored(str(self.summary['errors']), 'red')}")
        print(f"🟡 Warnings: {colored(str(self.summary['warnings']), 'yellow')}")
        print(f"ℹ️  Info: {self.summary['info']}")
        print()
        
        # Final status
        if self.summary['critical'] > 0:
            print(colored(f"🚨 Scan Complete — {self.summary['critical']} CRITICAL issues found!", 'red', attrs=['bold']))
        elif self.summary['errors'] > 0:
            print(colored(f"⚠️  Scan Complete — {self.summary['errors']} errors found", 'yellow', attrs=['bold']))
        elif self.summary['warnings'] > 0:
            print(colored(f"✅ Scan Complete — {self.summary['warnings']} warnings found", 'green'))
        else:
            print(colored("✅ Scan Complete — No issues found! 🎉", 'green', attrs=['bold']))
        
        print("=" * 80)
    
    def print_issue(self, issue: Dict, color: str):
        """Print single issue in formatted way"""
        file_path = issue.get('file', 'unknown')
        line = issue.get('line', 0)
        message = issue.get('message', 'No message')
        tool = issue.get('tool', 'unknown').upper()
        
        # Truncate file path if too long
        if len(file_path) > 60:
            file_path = '...' + file_path[-57:]
        
        print(colored(f"  [{tool}] {file_path}:{line}", color))
        print(f"    → {message}")
    
    def write_report(self):
        """Write results to bug_report.txt"""
        report_path = self.project_root / 'bug_report.txt'
        
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("GridBot Bug Finder - Analysis Report\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {self.summary['timestamp']}\n")
            f.write(f"Total Files Scanned: {self.summary['total_files']}\n")
            f.write(f"Critical Issues: {self.summary['critical']}\n")
            f.write(f"Errors: {self.summary['errors']}\n")
            f.write(f"Warnings: {self.summary['warnings']}\n")
            f.write(f"Info: {self.summary['info']}\n")
            f.write("=" * 80 + "\n\n")
            
            # Write all issues
            for tool, issues in self.results.items():
                if issues:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"{tool.upper()} Results\n")
                    f.write(f"{'='*80}\n\n")
                    
                    for issue in issues:
                        if isinstance(issue, dict) and 'file' in issue:
                            f.write(f"[{issue.get('severity', 'unknown').upper()}] ")
                            f.write(f"{issue.get('file', '')}:{issue.get('line', 0)}\n")
                            f.write(f"  {issue.get('message', '')}\n\n")
        
        print(f"\n📄 Full report written to: {report_path}")
    
    def export_json_report(self):
        """Export results as JSON for CI integration"""
        json_path = self.project_root / 'bug_report.json'
        
        report = {
            'summary': self.summary,
            'results': dict(self.results)
        }
        
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 JSON report exported to: {json_path}")
    
    def run(self):
        """Run the complete bug finding process"""
        self.print_header()
        
        # Find all Python files
        python_files = self.find_python_files()
        
        if not python_files:
            print(colored("⚠️  No Python files found in target directories!", 'yellow'))
            return
        
        print()
        
        # Run analysis tools
        if self.quick_mode:
            # Quick mode: only flake8 and pylint
            self.run_flake8(python_files)
            self.run_pylint(python_files)
        else:
            # Full mode: all tools
            self.run_flake8(python_files)
            self.run_pylint(python_files)
            self.run_mypy(python_files)
            self.run_bandit(python_files)
        
        # Print results
        self.print_results()
        
        # Write reports
        self.write_report()
        
        if self.export_json:
            self.export_json_report()
        
        # Return exit code based on critical issues
        return 1 if self.summary['critical'] > 0 else 0


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='GridBot Bug Finder - Automated Static Analysis Tool'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick mode: run only flake8 and pylint (faster)'
    )
    parser.add_argument(
        '--export-json',
        action='store_true',
        help='Export results as JSON for CI integration'
    )
    
    args = parser.parse_args()
    
    finder = BugFinder(quick_mode=args.quick, export_json=args.export_json)
    exit_code = finder.run()
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
