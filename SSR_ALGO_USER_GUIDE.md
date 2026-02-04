# SSR ALGO - User Guide

## Overview

SSR ALGO (Smart Strategy Rebalancing Algorithm) is an automated trading engine for a **Modified Iron Butterfly with Protective Wings** strategy. It's designed for cryptocurrency options (BTC/ETH) on Delta Exchange.

### Strategy Summary

- **Structure**: Modified Iron Butterfly with protective wings (8 legs total)
- **Ratio**: 1:2:1 (1 far OTM, 2 ATM, 1 OTM on each side)
- **Selection**: Percentage-based OTM strike selection
- **Auto-Adjustment**: Triggers when price hits max loss zones for 10 minutes

---

## Quick Start

### 1. Open SSR ALGO Dashboard

In the WebUI, click on **🦋 SSR ALGO** in the left sidebar.

### 2. Configure a New Session

| Field | Description | Default |
|-------|-------------|---------|
| **Underlying** | BTC or ETH | BTC |
| **Expiry** | Options expiration date | First available |
| **Auto Loop Rounds** | Number of butterfly entries (1-10) | 2 |
| **Order Type** | SSR (smart), Maker, or Market | SSR |
| **Start Time** | When monitoring begins (UTC) | 15:00 |
| **End Time** | When monitoring ends (UTC) | 21:00 |

### 3. Preview Strikes

Click **Preview** to see which strikes will be selected before creating the session. This shows:
- ATM strike (lowest CE-PE premium difference)
- OTM buy strikes (45-49% of ATM premium)
- Far OTM sell strikes (20-30% of OTM buy premium)

### 4. Create Session

Click **Start SSR ALGO** to:
1. Create a new session
2. Select strikes automatically
3. Execute auto-loop rounds
4. Begin price monitoring

---

## Strike Selection Logic

### ATM Strike Detection

The algorithm finds the ATM strike by:
1. Fetching live option chain data
2. Finding the strike where |CE_premium - PE_premium| is minimum
3. This represents the true ATM regardless of spot price

### OTM Buy Strikes (45-49% of ATM)

For the "wings" of the butterfly:
- **OTM Call Buy**: First strike above ATM with premium between 45-49% of ATM CE premium
- **OTM Put Buy**: First strike below ATM with premium between 45-49% of ATM PE premium

### Far OTM Sell Strikes (20-30% of OTM Buy)

For cost reduction and extended protection:
- **Far OTM Call Sell**: Premium 20-30% of OTM CE buy premium
- **Far OTM Put Sell**: Premium 20-30% of OTM PE buy premium

---

## Position Structure

Each butterfly entry creates 8 legs:

```
             Far OTM CE Sell (-1)
                    │
                    ▼
             OTM CE Buy (+1)
                    │
                    ▼
    ┌───────────────┴───────────────┐
    │        ATM CE Sell (-2)       │
    │        ATM PE Sell (-2)       │
    └───────────────┬───────────────┘
                    │
                    ▼
             OTM PE Buy (+1)
                    │
                    ▼
             Far OTM PE Sell (-1)
```

### Example Position

For BTC at $100,000:
- Far OTM Call Sell: 108000 CE x -1
- OTM Call Buy: 103000 CE x +1
- ATM Call Sell: 100000 CE x -2
- ATM Put Sell: 100000 PE x -2
- OTM Put Buy: 97000 PE x +1
- Far OTM Put Sell: 92000 PE x -1

---

## Auto-Adjustment System

### Max Loss Zone Detection

The algorithm calculates the payoff curve and identifies:
- **Upper Max Loss Zone**: Price above ATM where losses peak
- **Lower Max Loss Zone**: Price below ATM where losses peak

### Dwell Time Trigger

When price enters a max loss zone:
1. Timer starts counting
2. If price stays in zone for **10 minutes continuously**
3. Auto-adjustment is triggered
4. New butterfly is entered at the new ATM

### Adjustment Actions

When triggered:
1. New butterfly is placed at current price levels
2. Existing positions remain (no closing)
3. Combined position has adjusted risk profile
4. Session continues monitoring

---

## Session States

| Status | Description |
|--------|-------------|
| **IDLE** | Session created, not started |
| **SELECTING_STRIKES** | Fetching chain and selecting strikes |
| **EXECUTING_AUTO_LOOP** | Placing orders for butterfly legs |
| **MONITORING** | Active monitoring for price movements |
| **PAUSED** | Temporarily paused (can resume) |
| **ADJUSTING** | Executing auto-adjustment |
| **STOPPED** | Manually stopped or completed |
| **ERROR** | Error occurred |

---

## Session Controls

### From Session Card

- **▶️ Start**: Begin execution (from IDLE)
- **⏸️ Pause**: Pause monitoring (from MONITORING)
- **▶️ Resume**: Resume monitoring (from PAUSED)
- **⏹️ Stop**: Stop session completely
- **🗑️ Delete**: Remove session (STOPPED only)

### Best Practices

1. **Preview First**: Always preview strikes before creating a session
2. **Start Small**: Begin with 1-2 rounds to understand the behavior
3. **Set Time Window**: Configure start/end times to your trading hours
4. **Monitor Dashboard**: Keep the dashboard open to observe adjustments

---

## Payoff Chart

The interactive payoff chart shows:
- **X-axis**: Underlying price range (±20% of current)
- **Y-axis**: P&L at expiry
- **Green area**: Profit zone
- **Red area**: Loss zone
- **Vertical lines**: Max loss price points
- **Current price**: Highlighted on chart

---

## Advanced Configuration

Click **"Show Strike Selection Settings"** to customize:

### OTM Buy Range (45-49%)

Adjust where "wings" are placed:
- **Higher %** (e.g., 50-55%): Strikes closer to ATM, higher premium
- **Lower %** (e.g., 40-44%): Strikes further from ATM, lower premium

### Far OTM Sell Range (20-30%)

Adjust protective wing coverage:
- **Higher %** (e.g., 30-40%): More premium collected, wider protection
- **Lower %** (e.g., 15-20%): Less premium collected, narrower protection

---

## Troubleshooting

### "No strikes found in range"

**Cause**: Current option chain doesn't have strikes matching the percentage criteria.

**Solutions**:
1. Try a different expiry (closer dates have more liquid strikes)
2. Expand the percentage ranges in advanced settings
3. Check if the market is open and chain is loading

### "Failed to fetch chain data"

**Cause**: API connection issue or market data unavailable.

**Solutions**:
1. Check internet connection
2. Verify backend is running
3. Wait for market to open

### Session stuck in "EXECUTING"

**Cause**: Order fills taking longer than expected.

**Solutions**:
1. Switch order type to "Market" for faster fills
2. Check position panel for partially filled orders
3. Stop and restart with different settings

---

## API Endpoints

For developers integrating with SSR ALGO:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ssr-algo/sessions` | GET | List all sessions |
| `/api/ssr-algo/sessions` | POST | Create new session |
| `/api/ssr-algo/sessions/{id}` | GET | Get session details |
| `/api/ssr-algo/sessions/{id}/start` | POST | Start session |
| `/api/ssr-algo/sessions/{id}/stop` | POST | Stop session |
| `/api/ssr-algo/preview` | POST | Preview strike selection |

---

## Version History

- **v1.0** (Feb 2026): Initial release with full butterfly automation
- Core strike selection engine
- Auto-loop execution
- Price monitoring with dwell triggers
- Payoff visualization

---

*For support or feature requests, contact the development team.*
