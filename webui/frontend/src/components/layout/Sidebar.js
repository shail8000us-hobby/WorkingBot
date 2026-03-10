import clsx from 'clsx';
import React from 'react';
import { prefetchPage } from '../../utils/pagePrefetch';

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
    // Prefetch the actual webpack chunk when user hovers — makes page switch instant
    prefetchPage(sectionId);
  }, []);

  // First 9 sections get Ctrl+N shortcuts
  const shortcutMap = React.useMemo(() => {
    const map = {};
    sections.slice(0, 9).forEach((s, i) => { map[s.id] = i + 1; });
    return map;
  }, [sections]);

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
      className="fixed left-0 right-0 z-[38] hidden border-b border-slate-800/80 bg-slate-950 lg:block"
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
                const shortcutNum = shortcutMap[id];
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onSelect?.(id)}
                    onMouseEnter={() => handleMouseEnter(id)}
                    title={shortcutNum !== undefined ? `Ctrl+${shortcutNum}` : undefined}
                    className={clsx(
                      'group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition-all duration-150 whitespace-nowrap',
                      active
                        ? 'border-sky-500/50 bg-sky-500/10 text-sky-100 shadow-card'
                        : 'border-transparent bg-slate-900/50 text-slate-300 hover:border-slate-700 hover:bg-slate-900 hover:-translate-y-0.5',
                      'active:scale-[0.98]'
                    )}
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
                    {shortcutNum !== undefined && (
                      <span
                        className={clsx(
                          'ml-0.5 shrink-0 rounded border px-1 py-0.5 font-mono text-[9px] leading-none',
                          active
                            ? 'border-sky-500/40 bg-sky-500/20 text-sky-300'
                            : 'border-slate-700 bg-slate-800/80 text-slate-500'
                        )}
                      >
                        ⌃{shortcutNum}
                      </span>
                    )}
                  </button>
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
