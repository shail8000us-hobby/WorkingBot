/**
 * Page Prefetch Map — maps section IDs to their dynamic import() functions.
 *
 * These MUST match the exact import() calls used in App.js React.lazy() definitions.
 * When called on hover, webpack downloads and caches the chunk — so when React.lazy
 * needs it, the module is already in memory and renders instantly (no Suspense flash).
 *
 * Created: March 2, 2026 (Performance: eliminate page-switch loading flash)
 */

import { warmFetchJSON } from './dataWarmCache';

// Page-level imports (match App.js React.lazy exactly)
const pageImports = {
  todos: () => import('../pages/TodosPage'),
  options: () => import('../pages/OptionsPage'),
  options_chain: () => import('../pages/OptionsChainPage'),
  strategy_builder: () => import('../pages/StrategyBuilderPage'),
  mv_straddle: () => import('../pages/MVStraddlePage'),
  portfolio_margin: () => import('../pages/PortfolioMarginPage'),

  mmm: () => import('../pages/MMMPage'),
  mmmx: () => import('../pages/MMMXPage'),
  ic: () => import('../pages/ICPage'),
  patience: () => import('../pages/PatiencePage'),
  ssr_algo: () => import('../pages/SSRAlgoPage'),
  ssdh: () => import('../pages/SSDHPage'),

  tradingview: () => import('../pages/TradingViewPage'),
  oi: () => import('../pages/OIPage'),

  dashboard: () => import('../pages/DashboardPage'),
  monitoring: () => import('../pages/MonitoringPage'),
  config: () => import('../pages/ConfigPage'),
  risk: () => import('../pages/RiskPage'),

  ml_trading: () => import('../pages/MLTradingPage'),
  botmanagement: () => import('../pages/BotManagementPage'),

  zero_dte: () => import('../pages/ZeroDTEPage'),
  advanced_features: () => import('../pages/AdvancedFeaturesPage'),
  rsi: () => import('../pages/RSIPage'),
  emergency: () => import('../pages/EmergencyPage'),
};

// Track what's already been prefetched to avoid duplicate calls
const prefetched = new Set();
const warmedData = new Set();

async function warmMonitoringData() {
  const status = await warmFetchJSON('/api/monitoring/status', {
    includeSelectedInstance: true,
    ttlMs: 12000,
  });

  if (!status?.monitoring_active) {
    return;
  }

  await Promise.all([
    '/api/monitoring/price-health',
    '/api/monitoring/pre-order-stats',
    '/api/monitoring/tp-verification',
    '/api/monitoring/anomalies',
    '/api/monitoring/predictive-map',
    '/api/monitoring/advanced-predictions',
  ].map((endpoint) =>
    warmFetchJSON(endpoint, {
      includeSelectedInstance: true,
      ttlMs: 12000,
    })
  ));
}

const dataWarmers = {
  options: async () => {
    await Promise.all([
      warmFetchJSON('/api/options/dashboard', { ttlMs: 10000 }),
      warmFetchJSON('/api/options/fees-summary', { ttlMs: 25000 }),
      warmFetchJSON('/api/positions/pending-orders', { ttlMs: 10000 }),
    ]);
  },

  options_chain: async () => {
    const { optionsChainAPI } = await import('../components/optionsChain/services/chainAPI');
    await optionsChainAPI.warmup('BTC');
  },

  dashboard: warmMonitoringData,
  monitoring: warmMonitoringData,

  patience: async () => {
    await Promise.all([
      warmFetchJSON('/api/patience/status', { ttlMs: 10000 }),
      warmFetchJSON('/api/patience/cards', { ttlMs: 10000 }),
      warmFetchJSON('/api/patience/iv/current', { ttlMs: 45000 }),
    ]);
  },

  ssdh: async () => {
    await Promise.all([
      warmFetchJSON('/api/ssdh/sessions', { ttlMs: 12000 }),
      warmFetchJSON('/api/ssdh/health', { ttlMs: 12000 }),
    ]);
  },

  ic: async () => {
    await warmFetchJSON('/api/ic/sessions?active_only=false', { ttlMs: 12000 });
  },
};

function warmPageData(sectionId) {
  if (warmedData.has(sectionId)) return;
  const warmer = dataWarmers[sectionId];
  if (!warmer) return;

  warmedData.add(sectionId);
  warmer().catch(() => {
    warmedData.delete(sectionId);
  });
}

/**
 * Prefetch a page chunk by section ID.
 * Calls the actual webpack import() so the module is cached in memory.
 * Safe to call multiple times — deduplicates automatically.
 */
export function prefetchPage(sectionId) {
  warmPageData(sectionId);

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
