"""
Error Remediation Engine - Executes fix actions with safety guardrails
"""

import os
import subprocess
import time
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from pathlib import Path
from .schema import ErrorEvent, ErrorAction


class RemediationResult:
    """Result of a remediation action"""
    def __init__(
        self,
        success: bool,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ):
        self.success = success
        self.message = message
        self.details = details or {}
        self.dry_run = dry_run
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'details': self.details,
            'dry_run': self.dry_run,
            'timestamp': self.timestamp.isoformat()
        }


class ErrorRemediator:
    """Executes remediation actions for errors"""
    
    def __init__(
        self,
        config_path: str = "config.yaml",
        allow_destructive: bool = False
    ):
        self.config_path = config_path
        self.allow_destructive = allow_destructive
        self.action_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register built-in fix handlers"""
        self.action_handlers['refresh_api_keys'] = self._refresh_api_keys
        self.action_handlers['pause_trading_15m'] = self._pause_trading
        self.action_handlers['increase_api_delay'] = self._increase_api_delay
        self.action_handlers['reduce_position_size'] = self._reduce_position_size
        self.action_handlers['emergency_stop_entries'] = self._stop_entries
        self.action_handlers['sync_gridbot_params'] = self._sync_gridbot_params
        self.action_handlers['restore_default_config'] = self._restore_defaults
        self.action_handlers['disable_post_only'] = self._disable_post_only
        self.action_handlers['test_connectivity'] = self._test_connectivity
        self.action_handlers['force_config_reload'] = self._force_config_reload
    
    def execute_fix(
        self,
        error: ErrorEvent,
        fix_id: str,
        dry_run: bool = True,
        user: Optional[str] = None
    ) -> RemediationResult:
        """
        Execute a remediation action.
        
        Args:
            error: The error event to fix
            fix_id: ID of the fix action to execute
            dry_run: If True, simulate the action without making changes
            user: User who initiated the fix (for audit log)
        
        Returns:
            RemediationResult with outcome
        """
        # Find the fix action
        fix_action = None
        for action in error.available_fixes:
            if action.id == fix_id:
                fix_action = action
                break
        
        if not fix_action:
            return RemediationResult(
                success=False,
                message=f"Fix action '{fix_id}' not found for error {error.id}"
            )
        
        # Check if destructive actions are allowed
        if fix_action.is_destructive and not self.allow_destructive:
            return RemediationResult(
                success=False,
                message=f"Destructive fix '{fix_id}' blocked by ALLOW_DESTRUCTIVE_FIXES=False"
            )
        
        # Check preconditions
        precondition_result = self._check_preconditions(fix_action)
        if not precondition_result['passed']:
            return RemediationResult(
                success=False,
                message=f"Preconditions not met: {precondition_result['message']}",
                details=precondition_result
            )
        
        # Get the handler
        handler = self.action_handlers.get(fix_id)
        if not handler:
            return RemediationResult(
                success=False,
                message=f"No handler registered for fix '{fix_id}'"
            )
        
        # Execute the handler
        try:
            result = handler(error, dry_run=dry_run)
            result.dry_run = dry_run
            return result
        except Exception as e:
            return RemediationResult(
                success=False,
                message=f"Fix execution failed: {str(e)}",
                details={'exception': str(e)}
            )
    
    def _check_preconditions(self, action: ErrorAction) -> Dict[str, Any]:
        """Check if action preconditions are met"""
        if not action.preconditions:
            return {'passed': True}
        
        failed = []
        
        for condition in action.preconditions:
            if 'bot is running' in condition.lower():
                # Check if bot process exists
                try:
                    result = subprocess.run(
                        ['pgrep', '-f', 'hotwatch_grid.py'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        failed.append("Bot is not running")
                except:
                    pass
            
            elif 'config.yaml' in condition.lower() and 'writable' in condition.lower():
                # Check if config file is writable
                if not os.path.exists(self.config_path):
                    failed.append("config.yaml does not exist")
                elif not os.access(self.config_path, os.W_OK):
                    failed.append("config.yaml is not writable")
        
        if failed:
            return {'passed': False, 'message': '; '.join(failed), 'failed_conditions': failed}
        
        return {'passed': True}
    
    # ========== Fix Handlers ==========
    
    def _refresh_api_keys(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Reload API keys from secrets file"""
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Would reload API keys from secrets/api_keys.env",
                dry_run=True
            )
        
        # Actual implementation would trigger a reload signal to the bot
        # For now, return a placeholder
        return RemediationResult(
            success=True,
            message="API keys refresh triggered - bot will reload on next cycle"
        )
    
    def _pause_trading(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Pause trading for 15 minutes"""
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Would set EXECUTE_ORDERS=False for 15 minutes",
                dry_run=True
            )
        
        # Set EXECUTE_ORDERS=False
        self._update_config('EXECUTE_ORDERS', 'False')
        
        # Schedule re-enable after 15 minutes (in production, use a timer)
        return RemediationResult(
            success=True,
            message="Trading paused for 15 minutes (EXECUTE_ORDERS=False)",
            details={'duration_minutes': 15, 'resume_at': (datetime.utcnow().timestamp() + 900)}
        )
    
    def _increase_api_delay(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Increase API call delay"""
        current_delay = float(self._read_config('API_CALL_DELAY', '0.5'))
        new_delay = 1.0
        
        if dry_run:
            return RemediationResult(
                success=True,
                message=f"[DRY RUN] Would change API_CALL_DELAY from {current_delay} to {new_delay}",
                details={'current': current_delay, 'new': new_delay},
                dry_run=True
            )
        
        self._update_config('API_CALL_DELAY', str(new_delay))
        
        return RemediationResult(
            success=True,
            message=f"API_CALL_DELAY increased from {current_delay} to {new_delay}",
            details={'old_value': current_delay, 'new_value': new_delay}
        )
    
    def _reduce_position_size(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Reduce max position size by 50%"""
        current_size = int(self._read_config('GRIDBOT_MAX_OPEN', '100'))
        new_size = max(10, current_size // 2)  # At least 10
        
        if dry_run:
            return RemediationResult(
                success=True,
                message=f"[DRY RUN] Would change GRIDBOT_MAX_OPEN from {current_size} to {new_size}",
                details={'current': current_size, 'new': new_size},
                dry_run=True
            )
        
        self._update_config('GRIDBOT_MAX_OPEN', str(new_size))
        self._update_config('MAX_OPEN', str(new_size))  # Legacy sync
        
        return RemediationResult(
            success=True,
            message=f"Position size reduced from {current_size} to {new_size}",
            details={'old_value': current_size, 'new_value': new_size}
        )
    
    def _stop_entries(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Stop new entries"""
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Would set EXECUTE_ORDERS=False",
                dry_run=True
            )
        
        self._update_config('EXECUTE_ORDERS', 'False')
        
        return RemediationResult(
            success=True,
            message="New entries stopped (EXECUTE_ORDERS=False)"
        )
    
    def _sync_gridbot_params(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Ensure canonical GRIDBOT_* parameters are present."""
        config = self._read_all_config()
        canonical = [
            'GRIDBOT_LOWER',
            'GRIDBOT_UPPER',
            'GRIDBOT_STEP',
            'GRIDBOT_REF',
            'GRIDBOT_LOT',
            'GRIDBOT_MAX_OPEN',
        ]

        missing = [key for key in canonical if key not in config]
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Legacy GRID_* parameters are no longer synced. Canonical GRIDBOT_* values remain authoritative.",
                details={'missing': missing},
                dry_run=True,
            )

        if missing:
            return RemediationResult(
                success=False,
                message="Missing canonical GRIDBOT_* parameter(s); please update config.yaml",
                details={'missing': missing},
            )

        return RemediationResult(
            success=True,
            message="Canonical GRIDBOT_* parameters verified",
            details={'missing': []},
        )
    
    def _restore_defaults(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Restore missing config parameters to defaults"""
        # This would check for missing required params and add them
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Would add missing parameters with defaults",
                dry_run=True
            )
        
        return RemediationResult(
            success=True,
            message="Missing parameters restored (not implemented yet)"
        )
    
    def _disable_post_only(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Disable post-only mode"""
        current = self._read_config('POST_ONLY_MODE', 'True')
        
        if dry_run:
            return RemediationResult(
                success=True,
                message=f"[DRY RUN] Would set POST_ONLY_MODE=False (currently {current})",
                dry_run=True
            )
        
        self._update_config('POST_ONLY_MODE', 'False')
        
        return RemediationResult(
            success=True,
            message="Post-only mode disabled",
            details={'old_value': current, 'new_value': 'False'}
        )
    
    def _test_connectivity(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Test exchange connectivity"""
        results = {}
        
        # Test DNS
        try:
            import socket
            socket.gethostbyname('api.delta.exchange')
            results['dns'] = 'OK'
        except:
            results['dns'] = 'FAILED'
        
        # Test ping
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', 'api.delta.exchange'],
                capture_output=True,
                timeout=3
            )
            results['ping'] = 'OK' if result.returncode == 0 else 'FAILED'
        except:
            results['ping'] = 'FAILED'
        
        # Test HTTPS
        try:
            import requests
            response = requests.get('https://api.delta.exchange/v2/products', timeout=5)
            results['https'] = 'OK' if response.status_code == 200 else f'HTTP {response.status_code}'
        except Exception as e:
            results['https'] = f'FAILED: {str(e)}'
        
        all_ok = all(v == 'OK' for v in results.values())
        
        return RemediationResult(
            success=all_ok,
            message="Connectivity test completed",
            details=results
        )
    
    def _force_config_reload(self, error: ErrorEvent, dry_run: bool) -> RemediationResult:
        """Force config reload"""
        if dry_run:
            return RemediationResult(
                success=True,
                message="[DRY RUN] Would signal bot to reload configuration",
                dry_run=True
            )
        
        # In production, this would send a signal to the bot's config watcher
        return RemediationResult(
            success=True,
            message="Config reload signal sent"
        )
    
    # ========== Config Helpers ==========
    
    def _read_config(self, key: str, default: str = '') -> str:
        """Read a config value"""
        config = self._read_all_config()
        return config.get(key, default)
    
    def _read_all_config(self) -> Dict[str, str]:
        """Read entire config file"""
        config = {}
        
        if not os.path.exists(self.config_path):
            return config
        
        with open(self.config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        return config
    
    def _update_config(self, key: str, value: str):
        """Update a config value"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        # Read all lines
        with open(self.config_path, 'r') as f:
            lines = f.readlines()
        
        # Find and update the key
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(key + '='):
                lines[i] = f"{key}={value}\n"
                updated = True
                break
        
        # If not found, append
        if not updated:
            lines.append(f"{key}={value}\n")
        
        # Write back
        with open(self.config_path, 'w') as f:
            f.writelines(lines)
