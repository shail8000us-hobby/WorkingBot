# WebUI Performance Optimization Plan (Phased Approach)

This document outlines a step-by-step strategy to significantly improve the performance and perceived speed of the GridBot WebUI. We will apply optimizations one phase at a time.

## Phase 1: Quick Wins & Asset Optimization (Immediate Impact)
*Goal: Reduce initial load time and improve responsiveness with minimal architectural changes.*

1.  **Polling Strategy Refresh**
    *   **Current State:** `DataAggregator` polls every 20s (default) or 10s (active).
    *   **Optimization:** Implement "Smart Polling" with variable intervals based on specific data needs. Decrease interval for high-priority data (PnL/Positions) and increase for static data.
2.  **Asset Minification & Compression**
    *   Ensure all static assets (images, fonts, JSON) are compressed.
    *   Verify that the production build (`npm run build`) is properly minified and source maps are disabled or handled correctly.
3.  **Lazy Loading Expansion**
    *   Ensure ALL non-critical routes and panels are wrapped in `React.lazy` with appropriate `Suspense` skeletons.
4.  **Deduplicate Heavy Libraries**
    *   Audit `package.json` for redundant or heavy packages (e.g., icons, charting libraries) and replace them with lighter alternatives where possible.

## Phase 2: Real-time Data & State Optimization
*Goal: Transition from polling-heavy to event-driven updates for near-instant UI feedback.*

1.  **WebSocket-First Architecture**
    *   Migrate critical trading data (Positions, Orders, PnL) from the `DataAggregator` polling loop to the `RobustConnectionManager` (WebSocket).
    *   Backend should broadcast updates only when data actually changes (event-driven).
2.  **Zustand Store Refinement**
    *   Implement "Shallow Equality" checks for all store subscribers to prevent unnecessary re-renders of large component trees.
    *   Split the global store into smaller, specialized slices (e.g., `useTradingStore`, `useSystemStore`) to minimize state propagation overhead.
3.  **Memoization Audit**
    *   Strictly apply `React.memo`, `useMemo`, and `useCallback` to all heavy UI components, especially charting and large data tables.

## Phase 3: Advanced Rendering & Bundle Management
*Goal: Maximize browser-level performance and minimize blocking time.*

1.  **Bundle Splitting (Code Splitting)**
    *   Implement route-based and component-based code splitting to ensure the browser only downloads what is needed for the current view.
2.  **Web Worker Integration**
    *   Offload heavy data processing (e.g., PnL calculations, log parsing, charting data transformation) to Web Workers to keep the main UI thread responsive.
3.  **Virtualized Lists**
    *   Implement `react-window` or `react-virtualized` for the Logs Panel and large data tables (Orders/Positions) to handle thousands of entries without lag.
4.  **Service Worker Caching**
    *   Implement a Service Worker to cache static assets and provide offline/fast-load capabilities.

## Phase 4: Backend API & Data Pipeline Optimization
*Goal: Reduce server-side latency and payload size.*

1.  **Compressed API Payloads**
    *   Enable GZIP/Brotli compression for all Flask API responses.
2.  **Field Filtering**
    *   Modify API endpoints to support field selection (only fetch fields required by the current view) to reduce payload size.
3.  **Backend Cache Optimization**
    *   Fine-tune server-side caching for expensive data fetches (e.g., historical PnL, large config files).

---

### Implementation Strategy
We will implement **Phase 1** first and verify its impact before proceeding to Phase 2. Each phase will include a verification step with performance metrics (Lighthouse score, Time to Interactive).
