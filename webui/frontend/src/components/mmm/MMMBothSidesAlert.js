/**
 * MMMBothSidesAlert — Money Mind & Method
 *
 * Full-screen modal for when both CE and PE premiums exceed triggers
 * simultaneously (§8 Both-Sides-Up).
 *
 * Shows CE and PE details with excess, and action buttons:
 * - Hedge CE → Sell PE: Treat CE as aggressor, sell PE to cover CE's loss
 * - Hedge PE → Sell CE: Treat PE as aggressor, sell CE to cover PE's loss
 * - Resume (Update Triggers): Accept current premiums as new baseline, resume monitoring
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §8 (Both-Sides-Up)
 * Backend decisions: 'adjust_ce' | 'adjust_pe' | 'skip'
 *
 * Created: February 15, 2026
 * Updated: February 16, 2026 — Fixed action mapping to backend API decisions,
 *          added informative descriptions for each option
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Grid,
  Chip,
  Alert,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  Warning as WarningIcon,
  TrendingDown as HedgeIcon,
  PlayArrow as ResumeIcon,
} from '@mui/icons-material';

function PremiumDetail({ label, color, premium, trigger, excess }) {
  const excessPct = trigger ? ((excess / trigger) * 100).toFixed(1) : '0.0';
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        border: '1px solid',
        borderColor: `${color}40`,
        bgcolor: `${color}08`,
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, color, mb: 1 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Current</Typography>
          <Typography variant="h6" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
            {Number(premium || 0).toFixed(1)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Trigger</Typography>
          <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
            {Number(trigger || 0).toFixed(1)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Excess</Typography>
          <Typography
            variant="h6"
            sx={{ fontFamily: 'monospace', fontWeight: 700, color: '#f44336' }}
          >
            +{Number(excess || 0).toFixed(1)}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            ({excessPct}%)
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export default function MMMBothSidesAlert({
  open,
  alertData,
  sessionId,
  onAction,
  onClose,
}) {
  const [loading, setLoading] = useState(false);

  /**
   * Submit decision to dashboard handler.
   * Maps to backend endpoint: 'adjust_ce' | 'adjust_pe' | 'skip'
   */
  const handleDecision = async (decision) => {
    setLoading(true);
    try {
      // onAction expects (decision_string, params={})
      await onAction?.(decision, {});
      onClose?.();
    } catch (err) {
      console.error('Both-sides decision failed:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!alertData) return null;

  // Determine which side has higher excess (suggest hedging the bigger mover)
  const ceExcess = alertData.ce_excess || 0;
  const peExcess = alertData.pe_excess || 0;
  const suggestedSide = ceExcess >= peExcess ? 'CE' : 'PE';

  return (
    <Dialog
      open={open}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          border: '2px solid #f44336',
          bgcolor: 'background.paper',
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, bgcolor: 'rgba(244,67,54,0.08)' }}>
        <WarningIcon color="error" />
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          ⚠️ Both Sides Triggered (§8)
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ pt: 2 }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            Both CE and PE premiums have exceeded their triggers simultaneously.
          </Typography>
          <Typography variant="caption" color="text.secondary">
            The algorithm is <strong>paused</strong> — it cannot auto-adjust because selling either
            side would increase directional risk. This typically happens during IV spikes or sharp
            whipsaws. Choose how to proceed:
          </Typography>
        </Alert>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6}>
            <PremiumDetail
              label="CE Side"
              color="#2196f3"
              premium={alertData.ce_premium}
              trigger={alertData.ce_trigger}
              excess={alertData.ce_excess}
            />
          </Grid>
          <Grid item xs={6}>
            <PremiumDetail
              label="PE Side"
              color="#9c27b0"
              premium={alertData.pe_premium}
              trigger={alertData.pe_trigger}
              excess={alertData.pe_excess}
            />
          </Grid>
        </Grid>

        {/* Suggestion */}
        <Box sx={{ mb: 2, p: 1.5, borderRadius: 1, bgcolor: 'rgba(33,150,243,0.06)', border: '1px dashed rgba(33,150,243,0.3)' }}>
          <Typography variant="caption" color="text.secondary">
            💡 <strong>{suggestedSide}</strong> has the larger excess ({suggestedSide === 'CE'
              ? `+${ceExcess.toFixed(1)}` : `+${peExcess.toFixed(1)}`}). Consider hedging {suggestedSide}
            by selling the opposite side, unless you believe {suggestedSide} will decay quickly.
          </Typography>
        </Box>

        <Divider sx={{ mb: 2 }} />

        {/* Decision buttons with full explanations */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {/* Hedge CE (adjust_ce) */}
          <Tooltip
            title="Treats CE as the aggressor. The algo will calculate the loss from CE's premium exceeding its trigger and sell PE lots to cover that loss. Most effective when BTC is rallying (CE premiums rising)."
            placement="left"
            arrow
          >
            <Button
              fullWidth
              variant={ceExcess >= peExcess ? 'contained' : 'outlined'}
              color="primary"
              startIcon={<HedgeIcon />}
              onClick={() => handleDecision('adjust_ce')}
              disabled={loading}
              sx={{ py: 1.5, justifyContent: 'flex-start', textAlign: 'left' }}
            >
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Hedge CE → Sell PE
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  CE is the threat — sell more PE to cover CE's excess loss
                </Typography>
              </Box>
            </Button>
          </Tooltip>

          {/* Hedge PE (adjust_pe) */}
          <Tooltip
            title="Treats PE as the aggressor. The algo will calculate the loss from PE's premium exceeding its trigger and sell CE lots to cover that loss. Most effective when BTC is falling (PE premiums rising)."
            placement="left"
            arrow
          >
            <Button
              fullWidth
              variant={peExcess > ceExcess ? 'contained' : 'outlined'}
              color="secondary"
              startIcon={<HedgeIcon />}
              onClick={() => handleDecision('adjust_pe')}
              disabled={loading}
              sx={{ py: 1.5, justifyContent: 'flex-start', textAlign: 'left' }}
            >
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Hedge PE → Sell CE
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  PE is the threat — sell more CE to cover PE's excess loss
                </Typography>
              </Box>
            </Button>
          </Tooltip>

          {/* Resume / Skip (skip) */}
          <Tooltip
            title="Accept both current premiums as new baselines. Updates both CE and PE trigger snapshots to current values and resumes monitoring. No adjustment is executed. Use this if you believe premiums will decay (IV crush)."
            placement="left"
            arrow
          >
            <Button
              fullWidth
              variant="outlined"
              color="success"
              startIcon={<ResumeIcon />}
              onClick={() => handleDecision('skip')}
              disabled={loading}
              sx={{ py: 1.5, justifyContent: 'flex-start', textAlign: 'left' }}
            >
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Resume — Update Triggers
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Accept current levels as new baseline, resume monitoring (no adjustment)
                </Typography>
              </Box>
            </Button>
          </Tooltip>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
          Session: {sessionId}
        </Typography>
      </DialogActions>
    </Dialog>
  );
}
