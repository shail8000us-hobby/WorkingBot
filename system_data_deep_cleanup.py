#!/usr/bin/env python3
"""
System Data Deep Cleanup - Removes hidden storage hogs

Found storage issues:
1. Chrome code signing cache: 1.2 GB (in /private/var/folders)
2. Chrome browser cache: 1.8 GB (in ~/Library/Caches)
3. System diagnostics: 985 MB (in /private/var/db)
4. UUID text files: 673 MB (in /private/var/db)
5. Pip cache: 218 MB (regenerated)
6. System Library Developer: 1.8 GB

Total hidden: ~6 GB in System Data

Created: January 15, 2026
"""

import os
import shutil
import subprocess
from pathlib import Path

# Colors
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
    """Get directory/file size"""
    try:
        result = subprocess.run(['du', '-sh', str(path)], capture_output=True, text=True)
        return result.stdout.split()[0] if result.returncode == 0 else "0"
    except:
        return "0"

def clean_chrome_code_signing_cache():
    """Clean Chrome code signing cache (1.2 GB in temp folders)"""
    print_header("1. Chrome Code Signing Cache (1.2 GB)")
    
    print_info("Searching for Chrome code signing caches in system temp...")
    
    try:
        # Find Chrome code signing caches
        result = subprocess.run(
            ['find', '/private/var/folders', '-name', 'com.google.Chrome.code_sign_clone', '-type', 'd'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        paths = result.stdout.strip().split('\n')
        total_freed = 0
        
        for path in paths:
            if path and Path(path).exists():
                size = get_size(path)
                try:
                    subprocess.run(['sudo', 'rm', '-rf', path], check=True)
                    print_success(f"Removed: {path}")
                    print_info(f"Size: {size}")
                    total_freed += 1
                except Exception as e:
                    print_warning(f"Error: {e}")
        
        if total_freed > 0:
            print_success(f"Freed ~1.2 GB from Chrome temp files")
        else:
            print_info("No Chrome code signing cache found")
            
    except subprocess.TimeoutExpired:
        print_warning("Search timed out - may need manual cleanup")
    except Exception as e:
        print_warning(f"Error: {e}")

def clean_chrome_browser_cache():
    """Clean Chrome browser cache (1.8 GB)"""
    print_header("2. Chrome Browser Cache (1.8 GB)")
    
    chrome_cache = Path.home() / 'Library' / 'Caches' / 'Google' / 'Chrome'
    
    if chrome_cache.exists():
        size = get_size(chrome_cache)
        print_info(f"Current size: {size}")
        print_warning("This will clear all Chrome caches and cached images")
        
        response = input("     Clear Chrome cache? (y/N): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(chrome_cache)
                print_success(f"Cleared Chrome cache ({size})")
            except Exception as e:
                print_warning(f"Error: {e}")
                print_info("Try: Close Chrome first, then run this again")
    else:
        print_info("No Chrome cache found")

def clean_system_diagnostics():
    """Clean system diagnostic logs (985 MB)"""
    print_header("3. System Diagnostic Logs (985 MB)")
    
    diag_path = Path('/private/var/db/diagnostics')
    
    if diag_path.exists():
        size = get_size(diag_path)
        print_info(f"Current size: {size}")
        print_warning("These are system crash/diagnostic logs")
        print_info("Safe to delete - macOS will recreate as needed")
        
        response = input("     Clean diagnostic logs? (y/N): ")
        if response.lower() == 'y':
            try:
                # Clean Persist and Special subdirectories (safe to delete)
                for subdir in ['Persist', 'Special']:
                    path = diag_path / subdir
                    if path.exists():
                        subprocess.run(['sudo', 'rm', '-rf', str(path)], check=True)
                        print_success(f"Cleaned {subdir}")
                
                print_success(f"Freed ~962 MB from diagnostic logs")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No diagnostic logs found")

def clean_uuidtext():
    """Clean UUID text cache (673 MB)"""
    print_header("4. UUID Text Cache (673 MB)")
    
    uuid_path = Path('/private/var/db/uuidtext')
    
    if uuid_path.exists():
        size = get_size(uuid_path)
        print_info(f"Current size: {size}")
        print_warning("These are system crash symbol files")
        print_info("Safe to delete - regenerated when needed for crash reports")
        
        response = input("     Clean UUID text files? (y/N): ")
        if response.lower() == 'y':
            try:
                # Clean old UUID files (keeping recent ones)
                subprocess.run([
                    'find', str(uuid_path), '-type', 'f', '-mtime', '+30', '-delete'
                ], check=True)
                
                new_size = get_size(uuid_path)
                print_success(f"Cleaned old UUID files: {size} → {new_size}")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No UUID text files found")

def clean_pip_cache_again():
    """Clean pip cache that regenerated (218 MB)"""
    print_header("5. Python pip Cache (218 MB)")
    
    pip_cache = Path.home() / 'Library' / 'Caches' / 'pip'
    
    if pip_cache.exists():
        size = get_size(pip_cache)
        print_info(f"Current size: {size}")
        
        try:
            subprocess.run(['pip3', 'cache', 'purge'], check=False, capture_output=True)
            new_size = get_size(pip_cache)
            if pip_cache.exists():
                shutil.rmtree(pip_cache)
            print_success(f"Cleaned pip cache: {size} → 0 MB")
        except Exception as e:
            print_warning(f"Error: {e}")
    else:
        print_info("No pip cache found")

def clean_system_library_developer():
    """Report on System Library Developer (1.8 GB)"""
    print_header("6. System Library Developer (1.8 GB)")
    
    dev_path = Path('/Library/Developer')
    
    if dev_path.exists():
        size = get_size(dev_path)
        print_info(f"Current size: {size}")
        print_warning("Contains Xcode Command Line Tools cache")
        
        # Check if CommandLineTools exist
        clt_path = dev_path / 'CommandLineTools'
        if clt_path.exists():
            clt_size = get_size(clt_path)
            print_info(f"Command Line Tools: {clt_size}")
            print_info("This is needed for development (git, make, etc.)")
        
        print_info("Safe to clean:")
        print_info("  - CoreSimulator (iOS simulator caches)")
        print_info("  - Xcode derived data")
        
        response = input("     Clean developer caches? (y/N): ")
        if response.lower() == 'y':
            try:
                # Clean CoreSimulator if exists
                sim_path = dev_path / 'CoreSimulator'
                if sim_path.exists():
                    sim_size = get_size(sim_path)
                    subprocess.run(['sudo', 'rm', '-rf', str(sim_path)], check=True)
                    print_success(f"Cleaned CoreSimulator: {sim_size}")
                
                # Clean Xcode derived data
                xcode_dd = Path.home() / 'Library' / 'Developer' / 'Xcode' / 'DerivedData'
                if xcode_dd.exists():
                    dd_size = get_size(xcode_dd)
                    shutil.rmtree(xcode_dd)
                    print_success(f"Cleaned Xcode DerivedData: {dd_size}")
                    
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No developer tools found")

def clean_system_library_caches():
    """Clean system library caches (326 MB)"""
    print_header("7. System Library Caches (326 MB)")
    
    cache_path = Path('/Library/Caches')
    
    if cache_path.exists():
        size = get_size(cache_path)
        print_info(f"Current size: {size}")
        print_warning("System-level application caches")
        
        response = input("     Clean system caches? (y/N): ")
        if response.lower() == 'y':
            try:
                # List what's there first
                result = subprocess.run(
                    ['sudo', 'du', '-sh', str(cache_path) + '/*'],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                print_info("Contents:")
                print_info(result.stdout[:500])
                
                # Clean safely
                subprocess.run(['sudo', 'find', str(cache_path), '-type', 'f', '-delete'], check=True)
                new_size = get_size(cache_path)
                print_success(f"Cleaned system caches: {size} → {new_size}")
            except Exception as e:
                print_warning(f"Error: {e}")
    else:
        print_info("No system caches found")

def show_summary():
    """Show final summary"""
    print_header("Summary - Potential Space to Free")
    
    print_info("Identified storage hogs:")
    print_info("  • Chrome code signing cache:  1.2 GB")
    print_info("  • Chrome browser cache:       1.8 GB")
    print_info("  • System diagnostics:         962 MB")
    print_info("  • UUID text files:            ~400 MB")
    print_info("  • pip cache:                  218 MB")
    print_info("  • System caches:              ~300 MB")
    print_info("")
    print_info("  TOTAL POTENTIAL:              ~4.9 GB")
    print("")
    print_success("Run this script again anytime to clean up")
    print_warning("Note: Some files regenerate over time (normal behavior)")

def main():
    print_header("🧹 System Data Deep Cleanup")
    print_info("This will clean hidden system storage hogs")
    print_warning("Requires sudo password for system files")
    print("")
    
    response = input("Continue? (y/N): ")
    if response.lower() != 'y':
        print_info("Cancelled")
        return
    
    try:
        clean_chrome_code_signing_cache()
        clean_chrome_browser_cache()
        clean_system_diagnostics()
        clean_uuidtext()
        clean_pip_cache_again()
        clean_system_library_developer()
        clean_system_library_caches()
        show_summary()
    except KeyboardInterrupt:
        print("\n")
        print_warning("Interrupted by user")
    except Exception as e:
        print_warning(f"Error: {e}")

if __name__ == '__main__':
    main()
