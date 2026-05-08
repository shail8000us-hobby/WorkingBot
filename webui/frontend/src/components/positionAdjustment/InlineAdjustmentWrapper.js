/**
 * InlineAdjustmentWrapper
 * =======================
 * Orchestrates the inline position adjustment mode that appears alongside
 * the payoff graph. Manages proposed trades, computes combined payoff via
 * usePayoffCalculation, and renders the options chain panel + metrics strip.
 *
 * This component wraps around the payoff graph area to provide a side-by-side
 * layout: [Payoff Graph ~60%] + [Options Chain ~40%]
 *
 * Created: May 7, 2026
 */

import React, { useState, useCallback, useMemo, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  IconButton,
  Divider,
  Collapse,
  Tooltip,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Close as CloseIcon,
  PlayArrow as ExecuteIcon,
  DeleteSweep as ClearIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  SwapHoriz as SwapIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material';
import SlidingOptionsChainPanel from './SlidingOptionsChainPanel';
import AdjustmentReviewDialog from './AdjustmentReviewDialog';
import { usePayoffCalculation } from './hooks/usePayoffCalculation';
import { getContractMultiplier } from '../../utils/constants';

// ============================================================================
// COLORS
// ============================================================================
const COLORS = {
  bg: 'rgba(15, 23, 42, 0.95)',
  cardBg: 'rgba(30, 41, 59, 0.9)',
  border: 'rgba(71, 85, 105, 0.4)',
  text: '#e2e8f0',
  textSecondary: '#94a3b8',
  profit: '#10b981',
  loss: '#ef4444',
  primary: '#3b82f6',
  cyan: '#22d3ee',
  teal: '#00e5ff',
  warning: '#f59e0b',
  purple: '#a855f7',
};

/**
 * Parse symbol for display
 */
const parseSymbolForDisplay = (symbol) => {
  if (!symbol) return '';
  const parts = symbol.split('-');
  const type = parts[0] === 'C' ? 'CE' : 'PE';
  const strike = parseInt(parts[2]) || 0;
  const expiry = parts[3] || '';
  const day = expiry.slice(0, 2);
  const month = parseInt(expiry.slice(2, 4));
  const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${parseInt(day)} ${months[month] || ''} ${strike.toLocaleString()} ${type}`;
};

// ============================================================================
// PROPOSED TRADES STRIP
// ============================================================================
const ProposedTradesStrip = ({ trades, onRemove, onClearAll }) => {
  if (!trades || trades.length === 0) return null;

  return (
    <Box sx={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: 0.75,
      alignItems: 'center',
      p: 1,
      borderTop: `1px solid ${COLORS.border}`,
      bgcolor: alpha('#0f172a', 0.5),
    }}>
      <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 700, mr: 0.5 }}>
        Proposed:
      </Typography>
      {trades.map((trade, idx) => {
        const isBuy = trade.side === 'buy';
        const color = isBuy ? COLORS.profit : COLORS.loss;
        return (
          <Chip
            key={idx}
            label={`${isBuy ? 'B' : 'S'} ${trade.quantity || 1}× ${parseSymbolForDisplay(trade.symbol)}`}
            size="small"
            onDelete={() => onRemove(trade)}
            sx={{
              height: 24,
              fontSize: '0.7rem',
              fontWeight: 700,
              bgcolor: alpha(color, 0.12),
              color,
              border: `1px solid ${alpha(color, 0.35)}`,
              '& .MuiChip-deleteIcon': {
                color: alpha(color, 0.6),
                fontSize: 16,
                '&:hover': { color },
              },
            }}
          />
        );
      })}
      {trades.length > 1 && (
        <Chip
          label="Clear All"
          size="small"
          onClick={onClearAll}
          sx={{
            height: 22,
            fontSize: '0.65rem',
            color: COLORS.textSecondary,
            borderColor: COLORS.border,
            cursor: 'pointer',
            '&:hover': { bgcolor: alpha('#ef4444', 0.1), color: COLORS.loss },
          }}
          variant="outlined"
        />
      )}
    </Box>
  );
};

// ============================================================================
// METRICS DIFF STRIP
// ============================================================================
const MetricsDiffStrip = ({ metrics, hasProposedTrades }) => {
  if (!metrics || !hasProposedTrades) return null;

  const { current, combined, change, raw } = metrics;

  const MetricItem = ({ label, currentVal, combinedVal, changeVal, isGoodWhenPositive = true }) => {
    if (!changeVal || changeVal === '0' || changeVal === '$0.00' || changeVal === '+$0.00' || changeVal === '+0.000') return null;

    const isPositiveChange = changeVal?.startsWith('+');
    const isGood = isGoodWhenPositive ? isPositiveChange : !isPositiveChange;
    const changeColor = isGood ? COLORS.profit : COLORS.loss;

    return (
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        px: 1.2,
        py: 0.5,
        borderRadius: 1,
        bgcolor: alpha(changeColor, 0.08),
        border: `1px solid ${alpha(changeColor, 0.25)}`,
      }}>
        <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 700, fontSize: '0.62rem' }}>
          {label}
        </Typography>
        <Typography variant="caption" sx={{
          color: changeColor,
          fontWeight: 900,
          fontSize: '0.72rem',
          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
        }}>
          {changeVal}
        </Typography>
      </Box>
    );
  };

  // Net debit/credit for proposed trades
  const netPremium = raw?.combined?.netPremium != null
    ? (raw.combined.netPremium - (raw.current?.netPremium || 0))
    : null;
  const netLabel = netPremium != null
    ? (netPremium >= 0 ? `Net Credit: +$${Math.abs(netPremium).toFixed(2)}` : `Net Debit: -$${Math.abs(netPremium).toFixed(2)}`)
    : null;
  const netColor = netPremium >= 0 ? COLORS.profit : COLORS.loss;

  return (
    <Box sx={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: 0.75,
      alignItems: 'center',
      p: 1,
      borderTop: `1px solid ${COLORS.border}`,
      bgcolor: alpha('#0f172a', 0.4),
    }}>
      <Typography variant="caption" sx={{
        color: COLORS.cyan,
        fontWeight: 900,
        fontSize: '0.65rem',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        mr: 0.5,
      }}>
        Impact:
      </Typography>

      <MetricItem label="ΔMaxProfit" changeVal={change?.maxProfit} isGoodWhenPositive={true} />
      <MetricItem label="ΔMaxLoss" changeVal={change?.maxLoss} isGoodWhenPositive={false} />
      <MetricItem label="ΔDelta" changeVal={change?.netDelta} isGoodWhenPositive={true} />
      <MetricItem label="ΔTheta" changeVal={change?.netTheta} isGoodWhenPositive={true} />
      <MetricItem label="ΔPoP" changeVal={change?.pop} isGoodWhenPositive={true} />

      {netLabel && (
        <Box sx={{
          px: 1.2,
          py: 0.5,
          borderRadius: 1,
          bgcolor: alpha(netColor, 0.1),
          border: `1px solid ${alpha(netColor, 0.3)}`,
        }}>
          <Typography variant="caption" sx={{
            color: netColor,
            fontWeight: 900,
            fontSize: '0.72rem',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
          }}>
            {netLabel}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function InlineAdjustmentWrapper({
  // Adjustment mode state
  active,
  onClose,
  // Position data from OptionsPanel
  currentPositions = [],
  spotPrice,
  underlying = 'BTC',
  // Callback to refresh positions after execution
  onExecuteComplete,
  // Children = the payoff diagram component (rendered in the left panel)
  children,
}) {
  // Proposed trades state
  const [proposedTrades, setProposedTrades] = useState([]);
  // Review dialog
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  // Selected expiry for chain
  const [selectedExpiry, setSelectedExpiry] = useState('');

  // Derive underlying from positions if available
  const derivedUnderlying = useMemo(() => {
    if (currentPositions?.length > 0) {
      const parts = currentPositions[0]?.product_symbol?.split('-');
      return parts?.[1] || underlying;
    }
    return underlying;
  }, [currentPositions, underlying]);

  // Calculate combined payoff using the existing hook
  const payoffData = usePayoffCalculation(
    currentPositions,
    proposedTrades,
    spotPrice,
    { enabled: active && currentPositions.length > 0 }
  );

  // Handle adding a trade from the chain
  const handleAddTrade = useCallback((trade) => {
    setProposedTrades(prev => [...prev, trade]);
  }, []);

  // Handle removing a trade
  const handleRemoveTrade = useCallback((trade) => {
    setProposedTrades(prev => prev.filter(t =>
      !(t.strike === trade.strike && t.type === trade.type && t.side === trade.side)
    ));
  }, []);

  // Clear all proposed trades
  const handleClearAll = useCallback(() => {
    setProposedTrades([]);
  }, []);

  // Handle close — clear trades and exit
  const handleClose = useCallback(() => {
    setProposedTrades([]);
    setSelectedExpiry('');
    onClose?.();
  }, [onClose]);

  // Handle execute complete
  const handleExecuteComplete = useCallback(() => {
    setReviewDialogOpen(false);
    setProposedTrades([]);
    setSelectedExpiry('');
    onClose?.();
    onExecuteComplete?.();
  }, [onClose, onExecuteComplete]);

  // Build adjustment overlay for the payoff diagram.
  // Non-null as soon as active=true so the button label and line-muting trigger immediately.
  // proposedTrades is passed through so OptionsPayoffDiagram can compute the overlay
  // using the same native sealed formula (no scale mismatch with the existing chart).
  const adjustmentOverlay = useMemo(() => {
    if (!active) return null;
    return {
      proposedTrades,
      hasProposedTrades: proposedTrades.length > 0,
      metrics: proposedTrades.length > 0 ? payoffData?.formattedMetrics : null,
      breakevens: proposedTrades.length > 0 ? (payoffData?.combinedMetrics?.breakevens || []) : [],
    };
  }, [active, proposedTrades, payoffData]);

  // When not active, render children normally (no adjustment mode).
  // Children is a render-prop function — call it with null, don't return the function itself.
  if (!active) {
    return typeof children === 'function' ? children(null) : children;
  }

  return (
    <Box sx={{ position: 'relative' }}>
      {/* Adjustment Mode Banner */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        p: 1,
        mb: 1,
        borderRadius: 2,
        bgcolor: alpha(COLORS.cyan, 0.08),
        border: `1px solid ${alpha(COLORS.cyan, 0.3)}`,
        boxShadow: `0 0 12px ${alpha(COLORS.cyan, 0.12)}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label="ADJUSTMENT MODE"
            size="small"
            sx={{
              height: 24,
              fontWeight: 900,
              fontSize: '0.7rem',
              letterSpacing: '0.06em',
              bgcolor: alpha(COLORS.cyan, 0.15),
              color: COLORS.cyan,
              border: `1px solid ${alpha(COLORS.cyan, 0.4)}`,
            }}
          />
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
            Select trades from the option chain → see impact on your payoff graph
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
          {proposedTrades.length > 0 && (
            <>
              <Button
                size="small"
                variant="outlined"
                onClick={handleClearAll}
                startIcon={<ClearIcon sx={{ fontSize: 14 }} />}
                sx={{
                  color: COLORS.textSecondary,
                  borderColor: COLORS.border,
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  py: 0.3,
                  px: 1,
                  borderRadius: 999,
                  '&:hover': { borderColor: COLORS.loss, color: COLORS.loss },
                }}
              >
                Clear
              </Button>
              <Button
                size="small"
                variant="contained"
                onClick={() => setReviewDialogOpen(true)}
                startIcon={<ExecuteIcon sx={{ fontSize: 14 }} />}
                sx={{
                  bgcolor: alpha(COLORS.profit, 0.85),
                  fontSize: '0.7rem',
                  fontWeight: 900,
                  textTransform: 'uppercase',
                  py: 0.3,
                  px: 1.5,
                  borderRadius: 999,
                  boxShadow: `0 0 12px ${alpha(COLORS.profit, 0.3)}`,
                  '&:hover': { bgcolor: COLORS.profit },
                }}
              >
                Review & Execute ({proposedTrades.length})
              </Button>
            </>
          )}
          <Tooltip title="Exit adjustment mode" arrow>
            <IconButton
              size="small"
              onClick={handleClose}
              sx={{
                color: COLORS.textSecondary,
                border: `1px solid ${COLORS.border}`,
                borderRadius: 1,
                width: 28,
                height: 28,
                '&:hover': { color: COLORS.text, borderColor: COLORS.text },
              }}
            >
              <CloseIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Side-by-side Layout: Payoff Graph + Option Chain */}
      <Box sx={{
        display: 'flex',
        gap: 1.5,
        alignItems: 'stretch',
      }}>
        {/* LEFT: Payoff Graph Area (~60%) */}
        <Box sx={{ flex: '1 1 60%', minWidth: 0 }}>
          {/* Render the payoff diagram (passed as children) with overlay data injected */}
          {typeof children === 'function'
            ? children(adjustmentOverlay)
            : children
          }

          {/* Proposed Trades Strip — below the graph */}
          <ProposedTradesStrip
            trades={proposedTrades}
            onRemove={handleRemoveTrade}
            onClearAll={handleClearAll}
          />

          {/* Metrics Diff Strip — shows impact of proposed trades */}
          <MetricsDiffStrip
            metrics={payoffData?.formattedMetrics}
            hasProposedTrades={proposedTrades.length > 0}
          />
        </Box>

        {/* RIGHT: Options Chain Panel (~40%) */}
        <Box sx={{
          flex: '0 0 400px',
          maxWidth: 420,
          minWidth: 360,
          borderRadius: 2,
          overflow: 'hidden',
          border: `1px solid ${COLORS.border}`,
          bgcolor: COLORS.bg,
          display: 'flex',
          flexDirection: 'column',
          maxHeight: 700,
        }}>
          <SlidingOptionsChainPanel
            open={true}
            onClose={handleClose}
            underlying={derivedUnderlying}
            spotPrice={spotPrice}
            proposedTrades={proposedTrades}
            onAddTrade={handleAddTrade}
            onRemoveTrade={handleRemoveTrade}
            selectedExpiry={selectedExpiry}
            onExpiryChange={setSelectedExpiry}
            onReviewExecute={() => setReviewDialogOpen(true)}
            inline={true}
          />
        </Box>
      </Box>

      {/* Review & Execute Dialog */}
      <AdjustmentReviewDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        proposedTrades={proposedTrades}
        currentPositions={currentPositions}
        spotPrice={spotPrice}
        underlying={derivedUnderlying}
        onExecuteComplete={handleExecuteComplete}
      />
    </Box>
  );
}
