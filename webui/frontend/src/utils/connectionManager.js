/**
 * Connection Manager - Robust WebSocket connection handling
 * Provides automatic reconnection, state synchronization, and health monitoring
 */

import { io } from 'socket.io-client';

// Use port 5555 as default (matches config.yaml webui.port)
// For development with different ports, set REACT_APP_SOCKET_URL in .env
// Use window.location.origin to avoid cross-origin issues when accessing via LAN/Tailscale
const DEFAULT_SOCKET_URL =
  (process.env.REACT_APP_SOCKET_URL || '').trim() ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5555');
const DEFAULT_API_BASE_URL =
  (process.env.REACT_APP_API_BASE_URL || '').trim().replace(/\/$/, '') ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5555');

class ConnectionManager {
  constructor(config = {}) {
    this.config = {
      reconnectDelay: 1000,
      maxReconnectDelay: 30000,
      reconnectAttempts: Infinity,
      heartbeatInterval: 30000,
      syncInterval: 60000,
      socketUrl: config.socketUrl !== undefined ? config.socketUrl : DEFAULT_SOCKET_URL,
      apiBaseUrl: config.apiBaseUrl !== undefined ? config.apiBaseUrl : DEFAULT_API_BASE_URL,
      ...config,
    };

    this.socket = null;
    this.connectionState = 'disconnected'; // disconnected, connecting, connected, error
    this.reconnectAttempt = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.syncTimer = null;
    this.lastHeartbeat = null;
    this.listeners = new Map();
    this.stateCache = {};
    this.pendingRequests = new Map();
  }

  /**
   * Initialize connection
   */
  connect(socketIOConfig = {}) {
    if (this.socket && this.socket.connected) {
      console.log('🔵 Already connected');
      return;
    }

    // Destroy previous socket before creating a new one.
    // Without this, each reconnect attempt leaves the old socket alive and polling,
    // causing multiple concurrent polling loops that flood the console with errors
    // (e.g. 250+ "xhr poll error" entries during a 17-second backend restart).
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }

    console.log('🔵 Initializing connection...');
    this.setConnectionState('connecting');

    const connectionOptions = {
      path: '/socket.io',
      // Backend uses threading mode; WebSocket upgrade returns HTTP 500 (Werkzeug 3.x compat issue).
      // Polling works correctly and delivers all real-time data without the repeated upgrade errors.
      transports: ['polling'],
      // We handle reconnection manually for better control
      reconnection: false,
      // Mobile-optimized: increased timeout for high-latency networks (Tailscale/cellular)
      timeout: 60000, // Increased from 20s to 60s for mobile networks
      // NOTE: Do NOT set withCredentials or custom extraHeaders —
      // they trigger CORS preflight and block connections
      ...socketIOConfig,
    };

    // Always provide explicit URL from config (defaults to port 5555)
    const socketUrl = this.config.socketUrl || DEFAULT_SOCKET_URL;
    console.log('🔵 Connecting to:', socketUrl);

