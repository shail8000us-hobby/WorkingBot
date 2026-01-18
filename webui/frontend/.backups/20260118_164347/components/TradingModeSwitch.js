import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  Alert,
  AlertTitle,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Science as ScienceIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import HelpIcon from './help/HelpIcon';
import api from '../utils/apiShim';

const TradingModeSwitch = ({ botRunning }) => {
  const [currentMode, setCurrentMode] = useState('demo');
  const [modeInfo, setModeInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingMode, setPendingMode] = useState(null);

  const fetchCurrentMode = async () => {
    try {
      const { data } = await api.get('/api/trading-mode');
      
      if (data.mode) {
        setCurrentMode(data.mode);
        setModeInfo(data.display);
      }
    } catch (err) {
      console.error('Error fetching trading mode:', err);
    }
  };

  // Fetch current mode on mount and every 5 seconds
  useEffect(() => {
    fetchCurrentMode();
    const interval = setInterval(fetchCurrentMode, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleModeChange = (event, newMode) => {
    if (!newMode) return; // Prevent deselection
    
    // If switching to live, show confirmation dialog
    if (newMode === 'live') {
      setPendingMode(newMode);
      setConfirmDialogOpen(true);
    } else {
      // Demo mode doesn't need confirmation
      switchMode(newMode, false);
    }
  };

  const switchMode = async (mode, confirmed = false) => {
    setLoading(true);
    setError(null);
    
    try {
      const { data } = await api.post('/api/trading-mode', { mode, confirmed });

      if (data.success !== false) {
        setCurrentMode(mode);
        await fetchCurrentMode(); // Refresh mode info
        
        // Show success message
        alert(`✅ ${data.message}\n\n${data.restart_required ? 'Please restart the bot for changes to take effect.' : ''}`);
      } else {
        if (data.require_confirmation) {
          // This shouldn't happen as we handle confirmation in UI
          setError(data.warning);
        } else {
          setError(data.error || 'Failed to switch mode');
        }
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
      setConfirmDialogOpen(false);
      setPendingMode(null);
    }
  };

  const handleConfirmLiveMode = () => {
    switchMode('live', true);
  };

  const handleCancelLiveMode = () => {
    setConfirmDialogOpen(false);
    setPendingMode(null);
  };

  return (
    <Box sx={{ mb: 3 }}>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" component="div">
              🎛️ Trading Mode
            </Typography>
            {modeInfo && (
              <Chip
                icon={currentMode === 'demo' ? <ScienceIcon /> : <WarningIcon />}
                label={`${modeInfo.emoji} ${currentMode.toUpperCase()}`}
                color={currentMode === 'demo' ? 'success' : 'error'}
                size="small"
              />
            )}
          </Box>

          {loading && <LinearProgress sx={{ mb: 2 }} />}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 2 }}>
            <ToggleButtonGroup
              value={currentMode}
              exclusive
              onChange={handleModeChange}
              aria-label="trading mode"
              disabled={loading}
              sx={{ width: '100%' }}
              data-action-id="trading-mode"
            >
              <ToggleButton value="demo" sx={{ flex: 1, py: 2 }}>
                <Box sx={{ textAlign: 'center' }}>
                  <ScienceIcon sx={{ display: 'block', mx: 'auto', mb: 1, fontSize: 32 }} />
                  <Typography variant="body1" fontWeight="bold">
                    🟢 DEMO MODE
                  </Typography>
                  <Typography variant="caption" display="block">
                    Paper Trading (Testnet)
                  </Typography>
                </Box>
              </ToggleButton>
              
              <ToggleButton value="live" sx={{ flex: 1, py: 2 }}>
                <Box sx={{ textAlign: 'center' }}>
                  <WarningIcon sx={{ display: 'block', mx: 'auto', mb: 1, fontSize: 32 }} />
                  <Typography variant="body1" fontWeight="bold">
                    🔴 LIVE MODE
                  </Typography>
                  <Typography variant="caption" display="block">
                    Real Money Trading
                  </Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            <HelpIcon actionId="trading-mode" placement="right" />
          </Box>
        </CardContent>
      </Card>

      {/* Live Mode Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={handleCancelLiveMode}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: 'error.main', color: 'white' }}>
          <WarningIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          ⚠️ CONFIRM LIVE TRADING MODE
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>REAL MONEY WARNING</AlertTitle>
            You are about to switch to LIVE trading mode. This will use REAL MONEY from your account.
          </Alert>

          <DialogContentText sx={{ mb: 2 }}>
            Please confirm you have:
          </DialogContentText>

          <List>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Tested thoroughly on demo/testnet"
                secondary="Run the bot for several days on demo mode first"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Configured all safety limits correctly"
                secondary="MAX_ACCOUNT_LOSS_INR, GUARDIAN settings, etc."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CheckCircleIcon color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Set up your LIVE API keys"
                secondary="In secrets/api_keys.env (LIVE_DELTA_API_KEY)"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <WarningIcon color="error" />
              </ListItemIcon>
              <ListItemText
                primary="Understand the risks involved"
                secondary="You can lose real money. Only trade with funds you can afford to lose."
              />
            </ListItem>
          </List>

          <Alert severity="info" sx={{ mt: 2 }}>
            <AlertTitle>After Switching</AlertTitle>
            You MUST stop and restart the bot for the new mode to take effect.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCancelLiveMode} variant="outlined">
            Cancel
          </Button>
          <Button
            onClick={handleConfirmLiveMode}
            variant="contained"
            color="error"
            startIcon={<WarningIcon />}
            disabled={loading}
          >
            {loading ? 'Switching...' : 'Yes, Switch to LIVE MODE'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TradingModeSwitch;
