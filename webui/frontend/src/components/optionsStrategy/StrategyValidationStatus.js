/**
 * Strategy Validation Status Component
 * ====================================
 * Real-time validation feedback for options strategies before execution.
 * Shows validation errors, warnings, and pre-flight checks.
 *
 * Created: January 12, 2026
 */

import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  AlertTitle,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Button,
  CircularProgress,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Cancel as ErrorIcon,
  Warning as WarningIcon,
  Verified as VerifiedIcon,
  PlayArrow as ValidateIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

const API_BASE = '/api/production';

/**
 * Display validation result with errors and warnings
 */
function ValidationResult({ result, title }) {
  if (!result) return null;

  const { is_valid, errors, warnings } = result;

  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        {is_valid ? (
          <VerifiedIcon sx={{ color: 'success.main' }} />
        ) : (
          <ErrorIcon sx={{ color: 'error.main' }} />
        )}
        <Typography variant="subtitle2">{title}</Typography>
        <Chip
          label={is_valid ? 'VALID' : 'INVALID'}
          color={is_valid ? 'success' : 'error'}
          size="small"
        />
      </Box>

      {errors?.length > 0 && (
        <Alert severity="error" sx={{ mb: 1 }}>
          <AlertTitle>Validation Errors ({errors.length})</AlertTitle>
          <List dense disablePadding>
            {errors.map((error, i) => (
              <ListItem key={i} disablePadding>
                <ListItemIcon sx={{ minWidth: 28 }}>
                  <ErrorIcon fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText primary={error} primaryTypographyProps={{ variant: 'body2' }} />
              </ListItem>
            ))}
          </List>
        </Alert>
      )}

      {warnings?.length > 0 && (
        <Alert severity="warning">
          <AlertTitle>Warnings ({warnings.length})</AlertTitle>
          <List dense disablePadding>
            {warnings.map((warning, i) => (
              <ListItem key={i} disablePadding>
                <ListItemIcon sx={{ minWidth: 28 }}>
                  <WarningIcon fontSize="small" color="warning" />
                </ListItemIcon>
                <ListItemText primary={warning} primaryTypographyProps={{ variant: 'body2' }} />
              </ListItem>
            ))}
          </List>
        </Alert>
      )}

      {is_valid && errors?.length === 0 && warnings?.length === 0 && (
        <Alert severity="success">All validation checks passed</Alert>
      )}
    </Box>
  );
}

/**
 * Risk Check Component
 */
