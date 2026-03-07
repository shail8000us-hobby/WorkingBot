/**
 * Stress Test Matrix
 * ==================
 * Side-by-side PnL matrices for "Current Portfolio" and "After Adjustment"
 * under different price move & IV change scenarios.
 *
 * 7 rows (price: -15% to +15%) × 5 columns (IV: -20 to +20 vol pts)
 * Color-coded: green for profit, red for loss, yellow for near-zero.
 *
 * Created: March 6, 2026
 */

import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

// ============================================================================
// CELL COLOR
// ============================================================================

function getCellColor(value) {
    if (value == null || value === 0) return 'rgba(148, 163, 184, 0.1)';

    const absVal = Math.abs(value);

    // Near zero
    if (absVal < 100) return 'rgba(250, 204, 21, 0.15)';

    // Profit
    if (value > 0) {
        if (absVal > 5000) return 'rgba(34, 197, 94, 0.35)';
        if (absVal > 2000) return 'rgba(34, 197, 94, 0.25)';
        if (absVal > 500) return 'rgba(34, 197, 94, 0.15)';
        return 'rgba(34, 197, 94, 0.10)';
    }

    // Loss
    if (absVal > 5000) return 'rgba(239, 68, 68, 0.35)';
    if (absVal > 2000) return 'rgba(239, 68, 68, 0.25)';
    if (absVal > 500) return 'rgba(239, 68, 68, 0.15)';
    return 'rgba(239, 68, 68, 0.10)';
}

function getCellTextColor(value) {
    if (value == null || value === 0) return '#94a3b8';
    if (Math.abs(value) < 100) return '#fbbf24';
    return value > 0 ? '#22c55e' : '#ef4444';
}

function formatCellValue(value) {
    if (value == null) return '-';
    const abs = Math.abs(value);
    const sign = value >= 0 ? '' : '-';
    if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}K`;
    return `${sign}$${abs.toFixed(0)}`;
}

// ============================================================================
// SINGLE MATRIX
// ============================================================================

function MatrixTable({ data, title, spotPrice }) {
    if (!data || !data.matrix) return null;

    const { matrix, rowLabels, colLabels } = data;

    return (
        <Box sx={{ flex: 1 }}>
            <Typography variant="body2" sx={{
                color: '#e2e8f0',
                fontWeight: 700,
                mb: 1,
                textAlign: 'center',
                fontSize: '0.8rem',
            }}>
                {title}
            </Typography>
            <Box sx={{
                overflow: 'auto',
                border: '1px solid rgba(71, 85, 105, 0.3)',
                borderRadius: 1,
            }}>
                <table style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.7rem',
                }}>
                    <thead>
                        <tr>
                            <th style={{
                                padding: '6px 8px',
                                bgcolor: 'rgba(15, 23, 42, 0.8)',
                                borderBottom: '1px solid rgba(71, 85, 105, 0.4)',
                                color: '#94a3b8',
                                fontSize: '0.6rem',
                                fontWeight: 600,
                                textAlign: 'center',
                                position: 'sticky',
                                top: 0,
                                backgroundColor: '#1e293b',
                                zIndex: 1,
                            }}>
                                Price↓ / IV→
                            </th>
                            {colLabels.map((label, i) => (
                                <th key={i} style={{
                                    padding: '6px 6px',
                                    borderBottom: '1px solid rgba(71, 85, 105, 0.4)',
                                    color: i === 2 ? '#e2e8f0' : '#94a3b8',
                                    fontSize: '0.6rem',
                                    fontWeight: i === 2 ? 700 : 500,
                                    textAlign: 'center',
                                    position: 'sticky',
                                    top: 0,
                                    backgroundColor: '#1e293b',
                                    zIndex: 1,
                                }}>
                                    {label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {matrix.map((row, ri) => (
                            <tr key={ri}>
                                <td style={{
                                    padding: '5px 8px',
                                    borderBottom: '1px solid rgba(71, 85, 105, 0.15)',
                                    color: ri === 3 ? '#e2e8f0' : '#94a3b8',
                                    fontWeight: ri === 3 ? 700 : 500,
                                    textAlign: 'center',
                                    backgroundColor: ri === 3 ? 'rgba(71, 85, 105, 0.15)' : 'transparent',
                                    fontSize: '0.65rem',
                                    whiteSpace: 'nowrap',
                                }}>
                                    {rowLabels[ri]}
                                    {ri === 3 && spotPrice ? ` ($${(spotPrice / 1000).toFixed(0)}K)` : ''}
                                </td>
                                {row.map((value, ci) => (
                                    <td key={ci} style={{
                                        padding: '5px 6px',
                                        borderBottom: '1px solid rgba(71, 85, 105, 0.15)',
                                        backgroundColor: getCellColor(value),
                                        color: getCellTextColor(value),
                                        textAlign: 'center',
                                        fontWeight: ri === 3 || ci === 2 ? 700 : 500,
                                        fontFamily: 'monospace',
                                        fontSize: '0.7rem',
                                        transition: 'all 0.15s ease',
                                    }}>
                                        {formatCellValue(value)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Box>
        </Box>
    );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

/**
 * @param {Object} props
 * @param {Object} props.stressTestData - { current: { matrix, rowLabels, colLabels }, combined: {...} }
 * @param {number} props.spotPrice - Current spot
 * @param {boolean} props.hasProposedTrades - Whether there are proposed trades
 */
export default function StressTestMatrix({ stressTestData, spotPrice, hasProposedTrades }) {
    if (!stressTestData) {
        return (
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: 200,
            }}>
                <Typography color="text.secondary" variant="body2">
                    Add positions to see stress test results
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="body2" sx={{ color: '#94a3b8', mb: 2, textAlign: 'center', fontSize: '0.7rem' }}>
                PnL under price moves (rows) and IV changes (columns) — green = profit, red = loss
            </Typography>
            <Box sx={{
                display: 'flex',
                gap: 2,
                flexWrap: 'nowrap',
                overflowX: 'auto',
            }}>
                <MatrixTable
                    data={stressTestData.current}
                    title="📊 Current Portfolio"
                    spotPrice={spotPrice}
                />
                {hasProposedTrades && (
                    <MatrixTable
                        data={stressTestData.combined}
                        title="🔮 After Adjustment"
                        spotPrice={spotPrice}
                    />
                )}
            </Box>
        </Box>
    );
}
