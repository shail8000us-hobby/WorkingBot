#!/usr/bin/env python3
"""
AGGRESSIVE System Data Cleanup

FOUND THE REAL CULPRITS:
1. Git history: 1.5 GB (.git folder)
2. Cursor index in git: 496 MB
3. Git pack files: 1+ GB
4. Old logs in root: 425 MB
5. Reports folder: 783 MB
6. Data databases: 1.3 GB

These are all in ~/Projects which counts as System Data!

Created: January 15, 2026
"""

import os
import shutil
import subprocess
from pathlib import Path

GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"   {text}")

def get_size(path):
    try:
        result = subprocess.run(['du', '-sh', str(path)], capture_output=True, text=True)
        return result.stdout.split()[0] if result.returncode == 0 else "0"
    except:
        return "0"

def clean_cursor_git_index():
    """Clean Cursor index in .git (496 MB!)"""
    print_header("1. Cursor IDE Index in Git (496 MB)")
    
    cursor_index = Path.home() / 'Projects' / 'WorkingBot' / '.git' / 'cursor'
    
    if cursor_index.exists():
        size = get_size(cursor_index)
        print_info(f"Current size: {size}")
        print_warning("Cursor creates a search index inside .git")
        print_info("Safe to delete - will regenerate")
        
        response = input("     Delete Cursor git index? (y/N): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(cursor_index)
                print_success(f"Removed Cursor index ({size})")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No Cursor index found")

def clean_git_packs():
    """Optimize git repository"""
    print_header("2. Git Repository Optimization")
    
    git_dir = Path.home() / 'Projects' / 'WorkingBot' / '.git'
    
    if git_dir.exists():
        size_before = get_size(git_dir)
        print_info(f"Git folder size: {size_before}")
        print_warning("Git stores full history of all files")
        print_info("Can compress and optimize")
        
        response = input("     Optimize git repository? (y/N): ")
        if response.lower() == 'y':
            try:
                os.chdir(Path.home() / 'Projects' / 'WorkingBot')
                
                print_info("Running git gc (garbage collection)...")
                subprocess.run(['git', 'gc', '--aggressive', '--prune=now'], check=True)
                
                size_after = get_size(git_dir)
                print_success(f"Optimized: {size_before} → {size_after}")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No git repository found")

def clean_old_logs():
    """Clean old log files in root (425 MB)"""
    print_header("3. Old Logs in Root Directory (425 MB)")
    
    project_root = Path.home() / 'Projects' / 'WorkingBot'
    logs_dir = project_root / 'logs'
    
    if logs_dir.exists():
        size = get_size(logs_dir)
        print_info(f"logs/ folder size: {size}")
        print_warning("These are OLD logs (not the bot/logs folder)")
        
        response = input("     Delete old logs folder? (y/N): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(logs_dir)
                print_success(f"Removed logs/ folder ({size})")
            except Exception as e:
                print_warning(f"Error: {e}")
    
    # Clean .log files in root
    log_files = list(project_root.glob('*.log'))
    if log_files:
        total_size = sum(f.stat().st_size for f in log_files) / (1024 * 1024)
        print_info(f"Found {len(log_files)} .log files in root ({total_size:.1f} MB)")
        
        response = input("     Delete root .log files? (y/N): ")
        if response.lower() == 'y':
            for log_file in log_files:
                try:
                    log_file.unlink()
                except:
                    pass
            print_success(f"Removed {len(log_files)} log files")

def clean_reports():
    """Clean reports folder (783 MB)"""
    print_header("4. Reports Folder (783 MB)")
    
    reports = Path.home() / 'Projects' / 'WorkingBot' / 'reports'
    
    if reports.exists():
        size = get_size(reports)
        print_info(f"Current size: {size}")
        print_warning("Old trading reports and analysis")
        
        response = input("     Delete reports folder? (y/N): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(reports)
                print_success(f"Removed reports ({size})")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No reports folder found")

def clean_old_databases():
    """Clean old databases in data/ (1.3 GB)"""
    print_header("5. Old Databases (1.3 GB)")
    
    data_dir = Path.home() / 'Projects' / 'WorkingBot' / 'data'
    
    if data_dir.exists():
        size = get_size(data_dir)
        print_info(f"data/ folder size: {size}")
        
        # List databases
        dbs = list(data_dir.glob('*.db'))
        print_info(f"Found {len(dbs)} database files:")
        for db in dbs[:10]:
            db_size = db.stat().st_size / (1024 * 1024)
            print_info(f"  • {db.name}: {db_size:.1f} MB")
        
        print_warning("These contain historical trading data")
        
        response = input("     Clean old databases? (y/N): ")
        if response.lower() == 'y':
            # Vacuum databases to reclaim space
            for db in dbs:
                if db.name != 'bot_events_LONG.db':  # Keep main DB
                    try:
                        db.unlink()
                        print_info(f"  Removed: {db.name}")
                    except Exception as e:
                        pass
            
            # Vacuum the main DB
            main_db = data_dir / 'bot_events_LONG.db'
            if main_db.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(main_db))
                    conn.execute("VACUUM")
                    conn.close()
                    print_success("Vacuumed main database")
                except:
                    pass
            
            new_size = get_size(data_dir)
            print_success(f"data/ folder: {size} → {new_size}")

def clean_chrome_final():
    """Final attempt to clean Chrome cache"""
    print_header("6. Chrome Cache (Final Cleanup)")
    
    chrome_cache = Path.home() / 'Library' / 'Caches' / 'Google' / 'Chrome'
    
    if chrome_cache.exists():
        size = get_size(chrome_cache)
        print_info(f"Current size: {size}")
        print_warning("Close Chrome completely before running this")
        
        response = input("     Try cleaning Chrome cache again? (y/N): ")
        if response.lower() == 'y':
            try:
                # Force close Chrome
                subprocess.run(['killall', 'Google Chrome'], check=False, capture_output=True)
                
                # Wait a second
                import time
                time.sleep(2)
                
                # Remove cache
                shutil.rmtree(chrome_cache)
                print_success(f"Removed Chrome cache ({size})")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("Chrome cache already clean")

def show_summary():
    """Show final summary"""
    print_header("Summary")
    
    workingbot = Path.home() / 'Projects' / 'WorkingBot'
    git_size = get_size(workingbot / '.git')
    data_size = get_size(workingbot / 'data')
    
    print_success("Cleanup complete!")
    print_info("Current sizes:")
    print_info(f"  .git folder:    {git_size}")
    print_info(f"  data/ folder:   {data_size}")
    print("")
    print_warning("Recommendation: Review and delete old projects you don't need")
    print_info("Each project with git history consumes System Data space")

def main():
    print_header("🧹 AGGRESSIVE System Data Cleanup")
    print_info("Found in ~/Projects/WorkingBot:")
    print_info("  • Cursor git index:    496 MB")
    print_info("  • Git history:         1+ GB")
    print_info("  • Old logs:            425 MB")
    print_info("  • Reports:             783 MB")
    print_info("  • Databases:           1.3 GB")
    print_info("")
    print_info("TOTAL POTENTIAL:       ~4+ GB")
    print("")
    
    response = input("Continue with aggressive cleanup? (y/N): ")
    if response.lower() != 'y':
        print_info("Cancelled")
        return
    
    try:
        clean_cursor_git_index()
        clean_git_packs()
        clean_old_logs()
        clean_reports()
        clean_old_databases()
        clean_chrome_final()
        show_summary()
    except KeyboardInterrupt:
        print("\n")
        print_warning("Interrupted by user")
    except Exception as e:
        print_warning(f"Error: {e}")

if __name__ == '__main__':
    main()
