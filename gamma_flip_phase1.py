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
            
        print(f"[i] Processed {len(processed_contracts)} contracts with active OI.")
        if iv_miss_count > 0:
            print(f"[!] Skipped {iv_miss_count} contracts due to zero/null IV (Gap 2 handling).")
            
        return processed_contracts


# =============================================================================
# PHASE 1 DRIVER/TEST
# =============================================================================
if __name__ == "__main__":
    print("--- GAMMA FLIP ENGINE: PHASE 1 ---\n")
    client = DeribitDataClient()
    
    start_t = time.time()
    chain = client.build_greeks_surface()
    end_t = time.time()
    
    print(f"\n[+] Integration and Greek calculations took: {(end_t - start_t) * 1000:.2f} ms")
    
    if chain:
        # Let's inspect the contract with the highest Dollar Gamma for sanity checking
        highest_gamma_contract = max(chain, key=lambda x: x['dollar_gamma'])
        print("\n--- SAMPLE CONTRACT MATCH (Highest Individual Dollar Gamma) ---")
        for k, v in highest_gamma_contract.items():
            print(f"{k.ljust(15)}: {v}")
