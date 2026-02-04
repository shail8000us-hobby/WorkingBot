import clsx from 'clsx';
import { motion } from 'framer-motion';
import React from 'react';
import { prefetchChunk } from '../../utils/chunkPrefetch.ts';

// Map section IDs to their corresponding chunk names for prefetching
const sectionChunkMap = {
  dashboard: 'monitoring',
  positions: 'positions',
  options: 'options',
  'options-chain': 'optionsChain',
  'strategy-builder': 'strategyBuilder',
  'mv-straddle': 'mvStraddle',
  'ssr_algo': 'ssrAlgo',
  config: 'configPanel',
  logs: 'logsPanel',
  guardian: 'guardianDashboard',
  monitoring: 'monitoring',
};

const Sidebar = React.memo(function Sidebar({ sections = [], activeSection, onSelect }) {
  const handleMouseEnter = React.useCallback((sectionId) => {
    // Prefetch chunk when user hovers over navigation item
    const chunkName = sectionChunkMap[sectionId];
    if (chunkName) {
      prefetchChunk(chunkName, { priority: 'high' });
    }
  }, []);

  return (
    <nav
      className="fixed left-0 right-0 z-38 hidden border-b border-slate-800/80 bg-slate-950/90 backdrop-blur lg:block"
      style={{
        top: `calc(9.5rem + env(safe-area-inset-top))`,
      }}
    >
      <div className="mx-auto max-w-full px-4">
        <div className="flex items-center gap-2 overflow-x-auto py-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {sections.map(({ id, label, icon: Icon, badge }) => {
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
        </div>
      </div>
    </nav>
  );
});

export default Sidebar;
