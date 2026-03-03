/**
 * Section preloader — smart lazy-loading for adjacent navigation tabs.
 * Extracted from App.js (Phase 2.3).
 *
 * Maps section IDs to their dynamic import() calls and preloads only the
 * previous/next sections after a 2 s delay, rather than loading every
 * component upfront.
 */

// Smart preloader: maps section IDs to their dynamic imports
// Only loads what's needed (adjacent tabs), NOT everything at once
const sectionImports = {
  dashboard: [() => import('../components/MonitoringDashboard'), () => import('../components/MonitoringPanel')],
  portfolio: [() => import('../components/SymbolPortfolio')],
  config: [() => import('../components/ConfigPanel'), () => import('../components/SyncReconciliationPanel')],
  risk: [() => import('../components/RiskSafetyDashboard'), () => import('../components/RobustnessPanel')],
  tradingview: [() => import('../components/TradingViewSignals')],
  rsi: [() => import('../components/RSIPanel')],
  positions: [() => import('../components/PositionsPanel')],
  options: [() => import('../components/options')],
  options_chain: [() => import('../components/optionsChain')],
  strategy_builder: [() => import('../components/optionsStrategy')],
  mv_straddle: [() => import('../components/mvStraddle/MVStraddlePanel')],
  mmm: [() => import('../components/mmm')],
  ssr_algo: [() => import('../components/ssrAlgo')],
  ml_trading: [() => import('../components/options/MLInsightsPanel')],
  botmanagement: [() => import('../components/BotManagement/BotManagementDashboard'), () => import('../components/PM2Panel')],
  intelligence: [() => import('../components/AIAdvisorWidget')],
  system_health: [() => import('../components/SystemHealthPanel')],
  todos: [() => import('../components/TodoListPanel')],
  zero_dte: [() => import('../components/zero_dte/ZeroDTEDashboard')],
  experimental: [() => import('../components/ExperimentalPanel')],
  advanced_features: [() => import('../components/AdvancedFeaturesPanel')],
};

// Preload adjacent sections only — called when active section changes
const preloadedSections = new Set();

export const preloadAdjacentSections = (activeSectionId, sectionsList) => {
  const idx = sectionsList.findIndex(s => s.id === activeSectionId);
  if (idx === -1) return;
  // Preload prev and next sections
  const adjacentIds = [
    sectionsList[idx - 1]?.id,
    sectionsList[idx + 1]?.id,
  ].filter(Boolean);
  adjacentIds.forEach(id => {
    if (!preloadedSections.has(id) && sectionImports[id]) {
      preloadedSections.add(id);
      sectionImports[id].forEach(importFn => importFn().catch(() => { }));
    }
  });
};

export default sectionImports;
