/**
 * Position Adjustment Panel
 * =========================
 * Main container for the position adjustment system.
 * Provides Sensibull-like workflow for adjusting options positions.
 * 
 * Features:
 * - Slide-out panel from OptionsPanel
 * - Options chain with B/S selection
 * - Real-time payoff comparison chart
 * - Before/After metrics comparison
 * - Autoloop execution integration
 * 
 * Created: January 31, 2026
 */

import React, { useState, useCallback, useMemo, useRef } from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Button,
  Divider,
  Alert,
  Chip,
  Paper,
  Tabs,
  Tab,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  Refresh as RefreshIcon,
  TuneRounded as AdjustIcon,
  ShowChart as ChartIcon,
  TableChart as TableIcon,
} from '@mui/icons-material';

import AdjustmentChainTable from './AdjustmentChainTable';
import AdjustmentPayoffChart from './AdjustmentPayoffChart';
import AdjustmentMetricsPanel from './AdjustmentMetricsPanel';
import ProposedTradesTable from './ProposedTradesTable';
import AdjustmentReviewDialog from './AdjustmentReviewDialog';
import AdjustmentExecutionProgress from './AdjustmentExecutionProgress';
import { usePayoffCalculation } from './hooks/usePayoffCalculation';
import api from '../../utils/apiShim';

// Panel width
const PANEL_WIDTH = 1200;

/**
 * PositionAdjustmentPanel Component
 */
