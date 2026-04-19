/**
 * MMMXDashboard — orchestration shell
 *
 * Two-column layout:
 *   Left  (300px): session list, incident queue, controls
 *   Right (flex):  session detail tabs, top command strip
 *
 * All substantial components are extracted to separate files.
 * This file owns only state, callbacks, and layout.
 */

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import {
  Box, Typography, Chip, Button, IconButton, Tooltip,
  Tabs, Tab, CircularProgress, Alert, Snackbar,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
} from '@mui/material';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import CircleIcon from '@mui/icons-material/Circle';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { useMMMX } from './MMMXContext';
import { mmmxService } from './mmmxService';
import { evaluateControlSafety } from './mmmxControlSafety';
import { scfg, INCIDENT_RANK } from './utils/mmmxConstants';
import { heartbeatAgeSec, computeDTE } from './utils/mmmxFormatters';
import {
  deriveIntegrityState, deriveConfidence,
  buildIncidentQueue, deriveSystemHealth, deriveRecommendations,
} from './utils/mmmxDerivations';

// Extracted components
import MMMXSessionCard from './MMMXSessionCard';
import MMMXTopCommandStrip from './MMMXTopCommandStrip';
import MMMXIncidentQueuePanel from './MMMXIncidentQueuePanel';
import MMMXCriticalModePanel from './MMMXCriticalModePanel';
import MMMXErrorBoundary from './MMMXErrorBoundary';
import { MMMXCreateSessionDialog, MMMXDeployTr1Dialog } from './MMMXCreateSessionDialog';

// Tab components
import MMMXStatusTab from './tabs/MMMXStatusTab';
import MMMXTranchesTab from './tabs/MMMXTranchesTab';
import MMMXTriggerEngineTab from './tabs/MMMXTriggerEngineTab';
import MMMXHedgesTab from './tabs/MMMXHedgesTab';
import MMMXRiskTab from './tabs/MMMXRiskTab';
import MMMXExecutionTab from './tabs/MMMXExecutionTab';
import MMMXAdjustmentsTab from './tabs/MMMXAdjustmentsTab';
import MMMXProfitBookingTab from './tabs/MMMXProfitBookingTab';
import MMMXParametersTab from './tabs/MMMXParametersTab';
import MMMXReconcileTab from './tabs/MMMXReconcileTab';

// Phase 3 panels
import MMMXSafetyPanel from './panels/MMMXSafetyPanel';
import MMMXTradeAuditPanel from './panels/MMMXTradeAuditPanel';
import MMMXFeesCapitalPanel from './panels/MMMXFeesCapitalPanel';
import MMMXRegimePanel from './panels/MMMXRegimePanel';
import MMMXDeltaExposurePanel from './panels/MMMXDeltaExposurePanel';
import MMMXPnLChart from './panels/MMMXPnLChart';
import MMMXPerformancePanel from './panels/MMMXPerformancePanel';
import MMMXRiskRail from './panels/MMMXRiskRail';
import MMMXHealthRadar from './panels/MMMXHealthRadar';

// ── Constants ──────────────────────────────────────────────────────────────────
const TABS = [
  'Status', 'Tranches', 'Trigger Engine', 'Hedges', 'Risk', 'Execution',
  'Adjustments', 'Profit Booking', 'Parameters', 'Reconcile',
  'Safety', 'Trade Audit', 'Fees', 'Regime', 'Delta', 'P&L Chart', 'Performance', 'Health Radar',
];

