"""
Code Narrator Core Engine
Uses Python AST to understand and explain code in human language.

This is the heart of the dual-system: standalone analysis + runtime integration.
"""

import ast
import inspect
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class ExplanationMode(Enum):
    """Different explanation styles"""
    TECH = "tech"           # Technical, precise language
    TRADER = "trader"       # Story-style for traders
    SIMPLE = "simple"       # Child-level explanation


class CodeIssue(Enum):
    """Detected code quality issues"""
    DEAD_CODE = "dead_code"
    UNREACHABLE = "unreachable"
    MISSING_AWAIT = "missing_await"
    COMPLEX_FUNCTION = "complex_function"
    SHADOWED_VARIABLE = "shadowed_variable"
    DUPLICATED_LOGIC = "duplicated_logic"
    SPAGHETTI = "spaghetti"


@dataclass
class FunctionInfo:
    """Information about a function"""
    name: str
    args: List[str]
    returns: Optional[str]
    is_async: bool
    docstring: Optional[str]
    complexity: int
    line_start: int
    line_end: int


@dataclass
class ClassInfo:
    """Information about a class"""
    name: str
    bases: List[str]
    methods: List[FunctionInfo]
    docstring: Optional[str]
    line_start: int
    line_end: int


@dataclass
class CodeAnalysis:
    """Complete analysis of a code file"""
    file_path: str
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    issues: List[Tuple[CodeIssue, str, int]]  # (issue_type, description, line_number)
    total_lines: int
    complexity_score: int


