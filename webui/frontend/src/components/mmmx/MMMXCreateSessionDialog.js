/**
 * MMMXCreateSessionDialog + MMMXDeployTr1Dialog
 * Extracted from MMMXDashboard.js.
 */

import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Chip, Button, CircularProgress, Divider, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { mmmxService } from './mmmxService';
import { formatDdmmyy, ddmmyyyyToDdmmyy, computeUpcomingExpiries } from './utils/mmmxFormatters';

// Kept as last-resort fallback when Delta Exchange API is unavailable
const FALLBACK_EXPIRIES = computeUpcomingExpiries(3);

export function MMMXCreateSessionDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    total_budget_lots: 100,
    otm_distance_pct: 15,
    hard_stop_multiplier: 2.0,
    close_at_dte: 7,
    tranche_deploy_move_pct: 2.0,
    hedging_enabled: true,
    hedge_distance_pct: 20,
    target_expiry_ddmmyy: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [liveExpiries, setLiveExpiries] = useState(null);   // null = loading, [] = failed
  const [expiriesError, setExpiriesError] = useState('');

  // Reset form and fetch live expiries on open
  useEffect(() => {
    if (!open) return;
    setForm({
      total_budget_lots: 100, otm_distance_pct: 15, hard_stop_multiplier: 2.0,
      close_at_dte: 7, tranche_deploy_move_pct: 2.0, hedging_enabled: true,
      hedge_distance_pct: 20, target_expiry_ddmmyy: '',
    });
    setError('');
    setLiveExpiries(null);
    setExpiriesError('');

    mmmxService.getExpirations('BTC').then(res => {
      if (Array.isArray(res.expirations) && res.expirations.length > 0) {
        const converted = res.expirations.map(ddmmyyyyToDdmmyy).filter(Boolean);
        setLiveExpiries(converted);
      } else {
        setExpiriesError('Delta Exchange API unavailable — showing computed approximations.');
        setLiveExpiries([]);
      }
    }).catch(() => {
      setExpiriesError('Delta Exchange API unavailable — showing computed approximations.');
      setLiveExpiries([]);
    });
  }, [open]);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleCreate = async () => {
    if (!form.target_expiry_ddmmyy || form.target_expiry_ddmmyy.length !== 6) {
      setError('Enter a valid 6-digit expiry (DDMMYY) from your Delta Exchange contract.');
      return;
    }
    setBusy(true); setError('');
    try {
      const res = await mmmxService.createSession(form);
      if (res.ok) {
        onCreated(res.data);
        onClose();
      } else {
        setError(res.error || 'Failed to create session');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        New MMMX Session
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          Creates a DRAFT session. Deploy Tranche 1 to activate it and start monitoring.
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1.5 }}>

          {/* ── Expiry selection — live from Delta Exchange ── */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Target Expiry *
              </Typography>
              {liveExpiries === null ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
                  <CircularProgress size={12} />
                  <Typography variant="caption" color="text.secondary">Fetching from Delta Exchange…</Typography>
                </Box>
              ) : liveExpiries.length > 0 ? (
                <Chip size="small" color="success" label={`${liveExpiries.length} live contracts`} sx={{ height: 20, fontSize: '0.65rem' }} />
              ) : (
                <Chip size="small" color="warning" label="API unavailable — approx. dates shown" sx={{ height: 20, fontSize: '0.65rem' }} />
              )}
            </Box>

            {expiriesError && (
              <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mb: 0.8 }}>
                ⚠ {expiriesError}
              </Typography>
            )}

            {/* Expiry chips — live from Delta Exchange or fallback approximations */}
            <Box sx={{ display: 'flex', gap: 0.8, flexWrap: 'wrap', mb: 1.2 }}>
              {(liveExpiries?.length > 0 ? liveExpiries : FALLBACK_EXPIRIES.map(e => e.ddmmyy)).map(ddmmyy => (
                <Chip
                  key={ddmmyy}
                  size="small"
                  variant={form.target_expiry_ddmmyy === ddmmyy ? 'filled' : 'outlined'}
                  color={form.target_expiry_ddmmyy === ddmmyy ? 'success' : 'default'}
                  label={`${formatDdmmyy(ddmmyy)} · ${ddmmyy}`}
                  onClick={() => set('target_expiry_ddmmyy', ddmmyy)}
                  sx={{ cursor: 'pointer', fontSize: '0.75rem',
                    ...(form.target_expiry_ddmmyy !== ddmmyy && { opacity: 0.8 }) }}
                />
              ))}
            </Box>

            {/* Fallback manual entry */}
            <TextField
              size="small"
              fullWidth
              label="Or enter DDMMYY manually"
              placeholder="e.g., 260426"
              value={form.target_expiry_ddmmyy}
              inputProps={{ maxLength: 6, style: { fontFamily: 'monospace', letterSpacing: 2 } }}
              helperText={
                form.target_expiry_ddmmyy.length === 6
                  ? `Symbol format: C-BTC-STRIKE-${form.target_expiry_ddmmyy}`
                  : 'DD MM YY — must match contract suffix exactly'
              }
              FormHelperTextProps={{
                sx: { color: form.target_expiry_ddmmyy.length === 6 ? '#4caf50' : 'text.secondary', fontFamily: 'monospace' }
              }}
              onChange={e => {
                const v = e.target.value.replace(/\D/g, '').slice(0, 6);
                set('target_expiry_ddmmyy', v);
              }}
            />
          </Box>

          <Divider />

          {/* ── Strategy params ── */}
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: -1 }}>Strategy Parameters</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <TextField size="small" type="number" label="Total Budget Lots"
              value={form.total_budget_lots}
              helperText="Max lots across all 10 tranches"
              onChange={e => set('total_budget_lots', Number(e.target.value))} />
            <TextField size="small" type="number" label="OTM Distance %"
              value={form.otm_distance_pct}
              helperText="Target strike OTM % at entry"
              onChange={e => set('otm_distance_pct', Number(e.target.value))} />
            <TextField size="small" type="number" label="Hard Stop Multiplier"
              value={form.hard_stop_multiplier} inputProps={{ step: 0.1, min: 1, max: 5 }}
              helperText="× premium collected = max loss"
              onChange={e => set('hard_stop_multiplier', Number(e.target.value))} />
            <TextField size="small" type="number" label="Close at DTE (min 7)"
              value={form.close_at_dte} inputProps={{ min: 7 }}
              helperText="Force-close when DTE reaches this"
              onChange={e => set('close_at_dte', Math.max(7, Number(e.target.value)))} />
            <TextField size="small" type="number" label="Tranche Deploy Move %"
              value={form.tranche_deploy_move_pct} inputProps={{ step: 0.5 }}
              helperText="Spot move % to trigger next tranche"
              onChange={e => set('tranche_deploy_move_pct', Number(e.target.value))} />
            <TextField size="small" type="number" label="Hedge Distance %"
              value={form.hedge_distance_pct} inputProps={{ min: 10, max: 50 }}
              helperText="OTM % for perp hedge entry"
              onChange={e => set('hedge_distance_pct', Number(e.target.value))} />
          </Box>

          {error && <Alert severity="error">{error}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="contained" onClick={handleCreate} disabled={busy}
          startIcon={busy ? <CircularProgress size={14} color="inherit" /> : <AddIcon />}>
          Create Session
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// TRANCHE_COUNT is always 10 per spec
const TRANCHE_COUNT = 10;

// Compute mid-price from bid/ask, fallback to mark.
function _mid(bid, ask, mark) {
  if (bid > 0 && ask > 0) return parseFloat(((bid + ask) / 2).toFixed(4));
  if (mark > 0) return parseFloat(mark);
  return '';
}

export function MMMXDeployTr1Dialog({ open, sessionId, session, targetExpiry, onClose, onDeployed }) {
  // lots_per_tranche = floor(total_budget_lots / 10), minimum 1
  const lotsPerTranche = Math.max(1, Math.floor(
    (session?.params?.total_budget_lots ?? 100) / TRANCHE_COUNT
  ));

  const blankForm = () => ({
    ce_symbol: '', ce_strike: '', pe_symbol: '', pe_strike: '',
    lots: lotsPerTranche,
    ce_premium: '', pe_premium: '', ce_delta: '', pe_delta: '',
    spot: '', iv_rank: '',
  });

  const [form, setForm] = useState(blankForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState('');

  // On open: reset + auto-fetch strike data from exchange
  useEffect(() => {
    if (!open) return;
    const fresh = blankForm();
    setForm(fresh);
    setError('');
    setScanMsg('');

    if (!sessionId) return;
    const otmPct = session?.params?.otm_distance_pct ?? 15;
    setScanning(true);
    setScanMsg('Fetching live strikes from exchange…');
    mmmxService.scanStrikes(sessionId, otmPct)
      .then(r => {
        const data = r.data ?? r;
        if (data?.ce && data?.pe) {
          const ceBid  = data.ce.bid  ?? 0;
          const ceAsk  = data.ce.ask  ?? 0;
          const peBid  = data.pe.bid  ?? 0;
          const peAsk  = data.pe.ask  ?? 0;
          setForm(prev => ({
            ...prev,
            ce_symbol:  data.ce.symbol  ?? '',
            ce_strike:  data.ce.strike  ?? '',
            ce_delta:   data.ce.delta != null ? parseFloat(data.ce.delta.toFixed(4)) : '',
            ce_premium: _mid(ceBid, ceAsk, data.ce.mark_price),
            pe_symbol:  data.pe.symbol  ?? '',
            pe_strike:  data.pe.strike  ?? '',
            pe_delta:   data.pe.delta != null ? parseFloat(data.pe.delta.toFixed(4)) : '',
            pe_premium: _mid(peBid, peAsk, data.pe.mark_price),
            spot:       data.spot ? parseFloat(data.spot.toFixed(2)) : '',
          }));
          setScanMsg('');
        } else if (data?.reason === 'no_expiry_set') {
          setScanMsg('No expiry set — enter symbols manually.');
        } else {
          setScanMsg('Live chain unavailable — enter symbols manually.');
        }
      })
      .catch(() => setScanMsg('Strike scan failed — enter symbols manually.'))
      .finally(() => setScanning(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sessionId]);

  // Recompute lots when session params change (e.g., dialog stays mounted)
  useEffect(() => {
    if (!open) return;
    setForm(prev => ({ ...prev, lots: lotsPerTranche }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotsPerTranche, open]);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const autoFillStrike = (sym, side) => {
    const parts = sym.split('-');
    if (parts.length >= 3) {
      const strike = parseFloat(parts[2]);
      if (!isNaN(strike)) set(side === 'ce' ? 'ce_strike' : 'pe_strike', strike);
    }
  };

  const handleDeploy = async () => {
    if (!form.ce_symbol || !form.pe_symbol || !form.ce_strike || !form.pe_strike) {
      setError('CE Symbol, PE Symbol, CE Strike, and PE Strike are required');
      return;
    }
    setBusy(true); setError('');
    try {
      const payload = {
        ce_symbol: form.ce_symbol.trim(),
        pe_symbol: form.pe_symbol.trim(),
        ce_strike: parseFloat(form.ce_strike),
        pe_strike: parseFloat(form.pe_strike),
        lots: parseInt(form.lots, 10),
      };
      if (form.ce_premium) payload.ce_premium = parseFloat(form.ce_premium);
      if (form.pe_premium) payload.pe_premium = parseFloat(form.pe_premium);
      if (form.ce_delta) payload.ce_delta = parseFloat(form.ce_delta);
      if (form.pe_delta) payload.pe_delta = parseFloat(form.pe_delta);
      if (form.spot) payload.spot = parseFloat(form.spot);
      if (form.iv_rank) payload.iv_rank = parseFloat(form.iv_rank);

      const res = await mmmxService.deployTranche1(sessionId, payload);
      if (res.ok) {
        onDeployed(res.data);
        onClose();
      } else {
        setError(res.error || res.reason || 'Deploy failed');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const expSuffix = targetExpiry ? `-${targetExpiry}` : '-DDMMYY';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        Deploy Tranche 1
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          Symbol format: <code style={{ fontFamily: 'monospace', fontSize: '0.8em' }}>
            C-BTC-STRIKE{expSuffix}
          </code>
          {targetExpiry && (
            <Chip label={`Expiry: ${targetExpiry}`} size="small" color="primary"
              sx={{ ml: 1, height: 18, fontSize: '0.65rem' }} />
          )}
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>

          {/* Scan status banner */}
          {(scanning || scanMsg) && (
            <Alert severity={scanning ? 'info' : scanMsg === '' ? 'success' : 'warning'}
              icon={scanning ? <CircularProgress size={16} color="inherit" /> : undefined}
              sx={{ py: 0.4 }}>
              {scanning ? scanMsg || 'Fetching live strikes…' : scanMsg}
            </Alert>
          )}

          {/* CE side */}
          <Box sx={{ p: 1.5, border: '1px solid', borderColor: 'success.dark', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="success.main" sx={{ mb: 1, fontWeight: 700 }}>
              CE — Call Option (Short)
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              <TextField size="small" label="CE Symbol"
                placeholder={`C-BTC-85000${expSuffix}`}
                value={form.ce_symbol}
                onChange={e => { set('ce_symbol', e.target.value); autoFillStrike(e.target.value, 'ce'); }} />
              <TextField size="small" type="number" label="CE Strike"
                value={form.ce_strike} onChange={e => set('ce_strike', e.target.value)} />
              <TextField size="small" type="number" label="CE Premium / Mid (USD)"
                helperText="Bid/ask mid — order will be at this price"
                value={form.ce_premium} onChange={e => set('ce_premium', e.target.value)} />
              <TextField size="small" type="number" label="CE Delta" inputProps={{ step: 0.001 }}
                value={form.ce_delta} onChange={e => set('ce_delta', e.target.value)} />
            </Box>
          </Box>

          {/* PE side */}
          <Box sx={{ p: 1.5, border: '1px solid', borderColor: 'error.dark', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="error.main" sx={{ mb: 1, fontWeight: 700 }}>
              PE — Put Option (Short)
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              <TextField size="small" label="PE Symbol"
                placeholder={`P-BTC-65000${expSuffix}`}
                value={form.pe_symbol}
                onChange={e => { set('pe_symbol', e.target.value); autoFillStrike(e.target.value, 'pe'); }} />
              <TextField size="small" type="number" label="PE Strike"
                value={form.pe_strike} onChange={e => set('pe_strike', e.target.value)} />
              <TextField size="small" type="number" label="PE Premium / Mid (USD)"
                helperText="Bid/ask mid — order will be at this price"
                value={form.pe_premium} onChange={e => set('pe_premium', e.target.value)} />
              <TextField size="small" type="number" label="PE Delta" inputProps={{ step: 0.001 }}
                value={form.pe_delta} onChange={e => set('pe_delta', e.target.value)} />
            </Box>
          </Box>

          {/* Common */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1.5 }}>
            <TextField size="small" type="number" label="Lots per Side (this tranche)"
              helperText={`Budget ÷ 10 tranches = ${lotsPerTranche}`}
              value={form.lots} inputProps={{ min: 1 }}
              onChange={e => set('lots', e.target.value)} />
            <TextField size="small" type="number" label="Spot (USD)"
              placeholder="auto-filled"
              value={form.spot} onChange={e => set('spot', e.target.value)} />
            <TextField size="small" type="number" label="IV Rank (0-100)"
              placeholder="optional"
              value={form.iv_rank} onChange={e => set('iv_rank', e.target.value)} />
          </Box>

          {error && <Alert severity="error">{error}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="contained" color="success" onClick={handleDeploy} disabled={busy || scanning}
          startIcon={busy ? <CircularProgress size={14} color="inherit" /> : <RocketLaunchIcon />}>
          {busy ? 'Deploying...' : 'Deploy Tranche 1'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
