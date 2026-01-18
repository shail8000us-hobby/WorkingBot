/**
 * Futures Trade Dialog
 *
 * Dialog for placing Buy/Sell orders on futures positions.
 * Supports both market and limit orders with size/price inputs.
 *
 * Created: January 18, 2026
 * Purpose: UI for futures trading operations
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControlLabel,
  Checkbox,
  Typography,
  Box,
  Alert,
  CircularProgress,
  InputAdornment,
  Chip,
} from '@mui/material';
import { TrendingUp as BuyIcon, TrendingDown as SellIcon } from '@mui/icons-material';
import api from '../../utils/apiShim';

const FuturesTradeDialog = ({ open, onClose, position, side }) => {
  // State
  const [size, setSize] = useState('');
  const [price, setPrice] = useState('');
  const [isMarket, setIsMarket] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);

  // Reset form when dialog opens
  useEffect(() => {
    if (open && position) {
      setSize('');
      setPrice(position.mark_price?.toFixed(2) || '');
      setIsMarket(false);
      setError(null);
      fetchCurrentPrice();
    }
  }, [open, position]);

  // Fetch current market price
  const fetchCurrentPrice = async () => {
    if (!position?.symbol) return;

    try {
      const { data } = await api.get(`/api/futures/ticker/${position.symbol}`);
      if (data?.success) {
        const markPrice = data.ticker?.mark_price;
        if (markPrice) {
          setCurrentPrice(markPrice);
          setPrice(markPrice.toFixed(2));
        }
      }
    } catch (err) {
      console.error('Failed to fetch ticker:', err);
    }
  };

  // Handle market order toggle
  const handleMarketToggle = (event) => {
    setIsMarket(event.target.checked);
    if (event.target.checked && currentPrice) {
      setPrice(currentPrice.toFixed(2));
    }
  };

  // Handle submit
  const handleSubmit = async () => {
    // Validate inputs
    if (!size || parseFloat(size) <= 0) {
      setError('Size must be greater than 0');
      return;
    }

    if (!isMarket && (!price || parseFloat(price) <= 0)) {
      setError('Price must be greater than 0 for limit orders');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const endpoint = side === 'buy' ? '/api/futures/trade/buy' : '/api/futures/trade/sell';

      const { data } = await api.post(endpoint, {
        symbol: position.symbol,
        product_id: position.product_id,
        size: parseInt(size),
        price: parseFloat(price),
        is_market: isMarket,
      });

      if (data?.success) {
        // Success - close dialog
        onClose(true); // Pass true to indicate successful trade
      } else {
        setError(data?.error || 'Failed to place order');
      }
    } catch (err) {
      console.error('Failed to place order:', err);
      setError(err.response?.data?.error || err.message || 'Failed to place order');
    } finally {
      setLoading(false);
    }
  };

  if (!position) return null;

  const isBuy = side === 'buy';
  const sideColor = isBuy ? 'success' : 'error';
  const SideIcon = isBuy ? BuyIcon : SellIcon;

  return (
    <Dialog open={open} onClose={() => onClose(false)} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SideIcon color={sideColor} />
          <Typography variant="h6">
            {isBuy ? 'Buy' : 'Sell'} {position.symbol}
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* Current Position Info */}
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(14, 165, 233, 0.1)', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Current Position
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
            <Typography variant="body2">
              Size: <strong>{Math.abs(position.size)}</strong>
            </Typography>
            <Typography variant="body2">
              Entry: <strong>${position.entry_price?.toFixed(2)}</strong>
            </Typography>
            <Typography variant="body2">
              Mark: <strong>${position.mark_price?.toFixed(2)}</strong>
            </Typography>
          </Box>
        </Box>

        {/* Current Market Price */}
        {currentPrice && (
          <Box sx={{ mb: 2 }}>
            <Chip label={`Market Price: $${currentPrice.toFixed(2)}`} color="info" size="small" />
          </Box>
        )}

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Size Input */}
        <TextField
          label="Size (Lots)"
          type="number"
          value={size}
          onChange={(e) => setSize(e.target.value)}
          fullWidth
          required
          sx={{ mb: 2 }}
          InputProps={{
            inputProps: { min: 1, step: 1 },
          }}
          helperText="Number of contracts to trade"
        />

        {/* Market Order Checkbox */}
        <FormControlLabel
          control={<Checkbox checked={isMarket} onChange={handleMarketToggle} color="primary" />}
          label="Market Order (Execute at current market price)"
          sx={{ mb: 2 }}
        />

        {/* Price Input (disabled for market orders) */}
        <TextField
          label="Limit Price"
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          fullWidth
          required={!isMarket}
          disabled={isMarket}
          InputProps={{
            startAdornment: <InputAdornment position="start">$</InputAdornment>,
            inputProps: { min: 0, step: 0.01 },
          }}
          helperText={
            isMarket
              ? 'Price will be determined at execution'
              : 'Order will execute at this price or better'
          }
        />

        {/* Order Summary */}
        {size && price && (
          <Box sx={{ mt: 2, p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Order Summary
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              {isBuy ? 'Buying' : 'Selling'} <strong>{size}</strong> lots
              {isMarket ? ' at market price' : ` at $${parseFloat(price).toFixed(2)}`}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={() => onClose(false)} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color={sideColor}
          disabled={loading || !size || (!isMarket && !price)}
          startIcon={loading ? <CircularProgress size={16} /> : <SideIcon />}
        >
          {loading ? 'Placing Order...' : `${isBuy ? 'Buy' : 'Sell'} ${position.symbol}`}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FuturesTradeDialog;
