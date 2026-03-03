#!/usr/bin/env python3
"""
Bot-to-WebUI Feature Coverage Audit

Compares bot capabilities vs WebUI exposed features to find gaps

Usage:
    python audit_bot_webui_coherence.py

Output:
    - List of bot features not exposed in WebUI
    - Recommended API routes to create
    - Coverage percentage

Date: November 8, 2025
"""

import os
import ast
import json
from pathlib import Path
from typing import List, Dict, Set

class BotWebUIAuditor:
    def __init__(self):
        self.bot_dir = Path("bot")
        self.webui_dir = Path("webui/backend")
        
    def extract_bot_public_methods(self) -> Dict[str, List[str]]:
        """Extract all public methods from bot modules"""
        bot_features = {}
        
        # Key bot files to analyze
        bot_files = [
            "strategy/gridbot.py",
            "strategy/modules/order_manager.py",
            "strategy/modules/position_manager.py",
            "monitoring/price_health_monitor.py",
            "monitoring/pre_order_logger.py",
            "monitoring/tp_verification.py",
            "monitoring/anomaly_detection.py",
            "monitoring/predictive_display.py"
        ]
        
        for file_path in bot_files:
            full_path = self.bot_dir / file_path
            if not full_path.exists():
                continue
                
            try:
                with open(full_path, 'r') as f:
                    tree = ast.parse(f.read())
                
                methods = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Only public methods (not starting with _)
                        if not node.name.startswith('_'):
                            methods.append(node.name)
                
                if methods:
                    bot_features[file_path] = methods
            except Exception as e:
                print(f"⚠️  Warning: Could not parse {file_path}: {e}")
        
        return bot_features
    
    def extract_webui_routes(self) -> List[Dict[str, str]]:
        """Extract all API routes from WebUI backend"""
        routes = []
        
        if not self.webui_dir.exists():
            return routes
        
        # Find all Python files in routes directory
        routes_dir = self.webui_dir / "routes"
        if routes_dir.exists():
            for py_file in routes_dir.glob("*.py"):
                try:
                    with open(py_file, 'r') as f:
                        content = f.read()
                    
                    # Find route decorators
                    for line in content.split('\n'):
                        if '@' in line and 'route(' in line:
                            # Extract route path
                            if "'" in line:
                                route_path = line.split("'")[1]
                            elif '"' in line:
                                route_path = line.split('"')[1]
                            else:
                                continue
                            
                            routes.append({
                                'path': route_path,
                                'file': py_file.name
                            })
                except Exception as e:
                    print(f"⚠️  Warning: Could not parse {py_file}: {e}")
        
        return routes
    
    def analyze_coverage(self) -> Dict:
        """Analyze bot-to-WebUI coverage"""
        
        print("=" * 80)
        print("🔍 BOT-TO-WEBUI FEATURE COVERAGE AUDIT")
        print("=" * 80)
        print("")
        
        # Get bot features
        print("📊 Analyzing bot features...")
        bot_features = self.extract_bot_public_methods()
        total_bot_methods = sum(len(methods) for methods in bot_features.values())
        print(f"   Found {total_bot_methods} public methods across {len(bot_features)} modules")
        
        # Get WebUI routes
        print("")
        print("🌐 Analyzing WebUI routes...")
        webui_routes = self.extract_webui_routes()
        print(f"   Found {len(webui_routes)} API routes")
        
        # Define expected mappings for critical features
        expected_mappings = {
            # Monitoring features (NEW - not exposed yet)
            'monitoring:price_health': {
                'feature': 'Price Health Monitor',
                'expected_route': '/api/monitoring/price-health',
                'methods': ['get_price_age', 'is_price_fresh', 'can_place_orders'],
                'priority': 'HIGH',
                'exposed': False
            },
            'monitoring:pre_order_logger': {
                'feature': 'Pre-Order Decision Logger',
                'expected_route': '/api/monitoring/pre-order-stats',
                'methods': ['get_statistics', 'log_buy_decision', 'log_sell_decision'],
                'priority': 'HIGH',
                'exposed': False
            },
            'monitoring:tp_verification': {
                'feature': 'TP Verification System',
                'expected_route': '/api/monitoring/tp-verification',
                'methods': ['verify_tp_placement', 'verify_all_positions'],
                'priority': 'HIGH',
                'exposed': False
            },
            'monitoring:anomaly_detection': {
                'feature': 'Anomaly Detection',
                'expected_route': '/api/monitoring/anomalies',
                'methods': ['run_all_checks', 'get_recent_anomalies'],
                'priority': 'CRITICAL',
                'exposed': False
            },
            'monitoring:predictive_display': {
                'feature': 'Predictive Decision Map',
                'expected_route': '/api/monitoring/predictive-map',
                'methods': ['display_decision_map', 'get_next_actions'],
                'priority': 'MEDIUM',
                'exposed': False
            },
            
            # Bot control features
            'bot:seeding': {
                'feature': 'Grid Seeding',
                'expected_route': '/api/bot/seed',
                'methods': ['seed_missed_grid_levels'],
                'priority': 'MEDIUM',
                'exposed': False
            },
            'bot:statistics': {
                'feature': 'Bot Statistics',
                'expected_route': '/api/bot/stats',
                'methods': ['get_statistics', 'get_performance_metrics'],
                'priority': 'LOW',
                'exposed': False
            }
        }
        
        # Check which features are exposed
        route_paths = [r['path'] for r in webui_routes]
        for key, mapping in expected_mappings.items():
            mapping['exposed'] = mapping['expected_route'] in route_paths
        
        return {
            'bot_features': bot_features,
            'webui_routes': webui_routes,
            'expected_mappings': expected_mappings,
            'total_bot_methods': total_bot_methods,
            'total_webui_routes': len(webui_routes)
        }
    
    def print_report(self, analysis: Dict):
        """Print formatted audit report"""
        
        expected = analysis['expected_mappings']
        
        print("")
        print("=" * 80)
        print("📋 MISSING WEBUI INTEGRATIONS")
        print("=" * 80)
        print("")
        
        missing_count = 0
        for key, mapping in expected.items():
            if not mapping['exposed']:
                missing_count += 1
                priority_color = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🟢'
                }.get(mapping['priority'], '⚪')
                
                print(f"{priority_color} {mapping['feature']}")
                print(f"   Priority: {mapping['priority']}")
                print(f"   Expected Route: {mapping['expected_route']}")
                print(f"   Bot Methods: {', '.join(mapping['methods'])}")
                print(f"   Status: ❌ NOT EXPOSED")
                print("")
        
        if missing_count == 0:
            print("✅ All critical features are exposed in WebUI!")
            print("")
        
        print("=" * 80)
        print("📊 COVERAGE SUMMARY")
        print("=" * 80)
        print("")
        
        exposed_count = sum(1 for m in expected.values() if m['exposed'])
        total_expected = len(expected)
        coverage_pct = (exposed_count / total_expected * 100) if total_expected > 0 else 0
        
        print(f"   Total Bot Methods: {analysis['total_bot_methods']}")
        print(f"   Total WebUI Routes: {analysis['total_webui_routes']}")
        print(f"   Expected Integrations: {total_expected}")
        print(f"   Exposed: {exposed_count}/{total_expected}")
        print(f"   Coverage: {coverage_pct:.1f}%")
        print("")
        
        # Priority breakdown
        priority_stats = {}
        for mapping in expected.values():
            priority = mapping['priority']
            if priority not in priority_stats:
                priority_stats[priority] = {'total': 0, 'exposed': 0}
            priority_stats[priority]['total'] += 1
            if mapping['exposed']:
                priority_stats[priority]['exposed'] += 1
        
        print("   By Priority:")
        for priority in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            if priority in priority_stats:
                stats = priority_stats[priority]
                print(f"     {priority}: {stats['exposed']}/{stats['total']} exposed")
        print("")
        
        print("=" * 80)
        print("🔧 RECOMMENDED ACTIONS")
        print("=" * 80)
        print("")
        
        if missing_count > 0:
            print(f"1. Create monitoring.py blueprint in webui/backend/routes/")
            print(f"2. Implement {missing_count} missing API routes:")
            print("")
            
            for key, mapping in expected.items():
                if not mapping['exposed']:
                    print(f"   @monitoring_bp.route('{mapping['expected_route']}', methods=['GET'])")
                    print(f"   def {mapping['expected_route'].split('/')[-1].replace('-', '_')}():")
                    print(f"       # Return {mapping['feature']} data")
                    print("")
            
            print(f"3. Wire bot monitoring instances to Flask app")
            print(f"4. Create frontend components to display monitoring data")
            print(f"5. Add monitoring tab to navigation menu")
        else:
            print("✅ No action needed - all features exposed!")
        
        print("")
        print("=" * 80)
        
        # Save detailed report
        report_file = "bot_webui_coherence_report.json"
        with open(report_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"📄 Detailed report saved to: {report_file}")
        print("=" * 80)
        print("")

def main():
    auditor = BotWebUIAuditor()
    analysis = auditor.analyze_coverage()
    auditor.print_report(analysis)
    
    # Return exit code based on missing integrations
    missing = sum(1 for m in analysis['expected_mappings'].values() if not m['exposed'])
    return 1 if missing > 0 else 0

if __name__ == '__main__':
    exit(main())
