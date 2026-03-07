import React from 'react';
import StressTestPanel from './StressTestPanel';
import ExpiryExposure from './ExpiryExposure';
import StrikeExposure from './StrikeExposure';

/**
 * RiskDashboard — BUG 1 FIX: UCF now computed from positions.
 *   BUG 3 FIX: Futures Floor included in margin floors.
 *
 * All values come from computedMetrics (calculated in hook with CONTRACT_SIZE=0.001).
 */
const RiskDashboard = React.memo(function RiskDashboard({
    computedMetrics, primaryWallet, positions, btcSpotPrice,
}) {
    const m = computedMetrics;
    if (!m) {
        return (
            <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
                Loading risk metrics…
            </div>
        );
    }

    const ucfColor = m.ucf >= 0 ? 'text-emerald-400' : 'text-rose-400';

    return (
        <div className="space-y-4">
            {/* Liquidation Risk Banner */}
            {m.utilization > 90 && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/15 border border-rose-500/40 animate-pulse">
                    <span className="text-xl">🚨</span>
                    <span className="text-rose-400 text-sm font-semibold">
                        Liquidation Risk Detected — Utilization {m.utilization.toFixed(1)}%
                    </span>
                </div>
            )}

            {/* === IM / MM / UCF / Notional Cards === */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricCard
                    label="Initial Margin (IM)"
                    value={m.im.toFixed(4)}
                    color="text-indigo-400"
                    sub="= blocked_margin"
                />
                <MetricCard
                    label="Maintenance Margin (MM)"
                    value={m.mm.toFixed(4)}
                    color="text-amber-400"
                    sub={`= 0.80 × (IM+UCF) - UCF`}
                />
                <MetricCard
                    label="Unrealized Cashflow (UCF)"
                    value={m.ucf.toFixed(4)}
                    color={ucfColor}
                    sub={m.ucf >= 0 ? 'Reduces margin req.' : 'Increases margin req.'}
                />
                <MetricCard
                    label="Total Notional"
                    value={formatCompact(m.totalNotional)}
                    color="text-sky-400"
                    sub={`sum(|size| × mark × 0.001)`}
                />
            </div>

            {/* === UCF IMPACT Section === */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-3">UCF Impact</h4>
                <div className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between">
                        <span className="text-slate-400">Unrealized Cashflows (UCF)</span>
                        <span className={ucfColor}>{m.ucf.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between items-start">
                        <span className="text-slate-400">IM</span>
                        <span className="text-slate-300 text-right">
                            blocked_margin = {m.blockedMargin.toFixed(4)}
                        </span>
                    </div>
                    <div className="flex justify-between items-start">
                        <span className="text-slate-400">MM = 0.80 × (IM + UCF) - UCF</span>
                        <span className="text-slate-300 text-right">
                            {m.mm.toFixed(4)}
                        </span>
                    </div>
                    {m.ucf >= 0 && (
                        <div className="flex items-center gap-1 text-emerald-400/80 mt-1">
                            <span>✅</span>
                            <span>Positive UCF → reduces your IM requirement</span>
                        </div>
                    )}
                    {m.ucf < 0 && (
                        <div className="flex items-center gap-1 text-rose-400/80 mt-1">
                            <span>⚠️</span>
                            <span>Negative UCF → increases your IM requirement</span>
                        </div>
                    )}
                </div>
            </div>

            {/* === Margin Floors (Calculated) === */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                    Margin Floors (Calculated)
                </h4>
                <div className="space-y-2 text-sm">
                    <FloorRow label="Total Floor" value={m.marginFloors.total} />
                    <FloorRow label="Futures Floor" value={m.marginFloors.futures} />
                    <FloorRow label="Long Options Floor" value={m.marginFloors.long_options} />
                    <FloorRow label="Short Options Floor" value={m.marginFloors.short_options} />
                </div>
            </div>

            {/* === Stress Test (self-contained) === */}
            <StressTestPanel
                positions={positions}
                primaryWallet={primaryWallet}
                btcSpotPrice={btcSpotPrice}
            />

            {/* === Expiry + Strike Exposure === */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <ExpiryExposure positions={positions} />
                </div>
                <div>
                    <StrikeExposure positions={positions} />
                </div>
            </div>

            {/* === Margin Formulas (collapsible) === */}
            <details className="text-xs text-slate-600">
                <summary className="cursor-pointer hover:text-slate-400 transition">
                    📐 Margin Formulas (Delta Exchange India)
                </summary>
                <div className="mt-2 p-3 rounded-lg bg-slate-800/40 border border-slate-700/20 font-mono space-y-1">
                    <div>IM = max(Risk Margin, Margin Floor) - UCF</div>
                    <div>MM = 0.80 × (IM + UCF) - UCF</div>
                    <div>Risk Margin = from exchange's SPAN-like calculation</div>
                    <div>Short Options Floor = max(5% × mark × size × 0.001, OM% × size × K × 0.001)</div>
                    <div>Long Options Floor = min(mark_val, max(5% × mark_val, OM% × strike_val))</div>
                    <div>Futures Floor = FM% × max(long_notional, short_notional)</div>
                    <div>OM% = 0.5% (BTC), FM% = 0.5% base, cap 2%</div>
                    <div>1 lot = 0.001 BTC (contract size)</div>
                </div>
            </details>
        </div>
    );
});

function MetricCard({ label, value, color = 'text-slate-200', sub }) {
    return (
        <div className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/40">
            <div className="text-xs text-slate-500 mb-1">{label}</div>
            <div className={`text-lg font-bold tabular-nums ${color}`}>{value}</div>
            {sub && <div className="text-xs text-slate-600 mt-0.5">{sub}</div>}
        </div>
    );
}

function FloorRow({ label, value }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-slate-400">{label}</span>
            <span className="text-slate-200 font-medium tabular-nums">{formatCompact(value)}</span>
        </div>
    );
}

function formatCompact(n) {
    if (n == null) return '—';
    if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(2)}M`;
    if (Math.abs(n) >= 10000) return `${(n / 1000).toFixed(1)}K`;
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(2)}K`;
    return n.toFixed(2);
}

export default RiskDashboard;
