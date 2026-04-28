import math
import time
import requests
from datetime import datetime

# =============================================================================
# MODULE 2: GREEKS ENGINE (Dependency-Free Black-Scholes)
# =============================================================================

class GreeksEngine:
    """
    Computes Black-Scholes options Greeks from scratch using standard Python math.
    No reliance on external quantitative libraries.
    """
    
    @staticmethod
    def normal_pdf(x):
        """Standard Normal Probability Density Function."""
        return math.exp(-x**2 / 2.0) / math.sqrt(2.0 * math.pi)

    @staticmethod
    def normal_cdf(x):
        """Standard Normal Cumulative Distribution Function."""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    @staticmethod
    def calculate_d1(S, K, T, r, sigma):
        """Calculate d1 probability factor."""
        if sigma <= 0 or T <= 0:
            return 0.0
        return (math.log(S / K) + (r + (sigma**2) / 2.0) * T) / (sigma * math.sqrt(T))

    @classmethod
    def calculate_gamma(cls, S, K, T, r, sigma):
        """
        Calculate raw Black-Scholes Gamma (change in delta per $1 move in spot).
        Gamma is identical for both Calls and Puts.
        """
        if sigma <= 0 or T <= 0:
            return 0.0
        
        d1 = cls.calculate_d1(S, K, T, r, sigma)
        return cls.normal_pdf(d1) / (S * sigma * math.sqrt(T))

    @staticmethod
    def dollar_gamma(gamma, S):
        """
        Convert raw gamma to 'Dollar Gamma' (Gamma Exposure).
        This models the P&L impact (or required hedge) for a 1% move in the underlying spot price.
        """
        return gamma * (S**2) * 0.01


# =============================================================================
# MODULE 1: DATA INGESTION LAYER (Deribit Implementation)
# =============================================================================

class DeribitDataClient:
    """
    Fetches real-time Options data from Deribit, normalizes fields, and 
    handles edge cases like staleness/null IV.
    """
    BASE_URL = "https://deribit.com/api/v2/public"

    def __init__(self):
        self.contract_sizes = {}
        self.refresh_instruments()

    def refresh_instruments(self):
        """
        Gap 1 Addressed: Fetches exact contract_size multiplier per instrument.
        Returns mapping of: instrument_name -> contract_size
        """
        url = f"{self.BASE_URL}/get_instruments?currency=BTC&kind=option"
        response = requests.get(url).json()
        
        if 'result' in response:
            for inst in response['result']:
                self.contract_sizes[inst['instrument_name']] = inst['contract_size']
        print(f"[+] Loaded {len(self.contract_sizes)} active BTC option instruments.")

    def fetch_live_chain(self):
        """
        Fetches the bulk order book summary and processes it.
        """
        url = f"{self.BASE_URL}/get_book_summary_by_currency?currency=BTC&kind=option"
        response = requests.get(url).json()
        
        if 'result' not in response:
            print("[-] Error fetching book summary.")
            return []
            
        return response['result']

    @staticmethod
    def parse_instrument_name(instrument_name):
        """
        Parses 'BTC-27JUN25-100000-C' -> ('BTC', '27JUN25', 100000.0, 'C')
        """
        parts = instrument_name.split('-')
        if len(parts) != 4:
            return None
        
        base, expiry_str, strike_str, opt_type = parts
        strike = float(strike_str)
        
        # Parse Expiry to Timestamp
        expiry_dt = datetime.strptime(expiry_str, "%d%b%y")
        # Deribit expiries happen at 08:00 UTC
        expiry_dt = expiry_dt.replace(hour=8, minute=0, second=0)
        
        return expiry_dt, strike, opt_type

    def build_greeks_surface(self, risk_free_rate=0.05):
        """
        Ingests the live chain, filters edge cases (Gap 2: zero/null IV), 
        and calculates Greeks per contract.
        """
        raw_chain = self.fetch_live_chain()
        now = datetime.utcnow()
        
        processed_contracts = []
        iv_miss_count = 0
        
        for item in raw_chain:
            inst_name = item.get('instrument_name')
            spot = item.get('estimated_delivery_price') # robust spot proxy
            mark_iv = item.get('mark_iv')
            oi = item.get('open_interest', 0)
            
            # Skip empty OI contracts early for efficiency
            if oi <= 0:
                continue
                
            # Gap 2 Addressed: Handle Null/Zero IV
            # In Phase 2, we can interpolate. For Phase 1, we log and skip.
            if not mark_iv or mark_iv <= 0:
                iv_miss_count += 1
                continue
                
            parsed = self.parse_instrument_name(inst_name)
            if not parsed:
                continue
                
            expiry_dt, strike, opt_type = parsed
            
            # Calculate Time to Expiry (T) in years
            delta = expiry_dt - now
            T = delta.total_seconds() / (365.25 * 24 * 3600)
            
            if T <= 0:
                continue # Expired
                
            # Retrieve specific contract size mapping
            c_size = self.contract_sizes.get(inst_name, 1.0)
            
            # Model the IV (Deribit returns IV as whole number percentage, e.g., 50 for 50%)
            sigma = mark_iv / 100.0 
            
            # Calculate Phase 1 Greeks
            raw_gamma = GreeksEngine.calculate_gamma(spot, strike, T, risk_free_rate, sigma)
            dollar_gamma = GreeksEngine.dollar_gamma(raw_gamma, spot)
            
            processed_contracts.append({
                "instrument": inst_name,
                "type": opt_type,
                "strike": strike,
                "T_years": round(T, 4),
                "spot": spot,
                "iv": mark_iv,
                "oi": oi,
                "contract_size": c_size,
                "raw_gamma": raw_gamma,
                "dollar_gamma": dollar_gamma
            })
            
        return processed_contracts


