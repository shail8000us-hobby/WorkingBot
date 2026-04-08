import React from 'react';
import { Box, Paper, Chip, Button, LinearProgress } from '@mui/material';
import { scfg, INCIDENT_COLOR, INCIDENT_RANK } from './utils/mmmxConstants';
import { heartbeatAge, formatEta } from './utils/mmmxFormatters';

export default function MMMXTopCommandStrip({
  session,
  isConnected,
  integrityState,
  confidence,
  health,
  incidents,
  killProgress,
  criticalMode,
  onToggleCritical,
  onKillSession,
  onKillGlobal,
}) {
  const hbAge = heartbeatAge(session?._last_beat_at || session?.last_beat_at);
  const maxLevel = incidents[0]?.level || 'L0';
  const killAgeSec = killProgress?.timestamp
    ? Math.max(0, Math.floor((Date.now() - new Date(killProgress.timestamp).getTime()) / 1000))
    : null;
  const killVisible = !!killProgress && (killAgeSec == null || killAgeSec <= 180);
  const killProcessed = Number(killProgress?.details?.processed_count || 0);
  const killRequested = Number(killProgress?.details?.requested_count || 0);
  const killPct = killRequested > 0
    ? Math.max(0, Math.min(100, Math.round((killProcessed / killRequested) * 100)))
    : (killProgress?.stage === 'completed' ? 100 : 0);

  return (
    <Paper
      square
      variant="outlined"
      sx={{
        borderLeft: 0,
        borderRight: 0,
        borderTop: 0,
        px: 1.5,
        py: 1,
        bgcolor: criticalMode ? 'rgba(244,67,54,0.08)' : 'background.paper',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap' }}>
        <Chip
          size="small"
          label={session?.status || 'No Session'}
          sx={{
            fontWeight: 700,
            bgcolor: scfg(session?.status, session?.reconcile_required).bg,
            color: scfg(session?.status, session?.reconcile_required).color,
          }}
        />

        <Chip
          size="small"
          color={isConnected ? 'success' : 'error'}
          label={isConnected ? 'WS LIVE' : 'WS LOST'}
        />

        <Chip
          size="small"
          color={integrityState === 'SYNCED' ? 'success' : integrityState === 'DRIFT' ? 'warning' : 'error'}
          label={`Integrity ${integrityState}`}
        />

        <Chip
          size="small"
          color={health.state === 'NORMAL' ? 'success' : health.state === 'DEGRADED' ? 'warning' : 'error'}
          label={`Health ${health.score} · ${health.state}`}
        />

        <Chip
          size="small"
          variant="outlined"
          label={`Confidence ${confidence}`}
        />

        {hbAge && (
          <Chip
            size="small"
            variant="outlined"
            label={`Beat ${hbAge.label}`}
            sx={{ color: hbAge.color, borderColor: `${hbAge.color}66` }}
          />
        )}

        <Chip
          size="small"
          color={INCIDENT_COLOR[maxLevel] || 'default'}
          label={`Incidents ${incidents.length} · ${maxLevel}`}
        />

        {killVisible && (
          <Chip
            size="small"
            color={killProgress?.status?.includes('fail') ? 'warning' : 'error'}
            variant={killProgress?.stage === 'completed' ? 'filled' : 'outlined'}
            label={`${killProgress.scope === 'global' ? 'GLOBAL_KILL' : 'SESSION_KILL'} · ${killProgress.stage}${killRequested > 0 ? ` ${killProcessed}/${killRequested}` : ''}`}
          />
        )}

        <Box sx={{ ml: 'auto', display: 'flex', gap: 0.8, flexWrap: 'wrap' }}>
          <Button
            size="small"
            variant={criticalMode ? 'contained' : 'outlined'}
            color={criticalMode ? 'error' : 'warning'}
            onClick={onToggleCritical}
          >
            {criticalMode ? 'Critical Mode ON' : 'Critical Mode'}
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            onClick={onKillSession}
            disabled={!session?.session_id}
          >
            Kill Session
          </Button>
          <Button
            size="small"
            variant="contained"
            color="error"
            onClick={onKillGlobal}
          >
            Global Kill
          </Button>
        </Box>
      </Box>

      {killVisible && killProgress?.stage !== 'completed' && (
        <Box sx={{ mt: 0.8 }}>
          <LinearProgress variant="determinate" value={killPct} color="error" sx={{ height: 5, borderRadius: 1 }} />
        </Box>
      )}
    </Paper>
  );
}
