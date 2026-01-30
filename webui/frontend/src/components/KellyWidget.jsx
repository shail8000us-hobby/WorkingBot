/**
 * Kelly Criterion Position Sizing Widget
 * 
 * Displays optimal position size based on your actual trading performance.
 * Updates automatically as you close trades.
 */

import React, { useState, useEffect } from 'react';
import './KellyWidget.css';

const KellyWidget = () => {
    const [kellyData, setKellyData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedStrategy, setSelectedStrategy] = useState('iron_condor');
    const [accountBalance, setAccountBalance] = useState(100000);

    useEffect(() => {
        fetchKellySizing();
        const interval = setInterval(fetchKellySizing, 30000); // Update every 30s
        return () => clearInterval(interval);
    }, [selectedStrategy, accountBalance]);

    const fetchKellySizing = async () => {
        try {
            const response = await fetch(
                `/api/kelly/sizing/${selectedStrategy}?account_balance=${accountBalance}`
            );
            const data = await response.json();
            setKellyData(data);
            setLoading(false);
        } catch (err) {
            console.error('Kelly fetch error:', err);
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="kelly-widget loading">Loading Kelly data...</div>;
    }

    if (!kellyData || !kellyData.success) {
        return (
            <div className="kelly-widget error">
                <h3>⚠️ Kelly Sizer</h3>
                <p>No trade history yet. Start trading to build data.</p>
            </div>
        );
    }

    const { kelly_percent, position_size_usd, confidence, stats, recommendation } = kellyData;
    const kellyPct = (kelly_percent * 100).toFixed(1);

    const getConfidenceColor = (conf) => {
        if (conf === 'HIGH') return '#00ff00';
        if (conf === 'MEDIUM') return '#ffaa00';
        return '#ff4444';
    };

    const getConfidenceIcon = (conf) => {
        if (conf === 'HIGH') return '✅';
        if (conf === 'MEDIUM') return '⚠️';
        return '❌';
    };

    return (
        <div className="kelly-widget">
            <div className="kelly-header">
                <h3>🎯 Kelly Position Sizer</h3>
                <div className="kelly-confidence" style={{ color: getConfidenceColor(confidence) }}>
                    {getConfidenceIcon(confidence)} {confidence}
                </div>
            </div>

            <div className="kelly-main">
                <div className="kelly-size">
                    <div className="kelly-label">Recommended Size</div>
                    <div className="kelly-value">
                        ${position_size_usd.toLocaleString()}
                    </div>
                    <div className="kelly-percent">{kellyPct}% of account</div>
                </div>

                <div className="kelly-stats">
                    {stats && stats.total_trades > 0 && (
                        <>
                            <div className="stat-row">
                                <span>Total Trades:</span>
                                <span>{stats.total_trades}</span>
                            </div>
                            <div className="stat-row">
                                <span>Win Rate:</span>
                                <span style={{ color: stats.win_rate >= 0.5 ? '#00ff00' : '#ff4444' }}>
                                    {(stats.win_rate * 100).toFixed(1)}%
                                </span>
                            </div>
                            <div className="stat-row">
                                <span>Avg Win:</span>
                                <span style={{ color: '#00ff00' }}>
                                    ${stats.avg_win_usd.toFixed(0)}
                                </span>
                            </div>
                            <div className="stat-row">
                                <span>Avg Loss:</span>
                                <span style={{ color: '#ff4444' }}>
                                    ${stats.avg_loss_usd.toFixed(0)}
                                </span>
                            </div>
                            <div className="stat-row">
                                <span>Win/Loss Ratio:</span>
                                <span style={{ color: stats.win_loss_ratio >= 1 ? '#00ff00' : '#ff4444' }}>
                                    {stats.win_loss_ratio.toFixed(2)}x
                                </span>
                            </div>
                            <div className="stat-row">
                                <span>Expectancy:</span>
                                <span style={{ color: stats.expectancy >= 0 ? '#00ff00' : '#ff4444' }}>
                                    ${stats.expectancy.toFixed(0)}/trade
                                </span>
                            </div>
                        </>
                    )}
                </div>
            </div>

            <div className="kelly-recommendation">
                {recommendation}
            </div>

            <div className="kelly-controls">
                <select 
                    value={selectedStrategy} 
                    onChange={(e) => setSelectedStrategy(e.target.value)}
                    className="strategy-select"
                >
                    <option value="iron_condor">Iron Condor</option>
                    <option value="straddle">Straddle</option>
                    <option value="strangle">Strangle</option>
                    <option value="single_leg">Single Leg</option>
                    <option value="manual">Manual</option>
                </select>
            </div>
        </div>
    );
};

export default KellyWidget;
