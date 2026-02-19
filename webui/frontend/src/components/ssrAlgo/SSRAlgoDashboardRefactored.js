/**
 * SSR ALGO — Professional Trading Terminal Dashboard
 * 
 * Layout (top-to-bottom):
 *   ROW 1: Header bar — 44px — logo, status, controls
 *   ROW 2: Metrics ribbon — 44px — single horizontal row of key numbers
 *   ROW 3: Main content — fills remaining — chart (left 62%) | tabs (right 38%)
 *   Below chart: Stats strip + trigger cards (compact)
 * 
 * Design principles:
 *   - Minimum font size: 13px for data, 11px for labels
 *   - Payoff chart is the HERO element (~60% of screen)
 *   - Metrics ribbon is ONE horizontal row, never wraps
 *   - Config lives in a slide-out drawer, not on screen
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Button,
  CircularProgress,
  LinearProgress,
  Drawer,
  Tab,
  Tabs,
  Alert,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  PlayArrow as PlayIcon,
  Settings as SettingsIcon,
  TrendingDown as DownIcon,
  TrendingUp as UpIcon,
  FiberManualRecord as DotIcon,
  SwapVert as AdjustIcon,
  ShowChart as ChartIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import SSRAlgoConfigPanel from './SSRAlgoConfigPanel';
import SSRAlgoPayoffChart from './SSRAlgoPayoffChart';
import SSRAlgoPositionsTable from './SSRAlgoPositionsTable';
import SSRAlgoLogPanel from './SSRAlgoLogPanel';
import SSRAlgoTriggerHistory from './SSRAlgoTriggerHistory';
import ssrAlgoService from './ssrAlgoService';

/* ═══════════════════════════════════════════════════════════════════════════
   HELPER COMPONENTS
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Metric — single data point in the top ribbon.
 * Renders inline: LABEL VALUE (no stacking, no wrapping).
 */
const Metric = ({ label, value, color, valueSize }) => (
  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, whiteSpace: 'nowrap' }}>
    <Typography sx={{
      color: '#64748b',
      fontSize: 11,
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.4px',
    }}>
      {label}
    </Typography>
    <Typography sx={{
      color: color || '#e2e8f0',
      fontSize: valueSize || 14,
      fontWeight: 700,
      fontFamily: '"JetBrains Mono", "SF Mono", "Fira Code", monospace',
    }}>
      {value}
    </Typography>
  </Box>
);

/** Thin vertical divider for the metrics ribbon */
const Sep = () => (
  <Box sx={{ width: '1px', height: 22, bgcolor: 'rgba(71,85,105,0.4)', flexShrink: 0, mx: 0.5 }} />
);

/** Trigger zone card below the chart */
const TriggerCard = ({ label, price, tolerance, direction, currentPrice, isActive }) => {
  const distance = currentPrice && price ? Math.abs(currentPrice - price) : null;
  const pct = currentPrice && price ? ((distance / currentPrice) * 100).toFixed(1) : null;
  const isClose = pct && parseFloat(pct) < 3;
  const isDanger = pct && parseFloat(pct) < 1.5;

  return (
    <Box sx={{
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      px: 2,
      py: 1,
      borderRadius: 1.5,
      background: isDanger
        ? 'linear-gradient(135deg, rgba(239,68,68,0.22) 0%, rgba(239,68,68,0.08) 100%)'
        : isClose
        ? 'linear-gradient(135deg, rgba(251,191,36,0.18) 0%, rgba(251,191,36,0.06) 100%)'
        : 'rgba(30,41,59,0.6)',
      border: `1px solid ${isDanger ? 'rgba(239,68,68,0.5)' : isClose ? 'rgba(251,191,36,0.3)' : 'rgba(71,85,105,0.3)'}`,
      animation: isDanger && isActive ? 'triggerFlash 1.5s infinite' : 'none',
      transition: 'all 0.3s ease',
    }}>
      {/* Left: label + price */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {direction === 'lower'
            ? <DownIcon sx={{ fontSize: 16, color: '#f87171' }} />
            : <UpIcon sx={{ fontSize: 16, color: '#f87171' }} />
          }
          <Typography sx={{ color: '#94a3b8', fontWeight: 600, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {label} Trigger
          </Typography>
        </Box>
        <Typography sx={{
          fontWeight: 800,
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 20,
          color: isDanger ? '#fca5a5' : isClose ? '#fbbf24' : '#e2e8f0',
          mt: 0.3,
        }}>
          ${price?.toLocaleString() || '—'}
        </Typography>
        <Typography sx={{ color: 'rgba(148,163,184,0.6)', fontSize: 11 }}>±{tolerance}</Typography>
      </Box>
      {/* Right: distance */}
      {distance != null && (
        <Box sx={{ textAlign: 'right' }}>
          <Typography sx={{
            color: isDanger ? '#f87171' : isClose ? '#fbbf24' : '#94a3b8',
            fontWeight: 700,
            fontSize: 14,
            fontFamily: '"JetBrains Mono", monospace',
          }}>
            {direction === 'lower' ? '↓' : '↑'} ${(distance / 1000).toFixed(1)}k
          </Typography>
          <Typography sx={{ color: '#64748b', fontSize: 12 }}>({pct}%)</Typography>
        </Box>
      )}
    </Box>
  );
};

/**  Tab panel wrapper */
const TabPanel = ({ children, value, index }) => (
  <Box
    role="tabpanel"
    hidden={value !== index}
    sx={{
      flex: 1, minHeight: 0, overflow: 'auto',
      display: value === index ? 'flex' : 'none',
      flexDirection: 'column',
    }}
  >
    {value === index && children}
  </Box>
);

/** Empty state */
const EmptyState = ({ icon, text }) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 1.5, py: 6 }}>
    {icon}
    <Typography sx={{ color: '#64748b', textAlign: 'center', maxWidth: 280, fontSize: 14 }}>{text}</Typography>
  </Box>
);

