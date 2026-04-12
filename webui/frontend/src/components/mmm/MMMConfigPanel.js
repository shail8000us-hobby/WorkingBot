/**
 * MMM Config Panel — Money Mind & Method
 *
 * Phase 2 Enhanced: Initialization UI with four modes.
 *
 * Four modes:
 *   Mode A (Fresh):  Auto-find strikes by desired premium → preview → confirm → execute
 *   Mode B (Import): Enter existing position details → initialize
 *   Mode C (Manual): Browse full chain → click to select CE & PE → validate → execute
 *   Mode D (Adopt):  Scan exchange for open positions → select → assign roles → adopt
 *
 * Smart Execution:
 *   After strike selection (Mode A or C), orders are placed at mid-price
 *   with 60-second fill wait + auto-reprice cycle via mmm_executor.
 *
 * Sections from MONEY_POWER_CALCULATION_LOGIC.md:
 *   §3 Initialization (Mode A auto-find, Mode B import)
 *   §15 BTC-Specific (strike intervals, liquidity, premium format)
 *   §19 Parameters
 *
 * Created: February 15, 2026
 * Updated: February 15, 2026 — Added Manual mode + Smart Execution
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  Tooltip,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  Search as SearchIcon,
  Check as CheckIcon,
  Warning as WarningIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
  Upload as ImportIcon,
  TouchApp as ManualIcon,
  PlayArrow as ExecuteIcon,
  GetApp as AdoptIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';
import MMMStrikeSelector from './MMMStrikeSelector';
import MMMAdoptPanel from './MMMAdoptPanel';

// =============================================================================
// Helpers
// =============================================================================

/**
 * Format expiry from DDMMYYYY → human-readable "DD MMM YYYY"
 */
