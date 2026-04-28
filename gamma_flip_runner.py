import math
import time
import requests
import json
import os
import sqlite3
from datetime import datetime
from gamma_flip_engine import GreeksEngine, DeribitDataClient, AggregatedDataClient, GammaFlipEngine

DB_PATH = 'gamma_flip.db'

def setup_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flip_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            spot_price REAL,
            flip_level REAL,
            distance_pct REAL,
            regime TEXT,
            total_gex REAL,
            max_long_strike REAL,
            max_short_strike REAL,
            pin_zone_low REAL,
            pin_zone_high REAL,
            pin_zone_density REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(payload):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Safely extract from payload structure
    flip = payload['flip_level'] if payload['flip_level'] is not None else 0.0
    pin_low = payload['pin_zone']['low'] if payload['pin_zone'] else 0.0
    pin_high = payload['pin_zone']['high'] if payload['pin_zone'] else 0.0
    pin_density = payload['pin_zone']['cumulative_gex'] if payload['pin_zone'] else 0.0
    
    cursor.execute('''
        INSERT INTO flip_history (
            spot_price, flip_level, distance_pct, regime, 
            total_gex, max_long_strike, max_short_strike, 
            pin_zone_low, pin_zone_high, pin_zone_density
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        payload['spot_price'], flip, payload['distance_to_flip_pct'], payload['regime'],
        payload['total_net_gex'], payload['max_long_gamma_strike'], payload['max_short_gamma_strike'],
        pin_low, pin_high, pin_density
    ))
    
    conn.commit()
    conn.close()

def build_payload(current_spot, flip_level, regime, dist, total_gex, max_long, max_short, pin_zone, gex_profile):
    # Prepare gex_profile dict for high-performance WebUI Bar Chart rendering
    formatted_gex_by_strike = [
        {"strike": float(k), "gex": float(v)} for k, v in sorted(gex_profile.items())
    ]
    
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "spot_price": current_spot,
        "regime": regime,
        "flip_level": flip_level,
        "pin_zone": {
            "low": pin_zone['low'],
            "high": pin_zone['high'],
            "cumulative_gex": pin_zone['cumulative_gex']
        } if pin_zone else None,
        "max_long_gamma_strike": max_long,
        "max_short_gamma_strike": max_short,
        "total_net_gex": total_gex,
        "distance_to_flip_pct": dist,
        "iv_surface_quality": "PARTIAL", # Hardcoded as partial until IV interpolation added
        "gex_by_strike": formatted_gex_by_strike
    }
    return payload

def run_engine_cycle():
    print("--- GAMMA FLIP ENGINE: FULL CYCLE ---")
    setup_db()
    
    client = AggregatedDataClient()
    chain = client.build_greeks_surface()
    
    gex_profile, total_gex, filtered_chain = GammaFlipEngine.calculate_gex_profile(
        chain, 
        exclude_dte_under=1.0, 
        exclude_dte_over=60.0
    )
    
    flip_level = GammaFlipEngine.detect_flip_level(gex_profile)
    max_long, max_short, pin_zone = GammaFlipEngine.identify_magnet_levels(gex_profile)
    
    current_spot = filtered_chain[0]['spot'] if filtered_chain else 0.0
    
    regime = "UNKNOWN"
    dist = 0.0
    if flip_level:
        dist = ((current_spot - flip_level) / flip_level) * 100
        if abs(dist) <= 0.5:
            regime = "APPROACHING_FLIP"
        elif current_spot > flip_level:
            regime = "LONG_GAMMA"
        else:
            regime = "SHORT_GAMMA"
            
    payload = build_payload(current_spot, flip_level, regime, dist, total_gex, max_long, max_short, pin_zone, gex_profile)
    
    # Save to JSON line
    with open("gamma_flip_feed.json", "w") as f:
        json.dump(payload, f, indent=4)
        
    save_to_db(payload)
    
    print(f"[+] Cycle complete. Regime: {regime}, Flip: {flip_level:,.2f}")
    print("[+] State saved to SQLite and gamma_flip_feed.json")

if __name__ == "__main__":
    run_engine_cycle()
