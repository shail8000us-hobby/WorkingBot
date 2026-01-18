import React, { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Alert,
  AlertTitle,
  CircularProgress,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Cancel as CancelIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import HelpIcon from './help/HelpIcon';
import api from '../utils/apiShim';

const EmergencyKillButton = () => {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [resultOpen, setResultOpen] = useState(false);

  const handleOpenConfirm = () => {
    console.log('🚨 [EMERGENCY KILL] Confirmation dialog opened');
    setConfirmOpen(true);
  };

  const handleCloseConfirm = () => {
    console.log('🚨 [EMERGENCY KILL] Confirmation dialog closed');
    setConfirmOpen(false);
  };

  const handleKillAll = async () => {
    console.log('🚨 [EMERGENCY KILL] Button clicked!');
    console.log('🚨 [EMERGENCY KILL] Setting loading state...');
    setLoading(true);
    setConfirmOpen(false);

    try {
      console.log('🚨 [EMERGENCY KILL] Making POST request to /api/emergency/kill-all...');
      console.log('🚨 [EMERGENCY KILL] Timestamp:', new Date().toISOString());

      const { data } = await api.post('/api/emergency/kill-all');

      console.log('🚨 [EMERGENCY KILL] API Response received:', data);
      console.log('🚨 [EMERGENCY KILL] Success:', data.success);
      console.log('🚨 [EMERGENCY KILL] Total killed:', data.total_killed);

      setResult(data);
      setResultOpen(true);
    } catch (error) {
      console.error('🚨 [EMERGENCY KILL] Error occurred:', error);
      console.error('🚨 [EMERGENCY KILL] Error message:', error.message);
      console.error('🚨 [EMERGENCY KILL] Error stack:', error.stack);
      console.error('🚨 [EMERGENCY KILL] Error response:', error.response);

      setResult({
        success: false,
        message: `Failed to kill bots: ${error.message}`,
        killed: [],
        errors: [error.message],
      });
      setResultOpen(true);
    } finally {
      console.log('🚨 [EMERGENCY KILL] Clearing loading state...');
      setLoading(false);
    }
  };

  const handleCloseResult = () => {
    setResultOpen(false);
    setResult(null);
  };

  return (
    <>
      {/* Emergency Kill Button */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button
          variant="contained"
          color="error"
          size="large"
          startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <CancelIcon />}
          onClick={handleOpenConfirm}
          disabled={loading}
          data-action-id="emergency.kill-all"
          sx={{
            fontWeight: 'bold',
            boxShadow: 3,
            '&:hover': {
              boxShadow: 6,
              transform: 'scale(1.02)',
            },
            transition: 'all 0.2s',
          }}
        >
          {loading ? 'KILLING...' : '🚨 EMERGENCY KILL ALL BOTS'}
        </Button>
        <HelpIcon actionId="emergency.kill-all" placement="right" />
      </Box>

      {/* Confirmation Dialog */}
      <Dialog open={confirmOpen} onClose={handleCloseConfirm} maxWidth="sm" fullWidth>
        <DialogTitle
          sx={{
            bgcolor: 'error.main',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <WarningIcon />
          Emergency Kill All Bots
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>⚠️ WARNING: This is a HARD KILL!</AlertTitle>
            This will immediately terminate ALL bot processes using kill -9
          </Alert>

          <DialogContentText sx={{ mb: 2 }}>This action will forcefully stop:</DialogContentText>

          <List dense>
            <ListItem>
              <ListItemIcon>
                <CancelIcon color="error" />
              </ListItemIcon>
              <ListItemText primary="Trading Bot" secondary="Main grid trading bot" />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CancelIcon color="error" />
              </ListItemIcon>
              <ListItemText primary="Heartbeat Monitor" secondary="Dead man's switch monitor" />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CancelIcon color="error" />
              </ListItemIcon>
              <ListItemText primary="Guardian Bot" secondary="Position safety monitor" />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <CancelIcon color="error" />
              </ListItemIcon>
              <ListItemText primary="tmux Session" secondary="Terminal multiplexer session" />
            </ListItem>
          </List>

          <Alert severity="warning" sx={{ mt: 2 }}>
            <strong>Note:</strong> This does NOT cancel open orders or close positions on the
            exchange. It only stops the bot processes.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseConfirm} variant="outlined">
            Cancel
          </Button>
          <Button
            onClick={handleKillAll}
            variant="contained"
            color="error"
            startIcon={<CancelIcon />}
          >
            Yes, Kill All Bots
          </Button>
        </DialogActions>
      </Dialog>

      {/* Result Dialog */}
      <Dialog open={resultOpen} onClose={handleCloseResult} maxWidth="sm" fullWidth>
        <DialogTitle
          sx={{
            bgcolor: result?.success ? 'success.main' : 'error.main',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          {result?.success ? <CheckCircleIcon /> : <ErrorIcon />}
          {result?.success ? 'Success' : 'Failed'}
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity={result?.success ? 'success' : 'error'} sx={{ mb: 2 }}>
            <AlertTitle>{result?.message}</AlertTitle>
          </Alert>

          {result?.killed && result.killed.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold' }}>
                ✅ Killed Processes:
              </Typography>
              <List dense>
                {result.killed.map((proc, idx) => (
                  <ListItem key={idx}>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={proc} />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {result?.errors && result.errors.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                gutterBottom
                sx={{ fontWeight: 'bold', color: 'error.main' }}
              >
                ⚠️ Errors:
              </Typography>
              <List dense>
                {result.errors.map((err, idx) => (
                  <ListItem key={idx}>
                    <ListItemIcon>
                      <ErrorIcon color="error" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={err} />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {result?.still_running && result.still_running.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                gutterBottom
                sx={{ fontWeight: 'bold', color: 'warning.main' }}
              >
                ⚠️ Still Running:
              </Typography>
              <List dense>
                {result.still_running.map((proc, idx) => (
                  <ListItem key={idx}>
                    <ListItemIcon>
                      <ErrorIcon color="warning" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={proc}
                      sx={{
                        '& .MuiListItemText-primary': {
                          fontSize: '0.8rem',
                          fontFamily: 'monospace',
                        },
                      }}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseResult} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default EmergencyKillButton;
