/**
 * Data Aggregator for v2 WebUI
 * 
 * Polls real data from backend every 2 seconds and updates stores.
 * Based on v1's dataAggregator pattern but adapted for Zustand stores.
 */

import { getInstrumentStore } from '../stores/instrumentStore';
import { useGlobalStore } from '../stores/globalStore';
import type { InstanceId, Position, Order, PnL } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5555';

class DataAggregator {
  private interval: ReturnType<typeof setInterval> | null = null;
  private isRunning = false;
  private pollInterval = 2000; // 2 seconds
  private consecutiveErrors = 0;
  private maxConsecutiveErrors = 5;
  private currentInstance: string | null = null;

  /**
   * Start the data aggregator
   */
  start(instance?: string): void {
    if (this.isRunning && !instance) {
      console.log('📡 [v2] Data aggregator already running');
      return;
    }

    // If instance provided and different, switch to it
    if (instance && instance !== this.currentInstance) {
      this.currentInstance = instance;
    }

    this.isRunning = true;
    this.consecutiveErrors = 0;
    console.log(`📡 [v2] Data aggregator started (polling every 2s) for ${this.currentInstance || 'all instances'}`);

    // Clear existing interval
    if (this.interval) {
      clearInterval(this.interval);
    }

    // Start polling loop
    this.interval = setInterval(() => {
      this.fetchAllData();
    }, this.pollInterval);

    // Immediate first fetch
    this.fetchAllData();
  }

  /**
   * Switch to a specific instance
   */
  switchInstance(instance: string): void {
    console.log(`📡 [v2] Switching to instance: ${instance}`);
    this.currentInstance = instance;
    // Immediate fetch for new instance
    this.fetchAllData();
  }

  /**
   * Get current instance
   */
  getCurrentInstance(): string | null {
    return this.currentInstance;
  }