class NarratorCore:
    """
    Core code analysis and narration engine.
    
    Uses AST to deeply understand Python code structure and
    converts it into human-readable explanations.
    
    Thread-safe, no state, pure functions.
    """
    
    def __init__(self, mode: ExplanationMode = ExplanationMode.TRADER):
        self.mode = mode
    
    def analyze_file(self, file_path: str) -> CodeAnalysis:
        """
        Analyze a Python file and extract structure.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            CodeAnalysis object with all detected elements
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=file_path)
        
        functions = []
        classes = []
        imports = []
        issues = []
        
        # Walk the AST tree
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_info = self._analyze_function(node)
                functions.append(func_info)
                
                # Check for issues
                if func_info.complexity > 15:
                    issues.append((
                        CodeIssue.COMPLEX_FUNCTION,
                        f"Function '{func_info.name}' is too complex (complexity: {func_info.complexity})",
                        func_info.line_start
                    ))
                
                # Check for missing await
                if func_info.is_async:
                    missing_await = self._check_missing_await(node)
                    if missing_await:
                        issues.append((
                            CodeIssue.MISSING_AWAIT,
                            f"Async function '{func_info.name}' may be missing await on: {missing_await}",
                            func_info.line_start
                        ))
            
            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node)
                classes.append(class_info)
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(self._extract_imports(node))
        
        # Calculate overall complexity
        total_complexity = sum(f.complexity for f in functions)
        
        # Count lines
        total_lines = len(source.split('\n'))
        
        return CodeAnalysis(
            file_path=file_path,
            functions=functions,
            classes=classes,
            imports=imports,
            issues=issues,
            total_lines=total_lines,
            complexity_score=total_complexity
        )
    
    def _analyze_function(self, node: ast.FunctionDef) -> FunctionInfo:
        """Extract function information"""
        args = [arg.arg for arg in node.args.args]
        
        # Extract return type hint if available
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Calculate cyclomatic complexity
        complexity = self._calculate_complexity(node)
        
        return FunctionInfo(
            name=node.name,
            args=args,
            returns=returns,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=docstring,
            complexity=complexity,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno
        )
    
    def _analyze_class(self, node: ast.ClassDef) -> ClassInfo:
        """Extract class information"""
        bases = [ast.unparse(base) if hasattr(ast, 'unparse') else str(base) 
                 for base in node.bases]
        
        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._analyze_function(item))
        
        docstring = ast.get_docstring(node)
        
        return ClassInfo(
            name=node.name,
            bases=bases,
            methods=methods,
            docstring=docstring,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno
        )
    
    def _extract_imports(self, node) -> List[str]:
        """Extract import statements"""
        imports = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """
        Calculate cyclomatic complexity.
        
        Complexity = 1 + number of decision points
        Decision points: if, for, while, except, with, and, or
        """
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or operators
                complexity += len(child.values) - 1
        
        return complexity
    
    def _check_missing_await(self, node: ast.AsyncFunctionDef) -> Optional[str]:
        """
        Check if async function is missing await on async calls.
        
        Returns name of first suspiciously un-awaited call, or None.
        """
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Check if it's a call to something that looks async
                if isinstance(child.func, ast.Name):
                    if child.func.id.startswith('async_') or child.func.id.endswith('_async'):
                        # Check if this call is awaited
                        parent = getattr(child, 'parent', None)
                        if not isinstance(parent, ast.Await):
                            return child.func.id
        return None
    
    def explain_function(self, func_info: FunctionInfo) -> str:
        """
        Generate human explanation of a function.
        
        Args:
            func_info: Function information
            
        Returns:
            Human-readable explanation in selected mode
        """
        if self.mode == ExplanationMode.SIMPLE:
            return self._explain_function_simple(func_info)
        elif self.mode == ExplanationMode.TRADER:
            return self._explain_function_trader(func_info)
        else:
            return self._explain_function_tech(func_info)
    
    def _explain_function_simple(self, func: FunctionInfo) -> str:
        """Child-level explanation"""
        async_part = "waits for things to happen" if func.is_async else "does its job"
        
        if not func.args:
            explanation = f"The '{func.name}' box {async_part}. It doesn't need any information to start."
        else:
            explanation = f"The '{func.name}' box {async_part}. You give it {', '.join(func.args)} and it figures out what to do."
        
        if func.complexity > 10:
            explanation += " (It has many steps inside!)"
        
        return explanation
    
    def _explain_function_trader(self, func: FunctionInfo) -> str:
        """Trader/storytelling explanation"""
        if func.is_async:
            async_intro = "This is an async operation — it waits for things without blocking."
        else:
            async_intro = "This runs immediately and returns."
        
        # Guess purpose from name
        purpose = self._guess_function_purpose(func.name)
        
        explanation = f"**{func.name}()** — {async_intro}\n\n"
        explanation += f"{purpose}\n\n"
        
        if func.args:
            explanation += f"Takes: {', '.join(func.args)}\n"
        
        if func.complexity > 10:
            explanation += f"⚠️ Complex logic inside ({func.complexity} decision points) — watch this carefully.\n"
        
        if func.docstring:
            explanation += f"\nDoc says: \"{func.docstring.split('.')[0]}.\""
        
        return explanation
    
    def _explain_function_tech(self, func: FunctionInfo) -> str:
        """Technical explanation"""
        async_marker = "async " if func.is_async else ""
        args_str = ', '.join(func.args) if func.args else "no parameters"
        returns_str = f" -> {func.returns}" if func.returns else ""
        
        explanation = f"{async_marker}def {func.name}({args_str}){returns_str}:\n"
        explanation += f"  Complexity: {func.complexity}\n"
        explanation += f"  Lines: {func.line_start}-{func.line_end}\n"
        
        if func.docstring:
            explanation += f"  Purpose: {func.docstring.split('.')[0]}"
        
        return explanation
    
    def _guess_function_purpose(self, name: str) -> str:
        """Guess function purpose from naming patterns"""
        name_lower = name.lower()
        
        if 'process' in name_lower:
            return "This processes data — takes something raw, does work, spits out result."
        elif 'create' in name_lower or 'make' in name_lower:
            return "This creates something new — like building an order or saga."
        elif 'handle' in name_lower:
            return "This is an event handler — reacts when something happens."
        elif 'compute' in name_lower or 'calculate' in name_lower:
            return "This is the math brain — calculates numbers you need."
        elif 'check' in name_lower or 'validate' in name_lower:
            return "This is a safety check — makes sure things are correct."
        elif 'send' in name_lower or 'publish' in name_lower:
            return "This sends a message out — talks to other parts of the system."
        elif 'receive' in name_lower or 'on_' in name_lower:
            return "This receives incoming data — listener/reactor pattern."
        elif 'update' in name_lower:
            return "This updates state — changes something that was already there."
        elif 'get' in name_lower or 'fetch' in name_lower:
            return "This retrieves data — goes and gets something you need."
        elif 'set' in name_lower:
            return "This sets a value — stores or changes configuration."
        elif name_lower.startswith('is_') or name_lower.startswith('has_'):
            return "This is a yes/no question — returns True or False."
        else:
            return "This function does its job as part of the system."
    
    def explain_class(self, class_info: ClassInfo) -> str:
        """Generate human explanation of a class"""
        if self.mode == ExplanationMode.SIMPLE:
            return self._explain_class_simple(class_info)
        elif self.mode == ExplanationMode.TRADER:
            return self._explain_class_trader(class_info)
        else:
            return self._explain_class_tech(class_info)
    
    def _explain_class_simple(self, cls: ClassInfo) -> str:
        """Child-level explanation"""
        explanation = f"The '{cls.name}' is like a blueprint for making things.\n"
        explanation += f"It has {len(cls.methods)} special abilities (methods).\n"
        
        if cls.bases:
            explanation += f"It's built on top of: {', '.join(cls.bases)}"
        
        return explanation
    
    def _explain_class_trader(self, cls: ClassInfo) -> str:
        """Trader/storytelling explanation"""
        explanation = f"## {cls.name}\n\n"
        
        if cls.docstring:
            explanation += f"{cls.docstring}\n\n"
        
        if cls.bases:
            explanation += f"Inherits from: {', '.join(cls.bases)}\n\n"
        
        explanation += f"This class has {len(cls.methods)} methods:\n"
        for method in cls.methods[:5]:  # Show first 5
            explanation += f"  • {method.name}() - {self._guess_function_purpose(method.name)}\n"
        
        if len(cls.methods) > 5:
            explanation += f"  ... and {len(cls.methods) - 5} more.\n"
        
        return explanation
    
    def _explain_class_tech(self, cls: ClassInfo) -> str:
        """Technical explanation"""
        bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
        explanation = f"class {cls.name}{bases_str}:\n"
        explanation += f"  Methods: {len(cls.methods)}\n"
        explanation += f"  Lines: {cls.line_start}-{cls.line_end}\n"
        
        if cls.docstring:
            explanation += f"  Purpose: {cls.docstring.split('.')[0]}"
        
        return explanation
    
    def generate_file_summary(self, analysis: CodeAnalysis) -> str:
        """
        Generate a complete file summary.
        
        Args:
            analysis: Code analysis results
            
        Returns:
            Human-readable file summary
        """
        if self.mode == ExplanationMode.TRADER:
            return self._generate_summary_trader(analysis)
        elif self.mode == ExplanationMode.SIMPLE:
            return self._generate_summary_simple(analysis)
        else:
            return self._generate_summary_tech(analysis)
    
    def _generate_summary_trader(self, analysis: CodeAnalysis) -> str:
        """Trader-style file summary"""
        summary = f"# 📖 Code Story: {analysis.file_path}\n\n"
        
        summary += f"This file has **{len(analysis.functions)} functions** and **{len(analysis.classes)} classes**.\n"
        summary += f"Total complexity score: {analysis.complexity_score} ({self._complexity_rating(analysis.complexity_score)})\n\n"
        
        if analysis.classes:
            summary += "## 🏗️ Main Components (Classes)\n\n"
            for cls in analysis.classes:
                summary += self.explain_class(cls) + "\n\n"
        
        if analysis.functions:
            summary += "## ⚙️ Standalone Functions\n\n"
            for func in analysis.functions[:10]:  # First 10
                summary += f"### {func.name}()\n"
                summary += self.explain_function(func) + "\n\n"
            
            if len(analysis.functions) > 10:
                summary += f"... and {len(analysis.functions) - 10} more functions.\n\n"
        
        if analysis.issues:
            summary += "## ⚠️ Detected Issues\n\n"
            for issue_type, description, line_num in analysis.issues:
                summary += f"- **Line {line_num}**: {description}\n"
        
        return summary
    
    def _generate_summary_simple(self, analysis: CodeAnalysis) -> str:
        """Simple file summary"""
        summary = f"# About {analysis.file_path}\n\n"
        summary += f"This file has {len(analysis.functions)} functions (like little workers).\n"
        summary += f"It also has {len(analysis.classes)} classes (like blueprints).\n\n"
        
        if analysis.complexity_score > 100:
            summary += "⚠️ This file is pretty complex! Lots of decisions happening.\n\n"
        
        return summary
    
    def _generate_summary_tech(self, analysis: CodeAnalysis) -> str:
        """Technical file summary"""
        summary = f"# File Analysis: {analysis.file_path}\n\n"
        summary += f"Lines: {analysis.total_lines}\n"
        summary += f"Functions: {len(analysis.functions)}\n"
        summary += f"Classes: {len(analysis.classes)}\n"
        summary += f"Imports: {len(analysis.imports)}\n"
        summary += f"Complexity: {analysis.complexity_score}\n"
        summary += f"Issues: {len(analysis.issues)}\n\n"
        
        if analysis.issues:
            summary += "## Issues Detected\n\n"
            for issue_type, description, line_num in analysis.issues:
                summary += f"- Line {line_num}: [{issue_type.value}] {description}\n"
        
        return summary
    
    def _complexity_rating(self, score: int) -> str:
        """Rate complexity score"""
        if score < 50:
            return "Simple, easy to understand"
        elif score < 150:
            return "Moderate complexity"
        elif score < 300:
            return "Complex, needs attention"
        else:
            return "Very complex, refactor recommended"
    
    def explain_code_snippet(self, code: str, context: str = "") -> str:
        """
        Explain a small code snippet (for runtime narration).
        
        Args:
            code: Source code snippet
            context: Additional context about where this code is running
            
        Returns:
            Human explanation
        """
        try:
            tree = ast.parse(code)
            
            # Find the main element
            if tree.body:
                node = tree.body[0]
                
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_info = self._analyze_function(node)
                    return self.explain_function(func_info)
                elif isinstance(node, ast.ClassDef):
                    class_info = self._analyze_class(node)
                    return self.explain_class(class_info)
                else:
                    # Generic statement
                    if self.mode == ExplanationMode.TRADER:
                        return f"This code {context}: {ast.unparse(node) if hasattr(ast, 'unparse') else 'performs an operation'}"
                    else:
                        return ast.unparse(node) if hasattr(ast, 'unparse') else str(node)
        except:
            return f"Code snippet {context}"
