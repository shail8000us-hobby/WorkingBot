import React from 'react';
import {
  Box,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
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
  Paper
} from '@mui/material';
import {
  ORDER_TYPES,
  EXECUTION_TIMING,
  POSITION_SIZING
} from '../types/constants';

/**
 * ExecutionTab Component
 * 
 * Configures how orders should be executed:
 * - Order type (Market/Limit)
 * - Execution timing (Immediate/Delayed/Scheduled)
 * - Position sizing (Fixed/Percentage/Dynamic)
 * - Staggered entry options
 * - Dry run mode
 */
const ExecutionTab = ({ rules, onChange }) => {
  const handleExecutionChange = (field, value) => {
    onChange({
      ...rules,
      execution: {
        ...rules.execution,
        [field]: value
      }
    });
  };

  const handleStagingChange = (field, value) => {
    onChange({
      ...rules,
      execution: {
        ...rules.execution,
        staging: {
          ...rules.execution.staging,
          [field]: value
        }
      }
    });
  };

  return (
    <Box sx={{ p: 2 }}>
      {/* Dry Run Mode Alert */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2" fontWeight="bold">
          Dry Run Mode (Phase 2)
        </Typography>
        <Typography variant="caption">
          Orders will be simulated only. No real orders will be placed until Phase 3.
        </Typography>
      </Alert>

      {/* Order Type Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControl component="fieldset" fullWidth>
          <FormLabel component="legend" sx={{ mb: 1, fontWeight: 'bold' }}>
            Order Type
          </FormLabel>
          <RadioGroup
            value={rules.execution.orderType}
            onChange={(e) => handleExecutionChange('orderType', e.target.value)}
          >
            <FormControlLabel
              value={ORDER_TYPES.MARKET}
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body2">Market Order</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Execute immediately at best available price
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              value={ORDER_TYPES.LIMIT}
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body2">Limit Order</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Execute at specified price or better
                  </Typography>
                </Box>
              }
            />
          </RadioGroup>
        </FormControl>

        {/* Limit Order Options */}
        {rules.execution.orderType === ORDER_TYPES.LIMIT && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Limit Price Offset (%)"
                  type="number"
                  size="small"
                  value={rules.execution.limitPriceOffset || 0}
                  onChange={(e) => handleExecutionChange('limitPriceOffset', parseFloat(e.target.value))}
                  inputProps={{ step: 0.1 }}
                  helperText="Above market for sells, below for buys"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Order Timeout (seconds)"
                  type="number"
                  size="small"
                  value={rules.execution.orderTimeout || 60}
                  onChange={(e) => handleExecutionChange('orderTimeout', parseInt(e.target.value))}
                  helperText="Cancel if not filled within timeout"
                />
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Execution Timing Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControl fullWidth>
          <InputLabel>Execution Timing</InputLabel>
          <Select
            value={rules.execution.timing}
            onChange={(e) => handleExecutionChange('timing', e.target.value)}
            label="Execution Timing"
          >
            <MenuItem value={EXECUTION_TIMING.IMMEDIATE}>
              <Box>
                <Typography variant="body2">Immediate</Typography>
                <Typography variant="caption" color="text.secondary">
                  Execute as soon as conditions are met
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem value={EXECUTION_TIMING.DELAYED}>
              <Box>
                <Typography variant="body2">Delayed</Typography>
                <Typography variant="caption" color="text.secondary">
                  Wait specified time after conditions are met
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem value={EXECUTION_TIMING.SCHEDULED}>
              <Box>
                <Typography variant="body2">Scheduled</Typography>
                <Typography variant="caption" color="text.secondary">
                  Execute at specific time of day
                </Typography>
              </Box>
            </MenuItem>
          </Select>
        </FormControl>

        {/* Delayed Timing Options */}
        {rules.execution.timing === EXECUTION_TIMING.DELAYED && (
          <TextField
            fullWidth
            sx={{ mt: 2 }}
            label="Delay (seconds)"
            type="number"
            size="small"
            value={rules.execution.delaySeconds || 5}
            onChange={(e) => handleExecutionChange('delaySeconds', parseInt(e.target.value))}
            helperText="Wait this many seconds after conditions are met"
          />
        )}

        {/* Scheduled Timing Options */}
        {rules.execution.timing === EXECUTION_TIMING.SCHEDULED && (
          <TextField
            fullWidth
            sx={{ mt: 2 }}
            label="Execute At Time"
            type="time"
            size="small"
            value={rules.execution.scheduledTime || '09:30'}
            onChange={(e) => handleExecutionChange('scheduledTime', e.target.value)}
            helperText="Time in HH:MM format (IST)"
            InputLabelProps={{ shrink: true }}
          />
        )}
      </Paper>

      {/* Position Sizing Section */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControl fullWidth>
          <InputLabel>Position Sizing</InputLabel>
          <Select
            value={rules.execution.positionSizing}
            onChange={(e) => handleExecutionChange('positionSizing', e.target.value)}
            label="Position Sizing"
          >
            <MenuItem value={POSITION_SIZING.FIXED}>
              <Box>
                <Typography variant="body2">Fixed Quantity</Typography>
                <Typography variant="caption" color="text.secondary">
                  Always trade same number of contracts
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem value={POSITION_SIZING.PERCENTAGE}>
              <Box>
                <Typography variant="body2">Percentage of Capital</Typography>
                <Typography variant="caption" color="text.secondary">
                  Size based on % of account balance
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem value={POSITION_SIZING.DYNAMIC}>
              <Box>
                <Typography variant="body2">Dynamic (IV-Based)</Typography>
                <Typography variant="caption" color="text.secondary">
                  Adjust size based on volatility
                </Typography>
              </Box>
            </MenuItem>
          </Select>
        </FormControl>

        {/* Position Sizing Options */}
        <Box sx={{ mt: 2 }}>
          {rules.execution.positionSizing === POSITION_SIZING.FIXED && (
            <TextField
              fullWidth
              label="Quantity (contracts)"
              type="number"
              size="small"
              value={rules.execution.quantity || 1}
              onChange={(e) => handleExecutionChange('quantity', parseInt(e.target.value))}
              inputProps={{ min: 1, step: 1 }}
            />
          )}

          {rules.execution.positionSizing === POSITION_SIZING.PERCENTAGE && (
            <TextField
              fullWidth
              label="Capital Percentage (%)"
              type="number"
              size="small"
              value={rules.execution.capitalPercentage || 5}
              onChange={(e) => handleExecutionChange('capitalPercentage', parseFloat(e.target.value))}
              inputProps={{ min: 0.1, max: 100, step: 0.5 }}
              helperText="Percentage of available capital to risk"
            />
          )}

          {rules.execution.positionSizing === POSITION_SIZING.DYNAMIC && (
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Min Contracts"
                  type="number"
                  size="small"
                  value={rules.execution.minQuantity || 1}
                  onChange={(e) => handleExecutionChange('minQuantity', parseInt(e.target.value))}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Max Contracts"
                  type="number"
                  size="small"
                  value={rules.execution.maxQuantity || 10}
                  onChange={(e) => handleExecutionChange('maxQuantity', parseInt(e.target.value))}
                />
              </Grid>
            </Grid>
          )}
        </Box>
      </Paper>

      {/* Staggered Entry Section */}
      <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.execution.staging.enabled}
              onChange={(e) => handleStagingChange('enabled', e.target.checked)}
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Enable Staggered Entry
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Split order into multiple smaller entries
              </Typography>
            </Box>
          }
        />

        {rules.execution.staging.enabled && (
          <Box sx={{ mt: 2, pl: 4 }}>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Number of Stages"
                  type="number"
                  size="small"
                  value={rules.execution.staging.stages || 3}
                  onChange={(e) => handleStagingChange('stages', parseInt(e.target.value))}
                  inputProps={{ min: 2, max: 10 }}
                  helperText="Split into N orders"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Stage Interval (seconds)"
                  type="number"
                  size="small"
                  value={rules.execution.staging.intervalSeconds || 30}
                  onChange={(e) => handleStagingChange('intervalSeconds', parseInt(e.target.value))}
                  helperText="Time between orders"
                />
              </Grid>
            </Grid>

            <Typography variant="caption" color="primary" sx={{ display: 'block', mt: 1 }}>
              Example: {rules.execution.quantity || 1} contracts will be split into{' '}
              {rules.execution.staging.stages || 3} orders of{' '}
              {Math.ceil((rules.execution.quantity || 1) / (rules.execution.staging.stages || 3))}{' '}
              contracts each, placed {rules.execution.staging.intervalSeconds || 30} seconds apart
            </Typography>
          </Box>
        )}
      </Paper>

      {/* Summary Section */}
      <Divider sx={{ my: 3 }} />
      <Box>
        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
          Execution Summary
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <Chip
            label={`Type: ${rules.execution.orderType}`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Chip
            label={`Timing: ${rules.execution.timing}`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Chip
            label={`Size: ${rules.execution.positionSizing}`}
            size="small"
            color="primary"
            variant="outlined"
          />
          {rules.execution.staging.enabled && (
            <Chip
              label={`Staggered: ${rules.execution.staging.stages} stages`}
              size="small"
              color="secondary"
              variant="outlined"
            />
          )}
          <Chip
            label="DRY RUN"
            size="small"
            color="warning"
          />
        </Box>
      </Box>
    </Box>
  );
};

export default ExecutionTab;
