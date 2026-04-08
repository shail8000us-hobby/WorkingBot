/**
 * Page Prefetch Map — maps section IDs to their dynamic import() functions.
 *
 * These MUST match the exact import() calls used in App.js React.lazy() definitions.
 * When called on hover, webpack downloads and caches the chunk — so when React.lazy
 * needs it, the module is already in memory and renders instantly (no Suspense flash).
 *
 * Created: March 2, 2026 (Performance: eliminate page-switch loading flash)
 */

// Page-level imports (match App.js React.lazy exactly)
const pageImports = {
  todos: () => import('../pages/TodosPage'),
  options: () => import('../pages/OptionsPage'),
  ssr_algo: () => import('../pages/SSRAlgoPage'),
  tradingview: () => import('../pages/TradingViewPage'),
  zero_dte: () => import('../pages/ZeroDTEPage'),
  experimental: () => import('../pages/ExperimentalPage'),
  advanced_features: () => import('../pages/AdvancedFeaturesPage'),
  mv_straddle: () => import('../pages/MVStraddlePage'),
  rsi: () => import('../pages/RSIPage'),
  risk: () => import('../pages/RiskPage'),
  intelligence: () => import('../pages/IntelligencePage'),
  options_chain: () => import('../pages/OptionsChainPage'),
  strategy_builder: () => import('../pages/StrategyBuilderPage'),
  mmm: () => import('../pages/MMMPage'),
  guardian: () => import('../pages/GuardianPage'),
  ml_trading: () => import('../pages/MLTradingPage'),
  botmanagement: () => import('../pages/BotManagementPage'),
  emergency: () => import('../pages/EmergencyPage'),
  monitoring: () => import('../pages/MonitoringPage'),
  config: () => import('../pages/ConfigPage'),
  dashboard: () => import('../pages/DashboardPage'),
  portfolio_margin: () => import('../pages/PortfolioMarginPage'),
  oi: () => import('../pages/OIPage'),
};

// Track what's already been prefetched to avoid duplicate calls
const prefetched = new Set();

/**
 * Prefetch a page chunk by section ID.
 * Calls the actual webpack import() so the module is cached in memory.
 * Safe to call multiple times — deduplicates automatically.
 */
export function prefetchPage(sectionId) {
  if (prefetched.has(sectionId)) return;
  const importFn = pageImports[sectionId];
  if (!importFn) return;

  prefetched.add(sectionId);
  // Fire and forget — webpack caches the module
  importFn().catch(() => {
    // If prefetch fails, remove from set so it can retry
    prefetched.delete(sectionId);
  });
}

/**
 * Prefetch ALL page chunks (call after initial idle period).
 * Staggers imports to avoid network contention.
 */
export function prefetchAllPages() {
  const ids = Object.keys(pageImports);
  ids.forEach((id, i) => {
    setTimeout(() => prefetchPage(id), i * 150); // 150ms apart
  });
}

export default pageImports;
