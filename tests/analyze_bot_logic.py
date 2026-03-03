#!/usr/bin/env python3
"""
Bot Logic Flow Analyzer
Generates visual flow diagrams of bot decision-making logic
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Set

class LogicFlowAnalyzer(ast.NodeVisitor):
    """Analyze Python code to extract logic flow"""
    
    def __init__(self):
        self.functions = {}
        self.current_function = None
        self.call_graph = {}
        self.decision_points = {}
        
    def visit_FunctionDef(self, node):
        """Track function definitions"""
        self.current_function = node.name
        self.functions[node.name] = {
            'name': node.name,
            'args': [arg.arg for arg in node.args.args],
            'calls': [],
            'decisions': [],
            'loops': [],
            'line': node.lineno
        }
        self.generic_visit(node)
        self.current_function = None
        
    def visit_If(self, node):
        """Track decision points (if/elif/else)"""
        if self.current_function:
            condition = ast.unparse(node.test) if hasattr(ast, 'unparse') else 'condition'
            self.functions[self.current_function]['decisions'].append({
                'type': 'if',
                'condition': condition[:80],  # Truncate long conditions
                'line': node.lineno
            })
        self.generic_visit(node)
        
    def visit_While(self, node):
        """Track while loops"""
        if self.current_function:
            self.functions[self.current_function]['loops'].append({
                'type': 'while',
                'line': node.lineno
            })
        self.generic_visit(node)
        
    def visit_For(self, node):
        """Track for loops"""
        if self.current_function:
            self.functions[self.current_function]['loops'].append({
                'type': 'for',
                'line': node.lineno
            })
        self.generic_visit(node)
        
    def visit_Call(self, node):
        """Track function calls"""
        if self.current_function:
            if hasattr(node.func, 'attr'):
                call_name = node.func.attr
            elif hasattr(node.func, 'id'):
                call_name = node.func.id
            else:
                call_name = 'unknown'
                
            self.functions[self.current_function]['calls'].append(call_name)
        self.generic_visit(node)

def analyze_file(filepath: Path) -> Dict:
    """Analyze a Python file for logic flow"""
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())
    
    analyzer = LogicFlowAnalyzer()
    analyzer.visit(tree)
    
    return analyzer.functions

def generate_mermaid_diagram(functions: Dict, key_functions: List[str]) -> str:
    """Generate Mermaid flowchart syntax"""
    
    diagram = """flowchart TD
    Start([Bot Start]) --> Init[Initialize Components]
    """
    
    for func_name in key_functions:
        if func_name not in functions:
            continue
            
        func = functions[func_name]
        safe_name = func_name.replace('_', '')
        
        # Add function node
        diagram += f"\n    {safe_name}[{func_name}]\n"
        
        # Add decision nodes
        for i, decision in enumerate(func['decisions'][:3]):  # Limit to 3
            decision_node = f"{safe_name}Dec{i}"
            diagram += f"    {safe_name} --> {decision_node}{{{decision['condition'][:40]}}}\n"
            diagram += f"    {decision_node} -->|Yes| {safe_name}Yes{i}[Action]\n"
            diagram += f"    {decision_node} -->|No| {safe_name}No{i}[Skip]\n"
        
        # Add function calls
        for call in func['calls'][:5]:  # Limit to 5
            if call in functions:
                call_safe = call.replace('_', '')
                diagram += f"    {safe_name} --> {call_safe}\n"
    
    return diagram

def generate_html_visualization(bot_dir: Path) -> str:
    """Generate interactive HTML visualization"""
    
    # Analyze key bot files
    key_files = [
        'bot/strategy/gridbot.py',
        'bot/strategy/modules/reconciliation.py',
        'bot/strategy/modules/fill_detector.py',
        'bot/strategy/modules/order_manager.py',
    ]
    
    all_functions = {}
    for file_path in key_files:
        full_path = bot_dir / file_path
        if full_path.exists():
            functions = analyze_file(full_path)
            all_functions.update(functions)
    
    # Key logic functions to visualize
    key_functions = [
        '_on_fill_processed',
        'ensure_single_correct_pending_buy',
        '_handle_buy_fill',
        '_handle_tp_fill',
        'place_buy_order',
        'place_tp_order',
        'detect_missed_fills',
    ]
    
    # Generate Mermaid diagram
    mermaid_code = generate_mermaid_diagram(all_functions, key_functions)
    
    # Create detailed function info
    function_details = []
    for func_name, func_data in all_functions.items():
        if func_name in key_functions:
            function_details.append({
                'name': func_name,
                'decisions': len(func_data['decisions']),
                'calls': len(func_data['calls']),
                'loops': len(func_data['loops']),
                'complexity': len(func_data['decisions']) + len(func_data['loops'])
            })
    
    function_details.sort(key=lambda x: x['complexity'], reverse=True)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Bot Logic Flow Analysis</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }}
        h1 {{
            font-size: 36px;
            margin-bottom: 10px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
        }}
        .card h2 {{
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 10px;
        }}
        .function-item {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid;
        }}
        .function-item.high {{ border-left-color: #f44336; }}
        .function-item.medium {{ border-left-color: #ff9800; }}
        .function-item.low {{ border-left-color: #4caf50; }}
        .function-name {{
            font-family: 'Courier New', monospace;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .function-stats {{
            font-size: 12px;
            opacity: 0.8;
        }}
        .stat-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 4px 10px;
            border-radius: 12px;
            margin-right: 8px;
            font-size: 11px;
        }}
        .diagram-container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            overflow-x: auto;
        }}
        .mermaid {{
            text-align: center;
        }}
        .legend {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
            margin-top: 20px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 8px;
            vertical-align: middle;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Bot Logic Flow Analysis</h1>
            <p>Automated Code Structure & Decision Path Visualization</p>
        </div>

        <div class="grid">
            <div class="card">
                <h2>📊 Function Complexity</h2>
                {''.join([f'''
                <div class="function-item {'high' if f['complexity'] > 5 else 'medium' if f['complexity'] > 2 else 'low'}">
                    <div class="function-name">{f['name']}()</div>
                    <div class="function-stats">
                        <span class="stat-badge">🔀 {f['decisions']} decisions</span>
                        <span class="stat-badge">📞 {f['calls']} calls</span>
                        <span class="stat-badge">🔁 {f['loops']} loops</span>
                        <span class="stat-badge">⚡ Complexity: {f['complexity']}</span>
                    </div>
                </div>
                ''' for f in function_details[:10]])}
            </div>

            <div class="card">
                <h2>🎯 Key Metrics</h2>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #4caf50;">{len(all_functions)}</div>
                        <div style="opacity: 0.8; font-size: 14px;">Total Functions</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #ff9800;">{sum(len(f['decisions']) for f in all_functions.values())}</div>
                        <div style="opacity: 0.8; font-size: 14px;">Decision Points</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #2196f3;">{sum(len(f['calls']) for f in all_functions.values())}</div>
                        <div style="opacity: 0.8; font-size: 14px;">Function Calls</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 32px; font-weight: bold; color: #9c27b0;">{sum(len(f['loops']) for f in all_functions.values())}</div>
                        <div style="opacity: 0.8; font-size: 14px;">Loops</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="diagram-container">
            <h2 style="color: #333; margin-bottom: 20px;">Logic Flow Diagram</h2>
            <div class="mermaid">
{mermaid_code}
            </div>
        </div>

        <div class="legend">
            <h3 style="margin-bottom: 15px;">📖 Legend</h3>
            <div class="legend-item">
                <span class="legend-color" style="background: #f44336;"></span>
                High Complexity (>5 decisions)
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ff9800;"></span>
                Medium Complexity (3-5 decisions)
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #4caf50;"></span>
                Low Complexity (<3 decisions)
            </div>
        </div>
    </div>

    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</body>
</html>"""
    
    return html

def main():
    bot_dir = Path("/Users/ssr/Projects/WorkingBot")
    output_file = bot_dir / "analysis" / "logic_flow_analysis.html"
    
    print("🧠 Analyzing bot logic...")
    html = generate_html_visualization(bot_dir)
    
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(html)
    
    print(f"✅ Logic flow analysis created: {output_file}")
    print(f"🌐 Opening in browser...")
    
    import subprocess
    subprocess.run(['open', str(output_file)])

if __name__ == "__main__":
    main()
