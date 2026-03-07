#!/usr/bin/env python3
"""
Create beautiful gradient icons with emojis for GridBot apps
"""

import os
import subprocess
import tempfile

def create_gradient_icon_with_emoji(emoji, gradient_start, gradient_end, output_path):
    """Create a beautiful gradient icon with emoji overlay"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = os.path.join(tmpdir, "icon.iconset")
        os.makedirs(iconset, exist_ok=True)
        
        # All required sizes for complete iconset
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
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            has_pil = True
        except ImportError:
            print("⚠️  PIL not found, installing...")
            subprocess.run(["pip3", "install", "Pillow"], capture_output=True)
            try:
                from PIL import Image, ImageDraw, ImageFont
                has_pil = True
            except:
                has_pil = False
        
        if has_pil:
            from PIL import Image, ImageDraw, ImageFont
            
            for size, filename in sizes:
                create_png_with_pil(emoji, gradient_start, gradient_end, size, 
                                   os.path.join(iconset, f"icon_{filename}.png"))
        else:
            # Fallback to system icons
            for size, filename in sizes:
                create_simple_png(size, os.path.join(iconset, f"icon_{filename}.png"))
        
        # Convert to icns
        try:
            subprocess.run([
                "iconutil", "-c", "icns", iconset, "-o", output_path
            ], check=True, capture_output=True)
            print(f"✅ Created {os.path.basename(os.path.dirname(os.path.dirname(output_path)))}")
            return True
        except Exception as e:
            print(f"❌ Failed: {e}")
            return False

def create_png_with_pil(emoji, color_start, color_end, size, output_path):
    """Create PNG with gradient background and emoji"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Create image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Parse colors
    r1, g1, b1 = int(color_start[1:3], 16), int(color_start[3:5], 16), int(color_start[5:7], 16)
    r2, g2, b2 = int(color_end[1:3], 16), int(color_end[3:5], 16), int(color_end[5:7], 16)
    
    # Draw radial gradient
    center = size // 2
    max_radius = int(size * 0.7)
    
    for radius in range(max_radius, 0, -1):
        # Interpolate color
        t = radius / max_radius
        r = int(r1 * t + r2 * (1 - t))
        g = int(g1 * t + g2 * (1 - t))
        b = int(b1 * t + b2 * (1 - t))
        alpha = int(255 * (radius / max_radius))
        
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=(r, g, b, alpha)
        )
    
    # Draw emoji
    font_size = int(size * 0.5)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/AppleColorEmoji.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Center emoji
    bbox = draw.textbbox((0, 0), emoji, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((size - text_width) // 2, (size - text_height) // 2 - int(size * 0.05))
    
    # Draw with shadow for depth
    shadow_offset = max(1, size // 64)
    draw.text((position[0] + shadow_offset, position[1] + shadow_offset), 
              emoji, fill=(0, 0, 0, 128), font=font)
    draw.text(position, emoji, fill=(255, 255, 255, 255), font=font)
    
    img.save(output_path, 'PNG')

def create_simple_png(size, output_path):
    """Fallback: extract from system icon"""
    subprocess.run([
        "sips",
        "-s", "format", "png",
        "-z", str(size), str(size),
        "/System/Applications/Utilities/Terminal.app/Contents/Resources/Terminal.icns",
        "--out", output_path
    ], capture_output=True)

def main():
    base_path = "/Users/ssr/Projects/WorkingBot/apps"
    
    print("🎨 Creating beautiful gradient icons with emojis...\n")
    
    # App configurations: (emoji, gradient_start, gradient_end, app_path)
    apps = [
        ("⚡", "#FFB800", "#FF6B00", f"{base_path}/GridBot-Status.app/Contents/Resources/icon.icns"),
        ("🔴", "#FF6B6B", "#C92A2A", f"{base_path}/GridBot-Logs.app/Contents/Resources/icon.icns"),
        ("📊", "#4DABF7", "#1971C2", f"{base_path}/PM2-Monitor.app/Contents/Resources/icon.icns"),
        ("📈", "#51CF66", "#2F9E44", f"{base_path}/Grid-Status.app/Contents/Resources/icon.icns"),
        ("⚙️", "#868E96", "#495057", f"{base_path}/GridBot-Launcher.app/Contents/Resources/icon.icns"),
    ]
    
    for emoji, start_color, end_color, icon_path in apps:
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)
        create_gradient_icon_with_emoji(emoji, start_color, end_color, icon_path)
    
    print("\n🔄 Refreshing macOS icon cache...")
    
    # Force rebuild icon cache
    subprocess.run(["sudo", "rm", "-rf", "/Library/Caches/com.apple.iconservices.store"], capture_output=True)
    subprocess.run(["killall", "Finder"], capture_output=True)
    subprocess.run(["killall", "Dock"], capture_output=True)
    
    print("✨ Done! Icons created with beautiful gradients and emojis.")
    print("\n💡 If icons still don't appear:")
    print("   1. Log out and log back in")
    print("   2. Or run: sudo find /private/var/folders/ -name com.apple.dock.iconcache -delete && killall Dock")

if __name__ == "__main__":
    main()
