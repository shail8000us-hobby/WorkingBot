/**
 * DeltaNeutralCalcModal
 *
 * Workflow:
 *   1. Detects portfolio delta direction (negative → sell puts, positive → sell calls)
 *   2. User selects expiry → filtered option chain loads
 *   3. User clicks a strike row
 *   4. Lots = ceil(|Δ_portfolio| / (|Δ_option_per_contract| × 0.001))
 *   5. Execute → POST /api/options-chain/order  side='sell'
 *
 * Delta Exchange BTC options:
 *   1 lot = 0.001 BTC notional (LOT_MULT)
 *   mark_price / bid / ask are in USD per 1 BTC notional
 *   credit per lot = bid_usd × 0.001
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Box, Typography, Button, IconButton, CircularProgress,
  Table, TableHead, TableBody, TableRow, TableCell,
  Select, MenuItem, FormControl, InputLabel,
  Alert, Chip, Tooltip, LinearProgress,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CalculateIcon from '@mui/icons-material/Calculate';

const LOT_MULT = 0.001;

const MODAL_SX = {
  bgcolor: '#0f1623',
  border: '1px solid #1e2d45',
  borderRadius: '14px',
  color: '#e2e8f0',
  minWidth: 680,
  maxWidth: 780,
};

const CELL_SX = {
  fontSize: '0.72rem',
  py: 0.7, px: 0.9,
  borderBottom: '1px solid #141f2e',
  color: '#cbd5e1',
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
};

const HEAD_SX = {
  ...CELL_SX,
  bgcolor: '#080f1a',
  color: '#64748b',
  fontWeight: 700,
  fontSize: '0.63rem',
  letterSpacing: '0.07em',
  textTransform: 'uppercase',
};

// ── Pure helpers (stable across renders) ─────────────────────────────────────

/**
 * Calculate lots needed to neutralise portfolio delta by selling options.
 * Formula: ceil(|Δ_portfolio| / (|Δ_option| × LOT_MULT))
 *
 * Delta Exchange convention: delta is SIGNED (negative for puts, positive for calls).
 * Selling reverses the sign, so |delta| gives the per-lot offset magnitude.
 */
function calcLots(portfolioDelta, optionDelta) {
  const dPerLot = Math.abs(optionDelta) * LOT_MULT;
  if (dPerLot < 1e-10) return null;
  return Math.ceil(Math.abs(portfolioDelta) / dPerLot);
}

/**
 * Post-hedge portfolio delta after selling `lots` of the option.
 *
 * Selling an option: seller's delta = −(buyer's delta)
 *   • Sell put  (buyerΔ < 0): seller gets +|Δ| per lot  → offsets negative portfolio Δ
 *   • Sell call (buyerΔ > 0): seller gets −|Δ| per lot  → offsets positive portfolio Δ
 *
 * postΔ = portfolioΔ + (−optionDelta × lots × LOT_MULT)
 */
function calcPostDelta(portfolioDelta, optionDelta, lots) {
  return portfolioDelta + (-1 * optionDelta * lots * LOT_MULT);
}

/** Lot-count risk tier for UX warnings */
function lotRiskTier(lots) {
  if (lots == null) return 'none';
  if (lots > 2000) return 'extreme';
  if (lots > 500)  return 'high';
  if (lots > 200)  return 'moderate';
  return 'normal';
}
const LOT_WARN = {
  extreme:  { color: '#ef4444', label: '⛔ Extreme — likely impractical margin', bg: '#ef444418' },
  high:     { color: '#f59e0b', label: '⚠ High — consider closer-to-ATM strike', bg: '#f59e0b18' },
  moderate: { color: '#fbbf24', label: '⚡ Elevated — verify margin capacity',   bg: '#fbbf2412' },
  normal:   null,
  none:     null,
};

// bid/ask/mark_price on Delta Exchange are USD per 1 BTC notional;
// 1 lot = 0.001 BTC  →  credit per lot = price × 0.001
const creditPerLot = (priceUsd) =>
  priceUsd > 0 ? priceUsd * LOT_MULT : null;

