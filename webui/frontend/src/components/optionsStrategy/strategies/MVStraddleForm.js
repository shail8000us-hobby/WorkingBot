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
  Switch,
  FormControlLabel,
  Grid,
  Alert,
  Chip,
  Divider,
  CircularProgress,
  Slider,
  ToggleButtonGroup,
  ToggleButton
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import VolatilityIndicator from './VolatilityIndicator';
import BreakevenChart from './BreakevenChart';

const MVStraddleForm = ({ onSubmit, onCancel }) => {
  // Form state
  const [formData, setFormData] = useState({
    name: `MV Straddle ${new Date().toLocaleDateString()}`,
    underlying: 'BTC',
    expiry: '',
    strike: '',
    direction: 'long',
    quantity: 1,
    autoStrike: true,
    strikeOffset: 0
  });

  // UI state
  const [availableExpiries, setAvailableExpiries] = useState([]);
  const [spotPrice, setSpotPrice] = useState(0);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [volatilityData, setVolatilityData] = useState(null);
  const [error, setError] = useState(null);
  const [expiryLoading, setExpiryLoading] = useState(false);

  // Fetch expiries on mount and when underlying changes
  useEffect(() => {
    fetchExpiries();
    fetchSpotPrice();
  }, [formData.underlying]);

  // Fetch preview when key params change
  useEffect(() => {
    if (formData.expiry && (formData.strike || formData.autoStrike)) {
      const timeoutId = setTimeout(() => {
        fetchPreview();
      }, 500); // Debounce 500ms
      
      return () => clearTimeout(timeoutId);
    }
  }, [formData.expiry, formData.strike, formData.direction, formData.quantity, formData.autoStrike, formData.strikeOffset]);

  const fetchExpiries = async () => {
    try {
      setExpiryLoading(true);
      const response = await fetch(`/api/options-chain/expirations?underlying=${formData.underlying}`);
      const data = await response.json();
      
      if (data.expirations && data.expirations.length > 0) {
        setAvailableExpiries(data.expirations);
        if (data.expirations.length > 0) {
          setFormData(prev => ({ ...prev, expiry: data.expirations[0] }));
        }
      }
    } catch (error) {
      console.error('Error fetching expiries:', error);
      setError('Failed to fetch expiry dates');
    } finally {
      setExpiryLoading(false);
    }
  };

  const fetchSpotPrice = async () => {
    try {
      const response = await fetch('/api/market/spot-price');
      const data = await response.json();
      const price = data[formData.underlying.toLowerCase()];
      setSpotPrice(price);
      
      // Auto-set strike if autoStrike is enabled
      if (formData.autoStrike && !formData.strike) {
        const roundedStrike = Math.round(price / 1000) * 1000;
        setFormData(prev => ({ ...prev, strike: roundedStrike }));
      }
    } catch (error) {
      console.error('Error fetching spot price:', error);
    }
  };

  const fetchPreview = async () => {
    if (!formData.expiry) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch('/api/options-strategy/mv-straddle/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          underlying: formData.underlying,
          expiry: formData.expiry,
          strike: formData.autoStrike ? null : parseInt(formData.strike),
          direction: formData.direction,
          quantity: parseInt(formData.quantity),
          autoStrike: formData.autoStrike,
          strikeOffset: parseInt(formData.strikeOffset)
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.strategy) {
        setPreview(data.strategy);
        setVolatilityData(data.strategy.volatility_analysis);
      } else {
        setError(data.error || 'Failed to generate preview');
        setPreview(null);
        setVolatilityData(null);
      }
    } catch (error) {
      console.error('Preview error:', error);
      setError('Failed to fetch preview');
      setPreview(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.expiry) {
      setError('Please select an expiry date');
      return;
    }
    
    if (!formData.autoStrike && !formData.strike) {
      setError('Please enter a strike price or enable auto-strike');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch('/api/options-strategy/mv-straddle/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          underlying: formData.underlying,
          expiry: formData.expiry,
          strike: formData.autoStrike ? null : parseInt(formData.strike),
          direction: formData.direction,
          quantity: parseInt(formData.quantity),
          autoStrike: formData.autoStrike,
          strikeOffset: parseInt(formData.strikeOffset)
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        onSubmit(data.strategy);
      } else {
        setError(data.error || 'Failed to create strategy');
      }
    } catch (error) {
      console.error('Execution error:', error);
      setError('Failed to create strategy');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <ShowChartIcon />
        MV Straddle Builder
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Market View Straddle with enhanced volatility analysis
      </Typography>

      <Grid container spacing={3}>
        {/* Left Panel - Form */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Strategy Parameters</Typography>

            {/* Strategy Name */}
            <TextField
              fullWidth
              label="Strategy Name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              sx={{ mb: 2 }}
            />

            {/* Underlying */}
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Underlying</InputLabel>
              <Select
                value={formData.underlying}
                label="Underlying"
                onChange={(e) => setFormData(prev => ({ ...prev, underlying: e.target.value }))}
              >
                <MenuItem value="BTC">BTC</MenuItem>
                <MenuItem value="ETH">ETH</MenuItem>
              </Select>
            </FormControl>

            {/* Spot Price Display */}
            {spotPrice > 0 && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Current {formData.underlying} Spot: ${spotPrice.toLocaleString()}
              </Alert>
            )}

            {/* Expiry */}
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Expiry</InputLabel>
              <Select
                value={formData.expiry}
                label="Expiry"
                onChange={(e) => setFormData(prev => ({ ...prev, expiry: e.target.value }))}
                disabled={expiryLoading}
              >
                {expiryLoading ? (
                  <MenuItem value="">Loading...</MenuItem>
                ) : (
                  availableExpiries.map(exp => (
                    <MenuItem key={exp} value={exp}>
                      {formatExpiry(exp)}
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            {/* Direction */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Direction
              </Typography>
              <ToggleButtonGroup
                value={formData.direction}
                exclusive
                onChange={(e, value) => value && setFormData(prev => ({ ...prev, direction: value }))}
                fullWidth
              >
                <ToggleButton value="long" sx={{ gap: 1 }}>
                  <TrendingUpIcon fontSize="small" />
                  Long (Buy)
                </ToggleButton>
                <ToggleButton value="short" sx={{ gap: 1 }}>
                  <TrendingDownIcon fontSize="small" />
                  Short (Sell)
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Auto Strike */}
            <FormControlLabel
              control={
                <Switch
                  checked={formData.autoStrike}
                  onChange={(e) => setFormData(prev => ({ ...prev, autoStrike: e.target.checked }))}
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <AutoFixHighIcon fontSize="small" />
                  Auto ATM Strike
                </Box>
              }
              sx={{ mb: 2 }}
            />

            {/* Manual Strike (if auto disabled) */}
            {!formData.autoStrike && (
              <TextField
                fullWidth
                type="number"
                label="Strike Price"
                value={formData.strike}
                onChange={(e) => setFormData(prev => ({ ...prev, strike: e.target.value }))}
                sx={{ mb: 2 }}
              />
            )}

            {/* Strike Offset (if auto enabled) */}
            {formData.autoStrike && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Strike Offset: {formData.strikeOffset >= 0 ? '+' : ''}{formData.strikeOffset}
                </Typography>
                <Slider
                  value={formData.strikeOffset}
                  onChange={(e, value) => setFormData(prev => ({ ...prev, strikeOffset: value }))}
                  min={-5000}
                  max={5000}
                  step={500}
                  marks={[
                    { value: -5000, label: '-5000' },
                    { value: 0, label: 'ATM' },
                    { value: 5000, label: '+5000' }
                  ]}
                  valueLabelDisplay="auto"
                />
              </Box>
            )}

            {/* Quantity */}
            <TextField
              fullWidth
              type="number"
              label="Quantity (per leg)"
              value={formData.quantity}
              onChange={(e) => setFormData(prev => ({ ...prev, quantity: Math.max(1, parseInt(e.target.value) || 1) }))}
              inputProps={{ min: 1, max: 100 }}
              sx={{ mb: 2 }}
            />

            {/* Error Display */}
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || !formData.expiry}
                fullWidth
                sx={{ py: 1.5 }}
              >
                {loading ? <CircularProgress size={24} /> : 'Create Strategy'}
              </Button>
              <Button
                variant="outlined"
                onClick={onCancel}
                disabled={loading}
              >
                Cancel
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* Right Panel - Preview */}
        <Grid item xs={12} md={6}>
          {loading && !preview && (
            <Paper sx={{ p: 3, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
              <CircularProgress />
            </Paper>
          )}

          {!loading && !preview && (
            <Paper sx={{ p: 3, minHeight: 400 }}>
              <Typography variant="h6" gutterBottom>Preview</Typography>
              <Typography variant="body2" color="text.secondary">
                Configure strategy parameters to see preview
              </Typography>
            </Paper>
          )}

          {preview && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {/* Volatility Analysis */}
              {volatilityData && (
                <VolatilityIndicator data={volatilityData} />
              )}

              {/* Strategy Summary */}
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>Strategy Summary</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Strike</Typography>
                    <Typography variant="body1" fontWeight="bold">
                      ${preview.legs && preview.legs[0] ? preview.legs[0].strike.toLocaleString() : 'N/A'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Total Premium</Typography>
                    <Typography variant="body1" fontWeight="bold" color={formData.direction === 'long' ? 'error.main' : 'success.main'}>
                      {formData.direction === 'long' ? '-' : '+'}${preview.total_premium?.toFixed(2)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Max Profit</Typography>
                    <Typography variant="body1" fontWeight="bold">
                      {preview.max_profit_loss?.max_profit === 'Unlimited' ? '♾️ Unlimited' : `$${preview.max_profit_loss?.max_profit}`}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Max Loss</Typography>
                    <Typography variant="body1" fontWeight="bold">
                      {preview.max_profit_loss?.max_loss === 'Unlimited' ? '♾️ Unlimited' : `$${preview.max_profit_loss?.max_loss}`}
                    </Typography>
                  </Grid>
                </Grid>

                {/* Breakeven Points */}
                {preview.breakeven && preview.breakeven.breakeven_points && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="caption" color="text.secondary">Breakeven Points</Typography>
                    <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                      <Chip 
                        label={`Lower: $${Math.round(preview.breakeven.breakeven_points[0]).toLocaleString()}`}
                        size="small"
                        color="info"
                      />
                      <Chip 
                        label={`Upper: $${Math.round(preview.breakeven.breakeven_points[1]).toLocaleString()}`}
                        size="small"
                        color="info"
                      />
                    </Box>
                  </Box>
                )}

                {/* Legs Detail */}
                <Divider sx={{ my: 2 }} />
                <Typography variant="body2" color="text.secondary" gutterBottom>Legs</Typography>
                {preview.legs && preview.legs.map((leg, idx) => (
                  <Box key={idx} sx={{ mb: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                    <Typography variant="body2">
                      {leg.side.toUpperCase()} {leg.quantity}x {leg.option_type.toUpperCase()} @ ${leg.strike} = ${(leg.current_price * leg.quantity).toFixed(2)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      IV: {leg.iv?.toFixed(1)}% | Mid: ${leg.current_price?.toFixed(2)}
                    </Typography>
                  </Box>
                ))}
              </Paper>

              {/* Payoff Chart */}
              {preview.pnl_curve && (
                <BreakevenChart data={preview.pnl_curve} />
              )}
            </Box>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

// Helper function to format expiry date
const formatExpiry = (expiry) => {
  if (!expiry || expiry.length !== 8) return expiry;
  
  const day = expiry.substring(0, 2);
  const month = expiry.substring(2, 4);
  const year = expiry.substring(4, 8);
  
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthName = months[parseInt(month) - 1] || month;
  
  return `${day} ${monthName} ${year}`;
};

export default MVStraddleForm;
