/**
 * Strategy Review Dialog
 * ======================
 * Shows selected legs, payoff preview, and executes all legs simultaneously.
 *
 * Created: January 5, 2026
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Divider,
  Alert,
  CircularProgress,
  Grid,
  FormControlLabel,
  Switch,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  PlayArrow as ExecuteIcon,
  Assessment as PayoffIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import PayoffDiagram from '../optionsStrategy/PayoffDiagram';

// Format helpers
const formatPrice = (price) => {
  if (price === null || price === undefined) return '-';
  return `$${Number(price).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  // DDMMYYYY -> Weekday, MMM DD
  if (!dateStr || dateStr.length !== 8) return dateStr;
  const day = parseInt(dateStr.slice(0, 2));
  const month = parseInt(dateStr.slice(2, 4)) - 1; // JS months are 0-indexed
  const year = parseInt(dateStr.slice(4, 8));

  const date = new Date(year, month, day);
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];

  const weekday = weekdays[date.getDay()];
  const dayStr = day.toString().padStart(2, '0');

  return `${weekday}, ${months[month]} ${dayStr}`;
};

export default function StrategyReviewDialog({
  open,
  onClose,
  strategyContext,
  selectedLegs,
  spotPrice,
  expiry,
  underlying,
  onExecutionSuccess,
  onExecutionError,
}) {
  const [executing, setExecuting] = useState(false);
  const [executionMode, setExecutionMode] = useState('parallel');
  const [orderType, setOrderType] = useState('limit');
  const [slippage, setSlippage] = useState(0.5);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [executionProgress, setExecutionProgress] = useState([]);
  const [executionStep, setExecutionStep] = useState('');

  // Calculate strategy costs and metrics
  const strategyMetrics = useMemo(() => {
    if (!selectedLegs || selectedLegs.length === 0) {
      return { netCost: 0, maxRisk: 0, maxProfit: 0, breakevens: [] };
    }

    let totalCost = 0;
    let totalCredit = 0;

    selectedLegs.forEach((leg) => {
      const price = leg.side === 'buy' ? leg.ask : leg.bid;
      if (leg.side === 'buy') {
        totalCost += price || 0;
      } else {
        totalCredit += price || 0;
      }
    });

    const netCost = totalCost - totalCredit;

    // Calculate rough max risk/profit based on strategy type
    let maxRisk = 0;
    let maxProfit = 0;
    const strategyType = strategyContext?.strategyType?.toLowerCase() || '';

    if (strategyType.includes('long') || strategyType.includes('debit')) {
      // Debit strategies: max risk = premium paid
      maxRisk = netCost;
      maxProfit = 'Unlimited';
    } else if (strategyType.includes('short') || strategyType.includes('credit')) {
      // Credit strategies: max profit = premium received
      maxRisk = 'Potentially Unlimited';
      maxProfit = Math.abs(netCost);
    } else if (strategyType.includes('iron') || strategyType.includes('spread')) {
      // Defined risk spreads
      const strikes = selectedLegs.map((l) => l.strike).sort((a, b) => a - b);
      const width = strikes.length >= 2 ? strikes[strikes.length - 1] - strikes[0] : 0;
      maxRisk = Math.abs(netCost) + width;
      maxProfit = width - Math.abs(netCost);
    }

    // Calculate breakeven points (simplified)
    const breakevens = [];
    if (strategyType.includes('straddle') || strategyType.includes('strangle')) {
      const atmStrike = selectedLegs[0]?.strike || spotPrice;
      const premium = Math.abs(netCost);
      breakevens.push(atmStrike - premium);
      breakevens.push(atmStrike + premium);
    }

    return { netCost, totalCost, totalCredit, maxRisk, maxProfit, breakevens };
  }, [selectedLegs, strategyContext, spotPrice]);

  // Build payoff data for diagram
  const payoffData = useMemo(() => {
    if (!selectedLegs || selectedLegs.length === 0 || !spotPrice) return null;

    const legs = selectedLegs.map((leg) => ({
      option_type: leg.type,
      side: leg.side,
      strike: leg.strike,
      premium: leg.side === 'buy' ? leg.ask : leg.bid,
      quantity: 1,
    }));

    return {
      legs,
      spot_price: spotPrice,
      strategy_type: strategyContext?.strategyType || 'custom',
    };
  }, [selectedLegs, spotPrice, strategyContext]);

  // Execute the strategy
  const handleExecute = useCallback(async () => {
    if (!confirmChecked) return;

    setExecuting(true);
    setExecutionProgress([]);
    setExecutionStep('Creating strategy...');

    try {
      // First create the strategy, then execute it
      const createPayload = {
        strategy_type: strategyContext?.strategyType || 'custom',
        underlying: underlying,
        expiry: expiry,
        legs: selectedLegs.map((leg) => ({
          symbol: leg.symbol,
          option_type: leg.type,
          strike: leg.strike,
          side: leg.side,
          quantity: 1,
        })),
        name: `${strategyContext?.strategyName || 'Custom'} - ${underlying} ${formatDate(expiry)}`,
      };

      // Create strategy
      setExecutionProgress((prev) => [...prev, '📝 Creating strategy...']);
      const createResponse = await fetch('/api/options-strategy/create-custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createPayload),
      });

      const createResult = await createResponse.json();

      // Check if feature not implemented (501 status)
      if (createResponse.status === 501 || createResult.status === 501) {
        throw new Error(
          '⚠️ Strategy builder not yet implemented. This feature is under development. Please use single-leg orders for now.'
        );
      }

      if (!createResponse.ok || createResult.error) {
        throw new Error(createResult.error || 'Failed to create strategy');
      }

      const strategyId = createResult.strategy?.id;

      if (!strategyId) {
        throw new Error('No strategy ID returned');
      }

      setExecutionProgress((prev) => [
        ...prev,
        `✅ Strategy created (ID: ${strategyId.slice(0, 8)}...)`,
      ]);
      setExecutionStep('Validating and executing legs...');

      // Now execute the strategy
      const executePayload = {
        execution_mode: executionMode,
        order_type: orderType,
      };

      setExecutionProgress((prev) => [...prev, `🔍 Validating ${selectedLegs.length} legs...`]);
      setExecutionProgress((prev) => [
        ...prev,
        `📤 Placing ${orderType} orders (${executionMode} mode)...`,
      ]);

      const executeResponse = await fetch(`/api/options-strategy/execute/${strategyId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(executePayload),
      });

      const executeResult = await executeResponse.json();

      if (!executeResponse.ok || !executeResult.success) {
        // Build detailed error message
        let errorMsg = executeResult.message || executeResult.error || 'Execution failed';

        // Include specific leg errors if available
        if (
          executeResult.errors &&
          Array.isArray(executeResult.errors) &&
          executeResult.errors.length > 0
        ) {
          errorMsg += ':\n' + executeResult.errors.join('\n');
        }

        throw new Error(errorMsg);
      }

      // Show execution results
      if (executeResult.legs_filled) {
        setExecutionProgress((prev) => [
          ...prev,
          `✅ Filled ${executeResult.legs_filled}/${executeResult.legs_total} legs`,
        ]);
      }
      if (executeResult.total_cost !== undefined) {
        setExecutionProgress((prev) => [
          ...prev,
          `💰 Total cost: $${executeResult.total_cost.toFixed(2)}`,
        ]);
      }
      setExecutionStep('Execution complete!');

      // Wait a moment to show final status
      await new Promise((resolve) => setTimeout(resolve, 1000));

      onExecutionSuccess?.(executeResult);
    } catch (error) {
      console.error('Strategy execution error:', error);
      setExecutionProgress((prev) => [...prev, `❌ Error: ${error.message}`]);
      setExecutionStep('Execution failed');

      // Keep error visible for a moment
      await new Promise((resolve) => setTimeout(resolve, 2000));

      onExecutionError?.(error.message);
    } finally {
      setExecuting(false);
    }
  }, [
    confirmChecked,
    strategyContext,
    underlying,
    expiry,
    selectedLegs,
    executionMode,
    orderType,
    onExecutionSuccess,
    onExecutionError,
  ]);

  if (!strategyContext || !selectedLegs) return null;

  return (
    <Dialog
      open={open}
      onClose={executing ? undefined : onClose}
      maxWidth="lg"
      fullWidth
      disableRestoreFocus
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <PayoffIcon color="primary" />
        <Typography variant="h6" fontWeight="bold">
          Review Strategy: {strategyContext.strategyName || strategyContext.strategyType}
        </Typography>
        <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
          <Chip label={underlying} color="primary" size="small" />
          <Chip label={formatDate(expiry)} variant="outlined" size="small" />
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Grid container spacing={3}>
          {/* Left: Legs Table & Execution Settings */}
          <Grid item xs={12} md={6}>
            {/* Selected Legs */}
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              📋 Strategy Legs ({selectedLegs.length})
            </Typography>

            <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'action.hover' }}>
                    <TableCell>Type</TableCell>
                    <TableCell>Strike</TableCell>
                    <TableCell>Side</TableCell>
                    <TableCell align="right">Price</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selectedLegs.map((leg, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Chip
                          label={leg.type.toUpperCase()}
                          size="small"
                          color={leg.type === 'call' ? 'success' : 'error'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell fontWeight="bold">{formatPrice(leg.strike)}</TableCell>
                      <TableCell>
                        <Chip
                          label={leg.side.toUpperCase()}
                          size="small"
                          color={leg.side === 'buy' ? 'primary' : 'warning'}
                        />
                      </TableCell>
                      <TableCell align="right">
                        {formatPrice(leg.side === 'buy' ? leg.ask : leg.bid)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Summary Metrics */}
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                📊 Strategy Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">
                    Net Cost/Credit
                  </Typography>
                  <Typography
                    variant="h6"
                    fontWeight="bold"
                    color={strategyMetrics.netCost > 0 ? 'error.main' : 'success.main'}
                  >
                    {strategyMetrics.netCost > 0 ? 'Debit ' : 'Credit '}
                    {formatPrice(Math.abs(strategyMetrics.netCost))}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">
                    Spot Price
                  </Typography>
                  <Typography variant="h6" fontWeight="bold">
                    {formatPrice(spotPrice)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">
                    Max Risk
                  </Typography>
                  <Typography variant="body1" color="error.main">
                    {typeof strategyMetrics.maxRisk === 'string'
                      ? strategyMetrics.maxRisk
                      : formatPrice(strategyMetrics.maxRisk)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">
                    Max Profit
                  </Typography>
                  <Typography variant="body1" color="success.main">
                    {typeof strategyMetrics.maxProfit === 'string'
                      ? strategyMetrics.maxProfit
                      : formatPrice(strategyMetrics.maxProfit)}
                  </Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* Execution Settings */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                ⚙️ Execution Settings
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Execution Mode</InputLabel>
                    <Select
                      value={executionMode}
                      onChange={(e) => setExecutionMode(e.target.value)}
                      label="Execution Mode"
                    >
                      <MenuItem value="parallel">Parallel (Simultaneous)</MenuItem>
                      <MenuItem value="sequential">Sequential</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Order Type</InputLabel>
                    <Select
                      value={orderType}
                      onChange={(e) => setOrderType(e.target.value)}
                      label="Order Type"
                    >
                      <MenuItem value="limit">Limit</MenuItem>
                      <MenuItem value="market">Market</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>

              <Alert severity="info" sx={{ mt: 2 }} icon="💡">
                <Typography variant="caption">
                  <strong>Parallel:</strong> All legs placed simultaneously to minimize slippage.
                  <br />
                  <strong>Sequential:</strong> Legs placed one by one (may have slippage between
                  legs).
                </Typography>
              </Alert>
            </Paper>
          </Grid>

          {/* Right: Payoff Diagram */}
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              📈 Payoff at Expiration
            </Typography>

            <Paper variant="outlined" sx={{ p: 2, height: 350 }}>
              {payoffData ? (
                <PayoffDiagram data={payoffData} height={300} />
              ) : (
                <Box
                  sx={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Typography color="text.secondary">Select legs to see payoff diagram</Typography>
                </Box>
              )}
            </Paper>

            {/* Risk Warning */}
            <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}>
              <Typography variant="caption">
                <strong>Risk Disclosure:</strong> Options trading involves significant risk of loss.
                Ensure you understand the risks before executing this strategy. Past performance
                does not guarantee future results.
              </Typography>
            </Alert>
          </Grid>
        </Grid>
      </DialogContent>

      {/* Execution Progress Panel */}
      {executing && (
        <Box sx={{ px: 3, py: 2, bgcolor: 'primary.dark', borderTop: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <CircularProgress size={20} color="inherit" />
            <Typography variant="subtitle2" fontWeight="bold" color="primary.light">
              {executionStep}
            </Typography>
          </Box>

          {executionProgress.length > 0 && (
            <Box
              sx={{
                mt: 1,
                p: 1.5,
                bgcolor: 'background.paper',
                borderRadius: 1,
                maxHeight: 120,
                overflowY: 'auto',
              }}
            >
              {executionProgress.map((msg, idx) => (
                <Typography
                  key={idx}
                  variant="caption"
                  component="div"
                  sx={{
                    fontFamily: 'monospace',
                    mb: 0.5,
                    color: msg.includes('❌')
                      ? 'error.main'
                      : msg.includes('✅')
                        ? 'success.main'
                        : 'text.primary',
                  }}
                >
                  {msg}
                </Typography>
              ))}
            </Box>
          )}
        </Box>
      )}

      <DialogActions sx={{ p: 2, bgcolor: 'action.hover' }}>
        <FormControlLabel
          control={
            <Switch
              checked={confirmChecked}
              onChange={(e) => setConfirmChecked(e.target.checked)}
              color="primary"
            />
          }
          label={
            <Typography variant="body2">I understand the risks and confirm this order</Typography>
          }
        />

        <Box sx={{ flexGrow: 1 }} />

        <Button onClick={onClose} disabled={executing} variant="outlined">
          Cancel
        </Button>

        <Button
          variant="contained"
          color="success"
          size="large"
          startIcon={executing ? <CircularProgress size={20} color="inherit" /> : <ExecuteIcon />}
          onClick={handleExecute}
          disabled={!confirmChecked || executing}
          sx={{ minWidth: 180, fontWeight: 'bold' }}
        >
          {executing ? 'Executing...' : 'Execute Strategy'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
