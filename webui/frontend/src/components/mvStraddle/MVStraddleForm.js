/**
 * MV Straddle Trading Form - Full Implementation
 * Native Delta Exchange MV Straddle product with complete feature set
 */
import React, { useState, useEffect } from 'react';
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
  Grid,
  Chip,
  LinearProgress,
  Card,
  CardContent,
  Stack
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  LineChart,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  DollarSign
} from 'lucide-react';

const MVStraddleForm = ({ onSubmit, onCancel }) => {
  console.log('[MVStraddleForm] Component rendering...');
  
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

  console.log('[MVStraddleForm] State:', { 
    expiries: availableExpiries.length, 
    strikes: availableStrikes.length, 
    hasPreview: !!preview,
    loading 
  });

  // Fetch expiries - simple version without useCallback
  const fetchExpiries = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/mv-straddle/expirations?underlying=${formData.underlying}`);
      const data = await response.json();
      
      if (data.success) {
        setAvailableExpiries(data.expirations);
        // Auto-select first expiry
        if (data.expirations.length > 0 && !formData.expiry) {
          setFormData(prev => ({ ...prev, expiry: data.expirations[0].expiry }));
        }
      } else {
        setError(data.error || 'Failed to load expirations');
      }
    } catch (err) {
      setError('Failed to load expirations: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch strikes - simple version
  const fetchStrikes = async () => {
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
        // Auto-select ATM strike
        if (data.atm_strike && !formData.strike) {
          setFormData(prev => ({ ...prev, strike: data.atm_strike }));
        }
      } else {
        setError(data.error || 'Failed to load strikes');
      }
    } catch (err) {
      setError('Failed to load strikes: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch preview - simple version
  const fetchPreview = async () => {
    if (!formData.expiry || !formData.strike || !formData.quantity) return;
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
        // Auto-fill limit price
        if (formData.orderType === 'limit_order' && !formData.limitPrice) {
          const suggestedPrice = formData.side === 'buy' 
            ? data.preview.best_ask 
            : data.preview.best_bid;
          if (suggestedPrice) {
            setFormData(prev => ({ ...prev, limitPrice: suggestedPrice.toFixed(2) }));
          }
        }
      } else {
        setError(data.error || 'Failed to generate preview');
      }
    } catch (err) {
      setError('Failed to generate preview: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load expiries on mount only
  useEffect(() => {
    fetchExpiries();
  }, []); // Empty deps - run once on mount

  // Load strikes when expiry changes
  useEffect(() => {
    if (formData.expiry && availableStrikes.length === 0) {
      fetchStrikes();
    }
  }, [formData.expiry]); // Only when expiry changes

  // Load preview when strike/quantity/side changes (debounced)
  useEffect(() => {
    if (formData.strike && formData.quantity > 0) {
      const timer = setTimeout(() => {
        fetchPreview();
      }, 300); // 300ms debounce
      return () => clearTimeout(timer);
    }
  }, [formData.strike, formData.quantity, formData.side]); // Only these deps

  const handleSubmit = async () => {
    setError(null);
    
    // Validation
    if (!formData.expiry || !formData.strike) {
      setError('Please select expiry and strike');
      return;
    }
    
    if (formData.orderType === 'limit_order' && !formData.limitPrice) {
      setError('Limit price required for limit orders');
      return;
    }
    
    setLoading(true);
    try {
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
    <Box sx={{ p: 2 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Left Column - Form */}
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="h6" sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 1 }}>
              <LineChart size={24} />
              MV Straddle Order
            </Typography>

            <Stack spacing={3}>
              {/* Underlying */}
              <FormControl fullWidth size="small">
                <InputLabel>Underlying</InputLabel>
                <Select
                  value={formData.underlying}
                  onChange={(e) => {
                    setFormData({ ...formData, underlying: e.target.value, expiry: '', strike: '' });
                    setAvailableExpiries([]);
                    setAvailableStrikes([]);
                    setPreview(null);
                  }}
                  label="Underlying"
                  native={false}
                >
                  <MenuItem value="BTC">Bitcoin (BTC)</MenuItem>
                  <MenuItem value="ETH">Ethereum (ETH)</MenuItem>
                </Select>
              </FormControl>

              {/* Expiry */}
              <FormControl fullWidth size="small" disabled={availableExpiries.length === 0}>
                <InputLabel>Expiry Date</InputLabel>
                <Select
                  value={formData.expiry}
                  onChange={(e) => {
                    setFormData({ ...formData, expiry: e.target.value, strike: '' });
                    setAvailableStrikes([]);
                    setPreview(null);
                  }}
                  label="Expiry Date"
                  native={false}
                >
                  {availableExpiries.map((exp) => (
                    <MenuItem key={exp.expiry} value={exp.expiry}>
                      {exp.label} {exp.days_to_expiry <= 1 && '⚡'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Strike */}
              <FormControl fullWidth size="small" disabled={availableStrikes.length === 0}>
                <InputLabel>Strike Price</InputLabel>
                <Select
                  value={formData.strike}
                  onChange={(e) => {
                    setFormData({ ...formData, strike: e.target.value });
                    setPreview(null);
                  }}
                  label="Strike Price"
                  native={false}
                >
                  {availableStrikes.map((strike) => (
                    <MenuItem key={strike.strike} value={strike.strike}>
                      ${strike.strike.toLocaleString()}
                      {strike.is_atm && ' (ATM)'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Divider />

              {/* Direction */}
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Direction
                </Typography>
                <ToggleButtonGroup
                  value={formData.side}
                  exclusive
                  onChange={(e, value) => {
                    if (value) {
                      setFormData({ ...formData, side: value, limitPrice: '' });
                      setPreview(null);
                    }
                  }}
                  fullWidth
                  size="small"
                >
                  <ToggleButton value="buy" sx={{ py: 1.5 }}>
                    <TrendingUp size={18} style={{ marginRight: 8 }} />
                    Buy (Long)
                  </ToggleButton>
                  <ToggleButton value="sell" sx={{ py: 1.5 }}>
                    <TrendingDown size={18} style={{ marginRight: 8 }} />
                    Sell (Short)
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              {/* Quantity */}
              <TextField
                label="Quantity"
                type="number"
                value={formData.quantity}
                onChange={(e) => {
                  setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 });
                  setPreview(null);
                }}
                size="small"
                fullWidth
                inputProps={{ min: 1, step: 1 }}
              />

              {/* Order Type */}
              <FormControl fullWidth size="small">
                <InputLabel>Order Type</InputLabel>
                <Select
                  value={formData.orderType}
                  onChange={(e) => setFormData({ ...formData, orderType: e.target.value, limitPrice: '' })}
                  label="Order Type"
                  native={false}
                >
                  <MenuItem value="market_order">Market Order</MenuItem>
                  <MenuItem value="limit_order">Limit Order</MenuItem>
                </Select>
              </FormControl>

              {/* Limit Price */}
              {formData.orderType === 'limit_order' && (
                <TextField
                  label="Limit Price"
                  type="number"
                  value={formData.limitPrice}
                  onChange={(e) => {
                    setFormData({ ...formData, limitPrice: e.target.value });
                    setError(null);
                  }}
                  size="small"
                  fullWidth
                  required
                  error={!formData.limitPrice}
                  helperText={
                    !formData.limitPrice 
                      ? 'Required for limit orders' 
                      : preview 
                        ? `Best Bid: ${preview.best_bid?.toFixed(2)} | Best Ask: ${preview.best_ask?.toFixed(2)}`
                        : ''
                  }
                  inputProps={{ step: 0.5, min: 0.01 }}
                />
              )}

              {/* Actions */}
              <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
                <Button
                  variant="contained"
                  onClick={handleSubmit}
                  disabled={loading || !formData.strike || !formData.expiry || (formData.orderType === 'limit_order' && !formData.limitPrice)}
                  fullWidth
                  startIcon={loading ? <CircularProgress size={20} /> : <CheckCircle2 size={18} />}
                  sx={{ py: 1.5 }}
                >
                  {loading ? 'Processing...' : 'Place Order'}
                </Button>
                <Button
                  variant="outlined"
                  onClick={onCancel}
                  disabled={loading}
                  sx={{ minWidth: 100 }}
                >
                  Cancel
                </Button>
              </Stack>
            </Stack>
          </Paper>
        </Grid>

        {/* Right Column - Preview */}
        <Grid item xs={12} md={6}>
          <Paper elevation={2} sx={{ p: 3, borderRadius: 2, minHeight: 400 }}>
            <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <DollarSign size={24} />
              Order Preview
            </Typography>

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            {!preview ? (
              <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
                <AlertCircle size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                <Typography variant="body2">
                  Select expiry and strike to see preview
                </Typography>
              </Box>
            ) : (
              <Stack spacing={2}>
                {/* Symbol */}
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="caption" color="text.secondary">Symbol</Typography>
                    <Typography variant="h6" fontFamily="monospace">{preview.symbol}</Typography>
                  </CardContent>
                </Card>

                {/* Market Data */}
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Market Data</Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Best Bid</Typography>
                        <Typography variant="body1" fontWeight="bold" color="success.main">
                          ${preview.best_bid?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Best Ask</Typography>
                        <Typography variant="body1" fontWeight="bold" color="error.main">
                          ${preview.best_ask?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Mark Price</Typography>
                        <Typography variant="body1" fontWeight="bold">
                          ${preview.mark_price?.toFixed(2)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Last Price</Typography>
                        <Typography variant="body1" fontWeight="bold">
                          ${preview.last_price?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </CardContent>
                </Card>

                {/* Order Summary */}
                <Card variant="outlined" sx={{ bgcolor: formData.side === 'buy' ? 'success.lighter' : 'error.lighter' }}>
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Order Summary</Typography>
                    <Stack spacing={1}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Direction</Typography>
                        <Chip 
                          label={formData.side === 'buy' ? 'BUY' : 'SELL'} 
                          size="small" 
                          color={formData.side === 'buy' ? 'success' : 'error'}
                        />
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Quantity</Typography>
                        <Typography variant="body2" fontWeight="bold">{formData.quantity}</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Strike</Typography>
                        <Typography variant="body2" fontWeight="bold">${formData.strike}</Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Spot Price</Typography>
                        <Typography variant="body2" fontWeight="bold">${preview.spot_price?.toFixed(2)}</Typography>
                      </Box>
                      <Divider />
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" fontWeight="bold">Estimated Cost</Typography>
                        <Typography variant="h6" color={formData.side === 'buy' ? 'error.main' : 'success.main'}>
                          ${preview.estimated_cost?.toFixed(2)}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>

                {/* Greeks (if available) */}
                {preview.greeks && Object.keys(preview.greeks).length > 0 && (
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Greeks</Typography>
                      <Grid container spacing={1}>
                        {preview.greeks.delta && (
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">Delta</Typography>
                            <Typography variant="body2">{preview.greeks.delta.toFixed(4)}</Typography>
                          </Grid>
                        )}
                        {preview.greeks.gamma && (
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">Gamma</Typography>
                            <Typography variant="body2">{preview.greeks.gamma.toFixed(4)}</Typography>
                          </Grid>
                        )}
                        {preview.greeks.vega && (
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">Vega</Typography>
                            <Typography variant="body2">{preview.greeks.vega.toFixed(4)}</Typography>
                          </Grid>
                        )}
                        {preview.greeks.theta && (
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">Theta</Typography>
                            <Typography variant="body2">{preview.greeks.theta.toFixed(4)}</Typography>
                          </Grid>
                        )}
                      </Grid>
                    </CardContent>
                  </Card>
                )}
              </Stack>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MVStraddleForm;
