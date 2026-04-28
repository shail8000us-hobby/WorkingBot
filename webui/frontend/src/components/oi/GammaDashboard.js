import React, { useMemo } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';

function formatUSD(val) {
    if (!val && val !== 0) return '—';
    if (Math.abs(val) >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
    if (Math.abs(val) >= 1e6) return `${(val / 1e6).toFixed(0)}M`;
    if (Math.abs(val) >= 1e3) return `${(val / 1e3).toFixed(0)}K`;
    return `${val.toFixed(0)}`;
}

export default function GammaDashboard({ gammaState, underlyingPrice }) {
    const chartData = useMemo(() => {
        if (!gammaState || !gammaState.gex_by_strike) return [];

        // Convert gex dict to array
        const data = Object.entries(gammaState.gex_by_strike).map(([strikeStr, gex]) => {
            const strike = parseFloat(strikeStr);
            return {
                strike,
                gex,
                label: strike.toLocaleString()
            };
        });

        // Sort by strike
        data.sort((a, b) => a.strike - b.strike);

        // If we have spot, limit the range to +/- 20% of spot for better visualization
        if (underlyingPrice > 0) {
            const minS = underlyingPrice * 0.7;
            const maxS = underlyingPrice * 1.3;
            return data.filter(d => d.strike >= minS && d.strike <= maxS);
        }

        return data;
    }, [gammaState, underlyingPrice]);

    if (!gammaState) {
        return (
            <div style={{ color: '#64748b', padding: '20px', textAlign: 'center' }}>
                No Gamma Data Available. Waiting for engine refresh...
            </div>
        );
    }

    const {
        regime,
        flip_level,
        pin_zone,
        max_long_gamma_strike,
        max_short_gamma_strike,
        total_net_gex,
        distance_to_flip_pct
    } = gammaState;

    const isNetLong = total_net_gex > 0;

    return (
        <Box sx={{ color: '#e2e8f0', p: 1 }}>
            {/* ── Top Metrics Row ──────────────────────────────────── */}
            <Box sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '12px',
                mb: 2,
            }}>
                <Paper sx={{ p: '12px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                    <Typography sx={{ fontSize: '10px', color: '#64748b', mb: '4px', textTransform: 'uppercase' }}>
                        Distance - Flip
                    </Typography>
                    <Typography sx={{ fontSize: '18px', fontWeight: 700, color: distance_to_flip_pct >= 0 ? '#4caf50' : '#f44336' }}>
                        {distance_to_flip_pct > 0 ? '+' : ''}{distance_to_flip_pct.toFixed(2)}%
                    </Typography>
                    <Typography sx={{ fontSize: '10px', color: '#fbbf24', mt: 1 }}>
                        Level: {flip_level.toLocaleString()}
                    </Typography>
                </Paper>

                <Paper sx={{ p: '12px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                    <Typography sx={{ fontSize: '10px', color: '#64748b', mb: '4px', textTransform: 'uppercase' }}>
                        Regime
                    </Typography>
                    <Typography sx={{ fontSize: '15px', fontWeight: 700, color: regime === 'LONG_GAMMA' ? '#4caf50' : regime === 'SHORT_GAMMA' ? '#f44336' : '#fbbf24' }}>
                        {regime.replace('_', ' ')}
                    </Typography>
                </Paper>

                <Paper sx={{ p: '12px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                    <Typography sx={{ fontSize: '10px', color: '#64748b', mb: '4px', textTransform: 'uppercase' }}>
                        Net GEX Today
                    </Typography>
                    <Typography sx={{ fontSize: '18px', fontWeight: 700, color: isNetLong ? '#4caf50' : '#f44336' }}>
                        {isNetLong ? '+' : ''}{formatUSD(total_net_gex)}
                    </Typography>
                </Paper>

                <Paper sx={{ p: '12px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                    <Typography sx={{ fontSize: '10px', color: '#64748b', mb: '4px', textTransform: 'uppercase' }}>
                        Pin Zone
                    </Typography>
                    <Typography sx={{ fontSize: '15px', fontWeight: 700, color: '#60a5fa' }}>
                        {pin_zone.low.toLocaleString()} - {pin_zone.high.toLocaleString()}
                    </Typography>
                    <Typography sx={{ fontSize: '10px', color: '#94a3b8', mt: 1 }}>
                        Max Long: {max_long_gamma_strike.toLocaleString()}
                    </Typography>
                </Paper>

                <Paper sx={{ p: '12px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                    <Typography sx={{ fontSize: '10px', color: '#64748b', mb: '4px', textTransform: 'uppercase' }}>
                        Accel Zone (Max Short)
                    </Typography>
                    <Typography sx={{ fontSize: '15px', fontWeight: 700, color: '#fca5a5' }}>
                        {max_short_gamma_strike.toLocaleString()}
                    </Typography>
                </Paper>

            </Box>

            {/* ── Main Chart ────────────────────────────────────── */}
            <Box sx={{ height: 350, background: 'rgba(15, 23, 42, 0.2)', p: 2, borderRadius: 2, border: '1px solid rgba(51, 65, 85, 0.4)' }}>
                <Typography sx={{ fontSize: '12px', color: '#94a3b8', mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Gamma Exposure - Pin & Acceleration Zones
                </Typography>

                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 20 }}>
                        <XAxis dataKey="label" stroke="#64748b" fontSize={11} tickMargin={10} minTickGap={30} />
                        <YAxis stroke="#64748b" fontSize={11} tickFormatter={formatUSD} domain={['auto', 'auto']} width={60} />

                        <Tooltip
                            contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: '#334155', fontSize: '12px' }}
                            itemStyle={{ color: '#e2e8f0' }}
                            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                            formatter={(value) => formatUSD(value)}
                        />

                        {/* Zero Line */}
                        <ReferenceLine y={0} stroke="#334155" />

                        {/* Underlying Spot Line */}
                        {underlyingPrice && (
                            <ReferenceLine
                                x={chartData.find((d, i) => Math.abs(d.strike - underlyingPrice) === Math.min(...chartData.map(c => Math.abs(c.strike - underlyingPrice))))?.label}
                                stroke="#3b82f6" strokeDasharray="3 3"
                                label={{ position: 'top', value: `SPOT: ${Math.round(underlyingPrice)}`, fill: '#60a5fa', fontSize: 10 }}
                            />
                        )}

                        {/* Flip Level Line */}
                        {flip_level > 0 && (
                            <ReferenceLine
                                x={chartData.find((d, i) => Math.abs(d.strike - flip_level) === Math.min(...chartData.map(c => Math.abs(c.strike - flip_level))))?.label}
                                stroke="#fbbf24" strokeWidth={2}
                                label={{ position: 'bottom', value: 'FLIP', fill: '#fbbf24', fontSize: 10 }}
                            />
                        )}

                        <Bar dataKey="gex" radius={[2, 2, 0, 0]}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.gex > 0 ? '#4caf50' : '#f44336'} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </Box>

            {/* ── Simulator ─────────────────────────────────────── */}
            <Box sx={{ mt: 2, background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(51, 65, 85, 0.4)', p: 2, borderRadius: 2 }}>
                <Typography sx={{ fontSize: '11px', color: '#64748b', mb: 1, textTransform: 'uppercase' }}>
                    Dealer Flow Simulator - "What if Spot moves..."
                </Typography>
                <Box sx={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                    {[
                        { label: 'Spot -1.0%', move: -0.01 },
                        { label: 'Spot -0.5%', move: -0.005 },
                        { label: 'Spot +0.5%', move: 0.005 },
                        { label: 'Spot +1.0%', move: 0.01 }
                    ].map(sim => {
                        const shiftGex = isNetLong ? 'BUY' : 'SELL';
                        const newSpot = underlyingPrice * (1 + sim.move);
                        // This is a rough simulation: If we are short gamma and price drops, dealers sell to hedge
                        // If we are long gamma and price drops, dealers buy to hedge (stabilize)
                        let action = '';
                        let color = '';
                        if (regime === 'LONG_GAMMA') {
                            action = sim.move > 0 ? 'SELL' : 'BUY';
                            color = sim.move > 0 ? '#f44336' : '#4caf50';
                        } else {
                            action = sim.move > 0 ? 'BUY' : 'SELL';
                            color = sim.move > 0 ? '#4caf50' : '#f44336';
                        }
                        return (
                            <Box key={sim.label} sx={{ flex: 1, minWidth: '150px' }}>
                                <Typography sx={{ fontSize: '10px', color: '#94a3b8' }}>{sim.label} → {Math.round(newSpot)}</Typography>
                                <Typography sx={{ fontSize: '16px', fontWeight: 600, color: color, mt: 0.5 }}>
                                    {action} to Hedge
                                </Typography>
                            </Box>
                        )
                    })}
                </Box>
            </Box>

        </Box>
    );
}
