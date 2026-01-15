# 0DTE Premium Collection Bot - Master Implementation Plan

**Project:** Autonomous Delta-Neutral Strangle System for Delta Exchange India  
**Date:** January 13, 2026  
**Target:** Independent 0DTE options trading automation with minimal existing bot intrusion

---

## 📋 Executive Summary

**Strategy:** Sell equal-premium CE/PE strangles, dynamically rebalance lots to maintain premium parity, roll strikes when premium <₹5, auto-exit when both legs <₹5 or at 5:15 PM IST (before 5:30 PM settlement).

**Capital Required:** ₹2,00,000 - ₹4,00,000 ($2,400-$4,700 USD)  
**Target Returns:** 0.5-1% daily (₹1,000-₹2,000 per cycle)  
**Win Rate Estimate:** 60-70% on non-trending days

---

## 🎯 Core Trading Logic

### Entry Logic
1. User starts bot manually (no time-based auto-start)
2. Fetches current 0DTE option chain (BTC/ETH)
3. Selects ATM ±2-3% strikes where CE premium ≈ PE premium (±10% tolerance)
4. Validates both premiums are ₹15-30 range
5. Places 5-lot sell orders for each leg (maker orders with 2s timeout)
6. Records entry: CE premium × 5 lots, PE premium × 5 lots

### Rebalancing Logic (Every 30 seconds)
```
CE_total = CE_lots × CE_current_premium
PE_total = PE_lots × PE_current_premium

IF abs(CE_total - PE_total) / max(CE_total, PE_total) > 20%:
    IF CE_total < PE_total:
        # CE is cheaper, add CE lots
        additional_CE_lots = (PE_total - CE_total) / CE_current_premium
        BUY additional_CE_lots of CE (reduce short exposure)
    ELSE:
        # PE is cheaper, add PE lots
        additional_PE_lots = (CE_total - PE_total) / PE_current_premium
        BUY additional_PE_lots of PE (reduce short exposure)
```

### Strike Rollover Logic
```
IF CE_current_premium < ₹5:
    # Close existing CE leg
    CLOSE all CE lots (market order)
    
    # Open new CE leg at higher premium
    new_CE_strike = find_strike_with_premium(target=₹20-25, type=CALL)
    new_CE_lots = PE_total / new_CE_premium  # Match PE exposure
    SELL new_CE_lots at new_CE_strike

IF PE_current_premium < ₹5:
    # Close existing PE leg
    CLOSE all PE lots (market order)
    
    # Open new PE leg at higher premium
    new_PE_strike = find_strike_with_premium(target=₹20-25, type=PUT)
    new_PE_lots = CE_total / new_PE_premium  # Match CE exposure
    SELL new_PE_lots at new_PE_strike
```

### Exit Logic
```
# Primary exit condition
IF CE_current_premium < ₹5 AND PE_current_premium < ₹5:
    CLOSE all positions (maker orders with 2s timeout)
    CALCULATE profit = (entry_CE_total + entry_PE_total) - (exit_CE_total + exit_PE_total)
    STOP bot

# Time-based forced exit
IF current_time >= 5:15 PM IST:
    CLOSE all positions (market orders - immediate)
    LOG "Forced exit before settlement"
    STOP bot

# Loss protection
IF unrealized_loss > ₹5,000 OR unrealized_loss > 3 × collected_premium:
    CLOSE all positions (market orders)
    STOP bot
    ALERT user

# Manual exit
IF user clicks "Close All Positions" button:
    CLOSE all positions (market orders)
    STOP bot
```

---

## 📁 Documentation Structure

This implementation is divided into separate documents for clarity:

### **Phase 1: Backend Core Engine**
📄 [ZERO_DTE_PHASE1_BACKEND_CORE.md](ZERO_DTE_PHASE1_BACKEND_CORE.md)
- Core engine architecture
- Premium balancer module
- Strike rollover logic
- Configuration system
- Database schema
- Estimated Duration: **2-3 weeks**

### **Phase 2: Monitoring & Risk Management**
📄 [ZERO_DTE_PHASE2_MONITORING.md](ZERO_DTE_PHASE2_MONITORING.md)
- Real-time monitoring system
- Greeks tracking (Delta, Gamma, Theta, Vega)
- Risk validators
- Guardian integration
- Alert system
- Estimated Duration: **1-2 weeks**

