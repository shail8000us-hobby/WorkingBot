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
  LinearProgress,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { AttachMoney as MoneyIcon } from '@mui/icons-material';

const ACCENT_BLUE = '#60a5fa';
const ACCENT_CYAN = '#22d3ee';
const ACCENT_PURPLE = '#a855f7';
const ACCENT_EMERALD = '#34d399';

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

  const isCallSymbol = (symbol) => String(symbol || '').startsWith('C-');
  const isPutSymbol = (symbol) => String(symbol || '').startsWith('P-');

  if (!sortedPositions || sortedPositions.length === 0) return null;

  const livePnl = sortedPositions.reduce((sum, p) => sum + (Number(p.unrealized_pnl) || 0) + (Number(p.realized_pnl) || 0), 0);
  const totalPnl = livePnl + manualPnL;
  const callCount = sortedPositions.filter((p) => isCallSymbol(p.product_symbol)).length;
  const putCount = sortedPositions.filter((p) => isPutSymbol(p.product_symbol)).length;

  // CE/PE lot and cashflow summaries
  // cashflow is always positive (absolute); sign is: short (size<0) = credit received, long (size>0) = debit paid
  const ceLongLots = sortedPositions
    .filter((p) => isCallSymbol(p.product_symbol) && (p.size || 0) > 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const ceShortLots = sortedPositions
    .filter((p) => isCallSymbol(p.product_symbol) && (p.size || 0) < 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const ceNetCash = sortedPositions
    .filter((p) => isCallSymbol(p.product_symbol))
    .reduce((sum, p) => sum + ((p.size || 0) < 0 ? 1 : -1) * (Number(p.cashflow) || 0), 0);

  const peLongLots = sortedPositions
    .filter((p) => isPutSymbol(p.product_symbol) && (p.size || 0) > 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const peShortLots = sortedPositions
    .filter((p) => isPutSymbol(p.product_symbol) && (p.size || 0) < 0)
    .reduce((sum, p) => sum + Math.abs(p.size || 0), 0);
  const peNetCash = sortedPositions
    .filter((p) => isPutSymbol(p.product_symbol))
    .reduce((sum, p) => sum + ((p.size || 0) < 0 ? 1 : -1) * (Number(p.cashflow) || 0), 0);

  // Intrinsic / extrinsic value decomposition per position.
  // product_symbol format: "C-BTC-78400-270426" → underlying=BTC, strike=78400
  // cashflow = absSize × entryPrice × contractMultiplier
  // → absSize × contractMultiplier = cashflow / entryPrice (scale factor, avoids hardcoding multiplier)
  // mark_price is in the same USD/unit-of-underlying as entryPrice
  const computePositionIV = (p) => {
    const absSize = Math.abs(p.size || 0);
    if (absSize === 0) return { intrinsic: 0, extrinsic: 0 };
    const sym = p.product_symbol || '';
    const parts = sym.split('-');
    const strike = parts.length >= 3 ? Number(parts[2]) : 0;
    const underlying = parts.length >= 2 ? parts[1] : 'BTC';
    const spot = underlying === 'ETH' ? (indexPrices?.ETH || 0) : (indexPrices?.BTC || 0);
    if (strike === 0 || spot === 0) return { intrinsic: 0, extrinsic: 0 };
    const entryPrice = Number(p.entry_price) || 0;
    const cf = Number(p.cashflow) || 0;
    const markPrice = Number(p.mark_price) || ((Number(p.best_bid || 0) + Number(p.best_ask || 0)) / 2);
    const intrinsicUnit = isCallSymbol(sym) ? Math.max(0, spot - strike) : Math.max(0, strike - spot);
    const extrinsicUnit = Math.max(0, markPrice - intrinsicUnit);
    const scale = entryPrice > 0 && cf > 0 ? cf / entryPrice : absSize;
    return { intrinsic: intrinsicUnit * scale, extrinsic: extrinsicUnit * scale };
  };

  const ceIV = sortedPositions.filter((p) => isCallSymbol(p.product_symbol)).reduce((s, p) => s + computePositionIV(p).intrinsic, 0);
  const ceEV = sortedPositions.filter((p) => isCallSymbol(p.product_symbol)).reduce((s, p) => s + computePositionIV(p).extrinsic, 0);
  const peIV = sortedPositions.filter((p) => isPutSymbol(p.product_symbol)).reduce((s, p) => s + computePositionIV(p).intrinsic, 0);
  const peEV = sortedPositions.filter((p) => isPutSymbol(p.product_symbol)).reduce((s, p) => s + computePositionIV(p).extrinsic, 0);
  const formatIV = (v) => v < 0.005 ? '$0.00' : `$${v.toFixed(2)}`;

  const formatNetCash = (val) => {
    if (val > 0) return `+$${val.toFixed(2)} CR`;
    if (val < 0) return `-$${Math.abs(val).toFixed(2)} DB`;
    return '$0.00';
  };
  const netCashColor = (val) => (val > 0 ? '#4ade80' : val < 0 ? '#f87171' : '#9ca3af');
  const delta = Number(aggregatedGreeks?.delta) || 0;
  const theta = Number(aggregatedGreeks?.theta) || 0;
  const gamma = Number(aggregatedGreeks?.gamma) || 0;
  const vega = Number(aggregatedGreeks?.vega) || 0;
  const btcDelta = Number(aggregatedGreeks?.btcDelta) || 0;
  const ethDelta = Number(aggregatedGreeks?.ethDelta) || 0;
  const hasGreeks = (Number(aggregatedGreeks?.count) || 0) > 0;

  // Dollar equivalent of delta exposure
  const btcSpot = indexPrices?.BTC || 0;
  const ethSpot = indexPrices?.ETH || 0;
  const deltaExposureUsd = (btcDelta * btcSpot) + (ethDelta * ethSpot);
  const absDeltaExposure = Math.abs(deltaExposureUsd);
  const deltaExposureStr = absDeltaExposure >= 1000
    ? `$${(absDeltaExposure / 1000).toFixed(1)}K`
    : `$${absDeltaExposure.toFixed(0)}`;

  const hasMarginData = !!(marginData && marginData.wallet_balance_usd > 0);
  const blockedMargin = hasMarginData ? Number(marginData.blocked_margin_usd) || 0 : 0;
  const walletBalance = hasMarginData ? Number(marginData.wallet_balance_usd) || 1 : 1;
  const marginUtilPct = hasMarginData
    ? Math.min((blockedMargin / walletBalance) * 100, 100)
    : 0;
  const marginColor = marginUtilPct > 75 ? '#ef4444' : marginUtilPct > 50 ? '#f59e0b' : '#10b981';

  const isStale = dataAgeSec > 30;
  const isWarning = dataAgeSec > 10 && dataAgeSec <= 30;
  const staleBadgeColor = isStale ? '#ef4444' : isWarning ? '#f59e0b' : '#10b981';
  const staleLabel = isStale ? `STALE ${dataAgeSec}s` : isWarning ? `${dataAgeSec}s` : 'LIVE';

  const formatSignedUsd = (value) => {
    if (Math.abs(value) < 0.0005) return '$0.00';
    return `${value > 0 ? '+' : '-'}$${Math.abs(value).toFixed(2)}`;
  };

  const manualPnlColor = Math.abs(manualPnL) < 0.0005
    ? alpha('#cbd5e1', 0.9)
    : getPnlColor(manualPnL);

  const panelTitleSx = {
    display: 'block',
    fontSize: '0.58rem',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    color: alpha('#dbeafe', 0.9),
    fontWeight: 900,
    lineHeight: 1,
  };

  const panelMetaSx = {
    fontSize: '0.56rem',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: alpha('#94a3b8', 0.82),
    fontWeight: 800,
  };

  const panelHeaderSx = (accent) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    pb: 0.45,
    mb: 0.12,
    borderBottom: `1px solid ${alpha('#334155', 0.35)}`,
    '& .header-left': {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 0.5,
    },
    '& .header-dot': {
      width: 6,
      height: 6,
      borderRadius: '50%',
      bgcolor: accent,
      boxShadow: `0 0 10px ${alpha(accent, 0.45)}`,
      flexShrink: 0,
    },
  });

  const panelSx = (accent) => ({
    px: 1.05,
    py: 0.82,
    borderRadius: 1.35,
    border: `1px solid ${alpha(accent, 0.34)}`,
    backgroundImage: `
      radial-gradient(circle at 90% 0%, ${alpha(accent, 0.1)} 0%, transparent 36%),
      linear-gradient(180deg, ${alpha('#0f172a', 0.74)} 0%, ${alpha('#0b1220', 0.92)} 100%)
    `,
    boxShadow: `inset 0 1px 0 ${alpha('#e2e8f0', 0.05)}`,
    minWidth: 0,
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    gap: 0.45,
  });

  const metricRowSx = {
    display: 'grid',
    gridTemplateColumns: 'minmax(0,1fr) auto',
    alignItems: 'center',
    gap: 0.7,
    px: 0.45,
    py: 0.36,
    minHeight: 26,
    borderRadius: 0.9,
    border: `1px solid ${alpha('#334155', 0.28)}`,
    bgcolor: alpha('#0f172a', 0.3),
    transition: 'border-color 120ms ease, background-color 120ms ease',
    '&:hover': {
      borderColor: alpha('#475569', 0.45),
      bgcolor: alpha('#0f172a', 0.4),
    },
  };

  const metricLabelSx = {
    color: alpha('#94a3b8', 0.92),
    fontSize: '0.62rem',
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  };

  const metricValueSx = (color) => ({
    color,
    fontSize: '0.81rem',
    fontWeight: 900,
    fontVariantNumeric: 'tabular-nums',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    lineHeight: 1.1,
    whiteSpace: 'nowrap',
  });

  const ledgerHeaderSx = {
    display: 'grid',
    gridTemplateColumns: '44px repeat(5, minmax(0,1fr))',
    gap: 0.5,
    alignItems: 'center',
    px: 0.35,
    pb: 0.35,
    borderBottom: `1px solid ${alpha('#334155', 0.5)}`,
  };

  const ledgerRowSx = (accent) => ({
    display: 'grid',
    gridTemplateColumns: '44px repeat(5, minmax(0,1fr))',
    gap: 0.5,
    alignItems: 'center',
    px: 0.35,
    py: 0.38,
    borderRadius: 0.85,
    border: `1px solid ${alpha('#334155', 0.28)}`,
    bgcolor: alpha('#0f172a', 0.28),
    '& .ledger-cell': {
      justifySelf: 'end',
      ...metricValueSx(alpha('#e2e8f0', 0.93)),
      fontSize: '0.74rem',
    },
    '& .ledger-leg': {
      justifySelf: 'start',
      color: accent,
      fontSize: '0.74rem',
      fontWeight: 900,
      letterSpacing: '0.05em',
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    },
  });

  // Delta risk badge uses dollar-equivalent exposure for scale-invariant thresholds.
  // Falls back to raw BTC-unit comparison if spot price is unavailable.
  const deltaThresholdReady = btcSpot > 0 || ethSpot > 0;

  // Delta-directional card accent — tints the Portfolio Greeks panel to signal direction at a glance.
  // Near-neutral (< $1K): cyan (unchanged). Positive: green scale. Negative: red scale.
  const greeksCardAccent = (() => {
    if (!hasGreeks || !deltaThresholdReady) return ACCENT_CYAN;
    if (absDeltaExposure < 1000) return ACCENT_CYAN;
    if (deltaExposureUsd > 0) return absDeltaExposure >= 5000 ? '#22c55e' : '#4ade80';
    return absDeltaExposure >= 5000 ? '#ef4444' : '#f87171';
  })();
  let deltaRiskBadge = null;
  if (hasGreeks && (deltaThresholdReady ? absDeltaExposure < 1000 : Math.abs(delta) < 0.05)) {
    deltaRiskBadge = (
      <Chip
        label={`Δ Near-Neutral${deltaThresholdReady ? ` (${deltaExposureStr})` : ''}`}
        size="small"
        color="success"
        variant="outlined"
        sx={{ height: 20, fontSize: '0.67rem', fontWeight: 800 }}
      />
    );
  } else if (hasGreeks && (deltaThresholdReady ? absDeltaExposure >= 1000 && absDeltaExposure < 5000 : Math.abs(delta) >= 0.05 && Math.abs(delta) < 3)) {
    deltaRiskBadge = (
      <Chip
        label={`Δ Moderate (${deltaExposureStr})`}
        size="small"
        color="info"
        variant="outlined"
        sx={{ height: 20, fontSize: '0.67rem', fontWeight: 800 }}
      />
    );
  } else if (hasGreeks && (deltaThresholdReady ? absDeltaExposure >= 5000 && absDeltaExposure < 15000 : Math.abs(delta) >= 3 && Math.abs(delta) < 7)) {
    deltaRiskBadge = (
      <Chip
        label={`Δ Elevated (${deltaExposureStr})`}
        size="small"
        color="warning"
        variant="outlined"
        sx={{ height: 20, fontSize: '0.67rem', fontWeight: 800 }}
      />
    );
  } else if (hasGreeks && (deltaThresholdReady ? absDeltaExposure >= 15000 : Math.abs(delta) >= 7)) {
    deltaRiskBadge = (
      <Chip
        label={`Δ Critical (${deltaExposureStr})`}
        size="small"
        color="error"
        variant="outlined"
        sx={{
          height: 20,
          fontSize: '0.67rem',
          fontWeight: 800,
          animation: 'pulse 1.5s infinite',
          '@keyframes pulse': {
            '0%,100%': { opacity: 1 },
            '50%': { opacity: 0.6 },
          },
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        mb: 1,
        p: 0.85,
        borderRadius: 1.6,
        border: `1px solid ${alpha(ACCENT_BLUE, 0.35)}`,
        backgroundImage: `
          radial-gradient(circle at 12% 0%, ${alpha(ACCENT_BLUE, 0.13)} 0%, transparent 36%),
          radial-gradient(circle at 90% 0%, ${alpha(ACCENT_PURPLE, 0.12)} 0%, transparent 38%),
          linear-gradient(180deg, ${alpha('#0b1220', 0.93)} 0%, ${alpha('#070b14', 0.94)} 100%)
        `,
        boxShadow: [
          `0 0 0 1px ${alpha(ACCENT_BLUE, 0.12)}`,
          `0 10px 26px ${alpha('#000', 0.5)}`,
          `0 0 18px ${alpha(ACCENT_BLUE, 0.12)}`,
        ].join(', '),
        backdropFilter: 'blur(10px)',
      }}
    >
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            md: 'repeat(2, minmax(0, 1fr))',
            xl: '1.15fr 1.35fr 1.15fr 1.1fr',
          },
          gap: 0.72,
          alignItems: 'stretch',
        }}
      >
        {/* Performance */}
        <Box sx={panelSx(ACCENT_EMERALD)}>
          <Box sx={panelHeaderSx(ACCENT_EMERALD)}>
            <Box className="header-left">
              <Box className="header-dot" />
              <Typography variant="caption" sx={panelTitleSx}>Performance</Typography>
            </Box>
            <Typography sx={panelMetaSx}>P&L</Typography>
          </Box>

          <Tooltip
            title={manualPnL !== 0
              ? `Live: ${formatPnl(livePnl)} | Manual: ${manualPnL > 0 ? '+' : ''}$${Math.abs(manualPnL).toFixed(2)} | Total: ${formatPnl(totalPnl)}`
              : ''}
            disableHoverListener={manualPnL === 0}
            arrow
          >
            <Box sx={metricRowSx}>
              <Typography sx={metricLabelSx}>Total PnL</Typography>
              <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.55 }}>
                <MoneyIcon sx={{ fontSize: 14, color: getPnlColor(totalPnl) }} />
                <Typography sx={metricValueSx(getPnlColor(totalPnl))}>{formatPnl(totalPnl)}</Typography>
              </Box>
            </Box>
          </Tooltip>

          <Box sx={metricRowSx}>
            <Typography sx={metricLabelSx}>Live PnL</Typography>
            <Typography sx={metricValueSx(getPnlColor(livePnl))}>{formatPnl(livePnl)}</Typography>
          </Box>

          <Box sx={metricRowSx}>
            <Typography sx={metricLabelSx}>Manual PnL</Typography>
            <Typography sx={metricValueSx(manualPnlColor)}>
              {formatSignedUsd(manualPnL)}
            </Typography>
          </Box>

          <Box sx={metricRowSx}>
            <Typography sx={metricLabelSx}>Option Legs</Typography>
            <Typography sx={metricValueSx(alpha('#e2e8f0', 0.95))}>{callCount}C / {putCount}P</Typography>
          </Box>

          {manualPnLBadge && (
            <Box
              sx={{
                mt: 0.12,
                pt: 0.35,
                display: 'flex',
                justifyContent: 'flex-end',
                borderTop: `1px dashed ${alpha('#475569', 0.45)}`,
              }}
            >
              {manualPnLBadge}
            </Box>
          )}
        </Box>

        {/* CE / PE Exposure */}
        <Box sx={panelSx(ACCENT_BLUE)}>
          <Box sx={panelHeaderSx(ACCENT_BLUE)}>
            <Box className="header-left">
              <Box className="header-dot" />
              <Typography variant="caption" sx={panelTitleSx}>Leg Exposure Ledger</Typography>
            </Box>
            <Typography sx={panelMetaSx}>Lots</Typography>
          </Box>

          <Box sx={ledgerHeaderSx}>
            <Typography sx={metricLabelSx}>Leg</Typography>
            <Typography sx={{ ...metricLabelSx, justifySelf: 'end' }}>Long</Typography>
            <Typography sx={{ ...metricLabelSx, justifySelf: 'end' }}>Short</Typography>
            <Typography sx={{ ...metricLabelSx, justifySelf: 'end' }}>Net Cash</Typography>
            <Tooltip title="Intrinsic Value — in-the-money component of current open positions (spot vs strike)" arrow>
              <Typography sx={{ ...metricLabelSx, justifySelf: 'end', color: '#f59e0b', cursor: 'default' }}>Intr.</Typography>
            </Tooltip>
            <Tooltip title="Extrinsic Value — time/volatility premium remaining in current open positions" arrow>
              <Typography sx={{ ...metricLabelSx, justifySelf: 'end', color: ACCENT_CYAN, cursor: 'default' }}>Extr.</Typography>
            </Tooltip>
          </Box>

          {(callCount > 0 || putCount > 0) ? (
            <>
              <Tooltip title={`Calls — Long: ${ceLongLots} lots, Short: ${ceShortLots} lots, Net cashflow: ${formatNetCash(ceNetCash)} | Intrinsic: ${formatIV(ceIV)} | Extrinsic: ${formatIV(ceEV)}`} arrow>
                <Box sx={ledgerRowSx(ACCENT_BLUE)}>
                  <Typography className="ledger-leg">CE</Typography>
                  <Typography className="ledger-cell" sx={{ color: '#4ade80 !important' }}>{ceLongLots}</Typography>
                  <Typography className="ledger-cell" sx={{ color: '#f87171 !important' }}>{ceShortLots}</Typography>
                  <Typography className="ledger-cell" sx={{ color: `${netCashColor(ceNetCash)} !important` }}>
                    {formatNetCash(ceNetCash)}
                  </Typography>
                  <Typography className="ledger-cell" sx={{ color: `${ceIV > 0.005 ? '#f59e0b' : alpha('#94a3b8', 0.7)} !important` }}>
                    {formatIV(ceIV)}
                  </Typography>
                  <Typography className="ledger-cell" sx={{ color: `${ceEV > 0.005 ? ACCENT_CYAN : alpha('#94a3b8', 0.7)} !important` }}>
                    {formatIV(ceEV)}
                  </Typography>
                </Box>
              </Tooltip>

              <Tooltip title={`Puts — Long: ${peLongLots} lots, Short: ${peShortLots} lots, Net cashflow: ${formatNetCash(peNetCash)} | Intrinsic: ${formatIV(peIV)} | Extrinsic: ${formatIV(peEV)}`} arrow>
                <Box sx={{ ...ledgerRowSx(ACCENT_PURPLE), mt: 0.25 }}>
                  <Typography className="ledger-leg">PE</Typography>
                  <Typography className="ledger-cell" sx={{ color: '#4ade80 !important' }}>{peLongLots}</Typography>
                  <Typography className="ledger-cell" sx={{ color: '#f87171 !important' }}>{peShortLots}</Typography>
                  <Typography className="ledger-cell" sx={{ color: `${netCashColor(peNetCash)} !important` }}>
                    {formatNetCash(peNetCash)}
                  </Typography>
                  <Typography className="ledger-cell" sx={{ color: `${peIV > 0.005 ? '#f59e0b' : alpha('#94a3b8', 0.7)} !important` }}>
                    {formatIV(peIV)}
                  </Typography>
                  <Typography className="ledger-cell" sx={{ color: `${peEV > 0.005 ? ACCENT_CYAN : alpha('#94a3b8', 0.7)} !important` }}>
                    {formatIV(peEV)}
                  </Typography>
                </Box>
              </Tooltip>
            </>
          ) : (
            <Typography sx={{ color: alpha('#cbd5e1', 0.74), fontSize: '0.74rem', py: 0.5 }}>
              No active CE/PE exposure.
            </Typography>
          )}
        </Box>

        {/* Greeks — card accent shifts green/red with delta direction */}
        <Box sx={panelSx(greeksCardAccent)}>
          <Box sx={panelHeaderSx(greeksCardAccent)}>
            <Box className="header-left">
              <Box className="header-dot" />
              <Typography variant="caption" sx={panelTitleSx}>Portfolio Greeks</Typography>
            </Box>
            <Typography sx={panelMetaSx}>Risk</Typography>
          </Box>

          {hasGreeks ? (
            <>
              <Tooltip title={`Portfolio delta (≈ ${deltaExposureStr} directional exposure)`} arrow>
                <Box sx={metricRowSx}>
                  <Typography sx={metricLabelSx}>Delta</Typography>
                  <Typography sx={metricValueSx(delta >= 0 ? '#4ade80' : '#f87171')}>
                    {delta >= 0 ? '+' : ''}{delta.toFixed(4)}
                  </Typography>
                </Box>
              </Tooltip>

              <Tooltip title="Portfolio theta — daily time decay in USD. BTC options trade 24h/day so theta decays continuously." arrow>
                <Box sx={metricRowSx}>
                  <Typography sx={metricLabelSx}>Theta/Day</Typography>
                  <Typography sx={metricValueSx(theta >= 0 ? '#4ade80' : '#f87171')}>
                    {theta >= 0 ? '+' : ''}{theta.toFixed(2)}
                  </Typography>
                </Box>
              </Tooltip>

              <Tooltip title={`Theta per hour = ${theta >= 0 ? '+' : ''}${(theta / 24).toFixed(3)}/hr — BTC options decay continuously 24 h/day, 7 days/week.`} arrow>
                <Box sx={metricRowSx}>
                  <Typography sx={metricLabelSx}>Theta/Hr</Typography>
                  <Typography sx={metricValueSx(theta >= 0 ? alpha('#4ade80', 0.75) : alpha('#f87171', 0.75))}>
                    {theta >= 0 ? '+' : ''}{(theta / 24).toFixed(3)}
                  </Typography>
                </Box>
              </Tooltip>

              <Tooltip title="Portfolio gamma" arrow>
                <Box sx={metricRowSx}>
                  <Typography sx={metricLabelSx}>Gamma</Typography>
                  <Typography sx={metricValueSx(alpha('#e2e8f0', 0.92))}>{gamma.toFixed(6)}</Typography>
                </Box>
              </Tooltip>

              <Tooltip title="Portfolio vega" arrow>
                <Box sx={metricRowSx}>
                  <Typography sx={metricLabelSx}>Vega</Typography>
                  <Typography sx={metricValueSx(alpha('#e2e8f0', 0.92))}>{vega.toFixed(2)}</Typography>
                </Box>
              </Tooltip>

              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.6, pt: 0.25, flexWrap: 'wrap' }}>
                <Typography sx={{ color: alpha('#cbd5e1', 0.8), fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.04em' }}>
                  Directional ≈ {deltaExposureStr}
                </Typography>
                {deltaRiskBadge}
              </Box>
            </>
          ) : (
            <Typography sx={{ color: alpha('#cbd5e1', 0.75), fontSize: '0.74rem', py: 0.65 }}>
              Greeks unavailable.
            </Typography>
          )}
        </Box>

        {/* Hedge + Margin + Live */}
        <Box sx={panelSx(ACCENT_PURPLE)}>
          <Box sx={panelHeaderSx(ACCENT_PURPLE)}>
            <Box className="header-left">
              <Box className="header-dot" />
              <Typography variant="caption" sx={panelTitleSx}>Hedge & Health</Typography>
            </Box>
            <Typography sx={panelMetaSx}>Runtime</Typography>
          </Box>

          <Tooltip title={`BTC futures equivalent: ${Math.abs(btcDelta).toFixed(4)} BTC`} arrow>
            <Box sx={metricRowSx}>
              <Typography sx={metricLabelSx}>BTC Eq.</Typography>
              <Typography sx={metricValueSx(btcDelta >= 0 ? '#4ade80' : '#f87171')}>
                {btcDelta === 0 ? '0.0000' : `${btcDelta >= 0 ? 'L' : 'S'} ${Math.abs(btcDelta).toFixed(4)}`}
              </Typography>
            </Box>
          </Tooltip>

          <Tooltip title={`ETH futures equivalent: ${Math.abs(ethDelta).toFixed(4)} ETH`} arrow>
            <Box sx={metricRowSx}>
              <Typography sx={metricLabelSx}>ETH Eq.</Typography>
              <Typography sx={metricValueSx(ethDelta >= 0 ? '#4ade80' : '#f87171')}>
                {ethDelta === 0 ? '0.0000' : `${ethDelta >= 0 ? 'L' : 'S'} ${Math.abs(ethDelta).toFixed(4)}`}
              </Typography>
            </Box>
          </Tooltip>

          {hasMarginData ? (
            <Tooltip title={`Blocked: $${blockedMargin.toLocaleString()} / Balance: $${walletBalance.toLocaleString()} (${marginUtilPct.toFixed(1)}% utilized)`} arrow>
              <Box sx={metricRowSx}>
                <Typography sx={metricLabelSx}>Margin Util.</Typography>
                <Typography sx={metricValueSx(marginColor)}>{marginUtilPct.toFixed(0)}%</Typography>
              </Box>
            </Tooltip>
          ) : (
            <Box sx={metricRowSx}>
              <Typography sx={metricLabelSx}>Margin Util.</Typography>
              <Typography sx={metricValueSx(alpha('#94a3b8', 0.95))}>N/A</Typography>
            </Box>
          )}

          {hasMarginData && (
            <LinearProgress
              variant="determinate"
              value={marginUtilPct}
              sx={{
                width: '100%',
                height: 6,
                borderRadius: 99,
                bgcolor: alpha(marginColor, 0.18),
                '& .MuiLinearProgress-bar': { bgcolor: marginColor, borderRadius: 99 },
              }}
            />
          )}

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', pt: 0.3 }}>
            <Tooltip title={`Data last updated ${dataAgeSec}s ago`} arrow>
              <Chip
                label={staleLabel}
                size="small"
                variant="outlined"
                sx={{
                  height: 20,
                  fontSize: '0.67rem',
                  fontWeight: 900,
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  bgcolor: `${staleBadgeColor}15`,
                  color: staleBadgeColor,
                  borderColor: staleBadgeColor,
                  letterSpacing: '0.05em',
                  animation: isStale ? 'pulse 1s infinite' : 'none',
                  '@keyframes pulse': {
                    '0%,100%': { opacity: 1 },
                    '50%': { opacity: 0.5 },
                  },
                }}
              />
            </Tooltip>
          </Box>
        </Box>
      </Box>
    </Box>
  );
});

export default PortfolioSummaryStrip;
