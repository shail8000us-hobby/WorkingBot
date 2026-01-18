/**
 * PositionCard Component
 *
 * Optimized position card for PositionsPanel
 *
 * PERFORMANCE OPTIMIZED: Phase 6 (Jan 18, 2026)
 * - React.memo to prevent unnecessary re-renders
 * - Props optimized for shallow comparison
 */

import React, { memo } from 'react';
import { Box, Card, CardContent, Typography, Chip, Grid } from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import SymbolBadge from './SymbolBadge';

const PositionCard = memo(
  ({ position, index, getSymbolColor, formatCurrency, formatNumber, getPnlColor }) => {
    // Extract base symbol (BTCUSD, ETHUSD) from position symbol
    const baseSymbol = position.symbol?.includes('BTC')
      ? 'BTCUSD'
      : position.symbol?.includes('ETH')
        ? 'ETHUSD'
        : null;
    const symbolColors = baseSymbol
      ? getSymbolColor(baseSymbol)
      : { bg: '#64748b20', text: '#64748b' };

    return (
      <Card
        sx={{
          bgcolor: '#1e293b',
          border: '1px solid #334155',
          borderLeft: `4px solid ${position.unrealized_pnl >= 0 ? '#10b981' : '#ef4444'}`,
          transition: 'all 0.3s',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
            borderColor: '#475569',
          },
        }}
      >
        <CardContent>
          {/* Position Header */}
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box display="flex" alignItems="center" gap={1}>
              <Box>
                <Typography variant="h6" fontWeight={600} color="#f8fafc">
                  {position.symbol}
                </Typography>
                <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                  <Chip
                    label={position.type}
                    size="small"
                    sx={{
                      bgcolor: position.type === 'OPTION' ? '#8b5cf6' : '#3b82f6',
                      color: 'white',
                      fontWeight: 500,
                    }}
                  />
                  <Chip
                    label={position.size > 0 ? 'LONG' : 'SHORT'}
                    size="small"
                    sx={{
                      bgcolor: position.size > 0 ? '#10b98120' : '#ef444420',
                      color: position.size > 0 ? '#10b981' : '#ef4444',
                      fontWeight: 500,
                    }}
                  />
                  {baseSymbol && <SymbolBadge symbol={baseSymbol} />}
                </Box>
              </Box>
            </Box>

            {/* P&L Badge */}
            <Box textAlign="right">
              <Box display="flex" alignItems="center" justifyContent="flex-end" gap={0.5} mb={0.5}>
                {position.unrealized_pnl >= 0 ? (
                  <TrendingUp sx={{ fontSize: 20, color: '#10b981' }} />
                ) : (
                  <TrendingDown sx={{ fontSize: 20, color: '#ef4444' }} />
                )}
                <Typography
                  variant="h5"
                  fontWeight={700}
                  sx={{ color: getPnlColor(position.unrealized_pnl) }}
                >
                  {formatCurrency(position.unrealized_pnl)}
                </Typography>
              </Box>
              <Typography variant="caption" color="#64748b">
                Unrealized P&L
              </Typography>
            </Box>
          </Box>

          {/* Position Details Grid */}
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="caption" color="#64748b">
                Size
              </Typography>
              <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                {formatNumber(Math.abs(position.size), 4)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="#64748b">
                Entry Price
              </Typography>
              <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                ${formatNumber(position.entry_price, 2)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="#64748b">
                Current Price
              </Typography>
              <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                ${formatNumber(position.mark_price, 2)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="#64748b">
                Liquidation
              </Typography>
              <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                {position.liquidation_price
                  ? `$${formatNumber(position.liquidation_price, 2)}`
                  : 'N/A'}
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  }
);

PositionCard.displayName = 'PositionCard';

export default PositionCard;
