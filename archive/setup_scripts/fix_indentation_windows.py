#!/usr/bin/env python3
"""
Fix indentation in Windows testnet gridbot.py after mutex lock application
"""

import re

WINDOWS_GRIDBOT = "/Volumes/D_Drive/Projects/WorkingBot/bot/strategy/gridbot.py"

# Read the file
with open(WINDOWS_GRIDBOT, 'r') as f:
    lines = f.readlines()

# Find and fix the indentation issue in _on_fill_processed method
in_method = False
fixed_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Detect start of _on_fill_processed method
    if 'def _on_fill_processed(self, fill_data: Dict):' in line:
        in_method = True
        method_start = i
    
    # Fix the specific section with wrong indentation
    if in_method and 'with self.position_mgr.state_lock:' in line:
        # Found the mutex lock line, now fix the indented block
        fixed_lines.append(line)
        i += 1
        
        # The try block should be indented 12 spaces (3 levels)
        while i < len(lines):
            line = lines[i]
            
            # If we hit the except block at wrong indentation, fix it
            if line.strip().startswith('except Exception as e:'):
                # This should be indented to match the try block (12 spaces)
                if not line.startswith('            except'):
                    fixed_lines.append('            except Exception as e:\n')
                else:
                    fixed_lines.append(line)
                i += 1
                # Fix the lines inside except block (16 spaces)
                while i < len(lines) and (lines[i].startswith('            ') or lines[i].strip() == ''):
                    if 'log.error' in lines[i] or 'import traceback' in lines[i]:
                        # Ensure proper indentation (16 spaces for except block content)
                        stripped = lines[i].lstrip()
                        fixed_lines.append('                ' + stripped)
                    else:
                        fixed_lines.append(lines[i])
                    i += 1
                    if i < len(lines) and not lines[i].startswith('        '):
                        break
                in_method = False
                continue
            
            # Regular lines inside the with block - should be indented 16 spaces (4 levels) minimum
            if line.strip() and not line.strip().startswith('#'):
                # Count current indentation
                indent = len(line) - len(line.lstrip())
                
                # If line is at 8 or 12 spaces and should be inside the with block
                if indent in [8, 12] and not line.strip().startswith('def '):
                    # Re-indent to 16 spaces (inside with block, inside try)
                    stripped = line.lstrip()
                    fixed_lines.append('                ' + stripped)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
            
            i += 1
            if i < len(lines) and 'def ' in lines[i] and not lines[i].startswith('        '):
                in_method = False
                break
    else:
        fixed_lines.append(line)
        i += 1

# Write back
with open(WINDOWS_GRIDBOT, 'w') as f:
    f.writelines(fixed_lines)

print("✅ Fixed indentation in Windows gridbot.py")
