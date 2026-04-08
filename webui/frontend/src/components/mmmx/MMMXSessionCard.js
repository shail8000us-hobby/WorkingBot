import React, { useState, useEffect } from 'react';
import {
  Card, CardContent, Box, Typography, Chip, LinearProgress, IconButton, Tooltip,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import BoltIcon from '@mui/icons-material/Bolt';
import CircleIcon from '@mui/icons-material/Circle';
import { scfg } from './utils/mmmxConstants';
import { fmt, pnlColor, computeDTE, sessionDisplayName, heartbeatAge, formatDdmmyy } from './utils/mmmxFormatters';

/**
 * DTE chip with urgency pulse animation.
 * DTE > 14: grey · DTE 7-14: amber · DTE 3-7: orange pulse · DTE < 3: red fast pulse
 */
function DteChip({ dteInfo }) {
  if (!dteInfo) return null;
  const pulse = dteInfo.dte <= 7 && dteInfo.dte > 0;
  return (
    <Typography
      variant="caption"
      sx={{
        display: 'block', mb: 0.5, fontWeight: 700, fontFamily: 'monospace',
        color: dteInfo.color, fontSize: '0.72rem',
        ...(pulse && {
          animation: dteInfo.dte <= 3
            ? 'mmmxPulseFast 0.8s ease-in-out infinite'
            : 'mmmxPulse 1.6s ease-in-out infinite',
        }),
        '@keyframes mmmxPulse':     { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
        '@keyframes mmmxPulseFast': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } },
      }}
    >
      ⏱ {dteInfo.label}
    </Typography>
  );
}

