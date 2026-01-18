/**
 * EntryConditionsTab - Form for entry conditions
 *
 * Features:
 * - Action (Buy/Sell)
 * - Quantity
 * - IV filter
 * - Moneyness selector
 * - Premium range
 * - Time window
 */

import React from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Checkbox,
  FormControlLabel,
  ToggleButtonGroup,
  ToggleButton,
  Stack,
  Divider,
} from '@mui/material';
import { ACTION_TYPES, MONEYNESS, OPERATORS } from '../types/constants';
import ConditionChecks from './ConditionChecks';

const EntryConditionsTab = ({ rules, onChange }) => {
  const handleChange = (path, value) => {
    const newRules = { ...rules };
    const pathParts = path.split('.');
    let current = newRules.entry;

    for (let i = 0; i < pathParts.length - 1; i++) {
      current = current[pathParts[i]];
    }

    current[pathParts[pathParts.length - 1]] = value;
    onChange(newRules);
  };

  return (
    <Box sx={{ p: 3 }} onClick={(e) => e.stopPropagation()}>
      <Typography variant="h6" gutterBottom>
        Entry Conditions
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 3 }}>
        Define when the automation should execute
      </Typography>

      <Stack spacing={3}>
        {/* Action: Buy or Sell */}
        <FormControl fullWidth>
          <InputLabel>Action</InputLabel>
          <Select
            value={rules.entry.action}
            onChange={(e) => handleChange('action', e.target.value)}
            label="Action"
          >
            <MenuItem value={ACTION_TYPES.BUY}>Buy</MenuItem>
            <MenuItem value={ACTION_TYPES.SELL}>Sell</MenuItem>
          </Select>
        </FormControl>

        {/* Quantity */}
        <TextField
          fullWidth
          type="number"
          label="Quantity (lots)"
          value={rules.entry.quantity}
          onChange={(e) => handleChange('quantity', parseInt(e.target.value) || 1)}
          inputProps={{ min: 1, max: 100 }}
          helperText="Number of contracts to trade"
        />

        <Divider />

        {/* IV Filter */}
        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.entry.ivFilter.enabled}
                onChange={(e) => handleChange('ivFilter.enabled', e.target.checked)}
              />
            }
            label={
              <Typography variant="body2" fontWeight="bold">
                IV Filter
              </Typography>
            }
          />
          {rules.entry.ivFilter.enabled && (
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <FormControl sx={{ minWidth: 80 }}>
                <Select
                  value={rules.entry.ivFilter.operator}
                  onChange={(e) => handleChange('ivFilter.operator', e.target.value)}
                  size="small"
                >
                  <MenuItem value={OPERATORS.GREATER_THAN}>&gt;</MenuItem>
                  <MenuItem value={OPERATORS.LESS_THAN}>&lt;</MenuItem>
                  <MenuItem value={OPERATORS.GREATER_EQUAL}>≥</MenuItem>
                  <MenuItem value={OPERATORS.LESS_EQUAL}>≤</MenuItem>
                </Select>
              </FormControl>
              <TextField
                type="number"
                value={rules.entry.ivFilter.value}
                onChange={(e) => handleChange('ivFilter.value', parseFloat(e.target.value) || 0)}
                size="small"
                label="IV %"
                inputProps={{ min: 0, max: 300, step: 5 }}
                sx={{ flex: 1 }}
              />
            </Stack>
          )}
        </Box>

        {/* Moneyness */}
        <Box>
          <Typography variant="body2" fontWeight="bold" gutterBottom>
            Moneyness
          </Typography>
          <ToggleButtonGroup
            value={rules.entry.moneyness}
            exclusive
            onChange={(e, value) => value && handleChange('moneyness', value)}
            fullWidth
            size="small"
          >
            <ToggleButton value={MONEYNESS.ITM}>ITM</ToggleButton>
            <ToggleButton value={MONEYNESS.ATM}>ATM</ToggleButton>
            <ToggleButton value={MONEYNESS.OTM}>OTM</ToggleButton>
          </ToggleButtonGroup>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            ITM: In-The-Money | ATM: At-The-Money | OTM: Out-of-The-Money
          </Typography>
        </Box>

        <Divider />

        {/* Premium Range */}
        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.entry.premiumRange.enabled}
                onChange={(e) => handleChange('premiumRange.enabled', e.target.checked)}
              />
            }
            label={
              <Typography variant="body2" fontWeight="bold">
                Premium Range
              </Typography>
            }
          />
          {rules.entry.premiumRange.enabled && (
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField
                type="number"
                value={rules.entry.premiumRange.min}
                onChange={(e) => handleChange('premiumRange.min', parseFloat(e.target.value) || 0)}
                size="small"
                label="Min $"
                inputProps={{ min: 0, step: 10 }}
                sx={{ flex: 1 }}
              />
              <TextField
                type="number"
                value={rules.entry.premiumRange.max}
                onChange={(e) =>
                  handleChange('premiumRange.max', parseFloat(e.target.value) || 10000)
                }
                size="small"
                label="Max $"
                inputProps={{ min: 0, step: 10 }}
                sx={{ flex: 1 }}
              />
            </Stack>
          )}
        </Box>

        {/* Time Window */}
        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.entry.timeFilter.enabled}
                onChange={(e) => handleChange('timeFilter.enabled', e.target.checked)}
              />
            }
            label={
              <Typography variant="body2" fontWeight="bold">
                Time Window
              </Typography>
            }
          />
          {rules.entry.timeFilter.enabled && (
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField
                type="time"
                value={rules.entry.timeFilter.startTime}
                onChange={(e) => handleChange('timeFilter.startTime', e.target.value)}
                size="small"
                label="Start Time"
                InputLabelProps={{ shrink: true }}
                sx={{ flex: 1 }}
              />
              <TextField
                type="time"
                value={rules.entry.timeFilter.endTime}
                onChange={(e) => handleChange('timeFilter.endTime', e.target.value)}
                size="small"
                label="End Time"
                InputLabelProps={{ shrink: true }}
                sx={{ flex: 1 }}
              />
            </Stack>
          )}
        </Box>

        {/* Underlying Price Range */}
        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.entry.underlyingPrice.enabled}
                onChange={(e) => handleChange('underlyingPrice.enabled', e.target.checked)}
              />
            }
            label={
              <Typography variant="body2" fontWeight="bold">
                Underlying Price Range
              </Typography>
            }
          />
          {rules.entry.underlyingPrice.enabled && (
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField
                type="number"
                value={rules.entry.underlyingPrice.min}
                onChange={(e) =>
                  handleChange('underlyingPrice.min', parseFloat(e.target.value) || 0)
                }
                size="small"
                label="Min $"
                inputProps={{ min: 0, step: 1000 }}
                sx={{ flex: 1 }}
              />
              <TextField
                type="number"
                value={rules.entry.underlyingPrice.max}
                onChange={(e) =>
                  handleChange('underlyingPrice.max', parseFloat(e.target.value) || 150000)
                }
                size="small"
                label="Max $"
                inputProps={{ min: 0, step: 1000 }}
                sx={{ flex: 1 }}
              />
            </Stack>
          )}
        </Box>
      </Stack>

      {/* Summary */}
      <Box sx={{ mt: 3 }}>
        <ConditionChecks rules={rules} />
      </Box>
    </Box>
  );
};

export default EntryConditionsTab;
