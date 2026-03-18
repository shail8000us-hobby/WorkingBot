/**
 * MMMTradeAuditPanel — Trade Transparency System
 *
 * Institutional-grade audit view for an MMM session.
 * Sub-tabs: Trades | Strike Summary | P&L | Events | Reconcile
 *
 * Created: 2026-03-18
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Box, Typography, Paper, Tabs, Tab, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Chip,
  IconButton, Tooltip, CircularProgress, Alert, Button,
  Divider, Grid,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import mmmService from './mmmService';

// =============================================================================
// Helpers
// =============================================================================

const fmtTs = (ts) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleTimeString('en-IN', { hour12: false });
  } catch (_) { return ts; }
};

const fmtDate = (ts) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
      + ' ' + new Date(ts).toLocaleTimeString('en-IN', { hour12: false });
  } catch (_) { return ts; }
};

const pnlColor = (v) => (v > 0 ? '#4caf50' : v < 0 ? '#f44336' : 'text.secondary');

const ACTION_COLOR = { BUY: '#4fc3f7', SELL: '#ff8a65' };
const SEV_COLOR = { CRITICAL: '#f44336', WARN: '#ff9800', INFO: '#9e9e9e' };
const SIDE_COLOR = { CE: '#42a5f5', PE: '#ef9a9a' };

const MonoCell = ({ children, color }) => (
  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.78rem', color: color || 'text.primary', py: 0.5, px: 1 }}>
    {children}
  </TableCell>
);

const HeaderCell = ({ children }) => (
  <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', color: 'text.secondary', py: 0.75, px: 1, whiteSpace: 'nowrap' }}>
    {children}
  </TableCell>
);

// =============================================================================
// Sub-panel: Trade Log
// =============================================================================

const TradeLog = ({ sessionId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mmmService.getAuditTrades(sessionId);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load trades');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(load, 15000, 60000, true);

  const trades = data?.trades || [];

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {trades.length} fill{trades.length !== 1 ? 's' : ''} recorded
        </Typography>
        <IconButton size="small" onClick={load} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {loading && !data && <CircularProgress size={20} />}

      {trades.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
          No fills recorded yet
        </Typography>
      )}

      {trades.length > 0 && (
        <TableContainer component={Paper} sx={{ bgcolor: 'rgba(255,255,255,0.02)', maxHeight: 420 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: 'rgba(0,0,0,0.4)' } }}>
                <HeaderCell>Time</HeaderCell>
                <HeaderCell>Action</HeaderCell>
                <HeaderCell>Side</HeaderCell>
                <HeaderCell>Strike</HeaderCell>
                <HeaderCell>Lots</HeaderCell>
                <HeaderCell>Premium</HeaderCell>
                <HeaderCell>Event</HeaderCell>
                <HeaderCell>Realized P&L</HeaderCell>
                <HeaderCell>Remark</HeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.map((t, i) => (
                <TableRow key={i} hover sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' } }}>
                  <MonoCell>{fmtTs(t.created_at)}</MonoCell>
                  <TableCell sx={{ py: 0.5, px: 1 }}>
                    <Chip
                      label={t.action}
                      size="small"
                      sx={{
                        bgcolor: ACTION_COLOR[t.action] ? `${ACTION_COLOR[t.action]}22` : 'rgba(255,255,255,0.08)',
                        color: ACTION_COLOR[t.action] || 'text.primary',
                        fontWeight: 700, fontSize: '0.7rem', height: 20,
                      }}
                    />
                  </TableCell>
                  <TableCell sx={{ py: 0.5, px: 1 }}>
                    <Chip
                      label={t.option_type || '—'}
                      size="small"
                      sx={{
                        bgcolor: SIDE_COLOR[t.option_type] ? `${SIDE_COLOR[t.option_type]}22` : 'rgba(255,255,255,0.06)',
                        color: SIDE_COLOR[t.option_type] || 'text.secondary',
                        fontSize: '0.68rem', height: 18,
                      }}
                    />
                  </TableCell>
                  <MonoCell>{t.strike || '—'}</MonoCell>
                  <MonoCell>{t.quantity_filled ?? t.quantity_requested ?? '—'}</MonoCell>
                  <MonoCell>${(t.premium || 0).toFixed(2)}</MonoCell>
                  <MonoCell>{t.event_type || '—'}</MonoCell>
                  <MonoCell color={pnlColor(t.realized_pnl_usd)}>
                    {t.realized_pnl_usd != null ? `$${t.realized_pnl_usd.toFixed(4)}` : '—'}
                  </MonoCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary', py: 0.5, px: 1, maxWidth: 300 }}>
                    <Tooltip title={t.remark || ''} arrow placement="top">
                      <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280 }}>
                        {t.remark || '—'}
                      </span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

// =============================================================================
// Sub-panel: Strike Summary
// =============================================================================

const StrikeSummary = ({ sessionId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mmmService.getAuditStrikeSummary(sessionId);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load strike summary');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(load, 20000, 90000, true);

  const rows = data?.summary || [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">{rows.length} strike(s)</Typography>
        <IconButton size="small" onClick={load} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {loading && !data && <CircularProgress size={20} />}
      {rows.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>No data</Typography>
      )}

      {rows.length > 0 && (
        <TableContainer component={Paper} sx={{ bgcolor: 'rgba(255,255,255,0.02)', maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: 'rgba(0,0,0,0.4)' } }}>
                <HeaderCell>Side</HeaderCell>
                <HeaderCell>Strike</HeaderCell>
                <HeaderCell>Sell Qty</HeaderCell>
                <HeaderCell>Buy Qty</HeaderCell>
                <HeaderCell>Open Qty</HeaderCell>
                <HeaderCell>Avg Sell</HeaderCell>
                <HeaderCell>Avg Buy</HeaderCell>
                <HeaderCell>Gross Premium</HeaderCell>
                <HeaderCell>Realized P&L</HeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i} hover sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' } }}>
                  <TableCell sx={{ py: 0.5, px: 1 }}>
                    <Chip
                      label={r.option_type || '—'}
                      size="small"
                      sx={{
                        bgcolor: SIDE_COLOR[r.option_type] ? `${SIDE_COLOR[r.option_type]}22` : 'rgba(255,255,255,0.06)',
                        color: SIDE_COLOR[r.option_type] || 'text.secondary',
                        fontSize: '0.68rem', height: 18,
                      }}
                    />
                  </TableCell>
                  <MonoCell>{r.strike}</MonoCell>
                  <MonoCell>{r.sell_qty ?? '—'}</MonoCell>
                  <MonoCell>{r.buy_qty ?? '—'}</MonoCell>
                  <MonoCell color={r.open_qty > 0 ? '#ff9800' : '#4caf50'}>{r.open_qty ?? '—'}</MonoCell>
                  <MonoCell>${(r.avg_sell_premium || 0).toFixed(2)}</MonoCell>
                  <MonoCell>{r.avg_buy_premium > 0 ? `$${r.avg_buy_premium.toFixed(2)}` : '—'}</MonoCell>
                  <MonoCell color="#42a5f5">${(r.gross_premium_usd || 0).toFixed(4)}</MonoCell>
                  <MonoCell color={pnlColor(r.realized_pnl_usd)}>
                    {r.realized_pnl_usd != null ? `$${r.realized_pnl_usd.toFixed(4)}` : '—'}
                  </MonoCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

// =============================================================================
// Sub-panel: P&L Attribution
// =============================================================================

const PnLAttribution = ({ sessionId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mmmService.getAuditPnL(sessionId);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load P&L');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(load, 20000, 90000, true);

  const attr = data?.attribution || {};

  const kpis = [
    { label: 'Total Realized P&L', value: attr.total_realized_pnl_usd, prefix: '$', decimals: 4 },
    { label: 'CE Realized', value: attr.ce_realized_pnl_usd, prefix: '$', decimals: 4 },
    { label: 'PE Realized', value: attr.pe_realized_pnl_usd, prefix: '$', decimals: 4 },
    { label: 'CE Gross Premium', value: attr.ce_gross_premium_usd, prefix: '$', decimals: 4, neutral: true },
    { label: 'PE Gross Premium', value: attr.pe_gross_premium_usd, prefix: '$', decimals: 4, neutral: true },
    { label: 'Total Gross Premium', value: attr.total_gross_premium_usd, prefix: '$', decimals: 4, neutral: true },
    { label: 'CE Open Lots', value: attr.ce_open_lots, decimals: 0, neutral: true },
    { label: 'PE Open Lots', value: attr.pe_open_lots, decimals: 0, neutral: true },
    { label: 'Total Fills', value: attr.total_fills, decimals: 0, neutral: true },
    { label: 'CE Fills', value: attr.ce_fills, decimals: 0, neutral: true },
    { label: 'PE Fills', value: attr.pe_fills, decimals: 0, neutral: true },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
        <IconButton size="small" onClick={load} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {loading && !data && <CircularProgress size={20} />}
      {data && (
        <Grid container spacing={1.5}>
          {kpis.map((k) => {
            const v = k.value;
            const display = v != null
              ? `${k.prefix || ''}${Number(v).toFixed(k.decimals ?? 2)}`
              : '—';
            const color = k.neutral
              ? '#2196f3'
              : v != null ? pnlColor(v) : 'text.secondary';
            return (
              <Grid item xs={6} sm={4} md={3} key={k.label}>
                <Paper sx={{ p: 1.5, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, height: '100%' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', display: 'block' }}>
                    {k.label}
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: 'monospace', fontWeight: 600, color, mt: 0.25, fontSize: '1rem' }}>
                    {display}
                  </Typography>
                </Paper>
              </Grid>
            );
          })}
        </Grid>
      )}
    </Box>
  );
};

// =============================================================================
// Sub-panel: Events Log
// =============================================================================

const EventsLog = ({ sessionId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mmmService.getAuditEvents(sessionId);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load events');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(load, 20000, 90000, true);

  const events = data?.events || [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">{events.length} event(s)</Typography>
        <IconButton size="small" onClick={load} disabled={loading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {loading && !data && <CircularProgress size={20} />}
      {events.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>No events recorded yet</Typography>
      )}
      {events.length > 0 && (
        <TableContainer component={Paper} sx={{ bgcolor: 'rgba(255,255,255,0.02)', maxHeight: 420 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: 'rgba(0,0,0,0.4)' } }}>
                <HeaderCell>Time</HeaderCell>
                <HeaderCell>Category</HeaderCell>
                <HeaderCell>Type</HeaderCell>
                <HeaderCell>Severity</HeaderCell>
                <HeaderCell>Remark</HeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((e, i) => (
                <TableRow key={i} hover sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' } }}>
                  <MonoCell>{fmtDate(e.created_at)}</MonoCell>
                  <MonoCell>{e.event_category}</MonoCell>
                  <MonoCell>{e.event_type}</MonoCell>
                  <TableCell sx={{ py: 0.5, px: 1 }}>
                    <Chip
                      label={e.severity || 'INFO'}
                      size="small"
                      sx={{
                        bgcolor: SEV_COLOR[e.severity] ? `${SEV_COLOR[e.severity]}22` : 'rgba(255,255,255,0.06)',
                        color: SEV_COLOR[e.severity] || 'text.secondary',
                        fontSize: '0.68rem', height: 18, fontWeight: 700,
                      }}
                    />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary', py: 0.5, px: 1, maxWidth: 340 }}>
                    <Tooltip title={e.remark || ''} arrow placement="top">
                      <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 320 }}>
                        {e.remark || '—'}
                      </span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

// =============================================================================
// Sub-panel: Reconcile
// =============================================================================

const ReconcilePanel = ({ sessionId }) => {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mmmService.getAuditReconcile(sessionId);
      setResult(res);
    } catch (e) {
      // 409 = not clean — still parse the body
      if (e.response?.data) {
        setResult(e.response.data);
      } else {
        setError(e.message || 'Reconcile failed');
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Compares audit log totals against live session state.
        Checks realized P&L and per-strike open lot counts.
      </Typography>

      <Button
        variant="outlined"
        onClick={run}
        disabled={loading}
        startIcon={loading ? <CircularProgress size={14} /> : null}
        sx={{ mb: 2 }}
      >
        Run Reconciliation
      </Button>

      {error && <Alert severity="error">{error}</Alert>}

      {result && (
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            {result.is_clean ? (
              <CheckCircleIcon sx={{ color: '#4caf50' }} />
            ) : (
              <ErrorIcon sx={{ color: '#f44336' }} />
            )}
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, color: result.is_clean ? '#4caf50' : '#f44336' }}
            >
              {result.is_clean ? 'CLEAN — Audit matches session state' : 'MISMATCH — Discrepancy detected'}
            </Typography>
          </Box>

          <Grid container spacing={1.5} sx={{ mb: 2 }}>
            {[
              { label: 'P&L OK', value: result.pnl_ok ? 'Yes' : 'No', color: result.pnl_ok ? '#4caf50' : '#f44336' },
              { label: 'Audit P&L', value: `$${(result.pnl_audit || 0).toFixed(6)}`, color: '#2196f3' },
              { label: 'Session P&L', value: `$${(result.pnl_session || 0).toFixed(6)}`, color: '#2196f3' },
              { label: 'P&L Delta', value: `$${(result.pnl_delta || 0).toFixed(6)}`, color: Math.abs(result.pnl_delta) > 0.005 ? '#f44336' : '#4caf50' },
              { label: 'Trade Count', value: result.trade_count ?? '—', color: 'text.primary' },
              { label: 'Tolerance', value: `$${(result.pnl_tolerance || 0.005).toFixed(3)}`, color: 'text.secondary' },
            ].map((k) => (
              <Grid item xs={6} sm={4} md={2} key={k.label}>
                <Paper sx={{ p: 1.5, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', display: 'block' }}>
                    {k.label}
                  </Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', fontWeight: 600, color: k.color || 'text.primary' }}>
                    {k.value}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>

          {result.position_discrepancies && result.position_discrepancies.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 700, color: '#f44336', mb: 1, display: 'block' }}>
                Position Discrepancies
              </Typography>
              <TableContainer component={Paper} sx={{ bgcolor: 'rgba(244,67,54,0.05)', borderRadius: 1 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <HeaderCell>Side</HeaderCell>
                      <HeaderCell>Strike</HeaderCell>
                      <HeaderCell>Audit Lots</HeaderCell>
                      <HeaderCell>Session Lots</HeaderCell>
                      <HeaderCell>Delta</HeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.position_discrepancies.map((d, i) => (
                      <TableRow key={i}>
                        <MonoCell>{d.side}</MonoCell>
                        <MonoCell>{d.strike}</MonoCell>
                        <MonoCell>{d.audit_open_qty}</MonoCell>
                        <MonoCell>{d.session_lots}</MonoCell>
                        <MonoCell color="#f44336">{d.delta > 0 ? `+${d.delta}` : d.delta}</MonoCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {result.position_discrepancies && result.position_discrepancies.length === 0 && (
            <Alert severity="success" sx={{ mt: 1 }}>All strike lots match between audit and live session</Alert>
          )}
        </Box>
      )}
    </Box>
  );
};

// =============================================================================
// Auto-Reconcile Banner
// =============================================================================

const ReconcileBanner = ({ sessionId }) => {
  const [result, setResult] = useState(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    mmmService.getAuditReconcile(sessionId)
      .then((res) => { if (!cancelled) { setResult(res); setChecked(true); } })
      .catch((e) => {
        if (!cancelled) {
          const body = e?.response?.data;
          if (body) { setResult(body); }
          setChecked(true);
        }
      });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (!checked || !result) return null;
  if (result.is_clean) return null;  // silent on clean

  return (
    <Alert
      severity="warning"
      icon={<WarningAmberIcon fontSize="small" />}
      sx={{ mb: 1.5, fontSize: '0.78rem' }}
      action={
        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
          P&L delta: ${(result.pnl_delta || 0).toFixed(6)}
          {result.position_discrepancies?.length > 0 && ` | ${result.position_discrepancies.length} position mismatch(es)`}
        </Typography>
      }
    >
      Audit mismatch detected — open the Reconcile tab for details
    </Alert>
  );
};

// =============================================================================
// Main Panel
// =============================================================================

const MMMTradeAuditPanel = ({ sessionId }) => {
  const [tab, setTab] = useState(0);

  if (!sessionId) return null;

  return (
    <Box>
      {/* Auto-reconcile banner — silent on clean, visible on mismatch */}
      <ReconcileBanner sessionId={sessionId} />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: 1 }}>
          Trade Audit
        </Typography>
        <Chip label="Write-Once" size="small" sx={{ fontSize: '0.62rem', height: 16, bgcolor: 'rgba(33,150,243,0.15)', color: '#2196f3' }} />
      </Box>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider', minHeight: 32, '& .MuiTab-root': { minHeight: 32, fontSize: '0.78rem', py: 0.5 } }}
      >
        <Tab label="Fills" />
        <Tab label="Strike Summary" />
        <Tab label="P&L Attribution" />
        <Tab label="Events" />
        <Tab label="Reconcile" />
      </Tabs>

      {tab === 0 && <TradeLog sessionId={sessionId} />}
      {tab === 1 && <StrikeSummary sessionId={sessionId} />}
      {tab === 2 && <PnLAttribution sessionId={sessionId} />}
      {tab === 3 && <EventsLog sessionId={sessionId} />}
      {tab === 4 && <ReconcilePanel sessionId={sessionId} />}
    </Box>
  );
};

export default MMMTradeAuditPanel;
