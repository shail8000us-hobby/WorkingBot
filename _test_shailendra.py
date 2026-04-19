from datetime import datetime
from shailendra import MarketData, ShailendraEngine

def test_engine():
    engine = ShailendraEngine(rsi_delta_threshold=15.0)
    
    print("--- Test 1: Setting Anchor ---")
    d1 = MarketData(price=77000, rsi=50, mmm_trend_regime="NORMAL", timestamp=datetime(2026, 4, 18, 17, 0, 0))
    suggestions = engine.process(d1)
    print("Suggestions:", suggestions)
    print("Anchor set to:", engine.anchor_hour, engine.anchor_price, engine.anchor_rsi)
    
    print("\n--- Test 2: Normal movement (no trigger) ---")
    d2 = MarketData(price=77100, rsi=55, mmm_trend_regime="NORMAL", timestamp=datetime(2026, 4, 18, 17, 15, 0))
    suggestions = engine.process(d2)
    print("Suggestions:", suggestions)

    print("\n--- Test 3: Fast Trend UP Triggers ---")
    d3 = MarketData(price=78000, rsi=66, mmm_trend_regime="TREND_UP", timestamp=datetime(2026, 4, 18, 17, 45, 0))
    suggestions = engine.process(d3)
    print("Suggestions:")
    for s in suggestions:
        print(" ->", s)

    print("\n--- Test 4: Hour rollover resets anchor ---")
    d4 = MarketData(price=78500, rsi=70, mmm_trend_regime="TREND_UP", timestamp=datetime(2026, 4, 18, 18, 1, 0))
    suggestions = engine.process(d4)
    print("Suggestions:", suggestions)
    print("New Anchor set to:", engine.anchor_hour, engine.anchor_price, engine.anchor_rsi)

if __name__ == "__main__":
    test_engine()

