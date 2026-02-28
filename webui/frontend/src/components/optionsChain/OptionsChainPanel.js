/**
 * Options Chain Panel
 * ====================
 * Main container for options chain market data display.
 * Now includes trading functionality via OrderDialog.
 * Supports multi-leg strategy selection mode.
 *
 * Created: January 5, 2026
 * Updated: January 5, 2026 - Added trading functionality
 * Updated: January 5, 2026 - Added strategy leg selection mode
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  Chip,
  Switch,
  FormControlLabel,
  Snackbar,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import BuildIcon from '@mui/icons-material/Build';

import { optionsChainAPI } from './services/chainAPI';
import ChainTable from './ChainTable';
import OrderDialog from './OrderDialog';
import StrategyLegSelector from './StrategyLegSelector';
import StrategyReviewDialog from './StrategyReviewDialog';
import StrategyBuilderPanel from './StrategyBuilderPanel';

// Formatting helpers
const formatDate = (dateStr) => {
  // DDMMYYYY -> Weekday, DD MMM YYYY
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

const formatPrice = (price) => {
  if (price === null || price === undefined) return '-';
  return `$${Number(price).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
};

const OptionsChainPanel = ({ strategyParams, buildYourOwnMode = false }) => {
  // State
  const [underlying, setUnderlying] = useState('BTC');
  const [expiry, setExpiry] = useState('');
  const [expirations, setExpirations] = useState([]);
  const [chainData, setChainData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Strategy selection mode (template-based from Strategy Builder)
  const [strategyMode, setStrategyMode] = useState(false);
  const [strategyContext, setStrategyContext] = useState(null);
  const [selectedLegs, setSelectedLegs] = useState([]);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [executing, setExecuting] = useState(false);

  // Build Your Own mode (free-form strategy building)
  const [builderMode, setBuilderMode] = useState(buildYourOwnMode);
  const [builderLegs, setBuilderLegs] = useState([]);

  // Execution trigger for log panel
  const [executionRefreshTrigger, setExecutionRefreshTrigger] = useState(0);

  // Enable builder mode from prop or sessionStorage
  useEffect(() => {
    if (buildYourOwnMode) {
      setBuilderMode(true);
    }
    // Check sessionStorage for "build_your_own" flag
    const buildFlag = sessionStorage.getItem('build_your_own_strategy');
    if (buildFlag === 'true') {
      setBuilderMode(true);
      sessionStorage.removeItem('build_your_own_strategy');
    }
  }, [buildYourOwnMode]);

  // Check for strategy context on mount (from Strategy Builder navigation)
  useEffect(() => {
    const pendingStrategy = sessionStorage.getItem('pending_strategy');
    if (pendingStrategy) {
      try {
        const context = JSON.parse(pendingStrategy);
        setStrategyContext(context);
        setStrategyMode(true);
        // Clear after reading
        sessionStorage.removeItem('pending_strategy');
      } catch (e) {
        console.error('Failed to parse strategy context:', e);
      }
    }

    // Also check if strategyParams was passed directly as prop
    if (strategyParams) {
      setStrategyContext(strategyParams);
      setStrategyMode(true);
    }
  }, [strategyParams]);

  // Handle leg selection from chain
  const handleLegSelected = useCallback(
    (optionData) => {
      if (!strategyMode || !strategyContext) return;

      const maxLegs = strategyContext.requiredLegs || 4;
      const legDefinitions = strategyContext.legDefinitions || [];

      // Check if we've reached max legs
      if (selectedLegs.length >= maxLegs) {
        setSnackbar({
          open: true,
          message: `All ${maxLegs} legs selected. Click "Review & Execute" to continue.`,
          severity: 'info',
        });
        return;
      }

      // Check if this leg is already selected
      const alreadySelected = selectedLegs.find(
        (leg) => leg.symbol === optionData.symbol && leg.side === optionData.side
      );

      if (alreadySelected) {
        setSnackbar({
          open: true,
          message: 'This option is already selected',
          severity: 'warning',
        });
        return;
      }

      // Get the expected leg definition for current leg index
      const currentLegIndex = selectedLegs.length;
      const expectedLeg = legDefinitions[currentLegIndex];

      // If we have a leg definition, enforce the type and side
      if (expectedLeg) {
        // Check if option type matches expected
        if (expectedLeg.type !== optionData.type) {
          setSnackbar({
            open: true,
            message: `Expected ${expectedLeg.type.toUpperCase()} for leg ${currentLegIndex + 1}, but got ${optionData.type.toUpperCase()}`,
            severity: 'error',
          });
          return;
        }

        // Override the side with expected side from strategy definition
        optionData = { ...optionData, side: expectedLeg.side };
      }

      setSelectedLegs((prev) => [...prev, optionData]);

      // Show notification
      const newCount = selectedLegs.length + 1;
      if (newCount >= maxLegs) {
        setSnackbar({
          open: true,
          message: `✅ All ${maxLegs} legs selected! Click "Review & Execute" to continue.`,
          severity: 'success',
        });
      } else {
        setSnackbar({
          open: true,
          message: `Leg ${newCount}/${maxLegs} added: ${optionData.side.toUpperCase()} ${optionData.type} @ $${optionData.strike}`,
          severity: 'success',
        });
      }
    },
    [strategyMode, strategyContext, selectedLegs]
  );

  // Handle Build Your Own mode leg selection (free-form)
  const handleBuilderLegSelected = useCallback(
    (optionData) => {
      // Check if this exact leg already exists
      const existingIndex = builderLegs.findIndex(
        (leg) => leg.symbol === optionData.symbol && leg.side === optionData.side
      );

      if (existingIndex >= 0) {
        // Remove if already selected
        setBuilderLegs((prev) => {
          const newLegs = [...prev];
          newLegs.splice(existingIndex, 1);
          return newLegs;
        });
        setSnackbar({
          open: true,
          message: `Removed: ${optionData.side.toUpperCase()} ${optionData.type} @ $${optionData.strike}`,
          severity: 'info',
        });
      } else {
        // Add new leg with current expiry and complete pricing data
        const newLeg = {
          ...optionData,
          expiry: expiry,
          quantity: 1,
          premium: optionData.ltp || optionData.mark_price || 0,
          ltp: optionData.ltp,
          bid: optionData.bid,
          ask: optionData.ask,
          best_bid_price: optionData.best_bid_price || optionData.bid,
          best_ask_price: optionData.best_ask_price || optionData.ask,
          mark_price: optionData.mark_price,
        };
        setBuilderLegs((prev) => [...prev, newLeg]);
        setSnackbar({
          open: true,
          message: `Added: ${optionData.side.toUpperCase()} ${optionData.type} @ $${optionData.strike}`,
          severity: 'success',
        });
      }
    },
    [builderLegs, expiry]
  );

  // Update builder leg
  const handleUpdateBuilderLeg = useCallback((index, field, value) => {
    setBuilderLegs((prev) => {
      const newLegs = [...prev];
      newLegs[index] = { ...newLegs[index], [field]: value };
      return newLegs;
    });
  }, []);

  // Remove builder leg
  const handleRemoveBuilderLeg = useCallback((index) => {
    setBuilderLegs((prev) => {
      const newLegs = [...prev];
      newLegs.splice(index, 1);
      return newLegs;
    });
  }, []);

  // Clear all builder legs
  const handleClearBuilderLegs = useCallback(() => {
    setBuilderLegs([]);
  }, []);

  // Handle removing a leg
  const handleRemoveLeg = useCallback((index) => {
    setSelectedLegs((prev) => {
      const newLegs = [...prev];
      newLegs.splice(index, 1);
      return newLegs;
    });
  }, []);

  // Handle strategy complete - open review dialog
  const handleStrategyComplete = useCallback(() => {
    setReviewDialogOpen(true);
  }, []);

  // Handle cancel strategy mode
  const handleCancelStrategy = useCallback(() => {
    setStrategyMode(false);
    setStrategyContext(null);
    setSelectedLegs([]);
    setReviewDialogOpen(false);
  }, []);

  // Handle successful execution
  const handleExecutionSuccess = useCallback(
    (result) => {
      setReviewDialogOpen(false);
      setSnackbar({
        open: true,
        message: `Strategy executed successfully! ${result.orders?.length || 0} legs placed.`,
        severity: 'success',
      });
      // Trigger immediate log panel refresh
      setExecutionRefreshTrigger(prev => prev + 1);
      handleCancelStrategy();
      fetchChainData(); // Refresh chain
    },
    [handleCancelStrategy]
  );

  // Handle execution error
  const handleExecutionError = useCallback((error) => {
    // Split error message into lines for better display
    const errorLines = error.split('\n').filter((line) => line.trim());
    const mainError = errorLines[0] || 'Strategy execution failed';
    const details = errorLines.slice(1).join(' • ');

    const fullMessage = details ? `${mainError}: ${details}` : mainError;

    setSnackbar({
      open: true,
      message: fullMessage,
      severity: 'error',
    });
  }, []);

  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Open positions map: { [symbol]: { side, size, pnl } }
  const [openPositions, setOpenPositions] = useState({});

  // Fetch open positions to highlight used strikes on the chain
  const fetchOpenPositions = useCallback(async () => {
    try {
      const map = await optionsChainAPI.getOpenPositions();
      setOpenPositions(map);
    } catch (e) {
      console.warn('[OptionsChainPanel] Failed to fetch open positions:', e);
    }
  }, []);

  // Load on mount and refresh every 30s
  useEffect(() => {
    fetchOpenPositions();
    const interval = setInterval(fetchOpenPositions, 30000);
    return () => clearInterval(interval);
  }, [fetchOpenPositions]);

  // Trading state
  const [orderDialogOpen, setOrderDialogOpen] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // Fetch chain data when expiry changes - DEFINED EARLY to avoid initialization errors
  const fetchChainData = useCallback(async () => {
    if (!expiry) return;

    try {
      setLoading(true);
      setError(null);

      const data = await optionsChainAPI.getChainData(underlying, expiry);
      setChainData(data);
      setLastUpdated(new Date());
    } catch (err) {
      setError(`Failed to fetch chain data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [underlying, expiry]);

  // Fetch expirations when underlying changes
  useEffect(() => {
    const fetchExpirations = async () => {
      try {
        setLoading(true);
        setError(null);
        const exps = await optionsChainAPI.getExpirations(underlying);
        setExpirations(exps);

        // Auto-select first expiry if available
        if (exps.length > 0 && !expiry) {
          // Select nearest expiry (usually the first one)
          setExpiry(exps[0]);
        }
      } catch (err) {
        setError(`Failed to fetch expirations: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchExpirations();
  }, [underlying]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchChainData();
  }, [fetchChainData]);

  // Execute builder strategy using quick-execute endpoint
  const handleExecuteBuilderStrategy = useCallback(async (strategyData) => {
    setExecuting(true);
    try {
      console.log('=== Executing Strategy via quick-execute ===');
      console.log('Strategy data:', JSON.stringify(strategyData, null, 2));

      const requestPayload = {
        ...strategyData,
        execution_mode: 'parallel',
        order_type: 'limit'
      };

      console.log('Full request payload:', JSON.stringify(requestPayload, null, 2));

      // Use quick-execute endpoint - single call to create and execute
      const response = await fetch('/api/options-strategy/quick-execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
      });

      console.log('Response status:', response.status, response.statusText);

      const result = await response.json();
      console.log('Quick-execute response:', JSON.stringify(result, null, 2));

      if (!response.ok || !result.success) {
        // Extract detailed error info
        const errorMsg = result.error || result.message || 'Execution failed';
        const legErrors = result.execution?.leg_results?.filter(r => !r.success) || [];
        const detailedError = legErrors.length > 0
          ? `${errorMsg}: ${legErrors.map(r => r.error).join(', ')}`
          : errorMsg;
        console.error('Execution error details:', { errorMsg, legErrors, fullResult: result });
        throw new Error(detailedError);
      }

      // Success!
      const legsFilled = result.execution?.legs_filled || result.legs_filled || strategyData.legs.length;
      setSnackbar({
        open: true,
        message: `✅ Strategy executed! ${legsFilled}/${strategyData.legs.length} legs placed.`,
        severity: 'success',
      });
      setBuilderLegs([]);
      fetchChainData();
    } catch (err) {
      console.error('Strategy execution error:', err);
      setSnackbar({
        open: true,
        message: `❌ ${err.message}`,
        severity: 'error',
      });
    } finally {
      setExecuting(false);
    }
  }, [fetchChainData]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchChainData();
    }, 10000); // 10 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, fetchChainData]);

  // Handle refresh button
  const handleRefresh = useCallback(async () => {
    await optionsChainAPI.refresh(underlying, expiry);
    await fetchChainData();
  }, [underlying, expiry, fetchChainData]);

  // Handle trade button/cell click from ChainTable
  const handleTrade = useCallback((optionData) => {
    setSelectedOption(optionData);
    setOrderDialogOpen(true);
  }, []);

  // Handle order success from OrderDialog
  const handleOrderSuccess = useCallback(
    (order) => {
      setSnackbar({
        open: true,
        message: `Order placed successfully! ID: ${order.id}`,
        severity: 'success',
      });
      // Refresh chain data and open positions to reflect the new trade
      fetchChainData();
      setTimeout(fetchOpenPositions, 2000); // slight delay so exchange reflects the fill
    },
    [fetchChainData, fetchOpenPositions]
  );

  // Handle order error from OrderDialog
  const handleOrderError = useCallback((error) => {
    setSnackbar({
      open: true,
      message: `Order failed: ${error}`,
      severity: 'error',
    });
  }, []);

  // Close snackbar
  const handleCloseSnackbar = useCallback(() => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  }, []);

  // Calculate DTE (Days To Expiry)
  const dte = useMemo(() => {
    if (!expiry || expiry.length !== 8) return null;

    const day = parseInt(expiry.slice(0, 2));
    const month = parseInt(expiry.slice(2, 4)) - 1;
    const year = parseInt(expiry.slice(4, 8));

    const expiryDate = new Date(year, month, day);
    const today = new Date();
    const diffTime = expiryDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
  }, [expiry]);

  return (
    <Paper sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6" fontWeight="bold">
            📊 Options Chain
          </Typography>
          <Chip label="LIVE" color="success" size="small" sx={{}} />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastUpdated && (
            <Typography variant="caption" color="text.secondary">
              Updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                size="small"
              />
            }
            label="Auto-refresh"
          />
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon sx={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Controls */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2, alignItems: 'center' }}>
        {/* Build Your Own Button */}
        {!strategyMode && (
          <Button
            variant={builderMode ? 'contained' : 'outlined'}
            color="primary"
            startIcon={<BuildIcon />}
            onClick={() => {
              if (builderMode) {
                setBuilderMode(false);
                setBuilderLegs([]);
              } else {
                setBuilderMode(true);
              }
            }}
            sx={{ mr: 1 }}
          >
            {builderMode ? 'Exit Builder' : 'Build Your Own'}
          </Button>
        )}

        {/* Underlying Selector */}
        <ToggleButtonGroup
          value={underlying}
          exclusive
          onChange={(e, val) => val && setUnderlying(val)}
          size="small"
        >
          <ToggleButton value="BTC">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <span>₿</span> BTC
            </Box>
          </ToggleButton>
          <ToggleButton value="ETH">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <span>Ξ</span> ETH
            </Box>
          </ToggleButton>
        </ToggleButtonGroup>

        {/* Expiry Selector */}
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Expiry</InputLabel>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} label="Expiry">
            {expirations.map((exp) => (
              <MenuItem key={exp} value={exp}>
                {formatDate(exp)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Spot Price & ATM Info */}
        {chainData && (
          <Box sx={{ display: 'flex', gap: 3, ml: 'auto' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                {underlying} Spot
              </Typography>
              <Typography variant="h6" fontWeight="bold" color="primary">
                {formatPrice(chainData.spot_price)}
              </Typography>
            </Box>

            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                ATM Strike
              </Typography>
              <Typography variant="h6" fontWeight="bold">
                {formatPrice(chainData.atm_strike)}
              </Typography>
            </Box>

            {dte !== null && (
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Days to Expiry
                </Typography>
                <Typography
                  variant="h6"
                  fontWeight="bold"
                  color={dte <= 3 ? 'error.main' : dte <= 7 ? 'warning.main' : 'text.primary'}
                >
                  {dte}
                </Typography>
              </Box>
            )}

            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Put/Call Ratio
              </Typography>
              <Typography
                variant="h6"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
              >
                {chainData.summary.put_oi > 0 && chainData.summary.call_oi > 0
                  ? (chainData.summary.put_oi / chainData.summary.call_oi).toFixed(2)
                  : '-'}
                {chainData.summary.put_oi > chainData.summary.call_oi ? (
                  <TrendingDownIcon color="error" fontSize="small" />
                ) : (
                  <TrendingUpIcon color="success" fontSize="small" />
                )}
              </Typography>
            </Box>
          </Box>
        )}
      </Box>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading Spinner */}
      {loading && !chainData && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Strategy Mode Banner */}
      {strategyMode && strategyContext && (
        <Alert
          severity="info"
          icon="🎯"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={handleCancelStrategy}>
              Cancel
            </Button>
          }
        >
          <Typography variant="subtitle2" fontWeight="bold">
            Building: {strategyContext.strategyName || strategyContext.strategyType}
          </Typography>
          <Typography variant="caption">
            Select {strategyContext.requiredLegs} legs from the chain below • {selectedLegs.length}/
            {strategyContext.requiredLegs} selected
          </Typography>
        </Alert>
      )}

      {/* Builder Mode Banner */}
      {builderMode && !strategyMode && (
        <Alert
          severity="info"
          icon={<BuildIcon />}
          sx={{ mb: 2, bgcolor: 'rgba(33, 150, 243, 0.1)' }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                setBuilderMode(false);
                setBuilderLegs([]);
              }}
            >
              Exit Builder
            </Button>
          }
        >
          <Typography variant="subtitle2" fontWeight="bold">
            Build Your Own Strategy
          </Typography>
          <Typography variant="caption">
            Click B (Buy) or S (Sell) on any strike to add legs • {builderLegs.length} leg
            {builderLegs.length !== 1 ? 's' : ''} selected
          </Typography>
        </Alert>
      )}

      {/* Strategy Leg Selector (sticky on side) */}
      {strategyMode && strategyContext && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={9}>
            {/* Chain Table */}
            {chainData && (
              <ChainTable
                chainData={chainData}
                spotPrice={chainData.spot_price}
                atmStrike={chainData.atm_strike}
                onTrade={strategyMode ? handleLegSelected : handleTrade}
                strategyMode={strategyMode}
                strategyContext={strategyContext}
                selectedLegs={selectedLegs}
                expiry={expiry}
                openPositions={openPositions}
              />
            )}
          </Grid>
          <Grid item xs={12} md={3}>
            <StrategyLegSelector
              strategyContext={strategyContext}
              selectedLegs={selectedLegs}
              onLegSelected={setSelectedLegs}
              onComplete={handleStrategyComplete}
              onCancel={handleCancelStrategy}
            />
          </Grid>
        </Grid>
      )}

      {/* Normal Mode - Chain Table without leg selector */}
      {!strategyMode && !builderMode && chainData && (
        <ChainTable
          chainData={chainData}
          spotPrice={chainData.spot_price}
          atmStrike={chainData.atm_strike}
          onTrade={handleTrade}
          expiry={expiry}
          openPositions={openPositions}
        />
      )}

      {/* Builder Mode - Chain Table with Strategy Builder Panel */}
      {builderMode && !strategyMode && chainData && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={builderLegs.length > 0 ? 8 : 12}>
            <ChainTable
              chainData={chainData}
              spotPrice={chainData.spot_price}
              atmStrike={chainData.atm_strike}
              onTrade={handleBuilderLegSelected}
              strategyMode={true}
              builderMode={true}
              selectedLegs={builderLegs}
              expiry={expiry}
              openPositions={openPositions}
            />
          </Grid>
          {builderLegs.length > 0 && (
            <Grid item xs={12} md={4}>
              <StrategyBuilderPanel
                legs={builderLegs}
                underlying={underlying}
                spotPrice={chainData.spot_price}
                expiry={expiry}
                onUpdateLeg={handleUpdateBuilderLeg}
                onRemoveLeg={handleRemoveBuilderLeg}
                onClearAll={handleClearBuilderLegs}
                onExecute={handleExecuteBuilderStrategy}
                executing={executing}
              />
            </Grid>
          )}
        </Grid>
      )}

      {/* Strategy Review Dialog */}
      <StrategyReviewDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        strategyContext={strategyContext}
        selectedLegs={selectedLegs}
        spotPrice={chainData?.spot_price}
        expiry={expiry}
        underlying={underlying}
        onExecutionSuccess={handleExecutionSuccess}
        onExecutionError={handleExecutionError}
      />

      {/* Order Dialog */}
      <OrderDialog
        open={orderDialogOpen}
        onClose={() => setOrderDialogOpen(false)}
        option={selectedOption}
        onSuccess={handleOrderSuccess}
        onError={handleOrderError}
      />

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Add CSS animation keyframes */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Paper>
  );
};

export default OptionsChainPanel;
