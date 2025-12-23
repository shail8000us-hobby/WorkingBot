#!/usr/bin/env python3
"""
Quick Error Scan - Fast error detection for startup issues
Used by the Error Resolution Panel for quick diagnostics
"""

import sys
import os
from pathlib import Path
import json
import re
from datetime import datetime, timedelta

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def scan_startup_errors():
    """Quick scan for common startup errors"""
    errors_found = []
    
    # Check configuration file
    config_file = BASE_DIR / 'config.yaml'
    if config_file.exists():
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Check for missing critical settings
        if 'TRADING_MODE=' not in content:
            errors_found.append({
                'type': 'config_missing',
                'message': 'TRADING_MODE setting not found',
                'severity': 'high'
            })
        
        if 'EXECUTE_ORDERS=' not in content:
            errors_found.append({
                'type': 'config_missing',
                'message': 'EXECUTE_ORDERS setting not found',
                'severity': 'medium'
            })
        
        # Check for dangerous combinations
        if 'TRADING_MODE=live' in content and 'I_UNDERSTAND_LIVE=YES' not in content:
            errors_found.append({
                'type': 'config_dangerous',
                'message': 'Live mode without acknowledgment',
                'severity': 'critical'
            })
    
    # Check for emergency flags
    emergency_flag = BASE_DIR / '.guardian_emergency_stop'
    if emergency_flag.exists():
        errors_found.append({
            'type': 'emergency_flag',
            'message': 'Emergency stop flag exists',
            'severity': 'critical'
        })
    
    # Check recent bot logs for common issues
    log_file = BASE_DIR / 'bot_run.log'
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Check last 50 lines for common issues
            recent_lines = lines[-50:] if len(lines) > 50 else lines
            
            for line in recent_lines:
                if 'Safety gatekeeper blocked' in line:
                    errors_found.append({
                        'type': 'safety_block',
                        'message': 'Safety gatekeeper blocking orders',
                        'severity': 'medium'
                    })
                    break  # Only report once
                
                if 'CONFIGURATION CHANGES DETECTED' in line:
                    errors_found.append({
                        'type': 'config_change',
                        'message': 'Configuration changes detected',
                        'severity': 'low'
                    })
                    break  # Only report once
                    
        except Exception as e:
            errors_found.append({
                'type': 'log_error',
                'message': f'Could not read bot log: {e}',
                'severity': 'low'
            })
    
    return errors_found

def main():
    """Main entry point"""
    try:
        errors = scan_startup_errors()
        
        # Output results as JSON
        result = {
            'timestamp': datetime.now().isoformat(),
            'errors_found': len(errors),
            'errors': errors,
            'scan_type': 'startup_quick'
        }
        
        print(json.dumps(result, indent=2))
        
        # Exit with error code if critical issues found
        critical_count = sum(1 for e in errors if e['severity'] == 'critical')
        if critical_count > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        error_result = {
            'timestamp': datetime.now().isoformat(),
            'errors_found': 1,
            'errors': [{
                'type': 'scan_error',
                'message': f'Scan failed: {e}',
                'severity': 'high'
            }],
            'scan_type': 'startup_quick'
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

if __name__ == '__main__':
    main()