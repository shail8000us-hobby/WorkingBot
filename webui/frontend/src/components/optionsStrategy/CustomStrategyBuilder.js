/**
 * Custom Strategy Builder (Build Your Own Strategy)
 * ==================================================
 * Create custom multi-leg strategies with multiple expiries and one-click execution.
 *
 * Features:
 * - Add any number of legs
 * - Different expiries per leg
 * - Real-time premium calculation
 * - One-click execution
 * - Payoff preview
 *
 * Created: January 12, 2026
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  TextField,
  Button,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
  Collapse,
  Divider,
  InputAdornment,
  CircularProgress,
  Tooltip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  PlayArrow as ExecuteIcon,
  Refresh as RefreshIcon,
  TrendingUp as CallIcon,
  TrendingDown as PutIcon,
  ShoppingCart as BuyIcon,
  Sell as SellIcon,
  Build as BuildIcon,
  Calculate as CalcIcon,
  Visibility as PreviewIcon,
} from '@mui/icons-material';

const API_BASE = '/api/options-strategy';
const CHAIN_API = '/api/options-chain';

// Default leg template
const createEmptyLeg = (id = 1) => ({
  id,
  option_type: 'call',
  strike: '',
  side: 'buy',
  quantity: 1,
  expiry: '',
  premium: null,
  greeks: null,
  loading: false,
});

export default function CustomStrategyBuilder({ onStrategyCreated, onExecutionComplete }) {
  // Strategy name
  const [strategyName, setStrategyName] = useState('My Custom Strategy');
  const [underlying, setUnderlying] = useState('BTC');

  // Legs management
  const [legs, setLegs] = useState([createEmptyLeg(1)]);
  const [nextLegId, setNextLegId] = useState(2);

  // Available expiries and strikes
  const [expiries, setExpiries] = useState([]);
  const [strikesByExpiry, setStrikesByExpiry] = useState({});
  const [atmByExpiry, setAtmByExpiry] = useState({});
  const [loadingExpiries, setLoadingExpiries] = useState(false);

  // Creation and execution state
  const [createdStrategy, setCreatedStrategy] = useState(null);
  const [creating, setCreating] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Fetch expiries on mount or underlying change
  useEffect(() => {
    fetchExpiries();
  }, [underlying]);

  const fetchExpiries = async () => {
    setLoadingExpiries(true);
    try {
      const res = await fetch(`${CHAIN_API}/expirations?underlying=${underlying}`);
      const data = await res.json();
      if (data.expirations && data.expirations.length > 0) {
        setExpiries(data.expirations);
        // Set first expiry for first leg if empty
        if (legs.length > 0 && !legs[0].expiry) {
          updateLeg(legs[0].id, 'expiry', data.expirations[0]);
        }
      }
    } catch (err) {
      console.error('Failed to fetch expiries:', err);
      setError('Failed to load expiry dates');
    } finally {
      setLoadingExpiries(false);
    }
  };

  // Fetch strikes when a leg's expiry changes
  const fetchStrikes = useCallback(
    async (expiry) => {
      if (!expiry || strikesByExpiry[expiry]) return;

      try {
        const res = await fetch(`${CHAIN_API}/data?underlying=${underlying}&expiry=${expiry}`);
        const data = await res.json();
        if (data.chain) {
          const strikes = data.chain
            .map((item) => item.strike)
            .filter((s) => s)
            .sort((a, b) => a - b);
          setStrikesByExpiry((prev) => ({ ...prev, [expiry]: strikes }));
          setAtmByExpiry((prev) => ({
            ...prev,
            [expiry]: data.atm_strike || strikes[Math.floor(strikes.length / 2)],
          }));
        }
      } catch (err) {
        console.error('Failed to fetch strikes:', err);
      }
    },
    [underlying, strikesByExpiry]
  );

  // Fetch premium for a leg
  const fetchPremium = useCallback(
    async (leg) => {
      if (!leg.expiry || !leg.strike) return;

      try {
        // Build symbol: C-BTC-95000-130126 or P-BTC-93000-130126
        const prefix = leg.option_type === 'call' ? 'C' : 'P';
        // Convert DDMMYYYY to DDMMYY
        const expiryFormatted =
          leg.expiry.length === 8 ? leg.expiry.slice(0, 4) + leg.expiry.slice(6, 8) : leg.expiry;
        const symbol = `${prefix}-${underlying}-${leg.strike}-${expiryFormatted}`;

        const res = await fetch(`/api/options/ticker?symbol=${symbol}`);
        if (res.ok) {
          const data = await res.json();
          return {
            premium: data.mark_price || data.best_bid || 0,
            bid: data.best_bid,
            ask: data.best_ask,
            iv: data.mark_iv,
            delta: data.greeks?.delta,
            gamma: data.greeks?.gamma,
            theta: data.greeks?.theta,
            vega: data.greeks?.vega,
          };
        }
      } catch (err) {
        console.error('Failed to fetch premium:', err);
      }
      return null;
    },
    [underlying]
  );

  // Add a new leg
  const addLeg = () => {
    const lastLeg = legs[legs.length - 1];
    const newLeg = createEmptyLeg(nextLegId);
    // Copy expiry from last leg for convenience
    if (lastLeg?.expiry) {
      newLeg.expiry = lastLeg.expiry;
    }
    setLegs([...legs, newLeg]);
    setNextLegId(nextLegId + 1);
  };

  // Remove a leg
  const removeLeg = (legId) => {
    if (legs.length <= 1) {
      setError('Strategy must have at least one leg');
      return;
    }
    setLegs(legs.filter((l) => l.id !== legId));
  };

  // Update a leg property
  const updateLeg = async (legId, field, value) => {
    setLegs(
      legs.map((leg) => {
        if (leg.id !== legId) return leg;

        const updatedLeg = { ...leg, [field]: value };

        // Clear premium if strike/expiry/type changes
        if (['strike', 'expiry', 'option_type'].includes(field)) {
          updatedLeg.premium = null;
          updatedLeg.greeks = null;
        }

        return updatedLeg;
      })
    );

    // Fetch strikes if expiry changed
    if (field === 'expiry' && value) {
      fetchStrikes(value);
    }
  };

  // Refresh all premiums
  const refreshAllPremiums = async () => {
    const updatedLegs = await Promise.all(
      legs.map(async (leg) => {
        if (!leg.strike || !leg.expiry) return leg;
        const premiumData = await fetchPremium(leg);
        return {
          ...leg,
          premium: premiumData?.premium || null,
          greeks: premiumData
            ? {
                delta: premiumData.delta,
                gamma: premiumData.gamma,
                theta: premiumData.theta,
                vega: premiumData.vega,
                iv: premiumData.iv,
              }
            : null,
        };
      })
    );
    setLegs(updatedLegs);
  };

  // Calculate totals
  const totals = useMemo(() => {
    let totalPremium = 0;
    let totalDelta = 0;
    let totalGamma = 0;
    let totalTheta = 0;
    let totalVega = 0;
    let validLegs = 0;

    legs.forEach((leg) => {
      if (leg.premium) {
        const multiplier = leg.side === 'buy' ? -1 : 1;
        totalPremium += multiplier * leg.premium * leg.quantity;
        validLegs++;

        if (leg.greeks) {
          const deltaMultiplier = leg.side === 'buy' ? 1 : -1;
          totalDelta += deltaMultiplier * (leg.greeks.delta || 0) * leg.quantity;
          totalGamma += Math.abs((leg.greeks.gamma || 0) * leg.quantity);
          totalTheta += deltaMultiplier * (leg.greeks.theta || 0) * leg.quantity;
          totalVega += Math.abs((leg.greeks.vega || 0) * leg.quantity);
        }
      }
    });

    return {
      premium: totalPremium,
      delta: totalDelta,
      gamma: totalGamma,
      theta: totalTheta,
      vega: totalVega,
      validLegs,
      isCredit: totalPremium > 0,
    };
  }, [legs]);

  // Validate strategy
  const validation = useMemo(() => {
    const errors = [];

    if (!strategyName.trim()) {
      errors.push('Strategy name is required');
    }

    legs.forEach((leg, idx) => {
      if (!leg.expiry) errors.push(`Leg ${idx + 1}: Expiry required`);
      if (!leg.strike) errors.push(`Leg ${idx + 1}: Strike required`);
      if (leg.quantity < 1) errors.push(`Leg ${idx + 1}: Quantity must be at least 1`);
    });

    // Check for duplicate legs
    const legSignatures = legs.map((l) => `${l.option_type}-${l.strike}-${l.expiry}-${l.side}`);
    const duplicates = legSignatures.filter((s, i) => legSignatures.indexOf(s) !== i);
    if (duplicates.length > 0) {
      errors.push('Duplicate legs detected');
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }, [strategyName, legs]);

  // Create strategy
  const handleCreate = async () => {
    if (!validation.isValid) {
      setError(validation.errors.join(', '));
      return;
    }

    setCreating(true);
    setError(null);

    try {
      // Group legs by expiry for multi-expiry support
      // For now, use the first leg's expiry as primary
      const primaryExpiry = legs[0].expiry;

      const res = await fetch(`${API_BASE}/create-custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: strategyName,
          underlying,
          expiry: primaryExpiry,
          legs: legs.map((leg) => ({
            option_type: leg.option_type,
            strike: parseFloat(leg.strike),
            side: leg.side,
            quantity: leg.quantity,
            expiry: leg.expiry, // Include per-leg expiry
          })),
        }),
      });

      const data = await res.json();

      if (data.success) {
        setCreatedStrategy(data.strategy);
        setSuccess(`Strategy "${strategyName}" created successfully!`);
        if (onStrategyCreated) {
          onStrategyCreated(data.strategy);
        }
      } else {
        setError(data.error || 'Failed to create strategy');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  // Execute strategy (one-click)
  const handleExecute = async () => {
    if (!createdStrategy) {
      // Create and execute in one flow
      await handleCreate();
      return;
    }

    setExecuting(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/execute/${createdStrategy.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'market' }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess(`Strategy executed! ${data.legs_filled || 0} legs placed.`);
        if (onExecutionComplete) {
          onExecutionComplete(data);
        }
      } else {
        setError(data.error || data.message || 'Execution failed');
      }
    } catch (err) {
      setError(`Execution error: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  // One-click create and execute
  const handleOneClickExecute = async () => {
    if (!validation.isValid) {
      setError(validation.errors.join(', '));
      return;
    }

    setExecuting(true);
    setError(null);

    try {
      // First create
      const createRes = await fetch(`${API_BASE}/create-custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: strategyName,
          underlying,
          expiry: legs[0].expiry,
          legs: legs.map((leg) => ({
            option_type: leg.option_type,
            strike: parseFloat(leg.strike),
            side: leg.side,
            quantity: leg.quantity,
            expiry: leg.expiry,
          })),
        }),
      });

      const createData = await createRes.json();

      if (!createData.success) {
        throw new Error(createData.error || 'Failed to create strategy');
      }

      // Then execute
      const execRes = await fetch(`${API_BASE}/execute/${createData.strategy.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'market' }),
      });

      const execData = await execRes.json();

      if (execData.success) {
        setCreatedStrategy(createData.strategy);
        setSuccess(`Strategy created and executed! ${execData.legs_filled || 0} legs placed.`);
        if (onExecutionComplete) {
          onExecutionComplete(execData);
        }
      } else {
        setCreatedStrategy(createData.strategy);
        setError(execData.error || execData.message || 'Execution failed');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  // Reset form
  const handleReset = () => {
    setStrategyName('My Custom Strategy');
    setLegs([createEmptyLeg(1)]);
    setNextLegId(2);
    setCreatedStrategy(null);
    setError(null);
    setSuccess(null);
  };

  // Format expiry for display
  const formatExpiry = (expiry) => {
    if (!expiry || expiry.length !== 8) return expiry;
    const day = expiry.slice(0, 2);
    const month = expiry.slice(2, 4);
    const year = expiry.slice(4, 8);
    const date = new Date(year, parseInt(month) - 1, day);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <Paper sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <BuildIcon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Box>
          <Typography variant="h5" fontWeight="bold">
            Build Your Own Strategy
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create custom multi-leg strategies with any number of legs and expiries
          </Typography>
        </Box>
      </Box>

      {/* Alerts */}
      <Collapse in={!!error}>
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      </Collapse>

      <Collapse in={!!success}>
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      </Collapse>

      {/* Strategy Settings */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            size="small"
            label="Strategy Name"
            value={strategyName}
            onChange={(e) => setStrategyName(e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={3}>
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
        <Grid item xs={12} sm={3}>
          <Button
            fullWidth
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={refreshAllPremiums}
            disabled={legs.every((l) => !l.strike || !l.expiry)}
          >
            Refresh Prices
          </Button>
        </Grid>
      </Grid>

      <Divider sx={{ mb: 3 }} />

      {/* Legs Table */}
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        Strategy Legs
        <Chip label={`${legs.length} leg${legs.length > 1 ? 's' : ''}`} size="small" />
      </Typography>

      <TableContainer sx={{ mb: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Side</TableCell>
              <TableCell>Expiry</TableCell>
              <TableCell>Strike</TableCell>
              <TableCell>Qty</TableCell>
              <TableCell align="right">Premium</TableCell>
              <TableCell align="right">Delta</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {legs.map((leg, idx) => (
              <TableRow key={leg.id}>
                <TableCell>{idx + 1}</TableCell>

                {/* Option Type */}
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 100 }}>
                    <Select
                      value={leg.option_type}
                      onChange={(e) => updateLeg(leg.id, 'option_type', e.target.value)}
                    >
                      <MenuItem value="call">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CallIcon sx={{ color: 'success.main', fontSize: 18 }} />
                          Call
                        </Box>
                      </MenuItem>
                      <MenuItem value="put">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <PutIcon sx={{ color: 'error.main', fontSize: 18 }} />
                          Put
                        </Box>
                      </MenuItem>
                    </Select>
                  </FormControl>
                </TableCell>

                {/* Side */}
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 90 }}>
                    <Select
                      value={leg.side}
                      onChange={(e) => updateLeg(leg.id, 'side', e.target.value)}
                    >
                      <MenuItem value="buy">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <BuyIcon sx={{ color: 'primary.main', fontSize: 18 }} />
                          Buy
                        </Box>
                      </MenuItem>
                      <MenuItem value="sell">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <SellIcon sx={{ color: 'warning.main', fontSize: 18 }} />
                          Sell
                        </Box>
                      </MenuItem>
                    </Select>
                  </FormControl>
                </TableCell>

                {/* Expiry */}
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 120 }}>
                    <Select
                      value={leg.expiry}
                      onChange={(e) => updateLeg(leg.id, 'expiry', e.target.value)}
                      displayEmpty
                    >
                      <MenuItem value="">
                        <em>{loadingExpiries ? 'Loading...' : 'Select'}</em>
                      </MenuItem>
                      {expiries.map((exp) => (
                        <MenuItem key={exp} value={exp}>
                          {formatExpiry(exp)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </TableCell>

                {/* Strike */}
                <TableCell>
                  <FormControl size="small" sx={{ minWidth: 110 }}>
                    {strikesByExpiry[leg.expiry] ? (
                      <Select
                        value={leg.strike}
                        onChange={(e) => updateLeg(leg.id, 'strike', e.target.value)}
                        displayEmpty
                      >
                        <MenuItem value="">
                          <em>Select</em>
                        </MenuItem>
                        {strikesByExpiry[leg.expiry].map((strike) => (
                          <MenuItem
                            key={strike}
                            value={strike}
                            sx={{
                              fontWeight: strike === atmByExpiry[leg.expiry] ? 'bold' : 'normal',
                              bgcolor:
                                strike === atmByExpiry[leg.expiry] ? 'action.selected' : 'inherit',
                            }}
                          >
                            ${strike.toLocaleString()}
                            {strike === atmByExpiry[leg.expiry] && ' (ATM)'}
                          </MenuItem>
                        ))}
                      </Select>
                    ) : (
                      <TextField
                        size="small"
                        type="number"
                        value={leg.strike}
                        onChange={(e) => updateLeg(leg.id, 'strike', e.target.value)}
                        placeholder="Strike"
                        InputProps={{
                          startAdornment: <InputAdornment position="start">$</InputAdornment>,
                        }}
                      />
                    )}
                  </FormControl>
                </TableCell>

                {/* Quantity */}
                <TableCell>
                  <TextField
                    size="small"
                    type="number"
                    value={leg.quantity}
                    onChange={(e) => updateLeg(leg.id, 'quantity', parseInt(e.target.value) || 1)}
                    inputProps={{ min: 1, max: 100 }}
                    sx={{ width: 70 }}
                  />
                </TableCell>

                {/* Premium */}
                <TableCell align="right">
                  {leg.premium ? (
                    <Tooltip title={`IV: ${leg.greeks?.iv?.toFixed(1)}%`}>
                      <Typography
                        variant="body2"
                        color={leg.side === 'sell' ? 'success.main' : 'error.main'}
                      >
                        ${(leg.premium * leg.quantity).toFixed(2)}
                      </Typography>
                    </Tooltip>
                  ) : (
                    <Typography variant="body2" color="text.disabled">
                      -
                    </Typography>
                  )}
                </TableCell>

                {/* Delta */}
                <TableCell align="right">
                  {leg.greeks?.delta ? (
                    <Typography variant="body2">
                      {((leg.side === 'buy' ? 1 : -1) * leg.greeks.delta * leg.quantity).toFixed(3)}
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.disabled">
                      -
                    </Typography>
                  )}
                </TableCell>

                {/* Actions */}
                <TableCell align="center">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => removeLeg(leg.id)}
                    disabled={legs.length <= 1}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Add Leg Button */}
      <Button variant="outlined" startIcon={<AddIcon />} onClick={addLeg} sx={{ mb: 3 }}>
        Add Leg
      </Button>

      <Divider sx={{ mb: 3 }} />

      {/* Summary */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Strategy Summary
              </Typography>
              <Grid container spacing={1}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Net Premium:
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography
                    variant="body1"
                    fontWeight="bold"
                    color={totals.isCredit ? 'success.main' : 'error.main'}
                  >
                    {totals.isCredit ? '+' : ''}
                    {totals.premium.toFixed(2)} USD
                    <Typography variant="caption" component="span" sx={{ ml: 1 }}>
                      ({totals.isCredit ? 'Credit' : 'Debit'})
                    </Typography>
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Net Delta:
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body1">{totals.delta.toFixed(3)}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Total Theta:
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body1">{totals.theta.toFixed(2)}/day</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Validation Status
              </Typography>
              {validation.isValid ? (
                <Alert severity="success" sx={{ py: 0 }}>
                  Ready to execute ({legs.length} leg{legs.length > 1 ? 's' : ''})
                </Alert>
              ) : (
                <Alert severity="warning" sx={{ py: 0 }}>
                  {validation.errors[0]}
                  {validation.errors.length > 1 && ` (+${validation.errors.length - 1} more)`}
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
        <Button variant="outlined" onClick={handleReset}>
          Reset
        </Button>

        <Button
          variant="contained"
          color="primary"
          startIcon={creating ? <CircularProgress size={20} /> : <CalcIcon />}
          onClick={handleCreate}
          disabled={!validation.isValid || creating || executing}
        >
          Create Strategy
        </Button>

        <Button
          variant="contained"
          color="success"
          startIcon={executing ? <CircularProgress size={20} /> : <ExecuteIcon />}
          onClick={handleOneClickExecute}
          disabled={!validation.isValid || creating || executing}
          sx={{ minWidth: 180 }}
        >
          One-Click Execute
        </Button>
      </Box>

      {/* Created Strategy Info */}
      {createdStrategy && (
        <Box sx={{ mt: 3 }}>
          <Alert severity="info">
            <Typography variant="body2">
              Strategy ID: <strong>{createdStrategy.id}</strong>
              {' | '}
              Status: <Chip label={createdStrategy.status} size="small" sx={{ ml: 1 }} />
            </Typography>
          </Alert>
        </Box>
      )}
    </Paper>
  );
}
