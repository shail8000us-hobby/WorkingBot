/**
 * Adjustment Review Dialog
 * ========================
 * Final confirmation dialog before executing trades.
 * Now with REAL order execution using the same API as OptionsPanel.
 * 
 * Features:
 * - Summary of all proposed trades
 * - Before/After metrics comparison
 * - Real order types: Market, Smart, Limit, SSR, SSR Aggro, SSR Safe
 * - Auto-loop execution for low liquidity
 * - Execute button with proper API integration
 * - BACKGROUND EXECUTION: Autoloops run independently of dialog
 * 
 * Created: January 31, 2026
 * Updated: February 1, 2026 - Added real execution with autoloop
 * Updated: February 2, 2026 - Added background execution via AutoloopContext
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  TextField,
  Alert,
  Divider,
  CircularProgress,
  IconButton,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  PlayArrow as ExecuteIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Stop as StopIcon,
  OpenInNew as BackgroundIcon,
} from '@mui/icons-material';
import { getContractMultiplier } from '../../utils/constants';
import api from '../../utils/apiShim';
import { useAutoloop } from '../../context/AutoloopContext';

// Order types matching your system exactly
const ORDER_TYPES = [
  { key: 'market_only', label: '⚡ Market', desc: 'Instant fill', color: '#ef4444' },
  { key: 'maker_first', label: '🎯 Smart', desc: 'Mid-price post-only', color: '#3b82f6' },
  { key: 'maker_only', label: '💰 Limit', desc: 'Your price', color: '#8b5cf6' },
  { key: 'ssr_standard', label: '🏎️ SSR', desc: '2 ticks below', color: '#ff9800' },
  { key: 'ssr_aggressive', label: '🔥 SSR Aggro', desc: '3-8% margin', color: '#4caf50' },
  { key: 'ssr_conservative', label: '🛡️ SSR Safe', desc: '1-2% margin', color: '#03a9f4' },
];

// SSR mode mapping for backend
const SSR_MODE_MAP = {
  ssr_standard: 'standard',
  ssr_aggressive: 'aggressive',
  ssr_conservative: 'conservative',
};

// Styling
const styles = {
  buyChip: {
    backgroundColor: '#2e7d32',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
  },
  sellChip: {
    backgroundColor: '#c62828',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
  },
  callChip: {
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    color: '#4caf50',
  },
  putChip: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
    color: '#f44336',
  },
};

/**
 * AdjustmentReviewDialog Component
 */
