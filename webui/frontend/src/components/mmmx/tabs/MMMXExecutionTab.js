import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Box, Paper, Typography, Chip, Alert,
  FormControl, InputLabel, Select, MenuItem, TextField,
} from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { ORDER_EVENT_META } from '../utils/mmmxConstants';

export default function MMMXExecutionTab() {
  const { execution, isConnected, session, risk } = useMMMX();
  const [stageFilter, setStageFilter] = useState('ALL');
  const [sideFilter, setSideFilter] = useState('ALL');
  const [symbolFilter, setSymbolFilter] = useState('');
  const [changeLog, setChangeLog] = useState([]);
  const prevBeatRef = useRef(null);

  const timeline = execution?.timeline ?? [];

  useEffect(() => {
    if (!risk?.last_beat_at) return;
    const snapshot = {
      beat: session?.beat_number ?? session?.beat_count ?? 0,
      pnl: Number(risk?.portfolio_pnl ?? session?.portfolio_pnl ?? 0),
      delta: Number(risk?.portfolio_delta ?? 0),
      tranches: Number(session?.tranches_deployed ?? 0),
      ceReserve: Number(session?.ce_reserve_remaining ?? 0),
      peReserve: Number(session?.pe_reserve_remaining ?? 0),
      at: risk.last_beat_at,
    };
    const prev = prevBeatRef.current;
    if (prev && prev.at !== snapshot.at) {
      setChangeLog((old) => ([{
        beat: snapshot.beat, at: snapshot.at,
        pnlDelta: snapshot.pnl - prev.pnl,
        deltaShift: snapshot.delta - prev.delta,
        trancheDelta: snapshot.tranches - prev.tranches,
        ceReserveDelta: snapshot.ceReserve - prev.ceReserve,
        peReserveDelta: snapshot.peReserve - prev.peReserve,
      }, ...old]).slice(0, 40));
    }
    prevBeatRef.current = snapshot;
  }, [risk?.last_beat_at, risk?.portfolio_pnl, risk?.portfolio_delta, session?.beat_number, session?.beat_count, session?.tranches_deployed, session?.ce_reserve_remaining, session?.pe_reserve_remaining, session?.portfolio_pnl]);

  const filtered = useMemo(() => {
    const symbolQ = (symbolFilter || '').trim().toUpperCase();
    return timeline.filter((e) => {
      if (stageFilter !== 'ALL' && e?.event_name !== stageFilter) return false;
      if (sideFilter !== 'ALL' && String(e?.side || '').toUpperCase() !== sideFilter) return false;
      if (symbolQ && !String(e?.symbol || '').toUpperCase().includes(symbolQ)) return false;
      return true;
    });
  }, [timeline, stageFilter, sideFilter, symbolFilter]);

  return (
    <Box>
      {!isConnected && (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          Live updates paused — websocket disconnected.
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1.5, borderRadius: 1.2 }}>
        <Typography variant="subtitle2" sx={{ mb: 0.8 }}>Change Since Last Beat</Typography>
        {!changeLog.length ? (
          <Typography variant="caption" color="text.secondary">
            Waiting for consecutive heartbeat snapshots to compute diffs.
          </Typography>
        ) : (
          <Box sx={{ maxHeight: 140, overflow: 'auto' }}>
            {changeLog.slice(0, 8).map((row, idx) => (
              <Typography key={`${row.at}-${idx}`} variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
                beat#{row.beat} · Δpnl={row.pnlDelta >= 0 ? '+' : ''}{row.pnlDelta.toFixed(2)} ·
                Δdelta={row.deltaShift >= 0 ? '+' : ''}{row.deltaShift.toFixed(3)} ·
                Δtr={row.trancheDelta >= 0 ? '+' : ''}{row.trancheDelta} ·
                ΔCE={row.ceReserveDelta >= 0 ? '+' : ''}{row.ceReserveDelta} ·
                ΔPE={row.peReserveDelta >= 0 ? '+' : ''}{row.peReserveDelta}
              </Typography>
            ))}
          </Box>
        )}
      </Paper>

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1.5 }}>
        <FormControl size="small" sx={{ minWidth: 170 }}>
          <InputLabel>Stage</InputLabel>
          <Select value={stageFilter} label="Stage" onChange={(e) => setStageFilter(e.target.value)}>
            <MenuItem value="ALL">All Stages</MenuItem>
            {Object.keys(ORDER_EVENT_META).map((k) => (
              <MenuItem key={k} value={k}>{ORDER_EVENT_META[k].label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Side</InputLabel>
          <Select value={sideFilter} label="Side" onChange={(e) => setSideFilter(e.target.value)}>
            <MenuItem value="ALL">All</MenuItem>
            <MenuItem value="BUY">BUY</MenuItem>
            <MenuItem value="SELL">SELL</MenuItem>
          </Select>
        </FormControl>
        <TextField size="small" label="Symbol contains" value={symbolFilter}
          onChange={(e) => setSymbolFilter(e.target.value)} sx={{ minWidth: 220 }} />
        <Chip size="small" variant="outlined"
          label={`Showing ${filtered.length}/${timeline.length}`} sx={{ ml: 'auto' }} />
      </Box>

      {!timeline.length ? (
        <Alert severity="info">
          No order lifecycle events yet. New orders will appear here as intent/ack/partial/retry/filled/failed transitions.
        </Alert>
      ) : filtered.length === 0 ? (
        <Alert severity="info">No lifecycle events match the selected filters.</Alert>
      ) : (
        <Box sx={{ maxHeight: 520, overflow: 'auto' }}>
          {filtered.map((e, i) => {
            const meta = ORDER_EVENT_META[e?.event_name] || { label: e?.event_name || 'Event', color: 'default' };
            const ts = e?.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—';
            const laneKey = e?.origin_client_order_id || e?.client_order_id || e?.order_id || `${e?.symbol || 'UNKNOWN'}-${i}`;
            return (
              <Paper key={`${laneKey}-${i}`} variant="outlined" sx={{ p: 1.2, mb: 0.8, borderRadius: 1.2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap' }}>
                  <Chip label={meta.label} size="small" color={meta.color} />
                  <Chip size="small" variant="outlined"
                    label={`${String(e?.side || 'NA').toUpperCase()} ${e?.symbol || 'UNKNOWN'}`} />
                  {['mmmx_order_intent', 'mmmx_order_ack', 'mmmx_order_partial', 'mmmx_order_retry'].includes(e?.event_name) && (
                    <Chip size="small" color="warning" label="UNCERTAIN" />
                  )}
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    req={e?.requested_size ?? 0} fill={e?.filled_size ?? '—'} residual={e?.residual_size ?? '—'}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>{ts}</Typography>
                </Box>
                <Box sx={{ mt: 0.6, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                    mode={e?.mode || '—'} · attempt={e?.attempt ?? '—'} · action={e?.action || '—'}
                  </Typography>
                  {e?.avg_price != null && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      avg=${Number(e.avg_price).toFixed(2)}
                    </Typography>
                  )}
                  {e?.price != null && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      px=${Number(e.price).toFixed(2)}
                    </Typography>
                  )}
                </Box>
                <Typography variant="caption" sx={{ display: 'block', mt: 0.4, color: 'text.secondary' }}>
                  order_id={e?.order_id || '—'} · coid={e?.client_order_id || '—'} · tranche={e?.tranche_id || '—'}
                </Typography>
                {e?.reason && (
                  <Typography variant="caption" sx={{ display: 'block', mt: 0.4, color: 'warning.main' }}>
                    {e?.reason_code || 'reason'}: {e.reason}
                  </Typography>
                )}
              </Paper>
            );
          })}
        </Box>
      )}
    </Box>
  );
}
