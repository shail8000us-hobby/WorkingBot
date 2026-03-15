/**
 * ChainTreeView — visual parent-child tree of cards.
 * Groups cards by parent_card_id, renders indented tree layout.
 *
 * Created: March 14, 2026
 */

import React, { useState } from 'react';

const STATUS_COLORS = {
  DRAFT: '#9ca3af', WAITING: '#a78bfa', ARMED: '#3b82f6',
  TRIGGERED: '#f97316', EXECUTING: '#eab308',
  COMPLETED: '#22c55e', PAUSED: '#ef4444', CANCELLED: '#6b7280',
};

export default function ChainTreeView({ cards, onSelectCard }) {
  // Build tree
  const byId = {};
  cards.forEach(c => { byId[c.card_id] = { ...c, children: [] }; });
  const roots = [];
  cards.forEach(c => {
    if (c.parent_card_id && byId[c.parent_card_id]) {
      byId[c.parent_card_id].children.push(byId[c.card_id]);
    } else {
      roots.push(byId[c.card_id]);
    }
  });

  if (roots.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: 13 }}>
        No cards found. Create a card to see its chain here.
      </div>
    );
  }

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0 }}>Card Chain Tree</h4>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 16 }}>
        Click a card to view details. Children activate when parent completes.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {roots.map(root => (
          <TreeNode key={root.card_id} node={root} depth={0} onSelectCard={onSelectCard} />
        ))}
      </div>
    </div>
  );
}

function TreeNode({ node, depth, onSelectCard }) {
  const [collapsed, setCollapsed] = useState(false);
  const hasChildren = node.children?.length > 0;
  const statusColor = STATUS_COLORS[node.status] || '#9ca3af';

  return (
    <div>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          paddingLeft: depth * 24,
        }}
      >
        {/* Tree indent line */}
        {depth > 0 && (
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: 16, height: 1, background: '#1e293b',
              position: 'absolute', left: -16,
            }} />
          </div>
        )}

        {/* Collapse toggle */}
        {hasChildren ? (
          <button
            onClick={() => setCollapsed(c => !c)}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0, fontSize: 12, width: 16 }}
          >
            {collapsed ? '▶' : '▼'}
          </button>
        ) : (
          <div style={{ width: 16 }} />
        )}

        {/* Card tile */}
        <div
          onClick={() => onSelectCard?.(node)}
          style={{
            flex: 1, background: '#0f172a', borderRadius: 6, padding: '10px 14px',
            border: `1px solid ${statusColor}33`, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 12,
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = statusColor + '88'}
          onMouseLeave={e => e.currentTarget.style.borderColor = statusColor + '33'}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 13 }}>{node.card_name}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
              {node.trigger_type} @ ${node.trigger_price?.toLocaleString()}
              {node.iv_percentile_max ? ` · IV ≤ ${node.iv_percentile_max}%` : ''}
              {node.group_id ? ` · ${node.group_id}` : ''}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* Leg count */}
            <span style={{ fontSize: 11, color: '#64748b' }}>
              {(node.legs || []).length} leg{(node.legs || []).length !== 1 ? 's' : ''}
            </span>

            {/* Status */}
            <span style={{
              padding: '2px 8px', borderRadius: 10,
              background: statusColor, color: '#000', fontSize: 11, fontWeight: 700,
            }}>
              {node.status}
            </span>

            {/* Child count badge */}
            {hasChildren && (
              <span style={{
                padding: '2px 6px', borderRadius: 10,
                background: '#1e293b', color: '#a78bfa', fontSize: 10,
              }}>
                {node.children.length} child{node.children.length !== 1 ? 'ren' : ''}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Children */}
      {hasChildren && !collapsed && (
        <div style={{ position: 'relative', marginLeft: depth * 24 + 20, marginTop: 4 }}>
          {/* Vertical connector line */}
          <div style={{
            position: 'absolute', left: 8, top: 0, bottom: 12,
            width: 1, background: '#1e293b',
          }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 16 }}>
            {node.children.map(child => (
              <TreeNode key={child.card_id} node={child} depth={1} onSelectCard={onSelectCard} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