export default function MMMXSessionCard({
  s, selected, onSelect, onPause, onResume, onStop, onDeploy, onForceHB, controlSafety, allSessions,
}) {
  const cfg = scfg(s.status, s.reconcile_required);
  const pnl = s.portfolio_pnl ?? 0;
  const hardStop = s.hard_stop_usd ?? 0;
  const pnlPct = hardStop > 0 ? Math.min(100, (Math.abs(pnl) / hardStop) * 100) : 0;
  const safety = controlSafety || {};

  const dteInfo = computeDTE(s.expiry_date, s.expiry_ddmmyy || s.params?.target_expiry_ddmmyy);

  const [hbAge, setHbAge] = useState(() => heartbeatAge(s.last_beat_at));
  useEffect(() => {
    if (!['RUNNING', 'PAUSED'].includes(s.status)) { setHbAge(null); return; }
    setHbAge(heartbeatAge(s.last_beat_at));
    const t = setInterval(() => setHbAge(heartbeatAge(s.last_beat_at)), 15000);
    return () => clearInterval(t);
  }, [s.status, s.last_beat_at]);

  return (
    <Card
      variant="outlined"
      onClick={() => onSelect(s.session_id)}
      sx={{
        mb: 1, cursor: 'pointer',
        borderColor: selected ? cfg.color : `${cfg.color}44`,
        borderWidth: selected ? 2 : 1,
        backgroundColor: selected ? cfg.bg : 'transparent',
        transition: 'all 0.15s',
        '&:hover': { borderColor: cfg.color, boxShadow: `0 2px 8px ${cfg.color}22` },
      }}
    >
      <CardContent sx={{ pb: '8px !important', pt: 1.5, px: 1.5 }}>

        {/* Row 1: display name + status chip */}
        <Box sx={{ mb: 0.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.82rem', mb: 0.3, lineHeight: 1.2 }}>
            {sessionDisplayName(s, allSessions || [])}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
              <CircleIcon sx={{ fontSize: 9, color: cfg.color }} />
              <Chip label={cfg.label} size="small"
                sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 700, fontSize: '0.7rem', height: 20 }} />
            </Box>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.disabled', fontSize: '0.65rem' }}>
              {s.session_id?.slice(-8)}
            </Typography>
          </Box>
        </Box>

        {/* Row 2: DTE countdown */}
        <DteChip dteInfo={dteInfo} />
        {!dteInfo && s.status === 'DRAFT' && (
          <Typography variant="caption" sx={{ display: 'block', mb: 0.5, color: 'text.disabled', fontStyle: 'italic', fontSize: '0.68rem' }}>
            No expiry set — deploy Tranche 1 to activate
          </Typography>
        )}

        {/* Row 3: stats grid */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0.5, mb: 0.5 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.62rem' }}>Tranches</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.78rem' }}>{s.tranches_deployed ?? 0}/10</Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.62rem' }}>Premium</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.78rem', color: '#4caf50' }}>
              ${fmt(s.total_premium_collected, 0)}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.62rem' }}>P&amp;L</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.78rem', color: pnlColor(pnl) }}>
              ${fmt(pnl, 0)}
            </Typography>
          </Box>
        </Box>

        {/* Row 4: P&L bar */}
        {hardStop > 0 && (
          <Box sx={{ mb: 0.5 }}>
            <LinearProgress variant="determinate" value={pnlPct}
              color={pnlPct > 70 ? 'error' : pnlPct > 40 ? 'warning' : 'success'}
              sx={{ height: 3, borderRadius: 1 }} />
            {pnlPct > 5 && (
              <Typography variant="caption" sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>
                {pnlPct.toFixed(0)}% of hard stop
              </Typography>
            )}
          </Box>
        )}

        {/* Row 5: heartbeat age for live sessions */}
        {hbAge && (
          <Typography variant="caption" sx={{ display: 'block', fontSize: '0.65rem', color: hbAge.color, mb: 0.3 }}>
            Beat {hbAge.label}
          </Typography>
        )}

        {/* Row 6: quick controls */}
        <Box sx={{ display: 'flex', gap: 0.3, mt: 0.3 }} onClick={e => e.stopPropagation()}>
          {['DRAFT', 'GATES_PASSED', 'RUNNING'].includes(s.status) && (s.tranches_deployed ?? 0) === 0 && (
            <Tooltip title={safety.deploy_tranche1?.enabled !== false ? 'Deploy Tranche 1' : safety.deploy_tranche1?.reason || 'Deploy locked'}>
              <span>
                <IconButton size="small" color="primary"
                  disabled={safety.deploy_tranche1?.enabled === false}
                  onClick={() => onDeploy(s.session_id)}>
                  <RocketLaunchIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {s.status === 'RUNNING' && (
            <Tooltip title={safety.pause?.enabled !== false ? 'Pause' : safety.pause?.reason || 'Pause locked'}>
              <span>
                <IconButton size="small" color="warning"
                  disabled={safety.pause?.enabled === false}
                  onClick={() => onPause(s.session_id)}>
                  <PauseIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {s.status === 'RUNNING' && (
            <Tooltip title={safety.force_heartbeat?.enabled !== false ? 'Force heartbeat' : safety.force_heartbeat?.reason || 'Force heartbeat locked'}>
              <span>
                <IconButton size="small"
                  disabled={safety.force_heartbeat?.enabled === false}
                  sx={{ color: '#ffab00', '&:hover': { color: '#ffd600' } }}
                  onClick={() => onForceHB(s.session_id)}>
                  <BoltIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {s.status === 'PAUSED' && (
            <Tooltip title={safety.resume?.enabled !== false ? 'Resume' : safety.resume?.reason || 'Resume locked'}>
              <span>
                <IconButton size="small" color="success"
                  disabled={safety.resume?.enabled === false}
                  onClick={() => onResume(s.session_id)}>
                  <PlayArrowIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
          {['RUNNING', 'PAUSED', 'GATES_PASSED'].includes(s.status) && (
            <Tooltip title={safety.stop?.enabled !== false ? 'Stop' : safety.stop?.reason || 'Stop locked'}>
              <span>
                <IconButton size="small" color="error"
                  disabled={safety.stop?.enabled === false}
                  onClick={() => onStop(s.session_id)}>
                  <StopIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
