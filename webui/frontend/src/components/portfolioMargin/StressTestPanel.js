import React, { useState, useCallback } from 'react';

/**
 * StressTestPanel — BUG 2 FIX: Self-contained stress test with local state.
 *
 * Receives positions + wallet directly and computes stress scenarios locally.
 * No callback to parent hook — avoids state propagation issues.
 *
 * Uses CONTRACT_SIZE = 0.001 BTC for correct PnL scaling.
 */
const CONTRACT_SIZE = 0.001;
const PRESETS = [-30, -20, -10, -5, 5, 10, 20, 30];

function computeStressScenarios(positions, wallet, pctMoves, btcSpotPrice) {
    if (!positions?.length || !wallet) return [];
    const balance = wallet.balance || 0;
    const blockedMargin = wallet.blocked_margin || 0;
    const mm = 0.80 * blockedMargin; // Maintenance margin

    return pctMoves.map(pct => {
        const priceChange = btcSpotPrice * (pct / 100);
        const newPrice = btcSpotPrice + priceChange;
        let totalPnl = 0;

        for (const p of positions) {
            const size = p.size || 0;
            if (p.is_option) {
                // Options: delta + gamma approximation, scaled by CONTRACT_SIZE
                let pnl = size * (p.delta || 0) * priceChange * CONTRACT_SIZE;
                pnl += 0.5 * size * (p.gamma || 0) * (priceChange ** 2) * CONTRACT_SIZE;
                totalPnl += pnl;
            } else {
                // Futures: linear PnL, scaled by CONTRACT_SIZE
                totalPnl += size * priceChange * CONTRACT_SIZE;
            }
        }

        const stressedBalance = balance + totalPnl;
        const buffer = stressedBalance - mm;
        const status = buffer > mm * 0.1 ? 'SAFE' : buffer > 0 ? 'WARNING' : 'MARGIN CALL';

        return {
            scenario: `BTC ${pct > 0 ? '+' : ''}${pct}%`,
            pct_move: pct,
            new_price: Math.round(newPrice * 100) / 100,
            stressed_pnl: Math.round(totalPnl * 10000) / 10000,
            stressed_balance: Math.round(stressedBalance * 10000) / 10000,
            margin_required: Math.round(mm * 10000) / 10000,
            buffer: Math.round(buffer * 10000) / 10000,
            status,
        };
    });
}

