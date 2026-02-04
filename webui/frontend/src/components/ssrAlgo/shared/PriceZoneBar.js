/**
 * PriceZoneBar Component
 * 
 * Visual representation of current price relative to max loss zones.
 * Shows safe/warning/danger zones with current price indicator.
 * 
 * Per Implementation Plan: Section 2.3 - shared/PriceZoneBar.js
 * Created: February 3, 2026
 */

import React, { useMemo } from 'react';
import { calculateZoneBarPercentages, getZoneStatus } from '../utils/maxLossCalculator';

/**
 * PriceZoneBar Component
 * 
 * @param {number} currentPrice - Current spot price
 * @param {number} upperMaxLoss - Upper max loss point
 * @param {number} lowerMaxLoss - Lower max loss point
 * @param {number} atmStrike - ATM strike (optional, for reference line)
 * @param {string} size - Bar size: 'sm', 'md', 'lg'
 * @param {boolean} showLabels - Show price labels
 * @param {boolean} showLegend - Show color legend
 * @param {string} className - Additional CSS classes
 */
const PriceZoneBar = ({
  currentPrice,
  upperMaxLoss,
  lowerMaxLoss,
  atmStrike,
  size = 'md',
  showLabels = true,
  showLegend = false,
  className = '',
}) => {
  // Calculate bar percentages
  const barData = useMemo(() => {
    return calculateZoneBarPercentages(currentPrice, upperMaxLoss, lowerMaxLoss);
  }, [currentPrice, upperMaxLoss, lowerMaxLoss]);

  // Get zone status
  const zoneStatus = useMemo(() => {
    return getZoneStatus(currentPrice, upperMaxLoss, lowerMaxLoss);
  }, [currentPrice, upperMaxLoss, lowerMaxLoss]);

  // Size configurations
  const sizeConfig = {
    sm: { height: 'h-4', marker: 'h-6', fontSize: 'text-xs' },
    md: { height: 'h-6', marker: 'h-8', fontSize: 'text-sm' },
    lg: { height: 'h-8', marker: 'h-10', fontSize: 'text-base' },
  };
  
  const config = sizeConfig[size] || sizeConfig.md;

  if (!barData) {
    return (
      <div className={`flex items-center justify-center ${config.height} bg-gray-100 rounded ${className}`}>
        <span className="text-gray-400 text-sm">No zone data available</span>
      </div>
    );
  }

  // Calculate ATM position if provided
  const atmPosition = atmStrike
    ? ((atmStrike - barData.minPrice) / (barData.maxPrice - barData.minPrice)) * 100
    : null;

  return (
    <div className={className}>
      {/* Main bar container */}
      <div className="relative">
        {/* Zone bar */}
        <div className={`flex ${config.height} rounded-lg overflow-hidden`}>
          {/* Lower danger zone (red) */}
          <div
            className="bg-red-200 relative"
            style={{ width: `${barData.lowerZonePercent}%` }}
          >
            {showLabels && barData.lowerZonePercent > 15 && (
              <span className={`absolute inset-0 flex items-center justify-center text-red-700 font-medium ${config.fontSize}`}>
                Danger
              </span>
            )}
          </div>

          {/* Profit zone (green) */}
          <div
            className="bg-green-200 relative"
            style={{ width: `${barData.profitZonePercent}%` }}
          >
            {showLabels && (
              <span className={`absolute inset-0 flex items-center justify-center text-green-700 font-medium ${config.fontSize}`}>
                Profit Zone
              </span>
            )}
          </div>

          {/* Upper danger zone (red) */}
          <div
            className="bg-red-200 relative"
            style={{ width: `${barData.upperZonePercent}%` }}
          >
            {showLabels && barData.upperZonePercent > 15 && (
              <span className={`absolute inset-0 flex items-center justify-center text-red-700 font-medium ${config.fontSize}`}>
                Danger
              </span>
            )}
          </div>
        </div>

        {/* Lower max loss boundary marker */}
        <div
          className="absolute top-0 w-0.5 bg-red-600"
          style={{
            left: `${barData.lowerZonePercent}%`,
            height: config.marker,
            transform: 'translateY(-10%)',
          }}
        />

        {/* Upper max loss boundary marker */}
        <div
          className="absolute top-0 w-0.5 bg-red-600"
          style={{
            left: `${barData.lowerZonePercent + barData.profitZonePercent}%`,
            height: config.marker,
            transform: 'translateY(-10%)',
          }}
        />

        {/* ATM strike marker (if provided) */}
        {atmPosition !== null && atmPosition > 0 && atmPosition < 100 && (
          <div
            className="absolute top-0 w-0.5 bg-blue-500 opacity-50"
            style={{
              left: `${atmPosition}%`,
              height: config.marker,
              transform: 'translateY(-10%)',
            }}
          />
        )}

        {/* Current price marker */}
        <div
          className={`
            absolute top-1/2 transform -translate-y-1/2
            w-3 h-3 rounded-full border-2 border-white shadow-lg
            ${zoneStatus.inDanger ? 'bg-red-500 animate-pulse' : 'bg-blue-600'}
          `}
          style={{
            left: `${barData.currentPositionPercent}%`,
            transform: 'translate(-50%, -50%)',
          }}
        >
          {/* Price tooltip */}
          <div
            className={`
              absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2
              px-2 py-1 bg-gray-800 text-white rounded text-xs whitespace-nowrap
              opacity-0 group-hover:opacity-100 transition-opacity
            `}
          >
            ₹{currentPrice?.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Price labels below bar */}
      {showLabels && (
        <div className="flex justify-between mt-1 text-xs text-gray-500">
          <span>{barData.lowerBoundary?.toLocaleString()}</span>
          <span className="font-medium text-blue-600">
            Current: {currentPrice?.toLocaleString()}
          </span>
          <span>{barData.upperBoundary?.toLocaleString()}</span>
        </div>
      )}

      {/* Legend */}
      {showLegend && (
        <div className="flex items-center justify-center gap-4 mt-2 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-200 rounded" />
            <span>Max Loss Zone</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-green-200 rounded" />
            <span>Profit Zone</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-blue-600 rounded-full" />
            <span>Current Price</span>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Compact zone indicator for cards/headers
 */
export const CompactZoneIndicator = ({
  currentPrice,
  upperMaxLoss,
  lowerMaxLoss,
  className = '',
}) => {
  const zoneStatus = useMemo(() => {
    return getZoneStatus(currentPrice, upperMaxLoss, lowerMaxLoss, 200);
  }, [currentPrice, upperMaxLoss, lowerMaxLoss]);

  const statusConfig = {
    safe: { bg: 'bg-green-100', text: 'text-green-700', label: 'Safe' },
    warning: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Warning' },
    breached: { bg: 'bg-red-100', text: 'text-red-700', label: 'BREACH' },
  };

  const config = statusConfig[zoneStatus.status] || statusConfig.safe;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className={`
          px-2 py-1 rounded-full text-xs font-medium
          ${config.bg} ${config.text}
        `}
      >
        {config.label}
      </div>
      {zoneStatus.nearestDistance !== undefined && (
        <span className="text-xs text-gray-500">
          {Math.round(zoneStatus.nearestDistance)} pts to {zoneStatus.nearestBoundary} boundary
        </span>
      )}
    </div>
  );
};

/**
 * Vertical zone indicator (for sidebar/compact displays)
 */
export const VerticalZoneIndicator = ({
  currentPrice,
  upperMaxLoss,
  lowerMaxLoss,
  height = 200,
  className = '',
}) => {
  const barData = useMemo(() => {
    return calculateZoneBarPercentages(currentPrice, upperMaxLoss, lowerMaxLoss);
  }, [currentPrice, upperMaxLoss, lowerMaxLoss]);

  if (!barData) return null;

  return (
    <div className={`flex ${className}`} style={{ height }}>
      {/* Vertical bar */}
      <div className="w-4 rounded-full overflow-hidden flex flex-col">
        <div
          className="bg-red-200"
          style={{ height: `${barData.upperZonePercent}%` }}
        />
        <div
          className="bg-green-200 relative"
          style={{ height: `${barData.profitZonePercent}%` }}
        >
          {/* Current price marker */}
          <div
            className="absolute left-1/2 w-4 h-2 bg-blue-600 rounded-full transform -translate-x-1/2"
            style={{
              top: `${((100 - barData.currentPositionPercent) / 100) * 100}%`,
            }}
          />
        </div>
        <div
          className="bg-red-200"
          style={{ height: `${barData.lowerZonePercent}%` }}
        />
      </div>

      {/* Labels */}
      <div className="ml-2 flex flex-col justify-between text-xs text-gray-500">
        <span>{barData.maxPrice}</span>
        <span className="text-blue-600 font-medium">{currentPrice}</span>
        <span>{barData.minPrice}</span>
      </div>
    </div>
  );
};

export default PriceZoneBar;
