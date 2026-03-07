import React from 'react';

/**
 * PortfolioGreeks — BUG 4 FIX: now scaled by CONTRACT_SIZE = 0.001.
 * Greeks from tickers are per 1 BTC notional → hook multiplies by 0.001.
 *
 * Added unit labels per user request:
 *   Delta → "BTC equivalent"
 *   Gamma → "delta per $1 BTC"
 *   Theta → "per day (USD)"
 *   Vega  → "per 1% IV (USD)"
 */
const PortfolioGreeks = React.memo(function PortfolioGreeks({ computedMetrics }) {
    const greeks = computedMetrics?.greeks;
    if (!greeks) return null;

    const cards = [
        {
            symbol: 'Δ', label: 'Delta',
            value: greeks.delta,
            unit: 'BTC equivalent',
            tip: 'Net directional exposure in BTC. Near 0 = delta-neutral / hedged.',
            format: v => v.toFixed(4),
            colorFn: (v) => Math.abs(v) < 0.5 ? 'text-emerald-400' : Math.abs(v) < 2 ? 'text-amber-400' : 'text-rose-400',
        },
        {
            symbol: 'Γ', label: 'Gamma',
            value: greeks.gamma,
            unit: 'delta per $1 BTC',
            tip: 'Rate of delta change per $1 move in BTC.',
            format: v => v.toFixed(6),
            colorFn: (v) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-amber-400' : 'text-slate-400',
        },
        {
            symbol: 'Θ', label: 'Theta',
            value: greeks.theta,
            unit: 'per day (USD)',
            tip: 'Daily time decay in USD. Positive = earning theta (short premium).',
            format: v => v.toFixed(2),
            colorFn: (v) => v > 0 ? 'text-emerald-400' : 'text-rose-400',
        },
        {
            symbol: 'ν', label: 'Vega',
            value: greeks.vega,
            unit: 'per 1% IV (USD)',
            tip: 'PnL change per 1% implied volatility change in USD.',
            format: v => v.toFixed(2),
            colorFn: (v) => v > 0 ? 'text-sky-400' : 'text-amber-400',
        },
    ];

    return (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {cards.map(g => {
                const color = g.colorFn(g.value);
                return (
                    <div key={g.label}
                        className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/40"
                        title={g.tip}
                    >
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg">{g.symbol}</span>
                            <span className="text-xs text-slate-500">{g.label}</span>
                        </div>
                        <div className={`text-lg font-bold tabular-nums ${color}`}>
                            {g.format(g.value)}
                        </div>
                        <div className="text-xs text-slate-600 mt-0.5">{g.unit}</div>
                    </div>
                );
            })}
        </div>
    );
});

export default PortfolioGreeks;
