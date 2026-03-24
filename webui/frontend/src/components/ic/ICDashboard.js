/**
 * IC Dashboard — Iron Condor
 *
 * Main dashboard with session management, live P&L, leg table,
 * strike map, payoff diagram, cycle history, adjustments, and settings.
 *
 * Created: 2026-03-24
 */

import React, { useState, useCallback, useMemo } from 'react';
import {
  Box, Typography, Grid, Paper, Tabs, Tab, Button, Chip, Alert,
  CircularProgress, IconButton, Tooltip, Card, CardContent,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Switch, FormControlLabel, Snackbar,
} from '@mui/material';
import {
  Refresh as RefreshIcon, PlayArrow as PlayIcon, Pause as PauseIcon,
  Stop as StopIcon, Add as AddIcon, Delete as DeleteIcon,
  Settings as SettingsIcon, Circle as CircleIcon,
} from '@mui/icons-material';
import { useIC } from './ICContext';
import icService from './icService';
import ICLegTable from './ICLegTable';
import ICStrikeMap from './ICStrikeMap';
import ICPayoffDiagram from './ICPayoffDiagram';
import ICPnLChart from './ICPnLChart';
import ICAdjustmentLog from './ICAdjustmentLog';
import ICCycleHistory from './ICCycleHistory';
import ICConfigPanel from './ICConfigPanel';

// =============================================================================
// Status Config
// =============================================================================

const STATUS_CONFIG = {
  IDLE: { color: '#9e9e9e', bg: 'rgba(158,158,158,0.12)', label: 'Idle' },
  RUNNING: { color: '#4caf50', bg: 'rgba(76,175,80,0.12)', label: 'Running' },
  PAUSED: { color: '#ff9800', bg: 'rgba(255,152,0,0.12)', label: 'Paused' },
  STOPPED: { color: '#757575', bg: 'rgba(117,117,117,0.12)', label: 'Stopped' },
};
const getStatusConfig = (s) => STATUS_CONFIG[s] || STATUS_CONFIG.IDLE;

const StatusChip = ({ status }) => {
  const cfg = getStatusConfig(status);
  return (
    <Chip
      label={cfg.label} size="small"
      icon={<CircleIcon sx={{ fontSize: 10 }} />}
      sx={{ backgroundColor: cfg.bg, color: cfg.color, fontWeight: 600, '& .MuiChip-icon': { color: cfg.color } }}
    />
  );
};

// =============================================================================
// Session Card
// =============================================================================

const ICSessionCard = ({ session, selected, onSelect, onControl }) => {
  const status = session.status || 'IDLE';
  const cfg = getStatusConfig(status);
  const cycle = session.current_cycle;
  const pnl = session.unrealized_pnl || 0;

  return (
    <Card
      variant="outlined"
      onClick={() => onSelect(session.session_id)}
      sx={{
        cursor: 'pointer', mb: 1,
        border: selected ? `2px solid ${cfg.color}` : '1px solid rgba(255,255,255,0.12)',
        backgroundColor: selected ? cfg.bg : 'transparent',
        transition: 'all 0.2s',
        '&:hover': { backgroundColor: cfg.bg },
      }}
    >
      <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Typography variant="subtitle2" sx={{ fontFamily: 'monospace' }}>
            {session.name || session.session_id}
          </Typography>
          <StatusChip status={status} />
        </Box>

        {/* Cycle info */}
        {cycle && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontFamily: 'monospace' }}>
            Cycle #{cycle.cycle_number} · SP: {cycle.legs?.sp?.strike || '—'} · SC: {cycle.legs?.sc?.strike || '—'}
          </Typography>
        )}

        {/* P&L */}
        <Typography
          variant="body2"
          sx={{
            mt: 0.5, fontWeight: 700, fontFamily: 'monospace',
            color: pnl >= 0 ? '#4caf50' : '#f44336',
          }}
        >
          P&L: ${pnl.toFixed(4)}
        </Typography>

        {/* Cycle count */}
        <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace', fontSize: '0.65rem' }}>
          Cycles: {session.cycles_completed || 0} · Total: ${(session.total_realized_pnl || 0).toFixed(4)}
        </Typography>

        {/* Controls */}
        <Box sx={{ display: 'flex', gap: 0.5, mt: 1 }}>
          {status === 'IDLE' && (
            <Tooltip title="Start">
              <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); onControl('start', session.session_id); }}>
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'RUNNING' && (
            <Tooltip title="Pause">
              <IconButton size="small" color="warning" onClick={(e) => { e.stopPropagation(); onControl('pause', session.session_id); }}>
                <PauseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'PAUSED' && (
            <Tooltip title="Resume">
              <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); onControl('resume', session.session_id); }}>
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {['RUNNING', 'PAUSED'].includes(status) && (
            <Tooltip title="Stop">
              <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); onControl('stop', session.session_id); }}>
                <StopIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {['IDLE', 'STOPPED'].includes(status) && (
            <Tooltip title="Delete">
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); onControl('delete', session.session_id); }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Settings">
            <IconButton size="small" color="primary" onClick={(e) => { e.stopPropagation(); onControl('settings', session.session_id); }}>
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </CardContent>
    </Card>
  );
};

