#!/usr/bin/env python3
"""
Configuration Manager
Handles config drift detection, validation, and synchronization

⚠️  INTEGRATED WITH CENTRALIZED CONFIG SYSTEM
⚠️  Use bot.config.get_config() for new code
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

from bot.state.store import StateStore

# Import the centralized config manager
try:
    from bot.config import get_config_manager, get_config, set_config, reload_config
    BULLETPROOF_AVAILABLE = True
except ImportError:
    BULLETPROOF_AVAILABLE = False

class ConfigManager:
    def __init__(self, bot_dir: str = None):
        self.bot_dir = bot_dir or os.getcwd()
        self.state_file = os.path.join(self.bot_dir, 'state.json')
        self.config_file = os.path.join(self.bot_dir, 'grid_config.env')
        self.backup_dir = os.path.join(self.bot_dir, 'config_backups')
        os.makedirs(self.backup_dir, exist_ok=True)
        self.state_store = StateStore(Path(self.state_file))
        
        # Configuration mapping between files
        self.config_mapping = {
            'state_to_config': {
                'REFERENCE_LEVEL': 'GRIDBOT_REF',
                'GRID_LOWER': 'GRIDBOT_LOWER', 
                'GRID_UPPER': 'GRIDBOT_UPPER',
                'GRID_STEP': 'GRIDBOT_STEP',
                'LOT': 'GRIDBOT_LOT'
            },
            'config_to_state': {
                'GRIDBOT_REF': 'REFERENCE_LEVEL',
                'GRIDBOT_LOWER': 'GRID_LOWER',
                'GRIDBOT_UPPER': 'GRID_UPPER', 
                'GRIDBOT_STEP': 'GRID_STEP',
                'GRIDBOT_LOT': 'LOT'
            }
        }
    
    def load_state_json(self) -> Dict[str, Any]:
        """Load state.json file"""
        try:
            return self.state_store.locked_read()
        except Exception as e:
            print(f"❌ Error loading state.json: {e}")
            return {}
    
    def load_config_env(self) -> Dict[str, str]:
        """Load grid_config.env file"""
        config = {}
        try:
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines, comments, and lines with arrows (→)
                    if (line and not line.startswith('#') and '=' in line and 
                        '→' not in line and not line.startswith('#')):
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"')
        except FileNotFoundError as e:
            print(f"❌ Error loading grid_config.env: {e}")
        return config
    
    def save_state_json(self, data: Dict[str, Any]) -> bool:
        """Save state.json file with backup"""
        try:
            # Create backup
            backup_file = os.path.join(
                self.backup_dir, 
                f"state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            if os.path.exists(self.state_file):
                os.rename(self.state_file, backup_file)
            
            # Save new data atomically
            self.state_store.save(data)
            return True
        except Exception as e:
            print(f"❌ Error saving state.json: {e}")
            return False
    
    def save_config_env(self, config: Dict[str, str]) -> bool:
        """Save grid_config.env file with backup"""
        try:
            # Create backup
            backup_file = os.path.join(
                self.backup_dir,
                f"grid_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.env"
            )
            if os.path.exists(self.config_file):
                os.rename(self.config_file, backup_file)
            
            # Save new config
            with open(self.config_file, 'w') as f:
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
            return True
        except Exception as e:
            print(f"❌ Error saving grid_config.env: {e}")
            return False
    
    def detect_config_drift(self) -> List[Dict[str, Any]]:
        """Detect configuration drift between files"""
        drift_issues = []
        
        state_data = self.load_state_json()
        config_data = self.load_config_env()
        
        # Check state.json -> grid_config.env mapping
        for state_key, config_key in self.config_mapping['state_to_config'].items():
            if state_key in state_data and config_key in config_data:
                state_value = state_data[state_key]
                config_value = config_data[config_key]
                
                # Convert to comparable types
                try:
                    state_float = float(state_value)
                    config_float = float(config_value)
                    
                    if abs(state_float - config_float) > 0.001:  # Allow small floating point differences
                        drift_issues.append({
                            'type': 'value_mismatch',
                            'file1': 'state.json',
                            'file2': 'grid_config.env',
                            'key1': state_key,
                            'key2': config_key,
                            'value1': state_value,
                            'value2': config_value,
                            'severity': 'high' if state_key == 'REFERENCE_LEVEL' else 'medium'
                        })
                except (ValueError, TypeError):
                    # For non-numeric values, compare as strings
                    if str(state_value).strip() != str(config_value).strip():
                        drift_issues.append({
                            'type': 'value_mismatch',
                            'file1': 'state.json',
                            'file2': 'grid_config.env',
                            'key1': state_key,
                            'key2': config_key,
                            'value1': state_value,
                            'value2': config_value,
                            'severity': 'medium'
                        })
        
        return drift_issues
    
    def sync_configs(self, source: str = 'grid_config.env') -> bool:
        """Synchronize configurations using specified source as truth"""
        print(f"🔄 Synchronizing configs using {source} as source of truth...")
        
        if source == 'grid_config.env':
            return self._sync_from_config_env()
        elif source == 'state.json':
            return self._sync_from_state_json()
        else:
            print(f"❌ Unknown source: {source}")
            return False
    
    def _sync_from_config_env(self) -> bool:
        """Sync state.json from grid_config.env"""
        config_data = self.load_config_env()
        state_data = self.load_state_json()
        
        # Apply mappings from grid_config.env to state.json
        for config_key, state_key in self.config_mapping['config_to_state'].items():
            if config_key in config_data:
                try:
                    # Convert string to appropriate type
                    value = config_data[config_key]
                    if value.replace('.', '').replace('-', '').isdigit():
                        state_data[state_key] = float(value)
                    else:
                        state_data[state_key] = value
                except ValueError:
                    state_data[state_key] = value
        
        # Ensure required fields exist
        required_fields = {
            'last_price': 0,
            'open_positions': [],
            'GRID_ACTIVE': True,
            'LAST_SET_AT': int(datetime.now().timestamp())
        }
        
        for field, default_value in required_fields.items():
            if field not in state_data:
                state_data[field] = default_value
        
        return self.save_state_json(state_data)
    
    def _sync_from_state_json(self) -> bool:
        """Sync grid_config.env from state.json"""
        state_data = self.load_state_json()
        config_data = self.load_config_env()
        
        # Apply mappings from state.json to grid_config.env
        for state_key, config_key in self.config_mapping['state_to_config'].items():
            if state_key in state_data:
                config_data[config_key] = str(state_data[state_key])
        
        return self.save_config_env(config_data)
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration for consistency and completeness"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        state_data = self.load_state_json()
        config_data = self.load_config_env()
        
        # Check required fields in state.json
        required_state_fields = [
            'reference_level', 'GRID_LOWER', 'GRID_UPPER', 
            'GRID_STEP', 'LOT', 'open_positions'
        ]
        
        for field in required_state_fields:
            if field not in state_data:
                validation_result['errors'].append(f"Missing required field in state.json: {field}")
                validation_result['valid'] = False
        
        # Check required fields in grid_config.env
        required_config_fields = [
            'GRIDBOT_REF', 'GRIDBOT_LOWER', 'GRIDBOT_UPPER',
            'GRIDBOT_STEP', 'GRIDBOT_LOT', 'GRIDBOT_SYMBOL'
        ]
        
        for field in required_config_fields:
            if field not in config_data:
                validation_result['errors'].append(f"Missing required field in grid_config.env: {field}")
                validation_result['valid'] = False
        
        # Check for config drift
        drift_issues = self.detect_config_drift()
        if drift_issues:
            validation_result['warnings'].extend([
                f"Config drift detected: {issue['key1']} vs {issue['key2']} "
                f"({issue['value1']} vs {issue['value2']})"
                for issue in drift_issues
            ])
        
        # Check for reasonable values
        if 'GRID_LOWER' in state_data and 'GRID_UPPER' in state_data:
            lower = float(state_data['GRID_LOWER'])
            upper = float(state_data['GRID_UPPER'])
            if lower >= upper:
                validation_result['errors'].append("GRID_LOWER must be less than GRID_UPPER")
                validation_result['valid'] = False
        
        return validation_result
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        state_data = self.load_state_json()
        config_data = self.load_config_env()
        drift_issues = self.detect_config_drift()
        validation = self.validate_config()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'state_json': {
                'file': self.state_file,
                'exists': os.path.exists(self.state_file),
                'key_values': {
                    'reference_level': state_data.get('reference_level'),
                    'GRID_LOWER': state_data.get('GRID_LOWER'),
                    'GRID_UPPER': state_data.get('GRID_UPPER'),
                    'GRID_STEP': state_data.get('GRID_STEP'),
                    'LOT': state_data.get('LOT')
                }
            },
            'grid_config_env': {
                'file': self.config_file,
                'exists': os.path.exists(self.config_file),
                'key_values': {
                    'GRIDBOT_REF': config_data.get('GRIDBOT_REF'),
                    'GRIDBOT_LOWER': config_data.get('GRIDBOT_LOWER'),
                    'GRIDBOT_UPPER': config_data.get('GRIDBOT_UPPER'),
                    'GRIDBOT_STEP': config_data.get('GRIDBOT_STEP'),
                    'GRIDBOT_LOT': config_data.get('GRIDBOT_LOT')
                }
            },
            'drift_issues': len(drift_issues),
            'validation': validation
        }

def main():
    """CLI interface for config manager"""
    import sys
    
    manager = ConfigManager()
    
    if len(sys.argv) < 2:
        print("Usage: python3 config_manager.py <command>")
        print("Commands: detect, sync, validate, summary")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'detect':
        drift_issues = manager.detect_config_drift()
        if drift_issues:
            print("🚨 Config drift detected:")
            for issue in drift_issues:
                print(f"  {issue['key1']} ({issue['file1']}): {issue['value1']}")
                print(f"  {issue['key2']} ({issue['file2']}): {issue['value2']}")
                print(f"  Severity: {issue['severity']}")
                print()
        else:
            print("✅ No config drift detected")
    
    elif command == 'sync':
        source = sys.argv[2] if len(sys.argv) > 2 else 'grid_config.env'
        if manager.sync_configs(source):
            print(f"✅ Configs synchronized using {source} as source")
        else:
            print(f"❌ Failed to sync configs")
    
    elif command == 'validate':
        validation = manager.validate_config()
        if validation['valid']:
            print("✅ Configuration is valid")
        else:
            print("❌ Configuration validation failed:")
            for error in validation['errors']:
                print(f"  - {error}")
        
        if validation['warnings']:
            print("⚠️  Warnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
    
    elif command == 'summary':
        summary = manager.get_config_summary()
        print(json.dumps(summary, indent=2))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
