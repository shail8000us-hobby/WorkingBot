import math
from collections import defaultdict
from datetime import datetime, timezone

log = logging.getLogger('oi_aggregator') if 'logging' in globals() else None

RISK_FREE_RATE = 0.05

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x):
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)

def bs_greeks(S, K, T, r, sigma):
    """Compute Black-Scholes Delta and Gamma."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {'delta_call': 0, 'delta_put': 0, 'gamma': 0}
        
    d1 = (math.log(S / K) + (r + (sigma**2) / 2.0) * T) / (sigma * math.sqrt(T))
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    delta_call = norm_cdf(d1)
    delta_put = delta_call - 1.0
    
    return {
        'gamma': gamma,
        'delta_call': delta_call,
        'delta_put': delta_put
    }

def compute_gamma_state(aggregated_rows, S):
    """
    Computes GEX metrics as described in GAMMA_FLIP_ENGINE_DESIGN.md
    """
    if S <= 0 or not aggregated_rows:
        return None
        
    gex_by_strike = defaultdict(float)
    total_net_gex = 0.0
    
    now = datetime.now(timezone.utc)
    
    valid_strikes = False
    
    # Calculate GEX per row
    # Dealer GEX assumption: Dealers are short Call => Long Gamma, Short Put => Short Gamma
    for row in aggregated_rows:
        strike = row['strike']
        opt_type = row['type']
        expiry_str = row['expiry']
        oi = row['oi']
        iv = row.get('mark_iv', 0.0)
        
        # If IV is missing, fallback to standard assumption (0.50) to keep chain continuous
        if iv <= 0:
            iv = 0.50
            
        try:
            # Parse expiry to get time to expiry T in years
            # Assuming expiration at 08:00 UTC
            exp_date = datetime.strptime(f"{expiry_str} 08:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            delta_td = exp_date - now
            T_years = max(delta_td.total_seconds() / (365.25 * 24 * 3600.0), 0.0)
            
            # Module 6: Expiry Weighting (Exclude 0-1 DTE and > 60 DTE)
            days_to_expiry = delta_td.total_seconds() / 86400.0
            if days_to_expiry <= 1.0 or days_to_expiry > 60.0:
                continue
                
            greeks = bs_greeks(S, strike, T_years, RISK_FREE_RATE, iv)
            gamma = greeks['gamma']
            
            # Dollar Gamma (P&L impact of a 1% move in spot)
            # Gamma * Spot^2 * 0.01 per 1 unit of underlying
            dollar_gamma = gamma * (S ** 2) * 0.01
            
            # Dealer Net GEX
            # Call GEX: +1 * Dollar Gamma * OI
            # Put GEX: -1 * Dollar Gamma * OI
            # (Note: oi is in underlying BTC units, so contract_size is effectively 1)
            if opt_type == 'call':
                gex = dollar_gamma * oi
            else:
                gex = -1.0 * dollar_gamma * oi
                
            gex_by_strike[strike] += gex
            total_net_gex += gex
            valid_strikes = True
            
        except Exception as e:
            if log:
                log.debug(f"[GammaEngine] Error calculating strike {strike}: {e}")
            continue
            
    if not valid_strikes:
        return None
        
    # Module 4: Gamma Flip Level Detection
    # 1. Group and sum GEX by Strike Price (already in gex_by_strike)
    # 2. Sort strikes sequentially
    sorted_strikes = sorted(gex_by_strike.keys())
    
    # 3. Compute a running sum of GEX from lowest strike upward
    running_sum = 0.0
    flip_level = 0.0
    found_flip = False
    
    for i in range(len(sorted_strikes) - 1):
        k1 = sorted_strikes[i]
        k2 = sorted_strikes[i+1]
        
        gex1 = gex_by_strike[k1]
        running_sum += gex1
        
        next_sum = running_sum + gex_by_strike[k2]
        
        # 4. Identify zero-crossing
        if (running_sum <= 0 and next_sum > 0) or (running_sum >= 0 and next_sum < 0):
            # 5. Linearly interpolate
            # running_sum + x * (gex2) = 0 => x = -running_sum / gex2
            try:
                fraction = abs(running_sum) / abs(gex_by_strike[k2] if gex_by_strike[k2] != 0 else 1e-9)
                fraction = min(max(fraction, 0.0), 1.0)
                flip_level = k1 + fraction * (k2 - k1)
                found_flip = True
            except ZeroDivisionError:
                flip_level = (k1 + k2) / 2.0
                found_flip = True
            # Only record the first crossing near spot? 
            # Or nearest to spot? Let's take the zero crossing closest to spot
            if S > k1 and S < k2:
                break # best flip level

    # If no zero crossing, fallback to zero aggregate level or spot
    if not found_flip:
        # Fallback approximation
        flip_level = S
        
    # Magnet Levels (Pin Zone, Max Strikes)
    max_long_gamma_strike = 0
    max_long_gamma_val = -float('inf')
    max_short_gamma_strike = 0
    max_short_gamma_val = float('inf')
    
    for k, v in gex_by_strike.items():
        if v > max_long_gamma_val:
            max_long_gamma_val = v
            max_long_gamma_strike = k
        if v < max_short_gamma_val:
            max_short_gamma_val = v
            max_short_gamma_strike = k

    # Simple Pin Zone: highest density contiguous positive GEX cluster. Look +/- 5% from Max Long.
    pin_low = max_long_gamma_strike * 0.95
    pin_high = max_long_gamma_strike * 1.05
    cum_gex_pin = sum(v for k, v in gex_by_strike.items() if pin_low <= k <= pin_high and v > 0)
    
    # Module 5: Signal Generation Logic
    if S > flip_level * 1.005:
        regime = "LONG_GAMMA"
    elif S < flip_level * 0.995:
        regime = "SHORT_GAMMA"
    else:
        regime = "APPROACHING_FLIP"
        
    distance_to_flip_pct = ((S - flip_level) / flip_level) * 100.0 if flip_level > 0 else 0.0

    return {
        "regime": regime,
        "flip_level": round(flip_level, 2),
        "pin_zone": {
            "low": round(pin_low, 2),
            "high": round(pin_high, 2),
            "cumulative_gex": round(cum_gex_pin, 2)
        },
        "max_long_gamma_strike": max_long_gamma_strike,
        "max_short_gamma_strike": max_short_gamma_strike,
        "total_net_gex": round(total_net_gex, 2),
        "distance_to_flip_pct": round(distance_to_flip_pct, 4),
        "gex_by_strike": {k: round(v, 2) for k, v in gex_by_strike.items()},
        "iv_surface_quality": "PARTIAL"
    }
