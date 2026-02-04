/**
 * Position Legs Table V2
 * 
 * Purple-themed table showing active position legs.
 * Displays: Leg (with colored dots), Strike, Qty, Side badge, Entry price
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import { Table2 } from 'lucide-react';

const PositionLegsTableV2 = ({ positions = [], totalLegs = null }) => {
  // Flatten positions to get individual legs
  const legs = [];
  positions.forEach((position, posIdx) => {
    // Each position in SSR Algo has multiple legs (typically 8 per deployment)
    // Position structure: { atm_strike, otm_ce_buy_strike, otm_pe_buy_strike, far_otm_ce_strike, far_otm_pe_strike, ... }
    
    if (position.atm_strike) {
      // ATM CE (Sell)
      legs.push({
        id: `${posIdx}-atm-ce`,
        type: 'ATM',
        optionType: 'CE',
        strike: position.atm_strike,
        side: 'SELL',
        qty: -1,
        entry: position.atm_ce_entry || position.atm_ce_premium,
        color: '#ef4444' // Red for sell
      });
      // ATM PE (Sell)
      legs.push({
        id: `${posIdx}-atm-pe`,
        type: 'ATM',
        optionType: 'PE',
        strike: position.atm_strike,
        side: 'SELL',
        qty: -1,
        entry: position.atm_pe_entry || position.atm_pe_premium,
        color: '#ef4444'
      });
    }
    
    if (position.otm_ce_buy_strike) {
      legs.push({
        id: `${posIdx}-otm-ce`,
        type: 'OTM',
        optionType: 'CE',
        strike: position.otm_ce_buy_strike,
        side: 'BUY',
        qty: 1,
        entry: position.otm_ce_entry || position.otm_ce_buy_premium,
        color: '#22c55e' // Green for buy
      });
    }
    
    if (position.otm_pe_buy_strike) {
      legs.push({
        id: `${posIdx}-otm-pe`,
        type: 'OTM',
        optionType: 'PE',
        strike: position.otm_pe_buy_strike,
        side: 'BUY',
        qty: 1,
        entry: position.otm_pe_entry || position.otm_pe_buy_premium,
        color: '#22c55e'
      });
    }
    
    if (position.far_otm_ce_strike) {
      legs.push({
        id: `${posIdx}-far-ce`,
        type: 'FAR',
        optionType: 'CE',
        strike: position.far_otm_ce_strike,
        side: 'BUY',
        qty: 1,
        entry: position.far_otm_ce_entry || position.far_otm_ce_premium,
        color: '#22c55e'
      });
    }
    
    if (position.far_otm_pe_strike) {
      legs.push({
        id: `${posIdx}-far-pe`,
        type: 'FAR',
        optionType: 'PE',
        strike: position.far_otm_pe_strike,
        side: 'BUY',
        qty: 1,
        entry: position.far_otm_pe_entry || position.far_otm_pe_premium,
        color: '#22c55e'
      });
    }
  });

  const displayLegs = legs.slice(0, 8); // Show first 8 legs
  const legCount = totalLegs || legs.length;

  return (
    <div className="rounded-3xl bg-slate-900/50 border border-purple-500/20 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-purple-500/20 bg-gradient-to-r from-purple-500/10 to-transparent">
        <div className="flex items-center gap-2">
          <Table2 className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-purple-400">Position Legs</h2>
          <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded-lg text-sm">
            {legCount} total
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-800/30">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Leg</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Strike</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wider">Qty</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wider">Side</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Entry $</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {displayLegs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No positions loaded
                </td>
              </tr>
            ) : (
              displayLegs.map((leg, idx) => (
                <tr key={leg.id} className="hover:bg-slate-800/30 transition-colors">
                  {/* Leg with colored dot */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: leg.color }}
                      />
                      <span className="text-slate-300 font-medium">{leg.type} {leg.optionType}</span>
                    </div>
                  </td>
                  
                  {/* Strike */}
                  <td className="px-4 py-3">
                    <span className="text-white font-semibold">{leg.strike?.toLocaleString()}</span>
                  </td>
                  
                  {/* Qty - colored */}
                  <td className="px-4 py-3 text-center">
                    <span className={`font-semibold ${leg.qty > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {leg.qty > 0 ? `+${leg.qty}` : leg.qty}
                    </span>
                  </td>
                  
                  {/* Side badge */}
                  <td className="px-4 py-3 text-center">
                    <span className={`
                      inline-flex px-2 py-0.5 rounded text-xs font-medium
                      ${leg.side === 'BUY' 
                        ? 'bg-green-500/20 text-green-400' 
                        : 'bg-red-500/20 text-red-400'
                      }
                    `}>
                      {leg.side}
                    </span>
                  </td>
                  
                  {/* Entry price */}
                  <td className="px-4 py-3 text-right">
                    <span className="text-slate-300">
                      {leg.entry ? `$${leg.entry.toFixed(2)}` : '-'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

PositionLegsTableV2.propTypes = {
  positions: PropTypes.array,
  totalLegs: PropTypes.number,
};

export default PositionLegsTableV2;
