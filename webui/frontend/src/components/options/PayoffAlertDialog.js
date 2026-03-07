/**
 * PayoffAlertDialog — Alert creation dialog for the Payoff Diagram
 *
 * Extracted from OptionsPayoffDiagram.js for cleaner separation.
 * Opens when user clicks on the payoff chart to create a price alert.
 *
 * @version 1.0.0
 */

import React, { useState, useCallback } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Typography, RadioGroup, Radio,
  FormControlLabel, CircularProgress, Alert,
  Select, MenuItem, InputLabel, FormControl,
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';

const PayoffAlertDialog = React.memo(({
  open,
  onClose,
  alertPrice,
  setAlertPrice,
  alertPnLExpiry,
  alertPnLTarget,
  expiryDate,
  onAlertCreated,
}) => {
  const [direction, setDirection] = useState('above');
  const [note, setNote] = useState('');
  const [actionType, setActionType] = useState('none');
  const [loading, setLoading] = useState(false);

  const handleCreate = useCallback(async () => {
    if (!alertPrice) return;
    setLoading(true);
    try {
      const response = await fetch('/api/alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_price: alertPrice,
          direction,
          note: note || undefined,
          expected_pnl_expiry: alertPnLExpiry,
          expected_pnl_target: alertPnLTarget,
          notification_channels: 'telegram,in_app',
          expiry_date: expiryDate,
          action_type: actionType,
        }),
      });
      const data = await response.json();
      if (data.success) {
        onClose();
        onAlertCreated?.();
      } else {
        console.error('Failed to create alert:', data.error);
      }
    } catch (err) {
      console.error('Failed to create alert:', err);
    } finally {
      setLoading(false);
    }
  }, [alertPrice, direction, note, actionType, alertPnLExpiry, alertPnLTarget, expiryDate, onClose, onAlertCreated]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          backgroundImage: 'none',
        }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <NotificationsIcon sx={{ color: '#ffc107' }} />
        Create Price Alert
      </DialogTitle>
      <DialogContent>
        {alertPrice && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Click detected at <strong>${alertPrice?.toLocaleString()}</strong>
            <br />
            Expected P&L: <span style={{ color: alertPnLExpiry >= 0 ? '#10b981' : '#ef4444' }}>
              ${alertPnLExpiry?.toFixed(2)}
            </span>
          </Alert>
        )}

        <TextField
          label="Target Price"
          type="number"
          value={alertPrice || ''}
          onChange={(e) => setAlertPrice(parseFloat(e.target.value))}
          fullWidth
          sx={{ mt: 1 }}
          InputProps={{ startAdornment: <Typography sx={{ mr: 0.5 }}>$</Typography> }}
        />

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          Trigger when price:
        </Typography>
        <RadioGroup
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
        >
          <FormControlLabel
            value="above"
            control={<Radio size="small" />}
            label={<Typography variant="body2">Goes above ${alertPrice?.toLocaleString() || '...'}</Typography>}
          />
          <FormControlLabel
            value="below"
            control={<Radio size="small" />}
            label={<Typography variant="body2">Drops below ${alertPrice?.toLocaleString() || '...'}</Typography>}
          />
          <FormControlLabel
            value="cross"
            control={<Radio size="small" />}
            label={<Typography variant="body2">Crosses ${alertPrice?.toLocaleString() || '...'} (either direction)</Typography>}
          />
        </RadioGroup>

        <TextField
          label="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          fullWidth
          multiline
          rows={2}
          sx={{ mt: 2 }}
          placeholder="e.g., Take profit at this level, or enter new position"
        />

        <FormControl fullWidth sx={{ mt: 2 }}>
          <InputLabel id="action-type-label">On Trigger Action</InputLabel>
          <Select
            labelId="action-type-label"
            value={actionType}
            label="On Trigger Action"
            onChange={(e) => setActionType(e.target.value)}
            size="small"
          >
            <MenuItem value="none">Notify only (default)</MenuItem>
            <MenuItem value="log">Log silently (no notification)</MenuItem>
            <MenuItem value="close_position">Close position (see note)</MenuItem>
          </Select>
        </FormControl>
        {actionType === 'close_position' && (
          <Typography variant="caption" sx={{ color: '#f59e0b', display: 'block', mt: 0.5 }}>
            Add the option symbol to close in the Note field above (e.g. C-BTC-90000-260328).
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!alertPrice || loading}
          onClick={handleCreate}
          sx={{ bgcolor: '#ffc107', color: '#000', '&:hover': { bgcolor: '#ffb300' } }}
          startIcon={loading ? <CircularProgress size={16} /> : <NotificationsIcon />}
        >
          {loading ? 'Creating...' : 'Create Alert'}
        </Button>
      </DialogActions>
    </Dialog>
  );
});

PayoffAlertDialog.displayName = 'PayoffAlertDialog';

export default PayoffAlertDialog;
