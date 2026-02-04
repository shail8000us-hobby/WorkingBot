/**
 * SSR Algo Dashboard
 * 
 * Main dashboard for SSR Algo - automated position adjustment algorithm.
 * Displays configuration panel, active sessions, and historical sessions.
 * 
 * Created: February 2, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Tabs,
  Tab,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  IconButton,
  Tooltip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  History as HistoryIcon,
  Settings as SettingsIcon,
  ShowChart as ChartIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  DeleteSweep as DeleteSweepIcon,
} from '@mui/icons-material';
import SSRAlgoConfigPanel from './SSRAlgoConfigPanel';
import SSRAlgoSessionCard from './SSRAlgoSessionCard';
import SSRAlgoPayoffChart from './SSRAlgoPayoffChart';
import SSRAlgoPositionsTable from './SSRAlgoPositionsTable';
import SSRAlgoStatusBanner from './SSRAlgoStatusBanner';
import SSRAlgoTriggerHistory from './SSRAlgoTriggerHistory';
import SSRAlgoLogPanel from './SSRAlgoLogPanel';
import ssrAlgoService from './ssrAlgoService';

/**
 * Main SSR Algo Dashboard
 */
const SSRAlgoDashboard = () => {
  // State
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tabValue, setTabValue] = useState(0);
  const [healthStatus, setHealthStatus] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedPayoff, setSelectedPayoff] = useState(null);
  const [selectedMonitorStatus, setSelectedMonitorStatus] = useState(null);
  
  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const result = await ssrAlgoService.getSessions(false);
      if (result.success) {
        setSessions(result.sessions || []);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const result = await ssrAlgoService.healthCheck();
      setHealthStatus(result.success ? 'healthy' : 'error');
    } catch (err) {
      setHealthStatus('error');
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSessions();
    checkHealth();
    
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchSessions();
    }, 10000);
    
    return () => clearInterval(interval);
  }, [fetchSessions, checkHealth]);

  // Auto-select session for payoff display - prioritize MONITORING, then most recent
  useEffect(() => {
    if (sessions.length === 0) return;
    if (selectedSession) return; // Don't override manual selection
    
    // Priority: 1) MONITORING session, 2) Any active session, 3) Most recent session
    const monitoringSession = sessions.find(s => s.status === 'MONITORING');
    const activeSession = sessions.find(s => 
      ['IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'].includes(s.status)
    );
    const mostRecentSession = sessions[0]; // Sessions are sorted by created_at desc
    
    const sessionToSelect = monitoringSession || activeSession || mostRecentSession;
    if (sessionToSelect) {
      handleSelectSession(sessionToSelect);
    }
  }, [sessions]);

  // Auto-refresh payoff for selected session every 30 seconds
  useEffect(() => {
    if (!selectedSession || selectedSession.status !== 'MONITORING') return;
    
    const payoffInterval = setInterval(async () => {
      try {
        const result = await ssrAlgoService.getSessionPayoff(selectedSession.session_id);
        if (result.success) {
          setSelectedPayoff(result);
        }
      } catch (err) {
        console.error('Failed to refresh payoff:', err);
      }
    }, 30000);
    
    return () => clearInterval(payoffInterval);
  }, [selectedSession]);

  // Auto-refresh monitor status for selected session every 5 seconds (for current price updates)
  useEffect(() => {
    if (!selectedSession) return;
    
    const monitorInterval = setInterval(async () => {
      try {
        const result = await ssrAlgoService.getMonitorStatus(selectedSession.session_id);
        if (result.success) {
          setSelectedMonitorStatus(result.monitor);
        }
      } catch (err) {
        // Silent fail for monitor refresh
      }
    }, 5000);
    
    return () => clearInterval(monitorInterval);
  }, [selectedSession]);

  // Filter sessions by tab
  const activeSessions = sessions.filter(s => 
    ['IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'].includes(s.status)
  );
  const historicalSessions = sessions.filter(s => s.status === 'STOPPED');

  // Handle session created
  const handleSessionCreated = (session) => {
    setSessions(prev => [session, ...prev]);
    setTabValue(0); // Switch to active tab
  };

  // Handle session deleted
  const handleSessionDeleted = (sessionId) => {
    setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    if (selectedSession?.session_id === sessionId) {
      setSelectedSession(null);
      setSelectedPayoff(null);
    }
  };

  // Delete all IDLE (Ready to Start) sessions
  const handleDeleteAllIdle = async () => {
    const idleSessions = sessions.filter(s => s.status === 'IDLE');
    if (idleSessions.length === 0) return;
    
    if (!window.confirm(`Delete ${idleSessions.length} "Ready to Start" sessions?`)) return;
    
    for (const session of idleSessions) {
      try {
        await ssrAlgoService.deleteSession(session.session_id);
      } catch (err) {
        console.error('Failed to delete session:', session.session_id, err);
      }
    }
    fetchSessions();
  };

  // Delete all stopped (history) sessions
  const handleDeleteAllHistory = async () => {
    if (historicalSessions.length === 0) return;
    
    if (!window.confirm(`Delete ${historicalSessions.length} history sessions?`)) return;
    
    for (const session of historicalSessions) {
      try {
        await ssrAlgoService.deleteSession(session.session_id);
      } catch (err) {
        console.error('Failed to delete session:', session.session_id, err);
      }
    }
    fetchSessions();
  };

  // Handle session selection for payoff display
  const handleSelectSession = async (session) => {
    setSelectedSession(session);
    try {
      // Fetch payoff data
      const payoffResult = await ssrAlgoService.getSessionPayoff(session.session_id);
      if (payoffResult.success) {
        setSelectedPayoff(payoffResult);
      }
      // Fetch monitor status
      const monitorResult = await ssrAlgoService.getMonitorStatus(session.session_id);
      if (monitorResult.success) {
        setSelectedMonitorStatus(monitorResult.monitor);
      }
    } catch (err) {
      console.error('Failed to fetch session data:', err);
    }
  };

  return (
    <Box sx={{ 
      pt: 0, 
      pb: 1, 
      px: { xs: 1, md: 2 },
      height: '100vh',
      backgroundColor: 'transparent',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header - Compact */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        mb: 1,
        pb: 1,
        borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
        flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography 
            variant="h5" 
            component="h1" 
            sx={{ 
              fontWeight: 700,
              background: 'linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              display: 'flex',
              alignItems: 'center',
              gap: 1
            }}
          >
            <span style={{ fontSize: '1.5rem' }}>🦋</span>
            SSR ALGO
          </Typography>
          <Chip 
            size="small"
            icon={healthStatus === 'healthy' ? <HealthyIcon /> : <ErrorIcon />}
            label={healthStatus === 'healthy' ? 'Connected' : 'Error'}
            color={healthStatus === 'healthy' ? 'success' : 'error'}
            sx={{ fontWeight: 600, height: 24 }}
          />
          <Typography 
            variant="caption" 
            sx={{ 
              color: 'rgba(148, 163, 184, 0.7)',
              fontSize: '0.75rem',
            }}
          >
            Modified Iron Butterfly — Auto-adjusting
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {selectedSession && selectedSession.status === 'MONITORING' && (
            <Chip 
              size="small"
              label="● LIVE"
              sx={{ 
                fontWeight: 700, 
                height: 24,
                bgcolor: 'rgba(34, 197, 94, 0.2)',
                color: '#22c55e',
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.6 },
                },
              }}
            />
          )}
          <Tooltip title="Refresh">
            <IconButton 
              onClick={fetchSessions} 
              disabled={loading}
              size="small"
              sx={{ 
                border: '1px solid rgba(148, 163, 184, 0.3)',
                '&:hover': { borderColor: 'rgba(56, 189, 248, 0.5)' }
              }}
            >
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 1, borderRadius: 2, flexShrink: 0 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Status Banner - Compact */}
      {selectedSession && (
        <Box sx={{ flexShrink: 0, mb: 1.5 }}>
          <SSRAlgoStatusBanner 
            session={selectedSession}
            monitorStatus={selectedMonitorStatus}
            payoffData={selectedPayoff}
            currentPrice={selectedMonitorStatus?.last_price || selectedPayoff?.spot_price || null}
          />
        </Box>
      )}

      {/* MAIN CONTENT - Takes remaining space */}
      <Box sx={{ 
        flex: 1, 
        display: 'flex', 
        flexDirection: 'column',
        minHeight: 0,
        gap: 1.5,
      }}>
        
        {/* TOP ROW: Config (40%) + Payoff (60%) */}
        <Box sx={{ 
          flex: 1,
          display: 'flex', 
          gap: 1.5, 
          minHeight: 0,
          flexWrap: { xs: 'wrap', lg: 'nowrap' },
        }}>
          
          {/* LEFT COLUMN: Config & Sessions - 40% */}
          <Box sx={{ 
            width: { xs: '100%', lg: '40%' }, 
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
            minHeight: 0,
          }}>
            {/* Configuration Panel */}
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <SSRAlgoConfigPanel onSessionCreated={handleSessionCreated} />
            </Box>
          </Box>

          {/* RIGHT: Payoff Chart - 60% */}
          <Card sx={{ 
            flex: 1,
            width: { xs: '100%', lg: '60%' },
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
            border: '1px solid rgba(129, 140, 248, 0.2)',
            borderRadius: 2,
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
          }}>
            <CardContent sx={{ p: 1.5, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexShrink: 0 }}>
                <ChartIcon sx={{ fontSize: 18, color: '#818cf8' }} />
                <Typography variant="subtitle2" sx={{ color: '#818cf8', fontWeight: 600 }}>
                  Payoff Diagram
                </Typography>
                {selectedSession?.status === 'MONITORING' && (
                  <Chip 
                    size="small" 
                    label="● LIVE" 
                    sx={{ 
                      height: 18, 
                      fontSize: '0.6rem',
                      bgcolor: 'rgba(34, 197, 94, 0.2)',
                      color: '#22c55e',
                      fontWeight: 700,
                    }} 
                  />
                )}
                {selectedSession && (
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      ml: 'auto',
                      fontFamily: 'monospace',
                      fontSize: '0.65rem',
                      color: 'rgba(148, 163, 184, 0.7)',
                    }}
                  >
                    {selectedSession.session_id}
                  </Typography>
                )}
              </Box>
              
              {selectedSession ? (
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <Box sx={{ flex: 1, minHeight: 150 }}>
                    <SSRAlgoPayoffChart
                      payoffCurve={selectedPayoff?.payoff_curve || []}
                      maxLossPoints={selectedPayoff?.max_loss_points || {}}
                      adjustmentTriggers={selectedPayoff?.adjustment_triggers || {}}
                      breakevens={selectedPayoff?.breakevens || []}
                      spotPrice={selectedPayoff?.spot_price || 0}
                      currentPrice={selectedPayoff?.spot_price || 0}
                      height="100%"
                      loading={!selectedPayoff}
                    />
                  </Box>
                  
                  {/* Payoff Stats Row - Compact */}
                  {selectedPayoff && (
                    <Box sx={{ 
                      mt: 1, 
                      p: 1, 
                      background: 'rgba(0, 0, 0, 0.2)',
                      borderRadius: 1.5,
                      display: 'flex',
                      justifyContent: 'space-around',
                      flexWrap: 'wrap',
                      gap: 0.5,
                      flexShrink: 0,
                    }}>
                      <Box sx={{ textAlign: 'center', minWidth: 70 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Net Premium</Typography>
                        <Typography 
                          variant="body2" 
                          color={selectedPayoff.net_premium >= 0 ? 'success.main' : 'error.main'}
                          sx={{ fontWeight: 700, fontSize: '0.8rem' }}
                        >
                          ${selectedPayoff.net_premium?.toFixed(2)}
                        </Typography>
                      </Box>
                      <Box sx={{ textAlign: 'center', minWidth: 50 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Legs</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                          {selectedSession?.positions?.length * 6 || selectedPayoff.position_count || 0}
                        </Typography>
                      </Box>
                      <Box sx={{ textAlign: 'center', minWidth: 70 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Max Profit</Typography>
                        <Typography variant="body2" color="success.main" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                          ${selectedPayoff.max_loss_points?.max_profit_value?.toFixed(2) || '-'}
                        </Typography>
                      </Box>
                      <Box sx={{ textAlign: 'center', minWidth: 70 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>Max Loss</Typography>
                        <Typography variant="body2" color="error.main" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                          ${selectedPayoff.max_loss_points?.max_loss_value?.toFixed(2) || '-'}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </Box>
              ) : (
                <Box sx={{ 
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(0, 0, 0, 0.1)',
                  borderRadius: 2,
                  border: '1px dashed rgba(129, 140, 248, 0.3)'
                }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <ChartIcon sx={{ fontSize: 32, color: 'rgba(129, 140, 248, 0.4)', mb: 0.5 }} />
                    <Typography color="text.secondary" variant="caption">
                      Select a session to view
                    </Typography>
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>

        {/* MIDDLE ROW: Activity Log - Full Width */}
        <Box sx={{ 
          height: 220,
          flexShrink: 0,
        }}>
          <SSRAlgoLogPanel 
            sessionId={selectedSession?.session_id}
            height="100%"
            compact={false}
            showHeader={true}
            refreshInterval={2000}
          />
        </Box>

        {/* BOTTOM ROW: Position Legs (75%) + Trigger History (25%) */}
        <Box sx={{ 
          display: 'flex',
          gap: 1.5,
          height: 180,
          flexShrink: 0,
        }}>
          {/* Positions Table - 75% */}
          <Card sx={{ 
            flex: 3,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
            border: '1px solid rgba(71, 85, 105, 0.3)',
            borderRadius: 2,
          }}>
            <CardContent sx={{ p: 1.5, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'auto' }}>
              {selectedSession && selectedSession.positions?.length > 0 ? (
                <SSRAlgoPositionsTable 
                  positions={selectedSession.positions}
                  showHeader={true}
                  compact={true}
                />
              ) : (
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="text.secondary" variant="caption">
                    No positions yet
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Trigger History - 25% */}
          <Card sx={{ 
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
            border: '1px solid rgba(71, 85, 105, 0.3)',
            borderRadius: 2,
          }}>
            <CardContent sx={{ p: 1.5, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'auto' }}>
              {selectedSession ? (
                <SSRAlgoTriggerHistory 
                  session={selectedSession}
                  showHeader={true}
                  compact={true}
                />
              ) : (
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="text.secondary" variant="caption">
                    No session selected
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>

        {/* BOTTOM: Active/History Tabs + Sessions List */}
        <Box sx={{ 
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          height: 320,
          flexShrink: 0,
        }}>
          {/* Sessions Tabs */}
          <Paper sx={{ 
            background: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(71, 85, 105, 0.3)',
            borderRadius: 2,
            flexShrink: 0,
          }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Tabs 
                value={tabValue} 
                onChange={(e, v) => setTabValue(v)}
                sx={{ 
                  minHeight: 36,
                  '& .MuiTab-root': {
                    fontWeight: 600,
                    minHeight: 36,
                    fontSize: '0.7rem',
                    px: 1,
                    py: 0.5,
                  }
                }}
              >
                <Tab 
                  icon={<PlayIcon sx={{ fontSize: 14 }} />} 
                  label={`Active (${activeSessions.length})`} 
                  iconPosition="start"
                />
                <Tab 
                  icon={<HistoryIcon sx={{ fontSize: 14 }} />} 
                  label={`History (${historicalSessions.length})`} 
                  iconPosition="start"
                />
              </Tabs>
              <Box sx={{ pr: 0.5 }}>
                {tabValue === 0 && sessions.filter(s => s.status === 'IDLE').length > 0 && (
                  <Tooltip title="Delete all Ready to Start sessions">
                    <IconButton size="small" color="warning" onClick={handleDeleteAllIdle}>
                      <DeleteSweepIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                )}
                {tabValue === 1 && historicalSessions.length > 0 && (
                  <Tooltip title="Delete all history sessions">
                    <IconButton size="small" color="error" onClick={handleDeleteAllHistory}>
                      <DeleteSweepIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Box>
          </Paper>

          {/* Sessions List - Scrollable */}
          <Box sx={{ 
            flex: 1, 
            overflowY: 'auto', 
            minHeight: 0,
            background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 41, 59, 0.4) 100%)',
            borderRadius: 2,
            p: 1,
            border: '1px solid rgba(71, 85, 105, 0.2)',
          }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            ) : (
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {tabValue === 0 && (
                  <>
                    {activeSessions.length === 0 ? (
                      <Paper sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        background: 'rgba(30, 41, 59, 0.4)',
                        border: '1px dashed rgba(71, 85, 105, 0.5)',
                        borderRadius: 2,
                        width: '100%',
                      }}>
                        <Typography color="text.secondary" variant="caption">
                          No active sessions
                        </Typography>
                      </Paper>
                    ) : (
                      activeSessions.map(session => (
                        <Box 
                          key={session.session_id} 
                          onClick={() => handleSelectSession(session)}
                          sx={{ 
                            cursor: 'pointer',
                            border: selectedSession?.session_id === session.session_id 
                              ? '2px solid #818cf8' 
                              : '2px solid transparent',
                            borderRadius: 2,
                            width: { xs: '100%', sm: 'calc(50% - 4px)', lg: 'calc(25% - 6px)' },
                          }}
                        >
                          <SSRAlgoSessionCard
                            session={session}
                            onRefresh={fetchSessions}
                            onDelete={handleSessionDeleted}
                            compact={true}
                          />
                        </Box>
                      ))
                    )}
                  </>
                )}

                {tabValue === 1 && (
                  <>
                    {historicalSessions.length === 0 ? (
                      <Paper sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        width: '100%',
                      }}>
                        <Typography color="text.secondary" variant="caption">
                          No history
                        </Typography>
                      </Paper>
                    ) : (
                      historicalSessions.slice(0, 10).map(session => (
                        <Box 
                          key={session.session_id} 
                          onClick={() => handleSelectSession(session)}
                          sx={{ 
                            cursor: 'pointer',
                            border: selectedSession?.session_id === session.session_id 
                              ? '2px solid #818cf8' 
                              : '2px solid transparent',
                            borderRadius: 2,
                            width: { xs: '100%', sm: 'calc(50% - 4px)', lg: 'calc(25% - 6px)' },
                          }}
                        >
                          <SSRAlgoSessionCard
                            session={session}
                            onRefresh={fetchSessions}
                            onDelete={handleSessionDeleted}
                            compact={true}
                          />
                        </Box>
                      ))
                    )}
                  </>
                )}
              </Box>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SSRAlgoDashboard;