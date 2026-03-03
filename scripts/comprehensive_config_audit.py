#!/usr/bin/env python3
"""
Comprehensive Config Audit: Bot Code vs WebUI vs grid_config.env

Checks EVERY config parameter:
1. Used in bot code
2. Exposed in WebUI
3. Current value in grid_config.env
4. Type expectations (bool, int, float, enum)
5. WebUI compatibility
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import json

def extract_bot_params():
    """Extract all config parameters used in bot code"""
    params = {}
    bot_dir = Path('bot')
    
    for py_file in bot_dir.rglob('*.py'):
        with open(py_file, 'r', errors='ignore') as f:
            content = f.read()
            
            # Find os.getenv() calls
            for match in re.finditer(r'os\.getenv\(["\']([A-Z_]+)["\']\s*,\s*([^)]+)\)', content):
                param = match.group(1)
                default = match.group(2).strip().strip('"\'')
                if param not in params:
                    params[param] = {'default': default, 'files': []}
                params[param]['files'].append(str(py_file))
            
            # Find get_config() calls
            for match in re.finditer(r'get_config\(["\']([A-Z_]+)["\']\s*,\s*([^)]+)\)', content):
                param = match.group(1)
                default = match.group(2).strip().strip('"\'')
                if param not in params:
                    params[param] = {'default': default, 'files': []}
                params[param]['files'].append(str(py_file))
    
    return params

def extract_webui_params():
    """Extract all config parameters exposed in WebUI"""
    webui_params = set()
    frontend_dir = Path('webui/frontend/src')
    
    for js_file in frontend_dir.rglob('*.js'):
        with open(js_file, 'r', errors='ignore') as f:
            content = f.read()
            # Find config keys in WebUI
            for match in re.finditer(r'["\']([A-Z_]{3,})["\']', content):
                param = match.group(1)
                if param.startswith(('GRIDBOT_', 'DELTA_', 'GUARDIAN_', 'MAX_', 'MIN_', 
                                    'TELEGRAM_', 'VOLATILITY_', 'EXECUTE_', 'I_UNDERSTAND',
                                    'DRAWDOWN_', 'EQUITY_', 'MONITORING_')):
                    webui_params.add(param)
    
    return webui_params

def load_current_config():
    """Load current values from grid_config.env"""
    config = {}
    config_file = Path('grid_config.env')
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config

def infer_type(default_value, current_value=None):
    """Infer expected type from default value"""
    val = current_value or default_value
    
    if val in ['true', 'false', 'True', 'False']:
        return 'boolean'
    if val in ['YES', 'NO']:
        return 'yes_no'
    if val in ['"below"', '"nearest"', '"market"', '"limit"', '"tagged"', '"all"', 
               'below', 'nearest', 'market', 'limit', 'tagged', 'all', 'auto', 'on', 'off']:
        return 'enum'
    
    try:
        int(val.strip('"'))
        return 'integer'
    except:
        pass
    
    try:
        float(val.strip('"'))
        return 'float'
    except:
        pass
    
    return 'string'

def check_webui_compatibility(param, param_type, current_value):
    """Check if WebUI can correctly handle this parameter"""
    issues = []
    
    # Critical: I_UNDERSTAND_LIVE must be YES/NO
    if param == 'I_UNDERSTAND_LIVE':
        if current_value not in ['YES', 'NO']:
            issues.append(f"CRITICAL: Must be 'YES' or 'NO', found '{current_value}'")
    
    # Check for quoted values in config (WebUI bug)
    if current_value and current_value.startswith('"') and current_value.endswith('"'):
        issues.append(f"WebUI added quotes: '{current_value}' - bot will read with quotes!")
    
    # Boolean parameters should use lowercase true/false
    if param_type == 'boolean' and current_value not in ['true', 'false']:
        if current_value not in ['True', 'False', '1', '0']:
            issues.append(f"Boolean should be 'true'/'false', found '{current_value}'")
    
    return issues

def main():
    print("="*100)
    print("🔍 COMPREHENSIVE CONFIG AUDIT: Bot Code vs WebUI vs grid_config.env")
    print("="*100)
    print()
    
    print("📊 Extracting data...")
    bot_params = extract_bot_params()
    webui_params = extract_webui_params()
    current_config = load_current_config()
    
    print(f"  • Bot code uses: {len(bot_params)} parameters")
    print(f"  • WebUI exposes: {len(webui_params)} parameters")
    print(f"  • Config file has: {len(current_config)} parameters")
    print()
    
    # Categorize
    only_bot = set(bot_params.keys()) - webui_params
    only_webui = webui_params - set(bot_params.keys())
    both = set(bot_params.keys()) & webui_params
    
    print("="*100)
    print(f"📋 COVERAGE ANALYSIS")
    print("="*100)
    print(f"  ✅ In both bot & WebUI: {len(both)}")
    print(f"  ⚠️  Only in bot (not in WebUI): {len(only_bot)}")
    print(f"  ⚡ Only in WebUI (not used by bot): {len(only_webui)}")
    print()
    
    # Check for issues
    all_issues = defaultdict(list)
    
    for param in bot_params:
        current_value = current_config.get(param, 'NOT_SET')
        default_value = bot_params[param]['default']
        param_type = infer_type(default_value, current_value if current_value != 'NOT_SET' else None)
        
        issues = check_webui_compatibility(param, param_type, current_value)
        if issues:
            all_issues[param] = {
                'current': current_value,
                'default': default_value,
                'type': param_type,
                'issues': issues,
                'in_webui': param in webui_params
            }
    
    if all_issues:
        print("="*100)
        print(f"🔴 ISSUES FOUND: {len(all_issues)} parameters have problems")
        print("="*100)
        print()
        
        for param, data in sorted(all_issues.items()):
            print(f"  {param}:")
            print(f"    Current: {data['current']}")
            print(f"    Default: {data['default']}")
            print(f"    Type: {data['type']}")
            print(f"    In WebUI: {'✅' if data['in_webui'] else '❌'}")
            for issue in data['issues']:
                print(f"    ⚠️  {issue}")
            print()
    else:
        print("✅ No compatibility issues found!")
        print()
    
    # Show parameters only in bot (missing from WebUI)
    if only_bot:
        print("="*100)
        print(f"⚠️  PARAMETERS ONLY IN BOT CODE (Not exposed in WebUI): {len(only_bot)}")
        print("="*100)
        print()
        for param in sorted(only_bot)[:20]:  # Show first 20
            current_value = current_config.get(param, 'NOT_SET')
            print(f"  • {param} = {current_value}")
        if len(only_bot) > 20:
            print(f"  ... and {len(only_bot) - 20} more")
        print()
    
    print("="*100)
    print("✅ AUDIT COMPLETE")
    print("="*100)

if __name__ == '__main__':
    main()
