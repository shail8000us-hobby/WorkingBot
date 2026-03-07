import React, { useMemo } from 'react';

/**
 * WebSocketStatus — connection status with wallet/PM values, staleness, start/stop.
 * BUG 7 FIX: Shows portfolio margin value and wallet balance (not "—").
 */
const WebSocketStatus = React.memo(function WebSocketStatus({
    wsStatus, wallet, onStart, onStop, lastUpdated,
}) {
    const connected = wsStatus?.connected ?? false;
    const running = wsStatus?.running ?? false;
    const hasPortfolioData = wsStatus?.has_portfolio_data ?? false;
    const hasWalletData = wsStatus?.has_wallet_data ?? false;

    // Pick primary wallet for display
    const primary = useMemo(() => {
        if (!wallet || wallet.length === 0) return null;
        return wallet.find(w => w.balance > 0) || wallet[0];
    }, [wallet]);

    // Staleness check
    const stale = useMemo(() => {
        if (!lastUpdated) return false;
        const diff = Date.now() - new Date(lastUpdated).getTime();
        return diff > 30000; // 30 seconds
    }, [lastUpdated]);

    const timeAgo = useMemo(() => {
        if (!lastUpdated) return 'never';
        const d = new Date(lastUpdated);
        return d.toLocaleTimeString();
    }, [lastUpdated]);

    return (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-800/50 border border-slate-700/40">
            {/* Status Dot */}
            <div className="relative flex-shrink-0">
                <span className={`block w-3 h-3 rounded-full ${connected ? 'bg-emerald-400' : running ? 'bg-amber-400' : 'bg-slate-600'
                    }`} />
                {connected && (
                    <span className="absolute inset-0 w-3 h-3 rounded-full bg-emerald-400 animate-ping opacity-40" />
                )}
            </div>

            {/* Status Text */}
            <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-200">
                    {connected ? 'Connected' : running ? 'Reconnecting…' : 'Disconnected'}
                </div>
                <div className="text-xs text-slate-500 flex gap-3 flex-wrap">
                    <span>Portfolio: {primary ? `${primary.portfolio_margin?.toFixed(2)}` : '—'}</span>
                    <span>Wallet: {primary ? `${primary.balance?.toFixed(2)}` : '—'}</span>
                    {lastUpdated && (
                        <span className={stale ? 'text-amber-400' : 'text-slate-600'}>
                            {stale ? '⚠️ Stale' : '•'} {timeAgo}
                        </span>
                    )}
                </div>
            </div>

            {/* Controls */}
            <div className="flex gap-2">
                {!running ? (
                    <button
                        onClick={onStart}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600/80 hover:bg-emerald-500 text-white transition"
                    >
                        Start WS
                    </button>
                ) : (
                    <button
                        onClick={onStop}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-600/80 hover:bg-rose-500 text-white transition"
                    >
                        Stop WS
                    </button>
                )}
            </div>
        </div>
    );
});

export default WebSocketStatus;
