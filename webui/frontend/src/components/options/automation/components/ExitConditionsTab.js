import React from 'react';
import {
  Box,
  FormControl,
  FormControlLabel,
  FormLabel,
  TextField,
  Typography,
  Checkbox,
  Select,
  MenuItem,
  InputLabel,
  Alert,
  Chip,
  Grid,
  Divider,
  Paper,
  InputAdornment
} from '@mui/material';
import {
  EXIT_TYPES,
  TRAILING_STOP_TYPES
} from '../types/constants';

/**
 * ExitConditionsTab Component
 * 
 * Configures when to exit positions:
 * - Take profit targets (fixed/percentage)
 * - Stop loss limits
 * - Trailing stops
 * - Time-based exits
 * - Underlying price-based exits
 */
const ExitConditionsTab = ({ rules, onChange }) => {
  const handleExitChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        [field]: value
      }
    });
  };

  const handleTakeProfitChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        takeProfit: {
          ...rules.exit.takeProfit,
          [field]: value
        }
      }
    });
  };

  const handleStopLossChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        stopLoss: {
          ...rules.exit.stopLoss,
          [field]: value
        }
      }
    });
  };

  const handleTrailingStopChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        trailingStop: {
          ...rules.exit.trailingStop,
          [field]: value
        }
      }
    });
  };

  const handleTimeBasedChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        timeBased: {
          ...rules.exit.timeBased,
          [field]: value
        }
      }
    });
  };

  const handleUnderlyingExitChange = (field, value) => {
    onChange({
      ...rules,
      exit: {
        ...rules.exit,
        underlyingExit: {
          ...rules.exit.underlyingExit,
          [field]: value
        }
      }
    });
  };

  return (
    <Box sx={{ p: 3 }} onClick={(e) => e.stopPropagation()}>
      {/* Take Profit Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.exit.takeProfit.enabled}
              onChange={(e) => handleTakeProfitChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Take Profit
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Exit when position reaches profit target
              </Typography>
            </Box>
          }
        />

        {rules.exit.takeProfit.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Target Profit (%)"
                  type="number"
                  size="small"
                  value={rules.exit.takeProfit.percentage || 50}
                  onChange={(e) => handleTakeProfitChange('percentage', parseFloat(e.target.value))}
                  inputProps={{ step: 5, min: 1 }}
                  InputProps={{
                    endAdornment: <InputAdornment position="end">%</InputAdornment>,
                  }}
                  helperText="Exit when profit reaches this %"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Or Fixed Profit"
                  type="number"
                  size="small"
                  value={rules.exit.takeProfit.fixedValue || 0}
                  onChange={(e) => handleTakeProfitChange('fixedValue', parseFloat(e.target.value))}
                  inputProps={{ step: 0.0001 }}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                  }}
                  helperText="Or exit at fixed profit amount"
                />
              </Grid>
            </Grid>

            <FormControlLabel
              sx={{ mt: 1 }}
              control={
                <Checkbox
                  checked={rules.exit.takeProfit.partial || false}
                  onChange={(e) => handleTakeProfitChange('partial', e.target.checked)}
                />
              }
              label={
                <Typography variant="caption">
                  Partial exit (close 50% at target, let rest run)
                </Typography>
              }
            />
          </Box>
        )}
      </Paper>

      {/* Stop Loss Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.exit.stopLoss.enabled}
              onChange={(e) => handleStopLossChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Stop Loss
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Exit when position reaches loss limit
              </Typography>
            </Box>
          }
        />

        {rules.exit.stopLoss.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Max Loss (%)"
                  type="number"
                  size="small"
                  value={rules.exit.stopLoss.percentage || 50}
                  onChange={(e) => handleStopLossChange('percentage', parseFloat(e.target.value))}
                  inputProps={{ step: 5, min: 1 }}
                  InputProps={{
                    endAdornment: <InputAdornment position="end">%</InputAdornment>,
                  }}
                  helperText="Exit if loss reaches this %"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Or Fixed Loss"
                  type="number"
                  size="small"
                  value={rules.exit.stopLoss.fixedValue || 0}
                  onChange={(e) => handleStopLossChange('fixedValue', parseFloat(e.target.value))}
                  inputProps={{ step: 0.0001 }}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                  }}
                  helperText="Or exit at fixed loss amount"
                />
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Trailing Stop Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.exit.trailingStop.enabled}
              onChange={(e) => handleTrailingStopChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Trailing Stop
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Dynamically adjust stop loss as position moves in profit
              </Typography>
            </Box>
          }
        />

        {rules.exit.trailingStop.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <FormControl fullWidth size="small" sx={{ mb: 2 }}>
              <InputLabel>Trailing Type</InputLabel>
              <Select
                value={rules.exit.trailingStop.type}
                onChange={(e) => handleTrailingStopChange('type', e.target.value)}
                label="Trailing Type"
              >
                <MenuItem value={TRAILING_STOP_TYPES.PERCENTAGE}>
                  Percentage-based (% from peak)
                </MenuItem>
                <MenuItem value={TRAILING_STOP_TYPES.FIXED}>
                  Fixed amount (₹ from peak)
                </MenuItem>
              </Select>
            </FormControl>

            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label={rules.exit.trailingStop.type === TRAILING_STOP_TYPES.PERCENTAGE 
                    ? "Trail Distance (%)" 
                    : "Trail Distance (₹)"}
                  type="number"
                  size="small"
                  value={rules.exit.trailingStop.distance || 20}
                  onChange={(e) => handleTrailingStopChange('distance', parseFloat(e.target.value))}
                  inputProps={{ step: rules.exit.trailingStop.type === TRAILING_STOP_TYPES.PERCENTAGE ? 1 : 0.0001 }}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        {rules.exit.trailingStop.type === TRAILING_STOP_TYPES.PERCENTAGE ? '%' : '₹'}
                      </InputAdornment>
                    ),
                  }}
                  helperText="Distance from peak price"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Activation Profit (%)"
                  type="number"
                  size="small"
                  value={rules.exit.trailingStop.activationProfit || 10}
                  onChange={(e) => handleTrailingStopChange('activationProfit', parseFloat(e.target.value))}
                  inputProps={{ step: 5, min: 0 }}
                  InputProps={{
                    endAdornment: <InputAdornment position="end">%</InputAdornment>,
                  }}
                  helperText="Start trailing after this profit"
                />
              </Grid>
            </Grid>

            <Typography variant="caption" color="primary" sx={{ display: 'block', mt: 1 }}>
              Trailing stop will activate after {rules.exit.trailingStop.activationProfit || 10}% profit,
              then follow price at {rules.exit.trailingStop.distance || 20}
              {rules.exit.trailingStop.type === TRAILING_STOP_TYPES.PERCENTAGE ? '%' : '₹'} distance
            </Typography>
          </Box>
        )}
      </Paper>

      {/* Time-Based Exit Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.exit.timeBased.enabled}
              onChange={(e) => handleTimeBasedChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Time-Based Exit
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Exit position at specific time or after duration
              </Typography>
            </Box>
          }
        />

        {rules.exit.timeBased.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Exit At Time"
                  type="time"
                  size="small"
                  value={rules.exit.timeBased.exitTime || '15:15'}
                  onChange={(e) => handleTimeBasedChange('exitTime', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  helperText="Close position at this time (IST)"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Or After Duration (minutes)"
                  type="number"
                  size="small"
                  value={rules.exit.timeBased.duration || 0}
                  onChange={(e) => handleTimeBasedChange('duration', parseInt(e.target.value))}
                  inputProps={{ min: 0 }}
                  helperText="Or close after X minutes from entry"
                />
              </Grid>
            </Grid>

            <FormControlLabel
              sx={{ mt: 1 }}
              control={
                <Checkbox
                  checked={rules.exit.timeBased.closeBeforeExpiry || false}
                  onChange={(e) => handleTimeBasedChange('closeBeforeExpiry', e.target.checked)}
                />
              }
              label={
                <Typography variant="caption">
                  Auto-close 10 minutes before expiry (5:20 PM for 5:30 PM expiry)
                </Typography>
              }
            />
          </Box>
        )}
      </Paper>

      {/* Underlying Price Exit Section */}
      <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.exit.underlyingExit.enabled}
              onChange={(e) => handleUnderlyingExitChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Underlying Price Exit
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Exit when BTC/ETH reaches target price
              </Typography>
            </Box>
          }
        />

        {rules.exit.underlyingExit.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Exit Above Price"
                  type="number"
                  size="small"
                  value={rules.exit.underlyingExit.abovePrice || 0}
                  onChange={(e) => handleUnderlyingExitChange('abovePrice', parseFloat(e.target.value))}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">$</InputAdornment>,
                  }}
                  helperText="Exit if underlying goes above"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Exit Below Price"
                  type="number"
                  size="small"
                  value={rules.exit.underlyingExit.belowPrice || 0}
                  onChange={(e) => handleUnderlyingExitChange('belowPrice', parseFloat(e.target.value))}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">$</InputAdornment>,
                  }}
                  helperText="Exit if underlying goes below"
                />
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Summary Section */}
      <Divider sx={{ my: 3 }} />
      <Box>
        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
          Exit Conditions Summary
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {rules.exit.takeProfit.enabled && (
            <Chip
              label={`TP: ${rules.exit.takeProfit.percentage}%`}
              size="small"
              color="success"
              variant="outlined"
            />
          )}
          {rules.exit.stopLoss.enabled && (
            <Chip
              label={`SL: ${rules.exit.stopLoss.percentage}%`}
              size="small"
              color="error"
              variant="outlined"
            />
          )}
          {rules.exit.trailingStop.enabled && (
            <Chip
              label={`Trail: ${rules.exit.trailingStop.distance}${rules.exit.trailingStop.type === TRAILING_STOP_TYPES.PERCENTAGE ? '%' : '₹'}`}
              size="small"
              color="primary"
              variant="outlined"
            />
          )}
          {rules.exit.timeBased.enabled && (
            <Chip
              label={`Time: ${rules.exit.timeBased.exitTime || `${rules.exit.timeBased.duration}min`}`}
              size="small"
              color="secondary"
              variant="outlined"
            />
          )}
          {rules.exit.underlyingExit.enabled && (
            <Chip
              label="Underlying Exit"
              size="small"
              color="warning"
              variant="outlined"
            />
          )}
          {!rules.exit.takeProfit.enabled && !rules.exit.stopLoss.enabled && 
           !rules.exit.trailingStop.enabled && !rules.exit.timeBased.enabled && 
           !rules.exit.underlyingExit.enabled && (
            <Chip
              label="No exit conditions"
              size="small"
              variant="outlined"
            />
          )}
        </Box>

        {(!rules.exit.takeProfit.enabled && !rules.exit.stopLoss.enabled) && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="caption">
              Warning: No profit target or stop loss configured. Position will remain open until manual exit or time-based close.
            </Typography>
          </Alert>
        )}
      </Box>
    </Box>
  );
};

export default ExitConditionsTab;
