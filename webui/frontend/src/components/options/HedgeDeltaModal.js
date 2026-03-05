/**
 * HedgeDeltaModal
 *
 * Confirmation modal for manual delta hedge orders.
 * Shows current portfolio delta, proposed action, order type toggle.
 * On confirm → POST /api/options/hedge-delta
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  IconButton,
  LinearProgress,
  TextField,
  Alert,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import BoltIcon from '@mui/icons-material/Bolt';

const MODAL_STYLES = {
  bgcolor: '#0f1623',
  border: '1px solid #1e2d45',
  borderRadius: '14px',
  color: '#e2e8f0',
  minWidth: 420,
  maxWidth: 460,
};

export default function HedgeDeltaModal({ open, delta, btcPrice, onClose, onSuccess }) {
  const [orderType, setOrderType]     = useState('market');
  const [smartOffset, setSmartOffset] = useState(0.05);
  const [status, setStatus]           = useState('idle');  // idle|loading|success|error
  const [resultMsg, setResultMsg]     = useState('');
  const [orderId, setOrderId]         = useState('');

  // Reset when opened
  useEffect(() => {
    if (open) {
      setStatus('idle');
      setResultMsg('');
      setOrderId('');
      setOrderType('market');
      setSmartOffset(0.05);
    }
  }, [open]);

  const absDelta     = Math.abs(delta || 0);
  const isLong       = (delta || 0) > 0;           // long delta → need to SHORT
  const action       = isLong ? 'SELL (SHORT)' : 'BUY (LONG)';
  const confirmColor = isLong ? '#ef4444' : '#22c55e';
  const confirmHover = isLong ? '#dc2626' : '#16a34a';
  const usdNotional  = btcPrice > 0
    ? `≈ $${(absDelta * btcPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
    : '';
  const barPct = Math.min((absDelta / 20) * 100, 100);  // scale to 20 BTC max

  const handleConfirm = async () => {
    setStatus('loading');
    try {
      const payload = {
        portfolio_delta: delta,
        order_type: orderType,
        trigger: 'manual',
        ...(orderType === 'smart' ? { smart_offset_pct: smartOffset } : {}),
      };
      const res  = await fetch('/api/options/hedge-delta', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.status === 'success') {
        setStatus('success');
        setOrderId(data.order_id);
        setTimeout(() => onSuccess && onSuccess(), 1500);
      } else if (data.status === 'no_action') {
        setStatus('error');
        setResultMsg(data.message || 'Delta already neutral');
      } else {
        setStatus('error');
        setResultMsg(data.message || 'Order failed');
      }
    } catch (err) {
      setStatus('error');
      setResultMsg(err.message || 'Network error');
    }
  };

  return (
    <Dialog
      open={open}
      onClose={status === 'loading' ? undefined : onClose}
      PaperProps={{ sx: MODAL_STYLES }}
      BackdropProps={{ sx: { backdropFilter: 'blur(4px)', bgcolor: 'rgba(0,0,0,0.7)' } }}
    >
      {/* Header */}
      <DialogTitle
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid #1e2d45', pb: 1.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <BoltIcon sx={{ color: confirmColor }} />
          <Typography fontWeight="bold" fontSize="1rem">Delta Hedge Order</Typography>
        </Box>
        <IconButton
          size="small"
          onClick={onClose}
          disabled={status === 'loading'}
          sx={{ color: '#94a3b8' }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 2, pb: 1 }}>
        {/* --- Section 1: Current Delta Card --- */}
        <Box sx={{
          p: 2, mb: 2, bgcolor: '#1a2235',
          border: '1px solid #2d3f5a', borderRadius: 2,
        }}>
          <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 0.5 }}>
            Current Portfolio Delta
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5 }}>
            <Typography
              variant="h5"
              fontWeight="bold"
              sx={{ color: isLong ? '#10b981' : '#ef4444' }}
            >
              {isLong ? '+' : '-'}{absDelta.toFixed(4)} BTC
            </Typography>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>{usdNotional}</Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={barPct}
            sx={{
              height: 6, borderRadius: 3, mb: 0.5,
              bgcolor: '#1e2d45',
              '& .MuiLinearProgress-bar': { bgcolor: confirmColor },
            }}
          />
          <Typography variant="caption" sx={{ color: '#64748b' }}>
            {isLong ? 'Long Biased' : 'Short Biased'}
          </Typography>
        </Box>

        {/* --- Section 2: Proposed Action --- */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', mb: 1, fontWeight: 600 }}>
            Proposed Hedge Action
          </Typography>
          {[
            { label: 'Direction',  value: `${action} BTC-PERP` },
            { label: 'Size',       value: `${absDelta.toFixed(4)} contracts` },
            { label: 'Post-Delta', value: '~0.0000' },
          ].map(({ label, value }) => (
            <Box key={label} sx={{
              display: 'flex', justifyContent: 'space-between',
              py: 0.5, borderBottom: '1px solid #1e2d45',
            }}>
              <Typography variant="caption" sx={{ color: '#64748b' }}>{label}</Typography>
              <Typography variant="caption" fontWeight="bold" sx={{ color: '#e2e8f0' }}>{value}</Typography>
            </Box>
          ))}
        </Box>

        {/* --- Section 3: Order Type Toggle --- */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', mb: 1, fontWeight: 600 }}>
            Order Type
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {['market', 'smart'].map((ot) => (
              <Button
                key={ot}
                size="small"
                onClick={() => setOrderType(ot)}
                sx={{
                  flex: 1,
                  textTransform: 'capitalize',
                  bgcolor: orderType === ot ? '#e2e8f0' : '#1a2235',
                  color: orderType === ot ? '#0f1623' : '#94a3b8',
                  border: `1px solid ${orderType === ot ? '#e2e8f0' : '#2d3f5a'}`,
                  fontWeight: orderType === ot ? 'bold' : 'normal',
                  '&:hover': { bgcolor: orderType === ot ? '#cbd5e1' : '#243045' },
                }}
              >
                {ot.charAt(0).toUpperCase() + ot.slice(1)}
              </Button>
            ))}
          </Box>
        </Box>

        {/* Smart Offset — only when Smart selected */}
        {orderType === 'smart' && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', mb: 0.5 }}>
              Smart Offset %
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                type="number"
                value={smartOffset}
                onChange={(e) => setSmartOffset(parseFloat(e.target.value) || 0.05)}
                inputProps={{ min: 0.01, max: 5.0, step: 0.01 }}
                size="small"
                sx={{
                  width: 100,
                  '& .MuiInputBase-root': { bgcolor: '#1a2235', color: '#e2e8f0' },
                  '& .MuiOutlinedInput-notchedOutline': { borderColor: '#2d3f5a' },
                }}
              />
              <Typography variant="caption" sx={{ color: '#64748b' }}>%</Typography>
            </Box>
          </Box>
        )}

        {/* Warning */}
        <Typography variant="caption" sx={{ color: '#f59e0b', display: 'block', mb: 1 }}>
          ⚠️ This places a BTC-PERP position. Manage the perp separately after hedging.
        </Typography>

        {/* Loading */}
        {status === 'loading' && <LinearProgress sx={{ borderRadius: 1, mb: 1 }} />}

        {/* Result states */}
        {status === 'success' && (
          <Alert severity="success" sx={{ bgcolor: 'rgba(34,197,94,0.15)', color: '#22c55e', border: '1px solid #22c55e', py: 0.5 }}>
            ✅ Order placed! ID: #{orderId}
          </Alert>
        )}
        {status === 'error' && (
          <Alert severity="error" sx={{ bgcolor: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid #ef4444', py: 0.5 }}>
            ❌ Failed: {resultMsg}
          </Alert>
        )}
      </DialogContent>

      {/* Footer buttons — hidden after success */}
      {(status === 'idle' || status === 'loading') && (
        <DialogActions sx={{ borderTop: '1px solid #1e2d45', px: 2, pb: 2, gap: 1 }}>
          <Button
            onClick={onClose}
            disabled={status === 'loading'}
            sx={{
              flex: 1,
              color: '#94a3b8',
              border: '1px solid #2d3f5a',
              '&:hover': { bgcolor: '#1a2235' },
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={status === 'loading'}
            sx={{
              flex: 2,
              bgcolor: confirmColor,
              color: '#fff',
              fontWeight: 'bold',
              '&:hover': { bgcolor: confirmHover },
              '&.Mui-disabled': { bgcolor: '#374151', color: '#64748b' },
            }}
          >
            {status === 'loading'
              ? 'Placing...'
              : `⚡ Confirm ${isLong ? 'SHORT' : 'LONG'} ${absDelta.toFixed(2)} BTC-PERP`}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
