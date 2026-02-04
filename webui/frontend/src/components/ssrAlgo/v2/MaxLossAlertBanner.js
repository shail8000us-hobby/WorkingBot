/**
 * Max Loss Alert Banner
 * 
 * Red-themed alert banner showing real-time trading status and max loss warnings.
 * Displays: BTC symbol, Current Price, ATM Strike, Trigger Zones, Rounds, Open Legs, Active time
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Clock,
  Target,
  Layers
} from 'lucide-react';

const MaxLossAlertBanner = ({
  underlying = 'BTC',
  currentPrice = 0,
  atmStrike = 0,
  triggerZones = { upper: 0, lower: 0 },
  currentRound = 1,
  totalRounds = 2,
  openLegs = 8,
  activeTime = null,
  inMaxLossZone = false,
  zoneTimeMinutes = 0,
  triggerThresholdMinutes = 10,
  zoneSide = null, // 'upper' or 'lower'
}) => {
  // Format numbers
  const formatPrice = (price) => {
    if (!price) return '-';
    if (price >= 1000) {
      return `$${(price / 1000).toFixed(1)}k`;
    }
    return `$${price.toFixed(0)}`;
  };

  const formatFullPrice = (price) => {
    if (!price) return '-';
    return `$${price.toLocaleString()}`;
  };

  // Calculate price direction relative to ATM
  const priceDirection = currentPrice > atmStrike ? 'up' : currentPrice < atmStrike ? 'down' : 'neutral';

  // Calculate zone direction (which zone is price approaching/in)
  const nearUpperZone = currentPrice >= atmStrike;

  return (
    <div className={`
      relative overflow-hidden rounded-3xl
      ${inMaxLossZone 
        ? 'bg-gradient-to-r from-red-950/90 via-red-900/80 to-red-950/90 border-2 border-red-500/50' 
        : 'bg-gradient-to-r from-slate-900/90 via-slate-800/80 to-slate-900/90 border border-slate-700/50'
      }
      backdrop-blur-sm p-4
    `}>
      {/* Animated glow effect for max loss zone */}
      {inMaxLossZone && (
        <div className="absolute inset-0 bg-red-500/10 animate-pulse" />
      )}

      <div className="relative z-10">
        {/* Top Row: Main Metrics */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
          {/* Underlying + Current Price */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-orange-500">{underlying}</span>
              <span className="text-2xl font-bold text-white">{formatFullPrice(currentPrice)}</span>
            </div>
          </div>

          {/* Metrics Row */}
          <div className="flex flex-wrap items-center gap-6">
            {/* ATM Strike */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">ATM Strike</span>
              <span className="text-lg font-semibold text-cyan-400">{formatPrice(atmStrike)}</span>
              {priceDirection === 'up' && <TrendingUp className="w-4 h-4 text-green-400" />}
              {priceDirection === 'down' && <TrendingDown className="w-4 h-4 text-red-400" />}
            </div>

            {/* Trigger Zones */}
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-400">Trigger</span>
              <span className={`text-lg font-semibold ${nearUpperZone ? 'text-red-400' : 'text-slate-500'}`}>
                {formatPrice(triggerZones.upper)}
              </span>
              <TrendingDown className="w-3 h-3 text-slate-500" />
            </div>

            {/* Rounds */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Rounds</span>
              <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm font-semibold">
                {currentRound}/{totalRounds}
              </span>
            </div>

            {/* Open Legs */}
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-400">Open Legs</span>
              <span className="text-lg font-semibold text-white">{openLegs}</span>
            </div>

            {/* Active Time */}
            {activeTime && (
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-400" />
                <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm font-semibold">
                  {activeTime}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Bottom Row: Max Loss Zone Warning */}
        {inMaxLossZone && (
          <div className="flex items-center justify-between pt-2 border-t border-red-500/30">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-500 animate-pulse" />
              <span className="text-red-500 font-bold text-lg tracking-wide">MAX LOSS ZONE!</span>
            </div>
            <div className="flex items-center gap-6">
              <span className="text-red-300">
                In zone for <span className="font-bold text-red-400">{zoneTimeMinutes.toFixed(1)} min</span>
              </span>
              <span className="text-slate-400">
                Trigger at <span className="font-semibold text-red-400">{triggerThresholdMinutes} min</span>
              </span>
            </div>
          </div>
        )}

        {/* Normal status when not in max loss zone */}
        {!inMaxLossZone && (
          <div className="flex items-center justify-between pt-2 border-t border-slate-700/30">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-green-400 font-medium">Monitoring</span>
            </div>
            <span className="text-sm text-slate-500">
              Zone triggers: Lower {formatPrice(triggerZones.lower)} / Upper {formatPrice(triggerZones.upper)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

MaxLossAlertBanner.propTypes = {
  underlying: PropTypes.string,
  currentPrice: PropTypes.number,
  atmStrike: PropTypes.number,
  triggerZones: PropTypes.shape({
    upper: PropTypes.number,
    lower: PropTypes.number,
  }),
  currentRound: PropTypes.number,
  totalRounds: PropTypes.number,
  openLegs: PropTypes.number,
  activeTime: PropTypes.string,
  inMaxLossZone: PropTypes.bool,
  zoneTimeMinutes: PropTypes.number,
  triggerThresholdMinutes: PropTypes.number,
  zoneSide: PropTypes.oneOf(['upper', 'lower', null]),
};

export default MaxLossAlertBanner;
