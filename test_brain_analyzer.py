#!/usr/bin/env python3
"""
Test script for the Real-Time Bot Brain Analyzer

This script tests the brain analyzer components to ensure they work correctly.
"""

import sys
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_realtime_predictor():
    """Test the real-time predictor"""
    print("🧠 Testing Real-Time Bot Predictor...")
    
    try:
        from webui.backend.brain_analyzer.realtime_predictor import RealTimeBotPredictor
        
        predictor = RealTimeBotPredictor(project_root)
        result = predictor.get_comprehensive_prediction()
        
        print(f"✅ Predictor initialized successfully")
        print(f"📊 Prediction keys: {list(result.keys())}")
        
        if 'primary_prediction' in result:
            primary = result['primary_prediction']
            print(f"🎯 Primary prediction: {primary.get('action', 'Unknown')}")
            print(f"🎲 Confidence: {primary.get('confidence', 0):.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Predictor test failed: {e}")
        return False

def test_file_monitor():
    """Test the file monitor"""
    print("\n📁 Testing File Monitor...")
    
    try:
        from webui.backend.brain_analyzer.file_monitor import RealTimeFileMonitor
        
        monitor = RealTimeFileMonitor(project_root)
        changes = monitor.scan_for_changes()
        summary = monitor.get_monitoring_summary()
        
        print(f"✅ File monitor initialized successfully")
        print(f"📂 Files monitored: {summary.get('monitoring_state', {}).get('files_watched', 0)}")
        print(f"🔄 Changes detected: {len(changes)}")
        
        if changes:
            for change in changes[:3]:  # Show first 3 changes
                print(f"  📝 {change.file_path}: {change.change_type} ({change.impact_level})")
        
        return True
        
    except Exception as e:
        print(f"❌ File monitor test failed: {e}")
        return False

def test_state_reader():
    """Test the state reader"""
    print("\n📊 Testing State Reader...")
    
    try:
        from webui.backend.brain_analyzer.state_reader import BotStateReader
        
        reader = BotStateReader(project_root)
        state = reader.get_complete_state()
        
        print(f"✅ State reader initialized successfully")
        print(f"📈 State keys: {list(state.keys())}")
        
        if 'config' in state:
            config = state['config']
            print(f"⚙️  Grid step: {config.get('grid_step', 'Unknown')}")
            print(f"💰 Reference price: {config.get('reference_price', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ State reader test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Bot Brain Analyzer Tests\n")
    
    tests = [
        test_state_reader,
        test_realtime_predictor,
        test_file_monitor
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print(f"\n📋 Test Results:")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All tests passed! Brain analyzer is ready for real-time monitoring.")
        print("\n🌐 Access the brain analyzer at: http://localhost:3000")
        print("   Navigate to: Bot Brain Analyzer → Live Brain Monitor")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)