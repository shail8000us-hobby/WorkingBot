/**
 * ExpiryFilter — Sensibull-style multi-select expiry pill checkboxes
 *
 * Props:
 *   expiries:         array of { date, is_weekly, days_to_expiry }
 *   selectedExpiries: string[] of selected ISO dates
 *   onChange:         (string[]) => void
 *   maxSelections:    number (default 5)
 *
 * UI: horizontal pill row, each pill shows "30 Mar (3d)" with [W] badge for weeklies.
 * Selecting beyond maxSelections shows an inline warning.
 *
 * Created: March 27, 2026
 */

import React, { useState } from 'react';

const MAX_DEFAULT = 5;

function formatExpiryLabel(expiry) {
  // expiry.date = "2026-03-30"
  try {
    const d = new Date(expiry.date + 'T00:00:00Z');
    const day = d.getUTCDate();
    const mon = d.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' });
    const days = expiry.days_to_expiry;
    const daysLabel = days === 0 ? 'today' : days === 1 ? '1d' : `${days}d`;
    return { date: `${day} ${mon}`, days: daysLabel };
  } catch {
    return { date: expiry.date, days: '' };
  }
}

export default function ExpiryFilter({
  expiries = [],
  selectedExpiries = [],
  onChange,
  maxSelections = MAX_DEFAULT,
}) {
  const [limitWarning, setLimitWarning] = useState(false);

  if (!expiries.length) return null;

  const toggle = (dateStr) => {
    if (selectedExpiries.includes(dateStr)) {
      // Deselect
      setLimitWarning(false);
      onChange(selectedExpiries.filter(d => d !== dateStr));
    } else {
      // Select — enforce max
      if (selectedExpiries.length >= maxSelections) {
        setLimitWarning(true);
        setTimeout(() => setLimitWarning(false), 2000);
        return;
      }
      setLimitWarning(false);
      onChange([...selectedExpiries, dateStr]);
    }
  };

  const clearAll = () => {
    setLimitWarning(false);
    onChange([]);
  };

  const selectAll = () => {
    setLimitWarning(false);
    onChange(expiries.slice(0, maxSelections).map(e => e.date));
  };

  const selectedCount = selectedExpiries.length;

  return (
    <div style={{ marginBottom: '14px' }}>
      {/* Header row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '8px',
        flexWrap: 'wrap',
        gap: '6px',
      }}>
        <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Expiry Filter
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
            Selected: <strong style={{ color: '#e2e8f0' }}>{selectedCount}</strong>
            {selectedCount >= maxSelections && (
              <span style={{ color: '#f59e0b', marginLeft: '4px' }}>(max {maxSelections})</span>
            )}
          </span>
          {selectedCount > 0 && (
            <button
              onClick={clearAll}
              style={{
                fontSize: '11px',
                color: '#64748b',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '0',
                textDecoration: 'underline',
              }}
            >
              Clear all
            </button>
          )}
          {selectedCount === 0 && expiries.length > 0 && (
            <button
              onClick={selectAll}
              style={{
                fontSize: '11px',
                color: '#60a5fa',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '0',
                textDecoration: 'underline',
              }}
            >
              Select nearest {Math.min(maxSelections, expiries.length)}
            </button>
          )}
        </div>
      </div>

      {/* Pill row */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '6px',
      }}>
        {expiries.map((expiry) => {
          const isSelected = selectedExpiries.includes(expiry.date);
          const isDisabled = !isSelected && selectedCount >= maxSelections;
          const { date: dateLabel, days: daysLabel } = formatExpiryLabel(expiry);

          return (
            <button
              key={expiry.date}
              onClick={() => toggle(expiry.date)}
              disabled={isDisabled}
              title={isDisabled ? `Max ${maxSelections} expiries` : expiry.date}
              style={{
                position: 'relative',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 10px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: isSelected ? 600 : 400,
                cursor: isDisabled ? 'not-allowed' : 'pointer',
                border: `1px solid ${isSelected ? '#3b82f6' : 'rgba(71, 85, 105, 0.5)'}`,
                backgroundColor: isSelected
                  ? 'rgba(30, 58, 95, 0.9)'
                  : isDisabled
                    ? 'rgba(15, 23, 42, 0.2)'
                    : 'rgba(15, 23, 42, 0.4)',
                color: isSelected ? '#e2e8f0' : isDisabled ? '#475569' : '#94a3b8',
                transition: 'all 0.15s',
                outline: 'none',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => {
                if (!isDisabled && !isSelected) {
                  e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.5)';
                  e.currentTarget.style.color = '#cbd5e1';
                }
              }}
              onMouseLeave={e => {
                if (!isDisabled && !isSelected) {
                  e.currentTarget.style.borderColor = 'rgba(71, 85, 105, 0.5)';
                  e.currentTarget.style.color = '#94a3b8';
                }
              }}
            >
              {/* Checkmark for selected */}
              {isSelected && (
                <span style={{ fontSize: '10px', color: '#60a5fa' }}>✓</span>
              )}

              <span>{dateLabel}</span>

              {/* Days label */}
              <span style={{
                fontSize: '10px',
                color: isSelected ? '#93c5fd' : '#64748b',
              }}>
                ({daysLabel})
              </span>

              {/* Weekly badge */}
              {expiry.is_weekly && (
                <span style={{
                  fontSize: '9px',
                  fontWeight: 700,
                  color: isSelected ? '#fbbf24' : '#92400e',
                  backgroundColor: isSelected ? 'rgba(251, 191, 36, 0.15)' : 'rgba(146, 64, 14, 0.15)',
                  borderRadius: '3px',
                  padding: '0 3px',
                  lineHeight: '14px',
                }}>
                  W
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Limit warning inline */}
      {limitWarning && (
        <div style={{
          marginTop: '6px',
          fontSize: '11px',
          color: '#f59e0b',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}>
          ⚠ Maximum {maxSelections} expiries — deselect one to add another
        </div>
      )}
    </div>
  );
}
