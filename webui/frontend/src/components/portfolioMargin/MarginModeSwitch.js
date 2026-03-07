import React, { useState } from 'react';

/**
 * MarginModeSwitch — toggle between isolated and portfolio margin modes.
 * Shows current mode, confirmation dialog before switching.
 */
const MarginModeSwitch = React.memo(function MarginModeSwitch({ currentMode, onSwitch, loading }) {
    const [confirming, setConfirming] = useState(false);
    const targetMode = currentMode === 'portfolio' ? 'isolated' : 'portfolio';

    const handleSwitch = async () => {
        setConfirming(false);
        if (onSwitch) await onSwitch(targetMode);
    };

    const isPortfolio = currentMode === 'portfolio';

    return (
        <div className="relative">
            <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                <div className="flex-1">
                    <div className="text-sm text-slate-400 mb-1">Current Margin Mode</div>
                    <div className="flex items-center gap-2">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${isPortfolio
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            }`}>
                            <span className={`w-2 h-2 rounded-full ${isPortfolio ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                            {isPortfolio ? 'Portfolio' : 'Isolated'}
                        </span>
                        {currentMode === 'unknown' && (
                            <span className="text-xs text-slate-500">(unable to determine)</span>
                        )}
                    </div>
                </div>

                <button
                    onClick={() => setConfirming(true)}
                    disabled={loading || currentMode === 'unknown'}
                    className="px-4 py-2 rounded-lg bg-indigo-600/80 hover:bg-indigo-500 text-white text-sm font-medium transition disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    Switch to {targetMode === 'portfolio' ? 'Portfolio' : 'Isolated'}
                </button>
            </div>

            {/* Confirmation Dialog */}
            {confirming && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div className="bg-slate-800 border border-slate-600 rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                        <h3 className="text-lg font-semibold text-slate-100 mb-2">
                            ⚠️ Switch Margin Mode
                        </h3>
                        <p className="text-sm text-slate-300 mb-4">
                            You are about to switch from <strong>{currentMode}</strong> to <strong>{targetMode}</strong> margin mode.
                            This affects your <em>entire account</em> and all open positions.
                        </p>
                        {targetMode === 'portfolio' && (
                            <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 mb-4">
                                ✅ Portfolio margin typically reduces margin requirements for hedged positions.
                            </div>
                        )}
                        {targetMode === 'isolated' && (
                            <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mb-4">
                                ⚠️ Switching to isolated may increase margin requirements. Ensure sufficient balance.
                            </div>
                        )}
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setConfirming(false)}
                                className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSwitch}
                                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition"
                            >
                                Confirm Switch
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
});

export default MarginModeSwitch;
