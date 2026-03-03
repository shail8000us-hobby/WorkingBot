#!/usr/bin/env python3
"""
Test script to verify Error Resolution Panel integration
"""

import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def test_frontend_integration():
    """Test if frontend components are properly integrated"""
    print("🔍 Testing Frontend Integration...")
    
    # Check if ErrorResolutionPanel exists
    error_resolution_panel = BASE_DIR / 'webui' / 'frontend' / 'src' / 'components' / 'ErrorResolutionPanel.js'
    if error_resolution_panel.exists():
        print("✅ ErrorResolutionPanel.js exists")
    else:
        print("❌ ErrorResolutionPanel.js not found")
        return False
    
    # Check if ErrorIntelligencePanel imports it
    intelligence_panel = BASE_DIR / 'webui' / 'frontend' / 'src' / 'components' / 'ErrorIntelligencePanel.js'
    if intelligence_panel.exists():
        with open(intelligence_panel, 'r') as f:
            content = f.read()
            if 'ErrorResolutionPanel' in content:
                print("✅ ErrorIntelligencePanel imports ErrorResolutionPanel")
            else:
                print("❌ ErrorIntelligencePanel doesn't import ErrorResolutionPanel")
                return False
    else:
        print("❌ ErrorIntelligencePanel.js not found")
        return False
    
    # Check if App.js imports ErrorIntelligencePanel
    app_js = BASE_DIR / 'webui' / 'frontend' / 'src' / 'App.js'
    if app_js.exists():
        with open(app_js, 'r') as f:
            content = f.read()
            if 'ErrorIntelligencePanel' in content:
                print("✅ App.js imports ErrorIntelligencePanel")
            else:
                print("❌ App.js doesn't import ErrorIntelligencePanel")
                return False
    else:
        print("❌ App.js not found")
        return False
    
    return True

def test_backend_integration():
    """Test if backend routes are properly integrated"""
    print("\n🔍 Testing Backend Integration...")
    
    try:
        # Test error resolution routes
        from webui.backend.error_resolution import error_resolution_bp
        print("✅ Error resolution routes loaded")
        
        # Test error catalog updates
        from bot.observability.errors.catalog import ErrorCatalog
        catalog = ErrorCatalog()
        
        # Check for new error patterns
        patterns = catalog.get_all_codes()
        startup_patterns = [p for p in patterns if 'SAFETY_GATEKEEPER' in p or 'CONFIG_CHANGE' in p or 'LOG_FORMATTING' in p]
        
        if startup_patterns:
            print(f"✅ Found {len(startup_patterns)} startup error patterns: {startup_patterns}")
        else:
            print("❌ No startup error patterns found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Backend integration test failed: {e}")
        return False

def test_error_detection():
    """Test if error detection works for startup issues"""
    print("\n🔍 Testing Error Detection...")
    
    try:
        from bot.observability.errors import ErrorClassifier, ErrorSource
        from bot.observability.errors.catalog import ErrorCatalog
        
        catalog = ErrorCatalog()
        classifier = ErrorClassifier(catalog)
        
        # Test messages that should be detected
        test_messages = [
            "Safety gatekeeper blocked BUY order @ 114900.0",
            "🔄 CONFIGURATION CHANGES DETECTED (Hot Reload)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        detected_count = 0
        for message in test_messages:
            error = classifier.classify(message, ErrorSource.TRADING)
            if error and not error.code.startswith('UNKNOWN'):
                print(f"✅ Detected: {error.code} - {message[:50]}...")
                detected_count += 1
            else:
                print(f"❌ Not detected: {message[:50]}...")
        
        if detected_count > 0:
            print(f"✅ Successfully detected {detected_count}/{len(test_messages)} startup error patterns")
            return True
        else:
            print("❌ No startup error patterns detected")
            return False
            
    except Exception as e:
        print(f"❌ Error detection test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 Error Resolution Panel Integration Test")
    print("=" * 50)
    
    frontend_ok = test_frontend_integration()
    backend_ok = test_backend_integration()
    detection_ok = test_error_detection()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"Frontend Integration: {'✅ PASS' if frontend_ok else '❌ FAIL'}")
    print(f"Backend Integration: {'✅ PASS' if backend_ok else '❌ FAIL'}")
    print(f"Error Detection: {'✅ PASS' if detection_ok else '❌ FAIL'}")
    
    if frontend_ok and backend_ok and detection_ok:
        print("\n🎉 All tests passed! Error Resolution Panel is properly integrated.")
        print("\n📋 Next Steps:")
        print("1. Start your WebUI: cd webui/frontend && npm start")
        print("2. Start your bot to see startup errors")
        print("3. Look for the Error Intelligence panel at the bottom")
        print("4. Use the Error Resolution Panel to fix issues")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
