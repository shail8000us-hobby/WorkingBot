#!/usr/bin/env python3
"""
Generate custom .icns files for GridBot apps using SF Symbols
"""

import os
import subprocess
import tempfile

def create_icon(sf_symbol, color, output_path, label_text=""):
    """Create an .icns file from SF Symbol"""
    
    # Create temporary directory for icon generation
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = os.path.join(tmpdir, "icon.iconset")
        os.makedirs(iconset, exist_ok=True)
        
        # Generate different sizes for iconset
        sizes = [16, 32, 64, 128, 256, 512]
        
        for size in sizes:
            # Create PNG using SF Symbols with sips/iconutil
            png_1x = os.path.join(iconset, f"icon_{size}x{size}.png")
            png_2x = os.path.join(iconset, f"icon_{size}x{size}@2x.png")
            
            # Use Python to generate colorful icons with text overlay
            create_png_icon(sf_symbol, color, size, png_1x, label_text)
            create_png_icon(sf_symbol, color, size * 2, png_2x, label_text)
        
        # Convert iconset to icns
        subprocess.run([
            "iconutil", "-c", "icns", iconset, "-o", output_path
        ], check=True, capture_output=True)
        
        print(f"✅ Created {output_path}")

def create_png_icon(symbol, color, size, output_path, label=""):
    """Generate PNG icon using Python PIL or fallback to default"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create image with gradient background
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Color mappings
        colors = {
            "green": (52, 199, 89),
            "red": (255, 69, 58),
            "blue": (10, 132, 255),
            "purple": (191, 90, 242),
            "orange": (255, 159, 10)
        }
        
        rgb = colors.get(color, (100, 100, 100))
        
        # Draw circular gradient background
        for i in range(size // 2, 0, -1):
            alpha = int(200 * (i / (size // 2)))
            color_with_alpha = rgb + (alpha,)
            draw.ellipse([size//2 - i, size//2 - i, size//2 + i, size//2 + i], 
                        fill=color_with_alpha)
        
        # Draw emoji/symbol in center
        font_size = int(size * 0.5)
        try:
            # Try to use system font
            font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
        except:
            font = ImageFont.load_default()
        
        # Draw symbol
        text_bbox = draw.textbbox((0, 0), symbol, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        position = ((size - text_width) // 2, (size - text_height) // 2 - int(size * 0.05))
        draw.text(position, symbol, fill=(255, 255, 255, 255), font=font)
        
        # Save
        img.save(output_path, 'PNG')
        
    except ImportError:
        # Fallback: create simple colored circle
        create_simple_icon(color, size, output_path)

def create_simple_icon(color, size, output_path):
    """Fallback method without PIL"""
    # Use ImageMagick if available
    colors_hex = {
        "green": "#34C759",
        "red": "#FF453A",
        "blue": "#0A84FF",
        "purple": "#BF5AF2",
        "orange": "#FF9F0A"
    }
    
    hex_color = colors_hex.get(color, "#646464")
    
    # Create with ImageMagick
    try:
        subprocess.run([
            "magick", "-size", f"{size}x{size}",
            f"radial-gradient:{hex_color}-#00000000",
            output_path
        ], check=True, capture_output=True)
    except:
        # Final fallback: create empty transparent PNG
        subprocess.run([
            "sips", "-s", "format", "png",
            "--out", output_path,
            "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericDocumentIcon.icns"
        ], capture_output=True)

if __name__ == "__main__":
    base_path = "/Users/ssr/Projects/WorkingBot/apps"
    
    # App configurations: (symbol, color, path)
    apps = [
        ("⚡️", "orange", f"{base_path}/GridBot-Status.app/Contents/Resources/icon.icns"),
        ("🔴", "red", f"{base_path}/GridBot-Logs.app/Contents/Resources/icon.icns"),
        ("📊", "blue", f"{base_path}/PM2-Monitor.app/Contents/Resources/icon.icns"),
        ("📈", "green", f"{base_path}/Grid-Status.app/Contents/Resources/icon.icns"),
    ]
    
    print("🎨 Generating custom app icons...\n")
    
    for symbol, color, icon_path in apps:
        # Create Resources directory if needed
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)
        
        try:
            create_icon(symbol, color, icon_path, "")
        except Exception as e:
            print(f"⚠️  Error creating {icon_path}: {e}")
            # Copy default Terminal icon as fallback
            try:
                subprocess.run([
                    "cp",
                    "/System/Applications/Utilities/Terminal.app/Contents/Resources/Terminal.icns",
                    icon_path
                ], check=True)
                print(f"📋 Used default icon for {icon_path}")
            except:
                pass
    
    print("\n✅ Icon generation complete!")
    print("🔄 Updating icon cache...")
    
    # Update icon cache
    subprocess.run(["killall", "Dock"], capture_output=True)
    subprocess.run(["killall", "Finder"], capture_output=True)
    
    print("✨ Done! Your apps now have custom icons.")
