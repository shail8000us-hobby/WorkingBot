import React, { useMemo } from 'react';

/**
 * MarginHistoryChart — BUG 9 FIX: timestamps in IST (UTC+5:30).
 * Also plots utilization (not raw risk_margin).
 */
const MarginHistoryChart = React.memo(function MarginHistoryChart({ history, height = 180 }) {
    const WIDTH = 600;
    const PADDING = { top: 10, right: 10, bottom: 30, left: 50 };

    const { path, points, yTicks, xLabels, areaPath } = useMemo(() => {
        if (!history || history.length < 2) {
            return { path: '', points: [], yTicks: [], xLabels: [], areaPath: '' };
        }

        const values = history.map(h => h.margin_utilization ?? h.utilization ?? 0);
        const minVal = Math.min(0, ...values);
        const maxVal = Math.max(100, ...values) || 100;

        const chartW = WIDTH - PADDING.left - PADDING.right;
        const chartH = height - PADDING.top - PADDING.bottom;

        const pts = values.map((v, i) => ({
            x: PADDING.left + (i / (values.length - 1)) * chartW,
            y: PADDING.top + chartH - ((v - minVal) / (maxVal - minVal)) * chartH,
            value: v,
            timestamp: history[i]?.timestamp,
            source: history[i]?.source,
        }));

        const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
        const area = `${d} L ${pts[pts.length - 1].x} ${height - PADDING.bottom} L ${pts[0].x} ${height - PADDING.bottom} Z`;

        // Y axis ticks
        const ticks = [];
        for (let i = 0; i <= 4; i++) {
            const val = minVal + (i / 4) * (maxVal - minVal);
            ticks.push({
                value: `${val.toFixed(0)}%`,
                y: PADDING.top + chartH - (i / 4) * chartH,
            });
        }

        // BUG 9 FIX: X labels in IST
        const labels = [];
        [0, Math.floor(history.length / 2), history.length - 1].forEach((idx) => {
            if (history[idx]?.timestamp) {
                const time = toIST(history[idx].timestamp);
                labels.push({
                    text: time,
                    x: PADDING.left + (idx / (values.length - 1)) * chartW,
                });
            }
        });

        return { path: d, points: pts, yTicks: ticks, xLabels: labels, areaPath: area };
    }, [history, height]);

    if (!history || history.length < 2) {
        return (
            <div className="flex items-center justify-center h-40 text-slate-500 text-sm bg-slate-800/40 rounded-xl border border-slate-700/30">
                <div className="text-center">
                    <div>📈 Not enough data for chart</div>
                    <div className="text-xs mt-1 text-slate-600">
                        Data collects every ~10s. Currently {history?.length || 0} of 2 needed.
                    </div>
                </div>
            </div>
        );
    }

    const latestVal = points[points.length - 1]?.value;
    const latestColor = latestVal > 85 ? '#f43f5e' : latestVal > 60 ? '#f59e0b' : '#10b981';

    return (
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/40">
            <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs text-slate-500 uppercase tracking-wider">
                    Margin Utilization Over Time (IST)
                </h4>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-600">{history.length} data points</span>
                    {latestVal != null && (
                        <span className="text-xs font-medium tabular-nums" style={{ color: latestColor }}>
                            Current: {latestVal.toFixed(1)}%
                        </span>
                    )}
                </div>
            </div>
            <svg viewBox={`0 0 ${WIDTH} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
                {/* Grid lines */}
                {yTicks.map((tick, i) => (
                    <g key={i}>
                        <line
                            x1={PADDING.left} y1={tick.y}
                            x2={WIDTH - PADDING.right} y2={tick.y}
                            stroke="rgba(148,163,184,0.1)" strokeDasharray="3,3"
                        />
                        <text
                            x={PADDING.left - 5} y={tick.y + 3}
                            textAnchor="end" fill="#64748b" fontSize="9"
                        >
                            {tick.value}
                        </text>
                    </g>
                ))}

                {/* X labels */}
                {xLabels.map((label, i) => (
                    <text
                        key={i} x={label.x} y={height - 5}
                        textAnchor="middle" fill="#64748b" fontSize="9"
                    >
                        {label.text}
                    </text>
                ))}

                {/* Area fill */}
                {areaPath && (
                    <path d={areaPath} fill="url(#marginGradient)" opacity="0.3" />
                )}

                {/* Line */}
                <path d={path} fill="none" stroke={latestColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

                {/* Dots on last 5 points */}
                {points.slice(-5).map((p, i) => (
                    <circle key={i} cx={p.x} cy={p.y} r="3" fill={latestColor} stroke="#1e1b4b" strokeWidth="1.5" />
                ))}

                {/* Gradient */}
                <defs>
                    <linearGradient id="marginGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={latestColor} stopOpacity="0.4" />
                        <stop offset="100%" stopColor={latestColor} stopOpacity="0" />
                    </linearGradient>
                </defs>
            </svg>
        </div>
    );
});

/**
 * BUG 9 FIX: Convert timestamp to IST (UTC+5:30) string.
 */
function toIST(timestamp) {
    try {
        const d = new Date(timestamp);
        return d.toLocaleTimeString('en-IN', {
            timeZone: 'Asia/Kolkata',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        });
    } catch {
        // Fallback: manual offset
        const d = new Date(timestamp);
        const ist = new Date(d.getTime() + (5.5 * 60 * 60 * 1000));
        return `${ist.getUTCHours().toString().padStart(2, '0')}:${ist.getUTCMinutes().toString().padStart(2, '0')}`;
    }
}

export default MarginHistoryChart;
