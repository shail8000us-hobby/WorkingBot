/**
 * Order Dialog Component
 * ======================
 * Modal dialog for placing buy/sell orders from the options chain.
 *
 * Created: January 5, 2026
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
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  CircularProgress,
  Divider,
  Chip,
} from '@mui/material';
import { optionsChainAPI } from './services/chainAPI';

// Format helpers
const formatPrice = (price) => {
  if (!price) return '-';
  return `$${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const formatIV = (iv) => {
  if (!iv) return '-';
  return `${(Number(iv) * 100).toFixed(1)}%`;
};

const OrderDialog = ({
  open,
  onClose,
  option, // { symbol, strike, type (call/put), side, bid, ask, iv, delta }
  spotPrice,
  onSuccess,
  onError,
}) => {
  const [side, setSide] = useState(option?.side || 'buy');
  const [orderType, setOrderType] = useState('market');
  const [size, setSize] = useState(1);
  const [limitPrice, setLimitPrice] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [ticker, setTicker] = useState(null);

  // Set initial side when option changes
  useEffect(() => {
    if (option?.side) {
      setSide(option.side);
    }
  }, [option?.side]);

  // Fetch latest ticker when dialog opens
  useEffect(() => {
    const fetchTicker = async () => {
      try {
        const data = await optionsChainAPI.getTicker(option.symbol);
        setTicker(data);
      } catch (err) {
        console.error('Failed to fetch ticker:', err);
      }
    };

    if (open && option?.symbol) {
      fetchTicker();
    }
  }, [open, option?.symbol]);

  // Set initial limit price when ticker loads
  useEffect(() => {
    if (ticker) {
      // Default to mid-price
      const mid = (ticker.bid + ticker.ask) / 2;
      setLimitPrice(mid.toFixed(2));
    }
  }, [ticker]);

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);

    try {
      const orderParams = {
        symbol: option.symbol,
        side: side,
        size: parseInt(size),
        order_type: orderType,
      };

      if (orderType === 'limit') {
        orderParams.limit_price = parseFloat(limitPrice);
      }

      const result = await optionsChainAPI.placeOrder(orderParams);

      if (result.success) {
        onSuccess?.(result);
        onClose();
      } else {
        const errorMsg = result.error || 'Order failed';
        setError(errorMsg);
        onError?.(errorMsg);
      }
    } catch (err) {
      const errorMsg = err.message || 'Failed to place order';
      setError(errorMsg);
      onError?.(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setError(null);
      setSide('buy');
      setOrderType('market');
      setSize(1);
      setLimitPrice('');
      onClose();
    }
  };

  if (!option) return null;

  const isCall = option.type === 'call';
  const currentBid = ticker?.bid || option.bid;
  const currentAsk = ticker?.ask || option.ask;
  const midPrice = currentBid && currentAsk ? (currentBid + currentAsk) / 2 : 0;
  const spread = currentBid && currentAsk ? ((currentAsk - currentBid) / midPrice) * 100 : 0;

  // Estimated cost/proceeds
  const estPrice =
    orderType === 'market'
      ? side === 'buy'
        ? currentAsk
        : currentBid
      : parseFloat(limitPrice) || 0;
  const estTotal = estPrice * parseInt(size || 0);

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { bgcolor: 'background.paper', backgroundImage: 'none' },
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip label={isCall ? 'CALL' : 'PUT'} color={isCall ? 'success' : 'error'} size="small" />
          <Typography variant="h6">{option.symbol}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Strike: ${option.strike?.toLocaleString()} | Spot: {formatPrice(spotPrice)}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {/* Market Data */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Bid
              </Typography>
              <Typography variant="body1" color="success.main" fontWeight="bold">
                {formatPrice(currentBid)}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Spread
              </Typography>
              <Typography variant="body1">{spread.toFixed(2)}%</Typography>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" color="text.secondary">
                Ask
              </Typography>
              <Typography variant="body1" color="error.main" fontWeight="bold">
                {formatPrice(currentAsk)}
              </Typography>
            </Box>
          </Box>
          <Divider sx={{ my: 1 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="caption" color="text.secondary">
              IV: {formatIV(ticker?.iv || option.iv)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Delta: {(ticker?.delta || option.delta || 0).toFixed(2)}
            </Typography>
          </Box>
        </Box>

        {/* Buy/Sell Toggle */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Direction
          </Typography>
          <ToggleButtonGroup
            value={side}
            exclusive
            onChange={(e, val) => val && setSide(val)}
            fullWidth
          >
            <ToggleButton
              value="buy"
              sx={{
                '&.Mui-selected': {
                  bgcolor: 'success.dark',
                  color: 'white',
                  '&:hover': { bgcolor: 'success.main' },
                },
              }}
            >
              BUY
            </ToggleButton>
            <ToggleButton
              value="sell"
              sx={{
                '&.Mui-selected': {
                  bgcolor: 'error.dark',
                  color: 'white',
                  '&:hover': { bgcolor: 'error.main' },
                },
              }}
            >
              SELL
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Order Type Toggle */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Order Type
          </Typography>
          <ToggleButtonGroup
            value={orderType}
            exclusive
            onChange={(e, val) => val && setOrderType(val)}
            fullWidth
            size="small"
          >
            <ToggleButton value="market">Market</ToggleButton>
            <ToggleButton value="limit">Limit</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Size Input */}
        <Box sx={{ mb: 3 }}>
          <TextField
            label="Quantity (Contracts)"
            type="number"
            value={size}
            onChange={(e) => setSize(Math.max(1, parseInt(e.target.value) || 1))}
            inputProps={{ min: 1 }}
            fullWidth
          />
        </Box>

        {/* Limit Price Input */}
        {orderType === 'limit' && (
          <Box sx={{ mb: 3 }}>
            <TextField
              label="Limit Price ($)"
              type="number"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              inputProps={{ min: 0, step: 0.01 }}
              fullWidth
              helperText={`Mid: ${formatPrice(midPrice)}`}
            />
          </Box>
        )}

        {/* Order Summary */}
        <Box
          sx={{
            p: 2,
            bgcolor: side === 'buy' ? 'success.dark' : 'error.dark',
            borderRadius: 1,
            color: 'white',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">
              {side.toUpperCase()} {size} × {option.symbol.split('-').slice(0, 3).join('-')}
            </Typography>
            <Typography variant="body2">
              @ {orderType === 'market' ? 'MARKET' : formatPrice(limitPrice)}
            </Typography>
          </Box>
          <Divider sx={{ borderColor: 'rgba(255,255,255,0.3)', my: 1 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="body1" fontWeight="bold">
              Est. {side === 'buy' ? 'Cost' : 'Proceeds'}:
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              {formatPrice(estTotal)}
            </Typography>
          </Box>
        </Box>

        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={side === 'buy' ? 'success' : 'error'}
          onClick={handleSubmit}
          disabled={loading || (orderType === 'limit' && !limitPrice)}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {loading
            ? 'Placing Order...'
            : `${side.toUpperCase()} ${size} Contract${size > 1 ? 's' : ''}`}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default OrderDialog;
