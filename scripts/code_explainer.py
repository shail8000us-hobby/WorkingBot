#!/usr/bin/env python3
"""
Code Explainer - Standalone CLI Tool
Reads Python files and explains them in human language.

Usage:
    python code_explainer.py <file.py> [--mode tech|trader|simple] [--output md|json|terminal]

Examples:
    python code_explainer.py async_gridbot.py --mode trader
    python code_explainer.py human_logger.py --mode simple --output md
    python code_explainer.py order_actor.py --mode tech --output json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Import core narrator
from bot.utils.narrator_core import NarratorCore, ExplanationMode, CodeAnalysis


class CodeExplainer:
    """
    Standalone CLI tool for code explanation.
    
    Takes any Python file and outputs human-readable explanations.
    """
    
    def __init__(self, mode: ExplanationMode = ExplanationMode.TRADER):
        self.narrator = NarratorCore(mode=mode)
        self.mode = mode
    
    def explain_file(self, file_path: str, output_format: str = "terminal") -> Optional[str]:
        """
        Analyze and explain a Python file.
        
        Args:
            file_path: Path to Python file
            output_format: 'terminal', 'md', or 'json'
            
        Returns:
            Explanation string if output_format != 'terminal'
        """
        # Check file exists
        if not Path(file_path).exists():
            print(f"❌ Error: File not found: {file_path}")
            return None
        
        # Analyze the file
        print(f"🔍 Analyzing {file_path}...")
        try:
            analysis = self.narrator.analyze_file(file_path)
        except Exception as e:
            print(f"❌ Error analyzing file: {e}")
            return None
        
        # Generate explanation
        explanation = self.narrator.generate_file_summary(analysis)
        
        # Output based on format
        if output_format == "terminal":
            self._output_terminal(explanation, analysis)
            return None
        elif output_format == "md":
            output_file = self._output_markdown(file_path, explanation, analysis)
            print(f"✅ Explanation saved to: {output_file}")
            return output_file
        elif output_format == "json":
            output_file = self._output_json(file_path, explanation, analysis)
            print(f"✅ Analysis saved to: {output_file}")
            return output_file
        else:
            print(f"❌ Unknown output format: {output_format}")
            return None
    
    def _output_terminal(self, explanation: str, analysis: CodeAnalysis):
        """Print explanation to terminal"""
        print("\n" + "="*70)
        print(explanation)
        print("="*70)
        
        # Summary footer
        print(f"\n📊 Quick Stats:")
        print(f"   Functions: {len(analysis.functions)}")
        print(f"   Classes: {len(analysis.classes)}")
        print(f"   Lines: {analysis.total_lines}")
        print(f"   Complexity: {analysis.complexity_score}")
        print(f"   Issues: {len(analysis.issues)}")
        print()
    
    def _output_markdown(self, file_path: str, explanation: str, analysis: CodeAnalysis) -> str:
        """Save explanation as markdown file"""
        output_path = Path(file_path).stem + "_explanation.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Code Explanation: {Path(file_path).name}\n\n")
            f.write(f"**Mode**: {self.mode.value}\n")
            f.write(f"**Generated**: {self._get_timestamp()}\n\n")
            f.write("---\n\n")
            f.write(explanation)
            f.write("\n\n---\n\n")
            f.write("## Statistics\n\n")
            f.write(f"- **Total Lines**: {analysis.total_lines}\n")
            f.write(f"- **Functions**: {len(analysis.functions)}\n")
            f.write(f"- **Classes**: {len(analysis.classes)}\n")
            f.write(f"- **Imports**: {len(analysis.imports)}\n")
            f.write(f"- **Complexity Score**: {analysis.complexity_score}\n")
            f.write(f"- **Issues Detected**: {len(analysis.issues)}\n")
        
        return output_path
    
    def _output_json(self, file_path: str, explanation: str, analysis: CodeAnalysis) -> str:
        """Save analysis as JSON file"""
        output_path = Path(file_path).stem + "_analysis.json"
        
        # Build JSON structure
        data = {
            "file": file_path,
            "mode": self.mode.value,
            "timestamp": self._get_timestamp(),
            "summary": explanation,
            "statistics": {
                "total_lines": analysis.total_lines,
                "functions_count": len(analysis.functions),
                "classes_count": len(analysis.classes),
                "imports_count": len(analysis.imports),
                "complexity_score": analysis.complexity_score,
                "issues_count": len(analysis.issues)
            },
            "functions": [
                {
                    "name": f.name,
                    "async": f.is_async,
                    "args": f.args,
                    "returns": f.returns,
                    "complexity": f.complexity,
                    "lines": f"{f.line_start}-{f.line_end}",
                    "docstring": f.docstring
                }
                for f in analysis.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "bases": c.bases,
                    "methods_count": len(c.methods),
                    "lines": f"{c.line_start}-{c.line_end}",
                    "docstring": c.docstring
                }
                for c in analysis.classes
            ],
            "issues": [
                {
                    "type": issue[0].value,
                    "description": issue[1],
                    "line": issue[2]
                }
                for issue in analysis.issues
            ],
            "imports": analysis.imports
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return output_path
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def explain_directory(self, dir_path: str, output_format: str = "terminal", recursive: bool = False):
        """
        Explain all Python files in a directory.
        
        Args:
            dir_path: Path to directory
            output_format: Output format
            recursive: Search recursively
        """
        path = Path(dir_path)
        
        if not path.exists() or not path.is_dir():
            print(f"❌ Error: Directory not found: {dir_path}")
            return
        
        # Find Python files
        pattern = "**/*.py" if recursive else "*.py"
        py_files = list(path.glob(pattern))
        
        if not py_files:
            print(f"❌ No Python files found in {dir_path}")
            return
        
        print(f"📂 Found {len(py_files)} Python files")
        print()
        
        for py_file in py_files:
            print(f"\n{'='*70}")
            print(f"📄 {py_file.name}")
            print('='*70)
            self.explain_file(str(py_file), output_format=output_format)
    
    def compare_complexity(self, file_paths: list):
        """
        Compare complexity of multiple files.
        
        Args:
            file_paths: List of Python files to compare
        """
        results = []
        
        for file_path in file_paths:
            if not Path(file_path).exists():
                print(f"⚠️  Skipping {file_path} (not found)")
                continue
            
            try:
                analysis = self.narrator.analyze_file(file_path)
                results.append((
                    Path(file_path).name,
                    analysis.complexity_score,
                    len(analysis.functions),
                    len(analysis.classes),
                    len(analysis.issues)
                ))
            except Exception as e:
                print(f"⚠️  Error analyzing {file_path}: {e}")
        
        if not results:
            print("❌ No files to compare")
            return
        
        # Sort by complexity
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Display comparison table
        print("\n" + "="*90)
        print(f"{'File':<40} {'Complexity':<12} {'Functions':<12} {'Classes':<10} {'Issues':<8}")
        print("="*90)
        
        for name, complexity, funcs, classes, issues in results:
            print(f"{name:<40} {complexity:<12} {funcs:<12} {classes:<10} {issues:<8}")
        
        print("="*90)
        print(f"\nMost complex: {results[0][0]} (score: {results[0][1]})")
        print(f"Simplest: {results[-1][0]} (score: {results[-1][1]})")
        print()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Code Explainer - Transform Python code into human language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Explain a single file in trader mode (default)
  python code_explainer.py async_gridbot.py
  
  # Explain in simple language for beginners
  python code_explainer.py human_logger.py --mode simple
  
  # Technical explanation with JSON output
  python code_explainer.py order_actor.py --mode tech --output json
  
  # Explain all files in a directory
  python code_explainer.py bot/actors --dir
  
  # Compare complexity of multiple files
  python code_explainer.py file1.py file2.py file3.py --compare
        """
    )
    
    parser.add_argument("files", nargs='+', help="Python file(s) or directory to explain")
    parser.add_argument("--mode", choices=['tech', 'trader', 'simple'], default='trader',
                       help="Explanation style (default: trader)")
    parser.add_argument("--output", choices=['terminal', 'md', 'json'], default='terminal',
                       help="Output format (default: terminal)")
    parser.add_argument("--dir", action='store_true',
                       help="Treat input as directory and explain all .py files")
    parser.add_argument("--recursive", action='store_true',
                       help="Search directories recursively")
    parser.add_argument("--compare", action='store_true',
                       help="Compare complexity of multiple files")
    
    args = parser.parse_args()
    
    # Map mode string to enum
    mode_map = {
        'tech': ExplanationMode.TECH,
        'trader': ExplanationMode.TRADER,
        'simple': ExplanationMode.SIMPLE
    }
    
    mode = mode_map[args.mode]
    explainer = CodeExplainer(mode=mode)
    
    # Handle different modes
    if args.compare:
        explainer.compare_complexity(args.files)
    elif args.dir:
        for dir_path in args.files:
            explainer.explain_directory(dir_path, output_format=args.output, recursive=args.recursive)
    else:
        for file_path in args.files:
            explainer.explain_file(file_path, output_format=args.output)


if __name__ == "__main__":
    main()
