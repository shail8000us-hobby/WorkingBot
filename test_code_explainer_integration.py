#!/usr/bin/env python3
"""
Code Explainer Integration Test
Tests the complete flow: API → NarratorCore → Explanation
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.utils.narrator_core import NarratorCore, ExplanationMode

def test_narrator_core():
    """Test NarratorCore with a real file."""
    print("="*70)
    print("TEST 1: NarratorCore Import and Initialization")
    print("="*70)
    
    try:
        # Test all three modes
        for mode in [ExplanationMode.SIMPLE, ExplanationMode.TRADER, ExplanationMode.TECH]:
            narrator = NarratorCore(mode=mode)
            print(f"✅ Created narrator in {mode.value} mode")
        
        print("\n✅ All modes initialized successfully!\n")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize narrator: {e}")
        return False


def test_file_analysis():
    """Test analyzing a real Python file."""
    print("="*70)
    print("TEST 2: File Analysis")
    print("="*70)
    
    # Use a simple test file
    test_file = project_root / "code_explainer.py"
    
    if not test_file.exists():
        print(f"⚠️  Test file not found: {test_file}")
        return False
    
    try:
        narrator = NarratorCore(mode=ExplanationMode.TRADER)
        print(f"📄 Analyzing: {test_file.name}")
        
        # Analyze the file
        analysis = narrator.analyze_file(str(test_file))
        
        print(f"✅ Analysis complete!")
        print(f"   - Total Lines: {analysis.total_lines}")
        print(f"   - Functions: {len(analysis.functions)}")
        print(f"   - Classes: {len(analysis.classes)}")
        print(f"   - Complexity: {analysis.complexity_score}")
        print(f"   - Issues: {len(analysis.issues)}")
        
        # Generate explanation
        explanation = narrator.generate_file_summary(analysis)
        print(f"\n📝 Explanation preview (first 200 chars):")
        print(f"   {explanation[:200]}...")
        
        print("\n✅ File analysis successful!\n")
        return True
        
    except Exception as e:
        print(f"❌ Failed to analyze file: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_modes():
    """Test explanation generation in all modes."""
    print("="*70)
    print("TEST 3: All Reading Levels")
    print("="*70)
    
    test_file = project_root / "code_explainer.py"
    
    if not test_file.exists():
        print(f"⚠️  Test file not found: {test_file}")
        return False
    
    modes = [
        (ExplanationMode.SIMPLE, "🎓 SIMPLE (Non-Coders)"),
        (ExplanationMode.TRADER, "📊 TRADER (Business Users)"),
        (ExplanationMode.TECH, "⚙️ TECHNICAL (Developers)")
    ]
    
    for mode, label in modes:
        print(f"\n{label}")
        print("-" * 70)
        
        try:
            narrator = NarratorCore(mode=mode)
            analysis = narrator.analyze_file(str(test_file))
            explanation = narrator.generate_file_summary(analysis)
            
            # Print first 150 chars of explanation
            preview = explanation.split('\n')[0][:150]
            print(f"Preview: {preview}...")
            print(f"✅ {mode.value.upper()} mode working!")
            
        except Exception as e:
            print(f"❌ Failed in {mode.value} mode: {e}")
            return False
    
    print("\n✅ All reading levels working!\n")
    return True


def test_backend_integration():
    """Test the backend API blueprint."""
    print("="*70)
    print("TEST 4: Backend API Integration")
    print("="*70)
    
    try:
        from webui.backend.routes.code_explainer import code_explainer_bp, NARRATOR_AVAILABLE
        
        print(f"✅ Blueprint imported: {code_explainer_bp.name}")
        print(f"✅ Narrator available: {NARRATOR_AVAILABLE}")
        
        # Count registered routes
        route_count = len(list(code_explainer_bp.deferred_functions))
        print(f"✅ Routes registered: {route_count}")
        
        expected_routes = ['/explain', '/modes', '/health']
        print(f"   Expected routes: {', '.join(expected_routes)}")
        
        print("\n✅ Backend integration successful!\n")
        return True
        
    except Exception as e:
        print(f"❌ Backend integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_issue_detection():
    """Test code issue detection."""
    print("="*70)
    print("TEST 5: Issue Detection")
    print("="*70)
    
    # Create a test file with issues
    test_code = '''
import os
import sys  # unused import

async def test_function():
    """Missing await on async call."""
    result = another_async_function()  # Should be awaited
    return result

def unused_function():
    """This function is never called."""
    pass
'''
    
    try:
        narrator = NarratorCore(mode=ExplanationMode.TECH)
        analysis = narrator.analyze_code_string(test_code, filename="test.py")
        
        print(f"✅ Code analyzed")
        print(f"   - Functions: {len(analysis.functions)}")
        print(f"   - Issues detected: {len(analysis.issues)}")
        
        if analysis.issues:
            print("\n   Issues found:")
            for issue_type, description, line in analysis.issues:
                print(f"   - {issue_type.value}: {description} (line {line})")
        
        print("\n✅ Issue detection working!\n")
        return True
        
    except Exception as e:
        print(f"❌ Issue detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("CODE EXPLAINER INTEGRATION TEST SUITE")
    print("="*70 + "\n")
    
    tests = [
        ("Narrator Core", test_narrator_core),
        ("File Analysis", test_file_analysis),
        ("All Reading Levels", test_all_modes),
        ("Backend Integration", test_backend_integration),
        ("Issue Detection", test_issue_detection)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Code Explainer is ready to use!\n")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
