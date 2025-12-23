#!/usr/bin/env python3
"""
Convert LaunchAgent Quick Reference to PDF
"""

import subprocess
import sys
from pathlib import Path

def markdown_to_html(md_file, html_file):
    """Convert markdown to styled HTML"""
    
    # Read markdown
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple markdown to HTML conversion
    html_content = content.replace('```bash', '<pre><code class="bash">')
    html_content = html_content.replace('```xml', '<pre><code class="xml">')
    html_content = html_content.replace('```', '</code></pre>')
    
    # Convert headers
    for i in range(6, 0, -1):
        html_content = html_content.replace('#' * i + ' ', f'<h{i}>')
        html_content = html_content.replace('\n' * 2, f'</h{i}>\n\n')
    
    # Convert bold
    import re
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    
    # Convert lists
    lines = html_content.split('\n')
    new_lines = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('- '):
            if not in_list:
                new_lines.append('<ul>')
                in_list = True
            new_lines.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    
    if in_list:
        new_lines.append('</ul>')
    
    html_content = '\n'.join(new_lines)
    
    # Create full HTML document
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GridBot LaunchAgent Quick Reference</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #fff;
        }}
        
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            font-size: 2.5em;
            margin-top: 0;
        }}
        
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 8px;
            margin-top: 30px;
            font-size: 1.8em;
        }}
        
        h3 {{
            color: #34495e;
            margin-top: 20px;
            font-size: 1.3em;
        }}
        
        h4 {{
            color: #555;
            margin-top: 15px;
        }}
        
        pre {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        code {{
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 0.9em;
            color: #e83e8c;
        }}
        
        pre code {{
            background: none;
            padding: 0;
            color: #333;
        }}
        
        ul {{
            margin: 10px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 5px 0;
        }}
        
        strong {{
            color: #2c3e50;
            font-weight: 600;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #e0e0e0;
            margin: 30px 0;
        }}
        
        .emoji {{
            font-size: 1.2em;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        
        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        
        .status {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
        }}
        
        .warning {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
        }}
        
        .success {{
            color: #28a745;
            font-weight: 600;
        }}
        
        .error {{
            color: #dc3545;
            font-weight: 600;
        }}
        
        @media print {{
            body {{
                padding: 0;
            }}
            
            pre {{
                page-break-inside: avoid;
            }}
            
            h1, h2, h3 {{
                page-break-after: avoid;
            }}
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
    
    # Write HTML file
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    return html_file

def html_to_pdf_macos(html_file, pdf_file):
    """Convert HTML to PDF using macOS tools"""
    try:
        # Try using wkhtmltopdf if available
        subprocess.run(['which', 'wkhtmltopdf'], check=True, capture_output=True)
        print("📄 Converting HTML to PDF using wkhtmltopdf...")
        subprocess.run([
            'wkhtmltopdf',
            '--enable-local-file-access',
            '--print-media-type',
            '--margin-top', '15mm',
            '--margin-bottom', '15mm',
            '--margin-left', '15mm',
            '--margin-right', '15mm',
            html_file,
            pdf_file
        ], check=True)
        return True
    except:
        pass
    
    try:
        # Try using cupsfilter (built-in macOS)
        print("📄 Converting HTML to PDF using cupsfilter...")
        subprocess.run([
            'cupsfilter',
            html_file,
            '-o', 'media=Letter'
        ], stdout=open(pdf_file, 'wb'), check=True)
        return True
    except:
        pass
    
    return False

def main():
    md_file = 'LAUNCHAGENT_QUICK_REFERENCE.md'
    html_file = 'LAUNCHAGENT_QUICK_REFERENCE.html'
    pdf_file = 'LAUNCHAGENT_QUICK_REFERENCE.pdf'
    
    print("🚀 Converting LaunchAgent Quick Reference to PDF...\n")
    
    # Convert markdown to HTML
    print("📝 Step 1: Converting Markdown to HTML...")
    html_path = markdown_to_html(md_file, html_file)
    print(f"✅ HTML created: {html_path}\n")
    
    # Convert HTML to PDF
    print("📄 Step 2: Converting HTML to PDF...")
    if html_to_pdf_macos(html_file, pdf_file):
        print(f"✅ PDF created: {pdf_file}\n")
        print("🎉 Conversion complete!")
        print(f"\n📂 Files created:")
        print(f"   - HTML: {html_path}")
        print(f"   - PDF: {pdf_file}")
    else:
        print("⚠️  PDF conversion failed. Opening HTML in browser instead...")
        print(f"📂 HTML file created: {html_path}")
        print("\n💡 You can:")
        print("   1. Open the HTML file in your browser")
        print("   2. Press Cmd+P (Print)")
        print("   3. Select 'Save as PDF'")
        print("\nOpening in browser now...")
        subprocess.run(['open', html_path])

if __name__ == '__main__':
    main()

