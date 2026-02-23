/**
 * AddPositionDialog — Extracted from OptionsPanel.js (Phase 4.5)
 *
 * Premium-styled dialog for adding to / reducing an options position.
 * Supports Market, Smart, Limit, and SSR order types.
 * Includes AI recommendation display, quick-size presets, percentage shortcuts,
 * and a Quick Mode button to skip future confirmations.
 */
import React from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  TextField,
  Tooltip,
  Typography,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
} from '@mui/icons-material';

const QUICK_SIZES = [1, 2, 5, 10, 20, 50];

const ORDER_TYPES = {
  maker_first: {
    label: 'Smart',
    description: 'Post-only limit at mid-price (no fallback)',
  },
  maker_only: { label: 'Limit', description: 'Post-only limit at your price' },
  market_only: { label: 'Market', description: 'Immediate fill, higher fees' },
  ssr: { label: 'SSR Order', description: 'Competitive pricing: 2 ticks below best ask, auto-adjusts' },
  ssr_standard: { label: 'SSR', description: 'Stealth Sniper: 2 ticks below 2nd best, auto-adjusts' },
  ssr_aggressive: { label: 'SSR Aggro', description: 'Premium-based margin (3-8% below), faster fills' },
  ssr_conservative: { label: 'SSR Safe', description: 'Conservative 1-2% margin, safer fills' },
};

