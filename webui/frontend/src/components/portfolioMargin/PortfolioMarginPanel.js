import React, { useState, useCallback } from 'react';
import { usePortfolioMargin } from './usePortfolioMargin';
import MarginModeSwitch from './MarginModeSwitch';
import WalletOverview from './WalletOverview';
import PositionsTable from './PositionsTable';
import RiskDashboard from './RiskDashboard';
import WebSocketStatus from './WebSocketStatus';
import MarginHistoryChart from './MarginHistoryChart';
import PortfolioGreeks from './PortfolioGreeks';

/**
 * PortfolioMarginPanel — main panel orchestrating all sub-components.
 *
 * All computed data comes from the usePortfolioMargin hook.
 * This component passes pre-computed metrics to children — no child does its own fetching.
 *
 * BUG 7 FIX (previous): Efficiency displayed as leverage ratio (Xx)
 * Updated: passes positions + wallet to RiskDashboard for self-contained StressTest
 * Updated: passes btcSpotPrice to RiskDashboard
 */

const TABS = [
    { key: 'overview', label: '📊 Overview' },
    { key: 'positions', label: '📈 Positions' },
    { key: 'risk', label: '🛡️ Risk' },
    { key: 'history', label: '📉 History' },
];

const PortfolioMarginPanel = React.memo(function PortfolioMarginPanel() {
    const [activeTab, setActiveTab] = useState('overview');

    const {
        status,
        wallet,
        positions,
        riskMatrix,
        wsStatus,
        history,
        loading,
        error,
        lastUpdated,
        primaryWallet,
        computedMetrics,
        refreshAll,
        fetchPositions,
        switchMarginMode,
        startWebSocket,
        stopWebSocket,
        exportData,
    } = usePortfolioMargin({ refreshInterval: 15000 });

    const handleFilterChange = useCallback((contractType) => {
        fetchPositions(contractType);
    }, [fetchPositions]);

    // Single source for margin mode
    const marginMode = status?.margin_mode || 'unknown';
    const m = computedMetrics;

    // BTC spot price from WebSocket or fallback
    const btcSpotPrice = parseFloat(
        status?.portfolio_margin_ws?.spot_price || 68000
    );

    // Margin call warning
    const marginCallWarning = m && (m.utilization > 90);

    return (
        <div className="space-y-4">
            {/* Margin Call Warning Banner */}
            {marginCallWarning && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/15 border border-rose-500/40 animate-pulse">
                    <span className="text-2xl">🚨</span>
                    <div className="flex-1">
                        <div className="text-rose-400 font-bold text-sm">
                            ⚠️ MARGIN CALL WARNING — Utilization at {m.utilization.toFixed(1)}%
                        </div>
                        <div className="text-xs text-rose-300/70 mt-0.5">
                            Reduce positions or add margin immediately.
                        </div>
                    </div>
                    <button
                        onClick={refreshAll}
                        className="px-3 py-1.5 text-xs rounded-lg bg-rose-600/60 text-white hover:bg-rose-500 transition"
                    >
                        Refresh
                    </button>
                </div>
            )}

            {/* Error Banner */}
            {error && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
                    <span>⚠️</span>
                    <span>{error}</span>
                    <button onClick={refreshAll} className="ml-auto text-xs underline opacity-70 hover:opacity-100">Retry</button>
                </div>
            )}

            {/* WebSocket Status + Controls */}
            <div className="flex items-center gap-3">
                <div className="flex-1">
                    <WebSocketStatus
                        wsStatus={wsStatus}
                        wallet={wallet}
                        onStart={startWebSocket}
                        onStop={stopWebSocket}
                        lastUpdated={lastUpdated}
                    />
                </div>
                <button
                    onClick={refreshAll}
                    disabled={loading}
                    className="px-3 py-2 rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 text-xs font-medium transition disabled:opacity-40"
                    title="Refresh all data"
                >
                    {loading ? '⏳' : '🔄'} Refresh
                </button>
                <button
                    onClick={() => exportData('json')}
                    className="px-3 py-2 rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 text-xs font-medium transition"
                    title="Export data as JSON"
                >
                    📥 Export
                </button>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 bg-slate-800/40 p-1 rounded-xl">
                {TABS.map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg transition ${activeTab === key
                                ? 'bg-indigo-600/90 text-white shadow-sm'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                            }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="min-h-[300px]">
                {/* OVERVIEW TAB */}
                {activeTab === 'overview' && (
                    <div className="space-y-4">
                        <MarginModeSwitch
                            currentMode={marginMode}
                            onSwitch={switchMarginMode}
                            loading={loading}
                        />
                        <WalletOverview wallets={wallet} />

                        {/* Portfolio Greeks — BUG 4 FIX: scaled by 0.001 + unit labels */}
                        <PortfolioGreeks computedMetrics={m} />

                        {/* Quick Stats */}
                        {m && (
                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                                <QuickStat
                                    label="Margin Mode"
                                    value={capitalizeFirst(marginMode)}
                                    color={marginMode === 'portfolio' ? 'text-emerald-400' : 'text-amber-400'}
                                />
                                <QuickStat
                                    label="Utilization"
                                    value={`${m.utilization.toFixed(1)}%`}
                                    color={m.utilization > 85 ? 'text-rose-400' : m.utilization > 60 ? 'text-amber-400' : 'text-emerald-400'}
                                />
                                <QuickStat
                                    label="Efficiency"
                                    value={`${m.efficiency.toFixed(1)}x`}
                                    color="text-sky-400"
                                    tooltip="Total Notional / Blocked Margin — how much exposure per unit of margin"
                                />
                                <QuickStat
                                    label="NLV"
                                    value={m.nlv.toFixed(4)}
                                    color="text-violet-400"
                                    tooltip="Net Liquidation Value = Balance + Unrealized PnL"
                                />
                                <QuickStat
                                    label="Liq. Risk"
                                    value={m.utilization > 90 ? '⚠️ YES' : '✅ NO'}
                                    color={m.utilization > 90 ? 'text-rose-400' : 'text-emerald-400'}
                                />
                            </div>
                        )}
                    </div>
                )}

                {/* POSITIONS TAB */}
                {activeTab === 'positions' && (
                    <PositionsTable
                        positions={positions}
                        onFilterChange={handleFilterChange}
                    />
                )}

                {/* RISK TAB — passes positions + wallet for self-contained stress test */}
                {activeTab === 'risk' && (
                    <RiskDashboard
                        computedMetrics={m}
                        primaryWallet={primaryWallet}
                        positions={positions}
                        btcSpotPrice={btcSpotPrice}
                    />
                )}

                {/* HISTORY TAB */}
                {activeTab === 'history' && (
                    <div className="space-y-4">
                        <MarginHistoryChart history={history} height={200} />
                        <div className="flex gap-2 justify-end">
                            <button
                                onClick={() => exportData('csv')}
                                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 transition"
                            >
                                📥 Export CSV
                            </button>
                            <button
                                onClick={() => exportData('json')}
                                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 transition"
                            >
                                📥 Export JSON
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Loading Overlay */}
            {loading && !status && (
                <div className="flex items-center justify-center py-12">
                    <div className="flex items-center gap-3 text-slate-400">
                        <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-sm">Loading portfolio margin data…</span>
                    </div>
                </div>
            )}
        </div>
    );
});

function QuickStat({ label, value, color = 'text-slate-200', tooltip }) {
    return (
        <div className="bg-slate-800/50 rounded-xl p-3 border border-slate-700/30" title={tooltip}>
            <div className="text-xs text-slate-500 mb-1">{label}</div>
            <div className={`text-sm font-semibold ${color}`}>{value}</div>
        </div>
    );
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

export default PortfolioMarginPanel;
