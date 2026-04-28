# Gamma Flip Engine — Detailed Architecture & Build Plan

## Objective
Design and implement a system that ingests Bitcoin options market data, computes net dealer gamma exposure (GEX) across the options chain, identifies the gamma flip level (where dealer hedging behavior inverts), and generates directional and regime-filtering signals for an automated trading bot.

---

## Module 1: Data Ingestion Layer
The foundation of the engine is high-fidelity, aggregated options chain data leveraging the existing WebUI OI Dashboard infrastructure (collecting from all popular brokers: Deribit, Binance, OKX, Bybit).

### Data Sources & Normalization
- **Cross-Broker Aggregation**: Pool OI and volume across exchanges for a true global GEX profile.
- **Primary Endpoints (e.g., Deribit)**: 
  - `GET /api/v2/public/get_book_summary_by_currency` (Bulk fetch OI, mark price, IV).
  - `GET /api/v2/public/get_instruments` (Fetch actual `contract_size` multiplier).
- **IV Surface Staleness Handling**: If `mark_iv` returns `0` or `null` (common for illiquid far-OTM strikes), the engine must either skip the contract or linearly interpolate IV from adjacent liquid strikes to maintain calculation integrity.

### Extracted Fields per Contract
- **Instrument Name**: Base, expiry, strike, type
- **Strike Price ($K$)**
- **Time to Expiry ($T$)**: Calculated in years.
- **Option Type**: Call (C) or Put (P)
- **Open Interest ($OI$)**: Aggregated active contracts.
- **Contract Size**: Dynamically parsed per instrument/broker.
- **Mark IV ($\sigma$)**: Annualised implied volatility (with fallback logic).
- **Spot Price ($S$)**: Global aggregated index price.

### Polling Cadence
- **Positional Awareness**: REST API poll every 60 seconds.
- **Real-Time precision**: Websocket subscriptions for intraday spot and IV movements.

---

## Module 2: Greeks Engine
To remain dependency-free, calculate Black-Scholes gamma and delta directly using standard math functions (exp, log, sqrt, standard normal PDF/CDF).

### Inputs
- $S$: Spot Price
- $K$: Strike Price
- $T$: Time to Expiry (years)
- $r$: Risk-free rate (default ~0.05 or SOFR)
- $\sigma$: Mark IV

### Core Math
1. **$d_1$ Calculation**:
   $$ d_1 = \frac{\ln(S/K) + (r + \frac{\sigma^2}{2})T}{\sigma \sqrt{T}} $$
