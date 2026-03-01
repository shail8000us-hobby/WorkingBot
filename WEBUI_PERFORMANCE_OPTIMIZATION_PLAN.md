# WebUI Performance Optimization Plan

**Project:** WorkingBot WebUI
**Current Status:** Slow performance (774KB main bundle, 1749-line App.js, 62 route files)
**Architecture:** Flask Backend (port 5555) + React Frontend
**Last Updated:** March 1, 2026

---

## Performance Analysis Summary

### Current Issues Identified

**Frontend:**
- ❌ Main bundle: 774KB (uncompressed) - should be <250KB
- ❌ App.js: 1,749 lines with 61+ hooks - massive component
- ❌ No code splitting beyond basic chunks
- ❌ Heavy dependencies (MUI, Chart.js, Recharts, Monaco Editor, Framer Motion)
- ❌ Multiple context providers wrapping entire app
- ❌ Likely excessive re-renders from poorly optimized hooks

**Backend:**
- ⚠️ 62 route files/blueprints - potential N+1 queries
- ⚠️ SocketIO emissions not optimized (14 occurrences found)
- ⚠️ No caching layer visible
- ⚠️ Database queries may not be indexed properly

---

## Phase 1: Frontend Bundle Optimization (Quick Wins)
**Timeline:** 1-2 days
**Impact:** 🔥🔥🔥 High - 40-60% reduction in initial load time

### Tasks

#### 1.1 Analyze Current Bundle
```bash
cd webui/frontend
npm run build
npm run analyze  # Uses source-map-explorer
```
- Identify largest dependencies
- Find duplicate code
- Locate unused exports

#### 1.2 Implement Dynamic Imports (Code Splitting)
**Files to modify:**
- `src/App.js` - Convert static imports to `React.lazy()`
- Heavy components to lazy load:
  - Monaco Editor panel
  - Chart components (Recharts/Chart.js panels)
  - Options trading panels
  - Backtest panels
  - Brain analyzer

**Example transformation:**
```javascript
// BEFORE
import MLModelMonitor from './components/options/MLModelMonitor';

// AFTER
const MLModelMonitor = React.lazy(() => import('./components/options/MLModelMonitor'));
```

**Target:** Split into 8-12 smaller chunks (<100KB each)

#### 1.3 Tree-Shake Heavy Dependencies
- **MUI:** Import only used components (`@mui/material/Button` not `@mui/material`)
- **Recharts vs Chart.js:** Remove one library (keep Chart.js, remove Recharts)
- **Monaco Editor:** Load only when code panels are opened
- **Framer Motion:** Replace with CSS animations (already using `animations.css`)

#### 1.4 Enable Production Optimizations
**File:** `webui/frontend/config-overrides.js` (create if missing)
```javascript
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = {
  webpack: function(config, env) {
    if (env === 'production') {
      config.optimization.minimizer.push(
        new TerserPlugin({
          terserOptions: {
            compress: { drop_console: true },
          },
        })
      );
      config.plugins.push(
        new CompressionPlugin({
          algorithm: 'gzip',
          test: /\.(js|css|html|svg)$/,
        })
      );
    }
    return config;
  },
};
```

**Expected Results:**
- Main bundle: 774KB → 200-250KB
- Initial load: 40-50% faster
- Lighthouse score: +20 points

---

## Phase 2: React Performance Optimization
**Timeline:** 2-3 days
**Impact:** 🔥🔥 Medium-High - Eliminate UI lag/jank

### Tasks

#### 2.1 Refactor App.js (Break Down Monolith)
**Current:** 1,749 lines, 61+ hooks
**Target:** <300 lines, <15 hooks

**New Structure:**
```
src/
├── App.js (router + layout only)
├── layouts/
│   ├── DashboardLayout.js (sidebar, topbar, contexts)
│   └── MinimalLayout.js (for login/error pages)
├── pages/
│   ├── DashboardPage.js
│   ├── OptionsPage.js
│   ├── AnalyticsPage.js
│   ├── BacktestPage.js
│   └── ConfigPage.js
```

**Strategy:**
- Extract navigation logic → `useNavigation` hook
- Extract sidebar state → `SidebarProvider` context
- Split panels into separate page components
- Use `react-router-dom` for client-side routing

#### 2.2 Optimize Hooks & Re-renders
**Audit all `useEffect` dependencies:**
```bash
# Find all useEffect hooks
grep -n "useEffect" webui/frontend/src/App.js
```

**Common fixes:**
- Add missing dependencies or use `useCallback`/`useMemo`
- Debounce rapid state updates (e.g., WebSocket messages)
- Use `React.memo()` for expensive child components
- Move static data outside component (no re-creation on each render)

#### 2.3 Implement Virtual Scrolling
**For large lists (positions, trades, logs):**
- Install: `react-window` or `react-virtualized`
- Replace long `map()` renders with `<FixedSizeList>`

