/**
 * Enhanced Payoff Chart
 * =====================
 * Institutional-grade payoff visualization with:
 * - Before/After diff overlay with green/red shading
 * - Theta fan (multi-date decay curves)
 * - Probability distribution overlay
 * - Delta profile with secondary Y-axis
 * - Zoom & pan support
 *
 * Created: March 6, 2026
 */

import React, { useState, useMemo } from 'react';
import {
    Box,
    Typography,
    Button,
    Chip,
    Tooltip,
    ToggleButton,
    ToggleButtonGroup,
} from '@mui/material';
import {
    ZoomOut as ZoomOutIcon,
    CenterFocusStrong as ResetZoomIcon,
    Timeline as ThetaFanIcon,
} from '@mui/icons-material';
import {
    ResponsiveContainer,
    ComposedChart,
    Line,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as ChartTooltip,
    ReferenceLine,
    ReferenceArea,
} from 'recharts';

// ============================================================================
// COLORS
// ============================================================================

const CHART_COLORS = {
    currentLine: '#8888aa',       // Grey, semi-transparent — "Current Portfolio"
    afterLine: '#00e5ff',         // Bright teal/cyan — "After Adjustment"
    diffGreen: 'rgba(0, 255, 102, 0.13)',  // Semi-transparent green
    diffRed: 'rgba(255, 0, 0, 0.13)',      // Semi-transparent red
    spotLine: '#fbbf24',          // Yellow for ATM/spot
    breakeven: '#8b5cf6',         // Purple for breakeven
    grid: 'rgba(255, 255, 255, 0.08)',
    text: '#94a3b8',
    zero: 'rgba(255, 255, 255, 0.4)',
    delta: '#ff9800',             // Orange for delta curve
    // Theta fan colors — progressive brightness
    thetaFan: [
        'rgba(0, 150, 180, 0.25)',   // T-10 (dimmest)
        'rgba(0, 170, 200, 0.35)',   // T-7
        'rgba(0, 195, 220, 0.45)',   // T-5
        'rgba(0, 215, 235, 0.60)',   // T-3
        'rgba(0, 235, 255, 0.75)',   // T-1
        'rgba(255, 255, 255, 0.95)', // T-0 / Expiry (brightest)
    ],
    probability: {
        fill: 'rgba(255, 255, 255, 0.06)',
        fillBright: 'rgba(255, 255, 255, 0.12)',
    },
};

const THETA_FAN_KEYS = ['t10', 't7', 't5', 't3', 't1', 'expiry'];
const THETA_FAN_LABELS = ['T-10d', 'T-7d', 'T-5d', 'T-3d', 'T-1d', 'Expiry'];

// ============================================================================
// CUSTOM TOOLTIP
// ============================================================================