  /**
   * Stop the data aggregator
   */
  stop(): void {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
      this.isRunning = false;
      console.log('📡 [v2] Data aggregator stopped');
    }
  }

  /**
   * Fetch all data in parallel
   */
  async fetchAllData(): Promise<void> {
    const instances = useGlobalStore.getState().instances;
    
    if (instances.length === 0) {
      return;
    }

    try {
      // Fetch global data
      const [positionsRes, ordersRes, healthRes, botStatusRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/api/positions`).then(r => r.json()),
        fetch(`${API_BASE_URL}/api/orders`).then(r => r.json()),
        fetch(`${API_BASE_URL}/api/health`).then(r => r.json()),
        fetch(`${API_BASE_URL}/api/bot/status`).then(r => r.json()),
      ]);

      // Process positions by symbol
      if (positionsRes.status === 'fulfilled' && positionsRes.value?.positions) {
        this.updatePositions(positionsRes.value.positions, positionsRes.value.summary);
      }

      // Process orders by symbol
      if (ordersRes.status === 'fulfilled' && ordersRes.value?.orders) {
        this.updateOrders(ordersRes.value.orders);
      }

      // Update health
      if (healthRes.status === 'fulfilled') {
        const health = healthRes.value;
        useGlobalStore.getState().updateSystemHealth({
          backend: health.status === 'healthy' ? 'healthy' : 'degraded',
          database: 'healthy',
          exchange: 'healthy',
        });
      }

      // Update bot status - determines heartbeat
      if (botStatusRes.status === 'fulfilled') {
        this.updateBotStatus(botStatusRes.value);
      }

      this.consecutiveErrors = 0;

    } catch (error) {
      console.error('❌ [v2] Data aggregation failed:', error);
      this.consecutiveErrors++;

      if (this.consecutiveErrors >= this.maxConsecutiveErrors) {
        console.error(`❌ [v2] Data aggregator stopping after ${this.consecutiveErrors} errors`);
        this.stop();
      }
    }
  }

  /**
   * Update positions in instrument stores
   */
  private updatePositions(positions: any[], summary: any): void {
    const instances = useGlobalStore.getState().instances;
    
    // Group positions by symbol
    const positionsBySymbol: Record<string, any[]> = {};
    for (const pos of positions) {
      const symbol = pos.symbol || 'UNKNOWN';
      if (!positionsBySymbol[symbol]) {
        positionsBySymbol[symbol] = [];
      }
      positionsBySymbol[symbol].push(pos);
    }

    // Update each instrument store
    for (const instanceId of instances) {
      const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
      const mode = instanceId.includes('_LONG') ? 'long' : 'short';
      
      try {
        const store = getInstrumentStore(instanceId);
        const symbolPositions = positionsBySymbol[symbol] || [];
        
        // Filter positions by mode
        const modePositions = symbolPositions.filter(p => 
          p.side?.toLowerCase() === mode
        );

        // Transform to our Position type (matches types/index.ts)
        const transformedPositions: Position[] = modePositions.map(p => ({
          id: `${p.symbol}_${p.side}_${Date.now()}`,
          symbol: p.symbol || symbol,
          side: (p.side?.toUpperCase() === 'LONG' ? 'LONG' : 'SHORT') as 'LONG' | 'SHORT',
          size: p.size || 0,
          entryPrice: p.entry_price || 0,
          currentPrice: p.current_price || 0,
          unrealizedPnl: p.unrealized_pnl || 0,
          unrealizedPnlPercent: p.entry_price > 0 
            ? ((p.current_price - p.entry_price) / p.entry_price) * 100 
            : 0,
          openedAt: Date.now(),
        }));

        store.getState().updatePositions(transformedPositions);

        // Update PnL from summary
        if (summary && modePositions.length > 0) {
          const totalUnrealized = modePositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
          store.getState().updatePnL({
            realized: 0,
            unrealized: totalUnrealized,
            total: totalUnrealized,
            todayRealized: 0,
            todayUnrealized: totalUnrealized,
            todayTotal: totalUnrealized,
          });
        }
      } catch (e) {
        // Store might not exist
      }
    }
  }

  /**
   * Update orders in instrument stores
   */
  private updateOrders(orders: any[]): void {
    const instances = useGlobalStore.getState().instances;
    
    // Get product_id mapping from symbols endpoint (cached)
    // For now, update all instances with relevant orders
    
    for (const instanceId of instances) {
      try {
        const store = getInstrumentStore(instanceId);
        
        // Transform orders to our format (matches types/index.ts)
        const transformedOrders: Order[] = orders
          .filter(o => o.state === 'open' || o.state === 'pending')
          .slice(0, 20) // Limit to 20 orders per instrument
          .map(o => ({
            id: String(o.id),
            symbol: o.product_id?.replace('_PERP', '') || instanceId.replace(/_LONG|_SHORT/g, ''),
            side: (o.side?.toUpperCase() === 'BUY' ? 'BUY' : 'SELL') as 'BUY' | 'SELL',
            type: (o.order_type?.includes('limit') ? 'LIMIT' : 'MARKET') as 'LIMIT' | 'MARKET' | 'STOP',
            price: o.price || 0,
            size: o.size || 0,
            filledSize: o.filled_size || 0,
            status: o.state === 'open' ? 'open' : 'pending' as 'pending' | 'open' | 'filled' | 'cancelled' | 'rejected',
            createdAt: new Date(o.created_at).getTime() || Date.now(),
            updatedAt: new Date(o.updated_at || o.created_at).getTime() || Date.now(),
          }));

        store.getState().updateOrders(transformedOrders);
      } catch (e) {
        // Store might not exist
      }
    }
  }

  /**
   * Update bot status (heartbeat, guardian, trading)
   */
  private updateBotStatus(status: any): void {
    const instances = useGlobalStore.getState().instances;
    const isRunning = status.running === true;
    
    for (const instanceId of instances) {
      try {
        const store = getInstrumentStore(instanceId);
        
        // Update heartbeat based on bot running status
        if (isRunning) {
          store.getState().updateHeartbeat('alive');
          store.getState().updateGuardian('permitting');
          store.getState().updateTradingIntent('active');
        } else {
          store.getState().updateHeartbeat('dead', 'Bot process not running');
          store.getState().updateTradingIntent('paused');
        }

        // Update connection state
        store.getState().setConnectionState('connected');
      } catch (e) {
        // Store might not exist
      }
    }
  }

  /**
   * Manual refresh
   */
  async refresh(): Promise<void> {
    if (!this.isRunning) {
      this.start();
    } else {
      await this.fetchAllData();
    }
  }

  /**
   * Get status
   */
  getStatus() {
    return {
      isRunning: this.isRunning,
      pollInterval: this.pollInterval,
      consecutiveErrors: this.consecutiveErrors,
    };
  }
}

// Singleton instance
export const dataAggregator = new DataAggregator();