2. **Gamma ($\Gamma$)**:
   $$ \Gamma = \frac{N'(d_1)}{S \sigma \sqrt{T}} $$
   *(Where $N'()$ is the standard normal probability density function)*
3. **Delta ($\Delta$)**:
   - Call Delta: $N(d_1)$
   - Put Delta: $N(d_1) - 1$

### Dollar Gamma Conversion
Raw gamma measures $\Delta$ change per $\$1$ move in spot. To normalize exposure to the P&L impact of a 1% move in spot:
$$ \text{Dollar Gamma} = \Gamma \times S^2 \times 0.01 $$
This allows apples-to-apples GEX comparison across strikes.

---

## Module 3: Dealer GEX Model
The core market microstructure assumption: **Retail/institutional customers predominantly BUY options. Dealers (market makers) are on the other side, net SHORT options.**

### Dealer Hedging Dynamics
- **Dealers Short Calls**: As price rises, $\Delta$ becomes more negative. Dealers must *buy* the underlying to stay delta-neutral. As price falls, they *sell*. **(Net Long Gamma = Stabilizing)**
- **Dealers Short Puts**: As price falls, $\Delta$ becomes more positive. Dealers must *sell* the underlying to stay delta-neutral. As price rises, they *buy*. **(Net Short Gamma = Amplifying)**

### GEX Calculation per Contract
- **Call GEX**: $+1 \times \text{Dollar Gamma} \times OI \times \text{Contract Size}$
- **Put GEX**: $-1 \times \text{Dollar Gamma} \times OI \times \text{Contract Size}$
*(Crucial: Do not hardcode contract size to 1.0. Dynamically fetch `contract_size` from each broker's instrument metadata, as multipliers vary by exchange and instrument.)*

*Note: Without proprietary customer positioning data, this standardized dealer/client assumption is the industry standard for mapping GEX.*

---

## Module 4: Gamma Flip Level Detection
Aggregate the individual contract GEX values to form a chain-wide profile.

### Aggregation & State
- **Total Net GEX**: Sum of all GEX values across the chain.
  - **Positive**: Dealers are Net Long Gamma (Market-stabilizing regime).
  - **Negative**: Dealers are Net Short Gamma (Market-amplifying regime).

### Locating the Gamma Flip
The specific spot price where dealer behavior inverts from stabilizing to amplifying.
1. Group and sum GEX by Strike Price.
2. Sort strikes sequentially.
3. Compute a running sum of GEX from the lowest strike upward.
4. Identify the two adjacent strikes where the running sum crosses zero.
5. Linearly interpolate the spot price between these two strikes to find the exact **Gamma Flip Level**.

### Key Magnet Levels
- **Pin Zone (Clustering)**: Instead of a single max strike, use a clustering algorithm (e.g., K-means or density scan) to find the contiguous band where cumulative positive GEX is densest. This creates the true "magnet effect" zone.
- **Max Long Gamma Strike**: Highest individual positive GEX strike within the Pin Zone.
- **Max Short Gamma Strike**: Highest negative GEX strike (Accelerant / Liquidity void).

---

## Module 5: Signal Generation Logic
Translate GEX data into actionable signals for the trading bot.

### Regime Classification
- **LONG_GAMMA**: Spot > Flip Level. Dealers stabilize price. Mean-reversion strategies favored; momentum/breakout penalized.
- **SHORT_GAMMA**: Spot < Flip Level. Dealers amplify price. Breakout/trend strategies favored; expect volatility expansion.
- **APPROACHING_FLIP**: Spot is within a tight threshold (e.g., 0.5%) of the Flip Level. High-tension zone, risk of rapid regime change.

### API / Output Payload to Bot
```json
{
  "regime": "SHORT_GAMMA",
  "flip_level": 64200.50,
  "pin_zone": {
    "low": 63000,
    "high": 65000,
    "cumulative_gex": 45000000
  },
  "max_long_gamma_strike": 65000,
  "max_short_gamma_strike": 60000,
  "total_net_gex": -8500000,
  "distance_to_flip_pct": 1.2,
  "gex_by_strike": {"60000": -2000000, "65000": 3000000},
  "iv_surface_quality": "PARTIAL"
}
```

---

## Module 6: Expiry Weighting
Proximity to expiry warps gamma distributions (gamma risk converges sharply as $T \to 0$).

### Design Path: Weighted Exclusion (Option A Modified)
- **Exclude 0-1 DTE**: Gamma spikes create erratic, non-directional noise.
- **Exclude > 60 DTE**: Gamma is too flat to induce meaningful active hedging pressure.
- **Aggregate the rest equally**. 

*(Future enhancement: Weight by OI $\times$ Time-Decay factor to smoothly taper near-expiry contracts rather than a hard cutoff.)*

---

## Module 7: Storage and State Management
Track structural market shifts over time.

### Schema per Cycle (Time-Series)
- Timestamp
- Spot Price
- Gamma Flip Level
- Total Net GEX
- Max Long Gamma Strike
- Max Short Gamma Strike
- Derived Regime Classification

### Diagnostics
- **Bullish Structure**: Flip level drifting upwards over time.
- **Bearish Structure**: Flip level drifting downwards.
- **Sudden Skew**: Step-function jumps in the flip level indicate massive institutional block trades setting new boundaries.

---

## Module 8: Bot Integration
GEX is a **context layer**, not an entry signal. It dictates *how* the bot should interpret entirely independent signals (e.g., RSI, funding, order flow).

1. **Regime Filters**:
   - If `LONG_GAMMA`: Disable breakout buys. Increase mean-reversion position sizing.
   - If `SHORT_GAMMA`: Disable mean-reversion. Widen stop-losses for volatility. Enable momentum triggers.
2. **Level-Based Triggers**:
   - Use Flip Level and Max Gamma Strikes as dynamic Support/Resistance.
   - Example: A downward break of the Flip Level accompanied by selling momentum is a high-conviction Short (dealers will sell into the drop to hedge).

---

## Key Assumptions & Systematic Risks

1. **Dealer/Customer Simplification**: The model assumes dealers are indiscriminately short options. If a massive hedge fund buys puts, the assumption holds. If a fund *sells* massive covered calls, the dealer is actually long the call, inverting the local GEX assumed by the model. 
2. **Crypto Liquidity**: Deribit is thinner than SPX. Single massive block trades can immediately distort the GEX profile.
3. **Temporal Decay**: GEX models are highly predictive 0–7 days prior to major quarterly/monthly expiries due to absolute OI concentration. Mid-month, the signal-to-noise ratio is lower.
4. **Vol-Gamma (Vanna) & Charm**: IV changes shift the $\Delta$ and $\Gamma$ surface even if price is static. While computing explicit Vanna/Charm Greeks is acceptable to skip in v1, the engine mitigates this risk by rigorously recalculating GEX on live IV and time updates, not just spot ticks.

---

## Phased Build Order Recommendation

| Phase | Modules | Goal |
|---|---|---|
| **1** | Modules 1 & 2 | **Live Data & Greeks**: Engine correctly ingesting multi-broker data, handling IV staleness, generating BS Greeks. |
| **2** | Modules 3 & 4 | **GEX & Flip Detection**: Accurately mapping dealer profiles, calculating exact flip interpolation, and clustering the Pin Zone. |
| **3** | Modules 5 & 6 | **Signals & Filtering**: Implementing DTE weighting, regime classification, and generating the rich JSON payload. |
| **4** | Modules 7 & 8 | **Storage & Integration**: Tying into the SQLite/TimescaleDB time-series store and executing the regime filter trades via the bot. |
