/**
 * Take Profit Dialog Component
 *
 * Modal dialog for configuring take profit settings per strike.
 * Allows user to set target profit amount and quantity to exit.
 *
 * Created: February 3, 2026
 *
 * @sealed — handleSave() + handleRemove()
 * Sealed: Mar 12, 2026 — Test: src/components/options/__tests__/test_sealed_take_profit_dialog.test.js
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Chip,
  Alert,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import { TrendingUp, Warning as WarningIcon } from '@mui/icons-material';
import axios from 'axios';

const api = axios.create({ baseURL: '' });

export default function TakeProfitDialog({ open, onClose, position, settings, onUpdate }) {
  const [targetProfit, setTargetProfit] = useState('');
  const [exitQuantity, setExitQuantity] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Extract position details
  const symbol = position?.product_symbol || '';
  const currentSize = Math.abs(position?.size || 0);
  const currentPnl = position?.unrealized_pnl || 0;
  const currentProfit = currentPnl > 0 ? currentPnl : 0;

  // Initialize form with existing settings
  useEffect(() => {
    if (settings) {
      setTargetProfit(settings.target_profit?.toString() || '');
      setExitQuantity(settings.exit_quantity?.toString() || '');
    } else {
      setTargetProfit('');
      setExitQuantity('');
    }
    setError('');
  }, [settings, open]);

  // 🔒 SEALED #67 — test: test_sealed_take_profit_dialog.test.js
  const handleSave = async () => {
    setError('');

    // Validation
    const profit = parseFloat(targetProfit);
    const quantity = parseInt(exitQuantity);

    if (isNaN(profit) || profit === 0) {
      setError('Target must be a non-zero number (positive for profit, negative for loss)');
      return;
    }

    if (isNaN(quantity) || quantity <= 0) {
      setError('Exit quantity must be a positive integer');
      return;
    }

    if (quantity > currentSize) {
      setError(`Exit quantity cannot exceed current position size (${currentSize} lots)`);
      return;
    }

    setSaving(true);
    try {
      const { data } = await api.post('/api/options/take-profit/strike/set', {
        symbol,
        target_profit: profit,
        exit_quantity: quantity,
      });

      if (data.success) {
        onUpdate(symbol, {
          target_profit: profit,
          exit_quantity: quantity,
          enabled: true,
          triggered: false,
        });
        onClose();
      } else {
        setError(data.error || 'Failed to set take profit');
      }
    } catch (err) {
      console.error('Failed to save take profit:', err);
      setError(err.response?.data?.error || 'Failed to save take profit');
    } finally {
      setSaving(false);
    }
  };

  // 🔒 SEALED #67 — test: test_sealed_take_profit_dialog.test.js
  const handleRemove = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/api/options/take-profit/strike/remove', {
        symbol,
      });

      if (data.success) {
        onUpdate(symbol, null);
        onClose();
      } else {
        setError(data.error || 'Failed to remove take profit');
      }
    } catch (err) {
      console.error('Failed to remove take profit:', err);
      setError(err.response?.data?.error || 'Failed to remove take profit');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <TrendingUp color="success" />
          <Typography variant="h6">Target P&L Settings</Typography>
          <Chip label="🔒 SEALED" size="small" sx={{ fontSize: '0.6rem', height: 16, bgcolor: 'action.selected', color: 'text.secondary', ml: 0.5 }} />
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* Position Info */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="body2" fontWeight="bold" gutterBottom>
            {symbol}
          </Typography>
          <Box display="flex" gap={2} mt={1}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Quantity
              </Typography>
              <Typography variant="body2" fontWeight="bold">
                {currentSize} lots
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Current P&L
              </Typography>
              <Typography
                variant="body2"
                fontWeight="bold"
                color={currentPnl > 0 ? 'success.main' : currentPnl < 0 ? 'error.main' : 'text.primary'}
              >
                ${currentPnl.toFixed(2)}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Help Text */}
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="caption">
            <strong>Profit Target (positive):</strong> Exit when profit REACHES the target (e.g., $20 = exit when profit is $20 or more).
            <br />
            <strong>Loss Limit (negative):</strong> Exit when loss IMPROVES to the target (e.g., -$50 = exit when loss improves from -$100 to -$50 or better).
            <br />
            The system will automatically place a limit order to close the specified quantity when your P&L reaches the target.
          </Typography>
        </Alert>

        {/* Input Fields */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Target P&L"
            type="number"
            value={targetProfit}
            onChange={(e) => setTargetProfit(e.target.value)}
            onKeyDown={(e) => e.stopPropagation()}
            placeholder="e.g., 20 or -10"
            fullWidth
            InputProps={{
              startAdornment: <InputAdornment position="start">$</InputAdornment>,
            }}
            helperText="Exit when position P&L reaches this (positive for profit, negative for loss)"
          />

          <TextField
            label="Quantity to Exit"
            type="number"
            value={exitQuantity}
            onChange={(e) => setExitQuantity(e.target.value)}
            onKeyDown={(e) => e.stopPropagation()}
            placeholder="e.g., 10"
            fullWidth
            InputProps={{
              endAdornment: <InputAdornment position="end">lots</InputAdornment>,
            }}
            helperText={`Number of contracts to close (max: ${currentSize} lots)`}
            error={parseInt(exitQuantity) > currentSize}
          />
        </Box>

        {/* Example Calculation */}
        {targetProfit && exitQuantity && (
          <Box sx={{ mt: 2, p: 2, bgcolor: parseFloat(targetProfit) > 0 ? 'success.dark' : 'error.dark', borderRadius: 1, opacity: 0.8 }}>
            <Typography variant="caption" display="block" gutterBottom>
              <strong>Example:</strong>
            </Typography>
            {parseFloat(targetProfit) > 0 ? (
              <Typography variant="caption" display="block">
                When your <strong>{symbol}</strong> position profit reaches{' '}
                <strong>${targetProfit}</strong> or more, the system will place a limit order
                to close <strong>{exitQuantity} lots</strong>.
              </Typography>
            ) : (
              <Typography variant="caption" display="block">
                When your <strong>{symbol}</strong> position loss improves to{' '}
                <strong>${targetProfit}</strong> or better (less negative), the system will place a limit order
                to close <strong>{exitQuantity} lots</strong>.
                <br />
                <em>Example: Current loss -$100 → Triggers when loss improves to ${targetProfit} or better (like -${Math.abs(parseFloat(targetProfit)) - 10}).</em>
              </Typography>
            )}
            {parseInt(exitQuantity) < currentSize && (
              <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'warning.light' }}>
                ⚠️ Remaining {currentSize - parseInt(exitQuantity)} lots will stay open and you
                can set a new target for them.
              </Typography>
            )}
          </Box>
        )}

        {/* Error Message */}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        {settings && (
          <Button
            onClick={handleRemove}
            color="error"
            disabled={saving}
            sx={{ mr: 'auto' }}
          >
            Remove TP
          </Button>
        )}
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          color="success"
          disabled={saving || !targetProfit || !exitQuantity}
          startIcon={saving ? <CircularProgress size={16} /> : <TrendingUp />}
        >
          {saving ? 'Saving...' : 'Set Target'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
