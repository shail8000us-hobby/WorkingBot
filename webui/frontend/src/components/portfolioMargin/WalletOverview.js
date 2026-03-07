import React, { useMemo } from 'react';

/**
 * WalletOverview — displays balance, available balance, blocked margin,
 * portfolio margin, and a utilization gauge.
 *
 * BUG 1 FIX: Computes utilization directly from wallet data
 * (blocked_margin / balance * 100), no longer depends on riskData.
 */
const WalletOverview = React.memo(function WalletOverview({ wallets }) {
    const primary = useMemo(() => {
        if (!wallets || wallets.length === 0) return null;
        return wallets.find(w => w.balance > 0) || wallets[0];
    }, [wallets]);

    if (!primary) {
        return (
            <div className="text-center text-slate-500 py-8">
                No wallet data available. Connect WebSocket or check API credentials.
            </div>
        );
    }

    // BUG 1 FIX: Compute utilization directly from wallet data
    const utilization = primary.balance > 0
        ? (primary.blocked_margin / primary.balance) * 100
        : 0;

    const cards = [
        { label: 'Balance', value: primary.balance, color: 'text-slate-100', icon: '💰' },
        { label: 'Available Balance', value: primary.available_balance, color: 'text-emerald-400', icon: '✅' },
        { label: 'Blocked Margin', value: primary.blocked_margin, color: 'text-amber-400', icon: '🔒' },
        { label: 'Portfolio Margin', value: primary.portfolio_margin, color: 'text-sky-400', icon: '📊' },
        { label: 'Position Margin', value: primary.position_margin, color: 'text-violet-400', icon: '📈' },
        { label: 'Order Margin', value: primary.order_margin, color: 'text-pink-400', icon: '📋' },
    ];

    const utilizationColor = utilization > 85
        ? 'text-rose-400' : utilization > 75
            ? 'text-orange-400' : utilization > 60
                ? 'text-amber-400' : 'text-emerald-400';

    const barGradient = utilization > 85
        ? 'bg-gradient-to-r from-rose-500 to-red-600' : utilization > 75
            ? 'bg-gradient-to-r from-orange-500 to-rose-500' : utilization > 60
                ? 'bg-gradient-to-r from-amber-500 to-orange-500'
                : 'bg-gradient-to-r from-emerald-500 to-teal-500';

    return (
        <div className="space-y-4">
            {/* Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {cards.map(({ label, value, color, icon }) => (
                    <div key={label} className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/40">
                        <div className="text-xs text-slate-500 mb-1">{icon} {label}</div>
                        <div className={`text-lg font-semibold tabular-nums ${color}`}>
                            {typeof value === 'number' ? value.toFixed(4) : '—'}
                        </div>
                    </div>
                ))}
            </div>

            {/* Utilization Gauge */}
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-slate-400">Margin Utilization</span>
                    <span className={`text-sm font-semibold tabular-nums ${utilizationColor}`}>
                        {utilization.toFixed(1)}%
                    </span>
                </div>
                <div className="w-full h-3 bg-slate-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${barGradient}`}
                        style={{ width: `${Math.min(utilization, 100)}%` }}
                    />
                </div>
                <div className="flex justify-between text-xs text-slate-600 mt-1">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                </div>
            </div>

            {/* Asset Info */}
            {primary.asset_symbol && (
                <div className="text-xs text-slate-500 text-right">
                    Asset: {primary.asset_symbol} (ID: {primary.asset_id})
                </div>
            )}
        </div>
    );
});

export default WalletOverview;
