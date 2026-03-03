#!/usr/bin/env python3
"""
Test script for Predictive Intelligence Layer

Quick test to verify volatility spike prediction functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.volatility.predictive_engine import get_predictor
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test_prediction")

def test_prediction_engine():
    """Test the prediction engine functionality"""
    print("🧠 Testing Predictive Intelligence Layer")
    print("=" * 50)
    
    try:
        # Get predictor instance
        predictor = get_predictor()
        print(f"✅ Predictor initialized: {predictor}")
        
        # Test spike prediction
        print("\n📈 Testing spike prediction...")
        prediction = predictor.predict_spike()
        
        if prediction:
            print(f"✅ Prediction generated:")
            print(f"   Will spike: {prediction.will_spike}")
            print(f"   Confidence: {prediction.confidence:.1%}")
            print(f"   Minutes ahead: {prediction.minutes_ahead}")
            print(f"   Current IV: {prediction.current_iv:.1f}%")
            print(f"   Predicted IV: {prediction.predicted_iv:.1f}%")
            print(f"   Pattern: {prediction.pattern_match}")
        else:
            print("⚠️  No prediction available (insufficient data)")
        
        # Test early warning
        print("\n⚠️  Testing early warning...")
        warning = predictor.get_early_warning()
        
        if warning:
            print(f"🚨 Early warning active:")
            print(f"   {warning['message']}")
            print(f"   Confidence: {warning['confidence']}")
            print(f"   Pattern: {warning['pattern']}")
        else:
            print("✅ No early warning (safe conditions)")
        
        print("\n✅ Prediction engine test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_prediction_engine()
    sys.exit(0 if success else 1)