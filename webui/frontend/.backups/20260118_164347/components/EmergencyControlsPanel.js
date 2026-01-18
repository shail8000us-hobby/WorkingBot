import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Grid,
  Divider,
  Chip
} from '@mui/material';
import {
  Warning,
  CheckCircle,
  Delete,
  Refresh,
  Info
} from '@mui/icons-material';
import api from '../utils/apiShim';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';

export default function EmergencyControlsPanel() {
  const { selectedInstance, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const checkEmergencyFlag = async () => {
    try {
      setLoading(true);
      // v6.0: Use instance parameter for per-instance emergency flags
      const response = await api.get(withInstance('/api/emergency/check_flag'));
      setStatus(response.data);
    } catch (err) {
      console.error('Error checking flag:', err);
    } finally {
      setLoading(false);
    }
  };

  const clearEmergencyFlag = async () => {
    const instanceLabel = selectedInstance || 'all instances';
    if (!window.confirm(`Are you sure you want to clear the emergency stop flag for ${instanceLabel}? This will resume trading.`)) {
      return;
    }

    try {
      setLoading(true);
      // v6.0: Use instance parameter for per-instance emergency flag clear
      const response = await api.post(withInstance('/api/emergency/clear_flag'));
      if (response.data.success) {
        alert(`✅ Emergency flag cleared successfully for ${instanceLabel}! Trading can now resume.`);
        checkEmergencyFlag();
      } else {
        alert('❌ Failed to clear flag: ' + response.data.message);
      }
    } catch (err) {
      alert('❌ Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    checkEmergencyFlag();
  }, []);

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          🚨 Emergency Controls
        </Typography>
        {selectedInstance && <SymbolBadge symbol={instanceInfo.symbol} mode={instanceInfo.mode} />}
      </Box>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Use these controls to manage emergency stop flags and other critical safety mechanisms.
      </Typography>

      {/* Emergency Stop Flag Control */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Warning color="error" sx={{ fontSize: 40 }} />
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              Emergency Stop Flag
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Controls the emergency trading halt mechanism
            </Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {status && (
          <Box sx={{ mb: 3 }}>
            {status.flag_exists ? (
              <Alert severity="error" icon={<Warning />}>
                <AlertTitle>Emergency Stop Flag is ACTIVE</AlertTitle>
                <Typography variant="body2">
                  <strong>Flag Location:</strong> {status.flag_location}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  <strong>Effect:</strong> All trading is blocked. The Safety Gatekeeper is intercepting all order placement requests.
                </Typography>
              </Alert>
            ) : (
              <Alert severity="success" icon={<CheckCircle />}>
                <AlertTitle>No Emergency Flag Detected</AlertTitle>
                <Typography variant="body2">
                  Trading is not blocked by emergency flag.
                </Typography>
              </Alert>
            )}
          </Box>
        )}

        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<Refresh />}
              onClick={checkEmergencyFlag}
              disabled={loading}
            >
              Check Flag Status
            </Button>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Button
              fullWidth
              variant="contained"
              color="error"
              startIcon={<Delete />}
              onClick={clearEmergencyFlag}
              disabled={loading || (status && !status.flag_exists)}
            >
              Clear Emergency Flag
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Information Panel */}
      <Paper sx={{ p: 3, bgcolor: 'rgba(33, 150, 243, 0.1)' }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Info color="info" />
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
              About Emergency Stop Flag
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              The emergency stop flag (`.guardian_emergency_stop`) is created when:
            </Typography>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li><Typography variant="body2">Account loss exceeds configured limits</Typography></li>
              <li><Typography variant="body2">Guardian bot detects critical risk conditions</Typography></li>
              <li><Typography variant="body2">Manual emergency stop is triggered</Typography></li>
            </ul>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              <strong>⚠️ Important:</strong> Before clearing the flag, make sure you've:
            </Typography>
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              <li><Typography variant="body2">Investigated why the flag was created</Typography></li>
              <li><Typography variant="body2">Fixed the underlying issue</Typography></li>
              <li><Typography variant="body2">Verified account balance and positions</Typography></li>
              <li><Typography variant="body2">Confirmed trading conditions are safe</Typography></li>
            </ol>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}
