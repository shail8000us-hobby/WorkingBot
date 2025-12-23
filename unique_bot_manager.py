#!/usr/bin/env python3
"""
Unique Bot Manager - Ensures only ONE bot system runs at a time
This script prevents multiple bot instances and enforces uniqueness
"""

import os
import sys
import json
import time
import signal
import psutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime

class UniqueBotManager:
    def __init__(self):
        self.bot_dir = "/Users/shailendrasinghrajawat/Documents/WorkingBot"
        self.lock_file = os.path.join(self.bot_dir, ".bot_manager.lock")
        self.pid_file = os.path.join(self.bot_dir, ".bot_manager.pid")
        self.allowed_processes = [
            "python3 -m bot.run",
            "python3 -m bot.health",
            "python3 -m bot.guardian.guardian_bot"
        ]
        self.forbidden_patterns = [
            "app.py",
            "grid_loop",
            "ssr",
            "trading",
            "run.py"
        ]
        
    def acquire_lock(self):
        """Acquire exclusive lock for bot management"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    lock_data = json.load(f)
                    pid = lock_data.get('pid')
                    if pid and psutil.pid_exists(pid):
                        print(f"❌ Another bot manager is running (PID: {pid})")
                        return False
            
            # Create lock file
            lock_data = {
                'pid': os.getpid(),
                'timestamp': datetime.now().isoformat(),
                'manager': 'unique_bot_manager'
            }
            with open(self.lock_file, 'w') as f:
                json.dump(lock_data, f)
            
            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            print("✅ Bot manager lock acquired")
            return True
        except Exception as e:
            print(f"❌ Failed to acquire lock: {e}")
            return False
    
    def release_lock(self):
        """Release the bot management lock"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            print("✅ Bot manager lock released")
        except Exception as e:
            print(f"❌ Failed to release lock: {e}")
    
    def kill_all_bot_processes(self):
        """Kill ALL bot-related processes"""
        print("🔍 Scanning for bot processes...")
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Check for forbidden patterns
                for pattern in self.forbidden_patterns:
                    if pattern in cmdline.lower():
                        print(f"🔫 Killing forbidden process: {proc.info['pid']} - {cmdline}")
                        proc.kill()
                        killed_count += 1
                        break
                
                # Check for Python processes with bot-related names
                if 'python' in proc.info['name'].lower():
                    if any(keyword in cmdline.lower() for keyword in ['bot', 'trading', 'grid', 'run']):
                        print(f"🔫 Killing bot process: {proc.info['pid']} - {cmdline}")
                        proc.kill()
                        killed_count += 1
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        print(f"✅ Killed {killed_count} bot processes")
        return killed_count
    
    def stop_all_launchd_services(self):
        """Stop all launchd services related to bots"""
        print("🔍 Stopping launchd services...")
        stopped_count = 0
        
        try:
            # Get all launchd services
            result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
            services = result.stdout.split('\n')
            
            for service in services:
                if any(pattern in service.lower() for pattern in ['bot', 'grid', 'ssr', 'trading']):
                    service_name = service.split()[0]
                    if service_name and not service_name.startswith('-'):
                        try:
                            subprocess.run(['launchctl', 'unload', f'~/Library/LaunchAgents/{service_name}.plist'], 
                                         capture_output=True, check=False)
                            print(f"🛑 Stopped service: {service_name}")
                            stopped_count += 1
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ Error stopping services: {e}")
        
        print(f"✅ Stopped {stopped_count} launchd services")
        return stopped_count
    
    def start_bot(self, bot_type="trading"):
        """Start only the specified bot type"""
        if not self.acquire_lock():
            return False
        
        try:
            # First, kill everything
            self.kill_all_bot_processes()
            self.stop_all_launchd_services()
            time.sleep(2)
            
            # Start only the specified bot
            if bot_type == "trading":
                cmd = ["python3", "-m", "bot.run"]
                log_file = os.path.join(self.bot_dir, "logs", "trading_bot.log")
            elif bot_type == "health":
                cmd = ["python3", "-m", "bot.health"]
                log_file = os.path.join(self.bot_dir, "logs", "health_bot.log")
            elif bot_type == "guardian":
                cmd = ["python3", "-m", "bot.guardian.guardian_bot"]
                log_file = os.path.join(self.bot_dir, "logs", "guardian_bot.log")
            else:
                print(f"❌ Unknown bot type: {bot_type}")
                return False
            
            # Ensure log directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Start the bot
            with open(log_file, 'w') as f:
                process = subprocess.Popen(cmd, stdout=f, stderr=f, cwd=self.bot_dir)
            
            print(f"✅ Started {bot_type} bot (PID: {process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            return False
    
    def stop_all_bots(self):
        """Stop ALL bots and release lock"""
        print("🛑 Stopping all bots...")
        self.kill_all_bot_processes()
        self.stop_all_launchd_services()
        self.release_lock()
        print("✅ All bots stopped")
    
    def status(self):
        """Show status of all bot processes"""
        print("📊 Bot Status Report:")
        print("=" * 50)
        
        # Check for running processes
        bot_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if any(keyword in cmdline.lower() for keyword in ['bot', 'trading', 'grid', 'run']):
                    bot_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline
                    })
            except:
                continue
        
        if bot_processes:
            print("🔴 Running bot processes:")
            for proc in bot_processes:
                print(f"  PID {proc['pid']}: {proc['cmdline']}")
        else:
            print("✅ No bot processes running")
        
        # Check launchd services
        try:
            result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
            services = [line for line in result.stdout.split('\n') 
                       if any(pattern in line.lower() for pattern in ['bot', 'grid', 'ssr', 'trading'])]
            
            if services:
                print("\n🔴 Running launchd services:")
                for service in services:
                    print(f"  {service}")
            else:
                print("\n✅ No bot-related launchd services running")
        except:
            pass

def main():
    manager = UniqueBotManager()
    
    if len(sys.argv) < 2:
        print("Usage: python3 unique_bot_manager.py [start|stop|status|kill-all] [bot_type]")
        print("  start: Start a specific bot (trading|health|guardian)")
        print("  stop: Stop all bots")
        print("  status: Show bot status")
        print("  kill-all: Kill all bot processes")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        bot_type = sys.argv[2] if len(sys.argv) > 2 else "trading"
        manager.start_bot(bot_type)
    elif command == "stop":
        manager.stop_all_bots()
    elif command == "status":
        manager.status()
    elif command == "kill-all":
        manager.kill_all_bot_processes()
        manager.stop_all_launchd_services()
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
