#!/usr/bin/env python3
"""
System Data Cleanup - Removes bloat from macOS System Data

Major contributors to System Data:
1. Homebrew cache: 2.8 GB
2. Google cache: 1.8 GB
3. NPM cache: 1.6 GB
4. Node modules: 2.4 GB (across multiple frontends)
5. Python pip cache: 471 MB

This script safely cleans these without affecting functionality.

Created: January 15, 2026
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Colors for output
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
    """Get directory size in GB"""
    try:
        result = subprocess.run(['du', '-sh', str(path)], capture_output=True, text=True)
        size_str = result.stdout.split()[0] if result.returncode == 0 else "0"
        return size_str
    except:
        return "0"

def clean_homebrew_cache():
    """Clean Homebrew cache"""
    print_header("1. Homebrew Cache (2.8 GB)")
    
    cache_path = Path.home() / 'Library' / 'Caches' / 'Homebrew'
    
    if cache_path.exists():
        size_before = get_size(cache_path)
        print_info(f"Size before: {size_before}")
        
        try:
            # Use brew cleanup command
            subprocess.run(['brew', 'cleanup', '-s'], check=False)
            
            # Remove old downloads
            downloads = cache_path / 'downloads'
            if downloads.exists():
                shutil.rmtree(downloads)
            
            size_after = get_size(cache_path)
            print_success(f"Cleaned Homebrew cache: {size_before} → {size_after}")
        except Exception as e:
            print_warning(f"Error cleaning Homebrew: {e}")
    else:
        print_info("Homebrew cache not found")

def clean_google_cache():
    """Clean Google/Chrome cache"""
    print_header("2. Google/Chrome Cache (1.8 GB)")
    
    google_cache = Path.home() / 'Library' / 'Caches' / 'Google'
    
    if google_cache.exists():
        size_before = get_size(google_cache)
        print_info(f"Size before: {size_before}")
        
        try:
            # Keep Chrome directory structure but clear caches
            for item in google_cache.rglob('*'):
                if item.is_file() and any(x in item.name.lower() for x in ['cache', 'temp', 'tmp']):
                    item.unlink()
            
            size_after = get_size(google_cache)
            print_success(f"Cleaned Google cache: {size_before} → {size_after}")
        except Exception as e:
            print_warning(f"Error cleaning Google cache: {e}")
    else:
        print_info("Google cache not found")

def clean_npm_cache():
    """Clean NPM cache"""
    print_header("3. NPM Cache (1.6 GB)")
    
    npm_cache = Path.home() / '.npm'
    
    if npm_cache.exists():
        size_before = get_size(npm_cache)
        print_info(f"Size before: {size_before}")
        
        try:
            # Use npm cache clean
            subprocess.run(['npm', 'cache', 'clean', '--force'], check=False)
            
            size_after = get_size(npm_cache)
            print_success(f"Cleaned NPM cache: {size_before} → {size_after}")
        except Exception as e:
            print_warning(f"Error cleaning NPM cache: {e}")
    else:
        print_info("NPM cache not found")

def clean_pip_cache():
    """Clean Python pip cache"""
    print_header("4. Python pip Cache (471 MB)")
    
    pip_cache = Path.home() / 'Library' / 'Caches' / 'pip'
    
    if pip_cache.exists():
        size_before = get_size(pip_cache)
        print_info(f"Size before: {size_before}")
        
        try:
            # Use pip cache purge
            subprocess.run(['pip3', 'cache', 'purge'], check=False)
            subprocess.run(['pip', 'cache', 'purge'], check=False)
            
            size_after = get_size(pip_cache)
            print_success(f"Cleaned pip cache: {size_before} → {size_after}")
        except Exception as e:
            print_warning(f"Error cleaning pip cache: {e}")
    else:
        print_info("pip cache not found")

def clean_python_cache():
    """Clean Python compiled bytecode"""
    print_header("5. Python __pycache__ Directories")
    
    project_root = Path.home() / 'Projects' / 'WorkingBot'
    
    if project_root.exists():
        try:
            pycache_dirs = list(project_root.rglob('__pycache__'))
            count = len(pycache_dirs)
            
            if count > 0:
                for pycache in pycache_dirs:
                    shutil.rmtree(pycache, ignore_errors=True)
                
                print_success(f"Removed {count} __pycache__ directories")
            else:
                print_info("No __pycache__ directories found")
        except Exception as e:
            print_warning(f"Error cleaning __pycache__: {e}")
    else:
        print_info("Project directory not found")

def optimize_node_modules():
    """Report on node_modules (don't delete, just inform)"""
    print_header("6. Node Modules Analysis (2.4 GB)")
    
    project_root = Path.home() / 'Projects' / 'WorkingBot'
    
    if project_root.exists():
        node_modules = [
            ('webui/frontend', '1.2 GB'),
            ('webui/frontend-v3', '597 MB'),
            ('backtest_ui/frontend', '560 MB'),
            ('webui/frontend-v2', '83 MB')
        ]
        
        print_info("Current node_modules:")
        total_size = 0
        for path, size in node_modules:
            full_path = project_root / path / 'node_modules'
            if full_path.exists():
                print_info(f"  • {path}: {size}")
        
        print_warning("These are required for development")
        print_info("To free space temporarily: cd <dir> && rm -rf node_modules")
        print_info("To restore: cd <dir> && npm install")
    else:
        print_info("Project directory not found")

def clean_other_caches():
    """Clean miscellaneous caches"""
    print_header("7. Other System Caches")
    
    caches_to_clean = [
        Path.home() / 'Library' / 'Caches' / 'com.apple.python',
        Path.home() / 'Library' / 'Caches' / 'node-gyp',
        Path.home() / 'Library' / 'Caches' / 'typescript',
    ]
    
    for cache in caches_to_clean:
        if cache.exists():
            size_before = get_size(cache)
            try:
                shutil.rmtree(cache)
                print_success(f"Cleaned {cache.name}: {size_before}")
            except Exception as e:
                print_warning(f"Error cleaning {cache.name}: {e}")

def show_summary():
    """Show summary of system data"""
    print_header("Summary")
    
    print_info("System Data components:")
    print_info(f"  User Caches:     {get_size(Path.home() / 'Library' / 'Caches')}")
    print_info(f"  NPM Cache:       {get_size(Path.home() / '.npm')}")
    print_info(f"  Containers:      {get_size(Path.home() / 'Library' / 'Containers')}")
    print_info(f"  System Logs:     {get_size('/var/log')}")
    
    print("")
    print_success("Cleanup complete!")
    print_info("Recommendation: Restart your Mac to fully reclaim space")

def main():
    print_header("🧹 System Data Cleanup Tool")
    print_info("This will clean caches and temporary files")
    print_info("All cleaned data can be regenerated automatically")
    print("")
    
    response = input("Continue? (y/N): ")
    if response.lower() != 'y':
        print_info("Cancelled")
        return
    
    try:
        clean_homebrew_cache()
        clean_google_cache()
        clean_npm_cache()
        clean_pip_cache()
        clean_python_cache()
        optimize_node_modules()
        clean_other_caches()
        show_summary()
    except KeyboardInterrupt:
        print("\n")
        print_warning("Interrupted by user")
    except Exception as e:
        print_warning(f"Error: {e}")

if __name__ == '__main__':
    main()