export default function PositionAdjustmentPanel({
  open,
  onClose,
  currentPositions = [],
  spotPrice,
  underlying = 'BTC',
  onExecuteComplete,
}) {
  // Debug logging
  React.useEffect(() => {
    console.log('[PositionAdjustmentPanel] Render state:', {
      open,
      currentPositions: currentPositions?.length,
      spotPrice,
      underlying,
    });
  }, [open, currentPositions, spotPrice, underlying]);

  // State
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [proposedTrades, setProposedTrades] = useState([]);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState({});
  const [executionError, setExecutionError] = useState(null);
  const [currentRound, setCurrentRound] = useState(0);
  const [totalRounds, setTotalRounds] = useState(1);
  const [executionComplete, setExecutionComplete] = useState(false);
  const [activeTab, setActiveTab] = useState(0); // 0 = Chart view, 1 = Table view
  
  // Ref for stopping execution
  const stopExecutionRef = useRef(false);

  // Calculate payoff using hook
  const payoffData = usePayoffCalculation(
    currentPositions,
    proposedTrades,
    spotPrice,
    { enabled: open }
  );

  // Derive underlying from current positions if available
  const derivedUnderlying = useMemo(() => {
    if (currentPositions && currentPositions.length > 0) {
      const firstSymbol = currentPositions[0]?.product_symbol || '';
      const parts = firstSymbol.split('-');
      if (parts.length >= 2) {
        return parts[1]; // BTC, ETH
      }
    }
    return underlying;
  }, [currentPositions, underlying]);

  // Handle adding a proposed trade
  const handleAddTrade = useCallback((trade) => {
    setProposedTrades((prev) => [...prev, trade]);
    setExecutionComplete(false);
    setExecutionError(null);
  }, []);

  // Handle removing a proposed trade
  const handleRemoveTrade = useCallback((trade) => {
    setProposedTrades((prev) => 
      prev.filter(t => 
        !(t.strike === trade.strike && t.type === trade.type && t.side === trade.side)
      )
    );
  }, []);

  // Handle updating trade quantity
  const handleUpdateTradeQty = useCallback((strike, type, side, newQty) => {
    setProposedTrades((prev) =>
      prev.map(t => {
        if (t.strike === strike && t.type === type && t.side === side) {
          return { ...t, quantity: newQty };
        }
        return t;
      })
    );
  }, []);

  // Handle clearing all proposed trades
  const handleClearAll = useCallback(() => {
    setProposedTrades([]);
    setExecutionComplete(false);
    setExecutionError(null);
    setExecutionProgress({});
  }, []);

  // Handle expiry change
  const handleExpiryChange = useCallback((expiry) => {
    setSelectedExpiry(expiry);
    // Clear proposed trades when expiry changes
    setProposedTrades([]);
  }, []);

  // Prepare orders for batch execution
  const prepareOrders = useCallback(() => {
    return proposedTrades.map((trade) => ({
      symbol: trade.symbol,
      side: trade.side,
      size: trade.quantity || 1,
    }));
  }, [proposedTrades]);

  // Execute trades via batch API
  const handleExecute = useCallback(async ({ trades, orderType, loopRounds }) => {
    if (executing || trades.length === 0) return;

    console.log('[PositionAdjustment] Starting execution:', { trades, orderType, loopRounds });

    setExecuting(true);
    setExecutionError(null);
    setExecutionProgress({});
    setCurrentRound(0);
    setTotalRounds(loopRounds);
    setExecutionComplete(false);
    stopExecutionRef.current = false;

    const orders = trades.map((trade) => ({
      symbol: trade.symbol,
      side: trade.side,
      size: trade.quantity || 1,
    }));

    try {
      for (let round = 1; round <= loopRounds; round++) {
        if (stopExecutionRef.current) {
          setExecutionError(`Stopped by user at round ${round - 1}/${loopRounds}`);
          break;
        }

        setCurrentRound(round);

        // Initialize progress for this round
        const roundProgress = {};
        orders.forEach((order) => {
          roundProgress[order.symbol] = { 
            status: 'placing', 
            filled: false,
            size: order.size,
          };
        });
        setExecutionProgress(roundProgress);

        // Place all orders
        const response = await api.post('/api/options/batch_add', {
          orders,
          order_preference: orderType,
          confirm: true,
        });

        if (!response.data.success) {
          throw new Error(response.data.error || 'Batch order failed');
        }

        const results = response.data.results || [];
        console.log('[PositionAdjustment] Batch results:', results);

        // Update progress based on results
        const updatedProgress = { ...roundProgress };
        const pendingOrders = [];

        results.forEach((result) => {
          const execType = result.execution_type || '';
          const isFilled = ['market', 'market_fallback', 'limit_filled'].includes(execType) || !result.order_id;

          updatedProgress[result.symbol] = {
            status: result.success ? (isFilled ? 'filled' : 'pending') : 'failed',
            filled: isFilled,
            fillPrice: result.fill_price,
            orderId: result.order_id,
            error: result.error,
            size: result.size,
          };

          if (result.success && !isFilled && result.order_id) {
            pendingOrders.push(result);
          }
        });
        setExecutionProgress(updatedProgress);

        // Poll for pending orders
        if (pendingOrders.length > 0) {
          console.log('[PositionAdjustment] Polling for pending orders:', pendingOrders.length);
          const orderIds = pendingOrders.map((r) => r.order_id);
          let allFilled = false;
          let pollCount = 0;
          const maxPolls = 30; // 60 seconds max

          while (!allFilled && !stopExecutionRef.current && pollCount < maxPolls) {
            pollCount++;
            await new Promise((resolve) => setTimeout(resolve, 2000));

            try {
              const statusResponse = await api.post('/api/options/batch_order_status', {
                order_ids: orderIds,
              });

              if (!statusResponse.data.success) {
                console.warn('[PositionAdjustment] Status poll failed:', statusResponse.data.error);
                continue;
              }

              const statuses = statusResponse.data.orders || [];
              const progressUpdate = { ...updatedProgress };

              statuses.forEach((status) => {
                const matching = pendingOrders.find((o) => o.order_id === status.order_id);
                if (matching) {
                  const isFilled = status.state === 'filled' || status.state === 'closed';
                  progressUpdate[matching.symbol] = {
                    ...progressUpdate[matching.symbol],
                    status: isFilled ? 'filled' : 'pending',
                    filled: isFilled,
                    fillPrice: status.fill_price || progressUpdate[matching.symbol].fillPrice,
                  };
                }
              });

              setExecutionProgress(progressUpdate);

              const filledCount = Object.values(progressUpdate).filter((p) => p.filled).length;
              allFilled = filledCount === orders.length;

              console.log(`[PositionAdjustment] Poll ${pollCount}: ${filledCount}/${orders.length} filled`);
            } catch (pollError) {
              console.error('[PositionAdjustment] Poll error:', pollError);
            }
          }

          if (!allFilled && !stopExecutionRef.current) {
            console.warn('[PositionAdjustment] Not all orders filled after polling');
          }
        }

        // Delay between rounds
        if (round < loopRounds && !stopExecutionRef.current) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }

      // Execution complete
      if (!stopExecutionRef.current) {
        setExecutionComplete(true);
        console.log('[PositionAdjustment] Execution complete');
      }

    } catch (error) {
      console.error('[PositionAdjustment] Execution error:', error);
      setExecutionError(error.message || 'Execution failed');
    } finally {
      setExecuting(false);
      stopExecutionRef.current = false;
    }
  }, [executing]);

  // Handle stopping execution
  const handleStopExecution = useCallback(() => {
    stopExecutionRef.current = true;
  }, []);

  // Handle close after execution
  const handleClose = useCallback(() => {
    if (executing) {
      // Don't close while executing
      return;
    }

    if (executionComplete) {
      // Refresh positions and close
      onExecuteComplete?.();
    }

    // Reset state
    setProposedTrades([]);
    setExecutionProgress({});
    setExecutionError(null);
    setExecutionComplete(false);
    setReviewDialogOpen(false);
    onClose?.();
  }, [executing, executionComplete, onExecuteComplete, onClose]);

  return (
    <>
      <Drawer
        anchor="right"
        open={open}
        onClose={executing ? undefined : handleClose}
        PaperProps={{
          sx: {
            width: PANEL_WIDTH,
            maxWidth: '100vw',
            backgroundColor: '#1a1a2e',
            backgroundImage: 'none',
          },
        }}
      >
        {/* Header */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AdjustIcon sx={{ color: '#2196f3' }} />
            <Typography variant="h6">
              Position Adjustment
            </Typography>
            {derivedUnderlying && (
              <Chip label={derivedUnderlying} size="small" color="primary" variant="outlined" />
            )}
            {proposedTrades.length > 0 && (
              <Chip
                label={`${proposedTrades.length} trade${proposedTrades.length !== 1 ? 's' : ''} selected`}
                size="small"
                color="success"
              />
            )}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {proposedTrades.length > 0 && !executing && (
              <>
                <Button
                  size="small"
                  color="error"
                  startIcon={<ClearIcon />}
                  onClick={handleClearAll}
                >
                  Clear All
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<ExecuteIcon />}
                  onClick={() => setReviewDialogOpen(true)}
                >
                  Review & Execute
                </Button>
              </>
            )}
            
            {!executing && (
              <IconButton onClick={handleClose}>
                <CloseIcon />
              </IconButton>
            )}
          </Box>
        </Box>

        {/* Main content */}
        <Box sx={{ 
          flex: 1, 
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          p: 2,
        }}>
          {/* Execution progress (shown when executing or complete) */}
          {(executing || executionComplete || executionError) && (
            <Paper sx={{ p: 2, mb: 2, backgroundColor: 'rgba(255,255,255,0.02)' }}>
              <AdjustmentExecutionProgress
                orders={prepareOrders()}
                progress={executionProgress}
                currentRound={currentRound}
                totalRounds={totalRounds}
                error={executionError}
                onCancel={handleStopExecution}
                isRunning={executing}
                isComplete={executionComplete}
              />
            </Paper>
          )}

          {/* Main layout: Chain + Payoff/Metrics */}
          {!executionComplete && (
            <Box sx={{ 
              display: 'flex', 
              gap: 2, 
              flex: 1,
              overflow: 'hidden',
            }}>
              {/* Left: Options Chain */}
              <Paper sx={{ 
                flex: 1, 
                minWidth: 0,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                p: 2,
                backgroundColor: 'rgba(255,255,255,0.02)',
              }}>
                <AdjustmentChainTable
                  underlying={derivedUnderlying}
                  selectedExpiry={selectedExpiry}
                  onExpiryChange={handleExpiryChange}
                  proposedTrades={proposedTrades}
                  onAddTrade={handleAddTrade}
                  onRemoveTrade={handleRemoveTrade}
                  onUpdateTradeQty={handleUpdateTradeQty}
                  spotPrice={spotPrice}
                  loading={false}
                  isOpen={open}
                />
              </Paper>

              {/* Right: Payoff + Metrics */}
              <Box sx={{ 
                width: 450, 
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                overflow: 'auto',
              }}>
                {/* Payoff Chart */}
                <Paper sx={{ 
                  p: 2, 
                  backgroundColor: 'rgba(255,255,255,0.02)',
                }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    Payoff Comparison
                  </Typography>
                  <AdjustmentPayoffChart
                    chartData={payoffData.chartData}
                    spotPrice={spotPrice}
                    currentBreakevens={payoffData.currentMetrics?.breakevens || []}
                    combinedBreakevens={payoffData.combinedMetrics?.breakevens || []}
                    hasProposedTrades={proposedTrades.length > 0}
                    height={250}
                  />
                </Paper>

                {/* Metrics Panel */}
                <Paper sx={{ 
                  p: 2, 
                  backgroundColor: 'rgba(255,255,255,0.02)',
                }}>
                  <AdjustmentMetricsPanel
                    formattedMetrics={payoffData.formattedMetrics}
                    hasProposedTrades={proposedTrades.length > 0}
                    compact={false}
                  />
                </Paper>

                {/* Proposed Trades */}
                {proposedTrades.length > 0 && (
                  <Paper sx={{ 
                    p: 2, 
                    backgroundColor: 'rgba(255,255,255,0.02)',
                  }}>
                    <ProposedTradesTable
                      trades={proposedTrades}
                      onRemoveTrade={handleRemoveTrade}
                      onUpdateTradeQty={handleUpdateTradeQty}
                      onClearAll={handleClearAll}
                      compact
                    />
                  </Paper>
                )}
              </Box>
            </Box>
          )}

          {/* Execution complete - show summary */}
          {executionComplete && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="h5" sx={{ color: '#4caf50', mb: 2 }}>
                ✅ Adjustment Complete!
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                All trades have been executed. Your positions have been updated.
              </Typography>
              <Button
                variant="contained"
                color="primary"
                onClick={handleClose}
              >
                Close & Refresh Positions
              </Button>
            </Box>
          )}
        </Box>

        {/* Footer with spot price */}
        <Box sx={{
          p: 1.5,
          borderTop: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <Typography variant="caption" color="text.secondary">
            Current Positions: {currentPositions.length} | Spot: ${spotPrice?.toLocaleString() || '-'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Powered by Autoloop Execution
          </Typography>
        </Box>
      </Drawer>

      {/* Review Dialog */}
      <AdjustmentReviewDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        trades={proposedTrades}
        formattedMetrics={payoffData.formattedMetrics}
        onExecute={(params) => {
          setReviewDialogOpen(false);
          handleExecute(params);
        }}
        executing={executing}
      />
    </>
  );
}
