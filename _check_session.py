#!/usr/bin/env python3
"""Quick script to check session state for debugging"""
import json
import urllib.request

def main():
    url = 'http://localhost:5555/api/mmm/session/mmm04mar26-1'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"Error fetching session: {e}")
        return

    session = data.get('session', {})
    ce = session.get('ce', {})
    pe = session.get('pe', {})
    params = session.get('params', {})

    print('=== CE State ===')
    print(f"active_lots: {ce.get('active_lots')}")
    print(f"frozen_total_lots: {ce.get('frozen_total_lots')}")
    print(f"total_lots: {ce.get('total_lots')}")
    print(f"active_strike: {ce.get('active_strike')}")
    print(f"positions count: {len(ce.get('positions', []))}")
    print(f"frozen_positions count: {len(ce.get('frozen_positions', []))}")
    
    # Group positions by status
    ce_by_status = {}
    for p in ce.get('positions', []):
        s = p.get('status', 'unknown')
        ce_by_status.setdefault(s, []).append(p)
    print(f"  Positions by status: {[(k, len(v)) for k,v in ce_by_status.items()]}")
    
    for p in ce.get('positions', [])[:8]:
        print(f"  pos: id={p.get('id')}, status={p.get('status')}, lots={p.get('lots')}, strike={p.get('strike')}")

    print()
    print('=== PE State ===')
    print(f"active_lots: {pe.get('active_lots')}")
    print(f"frozen_total_lots: {pe.get('frozen_total_lots')}")
    print(f"total_lots: {pe.get('total_lots')}")
    print(f"active_strike: {pe.get('active_strike')}")
    print(f"positions count: {len(pe.get('positions', []))}")
    print(f"frozen_positions count: {len(pe.get('frozen_positions', []))}")
    
    # Group positions by status
    pe_by_status = {}
    for p in pe.get('positions', []):
        s = p.get('status', 'unknown')
        pe_by_status.setdefault(s, []).append(p)
    print(f"  Positions by status: {[(k, len(v)) for k,v in pe_by_status.items()]}")
    
    for p in pe.get('positions', [])[:8]:
        print(f"  pos: id={p.get('id')}, status={p.get('status')}, lots={p.get('lots')}, strike={p.get('strike')}")

    print()
    print('=== Key Params (M1/M2/M3 Config) ===')
    print(f"harvest_enabled: {params.get('harvest_enabled')}")
    print(f"recycle_enabled: {params.get('recycle_enabled')}")
    print(f"shift_recycle_enabled: {params.get('shift_recycle_enabled')}")
    print(f"harvest_pressure_threshold: {params.get('harvest_pressure_threshold')}")
    print(f"harvest_profit_pct: {params.get('harvest_profit_pct')}")
    print(f"max_lots_per_side: {params.get('max_lots_per_side')}")
    print(f"rebalance_enabled: {params.get('rebalance_enabled')}")
    print(f"close_at_threshold: {params.get('close_at_threshold')}")
    print(f"wind_down_mode: {session.get('wind_down_mode')}")
    print(f"wind_down_active: {session.get('wind_down_active')}")
    print(f"harvest_count: {session.get('harvest_count', 0)}")
    print(f"recycle_count: {session.get('recycle_count', 0)}")
    print(f"close_at_5_count: {session.get('close_at_5_count', 0)}")
    print()
    
    # Check capacity pressure to see if M1 would trigger
    ce_total = ce.get('total_lots', 0)
    pe_total = pe.get('total_lots', 0)
    max_lots = params.get('max_lots_per_side', 100)
    harvest_threshold = params.get('harvest_pressure_threshold', 0.5)
    ce_pressure = ce_total / max(max_lots, 1)
    pe_pressure = pe_total / max(max_lots, 1)
    print('=== M1 Eligibility Check ===')
    print(f"CE capacity pressure: {ce_pressure:.2f} (threshold: {harvest_threshold})")
    print(f"PE capacity pressure: {pe_pressure:.2f} (threshold: {harvest_threshold})")
    print(f"CE would scan for harvest: {ce_pressure >= harvest_threshold}")
    print(f"PE would scan for harvest: {pe_pressure >= harvest_threshold}")


if __name__ == '__main__':
    main()
