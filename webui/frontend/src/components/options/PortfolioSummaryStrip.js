/**
 * PortfolioSummaryStrip — Extracted from OptionsPanel.js (Phase 4.6)
 *
 * Sticky summary bar showing portfolio PnL, C/P counts, Greeks inline,
 * futures equivalent, and Delta Neutral / High Delta badges.
 */
import React from 'react';
import {
  Box,
  Chip,
  Divider,
  Tooltip,
  Typography,
} from '@mui/material';
import { AttachMoney as MoneyIcon } from '@mui/icons-material';

const PortfolioSummaryStrip = React.memo(function PortfolioSummaryStrip({
  sortedPositions,
  aggregatedGreeks,
  formatPnl,
  getPnlColor,
}) {
  if (!sortedPositions || sortedPositions.length === 0) return null;

  const totalPnl = sortedPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const callCount = sortedPositions.filter((p) => p.product_symbol.startsWith('C-')).length;
  const putCount = sortedPositions.filter((p) => p.product_symbol.startsWith('P-')).length;
  const delta = Number(aggregatedGreeks.delta) || 0;
  const theta = Number(aggregatedGreeks.theta) || 0;
  const gamma = Number(aggregatedGreeks.gamma) || 0;
  const vega = Number(aggregatedGreeks.vega) || 0;
  const btcDelta = Number(aggregatedGreeks.btcDelta) || 0;
  const ethDelta = Number(aggregatedGreeks.ethDelta) || 0;

  return (
    <Box
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        mb: 1,
        py: 0.75,
        px: 1.5,
        bgcolor: 'background.paper',
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        gap: 2,
        flexWrap: 'wrap',
        alignItems: 'center',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }}
    >
      {/* Total PnL */}
      <Chip
        icon={<MoneyIcon />}
        label={`PnL: ${formatPnl(totalPnl)}`}
        size="small"
        sx={{
          fontWeight: 'bold',
          bgcolor: getPnlColor(totalPnl) + '20',
          color: getPnlColor(totalPnl),
        }}
      />
      {/* Calls / Puts count */}
      <Chip
        label={`📈 ${callCount}C`}
        size="small"
        sx={{
          height: 22,
          bgcolor: '#3b82f615',
          color: '#3b82f6',
          fontSize: '0.7rem',
          fontWeight: 'bold',
        }}
      />
      <Chip
        label={`📉 ${putCount}P`}
        size="small"
        sx={{
          height: 22,
          bgcolor: '#a855f715',
          color: '#a855f7',
          fontSize: '0.7rem',
          fontWeight: 'bold',
        }}
      />
      {/* Inline Greeks — compact */}
      {aggregatedGreeks.count > 0 && (
        <>
          <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />
          <Tooltip title="Portfolio delta">
            <Typography
              variant="caption"
              sx={{
                fontWeight: 'bold',
                color: delta >= 0 ? '#10b981' : '#ef4444',
              }}
            >
              Δ {delta >= 0 ? '+' : ''}
              {delta.toFixed(4)}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio theta (daily time decay)">
            <Typography
              variant="caption"
              sx={{
                fontWeight: 'bold',
                color: theta >= 0 ? '#10b981' : '#ef4444',
              }}
            >
              θ {theta >= 0 ? '+' : ''}
              {theta.toFixed(2)}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio gamma">
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              γ {gamma.toFixed(6)}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio vega">
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              ν {vega.toFixed(2)}
            </Typography>
          </Tooltip>
        </>
      )}
      {/* Futures equivalent — compact */}
      {btcDelta !== 0 && (
        <>
          <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />
          <Tooltip
            title={`BTC futures equivalent: ${Math.abs(btcDelta).toFixed(4)} BTC`}
          >
            <Typography
              variant="caption"
              sx={{
                fontWeight: 'bold',
                color: btcDelta >= 0 ? '#10b981' : '#ef4444',
              }}
            >
              BTC: {btcDelta >= 0 ? 'L' : 'S'} {Math.abs(btcDelta).toFixed(4)}
            </Typography>
          </Tooltip>
        </>
      )}
      {ethDelta !== 0 && (
        <Tooltip
          title={`ETH futures equivalent: ${Math.abs(ethDelta).toFixed(4)} ETH`}
        >
          <Typography
            variant="caption"
            sx={{
              fontWeight: 'bold',
              color: ethDelta >= 0 ? '#10b981' : '#ef4444',
            }}
          >
            ETH: {ethDelta >= 0 ? 'L' : 'S'} {Math.abs(ethDelta).toFixed(4)}
          </Typography>
        </Tooltip>
      )}
      {/* Delta Neutral badge */}
      {aggregatedGreeks.count > 0 && Math.abs(delta) < 0.1 && (
        <Chip
          label="Δ Neutral ✅"
          size="small"
          color="info"
          sx={{ height: 18, fontSize: '0.6rem' }}
        />
      )}
      {aggregatedGreeks.count > 0 && Math.abs(delta) > 10 && (
        <Chip
          label="High Δ ⚠️"
          size="small"
          color="warning"
          sx={{ height: 18, fontSize: '0.6rem' }}
        />
      )}
    </Box>
  );
});

export default PortfolioSummaryStrip;