// =============================================================================
// Create Session Dialog
// =============================================================================

const CreateSessionDialog = ({ open, onClose, onCreated }) => {
  const [name, setName] = useState('BTC IC Weekly');
  const [simulate, setSimulate] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    setError(null);
    try {
      const result = await icService.createSession({
        name,
        params: { simulate },
      });
      if (result.success) {
        onCreated(result.session);
        onClose();
        setName('BTC IC Weekly');
      } else {
        setError(result.error || 'Failed to create session');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New Iron Condor Session</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          label="Session Name" fullWidth margin="normal"
          value={name} onChange={(e) => setName(e.target.value)}
        />
        <FormControlLabel
          control={<Switch checked={simulate} onChange={(e) => setSimulate(e.target.checked)} />}
          label="Simulate Mode (no real orders)"
          sx={{ mt: 1 }}
        />
        <Alert severity="info" sx={{ mt: 2 }}>
          Parameters can be configured after creation. Default wing width is $1,000 with 0.16 delta targeting.
        </Alert>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleCreate} disabled={creating}>
          {creating ? <CircularProgress size={20} /> : 'Create Session'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// =============================================================================
// Main Dashboard
// =============================================================================

const TABS = [
  { label: 'Positions', key: 'positions' },
  { label: 'Strike Map', key: 'strike_map' },
  { label: 'Payoff', key: 'payoff' },
  { label: 'P&L Chart', key: 'pnl_chart' },
  { label: 'Adjustments', key: 'adjustments' },
  { label: 'Cycle History', key: 'cycle_history' },
  { label: 'Settings', key: 'settings' },
];

const ICDashboard = () => {
  const { sessions, selectedSession, selectedSessionId, selectSession, fetchSessions, loading, error } = useIC();
  const [activeTab, setActiveTab] = useState(0);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [settingsSessionId, setSettingsSessionId] = useState(null);

  const notify = useCallback((message, severity = 'info') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  const handleControl = useCallback(async (action, sessionId) => {
    try {
      let result;
      switch (action) {
        case 'start':
          result = await icService.startSession(sessionId);
          notify(result.success ? 'Session started' : result.error, result.success ? 'success' : 'error');
          break;
        case 'pause':
          result = await icService.pauseSession(sessionId);
          notify(result.success ? 'Session paused' : result.error, result.success ? 'success' : 'error');
          break;
        case 'resume':
          result = await icService.resumeSession(sessionId);
          notify(result.success ? 'Session resumed' : result.error, result.success ? 'success' : 'error');
          break;
        case 'stop':
          result = await icService.stopSession(sessionId);
          notify(result.success ? 'Session stopped' : result.error, result.success ? 'success' : 'error');
          break;
        case 'delete':
          if (!window.confirm('Delete this session?')) return;
          result = await icService.deleteSession(sessionId);
          notify(result.success ? 'Session deleted' : result.error, result.success ? 'success' : 'error');
          break;
        case 'settings':
          setSettingsSessionId(sessionId);
          selectSession(sessionId);
          setActiveTab(6); // Settings tab
          return;
        default:
          break;
      }
      fetchSessions(false);
    } catch (err) {
      notify(err.message, 'error');
    }
  }, [fetchSessions, notify, selectSession]);

  // P&L summary for selected session
  const pnlSummary = useMemo(() => {
    if (!selectedSession) return null;
    const cycle = selectedSession.current_cycle;
    return {
      maxProfit: selectedSession.max_profit || cycle?.net_credit || 0,
      unrealized: selectedSession.unrealized_pnl || 0,
      maxLoss: selectedSession.max_loss || cycle?.dynamic_max_loss || 0,
      pnlPct: selectedSession.pnl_pct || 0,
      totalRealized: selectedSession.total_realized_pnl || 0,
    };
  }, [selectedSession]);

  const renderTabContent = () => {
    if (!selectedSession) {
      return (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">Select a session to view details</Typography>
        </Box>
      );
    }

    const cycle = selectedSession.current_cycle;
    const params = selectedSession.params || {};

    switch (TABS[activeTab]?.key) {
      case 'positions':
        return <ICLegTable cycle={cycle} params={params} />;
      case 'strike_map':
        return <ICStrikeMap session={selectedSession} />;
      case 'payoff':
        return <ICPayoffDiagram session={selectedSession} />;
      case 'pnl_chart':
        return <ICPnLChart session={selectedSession} />;
      case 'adjustments':
        return <ICAdjustmentLog session={selectedSession} />;
      case 'cycle_history':
        return <ICCycleHistory session={selectedSession} />;
      case 'settings':
        return <ICConfigPanel session={selectedSession} onSaved={() => { fetchSessions(false); notify('Settings saved', 'success'); }} />;
      default:
        return null;
    }
  };

  return (
    <Box sx={{ p: 2, maxWidth: 1400, mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            🦅 Iron Condor
          </Typography>
          <Typography variant="caption" color="text.secondary">
            4-leg defined-risk premium harvesting · BTC Options
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh">
            <IconButton onClick={() => fetchSessions(true)} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained" startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
            sx={{ textTransform: 'none' }}
          >
            New Session
          </Button>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        {/* Session List — Left sidebar */}
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 1.5, maxHeight: '80vh', overflowY: 'auto' }}>
            <Typography variant="subtitle2" sx={{ mb: 1, px: 0.5 }}>
              Sessions ({sessions.length})
            </Typography>

            {loading && sessions.length === 0 ? (
              <Box sx={{ p: 2, textAlign: 'center' }}><CircularProgress size={24} /></Box>
            ) : sessions.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                No sessions. Click "New Session" to get started.
              </Typography>
            ) : (
              sessions.map((session) => (
                <ICSessionCard
                  key={session.session_id}
                  session={session}
                  selected={selectedSessionId === session.session_id}
                  onSelect={selectSession}
                  onControl={handleControl}
                />
              ))
            )}
          </Paper>
        </Grid>

        {/* Main Content — Right panel */}
        <Grid item xs={12} md={9}>
          {/* P&L Banner */}
          {selectedSession && pnlSummary && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Max Profit</Typography>
                  <Typography variant="h6" sx={{ color: '#4caf50', fontFamily: 'monospace', fontWeight: 700 }}>
                    +${pnlSummary.maxProfit.toFixed(4)}
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Unrealized P&L</Typography>
                  <Typography
                    variant="h6"
                    sx={{ color: pnlSummary.unrealized >= 0 ? '#4caf50' : '#f44336', fontFamily: 'monospace', fontWeight: 700 }}
                  >
                    {pnlSummary.unrealized >= 0 ? '+' : ''}${pnlSummary.unrealized.toFixed(4)}
                    <Typography component="span" variant="caption" sx={{ ml: 1 }}>
                      ({pnlSummary.pnlPct.toFixed(1)}%)
                    </Typography>
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Max Loss</Typography>
                  <Typography variant="h6" sx={{ color: '#f44336', fontFamily: 'monospace', fontWeight: 700 }}>
                    -${Math.abs(pnlSummary.maxLoss).toFixed(4)}
                  </Typography>
                </Grid>
              </Grid>
            </Paper>
          )}

          {/* Tabs */}
          <Paper sx={{ mb: 0 }}>
            <Tabs
              value={activeTab}
              onChange={(_, v) => setActiveTab(v)}
              variant="scrollable"
              scrollButtons="auto"
              sx={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}
            >
              {TABS.map((tab) => (
                <Tab key={tab.key} label={tab.label} sx={{ textTransform: 'none', minWidth: 80 }} />
              ))}
            </Tabs>
          </Paper>

          <Paper sx={{ p: 2, minHeight: 300 }}>
            {renderTabContent()}
          </Paper>
        </Grid>
      </Grid>

      {/* Create Dialog */}
      <CreateSessionDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={(session) => {
          fetchSessions(false);
          selectSession(session.session_id);
          notify('Session created!', 'success');
        }}
      />

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((p) => ({ ...p, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((p) => ({ ...p, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ICDashboard;
