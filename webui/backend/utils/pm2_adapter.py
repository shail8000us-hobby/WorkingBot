"""
PM2 Integration Module for WebUI

This module provides integration between the WebUI backend and PM2 process manager.
It allows the WebUI to control bots managed by PM2 instead of direct subprocess management.

Features:
- Start/stop/restart bots via PM2
- Get bot status from PM2
- Graceful shutdown with 30s timeout
- Auto-restart on crash
- Log management
- Resource monitoring

Usage:
    from utils.pm2_adapter import PM2Adapter
    
    pm2 = PM2Adapter()
    
    # Start bot
    success, message = pm2.start_bot('live')
    
    # Stop bot
    success, message = pm2.stop_bot('live')
    
    # Get status
    status = pm2.get_bot_status('live')

Environment Variables:
    USE_PM2=true - Enable PM2 integration (default: false)
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Load YAML config
from config.loader import get_config

log = logging.getLogger(__name__)

# Detect if PM2 is available — lazy to avoid blocking Gunicorn worker boot
def is_pm2_available() -> bool:
    """Check if PM2 is installed and available.
    Uses shutil.which() first to avoid subprocess calls entirely when pm2 is not installed.
    """
    try:
        import shutil
        if not shutil.which('pm2'):
            return False
    except Exception:
        return False
    try:
        result = subprocess.run(
            ['pm2', '--version'],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False

# Lazy initialization — these are computed on first access, not at import time
_pm2_initialized = False
PM2_AVAILABLE = False
USE_PM2 = False

def _ensure_pm2_initialized():
    """Initialize PM2 detection lazily on first use, not at import time."""
    global _pm2_initialized, PM2_AVAILABLE, USE_PM2
    if _pm2_initialized:
        return
    _pm2_initialized = True

    PM2_AVAILABLE = is_pm2_available()

    # Check if PM2 is enabled via YAML config
    try:
        cfg = get_config()
        if hasattr(cfg, 'pm2') and hasattr(cfg.pm2, 'enabled'):
            USE_PM2 = cfg.pm2.enabled
            log.info(f"✅ PM2 enabled via cfg.pm2.enabled = {USE_PM2}")
        elif hasattr(cfg, 'webui') and hasattr(cfg.webui, 'pm2') and hasattr(cfg.webui.pm2, 'enabled'):
            USE_PM2 = cfg.webui.pm2.enabled
            log.info(f"✅ PM2 enabled via cfg.webui.pm2.enabled = {USE_PM2}")
    except Exception as e:
        log.warning(f"Could not load PM2 config: {e}")

    log.info(f"🔧 PM2 Initialization: PM2_AVAILABLE={PM2_AVAILABLE}, USE_PM2={USE_PM2}")

class PM2Adapter:
    """
    Adapter class for PM2 process manager integration
    
    This class provides a unified interface for managing bots via PM2,
    with fallback to direct process management if PM2 is not available.
    """
    
    def __init__(self, config_file: str = 'ecosystem.config.js'):
        """
        Initialize PM2 adapter

        Args:
            config_file: Path to PM2 ecosystem config file
        """
        _ensure_pm2_initialized()
        self.config_file = Path(__file__).parent.parent.parent.parent / config_file
        self.available = PM2_AVAILABLE
        self.enabled = USE_PM2 and PM2_AVAILABLE
        
        if USE_PM2 and not PM2_AVAILABLE:
            log.warning("PM2 is enabled but not installed. Falling back to direct process management.")
        
        # Bot name mapping (v5.0: Support multi-instance names)
        # For backward compatibility, check for both old and new naming conventions
        self.bot_names = {
            'live': 'gridbot-live',  # Legacy single-bot name
            'demo': 'gridbot-demo'   # Legacy demo name
        }
        # v5.0: Try to detect active instance from PM2
        self._detect_active_instance()
    
    def _detect_active_instance(self):
        """Detect which bot instance is actually running in PM2 (v5.0 multi-instance support)"""
        if not self.enabled:
            return
        
        try:
            success, stdout, _ = self._run_pm2_command(['jlist'])
            if success:
                processes = json.loads(stdout)
                for proc in processes:
                    name = proc.get('name', '')
                    pm2_env = proc.get('pm2_env', {})
                    status = pm2_env.get('status')
                    
                    # Check for gridbot-SYMBOL-MODE pattern (v5.0), gridbot-SYMBOL-live (v5.0 alt), or gridbot-live/demo (legacy)
                    if name.startswith('gridbot-') and status == 'online':
                        # Map to 'live' mode for API compatibility
                        if 'LONG' in name or 'SHORT' in name or name == 'gridbot-live' or '-live' in name:
                            self.bot_names['live'] = name
                            log.info(f"✅ Detected active bot instance: {name}")
                            return
        except Exception as e:
            log.debug(f"Could not detect active instance: {e}")
    
    def _run_pm2_command(self, args: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
        """
        Run a PM2 command
        
        Args:
            args: Command arguments
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ['pm2'] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.config_file.parent)
            )
            
            return (
                result.returncode == 0,
                result.stdout.strip(),
                result.stderr.strip()
            )
            
        except subprocess.TimeoutExpired:
            return False, '', f'Command timeout after {timeout}s'
        except Exception as e:
            return False, '', str(e)
    
    def start_bot(self, mode: str = 'live') -> Tuple[bool, str]:
        """
        Start bot via PM2
        
        Args:
            mode: 'live' or 'demo'
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return False, f'Invalid mode: {mode}'
        
        # Check if already running
        status = self.get_bot_status(mode)
        if status and status.get('status') == 'online':
            return False, f'{bot_name} is already running'
        
        # Start via PM2
        success, stdout, stderr = self._run_pm2_command([
            'start',
            str(self.config_file),
            '--only',
            bot_name
        ])
        
        if not success:
            log.error(f"PM2 start failed: {stderr}")
            return False, f'Failed to start {bot_name}: {stderr}'
        
        # Save PM2 process list
        self._run_pm2_command(['save', '--force'])
        
        log.info(f"Started {bot_name} via PM2")
        return True, f'{bot_name} started successfully'
    
    def stop_bot(self, mode: str = 'live', force: bool = False) -> Tuple[bool, str]:
        """
        Stop bot via PM2 (graceful shutdown with 30s timeout)
        
        Args:
            mode: 'live' or 'demo'
            force: Force immediate kill (skip graceful shutdown)
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return False, f'Invalid mode: {mode}'
        
        # Check if running
        status = self.get_bot_status(mode)
        if not status or status.get('status') != 'online':
            return True, f'{bot_name} is not running'
        
        # Stop via PM2 (graceful by default with 30s timeout from config)
        command = ['delete' if force else 'stop', bot_name]
        
        success, stdout, stderr = self._run_pm2_command(command, timeout=40)
        
        if not success:
            log.error(f"PM2 stop failed: {stderr}")
            return False, f'Failed to stop {bot_name}: {stderr}'
        
        # Save PM2 process list
        self._run_pm2_command(['save', '--force'])
        
        log.info(f"Stopped {bot_name} via PM2 (force={force})")
        return True, f'{bot_name} stopped successfully'
    
    def restart_bot(self, mode: str = 'live') -> Tuple[bool, str]:
        """
        Restart bot via PM2
        
        Args:
            mode: 'live' or 'demo'
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return False, f'Invalid mode: {mode}'
        
        # Restart via PM2
        success, stdout, stderr = self._run_pm2_command([
            'restart',
            bot_name
        ], timeout=40)
        
        if not success:
            log.error(f"PM2 restart failed: {stderr}")
            return False, f'Failed to restart {bot_name}: {stderr}'
        
        # Save PM2 process list
        self._run_pm2_command(['save', '--force'])
        
        log.info(f"Restarted {bot_name} via PM2")
        return True, f'{bot_name} restarted successfully'
    
    def reload_bot(self, mode: str = 'live') -> Tuple[bool, str]:
        """
        Reload bot via PM2 (zero-downtime reload)
        
        Args:
            mode: 'live' or 'demo'
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return False, f'Invalid mode: {mode}'
        
        # Reload via PM2
        success, stdout, stderr = self._run_pm2_command([
            'reload',
            bot_name
        ], timeout=40)
        
        if not success:
            log.error(f"PM2 reload failed: {stderr}")
            return False, f'Failed to reload {bot_name}: {stderr}'
        
        # Save PM2 process list
        self._run_pm2_command(['save', '--force'])
        
        log.info(f"Reloaded {bot_name} via PM2")
        return True, f'{bot_name} reloaded successfully'
    
    def get_bot_status(self, mode: str = 'live') -> Optional[Dict]:
        """
        Get bot status from PM2
        
        Args:
            mode: 'live' or 'demo'
            
        Returns:
            Dict with bot status or None if not found
        """
        if not self.enabled:
            return None
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return None
        
        # Get status via PM2 (JSON format)
        success, stdout, stderr = self._run_pm2_command([
            'jlist'  # JSON list
        ])
        
        if not success:
            log.error(f"PM2 jlist failed: {stderr}")
            return None
        
        try:
            processes = json.loads(stdout)
            
            # Find our bot
            for proc in processes:
                if proc.get('name') == bot_name:
                    pm2_env = proc.get('pm2_env', {})
                    monit = proc.get('monit', {})
                    
                    return {
                        'name': bot_name,
                        'pid': proc.get('pid'),
                        'status': pm2_env.get('status'),  # 'online', 'stopped', 'errored'
                        'uptime': pm2_env.get('pm_uptime'),
                        'restarts': pm2_env.get('restart_time', 0),
                        'cpu': monit.get('cpu', 0),
                        'memory': monit.get('memory', 0) / 1024 / 1024,  # MB
                        'mode': mode,
                        'pm2_id': proc.get('pm_id')
                    }
            
            return None  # Bot not found
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse PM2 output: {e}")
            return None
    
    def get_all_bots_status(self) -> List[Dict]:
        """
        Get status of all managed bots (scans all PM2 gridbot processes)
        
        Returns:
            List of bot status dicts
        """
        if not self.enabled:
            return []
        
        bots = []
        
        # First, get explicitly mapped modes
        for mode in ['live', 'demo']:
            status = self.get_bot_status(mode)
            if status:
                bots.append(status)
        
        # Also scan for any gridbot- processes not yet in bot_names
        try:
            success, stdout, _ = self._run_pm2_command(['jlist'])
            if success:
                seen_names = {b['name'] for b in bots}
                processes = json.loads(stdout)
                for proc in processes:
                    name = proc.get('name', '')
                    if name.startswith('gridbot-') and name not in seen_names:
                        pm2_env = proc.get('pm2_env', {})
                        monit = proc.get('monit', {})
                        bots.append({
                            'name': name,
                            'pid': proc.get('pid'),
                            'status': pm2_env.get('status'),
                            'uptime': pm2_env.get('pm_uptime'),
                            'restarts': pm2_env.get('restart_time', 0),
                            'cpu': monit.get('cpu', 0),
                            'memory': monit.get('memory', 0) / 1024 / 1024,
                            'mode': 'live',
                            'pm2_id': proc.get('pm_id')
                        })
        except Exception as e:
            log.debug(f"Could not scan extra PM2 processes: {e}")
        
        return bots
    
    def get_bot_logs(self, mode: str = 'live', lines: int = 30) -> Tuple[bool, str]:
        """
        Get bot logs from PM2
        
        Args:
            mode: 'live' or 'demo'
            lines: Number of lines to retrieve
            
        Returns:
            Tuple of (success, logs)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        bot_name = self.bot_names.get(mode)
        if not bot_name:
            return False, f'Invalid mode: {mode}'
        
        # Get logs via PM2
        success, stdout, stderr = self._run_pm2_command([
            'logs',
            bot_name,
            '--nostream',
            '--lines',
            str(lines)
        ], timeout=10)
        
        if not success:
            return False, stderr
        
        return True, stdout
    
    def flush_logs(self) -> Tuple[bool, str]:
        """
        Flush all PM2 logs
        
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['flush'])
        
        if not success:
            return False, f'Failed to flush logs: {stderr}'
        
        return True, 'Logs flushed successfully'
    
    def save_process_list(self) -> Tuple[bool, str]:
        """
        Save current PM2 process list
        
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['save', '--force'])
        
        if not success:
            return False, f'Failed to save: {stderr}'
        
        return True, 'Process list saved successfully'
    
    def list_all_processes(self) -> List[Dict]:
        """
        Get list of all PM2 processes
        
        Returns:
            List of process dictionaries with detailed information
        """
        if not self.enabled:
            return []
        
        try:
            success, stdout, stderr = self._run_pm2_command(['jlist'])
            
            if not success:
                log.error(f"Failed to list processes: {stderr}")
                return []
            
            import json
            processes_raw = json.loads(stdout) if stdout else []
            
            # Format process information
            processes = []
            for proc in processes_raw:
                pm2_env = proc.get('pm2_env', {})
                monit = proc.get('monit', {})
                
                processes.append({
                    'name': proc.get('name'),
                    'pm_id': proc.get('pm_id'),
                    'pid': proc.get('pid', 0),
                    'status': pm2_env.get('status', 'unknown'),
                    'cpu': round(monit.get('cpu', 0), 2),
                    'memory': round(monit.get('memory', 0) / (1024 * 1024), 2),  # Convert to MB
                    'uptime': pm2_env.get('pm_uptime', 0),
                    'restarts': pm2_env.get('restart_time', 0),
                    'created_at': pm2_env.get('created_at', 0),
                    'script': pm2_env.get('pm_exec_path', ''),
                    'interpreter': pm2_env.get('exec_interpreter', 'python3'),
                    'exec_mode': pm2_env.get('exec_mode', 'fork'),
                    'watching': pm2_env.get('watch', False)
                })
            
            return processes
            
        except Exception as e:
            log.error(f"Error listing PM2 processes: {e}")
            return []
    
    def describe_process(self, name: str) -> Optional[Dict]:
        """
        Get detailed information about a specific process
        
        Args:
            name: Process name
            
        Returns:
            Process details dictionary or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            # Use jlist instead of describe for reliable JSON output
            success, stdout, stderr = self._run_pm2_command(['jlist'])
            
            if not success or not stdout:
                return None
            
            import json
            processes = json.loads(stdout) if stdout else []
            
            # Find the process by name
            proc = None
            for p in processes:
                if p.get('name') == name:
                    proc = p
                    break
            
            if not proc:
                return None
            
            pm2_env = proc.get('pm2_env', {})
            monit = proc.get('monit', {})
            
            return {
                'name': proc.get('name'),
                'pm_id': proc.get('pm_id'),
                'pid': proc.get('pid', 0),
                'status': pm2_env.get('status', 'unknown'),
                'cpu': round(monit.get('cpu', 0), 2),
                'memory': round(monit.get('memory', 0) / (1024 * 1024), 2),  # MB
                'uptime': pm2_env.get('pm_uptime', 0),
                'restarts': pm2_env.get('restart_time', 0),
                'unstable_restarts': pm2_env.get('unstable_restarts', 0),
                'created_at': pm2_env.get('created_at', 0),
                'script': pm2_env.get('pm_exec_path', ''),
                'interpreter': pm2_env.get('exec_interpreter', 'python3'),
                'exec_mode': pm2_env.get('exec_mode', 'fork'),
                'watching': pm2_env.get('watch', False),
                'cwd': pm2_env.get('pm_cwd', ''),
                'env': pm2_env.get('env', {}),
                'log_file': pm2_env.get('pm_out_log_path', ''),
                'error_file': pm2_env.get('pm_err_log_path', ''),
                'kill_timeout': pm2_env.get('kill_timeout', 30000),
                'kill_signal': pm2_env.get('kill_signal', 'SIGTERM')
            }
            
        except Exception as e:
            log.error(f"Error describing process {name}: {e}")
            return None
    
    def start_process(self, name: str) -> Tuple[bool, str]:
        """
        Start a specific process by name
        
        Args:
            name: Process name
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command([
            'start',
            str(self.config_file),
            '--only',
            name
        ])
        
        if not success:
            return False, f'Failed to start {name}: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, f'{name} started successfully'
    
    def stop_process(self, name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Stop a specific process by name
        
        Args:
            name: Process name
            force: Force immediate kill
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        command = ['delete' if force else 'stop', name]
        success, stdout, stderr = self._run_pm2_command(command, timeout=40)
        
        if not success:
            return False, f'Failed to stop {name}: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, f'{name} stopped successfully'
    
    def restart_process(self, name: str) -> Tuple[bool, str]:
        """
        Restart a specific process by name
        
        Args:
            name: Process name
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['restart', name], timeout=40)
        
        if not success:
            return False, f'Failed to restart {name}: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, f'{name} restarted successfully'
    
    def reload_process(self, name: str) -> Tuple[bool, str]:
        """
        Zero-downtime reload of a specific process
        
        Args:
            name: Process name
            
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['reload', name], timeout=40)
        
        if not success:
            return False, f'Failed to reload {name}: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, f'{name} reloaded successfully (zero-downtime)'
    
    def start_all(self) -> Tuple[bool, str]:
        """Start all processes in config file"""
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['start', str(self.config_file)])
        
        if not success:
            return False, f'Failed to start all: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, 'All processes started successfully'
    
    def stop_all(self) -> Tuple[bool, str]:
        """Stop all PM2 processes"""
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['stop', 'all'], timeout=60)
        
        if not success:
            return False, f'Failed to stop all: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, 'All processes stopped successfully'
    
    def restart_all(self) -> Tuple[bool, str]:
        """Restart all PM2 processes"""
        if not self.enabled:
            return False, 'PM2 is not enabled'
        
        success, stdout, stderr = self._run_pm2_command(['restart', 'all'], timeout=60)
        
        if not success:
            return False, f'Failed to restart all: {stderr}'
        
        self._run_pm2_command(['save', '--force'])
        return True, 'All processes restarted successfully'
    
    def get_logs(self, name: str, lines: int = 30, log_type: str = 'all') -> Dict[str, List[str]]:
        """
        Get logs for a specific process
        
        Args:
            name: Process name
            lines: Number of lines to retrieve
            log_type: 'out', 'err', or 'all'
            
        Returns:
            Dictionary with 'out' and 'err' log arrays
        """
        if not self.enabled:
            return {'out': [], 'err': []}
        
        try:
            # Get log file paths
            process = self.describe_process(name)
            if not process:
                log.warning(f"Process {name} not found when getting logs")
                return {'out': [], 'err': []}
            
            logs = {'out': [], 'err': []}
            
            # Read output logs
            if log_type in ['out', 'all']:
                log_file = process.get('log_file', '')
                log.debug(f"Reading output log from: {log_file}")
                if log_file and os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            all_lines = f.readlines()
                            # Get last N lines and strip newlines
                            logs['out'] = [line.rstrip('\n') for line in all_lines[-lines:]]
                            log.debug(f"Read {len(logs['out'])} lines from output log")
                    except Exception as e:
                        log.error(f"Error reading output log {log_file}: {e}")
                else:
                    log.warning(f"Output log file not found or empty: {log_file}")
            
            # Read error logs
            if log_type in ['err', 'all']:
                error_file = process.get('error_file', '')
                log.debug(f"Reading error log from: {error_file}")
                if error_file and os.path.exists(error_file):
                    try:
                        with open(error_file, 'r', encoding='utf-8', errors='ignore') as f:
                            all_lines = f.readlines()
                            # Get last N lines and strip newlines
                            logs['err'] = [line.rstrip('\n') for line in all_lines[-lines:]]
                            log.debug(f"Read {len(logs['err'])} lines from error log")
                    except Exception as e:
                        log.error(f"Error reading error log {error_file}: {e}")
                else:
                    log.warning(f"Error log file not found or empty: {error_file}")
            
            log.info(f"Retrieved logs for {name}: {len(logs['out'])} out, {len(logs['err'])} err")
            return logs
            
        except Exception as e:
            log.error(f"Error getting logs for {name}: {e}")
            return {'out': [], 'err': []}


# Singleton instance
_pm2_adapter = None

def get_pm2_adapter() -> PM2Adapter:
    """Get singleton PM2 adapter instance"""
    global _pm2_adapter
    if _pm2_adapter is None:
        _pm2_adapter = PM2Adapter()
    return _pm2_adapter


# Convenience functions
def is_pm2_enabled() -> bool:
    """Check if PM2 integration is enabled"""
    _ensure_pm2_initialized()
    return USE_PM2 and PM2_AVAILABLE


def should_use_pm2() -> bool:
    """Determine if PM2 should be used for bot management"""
    return is_pm2_enabled()