const formatExpiry = (ddmmyyyy) => {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dd = ddmmyyyy.slice(0, 2);
  const mm = parseInt(ddmmyyyy.slice(2, 4), 10) - 1;
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${dd} ${months[mm] || '???'} ${yyyy}`;
};

/**
 * Format strike for display (no decimals for BTC)
 */
const fmtStrike = (v) =>
  typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v;

/**
 * Format premium ($)
 */
const fmtPrem = (v) =>
  typeof v === 'number' ? `$${v.toFixed(2)}` : '—';

// =============================================================================
// StrikePreviewTable — shows found strikes + alternatives
// =============================================================================

const StrikePreviewTable = ({ label, best, alternatives, color, onSelect }) => {
  const [showAlts, setShowAlts] = useState(false);
  if (!best) return null;

  const rows = [
    { ...best, isBest: true },
    ...(alternatives || []).map((a) => ({ ...a, isBest: false })),
  ];

  return (
    <Paper
      sx={{
        border: `1px solid ${color}44`,
        backgroundColor: `${color}06`,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color }}>
          {label}
        </Typography>
        <Chip
          label={`Strike: ${fmtStrike(best.strike)}`}
          size="small"
          sx={{ fontWeight: 600 }}
        />
        <Chip
          label={`Prem: ${fmtPrem(best.premium)}`}
          size="small"
          variant="outlined"
        />
        <Chip
          label={`Δ ${best.delta?.toFixed(3) || '—'}`}
          size="small"
          variant="outlined"
        />
        {best.diff_from_desired > 0 && (
          <Chip
            label={`Diff: ${fmtPrem(best.diff_from_desired)}`}
            size="small"
            color={best.diff_from_desired > 20 ? 'warning' : 'default'}
            variant="outlined"
          />
        )}
        {alternatives?.length > 0 && (
          <IconButton
            size="small"
            onClick={() => setShowAlts(!showAlts)}
            sx={{ ml: 'auto' }}
          >
            {showAlts ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        )}
      </Box>

      <Collapse in={showAlts}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Strike</TableCell>
                <TableCell align="right">Premium</TableCell>
                <TableCell align="right">Bid</TableCell>
                <TableCell align="right">Ask</TableCell>
                <TableCell align="right">Delta</TableCell>
                <TableCell align="right">OI</TableCell>
                <TableCell align="right">Diff</TableCell>
                <TableCell align="center"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row, i) => (
                <TableRow
                  key={row.strike}
                  sx={{
                    backgroundColor: row.isBest ? `${color}12` : 'transparent',
                    '&:hover': { backgroundColor: `${color}08` },
                  }}
                >
                  <TableCell sx={{ fontWeight: row.isBest ? 700 : 400, fontFamily: 'monospace' }}>
                    {fmtStrike(row.strike)}
                    {row.isBest && (
                      <Chip label="BEST" size="small" sx={{ ml: 1, height: 18, fontSize: 10 }} color="primary" />
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{fmtPrem(row.premium)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{fmtPrem(row.bid)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{fmtPrem(row.ask)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{row.delta?.toFixed(3) || '—'}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{row.oi ?? '—'}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>{fmtPrem(row.diff_from_desired)}</TableCell>
                  <TableCell align="center">
                    {!row.isBest && onSelect && (
                      <Button size="small" variant="text" onClick={() => onSelect(row)}>
                        Use
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Collapse>
    </Paper>
  );
};

// =============================================================================
// MMMConfigPanel
// =============================================================================

const MMMConfigPanel = ({ sessionId, sessionStatus, initialMode, onInitialized, sessionExpiry, isStraddle }) => {
  // ----- State -----
  const [mode, setMode] = useState(initialMode || 'fresh'); // 'fresh' | 'import' | 'manual' | 'adopt'
  const [expiries, setExpiries] = useState([]);
  // FIX: Initialize selectedExpiry from session's creation expiry to prevent
  // accidentally using a different expiry during init-fresh/init-import.
  // Previously this was '' which auto-selected the first dropdown item (today's 0DTE),
  // causing sessions created for tomorrow's expiry to trade on today's contracts.
  const [selectedExpiry, setSelectedExpiry] = useState(sessionExpiry || '');
  const [spotPrice, setSpotPrice] = useState(null);
  const [desiredCePremium, setDesiredCePremium] = useState(100);
  const [desiredPePremium, setDesiredPePremium] = useState(100);
  const [lots, setLots] = useState(10);

  // Preview state
  const [preview, setPreview] = useState(null);
  const [selectedCe, setSelectedCe] = useState(null);
  const [selectedPe, setSelectedPe] = useState(null);

  // Manual select state
  const [manualSelection, setManualSelection] = useState(null);

  // Import state
  const [importData, setImportData] = useState({
    ce_strike: '', ce_fill_price: '', ce_symbol: '',
    pe_strike: '', pe_fill_price: '', pe_symbol: '',
  });

  // Smart execution state
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [expiryLoading, setExpiryLoading] = useState(false);

  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  // M-27 fix: Regenerate import symbols when selectedExpiry changes
  useEffect(() => {
    if (!selectedExpiry) return;
    setImportData(prev => {
      const next = { ...prev };
      const symbolExpiry = selectedExpiry.length === 8
        ? selectedExpiry.slice(0, 4) + selectedExpiry.slice(6) : selectedExpiry;
      if (prev.ce_strike) {
        next.ce_symbol = `C-BTC-${Math.round(parseFloat(prev.ce_strike))}-${symbolExpiry}`;
      }
      if (prev.pe_strike) {
        next.pe_symbol = `P-BTC-${Math.round(parseFloat(prev.pe_strike))}-${symbolExpiry}`;
      }
      return next;
    });
  }, [selectedExpiry]);

  // ----- Load expiries on mount -----
  const fetchExpiries = useCallback(async () => {
    setExpiryLoading(true);
    try {
      const result = await mmmService.getExpiries();
      if (result.success && mounted.current) {
        setExpiries(result.expiries || []);
        // M-25 fix: Only auto-select if no expiry is currently selected
        if (result.expiries?.length > 0) {
          setSelectedExpiry(prev => {
            if (prev) return prev;  // Don't override existing selection
            if (sessionExpiry && result.expiries.includes(sessionExpiry)) {
              return sessionExpiry;
            }
            return result.expiries[0];
          });
        }
      }
    } catch (err) {
      console.error('Failed to fetch expiries:', err);
    } finally {
      if (mounted.current) setExpiryLoading(false);
    }
  }, [sessionExpiry]);  // M-25 fix: depend on sessionExpiry, not selectedExpiry

  const fetchSpotPrice = useCallback(async () => {
    try {
      const result = await mmmService.getSpotPrice();
      if (result.success && mounted.current) {
        setSpotPrice(result.spot_price);
      }
    } catch (err) {
      console.error('Failed to fetch spot price:', err);
    }
  }, []);

  useEffect(() => {
    fetchExpiries();
    fetchSpotPrice();
  }, [fetchExpiries, fetchSpotPrice]);

  // ----- Preview Strikes (Mode A) -----
  const handlePreviewStrikes = useCallback(async () => {
    if (!selectedExpiry) {
      setError('Please select an expiry date');
      return;
    }
    if (desiredCePremium <= 0 || desiredPePremium <= 0) {
      setError('Premium values must be positive');
      return;
    }
    // L-9 fix: Warn if user already manually selected an alternative strike
    if (selectedCe && preview && selectedCe.strike !== preview.ce?.strike) {
      if (!window.confirm('You have a manually selected CE strike. Re-preview will replace it. Continue?')) {
        return;
      }
    }

    setPreviewLoading(true);
    setError(null);
    setPreview(null);
    setSelectedCe(null);
    setSelectedPe(null);

    try {
      const result = await mmmService.previewStrikes({
        desired_ce_premium: desiredCePremium,
        desired_pe_premium: desiredPePremium,
        expiry: selectedExpiry,
      });

      if (mounted.current) {
        if (result.success) {
          setPreview(result);
          // M-26 fix: null guard on ce/pe before setting
          if (result.ce && result.pe) {
            setSelectedCe(result.ce);
            setSelectedPe(result.pe);
          } else {
            setError('Preview data incomplete — missing CE or PE strike');
          }
          setSpotPrice(result.spot_price);
        } else {
          setError(result.error || 'Failed to find strikes');
        }
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setPreviewLoading(false);
    }
  }, [selectedExpiry, desiredCePremium, desiredPePremium]);

  // ----- ATM Straddle Preview (STRADDLE_WITH_ADJUSTMENT preset only) -----
  const handlePreviewAtmStraddle = useCallback(async () => {
    if (!selectedExpiry) {
      setError('Please select an expiry date');
      return;
    }
    setPreviewLoading(true);
    setError(null);
    setPreview(null);
    setSelectedCe(null);
    setSelectedPe(null);

    try {
      const result = await mmmService.previewAtmStraddle({ expiry: selectedExpiry });
      if (mounted.current) {
        if (result.success) {
          setPreview(result);
          setSelectedCe(result.ce);
          setSelectedPe(result.pe);
          setSpotPrice(result.spot_price);
        } else {
          setError(result.error || 'Failed to find ATM strike');
        }
      }
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      if (mounted.current) setPreviewLoading(false);
    }
  }, [selectedExpiry]);

  // ----- Initialize Session (Mode A: Fresh) -----
  const handleInitFresh = useCallback(async () => {
    if (!selectedCe || !selectedPe) {
      setError('No strikes selected. Run preview first.');
      return;
    }
    if (!sessionId) {
      setError('No session ID');
      return;
    }
    // SAFETY: Catch expiry mismatch before sending to backend
    if (sessionExpiry && selectedExpiry !== sessionExpiry) {
      setError(
        `Expiry mismatch! Session was created for ${sessionExpiry} but you selected ${selectedExpiry}. ` +
        `This would trade on the wrong contracts. Please create a new session for ${selectedExpiry} instead.`
      );
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await mmmService.initSessionFresh(sessionId, {
        ce_strike: selectedCe.strike,
        ce_premium: selectedCe.premium,
        ce_symbol: selectedCe.symbol,
        pe_strike: selectedPe.strike,
        pe_premium: selectedPe.premium,
        pe_symbol: selectedPe.symbol,
        lots,
        expiry: selectedExpiry,
      });

      if (mounted.current) {
        if (result.success) {
          setSuccess('Session initialized — starting strategy...');
          setPreview(null);
          onInitialized?.(result);

          // Auto-start the session immediately after init
          try {
            const startResult = await mmmService.startSession(sessionId);
            if (mounted.current) {
              if (startResult.success) {
                setSuccess(`Strategy started! ${startResult.status === 'STARTING' ? 'Placing entry orders...' : 'Monitor active.'}`);
              } else {
                setError(`Initialized but failed to start: ${startResult.error}`);
              }
            }
          } catch (startErr) {
            if (mounted.current) {
              setError(`Initialized but start failed: ${startErr.details?.error || startErr.message}`);
            }
          }
        } else {
          setError(result.error || 'Failed to initialize');
        }
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [selectedCe, selectedPe, sessionId, lots, selectedExpiry, onInitialized]);

  // ----- Initialize Session (Mode B: Import) -----
  const handleInitImport = useCallback(async () => {
    if (!sessionId) {
      setError('No session ID');
      return;
    }

    const { ce_strike, ce_fill_price, ce_symbol, pe_strike, pe_fill_price, pe_symbol } = importData;

    if (!ce_strike || !ce_fill_price || !ce_symbol || !pe_strike || !pe_fill_price || !pe_symbol) {
      setError('All import fields are required');
      return;
    }
    // M-28 fix: Validate numeric fields before sending to backend
    if (isNaN(parseFloat(ce_strike)) || isNaN(parseFloat(ce_fill_price)) ||
        isNaN(parseFloat(pe_strike)) || isNaN(parseFloat(pe_fill_price))) {
      setError('Strike and fill price fields must be valid numbers');
      return;
    }
    if (!selectedExpiry) {
      setError('Please select an expiry date');
      return;
    }
    // SAFETY: Catch expiry mismatch before sending to backend
    if (sessionExpiry && selectedExpiry !== sessionExpiry) {
      setError(
        `Expiry mismatch! Session was created for ${sessionExpiry} but you selected ${selectedExpiry}. ` +
        `This would trade on the wrong contracts. Please create a new session for ${selectedExpiry} instead.`
      );
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await mmmService.initSessionImport(sessionId, {
        ce_strike: parseFloat(ce_strike),
        ce_fill_price: parseFloat(ce_fill_price),
        ce_symbol,
        pe_strike: parseFloat(pe_strike),
        pe_fill_price: parseFloat(pe_fill_price),
        pe_symbol,
        lots,
        expiry: selectedExpiry,
      });

      if (mounted.current) {
        if (result.success) {
          setSuccess('Position imported — starting monitor...');
          onInitialized?.(result);

          // Auto-start the session immediately after import
          try {
            const startResult = await mmmService.startSession(sessionId);
            if (mounted.current) {
              if (startResult.success) {
                setSuccess('Strategy started! Monitor active.');
              } else {
                setError(`Imported but failed to start: ${startResult.error}`);
              }
            }
          } catch (startErr) {
            if (mounted.current) {
              setError(`Imported but start failed: ${startErr.details?.error || startErr.message}`);
            }
          }
        } else {
          setError(result.error || 'Failed to initialize');
        }
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [sessionId, importData, lots, selectedExpiry, onInitialized]);

  // ----- Manual selection complete (from MMMStrikeSelector) -----
  const handleManualSelectionComplete = useCallback(async (selection) => {
    if (!sessionId) {
      setError('No session ID');
      return;
    }
    // SAFETY: Catch expiry mismatch before sending to backend
    if (sessionExpiry && selectedExpiry !== sessionExpiry) {
      setError(
        `Expiry mismatch! Session was created for ${sessionExpiry} but you selected ${selectedExpiry}. ` +
        `This would trade on the wrong contracts. Please create a new session for ${selectedExpiry} instead.`
      );
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // First: initialize session state with the manually selected strikes
      const result = await mmmService.initSessionFresh(sessionId, {
        ce_strike: selection.ce_strike,
        ce_premium: selection.ce_premium,
        ce_symbol: selection.ce_symbol,
        pe_strike: selection.pe_strike,
        pe_premium: selection.pe_premium,
        pe_symbol: selection.pe_symbol,
        lots,
        expiry: selectedExpiry,
      });

      if (mounted.current) {
        if (result.success) {
          setSuccess('Strikes confirmed — starting strategy...');
          onInitialized?.(result);

          // Auto-start the session immediately after manual selection
          try {
            const startResult = await mmmService.startSession(sessionId);
            if (mounted.current) {
              if (startResult.success) {
                setSuccess(`Strategy started! ${startResult.status === 'STARTING' ? 'Placing entry orders...' : 'Monitor active.'}`);
              } else {
                setError(`Initialized but failed to start: ${startResult.error}`);
              }
            }
          } catch (startErr) {
            if (mounted.current) {
              setError(`Initialized but start failed: ${startErr.details?.error || startErr.message}`);
            }
          }
        } else {
          setError(result.error || 'Failed to initialize');
        }
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [sessionId, lots, selectedExpiry, onInitialized]);

  // ----- Handle manual selection change (for display) -----
  const handleManualSelectionChange = useCallback((sel) => {
    setManualSelection(sel);
  }, []);

  // ----- Smart Execution: place orders at mid-price -----
  const handleExecuteEntry = useCallback(async () => {
    if (!sessionId) {
      setError('No session ID');
      return;
    }

    setExecuting(true);
    setError(null);
    setExecutionResult(null);

    try {
      const result = await mmmService.executeEntry(sessionId, mode);

      if (mounted.current) {
        setExecutionResult(result);
        if (result.success) {
          const ceResult = result.ce || {};
          const peResult = result.pe || {};
          setSuccess(
            `Entry executed! CE filled: ${ceResult.filled ? 'Yes' : 'No'}, ` +
            `PE filled: ${peResult.filled ? 'Yes' : 'No'}`
          );
          onInitialized?.(result);
        } else {
          setError(result.error || 'Execution failed');
        }
      }
    } catch (err) {
      if (mounted.current) {
        setError(err.details?.error || err.message);
      }
    } finally {
      if (mounted.current) setExecuting(false);
    }
  }, [sessionId, mode, onInitialized]);

  // ----- Select alternative strike -----
  const handleSelectAlternativeCe = useCallback((alt) => {
    setSelectedCe(alt);
  }, []);

  const handleSelectAlternativePe = useCallback((alt) => {
    setSelectedPe(alt);
  }, []);

  // Only show config panel for created/stopped sessions
  // Backend uses uppercase: IDLE, STOPPED. Dashboard may pass either.
  const normalizedStatus = (sessionStatus || '').toUpperCase();
  const canInitialize = ['CREATED', 'IDLE', 'STOPPED'].includes(normalizedStatus);
  if (!canInitialize) {
    return null;
  }

  // ----- Import field handler -----
  // Auto-generate symbols when strike changes and expiry is set
  const generateSymbol = (type, strike, expiry) => {
    if (!strike || !expiry) return '';
    // Expiry is DDMMYYYY from backend — symbol uses DDMMYY (first4 + last2)
    const symbolExpiry = expiry.length === 8
      ? expiry.slice(0, 4) + expiry.slice(6)
      : expiry; // fallback
    const prefix = type === 'ce' ? 'C' : 'P';
    return `${prefix}-BTC-${Math.round(parseFloat(strike))}-${symbolExpiry}`;
  };

  const handleImportField = (field) => (e) => {
    const value = e.target.value;
    setImportData((prev) => {
      const next = { ...prev, [field]: value };
      // Auto-generate symbol when strike changes
      if (field === 'ce_strike' && selectedExpiry) {
        next.ce_symbol = generateSymbol('ce', value, selectedExpiry);
      } else if (field === 'pe_strike' && selectedExpiry) {
        next.pe_symbol = generateSymbol('pe', value, selectedExpiry);
      }
      return next;
    });
  };

  // ----- Render -----
  return (
    <Paper sx={{ p: 3, mb: 2 }}>
      <Typography variant="h6" sx={{ mb: 2, fontWeight: 700 }}>
        Initialize Session
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Spot price banner */}
      {spotPrice && (
        <Box
          sx={{
            display: 'flex', alignItems: 'center', gap: 2, mb: 2,
            p: 1.5, borderRadius: 1,
            backgroundColor: 'rgba(33,150,243,0.06)',
            border: '1px solid rgba(33,150,243,0.2)',
          }}
        >
          <Typography variant="body2" color="text.secondary">BTC Spot:</Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
            ${spotPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}
          </Typography>
          <Tooltip title="Refresh spot price">
            <IconButton size="small" onClick={fetchSpotPrice}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Mode toggle */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Button
          variant={mode === 'fresh' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setMode('fresh')}
          startIcon={<SearchIcon />}
        >
          Auto-Find
        </Button>
        <Button
          variant={mode === 'manual' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setMode('manual')}
          startIcon={<ManualIcon />}
        >
          Manual Select
        </Button>
        <Button
          variant={mode === 'import' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setMode('import')}
          startIcon={<ImportIcon />}
        >
          Import Existing
        </Button>
        <Button
          variant={mode === 'adopt' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setMode('adopt')}
          startIcon={<AdoptIcon />}
          sx={mode === 'adopt' ? {
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderColor: 'transparent',
          } : {}}
        >
          Adopt from Exchange
        </Button>
      </Box>

      {/* Shared: Expiry + Lots */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6}>
          <FormControl fullWidth size="small">
            <InputLabel>Expiry</InputLabel>
            <Select
              value={selectedExpiry}
              label={sessionExpiry ? `Expiry (locked to session)` : 'Expiry'}
              disabled={!!sessionExpiry || expiryLoading}  // L-8 fix: lock dropdown when session expiry is set
              onChange={(e) => {
                const newExpiry = e.target.value;
                setSelectedExpiry(newExpiry);
                // Auto-update import symbols when expiry changes
                if (mode === 'import') {
                  setImportData((prev) => ({
                    ...prev,
                    ce_symbol: prev.ce_strike ? generateSymbol('ce', prev.ce_strike, newExpiry) : prev.ce_symbol,
                    pe_symbol: prev.pe_strike ? generateSymbol('pe', prev.pe_strike, newExpiry) : prev.pe_symbol,
                  }));
                }
              }}
            >
              {expiries.map((exp) => (
                <MenuItem key={exp} value={exp}>
                  {formatExpiry(exp)} ({exp})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={3}>
          <TextField
            label="Lots per side"
            type="number"
            value={lots}
            onChange={(e) => setLots(Math.max(1, parseInt(e.target.value) || 1))}
            fullWidth
            size="small"
            inputProps={{ min: 1 }}
          />
        </Grid>
        <Grid item xs={3}>
          <Tooltip title="Refresh expiry list">
            <Button
              variant="outlined"
              onClick={fetchExpiries}
              disabled={expiryLoading}
              fullWidth
              sx={{ height: '100%' }}
              startIcon={expiryLoading ? <CircularProgress size={16} /> : <RefreshIcon />}
            >
              Refresh
            </Button>
          </Tooltip>
        </Grid>
      </Grid>

      <Divider sx={{ mb: 3 }} />

      {/* ================================================================= */}
      {/* Mode A: Fresh — Auto-find strikes                                 */}
      {/* ================================================================= */}
      {mode === 'fresh' && (
        <>
          {/* Strike selection — ATM for straddle, premium-targeted for strangle */}
          {isStraddle ? (
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={10}>
                <Box sx={{ p: 1.5, borderRadius: 1, border: '1px solid rgba(255,255,255,0.12)', backgroundColor: 'rgba(255,255,255,0.04)' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.3 }}>
                    Strike Selection — Short Straddle
                  </Typography>
                  <Typography variant="body2">
                    ATM strike auto-selected (closest to spot). CE and PE sold at the same strike.
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={2}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handlePreviewAtmStraddle}
                  disabled={previewLoading || !selectedExpiry}
                  fullWidth
                  sx={{ height: '100%' }}
                  startIcon={previewLoading ? <CircularProgress size={16} /> : <SearchIcon />}
                >
                  {previewLoading ? 'Scanning...' : 'Find ATM'}
                </Button>
              </Grid>
            </Grid>
          ) : (
            <>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Desired Premiums (per lot)
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={5}>
                  <TextField
                    label="CE Premium ($)"
                    type="number"
                    value={desiredCePremium}
                    onChange={(e) => setDesiredCePremium(parseFloat(e.target.value) || 0)}
                    fullWidth
                    size="small"
                    inputProps={{ min: 0.01, step: 10 }}
                  />
                </Grid>
                <Grid item xs={5}>
                  <TextField
                    label="PE Premium ($)"
                    type="number"
                    value={desiredPePremium}
                    onChange={(e) => setDesiredPePremium(parseFloat(e.target.value) || 0)}
                    fullWidth
                    size="small"
                    inputProps={{ min: 0.01, step: 10 }}
                  />
                </Grid>
                <Grid item xs={2}>
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handlePreviewStrikes}
                    disabled={previewLoading || !selectedExpiry}
                    fullWidth
                    sx={{ height: '100%' }}
                    startIcon={previewLoading ? <CircularProgress size={16} /> : <SearchIcon />}
                  >
                    {previewLoading ? 'Scanning...' : 'Find'}
                  </Button>
                </Grid>
              </Grid>
            </>
          )}

          {/* Preview results */}
          {preview && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {isStraddle ? `ATM Strike — ${preview.atm_strike?.toLocaleString() ?? ''} (both legs)` : 'Found Strikes'}
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <StrikePreviewTable
                  label="CE (Call)"
                  best={selectedCe}
                  alternatives={isStraddle ? [] : preview.alternatives?.ce}
                  color="#4caf50"
                  onSelect={isStraddle ? undefined : handleSelectAlternativeCe}
                />
                <StrikePreviewTable
                  label="PE (Put)"
                  best={selectedPe}
                  alternatives={isStraddle ? [] : preview.alternatives?.pe}
                  color="#f44336"
                  onSelect={isStraddle ? undefined : handleSelectAlternativePe}
                />
              </Box>

              {/* Summary before confirm */}
              {selectedCe && selectedPe && (
                <Paper
                  sx={{
                    mt: 2, p: 2,
                    border: '1px solid rgba(33,150,243,0.3)',
                    backgroundColor: 'rgba(33,150,243,0.04)',
                  }}
                >
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Entry Summary
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        CE: {fmtStrike(selectedCe.strike)} @ {fmtPrem(selectedCe.premium)} × {lots} lots
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        PE: {fmtStrike(selectedPe.strike)} @ {fmtPrem(selectedPe.premium)} × {lots} lots
                      </Typography>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="body1" sx={{ fontWeight: 700, mt: 0.5 }}>
                        Total Premium: {fmtPrem(
                          ((selectedCe.premium * lots) + (selectedPe.premium * lots)) * 0.001
                        )}
                      </Typography>
                    </Grid>
                  </Grid>

                  <Button
                    variant="contained"
                    color="success"
                    onClick={handleInitFresh}
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={16} /> : <CheckIcon />}
                    sx={{ mt: 2 }}
                    fullWidth
                  >
                    {loading ? 'Initializing...' : 'Confirm & Initialize'}
                  </Button>
                </Paper>
              )}
            </Box>
          )}
        </>
      )}

      {/* ================================================================= */}
      {/* Mode C: Manual — Browse chain & click to select strikes          */}
      {/* ================================================================= */}
      {mode === 'manual' && selectedExpiry && (
        <MMMStrikeSelector
          expiry={selectedExpiry}
          lots={lots}
          onSelectionComplete={handleManualSelectionComplete}
          onSelectionChange={handleManualSelectionChange}
        />
      )}
      {mode === 'manual' && !selectedExpiry && (
        <Alert severity="info">Select an expiry date above to browse the chain.</Alert>
      )}

      {/* ================================================================= */}
      {/* Mode B: Import existing positions                                 */}
      {/* ================================================================= */}
      {mode === 'import' && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            CE Side (Call)
          </Typography>
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={4}>
              <TextField
                label="CE Strike"
                type="number"
                value={importData.ce_strike}
                onChange={handleImportField('ce_strike')}
                fullWidth
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="CE Fill Price"
                type="number"
                value={importData.ce_fill_price}
                onChange={handleImportField('ce_fill_price')}
                fullWidth
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="CE Symbol"
                placeholder="C-BTC-100000-150226"
                value={importData.ce_symbol}
                onChange={handleImportField('ce_symbol')}
                fullWidth
                size="small"
                helperText={importData.ce_strike && selectedExpiry ? 'Auto-generated from strike + expiry' : ''}
              />
            </Grid>
          </Grid>

          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            PE Side (Put)
          </Typography>
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={4}>
              <TextField
                label="PE Strike"
                type="number"
                value={importData.pe_strike}
                onChange={handleImportField('pe_strike')}
                fullWidth
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="PE Fill Price"
                type="number"
                value={importData.pe_fill_price}
                onChange={handleImportField('pe_fill_price')}
                fullWidth
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                label="PE Symbol"
                placeholder="P-BTC-96000-150226"
                value={importData.pe_symbol}
                onChange={handleImportField('pe_symbol')}
                fullWidth
                size="small"
                helperText={importData.pe_strike && selectedExpiry ? 'Auto-generated from strike + expiry' : ''}
              />
            </Grid>
          </Grid>

          <Button
            variant="contained"
            color="success"
            onClick={handleInitImport}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <CheckIcon />}
            fullWidth
          >
            {loading ? 'Initializing...' : 'Import & Initialize'}
          </Button>
        </>
      )}

      {/* ================================================================= */}
      {/* Mode D: Adopt — Scan exchange for open positions                  */}
      {/* ================================================================= */}
      {mode === 'adopt' && (
        <MMMAdoptPanel
          sessionId={sessionId}
          selectedExpiry={selectedExpiry}
          onAdopted={(result) => {
            onInitialized?.(result);
          }}
        />
      )}
    </Paper>
  );
};

export default MMMConfigPanel;
