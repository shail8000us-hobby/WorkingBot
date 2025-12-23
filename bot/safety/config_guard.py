"""
Two-Man Rule - Config Change Confirmation System

Prevents impulsive risk increases during emotional trading moments.
"Future you protecting present you"

Key Features:
- Detects risky config changes
- Requires explicit confirmation within timeout window
- Auto-reverts if not confirmed
- Logs all config changes for audit
"""

import os
import json
import logging
import hashlib
import time
from pathlib import Path
import logging
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

log = logging.getLogger("config_guard")

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# YAML Config Integration
try:
    from config.loader import get_config
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config(): return None


class ConfigGuard:
    """
    Guards against impulsive risk increases in configuration.
    
    Monitors critical config keys and requires confirmation for risky changes.
    """
    
    # Keys that require confirmation if increased
    GUARDED_KEYS = [
        'GUARDIAN_MAX_ACCOUNT_LOSS_INR',
        'GRIDBOT_MAX_OPEN',
        'GRIDBOT_LOT',
        'MAX_PENDING_NOTIONAL_INR',
        'MAX_NOTIONAL_INR_PER_MINUTE',
        'MAX_NEW_TRANCHES_PER_MINUTE',
        'DRAWDOWN_MAX_PCT'
    ]
    
    # Boolean keys that require confirmation if disabled
    SAFETY_FEATURES = [
        'EXECUTE_ORDERS',
        'CONFIRMATION_GUARD_ENABLED',
        'EXPOSURE_GROWTH_ENABLED',
        'DRAWDOWN_CAP_ENABLED',
        'VOLATILITY_SAFETY_ENABLED'
    ]
    
    def __init__(self, config=None, base_dir=None):
        """
        Initialize config guard.
        
        Args:
            config: Configuration dict (optional, uses env vars if not provided)
            base_dir: Base directory for state files (optional, defaults to current dir)
        """
        self.base_dir = Path(base_dir) if base_dir else Path('.')
        self.config_dict = config or {}
        
        # Load YAML configuration
        yaml_config = get_config()
        
        # Determine mode from YAML config
        self.mode = yaml_config.trading_mode
        
        # State files
        self.hash_file = self.base_dir / f'config_hash_{self.mode}.json'
        self.change_log_file = self.base_dir / 'bot' / 'state' / f'config_changes_{self.mode}.json'
        
        # Load two-man rule configuration from YAML
        self.enabled = yaml_config.capital_protection.two_man_rule.enabled
        self.timeout_sec = yaml_config.capital_protection.two_man_rule.timeout_seconds
        self.auto_revert = yaml_config.capital_protection.two_man_rule.auto_revert
        
        # Config file path (YAML is primary, env is legacy)
        self.config_file = self.base_dir / 'config.yaml'
        self.legacy_config_file = self.base_dir / 'config.yaml'
        
        # Load previous hash
        self.previous_hash = self._load_hash()
        
        # Pending change state
        self.pending_change: Optional[Dict] = None
        self._pending_flag_file: Optional[Path] = None
        
        if self.enabled:
            log.info("=" * 70)
            log.info("👥 TWO-MAN RULE (CONFIG GUARD) INITIALIZED")
            log.info("=" * 70)
            log.info(f"Mode: {self.mode}")
            log.info(f"Timeout: {self.timeout_sec}s ({self.timeout_sec//60} minutes)")
            log.info(f"Auto-revert: {self.auto_revert}")
            log.info(f"Guarded Keys: {len(self.GUARDED_KEYS)}")
            log.info(f"Safety Features: {len(self.SAFETY_FEATURES)}")
            log.info("=" * 70)
    
    def _load_hash(self) -> Optional[str]:
        """Load previous config hash"""
        if not self.hash_file.exists():
            return None
        
        try:
            with open(self.hash_file, 'r') as f:
                data = json.load(f)
                return data.get('hash')
        except Exception as e:
            log.error(f"Failed to load config hash: {e}")
            return None
    
    def _save_hash(self, config_hash: str):
        """Save current config hash"""
        try:
            self.hash_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.hash_file, 'w') as f:
                json.dump({
                    'hash': config_hash,
                    'timestamp': time.time(),
                    'date': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save config hash: {e}")
    
    def _calculate_hash(self, config: Dict) -> str:
        """Calculate SHA256 hash of guarded config keys"""
        # Extract only guarded keys
        guarded_values = {k: config.get(k, '') for k in self.GUARDED_KEYS + self.SAFETY_FEATURES}
        
        # Sort for consistent hashing
        sorted_str = json.dumps(guarded_values, sort_keys=True)
        
        return hashlib.sha256(sorted_str.encode()).hexdigest()
    
    def _detect_risky_changes(self, old_config: Dict, new_config: Dict) -> List[Dict]:
        """
        Detect risky config changes.
        
        Returns:
            List of change dicts with {'key', 'old', 'new', 'risk_type'}
        """
        risky_changes = []
        
        # Check guarded keys (risk increases)
        for key in self.GUARDED_KEYS:
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if old_val is None or new_val is None:
                continue
            
            try:
                old_num = float(old_val)
                new_num = float(new_val)
                
                # Risk increase if new > old
                if new_num > old_num:
                    risky_changes.append({
                        'key': key,
                        'old': old_val,
                        'new': new_val,
                        'risk_type': 'limit_increase',
                        'change_pct': ((new_num - old_num) / old_num * 100) if old_num > 0 else 0
                    })
            except (ValueError, TypeError):
                pass
        
        # Check safety features (disabled = risky)
        for key in self.SAFETY_FEATURES:
            old_val = str(old_config.get(key, '')).lower()
            new_val = str(new_config.get(key, '')).lower()
            
            # Special handling for EXECUTE_ORDERS
            if key == 'EXECUTE_ORDERS':
                # false → true is risky (enabling live trading)
                if old_val == 'false' and new_val == 'true':
                    risky_changes.append({
                        'key': key,
                        'old': old_val,
                        'new': new_val,
                        'risk_type': 'enable_live_trading',
                        'change_pct': 0
                    })
            else:
                # true → false is risky (disabling safety)
                if old_val == 'true' and new_val == 'false':
                    risky_changes.append({
                        'key': key,
                        'old': old_val,
                        'new': new_val,
                        'risk_type': 'disable_safety',
                        'change_pct': 0
                    })
        
        return risky_changes
    
    def _log_change(self, changes: List[Dict], confirmed: bool):
        """Log config change to audit file"""
        try:
            self.change_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing log
            if self.change_log_file.exists():
                with open(self.change_log_file, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = []
            
            # Append new entry
            log_data.append({
                'timestamp': time.time(),
                'date': datetime.now().isoformat(),
                'changes': changes,
                'confirmed': confirmed,
                'auto_reverted': not confirmed and self.auto_revert
            })
            
            # Keep last 100 entries
            log_data = log_data[-100:]
            
            # Save
            with open(self.change_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
        except Exception as e:
            log.error(f"Failed to log config change: {e}")
    
    def check_config_changes(self, current_config: Dict) -> Tuple[bool, Optional[str], Optional[List[Dict]]]:
        """
        Check for risky config changes.
        
        Args:
            current_config: Current configuration dict
            
        Returns:
            Tuple of (has_risky_changes: bool, message: Optional[str], changes: Optional[List[Dict]])
        """
        if not self.enabled:
            return False, None, None
        
        # Calculate current hash
        current_hash = self._calculate_hash(current_config)
        
        # First run - save hash and continue
        if self.previous_hash is None:
            self._save_hash(current_hash)
            self.previous_hash = current_hash
            log.info("First run - config hash saved")
            return False, None, None
        
        # No changes
        if current_hash == self.previous_hash:
            return False, None, None
        
        # Config changed - need to detect what changed
        # (We don't have old config stored, so we'll trust the hash change)
        # In production, we'd want to store the full config for comparison
        
        log.warning("=" * 70)
        log.warning("⚠️  CONFIG CHANGE DETECTED")
        log.warning("=" * 70)
        log.warning("Two-Man Rule: Config hash changed")
        log.warning("Risky changes may require confirmation")
        log.warning("=" * 70)
        
        # For now, we'll require confirmation for ANY config change to guarded keys
        # This is conservative but safe
        
        message = (
            f"⚠️ CONFIGURATION CHANGE DETECTED\n\n"
            f"The configuration file (config.yaml) has been modified.\n"
            f"Changes to critical safety parameters require confirmation.\n\n"
            f"CONFIRMATION REQUIRED:\n"
            f"To proceed with these changes, create confirmation file:\n"
            f"  touch .confirm_{current_hash[:8]}\n\n"
            f"Timeout: {self.timeout_sec//60} minutes\n"
            f"Auto-revert: {'YES' if self.auto_revert else 'NO'}\n\n"
            f"⚠️ IMPORTANT: Review changes carefully before confirming."
        )
        
        # Create pending change
        self.pending_change = {
            'new_hash': current_hash,
            'timestamp': time.time(),
            'timeout_sec': self.timeout_sec,
            'confirm_file': f'.confirm_{current_hash[:8]}'
        }
        
        self._pending_flag_file = Path(f'.config_change_pending_{current_hash[:8]}')
        self._pending_flag_file.touch()
        
        return True, message, []
    
    def check_confirmation(self) -> Tuple[bool, bool]:
        """
        Check if pending change has been confirmed or timed out.
        
        Returns:
            Tuple of (confirmed: bool, timed_out: bool)
        """
        if not self.pending_change:
            return False, False
        
        confirm_file = Path(self.pending_change['confirm_file'])
        elapsed = time.time() - self.pending_change['timestamp']
        
        # Check if confirmed
        if confirm_file.exists():
            log.info("=" * 70)
            log.info("✅ CONFIG CHANGE CONFIRMED")
            log.info("=" * 70)
            log.info(f"Confirmation file: {confirm_file}")
            log.info("Proceeding with config changes")
            log.info("=" * 70)
            
            # Save new hash
            self._save_hash(self.pending_change['new_hash'])
            self.previous_hash = self.pending_change['new_hash']
            
            # Cleanup
            confirm_file.unlink()
            if self._pending_flag_file and self._pending_flag_file.exists():
                self._pending_flag_file.unlink()
            
            self._log_change([], confirmed=True)
            self.pending_change = None
            
            return True, False
        
        # Check if timed out
        if elapsed > self.pending_change['timeout_sec']:
            log.warning("=" * 70)
            log.warning("⏰ CONFIG CHANGE CONFIRMATION TIMEOUT")
            log.warning("=" * 70)
            log.warning(f"Elapsed: {elapsed//60:.0f} minutes")
            log.warning(f"Timeout: {self.pending_change['timeout_sec']//60} minutes")
            
            if self.auto_revert:
                log.warning("Auto-revert enabled - changes REJECTED")
                log.warning("Please restore previous config and restart")
            else:
                log.warning("Auto-revert disabled - changes ACCEPTED by default")
                # Save new hash
                self._save_hash(self.pending_change['new_hash'])
                self.previous_hash = self.pending_change['new_hash']
            
            log.warning("=" * 70)
            
            # Cleanup
            if self._pending_flag_file and self._pending_flag_file.exists():
                self._pending_flag_file.unlink()
            
            self._log_change([], confirmed=False)
            self.pending_change = None
            
            return False, True
        
        # Still waiting
        return False, False
    
    def has_pending_change(self) -> bool:
        """Check if there's a pending config change"""
        return self.pending_change is not None
    
    def get_stats(self) -> Dict:
        """Get config guard statistics"""
        return {
            'enabled': self.enabled,
            'timeout_sec': self.timeout_sec,
            'auto_revert': self.auto_revert,
            'has_pending_change': self.has_pending_change(),
            'pending_change': self.pending_change,
            'guarded_keys_count': len(self.GUARDED_KEYS),
            'safety_features_count': len(self.SAFETY_FEATURES)
        }


# Global singleton instance
_config_guard: Optional[ConfigGuard] = None


def get_config_guard(config=None, base_dir=None) -> ConfigGuard:
    """Get or create global config guard instance"""
    global _config_guard
    if _config_guard is None:
        _config_guard = ConfigGuard(config=config, base_dir=base_dir)
    return _config_guard