/** Count total legs */
const countLegs = (s) => s?.positions ? s.positions.reduce((t, pg) => t + (pg.legs?.length || 0), 0) : 0;

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN DASHBOARD
   ═══════════════════════════════════════════════════════════════════════════ */
const SSRAlgoDashboardRefactored = () => {
  // ── State ──
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState('checking');
  const [selectedSession, setSelectedSession] = useState(null);
  const [payoff, setPayoff] = useState(null);
  const [monitor, setMonitor] = useState(null);
  const [rightTab, setRightTab] = useState(0);
  const [actionLoading, setActionLoading] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);

  // ── Derived ──
  const sess = selectedSession;
  const status = sess?.status || 'IDLE';
  const isMonitoring = status === 'MONITORING';
  const isExecuting = status === 'EXECUTING_AUTO_LOOP';
  const isActive = ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES'].includes(status);
  const isPaused = status === 'PAUSED';
  const isStopped = status === 'STOPPED';
  const isIdle = status === 'IDLE';
  const isError = status === 'ERROR';

  const currentPrice = monitor?.last_price || payoff?.spot_price || null;
  const atmStrike = payoff?.atm_strike || sess?.positions?.[sess?.positions?.length - 1]?.atm_strike;
  const triggers = payoff?.adjustment_triggers || {};
  const maxLoss = payoff?.max_loss_points || {};
  const dwellStatus = monitor?.dwell_status || {};
  const inZone = !!dwellStatus.current_zone;

  const priceDir = useMemo(() => {
    if (!currentPrice || !atmStrike) return 0;
    return currentPrice > atmStrike ? 1 : currentPrice < atmStrike ? -1 : 0;
  }, [currentPrice, atmStrike]);

  const activeTime = useMemo(() => {
    if (!sess?.started_at) return null;
    const mins = Math.floor((Date.now() - new Date(sess.started_at)) / 60000);
    if (mins < 60) return `${mins}m`;
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sess?.started_at, monitor]);

  // ── Fetching ──
  const fetchSessionData = useCallback(async (sid) => {
    try {
      const [p, m] = await Promise.all([
        ssrAlgoService.getSessionPayoff(sid),
        ssrAlgoService.getMonitorStatus(sid),
      ]);
      if (p.success) setPayoff(p);
      if (m.success) setMonitor(m.monitor);
    } catch (e) { console.error(e); }
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const r = await ssrAlgoService.getSessions(false);
      if (r.success) {
        const list = r.sessions || [];
        setSessions(list);
        const priority = ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES', 'PAUSED', 'IDLE'];
        let best = null;
        for (const s of priority) { best = list.find(x => x.status === s); if (best) break; }
        if (!best && list.length > 0) best = list[0];
        if (best) {
          setSelectedSession(prev => {
            if (prev?.session_id === best.session_id) return best;
            if (!prev) fetchSessionData(best.session_id);
            return prev || best;
          });
        }
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [fetchSessionData]);

  const checkHealth = useCallback(async () => {
    try {
      const r = await ssrAlgoService.healthCheck();
      setHealthStatus(r.status || (r.success ? 'healthy' : 'error'));
    } catch { setHealthStatus('error'); }
  }, []);

  // ── Polling ──
  useEffect(() => {
    fetchSessions(); checkHealth();
    const a = setInterval(fetchSessions, 10000);
    const b = setInterval(checkHealth, 30000);
    return () => { clearInterval(a); clearInterval(b); };
  }, [fetchSessions, checkHealth]);

  useEffect(() => {
    if (!sess) return;
    const sid = sess.session_id;
    const rp = async () => { try { const r = await ssrAlgoService.getSessionPayoff(sid); if (r.success) setPayoff(r); } catch {} };
    const rm = async () => { try { const r = await ssrAlgoService.getMonitorStatus(sid); if (r.success) setMonitor(r.monitor); } catch {} };
    rp(); rm();
    const pi = setInterval(rp, payoff?.pending_orders_count > 0 ? 5000 : 30000);
    const mi = setInterval(rm, 15000);
    return () => { clearInterval(pi); clearInterval(mi); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sess?.session_id, payoff?.pending_orders_count]);

  useEffect(() => {
    if (!sess || (!isActive && !isPaused)) return;
    const sync = async () => { try { await ssrAlgoService.syncOrders(sess.session_id); } catch {} };
    sync();
    const i = setInterval(sync, 15000);
    return () => clearInterval(i);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sess?.session_id, isActive, isPaused]);

  // ── Actions ──
  const act = async (fn) => {
    setActionLoading(true);
    try { await fn(); fetchSessions(); }
    catch (e) { setError(e.message); }
    finally { setActionLoading(false); }
  };

  const handleSelectSession = async (s) => { setSelectedSession(s); setPayoff(null); setMonitor(null); await fetchSessionData(s.session_id); };
  const handleSessionCreated = () => { setConfigDrawerOpen(false); fetchSessions(); };
  const handlePause = () => act(() => ssrAlgoService.pauseSession(sess.session_id));
  const handleResume = () => act(() => ssrAlgoService.resumeSession(sess.session_id));
  const handleStart = () => act(() => ssrAlgoService.startSession(sess.session_id));
  const handleRetry = () => act(() => ssrAlgoService.retrySession(sess.session_id));
  const handleStop = () => { if (window.confirm('Stop this session?')) act(() => ssrAlgoService.stopSession(sess.session_id)); };
  const handleDelete = async () => {
    if (!window.confirm('Delete this session permanently?')) return;
    setActionLoading(true);
    try { await ssrAlgoService.deleteSession(sess.session_id); setSelectedSession(null); setPayoff(null); setMonitor(null); fetchSessions(); }
    catch (e) { setError(e.message); }
    finally { setActionLoading(false); }
  };

  // ── No sessions → creation flow ──
  if (!loading && sessions.length === 0) {
    return (
      <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'transparent' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', p: 1.5, borderBottom: '1px solid rgba(71,85,105,0.3)', background: 'rgba(15,23,42,0.9)' }}>
          <Typography sx={{ fontWeight: 800, fontSize: 18, background: 'linear-gradient(135deg,#38bdf8,#818cf8)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>🦋 SSR ALGO</Typography>
        </Box>
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
          <Box sx={{ maxWidth: 600, width: '100%' }}>
            <Typography sx={{ textAlign: 'center', mb: 3, fontSize: 22, fontWeight: 700, background: 'linear-gradient(135deg,#38bdf8,#818cf8)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Create Your First Session
            </Typography>
            <SSRAlgoConfigPanel onSessionCreated={handleSessionCreated} />
          </Box>
        </Box>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box sx={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress sx={{ color: '#38bdf8' }} />
      </Box>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════
     MAIN RENDER
     ═══════════════════════════════════════════════════════════════════════ */
  return (
    <Box sx={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: 'transparent',
      overflow: 'hidden',
      '@keyframes triggerFlash': {
        '0%,100%': { borderColor: 'rgba(239,68,68,0.5)' },
        '50%':     { borderColor: 'rgba(239,68,68,0.9)', boxShadow: '0 0 12px rgba(239,68,68,0.3)' },
      },
      '@keyframes liveDot': {
        '0%,100%': { opacity: 1 },
        '50%':     { opacity: 0.3 },
      },
    }}>

      {/* ═════════════ ROW 1: HEADER — 44px ═════════════ */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        height: 44,
        minHeight: 44,
        borderBottom: '1px solid rgba(71,85,105,0.3)',
        background: 'linear-gradient(180deg, rgba(15,23,42,0.95) 0%, rgba(15,23,42,0.8) 100%)',
        flexShrink: 0,
      }}>
        {/* Left: branding + badges */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography sx={{
            fontWeight: 800, fontSize: 16,
            background: 'linear-gradient(135deg,#38bdf8,#818cf8)',
            backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            userSelect: 'none',
          }}>
            🦋 SSR ALGO
          </Typography>
          <Chip
            size="small"
            icon={healthStatus === 'healthy'
              ? <HealthyIcon sx={{ fontSize: '14px !important' }} />
              : <ErrorIcon sx={{ fontSize: '14px !important' }} />}
            label={healthStatus === 'healthy' ? 'Connected' : 'Offline'}
            color={healthStatus === 'healthy' ? 'success' : 'error'}
            sx={{ fontWeight: 600, height: 24, fontSize: 12 }}
          />
          {isActive && (
            <Chip
              size="small"
              icon={<DotIcon sx={{ fontSize: '10px !important', animation: 'liveDot 1.5s infinite' }} />}
              label="LIVE"
              sx={{
                fontWeight: 800, height: 24, fontSize: 12,
                bgcolor: 'rgba(34,197,94,0.2)', color: '#4ade80',
                '& .MuiChip-icon': { color: '#4ade80' },
              }}
            />
          )}
          {/* Session selector when >1 */}
          {sessions.length > 1 && sessions.map(s => (
            <Chip key={s.session_id} size="small"
              label={`${s.underlying} ${s.expiry?.substring(0, 5) || ''}`}
              onClick={() => handleSelectSession(s)}
              sx={{
                height: 24, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                bgcolor: s.session_id === sess?.session_id ? 'rgba(129,140,248,0.3)' : 'rgba(71,85,105,0.2)',
                color: s.session_id === sess?.session_id ? '#a5b4fc' : '#94a3b8',
                border: s.session_id === sess?.session_id ? '1px solid rgba(129,140,248,0.5)' : '1px solid transparent',
                '&:hover': { bgcolor: 'rgba(129,140,248,0.15)' },
              }}
            />
          ))}
        </Box>

        {/* Right: action buttons */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {isIdle && <ActionBtn color="primary" icon={<PlayIcon />} label="Start" onClick={handleStart} disabled={actionLoading} />}
          {isError && <ActionBtn color="warning" icon={<RefreshIcon />} label="Retry" onClick={handleRetry} disabled={actionLoading} />}
          {isPaused && <ActionBtn color="success" icon={<PlayIcon />} label="Resume" onClick={handleResume} disabled={actionLoading} />}
          {isActive && <ActionBtn color="warning" icon={<PauseIcon />} label="Pause" onClick={handlePause} disabled={actionLoading} variant="outlined" />}
          {(isActive || isPaused) && <ActionBtn color="error" icon={<StopIcon />} label="Stop" onClick={handleStop} disabled={actionLoading} variant="outlined" />}
          {(isStopped || isIdle) && (
            <Tooltip title="Delete session"><IconButton size="small" onClick={handleDelete} disabled={actionLoading} sx={{ color: '#64748b', '&:hover': { color: '#f87171' } }}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
          )}
          <Sep />
          <Tooltip title="New Session / Config"><IconButton size="small" onClick={() => setConfigDrawerOpen(true)} sx={{ color: '#94a3b8', '&:hover': { color: '#38bdf8' } }}><SettingsIcon sx={{ fontSize: 20 }} /></IconButton></Tooltip>
          <Tooltip title="Refresh"><IconButton size="small" onClick={fetchSessions} sx={{ color: '#64748b', '&:hover': { color: '#38bdf8' } }}><RefreshIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
        </Box>
      </Box>

      {/* ═════════════ ROW 2: METRICS RIBBON — single horizontal row ═════════════ */}
      {sess && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          height: 44,
          minHeight: 44,
          px: 2,
          gap: 1.5,
          overflow: 'hidden',
          flexShrink: 0,
          borderBottom: `2px solid ${
            inZone ? 'rgba(239,68,68,0.6)' :
            isActive ? 'rgba(34,197,94,0.35)' :
            isPaused ? 'rgba(249,115,22,0.35)' :
            'rgba(71,85,105,0.3)'
          }`,
          background: inZone
            ? 'linear-gradient(180deg, rgba(239,68,68,0.1) 0%, transparent 100%)'
            : 'rgba(15,23,42,0.3)',
        }}>
          {/* Status dot + word */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
            <Box sx={{
              width: 9, height: 9, borderRadius: '50%',
              bgcolor: isActive ? '#22c55e' : isPaused ? '#f97316' : isStopped ? '#64748b' : isError ? '#ef4444' : '#3b82f6',
              boxShadow: isActive ? '0 0 6px #22c55e' : 'none',
              animation: isActive ? 'liveDot 2s infinite' : 'none',
            }} />
            <Typography sx={{
              fontWeight: 700, fontSize: 14,
              color: isActive ? '#4ade80' : isPaused ? '#fb923c' : isStopped ? '#94a3b8' : isError ? '#f87171' : '#60a5fa',
            }}>
              {inZone ? `⚠ ${dwellStatus.current_zone?.toUpperCase()} ZONE` :
               isMonitoring ? 'Monitoring' :
               isExecuting ? 'Executing' :
               isPaused ? 'Paused' :
               isStopped ? 'Stopped' :
               isError ? 'Error' : 'Ready'}
            </Typography>
            <Chip size="small" label={sess.underlying} sx={{ fontWeight: 700, height: 22, fontSize: 12, bgcolor: 'rgba(255,255,255,0.08)' }} />
          </Box>

          <Sep />
          <Metric label="Price" value={currentPrice ? `$${currentPrice.toLocaleString()}` : '—'} color={priceDir > 0 ? '#4ade80' : priceDir < 0 ? '#f87171' : '#e2e8f0'} valueSize={15} />
          <Sep />
          <Metric label="ATM" value={atmStrike ? `$${atmStrike.toLocaleString()}` : '—'} color="#a78bfa" />
          <Sep />
          {triggers.lower_trigger && <Metric label="Lower" value={`$${triggers.lower_trigger.toLocaleString()}`} color="#f87171" />}
          {triggers.upper_trigger && <Metric label="Upper" value={`$${triggers.upper_trigger.toLocaleString()}`} color="#f87171" />}
          {(triggers.lower_trigger || triggers.upper_trigger) && <Sep />}
          <Metric label="Rounds" value={`${sess.rounds_completed || 0}/${sess.auto_loop_rounds || 2}`} color="#818cf8" />
          <Metric label="Adj" value={`${sess.trigger_count || 0}`} color={sess.trigger_count > 0 ? '#fbbf24' : '#94a3b8'} />
          <Sep />
          <Metric label="Expiry" value={sess.expiry || '—'} color="#fbbf24" />
          <Metric label="Window" value={`${sess.start_time || '00:00'}–${sess.end_time || '23:59'}`} />
          {activeTime && <Metric label="Active" value={activeTime} />}
        </Box>
      )}

      {/* Dwell progress bar (only when in max loss zone) */}
      {inZone && (
        <Box sx={{ px: 2, py: 0.5, bgcolor: 'rgba(239,68,68,0.08)', flexShrink: 0 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
            <Typography sx={{ color: '#fca5a5', fontWeight: 600, fontSize: 12 }}>
              ⏱ In {dwellStatus.current_zone?.toUpperCase()} zone: {(dwellStatus.time_in_zone_minutes || 0).toFixed(1)} min
            </Typography>
            <Typography sx={{ color: '#f87171', fontSize: 12 }}>
              Trigger at {dwellStatus.dwell_threshold_minutes || 10} min
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.min(100, ((dwellStatus.time_in_zone_minutes || 0) / (dwellStatus.dwell_threshold_minutes || 10)) * 100)}
            sx={{
              height: 5, borderRadius: 3, bgcolor: 'rgba(239,68,68,0.2)',
              '& .MuiLinearProgress-bar': {
                bgcolor: ((dwellStatus.time_in_zone_minutes || 0) / (dwellStatus.dwell_threshold_minutes || 10)) > 0.8 ? '#ef4444' : '#f59e0b',
                borderRadius: 3,
              },
            }}
          />
        </Box>
      )}

      {/* ═════════════ ROW 3: MAIN CONTENT ═════════════ */}
      <Box sx={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>

        {/* ─── LEFT: CHART HERO (62%) ─── */}
        <Box sx={{
          flex: '0 0 62%',
          display: 'flex', flexDirection: 'column', minHeight: 0,
          borderRight: '1px solid rgba(71,85,105,0.3)',
        }}>
          {/* Chart */}
          <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
            {sess && payoff?.payoff_curve?.length > 0 ? (
              <SSRAlgoPayoffChart
                payoffCurve={payoff.payoff_curve}
                maxLossPoints={payoff.max_loss_points || {}}
                adjustmentTriggers={payoff.adjustment_triggers || {}}
                breakevens={payoff.breakevens || []}
                spotPrice={payoff.spot_price || 0}
                currentPrice={currentPrice || payoff.spot_price || 0}
                height="100%"
                loading={false}
              />
            ) : (
              <EmptyState
                icon={<ChartIcon sx={{ fontSize: 56, color: 'rgba(129,140,248,0.25)' }} />}
                text={!sess ? 'No session selected' :
                  isIdle ? 'Start session to see the payoff diagram' :
                  isExecuting ? 'Placing orders on exchange…' :
                  'Loading payoff data…'}
              />
            )}
          </Box>

          {/* Bottom strip: stats + trigger cards */}
          <Box sx={{ flexShrink: 0, borderTop: '1px solid rgba(71,85,105,0.3)', background: 'rgba(15,23,42,0.85)' }}>
            {/* Compact stats row */}
            {payoff && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 2, py: 0.8, borderBottom: '1px solid rgba(71,85,105,0.2)', flexWrap: 'wrap' }}>
                <Stat label="Net Premium" value={`$${payoff.net_premium?.toFixed(2) || '0'}`} color={payoff.net_premium >= 0 ? '#4ade80' : '#f87171'} />
                <Stat label="Max Profit" value={`$${maxLoss.max_profit_value?.toFixed(2) || '—'}`} color="#4ade80" />
                <Stat label="Max Loss" value={`$${maxLoss.max_loss_value?.toFixed(2) || '—'}`} color="#f87171" />
                {payoff.breakevens?.map((be, i) => (
                  <Stat key={i} label={`BE ${i + 1}`} value={`$${be.toLocaleString()}`} color="#fbbf24" />
                ))}
                <Stat label="Positions" value={`${payoff.position_count || 0}`} color="#818cf8" />
              </Box>
            )}
            {/* Trigger zone cards */}
            {(triggers.lower_trigger || triggers.upper_trigger) && (
              <Box sx={{ display: 'flex', gap: 1.5, p: 1.5, alignItems: 'stretch' }}>
                {triggers.lower_trigger && (
                  <TriggerCard label="Lower" price={triggers.lower_trigger} tolerance={triggers.tolerance || 100} direction="lower" currentPrice={currentPrice} isActive={isActive} />
                )}
                {triggers.upper_trigger && (
                  <TriggerCard label="Upper" price={triggers.upper_trigger} tolerance={triggers.tolerance || 100} direction="upper" currentPrice={currentPrice} isActive={isActive} />
                )}
                {/* Dwell config */}
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', px: 2, borderLeft: '1px solid rgba(71,85,105,0.25)' }}>
                  <Typography sx={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase', fontWeight: 600 }}>Dwell</Typography>
                  <Typography sx={{ fontWeight: 700, fontSize: 18, fontFamily: '"JetBrains Mono", monospace', color: '#e2e8f0' }}>
                    {sess?.dwell_time_minutes || 10}m
                  </Typography>
                </Box>
              </Box>
            )}
          </Box>
        </Box>

        {/* ─── RIGHT: TABBED PANEL (38%) ─── */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0 }}>
          <Box sx={{ borderBottom: '1px solid rgba(71,85,105,0.3)', flexShrink: 0, bgcolor: 'rgba(15,23,42,0.5)' }}>
            <Tabs
              value={rightTab}
              onChange={(_, v) => setRightTab(v)}
              variant="fullWidth"
              sx={{
                minHeight: 38,
                '& .MuiTab-root': {
                  minHeight: 38, fontSize: 13, fontWeight: 600,
                  textTransform: 'none', py: 0.5, color: '#94a3b8',
                  '&.Mui-selected': { color: '#a5b4fc' },
                },
                '& .MuiTabs-indicator': { bgcolor: '#818cf8', height: 2 },
              }}
            >
              <Tab label="📊 Positions" />
              <Tab label="📋 Activity" />
              <Tab label="⚡ History" />
            </Tabs>
          </Box>

          <TabPanel value={rightTab} index={0}>
            <Box sx={{ flex: 1, overflow: 'auto', p: 1.5 }}>
              {sess?.positions?.length > 0 ? (
                <SSRAlgoPositionsTable positions={sess.positions} filledOrders={sess.filled_orders} showHeader={true} compact={true} />
              ) : (
                <EmptyState
                  icon={<AdjustIcon sx={{ fontSize: 36, color: 'rgba(129,140,248,0.3)' }} />}
                  text={isIdle ? 'Positions will appear after the session starts' : isExecuting ? 'Placing orders…' : 'No positions yet'}
                />
              )}
            </Box>
          </TabPanel>

          <TabPanel value={rightTab} index={1}>
            <Box sx={{ flex: 1, minHeight: 0 }}>
              {sess ? (
                <SSRAlgoLogPanel sessionId={sess.session_id} height="100%" compact={true} showHeader={false} refreshInterval={2000} />
              ) : (
                <EmptyState text="No session selected" />
              )}
            </Box>
          </TabPanel>

          <TabPanel value={rightTab} index={2}>
            <Box sx={{ flex: 1, overflow: 'auto', p: 1.5 }}>
              {sess ? <SSRAlgoTriggerHistory session={sess} compact={true} /> : <EmptyState text="No triggers" />}
            </Box>
          </TabPanel>
        </Box>
      </Box>

      {/* ═══════ ERROR ALERT ═══════ */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 1300, maxWidth: 500, boxShadow: '0 8px 32px rgba(0,0,0,0.5)', fontSize: 14 }}>
          {error}
        </Alert>
      )}

      {/* ═══════ CONFIG DRAWER ═══════ */}
      <Drawer
        anchor="right"
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
        PaperProps={{ sx: { width: 440, bgcolor: 'rgba(15,23,42,0.98)', borderLeft: '1px solid rgba(129,140,248,0.3)', backdropFilter: 'blur(12px)' } }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 2, borderBottom: '1px solid rgba(71,85,105,0.3)' }}>
            <Typography sx={{ fontWeight: 700, color: '#38bdf8', fontSize: 16 }}>⚙️ New Session</Typography>
            <IconButton size="small" onClick={() => setConfigDrawerOpen(false)} sx={{ color: '#94a3b8' }}><CloseIcon /></IconButton>
          </Box>
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <SSRAlgoConfigPanel onSessionCreated={handleSessionCreated} />
          </Box>
        </Box>
      </Drawer>

      {actionLoading && <LinearProgress sx={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 1400, height: 3 }} />}
    </Box>
  );
};

/* ═══════════════════════════════════════════════════════════════════════════
   SMALL HELPERS (defined after main component to keep it clean)
   ═══════════════════════════════════════════════════════════════════════════ */

/** Action button for header bar */
const ActionBtn = ({ color, icon, label, onClick, disabled, variant = 'contained' }) => (
  <Button
    size="small" variant={variant} color={color}
    startIcon={icon} onClick={onClick} disabled={disabled}
    sx={{ height: 30, fontSize: 13, textTransform: 'none', fontWeight: 700, minWidth: 'auto', px: 1.5 }}
  >
    {label}
  </Button>
);

/** Stat cell for the strip below the chart */
const Stat = ({ label, value, color }) => (
  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
    <Typography sx={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{label}</Typography>
    <Typography sx={{ fontWeight: 700, fontSize: 14, fontFamily: '"JetBrains Mono", monospace', color }}>{value}</Typography>
  </Box>
);

export default SSRAlgoDashboardRefactored;
