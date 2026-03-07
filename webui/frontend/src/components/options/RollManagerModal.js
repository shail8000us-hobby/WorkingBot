/**
 * RollManagerModal  (Feature 9 — Roll Management Tool)
 * ======================================================
 * Allows rolling a short option position to a further expiry.
 *
 * Flow:
 *   1. User clicks "Roll" on a position row (DTE <= 14 highlights it in amber)
 *   2. Modal opens — fetches real available expiries from exchange
 *   3. User picks target expiry from chips, fetches live quotes
 *   4. User confirms -> POST /api/options/roll/execute
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Box, Typography, Button, Chip,
  CircularProgress, Alert, Divider,
} from '@mui/material';
import SyncAltIcon from '@mui/icons-material/SyncAlt';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

/** Extract expiry part from symbol e.g. "C-BTC-72000-130326" -> "130326" */
function extractExpiry(symbol) {
  const parts = symbol?.split('-') || [];
  return parts.length >= 4 ? parts[parts.length - 1] : '';
}

function fmtPrice(v) {
  if (v == null) return '\u2014';
  return `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function RollManagerModal({ open, onClose, position, onRollComplete }) {
  const [expiries, setExpiries] = useState([]);
  const [expiriesLoading, setExpiriesLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [quotes, setQuotes] = useState(null);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const symbol = position?.product_symbol || '';
  const currentExpiry = extractExpiry(symbol);
  const posSize = Math.abs(parseInt(position?.size || 1));

  // Fetch available expiries when modal opens
  useEffect(() => {
    if (!open || !currentExpiry || currentExpiry.length !== 6) return;

    let cancelled = false;
    setExpiriesLoading(true);
    setExpiries([]);
    setSelectedIdx(-1);
    setQuotes(null);
    setError(null);
    setSuccessMsg(null);

    fetch(`/api/options/roll/expiries?current_expiry=${currentExpiry}`)
      .then(r => r.json())
      .then(data => {
        if (cancelled) return;
        if (data.success && data.expiries?.length) {
          setExpiries(data.expiries);
          setSelectedIdx(0);
        } else {
          setError(data.error || 'No future expiry dates available');
        }
      })
      .catch(e => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setExpiriesLoading(false); });

    return () => { cancelled = true; };
  }, [open, currentExpiry]);

  // Fetch quotes when selection changes
  const fetchQuotes = useCallback(async () => {
    if (!symbol || selectedIdx < 0 || selectedIdx >= expiries.length) return;
    const targetDdmmyy = expiries[selectedIdx].ddmmyy;
    if (!targetDdmmyy) return;

    setQuotesLoading(true);
    setError(null);
    setQuotes(null);
    try {
      const res = await fetch(
        `/api/options/roll/quotes?symbol=${encodeURIComponent(symbol)}&target_expiry=${targetDdmmyy}&size=${posSize}`
      );
      let data;
      try {
        data = await res.json();
      } catch (_) {
        throw new Error(`Server error (HTTP ${res.status})`);
      }
      if (data.success) {
        setQuotes(data);
      } else {
        // offline:true  → service-worker offline fallback
        // otherwise     → real backend error
        const msg = data.offline
          ? 'Exchange unavailable — check your connection and try again'
          : (data.error || 'Failed to fetch quotes');
        setError(msg);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setQuotesLoading(false);
    }
  }, [symbol, selectedIdx, expiries, posSize]);

  useEffect(() => {
    if (open && selectedIdx >= 0) {
      fetchQuotes();
    }
  }, [open, selectedIdx, fetchQuotes]);

  const handleExecute = async () => {
    if (!symbol || selectedIdx < 0) return;
    const targetDdmmyy = expiries[selectedIdx].ddmmyy;
    setExecuting(true);
    setError(null);
    try {
      const res = await fetch('/api/options/roll/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          target_expiry: targetDdmmyy,
          size: posSize,
          order_preference: 'smart',
        }),
      });
      let data;
      try {
        data = await res.json();
      } catch (_) {
        throw new Error(`Server error (HTTP ${res.status})`);
      }
      if (data.success) {
        setSuccessMsg(
          `Rolled ${posSize}x ${symbol} \u2192 ${data.opened?.symbol || ''}. ` +
          `Close fill: ${fmtPrice(data.closed?.fill_price)}, Open fill: ${fmtPrice(data.opened?.fill_price)}`
        );
        onRollComplete?.();
      } else {
        setError(data.error || 'Roll execution failed');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setExecuting(false);
    }
  };

  if (!position) return null;

  const netDebit = quotes?.net_debit;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{ sx: { bgcolor: '#0f172a', border: '1px solid rgba(99,102,241,0.3)' } }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <SyncAltIcon sx={{ color: '#818cf8' }} />
        <Typography variant="h6" sx={{ color: '#e2e8f0' }}>Roll Position</Typography>
        <Chip
          label={symbol}
          size="small"
          sx={{ ml: 1, bgcolor: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: '0.7rem' }}
        />
      </DialogTitle>

      <DialogContent sx={{ pt: 1 }}>
        {/* Current position summary */}
        <Box sx={{ p: 1.5, bgcolor: 'rgba(255,255,255,0.04)', borderRadius: 1, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="caption" color="text.secondary">Current position</Typography>
            <Typography variant="caption" sx={{ color: '#e2e8f0' }}>
              {posSize} lot{posSize > 1 ? 's' : ''} short &mdash; exp {currentExpiry}
            </Typography>
          </Box>
          {position.mark_price != null && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">Mark price</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0' }}>{fmtPrice(position.mark_price)}</Typography>
            </Box>
          )}
        </Box>

        {/* Target expiry selector — real exchange expiries */}
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          Roll to expiry:
        </Typography>

        {expiriesLoading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" color="text.secondary">Loading available expiries...</Typography>
          </Box>
        ) : expiries.length > 0 ? (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5 }}>
            {expiries.map((exp, i) => (
              <Chip
                key={exp.ddmmyy}
                label={exp.label}
                size="small"
                clickable
                onClick={() => { setSelectedIdx(i); setQuotes(null); }}
                sx={{
                  fontSize: '0.72rem',
                  bgcolor: selectedIdx === i ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                  color: selectedIdx === i ? '#818cf8' : '#94a3b8',
                  border: selectedIdx === i ? '1px solid rgba(99,102,241,0.5)' : '1px solid transparent',
                  '&:hover': { bgcolor: 'rgba(99,102,241,0.2)' },
                }}
              />
            ))}
          </Box>
        ) : !error ? (
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>
            No future expiry dates found.
          </Typography>
        ) : null}

        {/* Quotes */}
        <Box sx={{ mt: 1 }}>
          {quotesLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="caption" color="text.secondary">Fetching live quotes...</Typography>
            </Box>
          ) : quotes ? (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {/* Close leg */}
                <Box sx={{ flex: 1, p: 1, bgcolor: 'rgba(239,68,68,0.08)', borderRadius: 1, border: '1px solid rgba(239,68,68,0.2)' }}>
                  <Typography variant="caption" sx={{ color: '#ef4444', fontWeight: 600 }}>CLOSE</Typography>
                  <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', fontSize: '0.65rem' }}>{quotes.source?.symbol}</Typography>
                  <Typography variant="body2" sx={{ color: '#e2e8f0', mt: 0.25 }}>
                    Ask: {fmtPrice(quotes.source?.ask)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Bid: {fmtPrice(quotes.source?.bid)}
                  </Typography>
                  {quotes.source?.ask == null && quotes.source?.mid != null && (
                    <Typography variant="caption" sx={{ color: '#f59e0b', display: 'block', fontSize: '0.6rem' }}>
                      Mid: {fmtPrice(quotes.source?.mid)} (mark)
                    </Typography>
                  )}
                </Box>

                <ArrowForwardIcon sx={{ color: '#64748b', fontSize: '1rem' }} />

                {/* Open leg */}
                <Box sx={{ flex: 1, p: 1, bgcolor: 'rgba(16,185,129,0.08)', borderRadius: 1, border: '1px solid rgba(16,185,129,0.2)' }}>
                  <Typography variant="caption" sx={{ color: '#10b981', fontWeight: 600 }}>OPEN</Typography>
                  <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', fontSize: '0.65rem' }}>{quotes.target?.symbol}</Typography>
                  <Typography variant="body2" sx={{ color: '#e2e8f0', mt: 0.25 }}>
                    Bid: {fmtPrice(quotes.target?.bid)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Ask: {fmtPrice(quotes.target?.ask)}
                  </Typography>
                  {quotes.target?.bid == null && quotes.target?.mid != null && (
                    <Typography variant="caption" sx={{ color: '#f59e0b', display: 'block', fontSize: '0.6rem' }}>
                      Mid: {fmtPrice(quotes.target?.mid)} (mark)
                    </Typography>
                  )}
                </Box>
              </Box>

              <Divider sx={{ my: 1.5, borderColor: 'rgba(255,255,255,0.06)' }} />

              {/* Net cost */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2" sx={{ color: '#94a3b8' }}>Net roll {netDebit >= 0 ? 'debit' : 'credit'}</Typography>
                <Typography
                  variant="body1"
                  fontWeight="bold"
                  sx={{ color: netDebit == null ? '#64748b' : netDebit >= 0 ? '#ef4444' : '#10b981' }}
                >
                  {netDebit == null ? '\u2014' : `${netDebit >= 0 ? '-' : '+'}$${Math.abs(netDebit).toFixed(2)}`}
                </Typography>
              </Box>

              <Button size="small" onClick={fetchQuotes} sx={{ mt: 0.5, color: '#64748b', fontSize: '0.7rem' }}>
                &#8635; Refresh quotes
              </Button>
            </>
          ) : selectedIdx >= 0 && !quotesLoading && !error ? (
            <Typography variant="caption" color="text.secondary">
              No quote data available for this expiry.
            </Typography>
          ) : null}
        </Box>

        {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
        {successMsg && <Alert severity="success" sx={{ mt: 1.5 }}>{successMsg}</Alert>}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} sx={{ color: '#64748b' }}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!quotes || executing || !!successMsg}
          onClick={handleExecute}
          sx={{ bgcolor: '#6366f1', '&:hover': { bgcolor: '#4f46e5' }, '&:disabled': { bgcolor: 'rgba(99,102,241,0.3)' } }}
          startIcon={executing ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <SyncAltIcon />}
        >
          {executing ? 'Rolling\u2026' : `Execute Roll (${posSize} lot${posSize > 1 ? 's' : ''})`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