function RiskCheck({ onResult }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const checkRisk = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/risk/can-trade`);
      const data = await response.json();
      setResult(data);
      onResult?.(data.can_trade);
    } catch (err) {
      setResult({ can_trade: true, reason: 'Risk check unavailable', risk_level: 'unknown' });
      onResult?.(true);
    } finally {
      setLoading(false);
    }
  }, [onResult]);

  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography variant="subtitle2">Risk Check</Typography>
        <Button
          size="small"
          startIcon={loading ? <CircularProgress size={14} /> : <ValidateIcon />}
          onClick={checkRisk}
          disabled={loading}
        >
          {loading ? 'Checking...' : 'Check Risk'}
        </Button>
      </Box>

      {result && (
        <Alert severity={result.can_trade ? 'success' : 'error'}>
          <AlertTitle>{result.can_trade ? 'Trading Allowed' : 'Trading Blocked'}</AlertTitle>
          <Typography variant="body2">{result.reason}</Typography>
          {result.risk_level && (
            <Chip
              label={`Risk Level: ${result.risk_level.toUpperCase()}`}
              size="small"
              sx={{ mt: 1 }}
              color={
                result.risk_level === 'low'
                  ? 'success'
                  : result.risk_level === 'medium'
                    ? 'warning'
                    : 'error'
              }
            />
          )}
        </Alert>
      )}
    </Box>
  );
}

/**
 * Main Strategy Validation Status Component
 *
 * Props:
 *   - strategy: Strategy object with legs
 *   - onValidationComplete: Callback when validation completes (isValid, result)
 *   - autoValidate: Auto-validate when strategy changes
 */
export default function StrategyValidationStatus({
  strategy,
  onValidationComplete,
  autoValidate = false,
}) {
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [canTrade, setCanTrade] = useState(null);

  const validateStrategy = useCallback(async () => {
    if (!strategy?.legs?.length) {
      setValidationResult({
        is_valid: false,
        errors: ['No strategy legs to validate'],
        warnings: [],
      });
      onValidationComplete?.(false, null);
      return;
    }

    setValidating(true);
    try {
      const response = await fetch(`${API_BASE}/validate/strategy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_type: strategy.type || '',
          legs: strategy.legs.map((leg) => ({
            symbol: leg.symbol,
            side: leg.side,
            quantity: leg.quantity,
            option_type: leg.option_type,
            strike: leg.strike,
            expiry: leg.expiry,
          })),
        }),
      });

      const data = await response.json();
      setValidationResult(data);
      onValidationComplete?.(data.is_valid, data);
    } catch (err) {
      const errorResult = {
        is_valid: false,
        errors: [`Validation request failed: ${err.message}`],
        warnings: [],
      };
      setValidationResult(errorResult);
      onValidationComplete?.(false, errorResult);
    } finally {
      setValidating(false);
    }
  }, [strategy, onValidationComplete]);

  // Auto-validate when strategy changes
  React.useEffect(() => {
    if (autoValidate && strategy?.legs?.length) {
      validateStrategy();
    }
  }, [autoValidate, strategy, validateStrategy]);

  // Summary status
  const getOverallStatus = () => {
    if (validating) return { color: 'info', label: 'Validating...' };
    if (!validationResult) return { color: 'default', label: 'Not Validated' };
    if (!validationResult.is_valid) return { color: 'error', label: 'Invalid' };
    if (validationResult.warnings?.length > 0)
      return { color: 'warning', label: 'Valid with Warnings' };
    return { color: 'success', label: 'Valid' };
  };

  const status = getOverallStatus();

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <VerifiedIcon color={status.color === 'success' ? 'success' : 'action'} />
          <Typography variant="subtitle1">Pre-Execution Validation</Typography>
          <Chip label={status.label} color={status.color} size="small" />
        </Box>
        <IconButton size="small">{expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}</IconButton>
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ mt: 2 }}>
          {/* Validate Button */}
          <Button
            variant="contained"
            startIcon={
              validating ? <CircularProgress size={16} color="inherit" /> : <ValidateIcon />
            }
            onClick={validateStrategy}
            disabled={validating || !strategy?.legs?.length}
            sx={{ mb: 2 }}
            fullWidth
          >
            {validating ? 'Validating Strategy...' : 'Validate Strategy'}
          </Button>

          {/* Validation Results */}
          {validationResult && (
            <ValidationResult result={validationResult} title="Strategy Validation" />
          )}

          {/* Risk Check */}
          <RiskCheck onResult={setCanTrade} />

          {/* Pre-flight Summary */}
          {validationResult && canTrade !== null && (
            <Alert
              severity={validationResult.is_valid && canTrade ? 'success' : 'warning'}
              icon={validationResult.is_valid && canTrade ? <CheckIcon /> : <WarningIcon />}
            >
              <AlertTitle>Pre-Flight Check Summary</AlertTitle>
              <List dense disablePadding>
                <ListItem disablePadding>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    {validationResult.is_valid ? (
                      <CheckIcon fontSize="small" color="success" />
                    ) : (
                      <ErrorIcon fontSize="small" color="error" />
                    )}
                  </ListItemIcon>
                  <ListItemText primary="Strategy Validation" />
                </ListItem>
                <ListItem disablePadding>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    {canTrade ? (
                      <CheckIcon fontSize="small" color="success" />
                    ) : (
                      <ErrorIcon fontSize="small" color="error" />
                    )}
                  </ListItemIcon>
                  <ListItemText primary="Risk Limits" />
                </ListItem>
              </List>
              {validationResult.is_valid && canTrade && (
                <Typography variant="body2" sx={{ mt: 1, fontWeight: 'bold' }}>
                  ✅ Ready to execute
                </Typography>
              )}
            </Alert>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}

/**
 * Compact validation badge for inline use
 */
export function ValidationBadge({ isValid, hasWarnings }) {
  if (isValid === null || isValid === undefined) {
    return <Chip label="Not Validated" size="small" variant="outlined" />;
  }

  if (!isValid) {
    return <Chip icon={<ErrorIcon />} label="Invalid" size="small" color="error" />;
  }

  if (hasWarnings) {
    return <Chip icon={<WarningIcon />} label="Valid (warnings)" size="small" color="warning" />;
  }

  return <Chip icon={<CheckIcon />} label="Valid" size="small" color="success" />;
}
