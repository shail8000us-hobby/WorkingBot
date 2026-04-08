/**
 * MMMXTradeAuditPanel — paginated trade audit log from the backend audit_log table.
 * Endpoint: GET /api/mmmx/session/:id/audit?limit=N
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Chip, Paper, Button, CircularProgress, Alert,
  FormControl, InputLabel, Select, MenuItem, TextField,
} from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';

const CATEGORY_COLORS = {
  TRADE:    'success',
  TRIGGER:  'info',
  SAFETY:   'error',
  HEDGE:    'warning',
  SYSTEM:   'default',
};

export default function MMMXTradeAuditPanel() {
  const { session } = useMMMX();
  const [entries, setEntries]     = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [limit, setLimit]         = useState(50);
  const [catFilter, setCatFilter] = useState('ALL');
  const [search, setSearch]       = useState('');

  const load = useCallback(async () => {
    if (!session?.session_id) return;
    setLoading(true); setError('');
    try {
      const res = await mmmxService.getAuditLog(session.session_id, limit);
      if (res.ok) setEntries(res.data ?? []);
      else setError(res.error || 'Failed to load audit log');
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [session?.session_id, limit]);

  useEffect(() => { load(); }, [load]);

  const filtered = entries.filter(e => {
    if (catFilter !== 'ALL' && e?.category !== catFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      const hay = `${e?.action || ''} ${e?.symbol || ''} ${e?.message || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (!session) return <Typography color="text.secondary">No session loaded.</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Category</InputLabel>
          <Select value={catFilter} label="Category" onChange={e => setCatFilter(e.target.value)}>
            <MenuItem value="ALL">All</MenuItem>
            {Object.keys(CATEGORY_COLORS).map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
          </Select>
        </FormControl>
        <TextField size="small" label="Search" value={search} onChange={e => setSearch(e.target.value)}
          sx={{ minWidth: 200 }} />
        <FormControl size="small" sx={{ minWidth: 90 }}>
          <InputLabel>Limit</InputLabel>
          <Select value={limit} label="Limit" onChange={e => setLimit(Number(e.target.value))}>
            {[25, 50, 100, 200].map(v => <MenuItem key={v} value={v}>{v}</MenuItem>)}
          </Select>
        </FormControl>
        <Button size="small" variant="outlined" onClick={load} disabled={loading}
          startIcon={loading ? <CircularProgress size={12} /> : null}>
          Refresh
        </Button>
        <Chip size="small" variant="outlined" label={`${filtered.length}/${entries.length}`} sx={{ ml: 'auto' }} />
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {!entries.length && !loading && !error && (
        <Alert severity="info">No audit log entries found for this session.</Alert>
      )}

      <Box sx={{ maxHeight: 520, overflow: 'auto' }}>
        {filtered.map((e, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1, mb: 0.6, borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap', mb: 0.3 }}>
              {e.category && (
                <Chip size="small" label={e.category} color={CATEGORY_COLORS[e.category] || 'default'} />
              )}
              {e.action && (
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.8rem' }}>
                  {e.action}
                </Typography>
              )}
              {e.symbol && (
                <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                  {e.symbol}
                </Typography>
              )}
              {e.lots != null && (
                <Chip size="small" variant="outlined" label={`${e.lots} lots`} />
              )}
              {e.price != null && (
                <Typography variant="caption" color="text.secondary">${Number(e.price).toFixed(2)}</Typography>
              )}
              <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto', fontFamily: 'monospace' }}>
                {e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—'}
              </Typography>
            </Box>
            {e.message && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {e.message}
              </Typography>
            )}
          </Paper>
        ))}
      </Box>
    </Box>
  );
}
