"""
AST Decision Parser Module

Single Responsibility: Parse Python AST to extract decision points.

Analyzes source code to find:
- If/else conditions
- Decision functions
- Function calls
- Return paths

This is the "code understanding" layer - reads code structure.
"""

import ast
import logging
from typing import Dict, List, Any, Optional, Tuple

log = logging.getLogger(__name__)


class DecisionParser:
    """
    Parses Python AST to extract decision logic.
    
    Uses Python's ast module to understand code structure
    without executing it.
    """
    
    def __init__(self):
        """Initialize AST parser"""
        self.decision_nodes = []
        self.function_map = {}
    
    def parse_source_code(self, source_code: str, file_name: str = "unknown") -> Dict[str, Any]:
        """
        Parse source code to extract decision structure.
        
        Args:
            source_code: Python source code string
            file_name: Name of file being parsed
            
        Returns:
            Dict with parsed decision structure
        """
        try:
            # Parse AST
            tree = ast.parse(source_code)
            
            # Extract all functions
            functions = self._extract_functions(tree)
            
            # Extract decision points (if/else)
            decisions = self._extract_decision_points(tree)
            
            # Extract function calls (shows flow)
            calls = self._extract_function_calls(tree)
            
            return {
                'file': file_name,
                'functions': functions,
                'decisions': decisions,
                'function_calls': calls,
                'total_functions': len(functions),
                'total_decisions': len(decisions)
            }
            
        except SyntaxError as e:
            log.error(f"Syntax error parsing {file_name}: {e}")
            return {'error': str(e)}
        except Exception as e:
            log.error(f"Error parsing {file_name}: {e}")
            return {'error': str(e)}
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract all function definitions"""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'line_number': node.lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'has_decisions': self._has_decision_logic(node),
                    'is_async': isinstance(node, ast.AsyncFunctionDef)
                }
                functions.append(func_info)
        
        return functions
    
    def _extract_decision_points(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract all if/else decision points"""
        decisions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Extract condition
                condition_text = ast.unparse(node.test) if hasattr(ast, 'unparse') else "condition"
                
                decisions.append({
                    'type': 'if_statement',
                    'line': node.lineno,
                    'condition': condition_text[:100],  # Truncate long conditions
                    'has_else': len(node.orelse) > 0,
                    'has_elif': any(isinstance(n, ast.If) for n in node.orelse)
                })
        
        return decisions
    
    def _extract_function_calls(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function calls to understand flow"""
        calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                else:
                    continue
                
                # Track important decision functions
                if any(keyword in func_name.lower() for keyword in 
                      ['compute', 'calculate', 'check', 'verify', 'place', 'cancel', 'execute']):
                    calls.append({
                        'function': func_name,
                        'line': node.lineno,
                        'type': 'decision_call' if 'check' in func_name.lower() or 'verify' in func_name.lower() else 'action_call'
                    })
        
        return calls
    
    def _has_decision_logic(self, func_node: ast.FunctionDef) -> bool:
        """Check if function contains decision logic"""
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.Match, ast.While)):
                return True
        return False
    
    def find_key_decision_functions(self, parsed_data: Dict) -> List[str]:
        """
        Identify key decision-making functions.
        
        These are functions that:
        - Have decision logic (if/else)
        - Have "decision" keywords in name
        - Are called by other functions
        
        Returns list of function names to focus on.
        """
        key_functions = []
        
        for func in parsed_data.get('functions', []):
            # Check if it's a decision function
            if func['has_decisions']:
                key_functions.append(func['name'])
            
            # Check if name suggests decision logic
            decision_keywords = ['compute', 'calculate', 'check', 'verify', 'should', 'can', 'is']
            if any(keyword in func['name'].lower() for keyword in decision_keywords):
                if func['name'] not in key_functions:
                    key_functions.append(func['name'])
        
        return key_functions

