#!/usr/bin/env python3
"""
Config Validation: WebUI vs Bot Code Compatibility Check

Validates that config values written by WebUI are compatible with bot code expectations.
Checks for type mismatches (true/false vs YES/NO, string vs int, etc.)
"""

import os
import re
from pathlib import Path
from collections import defaultdict

# Known special cases where bot code expects specific values
SPECIAL_VALUE_EXPECTATIONS = {
    'I_UNDERSTAND_LIVE': {
        'expected_values': ['YES', 'NO'],
        'webui_might_write': ['true', 'false'],
        'bot_check': 'Must be exactly "YES" (guards.py line 53)',
        'severity': 'CRITICAL'
    },
    'EXECUTE_ORDERS': {
        'expected_values': ['true', 'false'],
        'webui_might_write': ['true', 'false', 'True', 'False'],
        'bot_check': '.lower() == "true" (tolerant)',
        'severity': 'OK'
    },
}

# Boolean config keys that should be 'true'/'false'
BOOLEAN_KEYS = [
    'EXECUTE_ORDERS', 'GRIDBOT_ENABLED', 'GUARDIAN_ENABLED', 'MONITORING_ENABLED',
    'VOLATILITY_SAFETY_ENABLED', 'TELEGRAM_ENABLED', 'WEBSOCKET_ENABLED',
    'EQUITY_FLOOR_REQUIRE_ACK', 'TWO_MAN_RULE_ENABLED', 'SOUND_ALERTS_ENABLED'
]

# Select/dropdown keys with specific allowed values
SELECT_OPTIONS = {
    'GRIDBOT_RUNG_SNAP_MODE': ['below', 'nearest'],
    'GAP_FILL_ORDER_TYPE': ['auto', 'maker', 'taker'],
    'GRIDBOT_CANCEL_SCOPE': ['tagged', 'all'],
    'GRIDBOT_POST_ONLY_MODE': ['on', 'off', 'auto'],
    'HEARTBEAT_ACTION': ['cancel_buy_orders', 'cancel_all_orders', 'notify_only'],
    'GUARDIAN_CLOSE_ORDER_TYPE': ['market', 'limit'],
    'GUARDIAN_LOG_LEVEL': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    'LIQUIDATION_LOG_LEVEL': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    'I_UNDERSTAND_LIVE': ['NO', 'YES'],
}

def load_config(filepath):
    """Load config from grid_config.env"""
    config = {}
    if not Path(filepath).exists():
        return config
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def check_i_understand_live(config):
    """Critical check: I_UNDERSTAND_LIVE must be YES or NO"""
    value = config.get('I_UNDERSTAND_LIVE', 'NO')
    if value not in ['YES', 'NO']:
        return {
            'key': 'I_UNDERSTAND_LIVE',
            'current_value': value,
            'expected_values': ['YES', 'NO'],
            'issue': f'Bot requires exactly "YES" or "NO", found "{value}"',
            'severity': 'CRITICAL',
            'fix': 'Change to "YES" (not "true")'
        }
    return None

def check_boolean_values(config):
    """Check boolean values are lowercase true/false"""
    issues = []
    for key in BOOLEAN_KEYS:
        if key in config:
            value = config[key]
            if value not in ['true', 'false', 'True', 'False', '1', '0']:
                issues.append({
                    'key': key,
                    'current_value': value,
                    'expected_values': ['true', 'false'],
                    'issue': f'Boolean value should be "true" or "false"',
                    'severity': 'WARNING',
                    'fix': f'Change to "true" or "false"'
                })
    return issues

def check_select_values(config):
    """Check dropdown/select values are valid"""
    issues = []
    for key, allowed_values in SELECT_OPTIONS.items():
        if key in config:
            value = config[key]
            if value not in allowed_values:
                issues.append({
                    'key': key,
                    'current_value': value,
                    'expected_values': allowed_values,
                    'issue': f'Value not in allowed list',
                    'severity': 'ERROR',
                    'fix': f'Must be one of: {", ".join(allowed_values)}'
                })
    return issues

def check_numeric_values(config):
    """Check numeric values can be parsed"""
    issues = []
    numeric_patterns = [
        'MAX', 'MIN', 'INTERVAL', 'TIMEOUT', 'LIMIT', 'SIZE', 'STEP',
        'UPPER', 'LOWER', 'TICK', 'LOT', 'QTY', 'COUNT', 'RATE', 'PCT'
    ]
    
    for key, value in config.items():
        if any(pattern in key for pattern in numeric_patterns):
            try:
                # Try to convert to number
                if '.' in value:
                    float(value)
                else:
                    int(value)
            except ValueError:
                if value and value not in ['true', 'false', 'auto', 'on', 'off']:
                    issues.append({
                        'key': key,
                        'current_value': value,
                        'expected_values': ['numeric'],
                        'issue': f'Expected numeric value, got "{value}"',
                        'severity': 'ERROR',
                        'fix': 'Set to a valid number'
                    })
    return issues

def main():
    config_file = Path('grid_config.env')
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        return
    
    print("=" * 80)
    print("🔍 CONFIG VALIDATION: WebUI vs Bot Code Compatibility Check")
    print("=" * 80)
    print()
    
    config = load_config(config_file)
    print(f"📋 Loaded {len(config)} parameters from {config_file}")
    print()
    
    all_issues = []
    
    # Critical check: I_UNDERSTAND_LIVE
    critical_issue = check_i_understand_live(config)
    if critical_issue:
        all_issues.append(critical_issue)
    
    # Check boolean values
    all_issues.extend(check_boolean_values(config))
    
    # Check select/dropdown values
    all_issues.extend(check_select_values(config))
    
    # Check numeric values
    all_issues.extend(check_numeric_values(config))
    
    # Group by severity
    by_severity = defaultdict(list)
    for issue in all_issues:
        by_severity[issue['severity']].append(issue)
    
    # Report
    if not all_issues:
        print("✅ All config values are compatible with bot code!")
        print()
        return
    
    for severity in ['CRITICAL', 'ERROR', 'WARNING']:
        issues = by_severity.get(severity, [])
        if issues:
            icon = {'CRITICAL': '🔴', 'ERROR': '⚠️', 'WARNING': '⚡'}[severity]
            print(f"\n{icon} {severity}: {len(issues)} issue(s)\n")
            for issue in issues:
                print(f"  {issue['key']}:")
                print(f"    Current: {issue['current_value']}")
                print(f"    Expected: {', '.join(map(str, issue['expected_values']))}")
                print(f"    Issue: {issue['issue']}")
                print(f"    Fix: {issue['fix']}")
                print()
    
    print("=" * 80)
    print(f"Total issues: {len(all_issues)}")
    print("=" * 80)
    
    if by_severity.get('CRITICAL'):
        print("\n❌ CRITICAL issues found - bot will NOT work until fixed!")
        exit(1)
    elif by_severity.get('ERROR'):
        print("\n⚠️  ERROR issues found - may cause runtime failures!")
        exit(1)
    else:
        print("\n⚡ Only warnings found - bot should work but review recommended")
        exit(0)

if __name__ == '__main__':
    main()
