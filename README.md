# WorkingBot GridBot (Delta Exchange)

**Version:** 4.0.0 (Modular Architecture)

---

## 🚨 FOR AI ASSISTANTS & DEVELOPERS

**⚠️ BEFORE MODIFYING THIS CODEBASE:**

1. 📖 **Read [AI_CRITICAL_RULES.md](./AI_CRITICAL_RULES.md)** ← MANDATORY
   - Port configuration rules (5555, 3000)
   - Currency conversion rules (USD→INR)
   - Architecture principles (Backend/Frontend)
   - Common mistakes & solutions

2. 📖 **Read [backend_frontend.md](./backend_frontend.md)**
   - Port conflict prevention
   - Development vs Production workflow
   - Service management commands

3. 📖 **Read [AI_CONTEXT.md](./AI_CONTEXT.md)** ← Full project context
   - Recent changes & refactoring
   - Code structure & patterns
   - Testing & deployment

**Violating the rules in AI_CRITICAL_RULES.md WILL break production!**

---

## Overview

A production-ready, strict rung GridBot designed for Delta Exchange using ccxt. This build emphasizes resilience and safety:
- **Modular architecture** with 7 domain-focused modules (Oct 2025 refactoring)
- Separate public/private API routing with global public fallback
- Robust trade confirmations (falls back to order-status when fills API is unavailable)
- Strict grid with REF-STEP seeding that snaps to nearest rung
- Operational scripts under `dashboard/` for start/status and grid configuration
- **Advanced robustness features for production trading**
- **Multiple layers of capital protection**
- **Self-documenting Web UI with comprehensive inline help**

> **Recent Update:** GridBot strategy refactored from single 3,492-line file into 7 focused modules 
> for better maintainability and testability. See `GRIDBOT_REFACTORING_QUICK_REF.md` for details.

## Core Features
- ✅ Strict rung enforcement with configurable tick/step
- ✅ Seed-at-REF-STEP (snaps to nearest rung; safe if REF off-grid)
- ✅ Heartbeats and health checks with rate-limit awareness
- ✅ Delta-specific error handling (post-only, price band, disruption)
- ✅ Audit pipeline for orders and CSV exports
- ✅ Web UI for configuration and monitoring with **inline help system** 📚
- ✅ Demo/Live mode switching
- ✅ Real-time volatility monitoring (IV/RV from Deribit & Delta)

## Production Robustness Features 🛡️

### Safety Systems
- **Safety Gatekeeper** (11 checks) - Single checkpoint for all order placement
- **Order Confirmation Guard** 🔒 - Prevents double-fills during exchange issues
- **Volatility Safety** 🌊 - Real-time IV/RV monitoring (Deribit + Delta) with auto-trading pause
- **Guardian Bot** - 24/7 position monitoring with auto-liquidation on loss limits
- **Circuit Breaker** - Automatic API failure protection
- **Liquidation Protection** 🚨 - Comprehensive margin & distance monitoring with emergency actions

### Capital Protection (NEW in v3.8.0)
- **Equity Floor** 💎 - Hard stop when equity falls below minimum (e.g., 50k INR)
- **Drawdown Cap** 📉 - Protective mode when 30-day drawdown exceeds limit (e.g., 20%)
- **Two-Man Rule** 👥 - Config change confirmation to prevent impulsive risk increases
- **Exposure Growth Limiter** ⚡ - Prevents flash cascade fills (max tranches/minute)
- **Pending Order Budget** 📊 - Limits total capital at risk in pending orders

### Resilience Features
- **INFINITE UPTIME** 🚀 - Hot grid reload without restarts (NEW!)
- **DYNAMIC IP PROTECTION** 🌐 - Auto-detects IP changes, Telegram alerts, auto-recovery (NEW!)
- **Smart Recovery** - Detects and fixes missing TP orders on restart
- **Smart Gap Fill** - Intelligently fills missing grid levels with maker/taker awareness
- **Heartbeat Monitor** - Dead man's switch (cancels orders if bot crashes)
- **Guardian Hysteresis** - Prevents alert spam with smart thresholds
- **Recovery Audit Tags** - Track order origins for debugging
- **Unified Loss Limits** - Validates consistent risk limits across systems

### Web UI Features (NEW in v3.9.0) 🎨
- **Inline Help System** ❓ - Every config parameter has contextual help with:
  - What it does (detailed explanation)
  - Trading & risk impact analysis
  - Warnings and dependencies
  - Recommended values
  - Markdown-formatted rich text
- **Self-Documenting Interface** - 171/171 parameters documented (100% coverage)
- **Real-Time Volatility Monitor** - Live IV/RV display with safety status
- **Mobile-Responsive** - Desktop tooltips, mobile modals

See **[INLINE_HELP_SYSTEM.md](INLINE_HELP_SYSTEM.md)** for help system documentation.  
See **[ROBUSTNESS_FEATURES.md](ROBUSTNESS_FEATURES.md)** for complete safety documentation.

## Requirements
- Python 3.10+
- `pip install -r requirements.txt`
- A `.env` file with Delta credentials

