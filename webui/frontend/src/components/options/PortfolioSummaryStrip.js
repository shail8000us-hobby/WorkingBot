/**
 * PortfolioSummaryStrip — Extracted from OptionsPanel.js (Phase 4.6)
 *
 * Sticky summary bar showing portfolio PnL, C/P counts, Greeks inline,
 * futures equivalent, and Delta Neutral / High Delta badges.
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Chip,
  Divider,
  LinearProgress,
  Tooltip,
  Typography,
} from '@mui/material';
import { AttachMoney as MoneyIcon } from '@mui/icons-material';

const PortfolioSummaryStrip = React.memo(function PortfolioSummaryStrip({
  sortedPositions,
  aggregatedGreeks,
  formatPnl,
  getPnlColor,
  indexPrices,
  marginData,
  lastDataUpdate,
  manualPnL = 0,
  manualPnLBadge = null,
}) {
  // Phase 6.6: Stale data detection — tick every second (hooks must be before early return)
  const [dataAgeSec, setDataAgeSec] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setDataAgeSec(Math.floor((Date.now() - (lastDataUpdate || Date.now())) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [lastDataUpdate]);

  if (!sortedPositions || sortedPositions.length === 0) return null;

  const livePnl = sortedPositions.reduce((sum, p) => sum + (Number(p.unrealized_pnl) || 0) + (Number(p.partial_realized_pnl) || 0), 0);
  const totalPnl = livePnl + manualPnL;
  const callCount = sortedPositions.filter((p) => p.product_symbol.startsWith('C-')).length;
  const putCount = sortedPositions.filter((p) => p.product_symbol.startsWith('P-')).length;

  // CE/PE lot and cashflow summaries
  // cashflow is always positive (absolute); sign is: short (size<0) = credit received, long (size>0) = debit paid
  const ceLongLots = sortedPositions
    .filter((p) => p.product_symbol.startsWith('C-') && (p.size || 0) > 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const ceShortLots = sortedPositions
    .filter((p) => p.product_symbol.startsWith('C-') && (p.size || 0) < 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const ceNetCash = sortedPositions
    .filter((p) => p.product_symbol.startsWith('C-'))
    .reduce((sum, p) => sum + ((p.size || 0) < 0 ? 1 : -1) * (Number(p.cashflow) || 0), 0);

  const peLongLots = sortedPositions
    .filter((p) => p.product_symbol.startsWith('P-') && (p.size || 0) > 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const peShortLots = sortedPositions
    .filter((p) => p.product_symbol.startsWith('P-') && (p.size || 0) < 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const peNetCash = sortedPositions
    .filter((p) => p.product_symbol.startsWith('P-'))
    .reduce((sum, p) => sum + ((p.size || 0) < 0 ? 1 : -1) * (Number(p.cashflow) || 0), 0);

  const formatNetCash = (val) => {
    if (val > 0) return `+$${val.toFixed(2)} CR`;
    if (val < 0) return `-$${Math.abs(val).toFixed(2)} DB`;
    return '$0.00';
  };
  const netCashColor = (val) => (val > 0 ? '#4ade80' : val < 0 ? '#f87171' : '#9ca3af');
  const delta = Number(aggregatedGreeks.delta) || 0;
  const theta = Number(aggregatedGreeks.theta) || 0;
  const gamma = Number(aggregatedGreeks.gamma) || 0;
  const vega = Number(aggregatedGreeks.vega) || 0;
  const btcDelta = Number(aggregatedGreeks.btcDelta) || 0;
  const ethDelta = Number(aggregatedGreeks.ethDelta) || 0;

  // Dollar equivalent of delta exposure
  const btcSpot = indexPrices?.BTC || 0;
  const ethSpot = indexPrices?.ETH || 0;
  const deltaExposureUsd = (btcDelta * btcSpot) + (ethDelta * ethSpot);
  const absDeltaExposure = Math.abs(deltaExposureUsd);
  const deltaExposureStr = absDeltaExposure >= 1000
    ? `$${(absDeltaExposure / 1000).toFixed(1)}K`
    : `$${absDeltaExposure.toFixed(0)}`;

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
      <Tooltip
        title={manualPnL !== 0
          ? `Live: ${formatPnl(livePnl)} | Manual: ${manualPnL > 0 ? '+' : ''}$${Math.abs(manualPnL).toFixed(2)} | Total: ${formatPnl(totalPnl)}`
          : ''}
        disableHoverListener={manualPnL === 0}
        arrow
      >
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
      </Tooltip>
      {/* Calls / Puts count */}
      <Chip
        label={`📈 ${callCount}C`}
        size="small"
        sx={{
          height: 22,
          bgcolor: '#3b82f615',
          color: '#3b82f6',
          fontSize: '1.4rem',
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
          fontSize: '1.4rem',
          fontWeight: 'bold',
        }}
      />
      {/* Manual PnL badge — display-only offset for payoff graph */}
      {manualPnLBadge}
      {/* CE summary: Long lots / Short lots / Net cashflow */}
      {callCount > 0 && (
        <Tooltip title={`CE Calls — Long: ${ceLongLots} lots, Short: ${ceShortLots} lots, Net cashflow: ${formatNetCash(ceNetCash)}`}>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.4,
              px: 0.8,
              py: 0.2,
              borderRadius: 1,
              border: '1px solid #3b82f640',
              bgcolor: '#3b82f608',
              fontSize: '1.36rem',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
            }}
          >
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#3b82f6', fontWeight: 'bold' }}>CE:</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#4ade80', fontWeight: 'bold' }}>▲{ceLongLots}L</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#f87171', fontWeight: 'bold' }}>▼{ceShortLots}S</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: netCashColor(ceNetCash), fontWeight: 'bold' }}>💰{formatNetCash(ceNetCash)}</Typography>
          </Box>
        </Tooltip>
      )}
      {/* PE summary: Long lots / Short lots / Net cashflow */}
      {putCount > 0 && (
        <Tooltip title={`PE Puts — Long: ${peLongLots} lots, Short: ${peShortLots} lots, Net cashflow: ${formatNetCash(peNetCash)}`}>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.4,
              px: 0.8,
              py: 0.2,
              borderRadius: 1,
              border: '1px solid #a855f740',
              bgcolor: '#a855f708',
              fontSize: '1.36rem',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
            }}
          >
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#a855f7', fontWeight: 'bold' }}>PE:</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#4ade80', fontWeight: 'bold' }}>▲{peLongLots}L</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: '#f87171', fontWeight: 'bold' }}>▼{peShortLots}S</Typography>
            <Typography component="span" sx={{ fontSize: '1.36rem', color: netCashColor(peNetCash), fontWeight: 'bold' }}>💰{formatNetCash(peNetCash)}</Typography>
          </Box>
        </Tooltip>
      )}
      {/* Inline Greeks — compact */}
      {aggregatedGreeks.count > 0 && (
        <>
          <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />
          <Tooltip title={`Portfolio delta (≈ ${deltaExposureStr} directional exposure)`}>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 'bold',
                color: delta >= 0 ? '#10b981' : '#ef4444',
                fontSize: '1.5rem',
              }}
            >
              Δ {delta >= 0 ? '+' : ''}
              {delta.toFixed(4)}
              {absDeltaExposure > 0 && (
                <Typography component="span" variant="caption" sx={{ ml: 0.5, opacity: 0.7, fontSize: '1.3rem' }}>
                  ≈{deltaExposureStr}
                </Typography>
              )}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio theta (daily time decay)">
            <Typography
              variant="caption"
              sx={{
                fontWeight: 'bold',
                color: theta >= 0 ? '#10b981' : '#ef4444',
                fontSize: '1.5rem',
              }}
            >
              θ {theta >= 0 ? '+' : ''}
              {theta.toFixed(2)}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio gamma">
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '1.5rem' }}>
              γ {gamma.toFixed(6)}
            </Typography>
          </Tooltip>
          <Tooltip title="Portfolio vega">
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '1.5rem' }}>
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
                fontSize: '1.5rem',
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
              fontSize: '1.5rem',
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
          sx={{ height: 18, fontSize: '1.2rem' }}
        />
      )}
      {aggregatedGreeks.count > 0 && Math.abs(delta) >= 3 && Math.abs(delta) < 7 && (
        <Chip
          label={`High Δ ⚠️ (≈${deltaExposureStr})`}
          size="small"
          color="warning"
          sx={{ height: 18, fontSize: '1.2rem' }}
        />
      )}
      {aggregatedGreeks.count > 0 && Math.abs(delta) >= 7 && (
        <Chip
          label={`🚨 Δ ${delta.toFixed(2)} (≈${deltaExposureStr})`}
          size="small"
          color="error"
          sx={{ height: 18, fontSize: '1.2rem', animation: 'pulse 1.5s infinite', '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.6 } } }}
        />
      )}

      {/* Phase 6.2: Margin Utilization Bar */}
      {marginData && marginData.wallet_balance_usd > 0 && (() => {
        const blocked = marginData.blocked_margin_usd || 0;
        const balance = marginData.wallet_balance_usd || 1;
        const utilPct = Math.min((blocked / balance) * 100, 100);
        const mColor = utilPct > 75 ? '#ef4444' : utilPct > 50 ? '#f59e0b' : '#10b981';
        return (
          <>
            <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />
            <Tooltip title={`Blocked: $${blocked.toLocaleString()} / Balance: $${balance.toLocaleString()} (${utilPct.toFixed(1)}% utilized)`}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 110 }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: mColor, whiteSpace: 'nowrap', fontSize: '1.3rem' }}>
                  Margin: {utilPct.toFixed(0)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={utilPct}
                  sx={{
                    width: 50,
                    height: 6,
                    borderRadius: 3,
                    bgcolor: `${mColor}20`,
                    '& .MuiLinearProgress-bar': { bgcolor: mColor, borderRadius: 3 },
                  }}
                />
              </Box>
            </Tooltip>
          </>
        );
      })()}

      {/* Phase 6.6: Stale Data Indicator */}
      {(() => {
        const isStale = dataAgeSec > 30;
        const isWarning = dataAgeSec > 10 && dataAgeSec <= 30;
        const badgeColor = isStale ? '#ef4444' : isWarning ? '#f59e0b' : '#10b981';
        const label = isStale ? `STALE ${dataAgeSec}s` : isWarning ? `${dataAgeSec}s` : 'LIVE';
        return (
          <Tooltip title={`Data last updated ${dataAgeSec}s ago`}>
            <Chip
              label={label}
              size="small"
              sx={{
                height: 18,
                fontSize: '1.2rem',
                fontWeight: 'bold',
                bgcolor: `${badgeColor}15`,
                color: badgeColor,
                borderColor: badgeColor,
                ml: 'auto',
                animation: isStale ? 'pulse 1s infinite' : 'none',
                '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
              }}
              variant="outlined"
            />
          </Tooltip>
        );
      })()}
    </Box>
  );
});

export default PortfolioSummaryStrip;