const StressTestPanel = React.memo(function StressTestPanel({ positions, primaryWallet, btcSpotPrice }) {
    const [scenarios, setScenarios] = useState([]);
    const [customPct, setCustomPct] = useState('');
    const [running, setRunning] = useState(false);

    // Use live BTC price from status, fallback to market price
    const spotPrice = btcSpotPrice || 68000;

    const handleRun = useCallback((pctMoves) => {
        setRunning(true);
        const results = computeStressScenarios(positions, primaryWallet, pctMoves, spotPrice);
        setScenarios(results);
        setRunning(false);
    }, [positions, primaryWallet, spotPrice]);

    const handleCustom = useCallback(() => {
        const val = parseFloat(customPct);
        if (isNaN(val)) return;
        handleRun([val]);
    }, [customPct, handleRun]);

    const handleRunAll = useCallback(() => {
        handleRun(PRESETS);
    }, [handleRun]);

    return (
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40 space-y-4">
            <div className="flex items-center justify-between">
                <h4 className="text-xs text-slate-500 uppercase tracking-wider">
                    🔥 Portfolio Stress Test
                </h4>
                <span className="text-xs text-slate-600">
                    {positions?.length || 0} positions · BTC ${spotPrice.toLocaleString()}
                    · Balance: {primaryWallet?.balance?.toFixed(2) || '—'}
                </span>
            </div>

            {/* Preset Buttons */}
            <div className="flex gap-2 flex-wrap">
                {PRESETS.map(pct => (
                    <button
                        key={pct}
                        onClick={() => handleRun([pct])}
                        disabled={running}
                        className={`px-3 py-1.5 text-xs font-medium rounded-lg transition disabled:opacity-40 ${pct < 0
                                ? 'bg-rose-600/20 border border-rose-500/30 text-rose-400 hover:bg-rose-600/40'
                                : 'bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-600/40'
                            }`}
                    >
                        {pct > 0 ? '+' : ''}{pct}%
                    </button>
                ))}
            </div>

            {/* Custom + Run All */}
            <div className="flex gap-2 items-center">
                <input
                    type="number"
                    value={customPct}
                    onChange={e => setCustomPct(e.target.value)}
                    placeholder="Custom %"
                    className="px-3 py-1.5 text-xs rounded-lg bg-slate-900/60 border border-slate-700/40 text-slate-200 placeholder-slate-600 w-24 focus:outline-none focus:border-indigo-500"
                />
                <button
                    onClick={handleCustom}
                    disabled={running || !customPct}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-600/80 text-white hover:bg-indigo-500 transition disabled:opacity-40"
                >
                    Run Custom
                </button>
                <button
                    onClick={handleRunAll}
                    disabled={running}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-600/80 text-white hover:bg-violet-500 transition disabled:opacity-40"
                >
                    🚀 Run All
                </button>
            </div>

            {/* Results Table — renders when scenarios array has data */}
            {Array.isArray(scenarios) && scenarios.length > 0 && (
                <div className="overflow-x-auto rounded-lg border border-slate-700/30">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="bg-slate-800/80 text-slate-400 uppercase tracking-wider">
                                <th className="px-3 py-2 text-left">Scenario</th>
                                <th className="px-3 py-2 text-right">BTC Price</th>
                                <th className="px-3 py-2 text-right">Est. PnL</th>
                                <th className="px-3 py-2 text-right">Est. Balance</th>
                                <th className="px-3 py-2 text-right">Buffer</th>
                                <th className="px-3 py-2 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/20">
                            {scenarios.map((s, i) => {
                                const rowBg = s.status === 'MARGIN CALL' ? 'bg-rose-500/5'
                                    : s.status === 'WARNING' ? 'bg-amber-500/5' : '';
                                return (
                                    <tr key={i} className={`${rowBg} hover:bg-slate-700/20`}>
                                        <td className="px-3 py-2 font-medium text-slate-300">
                                            {s.scenario}
                                        </td>
                                        <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                            ${s.new_price?.toLocaleString()}
                                        </td>
                                        <td className={`px-3 py-2 text-right tabular-nums font-medium ${s.stressed_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                                            }`}>
                                            {s.stressed_pnl?.toFixed(4)}
                                        </td>
                                        <td className="px-3 py-2 text-right tabular-nums text-slate-300">
                                            {s.stressed_balance?.toFixed(4)}
                                        </td>
                                        <td className={`px-3 py-2 text-right tabular-nums ${s.buffer >= 0 ? 'text-emerald-400' : 'text-rose-400'
                                            }`}>
                                            {s.buffer?.toFixed(4)}
                                        </td>
                                        <td className="px-3 py-2 text-center">
                                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.status === 'MARGIN CALL'
                                                    ? 'bg-rose-500/20 text-rose-400'
                                                    : s.status === 'WARNING'
                                                        ? 'bg-amber-500/20 text-amber-400'
                                                        : 'bg-emerald-500/20 text-emerald-400'
                                                }`}>
                                                {s.status === 'MARGIN CALL' ? '🔴' : s.status === 'WARNING' ? '⚠️' : '✅'} {s.status}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Hint when no results */}
            {(!Array.isArray(scenarios) || scenarios.length === 0) && (
                <div className="text-center text-xs text-slate-600 py-2">
                    Click a scenario button or "Run All" to see stress test results
                </div>
            )}
        </div>
    );
});

export default StressTestPanel;
