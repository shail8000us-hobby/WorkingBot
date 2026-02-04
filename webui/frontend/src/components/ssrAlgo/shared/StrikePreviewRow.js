/**
 * StrikePreviewRow Component
 * 
 * Displays a single leg in the strike selection preview table.
 * Shows strike, premium, target range, and match status.
 * 
 * Per Implementation Plan: Section 2.3 - shared/StrikePreviewRow.js
 * Created: February 3, 2026
 */

import React from 'react';
import StatusBadge from './StatusBadge';

/**
 * Leg type configurations
 */
const LEG_CONFIG = {
  'ATM CE Sell': {
    side: 'SELL',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    qty: 1,
  },
  'ATM PE Sell': {
    side: 'SELL',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    qty: 1,
  },
  'OTM CE Buy': {
    side: 'BUY',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    qty: 2,
  },
  'OTM PE Buy': {
    side: 'BUY',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    qty: 2,
  },
  'Far OTM CE Sell': {
    side: 'SELL',
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    qty: 1,
  },
  'Far OTM PE Sell': {
    side: 'SELL',
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    qty: 1,
  },
};

/**
 * StrikePreviewRow Component
 * 
 * @param {string} leg - Leg name (e.g., 'ATM CE Sell')
 * @param {number} strike - Strike price
 * @param {number} premium - Option premium
 * @param {string} targetRange - Target premium range string
 * @param {boolean} matches - Whether premium matches target
 * @param {string} side - Trade side ('BUY' or 'SELL')
 * @param {number} qty - Quantity/lots
 * @param {boolean} isLoading - Loading state
 * @param {string} error - Error message
 * @param {string} className - Additional CSS classes
 */
const StrikePreviewRow = ({
  leg,
  strike,
  premium,
  targetRange,
  matches,
  side,
  qty,
  isLoading = false,
  error,
  className = '',
}) => {
  const config = LEG_CONFIG[leg] || {
    side: side || 'SELL',
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
    qty: qty || 1,
  };

  // Loading state
  if (isLoading) {
    return (
      <tr className={`${config.bgColor} animate-pulse ${className}`}>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-24" />
        </td>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-16" />
        </td>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-20" />
        </td>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-24" />
        </td>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-12" />
        </td>
        <td className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded w-8" />
        </td>
      </tr>
    );
  }

  // Error state
  if (error) {
    return (
      <tr className={`bg-red-50 ${className}`}>
        <td className="px-4 py-3 font-medium text-gray-700">{leg}</td>
        <td colSpan={5} className="px-4 py-3 text-red-600 text-sm">
          ⚠️ {error}
        </td>
      </tr>
    );
  }

  return (
    <tr className={`${config.bgColor} hover:opacity-90 transition-opacity ${className}`}>
      {/* Leg name */}
      <td className="px-4 py-3">
        <span className={`font-medium ${config.color}`}>
          {leg}
        </span>
      </td>

      {/* Strike price */}
      <td className="px-4 py-3 font-mono text-gray-900">
        {strike?.toLocaleString() || '-'}
      </td>

      {/* Premium */}
      <td className="px-4 py-3">
        <span className="font-mono text-gray-900">
          ₹{premium?.toFixed(2) || '-'}
        </span>
      </td>

      {/* Target range */}
      <td className="px-4 py-3 text-sm text-gray-600">
        {targetRange || '-'}
      </td>

      {/* Match status */}
      <td className="px-4 py-3">
        {matches !== undefined && (
          <StatusBadge
            status={matches ? 'safe' : 'warning'}
            label={matches ? 'Match' : 'Deviation'}
            size="xs"
            showDot={false}
            showIcon
          />
        )}
      </td>

      {/* Side and quantity */}
      <td className="px-4 py-3">
        <span
          className={`
            inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium
            ${config.side === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}
          `}
        >
          {config.side}
          <span className="text-gray-500">×{config.qty}</span>
        </span>
      </td>
    </tr>
  );
};

/**
 * Strike preview table component
 */
export const StrikePreviewTable = ({
  previewData,
  isLoading = false,
  error,
  className = '',
}) => {
  // Generate rows from preview data
  const rows = React.useMemo(() => {
    if (!previewData) return [];

    const result = [];

    // ATM strikes
    if (previewData.atm) {
      result.push({
        leg: 'ATM CE Sell',
        strike: previewData.atm.strike,
        premium: previewData.atm.ce_premium,
        matches: true,
      });
      result.push({
        leg: 'ATM PE Sell',
        strike: previewData.atm.strike,
        premium: previewData.atm.pe_premium,
        matches: true,
      });
    }

    // OTM Buy strikes
    if (previewData.otm_ce_buy) {
      result.push({
        leg: 'OTM CE Buy',
        strike: previewData.otm_ce_buy.strike,
        premium: previewData.otm_ce_buy.premium,
        targetRange: previewData.otm_ce_buy.target_range,
        matches: previewData.otm_ce_buy.matches !== false,
      });
    }

    if (previewData.otm_pe_buy) {
      result.push({
        leg: 'OTM PE Buy',
        strike: previewData.otm_pe_buy.strike,
        premium: previewData.otm_pe_buy.premium,
        targetRange: previewData.otm_pe_buy.target_range,
        matches: previewData.otm_pe_buy.matches !== false,
      });
    }

    // Far OTM Sell strikes
    if (previewData.far_otm_ce) {
      result.push({
        leg: 'Far OTM CE Sell',
        strike: previewData.far_otm_ce.strike,
        premium: previewData.far_otm_ce.premium,
        targetRange: previewData.far_otm_ce.target_range,
        matches: previewData.far_otm_ce.matches !== false,
      });
    }

    if (previewData.far_otm_pe) {
      result.push({
        leg: 'Far OTM PE Sell',
        strike: previewData.far_otm_pe.strike,
        premium: previewData.far_otm_pe.premium,
        targetRange: previewData.far_otm_pe.target_range,
        matches: previewData.far_otm_pe.matches !== false,
      });
    }

    return result;
  }, [previewData]);

  if (error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-4 ${className}`}>
        <p className="text-red-700">⚠️ {error}</p>
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200 text-left text-sm text-gray-500">
            <th className="px-4 py-2 font-medium">Leg</th>
            <th className="px-4 py-2 font-medium">Strike</th>
            <th className="px-4 py-2 font-medium">Premium</th>
            <th className="px-4 py-2 font-medium">Target Range</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Side</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {isLoading ? (
            // Loading skeleton rows
            Array.from({ length: 6 }).map((_, i) => (
              <StrikePreviewRow key={i} leg={`Loading ${i + 1}`} isLoading />
            ))
          ) : rows.length > 0 ? (
            rows.map((row, i) => (
              <StrikePreviewRow key={i} {...row} />
            ))
          ) : (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                No strike preview data available
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Summary row */}
      {previewData && rows.length > 0 && (
        <div className="mt-4 p-3 bg-gray-50 rounded-lg flex items-center justify-between text-sm">
          <div className="flex items-center gap-4">
            <span className="text-gray-600">
              Total Legs: <strong>{rows.length}</strong>
            </span>
            <span className="text-gray-600">
              Total Lots: <strong>8</strong>
            </span>
          </div>
          <div className="flex items-center gap-2">
            {rows.every(r => r.matches !== false) ? (
              <StatusBadge status="safe" label="All Strikes Valid" size="sm" />
            ) : (
              <StatusBadge status="warning" label="Some Deviations" size="sm" />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default StrikePreviewRow;
