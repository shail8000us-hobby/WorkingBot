/**
 * Autoloop Context
 * ================
 * Global state management for background autoloop executions.
 * Allows autoloops to run independently of dialogs and persist across page navigation.
 * 
 * Created: February 2, 2026
 */

import React, { createContext, useContext, useState, useRef, useCallback } from 'react';
import api from '../utils/apiShim';
import { getContractMultiplier } from '../utils/constants';

const AutoloopContext = createContext(null);

// SSR mode mapping for backend
const SSR_MODE_MAP = {
  ssr_standard: 'standard',
  ssr_aggressive: 'aggressive',
  ssr_conservative: 'conservative',
};

/**
 * Generate unique ID for each autoloop
 */
const generateAutoloopId = () => `autoloop_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

/**
 * AutoloopProvider Component
 */
export function AutoloopProvider({ children }) {
  // Map of running autoloops: { [id]: autoloopState }
  const [autoloops, setAutoloops] = useState({});
  
  // Refs to control execution (for stop functionality)
  const stopRefs = useRef({});
  
  /**
   * Start a new autoloop execution
   */
  const startAutoloop = useCallback(async (config) => {
    const {
      trades,
      orderType,
      loopRounds,
      onComplete,
      onError,
      strategyName = 'Position Adjustment',
    } = config;
    
    const id = generateAutoloopId();
    const isSSR = orderType.startsWith('ssr_');
    const ssrMode = SSR_MODE_MAP[orderType] || 'standard';
    
    // Initialize stop ref
    stopRefs.current[id] = false;
    
    // Initialize autoloop state
    const initialState = {
      id,
      strategyName,
      trades,
      orderType,
      totalRounds: loopRounds,
      currentRound: 0,
      status: 'starting', // 'starting', 'placing', 'waiting', 'round_complete', 'completed', 'stopped', 'error'
      startedAt: new Date().toISOString(),
      roundHistory: [],
      currentRoundOrders: [],
      error: null,
      totalOrdersPlaced: 0,
      totalOrdersFilled: 0,
    };
    
    setAutoloops(prev => ({ ...prev, [id]: initialState }));
    
    // Run execution in background
    executeAutoloopInBackground(id, {
      trades,
      orderType,
      loopRounds,
      isSSR,
      ssrMode,
      onComplete,
      onError,
    });
    
    return id;
  }, []);
  
  /**
   * Background execution function
   */
  const executeAutoloopInBackground = async (id, config) => {
    const { trades, orderType, loopRounds, isSSR, ssrMode, onComplete, onError } = config;
    
    const updateState = (updates) => {
      setAutoloops(prev => ({
        ...prev,
        [id]: { ...prev[id], ...updates }
      }));
    };
    
    try {
      const allRoundHistory = [];
      
      for (let round = 1; round <= loopRounds; round++) {
        // Check if stopped
        if (stopRefs.current[id]) {
          updateState({ 
            status: 'stopped', 
            error: `Stopped by user at round ${round - 1}/${loopRounds}` 
          });
          return;
        }
        
        updateState({ 
          currentRound: round, 
          status: 'placing',
          currentRoundOrders: trades.map(t => ({
            symbol: t.symbol,
            side: t.side,
            size: t.quantity || 1,
            status: 'placing',
            filled: false,
            orderId: null,
            fillPrice: null,
          })),
        });
        
        // Build orders for this round
        const roundOrders = trades.map((trade, idx) => ({
          symbol: trade.symbol,
          side: trade.side,
          size: trade.quantity || 1,
          premium: trade.premium || trade.ltp || 0,
          id: idx,
        }));
        
        console.log(`[Autoloop ${id}] Round ${round}/${loopRounds} - placing orders`);
        
        // Execute batch and wait for fills
        updateState({ status: 'waiting' });
        const results = await executeBatchWithPolling(id, roundOrders, isSSR, ssrMode, orderType, updateState);
        
        // Check if stopped during execution
        if (stopRefs.current[id]) {
          updateState({ 
            status: 'stopped', 
            error: `Stopped by user during round ${round}` 
          });
          return;
        }
        
        // Check if all orders filled
        const allFilled = Object.values(results).every(r => r.filled);
        
        if (!allFilled) {
          const unfilled = Object.entries(results)
            .filter(([_, r]) => !r.filled)
            .map(([symbol]) => symbol);
          
          console.log(`[Autoloop ${id}] Round ${round} - waiting for fills: ${unfilled.join(', ')}`);
          // Continue waiting - don't stop the autoloop
        }
        
        // Calculate round premium
        let roundPremium = 0;
        roundOrders.forEach(order => {
          const result = results[order.symbol];
          const price = result?.fillPrice || order.premium || 0;
          const multiplier = getContractMultiplier(order.symbol);
          if (order.side === 'sell') {
            roundPremium += price * order.size * multiplier;
          } else {
            roundPremium -= price * order.size * multiplier;
          }
        });
        
        // Record round history
        const roundData = {
          round,
          orders: roundOrders.map(o => ({
            ...o,
            ...results[o.symbol],
          })),
          netPremium: roundPremium,
          completedAt: new Date().toISOString(),
          allFilled,
        };
        allRoundHistory.push(roundData);
        
        const filledCount = Object.values(results).filter(r => r.filled).length;
        
        updateState({ 
          status: 'round_complete',
          roundHistory: [...allRoundHistory],
          totalOrdersPlaced: round * roundOrders.length,
          totalOrdersFilled: (updateState.totalOrdersFilled || 0) + filledCount,
          currentRoundOrders: roundOrders.map(o => ({
            ...o,
            ...results[o.symbol],
            status: results[o.symbol]?.filled ? 'filled' : 'pending',
          })),
        });
        
        console.log(`[Autoloop ${id}] Round ${round}/${loopRounds} complete`);
        
        // Wait before next round (if not last)
        if (round < loopRounds && !stopRefs.current[id]) {
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
      }
      
      // All rounds complete
      updateState({ 
        status: 'completed',
        completedAt: new Date().toISOString(),
      });
      
      console.log(`[Autoloop ${id}] All ${loopRounds} rounds completed`);
      onComplete?.({ id, roundHistory: allRoundHistory });
      
    } catch (err) {
      console.error(`[Autoloop ${id}] Error:`, err);
      updateState({ 
        status: 'error', 
        error: err.message || 'Execution failed' 
      });
      onError?.(err);
    }
  };
  
  /**
   * Execute batch and poll for fills - waits indefinitely until all filled or stopped
   */
  const executeBatchWithPolling = async (autoloopId, orders, isSSR, ssrMode, orderType, updateState) => {
    const results = {};
    const pendingOrders = [];
    
    if (isSSR) {
      // SSR: Place orders one by one
      for (const order of orders) {
        if (stopRefs.current[autoloopId]) break;
        
        try {
          const response = await api.post('/api/options/ssr-order', {
            symbol: order.symbol,
            side: order.side,
            quantity: order.size,
            ssrMode: ssrMode,
          });
          
          if (response.data.success) {
            const orderId = response.data.ssrTracking?.orderId || response.data.order?.id;
            results[order.symbol] = { 
              filled: false, 
              orderId, 
              size: order.size,
              status: 'pending',
            };
            if (orderId) {
              pendingOrders.push({ symbol: order.symbol, orderId });
            }
            
            // Update UI
            updateState({
              currentRoundOrders: orders.map(o => ({
                ...o,
                status: results[o.symbol] ? 'punched' : 'placing',
                orderId: results[o.symbol]?.orderId,
                filled: false,
              })),
            });
          } else {
            results[order.symbol] = { 
              filled: false, 
              error: response.data.error,
              status: 'failed',
            };
          }
        } catch (err) {
          results[order.symbol] = { 
            filled: false, 
            error: err.message,
            status: 'failed',
          };
        }
      }
    } else {
      // Non-SSR: Batch add
      try {
        const response = await api.post('/api/options/batch_add', {
          orders,
          order_preference: orderType,
          confirm: true,
        });
        
        if (!response.data.success) {
          throw new Error(response.data.error || 'Batch order failed');
        }
        
        const apiResults = response.data.results || [];
        
        apiResults.forEach((result) => {
          const execType = result.execution_type || '';
          const isFilled = ['market', 'market_fallback', 'market_fallback_no_quotes', 'limit_filled', 'limit_filled_late'].includes(execType) || !result.order_id;
          
          results[result.symbol] = {
            filled: isFilled,
            size: result.size,
            orderId: result.order_id,
            fillPrice: result.fill_price,
            status: isFilled ? 'filled' : 'pending',
          };
          
          if (result.success && !isFilled && result.order_id) {
            pendingOrders.push({ symbol: result.symbol, orderId: result.order_id });
          }
        });
        
        // Update UI
        updateState({
          currentRoundOrders: orders.map(o => ({
            ...o,
            ...results[o.symbol],
          })),
        });
        
      } catch (err) {
        throw err;
      }
    }
    
    // Poll for pending orders - WAIT INDEFINITELY until all filled or stopped
    if (pendingOrders.length > 0) {
      const orderIds = pendingOrders.map(o => o.orderId).filter(Boolean);
      
      if (orderIds.length > 0) {
        console.log(`[Autoloop] Polling ${orderIds.length} orders: ${orderIds.join(', ')}`);
        
        let allFilled = false;
        let pollCount = 0;
        
        // Poll indefinitely (check every 3 seconds)
        while (!allFilled && !stopRefs.current[autoloopId]) {
          pollCount++;
          await new Promise(resolve => setTimeout(resolve, 3000));
          
          try {
            const statusResponse = await api.post('/api/options/batch_order_status', {
              order_ids: orderIds,
            });
            
            if (statusResponse.data.success) {
              const statuses = statusResponse.data.orders || [];
              
              statuses.forEach((status) => {
                const matching = pendingOrders.find(o => String(o.orderId) === String(status.order_id));
                if (matching) {
                  const isFilled = status.state === 'filled' || status.state === 'closed';
                  const isCancelled = status.state === 'cancelled' || status.state === 'rejected';
                  
                  if (isFilled) {
                    results[matching.symbol] = {
                      ...results[matching.symbol],
                      filled: true,
                      fillPrice: status.fill_price,
                      status: 'filled',
                    };
                  } else if (isCancelled) {
                    results[matching.symbol] = {
                      ...results[matching.symbol],
                      filled: false,
                      status: 'cancelled',
                    };
                  }
                }
              });
              
              // Update UI with current status
              updateState({
                currentRoundOrders: orders.map(o => ({
                  ...o,
                  ...results[o.symbol],
                })),
              });
              
              // Check if all done
              const filledOrCancelled = pendingOrders.every(o => 
                results[o.symbol]?.filled || results[o.symbol]?.status === 'cancelled'
              );
              allFilled = filledOrCancelled;
              
              const filledCount = pendingOrders.filter(o => results[o.symbol]?.filled).length;
              console.log(`[Autoloop] Poll ${pollCount}: ${filledCount}/${pendingOrders.length} filled`);
            }
          } catch (pollErr) {
            console.error('[Autoloop] Poll error:', pollErr);
          }
        }
      }
    }
    
    return results;
  };
  
  /**
   * Stop a running autoloop
   */
  const stopAutoloop = useCallback((id) => {
    if (stopRefs.current[id] !== undefined) {
      stopRefs.current[id] = true;
      setAutoloops(prev => ({
        ...prev,
        [id]: { ...prev[id], status: 'stopping' }
      }));
    }
  }, []);
  
  /**
   * Remove a completed/stopped autoloop from the list
   */
  const removeAutoloop = useCallback((id) => {
    setAutoloops(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    delete stopRefs.current[id];
  }, []);
  
  /**
   * Get active (running) autoloops
   */
  const getActiveAutoloops = useCallback(() => {
    return Object.values(autoloops).filter(a => 
      ['starting', 'placing', 'waiting', 'round_complete', 'stopping'].includes(a.status)
    );
  }, [autoloops]);
  
  /**
   * Get all autoloops
   */
  const getAllAutoloops = useCallback(() => {
    return Object.values(autoloops);
  }, [autoloops]);
  
  const value = {
    autoloops,
    startAutoloop,
    stopAutoloop,
    removeAutoloop,
    getActiveAutoloops,
    getAllAutoloops,
  };
  
  return (
    <AutoloopContext.Provider value={value}>
      {children}
    </AutoloopContext.Provider>
  );
}

/**
 * Hook to use autoloop context
 */
export function useAutoloop() {
  const context = useContext(AutoloopContext);
  if (!context) {
    throw new Error('useAutoloop must be used within an AutoloopProvider');
  }
  return context;
}

export default AutoloopContext;
