import clsx from 'clsx';
import { motion } from 'framer-motion';
import React from 'react';
import { prefetchChunk } from '../../utils/chunkPrefetch.ts';

// Map section IDs to their corresponding chunk names for prefetching
// Phase 1: Complete map — all sections covered
const sectionChunkMap = {
  dashboard: 'monitoring',
  portfolio: 'symbolPortfolio',
  positions: 'positions',
  config: 'configPanel',
  risk: 'riskSafetyDashboard',
  options: 'options',
  options_chain: 'optionsChain',
  strategy_builder: 'strategyBuilder',
  mv_straddle: 'mvStraddle',
  mmm: 'mmm',
  ssr_algo: 'ssrAlgo',
  zero_dte: 'zeroDTE',
  tradingview: 'tradingViewSignals',
  rsi: 'rsiPanel',
  ml_trading: 'mlTrading',
  botmanagement: 'botManagement',
  system_health: 'systemHealth',
  intelligence: 'intelligence',
  todos: 'todoList',
  guardian: 'guardianDashboard',
  experimental: 'experimentalPanel',
  advanced_features: 'advancedFeatures',
  monitoring: 'monitoring',
  logs: 'logsPanel',
};

// Short display labels for group headers
const groupLabels = {
  'Grid Bot': 'GRID',
  'Options Trading': 'OPTIONS',
  'Algorithms': 'ALGOS',
  'Signals & ML': 'SIGNALS',
  'System': 'SYSTEM',
  'Labs': 'LABS',
};

const Sidebar = React.memo(function Sidebar({ sections = [], activeSection, onSelect }) {
  const handleMouseEnter = React.useCallback((sectionId) => {
    // Prefetch chunk when user hovers over navigation item
    const chunkName = sectionChunkMap[sectionId];
    if (chunkName) {
      prefetchChunk(chunkName, { priority: 'high' });
    }
  }, []);

  // Build grouped structure: [{ group, items }]
  const groupedSections = React.useMemo(() => {
    const groups = [];
    let currentGroup = null;
    sections.forEach((section) => {
      const group = section.group || 'Other';
      if (group !== currentGroup) {
        groups.push({ group, items: [section] });
        currentGroup = group;
      } else {
        groups[groups.length - 1].items.push(section);
      }
    });
    return groups;
  }, [sections]);

  return (
    <nav
      className="fixed left-0 right-0 z-38 hidden border-b border-slate-800/80 bg-slate-950/90 backdrop-blur lg:block"
      style={{
        top: `calc(9.5rem + env(safe-area-inset-top))`,
      }}
    >
      <div className="mx-auto max-w-full px-4">
        <div className="flex items-center gap-1 overflow-x-auto py-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {groupedSections.map((g, gi) => (
            <React.Fragment key={g.group}>
              {/* Group divider (skip before first group) */}
              {gi > 0 && (
                <div className="mx-1.5 flex h-8 shrink-0 items-center">
                  <div className="h-5 w-px bg-slate-700/60" />
                </div>
              )}
              {/* Group label */}
              <span className="shrink-0 px-1 text-[9px] font-bold uppercase tracking-wider text-slate-600">
                {groupLabels[g.group] || g.group}
              </span>
              {/* Section buttons in this group */}
              {g.items.map(({ id, label, icon: Icon, badge }) => {
                const active = activeSection === id;
                return (
                  <motion.button
                    key={id}
                    type="button"
                    onClick={() => onSelect?.(id)}
                    onMouseEnter={() => handleMouseEnter(id)}
                    data-prefetch={sectionChunkMap[id]}
                    className={clsx(
                      'group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition whitespace-nowrap',
                      active
                        ? 'border-sky-500/50 bg-sky-500/10 text-sky-100 shadow-card'
                        : 'border-transparent bg-slate-900/50 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
                    )}
                    whileHover={{ y: active ? 0 : -2 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 22 }}
                  >
                    {Icon && (
                      <Icon
                        className={clsx('h-4 w-4 shrink-0', active ? 'text-sky-300' : 'text-slate-400')}
                      />
                    )}
                    <span className="flex items-center gap-1.5">
                      <span>{label}</span>
                      {badge !== undefined && (
                        <span
                          className={clsx(
                            'rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                            active ? 'bg-sky-500/30 text-sky-100' : 'bg-slate-800 text-slate-300'
                          )}
                        >
                          {badge}
                        </span>
                      )}
                    </span>
                  </motion.button>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </nav>
  );
});

export default Sidebar;
