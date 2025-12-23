#!/usr/bin/env python3
"""
Bot Process Manager
Ensures only single instances of each bot component run at any time
"""

import os
import sys
import time
import signal
import psutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class BotProcessManager:
    def __init__(self, bot_dir: str = None):
        self.bot_dir = bot_dir or os.getcwd()
        self.pid_dir = os.path.join(self.bot_dir, '.pids')
        os.makedirs(self.pid_dir, exist_ok=True)
        
        # Bot configurations
        self.bot_configs = {
            'trading': {
                'name': 'Trading Bot',
                'command': 'python3 -m bot.run',
                'pid_file': os.path.join(self.pid_dir, 'trading.pid'),
                'log_file': os.path.join(self.bot_dir, 'bot.log'),
                'required': True
            },
            'health': {
                'name': 'Health Bot', 
                'command': 'python3 -m bot.health',
                'pid_file': os.path.join(self.pid_dir, 'health.pid'),
                'log_file': os.path.join(self.bot_dir, 'logs', 'health.log'),
                'required': False
            },
            'guardian': {
                'name': 'Guardian Bot',
                'command': 'python3 -m bot.guardian.guardian_bot',
                'pid_file': os.path.join(self.pid_dir, 'guardian.pid'),
                'log_file': os.path.join(self.bot_dir, 'logs', 'guardian.log'),
                'required': False
            },
            'reconciliation': {
                'name': 'Position Reconciliation',
                'command': 'python3 reconciliation_scheduler.py',
                'pid_file': os.path.join(self.pid_dir, 'reconciliation.pid'),
                'log_file': os.path.join(self.bot_dir, 'logs', 'reconciliation.log'),
                'required': True
            }
        }
    
    def get_running_bots(self) -> Dict[str, Dict]:
        """Get currently running bot processes"""
        running_bots = {}
        
        for bot_type, config in self.bot_configs.items():
            running_bots[bot_type] = {
                'name': config['name'],
                'running': False,
                'pid': None,
                'process': None
            }
            
            # Check if PID file exists and process is running
            if os.path.exists(config['pid_file']):
                try:
                    with open(config['pid_file'], 'r') as f:
                        pid = int(f.read().strip())
                    
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        if self._is_bot_process(process, config['command']):
                            running_bots[bot_type]['running'] = True
                            running_bots[bot_type]['pid'] = pid
                            running_bots[bot_type]['process'] = process
                except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Also check for any running bot processes not in PID files
            if not running_bots[bot_type]['running']:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if self._is_bot_process(proc, config['command']):
                            running_bots[bot_type]['running'] = True
                            running_bots[bot_type]['pid'] = proc.info['pid']
                            running_bots[bot_type]['process'] = proc
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
        
        return running_bots
    
    def _is_bot_process(self, process, command_pattern: str) -> bool:
        """Check if process matches bot command pattern"""
        try:
            cmdline = ' '.join(process.cmdline())
            return command_pattern in cmdline and 'python' in cmdline.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def stop_all_bots(self) -> Dict[str, bool]:
        """Stop all running bot processes"""
        results = {}
        running_bots = self.get_running_bots()
        
        print("🛑 Stopping all bot processes...")
        
        for bot_type, bot_info in running_bots.items():
            if bot_info['running']:
                print(f"  Stopping {bot_info['name']} (PID: {bot_info['pid']})...")
                try:
                    # Try graceful shutdown first
                    bot_info['process'].terminate()
                    bot_info['process'].wait(timeout=5)
                    results[bot_type] = True
                    print(f"  ✅ {bot_info['name']} stopped gracefully")
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        # Force kill if graceful shutdown failed
                        bot_info['process'].kill()
                        results[bot_type] = True
                        print(f"  ✅ {bot_info['name']} force stopped")
                    except psutil.NoSuchProcess:
                        results[bot_type] = True
                        print(f"  ✅ {bot_info['name']} already stopped")
                except Exception as e:
                    results[bot_type] = False
                    print(f"  ❌ Failed to stop {bot_info['name']}: {e}")
            else:
                results[bot_type] = True
                print(f"  ℹ️  {bot_info['name']} not running")
        
        # Clean up PID files
        for config in self.bot_configs.values():
            if os.path.exists(config['pid_file']):
                os.remove(config['pid_file'])
        
        return results
    
    def start_bot(self, bot_type: str) -> bool:
        """Start a specific bot"""
        if bot_type not in self.bot_configs:
            print(f"❌ Unknown bot type: {bot_type}")
            return False
        
        config = self.bot_configs[bot_type]
        running_bots = self.get_running_bots()
        
        if running_bots[bot_type]['running']:
            print(f"⚠️  {config['name']} is already running (PID: {running_bots[bot_type]['pid']})")
            return True
        
        try:
            print(f"🚀 Starting {config['name']}...")
            
            # Start the process
            process = subprocess.Popen(
                config['command'].split(),
                cwd=self.bot_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            # Save PID
            with open(config['pid_file'], 'w') as f:
                f.write(str(process.pid))
            
            print(f"✅ {config['name']} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start {config['name']}: {e}")
            return False
    
    def start_all_bots(self) -> Dict[str, bool]:
        """Start all required bots"""
        results = {}
        
        print("🚀 Starting all required bots...")
        
        for bot_type, config in self.bot_configs.items():
            if config['required']:
                results[bot_type] = self.start_bot(bot_type)
            else:
                print(f"⏭️  Skipping optional {config['name']}")
                results[bot_type] = True
        
        return results
    
    def restart_bot(self, bot_type: str) -> bool:
        """Restart a specific bot"""
        print(f"🔄 Restarting {bot_type} bot...")
        
        # Stop first
        stop_results = self.stop_all_bots()
        if not stop_results.get(bot_type, True):
            return False
        
        time.sleep(2)  # Wait for cleanup
        
        # Start
        return self.start_bot(bot_type)
    
    def get_status(self) -> Dict:
        """Get comprehensive status of all bots"""
        running_bots = self.get_running_bots()
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'bots': running_bots,
            'summary': {
                'total_bots': len(self.bot_configs),
                'running_bots': sum(1 for bot in running_bots.values() if bot['running']),
                'required_bots_running': sum(
                    1 for bot_type, bot_info in running_bots.items() 
                    if bot_info['running'] and self.bot_configs[bot_type]['required']
                )
            }
        }
        
        return status
    
    def enforce_single_instances(self) -> bool:
        """Ensure only single instances of each bot are running"""
        print("🔍 Enforcing single bot instances...")
        
        running_bots = self.get_running_bots()
        issues_found = False
        
        for bot_type, bot_info in running_bots.items():
            if bot_info['running']:
                # Check for duplicate processes
                duplicate_count = 0
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if (proc.info['pid'] != bot_info['pid'] and 
                            self._is_bot_process(proc, self.bot_configs[bot_type]['command'])):
                            duplicate_count += 1
                            print(f"⚠️  Found duplicate {bot_info['name']} process (PID: {proc.info['pid']})")
                            proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                
                if duplicate_count > 0:
                    issues_found = True
                    print(f"✅ Cleaned up {duplicate_count} duplicate {bot_info['name']} processes")
        
        if not issues_found:
            print("✅ No duplicate processes found")
        
        return not issues_found

def main():
    """CLI interface for bot process manager"""
    manager = BotProcessManager()
    
    if len(sys.argv) < 2:
        print("Usage: python3 bot_process_manager.py <command> [bot_type]")
        print("Commands: start, stop, restart, status, enforce")
        print("Bot types: trading, health, guardian, all")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    bot_type = sys.argv[2] if len(sys.argv) > 2 else 'all'
    
    if command == 'stop':
        if bot_type == 'all':
            manager.stop_all_bots()
        else:
            manager.stop_all_bots()  # Stop all first, then start specific one
    elif command == 'start':
        if bot_type == 'all':
            manager.start_all_bots()
        else:
            manager.start_bot(bot_type)
    elif command == 'restart':
        if bot_type == 'all':
            manager.stop_all_bots()
            time.sleep(2)
            manager.start_all_bots()
        else:
            manager.restart_bot(bot_type)
    elif command == 'status':
        status = manager.get_status()
        print(json.dumps(status, indent=2))
    elif command == 'enforce':
        manager.enforce_single_instances()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