### **Phase 3: WebUI Frontend**
📄 [ZERO_DTE_PHASE3_WEBUI.md](ZERO_DTE_PHASE3_WEBUI.md)
- React dashboard components
- Real-time premium differential display
- Countdown timer to settlement
- Rebalancing history
- Emergency controls
- Estimated Duration: **1-2 weeks**

### **Phase 4: Testing & Deployment**
📄 [ZERO_DTE_PHASE4_TESTING.md](ZERO_DTE_PHASE4_TESTING.md)
- Unit tests
- Integration tests
- Paper trading simulator
- Backtesting framework
- Deployment checklist
- Estimated Duration: **1 week**

### **File Structure & Integration**
📄 [ZERO_DTE_FILE_STRUCTURE.md](ZERO_DTE_FILE_STRUCTURE.md)
- Complete directory structure
- File organization
- Integration points with existing bots
- API endpoints
- Database tables

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ZERO DTE BOT SYSTEM                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ├── BACKEND (Independent Module)
                              │   │
                              │   ├── bot/strategy/zero_dte/
                              │   │   ├── engine.py          (Main orchestrator)
                              │   │   ├── balancer.py        (Premium rebalancing)
                              │   │   ├── rollover.py        (Strike rollover)
                              │   │   ├── monitor.py         (Real-time monitoring)
                              │   │   ├── risk_manager.py    (Risk checks)
                              │   │   └── config.py          (Configuration)
                              │   │
                              │   ├── bot/api/zero_dte_api.py (REST API routes)
                              │   │
                              │   └── Database
                              │       ├── zero_dte_sessions.db    (Session state)
                              │       ├── zero_dte_trades.db      (Trade history)
                              │       └── zero_dte_rebalances.db  (Rebalancing log)
                              │
                              ├── FRONTEND (Independent UI)
                              │   │
                              │   └── webui/frontend/src/components/zero_dte/
                              │       ├── ZeroDTEDashboard.js     (Main panel)
                              │       ├── PremiumGauge.js         (CE vs PE visual)
                              │       ├── CountdownTimer.js       (Time to settlement)
                              │       ├── RebalanceHistory.js     (Activity log)
                              │       ├── ControlPanel.js         (Start/Stop/Close)
                              │       └── PnLTracker.js           (Profit/Loss)
                              │
                              └── CONFIG
                                  └── config/zero_dte_config.yaml (Strategy config)
```

---

## 🔌 Integration Points (Minimal Intrusion)

### 1. Shared Components (READ-ONLY)
- `bot/api/unified_api_client.py` - Delta Exchange API client (no modifications)
- `bot/strategy/options/options_helper.py` - Helper functions (no modifications)
- `config/loader.py` - Config loader (no modifications)

### 2. New API Routes (webui/backend/app.py)
```python
# Add new routes in separate blueprint
from bot.api.zero_dte_api import zero_dte_bp
app.register_blueprint(zero_dte_bp, url_prefix='/api/zero-dte')
```

### 3. Guardian Integration (OPTIONAL)
- Read `guardian_signal.txt` for GO/STOP signal
- Halt 0DTE bot if signal = STOP
- No modifications to guardian_bot.py

### 4. Database Isolation
- Separate SQLite databases (zero_dte_*.db)
- No shared tables with GridBot or existing Options module
- Independent schema

---

## 💰 Capital Requirements & Profitability

### Minimum Capital
| Component | Amount (INR) | Amount (USD) |
|-----------|--------------|--------------|
| 5-lot Strangle Margin | ₹68,000 - ₹1,28,000 | $800 - $1,500 |
| 3× Safety Buffer | ₹2,04,000 - ₹3,84,000 | $2,400 - $4,500 |
| **Recommended Starting Capital** | **₹2,50,000** | **$3,000** |

### Profitability Estimate
```
Entry: Sell 5x CE @ ₹20 + 5x PE @ ₹20 = ₹200 collected
Exit: Buy back 5x CE @ ₹3 + 5x PE @ ₹3 = ₹30 closing cost
Gross Profit: ₹200 - ₹30 = ₹170

Fees:
- Maker rebate on entry: ₹200 × -0.025% = -₹0.05 (profit)
- Maker rebate on exit: ₹30 × -0.025% = -₹0.0075 (profit)
- Net rebate: ₹0.0575

Rebalancing cost (2 rebalances × ₹50 avg): ₹100 × 0.075% × 2 = ₹0.15

