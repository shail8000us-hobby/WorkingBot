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
    this.maxRetryDelay = options.maxRetryDelay || 60000; // Increased from 30s to 60s for mobile
    this.reconnectOnClose = options.reconnectOnClose !== false;

    // Ping/Pong for connection health - mobile-optimized
    this.pingInterval = null;
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
    this.retryAttempts = 0;
    this.establishConnection();
  }

  establishConnection() {
    try {
      super.connect();
      this.setupConnectionHandlers();
      this.startPingPong();
      this.resetRetryDelay();
      this.emit('connection_quality', { quality: 'good' });
    } catch (error) {
      console.error('🔴 Connection error:', error);
      this.handleConnectionError(error);
    }
  }

  setupConnectionHandlers() {
    if (!this.socket) return;

    // Handle disconnect
    this.socket.on('disconnect', (reason) => {
      console.warn('⚠️  Disconnected:', reason);
      this.stopPingPong();
      this.connectionQuality = 'disconnected';
      this.emit('connection_quality', { quality: 'disconnected', reason });

      if (this.reconnectOnClose && reason !== 'io client disconnect') {
        this.handleConnectionError(new Error('Disconnected: ' + reason));
      }
    });

    // Handle reconnect
    this.socket.on('reconnect', (attemptNumber) => {
      console.log('✅ Reconnected after', attemptNumber, 'attempts');
      this.retryAttempts = 0;
      this.startPingPong();
      this.emit('reconnected', { attempts: attemptNumber });
    });

    // Handle reconnect attempt
    this.socket.on('reconnect_attempt', (attemptNumber) => {
      console.log('🔄 Reconnect attempt', attemptNumber);
      this.emit('reconnecting', { attempt: attemptNumber });
    });

    // Handle pong
    this.socket.on('pong', () => {
      this.lastPongTime = Date.now();
      const latency = this.lastPongTime - this.lastPingTime;
      this.trackLatency(latency);
    });

    // Handle connect error
    this.socket.on('connect_error', (error) => {
      console.error('🔴 Connect error:', error);
      this.handleConnectionError(error);
    });
  }

  handleConnectionError(error) {
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

    setTimeout(() => this.establishConnection(), delay);
  }

  startPingPong() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }

    this.pingInterval = setInterval(() => {
      if (this.socket?.connected) {
        this.lastPingTime = Date.now();
        this.socket.emit('ping', { timestamp: this.lastPingTime });

        // Check for pong timeout
        setTimeout(() => {
          if (this.lastPongTime < this.lastPingTime) {
            const timeSincePing = Date.now() - this.lastPingTime;
            if (timeSincePing > this.pingTimeout) {
              console.warn('⚠️  Ping timeout, connection may be dead');
              this.connectionQuality = 'poor';
              this.emit('connection_quality', { quality: 'poor', latency: timeSincePing });

              // Force reconnect
              this.socket.disconnect();
              this.establishConnection();
            }
          }
        }, this.pingTimeout);
      }
    }, 10000); // Ping every 10 seconds
  }

  stopPingPong() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
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

  resetRetryDelay() {
    this.retryAttempts = 0;
    this.retryDelay = 1000;
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
    if (this.socket) {
      this.socket.disconnect();
    }
  }

  forceReconnect() {
    console.log('🔄 Force reconnecting...');
    this.reconnectOnClose = true;
    this.retryAttempts = 0;
    if (this.socket?.connected) {
      this.socket.disconnect();
    }
    this.establishConnection();
  }

  /**
   * Setup network monitoring for mobile devices
   * Automatically reconnect when network becomes available
   */
  setupNetworkMonitoring() {
    // Monitor online/offline events
    window.addEventListener('online', () => {
      console.log('📶 Network online - attempting reconnection');
      this.isOnline = true;
      this.emit('network_status', { online: true });

      // Force reconnect when network comes back
      if (!this.socket?.connected) {
        this.retryAttempts = 0; // Reset retry counter
        setTimeout(() => this.forceReconnect(), 1000);
      }
    });

    window.addEventListener('offline', () => {
      console.log('📵 Network offline');
      this.isOnline = false;
      this.emit('network_status', { online: false });
      this.connectionQuality = 'offline';
    });

    // Monitor visibility changes (mobile screen lock/unlock)
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.isOnline && !this.socket?.connected) {
        console.log('👁️  App became visible - checking connection');
        // Check connection after app becomes visible (e.g., screen unlock)
        setTimeout(() => {
          if (!this.socket?.connected) {
            console.log('🔄 Connection lost while app was hidden - reconnecting');
            this.forceReconnect();
          }
        }, 500);
      }
    });

    // Mobile-specific: resume event for iOS
    window.addEventListener('resume', () => {
      console.log('▶️  App resumed from background');
      if (this.isOnline && !this.socket?.connected) {
        setTimeout(() => this.forceReconnect(), 1000);
      }
    });
  }
}

export default RobustConnectionManager;