const CustomTooltip = ({ active, payload, label, hasProposedTrades, thetaFanEnabled, deltaProfileEnabled }) => {
    if (!active || !payload || payload.length === 0) return null;

    return (
        <Box sx={{
            bgcolor: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(71, 85, 105, 0.5)',
            borderRadius: 1,
            p: 1.5,
            minWidth: 160,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        }}>
            <Typography variant="caption" sx={{ color: '#e2e8f0', fontWeight: 'bold', display: 'block', mb: 0.5 }}>
                Price: ${label?.toLocaleString()}
            </Typography>
            {payload.map((entry, idx) => {
                // Skip hidden/internal entries
                if (['diffGreen', 'diffRed', 'probDensity'].includes(entry.dataKey)) return null;
                if (THETA_FAN_KEYS.includes(entry.dataKey) && !thetaFanEnabled) return null;
                if (entry.dataKey === 'delta' && !deltaProfileEnabled) return null;

                const color = entry.dataKey === 'current' ? CHART_COLORS.currentLine
                    : entry.dataKey === 'combined' ? CHART_COLORS.afterLine
                        : entry.dataKey === 'delta' ? CHART_COLORS.delta
                            : entry.color || '#94a3b8';

                const displayName = entry.dataKey === 'current' ? 'Current'
                    : entry.dataKey === 'combined' ? 'After Adj.'
                        : entry.dataKey === 'delta' ? 'Delta'
                            : THETA_FAN_KEYS.includes(entry.dataKey)
                                ? THETA_FAN_LABELS[THETA_FAN_KEYS.indexOf(entry.dataKey)]
                                : entry.name;

                const value = entry.dataKey === 'delta'
                    ? entry.value?.toFixed(4)
                    : `$${entry.value?.toFixed(2)}`;

                return (
                    <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mt: 0.25 }}>
                        <Typography variant="caption" sx={{ color }}>{displayName}</Typography>
                        <Typography variant="caption" sx={{ color, fontWeight: 600 }}>{value}</Typography>
                    </Box>
                );
            })}
        </Box>
    );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function EnhancedPayoffChart({
    chartData = [],
    thetaFanData,
    deltaProfileData,
    probabilityData,
    spotPrice,
    breakevens = [],
    hasProposedTrades = false,
    zoomDomain,
    onZoomChange,
    thetaFanEnabled = false,
    onThetaFanToggle,
    deltaProfileEnabled = false,
    onDeltaProfileToggle,
    height = 320,
}) {
    const [refAreaLeft, setRefAreaLeft] = useState(null);
    const [refAreaRight, setRefAreaRight] = useState(null);
    const [isSelecting, setIsSelecting] = useState(false);

    // ──────────────────────────────────────────────
    // DATA PROCESSING
    // ──────────────────────────────────────────────

    // Merge all data sources into a single chart dataset
    const mergedData = useMemo(() => {
        if (!chartData || chartData.length === 0) return [];

        return chartData.map((d, i) => {
            const row = { ...d };

            // Diff shading: compute green/red fill zones
            if (hasProposedTrades && d.current != null && d.combined != null) {
                row.diffGreen = d.combined > d.current ? d.combined : d.current;
                row.diffRed = d.combined < d.current ? d.combined : d.current;
            }

            // Merge probability overlay (z-index below via render order)
            if (probabilityData && probabilityData[i]) {
                row.probDensity = probabilityData[i].density;
            }

            // Merge theta fan data
            if (thetaFanEnabled && thetaFanData && thetaFanData[i]) {
                THETA_FAN_KEYS.forEach(key => {
                    row[key] = thetaFanData[i][key];
                });
            }

            // Merge delta profile
            if (deltaProfileEnabled && deltaProfileData && deltaProfileData[i]) {
                row.delta = deltaProfileData[i].delta;
            }

            return row;
        });
    }, [chartData, hasProposedTrades, probabilityData, thetaFanEnabled, thetaFanData, deltaProfileEnabled, deltaProfileData]);

    // Filter to zoom domain
    const filteredData = useMemo(() => {
        if (!zoomDomain) return mergedData;
        return mergedData.filter(d => d.price >= zoomDomain[0] && d.price <= zoomDomain[1]);
    }, [mergedData, zoomDomain]);

    // ──────────────────────────────────────────────
    // Y-AXIS DOMAINS
    // ──────────────────────────────────────────────

    const { yDomain, deltaYDomain } = useMemo(() => {
        if (filteredData.length === 0) return { yDomain: [-100, 100], deltaYDomain: [-1, 1] };

        // PnL Y-axis
        const pnlValues = filteredData.flatMap(d => {
            const vals = [d.current, d.combined].filter(v => v != null);
            if (thetaFanEnabled) {
                THETA_FAN_KEYS.forEach(key => { if (d[key] != null) vals.push(d[key]); });
            }
            return vals;
        });
        const minPnl = Math.min(...pnlValues);
        const maxPnl = Math.max(...pnlValues);
        const pnlPad = Math.abs(maxPnl - minPnl) * 0.15 || 100;

        // Delta Y-axis
        let deltaMin = -1, deltaMax = 1;
        if (deltaProfileEnabled) {
            const deltaVals = filteredData.map(d => d.delta).filter(v => v != null);
            if (deltaVals.length > 0) {
                deltaMin = Math.min(...deltaVals);
                deltaMax = Math.max(...deltaVals);
                const deltaPad = Math.abs(deltaMax - deltaMin) * 0.15 || 0.5;
                deltaMin -= deltaPad;
                deltaMax += deltaPad;
            }
        }

        return {
            yDomain: [minPnl - pnlPad, maxPnl + pnlPad],
            deltaYDomain: [deltaMin, deltaMax],
        };
    }, [filteredData, thetaFanEnabled, deltaProfileEnabled]);

    // ──────────────────────────────────────────────
    // ZOOM HANDLERS
    // ──────────────────────────────────────────────

    const handleMouseDown = (e) => {
        if (e && e.activeLabel) {
            setRefAreaLeft(e.activeLabel);
            setIsSelecting(true);
        }
    };

    const handleMouseMove = (e) => {
        if (isSelecting && e && e.activeLabel) {
            setRefAreaRight(e.activeLabel);
        }
    };

    const handleMouseUp = () => {
        if (refAreaLeft && refAreaRight && refAreaLeft !== refAreaRight) {
            const left = Math.min(refAreaLeft, refAreaRight);
            const right = Math.max(refAreaLeft, refAreaRight);
            onZoomChange?.([left, right]);
        }
        setRefAreaLeft(null);
        setRefAreaRight(null);
        setIsSelecting(false);
    };

    // ──────────────────────────────────────────────
    // EMPTY STATE
    // ──────────────────────────────────────────────

    if (!chartData || chartData.length === 0) {
        return (
            <Box sx={{
                height,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'rgba(0,0,0,0.2)',
                borderRadius: 1,
            }}>
                <Typography color="text.secondary">No payoff data</Typography>
            </Box>
        );
    }

    // ──────────────────────────────────────────────
    // FORMAT HELPERS
    // ──────────────────────────────────────────────

    const formatYAxis = (v) => {
        if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}K`;
        return `$${v.toFixed(0)}`;
    };

    const formatXAxis = (v) => {
        return v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v.toFixed(0);
    };

    // ──────────────────────────────────────────────
    // RENDER
    // ──────────────────────────────────────────────

    return (
        <Box>
            {/* Toolbar: Toggles */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                mb: 1,
            }}>
                {/* Left — Graph toggles */}
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Tooltip title="Show time-decay curves at different days before expiry">
                        <Chip
                            label="Theta Fan"
                            size="small"
                            variant={thetaFanEnabled ? 'filled' : 'outlined'}
                            onClick={() => onThetaFanToggle?.(!thetaFanEnabled)}
                            sx={{
                                bgcolor: thetaFanEnabled ? 'rgba(0, 229, 255, 0.2)' : 'transparent',
                                color: thetaFanEnabled ? '#00e5ff' : '#94a3b8',
                                borderColor: thetaFanEnabled ? '#00e5ff' : 'rgba(71, 85, 105, 0.4)',
                                fontSize: '0.7rem',
                                height: 26,
                                cursor: 'pointer',
                                '&:hover': { bgcolor: 'rgba(0, 229, 255, 0.1)' },
                            }}
                        />
                    </Tooltip>
                    <Tooltip title="Show portfolio delta across price range">
                        <Chip
                            label="Δ Delta"
                            size="small"
                            variant={deltaProfileEnabled ? 'filled' : 'outlined'}
                            onClick={() => onDeltaProfileToggle?.(!deltaProfileEnabled)}
                            sx={{
                                bgcolor: deltaProfileEnabled ? 'rgba(255, 152, 0, 0.2)' : 'transparent',
                                color: deltaProfileEnabled ? '#ff9800' : '#94a3b8',
                                borderColor: deltaProfileEnabled ? '#ff9800' : 'rgba(71, 85, 105, 0.4)',
                                fontSize: '0.7rem',
                                height: 26,
                                cursor: 'pointer',
                                '&:hover': { bgcolor: 'rgba(255, 152, 0, 0.1)' },
                            }}
                        />
                    </Tooltip>
                </Box>

                {/* Right — Zoom controls */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {zoomDomain ? (
                        <>
                            <Button
                                size="small"
                                startIcon={<ZoomOutIcon />}
                                onClick={() => {
                                    const range = zoomDomain[1] - zoomDomain[0];
                                    const center = (zoomDomain[0] + zoomDomain[1]) / 2;
                                    const newRange = range * 1.5;
                                    onZoomChange?.([center - newRange / 2, center + newRange / 2]);
                                }}
                                sx={{ color: '#94a3b8', fontSize: '0.7rem' }}
                            >
                                Zoom Out
                            </Button>
                            <Button
                                size="small"
                                startIcon={<ResetZoomIcon />}
                                onClick={() => onZoomChange?.(null)}
                                sx={{ color: '#3b82f6', fontSize: '0.7rem' }}
                            >
                                Reset
                            </Button>
                        </>
                    ) : (
                        <Typography variant="caption" sx={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.65rem' }}>
                            Drag on chart to zoom
                        </Typography>
                    )}
                </Box>
            </Box>

            {/* Chart */}
            <Box sx={{ height, position: 'relative', cursor: isSelecting ? 'crosshair' : 'default' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                        data={filteredData}
                        margin={{ top: 10, right: deltaProfileEnabled ? 60 : 30, left: 10, bottom: 10 }}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        <defs>
                            {/* Diff green gradient */}
                            <linearGradient id="diffGreenGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#00ff66" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#00ff66" stopOpacity={0.03} />
                            </linearGradient>
                            {/* Diff red gradient */}
                            <linearGradient id="diffRedGrad" x1="0" y1="1" x2="0" y2="0">
                                <stop offset="0%" stopColor="#ff0000" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#ff0000" stopOpacity={0.03} />
                            </linearGradient>
                            {/* Probability distribution gradient */}
                            <linearGradient id="probGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#ffffff" stopOpacity={0.10} />
                                <stop offset="100%" stopColor="#ffffff" stopOpacity={0.02} />
                            </linearGradient>
                        </defs>

                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />

                        {/* X-Axis */}
                        <XAxis
                            dataKey="price"
                            tickFormatter={formatXAxis}
                            stroke="rgba(148, 163, 184, 0.6)"
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                            axisLine={{ stroke: 'rgba(148, 163, 184, 0.3)' }}
                            allowDataOverflow
                        />

                        {/* Left Y-Axis — PnL */}
                        <YAxis
                            yAxisId="pnl"
                            domain={yDomain}
                            tickFormatter={formatYAxis}
                            stroke="rgba(148, 163, 184, 0.6)"
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                            axisLine={{ stroke: 'rgba(148, 163, 184, 0.3)' }}
                            label={{
                                value: 'Profit / Loss',
                                angle: -90,
                                position: 'insideLeft',
                                style: { fill: '#94a3b8', fontSize: 11 },
                            }}
                        />

                        {/* Right Y-Axis — Delta (conditional) */}
                        {deltaProfileEnabled && (
                            <YAxis
                                yAxisId="delta"
                                orientation="right"
                                domain={deltaYDomain}
                                tickFormatter={v => v.toFixed(2)}
                                stroke="rgba(255, 152, 0, 0.6)"
                                tick={{ fontSize: 10, fill: '#ff9800' }}
                                axisLine={{ stroke: 'rgba(255, 152, 0, 0.3)' }}
                                label={{
                                    value: 'Delta',
                                    angle: 90,
                                    position: 'insideRight',
                                    style: { fill: '#ff9800', fontSize: 11 },
                                }}
                            />
                        )}

                        {/* Custom tooltip */}
                        <ChartTooltip
                            content={
                                <CustomTooltip
                                    hasProposedTrades={hasProposedTrades}
                                    thetaFanEnabled={thetaFanEnabled}
                                    deltaProfileEnabled={deltaProfileEnabled}
                                />
                            }
                        />

                        {/* ═══ PROBABILITY DISTRIBUTION (behind everything) ═══ */}
                        {probabilityData && (
                            <Area
                                yAxisId="pnl"
                                type="monotone"
                                dataKey="probDensity"
                                stroke="none"
                                fill="url(#probGrad)"
                                fillOpacity={1}
                                baseLine={0}
                                isAnimationActive={false}
                            />
                        )}

                        {/* ═══ DIFF SHADING (when proposed trades exist) ═══ */}
                        {hasProposedTrades && (
                            <>
                                {/* Green zone: where "After" > "Current" (improvement) */}
                                <Area
                                    yAxisId="pnl"
                                    type="monotone"
                                    dataKey="diffGreen"
                                    stroke="none"
                                    fill="url(#diffGreenGrad)"
                                    fillOpacity={1}
                                    baseLine={filteredData.map(d => ({ value: d.current || 0 }))}
                                    isAnimationActive={false}
                                />
                                {/* Red zone: where "Current" > "After" (worsening) */}
                                <Area
                                    yAxisId="pnl"
                                    type="monotone"
                                    dataKey="diffRed"
                                    stroke="none"
                                    fill="url(#diffRedGrad)"
                                    fillOpacity={1}
                                    baseLine={filteredData.map(d => ({ value: d.combined || d.current || 0 }))}
                                    isAnimationActive={false}
                                />
                            </>
                        )}

                        {/* ═══ THETA FAN CURVES (when enabled) ═══ */}
                        {thetaFanEnabled && THETA_FAN_KEYS.map((key, idx) => (
                            <Line
                                key={key}
                                yAxisId="pnl"
                                type="monotone"
                                dataKey={key}
                                stroke={CHART_COLORS.thetaFan[idx]}
                                strokeWidth={key === 'expiry' ? 2 : 1}
                                strokeDasharray={key === 'expiry' ? '' : '4 2'}
                                dot={false}
                                isAnimationActive={false}
                            />
                        ))}

                        {/* ═══ REFERENCE LINES ═══ */}

                        {/* Zero P&L line */}
                        <ReferenceLine
                            yAxisId="pnl"
                            y={0}
                            stroke={CHART_COLORS.zero}
                            strokeWidth={1.5}
                        />

                        {/* Delta zero line (when delta enabled) */}
                        {deltaProfileEnabled && (
                            <ReferenceLine
                                yAxisId="delta"
                                y={0}
                                stroke="rgba(255, 152, 0, 0.2)"
                                strokeWidth={1}
                                strokeDasharray="6 4"
                            />
                        )}

                        {/* ATM / Current spot line */}
                        {spotPrice && (
                            <ReferenceLine
                                yAxisId="pnl"
                                x={spotPrice}
                                stroke={CHART_COLORS.spotLine}
                                strokeWidth={2}
                                strokeDasharray="8 4"
                                label={{
                                    value: 'ATM',
                                    position: 'top',
                                    fill: CHART_COLORS.spotLine,
                                    fontSize: 12,
                                    fontWeight: 'bold',
                                }}
                            />
                        )}

                        {/* Breakeven lines */}
                        {breakevens?.map((be, idx) => (
                            <ReferenceLine
                                key={idx}
                                yAxisId="pnl"
                                x={be}
                                stroke={CHART_COLORS.breakeven}
                                strokeWidth={1}
                                strokeDasharray="4 4"
                            />
                        ))}

                        {/* ═══ MAIN PAYOFF CURVES ═══ */}

                        {/* Curve A: Current Portfolio — grey dashed */}
                        {hasProposedTrades && (
                            <Line
                                yAxisId="pnl"
                                type="monotone"
                                dataKey="current"
                                name="Current"
                                stroke={CHART_COLORS.currentLine}
                                strokeWidth={2}
                                strokeDasharray="6 4"
                                dot={false}
                                activeDot={{ r: 3, fill: CHART_COLORS.currentLine }}
                                isAnimationActive={false}
                            />
                        )}

                        {/* Curve B: After Adjustment (or sole curve if no trades) — teal solid */}
                        <Line
                            yAxisId="pnl"
                            type="monotone"
                            dataKey={hasProposedTrades ? 'combined' : 'current'}
                            name={hasProposedTrades ? 'After Adjustment' : 'On Expiry'}
                            stroke={hasProposedTrades ? CHART_COLORS.afterLine : '#10b981'}
                            strokeWidth={2.5}
                            dot={false}
                            activeDot={{ r: 4, fill: hasProposedTrades ? CHART_COLORS.afterLine : '#10b981' }}
                            isAnimationActive={false}
                        />

                        {/* ═══ DELTA PROFILE (when enabled) ═══ */}
                        {deltaProfileEnabled && (
                            <Line
                                yAxisId="delta"
                                type="monotone"
                                dataKey="delta"
                                name="Delta"
                                stroke={CHART_COLORS.delta}
                                strokeWidth={1.5}
                                strokeDasharray="6 3"
                                dot={false}
                                activeDot={{ r: 3, fill: CHART_COLORS.delta }}
                                isAnimationActive={false}
                            />
                        )}

                        {/* Zoom selection area */}
                        {refAreaLeft && refAreaRight && (
                            <ReferenceArea
                                yAxisId="pnl"
                                x1={refAreaLeft}
                                x2={refAreaRight}
                                strokeOpacity={0.3}
                                fill="#3b82f6"
                                fillOpacity={0.3}
                            />
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </Box>

            {/* Legend */}
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                flexWrap: 'wrap',
                gap: 2.5,
                mt: 1,
            }}>
                {/* Current line */}
                {hasProposedTrades && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{
                            width: 20, height: 2,
                            bgcolor: CHART_COLORS.currentLine,
                            borderTop: '1px dashed ' + CHART_COLORS.currentLine,
                            opacity: 0.8,
                        }} />
                        <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>Current</Typography>
                    </Box>
                )}
                {/* After adjustment / On Expiry */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{
                        width: 20, height: 3,
                        bgcolor: hasProposedTrades ? CHART_COLORS.afterLine : '#10b981',
                        borderRadius: 1,
                    }} />
                    <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>
                        {hasProposedTrades ? 'After Adjustment' : 'On Expiry'}
                    </Typography>
                </Box>
                {/* Diff zones */}
                {hasProposedTrades && (
                    <>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Box sx={{ width: 14, height: 10, bgcolor: 'rgba(0, 255, 102, 0.2)', border: '1px solid rgba(0, 255, 102, 0.4)', borderRadius: 0.5 }} />
                            <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>Improvement</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Box sx={{ width: 14, height: 10, bgcolor: 'rgba(255, 0, 0, 0.2)', border: '1px solid rgba(255, 0, 0, 0.4)', borderRadius: 0.5 }} />
                            <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>Worsening</Typography>
                        </Box>
                    </>
                )}
                {/* Theta fan */}
                {thetaFanEnabled && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ width: 20, height: 8, background: 'linear-gradient(90deg, rgba(0,150,180,0.3), rgba(255,255,255,0.8))', borderRadius: 0.5 }} />
                        <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>Theta Fan</Typography>
                    </Box>
                )}
                {/* Delta */}
                {deltaProfileEnabled && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ width: 20, height: 2, bgcolor: CHART_COLORS.delta, borderTop: '1px dashed #ff9800' }} />
                        <Typography variant="caption" sx={{ color: '#ff9800', fontSize: '0.65rem' }}>Delta</Typography>
                    </Box>
                )}
            </Box>
        </Box>
    );
}