## Key Environment Variables
- DELTA_API_KEY, DELTA_API_SECRET
- DELTA_PRIVATE_BASE_URL: Private API base (e.g., https://api.india.delta.exchange)
- DELTA_PUBLIC_BASE_URL: Public API base (usually same as private)
- DELTA_PUBLIC_FALLBACK: Global public fallback (default: https://api.delta.exchange)
- GRIDBOT_SYMBOL: Default BTC/USD:USD
- GRIDBOT_LOWER, GRIDBOT_UPPER, GRIDBOT_STEP, GRIDBOT_REF, GRIDBOT_LOT, GRIDBOT_MAX_OPEN

You can also keep grid params in `grid_config.env`; they override `.env` for grid values.

## How to Run
- Use the operational script:
  - `dashboard/start.sh` to start the bot (backgrounded with PID management)
  - `dashboard/status.sh` to check balances/open orders/positions
  - `dashboard/set_grid.sh` to push grid parameters from `grid_config.env`

The bot's main runner is `bot/run.py`. Logs go to `bot/logs/bot.log`.

## Development & CI Guardrails
- Run `scripts/ci_refactor_check.sh` before pushing refactor-related changes. It lint-checks Python, runs mypy, executes pytest smoke tests, compiles imports, performs quick sanity validation, and builds the frontend bundle.
- The GitHub Actions workflow **Refactor Compatibility CI** (`.github/workflows/refactor-ci.yml`) runs on pull requests and pushes to `main`/`master`, mirrors the local script, and publishes a legacy-parameter usage summary.
- Legacy configuration usage currently warns at **12** total hits and fails at **20** via `REFACTOR_COMPAT_WARN` / `REFACTOR_COMPAT_FAIL`. Tweak these env vars locally if you need a different budget for targeted migrations.
- To inspect usage manually, hit `http://localhost:5555/api/diagnostics/config-usage` while the backend is running or run the Python snippet from the workflow to load `get_structured_config(normalize=True)` and print `usage_snapshot()`.

## 🚀 Infinite Uptime (NEW!)

**Change grid parameters WITHOUT restarting the bot!**

### How It Works
1. Bot monitors `grid_config.env` every 5 seconds
2. Detects changes to `GRID_STEP`, `GRID_LOWER`, `GRID_UPPER`, `REFERENCE_LEVEL`
3. Auto-cancels old pending BUY order
4. Rebuilds grid in memory
5. Places new BUY at correct level
6. **NO RESTART REQUIRED!**

### 🚨 CRITICAL ISSUE - STARTUP RECOVERY NOT WORKING

**Problem:** Bot fails to handle missed grids at startup when price has moved past reference levels.

**Status:** Recovery system EXISTS in `bot/strategy/recovery/` but is NOT integrated with the bot.

**Fix Required:** Integrate recovery engines into bot startup flow. See `AI_CONTEXT.md` for details.

---

## 🚀 Quick Start
```bash
# 1. Install PM2 (process manager)
sudo npm install -g pm2

# 2. Start all bots
pm2 start ecosystem.config.js
pm2 save

# 3. Change grid while bot running
nano grid_config.env  # Edit GRID_STEP, etc.
# Bot detects change automatically in 5 seconds!

# 4. Monitor logs
pm2 logs gridbot-demo
```

### Benefits
✅ **Zero downtime** - Change grid anytime  
✅ **Auto-recovery** - Restarts on crashes  
✅ **Memory protection** - Auto-restart at limits  
✅ **No orphaned orders** - Safe BUY cancellation  
✅ **TP orders protected** - Never touched!  

### Documentation
- 📖 `QUICK_START_INFINITE_UPTIME.md` - 2-minute setup guide
- 📚 `INFINITE_UPTIME_SETUP.md` - Complete documentation
- 🧪 `test_grid_hot_reload.sh` - Test script

**Perfect for testing with tight `GRID_STEP=100`!**

## Behavior After Recent Hardening
- Ticker: Falls back to the public-only client when private ticker calls fail.
- Confirmations: If trade history (fills) is not permitted, confirms fills via `fetch_order`.
- Strict seed: Always places a valid seed order snapped to a rung.
- Resilience: Clear logs for endpoint routing and errors; cooldowns on disruptions.

## Troubleshooting
- 401/Unauthorized on fills: Ensure keys are correct; bot will still confirm via order status.
- Ticker 404: Public fallback is used automatically; ensure your DELTA_* base URLs are set correctly.
- Off-grid REF: Set `GRIDBOT_REF` to a rung (multiple of step over tick) or allow snapping.

## Reports
- Orders/trades audit: `audit/order_audit.py` parses `bot/logs/bot.log` to `bot/audit/orders.jsonl` and CSV.
- Last 24h trades: Written to `reports/trades_last_24h.csv` (on demand). You can schedule this if needed.

## Notes
- The bot uses ccxt `delta` with `options.defaultType=future`.
- Lot size is enforced integer on Delta; non-integer values are rounded and logged.
