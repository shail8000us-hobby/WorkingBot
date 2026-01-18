/**
 * Strategy Form
 * =============
 * Dynamic form for configuring strategy parameters.
 *
 * Created: January 5, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Typography,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  InputAdornment,
  Alert,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  PlayArrow as CreateIcon,
  AttachMoney as MoneyIcon,
} from '@mui/icons-material';

// Helper to format DDMMYYYY to readable format
const formatExpiryDate = (ddmmyyyy) => {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
  const day = parseInt(ddmmyyyy.slice(0, 2));
  const month = parseInt(ddmmyyyy.slice(2, 4)) - 1;
  const year = parseInt(ddmmyyyy.slice(4, 8));

  const date = new Date(year, month, day);
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
};

// Form configurations for each strategy type
const FORM_CONFIGS = {
  straddle: {
    fields: [
      {
        name: 'strike',
        label: 'Strike Price',
        type: 'number',
        required: true,
        helper: 'Usually ATM',
      },
    ],
  },
  strangle: {
    fields: [
      { name: 'call_strike', label: 'Call Strike (OTM)', type: 'number', required: true },
      { name: 'put_strike', label: 'Put Strike (OTM)', type: 'number', required: true },
    ],
  },
  iron_condor: {
    fields: [
      { name: 'put_buy_strike', label: 'Put Buy Strike (Wing)', type: 'number', required: true },
      { name: 'put_sell_strike', label: 'Put Sell Strike', type: 'number', required: true },
      { name: 'call_sell_strike', label: 'Call Sell Strike', type: 'number', required: true },
      { name: 'call_buy_strike', label: 'Call Buy Strike (Wing)', type: 'number', required: true },
    ],
    validation: (values) => {
      if (values.put_buy_strike >= values.put_sell_strike) {
        return 'Put buy strike must be below put sell strike';
      }
      if (values.put_sell_strike >= values.call_sell_strike) {
        return 'Put sell strike must be below call sell strike';
      }
      if (values.call_sell_strike >= values.call_buy_strike) {
        return 'Call sell strike must be below call buy strike';
      }
      return null;
    },
  },
  iron_butterfly: {
    fields: [
      { name: 'center_strike', label: 'Center Strike (ATM)', type: 'number', required: true },
      {
        name: 'wing_width',
        label: 'Wing Width',
        type: 'number',
        required: true,
        helper: 'Distance to wing strikes',
      },
    ],
  },
  call_spread: {
    fields: [
      { name: 'buy_strike', label: 'Buy Strike (Lower)', type: 'number', required: true },
      { name: 'sell_strike', label: 'Sell Strike (Higher)', type: 'number', required: true },
    ],
    validation: (values) => {
      if (values.buy_strike >= values.sell_strike) {
        return 'Buy strike must be below sell strike for bull call spread';
      }
      return null;
    },
  },
  put_spread: {
    fields: [
      { name: 'buy_strike', label: 'Buy Strike (Higher)', type: 'number', required: true },
      { name: 'sell_strike', label: 'Sell Strike (Lower)', type: 'number', required: true },
    ],
    validation: (values) => {
      if (values.buy_strike <= values.sell_strike) {
        return 'Buy strike must be above sell strike for bear put spread';
      }
      return null;
    },
  },
};

export default function StrategyForm({ strategyType, template, onSubmit, loading }) {
  const [underlying, setUnderlying] = useState('BTC');
  const [expiry, setExpiry] = useState('');
  const [expiries, setExpiries] = useState([]);
  const [expiryLoading, setExpiryLoading] = useState(false);
  const [strikes, setStrikes] = useState([]);
  const [strikesLoading, setStrikesLoading] = useState(false);
  const [atmStrike, setAtmStrike] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [params, setParams] = useState({});
  const [validationError, setValidationError] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Exit conditions
  const [exitConditions, setExitConditions] = useState({
    profit_target_pct: 50,
    stop_loss_pct: -100,
    dte_exit: 3,
  });

  const formConfig = FORM_CONFIGS[strategyType] || { fields: [] };

  // Fetch real expiries from Delta Exchange when underlying changes
  useEffect(() => {
    const fetchExpiries = async () => {
      setExpiryLoading(true);
      try {
        const res = await fetch(`/api/options-chain/expirations?underlying=${underlying}`);
        if (res.ok) {
          const data = await res.json();
          // Convert to format: [{value: 'DDMMYYYY', label: 'Wed, Jan 15'}]
          const formattedExpiries = (data.expirations || []).map((exp) => ({
            value: exp,
            label: formatExpiryDate(exp),
          }));
          setExpiries(formattedExpiries);
          // Set first expiry as default if none selected
          if (formattedExpiries.length > 0 && !expiry) {
            setExpiry(formattedExpiries[0].value);
          }
        }
      } catch (err) {
        console.error('Failed to fetch expiries:', err);
      } finally {
        setExpiryLoading(false);
      }
    };

    fetchExpiries();
  }, [underlying]);

  // Fetch strikes when expiry changes
  useEffect(() => {
    if (!expiry) return;

    const fetchStrikes = async () => {
      setStrikesLoading(true);
      try {
        const res = await fetch(
          `/api/options-chain/data?underlying=${underlying}&expiry=${expiry}`
        );
        if (res.ok) {
          const data = await res.json();
          const chainStrikes = (data.chain || []).map((item) => item.strike).filter((s) => s);
          setStrikes(chainStrikes.sort((a, b) => a - b));
          setAtmStrike(data.atm_strike || chainStrikes[Math.floor(chainStrikes.length / 2)]);

          // Auto-fill strike for straddle/butterfly if ATM available
          if (data.atm_strike && !params.strike) {
            setParams((prev) => ({
              ...prev,
              strike: data.atm_strike,
              center_strike: data.atm_strike,
            }));
          }
        }
      } catch (err) {
        console.error('Failed to fetch strikes:', err);
      } finally {
        setStrikesLoading(false);
      }
    };

    fetchStrikes();
  }, [underlying, expiry]);

  // Reset form when strategy type changes
  useEffect(() => {
    setParams({});
    setValidationError(null);
  }, [strategyType]);

  const handleParamChange = (name, value) => {
    const newParams = { ...params, [name]: parseFloat(value) || 0 };
    setParams(newParams);

    // Run validation
    if (formConfig.validation) {
      const error = formConfig.validation(newParams);
      setValidationError(error);
    }

    // Validate strike exists in chain
    if (name.includes('strike') && strikes.length > 0) {
      const strikeVal = parseFloat(value);
      if (strikeVal && !strikes.includes(strikeVal)) {
        // Find closest valid strike
        const closest = strikes.reduce((prev, curr) =>
          Math.abs(curr - strikeVal) < Math.abs(prev - strikeVal) ? curr : prev
        );
        setValidationError(`Strike ${strikeVal} not available. Closest: ${closest}`);
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    // Check required fields
    for (const field of formConfig.fields) {
      if (field.required && !params[field.name]) {
        setValidationError(`${field.label} is required`);
        return;
      }
    }

    // Validate strikes exist in chain
    if (strikes.length > 0) {
      for (const field of formConfig.fields) {
        if (field.name.includes('strike') && params[field.name]) {
          if (!strikes.includes(params[field.name])) {
            setValidationError(`Strike ${params[field.name]} is not available for this expiry`);
            return;
          }
        }
      }
    }

    // Run custom validation
    if (formConfig.validation) {
      const error = formConfig.validation(params);
      if (error) {
        setValidationError(error);
        return;
      }
    }

    onSubmit({
      strategy_type: strategyType,
      underlying,
      expiry,
      params: {
        ...params,
        quantity,
      },
    });
  };

  if (!strategyType) {
    return null;
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {/* Basic Settings */}
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <FormControl fullWidth size="small">
            <InputLabel>Underlying</InputLabel>
            <Select
              value={underlying}
              label="Underlying"
              onChange={(e) => setUnderlying(e.target.value)}
            >
              <MenuItem value="BTC">BTC</MenuItem>
              <MenuItem value="ETH">ETH</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={6}>
          <FormControl fullWidth size="small">
            <InputLabel>Expiry</InputLabel>
            <Select
              value={expiry}
              label="Expiry"
              onChange={(e) => setExpiry(e.target.value)}
              disabled={expiryLoading}
            >
              {expiryLoading ? (
                <MenuItem value="">Loading expiries...</MenuItem>
              ) : expiries.length === 0 ? (
                <MenuItem value="">No expiries available</MenuItem>
              ) : (
                expiries.map((exp) => (
                  <MenuItem key={exp.value} value={exp.value}>
                    {exp.label}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            size="small"
            type="number"
            label="Quantity (per leg)"
            value={quantity}
            onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
            inputProps={{ min: 1, max: 100 }}
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 2 }} />

      {/* Strategy-specific Parameters */}
      <Typography variant="subtitle2" gutterBottom color="text.secondary">
        Strike Configuration
        {atmStrike && (
          <Typography component="span" variant="body2" sx={{ ml: 1, color: 'primary.main' }}>
            (ATM: {atmStrike.toLocaleString()})
          </Typography>
        )}
      </Typography>

      {strikes.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Available strikes:{' '}
          {strikes
            .slice(0, 8)
            .map((s) => s.toLocaleString())
            .join(', ')}
          {strikes.length > 8 && ` ... and ${strikes.length - 8} more`}
        </Typography>
      )}

      <Grid container spacing={2}>
        {formConfig.fields.map((field) => (
          <Grid item xs={formConfig.fields.length > 2 ? 6 : 12} key={field.name}>
            <TextField
              fullWidth
              size="small"
              type="number"
              label={field.label}
              value={params[field.name] || ''}
              onChange={(e) => handleParamChange(field.name, e.target.value)}
              required={field.required}
              helperText={field.helper}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <MoneyIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
        ))}
      </Grid>

      {/* Validation Error */}
      {validationError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {validationError}
        </Alert>
      )}

      {/* Advanced Settings */}
      <Accordion
        expanded={showAdvanced}
        onChange={() => setShowAdvanced(!showAdvanced)}
        sx={{ mt: 2 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="body2">Exit Conditions (Optional)</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="Profit Target %"
                value={exitConditions.profit_target_pct}
                onChange={(e) =>
                  setExitConditions({
                    ...exitConditions,
                    profit_target_pct: parseFloat(e.target.value),
                  })
                }
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="Stop Loss %"
                value={exitConditions.stop_loss_pct}
                onChange={(e) =>
                  setExitConditions({
                    ...exitConditions,
                    stop_loss_pct: parseFloat(e.target.value),
                  })
                }
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="DTE Exit"
                value={exitConditions.dte_exit}
                onChange={(e) =>
                  setExitConditions({
                    ...exitConditions,
                    dte_exit: parseInt(e.target.value),
                  })
                }
                helperText="Days before expiry"
              />
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Submit Button */}
      <Button
        type="submit"
        variant="contained"
        color="primary"
        fullWidth
        size="large"
        disabled={loading || !!validationError}
        startIcon={<CreateIcon />}
        sx={{ mt: 3 }}
      >
        {loading ? 'Creating...' : 'Create Strategy'}
      </Button>
    </Box>
  );
}
