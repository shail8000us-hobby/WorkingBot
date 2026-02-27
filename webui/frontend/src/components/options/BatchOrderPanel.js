/**
 * BatchOrderPanel — Extracted from OptionsPanel.js (Phase 4.2 + 4.3)
 *
 * Presentational component for batch order controls, auto-loop management,
 * per-expiry loop controls, order preview, results display, and the batch
 * confirmation dialog.
 *
 * All state lives in the parent (OptionsPanel); this component receives
 * everything via props.
 */
import React from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Select,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Block as BlockIcon,
  PlayArrow as PlayArrowIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material';

const BatchOrderPanel = React.memo(function BatchOrderPanel({
  // Data
  positions,
  selectedStrikes,
  status,
  // Batch controls
  orderQuantity,
  setOrderQuantity,
  multiplierMode,
  setMultiplierMode,
  executionMode,
  setExecutionMode,
  // Batch execution
  batchOrderResults,
  setBatchOrderResults,
  batchExecuting,
  // Auto-loop state
  autoLoopEnabled,
  setAutoLoopEnabled,
  autoLoopRounds,
  setAutoLoopRounds,
  autoLoopRunning,
  autoLoopCurrentRound,
  autoLoopProgress,
  autoLoopError,
  expiryLoopState,
  anyExpiryLoopRunning,
  selectedExpiriesForLoop,
  // Batch confirm dialog
  batchConfirmDialog,
  setBatchConfirmDialog,
  pendingBatchOrders,
  setPendingBatchOrders,
  // Functions / callbacks
  getSelectedPositions,
  getPositionsGCD,
  calculateBatchOrders,
  executeBatchOrders,
  executeBatch,
  executeAutoLoop,
  autoLoopConfirmDialog,
  setAutoLoopConfirmDialog,
  doStartAutoLoop,
  stopAutoLoop,
  startAllExpiryLoops,
  executeExpiryAutoLoop,
  stopExpiryAutoLoop,
  clearAutoLoopError,
  clearExpiryLoopError,
}) {
  if (!positions || positions.length === 0) return null;

  return (
    <>
      {/* ================================================================
          BATCH ORDER PANEL - Quantity-based position scaling with execution modes
          ================================================================ */}
      <Box
        sx={{
          mt: 2,
          p: 2,
          bgcolor: 'rgba(59, 130, 246, 0.1)',
          borderRadius: 1,
          border: '1px solid rgba(59, 130, 246, 0.3)',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          {/* Left: Selection info and bulk ratio controls */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" fontWeight="bold">
              Batch Order
            </Typography>
            <Chip
              label={`${Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length} selected`}
              size="small"
              color={
                Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length > 0
                  ? 'primary'
                  : 'default'
              }
            />
          </Box>

          {/* Center: Quantity Control */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Quantity (lots)
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <IconButton
                size="small"
                onClick={() =>
                  setOrderQuantity((q) => {
                    if (q === 1) return -1;  // skip 0: +1 → -1
                    if (q > 1) return q - 1;
                    return Math.max(-10, q - 1);
                  })
                }
                sx={{
                  bgcolor: 'rgba(255,255,255,0.1)',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                }}
              >
                <RemoveIcon fontSize="small" />
              </IconButton>
              <Select
                value={orderQuantity}
                onChange={(e) => setOrderQuantity(e.target.value)}
                size="small"
                sx={{
                  minWidth: 80,
                  bgcolor: 'rgba(255,255,255,0.1)',
                  '& .MuiSelect-select': { py: 0.5 },
                }}
              >
                {[-10, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 10].map((q) => (
                  <MenuItem key={q} value={q}>
                    {q > 0 ? `+${q}` : q}
                  </MenuItem>
                ))}
              </Select>
              <IconButton
                size="small"
                onClick={() =>
                  setOrderQuantity((q) => {
                    if (q === -1) return 1;  // skip 0: -1 → +1
                    if (q < -1) return q + 1;
                    return Math.min(10, q + 1);
                  })
                }
                sx={{
                  bgcolor: 'rgba(255,255,255,0.1)',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                }}
              >
                <AddIcon fontSize="small" />
              </IconButton>
            </Box>
            <Tooltip
              title={
                multiplierMode === 'fixed'
                  ? orderQuantity > 0
                    ? `FIXED ADD: Exactly ${Math.abs(orderQuantity)} lot(s) per position per round. Use with Auto-Loop for gradual entry.`
                    : `FIXED EXIT: Exactly ${Math.abs(orderQuantity)} lot(s) per position per round. Use with Auto-Loop for gradual exit with minimal slippage.`
                  : multiplierMode === 'normal'
                    ? orderQuantity > 0
                      ? `ADD to positions: x${orderQuantity} multiplier. Scales with position size.`
                      : `EXIT positions: x${Math.abs(orderQuantity)} multiplier. Exits full position size × multiplier.`
                    : `GCD-based multiplier (GCD=${getPositionsGCD(getSelectedPositions())}). ${orderQuantity > 0 ? 'ADD to' : 'EXIT'} positions proportionally.`
              }
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" color={multiplierMode ? "text.secondary" : "warning.main"}>
                  {multiplierMode
                    ? `(${multiplierMode === 'fixed' ? `${Math.abs(orderQuantity)} lot${Math.abs(orderQuantity) > 1 ? 's' : ''} each` : `x${Math.abs(orderQuantity)}`} ${orderQuantity > 0 ? 'add' : 'exit'}${multiplierMode === 'gcd' ? ' GCD' : multiplierMode === 'fixed' ? ' fixed' : ''})`
                    : '⚠ select mode →'}
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    borderRadius: 1,
                    overflow: 'hidden',
                    border: '1px solid rgba(255,255,255,0.2)',
                  }}
                >
                  <Button
                    size="small"
                    variant={multiplierMode === 'normal' ? 'contained' : 'outlined'}
                    onClick={() => setMultiplierMode(prev => prev === 'normal' ? null : 'normal')}
                    sx={{
                      borderRadius: 0,
                      minWidth: 55,
                      fontSize: '0.7rem',
                      py: 0.25,
                      bgcolor:
                        multiplierMode === 'normal'
                          ? 'rgba(59, 130, 246, 0.8)'
                          : 'transparent',
                      color: multiplierMode === 'normal' ? '#fff' : 'rgba(59, 130, 246, 0.8)',
                      borderColor: 'transparent',
                      '&:hover': {
                        bgcolor:
                          multiplierMode === 'normal'
                            ? 'rgba(59, 130, 246, 1)'
                            : 'rgba(59, 130, 246, 0.1)',
                        borderColor: 'transparent',
                      },
                    }}
                  >
                    Normal
                  </Button>
                  <Button
                    size="small"
                    variant={multiplierMode === 'gcd' ? 'contained' : 'outlined'}
                    onClick={() => setMultiplierMode(prev => prev === 'gcd' ? null : 'gcd')}
                    sx={{
                      borderRadius: 0,
                      minWidth: 45,
                      fontSize: '0.7rem',
                      py: 0.25,
                      bgcolor:
                        multiplierMode === 'gcd' ? 'rgba(251, 191, 36, 0.8)' : 'transparent',
                      color: multiplierMode === 'gcd' ? '#000' : 'rgba(251, 191, 36, 0.8)',
                      borderColor: 'transparent',
                      '&:hover': {
                        bgcolor:
                          multiplierMode === 'gcd'
                            ? 'rgba(251, 191, 36, 1)'
                            : 'rgba(251, 191, 36, 0.1)',
                        borderColor: 'transparent',
                      },
                    }}
                  >
                    GCD
                  </Button>
                  <Button
                    size="small"
                    variant={multiplierMode === 'fixed' ? 'contained' : 'outlined'}
                    onClick={() => setMultiplierMode(prev => prev === 'fixed' ? null : 'fixed')}
                    sx={{
                      borderRadius: 0,
                      minWidth: 50,
                      fontSize: '0.7rem',
                      py: 0.25,
                      bgcolor:
                        multiplierMode === 'fixed' ? 'rgba(16, 185, 129, 0.8)' : 'transparent',
                      color: multiplierMode === 'fixed' ? '#fff' : 'rgba(16, 185, 129, 0.8)',
                      borderColor: 'transparent',
                      '&:hover': {
                        bgcolor:
                          multiplierMode === 'fixed'
                            ? 'rgba(16, 185, 129, 1)'
                            : 'rgba(16, 185, 129, 0.1)',
                        borderColor: 'transparent',
                      },
                    }}
                  >
                    Fixed
                  </Button>
                </Box>
              </Box>
            </Tooltip>
          </Box>

          {/* Execution Mode Toggle */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            <Tooltip title="Market: Fill immediately. Smart: Limit at mid-price. SSR: Competitive pricing with auto-adjust.">
              <Box
                sx={{
                  display: 'flex',
                  borderRadius: 1,
                  overflow: 'hidden',
                  border: '1px solid rgba(255,255,255,0.2)',
                  flexWrap: 'wrap',
                }}
              >
                <Button
                  size="small"
                  variant={executionMode === 'immediate' ? 'contained' : 'outlined'}
                  onClick={() => setExecutionMode('immediate')}
                  sx={{
                    borderRadius: 0,
                    minWidth: 70,
                    bgcolor:
                      executionMode === 'immediate'
                        ? 'rgba(239, 68, 68, 0.8)'
                        : 'transparent',
                    color: executionMode === 'immediate' ? '#fff' : 'rgba(239, 68, 68, 0.8)',
                    borderColor: 'transparent',
                    '&:hover': {
                      bgcolor:
                        executionMode === 'immediate'
                          ? 'rgba(239, 68, 68, 1)'
                          : 'rgba(239, 68, 68, 0.1)',
                      borderColor: 'transparent',
                    },
                  }}
                >
                  🚀 Market
                </Button>
                <Button
                  size="small"
                  variant={executionMode === 'smart' ? 'contained' : 'outlined'}
                  onClick={() => setExecutionMode('smart')}
                  sx={{
                    borderRadius: 0,
                    minWidth: 70,
                    bgcolor:
                      executionMode === 'smart' ? 'rgba(16, 185, 129, 0.8)' : 'transparent',
                    color: executionMode === 'smart' ? '#fff' : 'rgba(16, 185, 129, 0.8)',
                    borderColor: 'transparent',
                    '&:hover': {
                      bgcolor:
                        executionMode === 'smart'
                          ? 'rgba(16, 185, 129, 1)'
                          : 'rgba(16, 185, 129, 0.1)',
                      borderColor: 'transparent',
                    },
                  }}
                >
                  🧠 Smart
                </Button>
                <Button
                  size="small"
                  variant={executionMode === 'ssr_standard' ? 'contained' : 'outlined'}
                  onClick={() => setExecutionMode('ssr_standard')}
                  sx={{
                    borderRadius: 0,
                    minWidth: 60,
                    bgcolor:
                      executionMode === 'ssr_standard' ? 'rgba(255, 152, 0, 0.8)' : 'transparent',
                    color: executionMode === 'ssr_standard' ? '#fff' : 'rgba(255, 152, 0, 0.8)',
                    borderColor: 'transparent',
                    '&:hover': {
                      bgcolor:
                        executionMode === 'ssr_standard'
                          ? 'rgba(255, 152, 0, 1)'
                          : 'rgba(255, 152, 0, 0.1)',
                      borderColor: 'transparent',
                    },
                  }}
                >
                  🏎️ SSR
                </Button>
                <Button
                  size="small"
                  variant={executionMode === 'ssr_aggressive' ? 'contained' : 'outlined'}
                  onClick={() => setExecutionMode('ssr_aggressive')}
                  sx={{
                    borderRadius: 0,
                    minWidth: 70,
                    bgcolor:
                      executionMode === 'ssr_aggressive' ? 'rgba(76, 175, 80, 0.8)' : 'transparent',
                    color: executionMode === 'ssr_aggressive' ? '#fff' : 'rgba(76, 175, 80, 0.8)',
                    borderColor: 'transparent',
                    '&:hover': {
                      bgcolor:
                        executionMode === 'ssr_aggressive'
                          ? 'rgba(76, 175, 80, 1)'
                          : 'rgba(76, 175, 80, 0.1)',
                      borderColor: 'transparent',
                    },
                  }}
                >
                  🔥 Aggro
                </Button>
                <Button
                  size="small"
                  variant={executionMode === 'ssr_conservative' ? 'contained' : 'outlined'}
                  onClick={() => setExecutionMode('ssr_conservative')}
                  sx={{
                    borderRadius: 0,
                    minWidth: 60,
                    bgcolor:
                      executionMode === 'ssr_conservative' ? 'rgba(3, 169, 244, 0.8)' : 'transparent',
                    color: executionMode === 'ssr_conservative' ? '#fff' : 'rgba(3, 169, 244, 0.8)',
                    borderColor: 'transparent',
                    '&:hover': {
                      bgcolor:
                        executionMode === 'ssr_conservative'
                          ? 'rgba(3, 169, 244, 1)'
                          : 'rgba(3, 169, 244, 0.1)',
                      borderColor: 'transparent',
                    },
                  }}
                >
                  🛡️ Safe
                </Button>
              </Box>
            </Tooltip>
          </Box>

          {/* Right: Execute Button and Auto-Loop Controls */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            {/* Auto-Loop Toggle with Label */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 1.5,
              py: 0.5,
              borderRadius: '8px',
              bgcolor: autoLoopEnabled ? 'rgba(251, 191, 36, 0.15)' : 'transparent',
              border: autoLoopEnabled ? '1px solid rgba(251, 191, 36, 0.4)' : '1px solid transparent',
            }}>
              <Tooltip title="Enable Auto-Loop: Bot places batch orders → waits for ALL fills → repeats. Perfect for low-liquidity options where you can't punch large quantities at once.">
                <Checkbox
                  checked={autoLoopEnabled}
                  onChange={(e) => setAutoLoopEnabled(e.target.checked)}
                  size="small"
                  disabled={autoLoopRunning}
                  sx={{
                    color: 'rgba(251, 191, 36, 0.6)',
                    '&.Mui-checked': { color: 'rgba(251, 191, 36, 1)' },
                    p: 0.5,
                  }}
                />
              </Tooltip>
              <Typography
                variant="caption"
                sx={{
                  color: autoLoopEnabled ? '#fbbf24' : 'rgba(148, 163, 184, 0.8)',
                  fontWeight: autoLoopEnabled ? 600 : 400,
                  mr: 0.5,
                }}
              >
                🔁 Auto-Loop
              </Typography>
              {autoLoopEnabled && (
                <>
                  <TextField
                    type="number"
                    value={autoLoopRounds}
                    onChange={(e) => setAutoLoopRounds(Math.max(1, parseInt(e.target.value) || 1))}
                    size="small"
                    disabled={autoLoopRunning}
                    inputProps={{ min: 1, max: 1000, style: { textAlign: 'center' } }}
                    sx={{
                      width: 60,
                      '& .MuiInputBase-input': { py: 0.5, fontSize: '0.875rem', fontWeight: 'bold' },
                      '& .MuiOutlinedInput-root': {
                        bgcolor: 'rgba(0,0,0,0.3)',
                        '& fieldset': { borderColor: 'rgba(251, 191, 36, 0.4)' },
                      },
                    }}
                  />
                  <Typography variant="caption" sx={{ color: '#fbbf24', fontWeight: 500 }}>
                    rounds
                  </Typography>
                </>
              )}
            </Box>

            {/* Execute or Auto-Loop Button */}
            {autoLoopRunning ? (
              <Button
                variant="contained"
                color="error"
                startIcon={<BlockIcon />}
                onClick={stopAutoLoop}
                sx={{
                  minWidth: 160,
                  fontWeight: 'bold',
                  animation: 'pulse 1.5s infinite',
                  '@keyframes pulse': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.7 },
                  },
                }}
              >
                🛑 STOP Loop
              </Button>
            ) : autoLoopEnabled ? (
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                onClick={() => executeAutoLoop(1)}
                disabled={
                  calculateBatchOrders().length === 0 ||
                  !status?.trading_allowed ||
                  !autoLoopRounds ||
                  autoLoopRounds < 1
                }
                sx={{
                  minWidth: 180,
                  fontWeight: 'bold',
                  bgcolor: 'rgba(251, 191, 36, 0.9)',
                  color: '#000',
                  '&:hover': { bgcolor: 'rgba(251, 191, 36, 1)' },
                  '&:disabled': { bgcolor: 'rgba(100, 100, 100, 0.3)', color: 'rgba(150,150,150,0.5)' },
                }}
              >
                🚀 Start Auto-Loop
              </Button>
            ) : (
              <Button
                variant="contained"
                color={orderQuantity > 0 ? 'success' : 'error'}
                startIcon={
                  batchExecuting ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <PlayArrowIcon />
                  )
                }
                onClick={executeBatchOrders}
                disabled={
                  batchExecuting ||
                  calculateBatchOrders().length === 0 ||
                  !status?.trading_allowed
                }
                sx={{ minWidth: 160, fontWeight: 'bold' }}
              >
                {batchExecuting
                  ? 'Executing...'
                  : `Execute ${calculateBatchOrders().length} Orders`}
              </Button>
            )}
          </Box>
        </Box>

        {/* Auto-Loop Progress Display - Enhanced */}
        {autoLoopRunning && (
          <Box sx={{
            mt: 2,
            pt: 2,
            borderTop: '2px solid rgba(251, 191, 36, 0.4)',
            bgcolor: 'rgba(251, 191, 36, 0.05)',
            borderRadius: '0 0 12px 12px',
            mx: -2,
            px: 2,
            pb: 2,
          }}>
            {/* Header with round counter and progress bar */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <CircularProgress size={24} thickness={5} sx={{ color: '#fbbf24' }} />
                <Box>
                  <Typography variant="body1" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                    🔁 Auto-Loop Active
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(251, 191, 36, 0.7)' }}>
                    {executionMode === 'immediate'
                      ? 'Placing orders with Market execution (Instant Fill)'
                      : executionMode === 'smart'
                        ? 'Placing orders with Smart execution (Limit @ Mid-Price)'
                        : executionMode === 'ssr_standard'
                          ? 'Placing orders with SSR execution (Bid+2t / Ask-2t, auto-adjusting)'
                          : executionMode === 'ssr_aggressive'
                            ? 'Placing orders with SSR Aggro execution (5% inside spread, auto-adjusting)'
                            : executionMode === 'ssr_conservative'
                              ? 'Placing orders with SSR Safe execution (1.5% inside spread, auto-adjusting)'
                              : 'Placing orders with Smart execution (Limit @ Mid-Price)'}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ textAlign: 'right' }}>
                <Typography variant="h6" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                  Round {autoLoopCurrentRound} / {autoLoopRounds}
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.8)' }}>
                  {autoLoopRounds - autoLoopCurrentRound} rounds remaining
                </Typography>
              </Box>
            </Box>

            {/* Progress bar */}
            <Box sx={{
              width: '100%',
              height: 8,
              bgcolor: 'rgba(0,0,0,0.3)',
              borderRadius: 4,
              overflow: 'hidden',
              mb: 2,
            }}>
              <Box sx={{
                width: `${(autoLoopCurrentRound / autoLoopRounds) * 100}%`,
                height: '100%',
                bgcolor: '#fbbf24',
                borderRadius: 4,
                transition: 'width 0.5s ease',
              }} />
            </Box>

            {/* Current round status */}
            <Box sx={{
              p: 1.5,
              bgcolor: 'rgba(0,0,0,0.2)',
              borderRadius: '8px',
              border: '1px solid rgba(251, 191, 36, 0.2)',
            }}>
              <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.8)', display: 'block', mb: 1 }}>
                📋 Current Round Order Status:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {Object.entries(autoLoopProgress).map(([symbol, progress]) => {
                  const strikeInfo = symbol.split('-');
                  const optType = strikeInfo[0] || '';
                  const strike = strikeInfo[2] || symbol;
                  const statusIcon = progress.status === 'filled' ? '✅' : progress.status === 'pending' ? '⏳' : '📤';
                  const statusText = progress.status === 'filled' ? 'Filled' : progress.status === 'pending' ? 'Waiting...' : 'Placing...';

                  return (
                    <Chip
                      key={symbol}
                      size="small"
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <span>{statusIcon}</span>
                          <span style={{ fontWeight: 'bold' }}>{optType}{strike}</span>
                          <span style={{ opacity: 0.7 }}>×{progress.size}</span>
                          <span style={{ fontSize: '0.65rem' }}>{statusText}</span>
                          {progress.fillPrice && (
                            <span style={{ color: '#10b981', fontWeight: 'bold' }}>@{progress.fillPrice}</span>
                          )}
                        </Box>
                      }
                      sx={{
                        bgcolor: progress.status === 'filled'
                          ? 'rgba(16, 185, 129, 0.25)'
                          : progress.status === 'pending'
                            ? 'rgba(251, 191, 36, 0.25)'
                            : 'rgba(59, 130, 246, 0.25)',
                        border: `1px solid ${progress.status === 'filled' ? 'rgba(16, 185, 129, 0.5)' : progress.status === 'pending' ? 'rgba(251, 191, 36, 0.5)' : 'rgba(59, 130, 246, 0.5)'}`,
                        color: progress.status === 'filled' ? '#10b981' : progress.status === 'pending' ? '#fbbf24' : '#60a5fa',
                        fontWeight: 500,
                        fontSize: '0.75rem',
                        height: 'auto',
                        py: 0.5,
                        '& .MuiChip-label': { px: 1 },
                      }}
                    />
                  );
                })}
              </Box>
              {Object.keys(autoLoopProgress).length > 0 && (
                <Box sx={{ mt: 1.5, display: 'flex', gap: 2 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(16, 185, 129, 0.9)' }}>
                    ✅ Filled: {Object.values(autoLoopProgress).filter(p => p.status === 'filled').length}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(251, 191, 36, 0.9)' }}>
                    ⏳ Pending: {Object.values(autoLoopProgress).filter(p => p.status === 'pending').length}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(59, 130, 246, 0.9)' }}>
                    📤 Placing: {Object.values(autoLoopProgress).filter(p => p.status === 'placing').length}
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        )}

        {/* Auto-Loop Error/Warning/Recovery Display */}
        {autoLoopError && (
          <Box sx={{ mt: 2 }}>
            <Alert
              severity={autoLoopError.includes('Stopped by user') ? 'info' : autoLoopError.includes('⚠️') ? 'warning' : 'error'}
              onClose={clearAutoLoopError}
              action={
                autoLoopError.includes('⚠️') ? (
                  <Button color="inherit" size="small" onClick={clearAutoLoopError} sx={{ fontWeight: 'bold' }}>
                    DISMISS
                  </Button>
                ) : null
              }
              sx={{
                fontSize: '0.875rem',
                '& .MuiAlert-message': { fontWeight: 500 },
              }}
            >
              {autoLoopError}
              {autoLoopError.includes('⚠️') && (
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.8 }}>
                  Check Delta Exchange → Orders to see if any orders are still pending/open.
                </Typography>
              )}
            </Alert>
          </Box>
        )}

        {/* Auto-Loop Info Panel - Show when enabled OR when per-expiry loops are running */}
        {(autoLoopEnabled || anyExpiryLoopRunning) && calculateBatchOrders().length > 0 && (
          <Box sx={{
            mt: 2,
            p: 2,
            bgcolor: 'rgba(251, 191, 36, 0.08)',
            borderRadius: '10px',
            border: '1px dashed rgba(251, 191, 36, 0.4)',
          }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ color: '#fbbf24', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                📋 Auto-Loop Execution Plan {selectedExpiriesForLoop.length > 1 ? `(${selectedExpiriesForLoop.length} expiries)` : ''}
              </Typography>
              {selectedExpiriesForLoop.length > 1 && (
                <Button
                  variant="contained"
                  size="small"
                  onClick={startAllExpiryLoops}
                  disabled={!status?.trading_allowed}
                  sx={{
                    bgcolor: 'rgba(251, 191, 36, 0.9)',
                    color: '#000',
                    fontWeight: 'bold',
                    '&:hover': { bgcolor: 'rgba(251, 191, 36, 1)' }
                  }}
                >
                  🚀 Start ALL Expiries
                </Button>
              )}
            </Box>

            {/* Per-Expiry Loop Controls */}
            {selectedExpiriesForLoop.length >= 1 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {selectedExpiriesForLoop.map(expiry => {
                  const expiryOrders = calculateBatchOrders(expiry);
                  const loopState = expiryLoopState[expiry] || {};
                  const isRunning = loopState.running;
                  const hasError = loopState.error;

                  return (
                    <Box key={expiry} sx={{
                      p: 1.5,
                      bgcolor: isRunning ? 'rgba(251, 191, 36, 0.15)' : 'rgba(0,0,0,0.2)',
                      borderRadius: '8px',
                      border: isRunning ? '2px solid rgba(251, 191, 36, 0.5)' : hasError ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid transparent',
                    }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                          <Typography variant="body2" fontWeight="bold" sx={{ color: '#fbbf24', minWidth: 70 }}>
                            {expiry}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.8)' }}>
                            {expiryOrders.length} orders × {autoLoopRounds} rounds
                          </Typography>
                          {loopState.completed && (
                            <Chip label="✅ Done" size="small" sx={{ bgcolor: 'rgba(16,185,129,0.2)', color: '#10b981', fontWeight: 'bold' }} />
                          )}
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          {isRunning ? (
                            <>
                              <Chip
                                size="small"
                                icon={<CircularProgress size={12} sx={{ color: '#fbbf24' }} />}
                                label={`R${loopState.currentRound}/${loopState.totalRounds}`}
                                sx={{ bgcolor: 'rgba(251, 191, 36, 0.25)', color: '#fbbf24', fontWeight: 'bold' }}
                              />
                              <Button
                                variant="outlined"
                                size="small"
                                color="error"
                                onClick={() => stopExpiryAutoLoop(expiry)}
                                sx={{ minWidth: 60, fontSize: '0.7rem' }}
                              >
                                Stop
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="contained"
                              size="small"
                              onClick={() => executeExpiryAutoLoop(expiry)}
                              disabled={expiryOrders.length === 0 || !status?.trading_allowed}
                              sx={{
                                minWidth: 80,
                                bgcolor: 'rgba(16, 185, 129, 0.8)',
                                '&:hover': { bgcolor: 'rgba(16, 185, 129, 1)' },
                                fontWeight: 'bold',
                                fontSize: '0.75rem',
                              }}
                            >
                              ▶ Start
                            </Button>
                          )}
                        </Box>
                      </Box>
                      {hasError && (
                        <Alert
                          severity="error"
                          onClose={() => clearExpiryLoopError(expiry)}
                          sx={{ mt: 1, py: 0, fontSize: '0.75rem' }}
                        >
                          {hasError}
                        </Alert>
                      )}
                      {/* Per-expiry progress */}
                      {isRunning && Object.keys(loopState.progress || {}).length > 0 && (
                        <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {Object.entries(loopState.progress).map(([symbol, progress]) => {
                            const strike = symbol.split('-')[2] || symbol;
                            const optType = symbol.startsWith('C-') ? 'C' : 'P';
                            return (
                              <Chip
                                key={symbol}
                                size="small"
                                label={`${progress.filled ? '✅' : '⏳'} ${optType}${strike}`}
                                sx={{
                                  bgcolor: progress.filled ? 'rgba(16,185,129,0.2)' : 'rgba(251,191,36,0.2)',
                                  color: progress.filled ? '#10b981' : '#fbbf24',
                                  fontSize: '0.65rem',
                                  height: 20,
                                }}
                              />
                            );
                          })}
                        </Box>
                      )}
                    </Box>
                  );
                })}
              </Box>
            ) : (
              /* Single expiry - show original summary view */
              <>
                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2, mb: 2 }}>
                  <Box sx={{ p: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                    <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)', display: 'block' }}>Per Round</Typography>
                    <Typography variant="h6" sx={{ color: '#e2e8f0', fontWeight: 'bold' }}>
                      {calculateBatchOrders().length} orders
                    </Typography>
                  </Box>
                  <Box sx={{ p: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                    <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)', display: 'block' }}>Total Rounds</Typography>
                    <Typography variant="h6" sx={{ color: '#fbbf24', fontWeight: 'bold' }}>
                      {autoLoopRounds} rounds
                    </Typography>
                  </Box>
                  <Box sx={{ p: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                    <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)', display: 'block' }}>Total Orders</Typography>
                    <Typography variant="h6" sx={{ color: '#10b981', fontWeight: 'bold' }}>
                      {calculateBatchOrders().length * autoLoopRounds} orders
                    </Typography>
                  </Box>
                  <Box sx={{ p: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                    <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)', display: 'block' }}>Execution</Typography>
                    <Typography variant="body2" sx={{ color: '#60a5fa', fontWeight: 'bold' }}>
                      {executionMode === 'immediate' ? '🚀 Market (Instant)' : '🧠 Smart (Limit @ Mid)'}
                    </Typography>
                  </Box>
                </Box>

                <Box sx={{
                  p: 1.5,
                  bgcolor: 'rgba(59, 130, 246, 0.1)',
                  borderRadius: '8px',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                }}>
                  <Typography variant="caption" sx={{ color: '#60a5fa', fontWeight: 500 }}>
                    🔄 How it works:
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.9)', display: 'block', mt: 0.5, lineHeight: 1.6 }}>
                    1️⃣ Place all {calculateBatchOrders().length} orders at mid-price (limit orders)<br />
                    2️⃣ Wait indefinitely until ALL orders are filled<br />
                    3️⃣ Once all filled → automatically place next batch<br />
                    4️⃣ Repeat until all {autoLoopRounds} rounds complete<br />
                    ⚠️ Press STOP anytime to halt the loop
                  </Typography>
                </Box>

                {/* Order breakdown */}
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)', display: 'block', mb: 1 }}>
                    📊 Orders per round breakdown:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                    {calculateBatchOrders().map((order, idx) => {
                      const strikeInfo = order.symbol.split('-');
                      const strike = strikeInfo[2] || order.symbol;
                      return (
                        <Chip
                          key={idx}
                          size="small"
                          label={`${order.side === 'buy' ? '🟢' : '🔴'} ${order.optionType === 'Call' ? 'C' : 'P'}${strike} ×${order.size}`}
                          sx={{
                            bgcolor: order.side === 'buy' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            border: `1px solid ${order.side === 'buy' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                            color: order.side === 'buy' ? '#10b981' : '#ef4444',
                            fontWeight: 600,
                            fontSize: '0.7rem',
                          }}
                        />
                      );
                    })}
                  </Box>
                </Box>
              </>
            )}
          </Box>
        )}

        {/* Preview of orders */}
        {Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length > 0 && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mb: 1, display: 'block' }}
            >
              Order Preview (
              {executionMode === 'immediate'
                ? 'Market Orders - Instant Fill'
                : executionMode === 'smart'
                  ? 'Limit Orders @ Mid - Auto-Market after 5min'
                  : executionMode === 'ssr_standard'
                    ? 'SSR: Bid+2t / Ask-2t with continuous auto-adjust'
                    : executionMode === 'ssr_aggressive'
                      ? 'SSR Aggro: 5% inside spread, continuous auto-adjust'
                      : executionMode === 'ssr_conservative'
                        ? 'SSR Safe: 1.5% inside spread, continuous auto-adjust'
                        : 'Limit Orders @ Mid'}
              ):
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {calculateBatchOrders().map((order, idx) => (
                <Chip
                  key={idx}
                  size="small"
                  label={`${order.side.toUpperCase()} ${order.size} ${order.optionType === 'Call' ? 'C' : 'P'} ${order.symbol.split('-')[2]} ${executionMode === 'immediate' ? '🚀' : '🧠'}`}
                  sx={{
                    bgcolor:
                      order.side === 'buy'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : 'rgba(239, 68, 68, 0.2)',
                    color: order.side === 'buy' ? '#10b981' : '#ef4444',
                    fontWeight: 'bold',
                    fontSize: '0.7rem',
                  }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Batch order results */}
        {batchOrderResults.length > 0 && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 1,
              }}
            >
              <Typography variant="caption" color="text.secondary">
                Results:
              </Typography>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setBatchOrderResults([])}
                sx={{ fontSize: '0.7rem', py: 0, px: 1, minWidth: 'auto' }}
              >
                Dismiss
              </Button>
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {batchOrderResults.map((result, idx) => {
                const color = result.filled
                  ? '#10b981'
                  : result.success
                    ? '#3b82f6'
                    : '#ef4444';
                const icon = result.filled ? '✅' : result.success ? '📤' : '❌';

                return (
                  <Typography
                    key={idx}
                    variant="caption"
                    sx={{ color, display: 'flex', alignItems: 'center', gap: 0.5 }}
                  >
                    <span>{icon}</span>
                    <span>
                      {result.symbol.split('-').slice(0, 3).join('-')}: {result.message}
                    </span>
                  </Typography>
                );
              })}
            </Box>
          </Box>
        )}
      </Box>

      {/* Auto-Loop Confirmation Dialog */}
      <Dialog
        open={autoLoopConfirmDialog?.open || false}
        onClose={() => setAutoLoopConfirmDialog(prev => ({ ...prev, open: false }))}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { bgcolor: '#1a1f2e', border: '1px solid rgba(251, 191, 36, 0.4)', borderRadius: 2 } }}
      >
        <DialogTitle sx={{ bgcolor: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24', fontWeight: 'bold', borderBottom: '1px solid rgba(251, 191, 36, 0.3)' }}>
          🔁 Confirm Auto-Loop Execution
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="warning" sx={{ mb: 2, bgcolor: 'rgba(251, 191, 36, 0.1)', color: '#fbbf24', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
            <AlertTitle sx={{ fontWeight: 'bold' }}>Review before starting</AlertTitle>
            This will place orders repeatedly for <strong>{autoLoopConfirmDialog?.totalRounds} rounds</strong>.
          </Alert>

          {/* Summary stats */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, p: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1, border: '1px solid rgba(255,255,255,0.1)', textAlign: 'center' }}>
              <Typography variant="h5" fontWeight="bold" sx={{ color: '#fbbf24' }}>{autoLoopConfirmDialog?.orders?.length || 0}</Typography>
              <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.8)' }}>orders per round</Typography>
            </Box>
            <Box sx={{ flex: 1, p: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1, border: '1px solid rgba(255,255,255,0.1)', textAlign: 'center' }}>
              <Typography variant="h5" fontWeight="bold" sx={{ color: '#fbbf24' }}>×{autoLoopConfirmDialog?.totalRounds}</Typography>
              <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.8)' }}>rounds</Typography>
            </Box>
            <Box sx={{ flex: 1, p: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1, border: '1px solid rgba(255,255,255,0.1)', textAlign: 'center' }}>
              <Typography variant="h5" fontWeight="bold" sx={{ color: '#10b981' }}>{(autoLoopConfirmDialog?.orders?.length || 0) * (autoLoopConfirmDialog?.totalRounds || 0)}</Typography>
              <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.8)' }}>total placements</Typography>
            </Box>
          </Box>

          {/* Settings info */}
          <Box sx={{ p: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, border: '1px solid rgba(255,255,255,0.08)', mb: 2 }}>
            <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.6)', display: 'block', mb: 1 }}>SETTINGS</Typography>
            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
              <Box>
                <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.6)' }}>Order type</Typography>
                <Typography variant="body2" fontWeight="bold" sx={{ color: '#e2e8f0' }}>
                  {autoLoopConfirmDialog?.executionMode === 'immediate' ? '🚀 Market'
                    : autoLoopConfirmDialog?.executionMode === 'smart' ? '🧠 Smart'
                      : autoLoopConfirmDialog?.executionMode === 'ssr_standard' ? '🏎️ SSR'
                        : autoLoopConfirmDialog?.executionMode === 'ssr_aggressive' ? '🔥 Aggro'
                          : autoLoopConfirmDialog?.executionMode === 'ssr_conservative' ? '🛡️ Safe'
                            : autoLoopConfirmDialog?.executionMode}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.6)' }}>Size mode</Typography>
                <Typography variant="body2" fontWeight="bold" sx={{ color: '#e2e8f0' }}>
                  {autoLoopConfirmDialog?.multiplierMode === 'normal' ? 'Normal'
                    : autoLoopConfirmDialog?.multiplierMode === 'gcd' ? 'GCD'
                      : autoLoopConfirmDialog?.multiplierMode === 'fixed' ? 'Fixed'
                        : autoLoopConfirmDialog?.multiplierMode}
                </Typography>
              </Box>
            </Box>
          </Box>

          {/* Order list */}
          <Typography variant="caption" sx={{ color: 'rgba(148,163,184,0.6)', display: 'block', mb: 1 }}>ORDERS PER ROUND</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {(autoLoopConfirmDialog?.orders || []).map((o, i) => (
              <Chip
                key={i}
                size="small"
                label={`${o.side?.toUpperCase()} ${o.size} × ${o.symbol}`}
                sx={{
                  bgcolor: o.side === 'buy' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
                  color: o.side === 'buy' ? '#10b981' : '#ef4444',
                  border: `1px solid ${o.side === 'buy' ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
                  fontWeight: 600,
                  fontSize: '0.7rem',
                }}
              />
            ))}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <Button
            onClick={() => setAutoLoopConfirmDialog(prev => ({ ...prev, open: false }))}
            variant="outlined"
            sx={{ color: 'rgba(148,163,184,0.8)', borderColor: 'rgba(148,163,184,0.3)' }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              const { orders, totalRounds, orderPreference } = autoLoopConfirmDialog;
              setAutoLoopConfirmDialog(prev => ({ ...prev, open: false }));
              doStartAutoLoop(orders, totalRounds, orderPreference);
            }}
            variant="contained"
            autoFocus
            sx={{ bgcolor: 'rgba(251,191,36,0.9)', color: '#000', fontWeight: 'bold', '&:hover': { bgcolor: '#fbbf24' } }}
          >
            🚀 Start {autoLoopConfirmDialog?.totalRounds} Round{autoLoopConfirmDialog?.totalRounds !== 1 ? 's' : ''}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Batch Order Confirmation Dialog */}
      <Dialog
        open={batchConfirmDialog.open}
        onClose={() => setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: 'warning.main', color: 'warning.contrastText' }}>
          ⚠️ Large Batch Order Confirmation
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <AlertTitle>Please Confirm</AlertTitle>
            You're about to place <strong>{batchConfirmDialog.orderCount} orders</strong>.
          </Alert>
          <Typography variant="body2" color="text.secondary">
            • Estimated execution time: <strong>~{batchConfirmDialog.estimatedTime} seconds</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • Orders will be rate-limited to prevent API throttling
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • You can monitor progress in the results panel
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => {
              setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 });
              setPendingBatchOrders(null);
            }}
            variant="outlined"
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              const orders = pendingBatchOrders || calculateBatchOrders();
              setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 });
              setPendingBatchOrders(null);
              executeBatch(orders);
            }}
            color="warning"
            variant="contained"
            autoFocus
          >
            Proceed with {batchConfirmDialog.orderCount} Orders
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
});

export default BatchOrderPanel;
