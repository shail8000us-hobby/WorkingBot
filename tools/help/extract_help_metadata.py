#!/usr/bin/env python3
"""
Help Metadata Extraction Tool
Scans the codebase for API routes, config keys, docstrings, and @help annotations
to auto-generate help_registry.json for the universal help system.

Truth sources (in priority order):
1. @help annotations in comments
2. Docstrings on route handlers and functions
3. Inline comments above functions
4. Config key definitions from grid_config.env
"""

import os
import re
import json
import ast
import inspect
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_FILE = BASE_DIR / "webui" / "backend" / "help" / "help_registry.json"
CONFIG_FILE = BASE_DIR / "grid_config.env"

# Secret patterns to filter
SECRET_PATTERNS = [
    r'.*_KEY$', r'.*_SECRET$', r'.*_PASSWORD$', r'.*_TOKEN$',
    r'API_KEY', r'SECRET', r'PASSWORD', r'TOKEN', r'CREDENTIALS'
]

class HelpExtractor:
    """Extract help metadata from codebase"""
    
    def __init__(self):
        self.registry = []
        self.config_keys = {}
        self.action_map = {}
        
    def is_secret(self, key: str) -> bool:
        """Check if a config key contains secrets"""
        for pattern in SECRET_PATTERNS:
            if re.match(pattern, key, re.IGNORECASE):
                return True
        return False
    
    def parse_config_file(self):
        """Extract config keys with their defaults and descriptions"""
        if not CONFIG_FILE.exists():
            print(f"⚠️  Config file not found: {CONFIG_FILE}")
            return
        
        current_section = "General"
        current_key_comments = []
        
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Track section headers
            if stripped.startswith('#'):
                section_match = re.match(r'^#\s*\d+\.?\d*\s+(.+)', stripped)
                if section_match:
                    current_section = section_match.group(1).strip()
                # Collect comment lines before a key
                elif i < len(lines) - 1 and '=' in lines[i + 1]:
                    current_key_comments.append(stripped.lstrip('#').strip())
                continue
            
            # Parse key=value
            if '=' in stripped and not stripped.startswith('#'):
                key, value = stripped.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if self.is_secret(key):
                    # Store metadata but hide value
                    self.config_keys[key] = {
                        "value": "[SECRET]",
                        "description": " ".join(current_key_comments) if current_key_comments else "Secret configuration",
                        "section": current_section,
                        "is_secret": True
                    }
                else:
                    self.config_keys[key] = {
                        "value": value,
                        "description": " ".join(current_key_comments) if current_key_comments else "",
                        "section": current_section,
                        "is_secret": False
                    }
                
                current_key_comments = []
        
        print(f"✅ Parsed {len(self.config_keys)} config keys")
    
    def extract_help_annotations(self, file_path: Path) -> Dict[str, Dict]:
        """Extract @help annotations from file comments"""
        annotations = {}
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Match @help annotations
        help_pattern = r'#\s*@help:(\w+)=(.+)'
        matches = re.finditer(help_pattern, content)
        
        current_action = None
        for match in matches:
            key, value = match.groups()
            
            if key == 'action_id':
                current_action = value.strip()
                if current_action not in annotations:
                    annotations[current_action] = {}
            elif current_action:
                annotations[current_action][key] = value.strip()
        
        return annotations
    
    def extract_python_routes(self, file_path: Path):
        """Extract Flask routes and their metadata from Python file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Extract @help annotations
        help_annotations = self.extract_help_annotations(file_path)
        
        # Parse Flask routes
        route_pattern = r"@app\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?\)"
        
        for i, line in enumerate(lines):
            route_match = re.search(route_pattern, line)
            if not route_match:
                continue
            
            path = route_match.group(1)
            methods_str = route_match.group(2)
            methods = [m.strip().strip("'\"") for m in methods_str.split(',')] if methods_str else ['GET']
            
            # Find function definition
            func_line_idx = i + 1
            while func_line_idx < len(lines) and not lines[func_line_idx].strip().startswith('def '):
                func_line_idx += 1
            
            if func_line_idx >= len(lines):
                continue
            
            func_match = re.match(r'\s*def\s+(\w+)\s*\(', lines[func_line_idx])
            if not func_match:
                continue
            
            func_name = func_match.group(1)
            
            # Extract docstring
            docstring = ""
            doc_start = func_line_idx + 1
            if doc_start < len(lines) and '"""' in lines[doc_start]:
                doc_lines = []
                for j in range(doc_start, min(doc_start + 20, len(lines))):
                    doc_lines.append(lines[j])
                    if doc_lines[0] != lines[j] and '"""' in lines[j]:
                        break
                docstring = '\n'.join(doc_lines).strip().strip('"""').strip()
            
            # Generate action_id
            action_id = path.replace('/api/', '').replace('/', '.').strip('.')
            if '<' in action_id:  # Handle path parameters
                action_id = re.sub(r'<[^>]+>', 'param', action_id)
            
            # Check for @help annotations
            help_data = help_annotations.get(action_id, {})
            
            # Infer config keys from function body
            func_body_start = func_line_idx
            func_body_end = min(func_line_idx + 100, len(lines))
            func_body = '\n'.join(lines[func_body_start:func_body_end])
            
            related_config = []
            for key in self.config_keys:
                if key in func_body and not self.is_secret(key):
                    related_config.append({
                        "key": key,
                        "value": self.config_keys[key]["value"],
                        "source": "grid_config.env"
                    })
            
            # Determine risks
            risks = []
            if 'live' in func_body.lower() or 'execute_orders' in func_body.lower():
                risks.append("May place live orders if TRADING_MODE=live")
            if 'delete' in func_name.lower() or 'kill' in func_name.lower():
                risks.append("Destructive operation - cannot be undone")
            if 'emergency' in path.lower():
                risks.append("Emergency operation - use with caution")
            
            # Build entry
            entry = {
                "action_id": help_data.get('action_id', action_id),
                "title": help_data.get('title', func_name.replace('_', ' ').title()),
                "summary": help_data.get('summary', docstring.split('\n')[0] if docstring else f"Handler for {path}"),
                "effects": help_data.get('impact', docstring).split('\n') if help_data.get('impact') or docstring else [
                    f"Calls {func_name}() in backend"
                ],
                "risks": help_data.get('risks', ', '.join(risks)).split(',') if help_data.get('risks') or risks else [],
                "related_config": related_config[:5],  # Limit to top 5
                "api": {
                    "method": methods[0] if methods else "GET",
                    "path": path
                },
                "code_refs": [
                    f"{file_path.relative_to(BASE_DIR)}: {path}",
                    f"{file_path.relative_to(BASE_DIR)}:{func_line_idx + 1} {func_name}()"
                ],
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
            
            self.registry.append(entry)
            self.action_map[action_id] = entry
    
    def extract_javascript_actions(self, file_path: Path):
        """Extract action IDs from JavaScript/React components"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Find axios/fetch API calls
        api_pattern = r'(axios\.|fetch\([\'"]/api/)([^\'"]+)'
        matches = re.finditer(api_pattern, content)
        
        for match in matches:
            path = match.group(2).split("'")[0].split('"')[0]
            action_id = path.replace('/api/', '').replace('/', '.').strip('.')
            
            # This creates a stub for frontend-only actions
            # They'll be flagged if no backend match exists
            if action_id not in self.action_map:
                self.registry.append({
                    "action_id": action_id,
                    "title": action_id.replace('.', ' ').title(),
                    "summary": f"Frontend action (no backend mapping found)",
                    "effects": ["Frontend-only action - backend implementation needed"],
                    "risks": [],
                    "related_config": [],
                    "api": {"method": "UNKNOWN", "path": f"/api/{path}"},
                    "code_refs": [f"{file_path.relative_to(BASE_DIR)}: API call"],
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "needs_backend": True
                })
                self.action_map[action_id] = True  # Mark as seen
    
    def scan_backend(self):
        """Scan backend Python files"""
        backend_dir = BASE_DIR / "webui" / "backend"
        python_files = list(backend_dir.glob("*.py"))
        
        for py_file in python_files:
            print(f"📄 Scanning {py_file.name}...")
            try:
                self.extract_python_routes(py_file)
            except Exception as e:
                print(f"⚠️  Error scanning {py_file.name}: {e}")
    
    def scan_frontend(self):
        """Scan frontend JavaScript/React files"""
        frontend_dir = BASE_DIR / "webui" / "frontend" / "src"
        if not frontend_dir.exists():
            print(f"⚠️  Frontend directory not found: {frontend_dir}")
            return
        
        js_files = list(frontend_dir.glob("**/*.js")) + list(frontend_dir.glob("**/*.jsx"))
        
        for js_file in js_files:
            print(f"📄 Scanning {js_file.name}...")
            try:
                self.extract_javascript_actions(js_file)
            except Exception as e:
                print(f"⚠️  Error scanning {js_file.name}: {e}")
    
    def generate_registry(self):
        """Generate and save the help registry"""
        print("\n" + "="*60)
        print("🔍 Starting Help Metadata Extraction")
        print("="*60 + "\n")
        
        # Step 1: Parse config
        print("📋 Parsing configuration file...")
        self.parse_config_file()
        
        # Step 2: Scan backend
        print("\n🐍 Scanning backend Python files...")
        self.scan_backend()
        
        # Step 3: Scan frontend
        print("\n⚛️  Scanning frontend JavaScript files...")
        self.scan_frontend()
        
        # Step 3.5: Add synthetic entries
        print("\n📦 Adding synthetic help entries...")
        synthetic_count = self.add_synthetic_entries()
        print(f"✅ Added {synthetic_count} synthetic entries")
        
        # Step 4: Save registry
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(self.registry, f, indent=2)
        
        print("\n" + "="*60)
        print(f"✅ Help Registry Generated Successfully!")
        print("="*60)
        print(f"📊 Total actions: {len(self.registry)}")
        print(f"📁 Output: {OUTPUT_FILE.relative_to(BASE_DIR)}")
        print(f"🔑 Config keys: {len(self.config_keys)}")
        print(f"🔒 Secrets filtered: {sum(1 for k in self.config_keys.values() if k.get('is_secret'))}")
        
        # Stats
        needs_backend = [e for e in self.registry if e.get('needs_backend')]
        if needs_backend:
            print(f"\n⚠️  {len(needs_backend)} frontend actions need backend mapping:")
            for action in needs_backend[:5]:
                print(f"   - {action['action_id']}")
        
        print("\n✨ Run 'npm run help:watch' to auto-update on file changes")
    
    def add_synthetic_entries(self):
        """Add synthetic help entries for frontend actions that share backend routes"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from synthetic_entries import SYNTHETIC_HELP_ENTRIES
            
            for entry in SYNTHETIC_HELP_ENTRIES:
                entry['source'] = 'synthetic'
                entry['last_updated'] = datetime.now().isoformat()
                self.registry.append(entry)
            
            return len(SYNTHETIC_HELP_ENTRIES)
        except Exception as e:
            print(f"⚠️  Could not import synthetic entries: {e}")
            return 0


def main():
    """Main entry point"""
    extractor = HelpExtractor()
    extractor.generate_registry()


if __name__ == "__main__":
    main()