function TabPanel({ children, value, index }) {
  return value === index ? <Box sx={{ p: 2 }}>{children}</Box> : null;
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function MMMXDashboard() {
  const {
    session, isConnected, loadSession, activeSessionId,
    contract, activity, execution, risk,
  } = useMMMX();

  const [allSessions, setAllSessions]   = useState([]);
  const [listTab, setListTab]           = useState(0);   // 0=All, 1=Active, 2=Draft, 3=Done
  const [detailTab, setDetailTab]       = useState(0);
  const [showCreate, setShowCreate]     = useState(false);
  const [deployFor, setDeployFor]       = useState(null);
  const [refreshing, setRefreshing]     = useState(false);
  const [pendingControls, setPendingControls] = useState({});
  const [criticalMode, setCriticalMode] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [confirmText, setConfirmText]   = useState('');
  const [confirmStep, setConfirmStep]   = useState(1);
  const [confirmBusy, setConfirmBusy]   = useState(false);
  const [clockTick, setClockTick]       = useState(0);
  const [apiError, setApiError]         = useState(null);
  const [snackMsg, setSnackMsg]         = useState('');
  const autoFocusRef = useRef(null);

  // ── Derived state ────────────────────────────────────────────────────────────
  const activeHbAgeSec = heartbeatAgeSec(session?._last_beat_at || session?.last_beat_at);

  const integrityState = deriveIntegrityState({
    session, isConnected, contractStatus: contract?.status, hbAgeSec: activeHbAgeSec,
  });
  const confidence = deriveConfidence({ integrityState, hbAgeSec: activeHbAgeSec });

  const incidentQueue = useMemo(() => buildIncidentQueue({
    session, risk, activity, contract, execution, isConnected, hbAgeSec: activeHbAgeSec,
  }), [session, risk, activity, contract, execution, isConnected, activeHbAgeSec, clockTick]); // eslint-disable-line

  const healthModel = useMemo(() => deriveSystemHealth({
    integrityState, confidence, incidents: incidentQueue, risk, isConnected, hbAgeSec: activeHbAgeSec,
  }), [integrityState, confidence, incidentQueue, risk, isConnected, activeHbAgeSec]);

  const recommendations = useMemo(() => deriveRecommendations({
    incidents: incidentQueue, health: healthModel, integrityState,
  }), [incidentQueue, healthModel, integrityState]);

  // ── Session list ─────────────────────────────────────────────────────────────
  const fetchSessions = useCallback(async (silent = true) => {
    if (!silent) setRefreshing(true);
    try {
      const res = await mmmxService.listSessions();
      if (res.ok) { setAllSessions(res.data ?? []); setApiError(null); }
      else setApiError(`Session list unavailable: ${res.error || 'unknown error'}`);
    } catch (err) { setApiError(`API unreachable: ${String(err)}`); }
    finally { if (!silent) setRefreshing(false); }
  }, []);

  // Visibility-aware polling — pauses when tab is hidden, resumes on focus
  useVisibilityAwarePolling(() => fetchSessions(true), 10000, 30000);

  useEffect(() => { fetchSessions(false); }, [fetchSessions]); // initial load

  useEffect(() => {
    const timer = setInterval(() => setClockTick((v) => v + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  // Categorise sessions
  const active   = allSessions.filter(s => ['RUNNING', 'PAUSED', 'GATES_PASSED'].includes(s.status));
  const drafts   = allSessions.filter(s => s.status === 'DRAFT');
  const done     = allSessions.filter(s => ['COMPLETE', 'ERROR'].includes(s.status));
  const listMap  = [allSessions, active, drafts, done];
  const displayed = listMap[listTab] ?? allSessions;
  const totalPnl  = active.reduce((s, x) => s + (x.portfolio_pnl ?? 0), 0);

  // ── Control helpers ───────────────────────────────────────────────────────────
  const runControl = useCallback(async (controlKey, fn, label) => {
    if (pendingControls[controlKey]) return { ok: false, error: 'Command already pending' };
    setPendingControls(prev => ({ ...prev, [controlKey]: true }));
    try {
      const result = await fn();
      if (label) setSnackMsg(result?.ok ? `✓ ${label}` : `✗ ${result?.error || label + ' failed'}`);
      return result;
    } finally {
      setPendingControls(prev => { const n = { ...prev }; delete n[controlKey]; return n; });
    }
  }, [pendingControls]);

  const queueConfirmedAction = useCallback((cfg) => {
    if (!cfg || typeof cfg.run !== 'function') return;
    if ((cfg.tier || 'A') === 'A') { cfg.run(); return; }
    setConfirmText(''); setConfirmStep(1); setConfirmDialog(cfg);
  }, []);

  const handleControl = useCallback(async (action, sid) => {
    const fn = { pause: () => mmmxService.pauseSession(sid), resume: () => mmmxService.resumeSession(sid), stop: () => mmmxService.stopSession(sid) }[action];
    if (fn) {
      await runControl(`${action}:${sid}`, fn);
      setTimeout(() => fetchSessions(true), 800);
      if (activeSessionId === sid) setTimeout(() => loadSession(sid), 600);
    }
  }, [runControl, fetchSessions, activeSessionId, loadSession]);

  const handleForceHeartbeat = useCallback(async (sid) => {
    await runControl(`force_heartbeat:${sid}`, () => mmmxService.forceHeartbeat(sid));
    if (activeSessionId === sid) setTimeout(() => loadSession(sid), 500);
  }, [runControl, activeSessionId, loadSession]);

  const requestSessionAction = useCallback((action, sid) => {
    const actionLabel = {
      pause: 'Pause session', resume: 'Resume session', stop: 'Stop session',
      force_heartbeat: 'Force heartbeat', reconcile: 'Run reconcile',
    }[action] || action;
    const tier = action === 'stop' ? 'C' : 'B';
    const run = () => {
      if (action === 'force_heartbeat') return handleForceHeartbeat(sid);
      if (action === 'reconcile') return runControl(`reconcile:${sid}`, async () => {
        const out = await mmmxService.reconcile(sid);
        if (activeSessionId === sid) setTimeout(() => loadSession(sid), 500);
        return out;
      });
      return handleControl(action, sid);
    };
    queueConfirmedAction({
      tier,
      title: actionLabel,
      description: `Session ${sid.slice(-8)} · integrity=${integrityState} · health=${healthModel.state}`,
      typedPhrase: tier === 'C' ? `STOP ${sid.slice(0, 8)}` : '',
      run,
    });
  }, [queueConfirmedAction, integrityState, healthModel.state, handleForceHeartbeat, runControl, activeSessionId, loadSession, handleControl]);

  const handleCreated = (newSession) => {
    fetchSessions(true);
    const sid = newSession?.session_id ?? newSession?.session?.session_id;
    if (sid) { loadSession(sid); setDetailTab(0); }
  };

  const handleDeployed = () => {
    fetchSessions(true);
    if (activeSessionId) { loadSession(activeSessionId); setDetailTab(0); }
    setDeployFor(null);
  };

  const requestDeployAction = useCallback((sid) => {
    queueConfirmedAction({
      tier: 'B',
      title: 'Deploy Tranche 1',
      description: `Prepare manual deployment for session ${sid.slice(-8)} · integrity=${integrityState} · health=${healthModel.state}`,
      run: () => setDeployFor(sid),
    });
  }, [queueConfirmedAction, integrityState, healthModel.state]);

  const targetExpiry = session?.expiry_ddmmyy || session?.params?.target_expiry_ddmmyy;

  const focusIncident = useCallback((incident) => {
    if (!incident) return;
    const toTab = (name) => Math.max(0, TABS.indexOf(name));
    switch (incident.type) {
      case 'execution_uncertain': case 'residual_aging': setDetailTab(toTab('Execution')); break;
      case 'reconcile_required': case 'contract_drift': setDetailTab(toTab('Reconcile')); break;
      case 'orphan_hedges': setDetailTab(toTab('Hedges')); break;
      case 'safety_event': setDetailTab(toTab('Safety')); break;
      case 'circuit_breaker': setDetailTab(toTab('Regime')); break;
      default: setDetailTab(toTab('Status')); break;
    }
  }, []);

  // Auto-focus on L3+ incidents
  useEffect(() => {
    const liveSession = ['RUNNING', 'PAUSED', 'GATES_PASSED'].includes(session?.status);
    const top = incidentQueue[0];
    const hasL3 = top && (INCIDENT_RANK[top.level] || 0) >= INCIDENT_RANK.L3;
    if (hasL3 && liveSession) {
      setCriticalMode(true);
      const marker = `${top.id}:${top.timestamp}`;
      if (autoFocusRef.current !== marker) { autoFocusRef.current = marker; focusIncident(top); }
    } else if (!hasL3) {
      setCriticalMode(false); autoFocusRef.current = null;
    }
  }, [incidentQueue, session?.status, focusIncident]);

  const handleKillSession = useCallback(() => {
    if (!session?.session_id) return;
    queueConfirmedAction({
      tier: 'C',
      title: 'Kill current session',
      description: `Terminal stop for ${session.session_id}. Offensive controls remain locked until completion certainty.`,
      typedPhrase: `KILL ${session.session_id.slice(0, 8)}`,
      run: async () => {
        await runControl(`kill_switch:${session.session_id}`, () => mmmxService.killSwitch({ scope: 'session', session_id: session.session_id, reason: 'operator kill switch' }));
        setTimeout(() => fetchSessions(true), 600);
        setTimeout(() => loadSession(session.session_id), 600);
      },
    });
  }, [session?.session_id, queueConfirmedAction, runControl, fetchSessions, loadSession]);

  const handleKillGlobal = useCallback(() => {
    queueConfirmedAction({
      tier: 'C',
      title: 'Global kill switch',
      description: 'Terminal stop for all RUNNING/PAUSED/GATES_PASSED sessions.',
      typedPhrase: 'KILL GLOBAL',
      run: async () => {
        await runControl('kill_switch:global', () => mmmxService.killSwitch({ scope: 'global', reason: 'operator global kill switch' }));
        setTimeout(() => fetchSessions(true), 800);
        if (activeSessionId) setTimeout(() => loadSession(activeSessionId), 800);
      },
    });
  }, [queueConfirmedAction, runControl, fetchSessions, activeSessionId, loadSession]);

  const handleIntegrityCheck = useCallback(async (sid) => { if (sid) await loadSession(sid); }, [loadSession]);

  const closeConfirmDialog = useCallback(() => {
    if (confirmBusy) return;
    setConfirmDialog(null); setConfirmText(''); setConfirmStep(1);
  }, [confirmBusy]);

  const executeConfirmedAction = useCallback(async () => {
    if (!confirmDialog) return;
    if (confirmDialog.tier === 'B' && confirmStep === 1) { setConfirmStep(2); return; }
    if (confirmDialog.tier === 'C' && confirmDialog.typedPhrase) {
      if ((confirmText || '').trim() !== confirmDialog.typedPhrase) return;
    }
    setConfirmBusy(true);
    try { await Promise.resolve(confirmDialog.run()); }
    finally { setConfirmBusy(false); setConfirmDialog(null); setConfirmText(''); setConfirmStep(1); }
  }, [confirmDialog, confirmStep, confirmText]);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ display: 'flex', height: '100%', gap: 0, overflow: 'hidden' }}>

      {/* ── LEFT PANEL ──────────────────────────────────────────────────────── */}
      <Box sx={{ width: 300, minWidth: 260, flexShrink: 0, borderRight: '1px solid',
                 borderColor: 'divider', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Header */}
        <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider',
                   display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, letterSpacing: 0.5 }}>MMMX</Typography>
            <Chip label={isConnected ? 'WS ✓' : 'WS ✗'} color={isConnected ? 'success' : 'error'}
              size="small" sx={{ height: 18, fontSize: '0.62rem', fontWeight: 700 }} />
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
            <Tooltip title="Refresh session list">
              <IconButton size="small" onClick={() => fetchSessions(false)} disabled={refreshing}>
                {refreshing ? <CircularProgress size={14} /> : <RefreshIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Button size="small" variant="contained" startIcon={<AddIcon />}
              sx={{ fontSize: '0.72rem', py: 0.3, px: 1 }}
              onClick={() => setShowCreate(true)}>
              New Session
            </Button>
          </Box>
        </Box>

        {/* Active sessions P&L summary */}
        {active.length > 0 && (
          <Box sx={{ px: 1.5, py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
                     display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                     bgcolor: 'rgba(255,255,255,0.02)' }}>
            <Typography variant="caption" color="text.secondary">
              {active.length} active · Combined P&amp;L
            </Typography>
            <Typography variant="caption" sx={{ fontWeight: 700, fontFamily: 'monospace',
              color: totalPnl >= 0 ? '#4caf50' : '#f44336' }}>
              ${totalPnl.toFixed(2)}
            </Typography>
          </Box>
        )}

        {/* Filter tabs */}
        <Tabs value={listTab} onChange={(_, v) => setListTab(v)}
          variant="scrollable" scrollButtons="auto"
          sx={{ borderBottom: '1px solid', borderColor: 'divider', minHeight: 34,
                '& .MuiTab-root': { minHeight: 34, fontSize: '0.7rem', py: 0.5, px: 1.2 } }}>
          <Tab label={`All (${allSessions.length})`} />
          <Tab label={`Active (${active.length})`} />
          <Tab label={`Draft (${drafts.length})`} />
          <Tab label={`Done (${done.length})`} />
        </Tabs>

        <MMMXIncidentQueuePanel incidents={incidentQueue} onFocusIncident={focusIncident} />

        {/* Session cards */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
          {displayed.length === 0 ? (
            <Box sx={{ textAlign: 'center', pt: 4, px: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {listTab === 0 ? 'No sessions yet.' : `No ${['', 'active', 'draft', 'done'][listTab]} sessions.`}
              </Typography>
              {listTab === 0 && (
                <Typography variant="caption" color="text.disabled">
                  Click "New Session" above to create one.
                </Typography>
              )}
            </Box>
          ) : (
            displayed.map((s) => {
              const cardHbAgeSec = heartbeatAgeSec(s._last_beat_at || s.last_beat_at);
              const cardIntegrity = deriveIntegrityState({
                session: s, isConnected, contractStatus: contract?.status, hbAgeSec: cardHbAgeSec,
              });
              const cardSafety = evaluateControlSafety({
                session: s, isConnected, contractStatus: contract?.status,
                integrityState: cardIntegrity, heartbeatAgeSec: cardHbAgeSec,
                healthState: healthModel.state,
                pending: {
                  deploy_tranche1: !!pendingControls[`deploy_tranche1:${s.session_id}`],
                  pause: !!pendingControls[`pause:${s.session_id}`],
                  resume: !!pendingControls[`resume:${s.session_id}`],
                  stop: !!pendingControls[`stop:${s.session_id}`],
                  kill_switch: !!pendingControls[`kill_switch:${s.session_id}`],
                  reconcile: !!pendingControls[`reconcile:${s.session_id}`],
                  force_heartbeat: !!pendingControls[`force_heartbeat:${s.session_id}`],
                  hot_reload_apply: !!pendingControls[`hot_reload_apply:${s.session_id}`],
                },
              });
              return (
                <MMMXSessionCard key={s.session_id} s={s}
                  selected={s.session_id === activeSessionId}
                  onSelect={id => { loadSession(id); setDetailTab(0); }}
                  onPause={id => requestSessionAction('pause', id)}
                  onResume={id => requestSessionAction('resume', id)}
                  onStop={id => requestSessionAction('stop', id)}
                  onDeploy={id => requestDeployAction(id)}
                  onForceHB={id => requestSessionAction('force_heartbeat', id)}
                  onKillSwitch={id => runControl(`kill_switch:${id}`, () => mmmxService.killSwitch({ scope: 'session', session_id: id, reason: 'card kill switch' }))}
                  controlSafety={cardSafety}
                  allSessions={allSessions}
                />
              );
            })
          )}
        </Box>

        {/* Footer */}
        <Box sx={{ px: 1.5, py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
          {apiError ? (
            <Typography variant="caption" sx={{ color: 'error.main', display: 'block', fontWeight: 700 }}>
              ⚠ {apiError}
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {allSessions.length} session{allSessions.length !== 1 ? 's' : ''}
              {active.length > 0 && ` · ${active.length} active`}
            </Typography>
          )}
        </Box>
      </Box>

      {/* ── CENTER PANEL ─────────────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column',
                 bgcolor: criticalMode ? 'rgba(244,67,54,0.04)' : 'transparent' }}>
        {!session ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
                     justifyContent: 'center', gap: 1.5, color: 'text.secondary' }}>
            <Typography variant="h6" color="text.secondary">No session selected</Typography>
            <Typography variant="body2" color="text.disabled" sx={{ textAlign: 'center', maxWidth: 360 }}>
              Select a session from the left panel to view status, tranches, hedges, risk, and parameters.
              Use <strong>New Session</strong> in the left panel to create a new one.
            </Typography>
          </Box>
        ) : (
          <>
            <MMMXTopCommandStrip
              session={session}
              isConnected={isConnected}
              integrityState={integrityState}
              confidence={confidence}
              health={healthModel}
              incidents={incidentQueue}
              killProgress={risk.kill_switch_progress}
              criticalMode={criticalMode}
              onToggleCritical={() => setCriticalMode((v) => !v)}
              onKillSession={handleKillSession}
              onKillGlobal={handleKillGlobal}
            />

            {/* Session header bar */}
            <Box sx={{ px: 2, py: 1, borderBottom: '1px solid', borderColor: 'divider',
                       display: 'flex', alignItems: 'center', gap: 2,
                       bgcolor: scfg(session.status, session.reconcile_required).bg }}>
              <CircleIcon sx={{ fontSize: 10, color: scfg(session.status, session.reconcile_required).color }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: scfg(session.status, session.reconcile_required).color }}>
                {scfg(session.status, session.reconcile_required).label}
              </Typography>
              <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                {session.session_id}
              </Typography>
              {(() => {
                const d = computeDTE(session.expiry_date, session.expiry_ddmmyy);
                return d ? (
                  <Chip label={d.label} size="small"
                    sx={{ ml: 'auto', bgcolor: `${d.color}22`, color: d.color, fontWeight: 700,
                          fontFamily: 'monospace', fontSize: '0.72rem' }} />
                ) : null;
              })()}
              {['DRAFT', 'GATES_PASSED', 'RUNNING'].includes(session.status) && (session.tranches_deployed ?? 0) === 0 && (
                <Button size="small" variant="contained" color="primary"
                  startIcon={<RocketLaunchIcon />}
                  sx={{ ml: 'auto', fontSize: '0.72rem' }}
                  onClick={() => requestDeployAction(session.session_id)}>
                  Deploy Tranche 1
                </Button>
              )}
            </Box>

            {criticalMode ? (
              <MMMXErrorBoundary name="CriticalModePanel">
                <MMMXCriticalModePanel
                  session={session}
                  incidents={incidentQueue}
                  recommendations={recommendations}
                  onFocusIncident={focusIncident}
                  onKillSession={handleKillSession}
                  onKillGlobal={handleKillGlobal}
                  onExit={() => setCriticalMode(false)}
                />
              </MMMXErrorBoundary>
            ) : (
              <>
                <Tabs value={detailTab} onChange={(_, v) => setDetailTab(v)}
                  variant="scrollable" scrollButtons="auto"
                  sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 1,
                        '& .MuiTab-root': { fontSize: '0.8rem', minHeight: 40, py: 0.5 } }}>
                  {TABS.map((label, i) => <Tab key={i} label={label} />)}
                </Tabs>

                <Box sx={{ flex: 1, overflow: 'auto' }}>
                  <TabPanel value={detailTab} index={0}>
                    <MMMXErrorBoundary name="StatusTab">
                      <MMMXStatusTab
                        onDeploy={id => requestDeployAction(id)}
                        onForceHeartbeat={id => mmmxService.forceHeartbeat(id)}
                        onIntegrityCheck={handleIntegrityCheck}
                        runControl={runControl}
                        requestSessionAction={requestSessionAction}
                        pendingControls={pendingControls}
                        integrityState={integrityState}
                        healthModel={healthModel}
                        incidentQueue={incidentQueue}
                        recommendations={recommendations}
                      />
                    </MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={1}>
                    <MMMXErrorBoundary name="TranchesTab"><MMMXTranchesTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={2}>
                    <MMMXErrorBoundary name="TriggerEngineTab"><MMMXTriggerEngineTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={3}>
                    <MMMXErrorBoundary name="HedgesTab"><MMMXHedgesTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={4}>
                    <MMMXErrorBoundary name="RiskTab"><MMMXRiskTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={5}>
                    <MMMXErrorBoundary name="ExecutionTab"><MMMXExecutionTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={6}>
                    <MMMXErrorBoundary name="AdjustmentsTab"><MMMXAdjustmentsTab /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={7}>
                    <MMMXErrorBoundary name="ProfitBookingTab">
                      <MMMXProfitBookingTab queueConfirmedAction={queueConfirmedAction} />
                    </MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={8}>
                    <MMMXErrorBoundary name="ParametersTab">
                      <MMMXParametersTab queueConfirmedAction={queueConfirmedAction} runControl={runControl} />
                    </MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={9}>
                    <MMMXErrorBoundary name="ReconcileTab">
                      <MMMXReconcileTab queueConfirmedAction={queueConfirmedAction} />
                    </MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={10}>
                    <MMMXErrorBoundary name="SafetyPanel"><MMMXSafetyPanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={11}>
                    <MMMXErrorBoundary name="TradeAuditPanel"><MMMXTradeAuditPanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={12}>
                    <MMMXErrorBoundary name="FeesCapitalPanel"><MMMXFeesCapitalPanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={13}>
                    <MMMXErrorBoundary name="RegimePanel"><MMMXRegimePanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={14}>
                    <MMMXErrorBoundary name="DeltaExposurePanel"><MMMXDeltaExposurePanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={15}>
                    <MMMXErrorBoundary name="PnLChart"><MMMXPnLChart /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={16}>
                    <MMMXErrorBoundary name="PerformancePanel"><MMMXPerformancePanel /></MMMXErrorBoundary>
                  </TabPanel>
                  <TabPanel value={detailTab} index={17}>
                    <MMMXErrorBoundary name="HealthRadar"><MMMXHealthRadar /></MMMXErrorBoundary>
                  </TabPanel>
                </Box>
              </>
            )}
          </>
        )}
      </Box>

      {/* ── RISK RAIL ──────────────────────────────────────────────────────── */}
      <Box sx={{
        width: 220,
        minWidth: 200,
        flexShrink: 0,
        borderLeft: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <Box sx={{
          px: 1.2,
          py: 0.8,
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          gap: 0.8,
        }}>
          <Typography variant="caption" sx={{ fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase', fontSize: '0.65rem' }}>
            Risk Rail
          </Typography>
          <Chip
            label={isConnected ? 'LIVE' : 'STALE'}
            color={isConnected ? 'success' : 'error'}
            size="small"
            sx={{ height: 16, fontSize: '0.6rem', fontWeight: 700 }}
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
          <MMMXErrorBoundary name="RiskRail">
            <MMMXRiskRail />
          </MMMXErrorBoundary>
        </Box>
      </Box>

      {/* ── Dialogs ──────────────────────────────────────────────────────────── */}
      <MMMXCreateSessionDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={handleCreated}
      />
      <MMMXDeployTr1Dialog
        open={!!deployFor}
        sessionId={deployFor}
        session={session}
        targetExpiry={targetExpiry}
        onClose={() => setDeployFor(null)}
        onDeployed={handleDeployed}
      />

      {/* Action feedback snackbar */}
      <Snackbar
        open={!!snackMsg}
        autoHideDuration={3000}
        onClose={() => setSnackMsg('')}
        message={snackMsg}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      />

      {/* Tiered confirmation dialog */}
      <Dialog open={!!confirmDialog} onClose={closeConfirmDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{confirmDialog?.title || 'Confirm Action'}</DialogTitle>
        <DialogContent>
          <Alert severity={confirmDialog?.tier === 'C' ? 'error' : 'warning'} sx={{ mb: 1.2 }}>
            {confirmDialog?.tier === 'C'
              ? 'Tier C · typed confirmation required'
              : 'Tier B · double confirmation required'}
          </Alert>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {confirmDialog?.description || 'Please confirm this control action.'}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1.2, color: 'text.secondary' }}>
            Risk preview: integrity={integrityState}, health={healthModel.state}, incidents={incidentQueue.length}
          </Typography>
          {confirmDialog?.tier === 'B' && (
            <Typography variant="body2" sx={{ color: 'warning.main' }}>
              {confirmStep === 1 ? 'Step 1/2: Verify context and continue.' : 'Step 2/2: Execute action now.'}
            </Typography>
          )}
          {confirmDialog?.tier === 'C' && (
            <TextField size="small" fullWidth label="Type phrase to confirm" value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              helperText={`Required: ${confirmDialog?.typedPhrase || ''}`} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeConfirmDialog} disabled={confirmBusy}>Cancel</Button>
          <Button
            variant="contained"
            color={confirmDialog?.tier === 'C' ? 'error' : 'warning'}
            onClick={executeConfirmedAction}
            disabled={
              confirmBusy ||
              (confirmDialog?.tier === 'C' && !!confirmDialog?.typedPhrase && (confirmText || '').trim() !== confirmDialog.typedPhrase)
            }
          >
            {confirmBusy ? 'Executing...' : confirmDialog?.tier === 'B' ? (confirmStep === 1 ? 'Continue' : 'Execute') : 'Execute'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
