import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Switch,
  FormControlLabel,
  Alert,
  AlertTitle,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
} from '@mui/material';
import {
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  PowerSettingsNew as PowerIcon,
} from '@mui/icons-material';
import api from '../utils/apiShim';

/**
 * EmergencyToggle Component
 *
 * Provides a prominent emergency override switch for critical safety features.
 * Allows users to temporarily disable features in emergency situations.
 *
 * @param {string} featureName - Internal feature name (e.g., 'monitoring', 'liquidity_monitor')
 * @param {string} displayName - User-friendly display name (e.g., 'Safety Monitoring')
 * @param {string} description - Brief description of what this feature does
 * @param {string} warningMessage - Warning shown when disabling
 * @param {function} onStateChange - Optional callback when state changes
 */
function EmergencyToggle({ featureName, displayName, description, warningMessage, onStateChange }) {
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [lastChanged, setLastChanged] = useState(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [pendingState, setPendingState] = useState(null);

  // Load initial state
  useEffect(() => {
    loadOverrideState();
  }, [featureName]);

  const loadOverrideState = async () => {
    try {
      const response = await api.get('/api/emergency/overrides');
      if (response.data.success && response.data.overrides[featureName]) {
        const featureState = response.data.overrides[featureName];
        setEnabled(featureState.enabled);
        setLastChanged(featureState.last_changed);
      }
    } catch (error) {
      console.error(`Failed to load override state for ${featureName}:`, error);
    }
  };

  const handleToggleClick = (event) => {
    const newState = event.target.checked;

    // If disabling, show confirmation dialog
    if (!newState) {
      setPendingState(newState);
      setConfirmDialogOpen(true);
    } else {
      // If enabling, do it directly (no confirmation needed)
      updateOverrideState(newState, 'Re-enabling safety feature');
    }
  };

  const handleConfirmDisable = async () => {
    await updateOverrideState(pendingState, reason || 'Emergency override by user');
    setConfirmDialogOpen(false);
    setReason('');
    setPendingState(null);
  };

  const handleCancelDisable = () => {
    setConfirmDialogOpen(false);
    setReason('');
    setPendingState(null);
  };

  const updateOverrideState = async (newState, changeReason) => {
    setLoading(true);
    try {
      const response = await api.post(`/api/emergency/overrides/${featureName}`, {
        enabled: newState,
        reason: changeReason,
      });

      if (response.data.success) {
        setEnabled(newState);
        setLastChanged(new Date().toISOString());

        // Call optional callback
        if (onStateChange) {
          onStateChange(newState);
        }
      } else {
        console.error('Failed to update override:', response.data.error);
        alert(`Failed to update: ${response.data.error}`);
      }
    } catch (error) {
      console.error(`Error updating override for ${featureName}:`, error);
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const formatLastChanged = () => {
    if (!lastChanged) return null;
    try {
      const date = new Date(lastChanged);
      return date.toLocaleString();
    } catch {
      return null;
    }
  };

  return (
    <>
      <Paper
        elevation={3}
        sx={{
          p: 2,
          mb: 2,
          background: enabled
            ? 'linear-gradient(135deg, rgba(46, 213, 115, 0.1) 0%, rgba(0, 184, 148, 0.05) 100%)'
            : 'linear-gradient(135deg, rgba(255, 71, 87, 0.15) 0%, rgba(255, 107, 107, 0.08) 100%)',
          border: enabled
            ? '2px solid rgba(46, 213, 115, 0.3)'
            : '2px solid rgba(255, 71, 87, 0.5)',
          transition: 'all 0.3s ease',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          {/* Left side: Feature info and toggle */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
            {/* Status indicator */}
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              {enabled ? (
                <CheckCircleIcon sx={{ fontSize: 40, color: 'success.main' }} />
              ) : (
                <WarningIcon sx={{ fontSize: 40, color: 'error.main' }} />
              )}
              <Chip
                label={enabled ? 'ACTIVE' : 'DISABLED'}
                size="small"
                color={enabled ? 'success' : 'error'}
                sx={{ mt: 0.5, fontWeight: 'bold' }}
              />
            </Box>

            {/* Feature details */}
            <Box sx={{ flex: 1 }}>
              <Typography
                variant="h6"
                sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}
              >
                {displayName}
                <Tooltip title={description}>
                  <InfoIcon sx={{ fontSize: 20, color: 'text.secondary', cursor: 'help' }} />
                </Tooltip>
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {description}
              </Typography>
              {lastChanged && (
                <Typography variant="caption" color="text.secondary">
                  Last changed: {formatLastChanged()}
                </Typography>
              )}
            </Box>
          </Box>

          {/* Right side: Toggle switch */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={enabled}
                  onChange={handleToggleClick}
                  disabled={loading}
                  color={enabled ? 'success' : 'error'}
                  sx={{
                    '& .MuiSwitch-switchBase': {
                      '&.Mui-checked': {
                        color: 'success.main',
                      },
                      '&.Mui-checked + .MuiSwitch-track': {
                        backgroundColor: 'success.main',
                      },
                    },
                    '& .MuiSwitch-track': {
                      backgroundColor: enabled ? 'success.light' : 'error.light',
                    },
                  }}
                />
              }
              label={
                <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                  {enabled ? 'ENABLED' : 'DISABLED'}
                </Typography>
              }
              labelPlacement="start"
            />
            <Tooltip
              title={enabled ? 'Emergency Override - Click to disable' : 'Click to re-enable'}
            >
              <IconButton
                size="small"
                sx={{
                  color: enabled ? 'success.main' : 'error.main',
                  '&:hover': { backgroundColor: enabled ? 'success.light' : 'error.light' },
                }}
              >
                <PowerIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Warning when disabled */}
        {!enabled && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <AlertTitle>⚠️ Safety Feature Disabled</AlertTitle>
            <Typography variant="body2">
              {warningMessage ||
                `${displayName} is currently disabled. This increases risk. Re-enable as soon as possible.`}
            </Typography>
          </Alert>
        )}
      </Paper>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialogOpen} onClose={handleCancelDisable} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ backgroundColor: 'error.dark', color: 'white' }}>
          ⚠️ Disable {displayName}?
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>WARNING: Increased Risk</AlertTitle>
            {warningMessage ||
              `Disabling ${displayName} will reduce protection and increase trading risk.`}
          </Alert>

          <Typography variant="body2" sx={{ mb: 2 }}>
            Only disable this feature if you understand the risks and have a specific reason.
          </Typography>

          <TextField
            fullWidth
            label="Reason for disabling (optional)"
            placeholder="e.g., Testing, Emergency manual override"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            multiline
            rows={2}
            variant="outlined"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelDisable} color="inherit" variant="outlined">
            Cancel
          </Button>
          <Button
            onClick={handleConfirmDisable}
            color="error"
            variant="contained"
            startIcon={<WarningIcon />}
          >
            Yes, Disable Feature
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default EmergencyToggle;
