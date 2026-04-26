/**
 * MMMWhipsawCompareTab — Phase 4 comparison dashboard.
 *
 * Shows legacy vs smart whipsaw engine decisions side-by-side.
 * Data comes from session state (_smart_ws_shadow_last, _smart_ws_last_decision)
 * and the /api/mmm/whipsaw/metrics/<session_id> endpoint.
 *
 * Zero impact on existing tabs — lives only on the Whipsaw tab.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Chip,
  Paper,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  CircularProgress,
  Button,
} from '@mui/material';
import {
  CheckCircle as OKIcon,
  Warning as WarnIcon,
  Error as AlertIcon,
  CompareArrows as CompareIcon,
} from '@mui/icons-material';

const MODE_COLOR = {
  NORMAL:    '#4caf50',
  CAUTION:   '#ff9800',
  RESTRICT:  '#ff9800',
  COOLDOWN:  '#f44336',
  DEFENSIVE: '#ff9800',
  OBSERVE:   '#ff5722',
  LOCKDOWN:  '#f44336',
};

function ModeChip({ mode, label }) {
  const color = MODE_COLOR[mode] || '#9e9e9e';
  return (
    <Chip
      label={label || mode || '—'}
      size="small"
      sx={{
        fontFamily: 'monospace',
        fontWeight: 600,
        fontSize: '0.75rem',
        bgcolor: `${color}22`,
        color,
        border: `1px solid ${color}55`,
      }}
    />
  );
}

function MetricRow({ label, legacy, smart, highlight }) {
  const differ = legacy !== smart && legacy != null && smart != null;
  return (
    <TableRow
      sx={{
        bgcolor: differ && highlight ? 'rgba(255,152,0,0.08)' : 'transparent',
      }}
    >
      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'text.secondary', py: 0.8 }}>
        {label}
      </TableCell>
      <TableCell align="center" sx={{ py: 0.8 }}>{legacy ?? '—'}</TableCell>
      <TableCell align="center" sx={{ py: 0.8 }}>{smart ?? '—'}</TableCell>
    </TableRow>
  );
}

export default function MMMWhipsawCompareTab({ session, heartbeat }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sessionId = session?.session_id;
  const wsEngine = session?.params?.whipsaw_engine || 'LEGACY';
  const shadowEnabled = session?.params?.whipsaw_engine_shadow || false;

  const fetchMetrics = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/mmm/whipsaw/metrics/${sessionId}`);
      const data = await res.json();
      if (data.success) {
        setMetrics(data);
      } else {
        setError(data.error || 'Failed to load metrics');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Live state from session (no extra fetch needed)
  const legacyScore = session?._whipsaw_score ?? 0;
  const legacyMode  = session?._whipsaw_state  || 'NORMAL';
  const smartScore  = session?._smart_ws_score;
  const smartMode   = session?._smart_ws_mode;
  const smartTokens = session?._smart_ws_tokens;
  // Smart-primary stores shadow data in _ws_legacy_shadow_last; Legacy-primary uses _smart_ws_shadow_last.
  const shadowLast  = session?._ws_legacy_shadow_last || session?._smart_ws_shadow_last;
  const smartDec    = session?._smart_ws_last_decision;

  const seriesLength = session?._smart_ws_series?.length ?? 0;

  // Backend select_engine() uses whipsaw_engine param only — smartEnabled is not a gate.
  const isSmartActive = wsEngine === 'SMART';
  const isShadow      = !isSmartActive && shadowEnabled;

  return (
    <Box sx={{ p: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <CompareIcon sx={{ color: '#42a5f5' }} />
        <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
          Whipsaw Engine Comparison
        </Typography>
        <Chip
          label={isSmartActive ? 'SMART ACTIVE' : isShadow ? 'SMART SHADOW' : 'LEGACY ONLY'}
          size="small"
          sx={{
            fontFamily: 'monospace',
            fontWeight: 700,
            bgcolor: isSmartActive ? 'rgba(76,175,80,0.15)' : isShadow ? 'rgba(255,152,0,0.15)' : 'rgba(255,255,255,0.06)',
            color: isSmartActive ? '#4caf50' : isShadow ? '#ff9800' : '#9e9e9e',
          }}
        />
        <Chip
          label={`${seriesLength} beats logged`}
          size="small"
          variant="outlined"
          sx={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'text.secondary' }}
        />
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" variant="outlined" onClick={fetchMetrics} disabled={loading}>
          {loading ? <CircularProgress size={14} /> : 'Refresh'}
        </Button>
      </Box>

      {!isShadow && !isSmartActive && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: 'rgba(255,255,255,0.1)' }}>
          <Typography variant="body2" color="text.secondary">
            Smart engine is not running in shadow mode. To enable: set{' '}
            <code>whipsaw_engine_shadow=True</code> or{' '}
            <code>whipsaw_engine=SMART</code> in Settings → Safety.
          </Typography>
        </Paper>
      )}

      {/* Live side-by-side state */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {/* Legacy */}
        <Grid item xs={12} sm={6}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', color: '#9e9e9e', mb: 1 }}>
              LEGACY Engine (primary)
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <ModeChip mode={legacyMode} />
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                Score: <strong>{legacyScore}</strong>
              </Typography>
            </Box>
          </Paper>
        </Grid>

        {/* Smart */}
        <Grid item xs={12} sm={6}>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              borderRadius: 2,
              borderColor: isSmartActive ? 'rgba(76,175,80,0.3)' : isShadow ? 'rgba(255,152,0,0.3)' : 'divider',
            }}
          >
            <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', color: '#9e9e9e', mb: 1 }}>
              SMART Engine ({isSmartActive ? 'active' : isShadow ? 'shadow' : 'inactive'})
            </Typography>
            {smartMode != null ? (
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <ModeChip mode={smartMode} />
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  Score: <strong>{smartScore?.toFixed(3) ?? '—'}</strong>
                </Typography>
                {smartTokens != null && (
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                    Tokens: {smartTokens.toFixed(1)}
                  </Typography>
                )}
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">No data yet — waiting for first shadow run.</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Shadow disagree alert */}
      {shadowLast?.disagree && (
        <Paper
          variant="outlined"
          sx={{ p: 1.5, mb: 2, borderColor: '#ff980055', bgcolor: 'rgba(255,152,0,0.06)', borderRadius: 2 }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WarnIcon sx={{ fontSize: 18, color: '#ff9800' }} />
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              Engines disagree on latest beat: Legacy={shadowLast.primary_mode} / Smart={shadowLast.shadow_mode}
              {shadowLast.shadow_block !== shadowLast.primary_block && ' (block differs)'}
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Aggregate metrics table */}
      {metrics && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontFamily: 'monospace', color: 'text.secondary' }}>
            Replay Summary ({metrics.summary?.total_beats ?? 0} beats)
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'rgba(255,255,255,0.04)' }}>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 700 }}>Metric</TableCell>
                  <TableCell align="center" sx={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 700 }}>LEGACY</TableCell>
                  <TableCell align="center" sx={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 700 }}>SMART</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <MetricRow
                  label="Blocks fired"
                  legacy={metrics.summary?.legacy_block_count ?? '—'}
                  smart={metrics.summary?.smart_block_count ?? '—'}
                  highlight
                />
                <MetricRow
                  label="Only this engine blocked"
                  legacy={metrics.summary?.legacy_only_block ?? '—'}
                  smart={metrics.summary?.smart_only_block ?? '—'}
                  highlight
                />
                <TableRow>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'text.secondary', py: 0.8 }}>
                    Disagreement rate
                  </TableCell>
                  <TableCell colSpan={2} align="center" sx={{ py: 0.8, fontFamily: 'monospace' }}>
                    {metrics.summary?.disagree_pct ?? '—'}%
                    {' '}({metrics.summary?.disagree_count ?? 0} / {metrics.summary?.total_beats ?? 0} beats)
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* Smart detector breakdown from last decision */}
      {smartDec?.scores && (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1, fontFamily: 'monospace', color: 'text.secondary' }}>
            Smart Detector Scores (last beat)
          </Typography>
          <Grid container spacing={1}>
            {Object.entries(smartDec.scores).map(([key, val]) => (
              <Grid item key={key} xs={6} sm={4} md={3}>
                <Paper variant="outlined" sx={{ p: 1, borderRadius: 1.5, textAlign: 'center' }}>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', display: 'block' }}>
                    {key}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: 'monospace',
                      fontWeight: 700,
                      color: val > 0.6 ? '#f44336' : val > 0.3 ? '#ff9800' : '#4caf50',
                    }}
                  >
                    {typeof val === 'number' ? val.toFixed(3) : String(val)}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {error && (
        <Typography variant="body2" color="error" sx={{ mt: 1 }}>
          Error loading metrics: {error}
        </Typography>
      )}
    </Box>
  );
}
