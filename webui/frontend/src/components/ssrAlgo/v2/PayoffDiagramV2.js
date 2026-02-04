/**
 * Payoff Diagram V2
 * 
 * Purple-themed payoff chart using Recharts.
 * Shows butterfly spread payoff curve with zone markers.
 * Bottom metrics: Net Premium, Positions, Max Profit, Max Loss
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import { TrendingUp, Loader2 } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  Area,
  ComposedChart,
} from 'recharts';

const PayoffDiagramV2 = ({
  payoffCurve = [],
  spotPrice = 0,
  currentPrice = 0,
  maxLossPoints = {},
  breakevens = [],
  netPremium = 0,
  positionCount = 8,
  strategyId = '',
  loading = false,
}) => {
  // Format price for axis
  const formatPrice = (value) => {
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(0)}k`;
    }
    return `$${value}`;
  };

  // Format payoff for axis - smart formatting based on magnitude
  const formatPayoff = (value) => {
    const absVal = Math.abs(value);
    if (absVal >= 1000) {
      return `$${(value / 1000).toFixed(1)}k`;
    } else if (absVal >= 100) {
      return `$${value.toFixed(0)}`;
    } else if (absVal >= 1) {
      return `$${value.toFixed(2)}`;
    }
    return `$${value.toFixed(2)}`;
  };

  // Calculate max profit and max loss from curve
  const maxProfit = maxLossPoints?.max_profit_value || Math.max(...payoffCurve.map(p => p.payoff || 0), 0);
  const maxLoss = maxLossPoints?.max_loss_value || Math.min(...payoffCurve.map(p => p.payoff || 0), 0);
  
  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800/95 border border-slate-600/50 rounded-lg px-3 py-2 shadow-xl">
          <p className="text-xs text-slate-400">Price: ${label?.toLocaleString()}</p>
          <p className={`text-sm font-semibold ${payload[0].value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            Payoff: ${payload[0].value?.toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="rounded-3xl bg-slate-900/50 border border-purple-500/20 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-purple-500/20 bg-gradient-to-r from-purple-500/10 to-transparent">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-purple-400">Payoff Diagram</h2>
        </div>
        {strategyId && (
          <p className="mt-1 text-xs text-slate-500 font-mono">{strategyId}</p>
        )}
      </div>

      {/* Chart Area */}
      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
          </div>
        ) : payoffCurve.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-500">
            <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
            <p>No payoff data available</p>
            <p className="text-sm">Select a session to view payoff curve</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={payoffCurve} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              {/* Grid */}
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
              
              {/* Axes */}
              <XAxis 
                dataKey="price" 
                tickFormatter={formatPrice}
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={{ stroke: '#475569' }}
              />
              <YAxis 
                tickFormatter={formatPayoff}
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={{ stroke: '#475569' }}
                width={60}
              />
              
              {/* Zero line */}
              <ReferenceLine y={0} stroke="#475569" strokeWidth={2} />
              
              {/* Current price marker */}
              {(currentPrice || spotPrice) > 0 && (
                <ReferenceLine 
                  x={currentPrice || spotPrice} 
                  stroke="#06b6d4" 
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: 'Current',
                    position: 'top',
                    fill: '#06b6d4',
                    fontSize: 10
                  }}
                />
              )}
              
              {/* Breakeven lines */}
              {breakevens.map((be, idx) => (
                <ReferenceLine 
                  key={idx}
                  x={be} 
                  stroke="#f59e0b" 
                  strokeDasharray="3 3"
                  opacity={0.6}
                />
              ))}
              
              {/* Max loss zone markers */}
              {maxLossPoints?.upper_trigger && (
                <ReferenceLine 
                  x={maxLossPoints.upper_trigger} 
                  stroke="#ef4444" 
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                />
              )}
              {maxLossPoints?.lower_trigger && (
                <ReferenceLine 
                  x={maxLossPoints.lower_trigger} 
                  stroke="#ef4444" 
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                />
              )}
              
              {/* Tooltip */}
              <Tooltip content={<CustomTooltip />} />
              
              {/* Area fill for profit zone */}
              <defs>
                <linearGradient id="payoffGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
              </defs>
              
              {/* Payoff line */}
              <Line
                type="monotone"
                dataKey="payoff"
                stroke="#06b6d4"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#06b6d4' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}

        {/* Bottom Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 mt-4 p-3 bg-slate-800/30 rounded-xl">
          {/* Net Premium */}
          <div className="flex flex-col">
            <span className="text-xs text-slate-400">Net Premium</span>
            <span className={`text-lg font-bold ${netPremium >= 0 ? 'text-cyan-400' : 'text-red-400'}`}>
              ${netPremium?.toFixed(2)}
            </span>
          </div>
          
          {/* Positions */}
          <div className="flex flex-col">
            <span className="text-xs text-slate-400">Positions</span>
            <span className="text-lg font-bold text-white">{positionCount} legs</span>
          </div>
          
          {/* Max Profit */}
          <div className="flex flex-col">
            <span className="text-xs text-slate-400">Max Profit</span>
            <span className="text-lg font-bold text-green-400">
              ${maxProfit?.toFixed(2)}
            </span>
          </div>
          
          {/* Max Loss */}
          <div className="flex flex-col">
            <span className="text-xs text-slate-400">Max Loss</span>
            <span className="text-lg font-bold text-red-400">
              ${maxLoss?.toFixed(2)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

PayoffDiagramV2.propTypes = {
  payoffCurve: PropTypes.arrayOf(PropTypes.shape({
    price: PropTypes.number,
    payoff: PropTypes.number,
  })),
  spotPrice: PropTypes.number,
  currentPrice: PropTypes.number,
  maxLossPoints: PropTypes.object,
  breakevens: PropTypes.array,
  netPremium: PropTypes.number,
  positionCount: PropTypes.number,
  strategyId: PropTypes.string,
  loading: PropTypes.bool,
};

export default PayoffDiagramV2;