export default function AdjustmentReviewDialog({
  open,
  onClose,
  trades = [],
  formattedMetrics,
  onExecute,
  executing: externalExecuting = false,
  strategyName = 'Position Adjustment',
}) {
  // Get autoloop context for background execution
  const { startAutoloop } = useAutoloop();

  // State for execution options
  const [orderType, setOrderType] = useState('maker_first');
  const [loopRounds, setLoopRounds] = useState(1);
  const [confirmed, setConfirmed] = useState(false);
  const [executionMode, setExecutionMode] = useState('autoloop'); // 'autoloop' or 'all_at_once'
  const [useBackgroundExecution, setUseBackgroundExecution] = useState(true); // NEW: Run in background

  // Execution state (for inline execution fallback)
  const [executing, setExecuting] = useState(false);
  const [currentRound, setCurrentRound] = useState(0);
  const [executionProgress, setExecutionProgress] = useState({});
  const [executionError, setExecutionError] = useState(null);
  const [executionSuccess, setExecutionSuccess] = useState(false);
  const stopExecutionRef = useRef(false);

  // Enhanced execution tracking
  const [roundHistory, setRoundHistory] = useState([]); // Array of completed rounds with results
  const [currentRoundOrders, setCurrentRoundOrders] = useState([]); // Orders for current round with real-time status
  const [executionPhase, setExecutionPhase] = useState('idle'); // 'idle', 'punching', 'waiting', 'round_complete', 'done'

  // Calculate GCD of all trade quantities for proper autoloop
  const calculateGCD = (a, b) => {
    a = Math.abs(a);
    b = Math.abs(b);
    while (b !== 0) {
      const temp = b;
      b = a % b;
      a = temp;
    }
    return a;
  };

  const tradesGCD = useMemo(() => {
    if (trades.length === 0) return 1;
    if (trades.length === 1) return Math.abs(trades[0].quantity || 1);

    let gcd = Math.abs(trades[0].quantity || 1);
    for (let i = 1; i < trades.length; i++) {
      gcd = calculateGCD(gcd, Math.abs(trades[i].quantity || 1));
    }
    return gcd === 0 ? 1 : gcd;
  }, [trades]);

  // Calculate total loops needed (total qty / GCD)
  const totalLoops = useMemo(() => {
    if (trades.length === 0) return 0;
    const firstTradeQty = trades[0]?.quantity || 1;
    return Math.ceil(firstTradeQty / (firstTradeQty / tradesGCD));
  }, [trades, tradesGCD]);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setConfirmed(false);
      setExecuting(false);
      setCurrentRound(0);
      setExecutionProgress({});
      setExecutionError(null);
      setExecutionSuccess(false);
      setRoundHistory([]);
      setCurrentRoundOrders([]);
      setExecutionPhase('idle');
      stopExecutionRef.current = false;
    }
  }, [open]);

  // Calculate totals
  const calculateTotals = () => {
    let totalPremium = 0;
    let buyCount = 0;
    let sellCount = 0;

    trades.forEach((trade) => {
      const premium = Math.abs(trade.premium || trade.ltp || 0);
      const qty = trade.quantity || 1;
      const multiplier = getContractMultiplier(trade.symbol);
      const isLong = trade.side === 'buy';

      if (isLong) {
        buyCount++;
        totalPremium -= premium * qty * multiplier;
      } else {
        sellCount++;
        totalPremium += premium * qty * multiplier;
      }
    });

    return {
      totalPremium,
      buyCount,
      sellCount,
      isCredit: totalPremium >= 0,
    };
  };

  const totals = calculateTotals();

  // Get order type info
  const getOrderTypeInfo = (key) => ORDER_TYPES.find((t) => t.key === key) || ORDER_TYPES[1];

  // Execute orders with autoloop or all-at-once
  const executeOrders = async () => {
    if (trades.length === 0) return;

    // DEBUG: Log the exact trades data we received
    console.log('[Execution] Trade data received:', trades.map(t => ({
      symbol: t.symbol,
      side: t.side,
      quantity: t.quantity,
      qty: t.qty,
    })));

    setExecuting(true);
    setExecutionError(null);
    setExecutionSuccess(false);
    setRoundHistory([]);
    setCurrentRoundOrders([]);
    setExecutionPhase('idle');
    stopExecutionRef.current = false;

    const isSSR = orderType.startsWith('ssr_');
    const ssrMode = SSR_MODE_MAP[orderType] || 'standard';

    try {
      if (executionMode === 'all_at_once') {
        // ALL AT ONCE MODE: Place full quantity in one batch
        console.log('[Execution] All-at-once mode - placing full quantities');

        const orders = trades.map((trade, idx) => ({
          symbol: trade.symbol,
          side: trade.side,
          size: trade.quantity || 1,
          premium: trade.premium || trade.ltp || 0,
          id: idx,
        }));

        setCurrentRound(1);
        setExecutionPhase('punching');

        // Initialize current round orders for UI
        const initialOrders = orders.map(o => ({
          ...o,
          status: 'punching',
          filled: false,
          fillPrice: null,
        }));
        setCurrentRoundOrders(initialOrders);

        const roundProgress = {};
        orders.forEach((order) => {
          roundProgress[order.symbol] = { status: 'placing', filled: false, size: order.size };
        });
        setExecutionProgress(roundProgress);

        const results = await executeBatch(orders, isSSR, ssrMode, roundProgress, (statusUpdate) => {
          // Callback to update individual order status
          setCurrentRoundOrders(prev => prev.map(o =>
            o.symbol === statusUpdate.symbol ? { ...o, ...statusUpdate } : o
          ));
        });

        // Calculate round premium
        const roundPremium = calculateRoundPremium(orders, results);

        // Add to round history
        setRoundHistory([{
          round: 1,
          orders: orders.map(o => ({
            ...o,
            status: results[o.symbol]?.filled ? 'filled' : 'failed',
            filled: results[o.symbol]?.filled || false,
            fillPrice: results[o.symbol]?.fillPrice || null,
          })),
          netPremium: roundPremium,
          complete: true,
        }]);

        setExecutionPhase('done');
        setExecutionSuccess(true);
        console.log('[Execution] All-at-once completed');

      } else {
        // AUTOLOOP MODE: Execute exact user-specified quantities per round, wait for fills
        // Each round places the FULL user-specified quantity per trade
        // Total executed = user quantity × number of rounds

        const actualLoops = loopRounds || 1;
        const allRoundHistory = [];

        console.log(`[Execution] Autoloop mode - ${actualLoops} rounds`);
        console.log(`[Execution] Per-round quantities: ${trades.map(t => `${t.symbol}:${t.quantity || 1}`).join(', ')}`);

        for (let loop = 1; loop <= actualLoops; loop++) {
          if (stopExecutionRef.current) {
            setExecutionError(`Stopped by user at round ${loop - 1}/${actualLoops}`);
            break;
          }

          setCurrentRound(loop);
          setExecutionPhase('punching');

          // Build orders with EXACT user-specified quantities
          const loopOrders = trades.map((trade, idx) => ({
            symbol: trade.symbol,
            side: trade.side,
            size: trade.quantity || 1, // Use EXACT user-specified quantity
            premium: trade.premium || trade.ltp || 0,
            id: idx,
          }));

          console.log(`[Execution] Round ${loop}/${actualLoops} - placing: ${loopOrders.map(o => `${o.symbol}:${o.size}`).join(', ')}`);

          // Initialize current round orders for UI
          const initialOrders = loopOrders.map(o => ({
            ...o,
            status: 'punching',
            filled: false,
            fillPrice: null,
          }));
          setCurrentRoundOrders(initialOrders);

          const roundProgress = {};
          loopOrders.forEach((order) => {
            roundProgress[order.symbol] = {
              status: 'placing',
              filled: false,
              size: order.size,
              round: loop,
            };
          });
          setExecutionProgress(roundProgress);

          // Execute this round's batch and WAIT for all fills
          setExecutionPhase('waiting');
          const loopResult = await executeBatch(loopOrders, isSSR, ssrMode, roundProgress, (statusUpdate) => {
            // Callback to update individual order status
            setCurrentRoundOrders(prev => prev.map(o =>
              o.symbol === statusUpdate.symbol ? { ...o, ...statusUpdate } : o
            ));
          });

          // Check if all orders in this round are filled
          const allFilled = Object.values(loopResult).every(r => r.filled);

          if (!allFilled) {
            const unfilled = Object.entries(loopResult)
              .filter(([_, r]) => !r.filled)
              .map(([symbol, _]) => symbol)
              .join(', ');
            console.log(`[Execution] ⚠️ Round ${loop} - NOT ALL ORDERS FILLED BY EXCHANGE: ${unfilled}`);

            // CRITICAL: Do NOT proceed to next round if orders aren't confirmed filled!
            // This prevents placing Round 2 orders while Round 1 is still pending
            setExecutionError(`Round ${loop} incomplete: Orders not filled by exchange: ${unfilled}. Stopping to prevent duplicate orders.`);
            setExecutionPhase('idle');
            break; // Exit the loop - do not proceed to next round
          }

          console.log(`[Execution] ✅ Round ${loop}/${actualLoops} ALL ORDERS CONFIRMED FILLED BY EXCHANGE`);
          setExecutionPhase('round_complete');

          // Calculate round premium
          const roundPremium = calculateRoundPremium(loopOrders, loopResult);

          // Update current round orders to show filled status
          setCurrentRoundOrders(prev => prev.map(o => ({
            ...o,
            status: loopResult[o.symbol]?.filled ? 'filled' : 'failed',
            filled: loopResult[o.symbol]?.filled || false,
            fillPrice: loopResult[o.symbol]?.fillPrice || null,
          })));

          // Add to round history
          const roundData = {
            round: loop,
            orders: loopOrders.map(o => ({
              ...o,
              status: loopResult[o.symbol]?.filled ? 'filled' : 'failed',
              filled: loopResult[o.symbol]?.filled || false,
              fillPrice: loopResult[o.symbol]?.fillPrice || null,
            })),
            netPremium: roundPremium,
            complete: true,
          };
          allRoundHistory.push(roundData);
          setRoundHistory([...allRoundHistory]);

          // Update progress to show round complete
          Object.keys(roundProgress).forEach(symbol => {
            roundProgress[symbol] = {
              ...roundProgress[symbol],
              roundComplete: true,
            };
          });
          setExecutionProgress({ ...roundProgress });

          // Wait before next round (if not last round)
          if (loop < actualLoops && !stopExecutionRef.current) {
            console.log(`[Execution] Waiting 1.5s before Round ${loop + 1}...`);
            await new Promise(resolve => setTimeout(resolve, 1500));
          }
        }

        if (!stopExecutionRef.current) {
          setExecutionPhase('done');
          setExecutionSuccess(true);
          console.log('[Execution] Autoloop completed');
        }
      }

      // Notify parent
      onExecute?.({
        trades,
        orderType,
        executionMode,
        loopRounds,
      });

    } catch (err) {
      console.error('[Execution] Error:', err);
      setExecutionError(err.message || 'Execution failed');
      setExecutionPhase('idle');
    } finally {
      setExecuting(false);
    }
  };

  // Helper: Calculate net premium for a round
  const calculateRoundPremium = (orders, results) => {
    let premium = 0;
    orders.forEach(order => {
      const result = results[order.symbol];
      const price = result?.fillPrice || order.premium || 0;
      const multiplier = getContractMultiplier(order.symbol);
      if (order.side === 'sell') {
        premium += price * order.size * multiplier;
      } else {
        premium -= price * order.size * multiplier;
      }
    });
    return premium;
  };

  // Helper: Execute a batch of orders and wait for fills
  const executeBatch = async (orders, isSSR, ssrMode, roundProgress, onStatusUpdate) => {
    const results = {};

    if (isSSR) {
      // SSR orders: place one by one and monitor
      for (const order of orders) {
        if (stopExecutionRef.current) break;

        roundProgress[order.symbol] = { ...roundProgress[order.symbol], status: 'placing' };
        setExecutionProgress({ ...roundProgress });
        onStatusUpdate?.({ symbol: order.symbol, status: 'punched', filled: false });

        try {
          const response = await api.post('/api/options/ssr-order', {
            symbol: order.symbol,
            side: order.side,
            quantity: order.size,
            ssrMode: ssrMode,
          });

          if (response.data.success) {
            // Get order ID from ssrTracking or order object
            const orderId = response.data.ssrTracking?.orderId || response.data.order?.id || response.data.order_id;

            if (!orderId) {
              console.log(`[Execution] ⚠️ SSR order for ${order.symbol} succeeded but no order_id returned - cannot track`);
            }

            roundProgress[order.symbol] = {
              status: 'monitoring',
              filled: false,
              orderId: orderId,
              size: order.size,
            };
            results[order.symbol] = { filled: false, orderId: orderId, size: order.size };
            onStatusUpdate?.({ symbol: order.symbol, status: 'punched', filled: false, orderId: orderId });
          } else {
            roundProgress[order.symbol] = {
              status: 'failed',
              filled: false,
              error: response.data.error,
              size: order.size,
            };
            results[order.symbol] = { filled: false, error: response.data.error, size: order.size };
            onStatusUpdate?.({ symbol: order.symbol, status: 'failed', filled: false, error: response.data.error });
          }
        } catch (err) {
          roundProgress[order.symbol] = {
            status: 'failed',
            filled: false,
            error: err.message,
            size: order.size,
          };
          results[order.symbol] = { filled: false, error: err.message, size: order.size };
          onStatusUpdate?.({ symbol: order.symbol, status: 'failed', filled: false, error: err.message });
        }
        setExecutionProgress({ ...roundProgress });
      }

      // For SSR, poll the REAL exchange status endpoint to wait for ACTUAL fills
      // CRITICAL: We MUST confirm with the exchange - never assume orders are filled!
      console.log('[Execution] SSR orders placed, polling exchange for REAL fill confirmations...');

      // Collect all order IDs that need to be monitored
      const ssrPendingOrders = Object.entries(results)
        .filter(([_, r]) => r.orderId && !r.filled)
        .map(([symbol, r]) => ({ symbol, orderId: r.orderId }));

      if (ssrPendingOrders.length > 0) {
        const ssrOrderIds = ssrPendingOrders.map(o => o.orderId);
        console.log(`[Execution] Polling ${ssrPendingOrders.length} SSR orders: ${ssrOrderIds.join(', ')}`);

        let ssrAllFilled = false;
        let ssrPollCount = 0;
        const ssrMaxPolls = 90; // 3 minutes max for SSR (2s × 90 = 180s)

        while (!ssrAllFilled && !stopExecutionRef.current && ssrPollCount < ssrMaxPolls) {
          ssrPollCount++;
          await new Promise(resolve => setTimeout(resolve, 2000));

          try {
            // Call the REAL exchange status API
            const statusResponse = await api.post('/api/options/batch_order_status', {
              order_ids: ssrOrderIds,
            });

            if (!statusResponse.data.success) {
              console.log(`[Execution] SSR Poll ${ssrPollCount}: status API failed`);
              continue;
            }

            const statuses = statusResponse.data.orders || [];
            let filledCount = 0;

            statuses.forEach((status) => {
              const matching = ssrPendingOrders.find(o => String(o.orderId) === String(status.order_id));
              if (matching) {
                const isFilled = status.state === 'filled' || status.state === 'closed';
                const isCancelled = status.state === 'cancelled' || status.state === 'rejected';

                if (isFilled) {
                  roundProgress[matching.symbol] = {
                    ...roundProgress[matching.symbol],
                    status: 'filled',
                    filled: true,
                    fillPrice: status.fill_price || roundProgress[matching.symbol].fillPrice,
                  };
                  results[matching.symbol] = {
                    ...results[matching.symbol],
                    filled: true,
                    fillPrice: status.fill_price
                  };
                  onStatusUpdate?.({
                    symbol: matching.symbol,
                    status: 'filled',
                    filled: true,
                    fillPrice: status.fill_price,
                  });
                  filledCount++;
                } else if (isCancelled) {
                  roundProgress[matching.symbol] = {
                    ...roundProgress[matching.symbol],
                    status: 'cancelled',
                    filled: false,
                  };
                  results[matching.symbol] = {
                    ...results[matching.symbol],
                    filled: false,
                    cancelled: true,
                  };
                  onStatusUpdate?.({
                    symbol: matching.symbol,
                    status: 'cancelled',
                    filled: false,
                  });
                } else if (results[matching.symbol]?.filled) {
                  filledCount++;
                }
              }
            });

            setExecutionProgress({ ...roundProgress });

            // Check if all SSR orders are filled
            const totalFilled = ssrPendingOrders.filter(o => results[o.symbol]?.filled).length;
            ssrAllFilled = totalFilled === ssrPendingOrders.length;

            console.log(`[Execution] SSR Poll ${ssrPollCount}: ${totalFilled}/${ssrPendingOrders.length} CONFIRMED filled by exchange`);

            if (ssrAllFilled) {
              console.log('[Execution] ✅ All SSR orders CONFIRMED filled by exchange!');
            }
          } catch (pollErr) {
            console.error('[Execution] SSR Poll error:', pollErr);
          }
        }

        if (!ssrAllFilled && ssrPollCount >= ssrMaxPolls) {
          console.log('[Execution] ⚠️ SSR timeout waiting for exchange confirmation - NOT marking as filled!');
          // DO NOT mark unfilled orders as filled - this was the bug!
          const unfilledSymbols = ssrPendingOrders
            .filter(o => !results[o.symbol]?.filled)
            .map(o => o.symbol);
          if (unfilledSymbols.length > 0) {
            console.log(`[Execution] ⚠️ Orders still pending: ${unfilledSymbols.join(', ')}`);
          }
        }
      } else {
        console.log('[Execution] All SSR orders either filled immediately or failed');
      }

      console.log('[Execution] SSR batch complete - REAL exchange confirmations only');

    } else {
      // Non-SSR: batch add
      // First notify all orders are being punched
      orders.forEach(order => {
        onStatusUpdate?.({ symbol: order.symbol, status: 'punching', filled: false });
      });

      const response = await api.post('/api/options/batch_add', {
        orders,
        order_preference: orderType,
        confirm: true,
      });

      if (!response.data.success) {
        throw new Error(response.data.error || 'Batch order failed');
      }

      const apiResults = response.data.results || [];
      const pendingOrders = [];

      apiResults.forEach((result) => {
        const execType = result.execution_type || '';
        const isFilled = ['market', 'market_fallback', 'market_fallback_no_quotes', 'limit_filled', 'limit_filled_late'].includes(execType) || !result.order_id;

        roundProgress[result.symbol] = {
          status: result.success ? (isFilled ? 'filled' : 'pending') : 'failed',
          filled: isFilled,
          fillPrice: result.fill_price,
          orderId: result.order_id,
          error: result.error,
          size: result.size,
        };

        results[result.symbol] = {
          filled: isFilled,
          size: result.size,
          orderId: result.order_id,
          fillPrice: result.fill_price,
        };

        // Update UI with order status
        onStatusUpdate?.({
          symbol: result.symbol,
          status: isFilled ? 'filled' : 'punched',
          filled: isFilled,
          fillPrice: result.fill_price,
        });

        if (result.success && !isFilled && result.order_id) {
          pendingOrders.push(result);
        }
      });
      setExecutionProgress({ ...roundProgress });

      // Poll for pending orders - MUST wait for ALL fills before returning
      if (pendingOrders.length > 0) {
        console.log(`[Execution] Polling for ${pendingOrders.length} pending orders: ${pendingOrders.map(o => o.symbol).join(', ')}`);
        const orderIds = pendingOrders.map((r) => r.order_id);
        let allFilled = false;
        let pollCount = 0;
        const maxPolls = 60; // 2 minutes max (2s × 60 = 120s)

        while (!allFilled && !stopExecutionRef.current && pollCount < maxPolls) {
          pollCount++;
          await new Promise((resolve) => setTimeout(resolve, 2000));

          try {
            const statusResponse = await api.post('/api/options/batch_order_status', {
              order_ids: orderIds,
            });

            if (!statusResponse.data.success) {
              console.log(`[Execution] Poll ${pollCount}: status API failed`);
              continue;
            }

            const statuses = statusResponse.data.orders || [];

            statuses.forEach((status) => {
              const matching = pendingOrders.find((o) => o.order_id === status.order_id);
              if (matching) {
                const isFilled = status.state === 'filled' || status.state === 'closed';
                const isCancelled = status.state === 'cancelled' || status.state === 'rejected';

                roundProgress[matching.symbol] = {
                  ...roundProgress[matching.symbol],
                  status: isFilled ? 'filled' : isCancelled ? 'cancelled' : 'pending',
                  filled: isFilled,
                  fillPrice: status.fill_price || roundProgress[matching.symbol].fillPrice,
                };

                if (isFilled) {
                  results[matching.symbol] = { ...results[matching.symbol], filled: true, fillPrice: status.fill_price };
                  onStatusUpdate?.({
                    symbol: matching.symbol,
                    status: 'filled',
                    filled: true,
                    fillPrice: status.fill_price,
                  });
                }
              }
            });

            setExecutionProgress({ ...roundProgress });

            // Count only the orders we're waiting for
            const filledCount = pendingOrders.filter(o => results[o.symbol]?.filled).length;
            allFilled = filledCount === pendingOrders.length;

            console.log(`[Execution] Poll ${pollCount}: ${filledCount}/${pendingOrders.length} filled`);

            if (allFilled) {
              console.log('[Execution] All pending orders filled!');
            }
          } catch (pollErr) {
            console.error('[Execution] Poll error:', pollErr);
          }
        }

        if (!allFilled && pollCount >= maxPolls) {
          console.log('[Execution] ⚠️ Timeout waiting for exchange confirmation - orders remain UNFILLED');
          // Orders that didn't get confirmed as filled remain as unfilled in results
          // The autoloop will detect this and stop
          const unfilledSymbols = pendingOrders
            .filter(o => !results[o.symbol]?.filled)
            .map(o => o.symbol);
          console.log(`[Execution] ⚠️ Orders still pending on exchange: ${unfilledSymbols.join(', ')}`);
        }
      } else {
        console.log('[Execution] All orders filled immediately (no pending orders)');
      }
    }

    console.log(`[Execution] Batch complete - results: ${JSON.stringify(Object.entries(results).map(([s, r]) => `${s}:${r.filled}`))}`);
    return results;
  };

  // Start background execution using AutoloopContext
  const startBackgroundExecution = () => {
    console.log('[Execution] Starting BACKGROUND autoloop execution');

    const autoloopId = startAutoloop({
      trades,
      orderType,
      loopRounds: executionMode === 'autoloop' ? loopRounds : 1,
      strategyName,
      onComplete: (result) => {
        console.log('[Execution] Background autoloop completed:', result);
        onExecute?.({
          trades,
          orderType,
          executionMode,
          loopRounds,
          backgroundExecution: true,
        });
      },
      onError: (err) => {
        console.error('[Execution] Background autoloop error:', err);
      },
    });

    console.log(`[Execution] Background autoloop started with ID: ${autoloopId}`);

    // Close dialog - execution continues in background
    setConfirmed(false);
    onClose?.();
  };

  // Handle execute button click
  const handleExecute = () => {
    if (!confirmed) {
      setConfirmed(true);
      return;
    }

    // Use background execution for autoloop mode (recommended)
    if (executionMode === 'autoloop' && useBackgroundExecution) {
      startBackgroundExecution();
    } else {
      // Inline execution (legacy, for single batch)
      executeOrders();
    }
  };

  // Stop execution
  const handleStop = () => {
    stopExecutionRef.current = true;
  };

  // Reset on close
  const handleClose = () => {
    if (executing) {
      stopExecutionRef.current = true;
    }
    setConfirmed(false);
    onClose?.();
  };

  return (
    <Dialog
      open={open}
      onClose={executing ? undefined : handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: '#1a1a2e',
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">
            Review & Execute
          </Typography>
          <Chip
            label={`${trades.length} trade${trades.length !== 1 ? 's' : ''}`}
            size="small"
            color="primary"
          />
        </Box>

        {!executing && (
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        )}
      </DialogTitle>

      <DialogContent sx={{ py: 3 }}>
        {/* Warning for high-risk adjustments */}
        {formattedMetrics?.raw?.change?.popChange < -0.1 && !executing && !executionSuccess && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This adjustment significantly decreases your Probability of Profit. Review carefully.
            </Typography>
          </Alert>
        )}

        {/* ============================================ */}
        {/* PRE-TRADE RISK SUMMARY */}
        {/* ============================================ */}
        {formattedMetrics && !executing && !executionSuccess && (
          <Paper sx={{
            mb: 2.5,
            p: 2,
            bgcolor: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            borderRadius: 2,
          }}>
            <Typography variant="subtitle2" sx={{
              color: '#a78bfa', fontWeight: 700, mb: 1.5,
              display: 'flex', alignItems: 'center', gap: 0.5,
              fontSize: '0.85rem'
            }}>
              📊 Pre-Trade Risk Summary
            </Typography>

            {/* Net Premium Row */}
            <Box sx={{
              display: 'flex', alignItems: 'center', gap: 2, mb: 1, pb: 1,
              borderBottom: '1px solid rgba(71, 85, 105, 0.3)',
            }}>
              <Typography variant="caption" sx={{ color: '#94a3b8', minWidth: 90 }}>Net Premium</Typography>
              <Typography variant="body2" sx={{
                color: totals.isCredit ? '#22c55e' : '#f97316',
                fontWeight: 700,
                fontSize: '0.9rem'
              }}>
                {totals.isCredit ? 'CREDIT' : 'DEBIT'} ${Math.abs(totals.totalPremium).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>

            {/* Before → After Grid */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '90px 1fr 30px 1fr 1fr', gap: 0.5, alignItems: 'center' }}>
              {/* Header */}
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, fontSize: '0.6rem' }}>METRIC</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, fontSize: '0.6rem', textAlign: 'center' }}>BEFORE</Typography>
              <Box />
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, fontSize: '0.6rem', textAlign: 'center' }}>AFTER</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, fontSize: '0.6rem', textAlign: 'center' }}>CHANGE</Typography>

              {/* Max Profit */}
              <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>Max Profit</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontSize: '0.75rem' }}>{formattedMetrics.current?.maxProfit || '-'}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', textAlign: 'center' }}>→</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontWeight: 600, fontSize: '0.75rem' }}>{formattedMetrics.combined?.maxProfit || '-'}</Typography>
              <Typography variant="caption" sx={{
                color: formattedMetrics.change?.maxProfit?.startsWith('+') ? '#22c55e' : formattedMetrics.change?.maxProfit?.startsWith('-') ? '#ef4444' : '#94a3b8',
                textAlign: 'center', fontWeight: 600, fontSize: '0.7rem',
              }}>{formattedMetrics.change?.maxProfit || '-'}</Typography>

              {/* Max Loss */}
              <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>Max Loss</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontSize: '0.75rem' }}>{formattedMetrics.current?.maxLoss || '-'}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', textAlign: 'center' }}>→</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontWeight: 600, fontSize: '0.75rem' }}>{formattedMetrics.combined?.maxLoss || '-'}</Typography>
              <Typography variant="caption" sx={{
                color: formattedMetrics.change?.maxLoss?.startsWith('+') ? '#22c55e' : formattedMetrics.change?.maxLoss?.startsWith('-') ? '#ef4444' : '#94a3b8',
                textAlign: 'center', fontWeight: 600, fontSize: '0.7rem',
              }}>{formattedMetrics.change?.maxLoss || '-'}</Typography>

              {/* POP */}
              <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>PoP</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontSize: '0.75rem' }}>{formattedMetrics.current?.pop || '-'}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', textAlign: 'center' }}>→</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontWeight: 600, fontSize: '0.75rem' }}>{formattedMetrics.combined?.pop || '-'}</Typography>
              <Typography variant="caption" sx={{
                color: formattedMetrics.change?.pop?.startsWith('+') ? '#22c55e' : formattedMetrics.change?.pop?.startsWith('-') ? '#ef4444' : '#94a3b8',
                textAlign: 'center', fontWeight: 600, fontSize: '0.7rem',
              }}>{formattedMetrics.change?.pop || '-'}</Typography>

              {/* Delta */}
              <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>Delta</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontSize: '0.75rem' }}>{formattedMetrics.current?.netDelta || '-'}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', textAlign: 'center' }}>→</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontWeight: 600, fontSize: '0.75rem' }}>{formattedMetrics.combined?.netDelta || '-'}</Typography>
              <Typography variant="caption" sx={{
                color: '#94a3b8',
                textAlign: 'center', fontWeight: 600, fontSize: '0.7rem',
              }}>{formattedMetrics.change?.netDelta || '-'}</Typography>

              {/* Theta */}
              <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>Theta</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontSize: '0.75rem' }}>{formattedMetrics.current?.netTheta || '-'}</Typography>
              <Typography variant="caption" sx={{ color: '#64748b', textAlign: 'center' }}>→</Typography>
              <Typography variant="caption" sx={{ color: '#e2e8f0', textAlign: 'center', fontWeight: 600, fontSize: '0.75rem' }}>{formattedMetrics.combined?.netTheta || '-'}</Typography>
              <Typography variant="caption" sx={{
                color: formattedMetrics.change?.netTheta?.startsWith('+') ? '#22c55e' : formattedMetrics.change?.netTheta?.startsWith('-') ? '#ef4444' : '#94a3b8',
                textAlign: 'center', fontWeight: 600, fontSize: '0.7rem',
              }}>{formattedMetrics.change?.netTheta || '-'}</Typography>
            </Box>
          </Paper>
        )}

        {/* ============================================ */}
        {/* REAL-TIME EXECUTION PROGRESS WINDOW */}
        {/* ============================================ */}
        {(executing || executionSuccess) && (
          <Box sx={{
            mb: 3,
            p: 2,
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderRadius: 2,
            border: '1px solid rgba(59, 130, 246, 0.3)',
          }}>
            {/* Header */}
            <Box sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 2,
              pb: 1.5,
              borderBottom: '1px solid rgba(255,255,255,0.1)',
            }}>
              <Typography variant="h6" sx={{
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                color: executionSuccess ? '#22c55e' : '#3b82f6',
              }}>
                {executionSuccess ? '🎉' : '⚡'} Auto-Loop Execution Progress
              </Typography>
              <Chip
                label={`${loopRounds} round${loopRounds > 1 ? 's' : ''} × ${trades.length} trades = ${loopRounds * trades.length} total`}
                size="small"
                sx={{
                  backgroundColor: 'rgba(59, 130, 246, 0.2)',
                  color: '#94a3b8',
                }}
              />
            </Box>

            {/* Completed Rounds History */}
            {roundHistory.map((round, idx) => (
              <Box
                key={idx}
                sx={{
                  mb: 2,
                  p: 1.5,
                  backgroundColor: 'rgba(34, 197, 94, 0.1)',
                  borderRadius: 1,
                  border: '1px solid rgba(34, 197, 94, 0.3)',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2" sx={{ color: '#22c55e', fontWeight: 'bold' }}>
                    ✅ Round {round.round}/{loopRounds} Complete
                  </Typography>
                  <Typography variant="body2" sx={{
                    color: round.netPremium >= 0 ? '#22c55e' : '#ef4444',
                    fontWeight: 'bold',
                  }}>
                    Net: {round.netPremium >= 0 ? '+' : ''}{round.netPremium?.toFixed(2)} USD
                    <span style={{ color: '#94a3b8', marginLeft: 4 }}>
                      ({round.netPremium >= 0 ? 'Credit' : 'Debit'})
                    </span>
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {round.orders.map((order, orderIdx) => (
                    <Chip
                      key={orderIdx}
                      size="small"
                      label={`${order.side === 'sell' ? 'S' : 'B'} ${order.symbol.split('-').slice(0, 3).join('-')} ×${order.size}`}
                      sx={{
                        backgroundColor: order.filled ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                        color: order.filled ? '#22c55e' : '#ef4444',
                        fontSize: '0.7rem',
                      }}
                    />
                  ))}
                </Box>
              </Box>
            ))}

            {/* Current Round (if executing) */}
            {executing && currentRound > 0 && (
              <Box sx={{
                p: 1.5,
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderRadius: 1,
                border: '1px solid rgba(59, 130, 246, 0.3)',
              }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                  <Typography variant="subtitle2" sx={{ color: '#3b82f6', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={14} sx={{ color: '#3b82f6' }} />
                    Round {currentRound}/{loopRounds}: {
                      executionPhase === 'punching' ? 'Punching orders to exchange...' :
                        executionPhase === 'waiting' ? 'Waiting for fills...' :
                          executionPhase === 'round_complete' ? 'Complete!' : 'Processing...'
                    }
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                    {currentRoundOrders.filter(o => o.filled).length}/{currentRoundOrders.length} filled
                  </Typography>
                </Box>

                {/* Order Status Table */}
                <Table size="small" sx={{ '& td, & th': { py: 0.5, px: 1, border: 'none' } }}>
                  <TableBody>
                    {currentRoundOrders.map((order, idx) => (
                      <TableRow key={idx} sx={{ '&:hover': { backgroundColor: 'rgba(255,255,255,0.02)' } }}>
                        <TableCell sx={{ width: 30 }}>
                          <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                            {idx + 1}.
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {order.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell align="center" sx={{ width: 50 }}>
                          <Chip
                            label={order.side.toUpperCase()}
                            size="small"
                            sx={{
                              ...(order.side === 'sell' ? styles.sellChip : styles.buyChip),
                              height: 20,
                              fontSize: '0.65rem',
                            }}
                          />
                        </TableCell>
                        <TableCell align="center" sx={{ width: 50 }}>
                          <Typography variant="body2">{order.size} lot{order.size > 1 ? 's' : ''}</Typography>
                        </TableCell>
                        <TableCell align="right" sx={{ width: 120 }}>
                          {order.status === 'punching' && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
                              <CircularProgress size={12} sx={{ color: '#f59e0b' }} />
                              <Typography variant="caption" sx={{ color: '#f59e0b' }}>Punching...</Typography>
                            </Box>
                          )}
                          {order.status === 'punched' && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
                              <Typography variant="caption" sx={{ color: '#f59e0b' }}>⏳ Punched</Typography>
                            </Box>
                          )}
                          {order.status === 'filled' && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
                              <CheckIcon sx={{ fontSize: 14, color: '#22c55e' }} />
                              <Typography variant="caption" sx={{ color: '#22c55e' }}>
                                Filled {order.fillPrice ? `@ $${order.fillPrice.toFixed(2)}` : '✅'}
                              </Typography>
                            </Box>
                          )}
                          {order.status === 'failed' && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
                              <Typography variant="caption" sx={{ color: '#ef4444' }}>❌ Failed</Typography>
                            </Box>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            )}

            {/* Final Summary (when complete) */}
            {executionSuccess && roundHistory.length > 0 && (
              <Box sx={{
                mt: 2,
                p: 2,
                backgroundColor: 'rgba(34, 197, 94, 0.15)',
                borderRadius: 1,
                border: '1px solid rgba(34, 197, 94, 0.4)',
                textAlign: 'center',
              }}>
                <Typography variant="h6" sx={{ color: '#22c55e', fontWeight: 'bold', mb: 1 }}>
                  🎉 Auto-Loop Complete!
                </Typography>
                <Typography variant="body1" sx={{ color: '#e2e8f0' }}>
                  Total orders executed: <strong>{roundHistory.reduce((sum, r) => sum + r.orders.length, 0)}</strong>
                </Typography>
                <Typography variant="body1" sx={{
                  color: roundHistory.reduce((sum, r) => sum + (r.netPremium || 0), 0) >= 0 ? '#22c55e' : '#ef4444',
                  fontWeight: 'bold',
                  mt: 0.5,
                }}>
                  Total net premium: {roundHistory.reduce((sum, r) => sum + (r.netPremium || 0), 0) >= 0 ? '+' : ''}
                  {roundHistory.reduce((sum, r) => sum + (r.netPremium || 0), 0).toFixed(2)} USD
                  <span style={{ color: '#94a3b8', marginLeft: 8 }}>
                    ({roundHistory.reduce((sum, r) => sum + (r.netPremium || 0), 0) >= 0 ? 'Credit' : 'Debit'})
                  </span>
                </Typography>
                <Button
                  variant="contained"
                  color="success"
                  onClick={handleClose}
                  sx={{ mt: 2 }}
                >
                  Close
                </Button>
              </Box>
            )}

            {/* Stop Button */}
            {executing && (
              <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<StopIcon />}
                  onClick={handleStop}
                >
                  Stop Execution
                </Button>
              </Box>
            )}
          </Box>
        )}

        {/* Execution Error */}
        {executionError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              ❌ Execution Error
            </Typography>
            <Typography variant="caption" display="block">
              {executionError}
            </Typography>
          </Alert>
        )}

        {/* Trades Table */}
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
          Trades to Execute
        </Typography>

        <TableContainer
          component={Paper}
          sx={{
            mb: 3,
            backgroundColor: 'rgba(255,255,255,0.02)',
            maxHeight: 250,
          }}
        >
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Type</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Side</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Qty</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>Premium</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.map((trade, index) => {
                const premium = Math.abs(trade.premium || trade.ltp || 0);
                const qty = trade.quantity || 1;
                const totalPremium = premium * qty * getContractMultiplier(trade.symbol);
                const isCredit = trade.side === 'sell';

                return (
                  <TableRow key={index} hover>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {trade.symbol}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={trade.type === 'call' ? 'CALL' : 'PUT'}
                        size="small"
                        sx={trade.type === 'call' ? styles.callChip : styles.putChip}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={trade.side === 'buy' ? 'BUY' : 'SELL'}
                        size="small"
                        sx={trade.side === 'buy' ? styles.buyChip : styles.sellChip}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {qty}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 'bold',
                          color: isCredit ? '#4caf50' : '#f44336',
                        }}
                      >
                        {isCredit ? '+' : '-'}${totalPremium.toFixed(2)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Net Premium Summary */}
        <Box sx={{
          p: 2,
          mb: 3,
          backgroundColor: totals.isCredit
            ? 'rgba(76, 175, 80, 0.1)'
            : 'rgba(244, 67, 54, 0.1)',
          borderRadius: 1,
          borderLeft: `3px solid ${totals.isCredit ? '#4caf50' : '#f44336'}`,
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2">
              Net Premium ({totals.buyCount} buy, {totals.sellCount} sell):
            </Typography>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 'bold',
                color: totals.isCredit ? '#4caf50' : '#f44336',
              }}
            >
              {totals.isCredit ? '+' : ''}{totals.totalPremium.toFixed(2)} USD
              <Typography component="span" variant="body2" sx={{ ml: 1, color: 'text.secondary' }}>
                ({totals.isCredit ? 'Credit' : 'Debit'})
              </Typography>
            </Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Execution Options */}
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>
          Execution Options
        </Typography>

        {/* Order Type Selection - Visual Buttons like OptionsPanel */}
        <Typography variant="caption" sx={{ color: 'text.secondary', mb: 1, display: 'block' }}>
          Order Type
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          {ORDER_TYPES.map((type) => (
            <Tooltip key={type.key} title={type.desc}>
              <Button
                onClick={() => setOrderType(type.key)}
                disabled={executing}
                sx={{
                  flex: '1 1 auto',
                  minWidth: 100,
                  py: 1.5,
                  borderRadius: '10px',
                  flexDirection: 'column',
                  textTransform: 'none',
                  background: orderType === type.key
                    ? `${type.color}33`
                    : 'rgba(30, 41, 59, 0.5)',
                  border: orderType === type.key
                    ? `2px solid ${type.color}`
                    : '1px solid rgba(148, 163, 184, 0.15)',
                  '&:hover': {
                    background: `${type.color}22`,
                  },
                }}
              >
                <Typography sx={{
                  color: orderType === type.key ? type.color : '#e2e8f0',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                }}>
                  {type.label}
                </Typography>
                <Typography sx={{
                  color: 'rgba(148, 163, 184, 0.7)',
                  fontSize: '0.65rem',
                }}>
                  {type.desc}
                </Typography>
              </Button>
            </Tooltip>
          ))}
        </Box>

        {/* Loop Rounds */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', mb: 0.5, display: 'block' }}>
              Execution Mode
            </Typography>
            <Box sx={{ display: 'flex', borderRadius: 1, overflow: 'hidden', border: '1px solid rgba(148, 163, 184, 0.3)' }}>
              <Button
                size="small"
                onClick={() => setExecutionMode('autoloop')}
                disabled={executing}
                sx={{
                  px: 2,
                  py: 0.75,
                  minWidth: 100,
                  borderRadius: 0,
                  bgcolor: executionMode === 'autoloop' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                  color: executionMode === 'autoloop' ? '#3b82f6' : '#94a3b8',
                  fontSize: '0.75rem',
                  fontWeight: executionMode === 'autoloop' ? 600 : 400,
                  '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.1)' },
                }}
              >
                🔄 Auto-Loop
              </Button>
              <Button
                size="small"
                onClick={() => setExecutionMode('all_at_once')}
                disabled={executing}
                sx={{
                  px: 2,
                  py: 0.75,
                  minWidth: 100,
                  borderRadius: 0,
                  borderLeft: '1px solid rgba(148, 163, 184, 0.3)',
                  bgcolor: executionMode === 'all_at_once' ? 'rgba(34, 197, 94, 0.2)' : 'transparent',
                  color: executionMode === 'all_at_once' ? '#22c55e' : '#94a3b8',
                  fontSize: '0.75rem',
                  fontWeight: executionMode === 'all_at_once' ? 600 : 400,
                  '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.1)' },
                }}
              >
                ⚡ All at Once
              </Button>
            </Box>
          </Box>

          {executionMode === 'autoloop' && (
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary', mb: 0.5, display: 'block' }}>
                Loop Rounds
              </Typography>
              <TextField
                size="small"
                type="number"
                value={loopRounds}
                onChange={(e) => setLoopRounds(Math.max(1, parseInt(e.target.value) || 1))}
                inputProps={{ min: 1, max: 100 }}
                sx={{
                  width: 80,
                  '& input': { textAlign: 'center' },
                }}
                disabled={executing}
              />
            </Box>
          )}

          <Box sx={{ pt: 2.5 }}>
            {executionMode === 'autoloop' ? (
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {loopRounds} round{loopRounds > 1 ? 's' : ''} × {trades.length} trades = {loopRounds * trades.length} total executions
                <br />
                <span style={{ color: '#3b82f6' }}>Each round places EXACT quantities per trade, waits for fills</span>
              </Typography>
            ) : (
              <Typography variant="caption" sx={{ color: '#22c55e' }}>
                All {trades.reduce((sum, t) => sum + (t.quantity || 1), 0)} lots placed in one batch
                <br />
                <span style={{ color: '#94a3b8' }}>Best for liquid expiries</span>
              </Typography>
            )}
          </Box>
        </Box>

        {/* Info about execution */}
        <Alert
          severity={executionMode === 'all_at_once' ? 'success' : 'info'}
          sx={{ mb: 2 }}
        >
          <Typography variant="body2">
            <strong>{getOrderTypeInfo(orderType).label}</strong>: {getOrderTypeInfo(orderType).desc}
            {executionMode === 'autoloop' && loopRounds > 1 &&
              `. Will execute ${loopRounds} rounds, each round placing: ${trades.map(t => `${t.quantity || 1} lot`).join(', ')}. Waits for all fills.`}
            {executionMode === 'all_at_once' &&
              `. Will place all ${trades.reduce((sum, t) => sum + (t.quantity || 1), 0)} lots in one batch order.`}
          </Typography>
        </Alert>

        {/* Metrics Summary (compact) */}
        {formattedMetrics && (
          <Box sx={{
            p: 2,
            backgroundColor: 'rgba(255,255,255,0.03)',
            borderRadius: 1,
          }}>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              After Execution
            </Typography>
            <Box sx={{ display: 'flex', gap: 3, mt: 1, flexWrap: 'wrap' }}>
              <Box>
                <Typography variant="caption" color="text.secondary">Max Profit</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.maxProfit}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Max Loss</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.maxLoss}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">PoP</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.pop}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Breakeven</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.breakevens?.join(', ') || '-'}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{
        px: 3,
        py: 2,
        borderTop: '1px solid rgba(255,255,255,0.1)',
        justifyContent: 'space-between',
      }}>
        <Button
          onClick={handleClose}
          disabled={executing}
          color="inherit"
        >
          {executionSuccess ? 'Close' : 'Cancel'}
        </Button>

        <Box sx={{ display: 'flex', gap: 1 }}>
          {!confirmed && !executionSuccess ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleExecute}
              disabled={executing || trades.length === 0}
              startIcon={<CheckIcon />}
            >
              Confirm Execution
            </Button>
          ) : !executionSuccess ? (
            <Button
              variant="contained"
              onClick={handleExecute}
              disabled={executing || trades.length === 0}
              startIcon={executing ? <CircularProgress size={20} color="inherit" /> : <ExecuteIcon />}
              sx={{
                minWidth: 180,
                bgcolor: getOrderTypeInfo(orderType).color,
                '&:hover': {
                  bgcolor: getOrderTypeInfo(orderType).color,
                  filter: 'brightness(0.9)',
                },
              }}
            >
              {executing ? `Executing R${currentRound}...` : `Execute ${getOrderTypeInfo(orderType).label}`}
            </Button>
          ) : null}
        </Box>
      </DialogActions>
    </Dialog>
  );
}