    this.socket = io(socketUrl, connectionOptions);
    this.setupSocketListeners();
  }

  /**
   * Setup socket event listeners
   */
  setupSocketListeners() {
    // Connection events
    this.socket.on('connect', () => {
      console.log('✅ Socket connected');
      this.reconnectAttempt = 0;
      this.setConnectionState('connected');
      this.startHeartbeat();
      this.startSync();
      this.emit('connection', { status: 'connected' });
    });

    this.socket.on('disconnect', (reason) => {
      console.log('❌ Socket disconnected:', reason);
      this.setConnectionState('disconnected');
      this.stopHeartbeat();
      this.stopSync();
      this.emit('connection', { status: 'disconnected', reason });

      // Attempt reconnection for client-side disconnects
      if (reason === 'io client disconnect') {
        // Manual disconnect, don't reconnect
        return;
      }
      this.scheduleReconnect();
    });

    this.socket.on('connect_error', (error) => {
      // Suppress noisy transport errors — socket.io-client already logs these internally;
      // duplicating them doubles the console noise for no gain.
      const errorMsg = error?.message || String(error);
      const isSilent =
        errorMsg.includes('Invalid frame header') ||
        errorMsg.includes('websocket error') ||
        errorMsg.includes('xhr poll error') ||
        errorMsg.includes('xhr post error');
      if (!isSilent) {
        console.error('❌ Connection error:', error);
      }
      this.setConnectionState('error');
      this.emit('connection', { status: 'error', error: error.message });
      this.scheduleReconnect();
    });

    // Data sync events
    this.socket.on('config_updated', (data) => {
      this.stateCache.config = data;
      this.emit('config_updated', data);
    });

    this.socket.on('bot_status', (data) => {
      this.stateCache.botStatus = data;
      this.emit('bot_status', data);
    });

    this.socket.on('positions_update', (data) => {
      this.stateCache.positions = data;
      this.emit('positions_update', data);
    });

    this.socket.on('log_entry', (data) => {
      this.emit('log_entry', data);
    });

    this.socket.on('log_batch', (data) => {
      this.emit('log_batch', data);
    });

    this.socket.on('error', (data) => {
      console.error('⚠️ Server error:', data);
      this.emit('error', data);
    });

    this.socket.on('reconciliation_update', (data) => {
      this.emit('reconciliation_update', data);
    });

    this.socket.on('orders_memory_update', (data) => {
      this.stateCache.ordersMemory = data;
      this.emit('orders_memory_update', data);
    });

    // Heartbeat response
    this.socket.on('pong', (data) => {
      this.lastHeartbeat = Date.now();
      this.emit('heartbeat', { latency: data.latency, timestamp: this.lastHeartbeat });
    });
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectTimer) {
      return; // Already scheduled
    }

    const delay = Math.min(
      this.config.reconnectDelay * Math.pow(1.5, this.reconnectAttempt),
      this.config.maxReconnectDelay
    );

    console.log(`⏳ Reconnecting in ${delay}ms (attempt ${this.reconnectAttempt + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempt++;
      this.connect();
    }, delay);
  }

  /**
   * Start heartbeat monitoring
   */
  startHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    this.lastHeartbeat = Date.now();

    this.heartbeatTimer = setInterval(() => {
      if (!this.socket || !this.socket.connected) {
        return;
      }

      const start = Date.now();
      this.socket.emit('ping', { timestamp: start }, (response) => {
        const latency = Date.now() - start;
        this.lastHeartbeat = Date.now();
        this.emit('heartbeat', { latency, timestamp: this.lastHeartbeat });
      });

      // Check if heartbeat is stale (more than 2x the interval)
      if (Date.now() - this.lastHeartbeat > this.config.heartbeatInterval * 2) {
        console.warn('⚠️ Heartbeat timeout - connection may be stale');
        this.emit('heartbeat_timeout', { lastHeartbeat: this.lastHeartbeat });
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * Stop heartbeat monitoring
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Start periodic state synchronization
   */
  startSync() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
    }

    this.syncTimer = setInterval(() => {
      this.syncState();
    }, this.config.syncInterval);

    // Do initial sync
    this.syncState();
  }

  /**
   * Stop periodic state synchronization
   */
  stopSync() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
  }

  /**
   * Synchronize state with backend
   */
  async syncState() {
    if (!this.isConnected()) {
      return;
    }

    const buildApiUrl = (path) => {
      const trimmedPath = path.startsWith('/') ? path : `/${path}`;
      if (!this.config.apiBaseUrl) {
        return trimmedPath;
      }
      return `${this.config.apiBaseUrl}${trimmedPath}`;
    };

    try {
      // Import API shim dynamically to avoid CommonJS/ES6 module conflicts
      const { default: api } = await import('./apiShim');

      const [configRes, statusRes] = await Promise.all([
        api.get(buildApiUrl('/api/config')),
        api.get(buildApiUrl('/api/bot/status')),
      ]);

      // Check for differences and emit updates
      if (JSON.stringify(this.stateCache.config) !== JSON.stringify(configRes.data)) {
        this.stateCache.config = configRes.data;
        this.emit('config_updated', configRes.data);
      }

      if (JSON.stringify(this.stateCache.botStatus) !== JSON.stringify(statusRes.data)) {
        this.stateCache.botStatus = statusRes.data;
        this.emit('bot_status', statusRes.data);
      }

      this.emit('sync_complete', { timestamp: Date.now() });
    } catch (error) {
      console.error('❌ State sync failed:', error);
      this.emit('sync_error', { error: error.message });
    }
  }

  /**
   * Set connection state and emit event
   */
  setConnectionState(state) {
    const oldState = this.connectionState;
    this.connectionState = state;

    if (oldState !== state) {
      this.emit('connection_state_changed', { oldState, newState: state });
    }
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.socket && this.socket.connected && this.connectionState === 'connected';
  }

  /**
   * Get connection state
   */
  getConnectionState() {
    return {
      state: this.connectionState,
      connected: this.isConnected(),
      reconnectAttempt: this.reconnectAttempt,
      lastHeartbeat: this.lastHeartbeat,
    };
  }

  /**
   * Register event listener
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
  }

  /**
   * Unregister event listener
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Emit event to registered listeners
   */
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in ${event} listener:`, error);
        }
      });
    }
  }

  /**
   * Disconnect and cleanup
   */
  disconnect() {
    console.log('🔴 Disconnecting...');

    this.stopHeartbeat();
    this.stopSync();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    this.setConnectionState('disconnected');
  }

  /**
   * Get cached state
   */
  getState(key) {
    return this.stateCache[key];
  }

  /**
   * Force reconnection
   */
  forceReconnect() {
    console.log('🔄 Forcing reconnection...');
    this.reconnectAttempt = 0;
    this.disconnect();
    setTimeout(() => this.connect(), 100);
  }
}

export default ConnectionManager;
