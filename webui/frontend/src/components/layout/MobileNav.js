/**
 * MobileNav — horizontal pill-style navigation for mobile viewports.
 * Extracted from App.js (Phase 2.3).
 *
 * Groups sections by their `group` field and renders a sticky scrollable bar
 * below the TopBar, visible only on screens < lg (1024 px).
 */

import React from 'react';
import { prefetchPage } from '../../utils/pagePrefetch';

const MobileNav = ({ sections = [], activeSection, onSelect }) => {
  // Build grouped structure for mobile nav
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

  return (
    <div className="sticky top-[calc(9rem+env(safe-area-inset-top))] z-20 flex w-full items-center gap-1.5 overflow-x-auto border-b border-slate-800/80 bg-slate-950/80 px-4 py-3 backdrop-blur lg:hidden">
      {groups.map((g, gi) => (
        <React.Fragment key={g.group}>
          {gi > 0 && (
            <div className="mx-1 h-6 w-px shrink-0 bg-slate-700/60" />
          )}
          {g.items.map(({ id, label }) => {
            const active = activeSection === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onSelect?.(id)}
                onTouchStart={() => prefetchPage(id)}
                className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${active
                  ? 'bg-sky-500 text-slate-900 shadow-card'
                  : 'bg-slate-800/70 text-slate-300 hover:bg-slate-800'
                  }`}
              >
                {label}
              </button>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
};

export default React.memo(MobileNav);
