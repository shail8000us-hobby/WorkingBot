# Delta Exchange India - MV Straddle Research Prompt

## Research Request for Delta Exchange India API Documentation

Please provide detailed information about **MV Straddle** (Market View Straddle) product on Delta Exchange India:

### 1. Product Overview
- What is MV Straddle? Is it a single combined instrument or a strategy?
- How does it combine ATM Call and Put premiums?
- Is it traded as ONE product with a single symbol/ticker?
- How is it different from regular options trading?

### 2. API Endpoints
- What API endpoint is used to fetch MV Straddle products?
  - Is it `/v2/products` with a specific contract_type?
  - What is the contract_type value? (e.g., `mv_straddle`, `straddle_options`, etc.)
- How to get available MV Straddle expirations?
- How to get MV Straddle ticker/price data?
- How to place MV Straddle orders?

### 3. Symbol Format
- What is the symbol format for MV Straddle?
  - Example: `MV-BTC-100000-25JAN26` or different format?
- How does the symbol encode:
  - Underlying asset (BTC/ETH)
  - Strike price
  - Expiry date

### 4. Trading Details
- Can you buy/sell MV Straddle like a single instrument?
- What are the order types supported? (market, limit, stop)
- How is P&L calculated for MV Straddle?
- What are margin requirements?
- Settlement details?

### 5. Market Data Structure
- What does a MV Straddle ticker response look like?
- Does it have combined Greeks or separate?
- How is IV calculated/shown?
- Volume and Open Interest format?

### 6. Example API Response
Please provide example JSON responses for:

**a) Product listing:**
```json
GET /v2/products
// Filter for MV Straddle products
```

**b) Ticker data:**
```json
GET /v2/tickers/{mv_straddle_symbol}
// Current price, greeks, IV, volume
```

**c) Place order:**
```json
POST /v2/orders
// How to structure MV Straddle order
```

### 7. Specific Questions
- Is MV Straddle available for both BTC and ETH?
- Are strikes always ATM or can user select?
- How many expirations are typically available?
- Is there a weekly/monthly pattern?
- What are typical expiry dates (daily, weekly, monthly)?

### 8. UI/UX Requirements
For building a trading interface:
- How should expiry date picker be populated?
- Should strike be auto-selected (ATM) or user-selectable?
- What information should be displayed in the form?
- What validation is needed before order placement?

---

## Current Understanding (TO VERIFY)
Based on user input:
- MV Straddle = Single Delta Exchange India product
- Combines ATM CE + PE premium into one instrument
- NOT a synthetic strategy built from separate options
- Should be traded as a single order, not multi-leg

## Implementation Goal
Build a MV Straddle trading panel that:
1. Lists available MV Straddle expirations
2. Shows current MV Straddle price/premium
3. Allows buy/sell of MV Straddle as single instrument
4. Displays P&L and position management
5. Shows Greeks, IV, and other analytics

---

**Please provide API documentation, example responses, and any other details needed to correctly implement MV Straddle trading on Delta Exchange India.**
