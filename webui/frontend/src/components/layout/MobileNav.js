/**
 * MobileNav — horizontal pill-style navigation for mobile viewports.
 * Extracted from App.js (Phase 2.3).
 *
 * Groups sections by their `group` field and renders a sticky scrollable bar
 * below the TopBar, visible only on screens < lg (1024 px).
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useIsMobile } from '../../hooks/useIsMobile';
import { prefetchPage } from '../../utils/pagePrefetch';

const MobileNavDesktopVersion = ({ sections = [], activeSection, onSelect }) => {
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
    <div className="sticky top-[calc(6.5rem+env(safe-area-inset-top))] z-20 flex w-full items-center gap-1.5 overflow-x-auto border-b border-slate-800/80 bg-slate-950/80 px-4 py-3 backdrop-blur lg:hidden">
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

const MobileNavBottomTabs = ({ sections = [], activeSection }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const path = location.pathname.replace(/^\//, '') || activeSection;

  // Group sections the same way as MobileNavDesktopVersion
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
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      height: '56px',
      background: '#12121f',
      borderTop: '1px solid #2a2a3e',
      zIndex: 1000,
      paddingBottom: 'env(safe-area-inset-bottom)',
      boxShadow: '0 -2px 8px rgba(0,0,0,0.4)',
      overflowX: 'auto',
      overflowY: 'hidden',
      display: 'flex',
      alignItems: 'stretch',
      WebkitOverflowScrolling: 'touch',
      scrollbarWidth: 'none',
      msOverflowStyle: 'none',
    }}>
      {groups.map((g, gi) => (
        <React.Fragment key={g.group}>
          {gi > 0 && (
            <div style={{
              width: '1px',
              background: '#2a2a3e',
              alignSelf: 'center',
              height: '28px',
              flexShrink: 0,
              margin: '0 2px',
            }} />
          )}
          {g.items.map(tab => {
            const isActive = path === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => navigate(`/${tab.id}`)}
                style={{
                  border: 'none',
                  borderBottom: isActive ? '3px solid #4caf50' : '3px solid transparent',
                  background: 'transparent',
                  color: isActive ? '#4caf50' : '#888',
                  fontWeight: 600,
                  fontSize: '11px',
                  height: '56px',
                  minWidth: '56px',
                  padding: '0 10px',
                  flexShrink: 0,
                  touchAction: 'manipulation',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'color 0.15s',
                  whiteSpace: 'nowrap',
                }}
                title={tab.label}
              >
                {tab.label}
              </button>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
};

const MobileNav = (props) => {
  const isMobile = useIsMobile();
  return isMobile ? <MobileNavBottomTabs {...props} /> : <MobileNavDesktopVersion {...props} />;
};

export default React.memo(MobileNav);
