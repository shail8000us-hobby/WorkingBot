import ConnectionManager from './connectionManager';

/**
 * Robust Connection Manager with Auto-Recovery
 * Handles network failures, auto-reconnect with exponential backoff
 */
class RobustConnectionManager extends ConnectionManager {
  constructor(options = {}) {
    super(options);

    // Recovery settings - mobile-optimized
    this.retryAttempts = 0;
    this.maxRetries = options.maxRetries || 20; // Increased from 10 for mobile networks
    this.retryDelay = options.retryDelay || 1000; // Start with 1 second
    this.maxRetryDelay = options.maxRetryDelay || options.maxReconnectDelay || 60000; // Increased from 30s to 60s for mobile
    this.reconnectOnClose = options.reconnectOnClose !== false;
    this.boundSocket = null;
    this.hasConnectedOnce = false;

    // Ping/Pong for connection health - mobile-optimized
    this.pingInterval = null;
    this.pingTimeoutHandle = null;
    this.lastPingTime = null;
    this.lastPongTime = null;
    this.pingTimeout = options.pingTimeout || 10000; // Increased from 5s to 10s for mobile latency

    // Connection quality tracking
    this.connectionQuality = 'unknown';
    this.latencyHistory = [];
    this.maxLatencyHistory = 10;

    // Mobile-specific: track network changes
    this.isOnline = navigator.onLine;
    this.setupNetworkMonitoring();
  }

  connect() {
    console.log('🔵 RobustConnectionManager: Initiating connection...');
    this.reconnectOnClose = true;
    this.retryAttempts = 0;
    this.clearReconnectTimer();
    this.establishConnection();
  }

  establishConnection() {
    try {
      super.connect();
      this.setupConnectionHandlers();
    } catch (error) {
      console.error('🔴 Connection error:', error);
      this.handleConnectionError(error);
    }
  }

  setupConnectionHandlers() {
    if (!this.socket || this.boundSocket === this.socket) return;
    this.boundSocket = this.socket;

    this.socket.on('connect', () => {
      const attemptsBeforeSuccess = this.retryAttempts;
      this.clearReconnectTimer();
      this.retryAttempts = 0;
      this.startPingPong();

      if (this.connectionQuality !== 'good') {
        this.connectionQuality = 'good';
        this.emit('connection_quality', { quality: 'good' });
      }

      if (this.hasConnectedOnce && attemptsBeforeSuccess > 0) {
        this.emit('reconnected', { attempts: attemptsBeforeSuccess });
      }
      this.hasConnectedOnce = true;
    });

    // Handle disconnect
    this.socket.on('disconnect', (reason) => {
      console.warn('⚠️  Disconnected:', reason);
      this.stopPingPong();
      this.connectionQuality = 'disconnected';
      this.emit('connection_quality', { quality: 'disconnected', reason });
    });

    // Handle pong
    this.socket.on('pong', () => {
      if (this.lastPingTime == null) {
        return;
      }
      this.lastPongTime = Date.now();
      const latency = this.lastPongTime - this.lastPingTime;
      this.trackLatency(latency);
    });

    // Handle connect error
    this.socket.on('connect_error', (error) => {
      this.connectionQuality = 'poor';
      this.emit('connection_quality', {
        quality: 'poor',
        error: error?.message || String(error),
      });
    });
  }

  clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  handleConnectionError(error) {
    if (!this.reconnectOnClose) {
      return;
    }

    if (this.reconnectTimer) {
      return;
    }

    if (this.retryAttempts >= this.maxRetries) {
      console.error('❌ Max retries reached');
      this.emit('connection_failed', {
        message: 'Max retries reached',
        retries: this.retryAttempts,
        error: error.message,
      });
      this.connectionQuality = 'failed';
      return;
    }

    this.retryAttempts++;
    const delay = Math.min(
      this.retryDelay * Math.pow(2, this.retryAttempts - 1),
      this.maxRetryDelay
    );

    console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.retryAttempts}/${this.maxRetries})`);

    this.emit('connection_retry', {
      attempt: this.retryAttempts,
      maxRetries: this.maxRetries,
      delay: delay,
    });

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.establishConnection();
    }, delay);
  }

  scheduleReconnect() {
    this.handleConnectionError(new Error('Connection lost'));
  }

  startPingPong() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }
    if (this.pingTimeoutHandle) {
      clearTimeout(this.pingTimeoutHandle);
      this.pingTimeoutHandle = null;
    }

    this.pingInterval = setInterval(() => {
      if (this.socket?.connected) {
        this.lastPingTime = Date.now();
        this.socket.emit('ping', { timestamp: this.lastPingTime });

        // Cancel any previous timeout before scheduling a new one
        if (this.pingTimeoutHandle) {
          clearTimeout(this.pingTimeoutHandle);
        }

        // Check for pong timeout
        this.pingTimeoutHandle = setTimeout(() => {
          this.pingTimeoutHandle = null;
          if (this.lastPongTime < this.lastPingTime) {
            const timeSincePing = Date.now() - this.lastPingTime;
            if (timeSincePing > this.pingTimeout) {
              console.warn('⚠️  Ping timeout, connection may be dead');
              this.connectionQuality = 'poor';
              this.emit('connection_quality', { quality: 'poor', latency: timeSincePing });
              // Don't force reconnect here — let the disconnect handler do it
              // to avoid duplicate reconnection attempts
            }
          }
        }, this.pingTimeout);
      }
    }, 30000); // Ping every 30 seconds (was 10s — too aggressive)
  }

  stopPingPong() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.pingTimeoutHandle) {
      clearTimeout(this.pingTimeoutHandle);
      this.pingTimeoutHandle = null;
    }
  }

  trackLatency(latency) {
    this.latencyHistory.push(latency);
    if (this.latencyHistory.length > this.maxLatencyHistory) {
      this.latencyHistory.shift();
    }

    const avgLatency = this.latencyHistory.reduce((a, b) => a + b, 0) / this.latencyHistory.length;

    // Determine connection quality
    let quality = 'excellent';
    if (avgLatency > 500) quality = 'poor';
    else if (avgLatency > 200) quality = 'fair';
    else if (avgLatency > 100) quality = 'good';

    if (this.connectionQuality !== quality) {
      this.connectionQuality = quality;
      this.emit('connection_quality', { quality, latency: avgLatency });
    }
  }

  getConnectionStatus() {
    return {
      connected: this.socket?.connected || false,
      quality: this.connectionQuality,
      retryAttempts: this.retryAttempts,
      avgLatency:
        this.latencyHistory.length > 0
          ? Math.round(this.latencyHistory.reduce((a, b) => a + b, 0) / this.latencyHistory.length)
          : null,
    };
  }

  disconnect() {
    console.log('🔴 Manually disconnecting...');
    this.reconnectOnClose = false; // Prevent auto-reconnect
    this.stopPingPong();
    this.clearReconnectTimer();
    this.cleanupNetworkMonitoring();
    this.boundSocket = null;
    super.disconnect();
  }

  forceReconnect() {
    console.log('🔄 Force reconnecting...');
    this.reconnectOnClose = true;
    this.retryAttempts = 0;
    this.stopPingPong();
    this.stopHeartbeat();
    this.stopSync();
    this.clearReconnectTimer();
    this.boundSocket = null;
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
    this.establishConnection();
  }

  /**
   * Setup network monitoring for mobile devices
   * Automatically reconnect when network becomes available
   */
  setupNetworkMonitoring() {
    // Store bound handlers so we can remove them later
    this._onOnline = () => {
      this.isOnline = true;
      this.emit('network_status', { online: true });
      if (!this.socket?.connected) {
        this.retryAttempts = 0;
        setTimeout(() => this.forceReconnect(), 1000);
      }
    };

    this._onOffline = () => {
      this.isOnline = false;
      this.emit('network_status', { online: false });
      this.connectionQuality = 'offline';
    };

    this._onVisibility = () => {
      if (!document.hidden && this.isOnline && !this.socket?.connected) {
        setTimeout(() => {
          if (!this.socket?.connected) {
            this.forceReconnect();
          }
        }, 500);
      }
    };

    this._onResume = () => {
      if (this.isOnline && !this.socket?.connected) {
        setTimeout(() => this.forceReconnect(), 1000);
      }
    };

    window.addEventListener('online', this._onOnline);
    window.addEventListener('offline', this._onOffline);
    document.addEventListener('visibilitychange', this._onVisibility);
    window.addEventListener('resume', this._onResume);
  }

  /**
   * Cleanup network monitoring listeners
   */
  cleanupNetworkMonitoring() {
    if (this._onOnline) window.removeEventListener('online', this._onOnline);
    if (this._onOffline) window.removeEventListener('offline', this._onOffline);
    if (this._onVisibility) document.removeEventListener('visibilitychange', this._onVisibility);
    if (this._onResume) window.removeEventListener('resume', this._onResume);
  }
}

export default RobustConnectionManager;
