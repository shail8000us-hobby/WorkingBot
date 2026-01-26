/**
 * Native MV Straddle Form - Full Featured
 * Auto-loading with proper error handling
 * 
 * MV Straddle = Native Delta Exchange India product (contract_type: move_options)
 * Symbol format: MV-BTC-89400-250126
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Divider,
  CircularProgress,
  ToggleButtonGroup,
  ToggleButton,
  Chip
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw
} from 'lucide-react';

const MVStraddleNativeForm = ({ onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    underlying: 'BTC',
    expiry: '',
    strike: '',
    side: 'buy',
    quantity: 1,
    orderType: 'limit_order',
    limitPrice: ''
  });

  const [availableExpiries, setAvailableExpiries] = useState([]);
  const [availableStrikes, setAvailableStrikes] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchExpiries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/mv-straddle/expirations?underlying=${formData.underlying}`);
      const data = await response.json();
      
      if (data.success) {
        setAvailableExpiries(data.expirations);
      } else {
        setError(data.error || 'Failed to load expirations');
      }
    } catch (err) {
      setError('Failed to load expirations');
    } finally {
      setLoading(false);
    }
  }, [formData.underlying]);

  const fetchStrikes = useCallback(async () => {
    if (!formData.expiry) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/mv-straddle/strikes?underlying=${formData.underlying}&expiry=${formData.expiry}`
      );
      const data = await response.json();
      
      if (data.success) {
        setAvailableStrikes(data.strikes);
      } else {
        setError(data.error || 'Failed to load strikes');
      }
    } catch (err) {
      setError('Failed to load strikes');
    } finally {
      setLoading(false);
    }
  }, [formData.underlying, formData.expiry]);

  const fetchPreview = useCallback(async () => {
    if (!formData.expiry || !formData.strike) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/mv-straddle/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          underlying: formData.underlying,
          expiry: formData.expiry,
          strike: formData.strike,
          side: formData.side,
          quantity: formData.quantity
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setPreview(data.preview);
        // Auto-fill limit price with mark price for convenience
        if (formData.orderType === 'limit_order' && !formData.limitPrice && data.preview.mark_price) {
          setFormData(prev => ({ ...prev, limitPrice: data.preview.mark_price.toFixed(2) }));
        }
      } else {
        setError(data.error || 'Failed to generate preview');
      }
    } catch (err) {
      setError('Failed to generate preview');
    } finally {
      setLoading(false);
    }
  }, [formData.underlying, formData.expiry, formData.strike, formData.side, formData.quantity, formData.orderType, formData.limitPrice]);

  // Auto-load expiries on mount
  useEffect(() => {
    fetchExpiries();
  }, [fetchExpiries]);

  // Auto-load strikes when expiry changes
  useEffect(() => {
    if (formData.expiry) {
      fetchStrikes();
    }
  }, [formData.expiry, fetchStrikes]);

  // Auto-load preview when strike changes
  useEffect(() => {
    if (formData.strike && formData.quantity > 0) {
      fetchPreview();
    }
  }, [formData.strike, formData.quantity, formData.side, fetchPreview]);

  const handleSubmit = async () => {
    // Clear any previous errors
    setError(null);
    
    // Validation
    if (!formData.expiry || !formData.strike) {
      setError('Please select expiry and strike');
      return;
    }
    
    if (formData.orderType === 'limit_order') {
      const price = parseFloat(formData.limitPrice);
      if (!formData.limitPrice || isNaN(price) || price <= 0) {
        setError('Please enter a valid limit price greater than 0');
        return;
      }
    }
    
    setLoading(true);
    try {
      // Construct MV Straddle symbol: MV-{UNDERLYING}-{STRIKE}-{EXPIRY}
      const symbol = `MV-${formData.underlying}-${formData.strike}-${formData.expiry}`;
      
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol,
          side: formData.side,
          quantity: formData.quantity,
          orderType: formData.orderType,
          limitPrice: formData.orderType === 'limit_order' ? parseFloat(formData.limitPrice) : undefined
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        onSubmit(data);
      } else {
        setError(data.error || 'Failed to place order');
      }
    } catch (err) {
      setError('Failed to place order: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper elevation={0} sx={{ p: 3, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          MV Straddle Order Form
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Step 1: Load Expiries */}
          <Box>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Underlying</InputLabel>
              <Select
                value={formData.underlying}
                onChange={(e) => {
                  setFormData({ ...formData, underlying: e.target.value, expiry: '', strike: '' });
                  setAvailableExpiries([]);
                  setAvailableStrikes([]);
                }}
                label="Underlying"
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 300
                    }
                  }
                }}
              >
                <MenuItem value="BTC">Bitcoin (BTC)</MenuItem>
                <MenuItem value="ETH">Ethereum (ETH)</MenuItem>
              </Select>
            </FormControl>

            <Button
              variant="outlined"
              onClick={fetchExpiries}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} /> : <RefreshCw size={18} />}
              fullWidth
            >
              {availableExpiries.length > 0 ? 'Refresh Expiries' : 'Load Expiries'}
            </Button>
          </Box>

          {/* Step 2: Select Expiry */}
          {availableExpiries.length > 0 && (
            <FormControl fullWidth>
              <InputLabel>Expiry Date</InputLabel>
              <Select
                value={formData.expiry}
                onChange={(e) => {
                  setFormData({ ...formData, expiry: e.target.value, strike: '' });
                  setAvailableStrikes([]);
                }}
                label="Expiry Date"
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 300
                    }
                  }
                }}
              >
                {availableExpiries.map((exp) => (
                  <MenuItem key={exp.expiry} value={exp.expiry}>
                    {exp.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {/* Step 3: Load Strikes */}
          {formData.expiry && (
            <Button
              variant="outlined"
              onClick={fetchStrikes}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} /> : <RefreshCw size={18} />}
              fullWidth
            >
              {availableStrikes.length > 0 ? 'Refresh Strikes' : 'Load Strikes'}
            </Button>
          )}

          {/* Step 4: Select Strike */}
          {availableStrikes.length > 0 && (
            <FormControl fullWidth>
              <InputLabel>Strike Price</InputLabel>
              <Select
                value={formData.strike}
                onChange={(e) => setFormData({ ...formData, strike: e.target.value })}
                label="Strike Price"
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 400
                    }
                  }
                }}
              >
                {availableStrikes.map((strike) => (
                  <MenuItem key={strike.strike} value={strike.strike}>
                    ${strike.strike.toLocaleString()}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {/* Step 5: Configure Order */}
          {formData.strike && (
            <>
              <Divider />

              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Direction
                </Typography>
                <ToggleButtonGroup
                  value={formData.side}
                  exclusive
                  onChange={(e, value) => value && setFormData({ ...formData, side: value })}
                  fullWidth
                >
                  <ToggleButton value="buy">
                    <TrendingUp size={18} style={{ marginRight: 8 }} />
                    Buy
                  </ToggleButton>
                  <ToggleButton value="sell">
                    <TrendingDown size={18} style={{ marginRight: 8 }} />
                    Sell
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              <TextField
                label="Quantity"
                type="number"
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 })}
                fullWidth
                inputProps={{ min: 1 }}
              />

              <FormControl fullWidth>
                <InputLabel>Order Type</InputLabel>
                <Select
                  value={formData.orderType}
                  onChange={(e) => setFormData({ ...formData, orderType: e.target.value })}
                  label="Order Type"
                  MenuProps={{
                    PaperProps: {
                      style: {
                        maxHeight: 200
                      }
                    }
                  }}
                >
                  <MenuItem value="market_order">Market Order</MenuItem>
                  <MenuItem value="limit_order">Limit Order</MenuItem>
                </Select>
              </FormControl>

              {formData.orderType === 'limit_order' && (
                <TextField
                  label="Limit Price"
                  type="number"
                  value={formData.limitPrice}
                  onChange={(e) => {
                    setFormData({ ...formData, limitPrice: e.target.value });
                    setError(null);
                  }}
                  fullWidth
                  required
                  error={!formData.limitPrice}
                  helperText={!formData.limitPrice ? 'Required for limit orders' : 'Enter price or click Preview to auto-fill'}
                  inputProps={{ step: 0.1, min: 0.01 }}
                />
              )}

              <Button
                variant="outlined"
                onClick={fetchPreview}
                disabled={loading}
                startIcon={loading ? <CircularProgress size={20} /> : <RefreshCw size={18} />}
                fullWidth
              >
                Preview Order
              </Button>

              {preview && (
                <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
                    Market Data
                  </Typography>
                  
                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Best Bid</Typography>
                      <Typography variant="body1" fontWeight="bold" color="success.main">
                        ${preview.best_bid?.toFixed(2) || 'N/A'}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Best Ask</Typography>
                      <Typography variant="body1" fontWeight="bold" color="error.main">
                        ${preview.best_ask?.toFixed(2) || 'N/A'}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Mark Price</Typography>
                      <Typography variant="body1" fontWeight="bold">
                        ${preview.mark_price?.toFixed(2)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Last Price</Typography>
                      <Typography variant="body1" fontWeight="bold">
                        ${preview.last_price?.toFixed(2) || 'N/A'}
                      </Typography>
                    </Box>
                  </Box>

                  <Divider sx={{ my: 1.5 }} />

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Symbol</Typography>
                      <Typography variant="body2" fontWeight="600">{preview.symbol}</Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                      <Typography variant="caption" color="text.secondary">Est. Cost</Typography>
                      <Typography variant="h6" fontWeight="bold" color="primary.main">
                        ${preview.estimated_cost?.toFixed(2)}
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              )}

              <Divider />

              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  onClick={handleSubmit}
                  disabled={loading}
                  fullWidth
                  size="large"
                >
                  {loading ? <CircularProgress size={24} /> : 'Place Order'}
                </Button>
                <Button variant="outlined" onClick={onCancel} disabled={loading}>
                  Cancel
                </Button>
              </Box>
            </>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default MVStraddleNativeForm;
