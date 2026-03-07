import React, { useState, useMemo } from 'react';

/**
 * PositionsTable — BUG 8 FIX:
 *   - MARGIN column → "NOTIONAL" (abs(size) * markPrice)
 *   - LIQ. PRICE → "N/A" with tooltip explaining PM mode
 *   - Shows enriched data (delta, expiry, strike from parsed symbol)
 */
const CONTRACT_TYPES = [
    { key: '', label: 'All' },
    { key: 'perpetual_futures', label: 'Futures' },
    { key: 'call', label: 'Calls' },
    { key: 'put', label: 'Puts' },
];

const SORT_OPTIONS = [
    { key: 'symbol', label: 'Symbol' },
    { key: 'upnl', label: 'UPnL' },
    { key: 'notional', label: 'Notional' },
    { key: 'size', label: 'Size' },
    { key: 'delta', label: 'Delta' },
];

const PositionsTable = React.memo(function PositionsTable({ positions, onFilterChange }) {
    const [filter, setFilter] = useState('');
    const [search, setSearch] = useState('');
    const [sortBy, setSortBy] = useState('upnl');
    const [sortDir, setSortDir] = useState('desc');
    const [showOnlyLosers, setShowOnlyLosers] = useState(false);
    const [expandedRow, setExpandedRow] = useState(null);

    const { filtered, totals } = useMemo(() => {
        if (!positions) return { filtered: [], totals: {} };
        let list = [...positions];

        // Type filter — use parsed fields
        if (filter) {
            if (filter === 'perpetual_futures') {
                list = list.filter(p => !p.is_option);
            } else if (filter === 'call') {
                list = list.filter(p => p.is_call);
            } else if (filter === 'put') {
                list = list.filter(p => p.is_put);
            }
        }

        // Search
        if (search) {
            const q = search.toLowerCase();
            list = list.filter(p => p.product_symbol?.toLowerCase().includes(q));
        }

        // Winners/losers
        if (showOnlyLosers) list = list.filter(p => p.unrealized_pnl < 0);

        // Sort
        list.sort((a, b) => {
            let va, vb;
            switch (sortBy) {
                case 'symbol': va = a.product_symbol || ''; vb = b.product_symbol || ''; break;
                case 'upnl': va = a.unrealized_pnl || 0; vb = b.unrealized_pnl || 0; break;
                case 'notional': va = a.notional || 0; vb = b.notional || 0; break;
                case 'size': va = Math.abs(a.size || 0); vb = Math.abs(b.size || 0); break;
                case 'delta': va = Math.abs(a.delta || 0); vb = Math.abs(b.delta || 0); break;
                default: va = 0; vb = 0;
            }
            if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
            return sortDir === 'asc' ? va - vb : vb - va;
        });

        // Totals
        const totalUpnl = list.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
        const totalNotional = list.reduce((s, p) => s + (p.notional || 0), 0);

        return {
            filtered: list,
            totals: { upnl: totalUpnl, notional: totalNotional, count: list.length },
        };
    }, [positions, filter, search, sortBy, sortDir, showOnlyLosers]);

    const handleFilter = (key) => {
        setFilter(key);
        // Don't call onFilterChange with parsed types — backend expects contract_types
    };

    const toggleSort = (key) => {
        if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortBy(key); setSortDir('desc'); }
    };

    return (
        <div className="space-y-3">
            {/* Controls Row */}
            <div className="flex items-center gap-2 flex-wrap">
                {/* Filter Tabs */}
                <div className="flex gap-1 bg-slate-800/40 p-1 rounded-lg">
                    {CONTRACT_TYPES.map(({ key, label }) => (
                        <button
                            key={key || 'all'}
                            onClick={() => handleFilter(key)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${filter === key
                                    ? 'bg-indigo-600 text-white shadow-sm'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                                }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>

                {/* Search */}
                <input
                    type="text"
                    placeholder="Search symbol…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="px-3 py-1.5 text-xs rounded-lg bg-slate-800/60 border border-slate-700/40 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-40"
                />

                {/* Sort */}
                <select
                    value={sortBy}
                    onChange={e => setSortBy(e.target.value)}
                    className="px-2 py-1.5 text-xs rounded-lg bg-slate-800/60 border border-slate-700/40 text-slate-300"
                >
                    {SORT_OPTIONS.map(o => <option key={o.key} value={o.key}>Sort: {o.label}</option>)}
                </select>
                <button
                    onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
                    className="px-2 py-1.5 text-xs rounded-lg bg-slate-800/60 border border-slate-700/40 text-slate-400"
                >
                    {sortDir === 'asc' ? '↑' : '↓'}
                </button>

                {/* Losers toggle */}
                <button
                    onClick={() => setShowOnlyLosers(!showOnlyLosers)}
                    className={`px-3 py-1.5 text-xs rounded-lg transition ${showOnlyLosers ? 'bg-rose-600/80 text-white' : 'bg-slate-800/60 text-slate-400 border border-slate-700/40'
                        }`}
                >
                    {showOnlyLosers ? '🔴 Losers only' : 'Losers'}
                </button>

                <span className="text-xs text-slate-500 ml-auto">{totals.count} positions</span>
            </div>

            {/* Table */}
            {filtered.length === 0 ? (
                <div className="text-center text-slate-500 py-6 text-sm">
                    No positions found{filter ? ` for ${filter}` : ''}.
                </div>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-700/40">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-slate-800/60 text-slate-400 text-xs uppercase tracking-wider">
                                <th className="px-3 py-2 text-left cursor-pointer" onClick={() => toggleSort('symbol')}>
                                    Symbol {sortBy === 'symbol' && (sortDir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="px-3 py-2 text-left">Type</th>
                                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => toggleSort('size')}>
                                    Size {sortBy === 'size' && (sortDir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="px-3 py-2 text-right">Entry</th>
                                <th className="px-3 py-2 text-right">Mark</th>
                                <th className="px-3 py-2 text-right cursor-pointer" title="abs(size) × markPrice" onClick={() => toggleSort('notional')}>
                                    Notional {sortBy === 'notional' && (sortDir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => toggleSort('upnl')}>
                                    UPnL {sortBy === 'upnl' && (sortDir === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="px-3 py-2 text-right cursor-pointer" title="Portfolio delta contribution" onClick={() => toggleSort('delta')}>
                                    Delta {sortBy === 'delta' && (sortDir === 'asc' ? '↑' : '↓')}
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/30">
                            {filtered.map((p, i) => {
                                const pnlColor = p.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                                const typeLabel = p.is_call ? 'Call' : p.is_put ? 'Put' : p.is_option ? 'Option' : 'Futures';
                                const isExpanded = expandedRow === i;
                                const positionDelta = p.is_option
                                    ? (p.size || 0) * (p.delta || 0)
                                    : (p.size || 0);

                                return (
                                    <React.Fragment key={`${p.product_symbol}-${i}`}>
                                        <tr
                                            className="hover:bg-slate-700/20 transition cursor-pointer"
                                            onClick={() => setExpandedRow(isExpanded ? null : i)}
                                        >
                                            <td className="px-3 py-2 font-medium text-slate-200">
                                                {p.product_symbol || '—'}
                                            </td>
                                            <td className="px-3 py-2">
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${p.is_call ? 'bg-emerald-500/20 text-emerald-400' :
                                                        p.is_put ? 'bg-rose-500/20 text-rose-400' :
                                                            'bg-sky-500/20 text-sky-400'
                                                    }`}>
                                                    {typeLabel}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                                {p.size ?? '—'}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                                {p.entry_price?.toFixed(2) ?? '—'}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                                {p.mark_price?.toFixed(2) ?? '—'}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                                {formatCompact(p.notional || 0)}
                                            </td>
                                            <td className={`px-3 py-2 text-right tabular-nums font-medium ${pnlColor}`}>
                                                {p.unrealized_pnl?.toFixed(4) ?? '—'}
                                            </td>
                                            <td className={`px-3 py-2 text-right tabular-nums ${positionDelta >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'
                                                }`}>
                                                {positionDelta.toFixed(4)}
                                            </td>
                                        </tr>
                                        {/* Expanded detail row */}
                                        {isExpanded && (
                                            <tr className="bg-slate-800/40">
                                                <td colSpan={8} className="px-4 py-3">
                                                    <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-xs">
                                                        <div>
                                                            <span className="text-slate-500">Strike</span>
                                                            <div className="text-slate-200 font-medium">
                                                                {p.parsed_strike?.toLocaleString() || 'N/A'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Expiry</span>
                                                            <div className="text-slate-200">
                                                                {p.parsed_expiry_display || 'Perpetual'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Gamma (Γ)</span>
                                                            <div className="text-slate-200">{p.gamma?.toFixed(6) || '—'}</div>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Theta (Θ)</span>
                                                            <div className={`${p.theta > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                                {p.theta?.toFixed(4) || '—'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Vega (ν)</span>
                                                            <div className="text-slate-200">{p.vega?.toFixed(4) || '—'}</div>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Liq. Price</span>
                                                            <div className="text-slate-500" title="Individual liquidation prices are not available in Portfolio Margin mode. Your portfolio liquidates as a whole when equity < Maintenance Margin.">
                                                                N/A ⓘ
                                                            </div>
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                        {/* Aggregate Footer */}
                        <tfoot>
                            <tr className="bg-slate-800/80 text-xs font-semibold border-t border-slate-600/50">
                                <td className="px-3 py-2 text-slate-400" colSpan={5}>
                                    TOTAL ({totals.count} positions)
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums text-slate-200">
                                    {formatCompact(totals.notional)}
                                </td>
                                <td className={`px-3 py-2 text-right tabular-nums font-medium ${totals.upnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {totals.upnl?.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-right text-slate-500"></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}

            {/* PM Mode note */}
            <div className="text-xs text-slate-600 flex items-center gap-1">
                <span>ⓘ</span>
                <span>
                    In Portfolio Margin mode, margin is calculated at the portfolio level.
                    Individual liquidation prices and per-position margins are not provided by the exchange.
                </span>
            </div>
        </div>
    );
});

function formatCompact(n) {
    if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(2)}M`;
    if (Math.abs(n) >= 10000) return `${(n / 1000).toFixed(1)}K`;
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(2)}K`;
    return n.toFixed(2);
}

export default PositionsTable;
