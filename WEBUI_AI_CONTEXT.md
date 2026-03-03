# WebUI — AI Context & Architecture Reference

> **Single source of truth** for the GridBot WebUI. Use this document whenever improving, debugging, or extending the WebUI frontend or backend.
>
> Last verified: **March 2, 2026** — build passes, all budgets met, all optimizations confirmed.

---

## Table of Contents

1. [Quick Reference](#1-quick-reference)
2. [Architecture Overview](#2-architecture-overview)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Architecture](#4-backend-architecture)
5. [Performance Optimizations (Completed)](#5-performance-optimizations-completed)
6. [Bundle Budget & Metrics](#6-bundle-budget--metrics)
7. [State Management](#7-state-management)
8. [Routing & Navigation](#8-routing--navigation)
9. [Real-Time Communication](#9-real-time-communication)
10. [Caching Strategy](#10-caching-strategy)
11. [Service Worker](#11-service-worker)
12. [Deployment & Operations](#12-deployment--operations)
13. [Key Files Reference](#13-key-files-reference)
14. [Component Inventory](#14-component-inventory)
15. [API Endpoints](#15-api-endpoints)
16. [Common Tasks & Patterns](#16-common-tasks--patterns)
17. [Known Constraints & Gotchas](#17-known-constraints--gotchas)
18. [Optimization History](#18-optimization-history)

---

## 1. Quick Reference

| Item | Value |
|------|-------|
| **Frontend** | React 18.2 + CRA + react-app-rewired |
| **Backend** | Flask + Flask-SocketIO (threading mode) |
| **Port** | `5555` (backend serves built React app) |
| **URL** | `http://localhost:5555/#/dashboard` |
| **Routing** | `HashRouter` (react-router-dom 6.30) |
| **State** | Zustand 5.0 (global) + React Context (providers) |
| **Styling** | TailwindCSS 3.4 + MUI 5.14 + @emotion |
| **Build** | `cd webui/frontend && npm run build` |
| **Dev** | `cd webui/frontend && npm start` (proxy → :5555) |
| **Backend start** | `python3 webui/backend/app.py` |
| **LaunchAgent** | `com.gridbot.production.webui` |
| **Python** | `.venv/bin/python` (3.12) |
| **Main bundle** | 144KB raw / 40KB gzip |
| **Total JS** | 3,628KB across 60 files |

### Quick Commands

```bash
# Build frontend
cd webui/frontend && npm run build

# Start backend (foreground)
cd /Users/ssr/Projects/WorkingBot && python3 webui/backend/app.py

# Restart via LaunchAgent
launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui

# Check bundle sizes manually
cd webui/frontend && npm run check-budget

# Analyze bundle composition
cd webui/frontend && npm run analyze
```

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (React 18)                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐  │
│  │ HashRouter│  │ Zustand   │  │ Socket.IO Client     │  │
│  │ 24 pages  │  │ Store     │  │ RobustConnectionMgr  │  │
│  │ lazy-load │  │ (persist) │  │ + Circuit Breaker    │  │
│  └──────────┘  └───────────┘  └──────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Service Worker (cache-first static, network-first API)││
│  └──────────────────────────────────────────────────────┘│
└────────────────────────┬────────────────────────────────┘
                         │ HTTP + WebSocket
┌────────────────────────▼────────────────────────────────┐
│              Flask Backend (:5555)                        │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────────────┐│
│  │ 70 Blue- │ │ Flask-   │ │ Background Services:      ││
│  │ prints   │ │ Caching  │ │  • Health checker (5s)    ││
│  │ (~70     │ │ (Simple  │ │  • Volatility (30s)       ││
│  │  routes) │ │  Cache)  │ │  • SL/TP monitor (5s)     ││
│  └──────────┘ └──────────┘ │  • Max loss monitor       ││
│  ┌──────────┐ ┌──────────┐ │  • Take profit monitor    ││
│  │ Brotli   │ │ SocketIO │ │  • Delta price WS         ││
│  │ Compress │ │ threading│ │  • Cache warmer           ││
│  └──────────┘ └──────────┘ └───────────────────────────┘│
│  Serves: ../frontend/build/ (React production build)     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Frontend Architecture

### 3.1 Entry Point & Provider Tree

```
React.StrictMode
  └── ErrorBoundary
       └── AppProviders (src/context/AppProviders.js)
            ├── ThemeModeProvider     — dark/light mode
            ├── SystemStatusProvider  — global warnings
            ├── NotificationProvider  — toast notifications
            ├── KeyboardProvider      — keyboard shortcuts
            ├── InstanceProvider      — multi-instance bot selection
            └── SymbolProvider        — active trading symbol
                 └── HashRouter
                      └── App
                           └── AutoloopProvider (stays in App — used by always-visible AutoloopStatusBar)
                                └── Layout + Routes
```

**Key files:**
- `src/index.js` (46 lines) — mounts Root, registers service worker
- `src/context/AppProviders.js` (64 lines) — flat composite of 6 providers
- `src/App.js` (~430 lines) — layout shell, 25 lazy imports, hooks, routes

### 3.2 Layout Structure

```
┌────────────────────────────────────────────────┐
│ TopBar (fixed z-40 bg-slate-900)               │
├────────────────────────────────────────────────┤
│ SymbolContextBar (sticky z-30)                 │
├──────────┬─────────────────────────────────────┤
│ Sidebar  │ <main> (relative z-0)               │
│ (fixed   │   pt-60 lg:pt-56 (below TopBar)     │
│  z-[38]  │   <Routes>                          │
│  bg-     │     24 lazy-loaded pages             │
│  slate-  │   </Routes>                         │
│  950)    │                                     │
├──────────┴─────────────────────────────────────┤
│ AutoloopStatusBar (always visible)             │
│ FloatingPriceWidget (lazy, Suspense null)      │
└────────────────────────────────────────────────┘
```

**CSS root** (in `public/index.html`):
```css
#root { display: flex; flex-direction: column; width: 100%; }
#root > * { width: 100%; }
```

### 3.3 Pages (24 lazy-loaded routes)

| Page | Route | Notes |
|------|-------|-------|
| DashboardPage | `/dashboard` | Default, 6 inner lazy panels |
| OptionsPage | `/options` | Options trading |
| PositionsPage | `/positions` | Virtual scroll >20 items |
| MMMPage | `/mmm` | Money Mind & Method 0DTE |
| SSRAlgoPage | `/ssr_algo` | Butterfly adjustment algo |
| RSIPage | `/rsi` | RSI strategy |
| PortfolioPage | `/portfolio` | Portfolio overview |
| TodosPage | `/todos` | Task management |
| TradingViewPage | `/tradingview` | TradingView integration |
| ZeroDTEPage | `/zero_dte` | Zero DTE strangle |
| SystemHealthPage | `/system_health` | System diagnostics |
| ExperimentalPage | `/experimental` | Auto-delta hedging |
| AdvancedFeaturesPage | `/advanced_features` | Advanced features |
| MVStraddlePage | `/mv_straddle` | MV Straddle product |
| RiskPage | `/risk` | 7 inner lazy panels |
| IntelligencePage | `/intelligence` | 4 inner lazy panels |
| OptionsChainPage | `/options_chain` | Options chain viewer |
| StrategyBuilderPage | `/strategy_builder` | Multi-leg builder |
| GuardianPage | `/guardian` | Position guardian |
| MLTradingPage | `/ml_trading` | 6 inner lazy panels |
| BotManagementPage | `/botmanagement` | Bot control |
| EmergencyPage | `/emergency` | Emergency controls |
| MonitoringPage | `/monitoring` | System monitoring |
| ConfigPage | `/config` | Configuration editor |

**Pages with inner lazy panels** (progressive loading): Dashboard (6), Risk (7), MLTrading (6), Intelligence (4), Config (3), BotManagement (3), Emergency (2), Monitoring (2)

**Pages with direct imports** (single chunk, instant render): Options, Positions, MMM, SSRAlgo, RSI, Portfolio, Todos, TradingView, ZeroDTE, SystemHealth, Experimental, AdvancedFeatures, MVStraddle, OptionsChain, StrategyBuilder, Guardian

### 3.4 Custom Hooks (used in App.js)

| Hook | Purpose |
|------|---------|
| `useThemeMode` | Dark/light mode toggle |
| `useSystemStatus` | Global system status & warnings |
| `useIsMobile` | Responsive breakpoint detection |
| `useLatencyTracker` | Connection latency measurement |
| `useBotControl` | Start/stop/restart bot |
| `useSocketConnection` | WebSocket lifecycle management |
| `useConfigManager` | Config CRUD + initial data fetch |
| `useConnectionActions` | Hard refresh, cache clear |
| `useAppEventListeners` | Global keyboard/custom events |
| `useTradingData` | Positions, PnL, bot status |
| `useFeatureFlag` | Feature flag checks |

### 3.5 Key Dependencies

| Category | Libraries |
|----------|-----------|
| UI | `@mui/material` 5.14, `@mui/icons-material`, `@emotion/react` |
| State | `zustand` 5.0.8 |
| Routing | `react-router-dom` 6.30.3 |
| Charts | `recharts` 2.9 |
| Code Editor | `@monaco-editor/react` 4.7, `monaco-editor` 0.54 |
| Realtime | `socket.io-client` 4.8.1 |
| HTTP | `axios` 1.6 |
| Virtual Scroll | `react-window` 2.2.7 |
| Validation | `zod` 3.25 |
| DnD | `@dnd-kit/core` 6.3, `@dnd-kit/sortable` 10.0 |
| Markdown | `react-markdown` 10.1, `remark-gfm` 4.0 |
| YAML | `js-yaml` 4.1 |
| Styling | TailwindCSS 3.4, `clsx` 2.1 |
| Fonts | `@fontsource-variable/inter`, `@fontsource-variable/roboto-mono` |

**Dev tools:** react-app-rewired, customize-cra, ESLint, Prettier, Husky, lint-staged, TypeScript 5.4, source-map-explorer, compression-webpack-plugin, Storybook 7.6

### 3.6 Webpack Configuration (config-overrides.js)

**170 lines.** Production-only optimizations via react-app-rewired:

**7 chunk splitting groups:**

| Group | Contents | Priority |
|-------|----------|----------|
| `vendor` | react, react-dom, react-router | 40 |
| `uiLibs` | @mui, @emotion | 30 |
| `charts` | recharts, reactflow, dagre | 30 |
| `editors` | monaco-editor | 30 |
| `icons` | lucide-react, @mui/icons-material | 25 |
| `utils` | axios, socket.io-client, zustand, zod, clsx | 20 |
| `defaultVendors` | remaining node_modules | 10 |

**Other production optimizations:**
- TerserPlugin: strips `console.log` and `console.debug` (keeps warn/error)
- Gzip compression for files >10KB
- No source maps in production
- Moment.js locale stripping
- Scope hoisting (`concatenateModules`)
- 500KB asset/entrypoint warning threshold

**Development:** async-only split chunks for faster rebuilds.

---

## 4. Backend Architecture

### 4.1 Stack

| Component | Detail |
|-----------|--------|
| **Framework** | Flask |
| **Realtime** | Flask-SocketIO (`async_mode='threading'`) |
| **Compression** | Flask-Compress (Brotli → gzip → deflate) |
| **Caching** | Flask-Caching (SimpleCache, 500 items, 300s default) |
| **CORS** | Flask-CORS (origins from config.yaml) |
| **Logging** | RotatingFileHandler (10MB, 3 backups → `logs/backend_fixed.log`) |
| **Config** | `config.loader.get_config()` → YAML single source of truth |
| **Credentials** | `secrets/api_keys.env` |
| **Static** | Serves `../frontend/build` (React production build) |
| **Instance Lock** | `WebUIInstanceLock` — prevents duplicate processes |

### 4.2 Blueprints (70 registered)

The backend registers ~70 Flask blueprints from `webui/backend/routes/`. Major groups:

| Group | Blueprints |
|-------|------------|
| **Core** | yaml_config, resolved_state, utility, health, logs, system, monitor |
| **Trading** | positions, orders, pnl, bot_control, trades, market, ticker |
| **Options** | options_control, dashboard, groups, options_chain, options_strategy |
| **Futures** | futures, futures_trading, futures_max_loss |
| **Strategies** | mmm, ssr_algo, mv_straddle, zero_dte, strategy, kelly |
| **Risk** | risk, capital, emergency, liquidation, position_liquidation, unified_safety |
| **ML/AI** | ml_trading, prediction, ai, claude, dynamic_brain, brain_analyzer |
| **System** | guardian, pm2, monitoring, production_monitoring, system_health, recovery, reconciliation |
| **UI** | todos, settings, file_manager, mode_switcher, instance_manager, code_explainer, frontend_error |
| **Integration** | tradingview_webhook, alerts, delta_data, websocket_api |
| **Analytics** | analytics, performance, chart, backtest, metrics, docs |

### 4.3 Background Services (started in `__main__`)

| Service | Interval | Purpose |
|---------|----------|---------|
| Health Checker | 5s | Bot, guardian, telegram status |
| Volatility Collector | 30s | Delta Exchange IV polling, backfills 90 days |
| SL/TP Monitor | 5s | Options stop-loss / take-profit |
| Max Loss Monitor | continuous | Per-strike/expiry loss limits |
| Take Profit Monitor | continuous | Per-strike profit targets (2s stagger after SL/TP) |
| Delta Price WebSocket | streaming | BTC & ETH real-time feeds via `wss://socket.india.delta.exchange` |
| Cache Warmer | startup only | Pre-warms 5 critical endpoints |

### 4.4 Request Metrics

- `@app.before_request` records `request._start_time`
- `@app.after_request` computes latency, logs to SQLite via `metrics_logger`
- High-frequency endpoints are exempted from metric logging: `/api/health`, `/api/bot/status`, `/api/pnl/summary`, `/api/positions`, `/api/orders`

### 4.5 Error Handling

| Handler | Behavior |
|---------|----------|
| 404 | JSON: `{"error": "Not found", "path": "..."}` |
| 500 | JSON: `{"error": "Internal server error"}` |
| Global Exception | Prints traceback, returns 500 JSON |
| API 404 | Paths starting with `/api/` return 404 (not caught by React catch-all) |

---

## 5. Performance Optimizations (Completed)

All optimizations from the V2 plan have been implemented. Summary:

| Phase | What | Result | Status |
|-------|------|--------|--------|
| 2.1–2.4 | App.js decomposition | 1,754 → 425 lines (76% reduction) | ✅ |
| 5.1 | chart.js → Recharts | Vendors: 216 → 145KB (-33%) | ✅ |
| 5.2 | framer-motion eliminated | ~38KB saved | ✅ |
| 5.3 | uuid → crypto.randomUUID() | ~3KB saved | ✅ |
| 5.4 | MUI icon imports audit | Tree-shaking + icons chunk handles it | ✅ Verified |
| 6.0 | AppWrapper.js deleted | Dead code removed | ✅ |
| 6.2 | Provider consolidation | AppProviders.js — 6 providers flat, index.js 73→46 lines | ✅ |
| 6.3 | Context update frequency | SystemStatusContext already optimized (useCallback/useMemo) | ✅ Verified |
| 7.1 | Backend caching (11+ endpoints) | Faster API responses | ✅ |
| 7.1+ | MMM sessions SQLite json_extract() | 10.8s → 0.2s (54x faster) | ✅ |
| 7.2 | bot/status cache + Python 3.9 fix | 283ms → 2ms (142x faster) | ✅ |
| 7.3 | Browser Cache-Control headers | 3 tiers: config 60s, trading 5s, health no-store | ✅ |
| 8.1 | Virtual scroll PositionsPanel | react-window v2 for >20 positions | ✅ |
| 8.2 | Virtual scroll LogsPanel | react-window v2 always-on (28px rows) | ✅ |
| 8.3 | Virtual scroll OptionsChain | Deferred — MUI Table incompatible with react-window | ⏭️ |
| 9 | React re-render optimization | 35 components memoized, Zustand selectors clean | ✅ |
| 10.1 | Resource hints + critical CSS | Faster FCP | ✅ |
| 10.2 | Brotli compression | ~20% smaller responses | ✅ |
| 10.3 | Static asset caching (1yr) | Instant repeat visits | ✅ |
| 10.4 | Bundle budget enforcement | Auto postbuild check, 4 budgets | ✅ |
| 11 | Monitoring & regression prevention | Budget + review scripts, perf monitor | ✅ |
| 12 | Route-based code splitting | HashRouter, 24 lazy pages, 60 chunks | ✅ |
| 13 | Zustand store splitting | Skipped — only 1 consumer, near-zero impact | ⏭️ |
| 14 | Perceived speed fixes | No double-lazy, real prefetch, instant tabs | ✅ |
| 15 | Service Worker | cache-first static, network-first API (3s timeout) | ✅ |
| 16 | HTTP/2 + nginx | Skipped — localhost only | ⏭️ |

---

## 6. Bundle Budget & Metrics

### Current Metrics (March 2026)

| Metric | Value | Budget | Usage |
|--------|-------|--------|-------|
| Main bundle (raw) | 144KB | 195KB | 74% |
| Main bundle (gzip) | 40KB | 58KB | 69% |
| Largest chunk | 371KB | 976KB | 38% |
| Total JS | 3,628KB (60 files) | 4,882KB | 74% |

### Budget Enforcement

- Script: `webui/frontend/scripts/check-bundle-size.sh` (155 lines)
- Runs automatically as `postbuild` hook on every `npm run build`
- Exits with code 1 if any budget exceeded → blocks deployment
- Manual check: `npm run check-budget`
- Bundle analysis: `npm run analyze` (source-map-explorer)

### Historical Progress

```
Before optimization:  1,146KB total (vendors: 216KB)
After Phase 5:          994KB total (vendors: 145KB)  — -13.2%
After Phase 12:      ~3,770KB total (main: 190KB → 148KB + 67 lazy chunks)
After Phase 14:       3,618KB total (main: 144KB, 60 files)
Current:              3,628KB total (main: 144KB, 60 files)
```

---

## 7. State Management

### 7.1 Zustand Store (`src/store/index.js` — 350 lines)

Single store with `devtools` + `persist` middleware.

**State shape:**
```
positions, orders, pnl, config, configMeta, health,
botStatus, connection, warnings, lastUpdate, isLoading, error
```

**Persistence:** Only `config` and `lastUpdate` saved to `localStorage` (key: `webui-storage`)

**Selector hooks** (prevent unnecessary re-renders):
`usePositions`, `useOrders`, `useHealth`, `useConfig`, `usePnL`, `useLoading`, `useError`, `useLastUpdate`, `useStoreActions`

### 7.2 React Context Providers

| Context | File | Purpose |
|---------|------|---------|
| ThemeModeProvider | (in AppProviders) | Dark/light mode |
| SystemStatusProvider | `SystemStatusContext.js` | Bot status warnings (fully memoized) |
| NotificationProvider | (in AppProviders) | Toast notifications |
| KeyboardProvider | (in AppProviders) | Shortcuts → CustomEvents on window |
| InstanceProvider | `InstanceContext.js` | Multi-instance bot selection (19+ consumers) |
| SymbolProvider | `SymbolContext.js` | Active trading symbol |
| AutoloopProvider | `AutoloopContext.js` | In App.js (used by always-visible StatusBar) |
| IdleContext | `IdleContext.js` | Idle detection |
| MobileOptimizationContext | `MobileOptimizationContext.js` | Dead — only consumer commented out |

---

## 8. Routing & Navigation

- **Router:** `HashRouter` from react-router-dom 6.30
- **URL format:** `http://localhost:5555/#/options`
- **Navigation:** `useNavigate()` with `startTransition` (React 18 concurrent)
- **Active section:** Derived from `useLocation().pathname`
- **Deep linking:** Full support (browser back/forward, direct URL access)
- **Prefetch strategy:**
  - **Hover:** `pagePrefetch.js` → calls actual `import()` matching React.lazy definitions
  - **Idle (5s):** `prefetchAllPages()` → staggers all 24 page imports at 150ms intervals
  - After ~8s idle, every tab switch is instant (chunk already cached by browser)

---

## 9. Real-Time Communication

### 9.1 WebSocket (Socket.IO)

**Server config:**
```python
SocketIO(app, cors_allowed_origins="*", async_mode='threading',
         ping_timeout=60, ping_interval=25, max_http_buffer_size=1000000)
```

**Client-side handlers:**
- `RobustConnectionManager.js` — resilient reconnection
- Circuit breaker pattern (`circuitBreaker.ts`)
- `centralPollingManager.ts` — centralized polling coordination

**Server events emitted:**

| Event | Description |
|-------|-------------|
| `connected` | Connection confirmation |
| `log_entry` | Single real-time log line |
| `log_batch` | Batched log lines (up to 50) |
| `pong` | Latency measurement response |
| `market_price_update` | BTC/ETH real-time prices |
| `options_subscribed` | Options ticker subscription confirmed |
| `volatility_halt_status` | Halt status response |
| `recovery_history/stats/config` | Recovery system data |

**Client events listened for (server-side):**

| Event | Purpose |
|-------|---------|
| `connect` | Start log tailer, send last 30 lines |
| `disconnect` | Cleanup |
| `ping` | Latency measure → emits `pong` |
| `subscribe_options_tickers` | Subscribe to bid/ask via Delta WS |
| `unsubscribe_options_tickers` | Unsubscribe |
| `get_halt_status` | Request halt status |
| `get_recovery_*` | Recovery system queries |
| `update_recovery_config` | Write recovery config |

**Additional SocketIO integrations:**
- TradingView: `init_tradingview_socketio(socketio)`
- MMM: `init_mmm_websocket(socketio)`
- Take Profit: `init_tp_socketio(socketio)`
- Delta Prices: `start_price_service(socketio)` → broadcasts `market_price_update`

---

## 10. Caching Strategy

### 10.1 Server-Side (Flask-Caching)

| Setting | Value |
|---------|-------|
| Backend | `SimpleCache` (in-memory dict) |
| Default timeout | 300s |
| Max items | 500 |
| Cache key | `request.path` + `instance` + `symbol` + `mode` query params |

**Timeout tiers:**

| Key | TTL |
|-----|-----|
| `health` | 2s |
| `positions` | 5s |
| `logs` | 5s |
| `todos` | 10s |
| `market` | 10s |
| `analytics` | 30s |
| `config` | 60s |
| `static` | 300s |

**Cache pre-warming** (startup thread hits 5 endpoints): `bot/status`, `options/dashboard`, `mmm/sessions?summary=true`, `positions`, `config/flat`

### 10.2 Browser Cache-Control Headers (Flask after_request)

| Endpoint Category | Cache-Control |
|-------------------|---------------|
| Config (`/api/config/flat`, `/api/flags`, `/api/feature_flags`, `/api/options/expiries`, `/api/options/strategy/templates`) | `public, max-age=60, stale-while-revalidate=120` |
| Trading data (`/api/positions`, `/api/orders`, `/api/pnl/summary`, `/api/options/dashboard`, `/api/options/positions`, `/api/trading_status`, `/api/logs`) | `public, max-age=5, stale-while-revalidate=10` |
| Health (`/api/health`, `/api/bot/status`) | `no-store` |
| Default GET (`/api/*`) | `public, max-age=10, stale-while-revalidate=30` |
| Mutations (POST/PUT/DELETE/PATCH) | `no-store` |
| Hashed static assets (`main.abc123.js`) | `public, max-age=31536000, immutable` |
| `index.html` / non-hashed | `no-cache, must-revalidate` |

### 10.3 API Performance (Verified)

| Endpoint | Cold | Cached | Speedup |
|----------|------|--------|---------|
| `/api/config/flat` | 58ms | 5ms | 12x |
| `/api/bot/status` | 283ms | 2ms | 142x |
| `/api/positions` | 2,081ms | 2ms | 1,041x |
| `/api/options/positions` | 2,180ms | 2ms | 1,090x |
| `/api/options/dashboard` | 3,500ms | 4ms | 875x |
| `/api/mmm/sessions` | 10,800ms | 200ms | 54x |

---

## 11. Service Worker

### Files
- `public/sw.js` (101 lines) — the service worker
- `src/serviceWorkerRegistration.js` (62 lines) — registration utility
- Registered in `src/index.js` on app mount

### Caching Strategies

| Resource | Strategy | Details |
|----------|----------|---------|
| `/static/*` (hashed JS/CSS) | Cache-first | Immutable, cached indefinitely |
| `/api/*` | Network-first | 3s timeout, falls back to cache for offline |
| HTML & other | Network-first | Cache fallback on fetch failure |
| WebSocket / mutations | Skipped | Not cached |

### Behavior
- `CACHE_VERSION = 'gridbot-v1'` → two caches: `gridbot-v1-static`, `gridbot-v1-api`
- `skipWaiting()` on install for immediate activation
- Cleans old `gridbot-*` caches on activate
- Listens for `SKIP_WAITING` message from app
- Auto-checks for updates every 30 minutes

### Unregistering
```javascript
import { unregister } from './serviceWorkerRegistration';
unregister();
```
Or visit: `http://localhost:5555/unregister-sw.html`

---

## 12. Deployment & Operations

### LaunchAgent Configuration

**File:** `~/Library/LaunchAgents/com.gridbot.production.webui.plist`

| Setting | Value |
|---------|-------|
| Program | `.venv/bin/python webui/backend/app.py` |
| WorkingDirectory | `/Users/ssr/Projects/WorkingBot` |
| RunAtLoad | true |
| KeepAlive | true |
| ThrottleInterval | 10s |
| Stdout | `logs/webui_production.log` |
| Stderr | `logs/webui_production_error.log` |
| PYTHONUNBUFFERED | 1 |

**Only one WebUI LaunchAgent** should exist. Conflicting services were disabled previously.

### Management Commands

```bash
# Check if running
launchctl list | grep gridbot

# Restart backend (picks up new code + build)
launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui

# Stop
launchctl bootout gui/$(id -u)/com.gridbot.production.webui

# Start
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gridbot.production.webui.plist

# View logs
tail -f logs/webui_production.log
tail -f logs/webui_production_error.log
```

### Deployment Workflow

1. Make code changes
2. `cd webui/frontend && npm run build` (validates budgets automatically)
3. `launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui`
4. Verify at `http://localhost:5555`

---

## 13. Key Files Reference

### Frontend

| File | Lines | Purpose |
|------|-------|---------|
| `src/index.js` | 46 | Entry point, provider mount, SW registration |
| `src/App.js` | ~430 | Layout shell, 25 lazy imports, routes, hooks |
| `src/context/AppProviders.js` | 64 | Consolidated 6-provider wrapper |
| `src/store/index.js` | 350 | Zustand store (state + actions + selector hooks) |
| `config-overrides.js` | 170 | Webpack chunk splitting, Terser, gzip |
| `scripts/check-bundle-size.sh` | 155 | Bundle budget enforcement |
| `public/sw.js` | 101 | Service worker |
| `src/serviceWorkerRegistration.js` | 62 | SW registration utility |
| `src/utils/pagePrefetch.js` | — | Prefetch all lazy pages via import() |
| `src/utils/performanceMonitor.js` | 491 | Render, API, memory, page-load tracking |
| `src/utils/RobustConnectionManager.js` | — | Resilient WebSocket connection |
| `src/components/layout/TopBar.js` | — | Fixed top navigation bar |
| `src/components/layout/Sidebar.js` | — | Fixed sidebar navigation |
| `src/components/layout/SymbolContextBar.js` | — | Symbol context switching bar |
| `src/components/layout/MobileNav.js` | — | Mobile navigation |
| `src/components/LogsPanel.js` | ~508 | Virtual-scrolled log viewer |
| `src/components/PositionsPanel.js` | ~500 | Virtual-scrolled positions list |

### Backend

| File | Lines | Purpose |
|------|-------|---------|
| `webui/backend/app.py` | 1,465 | Main Flask server (routes, WS, middleware, startup) |
| `webui/backend/cache.py` | — | Flask-Caching config + timeout tiers |
| `webui/backend/config.py` | — | Backend config |
| `webui/backend/routes/` | ~67 files | All API route blueprints |
| `webui/backend/services/` | — | Business logic services |
| `webui/backend/utils/` | — | Metrics logger, file helpers, health checker, instance lock |
| `webui/backend/options_chain/` | — | Options chain market data |
| `webui/backend/options_strategy/` | — | Multi-leg strategy builder + SL/TP monitors |
| `webui/backend/brain_analyzer/` | — | Independent observer module |

---

## 14. Component Inventory

### Directory Structure (`src/components/`)

| Directory | Purpose |
|-----------|---------|
| `layout/` | TopBar, Sidebar, MobileNav, SymbolContextBar |
| `BotManagement/` | Bot management panels |
| `CodeEditor/` | Monaco editor wrapper |
| `CodeExplanationPanel/` | AI code explanations |
| `PredictiveIntelligence/` | ML/prediction UI |
| `charts/` | Chart components |
| `claude/` | Claude AI integration |
| `common/` | Shared primitives (SymbolBadge, etc.) |
| `futures/` | Futures trading UI |
| `help/` | Built-in help system |
| `incidents/` | Incident tracking |
| `indicators/` | Market indicators |
| `mmm/` | Market Making Module (large subsystem with hooks/) |
| `mvStraddle/` | MV Straddle strategy |
| `options/` | Options trading (chain, payoff, Greeks) |
| `optionsChain/` | Options chain viewer |
| `optionsStrategy/` | Strategy builder |
| `panels/` | Generic panel layouts |
| `positionAdjustment/` | Autoloop / position management |
| `ssrAlgo/` | SSR Algo trading |
| `ui/` | Shared UI primitives |
| `zero_dte/` | Zero DTE trading |

### Utilities (`src/utils/` — 34 files)

| File | Purpose |
|------|---------|
| `RobustConnectionManager.js` | Resilient WebSocket connection |
| `apiClient.js` / `enhancedApiClient.js` / `robustApiClient.js` | HTTP client layers |
| `apiShim.ts` | API abstraction layer |
| `centralPollingManager.ts` | Centralized polling coordination |
| `circuitBreaker.ts` | Circuit breaker pattern |
| `featureFlags.ts` | Feature flag system |
| `pagePrefetch.js` | Prefetch all lazy pages |
| `performanceMonitor.js` | Performance tracking (491 lines) |
| `performanceOptimizer.ts` | Performance optimization utilities |
| `rateLimiting.ts` | Rate limiting for API calls |
| `soundManager.js` | Audio notifications |
| `storage.ts` | localStorage wrapper |
| `symbolColors.ts` | Symbol color coding |
| `validation.ts` | Zod-based validation |

---

## 15. API Endpoints

### Direct Routes (in app.py)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/debug/routes` | Lists all registered routes |
| GET | `/api/config/all` | Full YAML config |
| GET | `/api/config/flat` | Flat config key-value |
| GET | `/` + `/<path>` | React catch-all (static files) |

### Blueprint Routes (70 blueprints — see Section 4.2)

Key endpoint patterns:
- `/api/positions` — Exchange positions
- `/api/orders` — Active orders
- `/api/pnl/summary` — P&L summary
- `/api/bot/status` — Bot running status
- `/api/health` — Health check
- `/api/config/*` — Configuration management
- `/api/options/*` — Options trading
- `/api/mmm/*` — Money Mind & Method
- `/api/ssr-algo/*` — SSR Algo
- `/api/zero-dte/*` — Zero DTE
- `/api/logs` — Log retrieval
- `/api/guardian/*` — Position guardian
- `/api/risk/*` — Risk management
- `/api/emergency/*` — Emergency controls

---

## 16. Common Tasks & Patterns

### Adding a New Page

1. Create `src/pages/NewPage.js` with your component
2. Add lazy import in `src/App.js`:
   ```javascript
   const NewPage = React.lazy(() => import('./pages/NewPage'));
   ```
3. Add `<Route>` in the `<Routes>` block:
   ```jsx
   <Route path="/new_page" element={<Suspense fallback={<SectionSkeleton />}><NewPage {...commonProps} /></Suspense>} />
   ```
4. Add navigation entry in Sidebar config
5. Add prefetch mapping in `src/utils/pagePrefetch.js`
6. Rebuild: `npm run build`

### Adding a New API Endpoint

1. Create `webui/backend/routes/new_feature.py`:
   ```python
   from flask import Blueprint, jsonify
   new_feature_bp = Blueprint('new_feature', __name__)

   @new_feature_bp.route('/api/new-feature', methods=['GET'])
   def get_new_feature():
       return jsonify({"data": "..."})
   ```
2. Register in `app.py`:
   ```python
   from routes.new_feature import new_feature_bp
   app.register_blueprint(new_feature_bp)
   ```
3. Restart backend

### Adding a Cached Endpoint

Use Flask-Caching decorator:
```python
from cache import cache, CACHE_TIMEOUTS

@new_feature_bp.route('/api/new-feature')
@cache.cached(timeout=CACHE_TIMEOUTS['market'], key_prefix=make_cache_key)
def get_new_feature():
    ...
```

### Virtual Scrolling Pattern

For large lists, use react-window v2:
```jsx
import { List as VirtualList } from 'react-window';

// Important: react-window v2.2.7 exports `List` and `Grid`
// NOT FixedSizeList/VariableSizeList (that was v1)
<VirtualList
  height={600}
  itemCount={items.length}
  itemSize={28}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>{items[index]}</div>
  )}
</VirtualList>
```

### Memoization Pattern

```jsx
// Component-level
export default React.memo(MyComponent);

// Expensive computations
const result = useMemo(() => expensiveCalc(data), [data]);

// Callbacks passed as props
const handleClick = useCallback(() => { ... }, [deps]);

// Zustand selectors (already set up)
const positions = usePositions(); // dedicated selector hook
```

---

## 17. Known Constraints & Gotchas

### Frontend

| Issue | Detail |
|-------|--------|
| **react-window v2 API** | Exports `List` and `Grid`, NOT `FixedSizeList`/`VariableSizeList` (v1 names). Always use `import { List } from 'react-window'`. |
| **TypeScript conflict** | TypeScript 5.9.3 conflicts with react-scripts peerOptional `^3.2.1 \|\| ^4`. Use `--legacy-peer-deps` when installing packages. |
| **MUI Table + react-window** | MUI `<Table>` elements are incompatible with react-window virtualization. Don't attempt to virtualize OptionsChain. Filtering already limits to 10-30 visible rows. |
| **Build command** | Must use `npm run build` (react-app-rewired), NOT `npx react-scripts build` (bypasses config-overrides.js → main bundle balloons to 648KB). |
| **#root CSS** | `display: flex; flex-direction: column; width: 100%` is set in index.html. Removing this breaks full-width layout. |
| **AutoloopProvider** | Must stay in App.js (not AppProviders) because AutoloopStatusBar is always visible and needs autoloop context. |
| **MobileOptimizationContext** | Dead code — only consumer (MobileBatteryIndicator) is commented out. Safe to delete. |
| **key prop on route wrapper** | Never add `key={activeSection}` on the page wrapper div — it forces unmount/remount on every tab switch, triggering Suspense flash. |
| **Double-lazy loading** | 16 pages were converted from inner React.lazy to direct import. Don't re-introduce inner lazy imports for pages that load as single chunks. |

### Backend

| Issue | Detail |
|-------|--------|
| **SocketIO CORS** | SocketIO allows `*` while Flask-CORS uses config-defined origins — intentional for local dev but worth noting for security. |
| **threading mode** | `async_mode='threading'` is adequate for single-user but won't scale to many concurrent WS clients. |
| **SimpleCache** | In-memory dict — all cache lost on restart. Acceptable for single-server deployment. |
| **Instance lock** | `WebUIInstanceLock` prevents duplicate processes. If backend crashes leaving stale lock, restart via LaunchAgent handles it. |
| **Signal handling** | Uses `os._exit()` to avoid `SIGABRT` from numpy/scipy threads during shutdown. |
| **Cache pre-warming** | Background thread on startup hits 5 endpoints — uses `app.test_request_context()` for Flask context. |

---

## 18. Optimization History

### Timeline

| Date | Milestone |
|------|-----------|
| March 2026 (early) | Initial V2 plan created. Phases 2, 5.1-5.3 completed. |
| March 2026 (mid) | Phases 6.0, 7.1-7.2, 9, 10.1-10.4, 11, 12 completed. |
| March 2026 (late) | Phase 14 (perceived speed) completed. Bundle: 144KB main. |
| March 2026 (final) | Phases 5.4, 6.2, 6.3, 7.3, 8.1-8.2, 15 completed. Plan complete. |

### Key Metrics Over Time

| Metric | Before | After |
|--------|--------|-------|
| Main bundle | 1,146KB | 144KB (87% reduction) |
| Vendor chunk | 216KB | 145KB (33% reduction) |
| JS files | 1 monolith | 60 lazy chunks |
| App.js | 1,754 lines | 425 lines (76% reduction) |
| Provider nesting | 8+ visible levels | 3 levels |
| `/api/positions` | 2,081ms | 2ms (1,041x faster) |
| `/api/bot/status` | 283ms | 2ms (142x faster) |
| `/api/mmm/sessions` | 10,800ms | 200ms (54x faster) |
| Tab switching | Double-lazy flash | Instant (after 5s prefetch) |

### Phases Intentionally Skipped/Deferred

| Phase | Reason |
|-------|--------|
| 8.3 (OptionsChain virtual scroll) | MUI `<Table>` incompatible with react-window. Filtering already limits visible rows. |
| 13 (Zustand store splitting) | Only 1 consumer, near-zero impact. |
| 16 (HTTP/2 + nginx) | Infrastructure-level change, localhost-only deployment. |
