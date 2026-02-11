/**
 * SSR Algo Dashboard - REFACTORED LAYOUT
 * 
 * LAYOUT ARCHITECTURE:
 * - CSS Grid with defined rows (no overlaps)
 * - Resizable panels with localStorage persistence
 * - Internal scrolling for logs/tables
 * - Collapse config panel when session active
 * 
 * Created: February 4, 2026
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Collapse,
  Paper,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import SSRAlgoConfigPanel from './SSRAlgoConfigPanel';
import SSRAlgoSessionCard from './SSRAlgoSessionCard';
import SSRAlgoPayoffChart from './SSRAlgoPayoffChart';
import SSRAlgoPositionsTable from './SSRAlgoPositionsTable';
import SSRAlgoStatusBanner from './SSRAlgoStatusBanner';
import SSRAlgoTriggerHistory from './SSRAlgoTriggerHistory';
import SSRAlgoLogPanel from './SSRAlgoLogPanel';
import ssrAlgoService from './ssrAlgoService';

// Resizable divider component
const ResizableDivider = ({ onResize, orientation = 'horizontal' }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging && onResize) {
        onResize(e);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, onResize]);

  return (
    <Box
      onMouseDown={handleMouseDown}
      sx={{
        cursor: orientation === 'horizontal' ? 'ns-resize' : 'ew-resize',
        height: orientation === 'horizontal' ? '8px' : '100%',
        width: orientation === 'horizontal' ? '100%' : '8px',
        bgcolor: isDragging ? 'rgba(129, 140, 248, 0.3)' : 'transparent',
        transition: 'background-color 0.2s',
        position: 'relative',
        '&:hover': {
          bgcolor: 'rgba(129, 140, 248, 0.2)',
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: orientation === 'horizontal' ? '40px' : '4px',
          height: orientation === 'horizontal' ? '4px' : '40px',
          bgcolor: 'rgba(148, 163, 184, 0.4)',
          borderRadius: '2px',
        }
      }}
    />
  );
};

const SSRAlgoDashboardRefactored = () => {
  // State
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState('checking');
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedPayoff, setSelectedPayoff] = useState(null);
  const [selectedMonitorStatus, setSelectedMonitorStatus] = useState(null);
  const [configExpanded, setConfigExpanded] = useState(true);
  
  // Panel heights (stored in localStorage)
  const [payoffHeight, setPayoffHeight] = useState(() => {
    const stored = localStorage.getItem('ssrAlgo_payoffHeight');
    return stored ? parseInt(stored) : 400;
  });
  const [logHeight, setLogHeight] = useState(() => {
    const stored = localStorage.getItem('ssrAlgo_logHeight');
    return stored ? parseInt(stored) : 300;
  });

  const containerRef = useRef(null);
  const payoffRef = useRef(null);
  const logRef = useRef(null);

  // Active session check
  const hasActiveSession = sessions.some(s => ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES'].includes(s.status));

  // Auto-collapse config when session becomes active
  useEffect(() => {
    if (hasActiveSession) {
      setConfigExpanded(false);
    }
  }, [hasActiveSession]);

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const result = await ssrAlgoService.getSessions(false);
      if (result.success) {
        const fetched = result.sessions || [];
        setSessions(fetched);
        
        // Auto-select: prioritize MONITORING > EXECUTING > PAUSED > IDLE > most recent
        const priority = ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES', 'PAUSED', 'IDLE'];
        let best = null;
        for (const status of priority) {
          best = fetched.find(s => s.status === status);
          if (best) break;
        }
        if (!best && fetched.length > 0) best = fetched[0];
        
        if (best) {
          // Always update selectedSession with fresh data from fetch
          if (selectedSession && selectedSession.session_id === best.session_id) {
            setSelectedSession(best);
          } else if (!selectedSession) {
            // First load — auto-select and fetch payoff/monitor
            handleSelectSession(best);
          }
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedSession]);

  // Check health
  const checkHealth = useCallback(async () => {
    try {
      const result = await ssrAlgoService.healthCheck();
      setHealthStatus(result.status || (result.success ? 'healthy' : 'error'));
    } catch (err) {
      setHealthStatus('error');
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    checkHealth();
    const interval = setInterval(fetchSessions, 10000);
    const healthInterval = setInterval(checkHealth, 30000);
    return () => {
      clearInterval(interval);
      clearInterval(healthInterval);
    };
  }, [fetchSessions, checkHealth]);

  // Auto-refresh payoff & monitor for selected session
  useEffect(() => {
    if (!selectedSession) return;
    
    const refreshPayoff = async () => {
      try {
        const result = await ssrAlgoService.getSessionPayoff(selectedSession.session_id);
        if (result.success) {
          setSelectedPayoff(result);
        }
      } catch (err) {
        console.error('Payoff refresh failed:', err);
      }
    };

    const refreshMonitor = async () => {
      try {
        const result = await ssrAlgoService.getMonitorStatus(selectedSession.session_id);
        if (result.success) {
          setSelectedMonitorStatus(result.monitor);
        }
      } catch (err) {
        // Silent fail
      }
    };

    refreshPayoff();
    refreshMonitor();
    
    const payoffInterval = setInterval(refreshPayoff, 30000);
    const monitorInterval = setInterval(refreshMonitor, 5000);
    
    return () => {
      clearInterval(payoffInterval);
      clearInterval(monitorInterval);
    };
  }, [selectedSession]);

  const handleSessionCreated = (sessionId) => {
    fetchSessions();
  };

  const handleSelectSession = async (session) => {
    setSelectedSession(session);
    try {
      const payoffResult = await ssrAlgoService.getSessionPayoff(session.session_id);
      if (payoffResult.success) {
        setSelectedPayoff(payoffResult);
      }
      const monitorResult = await ssrAlgoService.getMonitorStatus(session.session_id);
      if (monitorResult.success) {
        setSelectedMonitorStatus(monitorResult.monitor);
      }
    } catch (err) {
      console.error('Failed to fetch session data:', err);
    }
  };

  // Resize handlers
  const handlePayoffResize = useCallback((e) => {
    if (!payoffRef.current || !containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newHeight = Math.max(250, Math.min(600, e.clientY - payoffRef.current.getBoundingClientRect().top));
    setPayoffHeight(newHeight);
    localStorage.setItem('ssrAlgo_payoffHeight', newHeight.toString());
  }, []);

  const handleLogResize = useCallback((e) => {
    if (!logRef.current || !containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newHeight = Math.max(150, Math.min(500, e.clientY - logRef.current.getBoundingClientRect().top));
    setLogHeight(newHeight);
    localStorage.setItem('ssrAlgo_logHeight', newHeight.toString());
  }, []);

  const activeSessions = sessions.filter(s => ['IDLE', 'MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES', 'PAUSED', 'ERROR'].includes(s.status));
  const stoppedSessions = sessions.filter(s => s.status === 'STOPPED');

  return (
    <Box
      ref={containerRef}
      sx={{
        height: '100vh',
        display: 'grid',
        gridTemplateRows: 'auto auto 1fr auto',
        gridTemplateColumns: '1fr',
        gap: 0.5,
        p: 1,
        bgcolor: 'transparent',
        overflow: 'hidden',
      }}
    >
      {/* ROW 1: Header (fixed) */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        pb: 0.5,
        borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h6" sx={{
            fontWeight: 700,
            background: 'linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            fontSize: '1.1rem',
          }}>
            <span style={{ fontSize: '1.3rem' }}>🦋</span>
            SSR ALGO
          </Typography>
          <Chip
            size="small"
            icon={healthStatus === 'healthy' ? <HealthyIcon /> : healthStatus === 'checking' ? <RefreshIcon /> : <ErrorIcon />}
            label={healthStatus === 'healthy' ? 'Connected' : healthStatus === 'checking' ? 'Checking...' : 'Error'}
            color={healthStatus === 'healthy' ? 'success' : healthStatus === 'checking' ? 'default' : 'error'}
            sx={{ fontWeight: 600, height: 22, fontSize: '0.7rem' }}
          />
        </Box>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchSessions} disabled={loading} size="small">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* ROW 2: Status Banner (when session selected) */}
      {selectedSession && (
        <Box>
          <SSRAlgoStatusBanner
            session={selectedSession}
            monitorStatus={selectedMonitorStatus}
            payoffData={selectedPayoff}
            currentPrice={selectedMonitorStatus?.last_price || selectedPayoff?.spot_price || null}
          />
        </Box>
      )}

      {/* ROW 3: Main Content (flex grow) - CSS Grid within */}
      <Box sx={{
        display: 'grid',
        gridTemplateColumns: '400px 1fr',
        gap: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}>
        {/* LEFT COLUMN: Config + Sessions */}
        <Box sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          minHeight: 0,
        }}>
          {/* Config Panel (collapsible) */}
          <Paper sx={{
            bgcolor: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(71, 85, 105, 0.3)',
            borderRadius: 2,
            overflow: 'hidden',
          }}>
            <Box
              onClick={() => setConfigExpanded(!configExpanded)}
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                p: 1,
                cursor: 'pointer',
                bgcolor: 'rgba(59, 130, 246, 0.1)',
                '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.15)' },
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#60a5fa' }}>
                ⚙️ Configuration
              </Typography>
              {configExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </Box>
            <Collapse in={configExpanded}>
              <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                <SSRAlgoConfigPanel onSessionCreated={handleSessionCreated} />
              </Box>
            </Collapse>
          </Paper>

          {/* Sessions List */}
          <Paper sx={{
            flex: 1,
            bgcolor: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(71, 85, 105, 0.3)',
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}>
            <Box sx={{ p: 1, borderBottom: '1px solid rgba(71, 85, 105, 0.2)' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#94a3b8' }}>
                📊 Sessions ({sessions.length})
              </Typography>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
              {activeSessions.length > 0 && activeSessions.map(session => (
                <Box
                  key={session.session_id}
                  onClick={() => handleSelectSession(session)}
                  sx={{
                    cursor: 'pointer',
                    border: selectedSession?.session_id === session.session_id ? '2px solid #818cf8' : '2px solid transparent',
                    borderRadius: 2,
                    mb: 0.5,
                  }}
                >
                  <SSRAlgoSessionCard
                    session={session}
                    onRefresh={fetchSessions}
                    compact={true}
                  />
                </Box>
              ))}
              {stoppedSessions.length > 0 && (
                <>
                  <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mt: 1, mb: 0.5, pl: 1, fontWeight: 600 }}>
                    STOPPED ({stoppedSessions.length})
                  </Typography>
                  {stoppedSessions.map(session => (
                    <Box
                      key={session.session_id}
                      onClick={() => handleSelectSession(session)}
                      sx={{
                        cursor: 'pointer',
                        border: selectedSession?.session_id === session.session_id ? '2px solid #818cf8' : '2px solid transparent',
                        borderRadius: 2,
                        mb: 0.5,
                        opacity: 0.7,
                      }}
                    >
                      <SSRAlgoSessionCard
                        session={session}
                        onRefresh={fetchSessions}
                        compact={true}
                      />
                    </Box>
                  ))}
                </>
              )}
              {sessions.length === 0 && (
                <Box sx={{ textAlign: 'center', py: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    No sessions yet. Create one using the config panel above.
                  </Typography>
                </Box>
              )}
            </Box>
          </Paper>
        </Box>

        {/* RIGHT COLUMN: Payoff + Logs + Tables */}
        <Box sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
          minHeight: 0,
        }}>
          {/* Payoff Chart (resizable) */}
          <Paper
            ref={payoffRef}
            sx={{
              height: `${payoffHeight}px`,
              bgcolor: 'rgba(30, 41, 59, 0.9)',
              border: '1px solid rgba(129, 140, 248, 0.2)',
              borderRadius: 2,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ p: 1, borderBottom: '1px solid rgba(71, 85, 105, 0.2)', display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle2" sx={{ color: '#818cf8', fontWeight: 600 }}>
                📈 Payoff Diagram
              </Typography>
              {selectedSession?.status === 'MONITORING' && (
                <Chip size="small" label="● LIVE" sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(34, 197, 94, 0.2)', color: '#22c55e' }} />
              )}
            </Box>
            <Box sx={{ flex: 1, p: 1, minHeight: 0 }}>
              {selectedSession && selectedPayoff?.payoff_curve?.length > 0 ? (
                <SSRAlgoPayoffChart
                  payoffCurve={selectedPayoff?.payoff_curve || []}
                  maxLossPoints={selectedPayoff?.max_loss_points || {}}
                  adjustmentTriggers={selectedPayoff?.adjustment_triggers || {}}
                  breakevens={selectedPayoff?.breakevens || []}
                  spotPrice={selectedPayoff?.spot_price || 0}
                  currentPrice={selectedMonitorStatus?.last_price || selectedPayoff?.spot_price || 0}
                  height="100%"
                  loading={false}
                />
              ) : selectedSession ? (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 2 }}>
                  <Typography variant="h6" sx={{ color: 'rgba(148, 163, 184, 0.5)', fontWeight: 700 }}>
                    🦋
                  </Typography>
                  <Typography color="text.secondary" variant="body2">
                    {selectedSession.status === 'IDLE' ? 'Click "Start" to begin — payoff diagram will appear after execution' :
                     selectedSession.status === 'SELECTING_STRIKES' ? 'Selecting strikes...' :
                     selectedSession.status === 'EXECUTING_AUTO_LOOP' ? 'Executing orders — payoff diagram will appear shortly...' :
                     selectedSession.status === 'STOPPED' && selectedSession.positions?.length === 0 ? 'Session stopped without positions' :
                     selectedSession.status === 'STOPPED' ? 'Session stopped — positions data below' :
                     selectedSession.status === 'ERROR' ? `Error: ${selectedSession.error || 'Unknown'}` :
                     'Loading payoff data...'}
                  </Typography>
                  {selectedSession.status === 'IDLE' && (
                    <Box sx={{ mt: 1, p: 1.5, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2, border: '1px solid rgba(59, 130, 246, 0.2)', textAlign: 'center', maxWidth: 400 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Session Config</Typography>
                      <Typography variant="body2" sx={{ color: '#60a5fa', fontWeight: 600 }}>
                        {selectedSession.underlying} • Expiry: {selectedSession.expiry} • {selectedSession.auto_loop_rounds} rounds • {selectedSession.order_type?.toUpperCase()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        OTM Buy: {selectedSession.strike_config?.otm_buy_percent_min}-{selectedSession.strike_config?.otm_buy_percent_max}% • Far OTM: {selectedSession.strike_config?.far_otm_percent_min}-{selectedSession.strike_config?.far_otm_percent_max}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        Time Window: {selectedSession.start_time || '15:00'} - {selectedSession.end_time || '21:00'} • Dwell: {selectedSession.dwell_time_minutes || 10}min
                      </Typography>
                    </Box>
                  )}
                  {selectedSession.status === 'STOPPED' && selectedSession.positions?.length > 0 && (
                    <Box sx={{ mt: 1, p: 1.5, bgcolor: 'rgba(239, 68, 68, 0.1)', borderRadius: 2, border: '1px solid rgba(239, 68, 68, 0.2)', textAlign: 'center', maxWidth: 400 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Session Summary</Typography>
                      <Typography variant="body2" sx={{ color: '#fca5a5', fontWeight: 600 }}>
                        {selectedSession.positions.length} position group(s) • {selectedSession.rounds_completed || 0} rounds
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        Stopped: {selectedSession.stop_reason || 'Manual stop'}
                      </Typography>
                      {selectedSession.net_premium && (
                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: selectedSession.net_premium > 0 ? '#4ade80' : '#f87171' }}>
                          Net Premium: ${selectedSession.net_premium?.toFixed(2)}
                        </Typography>
                      )}
                    </Box>
                  )}
                  {selectedSession.status === 'ERROR' && (
                    <Box sx={{ mt: 1, p: 1.5, bgcolor: 'rgba(239, 68, 68, 0.15)', borderRadius: 2, border: '1px solid rgba(239, 68, 68, 0.3)', textAlign: 'center', maxWidth: 400 }}>
                      <Typography variant="body2" sx={{ color: '#fca5a5' }}>
                        {selectedSession.error || 'Unknown error'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        Click "Retry" in the session card to try again
                      </Typography>
                    </Box>
                  )}
                </Box>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Typography color="text.secondary">Select a session</Typography>
                </Box>
              )}
            </Box>
          </Paper>

          <ResizableDivider onResize={handlePayoffResize} orientation="horizontal" />

          {/* Activity Logs (resizable) */}
          <Paper
            ref={logRef}
            sx={{
              height: `${logHeight}px`,
              bgcolor: 'rgba(30, 41, 59, 0.9)',
              border: '1px solid rgba(71, 85, 105, 0.2)',
              borderRadius: 2,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ p: 1, borderBottom: '1px solid rgba(71, 85, 105, 0.2)' }}>
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                📋 Activity Logs
              </Typography>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {selectedSession ? (
                <SSRAlgoLogPanel
                  sessionId={selectedSession.session_id}
                  height="100%"
                  compact={true}
                  showHeader={false}
                  refreshInterval={2000}
                />
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Typography color="text.secondary" variant="caption">Select a session to view logs</Typography>
                </Box>
              )}
            </Box>
          </Paper>

          <ResizableDivider onResize={handleLogResize} orientation="horizontal" />

          {/* Positions & Trigger History (fill remaining) */}
          <Box sx={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: '2fr 1fr',
            gap: 1,
            minHeight: 0,
          }}>
            {/* Positions */}
            <Paper sx={{
              bgcolor: 'rgba(30, 41, 59, 0.9)',
              border: '1px solid rgba(71, 85, 105, 0.2)',
              borderRadius: 2,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
              <Box sx={{ p: 1, borderBottom: '1px solid rgba(71, 85, 105, 0.2)' }}>
                <Typography variant="subtitle2" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                  🎯 Positions
                </Typography>
              </Box>
              <Box sx={{ flex: 1, overflow: 'auto', p: 1, minHeight: 0 }}>
                {selectedSession && selectedSession.positions?.length > 0 ? (
                  <SSRAlgoPositionsTable
                    positions={selectedSession.positions}
                    showHeader={true}
                    compact={true}
                  />
                ) : selectedSession ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 0.5 }}>
                    <Typography color="text.secondary" variant="caption">
                      {selectedSession?.status === 'IDLE' ? 'Positions will appear after session starts' :
                       selectedSession?.status === 'EXECUTING_AUTO_LOOP' ? 'Placing orders...' :
                       selectedSession?.status === 'STOPPED' ? 'No positions were opened' :
                       selectedSession?.status === 'ERROR' ? 'Execution failed — no positions' :
                       'No positions'}
                    </Typography>
                    {selectedSession?.status === 'IDLE' && (
                      <Typography color="text.secondary" variant="caption" sx={{ opacity: 0.6, fontSize: '0.65rem' }}>
                        Modified Iron Butterfly: Sell 1 ATM CE + Sell 1 ATM PE + Buy 2 OTM (CE+PE) + Sell 1 Far OTM (CE+PE)
                      </Typography>
                    )}
                  </Box>
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <Typography color="text.secondary" variant="caption">Select a session</Typography>
                  </Box>
                )}
              </Box>
            </Paper>

            {/* Trigger History */}
            <Paper sx={{
              bgcolor: 'rgba(30, 41, 59, 0.9)',
              border: '1px solid rgba(71, 85, 105, 0.2)',
              borderRadius: 2,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
              <Box sx={{ p: 1, borderBottom: '1px solid rgba(71, 85, 105, 0.2)' }}>
                <Typography variant="subtitle2" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                  ⚡ Triggers
                </Typography>
              </Box>
              <Box sx={{ flex: 1, overflow: 'auto', p: 1, minHeight: 0 }}>
                {selectedSession ? (
                  <SSRAlgoTriggerHistory session={selectedSession} compact={true} />
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <Typography color="text.secondary" variant="caption">No triggers</Typography>
                  </Box>
                )}
              </Box>
            </Paper>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SSRAlgoDashboardRefactored;