const fmtD = (v) =>
  v != null ? (v >= 0 ? '+' : '') + Number(v).toFixed(4) : '—';

const fmtUsd = (v, decimals = 0) =>
  v != null ? `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: decimals })}` : '—';

const fmtUsd2 = (v) => fmtUsd(v, 2);

const dColor = (v) =>
  v == null ? '#94a3b8'
  : Math.abs(v) < 0.005 ? '#10b981'
  : v >= 0 ? '#4ade80' : '#f87171';

// ── Component ─────────────────────────────────────────────────────────────────

export default function DeltaNeutralCalcModal({
  open, portfolioDelta, indexPrices, onClose,
}) {
  const [expirations, setExpirations]         = useState([]);
  const [selectedExpiry, setSelectedExpiry]   = useState('');
  const [chainData, setChainData]             = useState(null);
  const [loadingExp, setLoadingExp]           = useState(false);
  const [loadingChain, setLoadingChain]       = useState(false);
  const [error, setError]                     = useState('');
  const [selectedStrike, setSelectedStrike]   = useState(null);
  const [orderType, setOrderType]             = useState('limit');
  const [execStatus, setExecStatus]           = useState('idle');
  const [execMsg, setExecMsg]                 = useState('');
  const [execOrderId, setExecOrderId]         = useState('');

  const btcSpot  = Number(indexPrices?.BTC) || 0;
  const pDelta   = portfolioDelta ?? 0;
  const absDelta = Math.abs(pDelta);

  // If portfolio delta < 0 → sell PUTS (add positive delta)
  // If portfolio delta > 0 → sell CALLS (add negative delta)
  const optType  = pDelta <= 0 ? 'put' : 'call';
  const optLabel = optType === 'put' ? 'PUTS' : 'CALLS';
  const dirLabel = optType === 'put' ? 'Short Delta → Sell Puts' : 'Long Delta → Sell Calls';
  const dirColor = optType === 'put' ? '#f87171' : '#4ade80';

  const resetExec = useCallback(() => {
    setExecStatus('idle'); setExecMsg(''); setExecOrderId('');
  }, []);

  // ── Fetch expirations on open ─────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    setError(''); setChainData(null); setSelectedStrike(null); resetExec();
    setLoadingExp(true);
    fetch('/api/options-chain/expirations?underlying=BTC')
      .then((r) => r.json())
      .then((d) => {
        const exps = d.expirations || [];
        setExpirations(exps);
        if (exps.length > 0) setSelectedExpiry(exps[0]);
      })
      .catch(() => setError('Failed to fetch expirations'))
      .finally(() => setLoadingExp(false));
  }, [open, resetExec]);

  // ── Fetch chain when expiry changes ──────────────────────────────────────
  useEffect(() => {
    if (!selectedExpiry) return;
    setError(''); setChainData(null); setSelectedStrike(null); resetExec();
    setLoadingChain(true);
    fetch(`/api/options-chain/data?underlying=BTC&expiry=${selectedExpiry}`)
      .then((r) => r.json())
      .then((d) => {
        // Backend returns result.chain (array of {strike, call, put})
        setChainData(d);
      })
      .catch(() => setError('Failed to fetch options chain'))
      .finally(() => setLoadingChain(false));
  }, [selectedExpiry, resetExec]);

  // ── Build rows ────────────────────────────────────────────────────────────
  // Show ONLY the relevant option type (puts for negative delta, calls for positive)
  // Require: valid bid/ask AND non-zero delta (real market data)
  const rows = useMemo(() => {
    const strikes = chainData?.chain;
    if (!Array.isArray(strikes) || strikes.length === 0) return [];

    const built = strikes
      .map((s) => {
        const opt = s[optType];
        if (!opt) return null;

        const delta    = Number(opt.delta)      || 0;
        const bidUsd   = Number(opt.bid)        || 0;
        const askUsd   = Number(opt.ask)        || 0;
        const markUsd  = Number(opt.mark_price) || 0;
        const iv       = Number(opt.iv)         || 0;
        const oi       = Number(opt.oi)         || 0;

        // Skip strikes with missing market data (no real bid/ask or no delta)
        if (bidUsd === 0 && askUsd === 0) return null;
        if (Math.abs(delta) < 1e-6) return null;

        const lots     = calcLots(pDelta, delta);
        const post     = lots != null ? calcPostDelta(pDelta, delta, lots) : null;

        // For a sell limit order we receive the bid price per lot
        const perLotBid  = creditPerLot(bidUsd);
        const perLotMark = creditPerLot(markUsd);
        const totalBid   = lots != null && perLotBid  != null ? lots * perLotBid  : null;
        const totalMark  = lots != null && perLotMark != null ? lots * perLotMark : null;

        // Notional margin estimate: lots × mark × LOT_MULT (rough)
        const notionalEst = lots != null && markUsd > 0 ? lots * markUsd * LOT_MULT : null;

        return {
          strike:    s.strike,
          delta,
          bidUsd,
          askUsd,
          markUsd,
          iv,
          oi,
          lots,
          post,
          perLotBid,
          perLotMark,
          totalBid,
          totalMark,
          notionalEst,
          symbol:    opt.symbol,
          risk:      lotRiskTier(lots),
        };
      })
      .filter(Boolean)
      // For puts: sort descending by strike (closest to spot first for negative delta case)
      // For calls: sort ascending
      .sort((a, b) => optType === 'put' ? b.strike - a.strike : a.strike - b.strike);

    // Tag the "best" (most capital-efficient) strike: fewest lots with acceptable residual
    let bestIdx = -1;
    let bestLots = Infinity;
    built.forEach((r, i) => {
      if (r.lots != null && r.lots < bestLots && r.lots > 0 && r.bidUsd > 0) {
        bestLots = r.lots;
        bestIdx = i;
      }
    });
    if (bestIdx >= 0) built[bestIdx].isBest = true;

    return built;
  }, [chainData, pDelta, optType]);

  // Auto-select the strike nearest to ATM when chain data loads (expiry change only).
  // Intentionally does NOT depend on `rows` or `pDelta` — live delta ticks must
  // not reset a strike the user has manually selected.
  useEffect(() => {
    if (!chainData?.chain || !chainData?.atm_strike) return;
    const atm = chainData.atm_strike;
    let best = null;
    let bestDist = Infinity;
    chainData.chain.forEach((s) => {
      const opt = s[optType];
      if (!opt) return;
      const delta  = Number(opt.delta) || 0;
      const bidUsd = Number(opt.bid)   || 0;
      const askUsd = Number(opt.ask)   || 0;
      if (bidUsd === 0 && askUsd === 0) return;
      if (Math.abs(delta) < 1e-6) return;
      const dist = Math.abs(s.strike - atm);
      if (dist < bestDist) { bestDist = dist; best = s.strike; }
    });
    if (best != null) setSelectedStrike(best);
  }, [chainData, optType]);

  const sel = rows.find((r) => r.strike === selectedStrike);

  // ── Execute order ────────────────────────────────────────────────────────
  const handleExecute = async () => {
    if (!sel?.symbol || !sel?.lots) return;
    setExecStatus('loading');
    try {
      const limitPrice = orderType === 'limit'
        ? (sel.markUsd > 0 ? sel.markUsd : sel.bidUsd)
        : undefined;

      const payload = {
        symbol:     sel.symbol,
        side:       'sell',
        size:       sel.lots,
        order_type: orderType,
        ...(limitPrice ? { limit_price: limitPrice } : {}),
      };

      const res  = await fetch('/api/options-chain/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.success) {
        setExecStatus('success');
        setExecOrderId(data.order_id || '');
      } else {
        setExecStatus('error');
        setExecMsg(data.error || data.message || 'Order failed');
      }
    } catch (err) {
      setExecStatus('error');
      setExecMsg(err.message || 'Network error');
    }
  };

  const isLoading = loadingExp || loadingChain;
  const canExec   = !!sel && (sel.lots ?? 0) > 0
    && execStatus !== 'loading' && execStatus !== 'success';

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <Dialog
      open={open}
      onClose={execStatus === 'loading' ? undefined : onClose}
      PaperProps={{ sx: MODAL_SX }}
      BackdropProps={{ sx: { backdropFilter: 'blur(4px)', bgcolor: 'rgba(0,0,0,0.75)' } }}
      maxWidth={false}
    >
      {/* Header */}
      <DialogTitle sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid #1e2d45', pb: 1.5,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CalculateIcon sx={{ color: '#60a5fa' }} />
          <Typography fontWeight="bold" fontSize="1rem">Delta Neutral Calculator</Typography>
          <Chip label={dirLabel} size="small" sx={{
            height: 18, fontSize: '0.62rem',
            bgcolor: `${dirColor}18`, color: dirColor,
          }} />
        </Box>
        <IconButton size="small" onClick={onClose}
          disabled={execStatus === 'loading'} sx={{ color: '#94a3b8' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 2, pb: 1 }}>
        {/* Summary cards */}
        <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
          <Box sx={{ flex: 1, p: 1.5, bgcolor: '#1a2235', border: '1px solid #2d3f5a', borderRadius: 2 }}>
            <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 0.3 }}>
              Portfolio Delta
            </Typography>
            <Typography variant="h6" fontWeight="bold"
              sx={{ color: pDelta < 0 ? '#f87171' : '#4ade80', fontFamily: 'monospace' }}>
              {fmtD(pDelta)} BTC
            </Typography>
            {btcSpot > 0 && (
              <Typography variant="caption" sx={{ color: '#64748b' }}>
                ≈ {fmtUsd(absDelta * btcSpot)} exposure
              </Typography>
            )}
          </Box>

          <Box sx={{ flex: 1, p: 1.5, bgcolor: '#1a2235', border: '1px solid #2d3f5a', borderRadius: 2 }}>
            <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 0.3 }}>
              Action
            </Typography>
            <Typography variant="body1" fontWeight="bold" sx={{ color: '#e2e8f0' }}>
              SELL {optLabel}
            </Typography>
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              {rows.length > 0
                ? `${rows.length} strikes available — click to select`
                : isLoading ? 'Loading chain…' : 'Select expiry above'}
            </Typography>
          </Box>

          <Box sx={{ flex: 1, p: 1.5, bgcolor: '#1a2235', border: '1px solid #2d3f5a', borderRadius: 2 }}>
            <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 0.3 }}>
              BTC Spot / ATM
            </Typography>
            <Typography variant="body1" fontWeight="bold"
              sx={{ color: '#e2e8f0', fontFamily: 'monospace' }}>
              {btcSpot > 0 ? fmtUsd(btcSpot) : '—'}
            </Typography>
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              ATM: {chainData?.atm_strike?.toLocaleString() || '…'}
            </Typography>
          </Box>
        </Box>

        {/* Expiry selector */}
        <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel sx={{ color: '#64748b', fontSize: '0.75rem' }}>Expiry</InputLabel>
            <Select
              value={selectedExpiry}
              label="Expiry"
              onChange={(e) => setSelectedExpiry(e.target.value)}
              disabled={loadingExp || expirations.length === 0}
              sx={{
                bgcolor: '#1a2235', color: '#e2e8f0', fontSize: '0.75rem',
                '& .MuiOutlinedInput-notchedOutline': { borderColor: '#2d3f5a' },
                '& .MuiSvgIcon-root': { color: '#64748b' },
              }}
            >
              {expirations.map((exp) => (
                <MenuItem key={exp} value={exp} sx={{ fontSize: '0.75rem' }}>{exp}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {isLoading && <CircularProgress size={16} sx={{ color: '#60a5fa' }} />}

          {!isLoading && chainData && (
            <Typography variant="caption" sx={{ color: '#475569' }}>
              {rows.length} {optLabel} with live data · ATM highlighted · click to select
            </Typography>
          )}
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 1.5, py: 0.5, bgcolor: 'rgba(239,68,68,0.1)',
            color: '#f87171', border: '1px solid #ef4444' }}>
            {error}
          </Alert>
        )}

        {/* Strike table */}
        {!isLoading && rows.length > 0 && (
          <Box sx={{ maxHeight: 280, overflowY: 'auto',
            border: '1px solid #1e2d45', borderRadius: 1.5, mb: 1.5 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {[
                    'Strike',
                    `${optType === 'put' ? 'Put' : 'Call'} Δ`,
                    'Lots',
                    'Bid',
                    'Mark',
                    'Credit',
                    'Post Δ',
                    'Notional',
                    'IV',
                  ].map((h) => (
                    <TableCell key={h} sx={HEAD_SX}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => {
                  const isSel = row.strike === selectedStrike;
                  const isAtm = chainData?.atm_strike === row.strike;
                  const abPost = row.post != null ? Math.abs(row.post) : null;
                  const warn = LOT_WARN[row.risk];
                  return (
                    <TableRow key={row.strike}
                      onClick={() => { setSelectedStrike(row.strike); resetExec(); }}
                      sx={{
                        cursor: 'pointer',
                        bgcolor: isSel ? '#122040' : 'transparent',
                        outline: isSel ? '1px solid #3b82f640' : 'none',
                        '&:hover': { bgcolor: isSel ? '#122040' : '#0e1a2a' },
                      }}
                    >
                      {/* Strike + badges */}
                      <TableCell sx={{ ...CELL_SX,
                        fontWeight: isSel ? 700 : 400,
                        color: isSel ? '#60a5fa' : isAtm ? '#f59e0b' : '#cbd5e1' }}>
                        {row.strike.toLocaleString()}
                        {isAtm && (
                          <Chip label="ATM" size="small" sx={{
                            ml: 0.5, height: 13, fontSize: '0.5rem',
                            bgcolor: '#f59e0b18', color: '#f59e0b',
                          }} />
                        )}
                        {row.isBest && (
                          <Chip label="BEST" size="small" sx={{
                            ml: 0.5, height: 13, fontSize: '0.5rem',
                            bgcolor: '#10b98118', color: '#10b981',
                          }} />
                        )}
                      </TableCell>

                      {/* Delta (buyer view — negative for puts, positive for calls) */}
                      <TableCell sx={{ ...CELL_SX, color: '#94a3b8' }}>
                        {fmtD(row.delta)}
                      </TableCell>

                      {/* Lots to sell — with risk colour */}
                      <TableCell sx={{ ...CELL_SX, fontWeight: 700,
                        fontSize: '0.78rem',
                        color: warn ? warn.color : isSel ? '#ffffff' : '#e2e8f0' }}>
                        {row.lots != null ? row.lots.toLocaleString() : '—'}
                        {warn && (
                          <Tooltip title={warn.label} arrow>
                            <span style={{ marginLeft: 3, fontSize: '0.6rem' }}>⚠</span>
                          </Tooltip>
                        )}
                      </TableCell>

                      {/* Bid */}
                      <TableCell sx={{ ...CELL_SX, color: '#10b981' }}>
                        {row.bidUsd > 0 ? fmtUsd(row.bidUsd) : '—'}
                      </TableCell>

                      {/* Mark */}
                      <TableCell sx={{ ...CELL_SX, color: '#94a3b8' }}>
                        {row.markUsd > 0 ? fmtUsd(row.markUsd) : '—'}
                      </TableCell>

                      {/* Total credit at bid for all lots */}
                      <TableCell sx={{ ...CELL_SX, color: '#10b981', fontWeight: 600 }}>
                        {row.totalBid != null ? fmtUsd2(row.totalBid) : '—'}
                      </TableCell>

                      {/* Post-hedge delta */}
                      <TableCell sx={{ ...CELL_SX, color: dColor(row.post) }}>
                        {row.post != null ? fmtD(row.post) : '—'}
                        {abPost != null && abPost < 0.002 && (
                          <Chip label="✓" size="small" sx={{
                            ml: 0.4, height: 13, fontSize: '0.5rem',
                            bgcolor: '#10b98118', color: '#10b981',
                          }} />
                        )}
                      </TableCell>

                      {/* Notional estimate */}
                      <TableCell sx={{ ...CELL_SX, color: '#64748b', fontSize: '0.65rem' }}>
                        {row.notionalEst != null ? fmtUsd2(row.notionalEst) : '—'}
                      </TableCell>

                      {/* IV */}
                      <TableCell sx={{ ...CELL_SX, color: '#64748b' }}>
                        {row.iv > 0 ? `${(row.iv * 100).toFixed(1)}%` : '—'}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Box>
        )}

        {!isLoading && rows.length === 0 && !error && chainData && (
          <Box sx={{ py: 3, textAlign: 'center', border: '1px solid #1e2d45',
            borderRadius: 1.5, mb: 1.5 }}>
            <Typography variant="body2" sx={{ color: '#64748b' }}>
              No {optLabel} with live bid/ask data found for this expiry.
            </Typography>
            <Typography variant="caption" sx={{ color: '#475569' }}>
              Try another expiry.
            </Typography>
          </Box>
        )}

        {/* Selected strike summary */}
        {sel && (
          <Box sx={{ p: 1.5, bgcolor: '#0b1828',
            border: '1px solid #2d4a70', borderRadius: 2 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{
                color: '#60a5fa', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {sel.strike.toLocaleString()} {optType.toUpperCase()} · {sel.symbol}
              </Typography>
              <Typography variant="caption"
                sx={{ color: '#475569', fontFamily: 'monospace' }}>
                ⌈|{absDelta.toFixed(5)}| ÷ (|{sel.delta.toFixed(4)}| × 0.001)⌉ = {sel.lots}
              </Typography>
            </Box>

            {/* Lot count warning */}
            {LOT_WARN[sel.risk] && (
              <Alert severity={sel.risk === 'extreme' ? 'error' : 'warning'} sx={{
                mb: 1, py: 0.3, fontSize: '0.72rem',
                bgcolor: LOT_WARN[sel.risk].bg,
                color: LOT_WARN[sel.risk].color,
                border: `1px solid ${LOT_WARN[sel.risk].color}`,
              }}>
                {LOT_WARN[sel.risk].label} — {sel.lots?.toLocaleString()} lots required because this strike has low delta ({Math.abs(sel.delta).toFixed(4)}). A closer-to-ATM strike needs fewer lots.
              </Alert>
            )}

            {/* Stats */}
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, mb: 1.5 }}>
              {[
                { label: 'Lots to Sell', value: sel.lots?.toLocaleString() ?? '—', color: LOT_WARN[sel.risk] ? LOT_WARN[sel.risk].color : '#ffffff', big: true },
                { label: 'Sell-side Δ/Lot', value: `${pDelta < 0 ? '+' : '−'}${(Math.abs(sel.delta) * LOT_MULT).toFixed(5)} BTC`, color: '#4ade80' },
                { label: 'Bid (per lot)', value: sel.perLotBid != null ? fmtUsd2(sel.perLotBid) : '—', color: '#10b981' },
                { label: 'Total Credit @ Bid', value: sel.totalBid != null ? fmtUsd2(sel.totalBid) : '—', color: '#10b981', bold: true },
                { label: 'Current Δ', value: `${fmtD(pDelta)} BTC`, color: pDelta < 0 ? '#f87171' : '#4ade80' },
                { label: 'Post-Hedge Δ', value: sel.post != null ? `${fmtD(sel.post)} BTC` : '—', color: dColor(sel.post) },
                { label: 'Δ Reduction', value: sel.post != null && absDelta > 0 ? `${((1 - Math.abs(sel.post) / absDelta) * 100).toFixed(1)}%` : '—', color: '#60a5fa' },
                { label: 'Est. Notional', value: sel.notionalEst != null ? fmtUsd2(sel.notionalEst) : '—', color: '#94a3b8' },
              ].map(({ label, value, color, big, bold }) => (
                <Box key={label}>
                  <Typography variant="caption" sx={{
                    color: '#475569', display: 'block',
                    fontSize: '0.58rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    {label}
                  </Typography>
                  <Typography sx={{
                    color, fontWeight: bold || big ? 700 : 400,
                    fontSize: big ? '1.1rem' : '0.78rem', fontFamily: 'monospace' }}>
                    {value}
                  </Typography>
                </Box>
              ))}
            </Box>

            {/* Order type toggle */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#64748b' }}>Order:</Typography>
              {['limit', 'market'].map((ot) => (
                <Button key={ot} size="small" onClick={() => setOrderType(ot)} sx={{
                  px: 1.2, py: 0.2, minWidth: 0, fontSize: '0.68rem', fontWeight: 700,
                  textTransform: 'none',
                  bgcolor: orderType === ot ? '#1e3a5f' : 'transparent',
                  color:   orderType === ot ? '#60a5fa' : '#475569',
                  border:  `1px solid ${orderType === ot ? '#3b82f6' : '#1e2d45'}`,
                  borderRadius: '6px',
                  '&:hover': { bgcolor: '#172a45' },
                }}>
                  {ot === 'limit' ? `📌 Limit @ ${sel.markUsd > 0 ? fmtUsd(sel.markUsd) : 'mark'}` : '⚡ Market'}
                </Button>
              ))}
              <Typography variant="caption" sx={{ color: '#334155', ml: 0.5 }}>
                {orderType === 'limit'
                  ? 'Post-only at mark price — maker only'
                  : 'Fills immediately at best bid — taker fee'}
              </Typography>
            </Box>

            {/* Exec feedback */}
            {execStatus === 'loading' && (
              <LinearProgress sx={{ mb: 1, borderRadius: 1 }} />
            )}
            {execStatus === 'success' && (
              <Alert severity="success" sx={{ mb: 1, py: 0.4, fontSize: '0.75rem',
                bgcolor: 'rgba(16,185,129,0.1)', color: '#10b981',
                border: '1px solid #10b981' }}>
                ✅ Order #{execOrderId} placed — SELL {sel.lots} × {optType.toUpperCase()} {sel.strike.toLocaleString()}
              </Alert>
            )}
            {execStatus === 'error' && (
              <Alert severity="error" sx={{ mb: 1, py: 0.4, fontSize: '0.75rem',
                bgcolor: 'rgba(239,68,68,0.1)', color: '#f87171',
                border: '1px solid #ef4444' }}>
                ❌ {execMsg}
              </Alert>
            )}
          </Box>
        )}
      </DialogContent>

      {/* Footer */}
      <DialogActions sx={{ borderTop: '1px solid #1e2d45', px: 2, pb: 2, pt: 1.5, gap: 1 }}>
        <Typography variant="caption" sx={{ color: '#334155', flex: 1 }}>
          ⚠️ Sells are option writing (short selling). Verify margin before executing.
        </Typography>
        <Button onClick={onClose} disabled={execStatus === 'loading'} sx={{
          color: '#94a3b8', border: '1px solid #2d3f5a',
          '&:hover': { bgcolor: '#1a2235' }, px: 2,
        }}>
          Close
        </Button>
        <Tooltip title={
          !sel ? 'Select a strike first'
          : execStatus === 'success' ? 'Order placed'
          : `SELL ${sel.lots} lots ${optType.toUpperCase()} ${sel.strike?.toLocaleString()} @ ${orderType}`
        } arrow>
          <span>
            <Button onClick={handleExecute} disabled={!canExec} sx={{
              px: 2.5, fontWeight: 700,
              bgcolor: canExec ? '#1a3a5c' : '#0f1a28',
              color:   canExec ? '#60a5fa' : '#334155',
              border: `1px solid ${canExec ? '#3b82f6' : '#1e2d45'}`,
              '&:hover': { bgcolor: '#1e4a72' },
              '&.Mui-disabled': { bgcolor: '#0f1a28', color: '#2d3f5a', border: '1px solid #1e2d45' },
            }}>
              {execStatus === 'loading' ? 'Placing…'
                : execStatus === 'success' ? '✅ Placed'
                : `⚡ Execute SELL ${sel?.lots ?? '—'} lots`}
            </Button>
          </span>
        </Tooltip>
      </DialogActions>
    </Dialog>
  );
}