**Example:**
```javascript
// BEFORE: Renders all 1000 positions
{positions.map(pos => <PositionRow key={pos.id} {...pos} />)}

// AFTER: Only renders visible rows
<FixedSizeList
  height={600}
  itemCount={positions.length}
  itemSize={50}
>
  {({ index, style }) => (
    <PositionRow style={style} {...positions[index]} />
  )}
</FixedSizeList>
```

#### 2.4 Optimize Context Providers
**Current:** 8+ providers wrapping App
```javascript
<SymbolProvider>
  <InstanceProvider>
    <AutoloopProvider>
      <MMMProvider>
        <SystemStatusProvider>
          {/* More nesting... */}
```

**Optimization:**
- Combine related contexts (e.g., Symbol + Instance → `TradingContext`)
- Use Zustand store instead of Context API for frequently updated state
- Move rarely-changing contexts higher in tree

**Expected Results:**
- 60-70% reduction in unnecessary re-renders
- Smooth 60fps animations
- Faster panel switching (<100ms)

---

## Phase 3: Backend API Optimization
**Timeline:** 2-3 days
**Impact:** 🔥🔥🔥 High - Reduce API response times by 50-80%

### Tasks

#### 3.1 Implement Response Caching
**Install:** Flask-Caching
```bash
pip install Flask-Caching
```

**File:** `webui/backend/app.py`
```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',  # or Redis for production
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Example cached endpoint
@cache.cached(timeout=60, key_prefix='positions')
def get_positions():
    # Expensive DB query
    return jsonify(positions)
```

**Endpoints to cache (with TTL):**
- `/api/positions` - 5s
- `/api/config/all` - 60s
- `/api/analytics/*` - 30s
- `/api/market` - 10s
- `/api/health` - 2s

#### 3.2 Database Query Optimization
**Add connection pooling:**
```python
# In database/__init__.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    db_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

**Optimize N+1 queries:**
- Use `joinedload()` for relationships
- Add indexes on frequently queried columns
- Batch updates instead of individual INSERT/UPDATE

**Audit slow queries:**
```bash
# Enable query logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

#### 3.3 Optimize SocketIO Emissions
**Current:** 14+ `socketio.emit()` calls scattered across routes

**Strategy:**
- Debounce rapid emissions (e.g., price updates)
- Use rooms for targeted broadcasts
- Batch multiple updates into single emission

**Example:**
```python
# BEFORE: Emits on every trade (100+ times/minute)
@socketio.on('trade_executed')
def on_trade(data):
    socketio.emit('trade_update', data)

# AFTER: Batch updates every 2 seconds
from collections import deque
trade_buffer = deque(maxlen=100)

def flush_trades():
    if trade_buffer:
        socketio.emit('trade_batch', list(trade_buffer))
        trade_buffer.clear()

# Run flush_trades() every 2s in background thread
```

#### 3.4 Add API Response Compression
**Already enabled in app.py:**
```python
compress = Compress()
compress.init_app(app)
```

**Verify gzip is working:**
- Check response headers: `Content-Encoding: gzip`
- If not, ensure `flask-compress` is installed

**Expected Results:**
- API response times: 200-500ms → 50-150ms
- WebSocket latency: <50ms
- Database query time: 70-90% reduction

---

## Phase 4: Network & Data Fetching
**Timeline:** 1-2 days
**Impact:** 🔥 Medium - Reduce redundant API calls

### Tasks

#### 4.1 Implement Request Deduplication
**Install:** `axios` with custom interceptor (already installed)

**File:** `webui/frontend/src/services/api.js`
```javascript
import axios from 'axios';

const pendingRequests = new Map();

api.interceptors.request.use(config => {
  const key = `${config.method}:${config.url}`;

  if (pendingRequests.has(key)) {
    // Return existing promise instead of making new request
    return pendingRequests.get(key);
  }

  const promise = axios(config);
  pendingRequests.set(key, promise);
  promise.finally(() => pendingRequests.delete(key));

  return config;
});
```

#### 4.2 Optimize Polling Intervals
**Audit current intervals:**
```bash
grep -r "setInterval\|setTimeout" webui/frontend/src/
```

**Recommendations:**
- Health checks: 5s → 10s
- Positions: 2s → 5s (use WebSocket instead)
- Logs: 3s → 10s
- Analytics: 30s (acceptable)

#### 4.3 Implement Smart Refetching
**Use Zustand store's dataAggregator:**
```javascript
// Only refetch when tab is visible
useEffect(() => {
  const handleVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      dataAggregator.refetchAll();
    }
  };

  document.addEventListener('visibilitychange', handleVisibilityChange);
  return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
}, []);
```

#### 4.4 Preload Critical Data
**In DashboardLayout.js:**
```javascript
useEffect(() => {
  // Preload on mount
  Promise.all([
    api.get('/api/positions'),
    api.get('/api/config/all'),
    api.get('/api/health')
  ]);
}, []);
```

**Expected Results:**
- 50% reduction in redundant API calls
- Faster perceived performance
- Lower server load

