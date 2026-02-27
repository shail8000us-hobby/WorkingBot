/**
 * PortfolioGreeksSummary Component
 *
 * ARCH-2: Extracted from OptionsPanel.js monolith.
 * Renders the PnL summary chips and portfolio Greeks panel.
 * Wrapped in React.memo — only re-renders when positions or Greeks change.
 *
 * Created: February 26, 2026 (ARCH-2 refactor)
 */

import React from 'react';
import {
    Box,
    Chip,
    Tooltip,
    Typography,
    Divider,
} from '@mui/material';
import {
    AttachMoney as MoneyIcon,
    TrendingUp,
    TrendingDown,
} from '@mui/icons-material';

// Utility functions (module-level for stable references)
const formatPnl = (pnl) => {
    const numPnl = Number(pnl) || 0;
    const formatted = Math.abs(numPnl).toFixed(4);
    return numPnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
};

const getPnlColor = (pnl) => {
    if (pnl > 0) return '#10b981';
    if (pnl < 0) return '#ef4444';
    return '#94a3b8';
};

function PortfolioGreeksSummary({ sortedPositions, aggregatedGreeks }) {
    const totalPnl = sortedPositions.reduce(
        (sum, p) => sum + (Number(p.unrealized_pnl) || 0) + (Number(p.partial_realized_pnl) || 0),
        0
    );

    return (
        <>
            <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Chip
                    icon={<MoneyIcon />}
                    label={`Total PnL: ${formatPnl(totalPnl)}`}
                    sx={{
                        bgcolor: getPnlColor(totalPnl) + '20',
                        color: getPnlColor(totalPnl),
                    }}
                />
                <Chip
                    label={`Calls: ${sortedPositions.filter((p) => p.product_symbol.startsWith('C-')).length}`}
                    sx={{ bgcolor: '#3b82f620', color: '#3b82f6' }}
                />
                <Chip
                    label={`Puts: ${sortedPositions.filter((p) => p.product_symbol.startsWith('P-')).length}`}
                    sx={{ bgcolor: '#a855f720', color: '#a855f7' }}
                />
            </Box>

            {/* Greeks Summary */}
            {aggregatedGreeks.count > 0 && (
                <Box sx={{ mt: 1.5, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight="bold">
                            Portfolio Greeks ({sortedPositions.length} visible positions)
                        </Typography>
                        {Math.abs(aggregatedGreeks.delta) < 0.1 && (
                            <Chip
                                label="Delta Neutral ✅"
                                size="small"
                                color="info"
                                sx={{ height: 18, fontSize: '0.65rem' }}
                            />
                        )}
                        {Math.abs(aggregatedGreeks.delta) > 10 && (
                            <Chip
                                label="High Delta ⚠️"
                                size="small"
                                color="warning"
                                sx={{ height: 18, fontSize: '0.65rem' }}
                            />
                        )}
                    </Box>

                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                        {/* Futures Equivalent */}
                        {(aggregatedGreeks.btcDelta !== 0 || aggregatedGreeks.ethDelta !== 0) && (
                            <>
                                <Typography variant="caption" color="text.secondary" sx={{ mr: -1 }}>
                                    Futures Equiv:
                                </Typography>
                                {aggregatedGreeks.btcDelta !== 0 && (
                                    <Tooltip
                                        title={`Your BTC options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC futures contracts`}
                                    >
                                        <Chip
                                            size="small"
                                            label={`${aggregatedGreeks.btcDelta >= 0 ? 'Long' : 'Short'} ${Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC`}
                                            icon={aggregatedGreeks.btcDelta >= 0 ? <TrendingUp sx={{ fontSize: 14 }} /> : <TrendingDown sx={{ fontSize: 14 }} />}
                                            sx={{
                                                height: 22,
                                                bgcolor: aggregatedGreeks.btcDelta >= 0 ? '#10b98120' : '#ef444420',
                                                color: aggregatedGreeks.btcDelta >= 0 ? '#10b981' : '#ef4444',
                                                fontWeight: 'bold',
                                                fontSize: '0.7rem',
                                            }}
                                        />
                                    </Tooltip>
                                )}
                                {aggregatedGreeks.ethDelta !== 0 && (
                                    <Tooltip
                                        title={`Your ETH options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH futures contracts`}
                                    >
                                        <Chip
                                            size="small"
                                            label={`${aggregatedGreeks.ethDelta >= 0 ? 'Long' : 'Short'} ${Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH`}
                                            icon={aggregatedGreeks.ethDelta >= 0 ? <TrendingUp sx={{ fontSize: 14 }} /> : <TrendingDown sx={{ fontSize: 14 }} />}
                                            sx={{
                                                height: 22,
                                                bgcolor: aggregatedGreeks.ethDelta >= 0 ? '#10b98120' : '#ef444420',
                                                color: aggregatedGreeks.ethDelta >= 0 ? '#10b981' : '#ef4444',
                                                fontWeight: 'bold',
                                                fontSize: '0.7rem',
                                            }}
                                        />
                                    </Tooltip>
                                )}
                                <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
                            </>
                        )}

                        {/* Greek Values */}
                        <Tooltip title="Portfolio delta - sensitivity to underlying price change">
                            <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">Delta:</Typography>
                                <Typography
                                    variant="caption"
                                    fontWeight="bold"
                                    sx={{ color: (Number(aggregatedGreeks.delta) || 0) >= 0 ? '#10b981' : '#ef4444' }}
                                >
                                    {(Number(aggregatedGreeks.delta) || 0) >= 0 ? '+' : ''}{(Number(aggregatedGreeks.delta) || 0).toFixed(4)}
                                </Typography>
                            </Box>
                        </Tooltip>
                        <Tooltip title="Portfolio gamma - rate of delta change">
                            <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">Gamma:</Typography>
                                <Typography variant="caption" fontWeight="bold">
                                    {(Number(aggregatedGreeks.gamma) || 0).toFixed(6)}
                                </Typography>
                            </Box>
                        </Tooltip>
                        <Tooltip title="Portfolio theta - daily time decay (P&L change per day)">
                            <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">Theta:</Typography>
                                <Typography
                                    variant="caption"
                                    fontWeight="bold"
                                    sx={{ color: (Number(aggregatedGreeks.theta) || 0) >= 0 ? '#10b981' : '#ef4444' }}
                                >
                                    {(Number(aggregatedGreeks.theta) || 0) >= 0 ? '+' : ''}{(Number(aggregatedGreeks.theta) || 0).toFixed(2)}
                                </Typography>
                            </Box>
                        </Tooltip>
                        <Tooltip title="Portfolio vega - sensitivity to 1% IV change">
                            <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">Vega:</Typography>
                                <Typography variant="caption" fontWeight="bold">
                                    {(Number(aggregatedGreeks.vega) || 0).toFixed(2)}
                                </Typography>
                            </Box>
                        </Tooltip>
                    </Box>
                </Box>
            )}
        </>
    );
}

export default React.memo(PortfolioGreeksSummary);
