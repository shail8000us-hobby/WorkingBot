/**
 * MMMStrikeSelector — Manual Strike Selection from Full Option Chain
 *
 * Displays the complete options chain in a calls-left / strike-center / puts-right
 * layout. User clicks a row to select the CE and PE strikes for MMM initialization.
 *
 * Features:
 *   - Full chain with bid/ask/mid/delta/OI for every strike
 *   - ITM/ATM/OTM color coding
 *   - Click-to-select CE and PE strikes
 *   - Validation feedback (warnings for ITM, low liquidity, wide spreads)
 *   - Summary panel with estimated premium
 *
 * Created: February 15, 2026
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Tooltip,
  IconButton,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Check as CheckIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

// =============================================================================
// Formatting helpers
// =============================================================================

const fmt$ = (v) => {
  if (v === null || v === undefined || v === 0) return '-';
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const fmtDelta = (d) => {
  if (d === null || d === undefined || d === 0) return '-';
  return Number(d).toFixed(3);
};

const fmtOI = (oi) => {
  if (!oi) return '-';
  if (oi >= 1000) return `${(oi / 1000).toFixed(1)}K`;
  return oi.toString();
};

const fmtSize = (s) => {
  if (!s) return '-';
  return Number(s).toFixed(0);
};

const fmtStrike = (v) =>
  typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v;

// Moneyness colors
const getMoneynessColor = (moneyness) => {
  switch (moneyness) {
    case 'ITM': return 'rgba(76, 175, 80, 0.12)';
    case 'ATM': return 'rgba(255, 193, 7, 0.2)';
    case 'OTM':
    default:   return 'transparent';
  }
};

// =============================================================================
// Column headers for calls and puts
// =============================================================================

const CALL_COLS = ['OI', 'BidSz', 'Bid', 'Mid', 'Ask', 'AskSz', 'Δ', 'IV'];
const PUT_COLS  = ['IV', 'Δ', 'BidSz', 'Bid', 'Mid', 'Ask', 'AskSz', 'OI'];

// =============================================================================
// OptionCell — renders one call or put data cell
// =============================================================================

const OptionCell = ({ option, field }) => {
  if (!option) return <TableCell align="right" sx={{ color: '#555', fontSize: 12 }}>-</TableCell>;

  let value;
  switch (field) {
    case 'OI':    value = fmtOI(option.oi); break;
    case 'BidSz': value = fmtSize(option.bid_size); break;
    case 'Bid':   value = fmt$(option.bid); break;
    case 'Mid':   value = fmt$(option.mid_price); break;
    case 'Ask':   value = fmt$(option.ask); break;
    case 'AskSz': value = fmtSize(option.ask_size); break;
    case 'Δ':     value = fmtDelta(option.delta); break;
    case 'IV':    value = option.iv ? `${(option.iv * 100).toFixed(0)}%` : '-'; break;
    default:      value = '-';
  }

  return (
    <TableCell
      align="right"
      sx={{
        fontSize: 12,
        fontFamily: 'monospace',
        py: 0.5,
        px: 0.75,
        whiteSpace: 'nowrap',
      }}
    >
      {value}
    </TableCell>
  );
};

// =============================================================================
// MMMStrikeSelector Component
// =============================================================================

const MMMStrikeSelector = ({
  expiry,
  lots = 1,
  onSelectionComplete,
  onSelectionChange,
}) => {
  const [chain, setChain] = useState([]);
  const [spotPrice, setSpotPrice] = useState(null);
  const [atmStrike, setAtmStrike] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Selected strikes
  const [selectedCeStrike, setSelectedCeStrike] = useState(null);
  const [selectedPeStrike, setSelectedPeStrike] = useState(null);

  // Validation
  const [validation, setValidation] = useState(null);
  const [validating, setValidating] = useState(false);

  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  // ---- Fetch chain data ----
  const fetchChain = useCallback(async () => {
    if (!expiry) return;
    setLoading(true);
    setError(null);

    try {
      const result = await mmmService.getChainData(expiry);
      if (!mounted.current) return;

      if (result.success) {
        setChain(result.chain || []);
        setSpotPrice(result.spot_price);
        setAtmStrike(result.atm_strike);
      } else {
        setError(result.error || 'Failed to load chain');
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [expiry]);

  useEffect(() => {
    fetchChain();
  }, [fetchChain]);

  // ---- Handle strike click ----
  const handleCallClick = useCallback((row) => {
    if (!row.call) return;
    setSelectedCeStrike((prev) => (prev === row.strike ? null : row.strike));
  }, []);

  const handlePutClick = useCallback((row) => {
    if (!row.put) return;
    setSelectedPeStrike((prev) => (prev === row.strike ? null : row.strike));
  }, []);

  // ---- Get selected option data ----
  const selectedCe = useMemo(
    () => chain.find((r) => r.strike === selectedCeStrike)?.call,
    [chain, selectedCeStrike]
  );

  const selectedPe = useMemo(
    () => chain.find((r) => r.strike === selectedPeStrike)?.put,
    [chain, selectedPeStrike]
  );

  // ---- Notify parent of selection changes ----
  useEffect(() => {
    onSelectionChange?.({
      ce: selectedCe ? { ...selectedCe, strike: selectedCeStrike } : null,
      pe: selectedPe ? { ...selectedPe, strike: selectedPeStrike } : null,
    });
  }, [selectedCe, selectedPe, selectedCeStrike, selectedPeStrike, onSelectionChange]);

  // ---- Validate selection ----
  const handleValidate = useCallback(async () => {
    if (!selectedCe || !selectedPe) return;
    setValidating(true);
    setValidation(null);

    try {
      const result = await mmmService.validateSelection({
        ce_symbol: selectedCe.symbol,
        pe_symbol: selectedPe.symbol,
        lots,
        expiry,
      });

      if (mounted.current) {
        setValidation(result);
      }
    } catch (err) {
      if (mounted.current) {
        setValidation({
          valid: false,
          errors: [err.details?.error || err.message],
          warnings: [],
        });
      }
    } finally {
      if (mounted.current) setValidating(false);
    }
  }, [selectedCe, selectedPe, lots, expiry]);

  // Auto-validate when both selected
  useEffect(() => {
    if (selectedCe && selectedPe) {
      handleValidate();
    } else {
      setValidation(null);
    }
  }, [selectedCe, selectedPe, handleValidate]);

  // ---- Confirm selection ----
  const handleConfirm = useCallback(() => {
    if (!selectedCe || !selectedPe || !validation?.valid) return;

    onSelectionComplete?.({
      ce_strike: selectedCeStrike,
      ce_premium: selectedCe.mid_price,
      ce_symbol: selectedCe.symbol,
      pe_strike: selectedPeStrike,
      pe_premium: selectedPe.mid_price,
      pe_symbol: selectedPe.symbol,
    });
  }, [selectedCe, selectedPe, selectedCeStrike, selectedPeStrike, validation, onSelectionComplete]);

  // ---- Estimated premium ----
  const estimatedPremium = useMemo(() => {
    if (!selectedCe || !selectedPe) return null;
    return ((selectedCe.mid_price || 0) + (selectedPe.mid_price || 0)) * lots * 0.001;
  }, [selectedCe, selectedPe, lots]);

  // ---- Loading state ----
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={32} />
        <Typography sx={{ ml: 2 }} color="text.secondary">Loading chain...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
        <Button size="small" onClick={fetchChain} sx={{ ml: 2 }}>Retry</Button>
      </Alert>
    );
  }

  if (!chain.length) {
    return (
      <Alert severity="info">No chain data available for this expiry.</Alert>
    );
  }

  // ---- Render ----
  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Select Strikes from Chain
        </Typography>
        <Chip
          label={`${chain.length} strikes`}
          size="small"
          variant="outlined"
        />
        {spotPrice && (
          <Chip
            label={`Spot: $${spotPrice.toLocaleString()}`}
            size="small"
            color="primary"
            variant="outlined"
          />
        )}
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Refresh chain data">
          <IconButton size="small" onClick={fetchChain}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Instructions */}
      <Alert severity="info" sx={{ mb: 1, py: 0 }}>
        Click a <strong>CALL</strong> row to select CE strike, click a <strong>PUT</strong> row to select PE strike.
      </Alert>

      {/* Chain Table */}
      <TableContainer
        component={Paper}
        sx={{
          maxHeight: 420,
          overflow: 'auto',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {/* Call columns */}
              {CALL_COLS.map((col) => (
                <TableCell
                  key={`call-${col}`}
                  align="right"
                  sx={{
                    fontSize: 11,
                    fontWeight: 700,
                    py: 0.5,
                    px: 0.75,
                    backgroundColor: 'rgba(76, 175, 80, 0.08)',
                    color: '#4caf50',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col}
                </TableCell>
              ))}

              {/* Strike column */}
              <TableCell
                align="center"
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  py: 0.5,
                  backgroundColor: 'rgba(33,150,243,0.1)',
                  color: '#2196f3',
                  minWidth: 80,
                }}
              >
                STRIKE
              </TableCell>

              {/* Put columns */}
              {PUT_COLS.map((col) => (
                <TableCell
                  key={`put-${col}`}
                  align="right"
                  sx={{
                    fontSize: 11,
                    fontWeight: 700,
                    py: 0.5,
                    px: 0.75,
                    backgroundColor: 'rgba(244, 67, 54, 0.08)',
                    color: '#f44336',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {chain.map((row) => {
              const isCeSelected = row.strike === selectedCeStrike;
              const isPeSelected = row.strike === selectedPeStrike;
              const isAtm = row.moneyness_call === 'ATM' || row.moneyness_put === 'ATM';

              return (
                <TableRow
                  key={row.strike}
                  sx={{
                    '&:hover': { backgroundColor: 'rgba(255,255,255,0.04)' },
                    borderBottom: isAtm ? '2px solid rgba(255,193,7,0.4)' : undefined,
                  }}
                >
                  {/* Call cells — clickable */}
                  {CALL_COLS.map((col) => (
                    <TableCell
                      key={`call-${col}-${row.strike}`}
                      align="right"
                      onClick={() => handleCallClick(row)}
                      sx={{
                        cursor: row.call ? 'pointer' : 'default',
                        backgroundColor: isCeSelected
                          ? 'rgba(76, 175, 80, 0.25)'
                          : getMoneynessColor(row.moneyness_call),
                        fontSize: 12,
                        fontFamily: 'monospace',
                        py: 0.5,
                        px: 0.75,
                        whiteSpace: 'nowrap',
                        borderLeft: isCeSelected && col === CALL_COLS[0]
                          ? '3px solid #4caf50' : undefined,
                        transition: 'background-color 0.15s',
                        '&:hover': row.call ? {
                          backgroundColor: 'rgba(76, 175, 80, 0.18)',
                        } : {},
                      }}
                    >
                      {(() => {
                        if (!row.call) return '-';
                        switch (col) {
                          case 'OI':    return fmtOI(row.call.oi);
                          case 'BidSz': return fmtSize(row.call.bid_size);
                          case 'Bid':   return fmt$(row.call.bid);
                          case 'Mid':   return fmt$(row.call.mid_price);
                          case 'Ask':   return fmt$(row.call.ask);
                          case 'AskSz': return fmtSize(row.call.ask_size);
                          case 'Δ':     return fmtDelta(row.call.delta);
                          case 'IV':    return row.call.iv ? `${(row.call.iv * 100).toFixed(0)}%` : '-';
                          default:      return '-';
                        }
                      })()}
                    </TableCell>
                  ))}

                  {/* Strike — center */}
                  <TableCell
                    align="center"
                    sx={{
                      fontWeight: 700,
                      fontSize: 12,
                      fontFamily: 'monospace',
                      backgroundColor: isAtm
                        ? 'rgba(255, 193, 7, 0.15)'
                        : 'rgba(33,150,243,0.04)',
                      borderLeft: '1px solid rgba(255,255,255,0.08)',
                      borderRight: '1px solid rgba(255,255,255,0.08)',
                      py: 0.5,
                    }}
                  >
                    {fmtStrike(row.strike)}
                    {isAtm && (
                      <Chip
                        label="ATM"
                        size="small"
                        sx={{ ml: 0.5, height: 16, fontSize: 9, fontWeight: 700 }}
                        color="warning"
                      />
                    )}
                  </TableCell>

                  {/* Put cells — clickable */}
                  {PUT_COLS.map((col) => (
                    <TableCell
                      key={`put-${col}-${row.strike}`}
                      align="right"
                      onClick={() => handlePutClick(row)}
                      sx={{
                        cursor: row.put ? 'pointer' : 'default',
                        backgroundColor: isPeSelected
                          ? 'rgba(244, 67, 54, 0.25)'
                          : getMoneynessColor(row.moneyness_put),
                        fontSize: 12,
                        fontFamily: 'monospace',
                        py: 0.5,
                        px: 0.75,
                        whiteSpace: 'nowrap',
                        borderRight: isPeSelected && col === PUT_COLS[PUT_COLS.length - 1]
                          ? '3px solid #f44336' : undefined,
                        transition: 'background-color 0.15s',
                        '&:hover': row.put ? {
                          backgroundColor: 'rgba(244, 67, 54, 0.18)',
                        } : {},
                      }}
                    >
                      {(() => {
                        if (!row.put) return '-';
                        switch (col) {
                          case 'OI':    return fmtOI(row.put.oi);
                          case 'BidSz': return fmtSize(row.put.bid_size);
                          case 'Bid':   return fmt$(row.put.bid);
                          case 'Mid':   return fmt$(row.put.mid_price);
                          case 'Ask':   return fmt$(row.put.ask);
                          case 'AskSz': return fmtSize(row.put.ask_size);
                          case 'Δ':     return fmtDelta(row.put.delta);
                          case 'IV':    return row.put.iv ? `${(row.put.iv * 100).toFixed(0)}%` : '-';
                          default:      return '-';
                        }
                      })()}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Selection Summary */}
      {(selectedCe || selectedPe) && (
        <Paper
          sx={{
            mt: 2,
            p: 2,
            border: '1px solid rgba(33,150,243,0.3)',
            backgroundColor: 'rgba(33,150,243,0.04)',
          }}
        >
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
            Selection Summary
          </Typography>

          <Box sx={{ display: 'flex', gap: 3, mb: 1 }}>
            {/* CE selection */}
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600, mb: 0.5 }}>
                CE (Call) {selectedCe ? '✓' : '— click a call row'}
              </Typography>
              {selectedCe && (
                <Box sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                  <Box>Strike: {fmtStrike(selectedCeStrike)}</Box>
                  <Box>Bid: {fmt$(selectedCe.bid)} | Ask: {fmt$(selectedCe.ask)}</Box>
                  <Box>Mid: {fmt$(selectedCe.mid_price)} | Δ: {fmtDelta(selectedCe.delta)}</Box>
                </Box>
              )}
            </Box>

            {/* PE selection */}
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ color: '#f44336', fontWeight: 600, mb: 0.5 }}>
                PE (Put) {selectedPe ? '✓' : '— click a put row'}
              </Typography>
              {selectedPe && (
                <Box sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                  <Box>Strike: {fmtStrike(selectedPeStrike)}</Box>
                  <Box>Bid: {fmt$(selectedPe.bid)} | Ask: {fmt$(selectedPe.ask)}</Box>
                  <Box>Mid: {fmt$(selectedPe.mid_price)} | Δ: {fmtDelta(selectedPe.delta)}</Box>
                </Box>
              )}
            </Box>

            {/* Premium estimate */}
            {estimatedPremium !== null && (
              <Box sx={{ minWidth: 120, textAlign: 'right' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                  Est. Premium ({lots} lots)
                </Typography>
                <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                  {fmt$(estimatedPremium)}
                </Typography>
              </Box>
            )}
          </Box>

          {/* Validation results */}
          {validating && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">Validating...</Typography>
            </Box>
          )}

          {validation && !validating && (
            <Box sx={{ mt: 1 }}>
              {validation.errors?.map((err, i) => (
                <Alert key={`err-${i}`} severity="error" sx={{ mb: 0.5, py: 0 }}>
                  {err}
                </Alert>
              ))}
              {validation.warnings?.map((warn, i) => (
                <Alert key={`warn-${i}`} severity="warning" sx={{ mb: 0.5, py: 0 }}>
                  {warn}
                </Alert>
              ))}
              {validation.valid && validation.errors?.length === 0 && (
                <Alert severity="success" sx={{ py: 0 }}>
                  Selection validated — ready to initialize
                </Alert>
              )}
            </Box>
          )}

          {/* Confirm button */}
          {selectedCe && selectedPe && validation?.valid && (
            <Button
              variant="contained"
              color="success"
              onClick={handleConfirm}
              startIcon={<CheckIcon />}
              sx={{ mt: 2 }}
              fullWidth
            >
              Confirm Selection
            </Button>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default MMMStrikeSelector;