---

## Phase 5: Production Build & Delivery
**Timeline:** 1 day
**Impact:** 🔥 Medium - Optimize asset delivery

### Tasks

#### 5.1 Enable Brotli Compression
**Backend:** Add Brotli support (better than gzip)
```bash
pip install Brotli-asgi
```

**Or serve via Nginx reverse proxy:**
```nginx
server {
    listen 5555;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    brotli on;
    brotli_types text/plain text/css application/json application/javascript;
}
```

#### 5.2 Add Resource Hints
**File:** `webui/frontend/public/index.html`
```html
<head>
  <!-- Preconnect to API -->
  <link rel="preconnect" href="http://localhost:5555">
  <link rel="dns-prefetch" href="http://localhost:5555">

  <!-- Preload critical fonts -->
  <link rel="preload" href="/static/fonts/Inter.woff2" as="font" crossorigin>
</head>
```

#### 5.3 Service Worker for Offline Support (Optional)
**File:** `webui/frontend/src/serviceWorker.js`
- Cache static assets
- Offline fallback page
- Background sync for failed requests

#### 5.4 Production Build Checklist
```bash
# Build with optimizations
cd webui/frontend
npm run build

# Verify bundle sizes
npm run analyze

# Test production build locally
cd ../backend
python3 app.py
# Visit http://localhost:5555

# Check Lighthouse score (should be 90+)
```

**Expected Results:**
- Brotli: 20-30% smaller than gzip
- First Contentful Paint: <1.5s
- Time to Interactive: <3s

---

## Phase 6: Monitoring & Long-term Optimization
**Timeline:** Ongoing
**Impact:** 🔧 Maintenance - Prevent regressions

### Tasks

#### 6.1 Add Performance Monitoring
**Already exists:** `utils/performanceMonitor.js`
```javascript
import { perfMonitor } from './utils/performanceMonitor';

// Track component render times
useEffect(() => {
  perfMonitor.mark('DashboardPage:mount');
  return () => perfMonitor.measure('DashboardPage:mount');
}, []);
```

#### 6.2 Bundle Size Budget
**File:** `webui/frontend/package.json`
```json
{
  "bundlewatch": {
    "files": [
      {
        "path": "build/static/js/main.*.js",
        "maxSize": "250kb"
      },
      {
        "path": "build/static/js/*.chunk.js",
        "maxSize": "100kb"
      }
    ]
  }
}
```

#### 6.3 Lighthouse CI (Optional)
```bash
npm install -g @lhci/cli
lhci autorun --config=.lighthouserc.json
```

**Set performance budgets:**
- Performance: >90
- Accessibility: >95
- Best Practices: >90

#### 6.4 Regular Audits
**Monthly tasks:**
- Run `npm audit` for security + performance
- Review `npm run analyze` for bundle bloat
- Check Chrome DevTools Performance tab
- Profile slow API endpoints

---

## Implementation Order

### Recommended Execution:
1. **Start with Phase 1** (biggest impact, least risk)
2. **Then Phase 3** (backend caching - high ROI)
3. **Then Phase 2** (frontend refactoring - most complex)
4. **Then Phase 4** (network optimization)
5. **Then Phase 5** (production polish)
6. **Finally Phase 6** (set up monitoring)

### Estimated Timeline:
- **Quick wins (Phases 1 + 3):** 3-4 days
- **Full optimization (All phases):** 10-12 days
- **Ongoing monitoring (Phase 6):** Continuous

---

## Expected Performance Gains

### Before Optimization:
- Initial Load: ~5-8 seconds
- Main Bundle: 774KB
- Time to Interactive: ~6-10 seconds
- API Response: 200-500ms
- Lighthouse Score: ~60-70

### After All Phases:
- Initial Load: ~1.5-2.5 seconds ✅ (70% faster)
- Main Bundle: 200-250KB ✅ (68% smaller)
- Time to Interactive: ~2-3 seconds ✅ (70% faster)
- API Response: 50-150ms ✅ (75% faster)
- Lighthouse Score: ~90-95 ✅ (+30 points)

---

## Risk Mitigation

### Testing Strategy:
- ✅ Test each phase in development first
- ✅ Compare before/after metrics
- ✅ Use git branches for each phase
- ✅ Keep rollback plan ready

### Backup Plan:
```bash
# Before each phase
git checkout -b perf-phase-N
git commit -m "Checkpoint before Phase N"

# If issues occur
git checkout main
git branch -D perf-phase-N
```

---

## Success Metrics

Track these KPIs:
- [ ] Bundle size <250KB
- [ ] First Contentful Paint <1.5s
- [ ] Time to Interactive <3s
- [ ] API P95 latency <200ms
- [ ] Lighthouse Performance >90
- [ ] Zero console errors in production
- [ ] Memory usage stable (no leaks)
- [ ] Smooth 60fps scrolling

---

**Ready to begin Phase 1?** Run `npm run analyze` to see current bundle composition.