const AddPositionDialog = React.memo(function AddPositionDialog({
  addDialog,
  setAddDialog,
  onSubmit,
  submittingOrder,
  lastUsedSize,
  skipConfirmStrikes,
}) {
  const handleClose = () => {
    setAddDialog({
      open: false,
      position: null,
      size: lastUsedSize,
      side: 'sell',
      orderType: 'maker_first',
      limitPrice: '',
    });
  };

  const update = (fields) => setAddDialog({ ...addDialog, ...fields });

  return (
    <Dialog
      open={addDialog.open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      disableRestoreFocus
      PaperProps={{
        sx: {
          background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.98) 0%, rgba(15, 23, 42, 0.98) 100%)',
          borderRadius: '16px',
          border: '1px solid rgba(148, 163, 184, 0.15)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(20px)',
        },
      }}
    >
      {/* Premium Header with Symbol Info */}
      <Box
        sx={{
          px: 3,
          pt: 2.5,
          pb: 2,
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          background: 'linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, transparent 100%)',
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: 'rgba(148, 163, 184, 0.8)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontSize: '0.65rem',
          }}
        >
          Trade Position
        </Typography>

        {/* Symbol breakdown */}
        {addDialog.position &&
          (() => {
            const parts = (addDialog.position.product_symbol || '').split('-');
            const optType = parts[0] === 'C' ? 'CALL' : 'PUT';
            const underlying = parts[1] || '???';
            const strike = parts[2] || '???';
            const expiry = parts[3]
              ? `${parts[3].slice(0, 2)}/${parts[3].slice(2, 4)}`
              : '??/??';
            const isCall = parts[0] === 'C';

            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1 }}>
                <Box
                  sx={{
                    px: 1.5,
                    py: 0.5,
                    borderRadius: '8px',
                    background: 'rgba(59, 130, 246, 0.15)',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                  }}
                >
                  <Typography sx={{ color: '#60a5fa', fontWeight: 700, fontSize: '1rem' }}>
                    {underlying}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    px: 1.5,
                    py: 0.5,
                    borderRadius: '8px',
                    background: isCall
                      ? 'rgba(16, 185, 129, 0.15)'
                      : 'rgba(239, 68, 68, 0.15)',
                    border: `1px solid ${isCall ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                  }}
                >
                  <Typography
                    sx={{
                      color: isCall ? '#10b981' : '#ef4444',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                    }}
                  >
                    {optType}
                  </Typography>
                </Box>
                <Typography sx={{ color: '#e2e8f0', fontWeight: 600, fontSize: '1.1rem' }}>
                  ${Number(strike).toLocaleString()}
                </Typography>
                <Typography sx={{ color: 'rgba(148, 163, 184, 0.7)', fontSize: '0.85rem' }}>
                  {expiry}
                </Typography>
              </Box>
            );
          })()}

        {/* Current position summary */}
        {addDialog.position && (
          <Box
            sx={{
              display: 'flex',
              gap: 3,
              mt: 1.5,
              py: 1,
              px: 1.5,
              borderRadius: '8px',
              background: 'rgba(0, 0, 0, 0.2)',
            }}
          >
            <Box>
              <Typography
                sx={{
                  color: 'rgba(148, 163, 184, 0.6)',
                  fontSize: '0.7rem',
                  textTransform: 'uppercase',
                }}
              >
                Current Size
              </Typography>
              <Typography
                sx={{
                  color:
                    addDialog.position.size > 0
                      ? '#10b981'
                      : addDialog.position.size < 0
                        ? '#ef4444'
                        : '#94a3b8',
                  fontWeight: 600,
                }}
              >
                {addDialog.position.size > 0 ? '+' : ''}
                {addDialog.position.size}
              </Typography>
            </Box>
            <Box>
              <Typography
                sx={{
                  color: 'rgba(148, 163, 184, 0.6)',
                  fontSize: '0.7rem',
                  textTransform: 'uppercase',
                }}
              >
                Entry
              </Typography>
              <Typography sx={{ color: '#e2e8f0', fontWeight: 600 }}>
                ${parseFloat(addDialog.position.entry_price || 0).toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography
                sx={{
                  color: 'rgba(148, 163, 184, 0.6)',
                  fontSize: '0.7rem',
                  textTransform: 'uppercase',
                }}
              >
                P&L
              </Typography>
              <Typography
                sx={{
                  color: (addDialog.position.unrealized_pnl || 0) >= 0 ? '#10b981' : '#ef4444',
                  fontWeight: 600,
                }}
              >
                {(addDialog.position.unrealized_pnl || 0) >= 0 ? '+' : ''}$
                {parseFloat(addDialog.position.unrealized_pnl || 0).toFixed(2)}
              </Typography>
            </Box>
          </Box>
        )}
      </Box>

      <DialogContent sx={{ px: 3, py: 2.5 }}>
        {/* Smart Scaling Recommendation */}
        {addDialog.recommendation && addDialog.recommendation.action !== 'hold' && (
          <Box
            sx={{
              mb: 2.5,
              p: 2,
              borderRadius: '12px',
              background:
                addDialog.recommendation.action === 'scale'
                  ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)'
                  : 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%)',
              border: `1px solid ${addDialog.recommendation.action === 'scale' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography sx={{ fontSize: '1.1rem' }}>
                {addDialog.recommendation.action === 'scale' ? '🎯' : '⚠️'}
              </Typography>
              <Typography
                sx={{
                  color:
                    addDialog.recommendation.action === 'scale' ? '#10b981' : '#ef4444',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                AI Recommendation:{' '}
                {addDialog.recommendation.action === 'scale' ? 'Scale In' : 'Reduce'}
              </Typography>
            </Box>
            <Typography sx={{ color: 'rgba(148, 163, 184, 0.9)', fontSize: '0.8rem', mb: 0.5 }}>
              Suggested size:{' '}
              <strong style={{ color: '#e2e8f0' }}>
                {addDialog.recommendation.size} contracts
              </strong>
            </Typography>
            <Typography sx={{ color: 'rgba(148, 163, 184, 0.7)', fontSize: '0.75rem' }}>
              {addDialog.recommendation.reason}
            </Typography>
          </Box>
        )}

        {/* Buy/Sell Toggle - Primary Action */}
        <Box sx={{ mb: 3 }}>
          <Typography
            sx={{
              color: 'rgba(148, 163, 184, 0.8)',
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              mb: 1.5,
            }}
          >
            Direction
          </Typography>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Button
              onClick={() => update({ side: 'buy' })}
              fullWidth
              sx={{
                py: 2,
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: 700,
                background:
                  addDialog.side === 'buy'
                    ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)'
                    : 'rgba(16, 185, 129, 0.1)',
                border:
                  addDialog.side === 'buy'
                    ? '2px solid #10b981'
                    : '1px solid rgba(16, 185, 129, 0.3)',
                color: addDialog.side === 'buy' ? '#ffffff' : '#10b981',
                boxShadow:
                  addDialog.side === 'buy'
                    ? '0 4px 15px rgba(16, 185, 129, 0.3)'
                    : 'none',
                transition: 'all 0.2s ease',
                '&:hover': {
                  background:
                    addDialog.side === 'buy'
                      ? 'linear-gradient(135deg, #047857 0%, #059669 100%)'
                      : 'rgba(16, 185, 129, 0.2)',
                  transform: 'translateY(-1px)',
                },
              }}
            >
              <TrendingUp sx={{ mr: 1 }} /> BUY
            </Button>
            <Button
              onClick={() => update({ side: 'sell' })}
              fullWidth
              sx={{
                py: 2,
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: 700,
                background:
                  addDialog.side === 'sell'
                    ? 'linear-gradient(135deg, #dc2626 0%, #ef4444 100%)'
                    : 'rgba(239, 68, 68, 0.1)',
                border:
                  addDialog.side === 'sell'
                    ? '2px solid #ef4444'
                    : '1px solid rgba(239, 68, 68, 0.3)',
                color: addDialog.side === 'sell' ? '#ffffff' : '#ef4444',
                boxShadow:
                  addDialog.side === 'sell'
                    ? '0 4px 15px rgba(239, 68, 68, 0.3)'
                    : 'none',
                transition: 'all 0.2s ease',
                '&:hover': {
                  background:
                    addDialog.side === 'sell'
                      ? 'linear-gradient(135deg, #b91c1c 0%, #dc2626 100%)'
                      : 'rgba(239, 68, 68, 0.2)',
                  transform: 'translateY(-1px)',
                },
              }}
            >
              <TrendingDown sx={{ mr: 1 }} /> SELL
            </Button>
          </Box>
        </Box>

        {/* Quantity Section */}
        <Box sx={{ mb: 3 }}>
          <Typography
            sx={{
              color: 'rgba(148, 163, 184, 0.8)',
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              mb: 1.5,
            }}
          >
            Quantity
          </Typography>

          {/* Quick size buttons */}
          <Box sx={{ display: 'flex', gap: 0.75, mb: 2, flexWrap: 'wrap' }}>
            {QUICK_SIZES.map((size) => (
              <Button
                key={size}
                variant="outlined"
                size="small"
                onClick={() => update({ size: size.toString() })}
                sx={{
                  minWidth: 48,
                  py: 0.75,
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  background:
                    addDialog.size === size.toString()
                      ? 'rgba(59, 130, 246, 0.2)'
                      : 'rgba(30, 41, 59, 0.5)',
                  borderColor:
                    addDialog.size === size.toString()
                      ? '#3b82f6'
                      : 'rgba(148, 163, 184, 0.2)',
                  color: addDialog.size === size.toString() ? '#60a5fa' : '#94a3b8',
                  '&:hover': {
                    background: 'rgba(59, 130, 246, 0.15)',
                    borderColor: '#3b82f6',
                  },
                }}
              >
                {size}
              </Button>
            ))}
          </Box>

          {/* Size input */}
          <TextField
            type="number"
            value={addDialog.size}
            onChange={(e) => update({ size: e.target.value })}
            fullWidth
            variant="outlined"
            placeholder="Enter quantity..."
            inputProps={{ min: 1 }}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: '10px',
                background: 'rgba(0, 0, 0, 0.2)',
                fontSize: '1.2rem',
                fontWeight: 600,
                '& fieldset': { borderColor: 'rgba(148, 163, 184, 0.2)' },
                '&:hover fieldset': { borderColor: 'rgba(148, 163, 184, 0.4)' },
                '&.Mui-focused fieldset': { borderColor: '#3b82f6' },
              },
              '& input': { color: '#e2e8f0', textAlign: 'center', py: 1.5 },
            }}
          />

          {/* Percentage shortcuts */}
          {addDialog.position?.size && Math.abs(addDialog.position.size) > 0 && (
            <Box sx={{ display: 'flex', gap: 0.75, mt: 1.5 }}>
              {[25, 50, 100, 200].map((pct) => {
                const adjustedSize = Math.max(
                  1,
                  Math.round(Math.abs(addDialog.position.size) * (pct / 100))
                );
                return (
                  <Button
                    key={pct}
                    size="small"
                    onClick={() => update({ size: adjustedSize.toString() })}
                    sx={{
                      flex: 1,
                      py: 0.5,
                      borderRadius: '6px',
                      fontSize: '0.7rem',
                      background: 'rgba(148, 163, 184, 0.1)',
                      color: '#94a3b8',
                      '&:hover': { background: 'rgba(148, 163, 184, 0.2)' },
                    }}
                  >
                    {pct}% ({adjustedSize})
                  </Button>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Order Type Section */}
        <Box sx={{ mb: 2 }}>
          <Typography
            sx={{
              color: 'rgba(148, 163, 184, 0.8)',
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              mb: 1.5,
            }}
          >
            Execution
          </Typography>
          {/* Row 1: Standard order types */}
          <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
            {[
              { key: 'market_only', label: '⚡ Market', desc: 'Instant fill' },
              { key: 'maker_first', label: '🎯 Smart', desc: 'Mid-price post-only' },
              { key: 'maker_only', label: '💰 Limit', desc: 'Your price' },
            ].map((opt) => (
              <Tooltip key={opt.key} title={ORDER_TYPES[opt.key]?.description || ''}>
                <Button
                  onClick={() => update({ orderType: opt.key })}
                  sx={{
                    flex: 1,
                    py: 1,
                    borderRadius: '10px',
                    flexDirection: 'column',
                    textTransform: 'none',
                    background:
                      addDialog.orderType === opt.key
                        ? 'rgba(59, 130, 246, 0.2)'
                        : 'rgba(30, 41, 59, 0.5)',
                    border:
                      addDialog.orderType === opt.key
                        ? '1px solid #3b82f6'
                        : '1px solid rgba(148, 163, 184, 0.15)',
                    '&:hover': { background: 'rgba(59, 130, 246, 0.15)' },
                  }}
                >
                  <Typography
                    sx={{
                      color: addDialog.orderType === opt.key ? '#60a5fa' : '#e2e8f0',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                    }}
                  >
                    {opt.label}
                  </Typography>
                  <Typography sx={{ color: 'rgba(148, 163, 184, 0.6)', fontSize: '0.65rem' }}>
                    {opt.desc}
                  </Typography>
                </Button>
              </Tooltip>
            ))}
          </Box>
          {/* Row 2: SSR order types */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            {[
              { key: 'ssr_standard', label: '🏎️ SSR', desc: '2 ticks below', color: '#ff9800' },
              {
                key: 'ssr_aggressive',
                label: '🔥 SSR Aggro',
                desc: '3-8% margin',
                color: '#4caf50',
              },
              {
                key: 'ssr_conservative',
                label: '🛡️ SSR Safe',
                desc: '1-2% margin',
                color: '#03a9f4',
              },
            ].map((opt) => (
              <Tooltip key={opt.key} title={ORDER_TYPES[opt.key]?.description || ''}>
                <Button
                  onClick={() => update({ orderType: opt.key })}
                  sx={{
                    flex: 1,
                    py: 1,
                    borderRadius: '10px',
                    flexDirection: 'column',
                    textTransform: 'none',
                    background:
                      addDialog.orderType === opt.key ? `${opt.color}33` : 'rgba(30, 41, 59, 0.5)',
                    border:
                      addDialog.orderType === opt.key
                        ? `1px solid ${opt.color}`
                        : '1px solid rgba(148, 163, 184, 0.15)',
                    '&:hover': { background: `${opt.color}22` },
                  }}
                >
                  <Typography
                    sx={{
                      color: addDialog.orderType === opt.key ? opt.color : '#e2e8f0',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                    }}
                  >
                    {opt.label}
                  </Typography>
                  <Typography sx={{ color: 'rgba(148, 163, 184, 0.6)', fontSize: '0.65rem' }}>
                    {opt.desc}
                  </Typography>
                </Button>
              </Tooltip>
            ))}
          </Box>
        </Box>

        {/* Limit Price Input (only for maker_only) */}
        {addDialog.orderType === 'maker_only' && (
          <Box
            sx={{
              mb: 2,
              p: 2,
              borderRadius: '10px',
              background: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.2)',
            }}
          >
            <Typography sx={{ color: '#fbbf24', fontSize: '0.75rem', mb: 1, fontWeight: 600 }}>
              💰 Limit Price (optional)
            </Typography>
            <TextField
              type="number"
              value={addDialog.limitPrice}
              onChange={(e) => update({ limitPrice: e.target.value })}
              fullWidth
              variant="outlined"
              placeholder="Leave empty for mid-price"
              inputProps={{ step: 0.01, min: 0 }}
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: '8px',
                  background: 'rgba(0, 0, 0, 0.2)',
                  '& fieldset': { borderColor: 'rgba(251, 191, 36, 0.3)' },
                  '&:hover fieldset': { borderColor: 'rgba(251, 191, 36, 0.5)' },
                  '&.Mui-focused fieldset': { borderColor: '#fbbf24' },
                },
                '& input': { color: '#e2e8f0' },
              }}
            />
          </Box>
        )}

        {/* Warnings */}
        {!addDialog.position?.is_liquid && (
          <Alert
            severity="warning"
            sx={{
              borderRadius: '10px',
              background: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.3)',
              '& .MuiAlert-icon': { color: '#fbbf24' },
            }}
          >
            <Typography sx={{ fontSize: '0.8rem' }}>
              Wide spread ({(Number(addDialog.position?.spread_pct) || 0).toFixed(1)}%) - Consider
              using limit order
            </Typography>
          </Alert>
        )}
      </DialogContent>

      <DialogActions
        sx={{
          px: 3,
          pb: 2.5,
          pt: 1.5,
          borderTop: '1px solid rgba(148, 163, 184, 0.1)',
          gap: 1.5,
        }}
      >
        <Button
          onClick={handleClose}
          sx={{ color: '#94a3b8', '&:hover': { background: 'rgba(148, 163, 184, 0.1)' } }}
        >
          Cancel
        </Button>
        <Box sx={{ flex: 1 }} />

        {/* Quick Mode Button */}
        {addDialog.position &&
          !skipConfirmStrikes[addDialog.position.product_symbol]?.enabled && (
            <Tooltip title="Execute now and skip this dialog for future orders on this strike">
              <Button
                onClick={() => onSubmit(true)}
                disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
                sx={{
                  px: 2,
                  borderRadius: '10px',
                  color: '#fbbf24',
                  border: '1px solid rgba(251, 191, 36, 0.3)',
                  '&:hover': {
                    background: 'rgba(251, 191, 36, 0.1)',
                    border: '1px solid rgba(251, 191, 36, 0.5)',
                  },
                }}
              >
                ⚡ Quick Mode
              </Button>
            </Tooltip>
          )}

        {/* Main Execute Button */}
        <Button
          onClick={() => onSubmit(false)}
          disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
          sx={{
            px: 4,
            py: 1.25,
            borderRadius: '10px',
            fontSize: '1rem',
            fontWeight: 700,
            background:
              addDialog.side === 'buy'
                ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)'
                : 'linear-gradient(135deg, #dc2626 0%, #ef4444 100%)',
            color: '#ffffff',
            boxShadow:
              addDialog.side === 'buy'
                ? '0 4px 15px rgba(16, 185, 129, 0.3)'
                : '0 4px 15px rgba(239, 68, 68, 0.3)',
            '&:hover': {
              background:
                addDialog.side === 'buy'
                  ? 'linear-gradient(135deg, #047857 0%, #059669 100%)'
                  : 'linear-gradient(135deg, #b91c1c 0%, #dc2626 100%)',
              transform: 'translateY(-1px)',
            },
            '&.Mui-disabled': {
              background: 'rgba(148, 163, 184, 0.2)',
              color: 'rgba(148, 163, 184, 0.5)',
            },
          }}
        >
          {submittingOrder
            ? '⏳ Submitting...'
            : `${addDialog.side === 'buy' ? '📈 BUY' : '📉 SELL'} ${addDialog.size || 0}`}
        </Button>
      </DialogActions>
    </Dialog>
  );
});

export default AddPositionDialog;
