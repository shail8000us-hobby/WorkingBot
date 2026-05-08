# Portfolio Greeks Calculation Fixes (May 8, 2026 Audit)

This document details the critical mathematical fixes applied to the Portfolio Greeks calculation logic across the backend APIs and frontend UI. This log is generated for secondary AI code auditing and verification.

## 1. Short Gamma and Vega Sign Correction (The `abs()` Bug)

### Context
In options trading (Black-Scholes), going short an option (e.g., selling a Call or a Put) results in negative Gamma and negative Vega exposure for that position.

### The Bug
In the previous implementation, the portfolio aggregator explicitly used `Math.abs(size)` (frontend) and `abs(size)` (backend) when scaling per-contract Gamma and Vega. This mathematically forced Gamma and Vega to always be positive. If a user traded a short strategy (like a short strangle), the system falsely reported them as being *long* Gamma and Vega.

### The Fix
Removed the absolute value wrapper from all Gamma and Vega calculations. The formulas now use the signed `size` parameter.
- **Frontend File**: `webui/frontend/src/components/options/OptionsPanel.js` (lines 1530-1533 and 1622-1625)
- **Backend File 1**: `webui/backend/routes/options/dashboard.py` (lines 98-101)
- **Backend File 2**: `webui/backend/options_strategy/position_greeks.py` (lines 196-199)

## 2. Dynamic Lot Multipliers (The ETH Bug)

### Context
Delta Exchange uses contract multipliers to represent exposure. For BTC options, 1 contract = `0.001` BTC. For ETH options, 1 contract = `0.01` ETH.

### The Bug
The aggregation logic hardcoded the lot multiplier (`LOT_MULT = 0.001`) globally. This means any ETH options had their true directional risk (Delta) and Greek exposures (Gamma, Theta, Vega) understated by exactly a factor of 10.

### The Fix
The aggregation logic now dynamically identifies the underlying asset from the product symbol. If it detects an ETH product, it applies the correct `0.01` multiplier.
- **Frontend Logic**: `const LOT_MULT = underlying === 'ETH' ? 0.01 : 0.001;`
- **Backend Logic**: `LOT_MULT = 0.01 if underlying == 'ETH' else 0.001`

## 3. Theta/Vega Scaling Normalization

### Context
Delta Exchange provides `theta` and `vega` per full unit (1 BTC or 1 ETH). To convert this to the actual lot size, you must scale the value by `size * LOT_MULT`.

### The Bug
The previous code used division by 1000 (`(perContractTheta / 1000) * size`). While mathematically identical to multiplying by `0.001` (and thus correct for BTC), it breaks for ETH since ETH requires a multiplier of `0.01`.

### The Fix
Standardized the scaling of Theta and Vega to universally use the dynamic lot multiplier:
- **Old Formula**: `greeks.theta += (perContractTheta / 1000) * size`
- **New Formula**: `greeks.theta += perContractTheta * size * LOT_MULT`

## Verification Summary for Secondary Auditor
Please review the changes made to the aforementioned files. You should verify that:
1. `size` is used instead of `abs(size)` or `Math.abs(size)` for Gamma and Vega aggregations.
2. The dynamic `LOT_MULT` accurately checks if the underlying is ETH.
3. The Theta scaling explicitly uses the `LOT_MULT` instead of division by 1000.
