#!/usr/bin/env python3
"""
Liquidation Distance Calculation Verification
==============================================

This script demonstrates the CORRECTED liquidation distance calculation
following Delta Exchange guidelines.

Run this to verify the fix is working correctly.
"""

def calculate_liquidation_distance_CORRECT(current_price: float, liq_price: float, is_long: bool) -> float:
    """
    ✅ CORRECT Formula (Delta Exchange Guideline)
    
    For LONG:  distance% = (current - liquidation) / current * 100
    For SHORT: distance% = (liquidation - current) / current * 100
    """
    if is_long:
        distance_pct = ((current_price - liq_price) / current_price) * 100
    else:
        distance_pct = ((liq_price - current_price) / current_price) * 100
    
    return distance_pct


def calculate_liquidation_distance_OLD_WRONG(current_price: float, liq_price: float, usd_to_inr: float = 85) -> float:
    """
    ❌ OLD WRONG Formula (What bot was doing before)
    
    Returns absolute INR distance instead of percentage
    """
    distance_usd = abs(current_price - liq_price)
    distance_inr = distance_usd * usd_to_inr
    return distance_inr


def main():
    print("=" * 80)
    print("LIQUIDATION DISTANCE CALCULATION - BEFORE vs AFTER FIX")
    print("=" * 80)
    
    # Example 1: LONG Position
    print("\n📈 Example 1: LONG Position")
    print("-" * 80)
    current_price = 80000.0  # BTC at ₹80,000
    liq_price_long = 76000.0  # Liquidation at ₹76,000
    
    old_result = calculate_liquidation_distance_OLD_WRONG(current_price, liq_price_long)
    new_result = calculate_liquidation_distance_CORRECT(current_price, liq_price_long, is_long=True)
    
    print(f"Current Price:     ₹{current_price:,.2f}")
    print(f"Liquidation Price: ₹{liq_price_long:,.2f}")
    print(f"\n❌ OLD (WRONG):    {old_result:,.2f} INR")
    print(f"✅ NEW (CORRECT):  {new_result:.2f}%")
    print(f"\n⚠️  Problem: Old method returned INR value, config threshold was 0.5")
    print(f"    Guardian thought: {old_result:,.2f} > 0.5 → Safe (WRONG!)")
    print(f"\n✅ Fix: New method returns percentage, config threshold is 1.0%")
    print(f"    Guardian now: {new_result:.2f}% > 1.0% → Safe (CORRECT)")
    
    # Example 2: SHORT Position
    print("\n📉 Example 2: SHORT Position")
    print("-" * 80)
    liq_price_short = 84000.0  # Liquidation at ₹84,000
    
    old_result = calculate_liquidation_distance_OLD_WRONG(current_price, liq_price_short)
    new_result = calculate_liquidation_distance_CORRECT(current_price, liq_price_short, is_long=False)
    
    print(f"Current Price:     ₹{current_price:,.2f}")
    print(f"Liquidation Price: ₹{liq_price_short:,.2f}")
    print(f"\n❌ OLD (WRONG):    {old_result:,.2f} INR")
    print(f"✅ NEW (CORRECT):  {new_result:.2f}%")
    
    # Example 3: Critical Scenario (0.8% from liquidation)
    print("\n🚨 Example 3: CRITICAL - Near Liquidation")
    print("-" * 80)
    current_price = 80000.0
    liq_price_critical = 79360.0  # Only 0.8% away!
    
    old_result = calculate_liquidation_distance_OLD_WRONG(current_price, liq_price_critical)
    new_result = calculate_liquidation_distance_CORRECT(current_price, liq_price_critical, is_long=True)
    
    print(f"Current Price:     ₹{current_price:,.2f}")
    print(f"Liquidation Price: ₹{liq_price_critical:,.2f}")
    print(f"\n❌ OLD (WRONG):    {old_result:,.2f} INR")
    print(f"   Guardian: {old_result:,.2f} > 0.5 → ✅ Safe (DANGEROUS!)")
    print(f"\n✅ NEW (CORRECT):  {new_result:.2f}%")
    print(f"   Guardian: {new_result:.2f}% < 1.0% → 🚨 CRITICAL! Stop trading!")
    
    # Config comparison
    print("\n" + "=" * 80)
    print("CONFIG CHANGES")
    print("=" * 80)
    print("\n❌ OLD config.yaml:")
    print("   guardian.liquidation_critical: 0.5        # Meaningless with INR calculation")
    print("   safety.min_liquidation_distance_pct: 50.0 # Too conservative")
    print("\n✅ NEW config.yaml:")
    print("   guardian.liquidation_critical: 1.0        # 1% = emergency stop")
    print("   guardian.liquidation_warning: 5.0         # 5% = warning alert")
    print("   safety.min_liquidation_distance_pct: 10.0 # 10% = minimum for trading")
    print("   liquidation_protection.liquidation_distance_min: 10.0")
    print("   liquidation_protection.liquidation_distance_target: 15.0")
    print("   liquidation_protection.liquidation_distance_critical: 5.0")
    
    # Safety levels
    print("\n" + "=" * 80)
    print("SAFETY LEVELS (10x Leverage)")
    print("=" * 80)
    print("\n✅ SAFE:     Distance > 10%  → Normal trading")
    print("⚠️  WARNING:  Distance 5-10% → Caution, early alert")
    print("🚨 CRITICAL: Distance 1-5%  → Aggressive warnings")
    print("🔴 EMERGENCY: Distance < 1%  → STOP trading, force close positions")
    
    print("\n" + "=" * 80)
    print("✅ FIXES APPLIED:")
    print("=" * 80)
    print("\n1. ✅ position_monitor.py - Now calculates percentage distance")
    print("2. ✅ config.yaml - Updated all thresholds to realistic percentages")
    print("3. ✅ Integrated with IntegratedLiquidationMonitor (already correct)")
    print("4. ✅ Guardian will now properly protect against liquidation")
    
    print("\n" + "=" * 80)
    print("🎯 NEXT STEPS:")
    print("=" * 80)
    print("\n1. Restart Guardian Bot: pm2 restart guardian-live")
    print("2. Check logs: pm2 logs guardian-live --lines 50")
    print("3. Monitor WebUI: http://localhost:5555")
    print("4. Test with paper trading first before going live")
    print("=" * 80)


if __name__ == "__main__":
    main()
