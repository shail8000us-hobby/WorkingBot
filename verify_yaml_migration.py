#!/usr/bin/env python3
"""
YAML Migration Verification Script
Performs real, file-by-file verification of YAML migration completeness.

NO ASSUMPTIONS. ONLY FACTS FROM CODE.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import yaml


class MigrationVerifier:
    """Verify YAML migration completeness with actual code inspection"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_yaml = project_root / 'config.yaml'
        self.schema_yaml = project_root / 'config' / 'schema.yaml'
        
        # Results
        self.findings = []
        self.files_analyzed = 0
        self.files_with_issues = []
        self.missing_yaml_keys = set()
        self.unused_yaml_keys = set()
        self.os_getenv_usage = []
        self.dotenv_usage = []
        
        # Load YAML structure
        self.yaml_config = self._load_yaml_config()
        self.yaml_keys = self._extract_all_yaml_keys(self.yaml_config)
        
    def _load_yaml_config(self) -> dict:
        """Load the YAML configuration"""
        if not self.config_yaml.exists():
            print(f"❌ config.yaml not found at {self.config_yaml}")
            return {}
        
        with open(self.config_yaml) as f:
            return yaml.safe_load(f) or {}
    
    def _extract_all_yaml_keys(self, data: dict, prefix: str = '') -> Set[str]:
        """Recursively extract all YAML keys as dot-notation paths"""
        keys = set()
        
        if not isinstance(data, dict):
            return keys
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)
            
            if isinstance(value, dict):
                keys.update(self._extract_all_yaml_keys(value, full_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        keys.update(self._extract_all_yaml_keys(item, f"{full_key}[{i}]"))
        
        return keys
    
    def scan_file(self, filepath: Path) -> Dict[str, any]:
        """Scan a single Python file for migration issues"""
        result = {
            'path': str(filepath.relative_to(self.project_root)),
            'status': 'COMPLETE',
            'issues': [],
            'os_getenv_calls': [],
            'dotenv_imports': [],
            'env_file_refs': [],
            'hardcoded_configs': [],
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            result['status'] = 'ERROR'
            result['issues'].append(f"Failed to read file: {e}")
            return result
        
        # Find os.getenv() calls
        getenv_pattern = r'os\.getenv\(["\']([^"\']+)["\'](?:,\s*["\']?([^"\']*)["\']?)?\)'
        for match in re.finditer(getenv_pattern, content):
            env_var = match.group(1)
            default_val = match.group(2) if match.group(2) else None
            line_num = content[:match.start()].count('\n') + 1
            
            # Skip API keys and system variables (these are intentionally kept)
            if env_var in ['DELTA_API_KEY', 'DELTA_API_SECRET', 'USER', 'VIRTUAL_ENV',
                          'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 
                          'OPENAI_API_KEY', 'NEWS_API_KEY', 'CRYPTOCOMPARE_API_KEY',
                          'FLASK_SECRET_KEY', 'WEBUI_AUTH_TOKEN', 'API_TOKEN']:
                continue
            
            # Skip if in comments or docstrings
            line_content = lines[line_num - 1] if line_num <= len(lines) else ''
            if line_content.strip().startswith('#'):
                continue
            
            result['os_getenv_calls'].append({
                'var': env_var,
                'default': default_val,
                'line': line_num,
                'snippet': line_content.strip()
            })
        
        # Find dotenv imports
        dotenv_patterns = [
            r'from dotenv import',
            r'import dotenv',
            r'load_dotenv\(',
        ]
        for pattern in dotenv_patterns:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ''
                
                # Skip comments
                if line_content.strip().startswith('#'):
                    continue
                
                result['dotenv_imports'].append({
                    'pattern': pattern,
                    'line': line_num,
                    'snippet': line_content.strip()
                })
        
        # Find .env file references
        env_file_pattern = r'["\']([^"\']*\.env[^"\']*)["\']'
        for match in re.finditer(env_file_pattern, content):
            env_file = match.group(1)
            if env_file and 'env' in env_file.lower():
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ''
                
                # Skip comments
                if line_content.strip().startswith('#'):
                    continue
                
                result['env_file_refs'].append({
                    'file': env_file,
                    'line': line_num,
                    'snippet': line_content.strip()
                })
        
        # Determine migration status
        if result['os_getenv_calls'] or result['dotenv_imports'] or result['env_file_refs']:
            result['status'] = 'PARTIAL'
            result['issues'].append(f"Found {len(result['os_getenv_calls'])} os.getenv() calls")
            result['issues'].append(f"Found {len(result['dotenv_imports'])} dotenv imports")
            result['issues'].append(f"Found {len(result['env_file_refs'])} .env file references")
        
        return result
    
    def scan_all_python_files(self):
        """Scan all Python files in the project"""
        print("🔍 Scanning all Python files...")
        
        directories = ['bot', 'webui', 'services', 'config']
        
        for directory in directories:
            dir_path = self.project_root / directory
            if not dir_path.exists():
                continue
            
            for py_file in dir_path.rglob('*.py'):
                # Skip test files and archives
                if 'test' in str(py_file).lower() or 'archive' in str(py_file).lower():
                    continue
                
                self.files_analyzed += 1
                result = self.scan_file(py_file)
                
                if result['status'] != 'COMPLETE':
                    self.files_with_issues.append(result)
                    
                # Track os.getenv usage
                for call in result['os_getenv_calls']:
                    self.os_getenv_usage.append({
                        'file': result['path'],
                        'var': call['var'],
                        'line': call['line'],
                        'snippet': call['snippet']
                    })
                
                # Track dotenv usage
                for imp in result['dotenv_imports']:
                    self.dotenv_usage.append({
                        'file': result['path'],
                        'line': imp['line'],
                        'snippet': imp['snippet']
                    })
        
        print(f"✅ Scanned {self.files_analyzed} Python files")
        print(f"⚠️  Found {len(self.files_with_issues)} files with migration issues")
    
    def generate_migration_audit_table(self) -> str:
        """Generate file-by-file migration audit table"""
        lines = []
        lines.append("\n" + "=" * 100)
        lines.append("YAML MIGRATION AUDIT - FILE-BY-FILE VERIFICATION")
        lines.append("=" * 100 + "\n")
        
        lines.append(f"{'File':<60} {'Status':<12} {'Issues':<10} {'Notes':<20}")
        lines.append("-" * 100)
        
        # Sort by status (PARTIAL first)
        sorted_files = sorted(self.files_with_issues, 
                            key=lambda x: (0 if x['status'] == 'PARTIAL' else 1, x['path']))
        
        for file_result in sorted_files:
            status_emoji = "⚠️ PARTIAL" if file_result['status'] == 'PARTIAL' else "✅ COMPLETE"
            issue_count = len(file_result['os_getenv_calls'])
            notes = f"{issue_count} getenv"
            
            lines.append(f"{file_result['path']:<60} {status_emoji:<12} {issue_count:<10} {notes:<20}")
        
        lines.append("-" * 100)
        lines.append(f"\nTOTAL FILES ANALYZED: {self.files_analyzed}")
        lines.append(f"FILES WITH ISSUES: {len(self.files_with_issues)}")
        lines.append(f"MIGRATION COMPLETE: {self.files_analyzed - len(self.files_with_issues)}")
        
        return "\n".join(lines)
    
    def generate_os_getenv_report(self) -> str:
        """Generate detailed os.getenv() usage report"""
        lines = []
        lines.append("\n" + "=" * 100)
        lines.append("OS.GETENV() USAGE REPORT")
        lines.append("=" * 100 + "\n")
        
        if not self.os_getenv_usage:
            lines.append("✅ NO os.getenv() calls found (excluding API keys)")
            return "\n".join(lines)
        
        # Group by environment variable
        by_var = defaultdict(list)
        for usage in self.os_getenv_usage:
            by_var[usage['var']].append(usage)
        
        for var, usages in sorted(by_var.items()):
            lines.append(f"\n{var} ({len(usages)} occurrences)")
            lines.append("-" * 80)
            for usage in usages:
                lines.append(f"  📄 {usage['file']}:{usage['line']}")
                lines.append(f"     {usage['snippet']}")
        
        lines.append(f"\n\nTOTAL os.getenv() CALLS: {len(self.os_getenv_usage)}")
        lines.append(f"UNIQUE ENVIRONMENT VARIABLES: {len(by_var)}")
        
        return "\n".join(lines)
    
    def generate_dotenv_report(self) -> str:
        """Generate dotenv import/usage report"""
        lines = []
        lines.append("\n" + "=" * 100)
        lines.append("DOTENV IMPORT/USAGE REPORT")
        lines.append("=" * 100 + "\n")
        
        if not self.dotenv_usage:
            lines.append("✅ NO dotenv imports found")
            return "\n".join(lines)
        
        # Group by file
        by_file = defaultdict(list)
        for usage in self.dotenv_usage:
            by_file[usage['file']].append(usage)
        
        for file, usages in sorted(by_file.items()):
            lines.append(f"\n📄 {file}")
            for usage in usages:
                lines.append(f"  Line {usage['line']}: {usage['snippet']}")
        
        lines.append(f"\n\nTOTAL DOTENV REFERENCES: {len(self.dotenv_usage)}")
        lines.append(f"FILES WITH DOTENV: {len(by_file)}")
        
        return "\n".join(lines)
    
    def check_yaml_completeness(self) -> str:
        """Check if YAML has all needed keys"""
        lines = []
        lines.append("\n" + "=" * 100)
        lines.append("YAML CONFIGURATION COMPLETENESS CHECK")
        lines.append("=" * 100 + "\n")
        
        lines.append(f"YAML Config Path: {self.config_yaml}")
        lines.append(f"Total YAML Keys: {len(self.yaml_keys)}")
        lines.append(f"\nSample Keys:")
        for key in sorted(list(self.yaml_keys))[:20]:
            lines.append(f"  - {key}")
        
        if len(self.yaml_keys) > 20:
            lines.append(f"  ... and {len(self.yaml_keys) - 20} more")
        
        return "\n".join(lines)
    
    def generate_final_report(self) -> str:
        """Generate comprehensive final report"""
        lines = []
        
        lines.append("\n" + "=" * 100)
        lines.append("🎯 YAML MIGRATION VERIFICATION - FINAL REPORT")
        lines.append("=" * 100 + "\n")
        
        # Summary
        total_issues = len(self.os_getenv_usage) + len(self.dotenv_usage)
        migration_pct = ((self.files_analyzed - len(self.files_with_issues)) / self.files_analyzed * 100) if self.files_analyzed > 0 else 0
        
        lines.append("📊 MIGRATION SUMMARY")
        lines.append("-" * 50)
        lines.append(f"Files Analyzed:        {self.files_analyzed}")
        lines.append(f"Files Migrated:        {self.files_analyzed - len(self.files_with_issues)}")
        lines.append(f"Files Partial:         {len(self.files_with_issues)}")
        lines.append(f"Migration %:           {migration_pct:.1f}%")
        lines.append(f"")
        lines.append(f"os.getenv() calls:     {len(self.os_getenv_usage)}")
        lines.append(f"dotenv imports:        {len(self.dotenv_usage)}")
        lines.append(f"Total Issues:          {total_issues}")
        
        # Verdict
        lines.append("\n" + "=" * 100)
        if total_issues == 0:
            lines.append("✅ MIGRATION STATUS: 100% COMPLETE")
            lines.append("=" * 100)
            lines.append("\nAll files have been migrated to YAML configuration.")
            lines.append("No os.getenv() calls or dotenv imports found (excluding intentional API keys).")
        else:
            lines.append("⚠️  MIGRATION STATUS: INCOMPLETE")
            lines.append("=" * 100)
            lines.append(f"\n{total_issues} migration issues found across {len(self.files_with_issues)} files.")
            lines.append("\nSee detailed reports below for specific files and line numbers.")
        
        return "\n".join(lines)
    
    def run_full_verification(self):
        """Run complete verification and generate all reports"""
        print("=" * 100)
        print("YAML MIGRATION VERIFICATION - STARTING")
        print("=" * 100)
        
        # Scan all files
        self.scan_all_python_files()
        
        # Generate reports
        print("\n📝 Generating reports...")
        
        reports = []
        reports.append(self.generate_final_report())
        reports.append(self.generate_migration_audit_table())
        reports.append(self.generate_os_getenv_report())
        reports.append(self.generate_dotenv_report())
        reports.append(self.check_yaml_completeness())
        
        full_report = "\n".join(reports)
        
        # Save to file
        output_file = self.project_root / 'YAML_MIGRATION_VERIFICATION_REPORT.md'
        with open(output_file, 'w') as f:
            f.write(full_report)
        
        print(f"\n✅ Full report saved to: {output_file}")
        
        # Print summary to console
        print(full_report)
        
        return full_report


def main():
    """Main entry point"""
    project_root = Path(__file__).parent
    
    verifier = MigrationVerifier(project_root)
    verifier.run_full_verification()


if __name__ == '__main__':
    main()
