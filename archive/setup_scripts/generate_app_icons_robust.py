#!/usr/bin/env python3
"""
Create robust icons for GridBot apps using SF Symbols and system resources
"""

import os
import subprocess
import tempfile
from pathlib import Path

def create_robust_icon(symbol_name, color_hex, output_path, bg_color="#FFFFFF"):
    """Create a robust .icns file using sips and iconutil"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = os.path.join(tmpdir, "icon.iconset")
        os.makedirs(iconset, exist_ok=True)
        
        # Sizes for complete iconset
        sizes = [
            (16, "16x16"),
            (32, "16x16@2x"),
            (32, "32x32"),
            (64, "32x32@2x"),
            (128, "128x128"),
            (256, "128x128@2x"),
            (256, "256x256"),
            (512, "256x256@2x"),
            (512, "512x512"),
            (1024, "512x512@2x")
        ]
        
        # Try different methods
        success = False
        
        # Method 1: Use SF Symbols if available (macOS 11+)
        try:
            success = create_with_sf_symbols(symbol_name, color_hex, sizes, iconset)
        except Exception as e:
            print(f"SF Symbols method failed: {e}")
        
        # Method 2: Use system icons as base
        if not success:
            try:
                success = create_from_system_icons(symbol_name, color_hex, sizes, iconset)
            except Exception as e:
                print(f"System icons method failed: {e}")
        
        # Method 3: Create simple colored icons
        if not success:
            create_simple_colored_icons(color_hex, sizes, iconset)
        
        # Convert iconset to icns
        try:
            subprocess.run([
                "iconutil", "-c", "icns", iconset, "-o", output_path
            ], check=True, capture_output=True)
            print(f"✅ Created {os.path.basename(output_path)}")
            return True
        except Exception as e:
            print(f"❌ Failed to create {output_path}: {e}")
            return False

def create_with_sf_symbols(symbol_name, color_hex, sizes, iconset):
    """Create icons using SF Symbols (macOS 11+)"""
    
    # Map symbol names to SF Symbol names
    sf_symbols = {
        "bolt": "bolt.fill",
        "circle": "circle.fill",
        "chart": "chart.bar.fill",
        "arrow": "arrow.up.right",
        "terminal": "terminal.fill"
    }
    
    sf_name = sf_symbols.get(symbol_name, "app.fill")
    
    for size, filename in sizes:
        output = os.path.join(iconset, f"icon_{filename}.png")
        
        # Use sf symbols command if available
        cmd = [
            "sf", "symbols",
            "--export", output,
            "--name", sf_name,
            "--size", str(size),
            "--color", color_hex
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception("SF Symbols not available")
    
    return True

def create_from_system_icons(symbol_name, color_hex, sizes, iconset):
    """Create icons from existing system icons"""
    
    # Map to system icon paths
    system_icons = {
        "bolt": "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/BookmarkIcon.icns",
        "circle": "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/AlertStopIcon.icns",
        "chart": "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ToolbarInfo.icns",
        "arrow": "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ForwardArrowIcon.icns",
        "terminal": "/System/Applications/Utilities/Terminal.app/Contents/Resources/Terminal.icns"
    }
    
    source_icon = system_icons.get(symbol_name, system_icons["terminal"])
    
    if not os.path.exists(source_icon):
        raise Exception(f"System icon not found: {source_icon}")
    
    # Extract PNG from icns and resize
    for size, filename in sizes:
        output = os.path.join(iconset, f"icon_{filename}.png")
        
        # Extract and resize using sips
        subprocess.run([
            "sips",
            "-s", "format", "png",
            "-z", str(size), str(size),
            source_icon,
            "--out", output
        ], capture_output=True, check=True)
    
    return True

def create_simple_colored_icons(color_hex, sizes, iconset):
    """Fallback: Create simple colored square icons"""
    
    for size, filename in sizes:
        output = os.path.join(iconset, f"icon_{filename}.png")
        
        # Create colored square using sips
        # First create a temporary file
        temp_png = os.path.join(iconset, "temp.png")
        
        # Use Python to create a simple PNG
        try:
            from PIL import Image, ImageDraw
            
            img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Convert hex to RGB
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            
            # Draw rounded rectangle
            margin = size // 8
            draw.rounded_rectangle(
                [margin, margin, size-margin, size-margin],
                radius=size // 6,
                fill=(r, g, b, 255)
            )
            
            img.save(output, 'PNG')
            
        except ImportError:
            # Even simpler fallback without PIL
            # Just copy a system icon
            subprocess.run([
                "sips",
                "-s", "format", "png",
                "-z", str(size), str(size),
                "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns",
                "--out", output
            ], capture_output=True)

def main():
    """Create icons for all GridBot apps"""
    
    base_path = "/Users/ssr/Projects/WorkingBot/apps"
    
    print("🎨 Creating robust icons for GridBot apps...\n")
    
    # App configurations: (symbol, color, app_path)
    apps = [
        ("bolt", "#FF9F0A", f"{base_path}/GridBot-Status.app/Contents/Resources/icon.icns"),
        ("circle", "#FF453A", f"{base_path}/GridBot-Logs.app/Contents/Resources/icon.icns"),
        ("chart", "#0A84FF", f"{base_path}/PM2-Monitor.app/Contents/Resources/icon.icns"),
        ("arrow", "#34C759", f"{base_path}/Grid-Status.app/Contents/Resources/icon.icns"),
        ("terminal", "#AC8E68", f"{base_path}/GridBot-Launcher.app/Contents/Resources/icon.icns"),
    ]
    
    success_count = 0
    
    for symbol, color, icon_path in apps:
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)
        
        if create_robust_icon(symbol, color, icon_path):
            success_count += 1
    
    print(f"\n✅ Successfully created {success_count}/{len(apps)} icons")
    
    # Refresh icon cache
    print("\n🔄 Refreshing icon cache...")
    subprocess.run(["killall", "Dock"], capture_output=True)
    subprocess.run(["killall", "Finder"], capture_output=True)
    
    print("✨ Done! Check your Desktop for the new icons.")
    print("💡 If icons still don't show, try logging out and back in.")

if __name__ == "__main__":
    main()
