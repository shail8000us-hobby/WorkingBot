/**
 * Add Symbol Dialog
 *
 * Dialog for adding a new trading symbol to the portfolio.
 * Creates a new symbol configuration in config.yaml.
 */

import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  InputAdornment,
  FormHelperText,
} from '@mui/material';
import {
  Add as AddIcon,
  ShowChart as ChartIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import apiClient from '../utils/apiClient';

// Common Delta Exchange perpetual product IDs
const COMMON_PRODUCTS = [
  { symbol: 'BTCUSD', product_id: 27, name: 'Bitcoin Perpetual', tick_size: 0.5 },
  { symbol: 'ETHUSD', product_id: 3136, name: 'Ethereum Perpetual', tick_size: 0.05 },
  { symbol: 'SOLUSD', product_id: 92, name: 'Solana Perpetual', tick_size: 0.01 },
  { symbol: 'XRPUSD', product_id: 259, name: 'XRP Perpetual', tick_size: 0.0001 },
  { symbol: 'LINKUSD', product_id: 108, name: 'Chainlink Perpetual', tick_size: 0.001 },
  { symbol: 'DOTUSD', product_id: 107, name: 'Polkadot Perpetual', tick_size: 0.001 },
  { symbol: 'AVAXUSD', product_id: 106, name: 'Avalanche Perpetual', tick_size: 0.01 },
  { symbol: 'MATICUSD', product_id: 249, name: 'Polygon Perpetual', tick_size: 0.0001 },
];

export default function AddSymbolDialog({ open, onClose, onSuccess, existingSymbols = [] }) {
  const [formData, setFormData] = useState({
    symbol: '',
    product_id: '',
    mode: 'LONG',
    grid: {
      lower: '',
      upper: '',
      step: '',
      reference: '',
    },
    lot_size: '1',
    max_open_positions: '10',
    tick_size: '0.5',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [useCustomSymbol, setUseCustomSymbol] = useState(false);

  const handleInputChange = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setError('');
  }, []);

  const handleGridChange = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      grid: {
        ...prev.grid,
        [field]: value,
      },
    }));
    setError('');
  }, []);

  const handlePresetSelect = useCallback((preset) => {
    if (preset) {
      setFormData((prev) => ({
        ...prev,
        symbol: preset.symbol,
        product_id: preset.product_id.toString(),
        tick_size: preset.tick_size.toString(),
      }));
      setUseCustomSymbol(false);
    }
    setError('');
  }, []);

  const handleSubmit = async () => {
    // Validation
    if (!formData.symbol) {
      setError('Symbol is required');
      return;
    }
    if (!formData.product_id) {
      setError('Product ID is required');
      return;
    }
    if (!formData.grid.lower || !formData.grid.upper || !formData.grid.step) {
      setError('Grid configuration (lower, upper, step) is required');
      return;
    }

    const lower = parseFloat(formData.grid.lower);
    const upper = parseFloat(formData.grid.upper);
    const step = parseFloat(formData.grid.step);

    if (lower >= upper) {
      setError('Grid lower must be less than upper');
      return;
    }
    if (step <= 0) {
      setError('Grid step must be positive');
      return;
    }
    if ((upper - lower) / step > 200) {
      setError('Too many grid levels (max 200). Increase step size.');
      return;
    }

    // Check if symbol already exists
    const symbolName = formData.symbol.toUpperCase();
    if (existingSymbols.some((s) => s.toUpperCase() === symbolName)) {
      setError(`Symbol '${symbolName}' already exists in portfolio`);
      return;
    }

    setLoading(true);
    setError('');

    try {
      const payload = {
        symbol: symbolName,
        product_id: parseInt(formData.product_id),
        mode: formData.mode,
        enabled: false, // New symbols start disabled for safety
        grid: {
          lower: lower,
          upper: upper,
          step: step,
          reference: formData.grid.reference
            ? parseFloat(formData.grid.reference)
            : (lower + upper) / 2,
        },
        lot_size: parseInt(formData.lot_size) || 1,
        max_open_positions: parseInt(formData.max_open_positions) || 10,
        tick_size: formData.tick_size,
      };

      const response = await apiClient.request('PUT', '/api/config/symbols', payload);

      if (response.success) {
        onSuccess && onSuccess(symbolName);
        handleClose();
      } else {
        setError(response.error || 'Failed to create symbol');
      }
    } catch (err) {
      console.error('Failed to create symbol:', err);
      setError(err.message || 'Failed to create symbol');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFormData({
      symbol: '',
      product_id: '',
      mode: 'LONG',
      grid: { lower: '', upper: '', step: '', reference: '' },
      lot_size: '1',
      max_open_positions: '10',
      tick_size: '0.5',
    });
    setError('');
    setLoading(false);
    setUseCustomSymbol(false);
    onClose();
  };

  // Filter out already configured symbols from presets
  const availablePresets = COMMON_PRODUCTS.filter(
    (p) => !existingSymbols.some((s) => s.toUpperCase() === p.symbol)
  );

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { bgcolor: 'background.paper' },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AddIcon color="primary" />
        Add New Symbol
      </DialogTitle>

      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Alert severity="info" sx={{ mb: 3 }}>
            New symbols are created as <strong>disabled</strong> for safety. Enable them from the
            Portfolio view after verifying the configuration.
          </Alert>

          {/* Symbol Selection */}
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Select Symbol
          </Typography>

          {!useCustomSymbol && availablePresets.length > 0 ? (
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Choose from common symbols</InputLabel>
              <Select
                value={formData.symbol}
                label="Choose from common symbols"
                onChange={(e) => {
                  const preset = COMMON_PRODUCTS.find((p) => p.symbol === e.target.value);
                  handlePresetSelect(preset);
                }}
              >
                {availablePresets.map((preset) => (
                  <MenuItem key={preset.symbol} value={preset.symbol}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ChartIcon fontSize="small" color="primary" />
                      <Box>
                        <Typography variant="body1">{preset.symbol}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {preset.name} (ID: {preset.product_id})
                        </Typography>
                      </Box>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
              <FormHelperText>
                <Button size="small" onClick={() => setUseCustomSymbol(true)} sx={{ mt: 0.5 }}>
                  Or enter custom symbol
                </Button>
              </FormHelperText>
            </FormControl>
          ) : (
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField
                label="Symbol"
                value={formData.symbol}
                onChange={(e) => handleInputChange('symbol', e.target.value.toUpperCase())}
                placeholder="e.g., BTCUSD"
                sx={{ flex: 1 }}
              />
              <TextField
                label="Product ID"
                value={formData.product_id}
                onChange={(e) => handleInputChange('product_id', e.target.value)}
                placeholder="e.g., 27"
                type="number"
                sx={{ flex: 1 }}
              />
            </Box>
          )}

          {/* Mode Selection */}
          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel>Trading Mode</InputLabel>
            <Select
              value={formData.mode}
              label="Trading Mode"
              onChange={(e) => handleInputChange('mode', e.target.value)}
            >
              <MenuItem value="LONG">LONG (Buy low, sell high)</MenuItem>
              <MenuItem value="SHORT">SHORT (Sell high, buy low)</MenuItem>
            </Select>
          </FormControl>

          <Divider sx={{ my: 2 }} />

          {/* Grid Configuration */}
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
            Grid Configuration
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              label="Lower Bound"
              value={formData.grid.lower}
              onChange={(e) => handleGridChange('lower', e.target.value)}
              type="number"
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
              }}
              sx={{ flex: 1 }}
              required
            />
            <TextField
              label="Upper Bound"
              value={formData.grid.upper}
              onChange={(e) => handleGridChange('upper', e.target.value)}
              type="number"
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
              }}
              sx={{ flex: 1 }}
              required
            />
          </Box>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              label="Grid Step"
              value={formData.grid.step}
              onChange={(e) => handleGridChange('step', e.target.value)}
              type="number"
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
              }}
              helperText="Distance between grid levels"
              sx={{ flex: 1 }}
              required
            />
            <TextField
              label="Reference Price"
              value={formData.grid.reference}
              onChange={(e) => handleGridChange('reference', e.target.value)}
              type="number"
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
              }}
              helperText="Optional (default: midpoint)"
              sx={{ flex: 1 }}
            />
          </Box>

          <Divider sx={{ my: 2 }} />

          {/* Position Sizing */}
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
            Position Sizing
          </Typography>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              label="Lot Size"
              value={formData.lot_size}
              onChange={(e) => handleInputChange('lot_size', e.target.value)}
              type="number"
              helperText="Contracts per order"
              sx={{ flex: 1 }}
            />
            <TextField
              label="Max Open Positions"
              value={formData.max_open_positions}
              onChange={(e) => handleInputChange('max_open_positions', e.target.value)}
              type="number"
              helperText="Maximum simultaneous positions"
              sx={{ flex: 1 }}
            />
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={loading || !formData.symbol || !formData.product_id}
          startIcon={loading ? <CircularProgress size={16} /> : <AddIcon />}
        >
          {loading ? 'Creating...' : 'Add Symbol'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
