import React, { useMemo } from 'react';

/**
 * ExpiryExposure — BUG 5a FIX: Groups positions by parsed expiry date from symbol.
 * Symbol format: P-BTC-70000-200326 → expiry 20-03-2026
 *
 * BUG 5b: Net delta now calculated from enriched positions (greeks from tickers)
 * BUG 5c: Shows notional instead of per-position margin (which is 0 in PM mode)
 */
const ExpiryExposure = React.memo(function ExpiryExposure({ positions }) {
    const groups = useMemo(() => {
        if (!positions || positions.length === 0) return [];

        const now = Date.now();
        const map = {};

        for (const p of positions) {
            // BUG 5a FIX: Use parsed_expiry from symbol, not the API field
            const key = p.parsed_expiry || p.expiry_date || 'Perpetual';
            const displayKey = p.parsed_expiry_display || key;
            if (!map[key]) {
                map[key] = {
                    expiry: key,
                    expiryDisplay: displayKey,
                    positions: [],
                    netDelta: 0,
                    totalNotional: 0,
                    totalUpnl: 0,
                    count: 0,
                    dte: null,
                };
            }
            map[key].positions.push(p);
            // BUG 5b FIX: Use enriched delta from tickers
            map[key].netDelta += (p.size || 0) * (p.delta || (p.is_option ? 0 : 1));
            // BUG 5c FIX: Show notional instead of margin
            map[key].totalNotional += p.notional || 0;
            map[key].totalUpnl += p.unrealized_pnl || 0;
            map[key].count += 1;

            // Calculate DTE from parsed expiry
            if (key !== 'Perpetual' && !map[key].dte) {
                const expiry = new Date(key);
                if (!isNaN(expiry.getTime())) {
                    map[key].dte = Math.max(0, Math.ceil((expiry.getTime() - now) / (1000 * 60 * 60 * 24)));
                }
            }
        }

        return Object.values(map).sort((a, b) => {
            if (a.dte === null) return 1;
            if (b.dte === null) return -1;
            return a.dte - b.dte;
        });
    }, [positions]);

    if (groups.length === 0) {
        return (
            <div className="text-center text-slate-500 py-4 text-sm">
                No position expiry data available.
            </div>
        );
    }

    const totalNotionalAll = groups.reduce((s, g) => s + g.totalNotional, 0);

    return (
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40">
            <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                📅 Expiry Exposure
            </h4>
            <div className="space-y-2">
                {groups.map(g => {
                    const dteColor = g.dte !== null
                        ? g.dte <= 3 ? 'text-rose-400' : g.dte <= 7 ? 'text-orange-400' : 'text-slate-300'
                        : 'text-slate-500';
                    const notionalPct = totalNotionalAll > 0 ? (g.totalNotional / totalNotionalAll * 100) : 0;

                    return (
                        <div key={g.expiry} className="p-3 bg-slate-900/40 rounded-lg border border-slate-700/20">
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                    <span className={`text-sm font-medium ${dteColor}`}>
                                        {g.expiry === 'Perpetual' ? '♾️ Perpetual' : g.expiryDisplay}
                                    </span>
                                    {g.dte !== null && (
                                        <span className={`text-xs px-2 py-0.5 rounded-full ${g.dte <= 3 ? 'bg-rose-500/20 text-rose-400' :
                                                g.dte <= 7 ? 'bg-orange-500/20 text-orange-400' :
                                                    'bg-slate-700/50 text-slate-400'
                                            }`}>
                                            {g.dte}d
                                        </span>
                                    )}
                                </div>
                                <span className="text-xs text-slate-500">{g.count} positions</span>
                            </div>
                            <div className="flex gap-4 text-xs">
                                <span className="text-slate-500">
                                    Net Δ: <span className={Math.abs(g.netDelta) > 0.0001 ? (g.netDelta >= 0 ? 'text-emerald-400' : 'text-rose-400') : 'text-slate-400'}>
                                        {g.netDelta.toFixed(4)}
                                    </span>
                                </span>
                                <span className="text-slate-500">
                                    Notional: <span className="text-slate-300">{formatCompact(g.totalNotional)}</span>
                                </span>
                                <span className="text-slate-500">
                                    UPnL: <span className={g.totalUpnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                                        {g.totalUpnl.toFixed(4)}
                                    </span>
                                </span>
                            </div>
                            {/* Notional concentration bar */}
                            <div className="w-full h-1 bg-slate-700/50 rounded-full mt-2 overflow-hidden">
                                <div className="h-full bg-indigo-500/60 rounded-full"
                                    style={{ width: `${Math.min(notionalPct, 100)}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
});

function formatCompact(n) {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toFixed(2);
}

export default ExpiryExposure;