Net Profit per Trade: ₹170 - ₹0.15 + ₹0.06 = ₹169.91

ROI on Margin (₹1,00,000 avg): 0.17% per trade
Daily Frequency: 1-2 trades/day (if running continuously)
Monthly Return (20 trades): ~3.4% on margin = ₹3,400
Annual Return (assuming 60% win rate): ~24% on capital
```

---

## ⚠️ Critical Risks & Mitigations

### 1. Directional Risk (Price Moves Sharply)
**Risk:** BTC moves 5% in one direction, one leg loses heavily  
**Mitigation:** 
- Rebalancing adds lots to losing leg (reduces delta)
- Stop loss at ₹5,000 unrealized loss
- Guardian halt at 75% margin utilization

### 2. Gamma Risk (Rapid Delta Changes)
**Risk:** Near expiry, delta swings rapidly on small price moves  
**Mitigation:**
- Monitor gamma exposure
- Force exit 15 min before settlement (5:15 PM)
- Reduce position size in last hour if gamma > threshold

### 3. Liquidity Risk (Wide Spreads at Exit)
**Risk:** Final 15 minutes have 10-20% bid-ask spreads  
**Mitigation:**
- Exit at 5:15 PM, not 5:25 PM
- Use maker orders with 2s timeout
- Monitor spread width, exit early if >10%

### 4. Rollover Execution Risk
**Risk:** Failed to close old strike or open new strike (partial fill)  
**Mitigation:**
- Use saga pattern with rollback
- Close old leg first (smaller risk)
- Verify new leg fill before releasing old leg

### 5. Time Zone Confusion
**Risk:** Mixing IST/UTC, missing 5:30 PM settlement  
**Mitigation:**
- All times in IST (Asia/Kolkata timezone)
- Countdown timer in WebUI
- Auto-exit 15 min before settlement

---

## 📊 Success Metrics

### Key Performance Indicators
| Metric | Target | Measurement |
|--------|--------|-------------|
| Win Rate | >60% | Profitable trades / Total trades |
| Avg Profit per Trade | ₹150-250 | Net profit after fees |
| Max Drawdown | <₹5,000 | Max unrealized loss in session |
| Rebalances per Trade | 2-4 | Frequency of lot adjustments |
| Settlement Timing | 100% before 5:30 PM | Never miss forced exit |
| Execution Quality | <3% slippage | Entry/exit vs expected prices |

### Monitoring Dashboards
1. **Real-time P&L** - Running profit/loss
2. **Premium Differential** - CE vs PE exposure imbalance
3. **Greeks Exposure** - Delta, Gamma, Theta, Vega
4. **Rebalancing Activity** - Timestamp, action, result
5. **Risk Metrics** - Margin utilization, liquidation distance

---

## 🚀 Development Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1: Backend Core** | 2-3 weeks | Working engine, balancer, rollover |
| **Phase 2: Monitoring & Risk** | 1-2 weeks | Real-time monitoring, Greeks tracking |
| **Phase 3: WebUI** | 1-2 weeks | Dashboard, controls, visualizations |
| **Phase 4: Testing** | 1 week | Unit tests, paper trading |
| **Total Estimated Time** | **5-8 weeks** | Production-ready system |

---

## 📚 Next Steps

1. **Read Phase 1 Document** → [ZERO_DTE_PHASE1_BACKEND_CORE.md](ZERO_DTE_PHASE1_BACKEND_CORE.md)
2. **Review File Structure** → [ZERO_DTE_FILE_STRUCTURE.md](ZERO_DTE_FILE_STRUCTURE.md)
3. **Set up development environment** (see Phase 1, Section 1)
4. **Begin implementation** following phase-by-phase approach

---

## 🔗 Quick Links

- [Phase 1: Backend Core](ZERO_DTE_PHASE1_BACKEND_CORE.md) - Core engine and balancer
- [Phase 2: Monitoring & Risk](ZERO_DTE_PHASE2_MONITORING.md) - Real-time monitoring
- [Phase 3: WebUI](ZERO_DTE_PHASE3_WEBUI.md) - Frontend dashboard
- [Phase 4: Testing](ZERO_DTE_PHASE4_TESTING.md) - Testing and deployment
- [File Structure](ZERO_DTE_FILE_STRUCTURE.md) - Complete file organization

---

**Ready to start?** Begin with [Phase 1: Backend Core Implementation](ZERO_DTE_PHASE1_BACKEND_CORE.md)
