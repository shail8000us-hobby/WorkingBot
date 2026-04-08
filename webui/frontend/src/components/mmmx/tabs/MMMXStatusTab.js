import React, { useState, useEffect, useMemo } from 'react';
import {
  Box, Paper, Typography, Chip, Button, LinearProgress, Alert, CircularProgress,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import BoltIcon from '@mui/icons-material/Bolt';
import CircleIcon from '@mui/icons-material/Circle';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';
import { evaluateControlSafety } from '../mmmxControlSafety';
import { CONTRACT_STATUS } from '../mmmxEventContracts';
import { scfg, INCIDENT_COLOR } from '../utils/mmmxConstants';
import { fmt, pnlColor, computeDTE, heartbeatAgeSec, formatDdmmyy } from '../utils/mmmxFormatters';

export default function MMMXStatusTab({
  onDeploy,
  onForceHeartbeat,
  onIntegrityCheck,
  runControl,
  requestSessionAction,
  pendingControls,
  integrityState,
  healthModel,
  incidentQueue = [],
  recommendations = [],
}) {
  const { session, risk, isConnected, contract } = useMMMX();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [health, setHealth] = useState(null);
  const [strikePreview, setStrikePreview] = useState(null);
  const [strikeLoading, setStrikeLoading] = useState(false);
  const [gatesResult, setGatesResult] = useState(null);
  const [gatesLoading, setGatesLoading] = useState(false);
  const hbAgeSec = heartbeatAgeSec(session?._last_beat_at || session?.last_beat_at);

  const sessionControlPending = useMemo(() => {
    if (!session?.session_id) {
      return {
        deploy_tranche1: false, pause: false, resume: false, stop: false,
        kill_switch: false, reconcile: false, force_heartbeat: false, hot_reload_apply: false,
      };
    }
    const sid = session.session_id;
    return {
      deploy_tranche1: !!pendingControls?.[`deploy_tranche1:${sid}`],
      pause: !!pendingControls?.[`pause:${sid}`],
      resume: !!pendingControls?.[`resume:${sid}`],
      stop: !!pendingControls?.[`stop:${sid}`],
      kill_switch: !!pendingControls?.[`kill_switch:${sid}`],
      reconcile: !!pendingControls?.[`reconcile:${sid}`],
      force_heartbeat: !!pendingControls?.[`force_heartbeat:${sid}`],
      hot_reload_apply: !!pendingControls?.[`hot_reload_apply:${sid}`],
    };
  }, [pendingControls, session?.session_id]);

  const safety = useMemo(() => evaluateControlSafety({
    session,
    isConnected,
    contractStatus: contract?.status,
    integrityState,
    heartbeatAgeSec: hbAgeSec,
    healthState: healthModel?.state,
    pending: sessionControlPending,
  }), [session, isConnected, contract?.status, integrityState, hbAgeSec, healthModel?.state, sessionControlPending]);

  useEffect(() => {
    mmmxService.getHealth().then(r => { if (r.ok) setHealth(r.data); }).catch(() => {});
  }, [session?.status]);

  useEffect(() => {
    if (!session?.session_id || session.status !== 'DRAFT') {
      setStrikePreview(null); setGatesResult(null); return;
    }
    const id = session.session_id;
    const otmPct = session.params?.otm_distance_pct ?? 15;

    setStrikeLoading(true);
    mmmxService.scanStrikes(id, otmPct)
      .then(r => { if (r.ok) setStrikePreview(r.data ?? r); })
      .catch(() => {}).finally(() => setStrikeLoading(false));

    if (session.expiry_ddmmyy) {
      setGatesLoading(true);
      mmmxService.checkGates(id, session.expiry_ddmmyy)
        .then(r => { if (r.ok || r.gates) setGatesResult(r.data ?? r); })
        .catch(() => {}).finally(() => setGatesLoading(false));
    }
  }, [session?.session_id, session?.status, session?.expiry_ddmmyy]);

  const act = async (controlKey, fn, label) => {
    setBusy(true); setMsg('');
    try {
      const run = runControl || (async (_key, op) => op());
      const r = await run(`${controlKey}:${session.session_id}`, fn);
      setMsg(r.ok ? `✓ ${label || 'Done'}` : (r.error || 'Failed'));
    } catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  };

  if (!session) return (
    <Box sx={{ py: 4, textAlign: 'center' }}>
      <Typography color="text.secondary">Select a session from the left panel to view details.</Typography>
    </Box>
  );

  const pnl = session.portfolio_pnl ?? 0;
  const hardStop = session.hard_stop_usd ?? 0;
  const pnlPct = hardStop > 0 ? Math.min(100, Math.abs(pnl / hardStop) * 100) : 0;
  const cfg = scfg(session.status, session.reconcile_required);
  const dteInfo = computeDTE(session.expiry_date, session.expiry_ddmmyy);

  // ── DRAFT pre-deployment view ────────────────────────────────────────────────
  if (session.status === 'DRAFT') {
    const p = session.params ?? {};
    const expiry = session.expiry_ddmmyy;
    return (
      <Box>
        <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5, borderColor: '#2196f366' }}>
          <Typography variant="subtitle2" sx={{ mb: 1.2, fontWeight: 700, color: '#2196f3' }}>
            Session Configuration
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.2 }}>
            {[
              ['Expiry', expiry ? `${formatDdmmyy(expiry)} (${expiry})` : '⚠ Not set — deploy Tr1 to set'],
              ['Budget (lots)', `${p.total_budget_lots ?? '—'} total across 10 tranches`],
              ['OTM Distance', `${p.otm_distance_pct ?? '—'}%`],
              ['Hard Stop', `${p.hard_stop_multiplier ?? '—'}× premium collected`],
              ['Close at DTE', `${p.close_at_dte ?? '—'} days`],
              ['Deploy Move', `${p.tranche_deploy_move_pct ?? '—'}% spot move per tranche`],
              ['Hedging', p.hedging_enabled ? `Enabled · ${p.hedge_distance_pct ?? '—'}% OTM` : 'Disabled'],
              ['CE Reserve', `${session.ce_reserve_remaining ?? 30} lots`],
              ['PE Reserve', `${session.pe_reserve_remaining ?? 30} lots`],
            ].map(([label, val]) => (
              <Box key={label}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.68rem' }}>{label}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.82rem',
                  color: label === 'Expiry' && !expiry ? 'warning.main' : 'text.primary' }}>{val}</Typography>
              </Box>
            ))}
          </Box>
        </Paper>

        <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Strike Preview at {p.otm_distance_pct ?? 15}% OTM
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.6, alignItems: 'center' }}>
              {strikeLoading && <CircularProgress size={14} />}
              <Button size="small" variant="text" onClick={() => {
                setStrikeLoading(true);
                mmmxService.scanStrikes(session.session_id, p.otm_distance_pct ?? 15)
                  .then(r => { if (r.ok) setStrikePreview(r.data ?? r); })
                  .catch(() => {}).finally(() => setStrikeLoading(false));
              }}>Refresh</Button>
            </Box>
          </Box>
          {!strikePreview && !strikeLoading && (
            <Typography variant="caption" color="text.secondary">Strike scan pending…</Typography>
          )}
          {strikePreview && strikePreview.reason === 'no_expiry_set' && (
            <Typography variant="caption" color="text.secondary">No expiry set — strikes will be available after Tranche 1 is deployed.</Typography>
          )}
          {strikePreview && strikePreview.reason === 'no_live_chain' && (
            <Typography variant="caption" color="text.secondary">Live chain unavailable — check WS connection and retry.</Typography>
          )}
          {strikePreview && strikePreview.ce && strikePreview.pe && (
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
              {[
                { side: 'CE (Call)', data: strikePreview.ce ?? strikePreview.call },
                { side: 'PE (Put)',  data: strikePreview.pe ?? strikePreview.put },
              ].map(({ side, data }) => data ? (
                <Paper key={side} variant="outlined" sx={{ p: 1.2, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.02)' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: side.startsWith('CE') ? '#4caf50' : '#f44336' }}>
                    {side}
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', mt: 0.3 }}>
                    Strike: <b>{data.strike ?? '—'}</b>
                  </Typography>
                  {data.symbol && (
                    <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', display: 'block' }}>
                      {data.symbol}
                    </Typography>
                  )}
                  {data.mark_price != null && (
                    <Typography variant="caption" color="text.secondary">
                      Mark: ${fmt(data.mark_price)} · IV: {data.iv != null ? `${fmt(data.iv, 1)}%` : '—'} · Δ: {data.delta != null ? fmt(data.delta, 3) : '—'}
                    </Typography>
                  )}
                </Paper>
              ) : (
                <Typography key={side} variant="caption" color="text.secondary">{side}: no data</Typography>
              ))}
            </Box>
          )}
        </Paper>

        {expiry && (
          <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Entry Gates</Typography>
              {gatesLoading && <CircularProgress size={14} />}
            </Box>
            {!gatesResult && !gatesLoading && (
              <Typography variant="caption" color="text.secondary">Gates check pending…</Typography>
            )}
            {gatesResult && (
              <Box>
                <Chip size="small"
                  color={gatesResult.all_passed ? 'success' : 'warning'}
                  label={gatesResult.all_passed ? '✓ All gates passed — ready to deploy' : 'Gates not fully passed'}
                  sx={{ mb: 1 }} />
                {Array.isArray(gatesResult.gates) && gatesResult.gates.map((g, i) => (
                  <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 0.8, mb: 0.4 }}>
                    <Typography sx={{ fontSize: '0.72rem', color: g.passed ? '#4caf50' : '#ff9800' }}>
                      {g.passed ? '✓' : '✗'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: g.passed ? 'text.primary' : 'warning.main' }}>
                      {g.name}: {g.detail ?? (g.passed ? 'OK' : 'Not met')}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        )}

        {!expiry && (
          <Alert severity="info" sx={{ mb: 2 }}>
            No expiry set. Deploy Tranche 1 — the expiry is parsed automatically from the CE symbol you provide.
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" color="primary" startIcon={<RocketLaunchIcon />}
            disabled={safety.deploy_tranche1?.enabled === false}
            onClick={() => onDeploy(session.session_id)}>
            Deploy Tranche 1
          </Button>
          <Button variant="outlined" onClick={() => {
            setStrikeLoading(true);
            mmmxService.scanStrikes(session.session_id, p.otm_distance_pct ?? 15)
              .then(r => { if (r.ok) setStrikePreview(r.data ?? r); })
              .catch(() => {}).finally(() => setStrikeLoading(false));
            if (expiry) {
              setGatesLoading(true);
              mmmxService.checkGates(session.session_id, expiry)
                .then(r => { if (r.ok || r.gates) setGatesResult(r.data ?? r); })
                .catch(() => {}).finally(() => setGatesLoading(false));
            }
          }}>
            Refresh Market Data
          </Button>
        </Box>

        {safety.deploy_tranche1?.enabled === false && (
          <Typography variant="caption" sx={{ display: 'block', mt: 0.8, color: 'warning.main' }}>
            Deploy locked: {safety.deploy_tranche1.reason}
          </Typography>
        )}
      </Box>
    );
  }
  // ── End DRAFT view ──────────────────────────────────────────────────────────

  return (
    <Box>
      {/* Status banner */}
      <Box sx={{ p: 1.5, mb: 2, borderRadius: 1.5, border: `1px solid ${cfg.color}44`, bgcolor: cfg.bg,
                 display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircleIcon sx={{ fontSize: 10, color: cfg.color }} />
          <Typography variant="h6" sx={{ color: cfg.color, fontWeight: 700 }}>{cfg.label}</Typography>
        </Box>
        {dteInfo && (
          <Chip label={dteInfo.label} size="small"
            sx={{ bgcolor: `${dteInfo.color}22`, color: dteInfo.color, fontWeight: 700, fontFamily: 'monospace' }} />
        )}
        {session.expiry_date && (
          <Typography variant="body2" color="text.secondary">Expiry: {session.expiry_date}</Typography>
        )}
        <Typography variant="body2" color="text.secondary">
          Beat #{session.beat_number ?? session.beat_count ?? 0}
        </Typography>
        <Chip
          size="small"
          label={`Contract: ${contract?.status || CONTRACT_STATUS.UNKNOWN}`}
          color={
            contract?.status === CONTRACT_STATUS.SYNCED ? 'success'
              : contract?.status === CONTRACT_STATUS.DRIFT ? 'warning'
                : 'default'
          }
        />
        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.disabled', ml: 'auto' }}>
          {session.session_id}
        </Typography>
      </Box>

      {/* P&L vs Hard Stop */}
      <Paper variant="outlined" sx={{ p: 1.5, mb: 2, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="body2">
            Portfolio P&amp;L: <b style={{ color: pnlColor(pnl) }}>${fmt(pnl)}</b>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Hard Stop: <b>${fmt(hardStop)}</b>
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={pnlPct}
          color={pnlPct > 70 ? 'error' : pnlPct > 40 ? 'warning' : 'success'}
          sx={{ height: 8, borderRadius: 1 }} />
        {pnlPct > 0 && (
          <Typography variant="caption" color="text.secondary">{pnlPct.toFixed(1)}% of hard stop used</Typography>
        )}
      </Paper>

      {/* Recommendation stack */}
      <Paper variant="outlined" sx={{ p: 1.5, mb: 2, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Action Recommendations</Typography>
        {recommendations.length === 0 ? (
          <Typography variant="caption" color="text.secondary">No recommendation available.</Typography>
        ) : (
          recommendations.map((rec, idx) => (
            <Alert
              key={`${rec.priority}-${idx}`}
              severity={rec.priority === 'REQUIRED' ? 'error' : rec.priority === 'RECOMMENDED' ? 'warning' : 'info'}
              sx={{ mb: 0.8 }}
            >
              <strong>{rec.priority}:</strong> {rec.text}
              <Typography variant="caption" sx={{ display: 'block', mt: 0.3, opacity: 0.85 }}>
                {rec.reason}
              </Typography>
            </Alert>
          ))
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.5, mb: 2, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>State Integrity Monitor</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.8, mb: 1 }}>
          <Chip size="small" label={`Stream v${contract?.integrity?.stream_version ?? '—'}`} variant="outlined" />
          <Chip size="small" label={`Snapshot v${contract?.integrity?.snapshot_version ?? '—'}`} variant="outlined" />
          <Chip
            size="small"
            color={(contract?.integrity?.mismatches || []).length ? 'warning' : 'success'}
            label={(contract?.integrity?.mismatches || []).length ? 'Drift checks failed' : 'Hash/sequence synced'}
          />
        </Box>
        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', fontFamily: 'monospace' }}>
          stream checksum: {contract?.integrity?.stream_checksum ? contract.integrity.stream_checksum.slice(0, 12) : '—'}
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mb: 0.8, color: 'text.secondary', fontFamily: 'monospace' }}>
          snapshot checksum: {contract?.integrity?.snapshot_checksum ? contract.integrity.snapshot_checksum.slice(0, 12) : '—'}
        </Typography>
        {(contract?.integrity?.mismatches || []).slice(0, 4).map((m, idx) => (
          <Alert key={`${m.type}-${idx}`} severity="warning" sx={{ mb: 0.6 }}>
            <strong>{m.type}</strong>: {m.message}
          </Alert>
        ))}
        <Button size="small" variant="outlined" onClick={() => onIntegrityCheck?.(session.session_id)}>
          Run Integrity Check Now
        </Button>
      </Paper>

      {incidentQueue.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 2, borderRadius: 1.5 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Active Incident Snapshot</Typography>
          {incidentQueue.slice(0, 3).map((inc) => (
            <Box key={inc.id} sx={{ mb: 0.8 }}>
              <Chip size="small" label={inc.level} color={INCIDENT_COLOR[inc.level] || 'default'} sx={{ mr: 0.6 }} />
              <Typography variant="body2" component="span" sx={{ fontWeight: 600 }}>{inc.title}</Typography>
              <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mt: 0.2 }}>{inc.detail}</Typography>
            </Box>
          ))}
        </Paper>
      )}

      {/* Stats grid */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 1.5, mb: 2 }}>
        {[
          ['Premium Collected', `$${fmt(session.total_premium_collected)}`],
          ['Profit Booked',     `$${fmt(session.profit_booked_total)}`],
          ['Hedge Cost',        `$${fmt(session.total_hedge_cost_paid)}`],
          ['Tranches Deployed', `${session.tranches_deployed ?? 0} / 10`],
          ['CE Reserve',        `${session.ce_reserve_remaining ?? 30} lots`],
          ['PE Reserve',        `${session.pe_reserve_remaining ?? 30} lots`],
        ].map(([label, val]) => (
          <Paper key={label} variant="outlined" sx={{ p: 1, textAlign: 'center', borderRadius: 1.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.7rem' }}>{label}</Typography>
            <Typography variant="body1" sx={{ fontWeight: 700 }}>{val}</Typography>
          </Paper>
        ))}
      </Box>

      {/* Naked positions alert */}
      {risk.naked_positions?.length > 0 && (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          Naked positions detected: {risk.naked_positions.join(', ')}
        </Alert>
      )}

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
        {['DRAFT', 'GATES_PASSED', 'RUNNING'].includes(session.status) && (session.tranches_deployed ?? 0) === 0 && (
          <Button variant="contained" color="primary"
            startIcon={<RocketLaunchIcon />} disabled={busy || safety.deploy_tranche1?.enabled === false}
            onClick={() => onDeploy(session.session_id)}>
            Deploy Tranche 1
          </Button>
        )}
        {session.status === 'RUNNING' && (
          <Button variant="outlined" color="warning" startIcon={<PauseIcon />} disabled={busy || safety.pause?.enabled === false}
            onClick={() => requestSessionAction
              ? requestSessionAction('pause', session.session_id)
              : act('pause', () => mmmxService.pauseSession(session.session_id), 'Paused')}>
            Pause
          </Button>
        )}
        {session.status === 'RUNNING' && (
          <Button variant="outlined"
            sx={{ borderColor: '#ffab00', color: '#ffab00' }}
            startIcon={<BoltIcon />}
            disabled={busy || safety.force_heartbeat?.enabled === false}
            onClick={() => requestSessionAction
              ? requestSessionAction('force_heartbeat', session.session_id)
              : act('force_heartbeat',
                () => (onForceHeartbeat ? onForceHeartbeat(session.session_id) : mmmxService.forceHeartbeat(session.session_id)),
                'Forced heartbeat')}>
            Force Heartbeat
          </Button>
        )}
        {session.status === 'PAUSED' && (
          <Button variant="contained" color="success" startIcon={<PlayArrowIcon />} disabled={busy || safety.resume?.enabled === false}
            onClick={() => requestSessionAction
              ? requestSessionAction('resume', session.session_id)
              : act('resume', () => mmmxService.resumeSession(session.session_id), 'Resumed')}>
            Resume
          </Button>
        )}
        {!['COMPLETE', 'ERROR', 'DRAFT'].includes(session.status) && (
          <Button variant="outlined" color="error" startIcon={<StopIcon />} disabled={busy || safety.stop?.enabled === false}
            onClick={() => requestSessionAction
              ? requestSessionAction('stop', session.session_id)
              : act('stop', () => mmmxService.stopSession(session.session_id), 'Stopped')}>
            Stop
          </Button>
        )}
        <Button variant="outlined" disabled={busy || safety.reconcile?.enabled === false}
          onClick={() => requestSessionAction
            ? requestSessionAction('reconcile', session.session_id)
            : act('reconcile', () => mmmxService.reconcile(session.session_id), 'Reconcile triggered')}>
          Reconcile
        </Button>
      </Box>

      {Object.values(safety).some((v) => v?.enabled === false) && (
        <Paper variant="outlined" sx={{ p: 1, mb: 1, borderRadius: 1.5, borderColor: '#ff9800' }}>
          <Typography variant="caption" sx={{ color: 'warning.main', fontWeight: 700 }}>Control locks</Typography>
          {Object.entries(safety)
            .filter(([, v]) => v?.enabled === false)
            .slice(0, 6)
            .map(([key, v]) => (
              <Typography key={key} variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                • {key}: {v.reason}
              </Typography>
            ))}
        </Paper>
      )}

      {msg && (
        <Typography variant="caption" sx={{ display: 'block', mb: 1,
          color: msg.startsWith('✓') ? 'success.main' : 'error.main' }}>
          {msg}
        </Typography>
      )}

      {health && (
        <Paper variant="outlined" sx={{ p: 1.5, mt: 1, borderRadius: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5, fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem' }}>
            System Health
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip label={health.watchdog_alive ? '● Watchdog Alive' : '○ Watchdog Dead'}
              color={health.watchdog_alive ? 'success' : 'error'} size="small" />
            <Chip label={`${health.active_monitors}/${health.total_monitors} Monitors`} size="small" variant="outlined" />
            <Chip label={health.ws?.socketio_initialized ? 'WS OK' : 'WS Not Init'}
              color={health.ws?.socketio_initialized ? 'success' : 'warning'} size="small" />
            {health.last_watchdog_tick && (
              <Typography variant="caption" color="text.secondary">
                Last tick: {health.last_watchdog_tick.slice(11, 19)} UTC
              </Typography>
            )}
          </Box>
        </Paper>
      )}
    </Box>
  );
}