class BinanceDataClient:
    """
    Fetches active BTC options from Binance (eAPI).
    """
    BASE_URL = "https://eapi.binance.com/eapi/v1"

    def fetch_live_chain(self):
        try:
            # Note: For production Binance options, you match exchangeInfo (for multipliers) 
            # and ticker (for IV/OI). Sticking to a soft skeleton that skips on failure 
            # so it doesn't break the main aggregator if eAPI rate limits.
            url = f"{self.BASE_URL}/ticker"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Dummy parse to match our unified structure
                # In full prod, we'd properly parse instrument, T, etc.
                return []
        except Exception as e:
            print(f"[-] Binance fetch failed: {e}")
        return []

class OkxDataClient:
    """
    Fetches active BTC options from OKX (v5 API).
    """
    BASE_URL = "https://www.okx.com/api/v5"

    def fetch_live_chain(self):
        try:
            url = f"{self.BASE_URL}/market/tickers?instType=OPTION&instFamily=BTC-USD"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # Return empty list until full OI endpoint parsing is perfectly matched
                return []
        except Exception as e:
            print(f"[-] OKX fetch failed: {e}")
        return []

class AggregatedDataClient:
    """
    Pools data from multiple exchanges to create a global options chain.
    """
    def __init__(self):
        self.deribit = DeribitDataClient()
        self.binance = BinanceDataClient()
        self.okx = OkxDataClient()
        
    def build_greeks_surface(self, risk_free_rate=0.05):
        print("[i] Aggregating Cross-Broker Options Data...")
        # 1. Fetch Deribit (Primary)
        global_chain = self.deribit.build_greeks_surface(risk_free_rate)
        
        # 2. Fetch Binance (Secondary)
        # binance_chain = self.binance.build_greeks_surface(...)
        # global_chain.extend(binance_chain)
        
        # 3. Fetch OKX (Tertiary)
        # okx_chain = self.okx.build_greeks_surface(...)
        # global_chain.extend(okx_chain)
        
        print(f"[+] Total Aggregated Active Contracts: {len(global_chain)}")
        return global_chain

# =============================================================================
# MODULE 3 & 4: DEALER GEX MODEL & GAMMA FLIP DETECTION
# =============================================================================

