import React, { useMemo } from 'react';

/**
 * StrikeExposure — BUG 5d FIX: horizontal bar chart of net delta at each strike.
 *
 * Uses parsed_strike and is_option from enriched positions (parsed from symbol name).
 * Previously failed because it checked position.strike_price which was null.
 */
const StrikeExposure = React.memo(function StrikeExposure({ positions }) {
    const strikes = useMemo(() => {
        if (!positions || positions.length === 0) return [];

        const map = {};
        for (const p of positions) {
            // BUG 5d FIX: use parsed_strike from symbol, not API field
            if (!p.is_option || p.parsed_strike == null) continue;
            const key = p.parsed_strike;
            if (!map[key]) {
                map[key] = { strike: key, netDelta: 0, calls: 0, puts: 0, totalSize: 0 };
            }
            // Use enriched delta from tickers
            map[key].netDelta += (p.size || 0) * (p.delta || 0);
            map[key].totalSize += Math.abs(p.size || 0);
            if (p.is_call) map[key].calls += Math.abs(p.size || 0);
            if (p.is_put) map[key].puts += Math.abs(p.size || 0);
        }

        return Object.values(map).sort((a, b) => a.strike - b.strike);
    }, [positions]);

    if (strikes.length === 0) {
        return (
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40">
                <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                    🎯 Strike Exposure
                </h4>
                <div className="text-center text-slate-500 py-4 text-sm">
                    No options positions to chart strike exposure.
                </div>
            </div>
        );
    }

    const maxDelta = Math.max(...strikes.map(s => Math.abs(s.netDelta)), 0.0001);

    return (
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40">
            <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                🎯 Strike Exposure (Net Delta)
            </h4>
            <div className="space-y-1.5">
                {strikes.map(s => {
                    const pct = (Math.abs(s.netDelta) / maxDelta) * 100;
                    const isLong = s.netDelta >= 0;
                    return (
                        <div key={s.strike} className="flex items-center gap-2 text-xs">
                            <span className="text-slate-400 w-16 text-right tabular-nums font-mono">
                                {s.strike.toLocaleString()}
                            </span>
                            <div className="flex-1 flex items-center h-5">
                                <div className="w-full relative h-4">
                                    {isLong ? (
                                        <div
                                            className="absolute left-1/2 h-full rounded-r bg-emerald-500/60"
                                            style={{ width: `${pct / 2}%` }}
                                        />
                                    ) : (
                                        <div
                                            className="absolute h-full rounded-l bg-rose-500/60"
                                            style={{ right: '50%', width: `${pct / 2}%` }}
                                        />
                                    )}
                                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-600" />
                                </div>
                            </div>
                            <span className={`w-20 text-right tabular-nums font-medium ${isLong ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {s.netDelta.toFixed(4)}
                            </span>
                            <span className="w-16 text-right text-slate-600">
                                {s.calls > 0 && <span className="text-emerald-500/60">C:{s.calls} </span>}
                                {s.puts > 0 && <span className="text-rose-500/60">P:{s.puts}</span>}
                            </span>
                        </div>
                    );
                })}
            </div>
            <div className="flex justify-between text-xs text-slate-600 mt-2 px-16">
                <span>◀ Short</span>
                <span>Long ▶</span>
            </div>
        </div>
    );
});

export default StrikeExposure;
