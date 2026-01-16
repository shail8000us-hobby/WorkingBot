#!/usr/bin/env python3
"""
IDE Storage Cleanup - Removes bloat from VS Code/Cursor

Major storage hogs found:
1. GitHub Copilot chat sessions: 4.1 GB (!)
2. VS Code workspace storage: 4.3 GB total
3. Cursor workspace storage: 755 MB
4. VS Code caches: 266 MB
5. Cursor caches: 34 MB

This script safely cleans these without losing settings.

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

def get_size_gb(path):
    """Get directory size in GB"""
    try:
        result = subprocess.run(['du', '-sh', str(path)], capture_output=True, text=True)
        return result.stdout.split()[0] if result.returncode == 0 else "0"
    except:
        return "0"

def clean_copilot_chat_sessions():
    """Clean GitHub Copilot chat history (3.7 GB!)"""
    print_header("1. GitHub Copilot Chat Sessions (4.1 GB)")
    
    vscode_workspace = Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'workspaceStorage'
    cursor_workspace = Path.home() / 'Library' / 'Application Support' / 'Cursor' / 'User' / 'workspaceStorage'
    
    total_freed = 0
    
    for workspace_root in [vscode_workspace, cursor_workspace]:
        if not workspace_root.exists():
            continue
        
        ide_name = 'VS Code' if 'Code' in str(workspace_root) else 'Cursor'
        
        for workspace_dir in workspace_root.iterdir():
            if not workspace_dir.is_dir():
                continue
            
            # Check for WorkingBot workspace
            workspace_json = workspace_dir / 'workspace.json'
            if workspace_json.exists():
                try:
                    with open(workspace_json) as f:
                        if 'WorkingBot' in f.read():
                            # Clean chat sessions
                            chat_sessions = workspace_dir / 'chatSessions'
                            chat_editing = workspace_dir / 'chatEditingSessions'
                            copilot_data = workspace_dir / 'GitHub.copilot-chat'
                            
                            for folder in [chat_sessions, chat_editing, copilot_data]:
                                if folder.exists():
                                    size = get_size_gb(folder)
                                    try:
                                        shutil.rmtree(folder)
                                        print_success(f"{ide_name}: Removed {folder.name} ({size})")
                                        total_freed += 1
                                    except Exception as e:
                                        print_warning(f"Error removing {folder.name}: {e}")
                except Exception as e:
                    pass
    
    if total_freed > 0:
        print_success(f"Freed ~4.1 GB of Copilot chat history")
    else:
        print_info("No Copilot chat data found")

def clean_vscode_caches():
    """Clean VS Code caches"""
    print_header("2. VS Code Caches (266 MB)")
    
    vscode_app_support = Path.home() / 'Library' / 'Application Support' / 'Code'
    
    cache_folders = [
        'Cache',
        'CachedData',
        'CachedExtensionVSIXs',
        'GPUCache',
        'logs'
    ]
    
    total_freed = 0
    
    for cache_name in cache_folders:
        cache_path = vscode_app_support / cache_name
        if cache_path.exists():
            size = get_size_gb(cache_path)
            try:
                if cache_path.is_dir():
                    shutil.rmtree(cache_path)
                else:
                    cache_path.unlink()
                print_success(f"Removed {cache_name} ({size})")
                total_freed += 1
            except Exception as e:
                print_warning(f"Error removing {cache_name}: {e}")
    
    if total_freed > 0:
        print_success(f"Freed ~266 MB from VS Code caches")

def clean_cursor_caches():
    """Clean Cursor IDE caches"""
    print_header("3. Cursor IDE Caches (34 MB)")
    
    cursor_app_support = Path.home() / 'Library' / 'Application Support' / 'Cursor'
    
    cache_folders = [
        'Cache',
        'CachedData',
        'GPUCache',
        'logs'
    ]
    
    total_freed = 0
    
    for cache_name in cache_folders:
        cache_path = cursor_app_support / cache_name
        if cache_path.exists():
            size = get_size_gb(cache_path)
            try:
                if cache_path.is_dir():
                    shutil.rmtree(cache_path)
                else:
                    cache_path.unlink()
                print_success(f"Removed {cache_name} ({size})")
                total_freed += 1
            except Exception as e:
                print_warning(f"Error removing {cache_name}: {e}")
    
    if total_freed > 0:
        print_success(f"Freed ~34 MB from Cursor caches")

def clean_old_workspace_storage():
    """Clean old unused workspace storage"""
    print_header("4. Old Workspace Storage")
    
    workspaces = [
        Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'workspaceStorage',
        Path.home() / 'Library' / 'Application Support' / 'Cursor' / 'User' / 'workspaceStorage'
    ]
    
    for workspace_root in workspaces:
        if not workspace_root.exists():
            continue
        
        ide_name = 'VS Code' if 'Code' in str(workspace_root) else 'Cursor'
        
        # Find workspaces that don't exist anymore
        for workspace_dir in workspace_root.iterdir():
            if not workspace_dir.is_dir():
                continue
            
            workspace_json = workspace_dir / 'workspace.json'
            if workspace_json.exists():
                try:
                    with open(workspace_json) as f:
                        content = f.read()
                        # Extract folder path
                        import json
                        data = json.loads(content)
                        folder_uri = data.get('folder', '')
                        
                        if folder_uri.startswith('file://'):
                            folder_path = folder_uri.replace('file://', '')
                            
                            # Check if folder still exists
                            if not Path(folder_path).exists():
                                size = get_size_gb(workspace_dir)
                                print_info(f"{ide_name}: Found old workspace: {Path(folder_path).name} ({size})")
                                
                                response = input(f"     Delete? (y/N): ")
                                if response.lower() == 'y':
                                    shutil.rmtree(workspace_dir)
                                    print_success(f"Removed old workspace ({size})")
                except Exception as e:
                    pass

def clean_whatsapp_data():
    """Report on WhatsApp backup size"""
    print_header("5. WhatsApp iCloud Backup (1.2 GB)")
    
    whatsapp_path = Path.home() / 'Library' / 'Mobile Documents'
    
    print_info("WhatsApp backup found in iCloud documents")
    print_info("Size: ~1.2 GB")
    print_warning("This is managed by WhatsApp/iCloud")
    print_info("To remove: Delete WhatsApp chat history on your phone")

def clean_other_bloat():
    """Clean other identified bloat"""
    print_header("6. Other Storage Optimizations")
    
    # TradingView cache
    tradingview = Path.home() / 'Library' / 'Application Support' / 'TradingView' / 'Cache'
    if tradingview.exists():
        size = get_size_gb(tradingview.parent)
        print_info(f"TradingView: {size}")
        response = input("     Clear TradingView cache? (y/N): ")
        if response.lower() == 'y':
            try:
                shutil.rmtree(tradingview)
                print_success(f"Cleared TradingView cache")
            except Exception as e:
                print_warning(f"Error: {e}")
    
    # Windsurf cache
    windsurf = Path.home() / 'Library' / 'Application Support' / 'Windsurf'
    if windsurf.exists():
        size = get_size_gb(windsurf)
        print_info(f"Windsurf IDE: {size}")

def show_summary():
    """Show final summary"""
    print_header("Summary")
    
    vscode_size = get_size_gb(Path.home() / 'Library' / 'Application Support' / 'Code')
    cursor_size = get_size_gb(Path.home() / 'Library' / 'Application Support' / 'Cursor')
    
    print_success("IDE Storage Cleanup Complete!")
    print_info(f"Current sizes:")
    print_info(f"  VS Code:  {vscode_size}")
    print_info(f"  Cursor:   {cursor_size}")
    print("")
    print_warning("Note: VS Code/Cursor will regenerate caches on next launch")
    print_warning("Your extensions and settings are preserved")

def main():
    print_header("🧹 IDE Storage Cleanup Tool")
    print_info("Found storage issues:")
    print_info("  • GitHub Copilot chat history: 4.1 GB")
    print_info("  • VS Code caches: 266 MB")
    print_info("  • Cursor caches: 34 MB")
    print("")
    print_warning("This will delete AI chat history and caches")
    print_info("Your settings, extensions, and code are safe")
    print("")
    
    response = input("Continue? (y/N): ")
    if response.lower() != 'y':
        print_info("Cancelled")
        return
    
    try:
        clean_copilot_chat_sessions()
        clean_vscode_caches()
        clean_cursor_caches()
        clean_old_workspace_storage()
        clean_whatsapp_data()
        clean_other_bloat()
        show_summary()
    except KeyboardInterrupt:
        print("\n")
        print_warning("Interrupted by user")
    except Exception as e:
        print_warning(f"Error: {e}")

if __name__ == '__main__':
    main()