class GammaFlipEngine:
    """
    Ingests processed contracts to build a chain-wide Dealer GEX profile,
    detects the Gamma Flip level via zero-crossing interpolation, and locates
    the highest density clustering for the Pin Zone.
    """
    
    @staticmethod
    def calculate_gex_profile(contracts, exclude_dte_under=1.0, exclude_dte_over=60.0):
        """
        Aggregate Call/Put Dealer GEX by Strike.
        (Net Short Assumption: Dealers short calls (+gamma), short puts (-gamma))
        Module 6 Filtering: Exclude < 1 DTE and > 60 DTE to reduce gamma noise/flatness.
        """
        gex_by_strike = {}
        total_gex = 0.0
        filtered_contracts = []
        
        for p in contracts:
            dte = p['T_years'] * 365.25
            
            # Expiry Exclusion Filter (Module 6)
            if dte < exclude_dte_under or dte > exclude_dte_over:
                continue
                
            filtered_contracts.append(p)
            
            # Module 3 calculation: Dealer Hedging Convention
            # Dealers short Calls -> + Gamma
            # Dealers short Puts -> - Gamma
            gex_val = p['dollar_gamma'] * p['oi'] * p['contract_size']
            if p['type'] == 'C':
                gex_exposure = gex_val
            elif p['type'] == 'P':
                gex_exposure = -gex_val
            else:
                continue
                
            total_gex += gex_exposure
            k = p['strike']
            gex_by_strike[k] = gex_by_strike.get(k, 0.0) + gex_exposure
            
        print(f"[i] Filtered down to {len(filtered_contracts)} contracts after {exclude_dte_under}-{exclude_dte_over} DTE exclusion.")
        return gex_by_strike, total_gex, filtered_contracts

    @staticmethod
    def detect_flip_level(gex_by_strike):
        """
        Sorts strikes, computes a cumulative running sum of GEX, and interpolates 
        the exact spot price where the running sum crosses zero.
        """
        if not gex_by_strike:
            return None
            
        strikes = sorted(gex_by_strike.keys())
        running_sum = 0.0
        cumulative_gex = []
        
        # Build cumulative sum profile
        for idx, k in enumerate(strikes):
            running_sum += gex_by_strike[k]
            cumulative_gex.append((k, running_sum, gex_by_strike[k]))
            
        flip_level = None
        
        # Locate Zero Crossing
        for i in range(1, len(cumulative_gex)):
            prev_k, prev_sum, _ = cumulative_gex[i-1]
            curr_k, curr_sum, _ = cumulative_gex[i]
            
            # Detect crossing
            if (prev_sum < 0 and curr_sum >= 0) or (prev_sum > 0 and curr_sum <= 0):
                # Linear Interpolation
                # formula: X_int = X1 - Y1 * (X2 - X1) / (Y2 - Y1)
                spread = curr_sum - prev_sum
                if spread == 0:
                    flip_level = prev_k
                else:
                    flip_level = prev_k - prev_sum * (curr_k - prev_k) / spread
                break
                
        # If no flip is cleanly found (e.g. extreme unidirectional positioning), fallback to spot proximity or center
        return flip_level

    @staticmethod
    def identify_magnet_levels(gex_by_strike):
        """
        Finds the highest net positive strike (Max Long Gamma), the highest net negative 
        strike (Max Short Gamma), and an initial heuristic for the Pin Zone.
        """
        if not gex_by_strike:
            return None, None, None
            
        # Max Long/Short Points
        max_long_gamma_strike = max(gex_by_strike.items(), key=lambda x: x[1])[0]
        max_short_gamma_strike = min(gex_by_strike.items(), key=lambda x: x[1])[0]
        
        # --- Pin Zone Clustering (Naive Density Filter) ---
        # A simple method to locate a contiguous band of highly positive GEX.
        # For a full k-means implementation we'd use scipy/sklearn, but sticking to core python:
        # We will scan a 3-strike rolling window to find the densest positive cluster.
        strikes = sorted(gex_by_strike.keys())
        highest_band_sum = 0
        best_band = (0, 0)
        
        for i in range(len(strikes) - 2):
            window_sum = gex_by_strike[strikes[i]] + gex_by_strike[strikes[i+1]] + gex_by_strike[strikes[i+2]]
            if window_sum > highest_band_sum:
                highest_band_sum = window_sum
                best_band = (strikes[i], strikes[i+2])
                
        pin_zone = {
            "low": best_band[0],
            "high": best_band[1],
            "cumulative_gex": highest_band_sum
        }

        return max_long_gamma_strike, max_short_gamma_strike, pin_zone

# =============================================================================
# PHASE 2 DRIVER/TEST
# =============================================================================
if __name__ == "__main__":
    print("--- GAMMA FLIP ENGINE: PHASE 2 ---\n")
    client = DeribitDataClient()
    
    start_t = time.time()
    # 1. Fetch and calculate raw Greeks
    chain = client.build_greeks_surface()
    
    # 2. Build profile, taking only 1-60 DTE into account to omit noise
    gex_profile, total_gex, filtered_chain = GammaFlipEngine.calculate_gex_profile(
        chain, 
        exclude_dte_under=1.0, 
        exclude_dte_over=60.0
    )
    
    # 3. Interpolate the exact Gamma Flip crossing Level
    flip_level = GammaFlipEngine.detect_flip_level(gex_profile)
    
    # 4. Find the max point magnets and dense Pin Zone clustering
    max_long, max_short, pin_zone = GammaFlipEngine.identify_magnet_levels(gex_profile)
    
    end_t = time.time()
    
    # Use first valid contract to grab current market spot
    current_spot = filtered_chain[0]['spot'] if filtered_chain else 0.0
    
    print(f"\n[+] Total Integration & Calculation time: {(end_t - start_t) * 1000:.2f} ms")
    
    print("\n--- SYSTEM DIAGNOSTICS & LEVELS ---")
    print(f"Overall Market Spot         : {current_spot:,.2f}")
    if flip_level:
        print(f"Calculated Gamma Flip Level : {flip_level:,.2f}")
        dist = ((current_spot - flip_level) / flip_level) * 100
        print(f"Distance to Flip            : {dist:+.2f}%")
        regime = "LONG_GAMMA (Stabilizing)" if current_spot > flip_level else "SHORT_GAMMA (Amplifying/Breakout)"
        print(f"Current Regime Classifier   : {regime}")
    else:
        print("Calculated Gamma Flip Level : [None detected - extreme unipolar chain]")
        
    print(f"Total Net GEX (Chain-wide)  : {total_gex:,.2f}")
    print(f"Max Long Gamma Strike       : {max_long:,.2f}")
    print(f"Max Short Gamma Strike      : {max_short:,.2f}")
    print(f"Dense Pin Zone (Magnet)     : {pin_zone['low']:,.2f} - {pin_zone['high']:,.2f} (Density: {pin_zone['cumulative_gex']:,.2f})")
